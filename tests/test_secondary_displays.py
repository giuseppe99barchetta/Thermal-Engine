import copy
import io
import time
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from src.core import device_backends, secondary_display
from src.core.device_backends import (DeviceDefinition, DeviceIOError, HIDBackend, USBBulkBackend, _finish,
                                      _hid_candidates, _usb_candidates, resolve_device)
from src.utils import settings

APP = QApplication.instance() or QApplication([])
TROFEO = (0x0416, 0x5302)


def hid(path, serial="", interface=0):
    return {"vendor_id": TROFEO[0], "product_id": TROFEO[1], "path": path, "serial_number": serial, "interface_number": interface}


def win_path(instance, interface):
    return f"\\\\?\\hid#vid_0416&pid_5302&mi_{interface:02d}#{instance}#{{4d1e55b2}}".encode()


def test_one_hid_device_opens_exactly_as_before():
    [device] = _finish(_hid_candidates([hid(win_path("7&aa&0&0000", 0))], platform="win32"))
    assert "path" not in device.extra_params and not device.extra_params["ambiguous"]
    # its interfaces on the same instance collapse into the same device
    [same] = _finish(_hid_candidates([hid(win_path("7&aa&0&0000", 0)), hid(win_path("7&aa&0&0000", 1), interface=1)], platform="win32"))
    assert same.extra_params["identity"] == device.extra_params["identity"]


def test_several_hid_devices_need_distinct_serials():
    two = _finish(_hid_candidates([hid(win_path("7&aa", 0), "A1"), hid(win_path("7&bb", 0), "B2")], platform="win32"))
    assert [d.name for d in two] == ["Thermalright Trofeo AIO", "Thermalright Trofeo AIO #2"]
    assert {d.extra_params["identity"] for d in two} == {"hid:0416:5302:sn:A1", "hid:0416:5302:sn:B2"}
    assert all(d.extra_params["path"] and not d.extra_params["ambiguous"] for d in two)
    for found in ([hid(win_path("7&aa", 0), "X"), hid(win_path("7&bb", 0), "X")],     # repeated serial
                  [hid(b"/dev/hidraw0"), hid(b"/dev/hidraw1")]):                      # no serials, not Windows
        [merged] = _finish(_hid_candidates(found, platform="linux"))
        assert merged.extra_params["ambiguous"] and "path" not in merged.extra_params


class FakeUsb:
    def __init__(self, devices):
        self.devices = devices

    def find(self, find_all=False, idVendor=None, idProduct=None, custom_match=None):
        found = [d for d in self.devices if (d.idVendor, d.idProduct) == (idVendor, idProduct)
                 and (custom_match is None or custom_match(d))]
        return found if find_all else (found[0] if found else None)


def usb_device(bus, address, ports=(1,), serial=None):
    return SimpleNamespace(idVendor=0x87AD, idProduct=0x70DB, bus=bus, address=address, port_numbers=ports,
                           iSerialNumber=1 if serial else 0, serial=serial)


USB_UTIL = SimpleNamespace(get_string=lambda dev, index: dev.serial)


def usb_candidates(devices, monkeypatch):
    monkeypatch.setattr(device_backends, "_has_bulk_out_endpoint", lambda dev, util: True)
    return _finish(_usb_candidates(FakeUsb(devices), USB_UTIL))


def test_usb_identity_follows_the_port_and_survives_reorder_and_new_address(monkeypatch):
    first = usb_candidates([usb_device(1, 5, (2,)), usb_device(2, 5, (3,))], monkeypatch)
    identity = first[0].extra_params["identity"]
    assert identity == "usb:87ad:70db:port:1-2" and first[1].extra_params["identity"] == "usb:87ad:70db:port:2-3"
    swapped = usb_candidates([usb_device(2, 5, (3,)), usb_device(1, 9, (2,))], monkeypatch)  # replugged: new address
    assert resolve_device(identity, swapped).extra_params["usb_address"] == (1, 9)
    assert resolve_device(identity, usb_candidates([usb_device(2, 5, (3,))], monkeypatch)) is None  # absent: no fallback
    keys = {USBBulkBackend(device)._cache_key() for device in first}
    assert keys == {(0x87AD, 0x70DB, 1, 5), (0x87AD, 0x70DB, 2, 5)}  # same address, different buses


def test_incomplete_or_repeated_usb_identities_are_ambiguous(monkeypatch):
    found = usb_candidates([usb_device(1, 5, None), usb_device(1, 6, (2,))], monkeypatch)
    assert found[0].extra_params["ambiguous"] and not found[1].extra_params["ambiguous"]
    twins = usb_candidates([usb_device(1, 5, (1,), "SAME"), usb_device(2, 6, (4,), "SAME")], monkeypatch)
    assert all(d.extra_params["ambiguous"] for d in twins)
    assert resolve_device("usb:87ad:70db:sn:SAME", twins) is None


def test_hid_backend_opens_by_path_only_when_given(monkeypatch):
    calls = []
    fake = SimpleNamespace(device=lambda: SimpleNamespace(open=lambda v, p: calls.append(("open", v, p)),
                                                          open_path=lambda path: calls.append(("path", path)),
                                                          write=lambda data: len(data)))
    monkeypatch.setitem(__import__("sys").modules, "hid", fake)
    definition = DeviceDefinition("T", *TROFEO, "hid")
    assert HIDBackend(definition).connect()
    with_path = copy.copy(definition)
    with_path.extra_params = {"path": b"/dev/hidraw3"}
    assert HIDBackend(with_path).connect()
    assert calls == [("open", *TROFEO), ("path", b"/dev/hidraw3")]


class FakeBackend:
    def __init__(self, device, sent, fail_after=None):
        self.device_def, self.sent, self.fail_after = device, sent, fail_after

    def connect(self): return True
    def disconnect(self): pass
    def is_connected(self): return True

    def send_frame(self, data):
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise DeviceIOError("unplugged")
        self.sent.append((self.device_def.extra_params.get("usb_address"), data))
        return True


def test_extra_display_renders_its_preset_and_reconnects(monkeypatch):
    device = DeviceDefinition("Panel", 0x87AD, 0x70DB, "usb_bulk", width=480, height=480)
    addresses = iter([(1, 5), (1, 9), (1, 9), (1, 9)])

    def enumerate_devices():
        found = copy.copy(device)
        found.extra_params = {"identity": "usb:87ad:70db:port:1-2", "ambiguous": False, "usb_address": next(addresses)}
        return [found]
    sent, backends = [], []
    monkeypatch.setattr(secondary_display, "enumerate_available_devices", enumerate_devices)
    monkeypatch.setattr(secondary_display, "create_backend",
                        lambda d: backends.append(FakeBackend(d, sent, fail_after=2 if not backends else None)) or backends[-1])
    monkeypatch.setattr(secondary_display, "RETRY_SECONDS", 0.01)
    preset = {"name": "Mini", "display_width": 1280, "display_height": 480, "background_color": "#102030",
              "elements": [{"type": "circle_gauge", "source": "cpu_percent", "x": 640, "y": 240, "radius": 100}]}
    out = secondary_display.SecondaryDisplay("usb:87ad:70db:port:1-2", "Panel", "Mini", preset, target_fps=60)
    out.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not any(address == (1, 9) for address, _ in sent):
        time.sleep(0.02)
    out.stop()
    assert any(address == (1, 5) for address, _ in sent) and any(address == (1, 9) for address, _ in sent)
    with Image.open(io.BytesIO(sent[-1][1])) as frame:  # the JPEG the backend receives
        assert frame.size == (480, 480)  # the 1280x480 preset is fitted to this display


def test_game_demand_includes_extra_displays():
    assert secondary_display.uses_game_sources([{"type": "text", "text": "FPS {game_fps}"}])
    assert secondary_display.uses_game_sources([{"type": "text", "condition": {"source": "game_fps"}}])
    assert not secondary_display.uses_game_sources([{"type": "circle_gauge", "source": "cpu_temp"}])


@pytest.fixture
def controller(monkeypatch, tmp_path):
    from src.ui.quick_controller import EditorController
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    result = EditorController(start_services=False)
    yield result
    result.cleanup()


class QuietDisplay:
    def __init__(self, identity, name, preset, data, *args):
        self.identity, self.name, self.preset, self.data, self.status = identity, name, preset, data, "Showing"
        self.stopped = False
    def start(self): pass
    def stop(self): self.stopped = True
    def set_preset(self, preset, data): self.preset, self.data = preset, data
    running = property(lambda self: not self.stopped)


def panel(identity, ambiguous=False, address=(1, 5)):
    device = DeviceDefinition("Panel", 0x87AD, 0x70DB, "usb_bulk", width=480, height=480)
    device.extra_params = {"identity": identity, "ambiguous": ambiguous, "usb_address": address}
    return device


def test_extra_displays_persist_and_never_share_a_device(controller, monkeypatch):
    import src.ui.quick_controller as module
    monkeypatch.setattr(module, "SecondaryDisplay", QuietDisplay)
    errors = []
    monkeypatch.setattr(controller, "error", errors.append)
    preset = next(iter(controller.repository.presets))
    controller._device_defs = [panel("usb:a"), panel("usb:b", ambiguous=True)]
    controller.addSecondaryDisplay(1, preset)
    assert not controller.secondaries and "main display" in errors[-1]
    controller.addSecondaryDisplay(0, preset)
    assert list(controller.secondaries) == ["usb:a"]
    assert settings.get_setting("secondary_displays") == [{"identity": "usb:a", "name": "Panel", "preset": preset}]
    controller.connectDevice(0)
    assert "already show a theme" in errors[-1] and controller.device is None
    controller.addSecondaryDisplay(0, preset)
    assert "already in use" in errors[-1]
    game_preset = {"elements": [{"type": "text", "text": "{game_fps}"}]}
    controller.secondaries["usb:a"].data = game_preset
    assert controller._uses_game_sources()
    controller.removeSecondaryDisplay("usb:a")
    assert not controller.secondaries and settings.get_setting("secondary_displays") == []


def test_main_display_is_found_again_after_its_address_changes(controller, monkeypatch):
    import src.ui.quick_controller as module
    controller.selected_device_def = panel("usb:main", address=(1, 5))
    monkeypatch.setattr(module, "enumerate_available_devices", lambda: [panel("usb:other", address=(2, 2)),
                                                                        panel("usb:main", address=(1, 9))])
    controller._refresh_selected_device()
    assert controller.selected_device_def.extra_params["usb_address"] == (1, 9)


def test_unresolved_main_display_is_not_opened_at_a_stale_address(controller, monkeypatch):
    import src.ui.quick_controller as module
    opened = []
    monkeypatch.setattr(controller, "connect_display", lambda silent=False: opened.append(True) or True)
    controller.selected_device_def = panel("usb:main", address=(1, 5))
    # two unclaimed panels of the same model, none with the saved identity: nothing safe to open
    monkeypatch.setattr(module, "enumerate_available_devices", lambda: [panel("usb:x", address=(1, 5)), panel("usb:y", address=(1, 6))])
    controller._attempt_reconnect()
    assert not opened and controller.selected_device_def.extra_params["usb_address"] == (1, 5)
    controller._reconnect_timer.stop()


def test_main_display_never_opens_a_device_used_by_an_extra_display(controller, monkeypatch):
    import src.ui.quick_controller as module
    created = []
    monkeypatch.setattr(module, "create_backend", lambda device: created.append(device))
    controller.secondaries["usb:a"] = QuietDisplay("usb:a", "Panel", "p", {})
    controller.selected_device_def = panel("usb:a")
    assert controller.connect_display(silent=True) is False and not created
    controller.secondaries.clear()


def test_extra_displays_are_restored_even_when_onboarding_opens(controller, monkeypatch):
    import src.ui.quick_controller as module
    monkeypatch.setattr(module, "SecondaryDisplay", QuietDisplay)
    monkeypatch.setattr(module, "enumerate_available_devices", lambda: [])
    monkeypatch.setattr(module.sensors, "get_sensor_status", lambda: {"cpu_thermal_available": True})
    preset = next(iter(controller.repository.presets))
    settings.set_setting("secondary_displays", [{"identity": "usb:a", "name": "Panel", "preset": preset}])
    settings._settings.update(onboarding_completed=False, last_preset=None, default_preset=None, check_for_updates=False)
    controller._start_services = True
    try:
        controller.startup()
        assert list(controller.secondaries) == ["usb:a"]
    finally:
        controller._start_services = False


def test_address_only_usb_identity_is_never_resolvable(monkeypatch):
    [alone] = usb_candidates([usb_device(1, 5, None)], monkeypatch)
    assert alone.extra_params["ambiguous"]
    assert resolve_device(alone.extra_params["identity"], [alone]) is None


def test_removed_while_connecting_sends_nothing_and_releases_the_device(monkeypatch):
    import threading as th
    release, entered, events = th.Event(), th.Event(), []

    class SlowBackend(FakeBackend):
        def connect(self):
            entered.set(); release.wait(5); return True
        def disconnect(self): events.append("disconnect")
    device = panel("usb:a")
    monkeypatch.setattr(secondary_display, "enumerate_available_devices", lambda: [device])
    monkeypatch.setattr(secondary_display, "create_backend", lambda d: SlowBackend(d, events))
    out = secondary_display.SecondaryDisplay("usb:a", "Panel", "p", {"elements": []}, target_fps=60)
    out.start()
    assert entered.wait(5)
    stopper = th.Thread(target=out.stop)
    stopper.start()
    time.sleep(0.05)
    release.set()  # connect() finishes after stop() was requested
    stopper.join(5); out._thread.join(5)
    assert not out._thread.is_alive() and events == ["disconnect"]  # no frame sent, backend released


def test_connect_errors_are_retried_not_fatal(monkeypatch):
    calls = []

    def flaky():
        calls.append(1)
        raise OSError("usb stack busy")
    monkeypatch.setattr(secondary_display, "enumerate_available_devices", flaky)
    monkeypatch.setattr(secondary_display, "RETRY_SECONDS", 0.01)
    out = secondary_display.SecondaryDisplay("usb:a", "Panel", "p", {"elements": []})
    out.start()
    deadline = time.monotonic() + 3
    while len(calls) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert out._thread.is_alive() and len(calls) >= 3 and out.status == "Not connected"
    out.stop()


def test_autosave_updates_extra_displays_showing_that_theme(controller, monkeypatch, tmp_path):
    controller.repository.user_dir = tmp_path
    controller._command("name", "Shared")
    controller.save()
    controller.secondaries["usb:a"] = QuietDisplay("usb:a", "Panel", "Shared", {"elements": []})
    controller._set_autosave_target("Shared")
    controller._command("background", "#123456")
    controller._autosave()
    assert controller.secondaries["usb:a"].data["background_color"] == "#123456"
    controller.secondaries.clear()


def test_main_display_never_falls_back_to_an_ambiguous_entry_an_extra_display_may_own(controller, monkeypatch):
    import src.ui.quick_controller as module
    hid_model = DeviceDefinition("Trofeo", *TROFEO, "hid")
    hid_model.extra_params = {"identity": "hid:0416:5302:model", "ambiguous": True}
    controller.secondaries["hid:0416:5302:sn:A1"] = QuietDisplay("hid:0416:5302:sn:A1", "Trofeo", "p", {})
    controller.selected_device_def = copy.copy(hid_model)
    controller.selected_device_def.extra_params = {"identity": "hid:0416:5302:sn:B2", "ambiguous": False}
    monkeypatch.setattr(module, "enumerate_available_devices", lambda: [hid_model])
    assert controller._refresh_selected_device() is False
    assert not controller._may_open(hid_model)
    controller.secondaries.clear()
    assert controller._may_open(hid_model)  # no extra display of that model: usable as before


def test_extra_display_chart_history_is_its_own(monkeypatch):
    from elements import get_custom_element
    line_chart = get_custom_element("line_chart")["module"]  # the instance that renders
    device = panel("usb:a")
    out = secondary_display.SecondaryDisplay("usb:a", "Panel", "p", {"display_width": 480, "display_height": 480,
        "elements": [{"type": "line_chart", "name": "Chart", "source": "cpu_percent", "width": 200, "height": 80}]})
    out.selected_device_def = device
    monkeypatch.setattr(secondary_display.sensors, "get_cached_sensors", lambda: {"cpu_percent": 40.0})
    out.render_frame()
    keys = [k for k in line_chart._value_history if isinstance(k, str) and k.endswith("Chart")]
    assert keys == ["secondary/usb:a/Chart"]
    out.stop()
    assert not [k for k in line_chart._value_history if str(k).startswith("secondary/usb:a/")]


def test_wake_resets_the_gif_playback_that_actually_renders(controller, monkeypatch):
    from elements import get_custom_element
    gif = get_custom_element("gif")["module"]
    monkeypatch.setitem(gif._playback_state, "Spinner", {"start_time": 1.0})
    controller.wake()
    assert gif._playback_state["Spinner"]["start_time"] > 1.0


def test_main_display_waiting_to_reconnect_stays_reserved(controller, monkeypatch):
    import src.ui.quick_controller as module
    monkeypatch.setattr(module, "SecondaryDisplay", QuietDisplay)
    errors = []
    monkeypatch.setattr(controller, "error", errors.append)
    controller.selected_device_def = panel("usb:main")
    controller._reconnect_timer.start(60000)  # disconnected, reconnect pending
    controller._device_defs = [panel("usb:main")]
    controller.addSecondaryDisplay(0, next(iter(controller.repository.presets)))
    assert not controller.secondaries and "already in use" in errors[-1]
    controller._reconnect_timer.stop()


def test_removed_display_stays_reserved_until_its_worker_exits(controller, monkeypatch):
    class Lingering(QuietDisplay):
        def stop(self): pass  # worker still inside a USB call
    controller.secondaries["usb:a"] = Lingering("usb:a", "Panel", "p", {})
    controller.removeSecondaryDisplay("usb:a")
    assert not controller._may_open(panel("usb:a"))
    controller._retired["usb:a"].stopped = True  # worker finished
    controller.refresh_sensors()
    assert controller._may_open(panel("usb:a"))


def test_a_theme_shown_on_an_extra_display_cannot_be_deleted(controller):
    name = next(iter(controller.repository.presets))
    controller.secondaries["usb:a"] = QuietDisplay("usb:a", "Panel", name, {})
    with pytest.raises(ValueError, match="Choose another theme"):
        controller._delete_preset(name)
    assert name in controller.repository.presets
    controller.secondaries.clear()
