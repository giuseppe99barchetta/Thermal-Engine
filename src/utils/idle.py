"""Seconds since the last keyboard or mouse input (Windows); None where it cannot be measured."""
import sys


def idle_ms(now_tick, last_tick):
    """Unsigned 32-bit difference: GetTickCount wraps every 49.7 days."""
    return (now_tick - last_tick) & 0xFFFFFFFF


def seconds_since_input():
    if sys.platform != "win32":
        return None
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    return idle_ms(ctypes.windll.kernel32.GetTickCount(), info.dwTime) / 1000
