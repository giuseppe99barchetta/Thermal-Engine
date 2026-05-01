"""
LibreHardwareMonitor Reader

Open-source replacement for HWiNFO.
Reads CPU / GPU / RAM / Power / Clocks directly via LibreHardwareMonitor DLL.

No external programs required.
"""

import os
import sys
import threading
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

    def _get_sensors(self):
        sensors = []
        for hw in self.computer.Hardware:
            hw.Update()
            for sensor in hw.Sensors:
                if sensor.Value is not None:
                    sensors.append((hw.Name, sensor))
            for sub in hw.SubHardware:
                sub.Update()
                for sensor in sub.Sensors:
                    if sensor.Value is not None:
                        sensors.append((f"{hw.Name} {sub.Name}", sensor))
        return sensors

    def _find_sensor(self, names, sensor_type, sensors=None):
        if sensors is None:
            sensors = self._get_sensors()

        names = [n.lower() for n in names]

        for hw_name, sensor in sensors:
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

    def get_cpu_temp(self, sensors=None):
        return self._find_sensor(
            ["cpu package", "tctl", "tdie", "cpu die"],
            SensorType.Temperature,
            sensors
        )

    def get_cpu_clock(self, sensors=None):
        return self._find_sensor(
            ["core 0 clock", "cpu core"],
            SensorType.Clock,
            sensors
        )

    def get_cpu_power(self, sensors=None):
        return self._find_sensor(
            ["cpu package power", "ppt", "cpu power"],
            SensorType.Power,
            sensors
        )

    def get_gpu_temp(self, sensors=None):
        return self._find_sensor(
            ["gpu core", "gpu temperature"],
            SensorType.Temperature,
            sensors
        )

    def get_gpu_clock(self, sensors=None):
        return self._find_sensor(
            ["gpu core clock", "gpu clock"],
            SensorType.Clock,
            sensors
        )

    def get_gpu_memory_clock(self, sensors=None):
        return self._find_sensor(
            ["memory clock"],
            SensorType.Clock,
            sensors
        )

    def get_gpu_usage(self, sensors=None):
        if sensors is None:
            sensors = self._get_sensors()

        candidates = [
            "gpu core",
            "gpu total",
            "d3d",
            "3d",
            "compute",
        ]

        best = 0.0
        fallback = 0.0

        for hw_name, sensor in sensors:
            if sensor.SensorType != SensorType.Load:
                continue

            label = f"{hw_name} {sensor.Name}".lower()

            if "gpu" in label:
                for c in candidates:
                    if c in label:
                        best = max(best, float(sensor.Value))

            if fallback == 0.0 and "3d" in label:
                fallback = float(sensor.Value)

        return best if best > 0.0 else fallback

    def get_gpu_memory_usage(self, sensors=None):
        return self._find_sensor(
            ["memory load", "memory usage"],
            SensorType.Load,
            sensors
        )

    def get_gpu_power(self, sensors=None):
        return self._find_sensor(
            ["gpu power", "board power"],
            SensorType.Power,
            sensors
        )

    def get_thermal_sensors(self):
        sensors = self._get_sensors()
        return {
            "cpu_temp": self.get_cpu_temp(sensors),
            "cpu_clock": int(self.get_cpu_clock(sensors)),
            "cpu_power": self.get_cpu_power(sensors),
            "gpu_temp": self.get_gpu_temp(sensors),
            "gpu_percent": self.get_gpu_usage(sensors),
            "gpu_clock": int(self.get_gpu_clock(sensors)),
            "gpu_memory_clock": int(self.get_gpu_memory_clock(sensors)),
            "gpu_memory_percent": self.get_gpu_memory_usage(sensors),
            "gpu_power": self.get_gpu_power(sensors),
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
