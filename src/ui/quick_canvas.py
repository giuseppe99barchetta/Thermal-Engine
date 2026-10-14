"""Qt Quick canvas using the existing editor geometry and gestures."""
from PySide6.QtCore import Qt, QRectF, Signal, Slot, Property, QObject
from PySide6.QtQuick import QQuickPaintedItem
from src.ui.canvas_behavior import CanvasBehavior


class QuickCanvas(CanvasBehavior, QQuickPaintedItem):
    element_selected = Signal(int)
    elements_selected = Signal(list)
    element_moved = Signal(int, int, int)
    element_resized = Signal(int)
    drag_started = Signal()
    zoom_changed = Signal()
    controllerChanged = Signal()

    def __init__(self, parent=None):
        QQuickPaintedItem.__init__(self, parent)
        self._controller = None
        self.init_canvas()
        self.setAcceptedMouseButtons(Qt.MouseButton.AllButtons)
        self.setAcceptHoverEvents(True)
        self.setActiveFocusOnTab(True)
        self.widthChanged.connect(self._geometry_changed)
        self.heightChanged.connect(self._geometry_changed)
        self.elements_selected.connect(self._select)
        self.drag_started.connect(self._begin)
        self.element_moved.connect(self._edited)
        self.element_resized.connect(self._edited)
        self.zoom_changed.connect(self._zoomed)

    @Property(QObject, notify=controllerChanged)
    def controller(self):
        return self._controller

    @controller.setter
    def controller(self, value):
        self._controller = value
        if value:
            value.attach_canvas(self)
        self.controllerChanged.emit()

    def _select(self, indices):
        if self._controller:
            self._controller.select_indices(indices)

    def _begin(self):
        if self._controller:
            self._controller.document.begin()

    def _edited(self, *args):
        if self._controller:
            self._controller.sync_selection()

    def _zoomed(self):
        if self._controller:
            self._controller.changed.emit()

    def _geometry_changed(self):
        self._update_scale()
        self.update()
        self._zoomed()

    def hoverMoveEvent(self, event):
        self.mouseMoveEvent(event)

    def rect(self):
        return QRectF(0, 0, self.width(), self.height())

    def setFocus(self, *args):
        self.forceActiveFocus()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._controller:
            changed = self._controller.document.commit()
            self._controller.refresh(mark_dirty=changed)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if self._controller:
            changed = self._controller.document.commit()
            self._controller.refresh(mark_dirty=changed)

    @Slot()
    def fit(self):
        self.set_zoom(None)

    @Slot(float)
    def zoomBy(self, factor):
        self.zoom_by(factor)
