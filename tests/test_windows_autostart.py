import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from src.utils import settings


class TestWindowsAutostart(unittest.TestCase):
    @patch.object(settings, "_remove_legacy_windows_autostart")
    @patch.object(settings, "get_setting", return_value=True)
    @patch.object(settings, "get_executable_path", return_value='"C:\\Program Files\\ThermalEngine\\ThermalEngine.exe"')
    @patch.object(settings.subprocess, "run", return_value=CompletedProcess([], 0))
    def test_elevated_task_starts_minimized(self, run, executable, minimized, remove_legacy):
        self.assertTrue(settings._configure_windows_autostart_task(True))
        self.assertEqual(
            run.call_args.args[0],
            [
                "schtasks.exe", "/create", "/tn", settings.WINDOWS_AUTOSTART_TASK_NAME,
                "/tr", '"C:\\Program Files\\ThermalEngine\\ThermalEngine.exe" --minimized',
                "/sc", "onlogon", "/rl", "highest", "/it", "/f",
            ],
        )
        remove_legacy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
