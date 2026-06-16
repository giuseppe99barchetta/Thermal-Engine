import unittest

from PIL import Image

from src.core.element import ThemeElement
from src.ui.main_window import ThemeEditorWindow


class TestGlassRender(unittest.TestCase):
    def test_glass_rectangle_cache_preserves_display_render(self):
        window = object.__new__(ThemeEditorWindow)
        window._element_render_cache = {}
        window.get_pil_font = lambda *args, **kwargs: None
        window._compute_element_state_hash = ThemeEditorWindow._compute_element_state_hash.__get__(window, ThemeEditorWindow)
        window._fast_alpha_composite = ThemeEditorWindow._fast_alpha_composite.__get__(window, ThemeEditorWindow)
        window.render_rectangle_rgba = ThemeEditorWindow.render_rectangle_rgba.__get__(window, ThemeEditorWindow)
        window.render_element_with_opacity = ThemeEditorWindow.render_element_with_opacity.__get__(window, ThemeEditorWindow)

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
        cached_overlay, _, _ = window._element_render_cache[id(element)]

        second = background.copy()
        window.render_element_with_opacity(second, element)

        self.assertIsNotNone(cached_overlay.getbbox())
        self.assertEqual(first.tobytes(), second.tobytes())


if __name__ == "__main__":
    unittest.main()
