"""A sensor that is not on this PC reads None ("--"); a real 0 stays 0."""
import threading
from types import SimpleNamespace

import pytest
from PIL import Image

from src.core import libre_hw_monitor as lhm
from src.core import sensors
from src.core.element import ThemeElement
from src.core.renderer import ThemeRenderer

TYPES = SimpleNamespace(Temperature="Temperature", Clock="Clock", Power="Power", Load="Load", Fan="Fan")


def reader_with(sensor_list, monkeypatch):
    """_LibreHardwareMonitorReader over fake (sensor, label) pairs, without the .NET library."""
    monkeypatch.setattr(lhm, "_load_lhm_types", lambda: (None, TYPES))
    reader = object.__new__(lhm._LibreHardwareMonitorReader)
    reader.computer = SimpleNamespace(Hardware=[])
    reader._cached_sensors, reader._cache_initialized = sensor_list, True
    reader._sensor_catalog, reader._specific_sensors, reader._sensor_mapping_cache = [], [], {}
    reader._gpu_usage_sensors = reader._gpu_usage_fallback = reader._cpu_temp_sensors = None
    reader._lock = threading.RLock()
    return reader


def sensor(kind, value, name="x", hardware="Cpu"):
    return SimpleNamespace(SensorType=kind, Value=value, Name=name, Hardware=SimpleNamespace(HardwareType=hardware))


def test_real_zeros_survive_and_absent_sensors_are_none(monkeypatch):
    reader = reader_with([
        (sensor("Clock", 0.0), "nvidia gpu core clock"), (sensor("Clock", 0.0), "nvidia memory clock"),
        (sensor("Load", 0.0), "nvidia gpu memory load"), (sensor("Power", 0.0), "nvidia gpu power"),
        (sensor("Load", 0.0), "nvidia gpu core"), (sensor("Temperature", 55.0), "cpu package"),
        (sensor("Fan", 0.0, "Fan #1", "Motherboard"), "board fan #1"),
    ], monkeypatch)
    data = reader.get_thermal_sensors()
    assert data["gpu_clock"] == 0 and data["gpu_memory_clock"] == 0 and data["gpu_memory_percent"] == 0
    assert data["gpu_power"] == 0 and data["gpu_percent"] == 0 and data["cpu_temp"] == 55.0
    assert data["fan_rpm"] == 0 and data["pump_rpm"] is None and data["liquid_temp"] is None
    assert data["gpu_temp"] is None and data["cpu_power"] is None


def test_present_gpu_load_without_value_is_not_zero(monkeypatch):
    reader = reader_with([(sensor("Load", None), "nvidia gpu core")], monkeypatch)
    assert reader.get_gpu_usage() is None
    assert reader_with([], monkeypatch).get_thermal_sensors()["cpu_clock"] is None


def test_smoothing_passes_missing_readings_through():
    assert sensors._apply_smoothing({"cpu_temp": None, "gpu_temp": 50})["cpu_temp"] is None


def test_usage_only_reader_reports_missing_gpu_usage(monkeypatch):
    reader = object.__new__(lhm._UsageOnlyReader)
    reader._gpu_reader = SimpleNamespace(get_gpu_usage=lambda: None)
    data = reader.get_thermal_sensors()
    assert data["gpu_percent"] is None and data["cpu_temp"] is None
    reader._gpu_reader = SimpleNamespace(get_gpu_usage=lambda: 0.0)
    assert reader.get_thermal_sensors()["gpu_percent"] == 0


def test_pdh_failure_is_none_and_valid_zero_is_zero():
    pdh = object.__new__(lhm._PdhGpuReader)
    pdh._query, pdh._counters = None, [1]
    pdh._pdh = SimpleNamespace(PdhCollectQueryData=lambda query: 1)
    assert pdh.get_gpu_usage() is None

    def formatted(counter, fmt, value_type, value):
        value._obj.CStatus, value._obj.doubleValue = 0, 0.0
        return 0
    pdh._pdh = SimpleNamespace(PdhCollectQueryData=lambda query: 0, PdhGetFormattedCounterValue=formatted)
    assert pdh.get_gpu_usage() == 0.0


def test_linux_readers_keep_zero_and_drop_unknown(tmp_path, monkeypatch):
    reader = lhm._LinuxReader()
    assert reader._read_first_float(tmp_path / "missing") is None
    card = tmp_path / "card0" / "device"
    card.mkdir(parents=True)
    (card / "vendor").write_text("0x1002")
    (card / "gpu_busy_percent").write_text("0")
    import pathlib
    monkeypatch.setattr(lhm, "Path", lambda text: tmp_path if text == "/sys/class/drm" else pathlib.Path(text))
    assert reader._read_sysfs_gpu()["gpu_percent"] == 0
    result = SimpleNamespace(returncode=0, stdout="65, 30, 1500, N/A\n", stderr="")
    monkeypatch.setattr(lhm.subprocess, "run", lambda *a, **k: result)
    gpu = reader._read_nvidia_smi()
    assert gpu == {"gpu_temp": 65.0, "gpu_percent": 30.0, "gpu_clock": 1500.0}  # power N/A: omitted


@pytest.mark.parametrize("kind", ["circle_gauge", "bar_gauge"])
def test_gauge_without_reading_keeps_its_track_and_prints_dashes(kind):
    element = ThemeElement(kind, source="pump_rpm", x=100, y=100, radius=80, width=300, height=40, max_value=3000)
    renderer = ThemeRenderer()
    missing = renderer.render({"background_color": "#000000", "sensor_data": {"pump_rpm": None},
                               "elements": [(1, element.to_dict())]}, (400, 240))
    blank = Image.new("RGB", (400, 240), "#000000")
    assert missing.getbbox() is not None and missing.tobytes() != blank.tobytes()  # the gauge is drawn
    zero = ThemeRenderer().render({"background_color": "#000000", "sensor_data": {"pump_rpm": 0},
                                   "elements": [(1, element.to_dict())]}, (400, 240))
    assert missing.tobytes() != zero.tobytes()  # "--" instead of "0 RPM"


def test_every_bundled_preset_renders_with_all_readings_missing():
    from src.core import renderer as module
    from src.core.preset_repository import PresetRepository
    repository = PresetRepository()
    failures_before = set(module._logged_failures)
    missing = {key: None for key in lhm.DEFAULT_SENSOR_DATA}
    for name, info in repository.presets.items():
        data = info["data"]
        elements = [(f"{name}/{i}", e) for i, e in enumerate(data.get("elements", []))]
        size = (data.get("display_width", 1280), data.get("display_height", 480))
        ThemeRenderer().render({"background_color": data.get("background_color", "#000000"),
                                "sensor_data": missing, "elements": elements}, size)
    assert module._logged_failures == failures_before  # no element failed (failures are logged, not raised)


def test_nothing_reads_as_zero_before_the_first_poll():
    import subprocess
    import sys
    from pathlib import Path
    code = "from src.core import sensors; print(sorted({repr(v) for v in sensors._latest_sensor_data.values()}))"
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "['None']"  # a fresh process: nothing measured yet


def test_a_failed_poll_keeps_no_stale_readings(monkeypatch):
    monkeypatch.setattr(sensors, "_latest_sensor_data", {"pump_rpm": 1200, "hardware_x": 3})
    monkeypatch.setattr(sensors, "_SENSOR_UPDATE_INTERVAL", 0)
    monkeypatch.setattr(sensors, "_update_status", lambda *a, **k: None)

    def broken():
        sensors._sensor_thread_running = False  # stop after this one iteration
        raise RuntimeError("driver gone")
    monkeypatch.setattr(sensors, "_get_reader", broken)
    monkeypatch.setattr(sensors, "_sensor_thread_running", True)
    sensors._sensor_polling_thread()
    assert sensors._latest_sensor_data == {"pump_rpm": None}
