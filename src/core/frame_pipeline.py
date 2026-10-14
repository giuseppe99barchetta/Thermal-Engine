"""Shared latest-frame rendering and device delivery pipeline."""
import io
import logging
import threading
import time
from PIL import Image, ImageEnhance
from PySide6.QtCore import Qt, QTimer
from src.core import constants
from src.core.device_backends import DeviceIOError
from src.ui.video_background import video_background
logger = logging.getLogger(__name__)


def simulate_snapshot(snapshot, fraction):
    """Editor-only stand-in readings: every sensor-driven element shows `fraction` of its scale.

    Lets themes be designed without live sensors (gauges at 0%, conditions never firing).
    """
    sensor_data = {key: fraction * 100 if isinstance(value, (int, float)) and not isinstance(value, bool) else value
                   for key, value in snapshot.get("sensor_data", {}).items()}
    elements = []
    for cache_key, data in snapshot["elements"]:
        if data.get("source", "static") != "static":
            data = {**data, "value": fraction * data.get("max_value", 100)}
            sensor_data[data["source"]] = data["value"]  # templates and conditional rules read sensor_data
        elements.append((cache_key, data))
    return {**snapshot, "sensor_data": sensor_data, "elements": elements}


class FramePipeline:
    preview_fraction = None  # Simulated reading for the editor preview (None = live data)

    def _editor_snapshot(self, page=None):
        """Snapshot for editor views; the device path uses _capture_render_snapshot directly."""
        snapshot = self._capture_render_snapshot(page)
        if self.preview_fraction is not None:
            snapshot = simulate_snapshot(snapshot, self.preview_fraction)
        return snapshot

    def _start_render_thread(self):
        """Start the one-slot latest-frame worker."""
        if self._render_thread and self._render_thread.is_alive():
            return
        self._frame_error = None
        self._render_thread_running = True
        self._render_thread = threading.Thread(target=self._render_thread_loop, daemon=True)
        self._render_thread.start()

    def _stop_render_thread(self):
        """Stop background render thread."""
        self._render_thread_running = False
        self._frame_request.set()
        if self._render_thread:
            self._render_thread.join(timeout=2.0)
            self._render_thread = None
        self._frame_request.clear()

    def _render_thread_loop(self):
        """Render, encode, and send only the latest requested frame."""
        while self._render_thread_running:
            self._frame_request.wait(timeout=0.5)
            if not self._render_thread_running:
                break
            if not self._frame_request.is_set():
                continue
            self._frame_request.clear()
            try:
                if self.backend and self.backend.is_connected():
                    with self._frame_snapshot_lock:
                        snapshot = self._frame_snapshot
                        self._frame_snapshot = None
                    if snapshot is None:
                        continue
                    img = self.render_theme_image(snapshot=snapshot)
                    self._last_device_frame = img
                    jpeg_data = self.image_to_jpeg(img)
                    self.send_jpeg_frame(jpeg_data)
                    self.frameDelivered.emit()
            except Exception as e:
                self._frame_error = e

    def _capture_render_snapshot(self, page=None):
        """Copy GUI-owned render state before handing it to the worker."""
        sensor_data = self.get_sensor_data()
        elements = []
        page_elements = self.get_current_page_elements() if page is None else [element for element in self.elements if element.page == page]
        for element in page_elements:
            data = element.to_dict()
            if element.source.startswith(('network_', 'hardware_')) and element.source not in sensor_data:
                data['value'] = 0
                element.value = 0
            if element.source != 'static' and element.source in sensor_data:
                value = sensor_data[element.source]
                data['value'] = float(value) if isinstance(value, (int, float)) else 0
                element.value = data['value']
            if element.animate_gauge:
                data['value'] = self._animated_value(element, float(data['value']))
            elements.append((id(element), data))
        return {'background_color': self.background_color, 'elements': elements, 'sensor_data': sensor_data}

    def _animated_value(self, element, target):
        """Ease the shown gauge value toward target, independent of frame rate.

        Both the editor preview and the device loop call this (GUI thread only).
        """
        now = time.perf_counter()
        current, last = self._animated_values.get(id(element), (target, now))
        dt = min(now - last, 0.5)
        diff = target - current
        speed = min(0.9, element.animation_speed * (1.0 + min(1.0, abs(diff) / 50.0) * 2.0))
        current += diff * (1 - (1 - speed) ** (dt * 60))
        if abs(target - current) < 0.05:
            current = target
        self._animated_values[id(element)] = (current, now)
        return current

    def start_continuous_send(self):
        interval = round(1000 / self.target_fps)
        self._frame_deadline = time.perf_counter()
        self._last_frame_request_time = 0
        self._frames_skipped = 0
        self._start_render_thread()
        if self.live_preview_timer is None:
            self.live_preview_timer = QTimer(self)
            self.live_preview_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.live_preview_timer.timeout.connect(self.send_frame_with_sensors)
            self.live_preview_timer.start(interval)
        else:
            self.live_preview_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.live_preview_timer.setInterval(interval)
            self.live_preview_timer.start()

    def stop_continuous_send(self):
        if self.live_preview_timer:
            self.live_preview_timer.stop()
            self.live_preview_timer = None
        self._stop_render_thread()

    def send_frame_with_sensors(self):
        if not self.device:
            return
        try:
            if self._frame_error is not None:
                error = self._frame_error
                self._frame_error = None
                raise error
            current_time = time.perf_counter()
            frame_interval = 1.0 / self.target_fps
            min_frame_interval = frame_interval * 0.9
            if self._last_frame_request_time > 0 and current_time - self._last_frame_request_time < min_frame_interval:
                return
            if self._frame_request.is_set():
                self._frames_skipped += 1
            snapshot = self._capture_render_snapshot()
            with self._frame_snapshot_lock:
                self._frame_snapshot = snapshot
            self._frame_request.set()
            self._last_frame_request_time = current_time
            self._canvas_update_counter += 1
            if self._canvas_update_counter >= self._canvas_update_interval:
                self._canvas_update_counter = 0
                self.canvas.set_elements(self.elements, self.current_page)
                self.canvas.update()
        except DeviceIOError as e:
            logger.warning(f'Device error, disconnecting: {e}')
            self.disconnect_display()
            self._was_connected_before_sleep = True
            self._reconnect_attempts = 0
            self._start_reconnect_timer()
            self.notify('Display disconnected - attempting to reconnect...')
        except Exception:
            logger.exception('Frame render error')
            self.notify('Frame render failed; see diagnostics')

    def get_current_page_elements(self):
        """Get elements for current page."""
        return [el for el in self.elements if getattr(el, 'page', 1) == self.current_page]

    def render_theme_image(self, snapshot=None):
        if snapshot is None:
            snapshot = self._editor_snapshot()
        background_frame = video_background.get_frame_pil() if video_background.enabled else None
        return self.renderer.render(snapshot, (constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT), background_frame)

    def image_to_jpeg(self, img, quality=80):
        """Convert image to JPEG bytes with optimized settings."""
        if self.display_brightness < 100:
            img = ImageEnhance.Brightness(img).enhance(self.display_brightness / 100)
        if self.display_orientation == 'flip_v':
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif self.display_orientation == 'flip_h':
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif self.display_orientation == 'rotate_180':
            img = img.transpose(Image.ROTATE_180)
        elif self.display_orientation == 'rotate_90_cw':
            img = img.transpose(Image.ROTATE_270)
        elif self.display_orientation == 'rotate_90_ccw':
            img = img.transpose(Image.ROTATE_90)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=False, subsampling=2)
        return buffer.getvalue()

    def send_jpeg_frame(self, jpeg_data):
        """Send JPEG frame to display via backend."""
        if not self.backend:
            raise DeviceIOError('Device not connected')
        if self.selected_device_def.backend_type == 'hid':
            MAGIC = bytes([218, 219, 220, 221])
            header = bytearray(512)
            header[0:4] = MAGIC
            header[4] = 2
            header[8:12] = bytes([0, 5, 224, 1])
            header[12] = 2
            jpeg_len = len(jpeg_data)
            header[16] = jpeg_len & 255
            header[17] = jpeg_len >> 8 & 255
            header[18] = jpeg_len >> 16 & 255
            header[19] = jpeg_len >> 24 & 255
            first_chunk = min(len(jpeg_data), 492)
            header[20:20 + first_chunk] = jpeg_data[:first_chunk]
            try:
                if not self.backend.send_frame(bytes(header)):
                    raise DeviceIOError('Failed to send header')
                offset = first_chunk
                while offset < len(jpeg_data):
                    chunk = jpeg_data[offset:offset + 512]
                    if len(chunk) < 512:
                        chunk = chunk + bytes(512 - len(chunk))
                    if not self.backend.send_frame(chunk):
                        raise DeviceIOError('Failed to send chunk')
                    offset += 512
            except Exception as e:
                raise DeviceIOError(f'Frame send failed: {e}')
        else:
            try:
                if not self.backend.send_frame(jpeg_data):
                    raise DeviceIOError('Frame send returned False')
            except Exception as e:
                raise DeviceIOError(f'Frame send failed: {e}') from e
