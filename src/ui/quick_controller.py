"""Application commands and observable editor state for Qt Quick."""
import copy
import json
import logging
import math
import sys
import threading
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl, Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtGui import QImage

from elements import get_custom_element_types, get_custom_element
from src.core import constants, sensors
from src.core.document import EditorDocument
from src.core.frame_pipeline import FramePipeline
from src.core.element import ThemeElement
from src.core.renderer import ThemeRenderer
from src.core.preset_repository import PresetRepository, resolve_assets, preview_background
from src.core.security import validate_element_schema, is_valid_color
from src.core.display_size import validate_display_size, get_device_size_override, device_size_key, DISPLAY_SIZE_PROFILES
from src.core.device_backends import enumerate_available_devices, create_backend
from src.core.network_sensors import validate_sources, NetworkSensorManager
from src.ui.video_background import video_background, HAS_CV2
from src.ui.quick_models import RowsModel
from src.utils import settings
from src.utils.app_path import write_json_atomic
from src.utils.app_version import get_version

logger = logging.getLogger(__name__)

ENUMS = {"text_align": ["left", "center", "right"], "bar_text_mode": ["full", "value_only", "none"],
         "bar_text_position": ["top", "inside", "bottom"], "bar_border_position": ["inside", "center", "outside"],
         "time_format": ["24h", "12h"], "clock_face_style": ["numbers", "ticks", "none"],
         "scale_mode": ["fit", "fill", "stretch"]}
GEOMETRY = {"x", "y", "width", "height", "radius", "border_radius", "clip", "page"}
TYPE_FIELDS = {
    "image": {"image_path", "scale_proportionally", "aspect_ratio"},
    "gif": {"gif_path", "scale_mode"},
    "line_chart": {"show_background", "show_label", "show_gradient", "line_thickness", "smooth"},
    "bar_gauge": {"rounded_corners", "gradient_fill", "gradient_stops", "bar_text_mode", "bar_text_position",
                  "bar_border", "bar_border_width", "bar_border_color", "bar_border_opacity", "bar_border_position"},
    "clock": {"time_format", "show_am_pm", "show_seconds", "show_leading_zero"},
    "digital_clock": {"time_format", "show_am_pm", "show_seconds", "show_leading_zero"},
    "analog_clock": {"time_format", "show_seconds_hand", "show_clock_border", "clock_face_style", "smooth_animation"},
    "circle_gauge": {"animate_gauge", "animation_speed", "auto_color_change", "gauge_rounded_ends"},
}
ALL_TYPE_FIELDS = set().union(*TYPE_FIELDS.values())
TYPE_LABELS = {"text": "Text", "rectangle": "Rectangle", "circle_gauge": "Circle gauge", "bar_gauge": "Bar gauge",
               "line_chart": "Line chart", "image": "Image", "gif": "GIF", "clock": "Digital clock",
               "digital_clock": "Digital clock", "analog_clock": "Analog clock"}
PROFILE_SETTINGS = {"system_profile_enabled": False, "system_idle_preset": None, "system_gaming_preset": None,
                    "system_idle_threshold": 15, "system_idle_seconds": 60,
                    "system_gaming_threshold": 60, "system_gaming_seconds": 10, "display_orientation": "normal"}


def pil_image(frame):
    frame = frame.convert("RGB")
    return QImage(frame.tobytes(), frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888).copy()


class ThumbnailProvider(QQuickImageProvider):
    def __init__(self, controller):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self.controller = controller

    def requestImage(self, key, size, requested_size):
        key = key.split("?")[0]
        image = self.controller.thumbnails.get(key, QImage())
        size.setWidth(image.width())
        size.setHeight(image.height())
        return image


class ConsoleHandler(logging.Handler):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record):
        self.controller.consoleLine.emit(self.format(record))


class EditorController(QObject, FramePipeline):
    changed = Signal()
    selectionChanged = Signal()
    requestDialog = Signal(str, 'QVariantMap')
    consoleLine = Signal(str)
    videoResult = Signal(bool, str)
    videoRestored = Signal(int, str)
    frameDelivered = Signal()

    def __init__(self, start_services=True, parent=None):
        QObject.__init__(self, parent)
        self.document = EditorDocument()
        self.document.width = settings.get_setting("last_display_width", 480)
        self.document.height = settings.get_setting("last_display_height", 480)
        constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT = validate_display_size(self.document.width, self.document.height)
        self.layers_model, self.pages_model = RowsModel(self), RowsModel(self)
        self.presets_model, self.devices_model, self.sensors_model = RowsModel(self), RowsModel(self), RowsModel(self)
        self.sensor_browser_model = RowsModel(self)
        self.preset_browser_model = RowsModel(self)
        self._preset_filter = ("", False)
        self._sensor_filter = ("Summary", "All groups", "", False)
        self.repository = PresetRepository()
        self.canvas = None
        self.window = None
        self.backend = self.device = self.selected_device_def = None
        self.live_preview_timer = None
        self._render_thread = None
        self._render_thread_running = False
        self._frame_request = threading.Event()
        self._frame_snapshot_lock = threading.Lock()
        self._frame_snapshot = self._frame_error = None
        self._last_frame_request_time = 0
        self._canvas_update_counter, self._canvas_update_interval = 0, 3
        self._animated_values = {}
        self._collapsed_groups = set()  # Group names folded in the layer list
        self._recent_colors = []  # Most recent first; feeds the color swatches
        self.frame_times = []
        self.last_frame_time = 0
        self.renderer = ThemeRenderer()
        self.thumbnails = {}
        self._preview_frame = None
        self._last_device_frame = None  # Latest frame rendered by the device worker
        self.revision = 0
        self.target_fps = settings.get_setting("target_fps", 30)
        self.display_brightness = settings.get_setting("display_brightness", 100)
        self.display_orientation = settings.get_setting("display_orientation", "normal")
        self.theme_path = None
        self.status = ""
        self._status_until = 0.0  # Notifications show until then; afterwards the context summary returns
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self.changed.emit)
        self.dirty = False
        self._pending = {}
        self._unsaved_token = None
        self._after_save = None
        self._probe = None
        self._network_error = ""
        self._network_draft = []
        self._probe_result = ""
        self._closed = False
        self._gesture = False
        self._video_generation = 0
        self._owns_video = False
        self._start_services = start_services
        self._hardware_check_ready = False
        self._hardware_prompted = False
        self._console_handler = ConsoleHandler(self)
        logging.getLogger().addHandler(self._console_handler)
        self._foreground_monitor = self._system_state_monitor = None
        self._profile_manager = None
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self._reconnect_attempts = 0
        self._was_connected_before_sleep = False
        self.rotation = QTimer(self)
        self.rotation.timeout.connect(self._rotate)
        self.rotation_interval = 5
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._preview_tick)
        self.sensors_timer = QTimer(self)
        self.sensors_timer.timeout.connect(self.refresh_sensors)
        self.probe_timer = QTimer(self)
        self.probe_timer.timeout.connect(self._probe_tick)
        self.autosave = QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.timeout.connect(self._autosave)
        self.videoResult.connect(self._video_result)
        self.videoRestored.connect(self._video_restored, Qt.ConnectionType.QueuedConnection)
        self.frameDelivered.connect(self.record_frame_time, Qt.ConnectionType.QueuedConnection)
        self.reload_presets()
        self.refresh_sensors()
        default = settings.get_setting("default_preset") or settings.get_setting("last_preset") or self._starter_preset()
        if default in self.repository.presets:
            self.document.load(copy.deepcopy(self.repository.presets[default]["data"]))
            self.document.undo_stack.clear()
        self.refresh(mark_dirty=False)
        if start_services:
            try:
                sensors.configure_network_sensors(settings.get_setting("network_sensors", []))
            except (ValueError, RuntimeError) as exc:
                self.notify(str(exc))
            self.preview_timer.start(50)
            self.sensors_timer.start(1000)
            self._start_profiles()

    @property
    def elements(self):
        return self.document.elements

    @property
    def background_color(self):
        return self.document.background_color

    @property
    def current_page(self):
        return self.document.current_page

    @Property('QVariantMap', notify=changed)
    def state(self):
        return {"name": self.document.theme_name, "background": self.background_color,
                "width": self.document.width, "height": self.document.height, "page": self.current_page,
                "pages": list(self.document.pages),
                "connected": self.device is not None, "device": self.selected_device_def.name if self.selected_device_def else "Offline editor",
                "fps": self.target_fps, "actualFps": round(len(self.frame_times) / sum(self.frame_times), 1) if self.frame_times and sum(self.frame_times) else 0,
                "status": self._status_text(), "dirty": self.dirty, "canUndo": bool(self.document.undo_stack),
                "canRedo": bool(self.document.redo_stack), "selectionCount": len(self.document.selection),
                "revision": self.revision, "zoom": round(self.canvas.scale * 100) if self.canvas else 100,
                "grid": self.canvas.show_grid if self.canvas else settings.get_setting("show_grid", True),
                "snap": self.canvas.snap_to_grid if self.canvas else settings.get_setting("snap_to_grid", True),
                "rotation": self.rotation.isActive(), "rotationInterval": self.rotation_interval,
                "orientation": self.display_orientation, "brightness": self.display_brightness,
                "previewFraction": -1 if self.preview_fraction is None else self.preview_fraction,
                "video": video_background.to_dict(), "version": get_version(), "probeResult": self._probe_result,
                "networkError": self._network_error,
                "layersWidth": settings.get_setting("layers_panel_width", 244),
                "inspectorWidth": settings.get_setting("inspector_panel_width", 296)}

    @Property('QVariantMap', notify=selectionChanged)
    def selected(self):
        selected = self.document.selected()
        return copy.deepcopy(selected[0].to_dict()) if len(selected) == 1 else {}

    @Property('QVariantList', notify=selectionChanged)
    def propertyRows(self):
        data = self.selected
        if not data:
            return []
        rows = []
        kind = data.get("type")
        allowed = TYPE_FIELDS.get(kind, set()) | ({"animate_gauge", "animation_speed", "auto_color_change", "gradient_stops"} if kind in ("bar_gauge", "circle_gauge") else set())
        for key, value in data.items():
            if key in {"type", "name", "source", "condition", "locked", "visible", "group"}:
                continue
            if key in ALL_TYPE_FIELDS and key not in allowed:
                continue
            if key == "radius" and kind not in ("circle_gauge", "analog_clock"):
                continue
            if key == "border_radius" and kind != "rectangle":  # Only rectangles draw rounded corners
                continue
            if key == "clip" and kind not in ("text", "clock", "digital_clock"):  # Only text is clipped
                continue
            if key in ("width", "height") and kind in ("circle_gauge", "analog_clock"):
                continue
            if key in ("value", "max_value", "temp_hide_unit"):
                if key == "value" and (data.get("source") != "static" or kind not in ("circle_gauge", "bar_gauge", "line_chart", "text")): continue
                if key == "max_value" and kind not in ("bar_gauge", "circle_gauge", "line_chart"): continue
                if key == "temp_hide_unit" and kind not in ("text", "bar_gauge", "circle_gauge"): continue
                section = "Data & range"
            elif key in GEOMETRY: section = "Position & size"
            elif key in ("animate_gauge", "animation_speed", "auto_color_change", "gradient_fill", "gradient_stops", "gauge_rounded_ends", "rounded_corners"): section = "Gauge & animation"
            elif key.startswith("glass_"): section = "Glass effect"
            elif key.startswith("bar_border"): section = "Border"
            elif key in TYPE_FIELDS.get("image", set()) | TYPE_FIELDS.get("gif", set()): section = "Media"
            elif key in TYPE_FIELDS.get("clock", set()) | TYPE_FIELDS.get("analog_clock", set()): section = "Clock"
            elif key in TYPE_FIELDS.get("line_chart", set()): section = "Chart"
            elif key.startswith("label_"): section = "Label"
            elif "font" in key or key in ("text", "text_align", "text_color", "text_color_opacity", "use_custom_text_color", "bar_text_mode", "bar_text_position"): section = "Text & value"
            else: section = "Appearance"
            if kind in ("image", "gif", "rectangle") and section in ("Text & value", "Label", "Data & range"): continue
            if kind != "rectangle" and section == "Glass effect": continue
            if kind not in ("bar_gauge", "circle_gauge", "line_chart", "analog_clock") and section == "Label": continue
            if kind in ("image", "gif") and key in ("color", "background_color", "background_color_opacity"): continue
            if key == "animation_speed" and not data.get("animate_gauge"): continue
            if key == "gradient_stops" and not (data.get("gradient_fill") or data.get("auto_color_change")): continue
            if key.startswith("glass_") and key != "glass_effect" and not data.get("glass_effect"): continue
            if key.startswith("bar_border_") and not data.get("bar_border"): continue
            choices = ENUMS.get(key, list(QFontDatabase.families()) if key.endswith("font_family") else [])
            field_type = "choice" if choices else "boolean" if isinstance(value, bool) else "number" if isinstance(value, (float, int)) else "json" if isinstance(value, (list, dict)) else "path" if key.endswith("_path") else "color" if "color" in key and "opacity" not in key and isinstance(value, str) and value.startswith("#") else "text"
            minimum, maximum = (0, 100) if "opacity" in key else (1, 10000) if key in ("width", "height", "radius", "font_size", "label_font_size", "max_value", "page", "line_thickness") else (0.01, 0.9) if key == "animation_speed" else (0.001, 1000) if key == "aspect_ratio" else (-10000, 10000)
            integer = isinstance(value, int)
            unit = "%" if "opacity" in key else "px" if key in ("x", "y", "width", "height", "radius", "font_size", "label_font_size", "border_radius") else ""
            rows.append({"key": key, "label": key.replace("_", " ").capitalize(), "value": json.dumps(value) if field_type == "json" else value,
                         "kind": field_type, "choices": choices, "section": section,
                         "minimum": minimum, "maximum": maximum, "integer": integer,
                         "step": 1 if integer else 0.01 if key == "animation_speed" else 0.1, "unit": unit})
        order = ["Position & size", "Data & range", "Media", "Text & value", "Label", "Appearance", "Gauge & animation", "Border", "Glass effect", "Chart", "Clock"]
        return sorted(rows, key=lambda r: (order.index(r["section"]), list(data).index(r["key"])))

    @Property('QVariantList', notify=selectionChanged)
    def propertySections(self):
        sections = []
        for row in self.propertyRows:
            if not sections or sections[-1]["title"] != row["section"]:
                sections.append({"title": row["section"], "rows": [], "open": row["section"] in ("Position & size", "Media", "Clock", "Data & range")})
            sections[-1]["rows"].append(row)
        return sections

    @Property(QObject, constant=True)
    def layers(self): return self.layers_model

    @Property(QObject, constant=True)
    def pages(self): return self.pages_model

    @Property(QObject, constant=True)
    def presets(self): return self.presets_model

    @Property(QObject, constant=True)
    def presetBrowser(self): return self.preset_browser_model

    @Slot(str, bool)
    def filterPresets(self, query, all_resolutions):
        self._preset_filter = (query.lower(), all_resolutions)
        self._filter_presets()

    def _filter_presets(self):
        query, all_resolutions = self._preset_filter
        self.preset_browser_model.replace([row for row in self.presets_model.rows if query in row["name"].lower()
                                           and (all_resolutions or (row["width"], row["height"]) == (self.document.width, self.document.height))])

    @Property(QObject, constant=True)
    def devices(self): return self.devices_model

    @Property(QObject, constant=True)
    def sensorModel(self): return self.sensors_model

    @Property(QObject, constant=True)
    def sensorBrowser(self): return self.sensor_browser_model

    @Property('QStringList', notify=changed)
    def sensorCategories(self):
        return ["All groups"] + sorted({row["category"] for row in self.sensors_model.rows if row["scope"] == self._sensor_filter[0]})

    @Slot(str, str, str, bool)
    def filterSensors(self, scope, category, query, show_unavailable):
        self._sensor_filter = (scope, category, query.lower(), show_unavailable)
        self._filter_sensors()
        self.changed.emit()

    def _filter_sensors(self):
        scope, category, query, show_unavailable = self._sensor_filter
        rows, previous = [], None
        for row in self.sensors_model.rows:
            if row["scope"] != scope or (category != "All groups" and row["category"] != category): continue
            if query not in (row["name"] + " " + row["category"] + " " + row["id"]).lower(): continue
            if not show_unavailable and not row["available"]: continue
            rows.append({**row, "heading": row["category"] != previous})
            previous = row["category"]
        self.sensor_browser_model.replace(rows)

    @Property('QStringList', constant=True)
    def elementTypes(self):
        return ["text", "rectangle", "circle_gauge", "bar_gauge", "line_chart", "image", "gif", "clock", "analog_clock"] + [t for t in get_custom_element_types() if t not in ("line_chart", "gif")]

    @Property('QVariantMap', constant=True)
    def typeLabels(self):
        custom = {t: (get_custom_element(t) or {}).get("name", t) for t in get_custom_element_types()}
        return {**custom, **TYPE_LABELS}

    @Property('QVariantList', notify=changed)
    def sources(self):
        groups = {source[0]: category for category, sources in constants.DATA_SOURCES_CATEGORIZED.items() for source in sources}
        rows = [{"id": key, "name": info["name"].split(" [", 1)[0], "category": groups.get(key, "Other")} for key, info in constants.SOURCE_UNITS.items()]
        known = set(constants.SOURCE_UNITS)
        missing = {e.source for e in self.elements} | {e.condition.get("source") for e in self.elements if e.condition}
        rows.extend({"id": key, "name": key + " (unavailable)", "category": "Unavailable sources"} for key in sorted(missing - known - {None}))
        return rows

    @Property('QVariantList', constant=True)
    def sizeProfiles(self):
        return [{"name": name, "width": width, "height": height} for name, width, height in DISPLAY_SIZE_PROFILES]

    @Property('QStringList', notify=changed)
    def colorSwatches(self):
        """Recently applied colors, then the theme's own colors by how often they are used."""
        from collections import Counter
        used = Counter([self.document.background_color.lower()])
        for element in self.elements:
            for key, value in element.to_dict().items():
                if key.endswith("color") and is_valid_color(value):
                    used[value.lower()] += 1
        swatches = []
        for color in self._recent_colors + [color for color, _ in used.most_common()]:
            if color not in swatches:
                swatches.append(color)
        return swatches[:10]

    def _remember_color(self, value):
        if isinstance(value, str) and is_valid_color(value):
            value = value.lower()
            self._recent_colors = [value] + [c for c in self._recent_colors if c != value][:9]

    @Property('QVariantList', notify=changed)
    def networkDraft(self):
        return copy.deepcopy(self._network_draft)

    NOTIFY_SECONDS = 6

    def notify(self, message, sticky=False):
        """Show a status message; it gives way to the context summary after a few seconds unless sticky."""
        self.status = str(message)
        self._status_until = math.inf if sticky else time.monotonic() + self.NOTIFY_SECONDS
        if not sticky:
            self._status_timer.start(self.NOTIFY_SECONDS * 1000)
        self.consoleLine.emit(self.status)
        self.changed.emit()

    def _status_text(self):
        if self.status and time.monotonic() < self._status_until:
            return self.status
        doc = self.document
        count = sum(1 for e in doc.elements if e.page == doc.current_page)
        parts = [f"Page {doc.pages.index(doc.current_page) + 1} of {len(doc.pages)}" if doc.current_page in doc.pages else "",
                 "No elements yet — use + Add" if count == 0 else f"{count} element{'s' * (count != 1)}"]
        if doc.selection:
            parts.append(f"{len(doc.selection)} selected")
        parts.append(f"Streaming to {self.selected_device_def.name}" if self.device and self.selected_device_def
                     else "Offline — Connect to drive the display")
        return " · ".join(p for p in parts if p)

    def attach_canvas(self, canvas):
        self.canvas = canvas
        canvas.frame_renderer = lambda: self._preview_frame
        canvas.show_grid = settings.get_setting("show_grid", True)
        canvas.snap_to_grid = settings.get_setting("snap_to_grid", True)
        self.refresh(mark_dirty=False)

    def refresh(self, mark_dirty=True):
        constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT = self.document.width, self.document.height
        self._preview_frame = self.render_theme_image()
        # Only the edited page changes; other pages' thumbnails are rebuilt when missing
        self.update_thumbnails({self.current_page} | {p for p in self.document.pages if f"page/{p}" not in self.thumbnails})
        self._refresh_layers()
        self._filter_presets()
        self.pages_model.replace([{"number": page, "name": f"Page {page}", "current": page == self.current_page} for page in self.document.pages])
        if self.canvas:
            self.canvas.set_elements(self.elements, self.current_page)
            self.canvas.set_selected_indices(self.document.selection)
            self.canvas.set_background_color(self.background_color)
            self.canvas._update_scale()
        self.revision += 1
        if mark_dirty:
            self.dirty = True
            if not self._needs_new_name(self.document.theme_name):
                self.autosave.start(3000)
        self.selectionChanged.emit()
        self.changed.emit()

    def sync_selection(self):
        self.selectionChanged.emit()
        if self.canvas:
            self.canvas.update()

    def _refresh_layers(self):
        """Layer rows in front-to-back order; each group gets a header row followed by its members."""
        selection = set(self.document.selection)
        on_page = [(i, e) for i, e in enumerate(self.elements) if e.page == self.current_page]
        members = {}
        for i, e in on_page:
            if e.group:
                members.setdefault(e.group, []).append((i, e))

        def element_row(i, e):
            return {"kind": "element", "index": i, "name": e.name, "type": e.type, "group": e.group or "",
                    "locked": e.locked, "visible": e.visible, "selected": i in selection, "indented": bool(e.group)}

        rows, emitted = [], set()
        for i, e in on_page:
            if not e.group:
                rows.append(element_row(i, e))
            elif e.group not in emitted:
                emitted.add(e.group)
                group = members[e.group]
                collapsed = e.group in self._collapsed_groups
                rows.append({"kind": "group", "index": group[0][0], "name": e.group, "type": "group", "group": e.group,
                             "count": len(group), "collapsed": collapsed,
                             "visible": any(m.visible for _, m in group), "locked": all(m.locked for _, m in group),
                             "selected": all(j in selection for j, _ in group), "indented": False})
                if not collapsed:
                    rows.extend(element_row(j, m) for j, m in group)
        self.layers_model.replace(rows)

    @Slot(str)
    def toggleGroup(self, name):
        self._collapsed_groups ^= {name}
        self._refresh_layers()

    @Slot(int, int, bool)
    def moveLayer(self, source, target, after):
        """Drag-reorder: put element `source` just before (or after) element `target` on the same page."""
        doc = self.document
        if source == target or not (0 <= source < len(doc.elements) and 0 <= target < len(doc.elements)):
            return
        moving, anchor = doc.elements[source], doc.elements[target]
        if moving.locked or moving.page != doc.current_page or anchor.page != doc.current_page:
            return
        selected = [doc.elements[i] for i in doc.selection]
        doc.begin()
        doc.elements.remove(moving)
        doc.elements.insert(doc.elements.index(anchor) + (1 if after else 0), moving)
        doc.selection = [doc.elements.index(e) for e in selected]
        doc.commit()
        self.refresh()

    def select_indices(self, indices):
        """Selection only changes overlays and panels, so nothing is re-rendered."""
        self.document.selection = [int(i) for i in indices if 0 <= int(i) < len(self.elements) and self.elements[int(i)].page == self.current_page]
        if self.canvas:
            self.canvas.set_selected_indices(self.document.selection)
            self.canvas.update()
        self._refresh_layers()
        self.selectionChanged.emit()
        self.changed.emit()

    @Slot(int, bool, bool)
    def selectLayer(self, index, extend=False, group=False):
        if not 0 <= index < len(self.elements): return
        indices = list(self.document.selection) if extend else []
        chosen = [i for i, e in enumerate(self.elements) if e.page == self.current_page and e.group == self.elements[index].group] if group and self.elements[index].group else [index]
        for i in chosen:
            if i in indices: indices.remove(i)
            else: indices.append(i)
        self.select_indices(indices)

    @Slot(str, 'QVariant')
    def edit(self, key, value):
        try:
            if hasattr(value, "toVariant"): value = value.toVariant()
            chosen = self.document.selected()
            if not chosen or key not in chosen[0].to_dict() or key == "type": return
            if key not in ("locked", "visible"):
                chosen = self.document.selected(editable=True)
            converted = []
            for element in chosen:
                old = getattr(element, key)
                new = value
                if isinstance(old, bool): new = bool(value)
                elif isinstance(old, int): new = int(float(value))
                elif isinstance(old, float): new = float(value)
                elif isinstance(old, (list, dict)) and isinstance(value, str): new = json.loads(value)
                elif key == "group": new = str(value) or None
                elif isinstance(old, str): new = str(value)
                if isinstance(new, (int, float)) and not math.isfinite(new): raise ValueError("Use a finite number")
                if key == "gradient_stops":
                    if not isinstance(new, list) or len(new) < 2: raise ValueError("Use at least two gradient stops")
                    if any(not isinstance(stop, (list, tuple)) or len(stop) != 2 or
                           not isinstance(stop[0], (int, float)) or not 0 <= stop[0] <= 1 or
                           not is_valid_color(stop[1]) for stop in new): raise ValueError("Invalid gradient position or color")
                    new = sorted((float(position), color) for position, color in new)
                data = {**element.to_dict(), key: new}
                if element.source != "static": data["value"] = 0
                errors = validate_element_schema(data, 0)
                if errors: raise ValueError("\n".join(errors))
                converted.append((element, new))
            self.document.begin()
            for element, new in converted:
                setattr(element, key, new)
                if key == "page" and new not in self.document.pages: self.document.pages.append(new)
            if key.endswith("color"):
                self._remember_color(value)
            if not self._gesture:
                changed = self.document.commit()
                self.refresh(mark_dirty=changed)
            else:
                self._preview_frame = self.render_theme_image()
                if self.canvas: self.canvas.update()
        except (ValueError, TypeError, OverflowError) as exc:
            self.error(str(exc))

    @Slot(str, 'QVariant')
    def command(self, action, value=None):
        if hasattr(value, "toVariant"): value = value.toVariant()
        try:
            self._command(action, value)
        except Exception as exc:
            logger.exception("Editor command failed: %s", action)
            self.error(str(exc))

    @Slot()
    def beginEdit(self):
        self._gesture = True
        self.document.begin()

    @Slot()
    def endEdit(self):
        self._gesture = False
        changed = self.document.commit()
        self.refresh(mark_dirty=changed)

    def _command(self, action, value):
        doc = self.document
        if action == "add":
            if value not in self.elementTypes: raise ValueError("Unknown element type")
            doc.begin()
            custom = get_custom_element(value) or {}
            props = copy.deepcopy(custom.get("defaults", {}))
            props.update(page=doc.current_page, name=f"{value.replace('_', ' ').title()} {len(doc.elements) + 1}")
            element = ThemeElement(value, **props)
            self._place_at_view_center(element)
            doc.elements.insert(0, element)
            doc.selection = [0]
            doc.commit()
            self.refresh()
        elif action in ("undo", "redo", "copy", "paste", "delete"):
            if action == "delete":
                self.confirm("Delete elements", "Remove the selected unlocked elements?", lambda: self._remove())
                return
            getattr(doc, action)()
            if action in ("undo", "redo"): self._restore_video()
            self.refresh(mark_dirty=action != "copy")
        elif action in ("front", "back", "up", "down"):
            doc.reorder(action)
            self.refresh()
        elif action == "selectAll":
            self.select_indices([i for i, e in enumerate(self.elements) if e.page == self.current_page])
        elif action == "group": self.prompt("Create group", "Group name", "Group", lambda name: self._group(name))
        elif action == "ungroup": self._group(None)
        elif action == "align": self._align(value)
        elif action == "page":
            doc.current_page = int(value)
            doc.selection = []
            self.refresh(mark_dirty=False)
        elif action == "addPage":
            doc.begin()
            doc.current_page = max(doc.pages) + 1
            doc.pages.append(doc.current_page)
            doc.selection = []
            doc.commit()
            self.refresh()
        elif action == "deletePage":
            if len(doc.pages) == 1: raise ValueError("The last page cannot be deleted")
            page = int(value)
            self.confirm("Delete page", f"Remove Page {page} and its elements?", lambda: self._delete_page(page))
        elif action == "name":
            doc.begin(); doc.theme_name = str(value)[:100]; doc.commit(); self.refresh()
        elif action == "background":
            if not is_valid_color(value): raise ValueError("Use a valid hex color")
            self._remember_color(value)
            doc.begin(); doc.background_color = value; doc.commit(); self.refresh()
        elif action == "new": self.guard_changes(self._new)
        elif action in ("open", "saveAs", "exportImage", "exportPackage", "importPackage", "image", "gif", "video"):
            self.requestDialog.emit("file", {"action": action})
        elif action == "save": self.save()
        elif action == "loadPreset":
            self.guard_changes(lambda: self._load_preset(value))
        elif action == "deletePreset": self.confirm("Delete preset", f"Delete {value}?", lambda: self._delete_preset(value))
        elif action == "defaultPreset": settings.set_setting("default_preset", value); self.notify(f"Default preset: {value}")
        elif action == "grid":
            if self.canvas: self.canvas.set_show_grid(bool(value))
            settings.set_setting("show_grid", bool(value)); self.changed.emit()
        elif action == "snap":
            if self.canvas: self.canvas.set_snap_to_grid(bool(value))
            settings.set_setting("snap_to_grid", bool(value)); self.changed.emit()
        elif action == "previewValues":
            # Simulated readings for the editor only; the display keeps live data
            self.preview_fraction = None if value is None or float(value) < 0 else max(0.0, min(1.0, float(value)))
            self.refresh(mark_dirty=False)
        elif action == "fit":
            if self.canvas: self.canvas.fit()
        elif action == "rotation":
            if value: self.rotation.start(self.rotation_interval * 1000)
            else: self.rotation.stop()
            self.changed.emit()
        elif action == "rotationInterval":
            self.rotation_interval = max(1, min(60, int(value)))
            if self.rotation.isActive(): self.rotation.start(self.rotation_interval * 1000)
            self.changed.emit()
        elif action == "connect":
            if self.device: self.disconnect_display()
            else: self.openDevices()
        elif action == "send": self.send_frame_with_sensors()
        elif action == "refreshSensors": sensors.invalidate_sensor_cache(); QTimer.singleShot(750, self.refresh_sensors)
        elif action == "network": self.openNetwork()
        elif action == "condition": self.requestDialog.emit("condition", {"rule": self.selected.get("condition", {})})
        elif action == "gradient": self.requestDialog.emit("gradient", {"stops": self.selected.get("gradient_stops", [])})
        elif action == "color": self.requestDialog.emit("color", {"key": value, "value": self.background_color if value == "theme" else self.selected.get(value, "#ffffff")})
        elif action == "clearVideo":
            doc.begin(); video_background.clear_video(); doc.video = {}; doc.commit(); self.refresh()
        elif action == "videoFit":
            doc.begin(); video_background.set_fit_mode(value); doc.video = video_background.to_dict(); doc.commit(); self.refresh()
        elif action == "diagnostics": self.requestDialog.emit("diagnostics", {"text": self.diagnostics()})
        elif action == "hardwareSetup":
            self._hardware_prompted = True
            self.requestDialog.emit("hardware", {})
        elif action == "pawnio":
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl("https://github.com/namazso/PawnIO.Setup/releases/tag/2.2.0"))
        elif action == "restartAdmin":
            import ctypes
            import subprocess
            import sys
            if sys.platform != "win32": return
            if settings._is_windows_elevated():
                self.notify("Already running as Administrator.")
                return
            if self.dirty:
                self.error("Save your theme before restarting as Administrator, then try again. Your current session is still open.")
                return
            arguments = sys.argv[1:] + ["--wait-for-pid", str(__import__("os").getpid())]
            # Relaunch the same script even when started from another working directory
            if not getattr(sys, "frozen", False): arguments.insert(0, str(Path(sys.argv[0]).resolve()))
            if ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, subprocess.list2cmdline(arguments), None, 1) > 32:
                if self.window: self.window.force_quit()
            else:
                self.error("Administrator restart was cancelled or Windows could not start the application. Your current session is still open.")
        elif action == "copyDiagnostics": QGuiApplication.clipboard().setText(self.diagnostics()); self.notify("Diagnostics copied")
        elif action == "settings": self.requestDialog.emit("settings", self.settingsData())
        elif action == "profiles": self.requestDialog.emit("profiles", self.settingsData())
        elif action == "updates": self.check_updates()
        elif action == "quit":
            self.requestQuit()

    def _remove(self): self.document.remove_selected(); self.refresh()

    IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
    VIDEO_TYPES = (".mp4", ".webm", ".avi", ".mov", ".mkv")

    @Slot('QVariantList', float, float)
    def dropFiles(self, urls, x, y):
        """Files dropped on the canvas: images/GIFs become elements at the drop point, a video the background."""
        point = None
        if self.canvas and self.canvas.scale > 0:
            from PySide6.QtCore import QPointF
            point = self.canvas.widget_to_canvas_pos(QPointF(x, y)) / self.canvas.scale
        for url in urls:
            path = str(Path(QUrl(url).toLocalFile()))  # native separators in saved themes
            suffix = Path(path).suffix.lower()
            try:
                if suffix == ".gif":
                    self._add_media("gif", path, point)
                elif suffix in self.IMAGE_TYPES:
                    self._add_media("image", path, point)
                elif suffix in self.VIDEO_TYPES:
                    self.fileChosen("video", QUrl.fromLocalFile(path))
                else:
                    self.notify(f"{Path(path).name}: drop an image, GIF or video")
            except Exception as exc:
                self.error(f"{Path(path).name}: {exc}")

    def _add_media(self, kind, path, point):
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.size
        doc = self.document
        fit = min(1.0, 0.6 * doc.width / width, 0.6 * doc.height / height)  # at most 60% of the display
        props = copy.deepcopy((get_custom_element(kind) or {}).get("defaults", {}))
        props.update(page=doc.current_page, name=f"{Path(path).stem} {len(doc.elements) + 1}",
                     width=max(1, round(width * fit)), height=max(1, round(height * fit)))
        props["gif_path" if kind == "gif" else "image_path"] = path
        if kind == "image":
            props["aspect_ratio"] = width / height
        element = ThemeElement(kind, **props)
        errors = validate_element_schema(element.to_dict(), 0)
        if errors:
            raise ValueError("\n".join(errors))
        if point is None:
            self._place_at_view_center(element)
        else:
            element.x, element.y = round(point.x() - element.width / 2), round(point.y() - element.height / 2)
        doc.begin()
        doc.elements.insert(0, element)
        doc.selection = [0]
        doc.commit()
        self.refresh()

    STARTER_PRESETS = ("Default", "System Monitor", "Minimal")

    def _starter_preset(self):
        """First-run theme: a bundled one made for this display's resolution, so nothing is shrunk."""
        size = (self.document.width, self.document.height)
        fitting = [name for name, info in sorted(self.repository.presets.items())
                   if info["builtin"] and (info["data"].get("display_width"), info["data"].get("display_height")) == size]
        preferred = [name for name in self.STARTER_PRESETS if name in fitting]
        return (preferred or fitting or ["Default"])[0]

    def _view_center(self):
        """Display coordinates at the middle of the visible canvas (the display center without a canvas)."""
        doc = self.document
        cx, cy = doc.width / 2, doc.height / 2
        if self.canvas and self.canvas.scale > 0:
            from PySide6.QtCore import QPointF
            point = self.canvas.widget_to_canvas_pos(QPointF(self.canvas.width() / 2, self.canvas.height() / 2)) / self.canvas.scale
            cx, cy = point.x(), point.y()
        return min(max(cx, 0), doc.width), min(max(cy, 0), doc.height)

    def _place_at_view_center(self, element):
        cx, cy = self._view_center()
        if element.type in ("circle_gauge", "analog_clock"):  # positioned by their center
            element.x, element.y = round(cx), round(cy)
        else:
            element.x, element.y = round(cx - element.width / 2), round(cy - element.height / 2)

    def _load_preset(self, name, manual=True):
        if name not in self.repository.presets: return
        if not manual and (self.document.theme_name == name or self.dirty): return  # Never replace unsaved edits
        self.document.load(copy.deepcopy(self.repository.presets[name]["data"]))
        settings.set_setting("last_preset", name)
        self._restore_video()
        if manual and self._profile_manager: self._profile_manager.suppress_auto_switch()
        self.refresh(mark_dirty=False)
        self.dirty = False

    def _group(self, name):
        self.document.begin()
        for e in self.document.selected(editable=True): e.group = name
        self.document.commit(); self.refresh()

    def _align(self, mode):
        chosen = self.document.selected(editable=True)
        if len(chosen) < 2: return
        from src.ui.canvas_behavior import CanvasBehavior
        boxes = [CanvasBehavior._display_extent(e, e.x, e.y) for e in chosen]
        left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
        self.document.begin()
        for e, box in zip(chosen, boxes):
            dx = {"left": left - box[0], "right": right - box[2], "center": (left + right - box[0] - box[2]) / 2}.get(mode, 0)
            dy = {"top": top - box[1], "bottom": bottom - box[3], "middle": (top + bottom - box[1] - box[3]) / 2}.get(mode, 0)
            e.x += round(dx); e.y += round(dy)
        if mode in ("horizontal", "vertical") and len(chosen) > 2:
            axis = 0 if mode == "horizontal" else 1
            ordered = sorted(zip(chosen, boxes), key=lambda p: p[1][axis])
            first, last = ordered[0][1][axis], ordered[-1][1][axis]
            for i, (e, box) in enumerate(ordered):
                delta = round(first + (last - first) * i / (len(chosen) - 1) - box[axis])
                if axis == 0: e.x += delta
                else: e.y += delta
        self.document.commit(); self.refresh()

    def _delete_page(self, page):
        self.document.begin()
        self.document.elements = [e for e in self.elements if e.page != page]
        self.document.pages.remove(page)
        if self.current_page == page: self.document.current_page = self.document.pages[0]
        self.document.selection = []
        self.document.commit(); self.refresh()

    def _new(self):
        self.document.begin()
        self.document.elements = []
        self.document.pages = [1]
        self.document.current_page = 1
        self.document.selection = []
        self.document.theme_name = "Untitled Theme"
        self.document.video = {}
        video_background.clear_video()
        self.theme_path = None
        self.document.commit(); self.refresh()

    def confirm(self, title, message, callback):
        token = uuid.uuid4().hex
        self._pending[token] = callback
        self.requestDialog.emit("confirm", {"title": title, "message": message, "token": token})

    def guard_changes(self, callback):
        if not self.dirty:
            callback()
            return
        if self._unsaved_token in self._pending:
            return
        self._unsaved_token = uuid.uuid4().hex
        def resolve(choice):
            if choice == "save":
                self._after_save = callback
                self.save()
            elif choice == "discard":
                callback()
        self._pending[self._unsaved_token] = resolve
        self.requestDialog.emit("unsaved", {"token": self._unsaved_token, "name": self.document.theme_name})

    @Slot()
    def requestQuit(self):
        if self.window:
            self.guard_changes(self.window.force_quit)

    def prompt(self, title, label, initial, callback):
        token = uuid.uuid4().hex
        self._pending[token] = callback
        self.requestDialog.emit("prompt", {"title": title, "label": label, "initial": initial, "token": token})

    @Slot(str, bool, str)
    def answer(self, token, accepted, value=""):
        callback = self._pending.pop(token, None)
        if token == self._unsaved_token:
            self._unsaved_token = None
        if not accepted:
            self._after_save = None
        if accepted and callback:
            try:
                if value: callback(value)
                else: callback()
            except Exception as exc: self.error(str(exc))

    def error(self, message):
        self._after_save = None
        self.notify(message)
        self.requestDialog.emit("error", {"title": "Action could not be completed", "message": str(message)})

    def reload_presets(self):
        self.repository.load()
        for name, info in self.repository.presets.items():
            try:
                data = info["data"]
                size = (data.get("display_width", 1280), data.get("display_height", 480))
                background = preview_background(data, size)
                saved = QImage(info["thumbnail"])
                if not saved.isNull() and (not data.get("video_background", {}).get("enabled") or background is None):
                    self.thumbnails["preset/" + name] = saved
                    continue
                frame = self.renderer.render({"background_color": data.get("background_color", "#0f0f19"), "sensor_data": {},
                                              "elements": [(f"preset/{name}/{i}", e) for i, e in enumerate(data.get("elements", [])) if e.get("page", 1) == 1]},
                                             size, background)
                frame.thumbnail((240, 150))
                self.thumbnails["preset/" + name] = pil_image(frame)
            except Exception: logger.warning("Could not render preset thumbnail %s", name)
        self.presets_model.replace([{"id": name, "name": name, "builtin": info["builtin"],
                                    "width": info["data"].get("display_width", 1280), "height": info["data"].get("display_height", 480)}
                                   for name, info in sorted(self.repository.presets.items(), key=lambda p: (p[0] != "Default", p[0].lower()))])
        self._filter_presets()

    def update_thumbnails(self, pages=None):
        for page in self.document.pages if pages is None else pages:
            frame = self.render_theme_image(self._editor_snapshot(page))
            frame.thumbnail((160, 90))
            self.thumbnails[f"page/{page}"] = pil_image(frame)

    def save(self, force=False):
        name = self.document.theme_name
        if self._needs_new_name(name):
            initial = "My theme" if name == "Untitled Theme" else f"{name} copy"
            self.prompt("Save theme", "Theme name", initial, self._save_named)
            return
        if name in self.repository.presets and not force:
            self.confirm("Overwrite preset", f"Replace {name} with this theme?", lambda: self.save(force=True))
            return
        self.repository.save(name, self.document.export(), self.render_theme_image())
        settings.set_setting("default_preset", name)
        self.reload_presets()
        self.dirty = False
        self.notify("Saved " + name)
        callback, self._after_save = self._after_save, None
        if callback:
            callback()

    def _needs_new_name(self, name):
        return name == "Untitled Theme" or self.repository.is_read_only(name)

    def _save_named(self, name):
        if not name.strip(): raise ValueError("Enter a theme name")
        self.document.theme_name = name.strip()[:100]
        self.save()

    def _autosave(self):
        try:
            self.repository.save(self.document.theme_name, self.document.export(), self.render_theme_image())
            self.dirty = False
            self.notify("Autosaved " + self.document.theme_name)
        except Exception as exc: self.notify("Autosave failed: " + str(exc))

    def _delete_preset(self, name):
        self.repository.delete(name); self.reload_presets(); self.changed.emit()

    @Slot(str, QUrl)
    def fileChosen(self, action, url, guarded=False):
        path = url.toLocalFile()
        if not path: return
        if action in ("open", "importPackage") and not guarded:
            self.guard_changes(lambda: self.fileChosen(action, url, True))
            return
        try:
            if action == "open":
                data = resolve_assets(json.loads(Path(path).read_text(encoding="utf-8")), Path(path).parent)
                self.document.load(data)
                self.theme_path = path
                self._restore_video(); self.refresh()
            elif action == "saveAs":
                write_json_atomic(path, self.document.export()); self.theme_path = path; self.dirty = False
                self.notify("Theme saved")
            elif action == "exportImage": self.render_theme_image().save(path)
            elif action == "exportPackage":
                from src.utils.theme_package import export_theme
                success, result = export_theme(self.document.export(), self.render_theme_image(), path)
                if not success: raise ValueError(result)
                self.notify("Theme package exported")
            elif action == "importPackage":
                from src.utils.theme_package import import_theme
                success, error, data = import_theme(path)
                if not success: raise ValueError(error)
                self.document.load(data); self._restore_video(); self.refresh()
            elif action in ("image", "gif"):
                self.edit(action + "_path", path)
                if action == "image":
                    from PIL import Image
                    with Image.open(path) as image: self.edit("aspect_ratio", image.width / image.height)
            elif action == "video":
                if not HAS_CV2: raise ValueError("Video support requires OpenCV")
                self._owns_video = True
                self.document.begin()
                self.notify("Loading video…")
                if not video_background.load_video(path, callback=lambda progress, done, error: self.videoResult.emit(not bool(error), error or "") if done else None):
                    raise ValueError("Could not start video loading")
        except Exception as exc: self.error(str(exc))

    def _video_result(self, success, error):
        self.document.video = video_background.to_dict()
        self.document.commit()
        self.refresh()
        if error: self.error(error)
        else: self.notify("Video loaded")

    def _restore_video(self):
        # Called whenever the document is replaced (load, open, import, undo/redo)
        self.renderer.clear_cache()
        for key in [k for k in self.thumbnails if k.startswith("page/")]:
            del self.thumbnails[key]
        self._video_generation += 1
        generation = self._video_generation
        self._owns_video = True
        if self.document.video:
            video_background.from_dict(self.document.video, callback=lambda progress, done, error: self.videoRestored.emit(generation, error or "") if done else None)
        else: video_background.clear_video()

    @Slot(int, str)
    def _video_restored(self, generation, error):
        if self._closed or generation != self._video_generation: return
        self.refresh(mark_dirty=False)
        if error: self.notify("Background media unavailable: " + error)

    def get_sensor_data(self): return sensors.get_cached_sensors()

    def refresh_sensors(self):
        constants.register_hardware_sources(sensors.get_hardware_sensor_catalog())
        values = self.get_sensor_data()
        groups = {source[0]: category for category, sources in constants.DATA_SOURCES_CATEGORIZED.items() for source in sources}
        rows = []
        for key, info in constants.SOURCE_UNITS.items():
            if key == "static": continue
            scope = "Hardware" if key.startswith("hardware_") else "External" if key.startswith("network_") else "Summary"
            category = groups.get(key, "Other")
            name = info["name"]
            if scope == "Hardware":
                identifier = name.rsplit(" [", 1)[-1].lower()
                name = name.split(" [", 1)[0]
                category = "CPU" if "cpu/" in identifier else "GPU" if "gpu/" in identifier else "Storage" if any(word in identifier for word in ("storage/", "hdd/", "ssd/", "nvme/")) else "Memory" if "memory/" in identifier else "Cooling & motherboard"
            rows.append({"id": key, "name": name, "scope": scope, "category": category,
                         "value": constants.get_value_with_unit(values.get(key), key), "available": key in values and values[key] is not None})
        self.sensors_model.replace(sorted(rows, key=lambda r: (r["scope"], r["category"], r["name"])))
        self._filter_sensors()
        self.changed.emit()
        if self._hardware_check_ready:
            self.checkHardwareAccess()

    def _preview_tick(self):
        if self.canvas and self.window and self.window.isVisible():
            # While streaming, show the frame the device worker just rendered instead of rendering twice
            device_frame = self._last_device_frame if self.live_preview_timer and self.preview_fraction is None else None
            self._preview_frame = device_frame or self.render_theme_image()
            self.canvas.update()

    @Slot()
    def record_frame_time(self):
        now = time.perf_counter()
        if self.last_frame_time:
            self.frame_times.append(now - self.last_frame_time)
            self.frame_times = self.frame_times[-60:]
        self.last_frame_time = now

    def _rotate(self):
        pages = self.document.pages
        self._command("page", pages[(pages.index(self.current_page) + 1) % len(pages)])

    @Slot()
    def openDevices(self):
        self._device_defs = enumerate_available_devices()
        self.devices_model.replace([{"index": i, "name": device.name, "experimental": device.experimental,
                                     "width": device.width, "height": device.height} for i, device in enumerate(self._device_defs)])
        self.requestDialog.emit("devices", {})

    @Slot(int)
    def connectDevice(self, index):
        if not 0 <= index < len(getattr(self, "_device_defs", [])): return
        device = copy.copy(self._device_defs[index])
        device.extra_params = dict(device.extra_params)
        self.selected_device_def = device
        if device.experimental:
            self.confirm("Experimental display", "This device's protocol is experimental. Continue connecting?", self.connect_display)
        else: self.connect_display()

    def connect_display(self, silent=False):
        if not self.selected_device_def: return False
        self.disconnect_display()
        device = self.selected_device_def
        override = get_device_size_override(settings.get_setting("display_size_overrides", {}), device)
        if override:
            device.width, device.height = override
            device.extra_params["manual_size_override"] = True
        backend = create_backend(device)
        try:
            if not backend or not backend.connect(): raise RuntimeError("Device unavailable or in use by another application")
            self.backend = self.device = backend
            self.document.resize(device.width, device.height)
            self.refresh(mark_dirty=False)
            self.start_continuous_send()
            self._reconnect_timer.stop()
            self._reconnect_attempts = 0
            self.notify("Connected to " + device.name)
            return True
        except Exception as exc:
            if backend:
                try: backend.disconnect()
                except Exception: pass
            self.backend = self.device = None
            if silent: self.notify(str(exc))
            else: self.error(str(exc))
            return False

    def disconnect_display(self):
        self.stop_continuous_send()
        if self.backend:
            try: self.backend.disconnect()
            except Exception: logger.warning("Device disconnect failed")
        self.backend = self.device = None
        self.frame_times = []
        self._last_frame_request_time = 0
        self.changed.emit()

    def _start_reconnect_timer(self):
        self._reconnect_timer.start(min(30000, 1000 * 2 ** min(self._reconnect_attempts, 5)))

    def _attempt_reconnect(self):
        if self._closed: return
        self._reconnect_attempts += 1
        if not self.connect_display(silent=True): self._start_reconnect_timer()

    def sleep(self):
        self._was_connected_before_sleep = self.device is not None
        self._reconnect_timer.stop()
        self.disconnect_display()

    def wake(self):
        video_background.reset_timing()
        from elements.gif import reset_all_playback
        reset_all_playback()
        sensors.invalidate_sensor_cache()
        if self._was_connected_before_sleep: self._start_reconnect_timer()

    @Property('QVariantMap', notify=changed)
    def hardwareStatus(self):
        status = sensors.get_sensor_status()
        windows = sys.platform == "win32"
        elevated = windows and settings._is_windows_elevated()
        available = status.get("cpu_thermal_available", False)
        needs_admin = windows and not elevated and not available
        reason = status.get("cpu_thermal_reason") or status.get("reason")
        if available:
            message = "CPU temperature monitoring is working."
        elif needs_admin:
            message = "CPU temperature is unavailable. Some CPU sensors need administrator access. Restart as Administrator to retry; Windows will ask for permission."
        elif reason == "pawnio_missing":
            message = "CPU temperature is unavailable. Install the optional PawnIO driver, then restart Thermal Engine and refresh sensors."
        else:
            message = "CPU temperature is unavailable. Check the hardware driver and diagnostics; unsupported hardware may expose no temperature."
        if needs_admin and reason == "pawnio_missing":
            message += " The PawnIO driver also appears to be missing."
        return {"isWindows": windows, "isAdmin": elevated, "needsAdmin": needs_admin,
                "cpuAvailable": available, "reason": reason, "message": message}

    @Slot()
    def checkHardwareAccess(self):
        if self._closed or not self._start_services:
            return
        self._hardware_check_ready = True
        if not self._hardware_prompted and self.hardwareStatus["needsAdmin"]:
            self._hardware_prompted = True
            self.requestDialog.emit("hardware", {})

    @Property('QVariantList', notify=changed)
    def networkHealth(self):
        return sensors.get_network_sensor_details()

    @Property('QVariantList', notify=changed)
    def healthChecks(self):
        hardware = self.hardwareStatus
        network = self.networkHealth
        online = sum(source["status"] == "Receiving" for source in network)
        ages = [source["age"] for source in network if source["age"] is not None]
        network_detail = f"{online} of {len(network)} connections receiving data." if network else "No external sensors configured."
        if ages:
            network_detail += f" Last reading {min(ages):g} seconds ago."
        return [{"id": "display", "name": "Display", "status": "Connected" if self.device else "Offline",
                 "severity": "success" if self.device else "muted", "detail": self.state["device"] + f" · {self.document.width} × {self.document.height}",
                 "action": "connect", "actionLabel": "Disconnect display" if self.device else "Choose a display"},
                {"id": "hardware", "name": "Hardware", "status": "Ready" if hardware["cpuAvailable"] else "Needs attention",
                 "severity": "success" if hardware["cpuAvailable"] else "warning", "detail": hardware["message"],
                 "action": "hardwareSetup", "actionLabel": "Open hardware setup"},
                {"id": "network", "name": "Network", "status": f"{online}/{len(network)} receiving" if network else "Not configured",
                 "severity": "success" if network and online == len(network) else "warning" if network else "muted",
                 "detail": network_detail, "action": "network", "actionLabel": "Manage network sensors"}]

    def diagnostics(self):
        return json.dumps({"version": get_version(), "sensors": sensors.get_sensor_status(),
                           "hardwareAccess": self.hardwareStatus,
                           "checks": self.healthChecks, "networkDetails": self.networkHealth,
                           "network": sensors.get_network_sensor_statuses(), "display": self.state["device"],
                           "resolution": [self.document.width, self.document.height],
                           "fps": self.state["actualFps"]}, indent=2, default=str)

    @Slot(result='QVariantMap')
    def settingsData(self):
        defaults = {**settings.DEFAULT_SETTINGS, **PROFILE_SETTINGS}
        return {key: settings.get_setting(key, default, resolve_secrets=False) for key, default in defaults.items() if key != "network_sensors"}

    @Slot(result='QVariantMap')
    def foregroundApp(self):
        from src.utils.profiles import _get_foreground_app
        process, title = _get_foreground_app()
        return {"process": process, "title": title}

    @Slot('QVariantMap', result=bool)
    def saveSettings(self, data):
        try:
            if "target_fps" in data and int(data["target_fps"]) not in (10, 20, 30, 60): raise ValueError("Choose 10, 20, 30 or 60 FPS")
            if "display_brightness" in data and not 0 <= int(data["display_brightness"]) <= 100: raise ValueError("Brightness must be between 0 and 100")
            if "display_orientation" in data and data["display_orientation"] not in ("normal", "flip_v", "flip_h", "rotate_180", "rotate_90_cw", "rotate_90_ccw"): raise ValueError("Invalid orientation")
            for key, lower, upper in (("layers_panel_width", 220, 440), ("inspector_panel_width", 280, 520)):
                if key in data and (type(data[key]) not in (int, float) or not lower <= data[key] <= upper):
                    raise ValueError("Invalid workspace panel width")
            if "profiles" in data:
                if not isinstance(data["profiles"], list): raise ValueError("Profiles must be a list")
                for rule in data["profiles"]:
                    if not isinstance(rule, dict) or not str(rule.get("app_name", "")).strip() or rule.get("match_mode") not in ("process", "title") or rule.get("preset_name") not in self.repository.presets:
                        raise ValueError("Each profile needs an application, a match mode and an existing preset")
            for key, lower, upper in (("system_idle_threshold", 1, 99), ("system_gaming_threshold", 1, 99), ("system_idle_seconds", 5, 3600), ("system_gaming_seconds", 1, 300)):
                if key in data and not lower <= int(data[key]) <= upper: raise ValueError(f"Invalid {key.replace('_', ' ')}")
            allowed = set(settings.DEFAULT_SETTINGS) | set(PROFILE_SETTINGS)
            changes = {key: value for key, value in data.items() if key in allowed and key != "network_sensors"}
            if settings._settings is None: settings.load_settings()
            previous = settings._settings.copy()
            updated = {**previous, **changes}
            startup_changed = bool(updated.get("launch_at_login")) != bool(previous.get("launch_at_login"))
            if startup_changed and not settings.set_autostart(bool(updated["launch_at_login"])):
                raise RuntimeError("Windows startup was not changed. The permission request was cancelled or configuration failed; previous settings are preserved.")
            try:
                write_json_atomic(settings.SETTINGS_FILE, updated)
            except Exception:
                if startup_changed and not settings.set_autostart(bool(previous.get("launch_at_login"))):
                    raise RuntimeError("Settings could not be saved and startup could not be restored. Check Launch at login before trying again.") from None
                raise
            settings._settings = updated
            self.target_fps = settings.get_setting("target_fps", 30)
            self.display_brightness = max(0, min(100, settings.get_setting("display_brightness", 100)))
            self.display_orientation = settings.get_setting("display_orientation", "normal")
            if self.live_preview_timer: self.live_preview_timer.setInterval(round(1000 / self.target_fps))
            self._start_profiles()
            self.changed.emit()
            return True
        except Exception as exc:
            self.error(str(exc)); return False

    @Slot(int, int, bool)
    def resizeDisplay(self, width, height, stretch):
        try:
            self.document.resize(width, height, stretch)
            settings.set_setting("last_display_width", width); settings.set_setting("last_display_height", height)
            if self.selected_device_def:
                overrides = dict(settings.get_setting("display_size_overrides", {}))
                overrides[device_size_key(self.selected_device_def)] = [width, height]
                settings.set_setting("display_size_overrides", overrides)
                self.selected_device_def.width, self.selected_device_def.height = width, height
                self.selected_device_def.extra_params["manual_size_override"] = True
            self.refresh()
        except ValueError as exc: self.error(str(exc))

    def _start_profiles(self):
        if not self._start_services: return
        from src.utils.profiles import ProfileManager, ForegroundAppMonitor, SystemStateMonitor
        if self._profile_manager is None: self._profile_manager = ProfileManager()
        self._profile_manager.load_profiles()
        if self._foreground_monitor is None:
            self._foreground_monitor = ForegroundAppMonitor()
            self._foreground_monitor.app_changed.connect(self._profile_app)
        if self._system_state_monitor is None:
            self._system_state_monitor = SystemStateMonitor()
            self._system_state_monitor.state_changed.connect(self._profile_system)
        for monitor, enabled in ((self._foreground_monitor, self._profile_manager.enabled), (self._system_state_monitor, self._profile_manager.system_profile_enabled)):
            if enabled and not monitor.isRunning(): monitor._running = True; monitor.start()
            elif not enabled and monitor.isRunning(): monitor.stop()

    def _profile_app(self, process, title):
        name = self._profile_manager.match_app(process, title)
        if name: self._load_preset(name, manual=False)

    def _profile_system(self, state):
        if not self._profile_manager.system_profile_enabled: return
        name = self._profile_manager.system_idle_preset if state == "idle" else self._profile_manager.system_gaming_preset if state == "gaming" else None
        if name: self._load_preset(name, manual=False)

    @Slot()
    def openNetwork(self):
        self.stopProbe()
        self._network_error = ""
        try: self._network_draft = validate_sources(settings.get_setting("network_sensors", []))
        except (ValueError, RuntimeError) as exc:
            self._network_error = str(exc)
            self._network_draft = validate_sources(settings.get_setting("network_sensors", [], resolve_secrets=False))
        self.changed.emit()
        self.requestDialog.emit("network", {})

    @Slot('QVariantList', result=bool)
    def saveNetwork(self, sources):
        try:
            sources = validate_sources(sources)
            if self._network_error and any(s.get(key + "_ref") and not s.get(key) for s in sources for key in ("password", "token")):
                raise RuntimeError("Re-enter missing saved credentials before saving. Existing settings are preserved.")
            settings.set_setting("network_sensors", sources)
            sensors.configure_network_sensors(sources)
            self._network_draft = sources
            self.stopProbe(); self.refresh_sensors(); self.notify("Network sensors saved")
            return True
        except (ValueError, RuntimeError) as exc: self.error(str(exc)); return False

    @Slot('QVariantList', result='QVariantMap')
    def validateNetworkDraft(self, sources):
        try:
            validate_sources(sources)
            return {}
        except ValueError as exc:
            message, index = str(exc), 0
            seen = set()
            for index, source in enumerate(sources):
                try:
                    validate_sources([source])
                except ValueError:
                    break
                if source["id"] in seen:
                    break
                seen.add(source["id"])
            markers = {"Sensor ID": "id", "HTTP URL": "url", "Port": "port", "Host": "host", "MQTT topic": "topic",
                       "scale": "scale", "offset": "offset", "interval": "interval", "stale_after": "stale_after",
                       "Decimals": "decimals", "Invalid token": "token", "Invalid password": "password", "Invalid username": "username"}
            field = next((key for marker, key in markers.items() if marker.lower() in message.lower()), "form")
            return {"index": index, "field": field, "message": message}

    @Slot('QVariantMap')
    def testNetwork(self, source):
        self.stopProbe()
        try:
            self._probe = NetworkSensorManager([source])
            self._probe_deadline = time.monotonic() + 5
            self._probe_result = "Testing unsaved connection…"
            self._probe.start(); self.probe_timer.start(250); self.changed.emit()
        except ValueError as exc: self.error(str(exc))

    def _probe_tick(self):
        if not self._probe: return
        source = self._probe.sources[0]
        value = self._probe.snapshot().get("network_" + source["id"])
        if value is not None or time.monotonic() >= self._probe_deadline:
            self._probe_result = "Test successful: " + str(value) if value is not None else "No valid reading: " + self._probe.statuses()[source["id"]]
            self.stopProbe(); self.changed.emit()

    @Slot()
    def stopProbe(self):
        self.probe_timer.stop()
        if self._probe: self._probe.stop(wait=False); self._probe = None

    def check_updates(self, silent=False):
        if self._closed or (getattr(self, "_update_checker", None) and self._update_checker.isRunning()): return
        from src.utils.updater import UpdateChecker
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._update_available)
        self._update_checker.no_update.connect(lambda: self.notify("You are up to date") if not silent else None)
        self._update_checker.error.connect(lambda error: self.notify("Update check failed") if silent else self.error(error))
        self._update_checker.start()

    def _update_available(self, version, url, notes, checksum, asset):
        self.requestDialog.emit("update", {"version": version, "url": url, "notes": notes, "checksum": checksum, "asset": asset})

    @Slot('QVariantMap')
    def downloadUpdate(self, info):
        if getattr(self, "_update_downloader", None) and self._update_downloader.isRunning(): return
        from src.utils.updater import UpdateDownloader, can_auto_install_asset
        if not can_auto_install_asset(info["asset"], expected_hash=info["checksum"]):
            from PySide6.QtGui import QDesktopServices
            from src.utils.updater import GITHUB_RELEASES_URL
            QDesktopServices.openUrl(QUrl(GITHUB_RELEASES_URL))
            return
        self._update_info = info
        self._update_downloader = UpdateDownloader(info["url"], info["version"], info["checksum"], info["asset"])
        self._update_downloader.progress.connect(lambda done, total: self.notify(f"Downloading update: {round(done / total * 100) if total else 0}%"))
        self._update_downloader.error.connect(self.error)
        self._update_downloader.finished.connect(self._update_downloaded)
        self._update_downloader.start()

    def _update_downloaded(self, path):
        from src.utils.updater import install_downloaded_update
        self.confirm("Install update", "Close Thermal Engine and start the downloaded installer?",
                     lambda: self.guard_changes(lambda: self._install_update(path, install_downloaded_update)))

    def _install_update(self, path, install):
        if install(path, self._update_info["asset"]):
            if self.window: self.window.force_quit()

    @Slot()
    def startup(self):
        if not self._start_services: return
        self._restore_video()
        if not sensors.get_sensor_status()["cpu_thermal_available"]:
            self.notify("CPU temperature unavailable. Open Hardware setup from the project menu for diagnostics and remedies.", sticky=True)
        if not settings.get_setting("onboarding_completed", False) and not settings.get_setting("last_preset") and not settings.get_setting("default_preset"):
            self.openDevices()
            self.requestDialog.emit("onboarding", {})
        else:
            devices = enumerate_available_devices()
            if len(devices) == 1 and not devices[0].experimental:
                self.selected_device_def = copy.copy(devices[0]); self.selected_device_def.extra_params = dict(devices[0].extra_params)
                self.connect_display(silent=True)
            self.checkHardwareAccess()
        if settings.get_setting("check_for_updates", True): QTimer.singleShot(2000, lambda: self.check_updates(silent=True))

    @Slot(int, int, int, str)
    def finishOnboarding(self, device, width, height, preset):
        if 0 <= device < len(getattr(self, "_device_defs", [])):
            overrides = dict(settings.get_setting("display_size_overrides", {}))
            overrides[device_size_key(self._device_defs[device])] = [width, height]
            settings.set_setting("display_size_overrides", overrides)
        self.resizeDisplay(width, height, False)
        if preset: self._load_preset(preset)  # The wizard chose it: no "discard changes?" prompt
        else: self._new()
        settings.set_setting("default_preset", preset or None)
        settings.set_setting("onboarding_completed", True)
        if device >= 0: self.connectDevice(device)

    def cleanup(self):
        if self._closed: return
        self._closed = True
        logging.getLogger().removeHandler(self._console_handler)
        for timer in (self.preview_timer, self.sensors_timer, self.autosave, self.rotation, self._reconnect_timer): timer.stop()
        self.stopProbe()
        self.disconnect_display()
        for monitor in (self._foreground_monitor, self._system_state_monitor):
            if monitor: monitor.stop()
        for worker in (getattr(self, "_update_checker", None), getattr(self, "_update_downloader", None)):
            if worker and worker.isRunning():
                if hasattr(worker, "cancel"): worker.cancel()
                worker.wait()
        if self._start_services: sensors.stop_sensors()
        if self._start_services or self._owns_video: video_background.close()
