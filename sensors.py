"""
Sensor monitoring using HWiNFO Shared Memory.

Requires HWiNFO to be running with "Shared Memory Support" enabled.
"""

import sys
import threading
import time

from hwinfo_reader import (
    get_hwinfo_reader,
    is_hwinfo_available,
    get_hwinfo_sensors,
    HWiNFOReader
)

# Configuration
_SENSOR_UPDATE_INTERVAL = 0.5

# Track initialization state
HAS_HWINFO = False
HWINFO_ERROR = None

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
_SMOOTHED_SENSORS = {"gpu_percent", "cpu_percent", "gpu_clock", "cpu_clock"}
_SMOOTHING_FACTOR = 0.3
_smoothed_values = {}


def _apply_smoothing(raw_data):
    """Apply exponential smoothing to sensor values that fluctuate rapidly."""
    global _smoothed_values

    smoothed = raw_data.copy()

    for key in _SMOOTHED_SENSORS:
        if key in raw_data:
            raw_value = raw_data[key]
            if key in _smoothed_values and _smoothed_values[key] > 0:
                smoothed[key] = _smoothed_values[key] * (1 - _SMOOTHING_FACTOR) + raw_value * _SMOOTHING_FACTOR
            else:
                smoothed[key] = raw_value
            _smoothed_values[key] = smoothed[key]

    return smoothed


def _sensor_polling_thread():
    """Background thread that continuously polls sensors from HWiNFO."""
    global _latest_sensor_data, _sensor_thread_running, HAS_HWINFO

    while _sensor_thread_running:
        try:
            if is_hwinfo_available():
                if not HAS_HWINFO:
                    HAS_HWINFO = True
                    print("[Sensors] Connected to HWiNFO")

                data = get_hwinfo_sensors()
                if data and any(v > 0 for v in data.values()):
                    smoothed_data = _apply_smoothing(data)
                    with _sensor_data_lock:
                        _latest_sensor_data = smoothed_data
            else:
                if HAS_HWINFO:
                    HAS_HWINFO = False
                    print("[Sensors] Lost connection to HWiNFO")

        except Exception as e:
            print(f"[Sensors] Poll error: {e}")

        time.sleep(_SENSOR_UPDATE_INTERVAL)


def init_sensors(app_dir=None):
    """Initialize the sensor system using HWiNFO shared memory."""
    global HAS_HWINFO, HWINFO_ERROR
    global _sensor_thread, _sensor_thread_running, _latest_sensor_data

    # Stop any existing thread first
    if _sensor_thread_running:
        stop_sensors()

    # Check if HWiNFO is available
    if is_hwinfo_available():
        HAS_HWINFO = True
        print("[Sensors] HWiNFO shared memory detected")

        # Do initial read
        initial_data = get_hwinfo_sensors()
        if initial_data:
            with _sensor_data_lock:
                _latest_sensor_data = initial_data.copy()
    else:
        HAS_HWINFO = False
        HWINFO_ERROR = "HWiNFO not running or shared memory not enabled"
        print("[Sensors] HWiNFO not available")
        print("[Sensors] Please start HWiNFO with 'Shared Memory Support' enabled")

    # Start background polling thread (will keep trying if HWiNFO starts later)
    _sensor_thread_running = True
    _sensor_thread = threading.Thread(target=_sensor_polling_thread, daemon=True)
    _sensor_thread.start()

    if HAS_HWINFO:
        print("[Sensors] Background polling started")
    else:
        print("[Sensors] Background polling started (waiting for HWiNFO)")

    return HAS_HWINFO


def get_cached_sensors():
    """Get sensor data from background thread cache (non-blocking)."""
    with _sensor_data_lock:
        return _latest_sensor_data.copy()


def get_sensors_sync():
    """Get sensor data synchronously from HWiNFO."""
    if is_hwinfo_available():
        return get_hwinfo_sensors()
    return None


# Aliases for backwards compatibility
get_lhm_sensors = get_cached_sensors
get_lhm_sensors_sync = get_sensors_sync


def stop_sensors():
    """Stop the sensor background thread."""
    global _sensor_thread_running, _sensor_thread, HAS_HWINFO

    print("[Sensors] Stopping sensor monitoring...")

    _sensor_thread_running = False
    if _sensor_thread and _sensor_thread.is_alive():
        _sensor_thread.join(timeout=3.0)
    _sensor_thread = None

    # Disconnect HWiNFO
    try:
        reader = get_hwinfo_reader()
        reader.disconnect()
    except:
        pass

    HAS_HWINFO = False
    print("[Sensors] Sensor monitoring stopped")


def get_sensor_source():
    """Get the current sensor source name."""
    return "hwinfo" if HAS_HWINFO else None


def get_sensor_source_display():
    """Get a user-friendly sensor source name."""
    if HAS_HWINFO:
        return "HWiNFO"
    else:
        return "Not connected"
