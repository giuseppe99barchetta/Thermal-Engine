from types import SimpleNamespace
import threading
from unittest.mock import patch

from src.core.constants import DATA_SOURCES, SOURCE_UNITS, get_value_with_unit
from src.core.libre_hw_monitor import _LibreHardwareMonitorReader


def test_missing_cpu_temperature_is_not_a_zero_reading(monkeypatch):
    from src.core import sensors
    monkeypatch.setattr(sensors, "_latest_sensor_data", {"cpu_temp": 0, "gpu_temp": 45, "cpu_percent": 0})
    monkeypatch.setattr(sensors, "_sensor_status", {"cpu_thermal_available": False, "gpu_thermal_available": True})
    monkeypatch.setattr(sensors, "_network_manager", None)
    readings = sensors.get_cached_sensors()
    assert readings == {"cpu_temp": None, "gpu_temp": 45, "cpu_percent": 0}
    from src.core.renderer import ThemeRenderer
    renderer = ThemeRenderer()
    rendered = []
    monkeypatch.setattr(renderer, "render_element_with_opacity", lambda image, element, **kwargs: rendered.append(element))
    renderer.render({"background_color": "#000000", "sensor_data": readings,
                     "elements": [(1, {"type": "circle_gauge", "source": "cpu_temp", "value": 0})]}, (480, 480))
    assert rendered[0].type == "text" and rendered[0].text == "--"


def sensor(name, kind, value, hardware="Cooler"):
    return SimpleNamespace(Name=name, SensorType=kind, Value=value,
                           Hardware=SimpleNamespace(HardwareType=hardware)), name.lower()


def test_cooling_storage_sensors_use_type_names_and_highest_valid_value():
    types = SimpleNamespace(Fan="Fan", Temperature="Temperature", Load="Load")
    values = [
        sensor("Pump", "Fan", 2400), sensor("Pump Control", "Load", 60),
        sensor("Fans", "Fan", 900), sensor("CPU Fan", "Fan", 1200, "Motherboard"),
        sensor("Liquid", "Temperature", 32), sensor("GPU Core", "Temperature", 70, "GpuNvidia"),
        sensor("Temperature", "Temperature", 45, "Storage"),
        sensor("Temperature", "Temperature", 50, "Storage"),
        sensor("Used Space", "Load", 72, "Storage"), sensor("Total Activity", "Load", 100, "Storage"),
        sensor("Pump", "Fan", None), sensor("Water", "Temperature", float("nan")),
        sensor("Fans", "Fan", -1),
    ]
    reader = _LibreHardwareMonitorReader.__new__(_LibreHardwareMonitorReader)
    with patch("src.core.libre_hw_monitor._load_lhm_types", return_value=(None, types)):
        result = reader.get_cooling_storage_sensors(values)
        assert reader.get_cooling_storage_sensors([]) == dict.fromkeys(result, 0)
    assert result == {"pump_rpm": 2400, "fan_rpm": 1200, "liquid_temp": 32,
                      "disk_temp": 50, "disk_percent": 72}
    assert set(result) <= set(DATA_SOURCES) & set(SOURCE_UNITS)
    assert get_value_with_unit(result["pump_rpm"], "pump_rpm") == "2400 RPM"


def test_storage_and_controller_discovery_are_enabled():
    computer = SimpleNamespace(Open=lambda: None)
    with patch("src.core.libre_hw_monitor._load_lhm_types", return_value=(lambda: computer, None)):
        _LibreHardwareMonitorReader()
    assert computer.IsStorageEnabled and computer.IsControllerEnabled


def test_specific_hardware_keeps_same_names_separate_and_stable():
    from src.core.constants import register_hardware_sources, format_sensor_template
    from src.core import constants
    types = SimpleNamespace(Fan="Fan", Temperature="Temperature", Load="Load", Clock="Clock", Power="Power")
    first, _ = sensor("Fan", "Fan", 800)
    second, _ = sensor("Fan", "Fan", 1600)
    first.Identifier, second.Identifier = "/cooler/fan/0", "/cooler/fan/1"
    hardware = SimpleNamespace(Name="Cooler", Sensors=[first, second], SubHardware=[], Update=lambda: None)
    reader = _LibreHardwareMonitorReader.__new__(_LibreHardwareMonitorReader)
    reader.computer = SimpleNamespace(Hardware=[hardware])
    reader._lock = threading.RLock()
    reader._cache_initialized = False
    reader._sensor_mapping_cache = {}
    reader._cpu_temp_sensors = None
    reader._gpu_usage_sensors = None
    reader._gpu_usage_fallback = None
    with patch("src.core.libre_hw_monitor._load_lhm_types", return_value=(None, types)):
        readings = reader.get_thermal_sensors()
        catalog = reader.get_sensor_catalog()
        assert len(catalog) == 2
        assert catalog[0]["id"] != catalog[1]["id"]
        assert [readings[s["id"]] for s in catalog] == [800, 1600]
        second.Value = None
        assert catalog[1]["id"] not in reader.get_thermal_sensors()
        reader.invalidate_cache()
        reader.get_thermal_sensors()
        assert reader.get_sensor_catalog() == catalog
    try:
        # Both fans become separate, selectable sources
        register_hardware_sources(catalog)
        assert {s["id"] for s in catalog} <= set(constants.SOURCE_UNITS)
        assert format_sensor_template("{" + catalog[0]["id"] + "}", readings) == "800 RPM"
    finally:
        register_hardware_sources([])
