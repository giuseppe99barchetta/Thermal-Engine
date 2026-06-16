import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


class TestLinuxAppPath(unittest.TestCase):
    def test_frozen_linux_user_data_uses_xdg_data_home(self):
        app_path = importlib.import_module("src.utils.app_path")

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(app_path.sys, "platform", "linux"):
                with patch.object(app_path.sys, "frozen", True, create=True):
                    with patch.dict(app_path.os.environ, {"XDG_DATA_HOME": temp_dir}, clear=False):
                        user_dir = app_path.get_user_data_dir()
                        self.assertEqual(user_dir, os.path.join(temp_dir, "ThermalEngine"))
                        self.assertTrue(os.path.isdir(user_dir))


class TestLinuxAutostart(unittest.TestCase):
    def test_linux_autostart_writes_desktop_entry(self):
        if "src.utils.settings" in sys.modules:
            del sys.modules["src.utils.settings"]

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = os.path.join(temp_dir, "settings.json")

            def fake_user_data_path(relative_path):
                return settings_path

            with patch("src.utils.app_path.get_user_data_path", side_effect=fake_user_data_path):
                with patch("sys.platform", "linux"):
                    with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                        settings = importlib.import_module("src.utils.settings")
                        importlib.reload(settings)
                        settings.set_setting("launch_minimized", True)
                        self.assertTrue(settings.set_autostart(True))

                        desktop_file = os.path.join(temp_dir, "autostart", "ThermalEngine.desktop")
                        self.assertTrue(os.path.exists(desktop_file))

                        with open(desktop_file, "r", encoding="utf-8") as f:
                            content = f.read()

                        self.assertIn("[Desktop Entry]", content)
                        self.assertIn("Exec=", content)
                        self.assertIn("--minimized", content)
                        self.assertTrue(settings.is_autostart_enabled())

                        self.assertTrue(settings.set_autostart(False))
                        self.assertFalse(os.path.exists(desktop_file))

    def test_linux_frozen_appimage_uses_appimage_path(self):
        if "src.utils.settings" in sys.modules:
            del sys.modules["src.utils.settings"]

        with patch("sys.platform", "linux"):
            with patch.dict(os.environ, {"APPIMAGE": "/tmp/ThermalEngine.AppImage"}, clear=False):
                settings = importlib.import_module("src.utils.settings")
                importlib.reload(settings)
                with patch.object(settings.sys, "frozen", True, create=True):
                    self.assertEqual(settings.get_executable_path(), "/tmp/ThermalEngine.AppImage")


class TestUpdaterAssetSelection(unittest.TestCase):
    def test_linux_prefers_linux_asset(self):
        updater = importlib.import_module("src.utils.updater")
        assets = [
            {"name": "ThermalEngine-1.0.0-Setup.exe", "browser_download_url": "https://example/exe"},
            {"name": "ThermalEngine-1.0.0.AppImage", "browser_download_url": "https://example/appimage", "digest": "sha256:abc"},
            {"name": "ThermalEngine-1.0.0.zip", "browser_download_url": "https://example/zip"},
        ]

        asset_name, download_url, expected_hash = updater.select_release_asset(assets, platform="linux")

        self.assertEqual(asset_name, "ThermalEngine-1.0.0.AppImage")
        self.assertEqual(download_url, "https://example/appimage")
        self.assertEqual(expected_hash, "abc")

    def test_windows_prefers_setup_exe(self):
        updater = importlib.import_module("src.utils.updater")
        assets = [
            {"name": "ThermalEngine-1.0.0.zip", "browser_download_url": "https://example/zip"},
            {"name": "ThermalEngine-1.0.0-Setup.exe", "browser_download_url": "https://example/exe"},
        ]

        asset_name, download_url, expected_hash = updater.select_release_asset(assets, platform="win32")

        self.assertEqual(asset_name, "ThermalEngine-1.0.0-Setup.exe")
        self.assertEqual(download_url, "https://example/exe")
        self.assertIsNone(expected_hash)

    def test_linux_appimage_can_auto_install(self):
        updater = importlib.import_module("src.utils.updater")
        self.assertTrue(updater.can_auto_install_asset("ThermalEngine-1.0.0.AppImage", platform="linux"))

    def test_linux_install_downloaded_update_moves_appimage(self):
        updater = importlib.import_module("src.utils.updater")

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "download.AppImage")
            target_path = os.path.join(temp_dir, "installed.AppImage")
            with open(source_path, "wb") as f:
                f.write(b"appimage")

            with patch.object(updater, "get_linux_appimage_target_path", return_value=target_path):
                with patch.object(updater.settings, "is_autostart_enabled", return_value=False):
                    result = updater.install_downloaded_update(
                        source_path,
                        "ThermalEngine-1.0.0.AppImage",
                        platform="linux",
                    )

            self.assertEqual(result["action"], "replace-appimage")
            self.assertEqual(result["path"], target_path)
            self.assertTrue(os.path.exists(target_path))
            self.assertFalse(os.path.exists(source_path))


if __name__ == "__main__":
    unittest.main()
