"""Import Home Assistant MQTT discovery configs as Thermal Engine MQTT sensors.

Only configs whose meaning can be kept exactly are imported: simple value templates are mapped to
our JSON path (never evaluated), anything else is skipped and counted.
"""
import json
import math
import re
import threading

MAX_ENTITIES = 500
MAX_PAYLOAD = 65536
MAX_TOTAL_BYTES = 8 * 1024 * 1024  # all retained configs together
COMPONENTS = ("sensor", "binary_sensor")
# HA abbreviations (https://www.home-assistant.io/integrations/mqtt/#discovery-payload) we read
ABBREVIATIONS = {"stat_t": "state_topic", "unit_of_meas": "unit_of_measurement", "val_tpl": "value_template",
                 "uniq_id": "unique_id", "dev_cla": "device_class", "stat_cla": "state_class",
                 "exp_aft": "expire_after", "pl_on": "payload_on", "pl_off": "payload_off", "dev": "device"}
NUMERIC_DEVICE_CLASSES = {"temperature", "humidity", "power", "energy", "voltage", "current", "pressure",
                          "battery", "illuminance", "speed", "frequency", "power_factor", "carbon_dioxide",
                          "pm25", "pm10", "signal_strength", "distance", "duration", "weight", "volume"}
_KEY = r"(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\s*'([^']+)'\s*\]|\[\s*\"([^\"]+)\"\s*\])"
_TEMPLATE = re.compile(r"^\{\{\s*(value(?:_json(?:" + _KEY + r")+)?)\s*((?:\|\s*[a-z_]+(?:\(\s*\d+\s*\))?\s*)*)\}\}$")
_TRUE, _FALSE = ("true", "on", "1"), ("false", "off", "0")


def _expand(config):
    config = {ABBREVIATIONS.get(key, key): value for key, value in config.items()}
    base = config.get("~")
    if isinstance(base, str):
        for key, value in list(config.items()):
            if key.endswith("topic") and isinstance(value, str):
                config[key] = value.replace("~", base, 1) if value.startswith("~") else value[:-1] + base if value.endswith("~") else value
    return config


def parse_template(template):
    """'{{ value_json.a.b | round(1) }}' -> ('a.b', 1, has_float); None when it is not a simple form."""
    if template is None:
        return "", None, False
    match = _TEMPLATE.match(template.strip()) if isinstance(template, str) else None
    if not match:
        return None
    keys = [a or b or c for a, b, c in re.findall(_KEY, match.group(1))]
    round_digits, has_float = None, False
    for name, digits in re.findall(r"\|\s*([a-z_]+)(?:\(\s*(\d+)\s*\))?", match.group(5) or ""):
        if name == "float" and not digits:
            has_float = True
        elif name == "round" and digits and int(digits) <= 6 and round_digits is None:
            round_digits, has_float = int(digits), True
        else:
            return None  # int, default, arithmetic... would change the value: skip
    if any("." in key for key in keys):
        return None  # our path syntax cannot express a key containing a dot
    return ".".join(keys), round_digits, has_float


def slug(text, taken):
    base = re.sub(r"[^a-z0-9_]+", "_", str(text).lower()).strip("_") or "ha_sensor"
    if not base[0].isalpha():
        base = "ha_" + base
    base = base[:44]
    name, number = base, 2
    while name in taken:
        name, number = f"{base[:44 - len(str(number)) - 1]}_{number}", number + 1
    taken.add(name)
    return name


def parse_discovery(topic, payload, taken=None):
    """One discovery message -> Thermal Engine source dict, or None when it must be skipped."""
    parts = topic.split("/")
    if len(parts) not in (4, 5) or parts[-1] != "config" or parts[1] not in COMPONENTS or len(payload) > MAX_PAYLOAD:
        return None
    try:
        config = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(config, dict):
        return None
    config = _expand(config)
    state_topic = config.get("state_topic")
    if not isinstance(state_topic, str) or not state_topic or any(c in state_topic for c in "+#\x00"):
        return None
    template = parse_template(config.get("value_template"))
    if template is None:
        return None
    path, round_digits, has_float = template
    binary = parts[1] == "binary_sensor"
    if binary:
        on, off = str(config.get("payload_on", "ON")).lower(), str(config.get("payload_off", "OFF")).lower()
        if on not in _TRUE or off not in _FALSE or round_digits is not None or has_float:
            return None  # reversed, identical or custom payloads would change the state's meaning
        value_type = "boolean"
    elif has_float or config.get("unit_of_measurement") or config.get("state_class") \
            or config.get("device_class") in NUMERIC_DEVICE_CLASSES:
        value_type = "number"
    else:
        value_type = "text"
    device = config.get("device") if isinstance(config.get("device"), dict) else {}
    name = config.get("name") or config.get("unique_id") or parts[-2]
    if device.get("name") and isinstance(name, str) and not name.startswith(str(device["name"])):
        name = f"{device['name']} {name}"
    expire = config.get("expire_after")
    finite = isinstance(expire, (int, float)) and not isinstance(expire, bool) and math.isfinite(expire) and expire > 0
    stale_after = min(86400, max(1, int(expire))) if finite else 86400  # JSON allows Infinity/NaN
    taken = set() if taken is None else taken
    return {"id": slug(config.get("unique_id") or name, taken), "name": str(name)[:100], "protocol": "mqtt",
            "topic": state_topic, "path": path, "value_type": value_type,
            "unit": str(config.get("unit_of_measurement") or "")[:20] if value_type == "number" else "",
            "round_digits": round_digits, "stale_after": stale_after}


def discover(broker, seconds=3.0, client_factory=None):
    """Collect retained discovery configs from the broker of an MQTT draft row.

    Returns (entities sorted by name, skipped count). Credentials are used for this one
    connection only.
    """
    if client_factory is None:
        import paho.mqtt.client as mqtt
        client_factory = lambda: mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # noqa: E731
    messages, lock, done = {}, threading.Lock(), threading.Event()
    state = {"connected": False, "refused": None, "bytes": 0}
    client = client_factory()
    if broker.get("username"):
        client.username_pw_set(broker["username"], broker.get("password") or None)
    if broker.get("tls"):
        client.tls_set()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            state["connected"] = True
            client.subscribe([("homeassistant/+/+/config", 0), ("homeassistant/+/+/+/config", 0)])
        else:
            state["refused"] = str(reason_code)
            done.set()

    def on_message(client, userdata, message):
        payload = message.payload
        if len(payload) > MAX_PAYLOAD:
            return  # ignored before it is kept
        with lock:
            if len(messages) < MAX_ENTITIES * 2 and state["bytes"] + len(payload) <= MAX_TOTAL_BYTES:
                messages[message.topic] = payload
                state["bytes"] += len(payload)

    client.on_connect, client.on_message = on_connect, on_message
    client.connect(broker["host"], int(broker.get("port") or 1883), keepalive=10)
    client.loop_start()
    try:
        done.wait(seconds)
    finally:
        client.disconnect()
        client.loop_stop()
    if state["refused"] is not None:
        raise ConnectionRefusedError(f"the broker refused the connection ({state['refused']}); check user name and password")
    if not state["connected"]:
        raise TimeoutError("the broker did not answer")
    taken, entities, skipped = set(), [], 0
    with lock:
        items = sorted(messages.items())
    for topic, payload in items:
        try:
            entity = parse_discovery(topic, payload, taken)
        except (ValueError, TypeError, OverflowError, AttributeError):
            entity = None  # one malformed message never aborts the whole discovery
        if entity is not None:
            try:  # offer only what the network sensor form can save (topic length, fields...)
                from src.core.network_sensors import validate_sources
                validate_sources([{**entity, "host": broker.get("host") or "127.0.0.1"}])
            except ValueError:
                entity = None
        if entity is None:
            skipped += topic.split("/")[1] in COMPONENTS
        else:
            entities.append(entity)
    entities.sort(key=lambda e: e["name"].lower())
    return entities[:MAX_ENTITIES], skipped
