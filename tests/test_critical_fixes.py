import json
import threading
import time
import zipfile
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core import sensors
from src.core.device_backends import DeviceDefinition, HIDBackend
from src.core.libre_hw_monitor import _classify_lhm_error
from src.ui.main_window import ThemeEditorWindow
from src.ui.video_background import VideoBackground
from src.utils import theme_package, updater


def test_usage_metrics_do_not_claim_thermal_support():
    assert not sensors._has_thermal_data({"cpu_percent": 80, "ram_percent": 50})
    assert sensors._has_thermal_data({"cpu_temp": 60})


def test_lhm_runtime_mismatch_has_stable_reason():
    error = RuntimeError("Cannot resolve System.Runtime, Version=10.0.0.0")
    assert _classify_lhm_error(error) == "dll_incompatible"


def test_hid_backend_owns_report_id_prefix():
    definition = DeviceDefinition("test", 1, 2, "hid")
    backend = HIDBackend(definition)
    backend.device = MagicMock()
    backend.device.write.return_value = 513
    backend.connected = True

    assert backend.send_frame(bytes(512))
    payload = backend.device.write.call_args.args[0]
    assert len(payload) == 513
    assert payload[0] == 0


def test_gui_frame_tick_only_sets_latest_frame_request():
    window = SimpleNamespace(
        device=object(),
        _frame_error=None,
        target_fps=30,
        last_frame_time=0,
        _frame_request=threading.Event(),
        _frames_skipped=0,
        _canvas_update_counter=0,
        _canvas_update_interval=3,
        canvas=MagicMock(),
        status_bar=MagicMock(),
    )
    window.get_current_page_elements = lambda: []
    window.send_frame_with_sensors = MethodType(
        ThemeEditorWindow.send_frame_with_sensors, window
    )

    window.send_frame_with_sensors()

    assert window._frame_request.is_set()


def test_slow_backend_does_not_block_gui_frame_tick():
    entered = threading.Event()
    release = threading.Event()
    backend = MagicMock()
    backend.is_connected.return_value = True
    window = SimpleNamespace(
        backend=backend,
        device=object(),
        _render_thread_running=True,
        _frame_request=threading.Event(),
        _frame_error=None,
        _frames_skipped=0,
        target_fps=30,
        last_frame_time=0,
        _canvas_update_counter=0,
        _canvas_update_interval=3,
        canvas=MagicMock(),
        status_bar=MagicMock(),
    )
    window.get_sensor_data = lambda: {}
    window.get_current_page_elements = lambda: []
    window.render_theme_image = lambda: object()
    window.image_to_jpeg = lambda image: b"jpeg"
    window.record_frame_time = lambda: None
    window.send_jpeg_frame = lambda data: (entered.set(), release.wait(1))
    window._render_thread_loop = MethodType(ThemeEditorWindow._render_thread_loop, window)
    window.send_frame_with_sensors = MethodType(
        ThemeEditorWindow.send_frame_with_sensors, window
    )

    worker = threading.Thread(target=window._render_thread_loop)
    worker.start()
    window._frame_request.set()
    assert entered.wait(1)

    started = time.perf_counter()
    window.send_frame_with_sensors()
    elapsed = time.perf_counter() - started

    release.set()
    window._render_thread_running = False
    window._frame_request.set()
    worker.join(1)
    assert elapsed < 0.05
    assert not worker.is_alive()


def test_video_buffer_is_bounded_to_three_frames():
    video = VideoBackground()
    for value in range(5):
        video._frame_buffer.append(value)
    assert list(video._frame_buffer) == [2, 3, 4]


def test_windows_installer_requires_digest_for_auto_install():
    assert not updater.can_auto_install_asset("ThermalEngine-Setup.exe", "win32")
    assert updater.can_auto_install_asset(
        "ThermalEngine-Setup.exe", "win32", expected_hash="abc"
    )


def test_theme_archive_file_count_limit(tmp_path):
    archive = tmp_path / "many.thermal"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("theme.json", json.dumps({"name": "test", "elements": []}))
        for index in range(theme_package.MAX_ARCHIVE_FILES):
            zf.writestr(f"assets/{index}.png", b"x")

    valid, error, _ = theme_package.validate_thermal_archive(archive)
    assert not valid
    assert "too many files" in error


def test_theme_archive_total_size_limit(tmp_path):
    archive = tmp_path / "large.thermal"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("theme.json", json.dumps({"name": "test", "elements": []}))
        zf.writestr("assets/test.png", b"0123456789")

    with patch.object(theme_package, "MAX_UNCOMPRESSED_SIZE", 5):
        valid, error, _ = theme_package.validate_thermal_archive(archive)
    assert not valid
    assert "expands beyond" in error
