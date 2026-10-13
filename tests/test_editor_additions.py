import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from src.core.element import ThemeElement
from src.ui.main_window import ThemeEditorWindow
from src.ui.onboarding import SetupWizard
from src.ui.properties import PropertiesPanel
from src.utils import settings
from src.core import constants

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def isolated_settings(monkeypatch):
    monkeypatch.setattr(settings, "_settings", {
        **settings.DEFAULT_SETTINGS, "onboarding_completed": True, "check_for_updates": False,
    })
    monkeypatch.setattr(settings, "save_settings", lambda: None)


@pytest.fixture
def window(monkeypatch, isolated_settings):
    monkeypatch.setattr(ThemeEditorWindow, "setup_console", lambda self: None)
    monkeypatch.setattr(ThemeEditorWindow, "_start_profile_monitors", lambda self: None)
    monkeypatch.setattr(ThemeEditorWindow, "auto_connect", lambda self: None)
    editor = ThemeEditorWindow()
    old_size = (constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT)
    yield editor
    editor.disconnect_display()
    for timer in editor.findChildren(QTimer):
        timer.stop()
    editor.deleteLater()
    APP.processEvents()
    constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT = old_size


def test_connection_button_displays_state_and_uses_existing_toggle(window, monkeypatch):
    window.update_performance_stats()
    assert "Disconnected" in window.perf_indicator.text()
    window.device = object()
    window.selected_device_def = SimpleNamespace(name="Test AIO")
    window.frame_times = [0.05, 0.05]
    window.update_performance_stats()
    assert "Test AIO" in window.perf_indicator.text()
    assert "20 fps" in window.perf_indicator.text()
    calls = []
    monkeypatch.setattr(window, "connect_display", lambda: calls.append("connect"))
    window.device = None
    window.perf_indicator.click()
    assert calls == ["connect"]


def test_page_thumbnails_and_snapshot_use_only_requested_page(window):
    window.elements = [ThemeElement("rectangle", page=1, color="#ff0000"),
                       ThemeElement("rectangle", page=2, color="#0000ff")]
    window._rebuild_pages()
    window._update_page_thumbnails()
    assert window.page_tabs.count() == 2
    assert not window.page_tabs.tabIcon(0).isNull()
    assert not window.page_tabs.tabIcon(1).isNull()
    assert [data["page"] for _, data in window._capture_render_snapshot(page=2)["elements"]] == [2]
    assert window.current_page == 1


def test_numeric_label_drag_changes_value_once_for_undo_and_respects_lock(isolated_settings):
    panel = PropertiesPanel()
    element = ThemeElement("rectangle", x=100)
    panel.set_element(element)
    undo = []
    panel.property_will_change.connect(lambda: undo.append(element.x))
    def event(kind, x, button, buttons):
        return QMouseEvent(kind, QPointF(x, 5), QPointF(x, 5), button, buttons, Qt.KeyboardModifier.NoModifier)
    panel.eventFilter(panel.x_label, event(QEvent.Type.MouseButtonPress, 10, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    panel.eventFilter(panel.x_label, event(QEvent.Type.MouseMove, 15, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
    panel.eventFilter(panel.x_label, event(QEvent.Type.MouseMove, 20, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
    panel.eventFilter(panel.x_label, event(QEvent.Type.MouseButtonRelease, 20, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
    assert element.x == 110 and undo == [100]
    element.locked = True
    panel.set_element(element)
    panel.eventFilter(panel.x_label, event(QEvent.Type.MouseButtonPress, 10, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    panel.eventFilter(panel.x_label, event(QEvent.Type.MouseMove, 30, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
    assert element.x == 110
    panel.deleteLater()


def test_wizard_device_size_filter_selection_and_back_navigation(monkeypatch, isolated_settings):
    device = SimpleNamespace(name="Test AIO", width=1280, height=480, experimental=False,
                             vendor_id=1, product_id=2, backend_type="hid")
    monkeypatch.setattr("src.ui.onboarding.enumerate_available_devices", lambda: [device])
    presets = {name: {"data": {"name": name, "display_width": width, "display_height": 480,
                               "elements": []}} for name, width in [("Wide", 1280), ("Square", 480)]}
    wizard = SetupWizard(presets, (480, 480), {})
    assert wizard.device_combo.currentData() is device
    wizard.initializePage(1)
    assert wizard.width_spin.value() == 1280
    wizard.initializePage(2)
    assert list(wizard.thumbnails) == ["Wide"]
    QTest.keyClick(wizard.thumbnails["Wide"], Qt.Key.Key_Return)
    assert wizard.preset_name == "Wide" and wizard.thumbnails["Wide"].is_selected
    wizard.profile_combo.setCurrentIndex(wizard.profile_combo.count() - 1)
    wizard.width_spin.setValue(640)
    wizard.refresh_gallery()
    assert set(wizard.thumbnails) == set(presets) and wizard.preset_name is None
    wizard.deleteLater()


def test_wizard_offline_and_saved_custom_size(monkeypatch, isolated_settings):
    monkeypatch.setattr("src.ui.onboarding.enumerate_available_devices", lambda: [])
    wizard = SetupWizard({}, (640, 360), {})
    wizard.initializePage(1)
    wizard.initializePage(2)
    assert wizard.device_combo.currentData() is None
    assert (wizard.width_spin.value(), wizard.height_spin.value()) == (640, 360)
    assert wizard.preset_name is None
    wizard.deleteLater()


def test_wizard_finish_applies_device_size_preset_and_persists_choice(window, monkeypatch):
    device = SimpleNamespace(name="AIO", width=1280, height=480, extra_params={},
                             vendor_id=1, product_id=2, backend_type="hid")
    fake = SimpleNamespace(
        exec=lambda: 1, device_combo=SimpleNamespace(currentData=lambda: device),
        width_spin=SimpleNamespace(value=lambda: 640), height_spin=SimpleNamespace(value=lambda: 360),
        preset_name="Default",
    )
    monkeypatch.setattr("src.ui.onboarding.SetupWizard", lambda *args: fake)
    connected = []
    monkeypatch.setattr(window, "connect_display", lambda: connected.append(True))
    window.show_setup_wizard()
    assert (constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT) == (640, 360)
    assert settings.get_setting("display_size_overrides")["0001:0002:hid"] == [640, 360]
    assert settings.get_setting("onboarding_completed") is True
    assert settings.get_setting("default_preset") == "Default"
    assert window.selected_device_def is not device
    assert (device.width, device.height) == (1280, 480)
    assert connected == [True]


def test_wizard_cancel_preserves_theme_and_settings(window, monkeypatch):
    before = window._snapshot_state()
    monkeypatch.setattr("src.ui.onboarding.SetupWizard", lambda *args: SimpleNamespace(exec=lambda: 0))
    window.show_setup_wizard()
    assert window._snapshot_state() == before


def test_wizard_blank_theme_can_be_undone(window, monkeypatch):
    before = window._snapshot_state()
    fake = SimpleNamespace(
        exec=lambda: 1, device_combo=SimpleNamespace(currentData=lambda: None),
        width_spin=SimpleNamespace(value=lambda: constants.DISPLAY_WIDTH),
        height_spin=SimpleNamespace(value=lambda: constants.DISPLAY_HEIGHT), preset_name=None,
    )
    monkeypatch.setattr("src.ui.onboarding.SetupWizard", lambda *args: fake)
    window.show_setup_wizard()
    assert window.elements == []
    window.undo()
    assert window._snapshot_state() == before
