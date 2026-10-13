import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock

from src.core.device_backends import DeviceIOError
from src.ui.main_window import ThemeEditorWindow


def _window_with_pending_error(error):
    window = SimpleNamespace(
        device=object(),
        _frame_error=error,
        disconnect_display=MagicMock(),
        _start_reconnect_timer=MagicMock(),
        status_bar=MagicMock(),
    )
    window.send = MethodType(ThemeEditorWindow.send_frame_with_sensors, window)
    return window


class TestFrameErrors(unittest.TestCase):
    def test_device_error_disconnects_and_schedules_reconnect(self):
        window = _window_with_pending_error(DeviceIOError("Short USB write"))
        window.send()
        window.disconnect_display.assert_called_once()
        window._start_reconnect_timer.assert_called_once()

    def test_render_error_keeps_device_connected(self):
        # A missing image file is an OSError too, but must not drop the display.
        window = _window_with_pending_error(FileNotFoundError("logo.png"))
        window.send()
        window.disconnect_display.assert_not_called()


if __name__ == "__main__":
    unittest.main()
