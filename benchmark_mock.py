import time
from unittest.mock import MagicMock, patch

from src.core.libre_hw_monitor import LibreHardwareMonitorReader


with (
    patch("src.core.libre_hw_monitor.sys.platform", "linux"),
    patch("src.core.libre_hw_monitor.psutil.cpu_percent", return_value=50.0),
    patch("src.core.libre_hw_monitor.psutil.cpu_freq", return_value=MagicMock(current=4200.0)),
    patch(
        "src.core.libre_hw_monitor.psutil.virtual_memory",
        return_value=MagicMock(percent=40.0, used=8 * 1024 ** 3, available=12 * 1024 ** 3),
    ),
):
    reader = LibreHardwareMonitorReader()
    reader.get_thermal_sensors()

    start = time.time()
    for _ in range(1000):
        reader.get_thermal_sensors()
    end = time.time()

print(f"Time: {end - start:.4f}s")
