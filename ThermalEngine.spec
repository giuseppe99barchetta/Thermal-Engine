# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("elements", "elements"),
    ("assets", "assets"),
    ("presets", "presets"),
    ("libs", "libs"),
    ("THIRD-PARTY-NOTICES.md", "."),
]
binaries = []
hiddenimports = ["clr"] + collect_submodules("src") + collect_submodules("usb")

for package in ("pythonnet", "clr_loader"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

if os.path.exists("libusb-1.0.dll"):
    binaries.append(("libusb-1.0.dll", "."))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "tkinter", "matplotlib", "pandas", "scipy", "PySide6.QtNetwork",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineWidgets",
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
    icon="assets/icon.ico",
    manifest="ThermalEngine.manifest",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="ThermalEngine",
)
