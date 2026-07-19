"""
Settings management for Thermal Engine.
Handles persistent settings and platform autostart.
"""

import os
import sys
import json
import shlex

# Windows-only imports
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
if IS_WINDOWS:
    import winreg

from src.utils.app_path import (
    get_app_dir,
    get_bundled_resource_path,
    get_resource_path,
    get_user_data_path,
)
from src.core.security import escape_registry_path

APP_NAME = "ThermalEngine"
SETTINGS_FILE = get_user_data_path("settings.json")

# Default settings
DEFAULT_SETTINGS = {
    "launch_at_login": False,
    "launch_minimized": True,
    "minimize_to_tray": True,
    "close_to_tray": True,
    "target_fps": 30,  # 30 FPS is smooth for most PCs
    "default_preset": None,  # Name of preset to load on startup (explicit user choice)
    "last_preset": None,  # Last used preset (auto-saved on every preset load)
    "suppress_60fps_warning": False,  # Show warning when selecting 60 FPS
    "show_grid": True,  # Show grid lines on canvas
    "snap_to_grid": True,  # Snap elements to grid when dragging
    "check_for_updates": True,  # Check for updates on startup
    "last_display_width": 480,  # Last connected display width (default to 480x480)
    "last_display_height": 480,  # Last connected display height
    "profiles": [],  # Auto-switch profile rules
    "profiles_enabled": False,  # Whether auto-switching is active
    "profiles_default_preset": None,  # Preset when no profile matches
}

_settings = None


def load_settings():
    """Load settings from file, creating defaults if needed."""
    global _settings

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                _settings = json.load(f)
            # Ensure all default keys exist
            for key, value in DEFAULT_SETTINGS.items():
                if key not in _settings:
                    _settings[key] = value
        except Exception as e:
            print(f"[Settings] Error loading settings: {e}")
            _settings = DEFAULT_SETTINGS.copy()
    else:
        _settings = DEFAULT_SETTINGS.copy()
        save_settings()  # Create the file with defaults

    return _settings


def save_settings():
    """Save current settings to file."""
    global _settings
    if _settings is None:
        _settings = DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(_settings, f, indent=2)
    except Exception as e:
        print(f"[Settings] Error saving settings: {e}")


def get_setting(key, default=None):
    """Get a setting value."""
    global _settings
    if _settings is None:
        load_settings()
    return _settings.get(key, default)


def set_setting(key, value):
    """Set a setting value and save."""
    global _settings
    if _settings is None:
        load_settings()
    _settings[key] = value
    save_settings()


def get_executable_path():
    """Get the path to use for autostart."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        if IS_LINUX:
            appimage_path = os.environ.get("APPIMAGE")
            if appimage_path:
                return appimage_path
        if IS_WINDOWS:
            return escape_registry_path(sys.executable)
        return sys.executable
    else:
        # Running as script - use pythonw on Windows to avoid console window
        if IS_WINDOWS:
            python_exe = sys.executable.replace('python.exe', 'pythonw.exe')
        else:
            python_exe = sys.executable
        script_path = get_resource_path('main.py')
        if IS_WINDOWS:
            return f'{escape_registry_path(python_exe)} {escape_registry_path(script_path)}'
        return f"{shlex.quote(python_exe)} {shlex.quote(script_path)}"


def _get_linux_autostart_dir():
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        autostart_dir = os.path.join(config_home, "autostart")
    else:
        autostart_dir = os.path.expanduser("~/.config/autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    return autostart_dir


def _get_linux_desktop_entry_path():
    return os.path.join(_get_linux_autostart_dir(), f"{APP_NAME}.desktop")


def _get_linux_icon_path():
    candidates = [
        os.path.join(get_app_dir(), "assets", "icon.png"),
        os.path.join(get_app_dir(), "icon.png"),
        os.path.join(get_app_dir(), "icon.ico"),
        get_bundled_resource_path("assets/icon.png"),
        get_bundled_resource_path("icon.png"),
        get_bundled_resource_path("icon.ico"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


def _build_linux_desktop_entry():
    exec_path = get_executable_path()
    if get_setting("launch_minimized", True):
        exec_path += " --minimized"

    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        f"Name={APP_NAME}",
        "Comment=Thermal Engine",
        f"Exec={exec_path}",
        "Terminal=false",
        "StartupNotify=false",
        "Categories=Utility;",
    ]

    icon_path = _get_linux_icon_path()
    if icon_path:
        lines.append(f"Icon={icon_path}")

    return "\n".join(lines) + "\n"


def set_autostart(enabled):
    """Enable or disable autostart for supported platforms."""
    if IS_LINUX:
        desktop_entry_path = _get_linux_desktop_entry_path()
        try:
            if enabled:
                with open(desktop_entry_path, "w", encoding="utf-8") as f:
                    f.write(_build_linux_desktop_entry())
                os.chmod(desktop_entry_path, 0o644)
            else:
                if os.path.exists(desktop_entry_path):
                    os.remove(desktop_entry_path)
            return True
        except Exception as e:
            print(f"[Settings] Error setting Linux autostart: {e}")
            return False

    if not IS_WINDOWS:
        print("[Settings] Autostart is not supported on this platform")
        return False

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)

        if enabled:
            exe_path = get_executable_path()
            # Add --minimized flag if launch_minimized is enabled
            if get_setting("launch_minimized", True):
                exe_path += " --minimized"
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass  # Already doesn't exist

        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"[Settings] Error setting autostart: {e}")
        return False


def is_autostart_enabled():
    """Check if autostart is currently enabled."""
    if IS_LINUX:
        return os.path.exists(_get_linux_desktop_entry_path())

    if not IS_WINDOWS:
        return False

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def _remove_startup_folder_shortcut():
    """Remove any Startup folder shortcut to avoid duplicate launches.

    The installer may create a shortcut in the Windows Startup folder,
    but the app manages autostart via the registry. Having both causes
    the app to launch twice on boot.
    """
    try:
        startup_folder = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
        )
        shortcut_path = os.path.join(startup_folder, f"{APP_NAME}.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            print(f"[Settings] Removed Startup folder shortcut to avoid duplicate launch")
    except Exception as e:
        print(f"[Settings] Could not remove Startup shortcut: {e}")


def apply_autostart_setting():
    """Apply current autostart setting for supported platforms."""
    if not (IS_WINDOWS or IS_LINUX):
        return
    enabled = get_setting("launch_at_login", False)
    set_autostart(enabled)
    # Always clean up Startup folder shortcut - the registry entry is the
    # single source of truth for autostart. The installer may have created
    # a shortcut in the Startup folder, causing a duplicate launch.
    if IS_WINDOWS:
        _remove_startup_folder_shortcut()


# Initialize settings on module load
load_settings()
