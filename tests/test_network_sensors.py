import socket
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.core.constants import (
    DATA_SOURCES_CATEGORIZED, SOURCE_UNITS, format_sensor_template,
    get_value_with_unit, register_network_sources,
)
from src.core.network_sensors import MAX_PAYLOAD, NetworkSensorManager, parse_value, validate_sources


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    assert predicate(), "Network sensor did not update before timeout"


@pytest.mark.parametrize("payload,path,expected", [
    (b"-12.5", "", -12.5), (b"+2.5", "", 2.5),
    (b'{"attributes":{"temperature":"21.75"}}', "attributes.temperature", 21.75),
    (b'{"values":[0,1234]}', "values.1", 1234), (b'"0"', "", 0),
])
def test_numeric_payloads(payload, path, expected):
    assert parse_value(payload, path) == expected


@pytest.mark.parametrize("payload,path,kind,expected", [
    (b"Occupied", "", "text", "Occupied"),
    (b'{"state":"playing"}', "state", "text", "playing"),
    (b"true", "", "boolean", True), (b'"OFF"', "", "boolean", False),
    (b"1", "", "boolean", True), (b'{"state":"on"}', "state", "boolean", True),
])
def test_typed_payloads(payload, path, kind, expected):
    assert parse_value(payload, path, kind) == expected


@pytest.mark.parametrize("payload,kind", [(b"{}", "text"), (b"12", "text"),
    (b"x" * 513, "text"), (b'"\\ud800"', "text"), (b"2", "boolean"), (b"unknown", "boolean")])
def test_typed_payload_validation(payload, kind):
    with pytest.raises(ValueError):
        parse_value(payload, "", kind)


def test_text_and_boolean_render_without_mutating_persisted_value():
    from src.core.element import ThemeElement
    from src.core.renderer import ThemeRenderer
    from src.ui.main_window import ThemeEditorWindow
    sources = validate_sources([
        {"id": "status", "protocol": "udp", "value_type": "text"},
        {"id": "door", "protocol": "udp", "value_type": "boolean"},
    ])
    element = ThemeElement("text", text="State", source="network_status", animate_gauge=True)
    values = {"network_status": "Occupied", "network_door": False}
    window = SimpleNamespace(get_sensor_data=lambda: values, get_current_page_elements=lambda: [element],
                             _animated_value=lambda element, value: value, background_color="#000000")
    try:
        register_network_sources(sources)
        assert format_sensor_template("{network_status}: {network_door}", values) == "Occupied: OFF"
        snapshot = ThemeEditorWindow._capture_render_snapshot(window)
        assert isinstance(element.to_dict()["value"], (int, float))
        renderer = ThemeRenderer()
        first = renderer.render(snapshot, (400, 200))
        values["network_status"] = "Playing"
        second = renderer.render(ThemeEditorWindow._capture_render_snapshot(window), (400, 200))
        assert first.tobytes() != second.tobytes()
    finally:
        register_network_sources([])


@pytest.mark.parametrize("payload,path", [
    (b"NaN", ""), (b"Infinity", ""), (b"1e100", ""), (b"true", ""),
    (b"null", ""), (b"{}", ""), (b"hello", ""), (b"\xff", ""),
    (b'"NaN"', ""), (b'{"x":1}', "missing"), (b"[1]", "3"),
    pytest.param(b"1" * (MAX_PAYLOAD + 1), "", id="oversized"),
])
def test_reject_bad_payloads(payload, path):
    with pytest.raises((ValueError, KeyError, IndexError)):
        parse_value(payload, path)


@pytest.mark.parametrize("changes", [
    {"id": "cpu_temp!"}, {"id": 5}, {"protocol": "file"}, {"url": "file:///etc/passwd"},
    {"url": "http://user:password@localhost"}, {"url": "http://localhost:bad"},
    {"interval": 0}, {"stale_after": float("nan")}, {"protocol": "tcp", "port": 0},
    {"protocol": "mqtt", "topic": ""}, {"tls": "false"},
    {"protocol": "mqtt", "topic": "home/#/room"},
])
def test_validate_configuration(changes):
    config = {"id": "room", "protocol": "http", "url": "http://127.0.0.1/"}
    config.update(changes)
    with pytest.raises(ValueError):
        validate_sources([config])


def test_duplicate_ids_and_limits():
    config = {"id": "room", "protocol": "udp"}
    with pytest.raises(ValueError):
        validate_sources([config, config])
    with pytest.raises(ValueError):
        validate_sources([config] * 65)
    assert validate_sources([{"id": "room", "protocol": "mqtt", "topic": "home/room", "tls": True}])[0]["port"] == 8883


def test_numeric_conversion_precision_and_bounds():
    manager = NetworkSensorManager([{"id": "speed", "protocol": "udp", "scale": 3.6, "offset": -1, "decimals": 2, "unit": " km/h"}])
    try:
        register_network_sources(manager.sources)
        manager._receive(manager.sources, b"10")
        value = manager.snapshot()["network_speed"]
        assert value == 35
        assert get_value_with_unit(value, "network_speed") == "35.00 km/h"
        assert format_sensor_template("{network_speed}", manager.snapshot()) == "35.00 km/h"
        manager._receive(manager.sources, b"1e12")
        assert manager.snapshot()["network_speed"] == 35
        for changes in ({"scale": float("nan")}, {"offset": True}, {"decimals": 7}, {"decimals": False}):
            with pytest.raises(ValueError):
                validate_sources([{**manager.sources[0], **changes}])
    finally:
        register_network_sources([])


def test_stale_data_invalid_payload_and_independent_copies():
    manager = NetworkSensorManager([{"id": "room", "protocol": "udp", "stale_after": 1}])
    manager._receive(manager.sources, b"23.5")
    manager._receive(manager.sources, b"invalid")
    assert manager.snapshot() == {"network_room": 23.5}
    assert manager.statuses()["room"] == "Invalid payload / JSON field"
    manager.snapshot().clear()
    assert manager.snapshot()
    manager._values["room"] = (23.5, time.monotonic() - 2)
    assert manager.snapshot() == {}
    assert manager.statuses()["room"] == "Stale"
    manager.stop()
    manager._receive(manager.sources, b"42")
    assert manager.snapshot() == {}


def test_source_registration_and_formatting():
    source = validate_sources([{"id": "room_2", "name": "Room", "protocol": "udp", "unit": " C"}])
    try:
        register_network_sources(source)
        assert SOURCE_UNITS["network_room_2"]["symbol"] == " C"
        assert DATA_SOURCES_CATEGORIZED["External Sensors"][0][0] == "network_room_2"
        assert get_value_with_unit(21.75, "network_room_2") == "21.75 C"
        assert format_sensor_template("Room: {network_room_2}", {"network_room_2": 21.75}) == "Room: 21.75 C"
        assert format_sensor_template("Room: {network_room_2}", {}) == "Room: --"
        register_network_sources([])
        assert "network_room_2" not in SOURCE_UNITS
        assert format_sensor_template("Room: {network_room_2}", {}) == "Room: --"
    finally:
        register_network_sources([])


def test_http_polling_and_auth():
    auth = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            auth.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"state":"22.5"}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    manager = NetworkSensorManager([{"id": "room", "protocol": "http", "url": f"http://127.0.0.1:{server.server_port}/", "path": "state", "token": "test-token", "interval": .1}])
    try:
        manager.start()
        wait_for(lambda: manager.snapshot().get("network_room") == 22.5)
        wait_for(lambda: len(auth) >= 2)
        assert auth == ["Bearer test-token"] * len(auth)
    finally:
        manager.stop()
        server.shutdown()
        server.server_close()
        thread.join(1)
    assert all(not thread.is_alive() for thread in manager._threads)


def test_http_streaming_body_has_a_total_read_budget(monkeypatch):
    manager = NetworkSensorManager([{"id": "room", "protocol": "http", "url": "http://localhost/"}])
    response = MagicMock()
    response.__enter__.return_value = response
    response.read1.return_value = b"1"
    opener = MagicMock()
    opener.open.return_value = response
    monkeypatch.setattr("src.core.network_sensors.build_opener", lambda *args: opener)
    clock = iter((0, 1, 3))
    monkeypatch.setattr("src.core.network_sensors.time.monotonic", lambda: next(clock))
    original_error = manager._error

    def stop_after_error(sources, message):
        original_error(sources, message)
        manager._stop.set()

    monkeypatch.setattr(manager, "_error", stop_after_error)
    manager._run(manager.sources)
    assert response.read1.call_count == 2
    assert manager._values == {}
    assert manager._status["room"] == "Connection / read failed; retrying"


def test_udp_shared_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    manager = NetworkSensorManager([
        {"id": "speed", "protocol": "udp", "port": port, "path": "speed"},
        {"id": "rpm", "protocol": "udp", "port": port, "path": "rpm"},
    ])
    try:
        manager.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            def send_and_check():
                sender.sendto(b'{"speed":123.5,"rpm":4200}', ("127.0.0.1", port))
                return manager.snapshot().get("network_rpm") == 4200
            wait_for(send_and_check)
        assert manager.snapshot() == {"network_speed": 123.5, "network_rpm": 4200}
        assert len(manager._threads) == 1
    finally:
        manager.stop()
    assert all(not thread.is_alive() for thread in manager._threads)


def test_tcp_framing_and_reconnect():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(2)
        server.settimeout(4)
        manager = NetworkSensorManager([{"id": "speed", "protocol": "tcp", "port": server.getsockname()[1], "interval": .1}])
        try:
            manager.start()
            connection, _ = server.accept()
            with connection:
                connection.sendall(b"12")
                connection.sendall(b".5\n14\ninvalid\n")
                wait_for(lambda: manager.snapshot().get("network_speed") == 14)
            connection, _ = server.accept()
            with connection:
                connection.sendall(b"17\n")
                wait_for(lambda: manager.snapshot().get("network_speed") == 17)
        finally:
            manager.stop()
        assert all(not thread.is_alive() for thread in manager._threads)


def test_mqtt_subscribe_auth_tls_and_shutdown():
    import paho.mqtt.client as mqtt
    client = MagicMock()
    manager = NetworkSensorManager([{"id": "room", "protocol": "mqtt", "topic": "home/room", "username": "mike", "password": "test-secret", "tls": True, "path": "temperature"}])
    with patch.object(mqtt, "Client", return_value=client):
        try:
            manager.start()
            wait_for(lambda: client.loop_start.called)
            client.on_connect(client, None, None, 0, None)
            client.subscribe.assert_called_with("home/room")
            client.on_message(client, None, SimpleNamespace(payload=b'{"temperature":20.5}'))
            assert manager.snapshot() == {"network_room": 20.5}
            client.on_connect(client, None, None, 0, None)
            assert client.subscribe.call_count == 2
            client.username_pw_set.assert_called_once_with("mike", "test-secret")
            client.tls_set.assert_called_once_with()
            client.connect_async.assert_called_once_with("127.0.0.1", 8883, keepalive=30)
        finally:
            manager.stop()
    client.disconnect.assert_called_once()
    client.loop_stop.assert_called_once()


def test_auth_not_forwarded_to_different_origin():
    from urllib.request import Request
    from src.core.network_sensors import _SafeRedirectHandler
    request = Request("https://home.example/state", headers={"Authorization": "Bearer secret"})
    with pytest.raises(ValueError):
        _SafeRedirectHandler().redirect_request(request, None, 302, "Found", {}, "http://other.example/state")


def test_mqtt_real_client_receives_retained_value():
    """A minimal loopback broker exercises Paho's wire-level subscribe and receive."""
    errors, subscribed = [], []
    finish = threading.Event()

    def read_packet(connection):
        header = connection.recv(1)
        if not header:
            raise ConnectionError("Client disconnected")
        size, multiplier = 0, 1
        while True:
            digit = connection.recv(1)[0]
            size += (digit & 127) * multiplier
            if not digit & 128:
                break
            multiplier *= 128
        body = b""
        while len(body) < size:
            body += connection.recv(size - len(body))
        return header[0], body

    def broker(server):
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(4)
                assert read_packet(connection)[0] >> 4 == 1  # CONNECT
                connection.sendall(b"\x20\x02\x00\x00")
                header, body = read_packet(connection)
                assert header >> 4 == 8  # SUBSCRIBE
                subscribed.append(body[4:-1].decode())
                connection.sendall(b"\x90\x03" + body[:2] + b"\x00")
                topic, payload = b"home/room", b"21.5"
                body = len(topic).to_bytes(2, "big") + topic + payload
                connection.sendall(b"\x31" + bytes([len(body)]) + body)
                finish.wait(4)
        except Exception as exc:
            errors.append(exc)

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(4)
        thread = threading.Thread(target=broker, args=(server,), daemon=True)
        manager = NetworkSensorManager([{"id": "room", "protocol": "mqtt", "topic": "home/room", "port": server.getsockname()[1]}])
        thread.start()
        try:
            manager.start()
            wait_for(lambda: manager.snapshot().get("network_room") == 21.5)
            assert subscribed == ["home/room"]
        finally:
            manager.stop()
            finish.set()
            thread.join(4)
        assert not errors
        assert not thread.is_alive()


def test_dialog_save_preserves_fields_and_does_not_export_credentials(monkeypatch):
    from PySide6.QtWidgets import QApplication, QDialog
    from src.core import sensors
    from src.core.element import ThemeElement
    from src.ui.network_sensors import NetworkSensorsDialog
    from src.ui.properties import PropertiesPanel
    from src.utils import settings

    app = QApplication.instance() or QApplication([])
    stored = []
    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(settings, "set_setting", lambda key, value: stored.append((key, value)))
    monkeypatch.setattr(sensors, "configure_network_sensors", lambda sources: register_network_sources(sources))
    dialog = NetworkSensorsDialog()
    try:
        dialog._add()
        dialog.fields["id"].setText("room_2")
        dialog.fields["name"].setText("Living room")
        dialog.fields["token"].setText("test-secret")
        dialog.fields["path"].setText("state")
        dialog.fields["unit"].setText(" C")
        dialog._add()
        dialog.fields["protocol"].setCurrentIndex(3)
        dialog.fields["path"].setText("rpm")
        dialog.source_list.setCurrentRow(0)
        assert dialog.fields["token"].text() == "test-secret"
        assert dialog.fields["path"].text() == "state"
        dialog._save()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert stored[0][0] == "network_sensors"
        assert stored[0][1][0]["unit"] == " C"
        assert stored[0][1][1]["protocol"] == "udp"
        assert stored[0][1][1]["port"] == 9000
        panel = PropertiesPanel()
        element = ThemeElement("text", source="network_room_2")
        panel.set_element(element)
        assert panel.get_selected_source() == "network_room_2"
        assert "test-secret" not in str(element.to_dict())
        register_network_sources([])
        panel.source_combo.blockSignals(True)
        panel.setup_source_combo()
        panel.set_source_by_id("network_room_2")
        panel.source_combo.blockSignals(False)
        assert panel.get_selected_source() == "network_room_2"
        assert element.source == "network_room_2"
        panel.deleteLater()
    finally:
        dialog.close()
        register_network_sources([])
        app.processEvents()


def test_dialog_only_shows_fields_for_selected_protocol_and_type(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from src.ui.network_sensors import NetworkSensorsDialog
    from src.utils import settings

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: default)
    dialog = NetworkSensorsDialog()
    try:
        dialog._add()
        keys = {"url", "token", "host", "port", "topic", "username", "password", "tls"}
        expected = ({"url", "token"}, {"host", "port", "topic", "username", "password", "tls"},
                    {"host", "port"}, {"host", "port"})
        for index, visible in enumerate(expected):
            dialog.fields["protocol"].setCurrentIndex(index)
            assert {key for key in keys if not dialog.fields[key].isHidden()} == visible
        for index in (1, 2):
            dialog.fields["value_type"].setCurrentIndex(index)
            assert all(dialog.fields[key].isHidden() for key in ("unit", "scale", "offset", "decimals"))
        dialog.fields["value_type"].setCurrentIndex(0)
        assert all(not dialog.fields[key].isHidden() for key in ("unit", "scale", "offset", "decimals"))
    finally:
        dialog.close()
        app.processEvents()


def test_dialog_missing_credentials_preserves_settings_until_reentered(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from src.core import sensors
    from src.ui.network_sensors import NetworkSensorsDialog
    from src.utils import settings

    app = QApplication.instance() or QApplication([])
    source = {"id": "room", "protocol": "mqtt", "topic": "home/room", "password_ref": "missing"}

    def get_setting(key, default=None, resolve_secrets=True):
        if resolve_secrets:
            raise RuntimeError("A saved sensor credential is missing.")
        return [source]

    monkeypatch.setattr(settings, "get_setting", get_setting)
    save, warning, configure = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(settings, "set_setting", save)
    monkeypatch.setattr(QMessageBox, "warning", warning)
    monkeypatch.setattr(sensors, "configure_network_sensors", configure)
    dialog = NetworkSensorsDialog()
    try:
        dialog._save()
        save.assert_not_called()
        configure.assert_not_called()
        warning.assert_called_once()
        dialog.fields["password"].setText("replacement")
        dialog._save()
        assert save.call_args.args[1][0]["password"] == "replacement"
        configure.assert_called_once()
    finally:
        dialog.close()
        app.processEvents()


def test_cache_merges_network_without_overwriting_hardware(monkeypatch):
    from src.core import sensors
    manager = NetworkSensorManager([{"id": "cpu_temp", "protocol": "udp"}])
    manager._receive(manager.sources, b"22.5")
    monkeypatch.setattr(sensors, "_network_manager", manager)
    monkeypatch.setattr(sensors, "_latest_sensor_data", {"cpu_temp": 50})
    assert sensors.get_cached_sensors() == {"cpu_temp": 50, "network_cpu_temp": 22.5}
    reader = MagicMock()
    reader.get_thermal_sensors.return_value = {"cpu_temp": 50}
    monkeypatch.setattr(sensors, "_reader", reader)
    assert sensors.get_sensors_sync() == {"cpu_temp": 50, "network_cpu_temp": 22.5}
    with pytest.raises(ValueError):
        sensors.configure_network_sensors([{"id": "broken", "protocol": "http"}])
    assert sensors._network_manager is manager


def test_render_snapshot_uses_network_values_then_clears_expired_reading():
    from src.core.element import ThemeElement
    from src.core.renderer import ThemeRenderer
    from src.ui.main_window import ThemeEditorWindow

    element = ThemeElement("text", source="network_room", animate_gauge=False)
    data = {"network_room": 22.5}
    window = SimpleNamespace(get_sensor_data=lambda: data, get_current_page_elements=lambda: [element],
                             background_color="#000000")
    source = validate_sources([{"id": "room", "protocol": "udp", "unit": " C"}])
    try:
        register_network_sources(source)
        snapshot = ThemeEditorWindow._capture_render_snapshot(window)
        assert snapshot["elements"][0][1]["value"] == 22.5
        assert ThemeRenderer().render(snapshot, (200, 100)).size == (200, 100)
        data.clear()
        snapshot = ThemeEditorWindow._capture_render_snapshot(window)
        assert snapshot["elements"][0][1]["value"] == 0
        assert element.value == 0
    finally:
        register_network_sources([])


@pytest.mark.parametrize("kind", ["text", "circle_gauge", "bar_gauge", "line_chart"])
def test_offline_reading_is_visible_and_zero_remains_valid(kind):
    from src.core.element import ThemeElement
    from src.core.renderer import ThemeRenderer
    element = ThemeElement(kind, source="network_room", x=60, y=60, radius=40, width=100, height=40)
    renderer = ThemeRenderer()
    captured = []
    original = renderer.render_element_with_opacity

    def render(img, element, cache_key=None):
        captured.append((element.type, element.text, element.value, element.source))
        original(img, element, cache_key)

    renderer.render_element_with_opacity = render
    snapshot = {"background_color": "#000000", "elements": [(1, element.to_dict())], "sensor_data": {}}
    renderer.render(snapshot, (200, 200))
    if kind == "text":
        assert captured[-1][2] is None
        assert get_value_with_unit(captured[-1][2], "network_room") == "--"
    else:
        assert captured[-1][:2] == ("text", "--")
    snapshot["sensor_data"] = {"network_room": 0}
    renderer.render(snapshot, (200, 200))
    assert captured[-1][0] == kind
    assert element.type == kind
    assert element.source == "network_room"


def test_dialog_probe_uses_unsaved_fields_and_leaves_running_connections(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from src.core import sensors
    from src.ui.network_sensors import NetworkSensorsDialog
    from src.utils import settings

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(settings, "get_setting", lambda key, default=None: default)
    save = MagicMock()
    monkeypatch.setattr(settings, "set_setting", save)
    active = NetworkSensorManager([{"id": "active", "protocol": "udp"}])
    active._receive(active.sources, b"123")
    monkeypatch.setattr(sensors, "_network_manager", active)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.bind(("127.0.0.1", 0))
        port = sender.getsockname()[1]
    dialog = NetworkSensorsDialog()
    try:
        dialog._add()
        dialog.fields["protocol"].setCurrentIndex(3)
        dialog.fields["port"].setValue(port)
        dialog.fields["path"].setText("temperature")
        dialog._test_connection()
        probe = dialog._probe
        assert not dialog.test_button.isEnabled()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            def received():
                sender.sendto(b'{"temperature":23.5}', ("127.0.0.1", port))
                app.processEvents()
                dialog._update_status()
                return dialog._probe_result is not None
            wait_for(received)
        assert "23.5" in dialog.status_label.text()
        wait_for(lambda: not any(t.is_alive() for t in probe._threads))
        assert sensors._network_manager is active
        assert active.snapshot() == {"network_active": 123}
        save.assert_not_called()
        dialog._test_connection()
        probe = dialog._probe
        dialog._probe_deadline = 0
        dialog._update_status()
        assert "without a valid reading" in dialog.status_label.text()
        wait_for(lambda: not any(t.is_alive() for t in probe._threads))
        dialog._test_connection()
        probe = dialog._probe
        dialog.reject()
        assert dialog._probe is None
        wait_for(lambda: not any(t.is_alive() for t in probe._threads))
    finally:
        dialog.reject()
        app.processEvents()
