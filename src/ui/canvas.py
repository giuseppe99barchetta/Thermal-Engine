"""
CanvasPreview - Visual preview and editing widget.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QImage

from src.core import constants


class CanvasPreview(QWidget):
    element_selected = Signal(int)  # Single selection (for backwards compat)
    elements_selected = Signal(list)  # Multi-selection
    element_moved = Signal(int, int, int)
    element_resized = Signal(int)  # Emitted when element is resized
    drag_started = Signal()  # Emitted when drag/resize starts (for undo)
    zoom_changed = Signal()

    FIT_PADDING = 24  # px around the display frame in fit mode
    GUIDE_SNAP_PX = 6  # Smart-guide snap distance, in widget pixels
    MIN_ZOOM, MAX_ZOOM = 0.1, 8.0

    # Resize handle positions
    HANDLE_NONE = 0
    HANDLE_TL = 1  # Top-left
    HANDLE_TR = 2  # Top-right
    HANDLE_BL = 3  # Bottom-left
    HANDLE_BR = 4  # Bottom-right

    def __init__(self):
        super().__init__()
        self.elements = []  # Full theme list; indices are global everywhere
        self.page = None  # Only elements on this page are drawn/hit-tested (None = all)
        self.selected_indices = []  # Support multiple selection
        self.dragging = False
        self.resizing = False
        self.resize_handle = self.HANDLE_NONE
        self.drag_offset = QPointF(0, 0)
        self.drag_start_positions = {}  # Store start positions for multi-drag
        self.resize_start_pos = QPointF(0, 0)
        self.resize_start_pos_element = (0, 0)
        self.resize_start_size = (0, 0)
        self.resize_start_bounds = None  # For multi-element resize
        self.zoom = None  # None = fit to widget; otherwise display px -> widget px factor
        self.pan = QPointF(0, 0)  # Offset of the frame from centered, in widget px
        self._pan_anchor = None  # Mouse position while middle-button panning
        self.guides = []  # Active smart guides while dragging: ("v", x) / ("h", y) in display px
        self.scale = 1.0
        self.background_color = QColor(15, 15, 25)
        self.handle_size = 10
        self.group_selection_mode = False  # True when a complete group is selected
        # Callable returning the display frame (PIL RGB image at display size).
        # The editor shows exactly what the device receives; None draws only the background.
        self.frame_renderer = None

        # Grid settings
        self.show_grid = True
        self.snap_to_grid = True
        self.grid_spacing = 20  # Grid spacing in actual pixels (not scaled)

        self._update_scale()

        # Allow widget to expand to fill available space
        # Margins will be calculated dynamically in paintEvent
        # Use smaller minimum size to prevent covering page controls when window is small
        self.setMinimumSize(400, 300)  # Reasonable minimum that allows page controls to stay visible
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Enable keyboard input

    def set_elements(self, elements, page=None):
        self.elements = elements
        self.page = page
        self.update()

    def visible_indices(self):
        """Global indices of shown (on this page, not hidden) elements, front (0) to back."""
        return [
            i for i, el in enumerate(self.elements)
            if el.visible and (self.page is None or getattr(el, 'page', 1) == self.page)
        ]

    def set_selected(self, index):
        """Set single selection (backwards compatible)."""
        if index >= 0:
            self.selected_indices = [index]
        else:
            self.selected_indices = []
        self.group_selection_mode = False  # Single selection is never a group selection
        self.update()

    def set_selected_indices(self, indices, group_selection=False):
        """Set multiple selected indices.

        Args:
            indices: List of element indices to select
            group_selection: True if this selection represents a complete group
                             (from clicking on group in tree, not individual elements)
        """
        self.selected_indices = list(indices)
        self.group_selection_mode = group_selection
        self.update()

    def get_selected_index(self):
        """Get single selected index (backwards compatible)."""
        return self.selected_indices[0] if len(self.selected_indices) == 1 else -1

    def set_background_color(self, color):
        self.background_color = QColor(color)
        self._glass_cache_valid = False  # Invalidate glass cache
        self.update()

    def snap_to_grid_coord(self, value):
        """Snap a coordinate value to the grid."""
        if not self.snap_to_grid:
            return value
        return round(value / self.grid_spacing) * self.grid_spacing

    def set_show_grid(self, show):
        """Toggle grid visibility."""
        self.show_grid = show
        self.update()

    def set_snap_to_grid(self, snap):
        """Toggle snap to grid."""
        self.snap_to_grid = snap

    def _update_scale(self):
        """Recompute scale and frame size from the zoom mode and widget size."""
        if self.zoom is None:
            avail_w = max(1, self.width() - 2 * self.FIT_PADDING)
            avail_h = max(1, self.height() - 2 * self.FIT_PADDING)
            self.scale = min(avail_w / constants.DISPLAY_WIDTH, avail_h / constants.DISPLAY_HEIGHT)
            self.pan = QPointF(0, 0)
        else:
            self.scale = self.zoom
        self.canvas_width = int(constants.DISPLAY_WIDTH * self.scale)
        self.canvas_height = int(constants.DISPLAY_HEIGHT * self.scale)

    def set_zoom(self, zoom, anchor=None):
        """Set zoom (None = fit). Keeps the display point under `anchor` (widget pos) still."""
        if zoom is not None:
            zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
        before = self.widget_to_canvas_pos(anchor) / self.scale if anchor is not None else None
        self.zoom = zoom
        self._update_scale()
        if before is not None and zoom is not None:
            after = self.widget_to_canvas_pos(anchor) / self.scale
            self.pan += (after - before) * self.scale
        self.zoom_changed.emit()
        self.update()

    def zoom_by(self, factor, anchor=None):
        self.set_zoom(self.scale * factor, anchor)

    def resizeEvent(self, event):
        self._update_scale()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if delta.y():
                self.zoom_by(1.15 if delta.y() > 0 else 1 / 1.15, event.position())
        elif self.zoom is not None:
            # Scroll the zoomed view; Shift scrolls horizontally on mice without a tilt wheel
            dx, dy = delta.x(), delta.y()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                dx, dy = dy, 0
            self.pan += QPointF(dx, dy) / 2
            self.update()
        else:
            super().wheelEvent(event)

    def get_canvas_margins(self):
        """Top-left of the display frame in widget coordinates (centered, plus pan)."""
        margin_x = (self.width() - self.canvas_width) // 2 + int(self.pan.x())
        margin_y = (self.height() - self.canvas_height) // 2 + int(self.pan.y())
        return margin_x, margin_y

    def draw_grid(self, painter):
        """Draw grid lines on canvas."""
        grid_color = QColor(60, 60, 80, 100)  # Semi-transparent grid lines
        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DotLine))

        # Scaled grid spacing
        spacing = int(self.grid_spacing * self.scale)

        # Draw vertical lines
        x = spacing
        while x < self.canvas_width:
            painter.drawLine(x, 0, x, self.canvas_height)
            x += spacing

        # Draw horizontal lines
        y = spacing
        while y < self.canvas_height:
            painter.drawLine(0, y, self.canvas_width, y)
            y += spacing

    def widget_to_canvas_pos(self, widget_pos):
        """Convert widget coordinates to canvas coordinates (accounting for margin)."""
        margin_x, margin_y = self.get_canvas_margins()
        return QPointF(
            widget_pos.x() - margin_x,
            widget_pos.y() - margin_y
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Dark background for the margin area, then center the canvas
        painter.fillRect(self.rect(), QColor(25, 25, 35))
        margin_x, margin_y = self.get_canvas_margins()
        painter.translate(margin_x, margin_y)

        canvas_rect = QRectF(0, 0, self.canvas_width, self.canvas_height)
        frame = self.frame_renderer() if self.frame_renderer else None
        if frame is not None:
            frame = frame.convert("RGB")
            data = frame.tobytes("raw", "RGB")  # must outlive the QImage below
            image = QImage(data, frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888)
            painter.drawImage(canvas_rect, image)
        else:
            painter.fillRect(canvas_rect, self.background_color)

        painter.setPen(QPen(QColor(100, 100, 120), 3))
        painter.drawRect(canvas_rect)

        if self.show_grid:
            self.draw_grid(painter)

        # Editor-only overlays: placeholders for empty media, then selection
        for i in self.visible_indices():
            element = self.elements[i]
            if self._is_empty_media(element):
                self.draw_placeholder(painter, element)
            if i in self.selected_indices and not self.group_selection_mode:
                self.draw_selection_box(painter, element, 0, 0)

        if len(self.selected_indices) > 1:
            self.draw_multi_selection_box(painter)

        self.draw_guides(painter)
        painter.resetTransform()
        self.draw_rulers(painter)
        painter.end()

    def draw_rulers(self, painter):
        """Pixel coordinates stay anchored to the display while zooming and panning."""
        thickness = 18
        painter.fillRect(0, 0, self.width(), thickness, QColor(35, 35, 45))
        painter.fillRect(0, 0, thickness, self.height(), QColor(35, 35, 45))
        painter.setPen(QColor(160, 160, 180))
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        margin_x, margin_y = self.get_canvas_margins()
        step = 10
        while step * self.scale < 55:
            step *= 2
        for value in range(0, constants.DISPLAY_WIDTH + 1, step):
            x = int(margin_x + value * self.scale)
            if thickness <= x < self.width():
                painter.drawLine(x, 13, x, thickness)
                painter.drawText(x + 3, 11, str(value))
        for value in range(0, constants.DISPLAY_HEIGHT + 1, step):
            y = int(margin_y + value * self.scale)
            if thickness <= y < self.height():
                painter.drawLine(13, y, thickness, y)
                painter.save()
                painter.translate(11, y - 3)
                painter.rotate(-90)
                painter.drawText(0, 0, str(value))
                painter.restore()

    @staticmethod
    def _is_empty_media(element):
        if element.type == "image":
            return not element.image_path
        if element.type == "gif":
            return not getattr(element, "gif_path", "")
        return False

    def draw_placeholder(self, painter, element):
        """Media elements without a file render nothing; keep them visible and clickable."""
        bounds = self.get_element_bounds(element)
        painter.setPen(QPen(QColor(120, 120, 150), 1, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(40, 40, 60, 160))
        painter.drawRect(bounds)
        painter.setPen(QColor(150, 150, 180))
        label = "No image" if element.type == "image" else "No GIF"
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, label)

    def get_element_bounds(self, element):
        """Get the bounding rectangle for an element."""
        x = int(element.x * self.scale)
        y = int(element.y * self.scale)

        if element.type in ["circle_gauge", "analog_clock"]:
            radius = int(element.radius * self.scale)
            return QRectF(x - radius, y - radius, radius * 2, radius * 2)
        elif hasattr(element, 'width') and hasattr(element, 'height') and element.width > 0 and element.height > 0:
            width = int(element.width * self.scale)
            height = int(element.height * self.scale)
            return QRectF(x, y, width, height)
        else:
            return QRectF(x, y, 100, 50)

    def draw_selection_box(self, painter, element, x, y):
        bounds = self.get_element_bounds(element)

        pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bounds)

        # Draw resize handles at corners
        hs = self.handle_size
        handles = [
            (bounds.left(), bounds.top()),      # TL
            (bounds.right(), bounds.top()),     # TR
            (bounds.left(), bounds.bottom()),   # BL
            (bounds.right(), bounds.bottom()),  # BR
        ]

        painter.setPen(Qt.PenStyle.NoPen)
        for hx, hy in handles:
            painter.setBrush(QBrush(QColor(0, 150, 255)))
            painter.drawRect(int(hx - hs / 2), int(hy - hs / 2), hs, hs)

    def get_multi_selection_bounds(self):
        """Get combined bounding rectangle for all selected elements."""
        if not self.selected_indices:
            return None

        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        for idx in self.selected_indices:
            if 0 <= idx < len(self.elements):
                bounds = self.get_element_bounds(self.elements[idx])
                min_x = min(min_x, bounds.left())
                min_y = min(min_y, bounds.top())
                max_x = max(max_x, bounds.right())
                max_y = max(max_y, bounds.bottom())

        if min_x == float('inf'):
            return None

        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def draw_multi_selection_box(self, painter):
        """Draw a combined selection box around all selected elements."""
        bounds = self.get_multi_selection_bounds()
        if bounds is None:
            return

        # Draw outer selection box
        pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bounds)

        # Draw resize handles at corners
        hs = self.handle_size
        handles = [
            (bounds.left(), bounds.top()),
            (bounds.right(), bounds.top()),
            (bounds.left(), bounds.bottom()),
            (bounds.right(), bounds.bottom()),
        ]

        painter.setPen(Qt.PenStyle.NoPen)
        for hx, hy in handles:
            painter.setBrush(QBrush(QColor(0, 150, 255)))
            painter.drawRect(int(hx - hs / 2), int(hy - hs / 2), hs, hs)

    def get_handle_at(self, pos, element):
        """Check if position is over a resize handle. Returns handle type or HANDLE_NONE."""
        bounds = self.get_element_bounds(element)
        hs = self.handle_size

        handles = {
            self.HANDLE_TL: (bounds.left(), bounds.top()),
            self.HANDLE_TR: (bounds.right(), bounds.top()),
            self.HANDLE_BL: (bounds.left(), bounds.bottom()),
            self.HANDLE_BR: (bounds.right(), bounds.bottom()),
        }

        for handle_type, (hx, hy) in handles.items():
            handle_rect = QRectF(hx - hs, hy - hs, hs * 2, hs * 2)
            if handle_rect.contains(pos):
                return handle_type

        return self.HANDLE_NONE

    def get_element_at(self, pos):
        # Check from index 0 first (top of tree = front of display)
        # This matches rendering order where index 0 is drawn last (on top)
        for i in self.visible_indices():
            element = self.elements[i]
            x = element.x * self.scale
            y = element.y * self.scale

            if element.type in ["circle_gauge", "analog_clock"]:
                radius = element.radius * self.scale
                dist = ((pos.x() - x) ** 2 + (pos.y() - y) ** 2) ** 0.5
                if dist <= radius:
                    return i
            elif hasattr(element, 'width') and hasattr(element, 'height') and element.width > 0 and element.height > 0:
                # Any element with width/height properties
                width = element.width * self.scale
                height = element.height * self.scale
                if x <= pos.x() <= x + width and y <= pos.y() <= y + height:
                    return i

        return -1

    def get_multi_handle_at(self, pos):
        """Check if position is over a resize handle for multi-selection."""
        bounds = self.get_multi_selection_bounds()
        if bounds is None:
            return self.HANDLE_NONE

        hs = self.handle_size
        handles = {
            self.HANDLE_TL: (bounds.left(), bounds.top()),
            self.HANDLE_TR: (bounds.right(), bounds.top()),
            self.HANDLE_BL: (bounds.left(), bounds.bottom()),
            self.HANDLE_BR: (bounds.right(), bounds.bottom()),
        }

        for handle_type, (hx, hy) in handles.items():
            handle_rect = QRectF(hx - hs, hy - hs, hs * 2, hs * 2)
            if handle_rect.contains(pos):
                return handle_type

        return self.HANDLE_NONE

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_anchor = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.widget_to_canvas_pos(event.position())
            modifiers = event.modifiers()
            ctrl_held = modifiers & Qt.KeyboardModifier.ControlModifier
            shift_held = modifiers & Qt.KeyboardModifier.ShiftModifier

            # Check if clicking on resize handle of selected element(s)
            # Don't allow resizing if any selected element is locked
            any_locked = any(self.elements[idx].locked for idx in self.selected_indices) if self.selected_indices else False

            if len(self.selected_indices) > 1 and not any_locked:
                # Multi-selection resize handle check
                handle = self.get_multi_handle_at(pos)
                if handle != self.HANDLE_NONE:
                    self.drag_started.emit()
                    self.resizing = True
                    self.resize_handle = handle
                    self.resize_start_pos = pos
                    self.resize_start_bounds = self.get_multi_selection_bounds()
                    # Store original positions and sizes for all selected elements
                    self.resize_start_elements = {}
                    for idx in self.selected_indices:
                        el = self.elements[idx]
                        if el.type in ["circle_gauge", "analog_clock"]:
                            self.resize_start_elements[idx] = (el.x, el.y, el.radius, el.radius)
                        else:
                            self.resize_start_elements[idx] = (el.x, el.y, el.width, el.height)
                    return
            elif len(self.selected_indices) == 1 and not any_locked:
                element = self.elements[self.selected_indices[0]]
                handle = self.get_handle_at(pos, element)
                if handle != self.HANDLE_NONE:
                    self.drag_started.emit()
                    self.resizing = True
                    self.resize_handle = handle
                    self.resize_start_pos = pos
                    self.resize_start_pos_element = (element.x, element.y)
                    if element.type in ["circle_gauge", "analog_clock"]:
                        self.resize_start_size = (element.radius, element.radius)
                    else:
                        self.resize_start_size = (element.width, element.height)
                    return

            # Check if clicking on an element
            index = self.get_element_at(pos)

            if index >= 0:
                clicked_element = self.elements[index]
                clicked_group = getattr(clicked_element, 'group', None)

                if ctrl_held:
                    # Ctrl+click: Toggle selection (respects groups)
                    if clicked_group:
                        # Get all indices in this group
                        group_indices = [i for i in self.visible_indices() if getattr(self.elements[i], 'group', None) == clicked_group]
                        # Check if entire group is selected
                        all_selected = all(i in self.selected_indices for i in group_indices)
                        if all_selected:
                            # Deselect entire group
                            for i in group_indices:
                                if i in self.selected_indices:
                                    self.selected_indices.remove(i)
                        else:
                            # Select entire group
                            for i in group_indices:
                                if i not in self.selected_indices:
                                    self.selected_indices.append(i)
                    else:
                        # Ungrouped element - toggle individual
                        if index in self.selected_indices:
                            self.selected_indices.remove(index)
                        else:
                            self.selected_indices.append(index)
                elif shift_held and self.selected_indices:
                    # Shift+click: Range selection
                    last_selected = self.selected_indices[-1]
                    start, end = min(last_selected, index), max(last_selected, index)
                    for i in self.visible_indices():
                        if start <= i <= end and i not in self.selected_indices:
                            self.selected_indices.append(i)
                else:
                    # Normal click behavior:
                    # - If element already selected (e.g., via tree), keep current selection for dragging
                    # - If element not selected, select entire group (or just element if ungrouped)
                    if index in self.selected_indices:
                        # Already selected - keep current selection (allows dragging individual from tree selection)
                        pass
                    elif clicked_group:
                        # Not selected, but in a group - select entire group
                        group_indices = [i for i in self.visible_indices() if getattr(self.elements[i], 'group', None) == clicked_group]
                        self.selected_indices = group_indices
                        self.group_selection_mode = True
                    else:
                        # Ungrouped element - single selection
                        self.selected_indices = [index]
                        self.group_selection_mode = False

                # Check if any selected element is locked - don't allow dragging
                any_locked = any(self.elements[idx].locked for idx in self.selected_indices)

                # Start dragging (only if not locked)
                if not any_locked:
                    self.drag_started.emit()
                    self.dragging = True
                    # Store start positions for all selected elements
                    self.drag_start_positions = {}
                    for idx in self.selected_indices:
                        el = self.elements[idx]
                        self.drag_start_positions[idx] = (el.x, el.y)
                    self.drag_start_mouse = pos

                # Emit signals
                if len(self.selected_indices) == 1:
                    self.element_selected.emit(self.selected_indices[0])
                else:
                    self.element_selected.emit(-1)  # -1 indicates multi-select
                self.elements_selected.emit(self.selected_indices.copy())
            else:
                # Clicked on empty space
                if not ctrl_held and not shift_held:
                    self.selected_indices = []
                    self.element_selected.emit(-1)
                    self.elements_selected.emit([])

            self.update()

    def mouseMoveEvent(self, event):
        if self._pan_anchor is not None:
            if self.zoom is None:
                self.zoom = self.scale  # Panning leaves fit mode at the current scale
                self.zoom_changed.emit()
            self.pan += event.position() - self._pan_anchor
            self._pan_anchor = event.position()
            self.update()
            return
        pos = self.widget_to_canvas_pos(event.position())

        # Handle multi-element resizing
        if self.resizing and len(self.selected_indices) > 1 and self.resize_start_bounds:
            dx = (pos.x() - self.resize_start_pos.x()) / self.scale
            dy = (pos.y() - self.resize_start_pos.y()) / self.scale

            orig_bounds = self.resize_start_bounds
            orig_w = orig_bounds.width() / self.scale
            orig_h = orig_bounds.height() / self.scale

            # Calculate scale factors
            if self.resize_handle in [self.HANDLE_TR, self.HANDLE_BR]:
                scale_x = (orig_w + dx) / orig_w if orig_w > 0 else 1
            elif self.resize_handle in [self.HANDLE_TL, self.HANDLE_BL]:
                scale_x = (orig_w - dx) / orig_w if orig_w > 0 else 1
            else:
                scale_x = 1

            if self.resize_handle in [self.HANDLE_BL, self.HANDLE_BR]:
                scale_y = (orig_h + dy) / orig_h if orig_h > 0 else 1
            elif self.resize_handle in [self.HANDLE_TL, self.HANDLE_TR]:
                scale_y = (orig_h - dy) / orig_h if orig_h > 0 else 1
            else:
                scale_y = 1

            scale_x = max(0.1, scale_x)
            scale_y = max(0.1, scale_y)

            # Apply scale to all selected elements
            anchor_x = orig_bounds.right() / self.scale if self.resize_handle in [self.HANDLE_TL, self.HANDLE_BL] else orig_bounds.left() / self.scale
            anchor_y = orig_bounds.bottom() / self.scale if self.resize_handle in [self.HANDLE_TL, self.HANDLE_TR] else orig_bounds.top() / self.scale

            for idx, (ox, oy, ow, oh) in self.resize_start_elements.items():
                el = self.elements[idx]
                if el.type in ["circle_gauge", "analog_clock"]:
                    new_radius = max(30, int(ow * (scale_x + scale_y) / 2))
                    el.radius = new_radius
                    el.x = int(anchor_x + (ox - anchor_x) * scale_x)
                    el.y = int(anchor_y + (oy - anchor_y) * scale_y)
                else:
                    el.width = max(20, int(ow * scale_x))
                    el.height = max(20, int(oh * scale_y))
                    el.x = int(anchor_x + (ox - anchor_x) * scale_x)
                    el.y = int(anchor_y + (oy - anchor_y) * scale_y)

            self.element_resized.emit(-1)
            self.update()
            return

        # Handle single element resizing
        if self.resizing and len(self.selected_indices) == 1:
            element = self.elements[self.selected_indices[0]]
            dx = (pos.x() - self.resize_start_pos.x()) / self.scale
            dy = (pos.y() - self.resize_start_pos.y()) / self.scale

            if element.type in ["circle_gauge", "analog_clock"]:
                if self.resize_handle in [self.HANDLE_BR, self.HANDLE_TR]:
                    new_radius = max(30, int(self.resize_start_size[0] + (dx + dy) / 2))
                else:
                    new_radius = max(30, int(self.resize_start_size[0] - (dx + dy) / 2))
                element.radius = new_radius
            else:
                new_width, new_height = self.resize_start_size

                if self.resize_handle in [self.HANDLE_TR, self.HANDLE_BR]:
                    new_width = max(20, int(self.resize_start_size[0] + dx))
                elif self.resize_handle in [self.HANDLE_TL, self.HANDLE_BL]:
                    new_width = max(20, int(self.resize_start_size[0] - dx))
                    element.x = int(self.resize_start_pos_element[0] + dx)

                if self.resize_handle in [self.HANDLE_BL, self.HANDLE_BR]:
                    new_height = max(20, int(self.resize_start_size[1] + dy))
                elif self.resize_handle in [self.HANDLE_TL, self.HANDLE_TR]:
                    new_height = max(20, int(self.resize_start_size[1] - dy))
                    element.y = int(self.resize_start_pos_element[1] + dy)

                if element.type == "image" and element.scale_proportionally and element.aspect_ratio > 0:
                    width_ratio = new_width / self.resize_start_size[0] if self.resize_start_size[0] > 0 else 1
                    height_ratio = new_height / self.resize_start_size[1] if self.resize_start_size[1] > 0 else 1

                    if abs(width_ratio - 1) > abs(height_ratio - 1):
                        new_height = max(20, int(new_width / element.aspect_ratio))
                    else:
                        new_width = max(20, int(new_height * element.aspect_ratio))

                    if self.resize_handle == self.HANDLE_TL:
                        element.x = int(self.resize_start_pos_element[0] + self.resize_start_size[0] - new_width)
                        element.y = int(self.resize_start_pos_element[1] + self.resize_start_size[1] - new_height)
                    elif self.resize_handle == self.HANDLE_TR:
                        element.y = int(self.resize_start_pos_element[1] + self.resize_start_size[1] - new_height)
                    elif self.resize_handle == self.HANDLE_BL:
                        element.x = int(self.resize_start_pos_element[0] + self.resize_start_size[0] - new_width)

                element.width = new_width
                element.height = new_height

            self.element_resized.emit(self.selected_indices[0])
            self.update()
            return

        # Handle dragging (single or multiple elements)
        if self.dragging and self.selected_indices:
            dx = (pos.x() - self.drag_start_mouse.x()) / self.scale
            dy = (pos.y() - self.drag_start_mouse.y()) / self.scale

            # Smart guides win over the grid on the axis they snap (Alt disables them)
            self.guides = []
            if not event.modifiers() & Qt.KeyboardModifier.AltModifier:
                dx, dy, self.guides = self._snap_to_guides(dx, dy)
            guide_axes = {axis for axis, _ in self.guides}

            for idx in self.selected_indices:
                if idx in self.drag_start_positions and 0 <= idx < len(self.elements):
                    start_x, start_y = self.drag_start_positions[idx]
                    new_x = start_x + dx
                    new_y = start_y + dy

                    # Apply snap to grid if enabled
                    if self.snap_to_grid:
                        if "v" not in guide_axes:
                            new_x = self.snap_to_grid_coord(new_x)
                        if "h" not in guide_axes:
                            new_y = self.snap_to_grid_coord(new_y)

                    new_x = int(new_x)
                    new_y = int(new_y)

                    # Allow elements to go outside canvas for cropping effects
                    # Set generous limits to prevent dragging infinitely far
                    new_x = max(-constants.DISPLAY_WIDTH * 2, min(new_x, constants.DISPLAY_WIDTH * 3))
                    new_y = max(-constants.DISPLAY_HEIGHT * 2, min(new_y, constants.DISPLAY_HEIGHT * 3))
                    self.elements[idx].x = new_x
                    self.elements[idx].y = new_y

            if len(self.selected_indices) == 1:
                el = self.elements[self.selected_indices[0]]
                self.element_moved.emit(self.selected_indices[0], el.x, el.y)
            self.update()
            return

        # Update cursor based on hover
        if len(self.selected_indices) > 1:
            # Multi-selection - check for multi-selection resize handles
            handle = self.get_multi_handle_at(pos)
            if handle in [self.HANDLE_TL, self.HANDLE_BR]:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handle in [self.HANDLE_TR, self.HANDLE_BL]:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif len(self.selected_indices) == 1:
            element = self.elements[self.selected_indices[0]]
            handle = self.get_handle_at(pos, element)
            if handle in [self.HANDLE_TL, self.HANDLE_BR]:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handle in [self.HANDLE_TR, self.HANDLE_BL]:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    @staticmethod
    def _display_extent(element, x, y):
        """(left, top, right, bottom) in display px for an element placed at x, y."""
        if element.type in ("circle_gauge", "analog_clock"):
            return x - element.radius, y - element.radius, x + element.radius, y + element.radius
        return x, y, x + element.width, y + element.height

    def _snap_to_guides(self, dx, dy):
        """Nudge the drag delta so selection edges/centers meet other elements or the display."""
        boxes = [
            self._display_extent(self.elements[i], *self.drag_start_positions[i])
            for i in self.selected_indices if i in self.drag_start_positions
        ]
        if not boxes:
            return dx, dy, []
        left = min(b[0] for b in boxes)
        top = min(b[1] for b in boxes)
        right = max(b[2] for b in boxes)
        bottom = max(b[3] for b in boxes)

        targets_x = [0, constants.DISPLAY_WIDTH / 2, constants.DISPLAY_WIDTH]
        targets_y = [0, constants.DISPLAY_HEIGHT / 2, constants.DISPLAY_HEIGHT]
        for i in self.visible_indices():
            if i in self.selected_indices:
                continue
            el = self.elements[i]
            l, t, r, b = self._display_extent(el, el.x, el.y)
            targets_x += [l, (l + r) / 2, r]
            targets_y += [t, (t + b) / 2, b]

        threshold = self.GUIDE_SNAP_PX / self.scale
        guides = []

        def best(edges, targets):
            options = [(abs(t - e), t - e, t) for e in edges for t in targets if abs(t - e) <= threshold]
            return min(options) if options else None

        snap_x = best([left + dx, (left + right) / 2 + dx, right + dx], targets_x)
        if snap_x:
            dx += snap_x[1]
            guides.append(("v", snap_x[2]))
        snap_y = best([top + dy, (top + bottom) / 2 + dy, bottom + dy], targets_y)
        if snap_y:
            dy += snap_y[1]
            guides.append(("h", snap_y[2]))
        return dx, dy, guides

    def draw_guides(self, painter):
        painter.setPen(QPen(QColor(255, 0, 170), 1))
        for axis, value in self.guides:
            p = value * self.scale
            if axis == "v":
                painter.drawLine(int(p), 0, int(p), self.canvas_height)
            else:
                painter.drawLine(0, int(p), self.canvas_width, int(p))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_anchor = None
            self.unsetCursor()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.guides:
                self.guides = []
                self.update()
            self.dragging = False
            self.resizing = False
            self.resize_handle = self.HANDLE_NONE

    def keyPressEvent(self, event):
        """Handle arrow key nudging for selected elements."""
        if not self.selected_indices:
            return

        # Check if any selected element is locked
        any_locked = any(self.elements[idx].locked for idx in self.selected_indices)
        if any_locked:
            return

        key = event.key()
        shift_held = event.modifiers() & Qt.KeyboardModifier.ShiftModifier

        # Determine nudge amount: 10px with Shift, 1px without
        nudge = 10 if shift_held else 1

        dx, dy = 0, 0
        if key == Qt.Key.Key_Left:
            dx = -nudge
        elif key == Qt.Key.Key_Right:
            dx = nudge
        elif key == Qt.Key.Key_Up:
            dy = -nudge
        elif key == Qt.Key.Key_Down:
            dy = nudge
        else:
            # Not an arrow key, pass to parent
            super().keyPressEvent(event)
            return

        # Emit drag_started for undo state
        self.drag_started.emit()

        # Move all selected elements. No grid snap: it would round a 1px nudge back.
        for idx in self.selected_indices:
            element = self.elements[idx]
            element.x = int(element.x + dx)
            element.y = int(element.y + dy)
            self.element_moved.emit(idx, element.x, element.y)

        self.update()
