"""First-run device, resolution and preset selection."""

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QFormLayout, QComboBox, QSpinBox,
    QPushButton, QLabel, QScrollArea, QWidget, QGridLayout,
)
from PySide6.QtCore import Qt

from src.core.device_backends import enumerate_available_devices
from src.core.display_size import DISPLAY_SIZE_PROFILES, get_device_size_override
from src.ui.presets import PresetThumbnail


class SetupWizard(QWizard):
    def __init__(self, presets, size, overrides, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Thermal Engine")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.resize(620, 520)
        self.presets = presets
        self.overrides = overrides
        self.preset_name = None
        self.thumbnails = {}

        device_page = QWizardPage()
        device_page.setTitle("Choose your display")
        device_page.setSubTitle("Connect your display, or continue offline to create a theme.")
        layout = QVBoxLayout(device_page)
        self.device_combo = QComboBox()
        layout.addWidget(self.device_combo)
        refresh = QPushButton("Refresh devices")
        refresh.clicked.connect(self.refresh_devices)
        layout.addWidget(refresh)
        layout.addStretch()
        self.addPage(device_page)
        self.refresh_devices()

        size_page = QWizardPage()
        size_page.setTitle("Choose the native screen resolution")
        size_page.setSubTitle("Check your panel size: some devices share the same USB identifier.")
        form = QFormLayout(size_page)
        self.profile_combo = QComboBox()
        for label, width, height in DISPLAY_SIZE_PROFILES:
            self.profile_combo.addItem(label, (width, height))
        self.profile_combo.addItem("Custom", None)
        form.addRow("Profile:", self.profile_combo)
        self.width_spin, self.height_spin = QSpinBox(), QSpinBox()
        for spin, value in zip((self.width_spin, self.height_spin), size):
            spin.setRange(160, 4096)
            spin.setValue(value)
        form.addRow("Width:", self.width_spin)
        form.addRow("Height:", self.height_spin)
        self.profile_combo.currentIndexChanged.connect(self.update_size)
        self.addPage(size_page)

        preset_page = QWizardPage()
        preset_page.setTitle("Choose a starting theme")
        preset_page.setSubTitle("Click a thumbnail, or finish with a blank theme.")
        layout = QVBoxLayout(preset_page)
        self.selection_label = QLabel("Blank theme selected")
        layout.addWidget(self.selection_label)
        blank = QPushButton("Use blank theme")
        blank.clicked.connect(lambda: self.select_preset(None))
        layout.addWidget(blank)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.gallery = QWidget()
        self.grid = QGridLayout(self.gallery)
        scroll.setWidget(self.gallery)
        layout.addWidget(scroll)
        self.addPage(preset_page)

    def refresh_devices(self):
        self.device_combo.clear()
        self.device_combo.addItem("Offline editor", None)
        for device in enumerate_available_devices():
            tag = " [experimental]" if device.experimental else ""
            self.device_combo.addItem(device.name + tag, device)
        if self.device_combo.count() > 1:
            self.device_combo.setCurrentIndex(1)

    def update_size(self):
        size = self.profile_combo.currentData()
        if size:
            self.width_spin.setValue(size[0])
            self.height_spin.setValue(size[1])
        self.width_spin.setEnabled(size is None)
        self.height_spin.setEnabled(size is None)

    def initializePage(self, page_id):
        if page_id == 1:
            device = self.device_combo.currentData()
            size = (self.width_spin.value(), self.height_spin.value())
            if device:
                size = get_device_size_override(self.overrides, device) or (device.width, device.height)
            index = self.profile_combo.findData(size)
            self.profile_combo.setCurrentIndex(index if index >= 0 else self.profile_combo.count() - 1)
            self.width_spin.setValue(size[0])
            self.height_spin.setValue(size[1])
            self.update_size()
        elif page_id == 2:
            self.refresh_gallery()

    def refresh_gallery(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.thumbnails.clear()
        self.select_preset(None)
        size = (self.width_spin.value(), self.height_spin.value())
        matching = [name for name, info in self.presets.items()
                    if (info["data"].get("display_width"), info["data"].get("display_height")) == size]
        names = matching or list(self.presets)
        self.page(2).setSubTitle(
            "Click a thumbnail, or finish with a blank theme."
            if matching else "No exact size matches. Themes below will be scaled to your screen."
        )
        for index, name in enumerate(sorted(names, key=str.lower)):
            info = self.presets[name]
            thumbnail = PresetThumbnail(
                name, info["data"], is_builtin=info.get("builtin", False),
                thumbnail_path=info.get("thumbnail_path")
            )
            thumbnail.clicked.connect(self.select_preset)
            thumbnail.setToolTip("Choose starting theme: " + name)
            thumbnail.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
            self.thumbnails[name] = thumbnail
            self.grid.addWidget(thumbnail, index // 3, index % 3)

    def select_preset(self, name):
        self.preset_name = name
        self.selection_label.setText(f"Selected: {name}" if name else "Blank theme selected")
        for preset_name, thumbnail in self.thumbnails.items():
            thumbnail.is_selected = preset_name == name
            thumbnail.update()
