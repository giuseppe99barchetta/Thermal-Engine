"""
Thermal Engine
A visual theme editor for LCD displays.

Entry point for the application.
"""

import sys
import os
import io

# Fix for PyInstaller --windowed mode where stdout/stderr are None
# This prevents AttributeError when logging tries to write to None streams
# Use UTF-8 encoding to support Unicode characters (like checkmarks ✓)
if sys.stdout is None:
    sys.stdout = io.open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = io.open(os.devnull, 'w', encoding='utf-8')

import argparse
import atexit
import signal
import webbrowser

from PySide6.QtWidgets import (
    QApplication, QMessageBox, QSystemTrayIcon, QMenu,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush, QFont
from PySide6.QtCore import Qt, QSharedMemory

from src.core.sensors import init_sensors, HAS_LHM
from src.ui.main_window import ThemeEditorWindow
from src.utils.app_path import get_app_dir


class SensorSetupDialog(QDialog):
    """Dialog shown when safe sensor monitoring is unavailable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sensor Setup Required")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title
        title = QLabel("Sensor Data Unavailable")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Explanation
        explanation = QLabel(
            "ThermalEngine could not read user-mode sensor data.\n"
            "Low-level driver-based monitoring is disabled to avoid\n"
            "Windows Defender vulnerable-driver blocks."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        # Download button
        instructions_title = QLabel("Available safe data:")
        instructions_title.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(instructions_title)

        instructions = QLabel(
            "1. CPU utilization, RAM, and network via psutil\n"
            "2. GPU utilization via Windows Performance Counters when available\n"
            "3. Temperature, power, and clocks stay 0 if no safe vendor API exists"
        )
        instructions.setStyleSheet("margin-left: 20px;")
        layout.addWidget(instructions)

        # Tip
        tip = QLabel("Tip: Keep Windows and GPU drivers updated for best counter support.")
        tip.setStyleSheet("color: #888; font-style: italic; margin-top: 10px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # Buttons
        button_layout = QHBoxLayout()

        check_again_btn = QPushButton("Check Again")
        check_again_btn.clicked.connect(self.check_again)
        button_layout.addWidget(check_again_btn)

        continue_btn = QPushButton("Continue Without Sensors")
        continue_btn.clicked.connect(self.accept)
        button_layout.addWidget(continue_btn)

        layout.addLayout(button_layout)

    def open_download_page(self):
        """Open Windows performance counter help page in browser."""
        webbrowser.open("https://learn.microsoft.com/windows/win32/perfctrs/performance-counters-portal")

    def check_again(self):
        """Re-check if safe sensors are now available."""
        from src.core.libre_hw_monitor import is_hwinfo_available

        if is_hwinfo_available():
            QMessageBox.information(
                self,
                "Sensors Detected",
                "Safe sensor data is now available."
            )
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Sensors Not Available",
                "Safe user-mode sensors are not available right now."
            )


def create_tray_icon():
    """Create tray icon from file or generate one."""
    # Try to load icon from file
    icon_path = os.path.join(get_app_dir(), 'icon.ico')
    if os.path.exists(icon_path):
        return QIcon(icon_path)

    # Fallback: generate icon programmatically
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(0, 200, 255)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.setBrush(QBrush(QColor(45, 45, 50)))
    painter.drawEllipse(6, 6, 20, 20)
    painter.setBrush(QBrush(QColor(0, 255, 150)))
    painter.drawPie(6, 6, 20, 20, 90 * 16, -200 * 16)
    painter.end()
    return QIcon(pixmap)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Thermal Engine')
    parser.add_argument('--minimized', action='store_true', help='Start minimized to system tray')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running when minimized to tray

    # Single instance check - prevent multiple instances from running
    shared_memory = QSharedMemory("ThermalEngineInstanceLock")
    # Clean up stale shared memory from a previous crash/forced shutdown
    if shared_memory.attach():
        shared_memory.detach()
    if not shared_memory.create(1):
        # Another instance is already running
        QMessageBox.warning(
            None,
            "Already Running",
            "Thermal Engine is already running.\n\n"
            "Check the system tray or minimize the existing window."
        )
        sys.exit(0)

    # Keep shared memory alive for the lifetime of the application
    app.shared_memory = shared_memory

    # Apply dark theme first (so dialog looks correct)
    app.setStyle("Fusion")

    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(45, 45, 50))
    palette.setColor(palette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Base, QColor(35, 35, 40))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(45, 45, 50))
    palette.setColor(palette.ColorRole.ToolTipBase, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.ToolTipText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Button, QColor(55, 55, 60))
    palette.setColor(palette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(palette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(palette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    # Initialize safe user-mode sensors.
    init_sensors()

    # Show sensor dialog if not connected (skip if minimized/auto-start)
    from src.core.sensors import HAS_LHM
    if not HAS_LHM and not args.minimized:
        dialog = SensorSetupDialog()
        dialog.exec()
        # Re-initialize sensors in case counters became available
        init_sensors()

    # Create main window
    window = ThemeEditorWindow()

    # Register cleanup handlers to ensure HID device is released on any exit
    def cleanup_on_exit():
        try:
            window.cleanup()
        except:
            pass

    atexit.register(cleanup_on_exit)
    app.aboutToQuit.connect(cleanup_on_exit)

    # Handle Ctrl+C and termination signals
    def signal_handler(signum, frame):
        cleanup_on_exit()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create system tray icon
    tray_icon = QSystemTrayIcon(create_tray_icon(), app)
    tray_icon.setToolTip("Thermal Engine")

    # Tray menu
    tray_menu = QMenu()
    show_action = tray_menu.addAction("Show")
    show_action.triggered.connect(lambda: (window.showNormal(), window.activateWindow()))
    tray_menu.addSeparator()
    quit_action = tray_menu.addAction("Quit")
    quit_action.triggered.connect(window.force_quit)
    tray_icon.setContextMenu(tray_menu)

    # Double-click tray to show window
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            window.showNormal()
            window.activateWindow()

    tray_icon.activated.connect(on_tray_activated)
    tray_icon.show()

    # Store tray reference in window for minimize-to-tray functionality
    window.tray_icon = tray_icon

    # Show window (or minimize based on settings/args)
    if args.minimized:
        # Start minimized to tray - don't show window
        window.hide()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
