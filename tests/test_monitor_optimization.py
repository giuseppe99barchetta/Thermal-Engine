import unittest
from collections import namedtuple
from unittest.mock import MagicMock, patch

from src.core.libre_hw_monitor import LibreHardwareMonitorReader
from src.core import sensors


class TestSafeHardwareMonitor(unittest.TestCase):
    @patch("src.core.libre_hw_monitor.sys.platform", "linux")
    @patch("src.core.libre_hw_monitor.psutil.virtual_memory")
    @patch("src.core.libre_hw_monitor.psutil.cpu_freq")
    @patch("src.core.libre_hw_monitor.psutil.cpu_percent")
    @patch("src.core.libre_hw_monitor.psutil.sensors_temperatures")
    def test_get_thermal_sensors_without_driver(
        self,
        mock_sensors_temperatures,
        mock_cpu_percent,
        mock_cpu_freq,
        mock_virtual_memory,
    ):
        mock_cpu_percent.return_value = 25.0
        mock_cpu_freq.return_value = MagicMock(current=4200.0)
        mock_virtual_memory.return_value = MagicMock(
            percent=60.0,
            used=8 * 1024 ** 3,
            available=12 * 1024 ** 3,
        )
        mock_sensors_temperatures.return_value = {}

        reader = LibreHardwareMonitorReader()
        sensors = reader.get_thermal_sensors()

        self.assertEqual(sensors["cpu_percent"], 25.0)
        self.assertEqual(sensors["cpu_clock"], 4200.0)
        self.assertEqual(sensors["ram_percent"], 60.0)
        self.assertEqual(sensors["ram_used"], 8.0)
        self.assertEqual(sensors["ram_available"], 12.0)
        self.assertEqual(sensors["cpu_temp"], 0.0)
        self.assertEqual(sensors["cpu_power"], 0.0)

    @patch("src.core.libre_hw_monitor.sys.platform", "win32")
    @patch("src.core.libre_hw_monitor._PdhGpuReader")
    def test_gpu_usage_uses_windows_performance_counters(self, mock_pdh_reader):
        mock_pdh_reader.return_value.get_gpu_usage.return_value = 33.0

        reader = LibreHardwareMonitorReader()
        sensors = reader.get_thermal_sensors()

        self.assertEqual(sensors["gpu_percent"], 33.0)

    @patch("src.core.libre_hw_monitor._LibreHardwareMonitorReader", side_effect=RuntimeError("no dll"))
    @patch("src.core.libre_hw_monitor.sys.platform", "linux")
    @patch("src.core.libre_hw_monitor.psutil.virtual_memory")
    @patch("src.core.libre_hw_monitor.psutil.cpu_freq")
    @patch("src.core.libre_hw_monitor.psutil.cpu_percent")
    @patch("src.core.libre_hw_monitor.psutil.sensors_temperatures")
    @patch("src.core.libre_hw_monitor._LinuxReader._read_nvidia_smi")
    @patch("src.core.libre_hw_monitor._LinuxReader._read_sysfs_gpu")
    def test_linux_fallback_reads_cpu_temp(
        self,
        mock_sysfs_gpu,
        mock_nvidia_smi,
        mock_sensors_temperatures,
        mock_cpu_percent,
        mock_cpu_freq,
        mock_virtual_memory,
        _mock_platform_reader,
    ):
        shwtemp = namedtuple("shwtemp", ["label", "current", "high", "critical"])
        mock_cpu_percent.return_value = 25.0
        mock_cpu_freq.return_value = MagicMock(current=4200.0)
        mock_virtual_memory.return_value = MagicMock(
            percent=60.0,
            used=8 * 1024 ** 3,
            available=12 * 1024 ** 3,
        )
        mock_sensors_temperatures.return_value = {
            "k10temp": [shwtemp(label="Tctl", current=67.5, high=None, critical=None)]
        }
        mock_nvidia_smi.return_value = {}
        mock_sysfs_gpu.return_value = {}

        reader = LibreHardwareMonitorReader()
        data = reader.get_thermal_sensors()

        self.assertEqual(reader.source, "linux-fallback")
        self.assertEqual(data["cpu_temp"], 67.5)
        self.assertEqual(data["cpu_percent"], 25.0)

    @patch("src.core.libre_hw_monitor._LibreHardwareMonitorReader", side_effect=RuntimeError("no dll"))
    @patch("src.core.libre_hw_monitor.sys.platform", "linux")
    @patch("src.core.libre_hw_monitor.psutil.virtual_memory")
    @patch("src.core.libre_hw_monitor.psutil.cpu_freq")
    @patch("src.core.libre_hw_monitor.psutil.cpu_percent")
    @patch("src.core.libre_hw_monitor.psutil.sensors_temperatures")
    @patch("src.core.libre_hw_monitor._LinuxReader._read_nvidia_smi")
    def test_linux_fallback_reads_nvidia_gpu_metrics(
        self,
        mock_nvidia_smi,
        mock_sensors_temperatures,
        mock_cpu_percent,
        mock_cpu_freq,
        mock_virtual_memory,
        _mock_platform_reader,
    ):
        mock_cpu_percent.return_value = 15.0
        mock_cpu_freq.return_value = MagicMock(current=4000.0)
        mock_virtual_memory.return_value = MagicMock(
            percent=40.0,
            used=6 * 1024 ** 3,
            available=10 * 1024 ** 3,
        )
        mock_sensors_temperatures.return_value = {}
        mock_nvidia_smi.return_value = {
            "gpu_temp": 55.0,
            "gpu_percent": 44.0,
            "gpu_clock": 2100.0,
            "gpu_power": 160.0,
        }

        reader = LibreHardwareMonitorReader()
        data = reader.get_thermal_sensors()

        self.assertEqual(data["gpu_temp"], 55.0)
        self.assertEqual(data["gpu_percent"], 44.0)
        self.assertEqual(data["gpu_clock"], 2100.0)
        self.assertEqual(data["gpu_power"], 160.0)

    @patch("src.core.sensors.SafeHardwareMonitorReader")
    def test_init_sensors_requires_non_zero_data(self, mock_reader_cls):
        original_reader = sensors._reader
        original_has_safe = sensors.HAS_SAFE_MONITOR
        original_has_lhm = sensors.HAS_LHM
        original_thread_running = sensors._sensor_thread_running
        original_thread = sensors._sensor_thread

        mock_reader = MagicMock()
        mock_reader.get_thermal_sensors.return_value = {
            "cpu_temp": 0.0,
            "cpu_clock": 0.0,
            "cpu_power": 0.0,
            "gpu_temp": 0.0,
            "gpu_percent": 0.0,
            "gpu_clock": 0.0,
            "gpu_memory_clock": 0.0,
            "gpu_memory_percent": 0.0,
            "gpu_power": 0.0,
        }
        mock_reader_cls.return_value = mock_reader

        sensors._reader = None
        sensors._sensor_thread_running = False
        sensors._sensor_thread = None
        sensors.HAS_SAFE_MONITOR = False
        sensors.HAS_LHM = False

        try:
            sensors.init_sensors()
            self.assertFalse(sensors.HAS_SAFE_MONITOR)
            self.assertFalse(sensors.HAS_LHM)
        finally:
            sensors.stop_sensors()
            sensors._reader = original_reader
            sensors.HAS_SAFE_MONITOR = original_has_safe
            sensors.HAS_LHM = original_has_lhm
            sensors._sensor_thread_running = original_thread_running
            sensors._sensor_thread = original_thread

    @patch("src.core.libre_hw_monitor._LibreHardwareMonitorReader", side_effect=RuntimeError("no dll"))
    @patch("src.core.libre_hw_monitor.sys.platform", "linux")
    @patch("src.core.libre_hw_monitor.psutil.virtual_memory")
    @patch("src.core.libre_hw_monitor.psutil.cpu_freq")
    @patch("src.core.libre_hw_monitor.psutil.cpu_percent")
    @patch("src.core.libre_hw_monitor.psutil.sensors_temperatures")
    @patch("src.core.libre_hw_monitor._LinuxReader._read_nvidia_smi")
    @patch("src.core.libre_hw_monitor._LinuxReader._read_sysfs_gpu")
    def test_linux_diagnostics_report_sources(
        self,
        mock_sysfs_gpu,
        mock_nvidia_smi,
        mock_sensors_temperatures,
        mock_cpu_percent,
        mock_cpu_freq,
        mock_virtual_memory,
        _mock_platform_reader,
    ):
        shwtemp = namedtuple("shwtemp", ["label", "current", "high", "critical"])
        mock_cpu_percent.return_value = 10.0
        mock_cpu_freq.return_value = MagicMock(current=3500.0)
        mock_virtual_memory.return_value = MagicMock(
            percent=30.0,
            used=4 * 1024 ** 3,
            available=12 * 1024 ** 3,
        )
        mock_sensors_temperatures.return_value = {
            "coretemp": [shwtemp(label="Package id 0", current=61.0, high=None, critical=None)]
        }
        mock_nvidia_smi.return_value = {"gpu_temp": 50.0, "gpu_percent": 20.0}
        mock_sysfs_gpu.return_value = {}

        reader = LibreHardwareMonitorReader()
        reader.get_thermal_sensors()
        diagnostics = reader.get_diagnostics()

        self.assertEqual(diagnostics["backend"], "linux-fallback")
        self.assertEqual(diagnostics["cpu_temp_source"], "psutil:coretemp")
        self.assertEqual(diagnostics["gpu_source"], "nvidia-smi")
        self.assertIn("GPU metrics prefer nvidia-smi", " ".join(diagnostics["notes"]))


if __name__ == "__main__":
    unittest.main()
