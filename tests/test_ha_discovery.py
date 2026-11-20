import json
from types import SimpleNamespace

import pytest

from src.core import network_sensors
from src.core.ha_discovery import discover, parse_discovery
from src.core.network_sensors import NetworkSensorManager, validate_sources


def config(**fields):
    return json.dumps(fields).encode()


def test_full_and_abbreviated_configs():
    full = parse_discovery("homeassistant/sensor/kitchen/temp/config", config(
        name="Temperature", state_topic="kitchen/climate", unit_of_measurement="°C",
        value_template="{{ value_json.temperature }}", unique_id="kitchen_temp", device={"name": "Kitchen"}))
    assert full == {"id": "kitchen_temp", "name": "Kitchen Temperature", "protocol": "mqtt", "topic": "kitchen/climate",
                    "path": "temperature", "value_type": "number", "unit": "°C", "round_digits": None, "stale_after": 86400}
    short = parse_discovery("homeassistant/sensor/plug/config", config(
        **{"~": "plugs/desk", "name": "Power", "stat_t": "~/state", "unit_of_meas": "W",
           "val_tpl": "{{ value_json['energy']['power'] | round(1) }}", "exp_aft": 120}))
    assert short["topic"] == "plugs/desk/state" and short["path"] == "energy.power"
    assert short["round_digits"] == 1 and short["stale_after"] == 120
    validate_sources([{**full, "host": "127.0.0.1"}, {**short, "host": "127.0.0.1"}])  # importable as is


@pytest.mark.parametrize("fields", [
    {"state_topic": "a", "value_template": "{{ value_json.x | int }}"},          # would change the value
    {"state_topic": "a", "value_template": "{{ value_json.x * 10 }}"},           # never evaluated
    {"state_topic": "a/+/b"},                                                    # wildcard state topic
    {"value_template": "{{ value }}"},                                           # no state topic
])
def test_unsupported_configs_are_skipped(fields):
    assert parse_discovery("homeassistant/sensor/x/config", config(**fields)) is None
    assert parse_discovery("homeassistant/sensor/x/config", b"{not json") is None


def test_binary_sensors_keep_their_meaning():
    door = parse_discovery("homeassistant/binary_sensor/door/config", config(name="Door", state_topic="door/state"))
    assert door["value_type"] == "boolean" and door["stale_after"] == 86400
    for on, off in (("OFF", "ON"), ("open", "closed"), ("ON", "ON")):
        assert parse_discovery("homeassistant/binary_sensor/door/config",
                               config(state_topic="d", payload_on=on, payload_off=off)) is None


def test_value_types_for_unitless_entities():
    counted = parse_discovery("homeassistant/sensor/c/config", config(state_topic="c", value_template="{{ value_json.count | float }}"))
    plain = parse_discovery("homeassistant/sensor/s/config", config(state_topic="s", value_template="{{ value_json.count }}"))
    assert counted["value_type"] == "number" and plain["value_type"] == "text"
    assert network_sensors.parse_value(b'{"count": 5}', counted["path"], "number") == 5
    assert network_sensors.parse_value(b'{"count": 5}', plain["path"], "text") == "5"


def test_ids_are_unique_slugs():
    taken = set()
    first = parse_discovery("homeassistant/sensor/a/config", config(name="9 Room temp!", state_topic="a"), taken)
    second = parse_discovery("homeassistant/sensor/b/config", config(name="9 Room temp!", state_topic="b"), taken)
    assert first["id"] == "ha_9_room_temp" and second["id"] == "ha_9_room_temp_2"


def test_rounding_and_long_expiry_end_to_end(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(network_sensors.time, "monotonic", lambda: clock[0])
    entity = parse_discovery("homeassistant/sensor/t/config", config(
        name="T", state_topic="t", unit_of_measurement="°C", value_template="{{ value_json.t | round(1) }}"))
    manager = NetworkSensorManager([{**entity, "host": "127.0.0.1"}])
    manager._receive(manager.sources, b'{"t": 21.46}')
    clock[0] += 31  # a retained state that does not change must not go stale after 30 s
    assert manager.snapshot() == {"network_t": 21.5}


def test_discover_reads_retained_configs_with_a_fake_broker():
    class FakeClient:
        def username_pw_set(self, user, password): self.auth = (user, password)
        def tls_set(self): self.tls = True
        def connect(self, host, port, keepalive): self.target = (host, port)
        def subscribe(self, topics): self.topics = topics
        def disconnect(self): pass
        def loop_stop(self): pass
        def loop_start(self):
            self.on_connect(self, None, None, 0, None)
            for topic, payload in (("homeassistant/sensor/a/config", config(name="A", state_topic="a", unit_of_measurement="W")),
                                   ("homeassistant/sensor/b/config", config(name="B", state_topic="b", value_template="{{ x }}")),
                                   ("homeassistant/light/l/config", config(name="L", command_topic="l"))):
                self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))

    client = FakeClient()
    entities, skipped = discover({"host": "broker", "port": 1884, "username": "u", "password": "p", "tls": True},
                                 seconds=0.01, client_factory=lambda: client)
    assert [e["name"] for e in entities] == ["A"] and skipped == 1  # light: not a sensor, not counted
    assert client.target == ("broker", 1884) and client.auth == ("u", "p") and client.tls
    assert ("homeassistant/+/+/config", 0) in client.topics


def test_round_digits_is_validated():
    with pytest.raises(ValueError):
        validate_sources([{"id": "a", "protocol": "mqtt", "topic": "a", "round_digits": 9}])


class Broker:
    """Fake paho client: connect result and retained messages chosen by the test."""
    def __init__(self, reason=0, answer=True, messages=()):
        self.reason, self.answer, self.messages = reason, answer, messages
    def username_pw_set(self, user, password): pass
    def tls_set(self): pass
    def connect(self, host, port, keepalive): pass
    def subscribe(self, topics): pass
    def disconnect(self): pass
    def loop_stop(self): pass
    def loop_start(self):
        if self.answer:
            self.on_connect(self, None, None, self.reason, None)
        for topic, payload in self.messages:
            self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload))


def test_refused_or_silent_brokers_are_errors_not_empty_results():
    with pytest.raises(ConnectionRefusedError):
        discover({"host": "b"}, seconds=0.01, client_factory=lambda: Broker(reason=5))
    with pytest.raises(TimeoutError):
        discover({"host": "b"}, seconds=0.01, client_factory=lambda: Broker(answer=False))


def test_oversized_configs_are_dropped_before_they_are_kept():
    huge = b'{"name": "x", "state_topic": "x", "pad": "' + b"a" * 70000 + b'"}'
    entities, skipped = discover({"host": "b"}, seconds=0.01, client_factory=lambda: Broker(messages=[
        ("homeassistant/sensor/big/config", huge), ("homeassistant/sensor/ok/config", config(name="Ok", state_topic="ok"))]))
    assert [e["name"] for e in entities] == ["Ok"] and skipped == 0  # never stored, so not even counted


def test_non_finite_expiry_and_malformed_messages_do_not_abort_discovery():
    weird = b'{"name": "W", "state_topic": "w", "expire_after": Infinity}'
    assert parse_discovery("homeassistant/sensor/w/config", weird)["stale_after"] == 86400
    broken = b'{"name": {"nested": 1}, "state_topic": "b", "device": {"name": 5}}'
    entities, _ = discover({"host": "b"}, seconds=0.01, client_factory=lambda: Broker(messages=[
        ("homeassistant/sensor/w/config", weird), ("homeassistant/sensor/b/config", broken),
        ("homeassistant/sensor/ok/config", config(name="Ok", state_topic="ok"))]))
    assert "Ok" in [e["name"] for e in entities]


def test_entities_the_form_could_not_save_are_skipped():
    long_topic = "a/" + "b" * 3000
    entities, skipped = discover({"host": "b"}, seconds=0.01, client_factory=lambda: Broker(messages=[
        ("homeassistant/sensor/long/config", config(name="Long", state_topic=long_topic)),
        ("homeassistant/sensor/ok/config", config(name="Ok", state_topic="ok"))]))
    assert [e["name"] for e in entities] == ["Ok"] and skipped == 1
