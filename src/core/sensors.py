"""Background hardware sensor monitoring with an honest degraded state."""

import logging
import threading
import time

from src.core.libre_hw_monitor import (
    SafeHardwareMonitorReader,
)

logger = logging.getLogger(__name__)

# Configuration
_SENSOR_UPDATE_INTERVAL = 0.5

# Track initialization state
HAS_SAFE_MONITOR = False
SENSOR_ERROR = None

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
    "cpu_percent": 0,
    "ram_percent": 0,
    "ram_used": 0,
    "ram_available": 0,
    "net_upload": 0,
    "net_download": 0,
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
_reader_lock = threading.RLock()
_sensor_status = {
    "backend": None,
    "thermal_available": False,
    "cpu_thermal_available": False,
    "gpu_thermal_available": False,
    "cpu_thermal_reason": "backend_error",
    "gpu_thermal_reason": "backend_error",
    "degraded": True,
    "reason": "backend_error",
    "values": _latest_sensor_data.copy(),
}


def _has_thermal_data(data):
    return bool(data) and any(float(data.get(key, 0) or 0) > 0 for key in ("cpu_temp", "gpu_temp"))


def _update_status(data, error=None):
    global HAS_SAFE_MONITOR, HAS_LHM, SENSOR_ERROR, LHM_ERROR, _sensor_status
    diagnostics = {}
    try:
        diagnostics = _reader.get_diagnostics() if _reader else {}
    except Exception:
        pass

    backend = diagnostics.get("backend") or diagnostics.get("source")
    cpu_thermal_available = float((data or {}).get("cpu_temp", 0) or 0) > 0
    gpu_thermal_available = float((data or {}).get("gpu_temp", 0) or 0) > 0
    thermal_available = cpu_thermal_available or gpu_thermal_available
    reason = None
    if error:
        reason = diagnostics.get("reason") or "backend_error"
    elif not thermal_available:
        if backend == "LibreHardwareMonitor" and diagnostics.get("pawnio_installed") is False:
            reason = "pawnio_missing"
        else:
            reason = diagnostics.get("reason") or "no_supported_sensor"

    HAS_SAFE_MONITOR = thermal_available
    HAS_LHM = thermal_available and backend == "LibreHardwareMonitor"
    SENSOR_ERROR = str(error) if error else diagnostics.get("initialization_error")
    LHM_ERROR = SENSOR_ERROR
    unavailable_reason = reason or "no_supported_sensor"
    with _sensor_data_lock:
        _sensor_status = {
            "backend": backend,
            "thermal_available": thermal_available,
            "cpu_thermal_available": cpu_thermal_available,
            "gpu_thermal_available": gpu_thermal_available,
            "cpu_thermal_reason": None if cpu_thermal_available else unavailable_reason,
            "gpu_thermal_reason": None if gpu_thermal_available else unavailable_reason,
            "degraded": not thermal_available,
            "reason": reason,
            "values": (data or {}).copy(),
        }


def _apply_smoothing(raw_data):
    smoothed = raw_data.copy()

    for key in _SMOOTHED_SENSORS:
        if key in raw_data:
            raw = raw_data[key]
            if raw <= 0:
                smoothed[key] = raw
                _smoothed_values.pop(key, None)
                continue
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
        _reader = SafeHardwareMonitorReader()
    return _reader


def _sensor_polling_thread():
    global _latest_sensor_data, _sensor_thread_running, HAS_SAFE_MONITOR, HAS_LHM

    while _sensor_thread_running:
        try:
            with _reader_lock:
                reader = _get_reader()
                data = reader.get_thermal_sensors()
            if data:
                smoothed = _apply_smoothing(data)
                with _sensor_data_lock:
                    _latest_sensor_data = smoothed
                _update_status(smoothed)
        except Exception as e:
            _update_status(get_cached_sensors(), e)
            with _reader_lock:
                if _reader and hasattr(_reader, "invalidate_cache"):
                    _reader.invalidate_cache()
            logger.exception("Sensor poll failed")

        time.sleep(_SENSOR_UPDATE_INTERVAL)


def init_sensors(app_dir=None):
    global HAS_SAFE_MONITOR, SENSOR_ERROR, HAS_LHM, LHM_ERROR
    global _sensor_thread, _sensor_thread_running

    if _sensor_thread_running:
        stop_sensors()

    try:
        with _reader_lock:
            reader = _get_reader()
            initial = reader.get_thermal_sensors()
        if initial:
            with _sensor_data_lock:
                _latest_sensor_data.update(initial)
        _update_status(initial)
        logger.info("Sensor backend initialized: %s", _sensor_status['backend'] or 'unknown')

    except Exception as e:
        _update_status({}, e)
        logger.exception("Safe hardware monitor initialization failed")

    _sensor_thread_running = True
    _sensor_thread = threading.Thread(
        target=_sensor_polling_thread,
        daemon=True
    )
    _sensor_thread.start()

    logger.info("Background sensor polling started")
    return HAS_SAFE_MONITOR


def get_cached_sensors():
    with _sensor_data_lock:
        return _latest_sensor_data.copy()


def get_sensors_sync():
    try:
        with _reader_lock:
            return _get_reader().get_thermal_sensors()
    except Exception as exc:
        _update_status(get_cached_sensors(), exc)
        return None


def get_sensor_status():
    with _sensor_data_lock:
        status = _sensor_status.copy()
        status["values"] = _latest_sensor_data.copy()
        return status


def invalidate_sensor_cache():
    """Refresh hardware discovery after resume or device changes."""
    with _reader_lock:
        if _reader and hasattr(_reader, "invalidate_cache"):
            _reader.invalidate_cache()


def get_sensor_diagnostics():
    diagnostics = {}
    try:
        reader = _get_reader()
        if hasattr(reader, "get_diagnostics"):
            diagnostics.update(reader.get_diagnostics())
    except Exception as e:
        diagnostics["sensor_error"] = str(e)
    diagnostics.update(get_sensor_status())
    diagnostics["connected"] = HAS_LHM
    diagnostics["sensor_error"] = SENSOR_ERROR or diagnostics.get("sensor_error")
    return diagnostics


# Backwards compatibility aliases
get_lhm_sensors = get_cached_sensors
get_lhm_sensors_sync = get_sensors_sync


def stop_sensors():
    global _sensor_thread_running, _sensor_thread, HAS_SAFE_MONITOR, HAS_LHM, _reader

    logger.info("Stopping sensor monitoring")

    _sensor_thread_running = False
    if _sensor_thread and _sensor_thread.is_alive():
        _sensor_thread.join(timeout=3.0)

    _sensor_thread = None
    with _reader_lock:
        if _reader and hasattr(_reader, "close"):
            _reader.close()
    _reader = None
    HAS_SAFE_MONITOR = False
    HAS_LHM = False
    _update_status({}, None)

    logger.info("Sensor monitoring stopped")


def get_sensor_source():
    diagnostics = get_sensor_diagnostics()
    return diagnostics.get("source") or diagnostics.get("backend")


def get_sensor_source_display():
    diagnostics = get_sensor_diagnostics()
    if not diagnostics.get("thermal_available"):
        backend = diagnostics.get("backend")
        return f"Degraded ({backend})" if backend else "Not connected"
    return diagnostics.get("backend") or diagnostics.get("source") or "Safe Hardware Monitor"


# Backwards compatibility for older imports.
HAS_LHM = HAS_SAFE_MONITOR
LHM_ERROR = SENSOR_ERROR
