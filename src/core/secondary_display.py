"""Extra displays: each one shows a saved preset on its own thread (experimental).

The device is found again by its physical identity on every (re)connect, so a replug or a changed
USB address never sends the theme to a different display.
"""
import copy
import logging
import threading
import time

from src.core import sensors
from src.core.device_backends import DeviceIOError, create_backend, enumerate_available_devices, resolve_device
from src.core.display_size import get_device_size_override
from src.core.document import EditorDocument
from src.core.frame_pipeline import FramePipeline
from src.core.renderer import ThemeRenderer

logger = logging.getLogger(__name__)
RETRY_SECONDS = 5


def uses_game_sources(elements):
    """elements: dicts or ThemeElements. True when any reads a game_* sensor (source, rule or template)."""
    for element in elements:
        get = element.get if isinstance(element, dict) else lambda key, default=None: getattr(element, key, default)
        condition = get("condition") or {}
        if str(get("source") or "").startswith("game_") or str(condition.get("source") or "").startswith("game_") \
                or "{game_" in str(get("text") or ""):
            return True
    return False


class SecondaryDisplay:
    display_orientation = "normal"  # per-output orientation is a non-goal

    def __init__(self, identity, name, preset, data, target_fps=30, size_overrides=None):
        self.identity, self.name = identity, name
        self.target_fps = target_fps
        self.display_brightness = self.output_brightness = 100
        self.size_overrides = size_overrides or {}
        self.backend = self.selected_device_def = None
        self.status = "Starting"
        self.renderer = ThemeRenderer()
        self._lock = threading.Lock()
        self._backend_lock = threading.Lock()
        self._stop = threading.Event()
        self._document = None
        self._logged = False
        self.set_preset(preset, data)
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"display-{name}")

    @property
    def state_prefix(self):
        """Element names are prefixed on this output: chart history and GIF playback (keyed by name) stay its own."""
        return f"secondary/{self.identity}/"

    def _forget_state(self):
        # The registry's module instances are the ones that render (loaded from file, not `import elements.x`)
        from elements import get_custom_element
        for kind, function in (("line_chart", "forget_history"), ("gif", "forget_playback")):
            module = (get_custom_element(kind) or {}).get("module")
            if module and hasattr(module, function):
                getattr(module, function)(self.state_prefix)

    @property
    def running(self):
        return self._thread.is_alive()

    def set_preset(self, preset, data):
        with self._lock:
            self.preset, self.data, self._document = preset, copy.deepcopy(data), None
        self.renderer.clear_cache()
        self._forget_state()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3)  # a worker still inside connect() disconnects itself when it returns
        if not self._thread.is_alive():
            self._disconnect()
        self._forget_state()
        self.status = "Stopped"

    def _disconnect(self):
        with self._backend_lock:
            backend, self.backend = self.backend, None
        if backend:
            try:
                backend.disconnect()
            except Exception:
                logger.warning("Secondary display disconnect failed")

    def _connect(self):
        device = resolve_device(self.identity, enumerate_available_devices())
        if device is None:
            self.status = "Not connected"
            return False
        device = copy.copy(device)
        device.extra_params = dict(device.extra_params)
        override = get_device_size_override(self.size_overrides, device)
        if override:
            device.width, device.height = override
        backend = create_backend(device)
        if not backend or not backend.connect():
            self.status = "Unavailable or in use"
            return False
        with self._backend_lock:
            self.backend, self.selected_device_def = backend, device
        with self._lock:
            self._document = None  # rebuilt at this device's size
        self.status = "Showing " + self.preset
        return True

    def _snapshot(self):
        device = self.selected_device_def
        with self._lock:
            if self._document is None:
                document = EditorDocument()
                document.width, document.height = device.width, device.height
                document.load(copy.deepcopy(self.data))  # fitted to this display, like a preset load
                self._document = document
            document = self._document
        sensor_data = sensors.get_cached_sensors()
        elements = []
        for index, element in enumerate(e for e in document.elements if e.page == document.current_page):
            data = element.to_dict()
            data["name"] = self.state_prefix + data["name"]
            if element.source != "static" and element.source in sensor_data:
                value = sensor_data[element.source]
                data["value"] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
            elif element.source.startswith(("network_", "hardware_", "game_")):
                data["value"] = 0
            elements.append((f"secondary/{self.identity}/{index}", data))
        return {"background_color": document.background_color, "elements": elements, "sensor_data": sensor_data}

    def render_frame(self):
        device = self.selected_device_def
        return self.renderer.render(self._snapshot(), (device.width, device.height))

    def _run(self):
        try:
            self._loop()
        finally:
            self._disconnect()  # whatever happened, the device is released when the worker ends

    def _loop(self):
        while not self._stop.is_set():
            if self.backend is None:
                try:
                    connected = self._connect()
                except Exception:  # enumeration/USB errors: retry, never end the worker
                    logger.warning("Secondary display %s: connect failed", self.name)
                    self.status, connected = "Not connected", False
                if self._stop.is_set():
                    return  # removed while connecting: send nothing
                if not connected:
                    self._stop.wait(RETRY_SECONDS)
                    continue
            started = time.monotonic()
            try:
                jpeg = FramePipeline.image_to_jpeg(self, self.render_frame())
                FramePipeline.send_jpeg_frame(self, jpeg)
                self.status = "Showing " + self.preset
            except DeviceIOError:
                self.status = "Reconnecting"
                self._disconnect()
                self._stop.wait(RETRY_SECONDS)
                continue
            except Exception:
                if not self._logged:  # once, not 30 times a second
                    self._logged = True
                    logger.exception("Secondary display %s: frame failed", self.name)
                self.status = "Frame failed; see diagnostics"
            self._stop.wait(max(0.0, 1 / max(1, self.target_fps) - (time.monotonic() - started)))
