"""Scheduled display dimming: a night window and no-input idle. Pure functions, easy to test."""
import re

DIM_KEYS = ("dim_night_enabled", "dim_night_start", "dim_night_end", "dim_night_level",
            "dim_idle_enabled", "dim_idle_minutes", "dim_idle_level")
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def valid_time(text):
    return isinstance(text, str) and bool(_TIME.match(text))


def _minutes(text):
    hours, minutes = _TIME.match(text).groups()
    return int(hours) * 60 + int(minutes)


def in_window(now_minutes, start, end):
    """Is now inside [start, end)? The window wraps past midnight when start > end; start == end never."""
    if start == end:
        return False
    return start <= now_minutes < end if start < end else now_minutes >= start or now_minutes < end


def effective_brightness(base, settings, now, idle_seconds):
    """(level, reason): the lowest of the base brightness and every active dimming rule."""
    level, reason = base, ""
    if settings.get("dim_night_enabled") and valid_time(settings.get("dim_night_start")) \
            and valid_time(settings.get("dim_night_end")):
        if in_window(now.hour * 60 + now.minute, _minutes(settings["dim_night_start"]), _minutes(settings["dim_night_end"])):
            if settings.get("dim_night_level", 100) < level:
                level, reason = settings["dim_night_level"], "night"
    if settings.get("dim_idle_enabled") and idle_seconds is not None \
            and idle_seconds >= settings.get("dim_idle_minutes", 10) * 60:
        if settings.get("dim_idle_level", 100) < level:
            level, reason = settings["dim_idle_level"], "idle"
    return level, reason
