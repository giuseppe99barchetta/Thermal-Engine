import pytest
from src.core.element import ThemeElement

def test_theme_element_initialization_defaults():
    """Test that ThemeElement initializes with correct default values for 'text' type."""
    elem = ThemeElement()
    assert elem.type == "text"
    assert elem.x == 100
    assert elem.y == 100
    assert elem.width == 200
    assert elem.height == 50
    assert elem.radius == 100
    assert elem.border_radius == 0
    assert elem.glass_effect is False
    assert elem.glass_blur == 10
    assert elem.glass_opacity == 50
    assert elem.color == "#00ff96"
    assert elem.color_opacity == 100
    assert elem.background_color == "#1a1a2e"
    assert elem.background_color_opacity == 100
    assert elem.use_custom_text_color is False
    assert elem.text_color == elem.color  # Default for text
    assert elem.text_color_opacity == 100
    assert elem.text == "Label"
    assert elem.font_size == 32
    assert elem.font_family == "Arial"
    assert elem.font_bold is False
    assert elem.font_italic is False
    assert elem.text_align == "center"
    assert elem.clip is False
    assert elem.source == "static"
    assert elem.value == 50
    assert elem.image_path == ""
    assert elem.scale_proportionally is True
    assert elem.aspect_ratio == 1.0
    assert elem.name.startswith("text_")

    # Line chart options
    assert elem.show_background is True
    assert elem.show_label is True
    assert elem.show_gradient is True
    assert elem.line_thickness == 2
    assert elem.smooth is False

    # Bar gauge options
    assert elem.rounded_corners is False
    assert elem.gradient_fill is False
    assert elem.gradient_stops == [(0.0, "#00ff96"), (1.0, "#ff4444")]
    assert elem.bar_text_mode == "full"
    assert elem.bar_text_position == "inside"  # Default for text
    assert elem.bar_border is False
    assert elem.bar_border_width == 2
    assert elem.bar_border_color == "#ffffff"
    assert elem.bar_border_opacity == 100
    assert elem.bar_border_position == "center"

    # Gauge options
    assert elem.auto_color_change is False
    assert elem.animate_gauge is False
    assert elem.animation_speed == 0.05
    assert elem.gauge_rounded_ends is False

    # Gauge label options
    assert elem.label_font_size == 16  # Default for text
    assert elem.label_font_family == "Arial"
    assert elem.label_font_bold is False
    assert elem.label_font_italic is False
    assert elem.label_text_color == elem.color

    # GIF options
    assert elem.gif_path == ""
    assert elem.scale_mode == "fit"

    # Clock options
    assert elem.time_format == "24h"
    assert elem.show_am_pm is True
    assert elem.show_seconds is True
    assert elem.show_leading_zero is True
    assert elem.show_seconds_hand is True
    assert elem.show_clock_border is True
    assert elem.clock_face_style == "numbers"
    assert elem.smooth_animation is True

    # Misc
    assert elem.group is None
    assert elem.locked is False
    assert elem.temp_hide_unit is False
    assert elem.page == 1

def test_theme_element_conditional_defaults():
    """Test conditional defaults for gauge types."""
    # circle_gauge
    circle = ThemeElement(element_type="circle_gauge")
    assert circle.text_color == "#ffffff"
    assert circle.label_font_size == 24

    # bar_gauge
    bar = ThemeElement(element_type="bar_gauge")
    assert bar.text_color == "#ffffff"
    assert bar.label_font_size == 24
    assert bar.bar_text_position == "top"

def test_theme_element_custom_kwargs():
    """Test that custom kwargs override defaults."""
    custom_stops = [(0.0, "#ff0000"), (1.0, "#0000ff")]
    elem = ThemeElement(
        element_type="image",
        x=50,
        y=60,
        width=300,
        height=150,
        color="#ff0000",
        text="Custom Label",
        font_size=24,
        gradient_stops=custom_stops,
        locked=True,
        page=2,
        name="custom_name"
    )
    assert elem.type == "image"
    assert elem.x == 50
    assert elem.y == 60
    assert elem.width == 300
    assert elem.height == 150
    assert elem.color == "#ff0000"
    assert elem.text == "Custom Label"
    assert elem.font_size == 24
    assert elem.gradient_stops == custom_stops
    assert elem.locked is True
    assert elem.page == 2
    assert elem.name == "custom_name"

def test_theme_element_serialization_roundtrip():
    """Test to_dict, from_dict and round-trip preservation."""
    original = ThemeElement(
        element_type="bar_gauge",
        x=10,
        y=20,
        width=100,
        height=40,
        color="#123456",
        text="Test",
        font_size=12,
        page=3,
        name="roundtrip_test"
    )

    data = original.to_dict()
    assert isinstance(data, dict)
    assert data["type"] == "bar_gauge"
    assert data["x"] == 10
    assert data["name"] == "roundtrip_test"

    reconstructed = ThemeElement.from_dict(data)

    # Verify all attributes are equal
    assert reconstructed.type == original.type
    assert reconstructed.name == original.name
    assert reconstructed.x == original.x
    assert reconstructed.y == original.y
    assert reconstructed.width == original.width
    assert reconstructed.height == original.height
    assert reconstructed.radius == original.radius
    assert reconstructed.border_radius == original.border_radius
    assert reconstructed.glass_effect == original.glass_effect
    assert reconstructed.glass_blur == original.glass_blur
    assert reconstructed.glass_opacity == original.glass_opacity
    assert reconstructed.color == original.color
    assert reconstructed.color_opacity == original.color_opacity
    assert reconstructed.background_color == original.background_color
    assert reconstructed.background_color_opacity == original.background_color_opacity
    assert reconstructed.use_custom_text_color == original.use_custom_text_color
    assert reconstructed.text_color == original.text_color
    assert reconstructed.text_color_opacity == original.text_color_opacity
    assert reconstructed.text == original.text
    assert reconstructed.font_size == original.font_size
    assert reconstructed.font_family == original.font_family
    assert reconstructed.font_bold == original.font_bold
    assert reconstructed.font_italic == original.font_italic
    assert reconstructed.text_align == original.text_align
    assert reconstructed.clip == original.clip
    assert reconstructed.source == original.source
    assert reconstructed.value == original.value
    assert reconstructed.image_path == original.image_path
    assert reconstructed.scale_proportionally == original.scale_proportionally
    assert reconstructed.aspect_ratio == original.aspect_ratio
    assert reconstructed.show_background == original.show_background
    assert reconstructed.show_label == original.show_label
    assert reconstructed.show_gradient == original.show_gradient
    assert reconstructed.line_thickness == original.line_thickness
    assert reconstructed.smooth == original.smooth
    assert reconstructed.rounded_corners == original.rounded_corners
    assert reconstructed.gradient_fill == original.gradient_fill
    assert reconstructed.gradient_stops == original.gradient_stops
    assert reconstructed.bar_text_mode == original.bar_text_mode
    assert reconstructed.bar_text_position == original.bar_text_position
    assert reconstructed.bar_border == original.bar_border
    assert reconstructed.bar_border_width == original.bar_border_width
    assert reconstructed.bar_border_color == original.bar_border_color
    assert reconstructed.bar_border_opacity == original.bar_border_opacity
    assert reconstructed.bar_border_position == original.bar_border_position
    assert reconstructed.auto_color_change == original.auto_color_change
    assert reconstructed.animate_gauge == original.animate_gauge
    assert reconstructed.animation_speed == original.animation_speed
    assert reconstructed.gauge_rounded_ends == original.gauge_rounded_ends
    assert reconstructed.label_font_size == original.label_font_size
    assert reconstructed.label_font_family == original.label_font_family
    assert reconstructed.label_font_bold == original.label_font_bold
    assert reconstructed.label_font_italic == original.label_font_italic
    assert reconstructed.label_text_color == original.label_text_color
    assert reconstructed.gif_path == original.gif_path
    assert reconstructed.scale_mode == original.scale_mode
    assert reconstructed.time_format == original.time_format
    assert reconstructed.show_am_pm == original.show_am_pm
    assert reconstructed.show_seconds == original.show_seconds
    assert reconstructed.show_leading_zero == original.show_leading_zero
    assert reconstructed.show_seconds_hand == original.show_seconds_hand
    assert reconstructed.show_clock_border == original.show_clock_border
    assert reconstructed.clock_face_style == original.clock_face_style
    assert reconstructed.smooth_animation == original.smooth_animation
    assert reconstructed.group == original.group
    assert reconstructed.locked == original.locked
    assert reconstructed.temp_hide_unit == original.temp_hide_unit
    assert reconstructed.page == original.page

def test_theme_element_to_dict_content():
    """Verify all expected keys are in to_dict output."""
    elem = ThemeElement()
    data = elem.to_dict()

    expected_keys = [
        "type", "name", "x", "y", "width", "height", "radius", "border_radius",
        "glass_effect", "glass_blur", "glass_opacity", "color", "color_opacity",
        "background_color", "background_color_opacity", "use_custom_text_color",
        "text_color", "text_color_opacity", "text", "font_size", "font_family",
        "font_bold", "font_italic", "text_align", "clip", "source", "value",
        "image_path", "scale_proportionally", "aspect_ratio", "show_background",
        "show_label", "show_gradient", "line_thickness", "smooth", "rounded_corners",
        "gradient_fill", "gradient_stops", "bar_text_mode", "bar_text_position",
        "bar_border", "bar_border_width", "bar_border_color", "bar_border_opacity",
        "bar_border_position", "auto_color_change", "animate_gauge", "animation_speed",
        "gauge_rounded_ends", "label_font_size", "label_font_family", "label_font_bold",
        "label_font_italic", "label_text_color", "gif_path", "scale_mode",
        "time_format", "show_am_pm", "show_seconds", "show_leading_zero",
        "show_seconds_hand", "show_clock_border", "clock_face_style",
        "smooth_animation", "group", "locked", "temp_hide_unit", "page"
    ]

    for key in expected_keys:
        assert key in data

    assert len(data) == len(expected_keys)
