"""Editor flows on the live Qt Quick controller (ported from the retired Widgets UI tests)."""
import copy
import json
import os
import socket
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication

from src.core import sensors
from src.core.element import ThemeElement
from src.core.network_sensors import NetworkSensorManager
from src.ui.quick_controller import EditorController
from src.utils import settings

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(settings, "_settings", copy.deepcopy(settings.DEFAULT_SETTINGS))
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    result = EditorController(start_services=False)
    yield result
    result.cleanup()


def test_onboarding_applies_size_and_preset_and_connects(controller, monkeypatch):
    device = SimpleNamespace(name="AIO", width=1280, height=480, extra_params={},
                             vendor_id=1, product_id=2, backend_type="hid")
    controller._device_defs = [device]
    monkeypatch.setattr(controller.repository, "presets", {"Wide": {"builtin": True, "data": {
        "name": "Wide", "display_width": 640, "display_height": 360, "elements": [{"type": "text"}]}}})
    connected, prompts = [], []
    monkeypatch.setattr(controller, "connectDevice", connected.append)
    monkeypatch.setattr(controller, "confirm", lambda *args: prompts.append(args))
    controller.finishOnboarding(0, 640, 360, "Wide")
    assert (controller.document.width, controller.document.height) == (640, 360)
    assert settings.get_setting("display_size_overrides")["0001:0002:hid"] == [640, 360]
    assert settings.get_setting("onboarding_completed") is True
    assert settings.get_setting("default_preset") == "Wide"
    # Resizing marks the document dirty, but the wizard's own choice must not ask to discard it
    assert prompts == [] and controller.document.theme_name == "Wide"
    assert connected == [0]


def test_onboarding_blank_theme_can_be_undone(controller):
    controller.document.elements = [ThemeElement("text")]
    controller.finishOnboarding(-1, controller.document.width, controller.document.height, "")
    assert controller.elements == []
    controller.command("undo", None)
    assert len(controller.elements) == 1


def test_condition_edit_is_one_undo_and_respects_lock(controller):
    controller.document.elements = [ThemeElement("text")]
    controller.select_indices([0])
    rule = {"source": "cpu_temp", "operator": ">", "value": "80", "action": "hide"}
    controller.edit("condition", rule)
    assert controller.elements[0].condition == rule and len(controller.document.undo_stack) == 1
    controller.elements[0].locked = True
    controller.edit("condition", {})
    assert controller.elements[0].condition == rule


def test_gesture_edits_are_one_undo(controller):
    controller.document.elements = [ThemeElement("rectangle", x=100)]
    controller.select_indices([0])
    controller.beginEdit()
    controller.edit("x", 105)
    controller.edit("x", 110)
    controller.endEdit()
    assert controller.elements[0].x == 110 and len(controller.document.undo_stack) == 1
    controller.command("undo", None)
    assert controller.elements[0].x == 100


def test_page_snapshot_contains_only_requested_page(controller):
    controller.document.elements = [ThemeElement("rectangle", page=1), ThemeElement("rectangle", page=2)]
    controller.document.pages = [1, 2]
    snapshot = controller._capture_render_snapshot(page=2)
    assert [data["page"] for _, data in snapshot["elements"]] == [2]
    assert controller.current_page == 1


def test_diagnostics_report_names_display_and_sensor_state(controller):
    controller.selected_device_def = SimpleNamespace(name="Test Display")
    with patch.object(sensors, "get_sensor_status", return_value={"cpu_thermal_available": True}):
        report = json.loads(controller.diagnostics())
    assert report["display"] == "Test Display"
    assert report["sensors"]["cpu_thermal_available"] is True
    assert report["resolution"] == [controller.document.width, controller.document.height]


def test_admin_restart_waits_for_current_process(controller):
    execute = MagicMock(return_value=33)
    controller.window = MagicMock()
    with (
        patch("os.getpid", return_value=1234),
        patch("sys.platform", "win32"),
        patch("sys.argv", ["ThermalEngine.exe"]),
        patch("sys.frozen", True, create=True),
        patch("ctypes.windll", SimpleNamespace(shell32=SimpleNamespace(ShellExecuteW=execute)), create=True),
    ):
        controller.command("restartAdmin", None)
    arguments = execute.call_args.args[3]
    assert "--wait-for-pid" in arguments and "1234" in arguments
    controller.window.force_quit.assert_called_once()


def test_saved_network_sensor_keeps_fields_and_secrets_stay_out_of_themes(controller, monkeypatch):
    stored = []
    monkeypatch.setattr(settings, "set_setting", lambda key, value: stored.append((key, value)))
    monkeypatch.setattr(sensors, "configure_network_sensors", lambda sources: None)
    source = {"id": "room_2", "name": "Living room", "protocol": "http", "url": "http://127.0.0.1/state",
              "token": "test-secret", "path": "state", "unit": " C"}
    assert controller.saveNetwork([source])
    key, saved = stored[0]
    assert key == "network_sensors" and saved[0]["unit"] == " C" and saved[0]["path"] == "state"
    element = ThemeElement("text", source="network_room_2")
    assert "test-secret" not in str(element.to_dict())


def test_probe_uses_unsaved_source_and_leaves_running_connections(controller, monkeypatch):
    save = MagicMock()
    monkeypatch.setattr(settings, "set_setting", save)
    active = NetworkSensorManager([{"id": "active", "protocol": "udp"}])
    active._receive(active.sources, b"123")
    monkeypatch.setattr(sensors, "_network_manager", active)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe_port:
        probe_port.bind(("127.0.0.1", 0))
        port = probe_port.getsockname()[1]
    controller.testNetwork({"id": "probe", "protocol": "udp", "host": "127.0.0.1", "port": port, "path": "temperature"})
    deadline = time.monotonic() + 4
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        while controller._probe is not None and time.monotonic() < deadline:
            sender.sendto(b'{"temperature":23.5}', ("127.0.0.1", port))
            time.sleep(0.05)
            controller._probe_tick()
    assert "23.5" in controller._probe_result
    assert sensors._network_manager is active and active.snapshot() == {"network_active": 123}
    save.assert_not_called()


def test_simulated_readings_scale_each_element_and_feed_templates():
    from src.core.frame_pipeline import simulate_snapshot
    snapshot = {"background_color": "#000", "sensor_data": {"cpu_temp": 41.0, "status": "ok"},
                "elements": [(1, {"source": "cpu_temp", "value": 41.0, "max_value": 100}),
                             (2, {"source": "hardware_fan", "value": 0, "max_value": 3000}),
                             (3, {"source": "static", "value": 7})]}
    result = simulate_snapshot(snapshot, 0.5)
    assert [data["value"] for _, data in result["elements"]] == [50.0, 1500.0, 7]
    assert result["sensor_data"] == {"cpu_temp": 50.0, "status": "ok", "hardware_fan": 1500.0}
    assert snapshot["elements"][0][1]["value"] == 41.0  # the live snapshot is not modified


def test_simulation_is_editor_only(controller, monkeypatch):
    monkeypatch.setattr(controller, "get_sensor_data", lambda: {"cpu_temp": 41.0})
    controller.document.elements = [ThemeElement("circle_gauge", source="cpu_temp")]
    controller.command("previewValues", 0.9)
    assert controller.state["previewFraction"] == 0.9
    assert controller._editor_snapshot()["elements"][0][1]["value"] == 90.0
    # What the display receives stays live
    assert controller._capture_render_snapshot()["elements"][0][1]["value"] == 41.0
    controller.command("previewValues", -1)
    assert controller._editor_snapshot()["elements"][0][1]["value"] == 41.0


def test_drag_reorder_is_one_undo_and_keeps_selection(controller):
    a, b, c = ThemeElement("text", name="a"), ThemeElement("text", name="b"), ThemeElement("text", name="c")
    controller.document.elements = [a, b, c]
    controller.select_indices([0])
    controller.moveLayer(0, 2, True)  # drag "a" below "c"
    assert controller.elements == [b, c, a]
    assert controller.document.selection == [2] and len(controller.document.undo_stack) == 1
    controller.moveLayer(2, 0, False)  # and back above "b"
    assert controller.elements == [a, b, c]
    c.locked = True
    controller.moveLayer(2, 0, False)
    assert controller.elements == [a, b, c]


def test_groups_are_folders_in_the_layer_list(controller):
    controller.document.elements = [ThemeElement("text", name="title"),
                                    ThemeElement("circle_gauge", name="cpu", group="Gauges"),
                                    ThemeElement("circle_gauge", name="gpu", group="Gauges", visible=False)]
    controller.refresh(mark_dirty=False)
    rows = [controller.layers_model.get(i) for i in range(controller.layers_model.rowCount())]
    assert [(r["kind"], r["name"]) for r in rows] == [("element", "title"), ("group", "Gauges"), ("element", "cpu"), ("element", "gpu")]
    assert rows[1]["count"] == 2 and rows[1]["visible"] and rows[2]["indented"]
    controller.toggleGroup("Gauges")
    assert controller.layers_model.rowCount() == 2


def test_first_run_theme_matches_the_display_resolution(controller, monkeypatch):
    presets = {"Default": {"builtin": True, "data": {"display_width": 1280, "display_height": 480}},
               "Blue Marble": {"builtin": True, "data": {"display_width": 480, "display_height": 480}},
               "System Monitor": {"builtin": True, "data": {"display_width": 480, "display_height": 480}}}
    monkeypatch.setattr(controller.repository, "presets", presets)
    controller.document.width, controller.document.height = 480, 480
    assert controller._starter_preset() == "System Monitor"
    controller.document.width = 1280
    assert controller._starter_preset() == "Default"
    controller.document.width, controller.document.height = 800, 600
    assert controller._starter_preset() == "Default"


def test_dropped_image_becomes_an_element_at_the_drop_point(controller, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtCore import QUrl
    path = tmp_path / "logo.png"
    Image.new("RGB", (1000, 500), "red").save(path)
    controller.document.width = controller.document.height = 480
    controller.document.elements = []
    monkeypatch.setattr(controller, "canvas", None)  # no canvas: drop at the display center
    controller.dropFiles([QUrl.fromLocalFile(str(path))], 0, 0)
    element = controller.elements[0]
    assert element.type == "image" and element.image_path == str(path)
    assert (element.width, element.height) == (288, 144)  # fits 60% of the display, keeps 2:1
    assert (element.x + element.width / 2, element.y + element.height / 2) == (240, 240)
    assert controller.document.selection == [0] and len(controller.document.undo_stack) == 1


def test_color_swatches_put_recent_picks_before_theme_colors(controller):
    controller.document.background_color = "#000000"
    controller.document.elements = [ThemeElement("text", color="#FF0000", text_color="#ff0000"),
                                    ThemeElement("rectangle", color="#00ff00")]
    controller.select_indices([1])
    controller.edit("color", "#123456")
    swatches = controller.colorSwatches
    assert swatches[0] == "#123456"
    assert swatches.index("#ff0000") < swatches.index("#000000")  # used twice vs once
    assert len(swatches) == len(set(swatches)) <= 10
