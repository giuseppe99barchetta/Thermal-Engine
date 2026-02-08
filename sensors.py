"""
Sensor monitoring using LibreHardwareMonitor (open-source).

No external programs required.
"""

import threading
import time

from libre_hw_monitor import (
    LibreHardwareMonitorReader,
)

# Configuration
_SENSOR_UPDATE_INTERVAL = 0.5

# Track initialization state
HAS_LHM = False
LHM_ERROR = None

# Background sensor thread
_sensor_thread = None
_sensor_thread_running = False
_sensor_data_lock = threading.Lock()
_latest_sensor_data = {
    "cpu_temp": 0,
    "cpu_clock": 0,
    "cpu_power": 0,
    "gpu_temp": 0,
    "gpu_percent": 0,
    "gpu_clock": 0,
    "gpu_memory_clock": 0,
    "gpu_memory_percent": 0,
    "gpu_power": 0,
}

# Smoothing configuration
_SMOOTHING_FACTOR = 0.15
_smoothed_values = {}

_SMOOTHED_SENSORS = {
    "cpu_temp", "cpu_clock", "cpu_power", "cpu_percent",
    "gpu_temp", "gpu_clock", "gpu_power", "gpu_percent",
    "gpu_memory_clock", "gpu_memory_percent",
}

# Global reader instance
_reader = None


def _apply_smoothing(raw_data):
    smoothed = raw_data.copy()

    for key in _SMOOTHED_SENSORS:
        if key in raw_data:
            raw = raw_data[key]
            if key in _smoothed_values and _smoothed_values[key] > 0:
                smoothed[key] = (
                    _smoothed_values[key] * (1 - _SMOOTHING_FACTOR)
                    + raw * _SMOOTHING_FACTOR
                )
            else:
                smoothed[key] = raw

            _smoothed_values[key] = smoothed[key]

    return smoothed


def _get_reader():
    global _reader
    if _reader is None:
        _reader = LibreHardwareMonitorReader()
    return _reader


def _sensor_polling_thread():
    global _latest_sensor_data, _sensor_thread_running, HAS_LHM

    while _sensor_thread_running:
        try:
            reader = _get_reader()
            data = reader.get_thermal_sensors()

            if data and any(v > 0 for v in data.values()):
                if not HAS_LHM:
                    HAS_LHM = True
                    print("[Sensors] Connected to LibreHardwareMonitor")

                smoothed = _apply_smoothing(data)
                with _sensor_data_lock:
                    _latest_sensor_data = smoothed
            else:
                if HAS_LHM:
                    HAS_LHM = False
                    print("[Sensors] LibreHardwareMonitor returned no data")

        except Exception as e:
            HAS_LHM = False
            print(f"[Sensors] Poll error: {e}")

        time.sleep(_SENSOR_UPDATE_INTERVAL)


def init_sensors(app_dir=None):
    global HAS_LHM, LHM_ERROR
    global _sensor_thread, _sensor_thread_running

    if _sensor_thread_running:
        stop_sensors()

    try:
        reader = _get_reader()
        initial = reader.get_thermal_sensors()
        if initial:
            with _sensor_data_lock:
                _latest_sensor_data.update(initial)
            HAS_LHM = True
            print("[Sensors] LibreHardwareMonitor initialized")
        else:
            HAS_LHM = False
            print("[Sensors] LibreHardwareMonitor started (no data yet)")

    except Exception as e:
        HAS_LHM = False
        LHM_ERROR = str(e)
        print(f"[Sensors] LibreHardwareMonitor init failed: {e}")

    _sensor_thread_running = True
    _sensor_thread = threading.Thread(
        target=_sensor_polling_thread,
        daemon=True
    )
    _sensor_thread.start()

    print("[Sensors] Background polling started")
    return HAS_LHM


def get_cached_sensors():
    with _sensor_data_lock:
        return _latest_sensor_data.copy()


def get_sensors_sync():
    try:
        return _get_reader().get_thermal_sensors()
    except Exception:
        return None


# Backwards compatibility aliases
get_lhm_sensors = get_cached_sensors
get_lhm_sensors_sync = get_sensors_sync


def stop_sensors():
    global _sensor_thread_running, _sensor_thread, HAS_LHM, _reader

    print("[Sensors] Stopping sensor monitoring...")

    _sensor_thread_running = False
    if _sensor_thread and _sensor_thread.is_alive():
        _sensor_thread.join(timeout=3.0)

    _sensor_thread = None
    _reader = None
    HAS_LHM = False

    print("[Sensors] Sensor monitoring stopped")


def get_sensor_source():
    return "librehardwaremonitor" if HAS_LHM else None


def get_sensor_source_display():
    return "LibreHardwareMonitor" if HAS_LHM else "Not connected"
