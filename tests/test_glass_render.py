import unittest
import threading
from types import MethodType, SimpleNamespace

from PIL import Image

from src.core.element import ThemeElement
from src.ui.main_window import ThemeEditorWindow


class TestGlassRender(unittest.TestCase):
    def test_glass_rectangle_tracks_changing_background(self):
        window = SimpleNamespace()
        window._element_render_cache = {}
        window._render_cache_lock = threading.RLock()
        window.get_pil_font = lambda *args, **kwargs: None
        window._compute_element_state_hash = MethodType(ThemeEditorWindow._compute_element_state_hash, window)
        window._fast_alpha_composite = MethodType(ThemeEditorWindow._fast_alpha_composite, window)
        window.render_rectangle_rgba = MethodType(ThemeEditorWindow.render_rectangle_rgba, window)
        window.render_element_with_opacity = MethodType(ThemeEditorWindow.render_element_with_opacity, window)

        element = ThemeElement(
            element_type="rectangle",
            x=10,
            y=10,
            width=40,
            height=40,
            color="#88ccff",
            glass_effect=True,
            glass_blur=8,
            glass_opacity=45,
        )

        background = Image.new("RGBA", (80, 80), "#101020")
        for x in range(80):
            for y in range(80):
                background.putpixel((x, y), ((x * 3) % 255, (y * 5) % 255, 120, 255))

        first = background.copy()
        window.render_element_with_opacity(first, element)

        second = Image.new("RGBA", (80, 80), "#f0d040")
        window.render_element_with_opacity(second, element)

        self.assertNotIn(id(element), window._element_render_cache)
        self.assertNotEqual(first.tobytes(), second.tobytes())


if __name__ == "__main__":
    unittest.main()
