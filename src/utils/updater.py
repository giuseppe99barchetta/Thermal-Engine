"""
Update checker for Thermal Engine.
Checks GitHub Releases for new versions.
"""

import json
import webbrowser
import urllib.request
import urllib.error
import os
import sys
import tempfile
from urllib.parse import urlparse, unquote
from packaging import version as version_parser
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QThread, Signal

try:
    from src.utils.app_version import __version__
except ImportError:
    __version__ = "0.0.0"

GITHUB_REPO = "giuseppe99barchetta/Thermal-Engine"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


def _asset_digest(asset):
    digest = asset.get("digest", "")
    if digest.startswith("sha256:"):
        return digest.split("sha256:", 1)[1]
    return None


def select_release_asset(assets, platform=None):
    """Select best release asset for current platform."""
    platform = platform or sys.platform

    if platform == "win32":
        preferred_suffixes = (".exe", ".zip")
        required_terms = ("setup", "thermalengine")
    elif platform.startswith("linux"):
        preferred_suffixes = (".appimage", ".tar.gz", ".tar.xz", ".zip")
        required_terms = ("thermalengine",)
    elif platform == "darwin":
        preferred_suffixes = (".dmg", ".pkg", ".zip")
        required_terms = ("thermalengine",)
    else:
        preferred_suffixes = (".zip",)
        required_terms = ("thermalengine",)

    normalized_assets = []
    for asset in assets:
        name = asset.get("name", "")
        lowered = name.lower()
        normalized_assets.append((asset, name, lowered))

    for suffix in preferred_suffixes:
        for asset, name, lowered in normalized_assets:
            if not lowered.endswith(suffix):
                continue
            if required_terms and not any(term in lowered for term in required_terms):
                continue
            return name, asset.get("browser_download_url", ""), _asset_digest(asset)

    return "", "", None


def get_download_filename(download_url, fallback_name):
    parsed = urlparse(download_url)
    filename = os.path.basename(unquote(parsed.path))
    return filename or fallback_name


def can_auto_install_asset(asset_name, platform=None):
    platform = platform or sys.platform
    return platform == "win32" and asset_name.lower().endswith(".exe")


class UpdateChecker(QThread):
    """Background thread to check for updates."""

    update_available = Signal(str, str, str, str, str)  # version, download_url, release_notes, expected_hash, asset_name
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

            # Find best asset for this platform
            download_url = GITHUB_RELEASES_URL
            expected_hash = None
            asset_name, selected_url, selected_hash = select_release_asset(data.get('assets', []))
            if selected_url:
                download_url = selected_url
                expected_hash = selected_hash

            # Compare versions
            try:
                current = version_parser.parse(__version__)
                latest = version_parser.parse(latest_version)

                if latest > current:
                    self.update_available.emit(
                        latest_version,
                        download_url,
                        release_notes,
                        expected_hash or "",
                        asset_name,
                    )
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

    def __init__(self, download_url, version, expected_hash=None, asset_name=""):
        super().__init__()
        self.download_url = download_url
        self.version = version
        self.expected_hash = expected_hash
        self.asset_name = asset_name
        self._cancelled = False

    def cancel(self):
        """Cancel the download."""
        self._cancelled = True

    def run(self):
        """Download the installer in background."""
        try:
            # Create temp directory for download
            temp_dir = tempfile.gettempdir()
            installer_filename = get_download_filename(
                self.download_url,
                self.asset_name or f"ThermalEngine-{self.version}.zip",
            )
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

                # Verify hash if expected_hash is provided
                if self.expected_hash:
                    import hashlib
                    hasher = hashlib.sha256()
                    with open(installer_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            hasher.update(chunk)

                    if hasher.hexdigest().lower() != self.expected_hash.lower():
                        if os.path.exists(installer_path):
                            os.remove(installer_path)
                        self.error.emit("Security error: Downloaded file failed integrity check. The file may have been tampered with.")
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

    def on_update_available(version, download_url, release_notes, expected_hash=None, asset_name=""):
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
        button_text = "Download Update" if asset_name else "Open Releases"
        download_btn = msg_box.addButton(button_text, QMessageBox.ButtonRole.AcceptRole)
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
