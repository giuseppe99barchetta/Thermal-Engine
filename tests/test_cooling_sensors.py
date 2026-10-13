from types import SimpleNamespace
from unittest.mock import patch

from src.core.constants import DATA_SOURCES, SOURCE_UNITS, get_value_with_unit
from src.core.libre_hw_monitor import _LibreHardwareMonitorReader


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
