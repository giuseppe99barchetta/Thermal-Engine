"""PIL theme rendering shared by the editor and physical displays."""

import functools
import json
import logging
import os
import sys
import threading
import time

from PIL import Image, ImageDraw, ImageFont, ImageChops
from elements import get_custom_element
from src.core.constants import get_value_with_unit, format_sensor_template, gauge_fraction
from src.core.element import ThemeElement
from src.core.conditions import apply_condition
from src.core.security import is_safe_path

logger = logging.getLogger(__name__)

# Global font cache for PIL fonts (shared across instances)
_pil_font_cache = {}
_pil_font_cache_lock = threading.Lock()

# Gradient image cache for performance
_gradient_cache = {}
_gradient_cache_max_size = 20  # Reduced from 50 to save memory

@functools.lru_cache(maxsize=64)
def _get_cached_image_element(image_path, width, height, scale_proportionally, color_opacity):
    """Cache loaded, resized, and opacity-adjusted images to prevent disk I/O and resampling overhead."""
    img_overlay = Image.open(image_path).convert('RGBA')
    if scale_proportionally:
        img_overlay.thumbnail((width, height), Image.Resampling.LANCZOS)
    else:
        img_overlay = img_overlay.resize((width, height), Image.Resampling.LANCZOS)

    # Apply opacity to image
    if color_opacity < 100:
        alpha = img_overlay.split()[3]
        alpha = alpha.point(lambda x: int(x * color_opacity / 100))
        img_overlay.putalpha(alpha)

    return img_overlay


def hex_to_rgba(hex_color, opacity=100):
    """Convert hex color and opacity (0-100) to RGBA tuple."""
    if hex_color.startswith('#'):
        hex_color = hex_color[1:]
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    a = int(255 * opacity / 100)
    return (r, g, b, a)

class ThemeRenderer:
    def __init__(self):
        self._render_cache_lock = threading.RLock()
        self._element_render_cache = {}
        self._analog_clock_cache = {}

    def clear_cache(self):
        with self._render_cache_lock:
            self._element_render_cache.clear()
            self._analog_clock_cache.clear()

    def _compute_element_state_hash(self, element):
        return hash(json.dumps(element.to_dict(), sort_keys=True, default=str))

    _font_cache = None

    def _get_font_dirs(self):
        """Get platform-specific font directories."""
        if sys.platform == "win32":
            return [os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')]
        elif sys.platform == "darwin":
            return [
                '/System/Library/Fonts',
                '/Library/Fonts',
                os.path.expanduser('~/Library/Fonts'),
            ]
        else:  # Linux
            return [
                '/usr/share/fonts/truetype',
                '/usr/share/fonts/TTF',
                '/usr/local/share/fonts',
                os.path.expanduser('~/.fonts'),
            ]

    def _build_font_cache(self):
        """Build a cache of font family names to file paths."""
        if self._font_cache is not None:
            return self._font_cache

        self._font_cache = {}

        # Windows: use registry for accurate font names
        if sys.platform == "win32":
            font_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
            try:
                import winreg
                reg_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
                    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
                ]

                for hkey, subkey in reg_paths:
                    try:
                        with winreg.OpenKey(hkey, subkey) as key:
                            i = 0
                            while True:
                                try:
                                    name, value, _ = winreg.EnumValue(key, i)
                                    font_name = name.replace(" (TrueType)", "").replace(" (OpenType)", "")

                                    if not os.path.isabs(value):
                                        value = os.path.join(font_dir, value)

                                    if os.path.exists(value):
                                        self._font_cache[font_name.lower()] = value

                                    i += 1
                                except OSError:
                                    break
                    except OSError:
                        pass
            except ImportError:
                pass
        else:
            # Non-Windows: scan font directories
            for font_dir in self._get_font_dirs():
                if not os.path.exists(font_dir):
                    continue
                try:
                    for root, dirs, files in os.walk(font_dir):
                        for filename in files:
                            if filename.lower().endswith(('.ttf', '.otf', '.ttc')):
                                font_path = os.path.join(root, filename)
                                # Use filename without extension as font name
                                font_name = os.path.splitext(filename)[0].lower()
                                self._font_cache[font_name] = font_path
                except:
                    pass

        return self._font_cache

    def _get_default_font_path(self):
        """Get a default fallback font path for the current platform."""
        if sys.platform == "win32":
            font_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
            for name in ['arial.ttf', 'segoeui.ttf', 'tahoma.ttf']:
                path = os.path.join(font_dir, name)
                if os.path.exists(path):
                    return path
        elif sys.platform == "darwin":
            for path in ['/System/Library/Fonts/Helvetica.ttc', '/Library/Fonts/Arial.ttf']:
                if os.path.exists(path):
                    return path
        else:  # Linux
            for path in [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/TTF/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            ]:
                if os.path.exists(path):
                    return path
        return None

    def get_font_path(self, font_family, bold=False, italic=False):
        font_dirs = self._get_font_dirs()
        font_cache = self._build_font_cache()

        if bold and italic:
            variants = [
                f"{font_family} Bold Italic",
                f"{font_family} Bold Oblique",
                f"{font_family}",
            ]
        elif bold:
            variants = [
                f"{font_family} Bold",
                f"{font_family}",
            ]
        elif italic:
            variants = [
                f"{font_family} Italic",
                f"{font_family} Oblique",
                f"{font_family}",
            ]
        else:
            variants = [
                f"{font_family}",
                f"{font_family} Regular",
            ]

        for variant in variants:
            if variant.lower() in font_cache:
                return font_cache[variant.lower()]

        font_name_lower = font_family.lower()
        for cached_name, cached_path in font_cache.items():
            if font_name_lower in cached_name or cached_name.startswith(font_name_lower):
                return cached_path

        # Try to find font by filename in font directories
        try:
            font_name_clean = font_family.lower().replace(' ', '')
            for font_dir in font_dirs:
                if not os.path.exists(font_dir):
                    continue
                for filename in os.listdir(font_dir):
                    if filename.lower().endswith(('.ttf', '.otf', '.ttc')):
                        if font_name_clean in filename.lower().replace(' ', ''):
                            return os.path.join(font_dir, filename)
        except:
            pass

        # Return platform-appropriate default font
        default_font = self._get_default_font_path()
        if default_font:
            return default_font

        # Last resort fallback
        if sys.platform == "win32":
            return os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf')
        return None

    def get_pil_font(self, element, size_override=None):
        """Get a PIL font with caching for performance."""
        size = size_override or element.font_size
        return self.get_pil_font_custom(element.font_family, element.font_bold, element.font_italic, size)

    def get_pil_font_custom(self, font_family, font_bold, font_italic, font_size):
        """Get a PIL font with explicit parameters and caching."""
        cache_key = (font_family, font_bold, font_italic, font_size)

        with _pil_font_cache_lock:
            if cache_key in _pil_font_cache:
                return _pil_font_cache[cache_key]

        try:
            font_path = self.get_font_path(font_family, font_bold, font_italic)
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        with _pil_font_cache_lock:
            # Limit cache size to prevent memory bloat (hard limit of 50)
            while len(_pil_font_cache) >= 50:
                # Remove oldest entry (FIFO)
                oldest_key = next(iter(_pil_font_cache))
                del _pil_font_cache[oldest_key]
            _pil_font_cache[cache_key] = font

        return font

    def _fast_alpha_composite(self, base, overlay):
        """Helper method to composite only the bounding box of an overlay.
        This is significantly faster than full-screen compositing."""
        bbox = overlay.getbbox()
        if bbox:
            base.alpha_composite(overlay.crop(bbox), (bbox[0], bbox[1]))
        else:
            # If bbox is None, the overlay is completely transparent, so we don't need to composite anything
            pass

    def render(self, snapshot, size, background_frame=None):
        """Render a copied theme snapshot without accessing GUI-owned state."""
        with self._render_cache_lock:
            img = (background_frame.copy().convert("RGBA") if background_frame is not None
                   else Image.new("RGBA", size, color=snapshot["background_color"]))
            for cache_key, data in reversed(snapshot["elements"]):
                element = ThemeElement.from_dict(data)
                apply_condition(element, snapshot.get("sensor_data", {}))
                live_value = snapshot.get("sensor_data", {}).get(element.source)
                if element.source.startswith(("network_", "hardware_")):
                    if element.type == "text":
                        element.value = live_value
                    elif live_value is None or isinstance(live_value, str):
                        if element.type == "circle_gauge":
                            element.x -= element.radius
                            element.y -= element.radius
                            element.width = element.height = element.radius * 2
                        element.type = "text"
                        element.source = "static"
                        element.text = "--"
                if element.type == "text":
                    if element.source != "static" and element.source in snapshot.get("sensor_data", {}):
                        element.value = snapshot["sensor_data"][element.source]
                    text = format_sensor_template(element.text, snapshot.get("sensor_data", {}))
                    if text != element.text:
                        element.text = text
                        element.source = "static"
                if element.visible:
                    self.render_element_with_opacity(img, element, cache_key=cache_key)
            return img.convert("RGB")

    def render_element_with_opacity(self, img, element, cache_key=None):
        """Render an element with opacity support using alpha compositing.
        Uses caching to avoid re-rendering elements whose state hasn't changed."""

        # Use element id for cache key
        elem_id = cache_key if cache_key is not None else id(element)

        cacheable = element.type in {"circle_gauge", "bar_gauge", "text", "image"}
        cacheable = cacheable or (
            element.type == "rectangle" and not getattr(element, "glass_effect", False)
        )
        current_state_hash = self._compute_element_state_hash(element)
        with self._render_cache_lock:
            cached = self._element_render_cache.get(elem_id) if cacheable else None
        if cached:
            cached_overlay, cached_hash, bounds = cached
            if cached_hash == current_state_hash:
                # Cache hit - use cached overlay
                # Optimization: Alpha composite only the bounding box instead of the full screen
                img.alpha_composite(cached_overlay, bounds)
                return

        # Cache miss - render element
        font = self.get_pil_font(element)
        font_small = self.get_pil_font(element, int(element.font_size * 0.6))

        # Get opacity values
        color_opacity = getattr(element, 'color_opacity', 100)
        bg_opacity = getattr(element, 'background_color_opacity', 100)

        # Create overlay that will be composited onto main image
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))

        if element.type == "circle_gauge":
            self.render_circle_gauge_rgba(overlay, element, font, font_small, color_opacity, bg_opacity)
        elif element.type == "bar_gauge":
            self.render_bar_gauge_rgba(overlay, element, font, color_opacity, bg_opacity)
        elif element.type == "text":
            self.render_text_rgba(overlay, element, font, color_opacity)
        elif element.type == "rectangle":
            self.render_rectangle_rgba(overlay, element, color_opacity, blur_source=img)
        elif element.type == "clock":
            # Build time format string based on element settings
            time_format = getattr(element, 'time_format', '24h')
            show_seconds = getattr(element, 'show_seconds', True)
            show_am_pm = getattr(element, 'show_am_pm', True)
            show_leading_zero = getattr(element, 'show_leading_zero', True)

            if time_format == '12h':
                fmt = "%I:%M:%S" if show_seconds else "%I:%M"
                if show_am_pm:
                    fmt += " %p"
            else:  # 24h
                fmt = "%H:%M:%S" if show_seconds else "%H:%M"

            current_time = time.strftime(fmt)

            # Remove leading zero from hour if disabled
            if not show_leading_zero and current_time[0] == '0':
                current_time = current_time[1:]
            temp_element = ThemeElement(
                text=current_time, x=element.x, y=element.y,
                font_family=element.font_family, font_size=element.font_size,
                font_bold=element.font_bold, font_italic=element.font_italic,
                text_align=element.text_align, color=element.color,
                color_opacity=color_opacity,
                width=element.width, height=element.height, clip=element.clip
            )
            self.render_text_rgba(overlay, temp_element, font, color_opacity)
        elif element.type == "analog_clock":
            self.render_analog_clock_rgba(
                overlay,
                element,
                color_opacity,
                bg_opacity,
                cache_key=elem_id,
            )
        elif element.type == "image":
            if element.image_path:
                # Validate image path is safe
                safe, resolved_path, err = is_safe_path(element.image_path, allow_absolute=True)
                if not safe or not os.path.exists(element.image_path):
                    if not safe:
                        logger.warning(f"Unsafe image path blocked: {element.image_path} - {err}")
                    return
                try:
                    # Use cached image element to prevent disk I/O and expensive LANCZOS resampling on every frame
                    img_overlay = _get_cached_image_element(
                        element.image_path,
                        element.width,
                        element.height,
                        element.scale_proportionally,
                        color_opacity
                    )
                    overlay.paste(img_overlay, (element.x, element.y), img_overlay)
                except Exception as e:
                    logger.warning(f"Image load error: {e}")
        else:
            custom = get_custom_element(element.type)
            if custom and custom.get('render_image'):
                try:
                    draw = ImageDraw.Draw(overlay)
                    custom['render_image'](draw, overlay, element)
                except Exception as e:
                    logger.warning(f"Custom element render error: {e}")

        # Cache the rendered overlay
        # Optimization: Crop the overlay to its non-transparent bounding box
        # This makes alpha compositing ~6x faster by avoiding full-screen blending
        bbox = overlay.getbbox()
        if bbox:
            cropped = overlay.crop(bbox)
            bounds = (bbox[0], bbox[1])
            if cacheable:
                with self._render_cache_lock:
                    self._element_render_cache[elem_id] = (cropped, current_state_hash, bounds)
            img.alpha_composite(cropped, bounds)
        else:
            if cacheable:
                with self._render_cache_lock:
                    self._element_render_cache[elem_id] = (overlay, current_state_hash, (0, 0))
            self._fast_alpha_composite(img, overlay)

    def render_rectangle_rgba(self, img, element, opacity, blur_source=None):
        """Render a rectangle with opacity, optional border radius, and glass effect."""
        from PIL import ImageFilter

        border_radius = getattr(element, 'border_radius', 0)
        glass_effect = getattr(element, 'glass_effect', False)
        coords = [element.x, element.y, element.x + element.width, element.y + element.height]

        if glass_effect:
            # Frosted glass effect
            glass_blur = getattr(element, 'glass_blur', 10)
            glass_opacity = getattr(element, 'glass_opacity', 50)

            x, y, w, h = element.x, element.y, element.width, element.height

            # Extract region to blur
            source_img = blur_source if blur_source is not None else img
            region = source_img.crop((x, y, x + w, y + h))

            # Apply gaussian blur
            blurred = region.filter(ImageFilter.GaussianBlur(radius=glass_blur))

            # Draw blurred background onto overlay so cache can preserve effect.
            mask = None
            if border_radius > 0:
                mask = Image.new('L', (w, h), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, w, h], radius=border_radius, fill=255)
            img.paste(blurred, (x, y), mask)

            # Composite the tint over the blur instead of replacing it.
            tint = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(tint)
            tint_rgba = hex_to_rgba(element.color, glass_opacity)

            if border_radius > 0:
                overlay_draw.rounded_rectangle(coords, radius=border_radius, fill=tint_rgba)
            else:
                overlay_draw.rectangle(coords, fill=tint_rgba)

            # Add subtle white border
            border_rgba = (255, 255, 255, 40)
            if border_radius > 0:
                overlay_draw.rounded_rectangle(coords, radius=border_radius, outline=border_rgba, width=1)
            else:
                overlay_draw.rectangle(coords, outline=border_rgba, width=1)
            img.alpha_composite(tint)

        elif opacity >= 100:
            draw = ImageDraw.Draw(img)
            if border_radius > 0:
                draw.rounded_rectangle(coords, radius=border_radius, fill=element.color)
            else:
                draw.rectangle(coords, fill=element.color)
        else:
            # Create overlay with alpha
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            rgba = hex_to_rgba(element.color, opacity)
            if border_radius > 0:
                overlay_draw.rounded_rectangle(coords, radius=border_radius, fill=rgba)
            else:
                overlay_draw.rectangle(coords, fill=rgba)
            self._fast_alpha_composite(img, overlay)

    def render_text_rgba(self, img, element, font, opacity):
        """Render text with opacity."""
        # Determine text to display based on source
        source = getattr(element, 'source', 'static')
        if source and source != 'static':
            # Display sensor value, optionally with label
            value_text = get_value_with_unit(element.value, source, getattr(element, 'temp_hide_unit', False))
            if element.text:
                text = f"{element.text}: {value_text}"
            else:
                text = value_text
        else:
            text = element.text

        # Create a temporary draw to measure text
        temp_draw = ImageDraw.Draw(img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if element.text_align == "left":
            x = element.x - bbox[0]
        elif element.text_align == "right":
            x = element.x + element.width - text_width - bbox[0]
        else:
            x = element.x + (element.width - text_width) // 2 - bbox[0]

        y = element.y + (element.height - text_height) // 2 - bbox[1]

        if opacity >= 100 and not element.clip:
            temp_draw.text((x, y), text, fill=element.color, font=font)
        else:
            # Create overlay with alpha
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            rgba = hex_to_rgba(element.color, opacity)
            overlay_draw.text((x, y), text, fill=rgba, font=font)

            if element.clip:
                # Create mask for clipping
                mask = Image.new('L', img.size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rectangle([element.x, element.y, element.x + element.width, element.y + element.height], fill=255)
                # Apply mask to overlay
                overlay_alpha = overlay.split()[3]
                overlay_alpha = Image.composite(overlay_alpha, Image.new('L', img.size, 0), mask)
                overlay.putalpha(overlay_alpha)

            self._fast_alpha_composite(img, overlay)

    def interpolate_gradient_color(self, gradient_stops, position):
        """Interpolate color from gradient stops at a given position (0-1)."""
        if not gradient_stops:
            return "#00ff96"

        sorted_stops = sorted(gradient_stops)
        position = max(0.0, min(1.0, position))

        if position <= sorted_stops[0][0]:
            return sorted_stops[0][1]
        if position >= sorted_stops[-1][0]:
            return sorted_stops[-1][1]

        for i in range(len(sorted_stops) - 1):
            p1, c1 = sorted_stops[i]
            p2, c2 = sorted_stops[i + 1]
            if p1 <= position <= p2:
                t = (position - p1) / (p2 - p1) if p2 != p1 else 0
                # Parse hex colors
                r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
                r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
                r = int(r1 + t * (r2 - r1))
                g = int(g1 + t * (g2 - g1))
                b = int(b1 + t * (b2 - b1))
                return f"#{r:02x}{g:02x}{b:02x}"

        return sorted_stops[-1][1]

    def create_horizontal_gradient(self, width, height, gradient_stops, opacity=100):
        """Create a horizontal gradient image from gradient stops using NumPy for performance."""
        width = int(width)
        height = int(height)
        if width <= 0 or height <= 0:
            return Image.new('RGBA', (max(1, width), max(1, height)), (0, 0, 0, 0))

        # Check cache first - use tuple of stops for hashable key
        cache_key = (width, height, tuple(gradient_stops) if gradient_stops else (), opacity)
        if cache_key in _gradient_cache:
            return _gradient_cache[cache_key].copy()

        try:
            import numpy as np
            # Create 1D array of colors for the gradient
            colors = np.zeros((width, 4), dtype=np.uint8)
            a = int(255 * opacity / 100)

            for px in range(width):
                position = px / (width - 1) if width > 1 else 0
                color = self.interpolate_gradient_color(gradient_stops, position)
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                colors[px] = [r, g, b, a]

            # Tile the 1D gradient to create 2D image (much faster than putpixel)
            gradient_array = np.tile(colors, (height, 1, 1))
            gradient = Image.fromarray(gradient_array, 'RGBA')
        except ImportError:
            # Fallback without numpy - use line drawing instead of putpixel
            gradient = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(gradient)
            a = int(255 * opacity / 100)

            for px in range(width):
                position = px / (width - 1) if width > 1 else 0
                color = self.interpolate_gradient_color(gradient_stops, position)
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                draw.line([(px, 0), (px, height - 1)], fill=(r, g, b, a))

        # Cache the result (limit cache size)
        if len(_gradient_cache) >= _gradient_cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(_gradient_cache))
            del _gradient_cache[oldest_key]
        _gradient_cache[cache_key] = gradient

        return gradient.copy()

    def render_circle_gauge_rgba(self, img, element, font, font_small, color_opacity, bg_opacity):
        """Render circle gauge with opacity support."""
        x, y = element.x, element.y
        radius = element.radius
        value = element.value

        # Check for gradient fill
        use_gradient = getattr(element, 'gradient_fill', False)
        if use_gradient:
            # Interpolate color from gradient stops based on value
            gradient_stops = getattr(element, 'gradient_stops', [(0.0, "#00ff96"), (1.0, "#ff4444")])
            color = self.interpolate_gradient_color(gradient_stops, gauge_fraction(value, element.max_value))
        else:
            # Determine color based on value thresholds (if enabled)
            auto_color = getattr(element, 'auto_color_change', True)
            if auto_color:
                if "temp" in element.source:
                    if value < 60:
                        color = element.color
                    elif value < 80:
                        color = "#ffcc00"
                    else:
                        color = "#ff3232"
                else:
                    percentage = 100 * gauge_fraction(value, element.max_value)
                    if percentage < 70:
                        color = element.color
                    elif percentage < 90:
                        color = "#ffcc00"
                    else:
                        color = "#ff3232"
            else:
                color = element.color

        # Create overlay for drawing with transparency
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Check for rounded ends (pill shape)
        rounded_ends = getattr(element, 'gauge_rounded_ends', False)
        import math

        # Draw background arc on separate layer for proper opacity handling
        arc_width = 15  # Match canvas pen width
        arc_radius = radius - arc_width // 2
        bg_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_layer)

        # Draw at full opacity
        bg_rgb = hex_to_rgba(element.background_color, 100)
        bg_draw.arc(
            [x - arc_radius, y - arc_radius, x + arc_radius, y + arc_radius],
            start=135, end=405,
            fill=bg_rgb, width=arc_width
        )

        # Draw rounded end caps for background arc
        if rounded_ends:
            cap_radius = arc_width // 2
            # Radial offset to push caps inward along the radius direction
            radial_offset = -7
            # Start cap at 135° (bottom-left)
            start_angle = 135
            start_x = x + (arc_radius + radial_offset) * math.cos(math.radians(start_angle))
            start_y = y + (arc_radius + radial_offset) * math.sin(math.radians(start_angle))
            bg_draw.ellipse(
                [start_x - cap_radius, start_y - cap_radius,
                 start_x + cap_radius, start_y + cap_radius],
                fill=bg_rgb
            )
            # End cap at 45° (bottom-right)
            end_angle_bg = 45
            end_x = x + (arc_radius + radial_offset) * math.cos(math.radians(end_angle_bg))
            end_y = y + (arc_radius + radial_offset) * math.sin(math.radians(end_angle_bg))
            bg_draw.ellipse(
                [end_x - cap_radius, end_y - cap_radius,
                 end_x + cap_radius, end_y + cap_radius],
                fill=bg_rgb
            )

        # Apply bg_opacity to the background layer by scaling the alpha channel
        if bg_opacity < 100:
            r, g, b, a = bg_layer.split()
            a = a.point(lambda x: int(x * bg_opacity / 100))
            bg_layer = Image.merge('RGBA', (r, g, b, a))

        # Composite background layer onto the main overlay
        self._fast_alpha_composite(overlay, bg_layer)

        # Draw value arc - use float for smoother animation
        sweep = 270 * gauge_fraction(value, element.max_value)
        end_angle = 135 + sweep

        if sweep > 0:
            # Create separate layer for value arc to properly handle opacity
            value_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            value_draw = ImageDraw.Draw(value_layer)

            if use_gradient:
                # Draw gradient arc using multiple small segments
                gradient_stops = getattr(element, 'gradient_stops', [(0.0, "#00ff96"), (1.0, "#ff4444")])
                # Draw in 2-degree increments for smooth gradient
                step = 2
                for i in range(0, int(sweep), step):
                    segment_start = 135 + i
                    segment_end = min(135 + i + step, end_angle)
                    # Calculate gradient position (0 to 1) based on arc position
                    t = i / 270.0  # Position along full arc range
                    grad_color = self.interpolate_gradient_color(gradient_stops, t)
                    # Draw at full opacity, we'll apply color_opacity to the layer
                    segment_rgb = hex_to_rgba(grad_color, 100)
                    value_draw.arc(
                        [x - arc_radius, y - arc_radius, x + arc_radius, y + arc_radius],
                        start=segment_start, end=segment_end,
                        fill=segment_rgb, width=arc_width
                    )
                # Draw rounded end caps for gradient arc
                if rounded_ends:
                    cap_radius = arc_width // 2
                    radial_offset = -7
                    # Start cap (use start color)
                    start_color = self.interpolate_gradient_color(gradient_stops, 0)
                    start_rgb = hex_to_rgba(start_color, 100)
                    start_x = x + (arc_radius + radial_offset) * math.cos(math.radians(135))
                    start_y = y + (arc_radius + radial_offset) * math.sin(math.radians(135))
                    value_draw.ellipse(
                        [start_x - cap_radius, start_y - cap_radius,
                         start_x + cap_radius, start_y + cap_radius],
                        fill=start_rgb
                    )
                    # End cap (use color at current position)
                    end_t = sweep / 270.0
                    end_color = self.interpolate_gradient_color(gradient_stops, end_t)
                    end_rgb = hex_to_rgba(end_color, 100)
                    end_x = x + (arc_radius + radial_offset) * math.cos(math.radians(end_angle))
                    end_y = y + (arc_radius + radial_offset) * math.sin(math.radians(end_angle))
                    value_draw.ellipse(
                        [end_x - cap_radius, end_y - cap_radius,
                         end_x + cap_radius, end_y + cap_radius],
                        fill=end_rgb
                    )
            else:
                # Draw at full opacity
                color_rgb = hex_to_rgba(color, 100)
                value_draw.arc(
                    [x - arc_radius, y - arc_radius, x + arc_radius, y + arc_radius],
                    start=135, end=end_angle,
                    fill=color_rgb, width=arc_width
                )
                # Draw rounded end caps for solid color arc
                if rounded_ends:
                    cap_radius = arc_width // 2
                    radial_offset = -7
                    # Start cap
                    start_x = x + (arc_radius + radial_offset) * math.cos(math.radians(135))
                    start_y = y + (arc_radius + radial_offset) * math.sin(math.radians(135))
                    value_draw.ellipse(
                        [start_x - cap_radius, start_y - cap_radius,
                         start_x + cap_radius, start_y + cap_radius],
                        fill=color_rgb
                    )
                    # End cap
                    end_x = x + (arc_radius + radial_offset) * math.cos(math.radians(end_angle))
                    end_y = y + (arc_radius + radial_offset) * math.sin(math.radians(end_angle))
                    value_draw.ellipse(
                        [end_x - cap_radius, end_y - cap_radius,
                         end_x + cap_radius, end_y + cap_radius],
                        fill=color_rgb
                    )

            # Apply color_opacity to the value layer by scaling the alpha channel
            if color_opacity < 100:
                r, g, b, a = value_layer.split()
                a = a.point(lambda x: int(x * color_opacity / 100))
                value_layer = Image.merge('RGBA', (r, g, b, a))

            # Composite value layer onto the main overlay
            self._fast_alpha_composite(overlay, value_layer)

        # Draw value text
        value_text = get_value_with_unit(value, element.source, getattr(element, 'temp_hide_unit', False))
        bbox = draw.textbbox((0, 0), value_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        # Get value text color
        value_text_color = getattr(element, 'text_color', element.color)
        value_text_opacity = getattr(element, 'text_color_opacity', 100)
        value_text_rgba = hex_to_rgba(value_text_color, value_text_opacity)
        draw.text(
            (x - text_width // 2, y - text_height // 2 - 10),
            value_text, fill=value_text_rgba, font=font
        )

        # Draw label text with separate label font settings and color
        label_font = self.get_pil_font_custom(
            getattr(element, 'label_font_family', element.font_family),
            getattr(element, 'label_font_bold', False),
            getattr(element, 'label_font_italic', False),
            getattr(element, 'label_font_size', 16)
        )
        label_text_color = getattr(element, 'label_text_color', element.color)
        label_rgba = hex_to_rgba(label_text_color, getattr(element, 'text_color_opacity', 100))
        bbox = draw.textbbox((0, 0), element.text, font=label_font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (x - text_width // 2, y + radius // 3),
            element.text, fill=label_rgba, font=label_font
        )

        # Composite onto main image
        self._fast_alpha_composite(img, overlay)

    def render_bar_gauge_rgba(self, img, element, font, color_opacity, bg_opacity):
        """Render bar gauge with opacity support."""
        x, y = element.x, element.y
        value = element.value
        width, height = element.width, element.height

        # Check for gradient fill
        use_gradient = getattr(element, 'gradient_fill', False)

        if not use_gradient:
            # Determine color based on value (if auto color enabled)
            auto_color = getattr(element, 'auto_color_change', True)
            if auto_color:
                threshold_value = value if "temp" in element.source else 100 * gauge_fraction(value, element.max_value)
                if threshold_value < 70:
                    color = element.color
                elif threshold_value < 90:
                    color = "#ffcc00"
                else:
                    color = "#ff3232"
            else:
                color = element.color

        rounded = getattr(element, 'rounded_corners', False)
        corner_radius = height // 2 if rounded else 0

        # Create overlay for final compositing
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))

        # Draw background on separate layer for proper opacity handling
        bg_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_layer)
        bg_rgb = hex_to_rgba(element.background_color, 100)  # Full opacity for drawing
        if rounded:
            bg_draw.rounded_rectangle(
                [x, y, x + width, y + height],
                radius=corner_radius,
                fill=bg_rgb
            )
        else:
            bg_draw.rectangle(
                [x, y, x + width, y + height],
                fill=bg_rgb
            )

        # Apply bg_opacity by scaling alpha channel
        if bg_opacity < 100:
            r, g, b, a = bg_layer.split()
            a = a.point(lambda px: int(px * bg_opacity / 100))
            bg_layer = Image.merge('RGBA', (r, g, b, a))

        # Composite background layer onto overlay
        self._fast_alpha_composite(overlay, bg_layer)

        # Draw fill on separate layer
        fill_width = int(width * gauge_fraction(value, element.max_value))
        if fill_width > 0:
            fill_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            fill_draw = ImageDraw.Draw(fill_layer)

            if use_gradient:
                # Draw horizontal gradient using lines at full opacity
                gradient_stops = getattr(element, 'gradient_stops', [(0.0, "#00ff96"), (1.0, "#ff4444")])

                if rounded and fill_width > 0:
                    # Create gradient on temporary image, then mask with rounded rect
                    gradient_layer = Image.new('RGBA', (fill_width, height), (0, 0, 0, 0))
                    gradient_draw = ImageDraw.Draw(gradient_layer)

                    for i in range(fill_width):
                        t = i / (width - 1) if width > 1 else 0
                        grad_color = self.interpolate_gradient_color(gradient_stops, t)
                        r = int(grad_color[1:3], 16)
                        g = int(grad_color[3:5], 16)
                        b = int(grad_color[5:7], 16)
                        gradient_draw.line([(i, 0), (i, height - 1)], fill=(r, g, b, 255))

                    # Create rounded rectangle mask
                    mask = Image.new('L', (fill_width, height), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.rounded_rectangle([0, 0, fill_width, height], radius=corner_radius, fill=255)

                    # Apply mask to gradient
                    gradient_layer.putalpha(ImageChops.multiply(gradient_layer.split()[3], mask))

                    # Paste onto fill layer
                    fill_layer.paste(gradient_layer, (x, y), gradient_layer)
                else:
                    # No rounded corners, draw lines directly
                    for i in range(fill_width):
                        t = i / (width - 1) if width > 1 else 0
                        grad_color = self.interpolate_gradient_color(gradient_stops, t)
                        r = int(grad_color[1:3], 16)
                        g = int(grad_color[3:5], 16)
                        b = int(grad_color[5:7], 16)
                        fill_draw.line([(x + i, y), (x + i, y + height - 1)], fill=(r, g, b, 255))
            else:
                fill_rgb = hex_to_rgba(color, 100)  # Full opacity for drawing
                if rounded:
                    fill_draw.rounded_rectangle(
                        [x, y, x + fill_width, y + height],
                        radius=corner_radius,
                        fill=fill_rgb
                    )
                else:
                    fill_draw.rectangle(
                        [x, y, x + fill_width, y + height],
                        fill=fill_rgb
                    )

            # Apply color_opacity by scaling alpha channel
            if color_opacity < 100:
                r, g, b, a = fill_layer.split()
                a = a.point(lambda px: int(px * color_opacity / 100))
                fill_layer = Image.merge('RGBA', (r, g, b, a))

            # Composite fill layer onto overlay
            self._fast_alpha_composite(overlay, fill_layer)

        # Draw border if enabled
        bar_border = getattr(element, 'bar_border', False)
        if bar_border:
            border_width = getattr(element, 'bar_border_width', 2)
            border_color = getattr(element, 'bar_border_color', '#ffffff')
            border_opacity = getattr(element, 'bar_border_opacity', 100)
            border_position = getattr(element, 'bar_border_position', 'center')

            # Create border layer for proper opacity handling
            border_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border_layer)
            border_rgb = hex_to_rgba(border_color, 100)  # Full opacity for drawing

            half_border = border_width / 2

            # Calculate offset based on border position
            # PIL draws stroke INSIDE the bounding box (not centered like Qt)
            if border_position == "inside":
                # Stroke entirely inside element - box at element boundary
                bx1, by1 = int(x), int(y)
                bx2, by2 = int(x + width), int(y + height)
                bradius = corner_radius
            elif border_position == "center":
                # Stroke centered on element boundary - expand box by half_border
                bx1, by1 = int(x - half_border), int(y - half_border)
                bx2, by2 = int(x + width + half_border), int(y + height + half_border)
                bradius = int(corner_radius + half_border)
            else:  # outside
                # Stroke entirely outside element - expand box by full border_width
                bx1, by1 = int(x - border_width), int(y - border_width)
                bx2, by2 = int(x + width + border_width), int(y + height + border_width)
                bradius = int(corner_radius + border_width)

            # Draw border (outline only)
            if rounded:
                border_draw.rounded_rectangle(
                    [bx1, by1, bx2, by2],
                    radius=bradius,
                    outline=border_rgb,
                    width=border_width
                )
            else:
                border_draw.rectangle(
                    [bx1, by1, bx2, by2],
                    outline=border_rgb,
                    width=border_width
                )

            # Apply border opacity
            if border_opacity < 100:
                r, g, b, a = border_layer.split()
                a = a.point(lambda px: int(px * border_opacity / 100))
                border_layer = Image.merge('RGBA', (r, g, b, a))

            # Composite border layer onto overlay
            self._fast_alpha_composite(overlay, border_layer)

        # Now use overlay's draw for text (text doesn't need the layer approach)
        draw = ImageDraw.Draw(overlay)

        # Draw text based on bar_text_mode and bar_text_position
        bar_text_mode = getattr(element, 'bar_text_mode', 'full')
        bar_text_position = getattr(element, 'bar_text_position', 'inside')

        if bar_text_mode != 'none':
            value_text = get_value_with_unit(value, element.source, getattr(element, 'temp_hide_unit', False))

            # Value font
            value_font = self.get_pil_font(element, element.font_size)
            # Label font (separate styling)
            label_font = self.get_pil_font_custom(
                getattr(element, 'label_font_family', element.font_family),
                getattr(element, 'label_font_bold', element.font_bold),
                getattr(element, 'label_font_italic', element.font_italic),
                getattr(element, 'label_font_size', element.font_size)
            )

            # Text colors
            value_text_color = getattr(element, 'text_color', element.color)
            value_text_opacity = getattr(element, 'text_color_opacity', 100)
            value_rgba = hex_to_rgba(value_text_color, value_text_opacity)

            label_text_color = getattr(element, 'label_text_color', element.color)
            label_rgba = hex_to_rgba(label_text_color, value_text_opacity)

            if bar_text_position == 'inside':
                if bar_text_mode == 'full':
                    # Draw label and value separately, centered with bar
                    label_text = f"{element.text} "
                    bbox_label = draw.textbbox((0, 0), label_text, font=label_font)
                    label_width = bbox_label[2] - bbox_label[0]

                    bbox_value = draw.textbbox((0, 0), value_text, font=value_font)
                    value_width = bbox_value[2] - bbox_value[0]

                    total_width = label_width + value_width
                    start_x = x + (width - total_width) // 2
                    center_y = y + height // 2

                    draw.text((start_x, center_y), label_text, fill=label_rgba, font=label_font, anchor="lm")
                    draw.text((start_x + label_width, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'value_only':
                    bbox = draw.textbbox((0, 0), value_text, font=value_font)
                    text_width = bbox[2] - bbox[0]
                    text_x = x + (width - text_width) // 2
                    center_y = y + height // 2
                    draw.text((text_x, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'label_only':
                    bbox = draw.textbbox((0, 0), element.text, font=label_font)
                    text_width = bbox[2] - bbox[0]
                    text_x = x + (width - text_width) // 2
                    center_y = y + height // 2
                    draw.text((text_x, center_y), element.text, fill=label_rgba, font=label_font, anchor="lm")

            elif bar_text_position == 'left':
                if bar_text_mode == 'full':
                    # Draw label and value separately, centered with bar
                    label_text = f"{element.text} "
                    bbox_label = draw.textbbox((0, 0), label_text, font=label_font)
                    label_width = bbox_label[2] - bbox_label[0]

                    bbox_value = draw.textbbox((0, 0), value_text, font=value_font)
                    value_width = bbox_value[2] - bbox_value[0]

                    total_width = label_width + value_width
                    start_x = x - total_width - 10
                    center_y = y + height // 2

                    draw.text((start_x, center_y), label_text, fill=label_rgba, font=label_font, anchor="lm")
                    draw.text((start_x + label_width, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'value_only':
                    bbox = draw.textbbox((0, 0), value_text, font=value_font)
                    text_width = bbox[2] - bbox[0]
                    text_x = x - text_width - 10
                    center_y = y + height // 2
                    draw.text((text_x, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'label_only':
                    bbox = draw.textbbox((0, 0), element.text, font=label_font)
                    text_width = bbox[2] - bbox[0]
                    text_x = x - text_width - 10
                    center_y = y + height // 2
                    draw.text((text_x, center_y), element.text, fill=label_rgba, font=label_font, anchor="lm")

            elif bar_text_position == 'right':
                if bar_text_mode == 'full':
                    # Draw label and value separately, centered with bar
                    label_text = f"{element.text} "
                    bbox_label = draw.textbbox((0, 0), label_text, font=label_font)
                    label_width = bbox_label[2] - bbox_label[0]

                    start_x = x + width + 10
                    center_y = y + height // 2

                    draw.text((start_x, center_y), label_text, fill=label_rgba, font=label_font, anchor="lm")
                    draw.text((start_x + label_width, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'value_only':
                    text_x = x + width + 10
                    center_y = y + height // 2
                    draw.text((text_x, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'label_only':
                    text_x = x + width + 10
                    center_y = y + height // 2
                    draw.text((text_x, center_y), element.text, fill=label_rgba, font=label_font, anchor="lm")

            elif bar_text_position == 'top':
                # Label and value inline above bar with 16px padding
                if bar_text_mode == 'full':
                    label_text = f"{element.text} "
                    bbox_label = draw.textbbox((0, 0), label_text, font=label_font)
                    label_width = bbox_label[2] - bbox_label[0]
                    label_height = bbox_label[3] - bbox_label[1]

                    bbox_value = draw.textbbox((0, 0), value_text, font=value_font)
                    value_width = bbox_value[2] - bbox_value[0]
                    value_height = bbox_value[3] - bbox_value[1]

                    total_width = label_width + value_width
                    max_height = max(label_height, value_height)
                    start_x = x + (width - total_width) // 2
                    center_y = y - 16 - max_height // 2

                    draw.text((start_x, center_y), label_text, fill=label_rgba, font=label_font, anchor="lm")
                    draw.text((start_x + label_width, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'value_only':
                    bbox = draw.textbbox((0, 0), value_text, font=value_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x + (width - text_width) // 2
                    center_y = y - 16 - text_height // 2
                    draw.text((text_x, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'label_only':
                    bbox = draw.textbbox((0, 0), element.text, font=label_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x + (width - text_width) // 2
                    center_y = y - 16 - text_height // 2
                    draw.text((text_x, center_y), element.text, fill=label_rgba, font=label_font, anchor="lm")

            elif bar_text_position == 'bottom':
                # Label and value inline below bar with 16px padding
                if bar_text_mode == 'full':
                    label_text = f"{element.text} "
                    bbox_label = draw.textbbox((0, 0), label_text, font=label_font)
                    label_width = bbox_label[2] - bbox_label[0]
                    label_height = bbox_label[3] - bbox_label[1]

                    bbox_value = draw.textbbox((0, 0), value_text, font=value_font)
                    value_width = bbox_value[2] - bbox_value[0]
                    value_height = bbox_value[3] - bbox_value[1]

                    total_width = label_width + value_width
                    max_height = max(label_height, value_height)
                    start_x = x + (width - total_width) // 2
                    center_y = y + height + 16 + max_height // 2

                    draw.text((start_x, center_y), label_text, fill=label_rgba, font=label_font, anchor="lm")
                    draw.text((start_x + label_width, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'value_only':
                    bbox = draw.textbbox((0, 0), value_text, font=value_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x + (width - text_width) // 2
                    center_y = y + height + 16 + text_height // 2
                    draw.text((text_x, center_y), value_text, fill=value_rgba, font=value_font, anchor="lm")
                elif bar_text_mode == 'label_only':
                    bbox = draw.textbbox((0, 0), element.text, font=label_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x + (width - text_width) // 2
                    center_y = y + height + 16 + text_height // 2
                    draw.text((text_x, center_y), element.text, fill=label_rgba, font=label_font, anchor="lm")

        # Composite onto main image
        self._fast_alpha_composite(img, overlay)

    def render_analog_clock_rgba(
        self,
        img,
        element,
        color_opacity,
        bg_opacity,
        cache_key=None,
    ):
        """Render analog clock with opacity support and per-second caching.
        Caches static clock face, only updates hands per frame."""
        import math
        import datetime

        x, y = element.x, element.y
        radius = element.radius
        elem_id = cache_key if cache_key is not None else id(element)

        # Get options
        show_seconds = getattr(element, 'show_seconds_hand', True)
        show_border = getattr(element, 'show_clock_border', True)
        face_style = getattr(element, 'clock_face_style', 'numbers')
        smooth = getattr(element, 'smooth_animation', True)

        # Get current time
        now = datetime.datetime.now()
        hours = now.hour % 12
        minutes = now.minute
        seconds = now.second
        microseconds = now.microsecond
        current_second = seconds  # For cache key

        # Create config hash for cache validation
        config_hash = hash((
            x, y, radius, show_seconds, show_border, face_style, smooth,
            element.color, element.background_color, color_opacity, bg_opacity,
            getattr(element, 'font_size', 14)
        ))

        # Check cache for static clock face (valid for entire second)
        clock_face_overlay = None
        with self._render_cache_lock:
            cached = self._analog_clock_cache.get(elem_id)
        if cached:
            cached_face, cached_second, cached_hash = cached
            if cached_second == current_second and cached_hash == config_hash:
                clock_face_overlay = cached_face.copy()

        # Render static clock face if not cached
        if clock_face_overlay is None:
            clock_face_overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(clock_face_overlay)

            # Get colors
            color_rgba = hex_to_rgba(element.color, color_opacity)
            bg_rgba = hex_to_rgba(element.background_color, bg_opacity)

            # Draw clock face background
            if show_border:
                draw.ellipse(
                    [x - radius, y - radius, x + radius, y + radius],
                    fill=bg_rgba, outline=color_rgba, width=2
                )
            else:
                draw.ellipse(
                    [x - radius, y - radius, x + radius, y + radius],
                    fill=bg_rgba
                )

            # Get font for numbers
            font = self.get_pil_font(element, int(getattr(element, 'font_size', 14) * 0.8))

            # Draw tick marks or numbers
            for i in range(12):
                angle_rad = math.radians(i * 30 - 90)

                if face_style == 'numbers':
                    num = i if i > 0 else 12
                    text = str(num)
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]

                    text_radius = radius * 0.78
                    tx = x + text_radius * math.cos(angle_rad) - text_width / 2
                    ty = y + text_radius * math.sin(angle_rad) - text_height / 2

                    draw.text((tx, ty), text, fill=color_rgba, font=font)

                elif face_style == 'ticks':
                    inner_radius = radius * 0.85
                    outer_radius = radius * 0.95

                    if i % 3 == 0:
                        inner_radius = radius * 0.75
                        tick_width = 3
                    else:
                        tick_width = 1

                    x1 = x + inner_radius * math.cos(angle_rad)
                    y1 = y + inner_radius * math.sin(angle_rad)
                    x2 = x + outer_radius * math.cos(angle_rad)
                    y2 = y + outer_radius * math.sin(angle_rad)

                    draw.line([(x1, y1), (x2, y2)], fill=color_rgba, width=tick_width)

            # Cache the static clock face
            with self._render_cache_lock:
                self._analog_clock_cache[elem_id] = (
                    clock_face_overlay.copy(),
                    current_second,
                    config_hash,
                )

        # Now add dynamic hands on top of cached face
        hands_overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(hands_overlay)
        color_rgba = hex_to_rgba(element.color, color_opacity)

        # Calculate hand angles
        if smooth:
            second_angle = (seconds + microseconds / 1000000) * 6
            minute_angle = (minutes + seconds / 60) * 6
            hour_angle = (hours + minutes / 60) * 30
        else:
            second_angle = seconds * 6
            minute_angle = minutes * 6
            hour_angle = hours * 30 + minutes * 0.5

        # Draw hour hand
        hour_length = radius * 0.5
        hour_rad = math.radians(hour_angle - 90)
        hx = x + hour_length * math.cos(hour_rad)
        hy = y + hour_length * math.sin(hour_rad)
        draw.line([(x, y), (hx, hy)], fill=color_rgba, width=4)

        # Draw minute hand
        minute_length = radius * 0.7
        minute_rad = math.radians(minute_angle - 90)
        mx = x + minute_length * math.cos(minute_rad)
        my = y + minute_length * math.sin(minute_rad)
        draw.line([(x, y), (mx, my)], fill=color_rgba, width=3)

        # Draw second hand (optional)
        if show_seconds:
            second_length = radius * 0.85
            second_rad = math.radians(second_angle - 90)
            sx = x + second_length * math.cos(second_rad)
            sy = y + second_length * math.sin(second_rad)
            # Red second hand
            second_rgba = (255, 80, 80, int(255 * color_opacity / 100))
            draw.line([(x, y), (sx, sy)], fill=second_rgba, width=2)

        # Draw center dot
        center_radius = 4
        draw.ellipse(
            [x - center_radius, y - center_radius, x + center_radius, y + center_radius],
            fill=color_rgba
        )

        # Composite face + hands onto main image
        self._fast_alpha_composite(img, clock_face_overlay)
        self._fast_alpha_composite(img, hands_overlay)
