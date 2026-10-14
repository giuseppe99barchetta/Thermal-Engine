import subprocess
import sys

from src.core.constants import format_sensor_template, gauge_fraction
from src.core.element import ThemeElement
from src.core.renderer import ThemeRenderer


def test_renderer_import_and_frame_need_no_qt():
    subprocess.run([sys.executable, "-c", (
        "import sys; from src.core.renderer import ThemeRenderer; "
        "assert not any(name.startswith('PySide6') for name in sys.modules); "
        "assert ThemeRenderer().render({'background_color': '#123456', 'elements': []}, "
        "(32, 24)).getpixel((0, 0)) == (18, 52, 86)"
    )], check=True)


def test_renderer_layer_order_visibility_and_cache_updates():
    renderer = ThemeRenderer()
    front = ThemeElement("rectangle", x=0, y=0, width=20, height=20, color="#ff0000")
    back = ThemeElement("rectangle", x=0, y=0, width=30, height=30, color="#0000ff")
    snapshot = {"background_color": "#000000", "elements": [(1, front.to_dict()), (2, back.to_dict())]}
    assert renderer.render(snapshot, (40, 40)).getpixel((10, 10)) == (255, 0, 0)
    snapshot["elements"][0][1]["visible"] = False
    assert renderer.render(snapshot, (40, 40)).getpixel((10, 10)) == (0, 0, 255)
    snapshot["elements"][1][1]["color"] = "#00ff00"
    assert renderer.render(snapshot, (40, 40)).getpixel((10, 10)) == (0, 255, 0)


def test_sensor_templates_keep_unknown_tokens_and_format_units():
    assert format_sensor_template("CPU {cpu_temp} · {cpu_percent}", {
        "cpu_temp": 59.2, "cpu_percent": 24.7,
    }) == "CPU 59°C · 25%"
    assert format_sensor_template("{pump_rpm} / {ram_used}", {
        "pump_rpm": 2400, "ram_used": 8.25,
    }) == "2400 RPM / 8.2GB"
    assert format_sensor_template("{unknown} {cpu_temp} {x.__class__}", {}) == "{unknown} -- {x.__class__}"


def test_template_renders_updates_without_mutating_saved_text():
    renderer = ThemeRenderer()
    element = ThemeElement("text", x=0, y=0, width=150, height=40,
                           text="CPU {cpu_temp}", source="cpu_percent")
    snapshot = {"background_color": "#000000", "elements": [(1, element.to_dict())],
                "sensor_data": {"cpu_temp": 50}}
    first = renderer.render(snapshot, (150, 40))
    snapshot["sensor_data"]["cpu_temp"] = 99
    second = renderer.render(snapshot, (150, 40))
    assert first.tobytes() != second.tobytes()
    assert snapshot["elements"][0][1]["text"] == "CPU {cpu_temp}"
    assert snapshot["elements"][0][1]["source"] == "cpu_percent"


def test_rpm_gauge_uses_configured_scale_and_round_trips():
    element = ThemeElement("bar_gauge", x=0, y=0, width=100, height=10,
                           source="pump_rpm", value=2500, max_value=5000,
                           color="#00ff00", background_color="#000000", bar_text_mode="none", auto_color_change=True)
    frame = ThemeRenderer().render({"background_color": "#000000", "elements": [(1, element.to_dict())]}, (120, 20))
    assert frame.getpixel((25, 5)) == (0, 255, 0)
    assert frame.getpixel((75, 5)) == (0, 0, 0)
    assert ThemeElement.from_dict(element.to_dict()).max_value == 5000
    assert ThemeElement.from_dict({"type": "bar_gauge"}).max_value == 100
    assert gauge_fraction(-5, 100) == 0
    assert gauge_fraction(6000, 5000) == 1


def test_date_source_renders_todays_date(monkeypatch):
    import datetime
    from src.core.renderer import ThemeRenderer
    rendered = []
    renderer = ThemeRenderer()
    monkeypatch.setattr(renderer, "render_element_with_opacity", lambda img, element, cache_key=None: rendered.append(element.text))
    element = ThemeElement("text", source="date", text="Monday, January 1")
    renderer.render({"background_color": "#000000", "elements": [(1, element.to_dict())]}, (100, 50))
    now = datetime.datetime.now()
    assert rendered == [f"{now:%A, %B} {now.day}"]
