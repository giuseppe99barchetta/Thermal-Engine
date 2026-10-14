from src.core.document import EditorDocument
from src.core.element import ThemeElement
import pytest


def test_gesture_is_one_undo_and_redo_restores_pages():
    doc = EditorDocument()
    doc.elements = [ThemeElement("rectangle", x=10, page=2)]
    doc.pages = [1, 2]
    doc.current_page = 2
    doc.selection = [0]
    doc.begin()
    for position in range(20, 100):
        doc.elements[0].x = position
    doc.commit()
    assert len(doc.undo_stack) == 1
    doc.undo()
    assert doc.elements[0].x == 10 and doc.current_page == 2
    doc.redo()
    assert doc.elements[0].x == 99


def test_locked_other_page_and_copy_roundtrip():
    doc = EditorDocument()
    doc.elements = [ThemeElement("rectangle", locked=True), ThemeElement("text", page=2)]
    doc.selection = [0, 1]
    doc.remove_selected()
    assert len(doc.elements) == 2
    doc.selection = [0, 1]
    doc.copy()
    doc.current_page = 2
    doc.paste()
    assert doc.elements[0].page == 2 and doc.elements[0].locked


def test_invalid_load_preserves_document_and_values_export_safely():
    doc = EditorDocument()
    doc.elements = [ThemeElement("text", source="network_rpm", value=1e10)]
    before = doc.snapshot()
    with pytest.raises(ValueError):
        doc.load({"elements": "bad"})
    assert doc.snapshot() == before
    assert doc.export()["elements"][0]["value"] == 0


def test_preset_uniform_scale_and_resize_undo():
    doc = EditorDocument()
    doc.load({"name": "Wide", "display_width": 1280, "display_height": 480,
              "elements": [ThemeElement("rectangle", x=640, y=240).to_dict()]})
    assert (doc.elements[0].x, doc.elements[0].y) == (240, 240)
    doc.resize(1280, 480, stretch=True)
    assert doc.width == 1280
    doc.undo()
    assert doc.width == 480


def test_live_sensor_changes_do_not_create_undo():
    doc = EditorDocument()
    doc.elements = [ThemeElement("text", source="cpu_temp", value=30)]
    doc.begin()
    doc.elements[0].value = 60
    assert not doc.commit()
    assert doc.undo_stack == []


def test_moving_up_a_selection_at_the_top_keeps_its_order():
    doc = EditorDocument()
    first, second, third = ThemeElement("text"), ThemeElement("text"), ThemeElement("text")
    doc.elements = [first, second, third]
    doc.selection = [0, 1]
    doc.reorder("up")
    assert doc.elements == [first, second, third]
    doc.selection = [1, 2]
    doc.reorder("up")
    assert doc.elements == [second, third, first]


def test_empty_pages_survive_json_roundtrip_and_old_themes_still_load():
    import json
    doc = EditorDocument()
    doc.pages = [1, 3, 4]
    doc.current_page = 4
    doc.elements = [ThemeElement("text", page=1)]
    restored = EditorDocument()
    restored.load(json.loads(json.dumps(doc.export())))
    assert restored.pages == [1, 3, 4] and restored.current_page == 4
    restored.load({"elements": [ThemeElement("text", page=2).to_dict()]})
    assert restored.pages == [1, 2] and restored.current_page == 1
    restored.load({"pages": [3], "current_page": 7, "elements": [ThemeElement("text", page=2).to_dict()]})
    assert restored.pages == [2, 3] and restored.current_page == 2


@pytest.mark.parametrize("pages", [[], "bad", [True], [0], [-1], [1.5], [10001]])
def test_invalid_pages_preserve_document(pages):
    doc = EditorDocument()
    previous = doc.snapshot()
    with pytest.raises(ValueError):
        doc.load({"pages": pages, "elements": []})
    assert doc.snapshot() == previous
