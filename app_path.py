"""
Application path utilities.
Handles path resolution for both script and frozen executable.
"""

import sys
import os


def get_app_dir():
    """Get the application directory where the exe lives (for user data)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - use exe location for user data
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir():
    """Get the bundle directory where packaged resources are (read-only)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - bundled files are in _MEIPASS
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # Running as script - same as app dir
        return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    """Get absolute path to resource - uses app dir for user data."""
    return os.path.join(get_app_dir(), relative_path)


def get_bundled_resource_path(relative_path):
    """Get absolute path to bundled read-only resource."""
    return os.path.join(get_bundle_dir(), relative_path)


# Commonly used paths
APP_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
