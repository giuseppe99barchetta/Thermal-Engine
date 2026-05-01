import sys
import types

# Mock clr and LibreHardwareMonitor
mock_clr = types.ModuleType("clr")
mock_clr.AddReference = lambda path: None
sys.modules["clr"] = mock_clr

mock_lhm = types.ModuleType("LibreHardwareMonitor")
mock_lhm.Hardware = types.ModuleType("Hardware")
class MockComputerCls:
    def Open(self): pass
mock_lhm.Hardware.Computer = MockComputerCls
class MockSensorTypeCls:
    Temperature = 0
    Clock = 1
    Power = 2
    Load = 3
mock_lhm.Hardware.SensorType = MockSensorTypeCls
sys.modules["LibreHardwareMonitor"] = mock_lhm
sys.modules["LibreHardwareMonitor.Hardware"] = mock_lhm.Hardware

import time
from src.core.libre_hw_monitor import LibreHardwareMonitorReader

class MockSensor:
    def __init__(self, name, sensor_type, value):
        self.Name = name
        self.SensorType = sensor_type
        self.Value = value

class MockHardware:
    def __init__(self, name):
        self.Name = name
        self.Sensors = [
            MockSensor("Other Sensor", MockSensorTypeCls.Load, 50.0),
            MockSensor("3D Engine", MockSensorTypeCls.Load, 40.0),
        ] * 10
        self.SubHardware = []
    def Update(self):
        # Simulate an expensive update
        time.sleep(0.001)

class MockComputer:
    def __init__(self):
        self.Hardware = [MockHardware("VideoCard " + str(i)) for i in range(5)]
        self.IsCpuEnabled = True
        self.IsGpuEnabled = True
        self.IsMemoryEnabled = True
        self.IsMotherboardEnabled = True
        self.IsStorageEnabled = False
    def Open(self):
        pass

r = LibreHardwareMonitorReader()
r.computer = MockComputer()

start = time.time()
for _ in range(100):
    r.get_gpu_usage()
end = time.time()
print(f"Time: {end - start:.4f}s")
