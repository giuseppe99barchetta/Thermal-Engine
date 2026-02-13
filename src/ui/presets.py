"""
PresetsPanel - Theme preset management widget.
"""

import os
import json
import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QMessageBox, QInputDialog, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPixmap

from src.core.constants import DISPLAY_WIDTH, DISPLAY_HEIGHT
from src.core.element import ThemeElement
from src.utils.app_path import get_resource_path, get_user_data_path, get_bundled_resource_path
from src.core.security import validate_preset_schema, is_safe_filename, sanitize_preset_name
from src.utils.settings import get_setting, set_setting

# Thumbnail dimensions (maintain aspect ratio of display)
THUMBNAIL_WIDTH = 150
THUMBNAIL_HEIGHT = int(THUMBNAIL_WIDTH * DISPLAY_HEIGHT / DISPLAY_WIDTH)  # ~56 for 1280x480
LABEL_HEIGHT = 20
WIDGET_HEIGHT = THUMBNAIL_HEIGHT + LABEL_HEIGHT  # Total widget height


# Default theme elements - optimized for 480x480 displays
DEFAULT_THEME = {
    "name": "Default",
    "background_color": "#0f0f19",
    "display_width": 480,
    "display_height": 480,
    "elements": [
        {"type": "analog_clock", "name": "main_clock", "x": 240, "y": 200, "radius": 140,
         "text": "Clock", "source": "static", "color": "#ffffff", "value": 50,
         "time_format": "24h", "show_seconds_hand": True, "smooth_animation": True,
         "background_color": "#1a1a2e", "background_color_opacity": 0},
        {"type": "text", "name": "cpu_temp", "x": 40, "y": 410, "width": 100, "height": 50,
         "text": "CPU", "source": "cpu_temp", "color": "#00ff96", "font_size": 28,
         "text_align": "left"},
        {"type": "text", "name": "cpu_util", "x": 160, "y": 410, "width": 100, "height": 50,
         "text": "CPU%", "source": "cpu_percent", "color": "#00c8ff", "font_size": 28,
         "text_align": "left"},
        {"type": "text", "name": "gpu_temp", "x": 280, "y": 410, "width": 100, "height": 50,
         "text": "GPU", "source": "gpu_temp", "color": "#ff9632", "font_size": 28,
         "text_align": "left"},
        {"type": "text", "name": "gpu_util", "x": 400, "y": 410, "width": 100, "height": 50,
         "text": "GPU%", "source": "gpu_percent", "color": "#c864ff", "font_size": 28,
         "text_align": "left"},
        {"type": "text", "name": "date", "x": 0, "y": 20, "width": 480, "height": 40,
         "text": "Monday, January 1", "source": "date", "color": "#666680", "font_size": 20,
         "text_align": "center"},
    ]
}


class PresetThumbnail(QWidget):
    """Widget that displays a small preview thumbnail of a preset."""
    clicked = Signal(str)  # Emits preset name
    delete_requested = Signal(str)  # Emits preset name for deletion
    set_default_requested = Signal(str)  # Emits preset name to set as default

    def __init__(self, preset_name, preset_data, is_builtin=False, is_default=False, thumbnail_path=None):
        super().__init__()
        self.preset_name = preset_name
        self.preset_data = preset_data
        self.is_builtin = is_builtin
        self.is_default = is_default
        self.thumbnail_path = thumbnail_path
        self.thumbnail_pixmap = None

        # Calculate thumbnail dimensions dynamically based on preset's display size
        preset_width = preset_data.get("display_width", DISPLAY_WIDTH)
        preset_height = preset_data.get("display_height", DISPLAY_HEIGHT)
        self.thumbnail_width = THUMBNAIL_WIDTH
        self.thumbnail_height = int(THUMBNAIL_WIDTH * preset_height / preset_width)
        self.widget_height = self.thumbnail_height + LABEL_HEIGHT

        # Load thumbnail image if it exists
        if thumbnail_path and os.path.exists(thumbnail_path):
            self.thumbnail_pixmap = QPixmap(thumbnail_path)

        self.setFixedSize(self.thumbnail_width, self.widget_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tooltip = f"Click to load: {preset_name}"
        if is_default:
            tooltip += " (Default)"
        self.setToolTip(tooltip)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use saved thumbnail if available, otherwise generate preview
        if self.thumbnail_pixmap and not self.thumbnail_pixmap.isNull():
            # Draw the saved thumbnail scaled to fill the preview area exactly
            scaled_pixmap = self.thumbnail_pixmap.scaled(
                self.thumbnail_width, self.thumbnail_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled_pixmap)

            # Draw border
            painter.setPen(QPen(QColor(60, 60, 80), 2))
            painter.drawRect(0, 0, self.thumbnail_width, self.thumbnail_height)
        else:
            # Fall back to generated preview
            # Draw background
            bg_color = QColor(self.preset_data.get("background_color", "#0f0f19"))
            painter.fillRect(0, 0, self.thumbnail_width, self.thumbnail_height, bg_color)

            # Draw border
            painter.setPen(QPen(QColor(60, 60, 80), 2))
            painter.drawRect(0, 0, self.thumbnail_width, self.thumbnail_height)

            # Scale factor for preview - use preset's actual display dimensions
            preset_width = self.preset_data.get("display_width", DISPLAY_WIDTH)
            preset_height = self.preset_data.get("display_height", DISPLAY_HEIGHT)
            scale_x = self.thumbnail_width / preset_width
            scale_y = self.thumbnail_height / preset_height

            # Draw simplified element previews
            elements = self.preset_data.get("elements", [])
            for el_data in elements:
                el_type = el_data.get("type", "")
                color = QColor(el_data.get("color", "#00ff96"))
                x = int(el_data.get("x", 0) * scale_x)
                y = int(el_data.get("y", 0) * scale_y)

                if el_type in ["circle_gauge", "analog_clock"]:
                    radius = int(el_data.get("radius", 50) * min(scale_x, scale_y))
                    painter.setPen(QPen(color, 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)
                elif el_type in ["bar_gauge", "rectangle", "text", "clock", "image", "line_chart", "gif"]:
                    width = int(el_data.get("width", 100) * scale_x)
                    height = int(el_data.get("height", 30) * scale_y)
                    painter.setPen(QPen(color, 1))
                    painter.setBrush(QBrush(color.darker(200)))
                    painter.drawRect(x, y, max(width, 3), max(height, 3))

        # Draw name label at bottom
        label_y = self.thumbnail_height
        painter.fillRect(0, label_y, self.thumbnail_width, LABEL_HEIGHT, QColor(35, 35, 40))
        painter.setPen(QPen(QColor(200, 200, 200)))
        font = QFont()
        font.setPixelSize(11)
        painter.setFont(font)

        # Truncate name if too long
        display_name = self.preset_name
        if len(display_name) > 18:
            display_name = display_name[:15] + "..."

        painter.drawText(5, label_y + LABEL_HEIGHT - 5, display_name)

        # Draw indicators on the right side
        indicator_x = self.thumbnail_width - 15

        # Draw checkmark for default preset
        if self.is_default:
            painter.setPen(QPen(QColor(0, 255, 150)))
            painter.drawText(indicator_x, label_y + LABEL_HEIGHT - 5, "✓")
            indicator_x -= 15

        # Draw star for built-in presets
        if self.is_builtin:
            painter.setPen(QPen(QColor(255, 200, 0)))
            painter.drawText(indicator_x, label_y + LABEL_HEIGHT - 5, "★")

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.preset_name)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)

        # Set as default option (available for all presets)
        if self.is_default:
            default_action = menu.addAction("✓ Default Preset")
            default_action.setEnabled(False)
        else:
            default_action = menu.addAction("Set as Default")

        # Delete option (only for non-builtin)
        delete_action = None
        if not self.is_builtin:
            menu.addSeparator()
            delete_action = menu.addAction("Delete Preset")

        action = menu.exec(event.globalPos())
        if action == default_action and not self.is_default:
            self.set_default_requested.emit(self.preset_name)
        elif action == delete_action:
            self.delete_requested.emit(self.preset_name)


class PresetsPanel(QWidget):
    preset_selected = Signal(dict)  # Emits preset data when selected
    preset_saved = Signal(str)  # Emits preset name when saved
    default_changed = Signal(str)  # Emits preset name when default is changed

    PRESETS_PER_PAGE = 8

    def __init__(self):
        super().__init__()
        self.presets = {}
        self.current_page = 0
        # User presets directory (writable, in AppData)
        self.user_presets_dir = get_user_data_path("presets")
        # Bundled presets directory (read-only, from installation)
        self.bundled_presets_dir = get_bundled_resource_path("presets")
        # Display resolution filtering - use last known resolution from settings
        self.current_display_width = get_setting("last_display_width", 480)
        self.current_display_height = get_setting("last_display_height", 480)
        self.show_all_resolutions = False
        self.setup_ui()
        self.load_presets()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title row with filter and New button
        title_row = QHBoxLayout()
        title = QLabel("Presets")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        title_row.addWidget(title)
        title_row.addStretch()

        # Resolution filter checkbox
        self.show_all_checkbox = QCheckBox("All resolutions")
        self.show_all_checkbox.setChecked(self.show_all_resolutions)
        self.show_all_checkbox.setToolTip("Show presets for all display resolutions")
        self.show_all_checkbox.stateChanged.connect(self.toggle_resolution_filter)
        title_row.addWidget(self.show_all_checkbox)

        self.new_preset_btn = QPushButton("+ New")
        self.new_preset_btn.setFixedWidth(60)
        self.new_preset_btn.clicked.connect(self.create_new_preset)
        title_row.addWidget(self.new_preset_btn)

        layout.addLayout(title_row)

        # Preset grid container
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        layout.addWidget(self.grid_container)

        # Pagination controls
        self.pagination_widget = QWidget()
        pagination_layout = QHBoxLayout(self.pagination_widget)
        pagination_layout.setContentsMargins(0, 5, 0, 0)

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setFixedWidth(70)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 1/1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setFixedWidth(70)
        pagination_layout.addWidget(self.next_btn)

        layout.addWidget(self.pagination_widget)

        layout.addStretch()

    def ensure_presets_dir(self):
        """Create user presets directory if it doesn't exist."""
        if not os.path.exists(self.user_presets_dir):
            os.makedirs(self.user_presets_dir)

    def _load_presets_from_dir(self, presets_dir, is_builtin=False, target_dict=None):
        """Load presets from a specific directory.

        Args:
            presets_dir: Directory to load presets from
            is_builtin: Whether these are bundled (read-only) presets
            target_dict: Optional dictionary to load presets into (defaults to self.presets)
        """
        if target_dict is None:
            target_dict = self.presets

        if not os.path.exists(presets_dir):
            return

        for filename in os.listdir(presets_dir):
            if filename.endswith(".json"):
                # Validate filename is safe
                safe, err = is_safe_filename(filename)
                if not safe:
                    print(f"Skipping unsafe filename {filename}: {err}")
                    continue

                filepath = os.path.join(presets_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)

                    # Validate preset schema before using
                    is_valid, errors = validate_preset_schema(data)
                    if not is_valid:
                        print(f"Invalid preset {filename}: {errors}")
                        continue

                    preset_name = data.get("name", filename[:-5])

                    # Check for corresponding thumbnail
                    thumbnail_path = filepath[:-5] + ".png"  # Replace .json with .png
                    if not os.path.exists(thumbnail_path):
                        thumbnail_path = None

                    # Add to target dictionary
                    target_dict[preset_name] = {
                        "data": data,
                        "builtin": is_builtin,
                        "filepath": filepath,
                        "thumbnail_path": thumbnail_path
                    }
                except Exception as e:
                    print(f"Failed to load preset {filename}: {e}")

    def load_presets(self):
        """Load all presets from both bundled and user directories."""
        self.presets = {}

        # Protected system presets (cannot be deleted or overwritten)
        PROTECTED_PRESETS = ["Default", "System Monitor", "Minimal"]

        # Always include the default preset
        self.presets["Default"] = {
            "data": DEFAULT_THEME,
            "builtin": True,
            "thumbnail_path": None
        }

        # Load bundled presets first (from installation directory)
        self._load_presets_from_dir(self.bundled_presets_dir, is_builtin=True)

        # Load user presets (from AppData) - but don't override protected system presets
        self.ensure_presets_dir()
        user_presets = {}
        self._load_presets_from_dir(self.user_presets_dir, is_builtin=False, target_dict=user_presets)

        # Merge user presets, but skip protected ones
        for name, preset_info in user_presets.items():
            if name not in PROTECTED_PRESETS:
                self.presets[name] = preset_info

        self.refresh_display()

    def refresh_display(self):
        """Refresh the preset thumbnails display."""
        # Clear existing thumbnails properly
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Filter presets by resolution if enabled
        if self.show_all_resolutions:
            filtered_presets = self.presets.keys()
        else:
            filtered_presets = []
            for name, preset_info in self.presets.items():
                preset_data = preset_info["data"]
                preset_width = preset_data.get("display_width", DISPLAY_WIDTH)
                preset_height = preset_data.get("display_height", DISPLAY_HEIGHT)

                # Show preset if it matches current display resolution
                if preset_width == self.current_display_width and preset_height == self.current_display_height:
                    filtered_presets.append(name)

        # Get sorted preset names (Default first, then alphabetical)
        preset_names = sorted(filtered_presets, key=lambda x: (x != "Default", x.lower()))

        # Calculate pagination
        total_presets = len(preset_names)
        total_pages = max(1, math.ceil(total_presets / self.PRESETS_PER_PAGE))
        self.current_page = min(self.current_page, total_pages - 1)

        # Get presets for current page
        start_idx = self.current_page * self.PRESETS_PER_PAGE
        end_idx = start_idx + self.PRESETS_PER_PAGE
        page_presets = preset_names[start_idx:end_idx]

        # Get the default preset name
        default_preset = get_setting("default_preset", None)

        # Create thumbnails in a 2-column grid
        for i, name in enumerate(page_presets):
            preset_info = self.presets[name]
            thumbnail = PresetThumbnail(
                name,
                preset_info["data"],
                preset_info.get("builtin", False),
                is_default=(name == default_preset),
                thumbnail_path=preset_info.get("thumbnail_path")
            )
            thumbnail.clicked.connect(self.on_preset_clicked)
            thumbnail.delete_requested.connect(self.on_delete_preset)
            thumbnail.set_default_requested.connect(self.on_set_default_preset)
            row = i // 2
            col = i % 2
            self.grid_layout.addWidget(thumbnail, row, col)

        # Update pagination controls
        self.page_label.setText(f"Page {self.current_page + 1}/{total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
        self.pagination_widget.setVisible(total_pages > 1)

        # Force layout update
        self.grid_container.updateGeometry()
        self.updateGeometry()
        self.update()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_display()

    def next_page(self):
        total_pages = math.ceil(len(self.presets) / self.PRESETS_PER_PAGE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.refresh_display()

    def toggle_resolution_filter(self, state):
        """Toggle the resolution filter on/off."""
        self.show_all_resolutions = bool(state)
        self.current_page = 0  # Reset to first page when filtering
        self.refresh_display()

    def set_display_resolution(self, width, height):
        """Update the current display resolution for filtering.

        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self.current_display_width = width
        self.current_display_height = height

        # Save resolution to settings for next startup
        set_setting("last_display_width", width)
        set_setting("last_display_height", height)

        # Refresh display if filtering is active
        if not self.show_all_resolutions:
            self.current_page = 0  # Reset to first page
            self.refresh_display()

    def on_preset_clicked(self, preset_name):
        """Handle preset selection."""
        if preset_name in self.presets:
            preset_data = self.presets[preset_name]["data"]
            # Remember the last loaded preset so it persists across restarts
            set_setting("last_preset", preset_name)
            self.preset_selected.emit(preset_data)

    def on_delete_preset(self, preset_name):
        """Handle preset deletion request."""
        if preset_name in self.presets and not self.presets[preset_name].get("builtin", False):
            reply = QMessageBox.question(
                self, "Delete Preset",
                f"Are you sure you want to delete the preset '{preset_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                filepath = self.presets[preset_name].get("filepath")
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        # Also delete thumbnail if it exists
                        thumbnail_path = filepath[:-5] + ".png"
                        if os.path.exists(thumbnail_path):
                            os.remove(thumbnail_path)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to delete preset file: {e}")
                        return
                del self.presets[preset_name]

                # Clear default if deleted preset was the default
                if get_setting("default_preset") == preset_name:
                    set_setting("default_preset", None)

                # Delay refresh to allow context menu to close properly
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self.refresh_display)

    def on_set_default_preset(self, preset_name):
        """Handle setting a preset as default."""
        if preset_name in self.presets:
            set_setting("default_preset", preset_name)
            self.default_changed.emit(preset_name)
            # Delay refresh to allow context menu to close properly
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.refresh_display)

    def create_new_preset(self):
        """Create a new empty preset with a black background."""
        name, ok = QInputDialog.getText(
            self, "New Preset",
            "Enter preset name:",
            text="New Theme"
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        # Check if name already exists
        if name in self.presets:
            QMessageBox.warning(
                self, "Name Exists",
                f"A preset named '{name}' already exists. Please choose a different name."
            )
            return

        # Create empty preset data
        new_preset_data = {
            "name": name,
            "background_color": "#000000",
            "display_width": DISPLAY_WIDTH,
            "display_height": DISPLAY_HEIGHT,
            "elements": [],
            "video_background": {
                "video_path": "",
                "fit_mode": "fit_height",
                "enabled": False
            }
        }

        # Save the preset (without thumbnail since it's empty/black)
        if self.save_preset(name, new_preset_data):
            # Emit signal to load the new preset
            self.preset_selected.emit(new_preset_data)

    def get_default_preset_data(self):
        """Get the default preset data, if one is set and exists.

        Priority order:
        1. Explicit default preset (set by user via right-click menu)
        2. Last used preset (auto-saved when loading any preset)
        3. Resolution-appropriate built-in preset
        """
        # 1. Explicit default preset
        default_name = get_setting("default_preset", None)
        if default_name and default_name in self.presets:
            return self.presets[default_name]["data"]

        # 2. Last used preset
        last_name = get_setting("last_preset", None)
        if last_name and last_name in self.presets:
            return self.presets[last_name]["data"]

        # 3. Resolution-appropriate built-in preset
        # For 480x480 displays, use "System Monitor" instead of "Default"
        if self.current_display_width == 480 and self.current_display_height == 480:
            if "System Monitor" in self.presets:
                return self.presets["System Monitor"]["data"]

        # Fallback to "Default" preset
        if "Default" in self.presets:
            return self.presets["Default"]["data"]

        return None

    def save_preset(self, name, theme_data, thumbnail_image=None):
        """Save a theme as a preset with optional thumbnail.

        Args:
            name: Preset name
            theme_data: Theme data dict
            thumbnail_image: Optional PIL Image to save as thumbnail
        """
        self.ensure_presets_dir()

        # Sanitize the name for safe filename
        safe_name = sanitize_preset_name(name)

        # Validate the filename is safe
        filename = f"{safe_name}.json"
        safe, err = is_safe_filename(filename)
        if not safe:
            QMessageBox.warning(self, "Error", f"Invalid preset name: {err}")
            return False

        # Always save to user presets directory (writable location)
        filepath = os.path.join(self.user_presets_dir, filename)
        thumbnail_path = os.path.join(self.user_presets_dir, f"{safe_name}.png")

        # Check if overwriting
        if os.path.exists(filepath):
            reply = QMessageBox.question(
                self, "Overwrite Preset",
                f"A preset named '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        try:
            with open(filepath, 'w') as f:
                json.dump(theme_data, f, indent=2)

            # Save thumbnail if provided
            if thumbnail_image is not None:
                try:
                    # Resize to thumbnail dimensions
                    thumbnail = thumbnail_image.copy()
                    thumbnail.thumbnail((THUMBNAIL_WIDTH * 2, THUMBNAIL_HEIGHT * 2))  # 2x for retina/sharp display
                    thumbnail.save(thumbnail_path, "PNG")
                except Exception as e:
                    print(f"[Presets] Failed to save thumbnail: {e}")
                    thumbnail_path = None
            else:
                thumbnail_path = None

            self.presets[name] = {
                "data": theme_data,
                "builtin": False,
                "filepath": filepath,
                "thumbnail_path": thumbnail_path if thumbnail_path and os.path.exists(thumbnail_path) else None
            }
            self.refresh_display()
            self.preset_saved.emit(name)
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save preset: {e}")
            return False
