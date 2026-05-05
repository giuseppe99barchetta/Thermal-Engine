import time

from src.core.libre_hw_monitor import LibreHardwareMonitorReader


reader = LibreHardwareMonitorReader()
reader.get_thermal_sensors()

start = time.time()
for _ in range(1000):
    reader.get_thermal_sensors()
end = time.time()

print(f"Time: {end - start:.4f}s")
