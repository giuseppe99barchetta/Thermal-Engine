"""
Hardware monitor reader.

Primary path uses bundled LibreHardwareMonitorLib.dll through pythonnet for
CPU/GPU temperature, clocks, power, and load. If that cannot initialize, it
falls back to safe user-mode Windows counters and psutil usage metrics.
"""

import ctypes
import os
import sys

import psutil


DEFAULT_SENSOR_DATA = {
    "cpu_temp": 0.0,
    "cpu_clock": 0.0,
    "cpu_power": 0.0,
    "gpu_temp": 0.0,
    "gpu_percent": 0.0,
    "gpu_clock": 0.0,
    "gpu_memory_clock": 0.0,
    "gpu_memory_percent": 0.0,
    "gpu_power": 0.0,
}

_LHM_TYPES = None


def _get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_lhm_types():
    global _LHM_TYPES
    if _LHM_TYPES is not None:
        return _LHM_TYPES

    dll_path = os.path.join(_get_base_path(), "libs", "LibreHardwareMonitorLib.dll")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"LibreHardwareMonitorLib.dll not found at {dll_path}")

    import clr

    clr.AddReference(os.path.abspath(dll_path))
    from LibreHardwareMonitor.Hardware import Computer, SensorType

    _LHM_TYPES = (Computer, SensorType)
    return _LHM_TYPES


class _PdhGpuReader:
    PDH_FMT_DOUBLE = 0x00000200
    ERROR_SUCCESS = 0
    PDH_MORE_DATA = 0x800007D2

    class _PDH_FMT_COUNTERVALUE_DOUBLE(ctypes.Structure):
        _fields_ = [
            ("CStatus", ctypes.c_ulong),
            ("doubleValue", ctypes.c_double),
        ]

    def __init__(self):
        self._pdh = ctypes.WinDLL("pdh.dll")
        self._query = ctypes.c_void_p()
        self._counters = []
        self._setup_api()
        self._open()

    def _setup_api(self):
        self._pdh.PdhOpenQueryW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._pdh.PdhOpenQueryW.restype = ctypes.c_ulong

        self._pdh.PdhAddEnglishCounterW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._pdh.PdhAddEnglishCounterW.restype = ctypes.c_ulong

        self._pdh.PdhAddCounterW.argtypes = self._pdh.PdhAddEnglishCounterW.argtypes
        self._pdh.PdhAddCounterW.restype = ctypes.c_ulong

        self._pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        self._pdh.PdhCollectQueryData.restype = ctypes.c_ulong

        self._pdh.PdhGetFormattedCounterValue.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(self._PDH_FMT_COUNTERVALUE_DOUBLE),
        ]
        self._pdh.PdhGetFormattedCounterValue.restype = ctypes.c_ulong

        self._pdh.PdhExpandWildCardPathW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_ulong,
        ]
        self._pdh.PdhExpandWildCardPathW.restype = ctypes.c_ulong

        self._pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
        self._pdh.PdhCloseQuery.restype = ctypes.c_ulong

    def _open(self):
        status = self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._query))
        if status != self.ERROR_SUCCESS:
            raise OSError(f"PdhOpenQueryW failed: 0x{status:08x}")

        for path in self._expand_paths(r"\GPU Engine(*)\Utilization Percentage"):
            lowered = path.lower()
            if not any(engine in lowered for engine in ("engtype_3d", "engtype_compute")):
                continue

            counter = ctypes.c_void_p()
            status = self._pdh.PdhAddEnglishCounterW(
                self._query,
                path,
                0,
                ctypes.byref(counter),
            )
            if status != self.ERROR_SUCCESS:
                status = self._pdh.PdhAddCounterW(
                    self._query,
                    path,
                    0,
                    ctypes.byref(counter),
                )
            if status == self.ERROR_SUCCESS:
                self._counters.append(counter)

        if not self._counters:
            raise OSError("No GPU Engine utilization counters available")

        self._pdh.PdhCollectQueryData(self._query)

    def _expand_paths(self, wildcard_path):
        size = ctypes.c_ulong(0)
        status = self._pdh.PdhExpandWildCardPathW(
            None,
            wildcard_path,
            None,
            ctypes.byref(size),
            0,
        )
        if status not in (self.PDH_MORE_DATA, self.ERROR_SUCCESS) or size.value == 0:
            return []

        buffer = ctypes.create_unicode_buffer(size.value)
        status = self._pdh.PdhExpandWildCardPathW(
            None,
            wildcard_path,
            buffer,
            ctypes.byref(size),
            0,
        )
        if status != self.ERROR_SUCCESS:
            return []

        raw = buffer[:size.value]
        return [part for part in raw.split("\x00") if part]

    def get_gpu_usage(self):
        status = self._pdh.PdhCollectQueryData(self._query)
        if status != self.ERROR_SUCCESS:
            return 0.0

        total = 0.0
        value_type = ctypes.c_ulong(0)
        value = self._PDH_FMT_COUNTERVALUE_DOUBLE()
        for counter in self._counters:
            status = self._pdh.PdhGetFormattedCounterValue(
                counter,
                self.PDH_FMT_DOUBLE,
                ctypes.byref(value_type),
                ctypes.byref(value),
            )
            if status == self.ERROR_SUCCESS and value.CStatus == self.ERROR_SUCCESS:
                total += max(0.0, value.doubleValue)

        return min(100.0, total)

    def close(self):
        if self._query:
            self._pdh.PdhCloseQuery(self._query)
            self._query = ctypes.c_void_p()


class _UsageOnlyReader:
    def __init__(self):
        self._gpu_reader = None
        if sys.platform == "win32":
            try:
                self._gpu_reader = _PdhGpuReader()
            except Exception:
                self._gpu_reader = None

    def get_thermal_sensors(self):
        data = DEFAULT_SENSOR_DATA.copy()
        data["cpu_percent"] = float(psutil.cpu_percent(interval=None))

        freq = psutil.cpu_freq()
        if freq and freq.current:
            data["cpu_clock"] = float(freq.current)

        vm = psutil.virtual_memory()
        data["ram_percent"] = float(vm.percent)
        data["ram_used"] = float(vm.used) / (1024 ** 3)
        data["ram_available"] = float(vm.available) / (1024 ** 3)

        if self._gpu_reader:
            data["gpu_percent"] = self._gpu_reader.get_gpu_usage()

        return data

    def close(self):
        if self._gpu_reader:
            self._gpu_reader.close()
            self._gpu_reader = None


class _LibreHardwareMonitorReader:
    def __init__(self):
        Computer, _ = _load_lhm_types()
        self.computer = Computer()
        self.computer.IsCpuEnabled = True
        self.computer.IsGpuEnabled = True
        self.computer.IsMemoryEnabled = True
        self.computer.IsMotherboardEnabled = True
        self.computer.IsStorageEnabled = False
        self.computer.Open()
        self._cached_sensors = []
        self._cache_initialized = False
        self._sensor_mapping_cache = {}
        self._gpu_usage_sensors = None
        self._gpu_usage_fallback = None

    def _get_sensors(self):
        if self._cache_initialized:
            for hw in self.computer.Hardware:
                hw.Update()
                for sub in hw.SubHardware:
                    sub.Update()
            return self._cached_sensors

        sensors = []
        for hw in self.computer.Hardware:
            hw.Update()
            for sensor in hw.Sensors:
                sensors.append((sensor, f"{hw.Name} {sensor.Name}".lower()))
            for sub in hw.SubHardware:
                sub.Update()
                for sensor in sub.Sensors:
                    sensors.append((sensor, f"{hw.Name} {sub.Name} {sensor.Name}".lower()))

        self._cached_sensors = sensors
        self._cache_initialized = True
        return sensors

    def _find_sensor(self, names, sensor_type, sensors=None):
        if sensors is None:
            sensors = self._get_sensors()

        cache_key = (tuple(names), sensor_type)
        if cache_key in self._sensor_mapping_cache:
            sensor = self._sensor_mapping_cache[cache_key]
            if sensor is not None and sensor.Value is not None:
                return float(sensor.Value)
            return 0.0

        names_lower = [name.lower() for name in names]
        for sensor, label in sensors:
            if sensor.SensorType != sensor_type:
                continue

            for name in names_lower:
                if name in label:
                    self._sensor_mapping_cache[cache_key] = sensor
                    if sensor.Value is not None:
                        return float(sensor.Value)
                    return 0.0

        self._sensor_mapping_cache[cache_key] = None
        return 0.0

    def _find_best_cpu_temperature(self, sensors=None):
        if sensors is None:
            sensors = self._get_sensors()

        _, SensorType = _load_lhm_types()
        include_terms = (
            "cpu",
            "processor",
            "package",
            "tctl",
            "tdie",
            "ccd",
            "core #",
            "core max",
            "core average",
            "intel core",
            "amd ryzen",
        )
        exclude_terms = (
            "gpu",
            "graphics",
            "memory junction",
            "vram",
            "hot spot",
            "hotspot",
            "motherboard",
            "mainboard",
            "chipset",
            "vrm",
            "pch",
            "ssd",
            "hdd",
            "nvme",
            "drive",
        )

        best = 0.0
        for sensor, label in sensors:
            if sensor.SensorType != SensorType.Temperature:
                continue
            if any(term in label for term in exclude_terms):
                continue
            if not any(term in label for term in include_terms):
                continue
            if sensor.Value is None:
                continue

            value = float(sensor.Value)
            if 5.0 <= value <= 125.0:
                best = max(best, value)

        return best

    def get_cpu_temp(self, sensors=None):
        _, SensorType = _load_lhm_types()
        cpu_temp = self._find_sensor(
            [
                "cpu package",
                "cpu core",
                "core max",
                "core average",
                "tctl",
                "tdie",
                "cpu die",
                "cpu ccd",
            ],
            SensorType.Temperature,
            sensors,
        )
        if cpu_temp > 0:
            return cpu_temp
        return self._find_best_cpu_temperature(sensors)

    def get_cpu_clock(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(["core 0 clock", "cpu core"], SensorType.Clock, sensors)

    def get_cpu_power(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(
            ["cpu package power", "ppt", "cpu power"],
            SensorType.Power,
            sensors,
        )

    def get_gpu_temp(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(
            ["gpu core", "gpu temperature"],
            SensorType.Temperature,
            sensors,
        )

    def get_gpu_clock(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(["gpu core clock", "gpu clock"], SensorType.Clock, sensors)

    def get_gpu_memory_clock(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(["memory clock"], SensorType.Clock, sensors)

    def get_gpu_usage(self, sensors=None):
        _, SensorType = _load_lhm_types()
        if sensors is None:
            sensors = self._get_sensors()

        if self._gpu_usage_sensors is None:
            candidates = ["gpu core", "gpu total", "d3d", "3d", "compute"]
            self._gpu_usage_sensors = []
            self._gpu_usage_fallback = None

            for sensor, label in sensors:
                if sensor.SensorType != SensorType.Load:
                    continue

                if "gpu" in label:
                    for candidate in candidates:
                        if candidate in label:
                            self._gpu_usage_sensors.append(sensor)
                            break

                if self._gpu_usage_fallback is None and "3d" in label:
                    self._gpu_usage_fallback = sensor

        best = 0.0
        for sensor in self._gpu_usage_sensors:
            if sensor.Value is not None:
                best = max(best, float(sensor.Value))

        if best > 0.0:
            return best

        if self._gpu_usage_fallback and self._gpu_usage_fallback.Value is not None:
            return float(self._gpu_usage_fallback.Value)

        return 0.0

    def get_gpu_memory_usage(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(["memory load", "memory usage"], SensorType.Load, sensors)

    def get_gpu_power(self, sensors=None):
        _, SensorType = _load_lhm_types()
        return self._find_sensor(["gpu power", "board power"], SensorType.Power, sensors)

    def get_thermal_sensors(self):
        sensors = self._get_sensors()
        data = {
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
        data["cpu_percent"] = float(psutil.cpu_percent(interval=None))
        return data

    def close(self):
        if self.computer:
            self.computer.Close()
            self.computer = None


class LibreHardwareMonitorReader:
    def __init__(self):
        try:
            self._reader = _LibreHardwareMonitorReader()
            self.source = "LibreHardwareMonitor"
        except Exception as exc:
            print(f"[Sensors] LibreHardwareMonitor unavailable: {exc}")
            self._reader = _UsageOnlyReader()
            self.source = "usage-only"

    def get_thermal_sensors(self):
        return self._reader.get_thermal_sensors()

    def close(self):
        if hasattr(self._reader, "close"):
            self._reader.close()


SafeHardwareMonitorReader = LibreHardwareMonitorReader

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


if __name__ == "__main__":
    reader = LibreHardwareMonitorReader()
    for key, value in reader.get_thermal_sensors().items():
        print(f"{key}: {value}")
