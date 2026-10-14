import copy
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
import pytest
from src.utils import settings
from src.ui.quick_controller import EditorController
from src.core.element import ThemeElement

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    result = EditorController(start_services=False)
    yield result
    result.cleanup()


@pytest.mark.parametrize("platform, elevated, available, expected", [
    ("win32", False, False, True), ("win32", False, True, False),
    ("win32", True, False, False), ("linux", False, False, False)])
def test_hardware_permission_prompt_is_relevant_and_once(controller, monkeypatch, platform, elevated, available, expected):
    from types import SimpleNamespace
    import src.ui.quick_controller as module
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(settings, "_is_windows_elevated", lambda: elevated)
    monkeypatch.setattr(module.sensors, "get_sensor_status", lambda: {"cpu_thermal_available": available})
    monkeypatch.setattr(module, "enumerate_available_devices", lambda: [])
    monkeypatch.setattr(controller, "_restore_video", lambda: None)
    settings._settings.update(onboarding_completed=True, check_for_updates=False)
    controller._start_services = True
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append(kind))
    controller.startup()
    controller.checkHardwareAccess()
    assert requests == (["hardware"] if expected else [])
    assert controller.hardwareStatus["needsAdmin"] == expected
    controller._start_services = False  # this fixture did not start the shared sensor service


def test_hardware_prompt_waits_for_onboarding_and_detects_late_failure(controller, monkeypatch):
    from types import SimpleNamespace
    import src.ui.quick_controller as module
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(settings, "_is_windows_elevated", lambda: False)
    status = {"cpu_thermal_available": False}
    monkeypatch.setattr(module.sensors, "get_sensor_status", lambda: status)
    monkeypatch.setattr(module, "enumerate_available_devices", lambda: [])
    monkeypatch.setattr(controller, "openDevices", lambda: None)
    monkeypatch.setattr(controller, "_restore_video", lambda: None)
    settings._settings.update(onboarding_completed=False, last_preset=None, default_preset=None, check_for_updates=False)
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append(kind))
    controller._start_services = True
    controller.startup()
    controller.refresh_sensors()
    assert requests == ["onboarding"]
    # The wizard's onClosed slot starts checking, even if the first reading was valid.
    status["cpu_thermal_available"] = True
    controller.checkHardwareAccess()
    status["cpu_thermal_available"] = False
    controller.refresh_sensors()
    controller.refresh_sensors()
    assert requests == ["onboarding", "hardware"]
    controller._start_services = False


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows elevation API")
@pytest.mark.parametrize("dirty, result, exits", [(True, 42, False), (False, 5, False), (False, 42, True)])
def test_admin_restart_preserves_unsaved_or_cancelled_session(controller, monkeypatch, dirty, result, exits):
    import ctypes
    from unittest.mock import Mock
    monkeypatch.setattr(settings, "_is_windows_elevated", lambda: False)
    shell = Mock(return_value=result)
    monkeypatch.setattr(ctypes.windll.shell32, "ShellExecuteW", shell)
    controller.window = Mock()
    controller.dirty = dirty
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append(kind))
    controller.command("restartAdmin", None)
    assert controller.window.force_quit.called == exits
    assert shell.called == (not dirty)
    assert requests == ([] if exits else ["error"])


def test_locked_elements_and_page_selection(controller):
    controller.document.elements = [ThemeElement("rectangle", locked=True, x=100), ThemeElement("text", page=2)]
    controller.document.pages = [1, 2]
    controller.selectLayer(0)
    controller.edit("x", 200)
    assert controller.elements[0].x == 100
    controller.edit("visible", False)
    assert not controller.elements[0].visible
    controller.command("page", 2)
    assert controller.selected == {} and controller.layers_model.get(0)["index"] == 1


def test_custom_element_defaults_are_kept(controller):
    from elements import get_custom_element
    defaults = get_custom_element("line_chart")["defaults"]
    controller.command("add", "line_chart")
    for key in ("width", "height", "source"):
        assert getattr(controller.elements[0], key) == defaults[key]


def test_package_and_json_round_trip(controller, tmp_path):
    controller.command("add", "bar_gauge")
    controller.edit("gradient_fill", True)
    controller.edit("gradient_stops", [[0, "#57d4ef"], [1, "#ffffff"]])
    before = controller.document.export()
    package = tmp_path / "theme.thermal"
    controller.fileChosen("exportPackage", QUrl.fromLocalFile(str(package)))
    assert package.exists()
    controller.command("add", "text")
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    controller.fileChosen("importPackage", QUrl.fromLocalFile(str(package)))
    assert requests[-1][0] == "unsaved"
    controller.answer(requests[-1][1]["token"], True, "discard")
    assert json.loads(json.dumps(controller.document.export())) == json.loads(json.dumps(before))
    path = tmp_path / "theme.json"
    controller.fileChosen("saveAs", QUrl.fromLocalFile(str(path)))
    assert json.loads(path.read_text()) == json.loads(json.dumps(before))


def test_invalid_gradient_preserves_document(controller):
    controller.command("add", "bar_gauge")
    before = controller.document.snapshot()
    controller.edit("gradient_stops", [[-1, "bad"], [1, "#ffffff"]])
    assert controller.document.snapshot() == before
    assert "gradient" in controller.status.lower()


def test_failed_save_preserves_dirty_state(controller, monkeypatch, tmp_path):
    controller.command("add", "text")
    def fail(*args): raise OSError("disk unavailable")
    monkeypatch.setattr("src.ui.quick_controller.write_json_atomic", fail)
    controller.fileChosen("saveAs", QUrl.fromLocalFile(str(tmp_path / "theme.json")))
    assert controller.dirty and "disk unavailable" in controller.status


def test_missing_credentials_preserves_stored_network(controller, monkeypatch):
    source = {"id": "private", "name": "Private", "protocol": "mqtt", "host": "localhost", "topic": "sensor", "password_ref": "missing"}
    def get(key, default=None, resolve_secrets=True):
        if key == "network_sensors":
            if resolve_secrets: raise RuntimeError("Missing saved credentials")
            return [source]
        return default
    monkeypatch.setattr(settings, "get_setting", get)
    writes = []
    monkeypatch.setattr(settings, "set_setting", lambda *args: writes.append(args))
    controller.openNetwork()
    assert controller.networkDraft[0]["password_ref"] == "missing"
    assert not controller.saveNetwork(controller.networkDraft)
    assert writes == []


def test_alignment_is_one_undo_and_skips_locked(controller):
    controller.document.elements = [ThemeElement("rectangle", x=40), ThemeElement("rectangle", x=100), ThemeElement("rectangle", x=200, locked=True)]
    controller.select_indices([0, 1, 2])
    count = len(controller.document.undo_stack)
    controller.command("align", "left")
    assert [e.x for e in controller.elements] == [40, 40, 200]
    assert len(controller.document.undo_stack) == count + 1
    controller.command("undo", None)
    assert [e.x for e in controller.elements] == [40, 100, 200]


def test_profile_settings_and_failed_write_preserve_previous(controller, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    assert controller.saveSettings({"system_idle_threshold": 20, "system_idle_seconds": 90, "display_brightness": 0})
    assert controller.settingsData()["system_idle_threshold"] == 20
    assert controller.display_brightness == 0
    previous = copy.deepcopy(settings._settings)
    def fail(*args): raise OSError("disk unavailable")
    monkeypatch.setattr("src.ui.quick_controller.write_json_atomic", fail)
    assert not controller.saveSettings({"system_idle_threshold": 25})
    assert settings._settings == previous


def test_automatic_profile_load_does_not_start_manual_cooldown(controller):
    from unittest.mock import MagicMock
    manager = controller._profile_manager = MagicMock()
    manager.match_app.return_value = "Default"
    controller.document.theme_name = "Other"
    controller._profile_app("simhub.exe", "SimHub")
    assert controller.document.theme_name == "Default"
    manager.suppress_auto_switch.assert_not_called()
    controller.command("loadPreset", "Default")
    manager.suppress_auto_switch.assert_called_once()


def test_render_worker_delivery_is_queued_on_gui_thread(controller, monkeypatch):
    import threading
    import time
    from PySide6.QtTest import QTest
    from PIL import Image
    gui_thread = threading.get_ident()
    deliveries = []
    controller.frameDelivered.connect(lambda: deliveries.append(threading.get_ident()))
    class Backend:
        def is_connected(self): return True
    controller.backend = Backend()
    monkeypatch.setattr(controller, "render_theme_image", lambda **kwargs: Image.new("RGB", (160, 160)))
    monkeypatch.setattr(controller, "send_jpeg_frame", lambda payload: None)
    controller._frame_snapshot = {"elements": []}
    controller._start_render_thread()
    controller._frame_request.set()
    deadline = time.monotonic() + 2
    while not deliveries and time.monotonic() < deadline: QTest.qWait(10)
    controller._stop_render_thread()
    controller.backend = None
    assert deliveries == [gui_thread]
    assert controller.last_frame_time > 0


def test_selecting_a_layer_does_not_rerender(controller, monkeypatch):
    controller.document.elements = [ThemeElement("rectangle"), ThemeElement("text")]
    controller.refresh(mark_dirty=False)
    renders = []
    monkeypatch.setattr(controller.renderer, "render", lambda *args, **kwargs: renders.append(1))
    controller.selectLayer(1)
    assert controller.document.selection == [1]
    assert controller.layers_model.get(1)["selected"]
    assert renders == []


def test_bundled_presets_are_saved_as_a_copy(controller, monkeypatch):
    monkeypatch.setattr(controller.repository, "presets", {"Aurora Pulse": {"builtin": True, "data": {}}})
    saved, prompts = [], []
    monkeypatch.setattr(controller.repository, "save", lambda *args: saved.append(args))
    monkeypatch.setattr(controller, "prompt", lambda title, label, initial, callback: prompts.append(initial))
    controller.document.theme_name = "Aurora Pulse"
    controller.refresh()  # an edit: must not schedule an autosave over the bundled theme
    assert not controller.autosave.isActive()
    controller.save()
    assert saved == [] and prompts == ["Aurora Pulse copy"]


def test_loading_a_preset_over_unsaved_edits_asks_first(controller, monkeypatch):
    monkeypatch.setattr(controller.repository, "presets", {"Other": {"builtin": True, "data": {}}})
    loaded, requests = [], []
    monkeypatch.setattr(controller, "_load_preset", lambda name, manual=True: loaded.append(name))
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    controller.dirty = True
    controller.command("loadPreset", "Other")
    assert loaded == [] and requests[0][0] == "unsaved"
    controller.answer(requests[0][1]["token"], True, "discard")
    assert loaded == ["Other"]


@pytest.mark.parametrize("choice, quits", [("cancel", False), ("discard", True)])
def test_dirty_quit_requires_a_decision(controller, choice, quits):
    from unittest.mock import Mock
    controller.window = Mock()
    controller.dirty = True
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    controller.requestQuit()
    controller.requestQuit()  # the tray can request quit again while the prompt is visible
    assert len(requests) == 1 and requests[0][0] == "unsaved"
    assert not controller.window.force_quit.called
    controller.answer(requests[0][1]["token"], choice != "cancel", choice)
    assert controller.window.force_quit.called == quits


@pytest.mark.parametrize("save_error", [False, True])
def test_save_before_quit_waits_for_name_and_write(controller, monkeypatch, save_error):
    from unittest.mock import Mock
    controller.window = Mock()
    controller.document.theme_name = "Untitled Theme"
    controller.dirty = True
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    writer = Mock(side_effect=OSError("disk full") if save_error else None)
    monkeypatch.setattr(controller.repository, "save", writer)
    monkeypatch.setattr(controller, "reload_presets", lambda: None)
    controller.requestQuit()
    controller.answer(requests[-1][1]["token"], True, "save")
    assert requests[-1][0] == "prompt" and not controller.window.force_quit.called
    controller.answer(requests[-1][1]["token"], True, "Saved copy")
    assert writer.called and controller.window.force_quit.called == (not save_error)
    if save_error:
        assert controller.dirty and requests[-1][0] == "error"
        assert controller._after_save is None


def test_cancelled_save_does_not_run_a_later_continuation(controller, monkeypatch):
    from unittest.mock import Mock
    controller.window = Mock()
    controller.document.theme_name = "Untitled Theme"
    controller.dirty = True
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    controller.requestQuit()
    controller.answer(requests[-1][1]["token"], True, "save")
    controller.answer(requests[-1][1]["token"], False, "")
    monkeypatch.setattr(controller.repository, "save", Mock())
    monkeypatch.setattr(controller, "reload_presets", lambda: None)
    controller._save_named("Later save")
    assert not controller.window.force_quit.called


def test_open_cancel_preserves_the_current_document(controller, tmp_path):
    target = tmp_path / "other.json"
    target.write_text(json.dumps({"name": "Other", "elements": []}))
    controller.command("add", "text")
    previous = controller.document.snapshot()
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    controller.fileChosen("open", QUrl.fromLocalFile(str(target)))
    assert requests[-1][0] == "unsaved"
    controller.answer(requests[-1][1]["token"], False, "")
    assert controller.document.snapshot() == previous


@pytest.mark.parametrize("permission, disk_error, success", [(False, False, False), (True, False, True), (True, True, False)])
def test_startup_setting_is_transactional(controller, monkeypatch, permission, disk_error, success):
    from unittest.mock import Mock, call
    settings._settings["launch_at_login"] = False
    configure = Mock(return_value=permission)
    writer = Mock(side_effect=OSError("disk full") if disk_error else None)
    monkeypatch.setattr(settings, "set_autostart", configure)
    monkeypatch.setattr("src.ui.quick_controller.write_json_atomic", writer)
    assert controller.saveSettings({"launch_at_login": True}) == success
    assert settings._settings["launch_at_login"] == success
    if not permission:
        writer.assert_not_called()
    if disk_error:
        assert configure.call_args_list == [call(True), call(False)]


def test_network_validation_locates_bad_fields_and_duplicate_ids(controller):
    valid = {"id": "room", "protocol": "http", "url": "http://127.0.0.1/value"}
    assert controller.validateNetworkDraft([valid]) == {}
    error = controller.validateNetworkDraft([valid, {**valid, "id": "other", "url": "bad"}])
    assert error["index"] == 1 and error["field"] == "url"
    error = controller.validateNetworkDraft([valid, valid.copy()])
    assert error["index"] == 1 and error["field"] == "id"


def test_preset_browser_filters_without_empty_cells(controller):
    controller.presets_model.replace([{"id": "wide", "name": "Wide", "width": 1280, "height": 480},
                                      {"id": "square", "name": "Square", "width": 480, "height": 480}])
    controller.filterPresets("", False)
    assert [row["id"] for row in controller.preset_browser_model.rows] == ["square"]
    controller.filterPresets("WIDE", True)
    assert [row["id"] for row in controller.preset_browser_model.rows] == ["wide"]
    controller.filterPresets("absent", True)
    assert controller.preset_browser_model.rowCount() == 0


@pytest.mark.parametrize("discard", [False, True])
def test_update_install_waits_for_unsaved_changes(controller, monkeypatch, discard):
    from unittest.mock import Mock
    installer = Mock(return_value=True)
    monkeypatch.setattr("src.utils.updater.install_downloaded_update", installer)
    controller.window = Mock()
    controller._update_info = {"asset": "setup.exe"}
    controller.dirty = True
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    controller._update_downloaded("download.exe")
    controller.answer(requests[-1][1]["token"], True, "")
    assert requests[-1][0] == "unsaved" and not installer.called
    controller.answer(requests[-1][1]["token"], discard, "discard" if discard else "")
    assert installer.called == discard and controller.window.force_quit.called == discard


def test_inspector_hides_properties_the_renderer_ignores(controller):
    controller.document.elements = [ThemeElement("circle_gauge")]
    controller.select_indices([0])
    keys = {row["key"] for row in controller.propertyRows}
    assert "radius" in keys and "border_radius" not in keys and "clip" not in keys
