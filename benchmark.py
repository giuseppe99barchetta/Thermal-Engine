import time
from src.core.libre_hw_monitor import LibreHardwareMonitorReader
from LibreHardwareMonitor.Hardware import SensorType

class MockSensor:
    def __init__(self, name, sensor_type, value):
        self.Name = name
        self.SensorType = sensor_type
        self.Value = value

class MockHardware:
    def __init__(self, name):
        self.Name = name
        self.Sensors = [
            MockSensor("GPU Core", SensorType.Load, 50.0),
            MockSensor("GPU Memory", SensorType.Load, 40.0),
            MockSensor("GPU Core Clock", SensorType.Clock, 1500.0),
            MockSensor("CPU Core", SensorType.Temperature, 60.0),
        ] * 10  # Make it a bit larger
        self.SubHardware = []
    def Update(self):
        pass

class MockComputer:
    def __init__(self):
        self.Hardware = [MockHardware("GPU " + str(i)) for i in range(5)]
    def Open(self):
        pass

r = LibreHardwareMonitorReader()
r.computer = MockComputer()

start = time.time()
for _ in range(1000):
    r.get_thermal_sensors()
end = time.time()
print(f"Time: {end - start:.4f}s")
