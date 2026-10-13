import unittest

from PIL import Image

from src.core.element import ThemeElement
from src.core.renderer import ThemeRenderer


class TestGlassRender(unittest.TestCase):
    def test_glass_rectangle_tracks_changing_background(self):
        window = ThemeRenderer()

        element = ThemeElement(
            element_type="rectangle",
            x=10,
            y=10,
            width=40,
            height=40,
            color="#88ccff",
            glass_effect=True,
            glass_blur=8,
            glass_opacity=0,
        )

        background = Image.new("RGBA", (80, 80), "#101020")
        for x in range(80):
            for y in range(80):
                value = 255 if (x + y) % 2 else 0
                background.putpixel((x, y), (value, value, value, 255))

        first = background.copy()
        window.render_element_with_opacity(first, element)

        second = Image.new("RGBA", (80, 80), "#f0d040")
        window.render_element_with_opacity(second, element)

        self.assertNotIn(id(element), window._element_render_cache)
        self.assertNotEqual(first.getpixel((30, 30)), background.getpixel((30, 30)))
        self.assertNotEqual(first.tobytes(), second.tobytes())


if __name__ == "__main__":
    unittest.main()
