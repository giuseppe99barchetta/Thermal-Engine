"""
Application path utilities.
Handles path resolution for both script and frozen executable.
"""

import sys
import os


def _get_project_root():
    """Get the project root directory when running as script.

    This file lives at src/utils/app_path.py, so we navigate 3 levels up.
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_app_dir():
    """Get the application directory where the exe lives (for user data)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use exe location for user data
        return os.path.dirname(sys.executable)
    else:
        # Running as script - project root
        return _get_project_root()


def get_bundle_dir():
    """Get the bundle directory where packaged resources are (read-only)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - bundled files are in _MEIPASS
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # Running as script - same as app dir (project root)
        return _get_project_root()


def get_resource_path(relative_path):
    """Get absolute path to resource - uses app dir for user data."""
    return os.path.join(get_app_dir(), relative_path)


def get_bundled_resource_path(relative_path):
    """Get absolute path to bundled read-only resource."""
    return os.path.join(get_bundle_dir(), relative_path)


def get_user_data_dir():
    """Get the user data directory (writable location for user files).

    Uses AppData\Local on Windows for installed apps, or app_dir for development.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use AppData\Local
        if sys.platform == 'win32':
            appdata = os.environ.get('LOCALAPPDATA')
            if appdata:
                user_dir = os.path.join(appdata, 'ThermalEngine')
                os.makedirs(user_dir, exist_ok=True)
                return user_dir
        # Fallback to app dir if not Windows
        return get_app_dir()
    else:
        # Running as script - use app dir
        return get_app_dir()


def get_user_data_path(relative_path):
    """Get absolute path to user data file (writable location)."""
    return os.path.join(get_user_data_dir(), relative_path)


# Commonly used paths
APP_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
USER_DATA_DIR = get_user_data_dir()
