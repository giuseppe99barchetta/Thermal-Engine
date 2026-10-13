"""One explicit condition per element; never evaluate user expressions."""
import math
import operator

COMPARISONS = {"==": operator.eq, "!=": operator.ne, ">": operator.gt,
               ">=": operator.ge, "<": operator.lt, "<=": operator.le}
ACTIONS = ("color", "text", "show", "hide")


def condition_matches(rule, values):
    value = values.get(rule.get("source"))
    comparison = COMPARISONS.get(rule.get("operator"))
    if value is None or comparison is None:
        return False
    target = rule.get("value", "")
    if isinstance(value, bool):
        if str(target).lower() not in ("true", "false", "on", "off", "1", "0"):
            return False
        target = str(target).lower() in ("true", "on", "1")
    elif isinstance(value, (int, float)):
        try:
            target = float(target)
        except (ValueError, TypeError, OverflowError):
            return False
        if not math.isfinite(value) or not math.isfinite(target):
            return False
    elif isinstance(value, str):
        if rule["operator"] not in ("==", "!="):
            return False
        target = str(target)
    else:
        return False
    return comparison(value, target)


def apply_condition(element, values):
    rule = element.condition
    if not rule:
        return
    matched = condition_matches(rule, values)
    action = rule.get("action")
    if action == "show":
        element.visible = element.visible and matched
    elif matched:
        if action == "hide":
            element.visible = False
        elif action == "color":
            element.color = element.text_color = element.label_text_color = rule["color"]
            element.auto_color_change = False
            element.gradient_fill = False
        elif action == "text":
            element.text = rule.get("text", "")
            if element.type == "text":
                element.source = "static"
