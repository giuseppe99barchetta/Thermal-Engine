import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtCore import QPointF
from src.ui.quick_models import RowsModel
from src.ui.quick_canvas import QuickCanvas
from src.core.element import ThemeElement

APP = QApplication.instance() or QApplication([])
QQuickStyle.setStyle("Basic")


def test_qml_component_library_loads():
    engine = QQmlApplicationEngine()
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(str(w) for w in warnings))
    url = (Path(__file__).resolve().parents[1] / "src/ui/qml/components").as_uri()
    engine.loadData(f'''import QtQuick
import QtQuick.Controls
import "{url}" as UI
ApplicationWindow {{ width: 800; height: 600
    Column {{ UI.TButton {{ text: "Save" }} UI.TField {{ text: "Name" }}
    UI.TCombo {{ model: ["One", "Two"] }} UI.TCheck {{ text: "Grid" }} }}
    UI.TDialog {{ title: "Check" }}
}}'''.encode())
    assert engine.rootObjects(), errors
    assert not errors


def test_quick_canvas_keeps_page_indices_and_guides():
    canvas = QuickCanvas()
    canvas.setWidth(640)
    canvas.setHeight(480)
    canvas.set_elements([ThemeElement("rectangle", x=0, y=0, page=1),
                         ThemeElement("rectangle", x=0, y=0, page=2)], page=2)
    assert canvas.get_element_at(QPointF(10, 10)) == 1
    assert canvas.visible_indices() == [1]


def test_quick_canvas_drag_snaps_to_neighbor_edge():
    canvas = QuickCanvas()
    canvas.setWidth(640)
    canvas.setHeight(480)
    canvas.set_elements([ThemeElement("rectangle", x=0, y=300, width=100, height=40),
                         ThemeElement("rectangle", x=400, y=331, width=50, height=50)])
    canvas.set_zoom(1.0)
    canvas.selected_indices = [1]
    canvas.drag_start_positions = {1: (400, 331)}
    # Dragging 297px left puts the left edge at 103, 3px from the anchor's right edge (100)
    dx, dy, guides = canvas._snap_to_guides(-297, 0)
    assert dx == -300 and ("v", 100) in guides and dy == 0


def test_rows_model_replacement_and_roles():
    model = RowsModel()
    model.replace([{"name": "CPU", "value": 21}])
    role = next(iter(model.roleNames()))
    assert model.data(model.index(0), role)["value"] == 21
    model.replace([])
    assert model.rowCount() == 0 and model.get(0) == {}


def test_sensor_values_update_without_resetting_the_model():
    from PySide6.QtTest import QSignalSpy
    model = RowsModel()
    model.replace([{"id": "cpu", "value": 21}, {"id": "gpu", "value": 30}])
    resets, changes = QSignalSpy(model.modelReset), QSignalSpy(model.dataChanged)
    model.replace([{"id": "cpu", "value": 22}, {"id": "gpu", "value": 30}])
    assert resets.count() == 0 and changes.count() == 1 and model.get(0)["value"] == 22
    model.replace([{"id": "gpu", "value": 30}])
    assert resets.count() == 1


def test_full_editor_loads_and_commands_preserve_history(monkeypatch):
    from src.utils import settings
    from src.ui.quick_window import QuickEditorWindow
    from PySide6.QtTest import QTest
    monkeypatch.setattr(settings, "_settings", {**settings.DEFAULT_SETTINGS, "onboarding_completed": True})
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    window = QuickEditorWindow(start_services=False)
    try:
        window.show()
        QTest.qWait(100)
        controller = window.controller
        count = len(controller.elements)
        controller.command("add", "text")
        assert len(controller.elements) == count + 1
        added = controller.elements[0]
        center_x, center_y = controller._view_center()
        assert (added.x + added.width / 2, added.y + added.height / 2) == pytest.approx((center_x, center_y), abs=1)
        added_x = added.x
        controller.beginEdit()
        for position in (200, 220, 240): controller.edit("x", position)
        controller.endEdit()
        assert controller.selected["x"] == 240
        controller.command("undo", None)
        assert controller.selected == {}
        assert controller.elements[0].x == added_x
        controller.command("redo", None)
        assert controller.elements[0].x == 240
        from PySide6.QtCore import Qt
        controller.document.resize(480, 480)
        controller.document.elements = [ThemeElement("rectangle", x=80, y=80, width=60, height=50)]
        controller.document.selection = []
        controller.refresh()
        canvas = controller.canvas
        canvas.set_zoom(1)
        canvas.snap_to_grid = False
        canvas.forceActiveFocus()
        QTest.qWait(50)
        mx, my = canvas.get_canvas_margins()
        start = canvas.mapToScene(QPointF(mx + 100, my + 100)).toPoint()
        end = start + QPointF(40, 20).toPoint()
        history = len(controller.document.undo_stack)
        QTest.mousePress(window.root, Qt.LeftButton, Qt.AltModifier, start)
        QTest.mouseMove(window.root, end, 10)
        QTest.mouseRelease(window.root, Qt.LeftButton, Qt.AltModifier, end)
        assert (controller.elements[0].x, controller.elements[0].y) == (120, 100)
        assert len(controller.document.undo_stack) == history + 1
        controller.command("addPage", None)
        QTest.qWait(30)
        assert controller.state["page"] == 2
        assert controller.document.selection == []
        controller.command("page", 1)
        controller.dirty = False
        QTest.mouseClick(window.root, Qt.LeftButton, Qt.NoModifier, end)
        assert not controller.dirty
        # Tab must leave the canvas with or without a selection
        for selection in ([0], []):
            controller.select_indices(selection)
            canvas.forceActiveFocus()
            QTest.keyClick(window.root, Qt.Key_Tab)
            assert window.root.activeFocusItem() != canvas
        for kind, data in [("settings", controller.settingsData()), ("profiles", controller.settingsData()),
                           ("resolution", {}), ("network", {}), ("devices", {}), ("onboarding", {}),
                           ("condition", {"rule": {}}), ("gradient", {"stops": [[0, "#ffffff"], [1, "#000000"]]}),
                           ("diagnostics", {"text": "Test report"}), ("console", {}), ("update", {"version": "0.13.4", "notes": "Test"})]:
            controller.requestDialog.emit(kind, data)
            QTest.qWait(20)
        assert not window.qml_errors, window.qml_errors
    finally:
        window.dispose()


@pytest.fixture
def editor_window(monkeypatch):
    from src.utils import settings
    from src.ui.quick_window import QuickEditorWindow
    from PySide6.QtTest import QTest
    monkeypatch.setattr(settings, "_settings", {**settings.DEFAULT_SETTINGS, "onboarding_completed": True})
    monkeypatch.setattr(settings, "save_settings", lambda: None)
    window = QuickEditorWindow(start_services=False)
    window.root.setWidth(1280)
    window.root.setHeight(720)
    window.show()
    QTest.qWait(100)
    yield window
    window.dispose()


def qml_value(obj, code):
    from PySide6.QtQml import QQmlExpression, qmlContext
    expression = QQmlExpression(qmlContext(obj), obj, code)
    result, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result


@pytest.mark.parametrize("key", ["Key_Delete", "Key_Backspace"])
@pytest.mark.parametrize("focus", ["canvas", "menuButton", "layerList"])
def test_delete_selection_from_canvas_or_toolbar(editor_window, key, focus):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    window = editor_window
    controller = window.controller
    controller.document.elements = [ThemeElement("text"), ThemeElement("rectangle", locked=True),
                                    ThemeElement("text", page=2)]
    controller.select_indices([0, 1])
    controller.refresh(mark_dirty=False)
    if focus == "layerList":
        # A layer click must leave the search field's editing focus.
        qml_value(window.root, 'search.forceActiveFocus()')
        QTest.qWait(30)
        position = qml_value(window.root, 'layerList.mapToItem(null, 24, 23)')
        QTest.mouseClick(window.root, Qt.LeftButton, Qt.NoModifier, position.toPoint())
        assert window.controller.canvas.hasActiveFocus(), (position, window.root.activeFocusItem(), window.qml_errors)
    else:
        qml_value(window.root, f"{focus}.forceActiveFocus()")
    requests = []
    controller.requestDialog.connect(lambda kind, data: requests.append((kind, data)))
    QTest.keyClick(window.root, getattr(Qt, key))
    QTest.qWait(30)
    assert [kind for kind, _ in requests] == ["confirm"]
    controller.answer(requests[0][1]["token"], True, "")
    assert len(controller.elements) == 2 and controller.elements[0].locked
    assert controller.elements[1].page == 2
    controller.command("undo", None)
    assert len(controller.elements) == 3
    assert not window.qml_errors, window.qml_errors


@pytest.mark.parametrize("key, expected", [("Key_Delete", "ac"), ("Key_Backspace", "bc")])
def test_delete_keys_edit_text_without_removing_elements(editor_window, key, expected):
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtTest import QTest
    window = editor_window
    window.controller.select_indices([0])
    count = len(window.controller.elements)
    requests = []
    window.controller.requestDialog.connect(lambda *args: requests.append(args))
    # Both single-line fields and multiline editors must retain native text editing.
    for field_type in ("TextInput", "TextEdit"):
        component = QQmlComponent(window.engine)
        component.setData(f'import QtQuick\n{field_type} {{ text: "abc"; cursorPosition: 1 }}'.encode(), QUrl())
        field = component.create()
        field.setParentItem(window.root.contentItem())
        field.forceActiveFocus()
        field.setProperty("cursorPosition", 1)
        QTest.keyClick(window.root, getattr(Qt, key))
        assert field.property("text") == expected
        field.setParentItem(None)
        field.deleteLater()
    assert len(window.controller.elements) == count and not requests


@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (853, 480), (640, 360)])
def test_settings_fits_content_and_blocks_editor_delete(editor_window, size):
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest
    window = editor_window
    window.root.setWidth(size[0])
    window.root.setHeight(size[1])
    window.controller.select_indices([0])
    window.controller.requestDialog.emit("settings", window.controller.settingsData())
    QTest.qWait(100)
    dialog = next(o for o in window.root.findChildren(QObject)
                  if o.inherits("QQuickDialog") and o.property("title") == "Settings")
    assert dialog.property("width") == min(760, size[0] - 40)
    assert dialog.property("height") <= size[1] - 20
    scrollers = [o for o in dialog.findChildren(QObject) if o.inherits("QQuickScrollView")]
    assert len(scrollers) == 1  # only the common dialog's small-window fallback
    if size[1] >= 480:
        assert qml_value(dialog, "contentItem.contentHeight <= contentItem.availableHeight + 1")
    requests = []
    window.controller.requestDialog.connect(lambda *args: requests.append(args))
    QTest.keyClick(window.root, Qt.Key_Delete)
    QTest.keyClick(window.root, Qt.Key_Backspace)
    assert not requests
    assert not window.qml_errors, window.qml_errors


def test_panel_resize_is_keyboard_accessible_and_persisted(editor_window, monkeypatch, tmp_path):
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest
    from src.utils import settings
    import json
    destination = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(destination))
    splitter = editor_window.root.findChild(QObject, "layersSplitter")
    splitter.forceActiveFocus()
    previous = editor_window.root.property("layersWidth")
    QTest.keyClick(editor_window.root, Qt.Key_Right)
    QTest.qWait(30)
    assert editor_window.root.property("layersWidth") == previous + 10
    assert json.loads(destination.read_text())["layers_panel_width"] == previous + 10
    editor_window.root.setWidth(800)
    QTest.qWait(30)
    assert not splitter.property("visible")
    assert not editor_window.qml_errors, editor_window.qml_errors


def test_numeric_inspector_rejects_invalid_input_and_supports_arrow_steps(editor_window):
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest
    window = editor_window
    window.controller.document.elements = [ThemeElement("circle_gauge", radius=50)]
    window.controller.select_indices([0])
    window.controller.refresh(mark_dirty=False)
    QTest.qWait(50)
    numeric = window.root.findChild(QObject, "property_radius")
    items = [window.root.contentItem()]
    while numeric is None and items:
        item = items.pop()
        if item.objectName() == "property_radius":
            numeric = item
        items.extend(item.childItems())
    assert numeric is not None, window.qml_errors
    field = numeric.findChild(QObject, "numberInput")
    field.forceActiveFocus()
    field.setProperty("text", "0")
    QTest.keyClick(window.root, Qt.Key_Return)
    assert window.controller.elements[0].radius == 50
    assert field.property("errorText")
    field.setProperty("text", "25")
    QTest.keyClick(window.root, Qt.Key_Up)
    assert window.controller.elements[0].radius == 26
    assert len(window.controller.document.undo_stack) == 1
    assert not window.qml_errors, window.qml_errors


def test_network_form_validates_inline_and_preserves_numeric_ports(editor_window):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    window = editor_window
    window.controller.command("network", None)
    dialog = next(o for o in window.root.findChildren(QObject)
                  if o.inherits("QQuickDialog") and o.property("title") == "Network sensors")
    qml_value(dialog, "add()")
    QTest.qWait(50)
    qml_value(dialog, 'setField("url", "invalid")')
    assert not qml_value(dialog, "check()")
    assert qml_value(dialog, 'errorFor("url")')
    qml_value(dialog, 'setField("protocol", "udp")')
    qml_value(dialog, 'setField("port", 9002.0)')
    assert qml_value(dialog, "check()")
    assert qml_value(dialog, "footer.height > 0")
    assert not window.qml_errors, window.qml_errors
