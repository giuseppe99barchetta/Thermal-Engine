#!/usr/bin/env bash

set -euo pipefail

APP_NAME="ThermalEngine"
DIST_DIR="dist"
BUILD_DIR="build"
SPEC_FILE="${APP_NAME}.spec"
OUTPUT_DIR="${DIST_DIR}/${APP_NAME}"
ARCHIVE_NAME="${APP_NAME}-linux-x64.tar.gz"

echo "=== Thermal Engine Linux Build ==="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install Python 3.10+."
    exit 1
fi

echo "[1/4] Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install \
    PySide6 \
    Pillow \
    psutil \
    hidapi \
    pyusb \
    opencv-python \
    numpy \
    packaging \
    pyinstaller

echo
echo "[2/4] Cleaning previous build..."
rm -rf "${DIST_DIR}" "${BUILD_DIR}" "${SPEC_FILE}"

echo
echo "[3/4] Building with PyInstaller..."
pyinstaller \
    --name="${APP_NAME}" \
    --onedir \
    --windowed \
    --icon="assets/icon.png" \
    --add-data="elements:elements" \
    --add-data="assets:assets" \
    --add-data="presets:presets" \
    --add-data="libs:libs" \
    --hidden-import=PySide6.QtCore \
    --hidden-import=PySide6.QtGui \
    --hidden-import=PySide6.QtWidgets \
    --hidden-import=src \
    --hidden-import=src.core \
    --hidden-import=src.core.constants \
    --hidden-import=src.core.element \
    --hidden-import=src.core.sensors \
    --hidden-import=src.core.libre_hw_monitor \
    --hidden-import=src.core.device_backends \
    --hidden-import=src.core.security \
    --hidden-import=src.ui \
    --hidden-import=src.ui.main_window \
    --hidden-import=src.ui.canvas \
    --hidden-import=src.ui.element_list \
    --hidden-import=src.ui.properties \
    --hidden-import=src.ui.presets \
    --hidden-import=src.ui.video_background \
    --hidden-import=src.utils \
    --hidden-import=src.utils.app_path \
    --hidden-import=src.utils.app_version \
    --hidden-import=src.utils.settings \
    --hidden-import=src.utils.updater \
    --hidden-import=src.utils.profiles \
    --hidden-import=src.utils.theme_package \
    --collect-submodules=src \
    --collect-submodules=src.core.device_backends \
    --hidden-import=usb \
    --hidden-import=usb.core \
    --hidden-import=usb.backend \
    --hidden-import=usb.backend.libusb1 \
    --collect-submodules=usb \
    --collect-binaries=usb \
    --collect-data=usb \
    --exclude-module=tkinter \
    --exclude-module=matplotlib \
    --exclude-module=pandas \
    --exclude-module=scipy \
    --exclude-module=PySide6.QtNetwork \
    --exclude-module=PySide6.QtQml \
    --exclude-module=PySide6.QtQuick \
    --exclude-module=PySide6.QtWebEngineWidgets \
    --exclude-module=PySide6.Qt3D \
    --exclude-module=PySide6.QtCharts \
    --exclude-module=PySide6.QtDataVisualization \
    main.py

echo
echo "[4/4] Packing Linux artifact..."
if [[ ! -d "${OUTPUT_DIR}" ]]; then
    echo "ERROR: Build output not found at ${OUTPUT_DIR}"
    exit 1
fi

tar -C "${DIST_DIR}" -czf "${ARCHIVE_NAME}" "${APP_NAME}"
echo "Output: ${ARCHIVE_NAME}"
