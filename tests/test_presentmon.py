import pytest

from src.core import presentmon, sensors
from src.core.constants import get_value_with_unit
from src.core.presentmon import GameFpsMonitor

HEADER = "Application,ProcessID,SwapChainAddress,PresentRuntime,SyncInterval,PresentFlags,CPUStartTime,MsBetweenPresents,MsInPresentAPI\n"


def row(app, ms):
    return f"{app},1234,0x1,DXGI,0,0,1.0,{ms},0.1\n"


def test_reports_the_application_presenting_most_frames():
    monitor = GameFpsMonitor("PresentMon.exe")
    lines = ["PresentMon starting...\n", HEADER] + [row("Game.exe", 8.0)] * 120 + [row("browser.exe", 16.0)] * 10
    lines += [row("Game.exe", "NA"), "truncated,line\n"]
    monitor.consume(lines)
    reading = monitor.snapshot()
    assert reading["game_fps"] == pytest.approx(125) and reading["game_frametime"] == pytest.approx(8.0)
    assert monitor.status == "Receiving"


def test_v1_column_names_and_unsupported_output():
    monitor = GameFpsMonitor("PresentMon.exe")
    monitor.consume(["Application,ProcessID,Runtime,msBetweenPresents", "game.exe,1,DXGI,10"])
    assert monitor.snapshot()["game_fps"] == pytest.approx(100)
    other = GameFpsMonitor("PresentMon.exe")
    other.consume(["Application,ProcessID,FrameTime", "game.exe,1,10"])
    assert other.snapshot() == {} and "Unsupported" in other.status


def test_readings_expire_when_the_game_stops():
    monitor = GameFpsMonitor("PresentMon.exe")
    monitor._add("game.exe", 16.0, now=100.0)
    assert monitor.snapshot(now=100.5)["game_fps"] == pytest.approx(62.5)
    assert monitor.snapshot(now=102.0) == {}
    assert not monitor._frames  # pruned, not kept forever


def test_process_lifecycle_closes_the_trace_session(monkeypatch):
    started, ran = [], []

    class FakeProcess:
        stdout = iter([HEADER, row("game.exe", 10.0)])
        def __init__(self, args, **kwargs): started.append(args)
        def wait(self, timeout=None): return 0
        def poll(self): return None
        def terminate(self): ran.append("terminate")

    monkeypatch.setattr(presentmon.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(presentmon.subprocess, "run", lambda args, **k: ran.append(args))
    monitor = GameFpsMonitor("C:/pm/PresentMon.exe")
    monitor.start()
    monitor._thread.join(timeout=2)
    args = started[0]
    assert "--output_stdout" in args and args[args.index("--session_name") + 1] == presentmon.SESSION
    assert "dwm.exe" in args
    monitor.stop()
    assert ran[0] == "terminate" and "--terminate_existing_session" in ran[1]
    assert monitor.status == "Stopped"


def test_missing_rights_are_reported(monkeypatch):
    class Denied:
        stdout = iter([])
        def __init__(self, *a, **k): pass
        def wait(self, timeout=None): return 1
    monkeypatch.setattr(presentmon.subprocess, "Popen", Denied)
    monitor = GameFpsMonitor("PresentMon.exe")
    monitor.start()
    monitor._thread.join(timeout=2)
    assert "administrator" in monitor.status


def test_unavailable_executable_is_reported(monkeypatch):
    def fail(*a, **k): raise OSError("not found")
    monkeypatch.setattr(presentmon.subprocess, "Popen", fail)
    monitor = GameFpsMonitor("missing.exe")
    monitor.start()
    assert "could not start" in monitor.status and monitor.snapshot() == {}


def test_sensor_runs_only_while_wanted(monkeypatch):
    created = []

    class FakeMonitor:
        status = "Receiving"
        def __init__(self, exe): created.append(self); self.stopped = False
        def start(self): pass
        def stop(self): self.stopped = True
        def snapshot(self): return {"game_fps": 144.0}

    monkeypatch.setattr(sensors.sys, "platform", "win32")
    monkeypatch.setattr(presentmon, "find_presentmon", lambda: "PresentMon.exe")
    monkeypatch.setattr(presentmon, "GameFpsMonitor", FakeMonitor)
    monkeypatch.setattr(sensors, "_game_fps", None)
    sensors.set_game_fps_enabled(True)
    sensors.set_game_fps_enabled(True)  # already running: no second process
    assert len(created) == 1 and sensors.get_cached_sensors()["game_fps"] == 144.0
    sensors.set_game_fps_enabled(False)
    assert created[0].stopped and "game_fps" not in sensors.get_cached_sensors()


def test_units():
    assert get_value_with_unit(143.6, "game_fps") == "144 FPS"
    assert get_value_with_unit(6.94, "game_frametime") == "6.9 ms"
