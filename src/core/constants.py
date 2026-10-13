"""
Constants and configuration for Thermal Engine.
"""

import re

# Display dimensions (default - can be overridden by device)
DISPLAY_WIDTH = 1280  # Default for Trofeo AIO (ultrawide)
DISPLAY_HEIGHT = 480

# Note: Actual display dimensions are determined by the connected device.
# - Thermalright Trofeo: 1280x480 (ultrawide)
# - Thermalright FW 360 Ultra: 480x480 (square)
# - Thermalright Stream Vision 360: 640x480 (handshake-detected)

# HID Device settings
VENDOR_ID = 0x35CC
PRODUCT_ID = 0x0104

# Base element types available in the editor
_BASE_ELEMENT_TYPES = [
    "circle_gauge",
    "bar_gauge",
    "text",
    "rectangle",
    "clock",
    "analog_clock",
    "image",
]

# This will be populated with custom elements after they are loaded
ELEMENT_TYPES = _BASE_ELEMENT_TYPES.copy()


def register_custom_element_types(custom_types):
    """Register custom element types from the elements folder."""
    global ELEMENT_TYPES
    ELEMENT_TYPES = _BASE_ELEMENT_TYPES + list(custom_types)

# Data sources for dynamic elements (flat list for backwards compatibility)
DATA_SOURCES = [
    "static",
    "cpu_percent",
    "cpu_temp",
    "cpu_clock",
    "cpu_power",
    "ram_percent",
    "ram_used",
    "ram_available",
    "gpu_percent",
    "gpu_temp",
    "gpu_clock",
    "gpu_memory_clock",
    "gpu_memory_percent",
    "gpu_power",
    "net_upload",
    "net_download",
    "pump_rpm",
    "fan_rpm",
    "liquid_temp",
    "disk_temp",
    "disk_percent",
]

# Categorized data sources for UI display
# Format: (source_id, display_name, unit, unit_symbol)
DATA_SOURCES_CATEGORIZED = {
    "Static": [
        ("static", "Static Value", "percent", "%"),
    ],
    "CPU": [
        ("cpu_percent", "CPU Utilization", "percent", "%"),
        ("cpu_temp", "CPU Temperature", "temp", "°C"),
        ("cpu_clock", "CPU Clock Speed", "clock", "MHz"),
        ("cpu_power", "CPU Power", "power", "W"),
    ],
    "GPU": [
        ("gpu_percent", "GPU Utilization", "percent", "%"),
        ("gpu_temp", "GPU Temperature", "temp", "°C"),
        ("gpu_clock", "GPU Clock Speed", "clock", "MHz"),
        ("gpu_memory_percent", "GPU Memory", "percent", "%"),
        ("gpu_memory_clock", "GPU Memory Clock", "clock", "MHz"),
        ("gpu_power", "GPU Power", "power", "W"),
    ],
    "Memory": [
        ("ram_percent", "RAM Usage", "percent", "%"),
        ("ram_used", "RAM Used", "size", "GB"),
        ("ram_available", "RAM Available", "size", "GB"),
    ],
    "Network": [
        ("net_upload", "Upload Speed", "speed", "MB/s"),
        ("net_download", "Download Speed", "speed", "MB/s"),
    ],
    "Cooling": [
        ("pump_rpm", "Pump Speed", "rpm", " RPM"),
        ("fan_rpm", "Fan Speed (highest)", "rpm", " RPM"),
        ("liquid_temp", "Liquid Temperature", "temp", "°C"),
    ],
    "Storage": [
        ("disk_temp", "Disk Temperature (highest)", "temp", "°C"),
        ("disk_percent", "Disk Space Used (highest)", "percent", "%"),
    ],
}

# Lookup for source units
SOURCE_UNITS = {}
for category, sources in DATA_SOURCES_CATEGORIZED.items():
    for source_info in sources:
        source_id, name, unit_type, unit_symbol = source_info
        SOURCE_UNITS[source_id] = {
            "name": name,
            "type": unit_type,
            "symbol": unit_symbol
        }

def register_network_sources(sources):
    """Update shared lookup objects so existing imports see configured sensors."""
    for key in list(SOURCE_UNITS):
        if key.startswith("network_"):
            SOURCE_UNITS.pop(key)
    DATA_SOURCES[:] = [key for key in DATA_SOURCES if not key.startswith("network_")]
    DATA_SOURCES_CATEGORIZED.pop("External Sensors", None)
    entries = []
    for source in sources:
        key = f"network_{source['id']}"
        value_type = source.get("value_type", "number")
        symbol = source["unit"] if value_type == "number" else ""
        entries.append((key, source["name"], value_type, symbol))
        DATA_SOURCES.append(key)
        SOURCE_UNITS[key] = {"name": source["name"], "type": value_type, "symbol": symbol,
                             "decimals": source.get("decimals")}
    if entries:
        DATA_SOURCES_CATEGORIZED["External Sensors"] = entries


def register_hardware_sources(sources):
    for key in list(SOURCE_UNITS):
        if key.startswith("hardware_"):
            SOURCE_UNITS.pop(key)
    DATA_SOURCES[:] = [key for key in DATA_SOURCES if not key.startswith("hardware_")]
    DATA_SOURCES_CATEGORIZED.pop("Specific Hardware", None)
    entries = []
    for source in sources:
        key = source["id"]
        SOURCE_UNITS[key] = {"name": source["name"], "type": source["type"], "symbol": source["symbol"]}
        entries.append((key, source["name"], source["type"], source["symbol"]))
        DATA_SOURCES.append(key)
    if entries:
        DATA_SOURCES_CATEGORIZED["Specific Hardware"] = entries


def get_value_with_unit(value, source, temp_hide_unit=False):
    """Format a value with its appropriate unit symbol."""
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if isinstance(value, str):
        return value
    unit_info = SOURCE_UNITS.get(source, {"symbol": "%", "type": "percent"})
    symbol = unit_info["symbol"]
    unit_type = unit_info["type"]

    if unit_type == "number":
        decimals = unit_info.get("decimals")
        return (f"{value:.{decimals}f}" if decimals is not None else f"{value:g}") + symbol
    elif unit_type == "clock":
        return f"{value:.0f}{symbol}"
    elif unit_type == "temp":
        # Option to show only ° instead of °C
        if temp_hide_unit:
            return f"{value:.0f}°"
        return f"{value:.0f}{symbol}"
    elif unit_type == "power":
        return f"{value:.0f}{symbol}"
    elif unit_type == "size":
        return f"{value:.1f}{symbol}"
    elif unit_type == "speed":
        return f"{value:.1f}{symbol}"
    else:  # percent
        return f"{value:.0f}{symbol}"


def format_sensor_template(text, sensor_data):
    """Replace known {sensor} tokens; leave ordinary braces and unknown names intact."""
    def replace(match):
        source = match.group(1)
        if (source not in SOURCE_UNITS and not source.startswith(("network_", "hardware_"))) or source == "static":
            return match.group(0)
        value = sensor_data.get(source)
        return "--" if value is None else get_value_with_unit(value, source)

    return re.sub(r"\{([a-z][a-z0-9_]*)\}", replace, text)


def gauge_fraction(value, maximum=100):
    return max(0, min(1, value / max(1, maximum)))

# Default element properties by type
DEFAULT_ELEMENT_PROPS = {
    "circle_gauge": {"radius": 120, "x": 200, "y": 240, "text": "GAUGE"},
    "bar_gauge": {"width": 300, "height": 30, "x": 100, "y": 100, "text": "BAR"},
    "text": {"x": 100, "y": 100, "text": "Text Label", "font_size": 36, "width": 200, "height": 50},
    "rectangle": {"width": 200, "height": 100, "x": 100, "y": 100, "border_radius": 0, "glass_effect": False, "glass_blur": 10, "glass_opacity": 50},
    "clock": {"x": 100, "y": 100, "font_size": 48, "width": 200, "height": 60},
    "analog_clock": {"radius": 100, "x": 200, "y": 240, "color": "#ffffff", "background_color": "#1a1a2e"},
    "image": {"width": 200, "height": 200, "x": 100, "y": 100}
}
