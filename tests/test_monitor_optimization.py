import unittest
from unittest.mock import MagicMock, patch

from src.core.libre_hw_monitor import LibreHardwareMonitorReader


class TestSafeHardwareMonitor(unittest.TestCase):
    @patch("src.core.libre_hw_monitor.sys.platform", "linux")
    @patch("src.core.libre_hw_monitor.psutil.virtual_memory")
    @patch("src.core.libre_hw_monitor.psutil.cpu_freq")
    @patch("src.core.libre_hw_monitor.psutil.cpu_percent")
    def test_get_thermal_sensors_without_driver(
        self,
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


if __name__ == "__main__":
    unittest.main()
