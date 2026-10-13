"""Local network sensor configuration, separate from portable display themes."""

import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget, QScrollArea,
)

from src.core import sensors
from src.core.network_sensors import NetworkSensorManager, validate_sources
from src.utils import settings


class NetworkSensorsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Sensors")
        self.resize(740, 640)
        config_error = None
        self._credentials_unavailable = False
        try:
            self._sources = validate_sources(settings.get_setting("network_sensors", []))
        except (ValueError, RuntimeError) as exc:
            self._credentials_unavailable = isinstance(exc, RuntimeError)
            try:
                self._sources = validate_sources(settings.get_setting("network_sensors", [], resolve_secrets=False))
            except ValueError:
                self._sources = []
            config_error = str(exc)
        self._config_error = config_error
        self._index = -1
        self._probe = None
        self._probe_result = None
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Choose Number, Text or Boolean and an optional JSON field (for example: attributes.temperature or values.0). "
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form_widget)
        body.addWidget(scroll, 2)
        self.fields = {}
        labels = {
            "id": "Sensor ID", "name": "Display name", "protocol": "Protocol", "unit": "Unit suffix",
            "value_type": "Value type",
            "scale": "Multiplier", "offset": "Offset", "decimals": "Decimal places",
            "url": "HTTP URL", "token": "HTTP bearer token", "host": "Host / UDP bind address",
            "port": "Port", "topic": "MQTT topic", "username": "MQTT username", "password": "MQTT password",
            "tls": "MQTT TLS", "path": "JSON field path", "interval": "Poll / retry interval (s)",
            "stale_after": "Expire reading after (s)",
        }
        for key, label in labels.items():
            if key == "decimals":
                field = QComboBox()
                field.addItem("Auto", None)
                for number in range(7):
                    field.addItem(str(number), number)
            elif key in ("protocol", "value_type"):
                field = QComboBox()
                choices = ("http", "mqtt", "tcp", "udp") if key == "protocol" else ("number", "text", "boolean")
                for choice in choices:
                    field.addItem(choice.upper() if key == "protocol" else choice.title(), choice)
            elif key == "tls":
                field = QCheckBox("Verify server certificate")
            elif key == "port":
                field = QSpinBox()
                field.setRange(1, 65535)
            elif key in ("scale", "offset"):
                field = QDoubleSpinBox()
                field.setDecimals(6)
                field.setRange(-1e12, 1e12)
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
        self.fields["value_type"].currentIndexChanged.connect(self._value_type_changed)
        self.status_label = QLabel()
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.test_button = QPushButton("Test connection")
        self.test_button.clicked.connect(self._test_connection)
        layout.addWidget(self.test_button)
        note = QLabel("Credentials are saved in your OS credential store. Re-enter missing credentials before saving. Use trusted senders for TCP/UDP; LAN binding accepts unauthenticated packets.")
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
        self._stop_probe()
        self._probe_result = None
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
        self._value_type_changed()
        self._update_status()

    def _value_type_changed(self):
        numeric = self.fields["value_type"].currentData() == "number"
        for key in ("scale", "offset", "decimals", "unit"):
            self.form_widget.layout().setRowVisible(self.fields[key], numeric)

    def _protocol_changed(self):
        protocol = self.fields["protocol"].currentData()
        form = self.form_widget.layout()
        for key in ("url", "token", "host", "port", "topic", "username", "password", "tls"):
            visible = (key in ("url", "token") if protocol == "http"
                       else key in ("host", "port", "topic", "username", "password", "tls") if protocol == "mqtt"
                       else key in ("host", "port"))
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
        self.test_button.setEnabled(self._index >= 0 and self._probe is None)
        if self._probe:
            source = self._probe.sources[0]
            value = self._probe.snapshot().get(f"network_{source['id']}")
            status = self._probe.statuses()[source["id"]]
            if value is not None or time.monotonic() >= self._probe_deadline:
                self._probe_result = (f"Test successful | Value: {value}" if value is not None
                                      else f"Test ended without a valid reading: {status}")
                self._stop_probe()
            self.status_label.setText(self._probe_result or f"Testing unsaved connection: {status}")
            return
        if self._probe_result:
            self.status_label.setText(self._probe_result)
            return
        if self._config_error:
            self.status_label.setText(self._config_error)
            return
        if self._index < 0:
            self.status_label.setText(f"Saved configuration could not be loaded: {self._config_error}"
                                      if self._config_error else "Add a sensor to get started.")
            return
        sensor_id = self.fields["id"].text()
        value = sensors.get_cached_sensors().get(f"network_{sensor_id}")
        status = sensors.get_network_sensor_statuses().get(sensor_id, "Save to start receiving")
        self.status_label.setText(f"Current saved connection: {status}" + (f" | Value: {value}" if value is not None else ""))

    def _save(self):
        self._store_fields()
        if self._credentials_unavailable and any(s.get(field + "_ref") and not s.get(field)
                                                 for s in self._sources for field in ("password", "token")):
            QMessageBox.warning(self, "Credentials unavailable", "Re-enter the missing saved credentials before saving; existing settings are preserved.")
            return
        try:
            sources = validate_sources(self._sources)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid sensor configuration", str(exc))
            return
        try:
            settings.set_setting("network_sensors", sources)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Settings not saved", str(exc))
            return
        sensors.configure_network_sensors(sources)
        self.accept()

    def _test_connection(self):
        if self._index < 0:
            return
        self._store_fields()
        try:
            probe = NetworkSensorManager([self._sources[self._index]])
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid sensor configuration", str(exc))
            return
        self._stop_probe()
        self._probe_result = None
        self._probe = probe
        self._probe_deadline = time.monotonic() + 5
        probe.start()
        self._update_status()

    def _stop_probe(self):
        if self._probe:
            self._probe.stop(wait=False)
            self._probe = None
        if hasattr(self, "test_button"):
            self.test_button.setEnabled(self._index >= 0)

    def done(self, result):
        self._stop_probe()
        super().done(result)
