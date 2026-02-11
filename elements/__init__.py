"""
Custom Elements Loader

Drop custom element Python files into this folder to extend the theme editor.
Each element file should define:
  - ELEMENT_TYPE: str - unique identifier for the element
  - ELEMENT_NAME: str - display name in the UI
  - DEFAULT_PROPS: dict - default properties for new elements
  - draw_preview(painter, element, x, y, scale) - Qt preview rendering
  - render_image(draw, img, element) - PIL rendering for display
"""

import os
import importlib.util
import sys
import re

# Store loaded custom elements
CUSTOM_ELEMENTS = {}

# Allowed characters in element filenames (alphanumeric, underscore, hyphen)
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+\.py$')


def get_elements_dir():
    """Get the elements directory (works for both script and frozen exe)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # PyInstaller uses _MEIPASS, Nuitka puts files next to executable
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            # Nuitka: files are relative to executable directory
            base_path = os.path.dirname(sys.executable)
        return os.path.join(base_path, 'elements')
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


def load_custom_elements():
    """Load all custom element modules from this folder."""
    elements_dir = get_elements_dir()

    for filename in os.listdir(elements_dir):
        # Skip non-Python files and private files
        if not filename.endswith('.py') or filename.startswith('_'):
            continue

        # Validate filename is safe (no path traversal)
        if not SAFE_FILENAME_PATTERN.match(filename):
            print(f"[Elements] Skipping unsafe filename: {filename}")
            continue

        module_name = filename[:-3]
        filepath = os.path.join(elements_dir, filename)

        # Verify file is actually inside elements_dir (prevent symlink attacks)
        real_path = os.path.realpath(filepath)
        real_elements_dir = os.path.realpath(elements_dir)
        if not real_path.startswith(real_elements_dir + os.sep):
            print(f"[Elements] Skipping file outside elements dir: {filename}")
            continue

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, 'ELEMENT_TYPE'):
                CUSTOM_ELEMENTS[module.ELEMENT_TYPE] = {
                    'name': getattr(module, 'ELEMENT_NAME', module.ELEMENT_TYPE),
                    'defaults': getattr(module, 'DEFAULT_PROPS', {}),
                    'draw_preview': getattr(module, 'draw_preview', None),
                    'render_image': getattr(module, 'render_image', None),
                    'module': module
                }
                print(f"[Elements] Loaded custom element: {module.ELEMENT_TYPE}")

        except Exception as e:
            print(f"[Elements] Failed to load {filename}: {e}")

    return CUSTOM_ELEMENTS


def get_custom_element_types():
    """Get list of custom element type names."""
    return list(CUSTOM_ELEMENTS.keys())


def get_custom_element(element_type):
    """Get custom element definition by type."""
    return CUSTOM_ELEMENTS.get(element_type)


# Load on import
load_custom_elements()

# Register custom element types with constants
try:
    from src.core.constants import register_custom_element_types
    register_custom_element_types(CUSTOM_ELEMENTS.keys())
except ImportError:
    pass
