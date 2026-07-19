"""Display-size profiles and helpers shared by the UI and device backends."""

MIN_DISPLAY_DIMENSION = 160
MAX_DISPLAY_DIMENSION = 4096

DISPLAY_SIZE_PROFILES = (
    ("Square LCD (480 × 480)", 480, 480),
    ("Thermalright Stream Vision 360 (640 × 480)", 640, 480),
    ("16:9 compact (640 × 360)", 640, 360),
    ("16:9 HD (1280 × 720)", 1280, 720),
    ("Thermalright Trofeo (1280 × 480)", 1280, 480),
)


def validate_display_size(width, height):
    """Return a validated integer display size."""
    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError) as exc:
        raise ValueError("Display width and height must be integers") from exc

    if not (
        MIN_DISPLAY_DIMENSION <= width <= MAX_DISPLAY_DIMENSION
        and MIN_DISPLAY_DIMENSION <= height <= MAX_DISPLAY_DIMENSION
    ):
        raise ValueError(
            f"Display dimensions must be between {MIN_DISPLAY_DIMENSION} "
            f"and {MAX_DISPLAY_DIMENSION} pixels"
        )
    return width, height


def device_size_key(device_def):
    """Build a stable settings key for a physical device transport."""
    return (
        f"{device_def.vendor_id:04x}:{device_def.product_id:04x}:"
        f"{device_def.backend_type}"
    )


def get_device_size_override(overrides, device_def):
    """Read and validate a saved size override, ignoring malformed settings."""
    if not isinstance(overrides, dict):
        return None
    value = overrides.get(device_size_key(device_def))
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return validate_display_size(value[0], value[1])
    except ValueError:
        return None


def resize_theme_elements(elements, old_size, new_size):
    """Stretch a theme layout to fill a new display size in-place."""
    old_width, old_height = validate_display_size(*old_size)
    new_width, new_height = validate_display_size(*new_size)
    scale_x = new_width / old_width
    scale_y = new_height / old_height
    uniform_scale = min(scale_x, scale_y)

    for element in elements:
        element.x = round(element.x * scale_x)
        element.y = round(element.y * scale_y)
        if getattr(element, "width", 0) > 0:
            element.width = max(1, round(element.width * scale_x))
        if getattr(element, "height", 0) > 0:
            element.height = max(1, round(element.height * scale_y))

        if getattr(element, "type", "") in ("circle_gauge", "analog_clock"):
            element.radius = max(1, round(element.radius * uniform_scale))

        for attribute, minimum in (
            ("font_size", 8),
            ("label_font_size", 6),
            ("border_radius", 0),
            ("glass_blur", 0),
            ("line_thickness", 1),
            ("bar_border_width", 1),
        ):
            if hasattr(element, attribute):
                current = getattr(element, attribute)
                if isinstance(current, (int, float)):
                    setattr(
                        element,
                        attribute,
                        max(minimum, round(current * uniform_scale)),
                    )

    return scale_x, scale_y
