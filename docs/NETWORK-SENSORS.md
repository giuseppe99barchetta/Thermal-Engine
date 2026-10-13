# Network sensors

Thermal Engine can display numbers, text and boolean values from MQTT, HTTP, TCP and UDP on any supported display, including Trofeo. Hardware sensors keep working alongside these sources.

Open **Settings > Network Sensors...**, add a sensor and save. Select it under **External Sensors** in an element's Data Source selector. Labels and conditional rules use the selected value; numeric gauges and charts support numbers and booleans. Set the element's gauge maximum to match your data, for example 9000 for engine RPM.

Use **Test connection** to try the selected sensor's unsaved fields for up to five seconds. The test shows a received value or connection/payload status, does not save settings, and stops when the dialog closes. For UDP, the test requires a free bind port; an already-running listener on that port remains active and the test reports that the port is in use.

Each sensor has a stable ID: `room_temperature` becomes the source `network_room_temperature`. Use `{network_room_temperature}` in a text label to include the formatted value. IDs must use lowercase letters, digits and underscores, starting with a letter. Changing an ID requires updating elements that refer to it.

## Payloads

Choose **Value type**: **Number** retains the existing numeric behavior; **Text** accepts a string of at most 512 characters for labels and templates; **Boolean** accepts JSON `true`/`false`, `on`/`off` or `1`/`0` and displays `ON`/`OFF`. Text values do not feed numeric gauges or charts. Boolean values can drive numeric elements as 1/0. Unit suffixes apply to numbers only.

For numbers, **Multiplier** and **Offset** apply `display_value = received_value * multiplier + offset` before the reading reaches elements or conditional rules. Defaults (1 and 0) preserve existing behavior. **Decimal places** controls labels and templates (Auto, or 0–6); rounding does not alter the numeric value used by gauges and rules. For example, multiplier 3.6 converts m/s to km/h.

Send a UTF-8 number such as `21.5`, or JSON containing a numeric field. Set **JSON field path** to `temperature` for `{"temperature":21.5}`, `attributes.temperature` for a nested field, or `values.0` for an array item. Leave the path empty for a plain number. Numeric strings such as Home Assistant's `"21.5"` state also work. Units come from the configured suffix, not the payload: use ` C`, ` RPM`, ` km/h`, `%`, or leave it empty.

Payloads are limited to 64 KiB. Invalid fields, values that do not match the selected type, NaN, infinity and numbers outside +/- 1e12 are rejected. The last valid reading remains available until **Expire reading after** seconds have elapsed. Labels, templates, gauges and charts show `--` when a network source is unavailable. A valid zero continues to display as zero. The settings dialog shows the saved connection's latest value and status. Unsaved edits affect a connection only when tested or saved.

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

Connection settings and opaque credential references are stored in local `settings.json`, separate from themes. Passwords and API tokens are stored with [keyring](https://keyring.readthedocs.io/en/stable/) in Windows Credential Manager, macOS Keychain or a supported Linux Secret Service/KWallet store; plaintext keyring backends are rejected. Theme exports contain source IDs, not credentials. A recipient configures their own connections with matching IDs.

Existing plaintext sensor credentials are migrated on startup only after the OS store confirms they can be read back. A failed migration preserves the existing settings and logs a message; install the new requirements and unlock/configure your OS credential store, then relaunch or save the sensors. New saves with credentials fail visibly if secure storage is unavailable. Missing saved secrets must be re-entered, and a failed file save keeps the previous configuration. Moving `settings.json` to another computer does not move its secrets. OS storage protects credentials at rest, not against other processes running with access to the same user's vault.

TCP/UDP have no authentication or encryption. UDP LAN binding accepts packets from any reachable sender; use trusted senders.

This version supports up to 64 sensors. It does not decode binary telemetry or implement Home Assistant MQTT discovery. UDP uses IPv4; TCP can resolve IPv4 or IPv6 hosts.
