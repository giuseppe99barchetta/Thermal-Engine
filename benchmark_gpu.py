import time
from unittest.mock import patch

from src.core.libre_hw_monitor import LibreHardwareMonitorReader


with patch("src.core.libre_hw_monitor.sys.platform", "win32"):
    with patch("src.core.libre_hw_monitor._PdhGpuReader") as mock_pdh:
        mock_pdh.return_value.get_gpu_usage.return_value = 40.0
        reader = LibreHardwareMonitorReader()

        start = time.time()
        for _ in range(1000):
            reader.get_thermal_sensors()
        end = time.time()

print(f"Time: {end - start:.4f}s")
