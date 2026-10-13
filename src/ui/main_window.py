"""
ThemeEditorWindow - Main application window.
"""

import sys
import os
import json
import time
import io
import threading
import copy
import psutil
import logging
import platform
import webbrowser

# Windows-specific imports for power event handling
if sys.platform == 'win32':
    pass

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QColorDialog, QFileDialog,
    QComboBox, QSplitter, QMessageBox, QStatusBar, QTabWidget,
    QDialog, QCheckBox, QDialogButtonBox, QGroupBox, QFormLayout, QSystemTrayIcon,
    QTextEdit, QPlainTextEdit, QSpinBox, QApplication, QProgressDialog, QStyle,
    QTabBar, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QSize
from PySide6.QtGui import QColor, QAction, QKeySequence, QIcon, QTextCursor, QFont, QImage, QPixmap


class ConsoleOutputStream(QObject):
    """Stream that captures output and emits signals for GUI display."""
    text_written = Signal(str)

    def __init__(self, original_stream=None):
        super().__init__()
        self.original_stream = original_stream

    def write(self, text):
        if text:
            self.text_written.emit(text)
            if self.original_stream:
                try:
                    self.original_stream.write(text)
                except UnicodeEncodeError:
                    # Legacy Windows consoles (cp1252) can't print symbols like ✓
                    encoding = getattr(self.original_stream, "encoding", None) or "ascii"
                    self.original_stream.write(text.encode(encoding, "replace").decode(encoding))
                self.original_stream.flush()

    def flush(self):
        if self.original_stream:
            self.original_stream.flush()


class ConsoleWindow(QDialog):
    """Window that displays captured console output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Console Output")
        self.setMinimumSize(600, 400)
        self.resize(800, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Console text display
        self.console_text = QPlainTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setMaximumBlockCount(5000)  # Limit lines to prevent memory issues

        # Use monospace font
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.console_text.setFont(font)

        # Dark theme styling
        self.console_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                selection-background-color: #264f78;
            }
        """)

        layout.addWidget(self.console_text)

        # Button row
        button_layout = QHBoxLayout()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.console_text.clear)
        self.clear_btn.setToolTip("Clear console")
        self.clear_btn.setAccessibleName("Clear console")
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.hide)
        self.close_btn.setToolTip("Close console")
        self.close_btn.setAccessibleName("Close console")
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def append_text(self, text):
        """Append text to the console display."""
        # Move cursor to end and insert text
        self.console_text.moveCursor(QTextCursor.End)
        self.console_text.insertPlainText(text)
        # Auto-scroll to bottom
        self.console_text.moveCursor(QTextCursor.End)

# Windows power event constants
WM_POWERBROADCAST = 0x0218
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMSUSPEND = 0x0004

from PIL import Image, ImageEnhance

from src.core.security import validate_preset_schema


from src.core import constants
from src.core.renderer import ThemeRenderer
from src.core.display_size import (
    DISPLAY_SIZE_PROFILES,
    device_size_key,
    get_device_size_override,
    resize_theme_elements,
    validate_display_size,
)

# Device backend system for multi-device support
from src.core.device_backends import (
    DeviceIOError, enumerate_available_devices,
    create_backend
)

# Setup logger for main window
logger = logging.getLogger(__name__)


from src.core.element import ThemeElement
from src.core import sensors
from src.core.sensors import get_cached_sensors, stop_sensors
from src.utils import settings
from src.utils.app_path import (
    get_bundled_resource_path,
    get_user_data_path,
    write_json_atomic,
)
from src.utils.updater import (
    GITHUB_RELEASES_URL,
    UpdateChecker,
    UpdateDownloader,
    can_auto_install_asset,
    install_downloaded_update,
)


from src.ui.canvas import CanvasPreview
from src.ui.icons import icon as svg_icon
from src.ui.properties import PropertiesPanel
from src.ui.element_list import ElementListPanel
from src.ui.presets import PresetsPanel
from src.ui.video_background import video_background, HAS_CV2


class ThemeEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theme_path = None
        try:
            sensors.configure_network_sensors(settings.get_setting("network_sensors", []))
        except ValueError as exc:
            logger.warning("Network sensor configuration invalid: %s", exc)
        self.theme_name = "Untitled Theme"
        self.background_color = "#0f0f19"
        self.elements = []
        self.device = None  # Legacy compatibility
        self.backend = None  # New device backend system
        self.selected_device_def = None  # Selected device definition
        self._selected_device_default_size = None
        self.live_preview_timer = None
        self.target_fps = settings.get_setting("target_fps", 30)
        self.display_brightness = settings.get_setting("display_brightness", 100)

        # Performance monitoring
        self.frame_times = []
        self.last_frame_time = 0
        self._last_frame_request_time = 0
        self.perf_update_timer = None
        self.process = psutil.Process()

        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_levels = 50

        # Clipboard for copy/paste
        self._clipboard = []

        # Canvas update throttling (skip canvas updates during high-speed rendering)
        self._canvas_update_counter = 0
        self._animated_values = {}  # id(element) -> (shown value, timestamp)
        self._canvas_update_interval = 3  # Update canvas every N frames when connected

        # Frame timing for smooth delivery
        self._frame_deadline = 0  # When next frame should be sent
        self._frames_skipped = 0  # Counter for skipped frames
        self.display_orientation = settings.get_setting("display_orientation", "normal")  # normal, flip_v, flip_h, rotate_180, rotate_90_cw, rotate_90_ccw
        self._render_thread = None
        self._render_thread_running = False
        self._frame_request = threading.Event()
        self._frame_error = None
        self._frame_snapshot = None
        self._frame_snapshot_lock = threading.Lock()
        self.renderer = ThemeRenderer()

        # Multi-page system
        self.pages = [{"name": "Page 1", "number": 1}]  # List of pages
        self.current_page = 1  # Current page being edited/displayed
        self.auto_rotate_pages = False  # Auto-rotate through pages
        self.page_rotation_interval = 5  # Seconds between page rotations
        self.page_rotation_timer = None  # Timer for auto-rotation

        # Sleep/wake handling - auto-reconnect
        self._reconnect_timer = None
        self._reconnect_attempts = 0
        self._was_connected_before_sleep = False
        self._last_wake_time = 0

        # Preset loading tracking (defer until after window shown)
        self._preset_loaded_on_startup = False
        self._needs_onboarding = (
            not settings.get_setting("onboarding_completed", False)
            and not settings.get_setting("last_preset")
            and not settings.get_setting("default_preset")
        )

        # Autosave: debounce timer, fires 3s after last change
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(3000)
        self._autosave_timer.timeout.connect(self._do_autosave)
        self._page_preview_timer = QTimer(self)
        self._page_preview_timer.setSingleShot(True)
        self._page_preview_timer.setInterval(300)
        self._page_preview_timer.timeout.connect(self._update_page_thumbnails)

        # Auto Profiles
        from src.utils.profiles import ProfileManager
        self._profile_manager = ProfileManager()
        self._foreground_monitor = None
        self._system_state_monitor = None
        self._start_profile_monitors()

        self.setup_ui()
        self.setup_console()
        self.setup_menu()
        self.connect_signals()

        self.add_default_elements()
        self.setup_performance_monitor()

        # Auto-connect to display after window is shown
        if not self._needs_onboarding:
            QTimer.singleShot(500, self.auto_connect)

        # Check for updates on startup (if enabled)
        if settings.get_setting("check_for_updates", True):
            QTimer.singleShot(2000, lambda: self.check_for_updates(silent=True))

    def showEvent(self, event):
        """Load default preset after window is first shown and fully rendered."""
        super().showEvent(event)
        # Load preset only once, after window is shown and canvas is sized
        if not self._preset_loaded_on_startup:
            self._preset_loaded_on_startup = True
            if self._needs_onboarding:
                QTimer.singleShot(0, self.show_setup_wizard)
            else:
                self.load_default_preset_on_startup()

    def show_setup_wizard(self):
        from src.ui.onboarding import SetupWizard

        wizard = SetupWizard(
            self.presets_panel.presets,
            (constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT),
            settings.get_setting("display_size_overrides", {}), self,
        )
        self._needs_onboarding = False
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        self.disconnect_display()
        device = wizard.device_combo.currentData()
        size = validate_display_size(wizard.width_spin.value(), wizard.height_spin.value())
        if device:
            self._selected_device_default_size = (device.width, device.height)
            self.selected_device_def = copy.copy(device)
            self.selected_device_def.extra_params = dict(device.extra_params)
            overrides = dict(settings.get_setting("display_size_overrides", {}))
            overrides[device_size_key(device)] = list(size)
            settings.set_setting("display_size_overrides", overrides)
        else:
            self.selected_device_def = None
            self._selected_device_default_size = None
        self._set_display_size(*size)
        settings.set_setting("default_preset", wizard.preset_name)
        if wizard.preset_name:
            self.presets_panel.on_preset_clicked(wizard.preset_name)
        else:
            self.save_undo_state()
            self.new_theme()
            settings.set_setting("last_preset", None)
        settings.set_setting("onboarding_completed", True)
        if device:
            self.connect_display()

    def auto_connect(self):
        """Attempt to connect to display automatically on startup."""
        if self.connect_display(show_error=False):
            self.status_bar.showMessage("Auto-connected to display")
            # Load preset with correct display dimensions after connection.
            # Also handles minimized-to-tray startup where showEvent never fires.
            self._preset_loaded_on_startup = True
            self.load_default_preset_on_startup()
        else:
            self.status_bar.showMessage("Display not found - click Connect when ready")

    def nativeEvent(self, eventType, message):
        """Handle native Windows events for sleep/wake detection."""
        if sys.platform == 'win32' and eventType == b"windows_generic_MSG":
            try:
                import ctypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_POWERBROADCAST:
                    if msg.wParam == PBT_APMSUSPEND:
                        # System is going to sleep
                        self._handle_system_sleep()
                    elif msg.wParam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                        # System is waking up
                        self._handle_system_wake()
            except Exception as e:
                logger.warning(f"Error handling power event: {e}")
        return super().nativeEvent(eventType, message)

    def _handle_system_sleep(self):
        """Handle system going to sleep."""
        logger.info("System going to sleep")
        self._was_connected_before_sleep = self.device is not None
        # Stop reconnect timer if running
        if self._reconnect_timer:
            self._reconnect_timer.stop()
            self._reconnect_timer = None

    def _handle_system_wake(self):
        """Handle system waking from sleep."""
        logger.info("System waking up")
        self._last_wake_time = time.time()

        # Reset video background timing to prevent frame jumps
        video_background.reset_timing()

        # Reset GIF playback timing
        try:
            from elements.gif import reset_all_playback
            reset_all_playback()
        except ImportError:
            pass

        # Reset frame timing for FPS calculation
        self.frame_times = []
        self.last_frame_time = 0
        self._last_frame_request_time = 0
        sensors.invalidate_sensor_cache()

        # If we were connected before sleep, try to reconnect
        if self._was_connected_before_sleep:
            # Disconnect cleanly first (device is likely invalid)
            if self.device:
                try:
                    self.device.close()
                except:
                    pass
                self.device = None

            # Start reconnection attempts after a short delay
            self._reconnect_attempts = 0
            self._start_reconnect_timer()
            self.status_bar.showMessage("Waking up - reconnecting to display...")

    def _start_reconnect_timer(self):
        """Start the auto-reconnect timer with exponential backoff."""
        if self._reconnect_timer is None:
            self._reconnect_timer = QTimer(self)
            self._reconnect_timer.timeout.connect(self._attempt_reconnect)

        # Exponential backoff: 1s, 2s, 4s, 8s... capped at 30s
        delay = min(30000, 1000 * (2 ** self._reconnect_attempts))
        self._reconnect_timer.start(delay)

    def _attempt_reconnect(self):
        """Attempt to reconnect to the display."""
        self._reconnect_attempts += 1

        logger.info(f"Reconnect attempt {self._reconnect_attempts}")

        if self.connect_display(show_error=False):
            # Success!
            if self._reconnect_timer:
                self._reconnect_timer.stop()
                self._reconnect_timer = None
            self._was_connected_before_sleep = False
            self.status_bar.showMessage("Reconnected to display after wake")
            logger.info("Reconnected successfully")
        else:
            # Keep trying with backoff (no max limit - will retry indefinitely)
            self._start_reconnect_timer()
            self.status_bar.showMessage(f"Reconnecting... attempt {self._reconnect_attempts}")

    def load_default_preset_on_startup(self):
        """Load the default preset if one is configured."""
        default_preset_data = self.presets_panel.get_default_preset_data()
        if default_preset_data:
            # Load without saving undo state (it's startup)
            self.theme_name = default_preset_data.get("name", "Untitled")
            self.theme_name_edit.setText(self.theme_name)
            self.background_color = default_preset_data.get("background_color", "#0f0f19")
            self.bg_color_btn.setStyleSheet(f"background-color: {self.background_color};")
            self.canvas.set_background_color(self.background_color)

            self.elements = [
                ThemeElement.from_dict(e) for e in default_preset_data.get("elements", [])
            ]
            self.element_list.set_elements(self.elements)
            self._rebuild_pages()

            # Load video background settings if present
            video_data = default_preset_data.get("video_background", {})
            if video_data:
                video_background.from_dict(video_data)
            else:
                video_background.clear_video()
            self._update_video_ui()

            logger.info(f"Loaded default preset: {self.theme_name}")

    def setup_ui(self):
        self.setWindowTitle("Thermal Engine")
        self.setMinimumSize(1200, 700)

        # Set window icon
        icon_path = get_bundled_resource_path("assets/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel with tabs for Elements and Presets
        left_panel = QTabWidget()
        left_panel.setMaximumWidth(340)

        self.element_list = ElementListPanel()
        left_panel.addTab(self.element_list, "Elements")

        self.presets_panel = PresetsPanel()
        left_panel.addTab(self.presets_panel, "Presets")

        splitter.addWidget(left_panel)

        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)

        self.theme_name_edit = QLineEdit(self.theme_name)
        self.theme_name_edit.textChanged.connect(self.on_theme_name_changed)

        self.quick_save_btn = QPushButton("Save")
        self.quick_save_btn.clicked.connect(self.quick_save)
        self.quick_save_btn.setToolTip("Save to presets folder (Ctrl+S)")
        self.quick_save_btn.setAccessibleName("Save to presets folder (Ctrl+S)")

        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(60, 25)
        self.bg_color_btn.setStyleSheet(f"background-color: {self.background_color};")
        self.bg_color_btn.setToolTip("Change background color")
        self.bg_color_btn.setAccessibleName("Change background color")
        self.bg_color_btn.clicked.connect(self.choose_background_color)

        self.video_btn = QPushButton("None")
        self.video_btn.clicked.connect(self.choose_video_background)
        self.video_btn.setToolTip("Choose video background")
        self.video_btn.setAccessibleName("Choose video background")

        self.video_fit_combo = QComboBox()
        self.video_fit_combo.addItem("Fit Height", "fit_height")
        self.video_fit_combo.addItem("Fit Width", "fit_width")
        self.video_fit_combo.currentIndexChanged.connect(self.on_video_fit_changed)
        self.video_fit_combo.setEnabled(False)

        self.clear_video_btn = QPushButton("Clear")
        self.clear_video_btn.clicked.connect(self.clear_video_background)
        self.clear_video_btn.setEnabled(False)

        self.canvas = CanvasPreview()
        self.canvas.frame_renderer = self._render_preview_frame

        # Set size policy to allow canvas to shrink when window is small
        # This prevents canvas from covering page controls
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Override canvas minimum height to prevent it from covering page controls
        self.canvas.setMinimumHeight(300)  # Ensure at least 300px height

        # Initialize grid settings from preferences
        self.canvas.set_show_grid(settings.get_setting("show_grid", True))
        self.canvas.set_snap_to_grid(settings.get_setting("snap_to_grid", True))

        # Add canvas with stretch factor to fill available space
        # Stretch factor 1 means it will grow, but page controls will stay visible
        canvas_layout.addWidget(self.canvas, 1)

        # Page controls at bottom (stretch factor 0 = fixed size, always visible)
        page_controls_layout = QHBoxLayout()

        self.page_tabs = QTabBar()
        self.page_tabs.setDrawBase(False)
        self.page_tabs.setExpanding(False)
        self.page_tabs.setIconSize(QSize(96, 48))
        self.page_tabs.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.page_tabs.currentChanged.connect(self.on_page_changed)
        self.page_tabs.tabCloseRequested.connect(self.delete_page)
        self.update_page_tabs()
        page_controls_layout.addWidget(self.page_tabs)

        self.add_page_btn = QToolButton()
        self.add_page_btn.setIcon(svg_icon("plus"))
        self.add_page_btn.setAutoRaise(True)
        self.add_page_btn.setToolTip("Add a new page")
        self.add_page_btn.setAccessibleName("Add a new page")
        self.add_page_btn.clicked.connect(self.add_page)
        page_controls_layout.addWidget(self.add_page_btn)
        page_controls_layout.addSpacing(12)

        self.auto_rotate_checkbox = QCheckBox("Auto-Rotate")
        self.auto_rotate_checkbox.setChecked(self.auto_rotate_pages)
        self.auto_rotate_checkbox.toggled.connect(self.toggle_auto_rotate)
        page_controls_layout.addWidget(self.auto_rotate_checkbox)

        self.rotation_interval_spin = QSpinBox()
        self.rotation_interval_spin.setRange(1, 60)
        self.rotation_interval_spin.setValue(self.page_rotation_interval)
        self.rotation_interval_spin.setSuffix(" sec")
        self.rotation_interval_spin.setFixedWidth(80)
        self.rotation_interval_spin.valueChanged.connect(self.set_rotation_interval)
        page_controls_layout.addWidget(self.rotation_interval_spin)

        page_controls_layout.addStretch()

        self.zoom_btn = QPushButton()
        self.zoom_btn.setFlat(True)
        self.zoom_btn.setToolTip("Zoom (Ctrl+wheel). Click to fit to window (Ctrl+0)")
        self.zoom_btn.setAccessibleName("Zoom level; click to fit to window")
        self.zoom_btn.clicked.connect(lambda: self.canvas.set_zoom(None))
        page_controls_layout.addWidget(self.zoom_btn)

        canvas_layout.addLayout(page_controls_layout)

        splitter.addWidget(canvas_container)

        self.properties_panel = PropertiesPanel()
        self.properties_panel.setMinimumWidth(280)
        self.properties_panel.setMaximumWidth(320)
        self.properties_panel.set_no_selection_widget(self._build_theme_section())
        splitter.addWidget(self.properties_panel)

        splitter.setSizes([200, 650, 300])

        main_layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Performance indicator widgets
        self.perf_indicator = QToolButton()
        self.perf_indicator.setText("● Disconnected · Connect")
        self.perf_indicator.setToolTip("Connect to a display")
        self.perf_indicator.setAccessibleName("Display connection")
        self.perf_indicator.clicked.connect(self.toggle_connection)

        self.perf_label = QLabel("FPS: -- | CPU: --%")
        self.perf_label.setStyleSheet("padding: 2px 8px;")

        self.status_bar.addPermanentWidget(self.perf_indicator)
        self.status_bar.addPermanentWidget(self.perf_label)

    def _build_theme_section(self):
        """Theme-wide settings, shown in the Properties panel when nothing is selected."""
        frame, form = self.properties_panel.create_section("Theme")

        name_row = QHBoxLayout()
        name_row.addWidget(self.theme_name_edit, 1)
        name_row.addWidget(self.quick_save_btn)
        form.addRow("Name:", name_row)
        form.addRow("Background:", self.bg_color_btn)
        form.addRow("Video:", self.video_btn)
        video_row = QHBoxLayout()
        video_row.addWidget(self.video_fit_combo, 1)
        video_row.addWidget(self.clear_video_btn)
        form.addRow("", video_row)

        display_row = QHBoxLayout()
        self.display_size_label = QLabel()
        display_row.addWidget(self.display_size_label, 1)
        change_size_btn = QPushButton("Change…")
        change_size_btn.setToolTip("Change display resolution")
        change_size_btn.setAccessibleName("Change display resolution")
        change_size_btn.clicked.connect(self.show_display_size_dialog)
        display_row.addWidget(change_size_btn)
        form.addRow("Display:", display_row)
        self._update_display_size_label()

        hint = QLabel("Select an element on the canvas or in the list to edit it.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-style: italic; padding: 8px 2px;")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(frame)
        layout.addWidget(hint)
        return container

    def _update_display_size_label(self):
        self.display_size_label.setText(f"{constants.DISPLAY_WIDTH} \u00d7 {constants.DISPLAY_HEIGHT}")

    def setup_console(self):
        """Setup console output capture and window."""
        self.console_window = ConsoleWindow(self)

        # Capture stdout and stderr
        self.stdout_stream = ConsoleOutputStream(sys.stdout)
        self.stderr_stream = ConsoleOutputStream(sys.stderr)

        self.stdout_stream.text_written.connect(self.console_window.append_text)
        self.stderr_stream.text_written.connect(self.console_window.append_text)

        sys.stdout = self.stdout_stream
        sys.stderr = self.stderr_stream

        # Log records also go to the console window (the file handler is set up in main.py)
        console_handler = logging.StreamHandler(self.stdout_stream)
        console_handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(console_handler)

    def show_console(self):
        """Show the console output window."""
        self.console_window.show()
        self.console_window.raise_()
        self.console_window.activateWindow()

    def setup_menu(self):
        menubar = self.menuBar()
        icon = self.style().standardIcon

        file_menu = menubar.addMenu("File")

        new_action = QAction("New Theme", self)
        new_action.setIcon(icon(QStyle.StandardPixmap.SP_FileIcon))
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_theme)
        file_menu.addAction(new_action)

        open_action = QAction("Open Theme...", self)
        open_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_theme)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.quick_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_theme_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_action = QAction("Export as Image...", self)
        export_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        export_action.triggered.connect(self.export_image)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        export_theme_action = QAction("Export Theme Package...", self)
        export_theme_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        export_theme_action.triggered.connect(self.export_theme_package)
        file_menu.addAction(export_theme_action)

        export_zip_action = QAction("Export Theme as ZIP...", self)
        export_zip_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        export_zip_action.triggered.connect(self.export_theme_zip)
        file_menu.addAction(export_zip_action)

        import_theme_action = QAction("Import Theme Package...", self)
        import_theme_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        import_theme_action.triggered.connect(self.import_theme_package)
        file_menu.addAction(import_theme_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogCloseButton))
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        self.undo_action = QAction("Undo", self)
        self.undo_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowBack))
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowForward))
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()

        copy_action = QAction("Copy", self)
        copy_action.setIcon(icon(QStyle.StandardPixmap.SP_FileIcon))
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.copy_selected_elements)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Paste", self)
        paste_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogApplyButton))
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.paste_elements)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        bring_front_action = QAction("Bring to Front", self)
        bring_front_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowUp))
        bring_front_action.setShortcut(QKeySequence("Ctrl+Shift+]"))
        bring_front_action.triggered.connect(self.bring_to_front)
        edit_menu.addAction(bring_front_action)

        bring_forward_action = QAction("Bring Forward", self)
        bring_forward_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowUp))
        bring_forward_action.setShortcut(QKeySequence("Ctrl+]"))
        bring_forward_action.triggered.connect(self.bring_forward)
        edit_menu.addAction(bring_forward_action)

        send_backward_action = QAction("Send Backward", self)
        send_backward_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowDown))
        send_backward_action.setShortcut(QKeySequence("Ctrl+["))
        send_backward_action.triggered.connect(self.send_backward)
        edit_menu.addAction(send_backward_action)

        send_back_action = QAction("Send to Back", self)
        send_back_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowDown))
        send_back_action.setShortcut(QKeySequence("Ctrl+Shift+["))
        send_back_action.triggered.connect(self.send_to_back)
        edit_menu.addAction(send_back_action)

        # View menu
        view_menu = menubar.addMenu("View")

        self.show_grid_action = QAction("Show Grid", self)
        self.show_grid_action.setIcon(icon(QStyle.StandardPixmap.SP_FileDialogListView))
        self.show_grid_action.setCheckable(True)
        self.show_grid_action.setChecked(settings.get_setting("show_grid", True))
        self.show_grid_action.triggered.connect(self.toggle_show_grid)
        view_menu.addAction(self.show_grid_action)

        self.snap_to_grid_action = QAction("Snap to Grid", self)
        self.snap_to_grid_action.setIcon(icon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.snap_to_grid_action.setCheckable(True)
        self.snap_to_grid_action.setChecked(settings.get_setting("snap_to_grid", True))
        self.snap_to_grid_action.triggered.connect(self.toggle_snap_to_grid)
        view_menu.addAction(self.snap_to_grid_action)

        view_menu.addSeparator()
        for label, shortcut, slot in (
            ("Zoom In", "Ctrl+=", lambda: self.canvas.zoom_by(1.25)),
            ("Zoom Out", "Ctrl+-", lambda: self.canvas.zoom_by(1 / 1.25)),
            ("Fit to Window", "Ctrl+0", lambda: self.canvas.set_zoom(None)),
            ("Actual Size (100%)", "Ctrl+1", lambda: self.canvas.set_zoom(1.0)),
        ):
            action = QAction(label, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            view_menu.addAction(action)

        display_menu = menubar.addMenu("Display")

        self.connect_action = QAction("Connect", self)
        self.connect_action.setIcon(icon(QStyle.StandardPixmap.SP_DriveNetIcon))
        self.connect_action.triggered.connect(self.toggle_connection)
        display_menu.addAction(self.connect_action)

        display_menu.addSeparator()

        self.send_action = QAction("Send to Display", self)
        self.send_action.setIcon(icon(QStyle.StandardPixmap.SP_ArrowRight))
        self.send_action.setShortcut("F5")
        self.send_action.triggered.connect(self.send_to_display)
        self.send_action.setEnabled(False)
        display_menu.addAction(self.send_action)

        display_menu.addSeparator()

        screen_size_action = QAction("Screen Size...", self)
        screen_size_action.setIcon(icon(QStyle.StandardPixmap.SP_DesktopIcon))
        screen_size_action.triggered.connect(self.show_display_size_dialog)
        display_menu.addAction(screen_size_action)

        display_menu.addSeparator()

        fps_menu = display_menu.addMenu("Frame Rate")
        fps_menu.setIcon(icon(QStyle.StandardPixmap.SP_MediaPlay))
        self.fps_actions = []
        for fps in [10, 20, 30, 60]:
            action = QAction(f"{fps} FPS", self)
            action.setCheckable(True)
            action.setChecked(fps == self.target_fps)
            action.triggered.connect(lambda checked, f=fps: self.set_target_fps(f))
            fps_menu.addAction(action)
            self.fps_actions.append(action)

        fps_menu.addSeparator()

        display_menu.addSeparator()

        brightness_menu = display_menu.addMenu("Software Brightness")
        brightness_menu.setIcon(icon(QStyle.StandardPixmap.SP_TitleBarShadeButton))
        self.brightness_actions = []
        for brightness in (25, 50, 75, 100):
            action = QAction(f"{brightness}%", self)
            action.setCheckable(True)
            action.setChecked(brightness == self.display_brightness)
            action.triggered.connect(
                lambda checked, value=brightness: self.set_display_brightness(value)
            )
            brightness_menu.addAction(action)
            self.brightness_actions.append((action, brightness))

        display_menu.addSeparator()

        # Display Orientation submenu
        orientation_menu = display_menu.addMenu("Display Orientation")
        orientation_menu.setIcon(icon(QStyle.StandardPixmap.SP_BrowserReload))
        self.orientation_actions = []
        orientations = [
            ("Normal", "normal"),
            ("Flip Vertical", "flip_v"),
            ("Flip Horizontal", "flip_h"),
            ("Rotate 180°", "rotate_180"),
            ("Rotate 90° CW", "rotate_90_cw"),
            ("Rotate 90° CCW", "rotate_90_ccw"),
        ]
        for label, value in orientations:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(value == self.display_orientation)
            action.triggered.connect(lambda checked, v=value: self.set_display_orientation(v))
            orientation_menu.addAction(action)
            self.orientation_actions.append((action, value))

        display_menu.addSeparator()

        diagnose_action = QAction("Diagnose Sensors...", self)
        diagnose_action.setIcon(icon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        diagnose_action.triggered.connect(self.diagnose_sensors)
        display_menu.addAction(diagnose_action)

        copy_diagnostics_action = QAction("Copy Diagnostic Report", self)
        copy_diagnostics_action.setIcon(icon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        copy_diagnostics_action.triggered.connect(self.copy_diagnostic_report)
        display_menu.addAction(copy_diagnostics_action)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")

        settings_action = QAction("Preferences...", self)
        settings_action.setIcon(icon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)

        network_action = QAction("Network Sensors...", self)
        network_action.triggered.connect(self.show_network_sensors)
        settings_menu.addAction(network_action)

        settings_menu.addSeparator()

        auto_profiles_action = QAction("Auto Profiles...", self)
        auto_profiles_action.setIcon(icon(QStyle.StandardPixmap.SP_DirHomeIcon))
        auto_profiles_action.triggered.connect(self.show_auto_profiles)
        settings_menu.addAction(auto_profiles_action)

        settings_menu.addSeparator()

        console_action = QAction("Show Console", self)
        console_action.setIcon(icon(QStyle.StandardPixmap.SP_ComputerIcon))
        console_action.triggered.connect(self.show_console)
        settings_menu.addAction(console_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        setup_action = help_menu.addAction("Setup Wizard...")
        setup_action.triggered.connect(self.show_setup_wizard)

        check_updates_action = QAction("Check for Updates...", self)
        check_updates_action.setIcon(icon(QStyle.StandardPixmap.SP_BrowserReload))
        check_updates_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(check_updates_action)

    def connect_signals(self):
        self.element_list.element_selected.connect(self.on_element_selected)
        self.element_list.elements_selected.connect(self.on_elements_selected)
        self.element_list.elements_will_change.connect(self.save_undo_state)
        self.element_list.elements_changed.connect(self.refresh_canvas)

        self._connect_canvas_signals()

        self.properties_panel.property_will_change.connect(self.save_undo_state)
        self.properties_panel.property_changed.connect(self._on_property_changed)
        self.properties_panel.property_changed.connect(self.refresh_canvas)
        self.properties_panel.property_changed.connect(self.update_element_list_name)
        self.properties_panel.alignment_will_change.connect(self.save_undo_state)
        self.properties_panel.alignment_changed.connect(self.refresh_canvas)

        self.presets_panel.preset_selected.connect(self.load_preset)
        self.presets_panel.preset_saved.connect(self.on_preset_saved)

        # Autosave on any change
        self.properties_panel.property_changed.connect(self._schedule_autosave)
        self.properties_panel.alignment_changed.connect(self._schedule_autosave)
        self.element_list.elements_changed.connect(self._schedule_autosave)

    def _connect_canvas_signals(self):
        """Wire the canvas; also used when it is recreated for a new display size."""
        self.canvas.element_selected.connect(self.on_canvas_element_selected)
        self.canvas.elements_selected.connect(self.on_canvas_elements_selected)
        self.canvas.element_moved.connect(self.on_element_moved)
        self.canvas.element_resized.connect(self.on_element_resized)
        self.canvas.drag_started.connect(self.save_undo_state)
        self.canvas.element_moved.connect(self._schedule_autosave)
        self.canvas.element_resized.connect(self._schedule_autosave)
        self.canvas.zoom_changed.connect(self._update_zoom_label)
        self._update_zoom_label()

    def setup_performance_monitor(self):
        """Setup timer to update performance stats."""
        self.perf_update_timer = QTimer(self)
        self.perf_update_timer.timeout.connect(self.update_performance_stats)
        self.perf_update_timer.start(500)  # Update every 500ms

        # Keep clocks, sensors and animations moving in the editor when no display is connected
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._tick_preview)
        self.preview_timer.start(100)

    def update_performance_stats(self):
        """Update the performance indicator in the status bar."""
        # Calculate actual FPS from frame times
        if len(self.frame_times) >= 2:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            actual_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        else:
            actual_fps = 0

        # Get CPU usage of this process
        try:
            cpu_percent = self.process.cpu_percent(interval=None)
        except:
            cpu_percent = 0

        # Determine status color based on performance
        if not self.device:
            color = "#aaaaaa"
            status = "Idle"
        elif actual_fps >= self.target_fps * 0.9:
            color = "#4CAF50"
            status = "Good"
        elif actual_fps >= self.target_fps * 0.7:
            color = "#FFC107"
            status = "Moderate"
        else:
            color = "#F44336"
            status = "High Load"

        self.perf_indicator.setStyleSheet(
            f"color: {color}; padding: 3px 8px;"
        )
        if self.device:
            name = self.selected_device_def.name if self.selected_device_def else "Display"
            self.perf_indicator.setText(
                f"● {name} {constants.DISPLAY_WIDTH}×{constants.DISPLAY_HEIGHT} · {actual_fps:.0f} fps"
            )
            self.perf_indicator.setToolTip("Disconnect display")
        else:
            self.perf_indicator.setText("● Disconnected · Connect")
            self.perf_indicator.setToolTip("Connect to a display")

        # Get memory usage
        try:
            mem_mb = self.process.memory_info().rss / (1024 * 1024)
            mem_str = f" | RAM: {mem_mb:.0f}MB"
        except:
            mem_str = ""

        if self.device:
            skip_str = f" Skip:{self._frames_skipped}" if self._frames_skipped > 0 else ""
            self.perf_label.setText(
                f"FPS: {actual_fps:.1f}/{self.target_fps} | CPU: {cpu_percent:.1f}%{mem_str} | {status}{skip_str}"
            )
            # Reset skip counter periodically
            self._frames_skipped = 0
        else:
            self.perf_label.setText(f"FPS: -- | CPU: --%{mem_str}")

        if self.device and actual_fps < self.target_fps * 0.7 and actual_fps > 0:
            self.status_bar.showMessage(
                f"Performance warning: Only achieving {actual_fps:.1f} FPS. "
                f"Consider reducing target FPS or simplifying theme.", 3000
            )

    def record_frame_time(self):
        """Record the time between frames sent to the device."""
        current_time = time.perf_counter()  # High-precision timer
        if self.last_frame_time > 0:
            frame_time = current_time - self.last_frame_time
            # Only record reasonable frame times (filter out outliers from pauses)
            if frame_time < 1.0:  # Ignore gaps > 1 second
                self.frame_times.append(frame_time)
                if len(self.frame_times) > 60:  # Larger sample for stability
                    self.frame_times.pop(0)
        self.last_frame_time = current_time

    def add_default_elements(self):
        """Add default elements optimized for 480x480 displays."""
        defaults = [
            ThemeElement("analog_clock", name="main_clock", x=240, y=200, radius=140,
                         text="Clock", source="static", color="#ffffff", value=50,
                         time_format="24h", show_seconds_hand=True, smooth_animation=True,
                         background_color="#1a1a2e", background_color_opacity=0),
            ThemeElement("text", name="cpu_temp", x=40, y=410, width=100, height=50,
                         text="CPU", source="cpu_temp", color="#00ff96", font_size=28,
                         text_align="left"),
            ThemeElement("text", name="cpu_util", x=160, y=410, width=100, height=50,
                         text="CPU%", source="cpu_percent", color="#00c8ff", font_size=28,
                         text_align="left"),
            ThemeElement("text", name="gpu_temp", x=280, y=410, width=100, height=50,
                         text="GPU", source="gpu_temp", color="#ff9632", font_size=28,
                         text_align="left"),
            ThemeElement("text", name="gpu_util", x=400, y=410, width=100, height=50,
                         text="GPU%", source="gpu_percent", color="#c864ff", font_size=28,
                         text_align="left"),
            ThemeElement("text", name="date", x=0, y=20, width=480, height=40,
                         text="Monday, January 1", source="date", color="#666680", font_size=20,
                         text_align="center"),
        ]

        self.elements = defaults
        self.element_list.set_elements(self.elements)
        self._rebuild_pages()

    def on_element_selected(self, idx):
        self.canvas.set_selected(idx)
        if idx >= 0 and idx < len(self.elements):
            self.properties_panel.set_element(self.elements[idx])
        else:
            self.properties_panel.set_element(None)

    def on_canvas_element_selected(self, idx):
        self.element_list.select_element(idx, emit_signals=False)
        if idx >= 0 and idx < len(self.elements):
            self.properties_panel.set_element(self.elements[idx])
        else:
            self.properties_panel.set_element(None)

    def on_elements_selected(self, indices):
        """Handle multi-selection from element list."""
        # Check if a group was selected (vs individual elements)
        is_group = self.element_list.is_group_selected()
        self.canvas.set_selected_indices(indices, group_selection=is_group)
        if len(indices) == 1:
            self.properties_panel.set_element(self.elements[indices[0]])
        elif len(indices) > 1:
            # Show alignment panel for multiple selection
            self.properties_panel.set_multi_selection([self.elements[i] for i in indices], indices)
        else:
            self.properties_panel.set_element(None)

    def on_canvas_elements_selected(self, indices):
        """Handle multi-selection from canvas."""
        self.element_list.select_elements(indices, emit_signals=False)
        if len(indices) == 1:
            self.properties_panel.set_element(self.elements[indices[0]])
        elif len(indices) > 1:
            # Show alignment panel for multiple selection
            self.properties_panel.set_multi_selection([self.elements[i] for i in indices], indices)
        else:
            self.properties_panel.set_element(None)

    def on_element_moved(self, idx, x, y):
        if idx >= 0 and idx < len(self.elements):
            self.properties_panel.set_element(self.elements[idx])

    def on_element_resized(self, idx):
        if idx >= 0 and idx < len(self.elements):
            self.properties_panel.set_element(self.elements[idx])

    def refresh_canvas(self):
        """Refresh canvas - debounced to prevent rapid successive updates."""
        # Use a short timer to batch multiple rapid changes into one update
        if not hasattr(self, '_refresh_timer'):
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(self._do_refresh_canvas)

        # Restart timer - this batches rapid changes
        self._refresh_timer.start(16)  # ~60fps max update rate

    def _do_refresh_canvas(self):
        """Actually perform the canvas refresh."""
        self.canvas.set_elements(self.elements, self.current_page)
        self.canvas.update()
        self._page_preview_timer.start()

    def _schedule_autosave(self, *args):
        """Restart autosave debounce timer. Saves 3s after last change."""
        if self.theme_name and self.theme_name.strip() and self.theme_name != "Untitled Theme":
            self._autosave_timer.start()

    def _do_autosave(self):
        """Silently save current theme as preset (called by autosave timer)."""
        if not self.theme_name or self.theme_name.strip() == "" or self.theme_name == "Untitled Theme":
            return
        theme_data = {
            "name": self.theme_name,
            "background_color": self.background_color,
            "display_width": constants.DISPLAY_WIDTH,
            "display_height": constants.DISPLAY_HEIGHT,
            "elements": [e.to_dict() for e in self.elements],
            "video_background": video_background.to_dict()
        }
        thumbnail_image = None
        try:
            thumbnail_image = self.render_theme_image()
            if thumbnail_image and thumbnail_image.mode == 'RGBA':
                thumbnail_image = thumbnail_image.convert('RGB')
        except Exception:
            pass
        self.presets_panel.save_preset(self.theme_name, theme_data, thumbnail_image, silent=True)
        self.status_bar.showMessage(f"Autosaved: {self.theme_name}", 2000)

    def _on_property_changed(self):
        """Invalidate render cache when element properties change."""
        # Clear all caches - properties changed so cached renders are stale
        self.renderer.clear_cache()

    def save_undo_state(self):
        """Save current state to undo stack."""
        self.undo_stack.append(self._snapshot_state())
        if len(self.undo_stack) > self.max_undo_levels:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_undo_actions()

    def _snapshot_state(self):
        return {
            'elements': [e.to_dict() for e in self.elements],
            'background_color': self.background_color
        }

    def _restore_state(self, state):
        self.elements = [ThemeElement.from_dict(e) for e in state['elements']]
        self.background_color = state['background_color']
        self.element_list.set_elements(self.elements)
        self.canvas.set_background_color(self.background_color)
        self.bg_color_btn.setStyleSheet(f"background-color: {self.background_color};")
        self._rebuild_pages(keep_existing=True)
        self.update_undo_actions()

    def undo(self):
        """Undo the last action."""
        if not self.undo_stack:
            return
        self.redo_stack.append(self._snapshot_state())
        if len(self.redo_stack) > self.max_undo_levels:
            self.redo_stack.pop(0)
        self._restore_state(self.undo_stack.pop())
        self.status_bar.showMessage("Undo", 1500)

    def redo(self):
        """Redo the last undone action."""
        if not self.redo_stack:
            return
        self.undo_stack.append(self._snapshot_state())
        self._restore_state(self.redo_stack.pop())
        self.status_bar.showMessage("Redo", 1500)

    def update_undo_actions(self):
        """Update enabled state of undo/redo actions."""
        self.undo_action.setEnabled(len(self.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.redo_stack) > 0)

    # ------------------------------------------------------------------ #
    #  Copy / Paste
    # ------------------------------------------------------------------ #

    def copy_selected_elements(self):
        """Copy selected elements to clipboard."""
        indices = self._get_selected_global_indices()
        if not indices:
            return
        self._clipboard = [self.elements[i].to_dict() for i in indices]
        self.status_bar.showMessage(
            f"Copied {len(self._clipboard)} element(s)", 2000
        )

    def paste_elements(self):
        """Paste elements from clipboard with a small offset."""
        if not self._clipboard:
            return
        self.save_undo_state()
        new_elements = []
        for elem_dict in self._clipboard:
            new_el = ThemeElement.from_dict(elem_dict)
            new_el.x += 20
            new_el.y += 20
            new_el.name = f"{new_el.name}_copy"
            new_el.page = self.current_page
            self.elements.append(new_el)
            new_elements.append(new_el)
        self.element_list.set_elements(self.elements)
        self.refresh_canvas()
        # Select newly pasted elements
        self.canvas.set_selected_indices([self.elements.index(el) for el in new_elements])
        self.status_bar.showMessage(
            f"Pasted {len(new_elements)} element(s)", 2000
        )

    # ------------------------------------------------------------------ #
    #  Z-Order
    # ------------------------------------------------------------------ #

    def _get_selected_global_indices(self):
        """Canvas selection indices (already global into self.elements)."""
        return [i for i in self.canvas.selected_indices if 0 <= i < len(self.elements)]

    def bring_to_front(self):
        """Move selected elements to index 0 (front)."""
        indices = sorted(self._get_selected_global_indices())
        if not indices:
            return
        self.save_undo_state()
        selected_els = [self.elements[i] for i in indices]
        for el in selected_els:
            self.elements.remove(el)
        for i, el in enumerate(selected_els):
            self.elements.insert(i, el)
        self._refresh_after_zorder()

    def bring_forward(self):
        """Move selected elements one step toward front (lower index)."""
        indices = sorted(self._get_selected_global_indices())
        if not indices or indices[0] == 0:
            return
        self.save_undo_state()
        for idx in indices:
            if idx > 0:
                self.elements[idx], self.elements[idx - 1] = (
                    self.elements[idx - 1], self.elements[idx]
                )
        self._refresh_after_zorder()

    def send_backward(self):
        """Move selected elements one step toward back (higher index)."""
        indices = sorted(self._get_selected_global_indices(), reverse=True)
        if not indices or indices[0] == len(self.elements) - 1:
            return
        self.save_undo_state()
        for idx in indices:
            if idx < len(self.elements) - 1:
                self.elements[idx], self.elements[idx + 1] = (
                    self.elements[idx + 1], self.elements[idx]
                )
        self._refresh_after_zorder()

    def send_to_back(self):
        """Move selected elements to the end (back)."""
        indices = sorted(self._get_selected_global_indices(), reverse=True)
        if not indices:
            return
        self.save_undo_state()
        selected_els = [self.elements[i] for i in sorted(indices)]
        for el in selected_els:
            self.elements.remove(el)
        self.elements.extend(selected_els)
        self._refresh_after_zorder()

    def _refresh_after_zorder(self):
        self.element_list.set_elements(self.elements)
        self.refresh_canvas()
        self.status_bar.showMessage("Z-order updated", 1500)

    # ------------------------------------------------------------------ #
    #  Auto Profiles
    # ------------------------------------------------------------------ #

    def _start_profile_monitors(self):
        """Start foreground app monitor and system state monitor."""
        from src.utils.profiles import ForegroundAppMonitor, SystemStateMonitor

        if self._foreground_monitor is None:
            self._foreground_monitor = ForegroundAppMonitor()
            self._foreground_monitor.app_changed.connect(self._on_foreground_app_changed)
            if self._profile_manager.enabled:
                self._foreground_monitor.start()

        if self._system_state_monitor is None:
            self._system_state_monitor = SystemStateMonitor()
            self._system_state_monitor.state_changed.connect(self._on_system_state_changed)
            if self._profile_manager.system_profile_enabled:
                self._system_state_monitor.start()

    def _on_foreground_app_changed(self, process_name, window_title):
        """Handle foreground app change for profile switching."""
        preset_name = self._profile_manager.match_app(process_name, window_title)
        if preset_name:
            preset_data = self.presets_panel.get_preset_data_by_name(preset_name)
            if preset_data:
                self.load_preset(preset_data)
                self.status_bar.showMessage(
                    f"Auto profile: {preset_name} (app: {process_name})", 3000
                )

    def _on_system_state_changed(self, state):
        """Handle system state change (idle/gaming/normal) for profile switching."""
        if not self._profile_manager.system_profile_enabled:
            return
        preset_name = None
        if state == "idle":
            preset_name = self._profile_manager.system_idle_preset
        elif state == "gaming":
            preset_name = self._profile_manager.system_gaming_preset
        if preset_name:
            preset_data = self.presets_panel.get_preset_data_by_name(preset_name)
            if preset_data:
                self.load_preset(preset_data)
                self.status_bar.showMessage(
                    f"System state → {state}: loaded preset '{preset_name}'", 3000
                )

    def show_auto_profiles(self):
        """Show the Auto Profiles configuration dialog."""
        from src.utils.profiles import ProfileDialog
        available = self.presets_panel.get_preset_names()
        dialog = ProfileDialog(self._profile_manager, available, self)
        if dialog.exec():
            # Restart monitors based on new settings
            if self._foreground_monitor:
                if self._profile_manager.enabled:
                    if not self._foreground_monitor.isRunning():
                        self._foreground_monitor.start()
                else:
                    self._foreground_monitor.stop()

            if self._system_state_monitor:
                if self._profile_manager.system_profile_enabled:
                    if not self._system_state_monitor.isRunning():
                        self._system_state_monitor.start()
                else:
                    self._system_state_monitor.stop()

    def load_preset(self, preset_data):
        """Load a preset into the editor."""
        self.save_undo_state()

        self.theme_name = preset_data.get("name", "Untitled")
        self.theme_name_edit.setText(self.theme_name)
        self.background_color = preset_data.get("background_color", "#0f0f19")
        self.bg_color_btn.setStyleSheet(f"background-color: {self.background_color};")
        self.canvas.set_background_color(self.background_color)

        # Load elements
        self.elements = [
            ThemeElement.from_dict(e) for e in preset_data.get("elements", [])
        ]

        # Auto-scale elements if preset was created for different display dimensions
        # If no dimensions saved, assume it was created for the original wide display (1280x480)
        preset_width = preset_data.get("display_width", 1280)
        preset_height = preset_data.get("display_height", 480)

        if preset_width != constants.DISPLAY_WIDTH or preset_height != constants.DISPLAY_HEIGHT:
            # Calculate UNIFORM scale factor (same for X and Y to avoid distortion)
            # Use the smaller scale to ensure everything fits
            scale_x = constants.DISPLAY_WIDTH / preset_width
            scale_y = constants.DISPLAY_HEIGHT / preset_height
            scale = min(scale_x, scale_y)

            # Calculate centering offsets
            scaled_width = preset_width * scale
            scaled_height = preset_height * scale
            offset_x = (constants.DISPLAY_WIDTH - scaled_width) / 2
            offset_y = (constants.DISPLAY_HEIGHT - scaled_height) / 2

            logger.info(f"Auto-scaling preset from {preset_width}x{preset_height} to {constants.DISPLAY_WIDTH}x{constants.DISPLAY_HEIGHT}")
            logger.info(f"Uniform scale factor: {scale:.2f}, Offset: ({offset_x:.0f}, {offset_y:.0f})")

            # Scale all elements uniformly
            for element in self.elements:
                # Scale position and add centering offset
                element.x = int(element.x * scale + offset_x)
                element.y = int(element.y * scale + offset_y)

                # Scale size uniformly (for elements with width/height)
                if hasattr(element, 'width') and element.width > 0:
                    element.width = int(element.width * scale)
                if hasattr(element, 'height') and element.height > 0:
                    element.height = int(element.height * scale)

                # Scale radius uniformly (for circle gauges and analog clocks)
                if hasattr(element, 'radius') and element.type in ["circle_gauge", "analog_clock"]:
                    element.radius = int(element.radius * scale)

                # Scale font sizes uniformly
                if hasattr(element, 'font_size'):
                    element.font_size = max(8, int(element.font_size * scale))
                if hasattr(element, 'label_font_size'):
                    element.label_font_size = max(6, int(element.label_font_size * scale))

            self.status_bar.showMessage(f"Loaded and auto-scaled preset: {self.theme_name} ({preset_width}x{preset_height} → {constants.DISPLAY_WIDTH}x{constants.DISPLAY_HEIGHT}, scale: {scale:.2f}x)")
        else:
            self.status_bar.showMessage(f"Loaded preset: {self.theme_name}")

        self.element_list.set_elements(self.elements)
        self._rebuild_pages()
        self.properties_panel.set_element(None)
        self.canvas.set_selected_indices([])

        # Load video background settings if present
        video_data = preset_data.get("video_background", {})
        if video_data:
            video_background.from_dict(video_data)
        else:
            video_background.clear_video()
        self._update_video_ui()

    def on_preset_saved(self, preset_name):
        """Called when a preset is saved."""
        self.status_bar.showMessage(f"Preset saved: {preset_name}")

    def save_as_preset(self):
        """Save current theme as a preset with thumbnail snapshot."""
        theme_data = {
            "name": self.theme_name,
            "background_color": self.background_color,
            "display_width": constants.DISPLAY_WIDTH,
            "display_height": constants.DISPLAY_HEIGHT,
            "elements": [e.to_dict() for e in self.elements],
            "video_background": video_background.to_dict()
        }

        # Capture current frame as thumbnail
        thumbnail_image = None
        try:
            thumbnail_image = self.render_theme_image()
            # Convert to RGB if necessary (remove alpha channel for PNG efficiency)
            if thumbnail_image and thumbnail_image.mode == 'RGBA':
                thumbnail_image = thumbnail_image.convert('RGB')
        except Exception as e:
            logger.warning(f"Failed to capture thumbnail: {e}")

        self.presets_panel.save_preset(self.theme_name, theme_data, thumbnail_image)

    def quick_save(self):
        """Quick save to presets folder using current theme name."""
        if not self.theme_name or self.theme_name.strip() == "":
            self.status_bar.showMessage("Please enter a theme name first")
            return
        self.save_as_preset()
        self.status_bar.showMessage(f"Saved: {self.theme_name}")

    def update_element_list_name(self):
        self.element_list.refresh_list()

    def on_theme_name_changed(self, name):
        self.theme_name = name
        self.setWindowTitle(f"Thermal Engine - {name}")

    def choose_background_color(self):
        color = QColorDialog.getColor(QColor(self.background_color), self)
        if color.isValid():
            self.background_color = color.name()
            self.bg_color_btn.setStyleSheet(f"background-color: {color.name()};")
            self.canvas.set_background_color(color.name())
            self._schedule_autosave()

    def choose_video_background(self):
        """Select a video file for background."""
        if not HAS_CV2:
            QMessageBox.warning(
                self, "OpenCV Required",
                "Video backgrounds require OpenCV.\nRun: pip install opencv-python"
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video Background", "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.webm *.gif);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if path:
            # Update UI immediately
            filename = os.path.basename(path)
            if len(filename) > 12:
                filename = filename[:10] + "..."
            self.video_btn.setText(filename)
            self.video_btn.setToolTip(path)
            self.video_fit_combo.setEnabled(True)
            self.clear_video_btn.setEnabled(True)

            # Start loading with progress callback
            self.status_bar.showMessage(f"Loading video: {os.path.basename(path)}...")

            # Start a timer to update canvas during loading
            self._video_load_timer = QTimer(self)
            self._video_load_timer.timeout.connect(self._on_video_load_tick)
            self._video_load_timer.start(100)  # Update every 100ms

            if not video_background.load_video(path, callback=self._on_video_load_progress):
                self._video_load_timer.stop()
                QMessageBox.warning(self, "Error", f"Failed to load video:\n{path}")
                self.clear_video_background()

    def _on_video_load_tick(self):
        """Timer callback during video loading."""
        self.canvas.update()
        if not video_background.is_loading:
            self._video_load_timer.stop()

    def _on_video_load_progress(self, progress, done, error):
        """Callback for video loading progress."""
        if error:
            # Use QTimer to show message box from main thread
            QTimer.singleShot(0, lambda: self._show_video_error(error))
            return

        if done and not error:
            mem_mb = video_background.memory_usage_mb
            frames = video_background.frame_count
            fps = video_background.fps
            QTimer.singleShot(0, lambda: self.status_bar.showMessage(
                f"Video loaded: {frames} frames @ {fps:.1f}fps ({mem_mb:.1f} MB in memory)"
            ))

    def _show_video_error(self, error):
        """Show video load error (called from main thread)."""
        QMessageBox.warning(self, "Video Load Error", str(error))
        self.clear_video_background()

    def on_video_fit_changed(self, index):
        """Handle video fit mode change."""
        fit_mode = self.video_fit_combo.currentData()
        if fit_mode and fit_mode != video_background.fit_mode:
            self.status_bar.showMessage("Reloading video with new fit mode...")
            # Start timer to show loading progress
            if not hasattr(self, '_video_load_timer'):
                self._video_load_timer = QTimer(self)
                self._video_load_timer.timeout.connect(self._on_video_load_tick)
            self._video_load_timer.start(100)
            video_background.set_fit_mode(fit_mode)
        self.canvas.update()

    def clear_video_background(self):
        """Clear the video background."""
        # Stop load timer if running
        if hasattr(self, '_video_load_timer') and self._video_load_timer.isActive():
            self._video_load_timer.stop()
        video_background.clear_video()
        self.video_btn.setText("None")
        self.video_btn.setToolTip("")
        self.video_fit_combo.setEnabled(False)
        self.clear_video_btn.setEnabled(False)
        self.canvas.update()
        self.status_bar.showMessage("Video background cleared")

    def _update_video_ui(self):
        """Update video UI controls to match current video_background state."""
        if video_background.enabled:
            filename = os.path.basename(video_background.video_path)
            if len(filename) > 26:
                filename = filename[:24] + "\u2026"
            self.video_btn.setText(filename)
            self.video_btn.setToolTip(video_background.video_path)
            self.video_fit_combo.setEnabled(True)
            self.clear_video_btn.setEnabled(True)
            # Set fit mode in combo
            idx = self.video_fit_combo.findData(video_background.fit_mode)
            if idx >= 0:
                self.video_fit_combo.setCurrentIndex(idx)
        else:
            self.video_btn.setText("None")
            self.video_btn.setToolTip("")
            self.video_fit_combo.setEnabled(False)
            self.clear_video_btn.setEnabled(False)

    def new_theme(self):
        self.theme_path = None
        self.theme_name = "Untitled Theme"
        self.theme_name_edit.setText(self.theme_name)
        self.background_color = "#0f0f19"
        self.bg_color_btn.setStyleSheet(f"background-color: {self.background_color};")
        self.canvas.set_background_color(self.background_color)
        self.elements = []
        self.element_list.set_elements(self.elements)
        self._rebuild_pages()
        self.properties_panel.set_element(None)
        # Clear video background
        video_background.clear_video()
        self._update_video_ui()
        self.status_bar.showMessage("New theme created")

    def open_theme(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Theme", "",
            "Theme Files (*.json);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate theme schema before loading
                is_valid, errors = validate_preset_schema(data)
                if not is_valid:
                    QMessageBox.warning(self, "Invalid Theme",
                        f"Theme file has invalid format:\n{', '.join(errors[:5])}")
                    return

                self.theme_name = data.get("name", "Untitled")
                self.theme_name_edit.setText(self.theme_name)
                self.background_color = data.get("background_color", "#0f0f19")
                self.bg_color_btn.setStyleSheet(f"background-color: {self.background_color};")
                self.canvas.set_background_color(self.background_color)

                self.elements = [
                    ThemeElement.from_dict(e) for e in data.get("elements", [])
                ]
                self.element_list.set_elements(self.elements)
                self._rebuild_pages()

                # Load video background settings
                video_data = data.get("video_background", {})
                if video_data:
                    video_background.from_dict(video_data)
                    self._update_video_ui()
                else:
                    video_background.clear_video()
                    self._update_video_ui()

                self.theme_path = path
                self.status_bar.showMessage(f"Opened: {path}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open theme:\n{e}")

    def save_theme(self):
        if self.theme_path:
            self._save_to_path(self.theme_path)
        else:
            self.save_theme_as()

    def save_theme_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Theme", f"{self.theme_name}.json",
            "Theme Files (*.json);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if path:
            self._save_to_path(path)

    def _save_to_path(self, path):
        try:
            data = {
                "name": self.theme_name,
                "background_color": self.background_color,
                "display_width": constants.DISPLAY_WIDTH,
                "display_height": constants.DISPLAY_HEIGHT,
                "elements": [e.to_dict() for e in self.elements],
                "video_background": video_background.to_dict()
            }

            write_json_atomic(path, data)

            self.theme_path = path
            self.status_bar.showMessage(f"Saved: {path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save theme:\n{e}")

    def export_image(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Image", f"{self.theme_name}.png",
            "PNG Image (*.png);;JPEG Image (*.jpg)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if path:
            try:
                img = self.render_theme_image()
                img.save(path)
                self.status_bar.showMessage(f"Exported: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export image:\n{e}")

    def export_theme_package(self):
        """Export current theme as a .thermal package with embedded assets."""
        from src.utils.theme_package import export_theme, THERMAL_EXTENSION

        default_name = f"{self.theme_name}{THERMAL_EXTENSION}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Theme Package", default_name,
            f"Thermal Theme (*{THERMAL_EXTENSION});;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if not path:
            return

        if not path.endswith(THERMAL_EXTENSION):
            path += THERMAL_EXTENSION

        theme_data = {
            "name": self.theme_name,
            "background_color": self.background_color,
            "display_width": constants.DISPLAY_WIDTH,
            "display_height": constants.DISPLAY_HEIGHT,
            "elements": [e.to_dict() for e in self.elements],
            "video_background": video_background.to_dict()
        }

        thumbnail_image = None
        try:
            thumbnail_image = self.render_theme_image()
        except Exception:
            pass

        success, result = export_theme(theme_data, thumbnail_image, path)
        if success:
            self.status_bar.showMessage(f"Theme exported: {os.path.basename(path)}", 3000)
        else:
            QMessageBox.critical(self, "Export Failed", f"Failed to export theme:\n{result}")

    def import_theme_package(self):
        """Import a .thermal or .zip theme package."""
        from src.utils.theme_package import import_theme, THERMAL_EXTENSION

        path, _ = QFileDialog.getOpenFileName(
            self, "Import Theme Package", "",
            f"Theme Packages (*{THERMAL_EXTENSION} *.zip);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if not path:
            return

        success, error, theme_data = import_theme(path)
        if not success:
            QMessageBox.critical(self, "Import Failed", f"Failed to import theme:\n{error}")
            return

        self.load_preset(theme_data)
        self.theme_path = None
        self.status_bar.showMessage(f"Imported theme: {theme_data.get('name', 'Unknown')}", 3000)

        reply = QMessageBox.question(
            self, "Save as Preset?",
            f"Theme '{theme_data.get('name', 'Unknown')}' imported successfully.\n\n"
            "Would you like to save it as a preset?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.save_as_preset()

    def export_theme_zip(self):
        """Export current theme as a standard .zip archive with embedded images."""
        from src.utils.theme_package import export_theme

        default_name = f"{self.theme_name}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Theme as ZIP", default_name,
            "ZIP Archive (*.zip);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if not path:
            return

        if not path.endswith(".zip"):
            path += ".zip"

        theme_data = {
            "name": self.theme_name,
            "background_color": self.background_color,
            "display_width": constants.DISPLAY_WIDTH,
            "display_height": constants.DISPLAY_HEIGHT,
            "elements": [e.to_dict() for e in self.elements],
            "video_background": video_background.to_dict()
        }

        thumbnail_image = None
        try:
            thumbnail_image = self.render_theme_image()
        except Exception:
            pass

        success, result = export_theme(theme_data, thumbnail_image, path)
        if success:
            self.status_bar.showMessage(
                f"Theme exported as ZIP: {os.path.basename(path)}", 3000
            )
        else:
            QMessageBox.critical(self, "Export Failed", f"Failed to export theme:\n{result}")

    def get_sensor_data(self):
        """Get all metrics from the single background sensor sampler."""
        data = {
            'static': 50,
            'cpu_percent': 0,
            'cpu_temp': 0,
            'cpu_clock': 0,
            'cpu_power': 0,
            'gpu_percent': 0,
            'gpu_temp': 0,
            'gpu_clock': 0,
            'gpu_memory_percent': 0,
            'gpu_memory_clock': 0,
            'gpu_power': 0,
            'ram_percent': 0,
            'ram_used': 0,
            'ram_available': 0,
            'net_upload': 0,
            'net_download': 0,
        }
        data.update(get_cached_sensors())
        return data

    def diagnose_sensors(self):
        """Show diagnostic information about available sensors."""
        QMessageBox.information(
            self,
            "Sensor Diagnostic",
            self.build_diagnostic_report(),
        )

    def build_diagnostic_report(self):
        """Build a support-ready report without secrets or user file contents."""
        info = []
        info.append("=== ThermalEngine Diagnostic ===")

        try:
            from src.utils.app_version import __version__
        except ImportError:
            __version__ = "unknown"

        device = self.selected_device_def
        info.append(f"Version: {__version__}")
        info.append(f"Platform: {platform.platform()}")
        info.append(f"Python: {platform.python_version()}")
        info.append(
            f"Display: {device.name} ({device.backend_type})"
            if device else "Display: not connected"
        )
        if device:
            default_size = getattr(
                self,
                "_selected_device_default_size",
                None,
            ) or (
                device.width,
                device.height,
            )
            size_mode = (
                "device default"
                if (device.width, device.height) == tuple(default_size)
                else "custom override"
            )
            info.append(
                f"Output size: {device.width}x{device.height} ({size_mode})"
            )
        info.append(f"Target FPS: {self.target_fps}")
        info.append(f"Log file: {get_user_data_path('ThermalEngine.log')}")
        if self._frame_error:
            info.append(f"Last frame error: {self._frame_error}")
        info.append("\n=== Sensors ===")

        source = sensors.get_sensor_source_display() if hasattr(sensors, 'get_sensor_source_display') else "Unknown"
        sensor_diag = sensors.get_sensor_diagnostics() if hasattr(sensors, 'get_sensor_diagnostics') else {}

        info.append(f"Sensor source: {source}")
        info.append(f"Sensor platform: {sensor_diag.get('platform', 'unknown')}")
        info.append(f"Reader source: {sensor_diag.get('source', 'unknown')}")
        info.append(f"Backend: {sensor_diag.get('backend', 'unknown')}")
        info.append("")

        thermal_available = sensor_diag.get("thermal_available", False)
        info.append(f"Thermal sensors available: {thermal_available}")
        info.append(
            "CPU temperature: "
            + (
                "available"
                if sensor_diag.get("cpu_thermal_available")
                else f"unavailable ({sensor_diag.get('cpu_thermal_reason') or 'unknown'})"
            )
        )
        info.append(
            "GPU temperature: "
            + (
                "available"
                if sensor_diag.get("gpu_thermal_available")
                else f"unavailable ({sensor_diag.get('gpu_thermal_reason') or 'unknown'})"
            )
        )
        info.append(f"Degraded: {sensor_diag.get('degraded', True)}")
        info.append(f"Reason: {sensor_diag.get('reason') or 'none'}")
        info.append(f"CPU temp source: {sensor_diag.get('cpu_temp_source') or 'not found'}")
        info.append(f"GPU source: {sensor_diag.get('gpu_source') or 'not found'}")
        if sensor_diag.get('gpu_card'):
            info.append(f"GPU card: {sensor_diag['gpu_card']}")
        if sensor_diag.get('sensor_error'):
            info.append(f"Last error: {sensor_diag['sensor_error']}")
        info.append("")

        if thermal_available:
            info.append("Sensor readings:")
            info.append("-" * 40)
            for key, value in get_cached_sensors().items():
                info.append(f"  {key}: {value}")
        else:
            info.append("Usage metrics remain available; CPU/GPU temperatures are unavailable.")
            if sys.platform == "win32":
                info.append("Install PawnIO or restart as administrator, then check again.")

        notes = sensor_diag.get('notes') or []
        if notes:
            info.append("")
            info.append("Backend notes:")
            info.append("-" * 40)
            for note in notes:
                info.append(f"  - {note}")

        info.append("\n" + "-" * 40)
        info.append("Current sensor values:")
        data = self.get_sensor_data()
        for key, value in data.items():
            info.append(f"  {key}: {value}")

        return "\n".join(info)

    def copy_diagnostic_report(self):
        """Copy the diagnostic report for support requests."""
        QApplication.clipboard().setText(self.build_diagnostic_report())
        self.status_bar.showMessage("Diagnostic report copied", 2500)

    def toggle_connection(self):
        """Toggle between connected and disconnected states."""
        if self.backend:
            # User manually disconnecting - stop any auto-reconnect
            if self._reconnect_timer:
                self._reconnect_timer.stop()
                self._reconnect_timer = None
            self._was_connected_before_sleep = False
            self.disconnect_display()
        else:
            self.connect_display()

    def select_device(self):
        """Show device selection dialog."""
        available = enumerate_available_devices()

        if not available:
            QMessageBox.warning(
                self,
                "No Devices Found",
                "No supported display devices detected.\n\n"
                "Make sure your display is connected and not in use by other software."
            )
            return None

        # If only one device, auto-select it
        if len(available) == 1:
            return available[0]

        # Multiple devices - show selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Display Device")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        label = QLabel("Multiple display devices detected. Please select one:")
        label.setWordWrap(True)
        layout.addWidget(label)

        device_combo = QComboBox()
        for dev in available:
            exp_tag = " [EXPERIMENTAL]" if dev.experimental else ""
            device_combo.addItem(f"{dev.name}{exp_tag}", dev)
        layout.addWidget(device_combo)

        # Warning for experimental devices
        if any(dev.experimental for dev in available):
            warning = QLabel(
                "⚠️ EXPERIMENTAL devices have incomplete protocol support.\n"
                "Display output may not work until the protocol is reverse-engineered."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #ff9800; padding: 10px; background: #2d2d2d; border-radius: 4px;")
            layout.addWidget(warning)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return device_combo.currentData()

        return None

    def _apply_saved_display_size(self):
        """Apply a per-device size override before creating the backend."""
        device = self.selected_device_def
        if device is None:
            return

        if self._selected_device_default_size is None:
            self._selected_device_default_size = (device.width, device.height)

        default_width, default_height = self._selected_device_default_size
        override = get_device_size_override(
            settings.get_setting("display_size_overrides", {}),
            device,
        )
        device.extra_params["manual_size_override"] = override is not None
        device.width, device.height = override or (default_width, default_height)

    def _recreate_canvas_for_display(self):
        """Recreate the preview after its physical aspect ratio changes."""
        old_canvas = self.canvas
        selected_indices = list(getattr(old_canvas, "selected_indices", []))
        show_grid = getattr(old_canvas, "show_grid", True)
        snap_to_grid = getattr(old_canvas, "snap_to_grid", True)

        self.canvas = CanvasPreview()
        self.canvas.frame_renderer = self._render_preview_frame
        self.canvas.set_background_color(self.background_color)
        self.canvas.set_elements(self.elements, self.current_page)
        self.canvas.set_show_grid(show_grid)
        self.canvas.set_snap_to_grid(snap_to_grid)
        self.canvas.set_selected_indices(selected_indices)

        canvas_wrapper = old_canvas.parent()
        canvas_wrapper.layout().replaceWidget(old_canvas, self.canvas)
        old_canvas.deleteLater()

        self._connect_canvas_signals()

    def _update_zoom_label(self):
        percent = f"{round(self.canvas.scale * 100)}%"
        self.zoom_btn.setText(f"Fit \u00b7 {percent}" if self.canvas.zoom is None else percent)

    def _set_display_size(self, width, height, stretch_layout=False):
        """Apply output dimensions to rendering, preview, presets, and backend."""
        width, height = validate_display_size(width, height)
        old_size = (constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT)
        new_size = (width, height)
        if old_size == new_size:
            return

        was_streaming = self.live_preview_timer is not None
        if was_streaming:
            self.stop_continuous_send()

        if stretch_layout and self.elements:
            self.save_undo_state()
            resize_theme_elements(self.elements, old_size, new_size)
            self.element_list.set_elements(self.elements)
            self.properties_panel.set_element(None)

        constants.DISPLAY_WIDTH = width
        constants.DISPLAY_HEIGHT = height

        if self.selected_device_def:
            self.selected_device_def.width = width
            self.selected_device_def.height = height
        if self.backend:
            self.backend.device_def.width = width
            self.backend.device_def.height = height

        self.presets_panel.set_display_resolution(width, height)
        self._update_display_size_label()

        self.renderer.clear_cache()
        self._recreate_canvas_for_display()

        if video_background.enabled and video_background.video_path:
            video_background.load_video(video_background.video_path)

        self._schedule_autosave()
        self.status_bar.showMessage(
            f"Display size set to {width}x{height}"
            + ("; current theme stretched to fit" if stretch_layout else ""),
            4000,
        )
        if was_streaming and self.backend:
            self.start_continuous_send()

    def show_display_size_dialog(self):
        """Choose a known or custom physical output size for the active device."""
        if not self.selected_device_def:
            QMessageBox.information(
                self,
                "Screen Size",
                "Connect or select a display before choosing its screen size.",
            )
            return

        default_size = self._selected_device_default_size or (
            self.selected_device_def.width,
            self.selected_device_def.height,
        )
        current_size = (
            constants.DISPLAY_WIDTH,
            constants.DISPLAY_HEIGHT,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Screen Size")
        dialog.setMinimumWidth(470)
        layout = QVBoxLayout(dialog)

        description = QLabel(
            "Thermalright reuses the same USB identifier for panels with "
            "different resolutions. Choose the panel's native size; use "
            "640×360 for a 16:9 Stream Vision variant, or enter a custom size."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        profile_combo = QComboBox()
        profile_combo.addItem(
            f"Device default ({default_size[0]} × {default_size[1]})",
            "default",
        )
        for label, width, height in DISPLAY_SIZE_PROFILES:
            profile_combo.addItem(label, (width, height))
        profile_combo.addItem("Custom", "custom")
        form.addRow("Profile:", profile_combo)

        width_spin = QSpinBox()
        width_spin.setRange(160, 4096)
        width_spin.setValue(current_size[0])
        form.addRow("Width:", width_spin)

        height_spin = QSpinBox()
        height_spin.setRange(160, 4096)
        height_spin.setValue(current_size[1])
        form.addRow("Height:", height_spin)
        layout.addLayout(form)

        stretch_checkbox = QCheckBox(
            "Stretch the current theme to fill the new screen"
        )
        stretch_checkbox.setChecked(True)
        layout.addWidget(stretch_checkbox)

        def update_profile_fields():
            value = profile_combo.currentData()
            if value == "default":
                value = default_size
            editable = value == "custom"
            if not editable:
                width_spin.setValue(value[0])
                height_spin.setValue(value[1])
            width_spin.setEnabled(editable)
            height_spin.setEnabled(editable)

        initial_index = profile_combo.findData(
            "default" if current_size == tuple(default_size) else current_size
        )
        if initial_index < 0:
            initial_index = profile_combo.findData("custom")
        profile_combo.setCurrentIndex(initial_index)
        profile_combo.currentIndexChanged.connect(update_profile_fields)
        update_profile_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_profile = profile_combo.currentData()
        width, height = validate_display_size(
            width_spin.value(),
            height_spin.value(),
        )
        overrides = dict(settings.get_setting("display_size_overrides", {}))
        key = device_size_key(self.selected_device_def)
        if selected_profile == "default":
            overrides.pop(key, None)
        else:
            overrides[key] = [width, height]
        settings.set_setting("display_size_overrides", overrides)
        self._set_display_size(
            width,
            height,
            stretch_layout=stretch_checkbox.isChecked(),
        )

    def connect_display(self, show_error=True):
        """Connect to display using new backend system."""
        # Check if already connected - don't create duplicate backend!
        if self.backend and self.backend.is_connected():
            logger.info("Display already connected, skipping reconnect")
            return True

        # Select device if not already selected
        if not self.selected_device_def:
            selected_device = self.select_device()
            if not selected_device:
                return False  # User cancelled
            self._selected_device_default_size = (
                selected_device.width,
                selected_device.height,
            )
            self.selected_device_def = copy.copy(selected_device)
            self.selected_device_def.extra_params = dict(
                selected_device.extra_params
            )

        self._apply_saved_display_size()

        # Show experimental warning
        if self.selected_device_def.experimental and show_error:
            reply = QMessageBox.question(
                self,
                "Experimental Device",
                f"⚠️ {self.selected_device_def.name} support is EXPERIMENTAL.\n\n"
                "This device's protocol is not yet fully understood.\n"
                "Display output may not work correctly.\n\n"
                "A console window will open to show detailed logs for debugging.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.selected_device_def = None
                return False

            # Show console window for experimental devices
            self.show_console()

        try:
            # Create backend
            self.backend = create_backend(self.selected_device_def)
            if not self.backend:
                if show_error:
                    QMessageBox.critical(self, "Error", "Failed to create device backend.")
                return False

            # Connect
            if not self.backend.connect():
                if show_error:
                    QMessageBox.critical(
                        self,
                        "Connection Failed",
                        f"Failed to connect to {self.selected_device_def.name}.\n\n"
                        "Make sure the device is connected and not in use by other software."
                    )
                self.backend = None
                return False

            if not self.selected_device_def.extra_params.get(
                "manual_size_override",
                False,
            ):
                self._selected_device_default_size = (
                    self.selected_device_def.width,
                    self.selected_device_def.height,
                )

            # Set legacy device reference for compatibility
            self.device = self.backend  # Acts as a flag for connected state

            self._set_display_size(
                self.selected_device_def.width,
                self.selected_device_def.height,
            )
            # _set_display_size returns early when the startup defaults already
            # match, but the preset filter still needs the effective device size.
            self.presets_panel.set_display_resolution(
                self.selected_device_def.width,
                self.selected_device_def.height,
            )
            logger.info(
                "Display dimensions set to "
                f"{constants.DISPLAY_WIDTH}x{constants.DISPLAY_HEIGHT}"
            )
            logger.info("Canvas recreated with device dimensions")

            # Update button text to "Disconnect"
            self.connect_action.setText("Disconnect")
            self.send_action.setEnabled(True)

            psutil.cpu_percent(interval=None)

            self.frame_times = []
            self.last_frame_time = 0
            self._last_frame_request_time = 0

            self.start_continuous_send()

            # Stop reconnect timer if running (successful connection)
            if self._reconnect_timer:
                self._reconnect_timer.stop()
                self._reconnect_timer = None
            self._was_connected_before_sleep = False
            self._reconnect_attempts = 0

            status_msg = f"Connected to {self.selected_device_def.name} ({constants.DISPLAY_WIDTH}x{constants.DISPLAY_HEIGHT})"
            if self.selected_device_def.experimental:
                status_msg += " [experimental]"
            self.status_bar.showMessage(status_msg)
            self.update_performance_stats()
            return True

        except Exception as e:
            logger.error(f"Exception during connect_display: {e}", exc_info=True)
            if show_error:
                QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")
            self.backend = None
            self.device = None
            return False

    def disconnect_display(self):
        """Disconnect from display using backend system."""
        self.stop_continuous_send()

        if self.backend:
            try:
                self.backend.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting backend: {e}")
            finally:
                self.backend = None
                self.device = None  # Clear legacy reference

        self.frame_times = []
        self.last_frame_time = 0
        self._last_frame_request_time = 0

        # Update button text to "Connect"
        try:
            self.connect_action.setText("Connect")
            self.send_action.setEnabled(False)
            self.status_bar.showMessage("Disconnected")
            self.update_performance_stats()
        except:
            pass  # UI might not be available during shutdown

    def set_target_fps(self, fps):
        # Show warning for 60 FPS if not suppressed
        if fps == 60 and not settings.get_setting("suppress_60fps_warning", False):
            if not self._show_60fps_warning():
                # User declined - revert to previous FPS selection
                for action in self.fps_actions:
                    action.setChecked(action.text() == f"{self.target_fps} FPS")
                return

        self.target_fps = fps
        settings.set_setting("target_fps", fps)  # Persist across relaunches

        for action in self.fps_actions:
            action.setChecked(action.text() == f"{fps} FPS")

        if self.live_preview_timer and self.live_preview_timer.isActive():
            # Calculate interval with proper rounding for accurate FPS
            interval = round(1000 / self.target_fps)
            self.live_preview_timer.setTimerType(Qt.TimerType.PreciseTimer)  # More accurate timing
            self.live_preview_timer.setInterval(interval)

        self.status_bar.showMessage(f"Frame rate set to {fps} FPS")

    def _show_60fps_warning(self):
        """Show warning dialog for 60 FPS mode. Returns True if user accepts."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Performance Warning")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        # Warning message
        warning_label = QLabel(
            "<b>60 FPS Mode</b><br><br>"
            "Running at 60 FPS significantly increases CPU usage and may cause:<br><br>"
            "• Higher CPU temperatures<br>"
            "• Reduced battery life on laptops<br>"
            "• Potential frame drops on older hardware<br>"
            "• Less headroom for other applications<br><br>"
            "<b>Recommended:</b> Use 30 FPS for smooth performance on most systems."
        )
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Don't show again checkbox
        dont_show_checkbox = QCheckBox("Don't show this warning again")
        layout.addWidget(dont_show_checkbox)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Continue with 60 FPS")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Save preference if checkbox is checked
            if dont_show_checkbox.isChecked():
                settings.set_setting("suppress_60fps_warning", True)
            return True
        return False

    def set_display_orientation(self, orientation):
        """Set display orientation (normal, flip_v, flip_h, rotate_180, rotate_90_cw, rotate_90_ccw)."""
        self.display_orientation = orientation
        settings.set_setting("display_orientation", orientation)

        # Update checkmarks
        for action, value in self.orientation_actions:
            action.setChecked(value == orientation)

        self.status_bar.showMessage(f"Display orientation: {orientation.replace('_', ' ').title()}")

    def set_display_brightness(self, brightness):
        self.display_brightness = brightness
        settings.set_setting("display_brightness", brightness)
        for action, value in self.brightness_actions:
            action.setChecked(value == brightness)
        self.status_bar.showMessage(f"Display brightness: {brightness}%")

    def toggle_show_grid(self, checked):
        """Toggle grid visibility."""
        self.canvas.set_show_grid(checked)
        settings.set_setting("show_grid", checked)
        self.status_bar.showMessage(f"Grid: {'Shown' if checked else 'Hidden'}")

    def toggle_snap_to_grid(self, checked):
        """Toggle snap to grid."""
        self.canvas.set_snap_to_grid(checked)
        settings.set_setting("snap_to_grid", checked)
        self.status_bar.showMessage(f"Snap to Grid: {'Enabled' if checked else 'Disabled'}")

    def update_page_tabs(self):
        """Update page combo box with current pages."""
        self.page_tabs.blockSignals(True)
        while self.page_tabs.count():
            self.page_tabs.removeTab(0)
        for page in self.pages:
            self.page_tabs.addTab(page["name"])
        # Select current page
        for i, page in enumerate(self.pages):
            if page["number"] == self.current_page:
                self.page_tabs.setCurrentIndex(i)
                break
        self.page_tabs.setTabsClosable(len(self.pages) > 1)  # The last page can't be deleted
        self.page_tabs.blockSignals(False)
        self._page_preview_timer.start()

    def _update_page_thumbnails(self):
        for index, page in enumerate(self.pages):
            snapshot = self._capture_render_snapshot(page=page["number"])
            frame = self.render_theme_image(snapshot=snapshot)
            frame.thumbnail((96, 48), Image.Resampling.LANCZOS)
            data = frame.tobytes("raw", "RGB")
            image = QImage(data, frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888)
            self.page_tabs.setTabIcon(index, QIcon(QPixmap.fromImage(image)))

    def _show_page(self, number):
        """Make `number` the edited page in the window, element list and canvas."""
        self.current_page = number
        self.element_list.current_page = number
        self.element_list.refresh_list(preserve_state=False)
        self.canvas.set_selected_indices([])
        self.properties_panel.set_element(None)
        self._do_refresh_canvas()

    def _rebuild_pages(self, keep_existing=False):
        """Derive the page list from elements (themes only persist element.page).

        keep_existing=False is for a freshly loaded theme: reset to its first page.
        """
        numbers = {getattr(e, 'page', 1) for e in self.elements} | {1}
        if keep_existing:
            numbers |= {p["number"] for p in self.pages}
        self.pages = [{"name": f"Page {n}", "number": n} for n in sorted(numbers)]
        if not keep_existing or self.current_page not in numbers:
            self.current_page = min(numbers)
        self.update_page_tabs()
        self._show_page(self.current_page)

    def on_page_changed(self, index):
        """Handle page selection change."""
        if index >= 0 and index < len(self.pages):
            self._show_page(self.pages[index]["number"])
            self.status_bar.showMessage(f"Switched to {self.pages[index]['name']}")

    def add_page(self):
        """Add a new page."""
        new_page_num = max(p["number"] for p in self.pages) + 1 if self.pages else 1
        new_page = {"name": f"Page {new_page_num}", "number": new_page_num}
        self.pages.append(new_page)
        self.update_page_tabs()
        # Switch to new page
        self.page_tabs.setCurrentIndex(len(self.pages) - 1)
        self.status_bar.showMessage(f"Created {new_page['name']}")

    def delete_page(self, current_index):
        """Delete the page at tab `current_index` (if not the last one)."""
        if len(self.pages) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the last page.")
            return

        page_to_delete = self.pages[current_index]

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Page",
            f"Delete {page_to_delete['name']}? All elements on this page will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.save_undo_state()
            # Remove elements on this page
            self.elements = [el for el in self.elements if getattr(el, 'page', 1) != page_to_delete["number"]]
            self.pages.pop(current_index)
            # Closing another tab keeps the current page; closing this one moves to a neighbor
            if self.current_page == page_to_delete["number"]:
                self.current_page = self.pages[max(0, current_index - 1)]["number"]
            self.update_page_tabs()
            self.element_list.set_elements(self.elements)
            self._show_page(self.current_page)
            self.status_bar.showMessage(f"Deleted {page_to_delete['name']}")

    def toggle_auto_rotate(self, checked):
        """Toggle auto-rotation of pages."""
        self.auto_rotate_pages = checked
        if checked:
            self.start_page_rotation()
        else:
            self.stop_page_rotation()
        self.status_bar.showMessage(f"Auto-Rotate: {'Enabled' if checked else 'Disabled'}")

    def set_rotation_interval(self, value):
        """Set page rotation interval in seconds."""
        self.page_rotation_interval = value
        if self.auto_rotate_pages:
            # Restart timer with new interval
            self.start_page_rotation()

    def start_page_rotation(self):
        """Start auto-rotation timer."""
        if self.page_rotation_timer:
            self.page_rotation_timer.stop()
        self.page_rotation_timer = QTimer()
        self.page_rotation_timer.timeout.connect(self.rotate_to_next_page)
        self.page_rotation_timer.start(self.page_rotation_interval * 1000)

    def stop_page_rotation(self):
        """Stop auto-rotation timer."""
        if self.page_rotation_timer:
            self.page_rotation_timer.stop()
            self.page_rotation_timer = None

    def rotate_to_next_page(self):
        """Rotate to next page (wraps around to first page)."""
        current_index = self.page_tabs.currentIndex()
        next_index = (current_index + 1) % len(self.pages)
        self.page_tabs.setCurrentIndex(next_index)

    def _start_render_thread(self):
        """Start the one-slot latest-frame worker."""
        if self._render_thread and self._render_thread.is_alive():
            return

        self._frame_error = None
        self._render_thread_running = True
        self._render_thread = threading.Thread(target=self._render_thread_loop, daemon=True)
        self._render_thread.start()

    def _stop_render_thread(self):
        """Stop background render thread."""
        self._render_thread_running = False
        self._frame_request.set()
        if self._render_thread:
            self._render_thread.join(timeout=2.0)
            self._render_thread = None
        self._frame_request.clear()

    def _render_thread_loop(self):
        """Render, encode, and send only the latest requested frame."""
        while self._render_thread_running:
            self._frame_request.wait(timeout=0.5)
            if not self._render_thread_running:
                break
            if not self._frame_request.is_set():
                continue
            self._frame_request.clear()
            try:
                if self.backend and self.backend.is_connected():
                    with self._frame_snapshot_lock:
                        snapshot = self._frame_snapshot
                        self._frame_snapshot = None
                    if snapshot is None:
                        continue
                    img = self.render_theme_image(snapshot=snapshot)
                    jpeg_data = self.image_to_jpeg(img)
                    self.send_jpeg_frame(jpeg_data)
                    self.record_frame_time()
            except Exception as e:
                self._frame_error = e

    def _capture_render_snapshot(self, page=None):
        """Copy GUI-owned render state before handing it to the worker."""
        sensor_data = self.get_sensor_data()
        elements = []
        page_elements = (self.get_current_page_elements() if page is None else
                         [element for element in self.elements if element.page == page])
        for element in page_elements:
            data = element.to_dict()
            if element.source.startswith("network_") and element.source not in sensor_data:
                data["value"] = 0
                element.value = 0
            if element.source != "static" and element.source in sensor_data:
                data["value"] = sensor_data[element.source]
                element.value = data["value"]
            if element.animate_gauge:
                data["value"] = self._animated_value(element, float(data["value"]))
            elements.append((id(element), data))
        return {
            "background_color": self.background_color,
            "elements": elements,
            "sensor_data": sensor_data,
        }

    def _animated_value(self, element, target):
        """Ease the shown gauge value toward target, independent of frame rate.

        Both the editor preview and the device loop call this (GUI thread only).
        """
        now = time.perf_counter()
        current, last = self._animated_values.get(id(element), (target, now))
        dt = min(now - last, 0.5)
        diff = target - current
        # Bigger jumps move faster (ease-out), tuned as a per-1/60s step like the old canvas
        speed = min(0.9, element.animation_speed * (1.0 + min(1.0, abs(diff) / 50.0) * 2.0))
        current += diff * (1 - (1 - speed) ** (dt * 60))
        if abs(target - current) < 0.05:
            current = target
        self._animated_values[id(element)] = (current, now)
        return current

    def _render_preview_frame(self):
        """Editor canvas frame: the same image the device receives."""
        return self.render_theme_image(snapshot=self._capture_render_snapshot())

    def _tick_preview(self):
        # While connected, send_frame_with_sensors already refreshes the canvas
        if self.live_preview_timer is None and self.isVisible() and not self.isMinimized():
            self.canvas.update()

    def start_continuous_send(self):
        interval = round(1000 / self.target_fps)
        self._frame_deadline = time.perf_counter()
        self._last_frame_request_time = 0
        self._frames_skipped = 0
        self._start_render_thread()

        if self.live_preview_timer is None:
            self.live_preview_timer = QTimer(self)
            self.live_preview_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.live_preview_timer.timeout.connect(self.send_frame_with_sensors)
            self.live_preview_timer.start(interval)
        else:
            self.live_preview_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.live_preview_timer.setInterval(interval)
            self.live_preview_timer.start()

    def stop_continuous_send(self):
        if self.live_preview_timer:
            self.live_preview_timer.stop()
            self.live_preview_timer = None

        self._stop_render_thread()

    def send_to_display(self):
        self.send_frame_with_sensors()

    def send_frame_with_sensors(self):
        if not self.device:
            return

        try:
            if self._frame_error is not None:
                error = self._frame_error
                self._frame_error = None
                raise error

            current_time = time.perf_counter()
            frame_interval = 1.0 / self.target_fps
            min_frame_interval = frame_interval * 0.9
            if (
                self._last_frame_request_time > 0
                and current_time - self._last_frame_request_time < min_frame_interval
            ):
                return

            if self._frame_request.is_set():
                self._frames_skipped += 1
            snapshot = self._capture_render_snapshot()
            with self._frame_snapshot_lock:
                self._frame_snapshot = snapshot
            self._frame_request.set()
            self._last_frame_request_time = current_time

            self._canvas_update_counter += 1
            if self._canvas_update_counter >= self._canvas_update_interval:
                self._canvas_update_counter = 0
                self.canvas.set_elements(self.elements, self.current_page)
                self.canvas.update()

        except DeviceIOError as e:
            logger.warning(f"Device error, disconnecting: {e}")
            self.disconnect_display()
            self._was_connected_before_sleep = True
            self._reconnect_attempts = 0
            self._start_reconnect_timer()
            self.status_bar.showMessage("Display disconnected - attempting to reconnect...")
        except Exception as e:
            logger.exception("Frame render error")
            self.status_bar.showMessage(f"Error: {e}")

    def get_current_page_elements(self):
        """Get elements for current page."""
        return [el for el in self.elements if getattr(el, 'page', 1) == self.current_page]

    def render_theme_image(self, snapshot=None):
        if snapshot is None:
            snapshot = self._capture_render_snapshot()
        background_frame = video_background.get_frame_pil() if video_background.enabled else None
        return self.renderer.render(
            snapshot, (constants.DISPLAY_WIDTH, constants.DISPLAY_HEIGHT), background_frame
        )

    def image_to_jpeg(self, img, quality=80):
        """Convert image to JPEG bytes with optimized settings."""
        if self.display_brightness < 100:
            img = ImageEnhance.Brightness(img).enhance(self.display_brightness / 100)

        # Apply display orientation transformation
        if self.display_orientation == "flip_v":
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif self.display_orientation == "flip_h":
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif self.display_orientation == "rotate_180":
            img = img.transpose(Image.ROTATE_180)
        elif self.display_orientation == "rotate_90_cw":
            img = img.transpose(Image.ROTATE_270)  # PIL uses counter-clockwise, so 270 = 90 CW
        elif self.display_orientation == "rotate_90_ccw":
            img = img.transpose(Image.ROTATE_90)

        buffer = io.BytesIO()
        # Use quality=80 and optimize=False for faster encoding
        # The LCD display doesn't need highest quality
        img.save(buffer, format='JPEG', quality=quality, optimize=False, subsampling=2)
        return buffer.getvalue()

    def send_jpeg_frame(self, jpeg_data):
        """Send JPEG frame to display via backend."""
        if not self.backend:
            raise DeviceIOError("Device not connected")

        # Build frame data according to protocol
        # For HID devices (Thermalright Trofeo): Use known protocol with header + chunks
        # For experimental USB devices: Send raw frame data (protocol unknown)

        if self.selected_device_def.backend_type == 'hid':
            # HID Protocol for Thermalright Trofeo
            MAGIC = bytes([0xDA, 0xDB, 0xDC, 0xDD])

            header = bytearray(512)
            header[0:4] = MAGIC
            header[4] = 0x02
            header[8:12] = bytes([0x00, 0x05, 0xE0, 0x01])
            header[12] = 0x02

            jpeg_len = len(jpeg_data)
            header[16] = jpeg_len & 0xFF
            header[17] = (jpeg_len >> 8) & 0xFF
            header[18] = (jpeg_len >> 16) & 0xFF
            header[19] = (jpeg_len >> 24) & 0xFF

            first_chunk = min(len(jpeg_data), 492)
            header[20:20 + first_chunk] = jpeg_data[:first_chunk]

            try:
                # Send header
                if not self.backend.send_frame(bytes(header)):
                    raise DeviceIOError("Failed to send header")

                # Send remaining chunks
                offset = first_chunk
                while offset < len(jpeg_data):
                    chunk = jpeg_data[offset:offset + 512]
                    if len(chunk) < 512:
                        chunk = chunk + bytes(512 - len(chunk))
                    if not self.backend.send_frame(chunk):
                        raise DeviceIOError("Failed to send chunk")
                    offset += 512
            except Exception as e:
                raise DeviceIOError(f"Frame send failed: {e}")

        else:
            # USB devices (ChiZhu Tech USBDISPLAY) - send JPEG with protocol header
            try:
                if not self.backend.send_frame(jpeg_data):
                    raise DeviceIOError("Frame send returned False")
            except Exception as e:
                raise DeviceIOError(f"Frame send failed: {e}") from e

    def show_network_sensors(self):
        from src.ui.network_sensors import NetworkSensorsDialog
        if NetworkSensorsDialog(self).exec() == QDialog.DialogCode.Accepted:
            panel = self.properties_panel
            panel.source_combo.blockSignals(True)
            panel.setup_source_combo()
            if panel.current_element:
                panel.set_source_by_id(panel.current_element.source)
            panel.source_combo.blockSignals(False)
            self.refresh_canvas()

    def show_settings(self):
        """Show the settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Preferences")
        dialog.setMinimumWidth(350)

        layout = QVBoxLayout(dialog)

        # Startup group
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)

        launch_label = "Launch at login"
        if sys.platform == "win32":
            launch_label = "Launch at Windows startup"
        self.launch_at_login_cb = QCheckBox(launch_label)
        if sys.platform == "win32":
            self.launch_at_login_cb.setToolTip(
                "Approve UAC once to create the elevated startup task; future logins are silent."
            )
        self.launch_at_login_cb.setChecked(settings.get_setting("launch_at_login", False))
        startup_layout.addWidget(self.launch_at_login_cb)

        self.launch_minimized_cb = QCheckBox("Start minimized to system tray")
        self.launch_minimized_cb.setChecked(settings.get_setting("launch_minimized", True))
        startup_layout.addWidget(self.launch_minimized_cb)

        self.check_for_updates_cb = QCheckBox("Check for updates on startup")
        self.check_for_updates_cb.setChecked(settings.get_setting("check_for_updates", True))
        startup_layout.addWidget(self.check_for_updates_cb)

        layout.addWidget(startup_group)

        # Behavior group
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        self.minimize_to_tray_cb = QCheckBox("Minimize to system tray instead of taskbar")
        self.minimize_to_tray_cb.setChecked(settings.get_setting("minimize_to_tray", True))
        behavior_layout.addWidget(self.minimize_to_tray_cb)

        self.close_to_tray_cb = QCheckBox("Close button minimizes to tray")
        self.close_to_tray_cb.setChecked(settings.get_setting("close_to_tray", True))
        behavior_layout.addWidget(self.close_to_tray_cb)

        layout.addWidget(behavior_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save settings
            settings.set_setting("launch_at_login", self.launch_at_login_cb.isChecked())
            settings.set_setting("launch_minimized", self.launch_minimized_cb.isChecked())
            settings.set_setting("check_for_updates", self.check_for_updates_cb.isChecked())
            settings.set_setting("minimize_to_tray", self.minimize_to_tray_cb.isChecked())
            settings.set_setting("close_to_tray", self.close_to_tray_cb.isChecked())

            # Apply autostart setting
            if not settings.apply_autostart_setting():
                QMessageBox.warning(
                    self,
                    "Autostart Not Updated",
                    "Windows blocked the elevated startup task. Try saving the setting again and accept the UAC prompt.",
                )
                return

            self.status_bar.showMessage("Settings saved", 2000)

    def check_for_updates(self, silent=False):
        """Check for available updates."""
        self.update_checker = UpdateChecker()

        if not silent:
            # Show a message that we're checking
            self.status_bar.showMessage("Checking for updates...")

        # Connect signals
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.no_update.connect(lambda: self._on_no_update(silent))
        self.update_checker.error.connect(lambda msg: self._on_update_error(msg, silent))

        # Start checking in background
        self.update_checker.start()

    def _on_update_available(self, latest_version, release_url, release_notes, expected_hash="", asset_name=""):
        """Handle update available signal."""
        try:
            from src.utils.app_version import __version__
        except ImportError:
            __version__ = "0.0.0"

        dialog = QDialog(self)
        dialog.setWindowTitle("Update Available")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Title
        title_label = QLabel(f"<b>New version available: {latest_version}</b>")
        title_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(title_label)

        current_label = QLabel(f"Current version: {__version__}")
        layout.addWidget(current_label)

        layout.addSpacing(10)

        # Release notes
        notes_label = QLabel("What's new:")
        layout.addWidget(notes_label)

        notes_text = QTextEdit()
        notes_text.setPlainText(release_notes)
        notes_text.setReadOnly(True)
        notes_text.setMaximumHeight(200)
        layout.addWidget(notes_text)

        # Buttons
        buttons = QDialogButtonBox()
        download_label = "Download"
        if can_auto_install_asset(asset_name, expected_hash=expected_hash):
            download_label = "Download && Install"
        buttons.addButton(download_label, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Later", QDialogButtonBox.ButtonRole.RejectRole)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            auto_install = can_auto_install_asset(
                asset_name, expected_hash=expected_hash
            )
            if (
                sys.platform == "win32"
                and asset_name.lower().endswith(".exe")
                and not auto_install
            ):
                webbrowser.open(GITHUB_RELEASES_URL)
            elif asset_name:
                self._download_and_install_update(latest_version, release_url, expected_hash, asset_name)
            else:
                webbrowser.open(release_url)
        else:
            self.status_bar.showMessage("Update dismissed", 2000)

    def _download_and_install_update(self, version, download_url, expected_hash="", asset_name=""):
        """Download installer and prompt for installation."""
        import subprocess
        import os

        # Create progress dialog
        progress = QProgressDialog(
            "Downloading update...",
            "Cancel",
            0, 100,
            self
        )
        progress.setWindowTitle("Downloading Update")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)

        # Start download
        self.update_downloader = UpdateDownloader(download_url, version, expected_hash, asset_name)

        def on_progress(downloaded, total):
            if total > 0:
                percent = int((downloaded / total) * 100)
                progress.setValue(percent)
                # Update label with MB downloaded
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                progress.setLabelText(f"Downloading update... {downloaded_mb:.1f} MB / {total_mb:.1f} MB")

        def on_download_finished(installer_path):
            progress.close()

            if can_auto_install_asset(asset_name, expected_hash=expected_hash) and os.path.exists(installer_path):
                is_linux_appimage = sys.platform.startswith("linux") and asset_name.lower().endswith(".appimage")
                install_prompt = (
                    "Do you want to install it now?\n\n"
                    "The application will close and restart from the new AppImage."
                    if is_linux_appimage else
                    "Do you want to install it now?\n\n"
                    "The application will close and the installer will start."
                )
                reply = QMessageBox.question(
                    self,
                    "Download Complete",
                    "Update downloaded successfully!\n\n"
                    f"{install_prompt}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply != QMessageBox.StandardButton.Yes:
                    QMessageBox.information(
                        self,
                        "Install Later",
                        f"The installer has been saved to:\n{installer_path}\n\n"
                        "You can run it manually when ready."
                    )
                    return

                try:
                    install_info = install_downloaded_update(installer_path, asset_name)
                    subprocess.Popen([install_info["path"]])
                    QApplication.instance().quit()
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to launch installer:\n{e}"
                    )
            else:
                QMessageBox.information(
                    self,
                    "Download Complete",
                    f"The update file has been saved to:\n{installer_path}\n\n"
                    "Install or extract it manually when ready."
                )

        def on_download_error(error_msg):
            progress.close()
            QMessageBox.warning(
                self,
                "Download Failed",
                f"Failed to download update:\n\n{error_msg}"
            )
            self.status_bar.showMessage("Update download failed", 3000)

        # Connect signals
        self.update_downloader.progress.connect(on_progress)
        self.update_downloader.finished.connect(on_download_finished)
        self.update_downloader.error.connect(on_download_error)

        # Handle cancel button
        def on_cancel():
            if self.update_downloader and self.update_downloader.isRunning():
                self.update_downloader.cancel()
                self.update_downloader.wait()
                self.status_bar.showMessage("Download cancelled", 2000)

        progress.canceled.connect(on_cancel)

        # Start download
        self.update_downloader.start()
        self.status_bar.showMessage("Downloading update...", 3000)

    def _on_no_update(self, silent):
        """Handle no update available signal."""
        if not silent:
            QMessageBox.information(
                self,
                "No Updates",
                "You are running the latest version of Thermal Engine."
            )
            self.status_bar.showMessage("No updates available", 2000)

    def _on_update_error(self, error_msg, silent):
        """Handle update check error signal."""
        if not silent:
            QMessageBox.warning(
                self,
                "Update Check Failed",
                f"Could not check for updates:\n\n{error_msg}"
            )
            self.status_bar.showMessage("Update check failed", 2000)

    def changeEvent(self, event):
        """Handle window state changes (minimize)."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                if settings.get_setting("minimize_to_tray", True):
                    # Hide window and show only in tray
                    QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    def cleanup(self):
        """Clean up all resources before quitting."""
        # Restore original stdout/stderr
        if hasattr(self, 'stdout_stream') and self.stdout_stream.original_stream:
            sys.stdout = self.stdout_stream.original_stream
        if hasattr(self, 'stderr_stream') and self.stderr_stream.original_stream:
            sys.stderr = self.stderr_stream.original_stream

        # Stop reconnect timer if running
        if self._reconnect_timer:
            self._reconnect_timer.stop()
            self._reconnect_timer = None

        self.disconnect_display()

        if self.perf_update_timer:
            self.perf_update_timer.stop()

        if hasattr(self, '_video_load_timer') and self._video_load_timer.isActive():
            self._video_load_timer.stop()

        # Stop background threads
        self._stop_render_thread()
        stop_sensors()
        video_background.close()

    def force_quit(self):
        """Force quit the application, bypassing minimize-to-tray."""
        self.cleanup()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, event):
        # Check if we should minimize to tray instead of closing
        if settings.get_setting("close_to_tray", True) and hasattr(self, 'tray_icon'):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "Thermal Engine",
                "Application minimized to system tray. Right-click tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            return

        self.cleanup()
        event.accept()
