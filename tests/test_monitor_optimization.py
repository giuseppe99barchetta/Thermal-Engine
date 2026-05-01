import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock clr and LibreHardwareMonitor before importing the reader
sys.modules["clr"] = MagicMock()
lhm_mock = MagicMock()
sys.modules["LibreHardwareMonitor"] = lhm_mock
sys.modules["LibreHardwareMonitor.Hardware"] = lhm_mock.Hardware

class MockSensorType:
    Temperature = "Temperature"
    Clock = "Clock"
    Power = "Power"
    Load = "Load"

lhm_mock.Hardware.SensorType = MockSensorType

from src.core.libre_hw_monitor import LibreHardwareMonitorReader

class TestLibreHardwareMonitorOptimization(unittest.TestCase):
    def setUp(self):
        # Create a mock computer and hardware
        self.mock_cpu = MagicMock()
        self.mock_cpu.Name = "CPU"
        self.mock_gpu = MagicMock()
        self.mock_gpu.Name = "GPU"

        # CPU sensors
        self.cpu_temp = MagicMock()
        self.cpu_temp.Name = "CPU Package"
        self.cpu_temp.SensorType = MockSensorType.Temperature
        self.cpu_temp.Value = 45.0

        self.cpu_clock = MagicMock()
        self.cpu_clock.Name = "Core 0 Clock"
        self.cpu_clock.SensorType = MockSensorType.Clock
        self.cpu_clock.Value = 3200.0

        self.mock_cpu.Sensors = [self.cpu_temp, self.cpu_clock]
        self.mock_cpu.SubHardware = []

        # GPU sensors
        self.gpu_temp = MagicMock()
        self.gpu_temp.Name = "GPU Core"
        self.gpu_temp.SensorType = MockSensorType.Temperature
        self.gpu_temp.Value = 55.0

        self.gpu_load = MagicMock()
        self.gpu_load.Name = "GPU Core"
        self.gpu_load.SensorType = MockSensorType.Load
        self.gpu_load.Value = 20.0

        self.mock_gpu.Sensors = [self.gpu_temp, self.gpu_load]
        self.mock_gpu.SubHardware = []

        # Patch Computer and its methods
        with patch('src.core.libre_hw_monitor.Computer') as MockComputer:
            self.reader = LibreHardwareMonitorReader()
            self.reader.computer.Hardware = [self.mock_cpu, self.mock_gpu]

    def test_get_thermal_sensors_optimization(self):
        # Call get_thermal_sensors
        sensors = self.reader.get_thermal_sensors()

        # Verify values
        self.assertEqual(sensors["cpu_temp"], 45.0)
        self.assertEqual(sensors["cpu_clock"], 3200)
        self.assertEqual(sensors["gpu_temp"], 55.0)
        self.assertEqual(sensors["gpu_percent"], 20.0)

        # Verify Update calls
        self.assertEqual(self.mock_cpu.Update.call_count, 1)
        self.assertEqual(self.mock_gpu.Update.call_count, 1)

    def test_update_called_once_per_retrieval(self):
        # Call get_thermal_sensors
        self.reader.get_thermal_sensors()

        self.assertEqual(self.mock_cpu.Update.call_count, 1)
        self.assertEqual(self.mock_gpu.Update.call_count, 1)

        # Call it again and verify Update count increases by only 1
        self.reader.get_thermal_sensors()
        self.assertEqual(self.mock_cpu.Update.call_count, 2)
        self.assertEqual(self.mock_gpu.Update.call_count, 2)

if __name__ == "__main__":
    unittest.main()
