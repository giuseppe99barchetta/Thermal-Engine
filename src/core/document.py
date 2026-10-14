"""Editor state and undo transactions, independent of a window toolkit."""
import copy

from src.core.element import ThemeElement
from src.core.security import validate_preset_schema
from src.core.display_size import resize_theme_elements, validate_display_size


class EditorDocument:
    def __init__(self):
        self.elements = []
        self.theme_name = "Untitled Theme"
        self.background_color = "#0f0f19"
        self.width, self.height = 480, 480
        self.pages = [1]
        self.current_page = 1
        self.selection = []
        self.undo_stack, self.redo_stack = [], []
        self._transaction = None
        self._clipboard = []
        self.video = {}

    def snapshot(self):
        elements = [e.to_dict() for e in self.elements]
        for element in elements:
            if element["source"] != "static": element["value"] = 0
        return copy.deepcopy({"name": self.theme_name, "background_color": self.background_color,
                              "display_width": self.width, "display_height": self.height,
                              "elements": elements,
                              "video_background": self.video, "pages": self.pages,
                              "current_page": self.current_page})

    def restore(self, state):
        self.theme_name = state.get("name", "Untitled Theme")
        self.background_color = state.get("background_color", "#0f0f19")
        self.width, self.height = state["display_width"], state["display_height"]
        self.elements = [ThemeElement.from_dict(e) for e in state["elements"]]
        self.video = copy.deepcopy(state.get("video_background", {}))
        self.pages = sorted(set(state.get("pages", [1])) | {e.page for e in self.elements})
        self.current_page = state.get("current_page", self.pages[0])
        if self.current_page not in self.pages:
            self.current_page = self.pages[0]
        self.selection = []

    def begin(self):
        if self._transaction is None:
            self._transaction = self.snapshot()

    def commit(self):
        changed = self._transaction is not None and self._transaction != self.snapshot()
        if changed:
            self.undo_stack.append(self._transaction)
            self.undo_stack = self.undo_stack[-50:]
            self.redo_stack.clear()
        self._transaction = None
        return changed

    def undo(self):
        self.commit()
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self.restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self.restore(self.redo_stack.pop())

    def load(self, data, scale=True):
        valid, errors = validate_preset_schema(data)
        if not valid:
            raise ValueError("\n".join(errors))
        validate_display_size(data.get("display_width", 1280), data.get("display_height", 480))
        target = (self.width, self.height)
        self.begin()
        self.restore({**data, "display_width": data.get("display_width", 1280),
                      "display_height": data.get("display_height", 480)})
        if scale and (self.width, self.height) != target:
            self._scale_to(target)
            self.width, self.height = target
        self.commit()

    def export(self):
        data = self.snapshot()
        # Live values are presentation state, never a reason to reject a saved theme.
        for element in data["elements"]:
            if element["source"] != "static":
                element["value"] = 0
        return data

    def resize(self, width, height, stretch=False):
        width, height = validate_display_size(width, height)
        self.begin()
        if stretch:
            resize_theme_elements(self.elements, (self.width, self.height), (width, height))
        self.width, self.height = width, height
        self.commit()

    def _scale_to(self, target):
        scale = min(target[0] / self.width, target[1] / self.height)
        ox, oy = (target[0] - self.width * scale) / 2, (target[1] - self.height * scale) / 2
        for element in self.elements:
            element.x, element.y = round(element.x * scale + ox), round(element.y * scale + oy)
            for key in ("width", "height", "radius", "font_size", "label_font_size"):
                setattr(element, key, max(1, round(getattr(element, key) * scale)))

    def selected(self, editable=False):
        return [self.elements[i] for i in self.selection if 0 <= i < len(self.elements)
                and self.elements[i].page == self.current_page and (not editable or not self.elements[i].locked)]

    def copy(self):
        self._clipboard = [copy.deepcopy(e.to_dict()) for e in self.selected()]

    def paste(self):
        if not self._clipboard:
            return
        self.begin()
        pasted = [ThemeElement.from_dict(data) for data in self._clipboard]
        groups = {}
        for element in pasted:
            element.x += 20
            element.y += 20
            element.page = self.current_page
            if element.group:
                groups.setdefault(element.group, element.group + " copy")
                element.group = groups[element.group]
        self.elements[0:0] = pasted
        self.selection = list(range(len(pasted)))
        self.commit()

    def remove_selected(self):
        selected = self.selected(editable=True)
        self.begin()
        self.elements = [e for e in self.elements if e not in selected]
        self.selection = []
        self.commit()

    def reorder(self, direction):
        chosen = self.selected(editable=True)
        if not chosen:
            return
        self.begin()
        if direction in ("front", "back"):
            others = [e for e in self.elements if e not in chosen]
            self.elements = chosen + others if direction == "front" else others + chosen
        else:
            indices = sorted((self.elements.index(e) for e in chosen), reverse=direction == "down")
            for index in indices:
                neighbor = index + (1 if direction == "down" else -1)
                # A selected neighbor is blocked at the edge too: don't swap selected elements among themselves
                if (0 <= neighbor < len(self.elements) and self.elements[neighbor].page == self.current_page
                        and self.elements[neighbor] not in chosen):
                    self.elements[index], self.elements[neighbor] = self.elements[neighbor], self.elements[index]
        self.selection = [self.elements.index(e) for e in chosen]
        self.commit()
