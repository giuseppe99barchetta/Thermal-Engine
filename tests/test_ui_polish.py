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
    image = Image.new("RGB", (160, 160), "black")
    image.paste((255, 255, 255), (0, 0, 40, 40))
    from io import BytesIO
    with Image.open(BytesIO(controller.image_to_jpeg(image))) as output:
        assert output.size == (160, 160) and output.getpixel((140, 20))[0] > 200 and output.getpixel((20, 20))[0] < 50  # top-left corner turned to top-right


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


def test_control_outlines_and_selection_meet_3_to_1_contrast_in_every_theme():
    import re
    from pathlib import Path

    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast(a, b):
        hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    source = (Path(__file__).resolve().parents[1] / "src/ui/qml/components/Theme.qml").read_text(encoding="utf-8")
    themes = re.findall(r"(\w+): \{\s*(background:.*?radius: \d+)", source, re.S)
    assert len(themes) == 3
    for name, body in themes:
        token = dict(re.findall(r'(\w+): "(#[0-9a-fA-F]{6})"', body))
        for outline in ("borderStrong", "accentBorder"):
            for ground in ("surface", "input"):
                assert contrast(token[outline], token[ground]) >= 3, (name, outline, ground)


def test_picked_or_dropped_network_media_never_reaches_the_document(controller, monkeypatch):
    import PIL.Image
    controller.document.elements = [ThemeElement("image")]
    controller.select_indices([0])
    before = controller.document.export()
    monkeypatch.setattr(PIL.Image, "open", lambda *a, **k: pytest.fail("network path opened"))
    for action in ("image", "gif", "video"):
        controller.fileChosen(action, QUrl("file://evil/share/x.png"))
    controller.dropFiles([QUrl("file://evil/share/x.png")], 0, 0)
    assert controller.document.export() == before


def test_quarter_turn_on_a_wide_panel_designs_in_portrait(controller, monkeypatch, tmp_path):
    from io import BytesIO
    from src.core.device_backends import DeviceDefinition
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    controller.resizeDisplay(1280, 480, False)
    controller.document.elements = [ThemeElement("rectangle", x=10, y=20, width=1280, height=480)]
    controller.selected_device_def = DeviceDefinition("Panel", 0x87AD, 0x70DB, "usb_bulk", width=1280, height=480)
    assert controller.saveSettings({"display_orientation": "rotate_90_cw"})
    assert (controller.document.width, controller.document.height) == (480, 1280)
    assert controller.state["panel"] == [1280, 480]
    with Image.open(BytesIO(controller.image_to_jpeg(Image.new("RGB", (480, 1280))))) as output:
        assert output.size == (1280, 480)  # portrait canvas turned back to the panel's shape
    controller._command("undo", None)  # canvas back to landscape, orientation still portrait
    assert (controller.document.width, controller.document.height) == (1280, 480)
    assert controller.state["panel"] == [1280, 480]  # stored, not derived from the canvas
    with Image.open(BytesIO(controller.image_to_jpeg(Image.new("RGB", (1280, 480))))) as output:
        assert output.size == (1280, 480)  # sent unrotated, still fits
    controller._command("redo", None)
    assert controller.saveSettings({"display_orientation": "normal"})
    assert (controller.document.width, controller.document.height) == (1280, 480)
    rect = controller.document.elements[0]
    assert (rect.x, rect.y, rect.width, rect.height) == (10, 20, 1280, 480)  # round trip is lossless
    assert controller.saveSettings({"display_orientation": "rotate_90_ccw"})
    controller.resizeDisplay(640, 480, False)  # the dialog speaks panel sizes
    assert (controller.document.width, controller.document.height) == (480, 640)
    assert settings.get_setting("last_display_width") == 640  # settings keep the panel size


def test_old_settings_with_quarter_turn_open_in_portrait(monkeypatch):
    stored = copy.deepcopy(settings.DEFAULT_SETTINGS)
    stored.update(last_display_width=1280, last_display_height=480, display_orientation="rotate_90_cw")
    monkeypatch.setattr(settings, "_settings", stored)
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    controller = EditorController(start_services=False)
    try:
        assert (controller.document.width, controller.document.height) == (480, 1280)
        assert controller.state["panel"] == [1280, 480]
    finally:
        controller.cleanup()


def test_preview_timer_renders_off_the_gui_thread(controller, monkeypatch):
    import threading
    threads = []
    real_render = controller.renderer.render
    monkeypatch.setattr(controller.renderer, "render", lambda *a: threads.append(threading.current_thread()) or real_render(*a))
    controller.canvas = SimpleCanvas()
    controller.window = SimpleCanvas()
    controller._preview_tick()
    controller._preview_tick()  # still in flight: skipped, not queued
    controller._preview_worker.submit(lambda: None).result(timeout=5)
    APP.processEvents()
    assert threads == [threads[0]] and threads[0] is not threading.main_thread()
    assert controller._preview_frame is not None and not controller._preview_busy
    generation = controller._preview_generation
    controller._preview_ready(None, generation)
    controller._preview_ready(Image.new("RGB", (8, 8)), generation - 1)  # older than a synchronous render
    assert controller._preview_frame.size != (8, 8)


class SimpleCanvas:
    def isVisible(self): return True
    def update(self): pass


def test_presentmon_follows_the_theme(controller, monkeypatch):
    calls = []
    monkeypatch.setattr(sensors, "set_game_fps_enabled", calls.append)
    controller._start_services = True
    controller.document.elements = [ThemeElement("text", text="CPU {cpu_temp}")]
    controller.refresh_sensors()
    controller.document.elements = [ThemeElement("text", text="FPS {game_fps}")]
    controller.refresh_sensors()
    controller.document.elements = [ThemeElement("circle_gauge", source="game_frametime")]
    controller.refresh_sensors()
    controller._start_services = False
    assert calls == [False, True, True]
