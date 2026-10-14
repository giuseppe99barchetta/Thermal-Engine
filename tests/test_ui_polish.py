import copy
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PySide6.QtCore import QUrl, QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
import pytest
from src.core import constants, sensors
from src.core.element import ThemeElement
from src.core.preset_repository import preview_background
from src.ui.quick_controller import EditorController
from src.ui.quick_window import QuickEditorWindow
from src.utils import settings

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    result = EditorController(start_services=False)
    yield result
    result.cleanup()


def test_gif_background_visible_in_reloaded_preset_thumbnail(controller, tmp_path):
    previous_video = copy.deepcopy(controller.document.video)
    media = tmp_path / "local.gif"
    Image.new("RGB", (40, 80), "#ee2255").save(media, save_all=True, append_images=[Image.new("RGB", (40, 80), "blue")], duration=100)
    theme = {"name": "Local GIF", "display_width": 480, "display_height": 480, "elements": [],
             "video_background": {"video_path": "local.gif", "enabled": True, "fit_mode": "fit_height"}}
    (tmp_path / "Local GIF.json").write_text(json.dumps(theme))
    controller.repository.user_dir = tmp_path
    controller.reload_presets()
    thumbnail = controller.thumbnails["preset/Local GIF"]
    assert thumbnail.pixelColor(thumbnail.width() // 2, thumbnail.height() // 2).red() > 200
    assert thumbnail.pixelColor(0, thumbnail.height() // 2).red() == 0
    assert controller.document.video == previous_video
    data = controller.repository.presets["Local GIF"]["data"]
    data["video_background"]["fit_mode"] = "fit_width"
    assert preview_background(data, (480, 480)).getpixel((0, 240))[0] > 200
    import time
    controller._load_preset("Local GIF")
    history = len(controller.document.undo_stack)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        QTest.qWait(20)
        page = controller.thumbnails["page/1"]
        color = page.pixelColor(page.width() // 2, page.height() // 2)
        if max(color.red(), color.blue()) > 200: break
    assert max(color.red(), color.blue()) > 200
    assert len(controller.document.undo_stack) == history
    assert not controller.dirty


def test_missing_media_uses_saved_thumbnail(controller, tmp_path):
    theme = {"name": "Missing media", "elements": [], "video_background": {"enabled": True, "video_path": "missing.gif"}}
    (tmp_path / "Missing media.json").write_text(json.dumps(theme))
    Image.new("RGB", (150, 150), "#1234aa").save(tmp_path / "Missing media.png")
    controller.repository.user_dir = tmp_path
    controller.reload_presets()
    assert controller.thumbnails["preset/Missing media"].pixelColor(20, 20).blue() == 170


def test_sensor_browser_groups_and_filters(controller, monkeypatch):
    monkeypatch.setattr(sensors, "get_hardware_sensor_catalog", lambda: [{"id": "hardware_package", "name": "CPU Package [/amdcpu/0/temperature/0]", "type": "temp", "symbol": "°C"}])
    monkeypatch.setattr(controller, "get_sensor_data", lambda: {"cpu_temp": 62, "hardware_package": 63, "network_room": 21})
    saved = copy.deepcopy(constants.SOURCE_UNITS)
    categorized = copy.deepcopy(constants.DATA_SOURCES_CATEGORIZED)
    sources = list(constants.DATA_SOURCES)
    try:
        constants.register_network_sources([{"id": "room", "name": "Room", "unit": "°C"}])
        controller.refresh_sensors()
        controller.filterSensors("Summary", "CPU", "", False)
        assert [r["id"] for r in controller.sensor_browser_model.rows] == ["cpu_temp"]
        controller.filterSensors("Hardware", "All groups", "package", False)
        assert controller.sensor_browser_model.get(0)["category"] == "CPU"
        controller.filterSensors("External", "All groups", "room", False)
        assert controller.sensor_browser_model.get(0)["id"] == "network_room"
        controller.filterSensors("Summary", "GPU", "", False)
        assert controller.sensor_browser_model.rows == []
        controller.filterSensors("Summary", "GPU", "", True)
        assert controller.sensor_browser_model.rows and all(not r["available"] for r in controller.sensor_browser_model.rows)
    finally:
        constants.SOURCE_UNITS.clear(); constants.SOURCE_UNITS.update(saved)
        constants.DATA_SOURCES_CATEGORIZED.clear(); constants.DATA_SOURCES_CATEGORIZED.update(categorized)
        constants.DATA_SOURCES[:] = sources


def test_contextual_property_sections_and_display_rotation(controller, monkeypatch, tmp_path):
    controller.document.elements = [ThemeElement("gif")]
    controller.select_indices([0])
    titles = [section["title"] for section in controller.propertySections]
    assert "Media" in titles and "Text & value" not in titles and "Glass effect" not in titles
    controller.document.elements = [ThemeElement("bar_gauge", source="cpu_temp")]
    rows = {row["key"] for row in controller.propertyRows}
    assert "animation_speed" not in rows and "gradient_stops" not in rows and "value" not in rows
    controller.edit("animate_gauge", True)
    assert "animation_speed" in {row["key"] for row in controller.propertyRows}
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    assert controller.saveSettings({"display_orientation": "rotate_90_cw"})
    image = Image.new("RGB", (180, 160))
    from io import BytesIO
    with Image.open(BytesIO(controller.image_to_jpeg(image))) as output:
        assert output.size == (160, 180)


def test_pages_not_clipped_and_logo_available(monkeypatch):
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    window = QuickEditorWindow(start_services=False)
    try:
        window.root.setWidth(1280); window.root.setHeight(720); window.show()
        strip = window.root.findChild(QObject, "pageStrip")
        single_page_height = strip.property("height")
        window.controller.command("addPage", None)  # thumbnails appear from the second page on
        QTest.qWait(150)
        assert strip.property("height") > single_page_height
        page_list = window.root.findChild(QObject, "pageList")
        thumbnail = page_list.property("currentItem")
        assert thumbnail is not None
        assert thumbnail.height() <= page_list.property("height")
        logo = window.root.findChild(QObject, "applicationLogo")
        root = Path(__file__).resolve().parents[1]
        base = QUrl.fromLocalFile(str(root / "src/ui/qml/Main.qml"))
        assert base.resolved(logo.property("source")) == QUrl.fromLocalFile(str(root / "assets/icon.png"))
        from PySide6.QtQml import QQmlExpression, qmlContext
        loaded, error = QQmlExpression(qmlContext(logo), logo, "status === 1").evaluate()
        assert loaded and not error
        assert not window.qml_errors, window.qml_errors
    finally:
        window.dispose()
