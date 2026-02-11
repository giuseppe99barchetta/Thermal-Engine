"""
Theme Package Import/Export for Thermal Engine.
Handles .thermal ZIP archive format with embedded assets.
"""

import os
import io
import copy
import json
import zipfile
import shutil
import logging

from src.utils.app_path import get_user_data_path
from src.core.security import validate_preset_schema, is_safe_filename, sanitize_preset_name

logger = logging.getLogger(__name__)

THERMAL_EXTENSION = ".thermal"
THEME_JSON_NAME = "theme.json"
THUMBNAIL_NAME = "thumbnail.png"
ASSETS_DIR_NAME = "assets"
MAX_ARCHIVE_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_SINGLE_FILE_SIZE = 200 * 1024 * 1024  # 200 MB per file
ALLOWED_ASSET_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.bmp', '.gif',
    '.mp4', '.avi', '.mkv', '.mov', '.webm',
}


def collect_theme_assets(theme_data):
    """
    Scan theme data for all referenced asset files that exist on disk.

    Returns list of (absolute_path, location_descriptor) tuples.
    """
    assets = []
    for i, elem in enumerate(theme_data.get("elements", [])):
        for field in ("image_path", "gif_path"):
            path = elem.get(field, "")
            if path and os.path.isfile(path):
                assets.append((path, f"elements.{i}.{field}"))

    vb = theme_data.get("video_background", {})
    vb_path = vb.get("video_path", "")
    if vb_path and vb.get("enabled", False) and os.path.isfile(vb_path):
        assets.append((vb_path, "video_background.video_path"))

    return assets


def export_theme(theme_data, thumbnail_image, output_path):
    """
    Export theme as a .thermal ZIP package.

    Args:
        theme_data: Theme dict (same format as _save_to_path)
        thumbnail_image: PIL Image for preview (or None)
        output_path: Destination .thermal file path

    Returns:
        (success: bool, error_or_path: str)
    """
    try:
        assets = collect_theme_assets(theme_data)

        # Map original paths to archive names (deduplicated)
        path_to_archive_name = {}
        used_names = set()

        for abs_path, _ in assets:
            if abs_path in path_to_archive_name:
                continue

            base = os.path.basename(abs_path)
            ext = os.path.splitext(base)[1].lower()

            if ext not in ALLOWED_ASSET_EXTENSIONS:
                logger.warning(f"Skipping unsupported asset: {abs_path}")
                continue

            # Deduplicate names
            name = base
            counter = 1
            while name in used_names:
                stem = os.path.splitext(base)[0]
                name = f"{stem}_{counter}{ext}"
                counter += 1

            used_names.add(name)
            path_to_archive_name[abs_path] = name

        # Deep copy and rewrite paths to relative
        export_data = copy.deepcopy(theme_data)

        for elem in export_data.get("elements", []):
            for field in ("image_path", "gif_path"):
                path = elem.get(field, "")
                if path and path in path_to_archive_name:
                    elem[field] = f"{ASSETS_DIR_NAME}/{path_to_archive_name[path]}"

        vb = export_data.get("video_background", {})
        vb_path = vb.get("video_path", "")
        if vb_path and vb_path in path_to_archive_name:
            vb["video_path"] = f"{ASSETS_DIR_NAME}/{path_to_archive_name[vb_path]}"

        # Write ZIP
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # theme.json
            zf.writestr(THEME_JSON_NAME, json.dumps(export_data, indent=2))

            # thumbnail
            if thumbnail_image:
                buf = io.BytesIO()
                thumb = thumbnail_image.copy()
                thumb.thumbnail((640, 480))
                thumb.save(buf, "PNG")
                zf.writestr(THUMBNAIL_NAME, buf.getvalue())

            # asset files
            for abs_path, archive_name in path_to_archive_name.items():
                zf.write(abs_path, f"{ASSETS_DIR_NAME}/{archive_name}")

        return True, output_path

    except Exception as e:
        logger.error(f"Export failed: {e}")
        return False, str(e)


def validate_thermal_archive(zip_path):
    """
    Validate a .thermal archive for safety before import.

    Returns:
        (is_valid: bool, error: str, theme_data: dict or None)
    """
    try:
        if not zipfile.is_zipfile(zip_path):
            return False, "Not a valid archive", None

        file_size = os.path.getsize(zip_path)
        if file_size > MAX_ARCHIVE_SIZE:
            return False, f"Archive too large ({file_size // (1024 * 1024)} MB)", None

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()

            if THEME_JSON_NAME not in names:
                return False, "Missing theme.json", None

            # Check for path traversal
            for name in names:
                if '..' in name or name.startswith('/') or name.startswith('\\'):
                    return False, f"Suspicious path in archive: {name}", None
                parts = name.replace('\\', '/').split('/')
                if len(parts) > 2:
                    return False, f"Unexpected directory depth: {name}", None
                if len(parts) == 2 and parts[0] != ASSETS_DIR_NAME:
                    return False, f"Unexpected directory: {parts[0]}", None

            # Check individual file sizes
            for info in zf.infolist():
                if info.file_size > MAX_SINGLE_FILE_SIZE:
                    return False, f"File too large: {info.filename}", None

            # Validate theme.json
            theme_json = zf.read(THEME_JSON_NAME)
            theme_data = json.loads(theme_json)

            is_valid, errors = validate_preset_schema(theme_data)
            if not is_valid:
                return False, f"Invalid theme: {', '.join(errors[:3])}", None

            return True, "", theme_data

    except json.JSONDecodeError:
        return False, "Invalid JSON in theme.json", None
    except Exception as e:
        return False, str(e), None


def import_theme(zip_path):
    """
    Import a .thermal package, extracting assets and resolving paths.

    Returns:
        (success: bool, error: str, theme_data: dict or None)
    """
    is_valid, error, theme_data = validate_thermal_archive(zip_path)
    if not is_valid:
        return False, error, None

    try:
        # Create import directory
        theme_name = sanitize_preset_name(theme_data.get("name", "imported"))
        import_dir = get_user_data_path(os.path.join("imported_assets", theme_name))

        # Handle directory collision
        base_dir = import_dir
        counter = 1
        while os.path.exists(import_dir):
            import_dir = f"{base_dir}_{counter}"
            counter += 1

        os.makedirs(import_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Extract only asset files
            for name in zf.namelist():
                if name.startswith(f"{ASSETS_DIR_NAME}/") and name != f"{ASSETS_DIR_NAME}/":
                    asset_filename = os.path.basename(name)
                    safe, err = is_safe_filename(asset_filename)
                    if not safe:
                        logger.warning(f"Skipping unsafe asset: {name} ({err})")
                        continue

                    target_path = os.path.join(import_dir, asset_filename)
                    with zf.open(name) as src, open(target_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

        # Rewrite relative paths to absolute
        for elem in theme_data.get("elements", []):
            for field in ("image_path", "gif_path"):
                path = elem.get(field, "")
                if path and path.startswith(f"{ASSETS_DIR_NAME}/"):
                    filename = os.path.basename(path)
                    elem[field] = os.path.join(import_dir, filename)

        vb = theme_data.get("video_background", {})
        vb_path = vb.get("video_path", "")
        if vb_path and vb_path.startswith(f"{ASSETS_DIR_NAME}/"):
            filename = os.path.basename(vb_path)
            vb["video_path"] = os.path.join(import_dir, filename)

        return True, "", theme_data

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return False, str(e), None
