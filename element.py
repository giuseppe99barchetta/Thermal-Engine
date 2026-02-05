"""
ThemeElement - Data model for theme elements.
"""


class ThemeElement:
    def __init__(self, element_type="text", **kwargs):
        self.type = element_type
        self.x = kwargs.get("x", 100)
        self.y = kwargs.get("y", 100)
        self.width = kwargs.get("width", 200)
        self.height = kwargs.get("height", 50)
        self.radius = kwargs.get("radius", 100)
        self.border_radius = kwargs.get("border_radius", 0)
        self.glass_effect = kwargs.get("glass_effect", False)
        self.glass_blur = kwargs.get("glass_blur", 10)
        self.glass_opacity = kwargs.get("glass_opacity", 50)
        self.color = kwargs.get("color", "#00ff96")
        self.color_opacity = kwargs.get("color_opacity", 100)  # 0-100
        self.background_color = kwargs.get("background_color", "#1a1a2e")
        self.background_color_opacity = kwargs.get("background_color_opacity", 100)  # 0-100
        self.use_custom_text_color = kwargs.get("use_custom_text_color", False)
        # Default text color: white for gauges, element color for others
        default_text_color = "#ffffff" if element_type in ["circle_gauge", "bar_gauge"] else self.color
        self.text_color = kwargs.get("text_color", default_text_color)
        self.text_color_opacity = kwargs.get("text_color_opacity", 100)  # 0-100
        self.text = kwargs.get("text", "Label")
        self.font_size = kwargs.get("font_size", 32)
        self.font_family = kwargs.get("font_family", "Arial")
        self.font_bold = kwargs.get("font_bold", False)
        self.font_italic = kwargs.get("font_italic", False)
        self.text_align = kwargs.get("text_align", "center")
        self.clip = kwargs.get("clip", False)
        self.source = kwargs.get("source", "static")
        self.value = kwargs.get("value", 50)
        self.image_path = kwargs.get("image_path", "")
        self.scale_proportionally = kwargs.get("scale_proportionally", True)
        self.aspect_ratio = kwargs.get("aspect_ratio", 1.0)
        self.name = kwargs.get("name", f"{element_type}_{id(self)}")

        # Line chart options
        self.show_background = kwargs.get("show_background", True)
        self.show_label = kwargs.get("show_label", True)
        self.show_gradient = kwargs.get("show_gradient", True)
        self.line_thickness = kwargs.get("line_thickness", 2)
        self.smooth = kwargs.get("smooth", False)

        # Bar gauge options
        self.rounded_corners = kwargs.get("rounded_corners", False)
        self.gradient_fill = kwargs.get("gradient_fill", False)
        self.gradient_stops = kwargs.get("gradient_stops", [(0.0, "#00ff96"), (1.0, "#ff4444")])  # Gradient color stops
        self.bar_text_mode = kwargs.get("bar_text_mode", "full")  # "full", "value_only", "none"
        # Default text position: "top" for bar gauge, "inside" for others
        default_bar_text_position = "top" if element_type == "bar_gauge" else "inside"
        self.bar_text_position = kwargs.get("bar_text_position", default_bar_text_position)
        # Bar gauge border options
        self.bar_border = kwargs.get("bar_border", False)  # Show border around bar
        self.bar_border_width = kwargs.get("bar_border_width", 2)  # Border stroke width
        self.bar_border_color = kwargs.get("bar_border_color", "#ffffff")  # Border color
        self.bar_border_opacity = kwargs.get("bar_border_opacity", 100)  # Border opacity 0-100
        self.bar_border_position = kwargs.get("bar_border_position", "inside")  # "inside", "center", "outside"

        # Gauge options
        self.auto_color_change = kwargs.get("auto_color_change", False)  # Change color at thresholds
        self.animate_gauge = kwargs.get("animate_gauge", False)  # Animate value changes
        self.animation_speed = kwargs.get("animation_speed", 0.05)  # Animation interpolation speed (0.02-0.15, lower=smoother)
        self.gauge_rounded_ends = kwargs.get("gauge_rounded_ends", False)  # Circle gauge: pill-shaped arc ends

        # Gauge label options (separate from value text)
        # Default label size: 24 for gauges, 16 for others
        default_label_font_size = 24 if element_type in ["circle_gauge", "bar_gauge"] else 16
        self.label_font_size = kwargs.get("label_font_size", default_label_font_size)
        self.label_font_family = kwargs.get("label_font_family", "Arial")
        self.label_font_bold = kwargs.get("label_font_bold", False)
        self.label_font_italic = kwargs.get("label_font_italic", False)
        self.label_text_color = kwargs.get("label_text_color", self.color)  # Label text color

        # GIF options
        self.gif_path = kwargs.get("gif_path", "")
        self.scale_mode = kwargs.get("scale_mode", "fit")  # fit, fill, stretch

        # Clock time format options (for digital clock)
        self.time_format = kwargs.get("time_format", "24h")  # "24h", "12h"
        self.show_am_pm = kwargs.get("show_am_pm", True)  # Show AM/PM indicator
        self.show_seconds = kwargs.get("show_seconds", True)  # Show seconds
        self.show_leading_zero = kwargs.get("show_leading_zero", True)  # Show leading zero (09 vs 9)

        # Analog clock options
        self.show_seconds_hand = kwargs.get("show_seconds_hand", True)
        self.show_clock_border = kwargs.get("show_clock_border", True)
        self.clock_face_style = kwargs.get("clock_face_style", "numbers")  # "numbers", "ticks", "none"
        self.smooth_animation = kwargs.get("smooth_animation", True)

        # Grouping
        self.group = kwargs.get("group", None)  # Group name, None if ungrouped

        # Locking
        self.locked = kwargs.get("locked", False)  # Prevent editing/dragging when True

        # Temperature display option
        self.temp_hide_unit = kwargs.get("temp_hide_unit", False)  # Show only ° instead of °C

    def to_dict(self):
        return {
            "type": self.type,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "radius": self.radius,
            "border_radius": self.border_radius,
            "glass_effect": self.glass_effect,
            "glass_blur": self.glass_blur,
            "glass_opacity": self.glass_opacity,
            "color": self.color,
            "color_opacity": self.color_opacity,
            "background_color": self.background_color,
            "background_color_opacity": self.background_color_opacity,
            "use_custom_text_color": self.use_custom_text_color,
            "text_color": self.text_color,
            "text_color_opacity": self.text_color_opacity,
            "text": self.text,
            "font_size": self.font_size,
            "font_family": self.font_family,
            "font_bold": self.font_bold,
            "font_italic": self.font_italic,
            "text_align": self.text_align,
            "clip": self.clip,
            "source": self.source,
            "value": self.value,
            "image_path": self.image_path,
            "scale_proportionally": self.scale_proportionally,
            "aspect_ratio": self.aspect_ratio,
            "show_background": self.show_background,
            "show_label": self.show_label,
            "show_gradient": self.show_gradient,
            "line_thickness": self.line_thickness,
            "smooth": self.smooth,
            "rounded_corners": self.rounded_corners,
            "gradient_fill": self.gradient_fill,
            "gradient_stops": self.gradient_stops,
            "bar_text_mode": self.bar_text_mode,
            "bar_text_position": self.bar_text_position,
            "bar_border": self.bar_border,
            "bar_border_width": self.bar_border_width,
            "bar_border_color": self.bar_border_color,
            "bar_border_opacity": self.bar_border_opacity,
            "bar_border_position": self.bar_border_position,
            "auto_color_change": self.auto_color_change,
            "animate_gauge": self.animate_gauge,
            "animation_speed": self.animation_speed,
            "gauge_rounded_ends": self.gauge_rounded_ends,
            "label_font_size": self.label_font_size,
            "label_font_family": self.label_font_family,
            "label_font_bold": self.label_font_bold,
            "label_font_italic": self.label_font_italic,
            "label_text_color": self.label_text_color,
            "gif_path": self.gif_path,
            "scale_mode": self.scale_mode,
            "time_format": self.time_format,
            "show_am_pm": self.show_am_pm,
            "show_seconds": self.show_seconds,
            "show_leading_zero": self.show_leading_zero,
            "show_seconds_hand": self.show_seconds_hand,
            "show_clock_border": self.show_clock_border,
            "clock_face_style": self.clock_face_style,
            "smooth_animation": self.smooth_animation,
            "group": self.group,
            "locked": self.locked,
            "temp_hide_unit": self.temp_hide_unit
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            element_type=data.get("type", "text"),
            **{k: v for k, v in data.items() if k != "type"}
        )
