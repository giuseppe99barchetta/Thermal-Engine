"""Explicit, isolated verification of the installed Qt Quick runtime."""
import json
import sys
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, QMetaObject, qVersion
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid
from src.ui.quick_window import QuickEditorWindow
from src.utils import settings


def run_smoke(destination, size=(1440, 900)):
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    settings._settings = {**settings.DEFAULT_SETTINGS, "onboarding_completed": True}
    window = QuickEditorWindow(start_services=False)
    window.root.setWidth(size[0])
    window.root.setHeight(size[1])
    window.show()
    controller = window.controller
    results = {"frozen": bool(getattr(sys, "frozen", False)), "python": sys.version, "qt": qVersion(), "size": list(size), "dpr": window.root.devicePixelRatio(), "screens": []}
    screens = [("editor", None), ("element", None), ("presets", None), ("sensors", None), ("display", None), ("settings", controller.settingsData()), ("profiles", controller.settingsData()),
               ("network", {}), ("resolution", {}), ("devices", {}), ("onboarding", {}),
               ("condition", {"rule": {}}), ("gradient", {"stops": [[0, "#57d4ef"], [1, "#ffffff"]]}),
               ("diagnostics", {"text": controller.diagnostics()}), ("console", {}), ("hardware", {}),
               ("update", {"version": "0.13.4", "notes": "Local runtime verification"}), ("shortcuts", None),
               ("unsaved", {"token": "verification", "name": "Unsaved theme"}), ("network-form", {}),
               ("onboarding-resolution", {}), ("onboarding-themes", {}), ("add-menu", None)]

    def advance():
        try:
            name, data = screens.pop(0)
            window.root.setProperty("leftTab", 1 if name == "presets" else 2 if name == "sensors" else 0)
            window.root.setProperty("inspectorTab", 1 if name == "display" else 0)
            window.root.setProperty("layersOpen", name == "add-menu")
            controller.select_indices([0] if name == "element" else [])
            for item in window.root.findChildren(QObject):
                if isValid(item) and item.inherits("QQuickPopup") and item.property("visible"):
                    QMetaObject.invokeMethod(item, "close")
            kind = "network" if name == "network-form" else "onboarding" if name.startswith("onboarding-") else name
            if data is not None: controller.requestDialog.emit(kind, data)
            if name in ("network-form", "onboarding-resolution", "onboarding-themes"):
                title = "Network sensors" if name == "network-form" else "Welcome to Display Studio"
                dialog = next(item for item in window.root.findChildren(QObject) if item.inherits("QQuickDialog") and item.property("title") == title)
                if name == "network-form": QMetaObject.invokeMethod(dialog, "add")
                else: dialog.setProperty("step", 1 if name == "onboarding-resolution" else 2)
            if name == "shortcuts": QMetaObject.invokeMethod(window.root.findChild(QObject, "shortcutsDialog"), "open")
            if name == "add-menu": QMetaObject.invokeMethod(window.root.findChild(QObject, "addMenu"), "open")
            QTimer.singleShot(100, lambda: capture(name))
        except Exception as exc:
            results["error"] = str(exc)
            finish()

    def capture(name):
        image = window.root.grabWindow()
        if image.isNull() or not image.save(str(target / (name + ".png"))):
            results["error"] = "Could not capture " + name
            finish()
            return
        results["screens"].append(name)
        if screens: advance()
        else:
            count = len(controller.elements)
            controller.command("add", "text")
            controller.beginEdit()
            controller.edit("x", 200)
            controller.edit("x", 240)
            controller.endEdit()
            controller.command("undo", None)
            controller.command("redo", None)
            results["history"] = len(controller.elements) == count + 1 and controller.elements[0].x == 240
            finish()

    def finish():
        results["qml_errors"] = window.qml_errors
        results["passed"] = not results.get("error") and not window.qml_errors and results.get("history", False)
        (target / "report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        window.dispose()
        app.exit(0 if results["passed"] else 1)

    QTimer.singleShot(250, advance)
    return app.exec()
