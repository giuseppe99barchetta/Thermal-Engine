# Qt Quick local Windows build

The application entry point uses `QuickEditorWindow` and the QML screens in
`src/ui/qml`. The Python document, renderer, sensor services and display backends
keep the existing theme format and user data locations.

The editor includes layers, groups, pages, presets, contextual properties,
media, conditions, gradients, alignment, zoom, pan, rulers, guides and grid
snapping. Compact windows expose layers and properties as alternate panels.
Project, device, sensor, settings, profile, diagnostics and update actions are
available in the project menu. File and color selection use asynchronous Qt
platform dialogs.

Rotation, mirroring, brightness and frame rate are also directly available in
the inspector's Display tab and through the header's Display button. Sensors
are separated into Summary, Hardware and External, with category, search and
availability filters. Property sections are collapsible and depend on the
selected element. Preset previews include saved GIF/video backgrounds; page
thumbnails refresh after asynchronous background loading completes.

## Checks

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_QUICK_BACKEND = 'software'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest -q -p no:cacheprovider
python -m ruff check --isolated --select F --exclude build,dist,third_party .
python scripts/check_qml.py
python main.py --ui-smoke-test build/smoke-source
```

`--ui-smoke-test` opens the editor and secondary screens, checks undo/redo,
captures PNGs and writes `report.json` to its argument directory. It does not
start hardware, network, update or automatic-profile workers or persist changes.
The same command is supported by the packaged executable.

```powershell
python scripts/check_ui_visual.py --native --output build/visual-checks
```

The visual check captures 23 views at physical 1280x720 and 1920x1080, with
100%, 150% and 200% scale. Omit `--native` for offscreen CI. The hidden
`--ui-smoke-size WIDTHxHEIGHT` switch selects logical dimensions for a single
capture run. PNGs are evidence for visual review; runtime checks do not replace
inspection of clipping, alignment and contrast.

Tests isolate settings writes under their temporary directory. Linux platform
probes restore imported settings modules, so later tests cannot use another
module's data path.

## Build

```powershell
.\scripts\build-installer-local.ps1 -Python 'C:\path\to\python.exe' -InnoCompiler 'C:\path\to\ISCC.exe'
```

The build creates `build/venv`, uses the tracked `ThermalEngine.spec` in `onedir`
mode and verifies the existing LibreHardwareMonitor/PawnIO dependencies.
7-Zip is required to prepare libusb. Python 3.14 requires PyInstaller 6.15 or
later. The local delivery was built with Python 3.14.4, PySide6 6.12.0,
PyInstaller 6.22.3 and Inno Setup 6.7.3.

`requirements-build-windows.txt` pins the complete verified Windows build
environment. Use Python 3.14 for this lock; `requirements.txt` retains the broader
source compatibility requirements. CI checks Windows/Linux on Python 3.11 and
3.14, and separately verifies the packaged Windows executable outside Python.
The source screenshot in the README shows simulated readings, not hardware data.

To use the existing build environment and avoid files locked by a running build:

```powershell
.\scripts\build-local.ps1 -Python "$pwd\build\venv\Scripts\python.exe" -SkipDependencies -OutputDirectory build/local-package
.\scripts\build-installer-local.ps1 -SkipBuild -OutputDirectory build/local-package
```

Output: `dist/ThermalEngine-0.13.4-UI-Local-Setup.exe`. The build does not bump
the version, tag, publish, or install the application. The installer preserves
the existing AppId and data directory. Close running copies before installing.

Physical USB/HID operation, actual suspend/resume events and installation on the
target machine must be verified separately. Local Ubuntu/WSL checks complement
the Windows/Linux CI configuration; remote CI requires a subsequent push.
