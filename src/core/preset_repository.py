"""Preset storage shared by desktop frontends."""
import copy
import json
import logging
from pathlib import Path
from PIL import Image

from src.core.security import validate_preset_schema, is_safe_filename, sanitize_preset_name
from src.utils.app_path import get_user_data_path, get_bundled_resource_path, write_json_atomic

logger = logging.getLogger(__name__)
PROTECTED_PRESETS = {"Default", "System Monitor", "Minimal"}


def preview_background(data, size):
    """Read one media frame without changing the editor's active video worker."""
    video = data.get("video_background", {})
    path = video.get("video_path", "")
    if not video.get("enabled") or not path or not Path(path).is_file():
        return None
    try:
        with Image.open(path) as image:
            frame = image.convert("RGBA")
    except OSError:
        try:
            import cv2
            capture = cv2.VideoCapture(path)
            try:
                success, pixels = capture.read()
                if not success: return None
                frame = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGBA))
            finally:
                capture.release()
        except (ImportError, OSError, ValueError):
            return None
    scale = size[0] / frame.width if video.get("fit_mode") == "fit_width" else size[1] / frame.height
    frame = frame.resize((max(1, round(frame.width * scale)), max(1, round(frame.height * scale))), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", size, "black")
    background.paste(frame, ((size[0] - frame.width) // 2, (size[1] - frame.height) // 2), frame)
    return background


def resolve_assets(data, root):
    root = Path(root).resolve()
    for element in data.get("elements", []):
        for key in ("image_path", "gif_path"):
            path = element.get(key)
            if path and not Path(path).is_absolute():
                candidate = (root / path).resolve()
                if candidate.is_relative_to(root) and candidate.is_file():
                    element[key] = str(candidate)
    video = data.get("video_background", {})
    path = video.get("video_path")
    if path and not Path(path).is_absolute():
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            video["video_path"] = str(candidate)
    return data


class PresetRepository:
    def __init__(self):
        self.user_dir = Path(get_user_data_path("presets"))
        self.builtin_dir = Path(get_bundled_resource_path("presets"))
        self.presets = {}
        self.load()

    def load(self):
        self.presets = {}
        for root, builtin in ((self.builtin_dir, True), (self.user_dir, False)):
            if not root.is_dir():
                continue
            for path in root.glob("*.json"):
                try:
                    if not is_safe_filename(path.name)[0]:
                        continue
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if not validate_preset_schema(data)[0]:
                        continue
                    name = data.get("name", path.stem)
                    if not builtin and name in PROTECTED_PRESETS and name in self.presets:
                        continue
                    self.presets[name] = {"data": resolve_assets(data, root), "builtin": builtin,
                                          "path": str(path), "thumbnail": str(path.with_suffix(".png"))}
                except (OSError, ValueError, TypeError):
                    logger.warning("Could not read preset %s", path.name)

    def is_read_only(self, name):
        """Bundled themes are never overwritten; edits are saved as a copy under a new name."""
        preset = self.presets.get(name)
        return name in PROTECTED_PRESETS or bool(preset and preset["builtin"])

    def save(self, name, data, frame=None):
        if name in PROTECTED_PRESETS:
            raise ValueError("Choose a new name to save a copy of this built-in theme.")
        filename = sanitize_preset_name(name) + ".json"
        safe, error = is_safe_filename(filename)
        if not safe:
            raise ValueError(error)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / filename
        write_json_atomic(str(path), data)
        if frame is not None:
            try:
                frame = frame.copy()
                frame.thumbnail((300, 180))
                frame.save(path.with_suffix(".png"))
            except OSError:
                logger.warning("Could not save preset thumbnail")
        self.presets[name] = {"data": copy.deepcopy(data), "builtin": False, "path": str(path),
                              "thumbnail": str(path.with_suffix(".png"))}

    def delete(self, name):
        preset = self.presets.get(name)
        if not preset or preset["builtin"]:
            raise ValueError("Built-in presets cannot be deleted.")
        path = Path(preset["path"]).resolve()
        if not path.is_relative_to(self.user_dir.resolve()):
            raise ValueError("Preset is outside the user directory.")
        path.unlink(missing_ok=True)
        path.with_suffix(".png").unlink(missing_ok=True)
        self.presets.pop(name)
