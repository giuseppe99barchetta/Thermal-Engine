"""
Settings management for Thermal Engine.
Handles persistent settings and platform autostart.
"""

import os
import sys
import json
import shlex
import ctypes
import subprocess

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
WINDOWS_AUTOSTART_TASK_NAME = "ThermalEngine Elevated Startup"
SETTINGS_FILE = get_user_data_path("settings.json")

# Default settings
DEFAULT_SETTINGS = {
    "launch_at_login": False,
    "launch_minimized": True,
    "minimize_to_tray": True,
    "close_to_tray": True,
    "target_fps": 30,  # 30 FPS is smooth for most PCs
    "display_brightness": 100,  # Software brightness applied to display frames
    "default_preset": None,  # Name of preset to load on startup (explicit user choice)
    "last_preset": None,  # Last used preset (auto-saved on every preset load)
    "suppress_60fps_warning": False,  # Show warning when selecting 60 FPS
    "show_grid": True,  # Show grid lines on canvas
    "snap_to_grid": True,  # Snap elements to grid when dragging
    "check_for_updates": True,  # Check for updates on startup
    "last_display_width": 480,  # Last connected display width (default to 480x480)
    "last_display_height": 480,  # Last connected display height
    "display_size_overrides": {},  # Per-device output size overrides
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


def _is_windows_elevated():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _remove_legacy_windows_autostart():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except OSError:
        pass


def _configure_windows_autostart_task(enabled):
    command = ["schtasks.exe", "/delete", "/tn", WINDOWS_AUTOSTART_TASK_NAME, "/f"]
    if enabled:
        task_command = get_executable_path()
        if get_setting("launch_minimized", True):
            task_command += " --minimized"
        command = [
            "schtasks.exe", "/create", "/tn", WINDOWS_AUTOSTART_TASK_NAME,
            "/tr", task_command, "/sc", "onlogon", "/rl", "highest", "/it", "/f",
        ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as e:
        print(f"[Settings] Error configuring elevated autostart: {e}")
        return False

    if result.returncode != 0:
        print(f"[Settings] Error configuring elevated autostart: {result.stderr.strip()}")
        return False

    _remove_legacy_windows_autostart()
    return True


def _request_elevated_autostart_change(enabled):
    action = "enable" if enabled else "disable"
    parameters = f"--configure-autostart {action}"
    if not getattr(sys, "frozen", False):
        parameters = f'{escape_registry_path(get_resource_path("main.py"))} {parameters}'
    return ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, parameters, None, 0
    ) > 32


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

    if _is_windows_elevated():
        return _configure_windows_autostart_task(enabled)
    return _request_elevated_autostart_change(enabled)


def is_autostart_enabled():
    """Check if autostart is currently enabled."""
    if IS_LINUX:
        return os.path.exists(_get_linux_desktop_entry_path())

    if not IS_WINDOWS:
        return False

    try:
        result = subprocess.run(
            ["schtasks.exe", "/query", "/tn", WINDOWS_AUTOSTART_TASK_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except OSError:
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
    if IS_WINDOWS and enabled == is_autostart_enabled():
        _remove_legacy_windows_autostart()
        applied = True
    else:
        applied = set_autostart(enabled)
    # Always clean up Startup folder shortcuts. The scheduled task is the
    # Windows source of truth and a shortcut would launch a second instance.
    if IS_WINDOWS:
        _remove_startup_folder_shortcut()
    return applied


# Initialize settings on module load
load_settings()
