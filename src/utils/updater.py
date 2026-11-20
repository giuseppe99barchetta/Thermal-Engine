"""
Update checker for Thermal Engine.
Checks GitHub Releases for new versions.
"""

import json
import urllib.request
import urllib.error
import os
import shutil
import sys
import tempfile
from urllib.parse import urlparse, unquote
from packaging import version as version_parser
try:
    from PySide6.QtCore import QThread, Signal
except ImportError:  # pragma: no cover - test fallback
    class Signal:
        def __init__(self, *args, **kwargs):
            self._subscribers = []

        def connect(self, callback):
            self._subscribers.append(callback)

        def emit(self, *args, **kwargs):
            for callback in self._subscribers:
                callback(*args, **kwargs)

    class QThread:
        def start(self):
            self.run()

try:
    from src.utils.app_version import __version__
except ImportError:
    __version__ = "0.0.0"

from src.utils import settings

GITHUB_REPO = "giuseppe99barchetta/Thermal-Engine"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


TRUSTED_DOWNLOAD_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")


def is_trusted_download_url(url):
    """Only this repo's GitHub release assets (and GitHub's asset CDN, reached by redirect) may be auto-installed."""
    parsed = urlparse(url or "")
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED_DOWNLOAD_HOSTS:
        return False
    return parsed.hostname != "github.com" or parsed.path.startswith(f"/{GITHUB_REPO}/releases/download/")


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


def can_auto_install_asset(asset_name, platform=None, expected_hash=None):
    platform = platform or sys.platform
    asset_name = (asset_name or "").lower()
    if platform == "win32":
        return asset_name.endswith(".exe") and bool(expected_hash)
    if platform.startswith("linux"):
        return asset_name.endswith(".appimage") and bool(expected_hash)
    return False


def get_linux_appimage_target_path(asset_name=""):
    current_appimage = os.environ.get("APPIMAGE")
    if current_appimage:
        return current_appimage

    if getattr(sys, "frozen", False) and sys.executable.lower().endswith(".appimage"):
        return sys.executable

    filename = asset_name or "ThermalEngine.AppImage"
    return os.path.expanduser(os.path.join("~", ".local", "bin", filename))


def install_downloaded_update(installer_path, asset_name, platform=None):
    platform = platform or sys.platform
    lowered = (asset_name or "").lower()

    if platform == "win32" and lowered.endswith(".exe"):
        os.startfile(installer_path)  # ShellExecute: shows the UAC prompt the installer needs; returns at once
        return {"action": "launch-installer", "path": installer_path}

    if platform.startswith("linux") and lowered.endswith(".appimage"):
        target_path = get_linux_appimage_target_path(asset_name)
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)

        shutil.move(installer_path, target_path)
        os.chmod(target_path, 0o755)

        if settings.is_autostart_enabled():
            settings.set_autostart(True)

        return {"action": "replace-appimage", "path": target_path}

    raise ValueError(f"Unsupported auto-install asset: {asset_name}")


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
            if not is_trusted_download_url(self.download_url):
                self.error.emit("Security error: the update is not hosted on the official GitHub releases.")
                return
            # Private random directory: a predictable path in %TEMP% could be swapped between verification and launch
            temp_dir = tempfile.mkdtemp(prefix="thermal-engine-update-")
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
                reported = -1  # last percent (or MiB when the size is unknown) sent to the UI

                with open(installer_path, 'wb') as f:
                    while not self._cancelled:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        # One signal per percent, not per 8 KB chunk: each one repaints the UI
                        step = downloaded * 100 // total_size if total_size else downloaded >> 20
                        if step != reported:
                            reported = step
                            self.progress.emit(downloaded, total_size)

                if self._cancelled:
                    # Clean up partial download
                    if os.path.exists(installer_path):
                        os.remove(installer_path)
                    return

                if self.asset_name.lower().endswith((".exe", ".appimage")) and not self.expected_hash:
                    os.remove(installer_path)
                    self.error.emit("Security error: the release does not provide a SHA-256 digest.")
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

