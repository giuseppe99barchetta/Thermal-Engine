import ast
import json
import threading
import time
import zipfile
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core import sensors
from src.core.device_backends import (
    DeviceDefinition,
    HIDBackend,
    USBBulkBackend,
    _has_bulk_out_endpoint,
    find_device_definition,
    get_bulk_display_size,
)
from src.core.display_size import (
    device_size_key,
    get_device_size_override,
    resize_theme_elements,
    validate_display_size,
)
from src.core.element import ThemeElement
from src.core.libre_hw_monitor import _classify_lhm_error
from src.core.security import validate_preset_schema
from src.ui.main_window import ThemeEditorWindow
from src.ui.presets import resolve_preset_asset_paths
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
        _last_frame_request_time=0,
        _frame_request=threading.Event(),
        _frame_snapshot=None,
        _frame_snapshot_lock=threading.Lock(),
        _frames_skipped=0,
        _canvas_update_counter=0,
        _canvas_update_interval=3,
        canvas=MagicMock(),
        status_bar=MagicMock(),
    )
    window._capture_render_snapshot = lambda: {"elements": [], "background_color": "#000"}
    window.get_current_page_elements = lambda: []
    window.send_frame_with_sensors = MethodType(
        ThemeEditorWindow.send_frame_with_sensors, window
    )

    window.send_frame_with_sensors()

    assert window._frame_request.is_set()


def test_frame_requests_are_limited_to_selected_fps():
    window = SimpleNamespace(
        device=object(),
        _frame_error=None,
        target_fps=10,
        _last_frame_request_time=0,
        _frame_request=threading.Event(),
        _frame_snapshot=None,
        _frame_snapshot_lock=threading.Lock(),
        _frames_skipped=0,
        _canvas_update_counter=0,
        _canvas_update_interval=99,
        canvas=MagicMock(),
        status_bar=MagicMock(),
    )
    window._capture_render_snapshot = lambda: {"elements": [], "background_color": "#000"}
    window.get_current_page_elements = lambda: []
    window.send_frame_with_sensors = MethodType(
        ThemeEditorWindow.send_frame_with_sensors, window
    )

    with patch(
        "src.ui.main_window.time.perf_counter",
        side_effect=[1.0, 1.01, 1.10],
    ):
        window.send_frame_with_sensors()
        window._frame_request.clear()
        window.send_frame_with_sensors()
        assert not window._frame_request.is_set()
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
        _frame_snapshot={"elements": [], "background_color": "#000"},
        _frame_snapshot_lock=threading.Lock(),
        _frame_error=None,
        _frames_skipped=0,
        target_fps=30,
        last_frame_time=0,
        _last_frame_request_time=0,
        _canvas_update_counter=0,
        _canvas_update_interval=3,
        canvas=MagicMock(),
        status_bar=MagicMock(),
    )
    window._capture_render_snapshot = lambda: {"elements": [], "background_color": "#000"}
    window.render_theme_image = lambda snapshot=None: object()
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


def test_render_snapshot_is_independent_from_gui_elements():
    element = ThemeElement("text", source="cpu_temp", value=0, page=1)
    window = SimpleNamespace(
        elements=[element],
        current_page=1,
        background_color="#123456",
    )
    window.get_current_page_elements = MethodType(
        ThemeEditorWindow.get_current_page_elements, window
    )
    window.get_sensor_data = lambda: {"cpu_temp": 64}
    window._capture_render_snapshot = MethodType(
        ThemeEditorWindow._capture_render_snapshot, window
    )

    snapshot = window._capture_render_snapshot()
    element.value = 99

    assert snapshot["elements"][0][1]["value"] == 64
    assert snapshot["background_color"] == "#123456"


def test_bulk_backend_requires_bulk_out_endpoint():
    util = SimpleNamespace(
        ENDPOINT_OUT=0,
        ENDPOINT_TYPE_BULK=2,
        endpoint_direction=lambda address: address & 0x80,
        endpoint_type=lambda attributes: attributes & 0x03,
    )
    interrupt_out = SimpleNamespace(bEndpointAddress=0x01, bmAttributes=3)
    bulk_out = SimpleNamespace(bEndpointAddress=0x01, bmAttributes=2)

    assert not _has_bulk_out_endpoint([[[interrupt_out]]], util)
    assert _has_bulk_out_endpoint([[[bulk_out]]], util)
    assert find_device_definition(0x0416, 0x5302, "hid").backend_type == "hid"
    assert find_device_definition(0x0416, 0x5302, "usb_bulk").backend_type == "usb_bulk"


def test_usb_bulk_header_contains_non_square_width_and_height():
    definition = DeviceDefinition(
        "Stream Vision",
        0x87AD,
        0x70DB,
        "usb_bulk",
        width=640,
        height=360,
    )
    backend = USBBulkBackend(definition)
    backend.device = MagicMock()
    backend.device.write.side_effect = lambda endpoint, data, timeout: len(data)
    backend.endpoint_out = 0x01
    backend.connected = True
    backend.usb = SimpleNamespace(core=SimpleNamespace(USBError=RuntimeError))

    assert backend.send_frame(b"jpeg")
    payload = backend.device.write.call_args.args[1]
    assert int.from_bytes(payload[8:12], "little") == 640
    assert int.from_bytes(payload[12:16], "little") == 360


def test_stream_vision_size_is_detected_from_bulk_handshake():
    response = bytearray(1024)
    response[24] = 7

    assert get_bulk_display_size(response) == (640, 480)
    response[24] = 255
    assert get_bulk_display_size(response) is None


def test_display_size_override_is_per_device_and_validated():
    definition = DeviceDefinition("Stream Vision", 0x87AD, 0x70DB, "usb_bulk")
    key = device_size_key(definition)

    assert get_device_size_override({key: [640, 360]}, definition) == (640, 360)
    assert get_device_size_override({key: [0, 360]}, definition) is None
    assert validate_display_size("640", "480") == (640, 480)


def test_theme_layout_can_stretch_from_square_to_16_by_9():
    element = ThemeElement(
        "image",
        x=24,
        y=40,
        width=432,
        height=400,
        font_size=20,
    )

    scale_x, scale_y = resize_theme_elements(
        [element],
        (480, 480),
        (640, 360),
    )

    assert (scale_x, scale_y) == (640 / 480, 360 / 480)
    assert (element.x, element.y) == (32, 30)
    assert (element.width, element.height) == (576, 300)
    assert element.font_size == 15


def test_sensor_status_reports_cpu_and_gpu_separately():
    original_status = sensors._sensor_status
    original_reader = sensors._reader
    original_safe = sensors.HAS_SAFE_MONITOR
    original_lhm = sensors.HAS_LHM
    try:
        sensors._reader = MagicMock()
        sensors._reader.get_diagnostics.return_value = {
            "backend": "LibreHardwareMonitor"
        }
        sensors._update_status({"cpu_temp": 63, "gpu_temp": 0})
        status = sensors.get_sensor_status()

        assert status["thermal_available"]
        assert status["cpu_thermal_available"]
        assert not status["gpu_thermal_available"]
        assert status["gpu_thermal_reason"] == "no_supported_sensor"
    finally:
        sensors._sensor_status = original_status
        sensors._reader = original_reader
        sensors.HAS_SAFE_MONITOR = original_safe
        sensors.HAS_LHM = original_lhm


def test_main_window_has_no_duplicate_methods():
    source = Path("src/ui/main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    window_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ThemeEditorWindow"
    )
    names = [
        node.name for node in window_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert len(names) == len(set(names))


def test_diagnostic_report_is_ready_to_copy():
    window = SimpleNamespace(
        selected_device_def=DeviceDefinition("Test Display", 1, 2, "hid"),
        target_fps=30,
        _frame_error=None,
        get_sensor_data=lambda: {"cpu_temp": 61, "gpu_temp": 0},
    )
    window.build_diagnostic_report = MethodType(
        ThemeEditorWindow.build_diagnostic_report, window
    )
    status = {
        "platform": "win32",
        "backend": "LibreHardwareMonitor",
        "thermal_available": True,
        "cpu_thermal_available": True,
        "gpu_thermal_available": False,
        "gpu_thermal_reason": "no_supported_sensor",
        "degraded": False,
    }
    with (
        patch.object(sensors, "get_sensor_source_display", return_value="LibreHardwareMonitor"),
        patch.object(sensors, "get_sensor_diagnostics", return_value=status),
    ):
        report = window.build_diagnostic_report()

    assert "Test Display (hid)" in report
    assert "Output size: 1280x480" in report
    assert "CPU temperature: available" in report
    assert "GPU temperature: unavailable (no_supported_sensor)" in report


def test_pawnio_runs_inside_installer_and_is_verified():
    script = Path("installer.iss").read_text(encoding="utf-8")
    assert "procedure CurStepChanged" in script
    assert "ewWaitUntilTerminated" in script
    assert "(not PawnIOInstalled)" in script
    assert 'Filename: "{tmp}\\PawnIO_setup.exe"' not in script


def test_bundled_presets_have_valid_local_assets():
    preset_dir = Path("presets").resolve()
    new_presets = {
        "Aurora Pulse",
        "Blue Marble Telemetry",
        "Cosmic Cliffs HUD",
        "Cosmic Core",
        "Event Horizon Live",
        "Orbital Command",
        "Stream Vision Nebula",
    }
    loaded = set()
    for path in preset_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        valid, errors = validate_preset_schema(data)
        assert valid, f"{path.name}: {errors}"
        resolve_preset_asset_paths(data, preset_dir)
        loaded.add(data["name"])
        for element in data.get("elements", []):
            for field in ("image_path", "gif_path"):
                asset = element.get(field)
                if asset:
                    assert Path(asset).is_file(), f"{path.name}: missing {asset}"

    assert new_presets <= loaded
    for name in new_presets:
        assert (preset_dir / f"{name}.png").is_file()


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
