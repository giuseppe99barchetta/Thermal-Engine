# Network sensors

Thermal Engine can display numeric values from MQTT, HTTP, TCP and UDP on any supported display, including Trofeo. Hardware sensors keep working alongside these sources.

Open **Settings > Network Sensors...**, add a sensor and save. Select it under **External Sensors** in an element's Data Source selector. Text labels, gauges and charts use the same value. Set the element's gauge maximum to match your data, for example 9000 for engine RPM.

Each sensor has a stable ID: `room_temperature` becomes the source `network_room_temperature`. Use `{network_room_temperature}` in a text label to include the formatted value. IDs must use lowercase letters, digits and underscores, starting with a letter. Changing an ID requires updating elements that refer to it.

## Payloads

Send a UTF-8 number such as `21.5`, or JSON containing a numeric field. Set **JSON field path** to `temperature` for `{"temperature":21.5}`, `attributes.temperature` for a nested field, or `values.0` for an array item. Leave the path empty for a plain number. Numeric strings such as Home Assistant's `"21.5"` state also work. Units come from the configured suffix, not the payload: use ` C`, ` RPM`, ` km/h`, `%`, or leave it empty.

Payloads are limited to 64 KiB. Invalid JSON fields, nonnumeric values, NaN, infinity and numbers outside +/- 1e12 are rejected. The last valid reading remains available until **Expire reading after** seconds have elapsed. Text templates show `--` when a source is unavailable; gauges and charts return to zero. The settings dialog shows the saved connection's latest value and status. An unsaved edit does not test or change the running connection.

## MQTT / Home Assistant

Install the updated requirements (`pip install -r requirements.txt`); MQTT uses the [Eclipse Paho client](https://eclipse.dev/paho/clients/python/docs/).

Choose MQTT, enter the broker host and port (usually 1883, or 8883 with TLS), a topic, and optional username/password. TLS verifies the broker's certificate with the system's trusted certificate authorities. Publish a number to that topic, or select a JSON field from its messages. Retained messages can supply the initial value. Connections retry and resubscribe after disconnects.

Example: ID `room_temperature`, topic `home/living_room/temperature`, suffix ` C`, empty JSON path. Publish `21.5`. A text label `Living room: {network_room_temperature}` displays `Living room: 21.5 C`. Configure the expiry longer than the sender's normal publish interval. Retained MQTT messages do not carry the measurement's age; expiry starts when Thermal Engine receives them.

## HTTP / Home Assistant REST API

Choose HTTP and enter a full HTTP or HTTPS URL. Thermal Engine sends a GET at the configured polling interval, with a three-second I/O timeout. HTTPS uses normal certificate verification. An optional bearer token supports Home Assistant authentication; tokens are never forwarded across redirects to another origin.

For example, use URL `http://homeassistant.local:8123/api/states/sensor.living_room_temperature`, a Home Assistant long-lived access token in **HTTP bearer token**, path `state`, and suffix ` C`. This reads a numeric entity state. States such as `unknown` or `unavailable` are rejected and eventually expire. See the [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/).

## TCP

Thermal Engine connects as a TCP client to your configured host/port. The sender must serve a UTF-8 stream with one number or JSON document per line, ending each reading with a newline (`\n`). Partial reads and multiple lines in one read are handled. Connections retry when the sender disconnects. This is a receive-only stream; binary telemetry and protocols requiring request commands need an adapter.

## UDP / telemetry senders

Thermal Engine listens on the configured IPv4 bind address/port. Use `127.0.0.1` for a sender on the same PC, or `0.0.0.0` to accept LAN traffic. Send one UTF-8 number or JSON document per datagram. If your sender uses binary telemetry, convert it into this format first; protocol support alone does not decode a game's or SimHub's specific packet format.

Multiple sensors with the same TCP endpoint or UDP bind address/port share a receiver. For example, configure `speed` with path `speed` and `rpm` with path `rpm` on UDP port 9000; send `{"speed":123.5,"rpm":4200}` and choose the two sources for different elements.

Minimal Python sender:

```python
import json
import socket

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
    sender.sendto(json.dumps({"speed": 123.5, "rpm": 4200}).encode(),
                  ("127.0.0.1", 9000))
```

## Settings and sharing

Connections and credentials are stored in the application's local `settings.json`, separate from themes. Theme exports contain source IDs, not broker passwords or API tokens. A recipient configures their own connections with matching IDs. Credentials in the local settings file are plaintext; protect that file and use trusted senders. TCP/UDP have no authentication or encryption. UDP LAN binding accepts packets from any reachable sender.

This version supports up to 64 numeric sensors. It does not decode binary telemetry, display arbitrary string states, or implement Home Assistant MQTT discovery. UDP uses IPv4; TCP can resolve IPv4 or IPv6 hosts.
