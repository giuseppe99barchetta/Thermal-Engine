import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from src.core.conditions import apply_condition, condition_matches
from src.core.element import ThemeElement
from src.core.renderer import ThemeRenderer
from src.core.security import validate_element_schema


@pytest.mark.parametrize("value,comparison,target,expected", [
    (81, ">", "80", True), (80, ">", "80", False), (0, "==", "0", True),
    (False, "==", "OFF", True), (True, "!=", "false", True),
    ("playing", "==", "playing", True), ("Playing", "==", "playing", False),
    ("playing", ">", "idle", False), (None, "!=", "0", False),
    (float("nan"), ">", "0", False), (3, ">", "__import__('os')", False),
])
def test_explicit_comparisons(value, comparison, target, expected):
    assert condition_matches({"source": "sensor", "operator": comparison, "value": target}, {"sensor": value}) is expected


def test_rule_roundtrip_validation_and_frame_restoration():
    rule = {"source": "cpu_temp", "operator": ">", "value": "80", "action": "color", "color": "#ff0000"}
    element = ThemeElement("rectangle", x=0, y=0, width=20, height=20, color="#00ff00", condition=rule)
    assert ThemeElement.from_dict(element.to_dict()).condition == rule
    assert not validate_element_schema(element.to_dict(), 0)
    renderer = ThemeRenderer()
    snapshot = {"background_color": "#000000", "elements": [(1, element.to_dict())], "sensor_data": {"cpu_temp": 81}}
    assert renderer.render(snapshot, (30, 30)).getpixel((5, 5)) == (255, 0, 0)
    snapshot["sensor_data"]["cpu_temp"] = 70
    assert renderer.render(snapshot, (30, 30)).getpixel((5, 5)) == (0, 255, 0)
    assert element.color == "#00ff00"
    assert validate_element_schema({"type": "text", "condition": {**rule, "color": "red"}}, 0)
    assert validate_element_schema({"type": "text", "condition": {**rule, "operator": []}}, 0)


def test_visibility_preserves_manual_hidden_and_missing_state():
    rule = {"source": "door", "operator": "==", "value": "on", "action": "show"}
    element = ThemeElement("text", visible=False, condition=rule)
    apply_condition(element, {"door": True})
    assert not element.visible
    element.visible = True
    apply_condition(element, {})
    assert not element.visible
    element.visible = True
    element.condition["action"] = "hide"
    apply_condition(element, {"door": True})
    assert not element.visible
    element.condition["action"] = "text"
    element.condition["text"] = "Door open"
    apply_condition(element, {"door": True})
    assert element.text == "Door open" and element.source == "static"

