"""
Auto Profiles for Thermal Engine.
Monitor foreground application and auto-switch presets.
"""

import os
import sys
import time
import logging

import psutil

from PySide6.QtCore import QThread, Signal

from src.utils.settings import get_setting

logger = logging.getLogger(__name__)

# Windows API imports
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _get_foreground_app():
    """Get the foreground window's process name and title using Win32 API."""
    if sys.platform != 'win32':
        return "", ""

    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", ""

        # Window title
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        window_title = buf.value

        # Process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Process name from PID
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return "", window_title

        try:
            buf_size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            success = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(buf_size))
            if success:
                return os.path.basename(buf.value).lower(), window_title
        finally:
            kernel32.CloseHandle(handle)

        return "", window_title

    except Exception as e:
        logger.debug(f"GetForegroundApp error: {e}")
        return "", ""


def _wait_while_running(monitor, step_ms=100):
    """Sleep one poll interval in short steps so stop() returns at once instead of after a full interval."""
    waited = 0
    while monitor._running and waited < monitor.poll_interval_ms:
        monitor.msleep(step_ms)
        waited += step_ms


class ForegroundAppMonitor(QThread):
    """Polls the foreground window and emits signals on app changes."""

    app_changed = Signal(str, str)  # (process_name, window_title)

    def __init__(self, poll_interval_ms=2500):
        super().__init__()
        self.poll_interval_ms = poll_interval_ms
        self._running = True
        self._last_process = ""

    def stop(self):
        self._running = False
        self.wait(5000)

    def run(self):
        while self._running:
            try:
                process_name, window_title = _get_foreground_app()
                if process_name and process_name != self._last_process:
                    self._last_process = process_name
                    self.app_changed.emit(process_name, window_title)
            except Exception as e:
                logger.error(f"Foreground monitor error: {e}")

            _wait_while_running(self)


class SystemStateMonitor(QThread):
    """Monitors CPU usage to detect idle vs gaming/high-load states."""

    state_changed = Signal(str)  # 'idle', 'gaming', or 'normal'

    def __init__(self, poll_interval_ms=5000):
        super().__init__()
        self.poll_interval_ms = poll_interval_ms
        self._running = True
        self._current_state = "normal"

    def stop(self):
        self._running = False
        self.wait(5000)

    def run(self):
        # Prime psutil CPU measurement
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        idle_seconds_count = 0
        gaming_seconds_count = 0
        interval_s = self.poll_interval_ms / 1000.0

        while self._running:
            try:
                idle_threshold = get_setting("system_idle_threshold", 15)
                gaming_threshold = get_setting("system_gaming_threshold", 60)
                idle_secs = get_setting("system_idle_seconds", 60)
                gaming_secs = get_setting("system_gaming_seconds", 10)

                cpu = psutil.cpu_percent(interval=None)

                if cpu <= idle_threshold:
                    idle_seconds_count += interval_s
                    gaming_seconds_count = 0
                elif cpu >= gaming_threshold:
                    gaming_seconds_count += interval_s
                    idle_seconds_count = 0
                else:
                    idle_seconds_count = 0
                    gaming_seconds_count = 0

                new_state = self._current_state
                if idle_seconds_count >= idle_secs:
                    new_state = "idle"
                elif gaming_seconds_count >= gaming_secs:
                    new_state = "gaming"
                elif cpu > idle_threshold and self._current_state == "idle":
                    new_state = "normal"
                    idle_seconds_count = 0
                elif cpu < gaming_threshold and self._current_state == "gaming":
                    new_state = "normal"
                    gaming_seconds_count = 0

                if new_state != self._current_state:
                    self._current_state = new_state
                    self.state_changed.emit(new_state)

            except Exception as e:
                logger.error(f"SystemStateMonitor error: {e}")

            _wait_while_running(self)


class ProfileManager:
    """Manages profile rules and matching logic."""

    def __init__(self):
        self._profiles = []
        self._enabled = False
        self._cooldown_until = 0
        self._active_profile = None
        self._default_preset = None
        # System state profiles
        self.system_profile_enabled = False
        self.system_idle_preset = None
        self.system_gaming_preset = None
        self.load_profiles()

    def load_profiles(self):
        self._profiles = get_setting("profiles", [])
        self._enabled = get_setting("profiles_enabled", False)
        self._default_preset = get_setting("profiles_default_preset", None)
        self.system_profile_enabled = get_setting("system_profile_enabled", False)
        self.system_idle_preset = get_setting("system_idle_preset", None)
        self.system_gaming_preset = get_setting("system_gaming_preset", None)

    @property
    def enabled(self):
        return self._enabled

    @property
    def profiles(self):
        return self._profiles

    @property
    def default_preset(self):
        return self._default_preset

    @property
    def active_profile_name(self):
        return self._active_profile

    def suppress_auto_switch(self, seconds=30):
        """Suppress auto-switching for N seconds after manual interaction."""
        self._cooldown_until = time.time() + seconds

    def match_app(self, process_name, window_title):
        """
        Check if foreground app matches any profile.

        Returns preset_name if matched, default_preset if no match, or None.
        """
        if not self._enabled:
            return None

        if time.time() < self._cooldown_until:
            return None

        process_name = process_name.lower()

        for profile in self._profiles:
            match_mode = profile.get("match_mode", "process")
            target = profile["app_name"].lower()

            if match_mode == "process" and target in process_name:
                self._active_profile = profile["app_name"]
                return profile["preset_name"]
            elif match_mode == "title" and target in window_title.lower():
                self._active_profile = profile["app_name"]
                return profile["preset_name"]

        # No match — return default
        self._active_profile = None
        return self._default_preset

