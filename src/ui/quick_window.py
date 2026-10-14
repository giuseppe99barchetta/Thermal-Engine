"""Qt Quick application window and platform lifecycle integration."""
import sys
from PySide6.QtCore import QObject, QUrl, QTimer, QAbstractNativeEventFilter, Qt
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication
from src.ui.quick_canvas import QuickCanvas
from src.ui.quick_controller import EditorController, ThumbnailProvider
from src.utils.app_path import get_bundled_resource_path
from src.utils import settings

_registered = False


class PowerEvents(QAbstractNativeEventFilter):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32" and event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x218:
                if msg.wParam == 4: self.controller.sleep()
                elif msg.wParam in (7, 18): self.controller.wake()
        return False, 0


class QuickEditorWindow(QObject):
    def __init__(self, start_services=True):
        super().__init__()
        global _registered
        if not _registered:
            QQuickStyle.setStyle("Basic")
        if not _registered:
            qmlRegisterType(QuickCanvas, "ThermalEngine", 1, 0, "QuickCanvas")
            _registered = True
        self.engine = QQmlApplicationEngine(self)
        self.controller = EditorController(start_services=start_services, parent=self)
        self.controller.window = self
        self.qml_errors = []
        self.engine.warnings.connect(lambda warnings: self.qml_errors.extend(str(w) for w in warnings))
        self.engine.rootContext().setContextProperty("editor", self.controller)
        self.engine.addImageProvider("thumbs", ThumbnailProvider(self.controller))
        self.engine.load(QUrl.fromLocalFile(get_bundled_resource_path("src/ui/qml/Main.qml")))
        if not self.engine.rootObjects():
            self.controller.cleanup()
            raise RuntimeError("Could not load Qt Quick interface: " + "\n".join(self.qml_errors))
        self.root = self.engine.rootObjects()[0]
        self.root.closeRequested.connect(self._close_requested)
        self.root.windowStateChanged.connect(self._window_state_changed)
        self.power_events = PowerEvents(self.controller)
        QApplication.instance().installNativeEventFilter(self.power_events)
        QApplication.instance().aboutToQuit.connect(self.dispose)
        QTimer.singleShot(0, self.controller.startup)

    def show(self): self.root.show()
    def hide(self): self.root.hide()
    def showNormal(self): self.root.showNormal()
    def activateWindow(self): self.root.requestActivate()
    def isVisible(self): return self.root.isVisible()
    def isMinimized(self): return self.root.windowState() == Qt.WindowState.WindowMinimized
    def cleanup(self): self.controller.cleanup()

    def dispose(self):
        from shiboken6 import delete, isValid
        self.cleanup()
        QApplication.instance().removeNativeEventFilter(self.power_events)
        if isValid(self.engine): delete(self.engine)

    def _close_requested(self):
        if settings.get_setting("close_to_tray", True): self.hide()
        else: self.request_quit()

    def request_quit(self):
        if self.controller.dirty:
            self.showNormal()
            self.activateWindow()
        self.controller.requestQuit()

    def _window_state_changed(self, state):
        if state == Qt.WindowState.WindowMinimized and settings.get_setting("minimize_to_tray", True):
            self.hide()

    def force_quit(self):
        self.cleanup()
        self.root.setProperty("exiting", True)
        self.root.close()
        QApplication.instance().quit()
