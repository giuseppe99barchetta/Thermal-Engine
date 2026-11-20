import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import patch

from src.core.frame_pipeline import FramePipeline
from src.core.element import ThemeElement


def _run(calls_per_second, seconds=0.5):
    window = SimpleNamespace()
    animate = MethodType(FramePipeline._animated_value, window)
    gauge = ThemeElement("circle_gauge", animate_gauge=True, animation_speed=0.05)
    clock = [0.0]
    with patch("src.core.frame_pipeline.time.perf_counter", lambda: clock[0]):
        animate(gauge, 0.0)
        value = 0.0
        for _ in range(int(seconds * calls_per_second)):
            clock[0] += 1 / calls_per_second
            value = animate(gauge, 100.0)
    return value


class TestGaugeAnimation(unittest.TestCase):
    def test_speed_does_not_depend_on_call_rate(self):
        # Preview (10 Hz) and device loop (60 Hz) must show the same motion.
        self.assertAlmostEqual(_run(10), _run(60), delta=2.0)

    def test_reaches_target(self):
        self.assertEqual(_run(30, seconds=5), 100.0)

    def test_new_element_starts_at_its_own_target(self):
        animate = MethodType(FramePipeline._animated_value, SimpleNamespace())
        old = ThemeElement("circle_gauge", animate_gauge=True)
        animate(old, 20.0)
        fresh = ThemeElement("circle_gauge", animate_gauge=True)
        self.assertEqual(animate(fresh, 80.0), 80.0)
        self.assertNotIn("_animation", old.to_dict())


if __name__ == "__main__":
    unittest.main()
