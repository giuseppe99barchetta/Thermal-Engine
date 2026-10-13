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
