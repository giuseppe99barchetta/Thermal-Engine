"""
Update checker for Thermal Engine.
Checks GitHub Releases for new versions.
"""

import json
import webbrowser
import urllib.request
import urllib.error
import os
import tempfile
import subprocess
from packaging import version as version_parser
from PySide6.QtWidgets import QMessageBox, QPushButton, QProgressDialog
from PySide6.QtCore import QThread, Signal, Qt

try:
    from app_version import __version__
except ImportError:
    __version__ = "0.0.0"

GITHUB_REPO = "giuseppe99barchetta/Thermal-Engine"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


class UpdateChecker(QThread):
    """Background thread to check for updates."""

    update_available = Signal(str, str, str)  # version, download_url, release_notes
    no_update = Signal()
    error = Signal(str)

    def run(self):
        """Check for updates in background."""
        try:
            # Request latest release info from GitHub API
            request = urllib.request.Request(
                GITHUB_API_URL,
                headers={'User-Agent': 'ThermalEngine-UpdateChecker'}
            )

            # Fetch data with 10 second timeout
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            latest_version = data.get('tag_name', '').lstrip('v')
            release_notes = data.get('body', 'No release notes available.')

            # Find the installer asset
            download_url = GITHUB_RELEASES_URL
            for asset in data.get('assets', []):
                if 'Setup.exe' in asset.get('name', ''):
                    download_url = asset.get('browser_download_url', GITHUB_RELEASES_URL)
                    break

            # Compare versions
            try:
                current = version_parser.parse(__version__)
                latest = version_parser.parse(latest_version)

                if latest > current:
                    self.update_available.emit(latest_version, download_url, release_notes)
                else:
                    self.no_update.emit()
            except Exception as e:
                self.error.emit(f"Version comparison failed: {e}")

        except urllib.error.URLError as e:
            self.error.emit(f"Network error: {e.reason}")
        except Exception as e:
            self.error.emit(f"Failed to check for updates: {e}")


class UpdateDownloader(QThread):
    """Background thread to download installer."""

    progress = Signal(int, int)  # downloaded_bytes, total_bytes
    finished = Signal(str)  # installer_path
    error = Signal(str)

    def __init__(self, download_url, version):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self._cancelled = False

    def cancel(self):
        """Cancel the download."""
        self._cancelled = True

    def run(self):
        """Download the installer in background."""
        try:
            # Create temp directory for download
            temp_dir = tempfile.gettempdir()
            installer_filename = f"ThermalEngine-{self.version}-Setup.exe"
            installer_path = os.path.join(temp_dir, installer_filename)

            # Download with progress reporting
            request = urllib.request.Request(
                self.download_url,
                headers={'User-Agent': 'ThermalEngine-UpdateChecker'}
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(installer_path, 'wb') as f:
                    while not self._cancelled:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)

                if self._cancelled:
                    # Clean up partial download
                    if os.path.exists(installer_path):
                        os.remove(installer_path)
                    return

                self.finished.emit(installer_path)

        except urllib.error.URLError as e:
            self.error.emit(f"Download failed: {e.reason}")
        except Exception as e:
            self.error.emit(f"Download failed: {e}")


def check_for_updates(parent=None, silent=False):
    """
    Check for updates and show dialog if available.

    Args:
        parent: Parent widget for dialogs
        silent: If True, only show dialog if update is available
    """
    checker = UpdateChecker()

    def on_update_available(version, download_url, release_notes):
        # Create custom message box with download button
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle("Update Available")
        msg_box.setIcon(QMessageBox.Icon.Information)

        # Truncate release notes if too long
        notes = release_notes[:500] + "..." if len(release_notes) > 500 else release_notes

        msg_box.setText(f"A new version of Thermal Engine is available!")
        msg_box.setInformativeText(
            f"Current version: {__version__}\n"
            f"Latest version: {version}\n\n"
            f"Release notes:\n{notes}"
        )

        # Add custom buttons
        download_btn = msg_box.addButton("Download Update", QMessageBox.ButtonRole.AcceptRole)
        later_btn = msg_box.addButton("Later", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == download_btn:
            webbrowser.open(download_url)

    def on_no_update():
        if not silent:
            QMessageBox.information(
                parent,
                "No Updates",
                f"You are running the latest version ({__version__})."
            )

    def on_error(error_msg):
        if not silent:
            QMessageBox.warning(
                parent,
                "Update Check Failed",
                f"Could not check for updates:\n{error_msg}"
            )

    checker.update_available.connect(on_update_available)
    checker.no_update.connect(on_no_update)
    checker.error.connect(on_error)

    checker.start()

    return checker
