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


class TestFindBestCpuTemperatureCaching(unittest.TestCase):
    @patch('src.core.libre_hw_monitor._load_lhm_types')
    def test_find_best_cpu_temperature_caching(self, mock_load):
        import src.core.libre_hw_monitor as lhm
        # Mock _load_lhm_types to return a mock SensorType
        class MockSensorType:
            Temperature = "Temperature"
        mock_load.return_value = (MagicMock(), MockSensorType)

        reader = lhm._LibreHardwareMonitorReader()

        # Mock sensors
        mock_sensor1 = MagicMock()
        mock_sensor1.SensorType = "Temperature"
        mock_sensor1.Value = 45.0

        mock_sensor2 = MagicMock()
        mock_sensor2.SensorType = "Temperature"
        mock_sensor2.Value = 55.0

        # gpu sensor (should be excluded)
        mock_sensor3 = MagicMock()
        mock_sensor3.SensorType = "Temperature"
        mock_sensor3.Value = 60.0

        # invalid temp sensor (should be included, but value is None initially)
        mock_sensor4 = MagicMock()
        mock_sensor4.SensorType = "Temperature"
        mock_sensor4.Value = None

        mock_sensors = [
            (mock_sensor1, "cpu core #1"),
            (mock_sensor2, "cpu package"),
            (mock_sensor3, "gpu core"),
            (mock_sensor4, "cpu core max")
        ]

        reader._get_sensors = MagicMock(return_value=mock_sensors)

        # Call 1: Should populate the cache and return best temp
        best_temp = reader._find_best_cpu_temperature()
        self.assertEqual(best_temp, 55.0)
        self.assertEqual(len(reader._cpu_temp_sensors), 3) # Should include sensor 1, 2, and 4
        self.assertEqual(reader._get_sensors.call_count, 1)

        # Modify a sensor value and call again
        mock_sensor4.Value = 70.0

        # Call 2: Should use the cache and NOT call _get_sensors again
        best_temp2 = reader._find_best_cpu_temperature()
        self.assertEqual(best_temp2, 70.0)
        self.assertEqual(reader._get_sensors.call_count, 1) # Still 1

if __name__ == "__main__":
    unittest.main()
