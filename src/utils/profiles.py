"""
Auto Profiles for Thermal Engine.
Monitor foreground application and auto-switch presets.
"""

import os
import sys
import time
import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QCheckBox,
    QHeaderView, QMessageBox, QDialogButtonBox, QAbstractItemView
)

from src.utils.settings import get_setting, set_setting

logger = logging.getLogger(__name__)

# Windows API imports
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _get_foreground_app():
    """Get the foreground window's process name and title using Win32 API."""
    if sys.platform != 'win32':
        return "", ""

    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", ""

        # Window title
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        window_title = buf.value

        # Process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Process name from PID
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return "", window_title

        try:
            buf_size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            success = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(buf_size))
            if success:
                return os.path.basename(buf.value).lower(), window_title
        finally:
            kernel32.CloseHandle(handle)

        return "", window_title

    except Exception as e:
        logger.debug(f"GetForegroundApp error: {e}")
        return "", ""


class ForegroundAppMonitor(QThread):
    """Polls the foreground window and emits signals on app changes."""

    app_changed = Signal(str, str)  # (process_name, window_title)

    def __init__(self, poll_interval_ms=2500):
        super().__init__()
        self.poll_interval_ms = poll_interval_ms
        self._running = True
        self._last_process = ""

    def stop(self):
        self._running = False
        self.wait(5000)

    def run(self):
        while self._running:
            try:
                process_name, window_title = _get_foreground_app()
                if process_name and process_name != self._last_process:
                    self._last_process = process_name
                    self.app_changed.emit(process_name, window_title)
            except Exception as e:
                logger.error(f"Foreground monitor error: {e}")

            self.msleep(self.poll_interval_ms)


class ProfileManager:
    """Manages profile rules and matching logic."""

    def __init__(self):
        self._profiles = []
        self._enabled = False
        self._cooldown_until = 0
        self._active_profile = None
        self._default_preset = None
        self.load_profiles()

    def load_profiles(self):
        self._profiles = get_setting("profiles", [])
        self._enabled = get_setting("profiles_enabled", False)
        self._default_preset = get_setting("profiles_default_preset", None)

    def save_profiles(self):
        set_setting("profiles", self._profiles)
        set_setting("profiles_enabled", self._enabled)
        set_setting("profiles_default_preset", self._default_preset)

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value
        self.save_profiles()

    @property
    def profiles(self):
        return self._profiles

    @property
    def default_preset(self):
        return self._default_preset

    @default_preset.setter
    def default_preset(self, value):
        self._default_preset = value
        self.save_profiles()

    @property
    def active_profile_name(self):
        return self._active_profile

    def add_profile(self, app_name, preset_name, match_mode="process"):
        self._profiles.append({
            "app_name": app_name.lower(),
            "preset_name": preset_name,
            "match_mode": match_mode
        })
        self.save_profiles()

    def remove_profile(self, index):
        if 0 <= index < len(self._profiles):
            self._profiles.pop(index)
            self.save_profiles()

    def suppress_auto_switch(self, seconds=30):
        """Suppress auto-switching for N seconds after manual interaction."""
        self._cooldown_until = time.time() + seconds

    def match_app(self, process_name, window_title):
        """
        Check if foreground app matches any profile.

        Returns preset_name if matched, default_preset if no match, or None.
        """
        if not self._enabled:
            return None

        if time.time() < self._cooldown_until:
            return None

        process_name = process_name.lower()

        for profile in self._profiles:
            match_mode = profile.get("match_mode", "process")
            target = profile["app_name"].lower()

            if match_mode == "process" and target in process_name:
                self._active_profile = profile["app_name"]
                return profile["preset_name"]
            elif match_mode == "title" and target in window_title.lower():
                self._active_profile = profile["app_name"]
                return profile["preset_name"]

        # No match — return default
        self._active_profile = None
        return self._default_preset


class ProfileDialog(QDialog):
    """Dialog for managing auto-switch profiles."""

    def __init__(self, profile_manager, available_presets, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.available_presets = sorted(available_presets)

        self.setWindowTitle("Auto Profiles")
        self.setMinimumSize(550, 400)
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Enable toggle
        self.enable_cb = QCheckBox("Enable auto profile switching")
        self.enable_cb.setChecked(self.profile_manager.enabled)
        layout.addWidget(self.enable_cb)

        layout.addSpacing(5)

        # Default preset
        default_layout = QHBoxLayout()
        default_layout.addWidget(QLabel("Default preset (when no app matches):"))
        self.default_combo = QComboBox()
        self.default_combo.addItem("(None)", None)
        for name in self.available_presets:
            self.default_combo.addItem(name, name)
        current_default = self.profile_manager.default_preset
        if current_default:
            idx = self.default_combo.findData(current_default)
            if idx >= 0:
                self.default_combo.setCurrentIndex(idx)
        default_layout.addWidget(self.default_combo, 1)
        layout.addLayout(default_layout)

        layout.addSpacing(10)

        # Profile table
        layout.addWidget(QLabel("Profile Rules:"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Application", "Preset", "Match By"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add Rule")
        add_btn.clicked.connect(self._add_empty_row)
        btn_layout.addWidget(add_btn)

        detect_btn = QPushButton("Detect Current App")
        detect_btn.setToolTip("Switch to the target app, then click this within 5 seconds")
        detect_btn.clicked.connect(self._detect_current_app)
        btn_layout.addWidget(detect_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(remove_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_changes)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_table(self):
        self.table.setRowCount(0)
        for profile in self.profile_manager.profiles:
            self._add_row(
                profile.get("app_name", ""),
                profile.get("preset_name", ""),
                profile.get("match_mode", "process")
            )

    def _add_row(self, app_name="", preset_name="", match_mode="process"):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(app_name))

        preset_combo = QComboBox()
        for name in self.available_presets:
            preset_combo.addItem(name)
        if preset_name:
            idx = preset_combo.findText(preset_name)
            if idx >= 0:
                preset_combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 1, preset_combo)

        mode_combo = QComboBox()
        mode_combo.addItem("Process Name", "process")
        mode_combo.addItem("Window Title", "title")
        idx = mode_combo.findData(match_mode)
        if idx >= 0:
            mode_combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 2, mode_combo)

    def _add_empty_row(self):
        self._add_row()

    def _remove_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _detect_current_app(self):
        process_name, window_title = _get_foreground_app()
        if process_name and "thermalengine" not in process_name.lower():
            self._add_row(app_name=process_name)
        else:
            QMessageBox.information(
                self, "Detection",
                "Switch to the target application first, then click Detect Current App."
            )

    def _accept_changes(self):
        new_profiles = []
        for row in range(self.table.rowCount()):
            app_item = self.table.item(row, 0)
            app_name = app_item.text().strip() if app_item else ""

            preset_combo = self.table.cellWidget(row, 1)
            preset_name = preset_combo.currentText() if preset_combo else ""

            mode_combo = self.table.cellWidget(row, 2)
            match_mode = mode_combo.currentData() if mode_combo else "process"

            if app_name and preset_name:
                new_profiles.append({
                    "app_name": app_name.lower(),
                    "preset_name": preset_name,
                    "match_mode": match_mode
                })

        self.profile_manager._profiles = new_profiles
        self.profile_manager.enabled = self.enable_cb.isChecked()
        self.profile_manager.default_preset = self.default_combo.currentData()
        self.profile_manager.save_profiles()
        self.accept()
