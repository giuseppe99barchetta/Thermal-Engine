import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from src.core.element import ThemeElement
from src.ui.canvas import CanvasPreview


class TestCanvasPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hit_test_returns_global_index_for_current_page(self):
        # Same spot on two pages: page-2 element must report its global index.
        on_page_1 = ThemeElement("rectangle", x=0, y=0, width=100, height=100, page=1)
        on_page_2 = ThemeElement("rectangle", x=0, y=0, width=100, height=100, page=2)
        canvas = CanvasPreview()
        canvas.set_elements([on_page_1, on_page_2], page=2)

        self.assertEqual(canvas.visible_indices(), [1])
        self.assertEqual(canvas.get_element_at(QPointF(10, 10)), 1)

        canvas.set_elements([on_page_1, on_page_2], page=1)
        self.assertEqual(canvas.get_element_at(QPointF(10, 10)), 0)

    def test_drag_snaps_to_neighbor_edge(self):
        anchor = ThemeElement("rectangle", x=0, y=300, width=100, height=40)
        moving = ThemeElement("rectangle", x=400, y=331, width=50, height=50)
        canvas = CanvasPreview()
        canvas.set_elements([anchor, moving])
        canvas.set_zoom(1.0)
        canvas.selected_indices = [1]
        canvas.drag_start_positions = {1: (400, 331)}

        # Dragging 297px left puts the left edge at 103, 3px from the anchor's right edge (100)
        dx, dy, guides = canvas._snap_to_guides(-297, 0)
        self.assertEqual(dx, -300)
        self.assertIn(("v", 100), guides)
        # Nothing to align with vertically within reach: y is untouched
        self.assertEqual(dy, 0)


if __name__ == "__main__":
    unittest.main()
