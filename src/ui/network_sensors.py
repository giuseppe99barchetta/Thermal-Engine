"""Local network sensor configuration, separate from portable display themes."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from src.core import sensors
from src.core.network_sensors import validate_sources
from src.utils import settings


class NetworkSensorsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Sensors")
        self.resize(740, 640)
        config_error = None
        try:
            self._sources = validate_sources(settings.get_setting("network_sensors", []))
        except ValueError as exc:
            self._sources = []
            config_error = str(exc)
        self._config_error = config_error
        self._index = -1
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Use a numeric payload or a numeric JSON field (for example: attributes.temperature or values.0). "
            "TCP connects to a sender and reads newline-delimited values; UDP listens for one value per packet. "
            "Saved sensors appear under External Sensors in the element's Data Source selector."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        body = QHBoxLayout()
        layout.addLayout(body)
        left = QVBoxLayout()
        body.addLayout(left, 1)
        self.source_list = QListWidget()
        left.addWidget(self.source_list)
        actions = QHBoxLayout()
        left.addLayout(actions)
        add = QPushButton("Add")
        remove = QPushButton("Remove")
        actions.addWidget(add)
        actions.addWidget(remove)
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        self.form_widget = QWidget()
        form = QFormLayout(self.form_widget)
        body.addWidget(self.form_widget, 2)
        self.fields = {}
        labels = {
            "id": "Sensor ID", "name": "Display name", "protocol": "Protocol", "unit": "Unit suffix",
            "url": "HTTP URL", "token": "HTTP bearer token", "host": "Host / UDP bind address",
            "port": "Port", "topic": "MQTT topic", "username": "MQTT username", "password": "MQTT password",
            "tls": "MQTT TLS", "path": "JSON field path", "interval": "Poll / retry interval (s)",
            "stale_after": "Expire reading after (s)",
        }
        for key, label in labels.items():
            if key == "protocol":
                field = QComboBox()
                for protocol in ("http", "mqtt", "tcp", "udp"):
                    field.addItem(protocol.upper(), protocol)
            elif key == "tls":
                field = QCheckBox("Verify server certificate")
            elif key == "port":
                field = QSpinBox()
                field.setRange(1, 65535)
            elif key in ("interval", "stale_after"):
                field = QDoubleSpinBox()
                field.setRange(.1 if key == "interval" else 1, 3600 if key == "interval" else 86400)
            else:
                field = QLineEdit()
                if key in ("token", "password"):
                    field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setAccessibleName(label)
            form.addRow(label, field)
            self.fields[key] = field
        self.fields["id"].setToolTip("Stable ID used by themes; use lowercase letters, digits and underscores.")
        self.fields["host"].setToolTip("UDP: 127.0.0.1 for this computer; 0.0.0.0 to accept packets from your LAN.")
        self.fields["protocol"].currentIndexChanged.connect(self._protocol_changed)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        note = QLabel("Credentials are stored in your local settings file. Use trusted senders for TCP/UDP; LAN binding accepts unauthenticated packets.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.source_list.currentRowChanged.connect(self._select)
        self._refresh_list()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_status)
        self.timer.start(500)
        self._update_status()

    def _store_fields(self):
        if not 0 <= self._index < len(self._sources):
            return
        source = self._sources[self._index]
        for key, field in self.fields.items():
            if isinstance(field, QComboBox):
                source[key] = field.currentData()
            elif isinstance(field, QCheckBox):
                source[key] = field.isChecked()
            elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
                source[key] = field.value()
            else:
                source[key] = field.text()
        self.source_list.item(self._index).setText(source["name"] or source["id"] or "New sensor")

    def _select(self, index):
        self._store_fields()
        self._index = index
        self.form_widget.setEnabled(index >= 0)
        if index < 0:
            return
        source = self._sources[index]
        self.fields["protocol"].blockSignals(True)
        for key, field in self.fields.items():
            value = source.get(key, "")
            if isinstance(field, QComboBox):
                field.setCurrentIndex(max(0, field.findData(value)))
            elif isinstance(field, QCheckBox):
                field.setChecked(bool(value))
            elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
                field.setValue(value if isinstance(value, (int, float)) else 1)
            else:
                field.setText(str(value))
        self.fields["protocol"].blockSignals(False)
        self._protocol_changed()
        self._update_status()

    def _protocol_changed(self):
        protocol = self.fields["protocol"].currentData()
        form = self.form_widget.layout()
        for key in ("url", "token", "host", "port", "topic", "username", "password", "tls"):
            visible = (key in ("url", "token") if protocol == "http"
                       else key in ("host", "port") or protocol == "mqtt")
            form.setRowVisible(self.fields[key], visible)
        if self.sender() is self.fields["protocol"]:
            self.fields["port"].setValue(1883 if protocol == "mqtt" else 9000)

    def _refresh_list(self):
        self.source_list.blockSignals(True)
        self.source_list.clear()
        for source in self._sources:
            self.source_list.addItem(source.get("name") or source.get("id") or "New sensor")
        self._index = -1
        self.source_list.blockSignals(False)
        self.source_list.setCurrentRow(0 if self._sources else -1)
        self.form_widget.setEnabled(bool(self._sources))

    def _add(self):
        self._store_fields()
        ids = {s.get("id") for s in self._sources}
        number = 1
        while f"sensor_{number}" in ids:
            number += 1
        self._sources.append(validate_sources([{"id": f"sensor_{number}", "protocol": "http", "url": "http://127.0.0.1:8123/api/states/sensor.example"}])[0])
        self._refresh_list()
        self.source_list.setCurrentRow(len(self._sources) - 1)

    def _remove(self):
        if self._index >= 0:
            self._sources.pop(self._index)
            self._refresh_list()

    def _update_status(self):
        if self._index < 0:
            self.status_label.setText(f"Saved configuration could not be loaded: {self._config_error}"
                                      if self._config_error else "Add a sensor to get started.")
            return
        sensor_id = self.fields["id"].text()
        value = sensors.get_cached_sensors().get(f"network_{sensor_id}")
        status = sensors.get_network_sensor_statuses().get(sensor_id, "Save to start receiving")
        self.status_label.setText(f"Current saved connection: {status}" + (f" | Value: {value:g}" if value is not None else ""))

    def _save(self):
        self._store_fields()
        try:
            sources = validate_sources(self._sources)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid sensor configuration", str(exc))
            return
        settings.set_setting("network_sensors", sources)
        sensors.configure_network_sensors(sources)
        self.accept()
