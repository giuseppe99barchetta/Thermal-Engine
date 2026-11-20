"""Game FPS and frametime from Intel PresentMon (the bundled console exe, Windows only).

PresentMon traces DXGI/D3D presents through ETW, which needs administrator rights
(or membership of "Performance Log Users"). It only runs while a theme uses a game_* source.
"""
import collections
import csv
import logging
import os
import subprocess
import threading
import time

from src.utils.app_path import get_bundled_resource_path

logger = logging.getLogger(__name__)

SESSION = "ThermalEngineFPS"
WINDOW = 1.0  # seconds of frames averaged into one reading
IGNORED = ("dwm.exe", "thermalengine.exe", "presentmon.exe")  # compositor and ourselves
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_presentmon():
    """Bundled exe in a frozen build; build/deps/ (where the build scripts download it) from source."""
    for relative in (("presentmon", "PresentMon.exe"), ("build", "deps", "PresentMon.exe")):
        path = get_bundled_resource_path(os.path.join(*relative))
        if os.path.isfile(path):
            return path
    return None


class GameFpsMonitor:
    def __init__(self, executable):
        self.executable = executable
        self.status = "Starting"
        self._frames = collections.deque()  # (monotonic time, application, ms between presents)
        self._lock = threading.Lock()
        self._process = None
        self._thread = None

    def start(self):
        args = [self.executable, "--output_stdout", "--no_console_stats", "--no_track_gpu",
                "--no_track_input", "--no_track_display", "--session_name", SESSION, "--stop_existing_session"]
        for name in IGNORED:
            args += ["--exclude", name]
        try:
            self._process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                             stdin=subprocess.DEVNULL, text=True, errors="replace",
                                             creationflags=NO_WINDOW)
        except OSError as exc:
            self.status = f"PresentMon could not start: {exc}"
            return
        self.status = "Waiting for a game"
        self._thread = threading.Thread(target=self._read, args=(self._process,), daemon=True, name="presentmon")
        self._thread.start()

    def _read(self, process):
        self.consume(process.stdout)
        code = process.wait()
        if self._process is process:  # not stopped by us
            self.status = ("PresentMon needs administrator rights: restart Thermal Engine as Administrator"
                           if code else "PresentMon stopped")

    def consume(self, lines):
        """Parse PresentMon CSV rows; anything before the header (or malformed) is skipped."""
        columns = None
        for row in csv.reader(lines):
            if columns is None:
                names = [name.strip().lower() for name in row]
                if "application" in names:  # header; 2.x default writes MsBetweenPresents, --v1_metrics msBetweenPresents
                    if "msbetweenpresents" not in names:
                        self.status = "Unsupported PresentMon output (no MsBetweenPresents column)"
                        return
                    columns = names.index("application"), names.index("msbetweenpresents")
                continue
            try:
                application, ms = row[columns[0]], float(row[columns[1]])
            except (IndexError, ValueError):  # "NA" or a truncated line
                continue
            if 0 < ms < 1000:
                self._add(application.lower(), ms)

    def _add(self, application, ms, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            self._frames.append((now, application, ms))
            self._prune(now)
        self.status = "Receiving"

    def _prune(self, now):
        while self._frames and now - self._frames[0][0] > WINDOW:
            self._frames.popleft()

    def snapshot(self, now=None):
        """FPS of the application presenting the most frames in the last second (the game, normally)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._prune(now)
            per_app = collections.defaultdict(list)
            for _, application, ms in self._frames:
                per_app[application].append(ms)
        if not per_app:
            return {}
        frame_times = max(per_app.values(), key=len)
        frametime = sum(frame_times) / len(frame_times)
        return {"game_fps": 1000 / frametime, "game_frametime": frametime}

    def stop(self):
        process, self._process = self._process, None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if process:
            # A killed PresentMon can leave its ETW session running; close it by name
            try:
                subprocess.run([self.executable, "--terminate_existing_session", "--session_name", SESSION],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                               timeout=5, creationflags=NO_WINDOW, check=False)
            except (OSError, subprocess.TimeoutExpired):
                logger.warning("Could not close the PresentMon trace session")
        if self._thread:
            self._thread.join(timeout=3)
        self.status = "Stopped"
