"""
LibreHardwareMonitor Reader

Open-source replacement for HWiNFO.
Reads CPU / GPU / RAM / Power / Clocks directly via LibreHardwareMonitor DLL.

No external programs required.
"""

import os
import sys
import clr

# -----------------------------
# Load LibreHardwareMonitor DLL
# -----------------------------

def _get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    # Navigate from src/core/ to project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = _get_base_path()
DLL_PATH = os.path.join(BASE_DIR, "libs", "LibreHardwareMonitorLib.dll")

if not os.path.exists(DLL_PATH):
    raise FileNotFoundError(
        "LibreHardwareMonitorLib.dll not found.\n"
        "Download it from:\n"
        "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases\n"
        "and place it in /libs"
    )

clr.AddReference(os.path.abspath(DLL_PATH))

from LibreHardwareMonitor.Hardware import Computer, SensorType

# -----------------------------
# Reader
# -----------------------------

class LibreHardwareMonitorReader:
    def __init__(self):
        self.computer = Computer()
        self.computer.IsCpuEnabled = True
        self.computer.IsGpuEnabled = True
        self.computer.IsMemoryEnabled = True
        self.computer.IsMotherboardEnabled = True
        self.computer.IsStorageEnabled = False
        self.computer.Open()

    def _iter_sensors(self):
        for hw in self.computer.Hardware:
            hw.Update()

            for sensor in hw.Sensors:
                if sensor.Value is not None:
                    yield hw.Name, sensor

            for sub in hw.SubHardware:
                sub.Update()
                for sensor in sub.Sensors:
                    if sensor.Value is not None:
                        yield f"{hw.Name} {sub.Name}", sensor

    def _find_sensor(self, names, sensor_type):
        names = [n.lower() for n in names]

        for hw_name, sensor in self._iter_sensors():
            if sensor.SensorType != sensor_type:
                continue

            label = f"{hw_name} {sensor.Name}".lower()

            for n in names:
                if n in label:
                    return float(sensor.Value)

        return 0.0

    # -----------------------------
    # Public API (drop-in)
    # -----------------------------

    def get_cpu_temp(self):
        return self._find_sensor(
            ["cpu package", "tctl", "tdie", "cpu die"],
            SensorType.Temperature
        )

    def get_cpu_clock(self):
        return self._find_sensor(
            ["core 0 clock", "cpu core"],
            SensorType.Clock
        )

    def get_cpu_power(self):
        return self._find_sensor(
            ["cpu package power", "ppt", "cpu power"],
            SensorType.Power
        )

    def get_gpu_temp(self):
        return self._find_sensor(
            ["gpu core", "gpu temperature"],
            SensorType.Temperature
        )

    def get_gpu_clock(self):
        return self._find_sensor(
            ["gpu core clock", "gpu clock"],
            SensorType.Clock
        )

    def get_gpu_memory_clock(self):
        return self._find_sensor(
            ["memory clock"],
            SensorType.Clock
        )

    def get_gpu_usage(self):
        candidates = [
            "gpu core",
            "gpu total",
            "d3d",
            "3d",
            "compute",
        ]

        best = 0.0

        for hw_name, sensor in self._iter_sensors():
            if sensor.SensorType != SensorType.Load:
                continue

            label = f"{hw_name} {sensor.Name}".lower()

            if "gpu" not in label:
                continue

            for c in candidates:
                if c in label:
                    best = max(best, float(sensor.Value))

        # Fallback (NVIDIA / casi strani)
        if best == 0.0:
            for hw_name, sensor in self._iter_sensors():
                if sensor.SensorType == SensorType.Load:
                    label = f"{hw_name} {sensor.Name}".lower()
                    if "3d" in label:
                        return float(sensor.Value)

        return best

    def get_gpu_memory_usage(self):
        return self._find_sensor(
            ["memory load", "memory usage"],
            SensorType.Load
        )

    def get_gpu_power(self):
        return self._find_sensor(
            ["gpu power", "board power"],
            SensorType.Power
        )

    def get_thermal_sensors(self):
        return {
            "cpu_temp": self.get_cpu_temp(),
            "cpu_clock": int(self.get_cpu_clock()),
            "cpu_power": self.get_cpu_power(),
            "gpu_temp": self.get_gpu_temp(),
            "gpu_percent": self.get_gpu_usage(),
            "gpu_clock": int(self.get_gpu_clock()),
            "gpu_memory_clock": int(self.get_gpu_memory_clock()),
            "gpu_memory_percent": self.get_gpu_memory_usage(),
            "gpu_power": self.get_gpu_power(),
        }


# -----------------------------
# Global helpers (same pattern)
# -----------------------------

_reader = None

def get_hwinfo_reader():
    global _reader
    if _reader is None:
        _reader = LibreHardwareMonitorReader()
    return _reader

def is_hwinfo_available():
    try:
        get_hwinfo_reader()
        return True
    except Exception:
        return False

def get_hwinfo_sensors():
    reader = get_hwinfo_reader()
    return reader.get_thermal_sensors()


# -----------------------------
# Test
# -----------------------------

if __name__ == "__main__":
    r = LibreHardwareMonitorReader()
    sensors = r.get_thermal_sensors()

    print("LibreHardwareMonitor sensors")
    print("=" * 40)
    for k, v in sensors.items():
        print(f"{k}: {v}")
