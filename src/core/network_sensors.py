"""Network sensors; I/O stays outside the hardware and render threads."""

import json
import math
import re
import socket
import threading
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_PAYLOAD = 65536


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if req.has_header("Authorization") and (old.scheme, old.netloc) != (new.scheme, new.netloc):
            raise ValueError("Refusing to forward credentials to another origin.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_sources(sources):
    """Validate local configuration before starting any connections."""
    if not isinstance(sources, list) or len(sources) > 64:
        raise ValueError("Use a list of at most 64 network sensors.")
    result, ids = [], set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("Each sensor must be an object.")
        config = dict(source)
        sensor_id = config.get("id", "")
        if not isinstance(sensor_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", sensor_id):
            raise ValueError("Sensor ID must start with a lowercase letter and use letters, digits or underscores (48 max).")
        if sensor_id in ids:
            raise ValueError("Sensor IDs must be unique.")
        ids.add(sensor_id)
        protocol = config.get("protocol")
        if protocol not in ("http", "mqtt", "tcp", "udp"):
            raise ValueError("Protocol must be HTTP, MQTT, TCP or UDP.")
        config.setdefault("value_type", "number")
        if config["value_type"] not in ("number", "text", "boolean"):
            raise ValueError("Value type must be number, text or boolean.")
        for key, default in (("scale", 1), ("offset", 0)):
            value = config.get(key, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e12:
                raise ValueError(f"{key} must be a finite number within +/- 1e12.")
            config[key] = value
        config.setdefault("decimals", None)
        decimals = config["decimals"]
        if decimals is not None and (isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 6):
            raise ValueError("Decimals must be Auto or an integer between 0 and 6.")
        defaults = {"name": sensor_id, "unit": "", "path": "", "host": "127.0.0.1",
                    "topic": "", "username": "", "password": "", "token": "", "url": ""}
        for key, default in defaults.items():
            config.setdefault(key, default)
            if not isinstance(config[key], str) or len(config[key]) > 2048:
                raise ValueError(f"Invalid {key} for sensor {sensor_id}.")
        for key, default, low, high in (("interval", 1, .1, 3600), ("stale_after", 30, 1, 86400)):
            value = config.get(key, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high} seconds.")
            config[key] = value
        config.setdefault("tls", False)
        if not isinstance(config["tls"], bool):
            raise ValueError("TLS must be true or false.")
        if protocol == "http":
            try:
                parsed = urlsplit(config["url"])
                valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password
                parsed.port
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("HTTP URL must use http:// or https:// without embedded credentials.")
        else:
            port = config.get("port", 8883 if config["tls"] and protocol == "mqtt" else 1883 if protocol == "mqtt" else 9000)
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError("Port must be between 1 and 65535.")
            config["port"] = port
            if not config["host"].strip():
                raise ValueError("Host / bind address is required.")
        if protocol == "mqtt" and (not config["topic"] or "\x00" in config["topic"]):
            raise ValueError("An MQTT topic is required.")
        if protocol == "mqtt":
            levels = config["topic"].split("/")
            if any(("+" in level and level != "+") or ("#" in level and (level != "#" or i != len(levels) - 1))
                   for i, level in enumerate(levels)):
                raise ValueError("MQTT wildcards must occupy a whole level; # must be last.")
        result.append(config)
    return result


def parse_value(payload, path="", value_type="number"):
    """Select and validate a scalar without executing expressions from the sender."""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("Payload is too large.")
    text = payload.decode("utf-8").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = text
    if path:
        for key in path.split("."):
            value = value[int(key)] if isinstance(value, list) else value[key]
    if value_type == "text":
        if not isinstance(value, str) or len(value) > 512 or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Text must be a string of at most 512 characters without control characters.")
        value.encode("utf-8")
        return value
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false", "on", "off", "1", "0"):
            return value.lower() in ("true", "on", "1")
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        raise ValueError("Boolean must be true/false, on/off or 1/0.")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Sensor value must be numeric.")
    value = float(value)
    if not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError("Sensor value must be finite and within +/- 1e12.")
    return value


class NetworkSensorManager:
    def __init__(self, sources):
        self.sources = validate_sources(sources)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._values = {}
        self._status = {s["id"]: "Waiting for data" for s in self.sources}
        self._threads = []
        self._sockets = set()

    def start(self):
        groups = {}
        for source in self.sources:
            # Multiple fields on one stream/datagram share a socket and payload.
            key = (source["protocol"], source["host"], source.get("port")) if source["protocol"] in ("tcp", "udp") else source["id"]
            groups.setdefault(key, []).append(source)
        for sources in groups.values():
            thread = threading.Thread(target=self._run, args=(sources,), daemon=True,
                                      name=f"network-sensor-{sources[0]['id']}")
            self._threads.append(thread)
            thread.start()

    def stop(self, wait=True):
        self._stop.set()
        with self._lock:
            sockets = list(self._sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        if not wait:
            return
        deadline = time.monotonic() + 4
        for thread in self._threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))

    def snapshot(self):
        now = time.monotonic()
        with self._lock:
            return {f"network_{s['id']}": self._values[s["id"]][0]
                    for s in self.sources if s["id"] in self._values
                    and now - self._values[s["id"]][1] <= s["stale_after"]}

    def statuses(self):
        values = self.snapshot()
        with self._lock:
            return {s["id"]: ("Stale" if s["id"] in self._values and f"network_{s['id']}" not in values
                              else self._status[s["id"]]) for s in self.sources}

    def _error(self, sources, message):
        with self._lock:
            for source in sources:
                self._status[source["id"]] = message

    def _receive(self, sources, payload):
        for source in sources:
            try:
                value = parse_value(payload, source["path"], source["value_type"])
                if source["value_type"] == "number":
                    value = value * source["scale"] + source["offset"]
                    if not math.isfinite(value) or abs(value) > 1e12:
                        raise ValueError("Converted reading is out of range.")
            except (ValueError, KeyError, IndexError, TypeError, OverflowError, RecursionError):
                self._error([source], "Invalid payload / JSON field")
                continue
            with self._lock:
                if not self._stop.is_set():
                    self._values[source["id"]] = (value, time.monotonic())
                    self._status[source["id"]] = "Receiving"

    def _run(self, sources):
        source = sources[0]
        if source["protocol"] == "mqtt":
            self._mqtt(source)
            return
        while not self._stop.is_set():
            try:
                if source["protocol"] == "http":
                    headers = {"Authorization": f"Bearer {source['token']}"} if source["token"] else {}
                    with build_opener(_SafeRedirectHandler()).open(Request(source["url"], headers=headers), timeout=3) as response:
                        payload = bytearray()
                        deadline = time.monotonic() + 3
                        while len(payload) <= MAX_PAYLOAD and not self._stop.is_set():
                            chunk = response.read1(min(4096, MAX_PAYLOAD + 1 - len(payload)))
                            if not chunk:
                                break
                            payload.extend(chunk)
                            if time.monotonic() >= deadline:
                                raise TimeoutError("HTTP body exceeded read budget")
                        self._receive(sources, bytes(payload))
                else:
                    self._socket_stream(sources)
            except HTTPError as exc:
                self._error(sources, f"HTTP error: {exc.code}")
            except OSError as exc:
                message = ("Port already in use" if exc.errno in (48, 98, 10048)
                           or getattr(exc, "winerror", None) == 10048 else "Connection / read failed; retrying")
                self._error(sources, message)
            except Exception:
                # Exceptions may contain URLs, credentials or payloads: keep diagnostics generic.
                self._error(sources, "Connection / read failed; retrying")
            self._stop.wait(source["interval"])

    def _socket_stream(self, sources):
        source = sources[0]
        udp = source["protocol"] == "udp"
        # shortcut: UDP uses IPv4, add IPv6 binding when a supported sender needs it.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if udp else socket.create_connection((source["host"], source["port"]), timeout=3)
        try:
            with self._lock:
                self._sockets.add(sock)
            sock.settimeout(.5)
            if udp:
                sock.bind((source["host"], source["port"]))
            buffer = b""
            while not self._stop.is_set():
                try:
                    payload = sock.recv(MAX_PAYLOAD + 1 if udp else 4096)
                except socket.timeout:
                    continue
                if udp:
                    self._receive(sources, payload)
                else:
                    if not payload:
                        raise ConnectionError("Stream closed")
                    buffer += payload
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        self._receive(sources, line)
                    if len(buffer) > MAX_PAYLOAD:
                        raise ValueError("TCP line exceeds payload limit")
        finally:
            with self._lock:
                self._sockets.discard(sock)
            sock.close()

    def _mqtt(self, source):
        client = None
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            if source["username"]:
                client.username_pw_set(source["username"], source["password"])
            if source["tls"]:
                client.tls_set()

            def on_connect(client, userdata, flags, reason_code, properties):
                if reason_code == 0:
                    client.subscribe(source["topic"])
                    self._error([source], "Subscribed; waiting for data")
                else:
                    self._error([source], "Broker rejected connection")

            def on_subscribe(client, userdata, mid, reason_codes, properties):
                if any(code.is_failure for code in reason_codes):
                    self._error([source], "Broker rejected subscription")

            client.on_connect = on_connect
            client.on_subscribe = on_subscribe
            client.on_message = lambda client, userdata, message: self._receive([source], message.payload)
            client.on_connect_fail = lambda client, userdata: self._error([source], "Broker unavailable; retrying")
            client.on_disconnect = lambda client, userdata, flags, reason_code, properties: self._error([source], "Disconnected; retrying")
            client.reconnect_delay_set(1, 30)
            client.connect_async(source["host"], source["port"], keepalive=30)
            client.loop_start()
            self._stop.wait()
        except ImportError:
            self._error([source], "MQTT requires paho-mqtt >= 2")
        except Exception:
            self._error([source], "MQTT setup failed")
        finally:
            if client:
                client.disconnect()
                client.loop_stop()
