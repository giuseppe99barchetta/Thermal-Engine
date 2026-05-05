"""
Safe hardware monitor reader.

This module intentionally avoids bundled kernel monitoring drivers.
It uses user-mode Windows APIs and psutil only, so Windows Defender does not
see a vulnerable driver extracted at runtime.
"""

import ctypes
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


class LibreHardwareMonitorReader:
    """Compatibility wrapper with old class name, but no bundled driver."""

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
