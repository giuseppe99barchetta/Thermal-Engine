"""
Security utilities for Thermal Engine.
Handles path validation, schema validation, and integrity checks.
"""

import os
import re
from app_path import get_app_dir

# Allowed directories for file loading (relative to app dir)
ALLOWED_SUBDIRS = ['presets', 'elements', 'themes', 'images', 'videos']


def is_safe_path(file_path, allow_absolute=False):
    """
    Validate that a file path is safe to use.

    - Prevents path traversal attacks
    - Optionally restricts to app directory

    Returns: (is_safe: bool, resolved_path: str or None, error: str or None)
    """
    if not file_path:
        return False, None, "Empty path"

    # Normalize the path
    try:
        resolved = os.path.normpath(os.path.abspath(file_path))
    except (ValueError, OSError) as e:
        return False, None, f"Invalid path: {e}"

    # Check for null bytes (path injection)
    if '\x00' in file_path:
        return False, None, "Null byte in path"

    # Check for path traversal patterns
    dangerous_patterns = ['..', '...']
    path_parts = file_path.replace('\\', '/').split('/')
    for part in path_parts:
        if part in dangerous_patterns:
            return False, None, "Path traversal detected"

    if allow_absolute:
        # Allow any absolute path, but verify it exists
        return True, resolved, None

    # Restrict to app directory and subdirectories
    app_dir = get_app_dir()

    # Check if path is within app directory
    try:
        common = os.path.commonpath([resolved, app_dir])
        if common != app_dir:
            return False, None, "Path outside application directory"
    except ValueError:
        # Different drives on Windows
        return False, None, "Path on different drive"

    return True, resolved, None


def is_safe_filename(filename):
    """
    Validate that a filename is safe (no path components).

    Returns: (is_safe: bool, error: str or None)
    """
    if not filename:
        return False, "Empty filename"

    # Check for path separators
    if '/' in filename or '\\' in filename:
        return False, "Filename contains path separator"

    # Check for null bytes
    if '\x00' in filename:
        return False, "Null byte in filename"

    # Check for reserved characters (Windows)
    reserved = '<>:"|?*'
    for char in reserved:
        if char in filename:
            return False, f"Reserved character '{char}' in filename"

    # Check for reserved names (Windows)
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + \
                     [f'COM{i}' for i in range(1, 10)] + \
                     [f'LPT{i}' for i in range(1, 10)]
    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in reserved_names:
        return False, "Reserved filename"

    return True, None


def validate_preset_schema(data):
    """
    Validate preset/theme JSON data against expected schema.

    Returns: (is_valid: bool, errors: list)
    """
    errors = []

    if not isinstance(data, dict):
        return False, ["Root must be a dictionary"]

    # Validate top-level fields
    allowed_keys = {
        'name', 'background_color', 'display_width', 'display_height',
        'elements', 'video_background'
    }
    for key in data.keys():
        if key not in allowed_keys:
            errors.append(f"Unknown key: {key}")

    # Validate name
    if 'name' in data:
        if not isinstance(data['name'], str):
            errors.append("'name' must be a string")
        elif len(data['name']) > 100:
            errors.append("'name' too long (max 100 chars)")

    # Validate background_color
    if 'background_color' in data:
        if not is_valid_color(data['background_color']):
            errors.append("Invalid 'background_color' format")

    # Validate dimensions
    for dim in ['display_width', 'display_height']:
        if dim in data:
            if not isinstance(data[dim], int) or data[dim] < 0 or data[dim] > 10000:
                errors.append(f"Invalid '{dim}' value")

    # Validate elements
    if 'elements' in data:
        if not isinstance(data['elements'], list):
            errors.append("'elements' must be a list")
        else:
            for i, element in enumerate(data['elements']):
                elem_errors = validate_element_schema(element, i)
                errors.extend(elem_errors)

    # Validate video_background
    if 'video_background' in data:
        vb = data['video_background']
        if not isinstance(vb, dict):
            errors.append("'video_background' must be a dictionary")
        else:
            if 'video_path' in vb and vb['video_path']:
                safe, _, err = is_safe_path(vb['video_path'], allow_absolute=True)
                if not safe:
                    errors.append(f"video_background path: {err}")

    return len(errors) == 0, errors


def validate_element_schema(element, index):
    """Validate a single element's schema."""
    errors = []
    prefix = f"Element {index}"

    if not isinstance(element, dict):
        return [f"{prefix}: must be a dictionary"]

    # Required fields
    if 'type' not in element:
        errors.append(f"{prefix}: missing 'type'")
    elif not isinstance(element['type'], str):
        errors.append(f"{prefix}: 'type' must be a string")

    # Validate numeric fields
    numeric_fields = ['x', 'y', 'width', 'height', 'radius', 'font_size', 'value']
    for field in numeric_fields:
        if field in element:
            val = element[field]
            if not isinstance(val, (int, float)):
                errors.append(f"{prefix}: '{field}' must be numeric")
            elif val < -10000 or val > 10000:
                errors.append(f"{prefix}: '{field}' out of range")

    # Validate color fields
    color_fields = ['color', 'background_color']
    for field in color_fields:
        if field in element and element[field]:
            if not is_valid_color(element[field]):
                errors.append(f"{prefix}: invalid '{field}' format")

    # Validate path fields
    path_fields = ['image_path', 'gif_path']
    for field in path_fields:
        if field in element and element[field]:
            safe, _, err = is_safe_path(element[field], allow_absolute=True)
            if not safe:
                errors.append(f"{prefix}: {field}: {err}")

    # Validate string fields length
    string_fields = ['name', 'text', 'font_family', 'source']
    for field in string_fields:
        if field in element:
            if not isinstance(element[field], str):
                errors.append(f"{prefix}: '{field}' must be a string")
            elif len(element[field]) > 500:
                errors.append(f"{prefix}: '{field}' too long")

    return errors


def is_valid_color(color):
    """Validate hex color format."""
    if not isinstance(color, str):
        return False

    # Match #RGB, #RRGGBB, or #RRGGBBAA
    pattern = r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$'
    return bool(re.match(pattern, color))


def escape_registry_path(path):
    """
    Properly escape a path for Windows registry.
    Ensures the path is properly quoted.
    """
    if not path:
        return '""'

    # Remove any existing quotes
    path = path.strip('"')

    # Always wrap in quotes for safety
    return f'"{path}"'


def sanitize_preset_name(name):
    """
    Sanitize a preset name for use as a filename.

    Returns: sanitized name
    """
    if not name:
        return "preset"

    # Remove/replace dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)

    # Limit length
    sanitized = sanitized[:50]

    # Ensure not empty after sanitization
    if not sanitized.strip():
        return "preset"

    return sanitized.strip()
