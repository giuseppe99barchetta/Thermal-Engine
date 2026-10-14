# -*- mode: python ; coding: utf-8 -*-
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [
    ("elements", "elements"),
    ("assets", "assets"),
    ("presets", "presets"),
    ("libs", "libs"),
    ("src/ui/qml", "src/ui/qml"),
    ("THIRD-PARTY-NOTICES.md", "."),
]
binaries = []
hiddenimports = collect_submodules("src") + collect_submodules("usb") + collect_submodules("paho.mqtt")
hiddenimports += collect_submodules("keyring.backends")
hiddenimports += ["PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2", "PySide6.QtNetwork"]
datas += copy_metadata("keyring", recursive=True)

if sys.platform == "win32": hiddenimports.append("clr")
for package in (("pythonnet", "clr_loader") if sys.platform == "win32" else ()):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

if sys.platform == "win32" and os.path.exists("libusb-1.0.dll"):
    binaries.append(("libusb-1.0.dll", "."))
elif sys.platform == "win32" and os.path.exists("build/deps/libusb-1.0.dll"):
    binaries.append(("build/deps/libusb-1.0.dll", "."))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "matplotlib", "pandas", "scipy", "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3D", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ThermalEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/icon.ico" if sys.platform == "win32" else "assets/icon.png",
    manifest="ThermalEngine.manifest" if sys.platform == "win32" else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="ThermalEngine",
)
