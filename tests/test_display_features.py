import copy
import datetime

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from src.core.brightness import effective_brightness, in_window
from src.core.conditions import apply_condition
from src.core.element import ThemeElement
from src.core.security import validate_element_schema
from src.ui.quick_controller import EditorController
from src.utils import settings
from src.utils.idle import idle_ms

APP = QApplication.instance() or QApplication([])
NIGHT = {"dim_night_enabled": True, "dim_night_start": "22:00", "dim_night_end": "07:00", "dim_night_level": 30,
         "dim_idle_enabled": True, "dim_idle_minutes": 10, "dim_idle_level": 10}


@pytest.fixture
def controller(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    result = EditorController(start_services=False)
    yield result
    result.cleanup()


def at(hour, minute=0):
    return datetime.datetime(2026, 11, 20, hour, minute)


def test_night_window_wraps_midnight_and_equal_bounds_never_match():
    assert in_window(23 * 60, 22 * 60, 7 * 60) and in_window(3 * 60, 22 * 60, 7 * 60)
    assert not in_window(12 * 60, 22 * 60, 7 * 60) and not in_window(7 * 60, 22 * 60, 7 * 60)
    assert in_window(13 * 60, 12 * 60, 14 * 60) and not in_window(14 * 60, 12 * 60, 14 * 60)
    assert not in_window(5, 300, 300)


def test_effective_brightness_takes_the_lowest_active_rule():
    assert effective_brightness(80, NIGHT, at(12), 0) == (80, "")
    assert effective_brightness(80, NIGHT, at(23), 0) == (30, "night")
    assert effective_brightness(80, NIGHT, at(12), 600) == (10, "idle")
    assert effective_brightness(80, NIGHT, at(23), 599) == (30, "night")
    assert effective_brightness(80, NIGHT, at(23), 3600) == (10, "idle")
    assert effective_brightness(5, NIGHT, at(23), 3600) == (5, "")  # base already lower
    assert effective_brightness(80, NIGHT, at(23), None) == (30, "night")  # idle unknown off Windows
    assert effective_brightness(80, {**NIGHT, "dim_night_enabled": False, "dim_idle_enabled": False}, at(23), 3600) == (80, "")


def test_idle_ticks_survive_the_32_bit_wrap():
    assert idle_ms(5, 0xFFFFFFF0) == 21
    assert idle_ms(1000, 400) == 600


def test_dimming_settings_are_validated_and_applied_to_the_output(controller, monkeypatch):
    messages = []
    monkeypatch.setattr(controller, "error", messages.append)
    assert not controller.saveSettings({"dim_night_start": "25:00"})
    assert not controller.saveSettings({"dim_night_level": 150})
    assert not controller.saveSettings({"dim_idle_minutes": 0})
    monkeypatch.setattr("src.ui.quick_controller.seconds_since_input", lambda: 3600)
    assert controller.saveSettings({"dim_idle_enabled": True, "dim_idle_level": 15, "display_brightness": 90})
    assert controller.output_brightness == 15 and controller.state["dimReason"] == "idle"
    assert controller.display_brightness == 90  # the setting itself is untouched


def test_blink_rule_toggles_twice_a_second():
    rule = {"source": "cpu_temp", "operator": ">", "value": "80", "action": "blink"}
    assert not validate_element_schema({"type": "text", "condition": rule}, 0)
    for now, visible in ((10.2, True), (10.7, False), (11.1, True)):
        element = ThemeElement("text", condition=rule)
        apply_condition(element, {"cpu_temp": 90}, now=now)
        assert element.visible is visible
    calm = ThemeElement("text", condition=rule)
    apply_condition(calm, {"cpu_temp": 50}, now=10.7)
    assert calm.visible


def test_inspector_labels_read_naturally(controller):
    controller.document.elements = [ThemeElement("bar_gauge", source="cpu_temp")]
    controller.select_indices([0])
    labels = {row["key"]: row["label"] for row in controller.propertyRows}
    assert labels["temp_hide_unit"] == "Hide °C/°F unit" and labels["max_value"] == "Maximum value"
    assert labels["bar_text_mode"] == "Value text" and labels["width"] == "Width"  # fallback unchanged


def test_game_sensors_are_listed_before_presentmon_runs(controller, monkeypatch):
    from src.core import sensors
    monkeypatch.setattr(sensors, "get_game_fps_status", lambda: "Not running (no theme uses game sources)")
    controller.refresh_sensors()
    controller.filterSensors("Summary", "Gaming", "", False)
    rows = {row["id"]: row for row in controller.sensor_browser_model.rows}
    assert rows["game_fps"]["value"] == "Starts when used" and rows["game_fps"]["available"]
    monkeypatch.setattr(sensors, "get_game_fps_status", lambda: "PresentMon is not bundled in this build")
    controller.refresh_sensors()
    controller.filterSensors("Summary", "Gaming", "", False)
    assert not controller.sensor_browser_model.rows


def test_device_name_fits_and_icons_are_square_and_sharp(monkeypatch):
    from src.ui.quick_window import QuickEditorWindow
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    window = QuickEditorWindow(start_services=False)
    try:
        window.root.setWidth(1920); window.root.setHeight(1080); window.show(); QTest.qWait(200)
        pill = window.root.findChild(QObject, "connectionPill")
        name = next(t for t in pill.property("contentItem").childItems()[0].childItems() if t.property("text") == "Offline editor")
        assert name.width() >= name.implicitWidth()  # not elided
        ratio = window.root.devicePixelRatio()
        icons = [item for item in window.root.findChildren(QQuickItem)
                 if item.metaObject().className().startswith("QQuickImage")
                 and str(item.property("source").toString()).startswith("data:image/svg")]
        assert icons
        for image in icons:
            if image.width() <= 0:
                continue
            assert image.width() == image.height() and image.x() == int(image.x()) and image.y() == int(image.y())
            assert image.property("sourceSize").width() == round(image.width() * ratio)
    finally:
        window.controller.cleanup()


def test_discovered_entities_respect_the_sensor_limit(controller, monkeypatch):
    messages = []
    monkeypatch.setattr(controller, "error", messages.append)
    broker = {"host": "broker", "port": 1883, "tls": False, "username": "u", "password": "p"}
    draft = [{"id": f"s{i}"} for i in range(63)]
    entity = {"id": "s1", "name": "Door", "protocol": "mqtt", "topic": "door"}
    added = controller.addDiscovered(draft, [entity], broker)
    assert len(added) == 64 and added[-1]["id"] == "s1_2" and added[-1]["password"] == "p"
    assert len(controller.addDiscovered(added, [entity], broker)) == 64 and "0 more" in messages[-1]
