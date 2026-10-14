#!/usr/bin/env bash

set -euo pipefail

APP_NAME="ThermalEngine"
DIST_DIR="dist"
BUILD_DIR="build"
SPEC_FILE="${APP_NAME}.spec"
OUTPUT_DIR="${DIST_DIR}/${APP_NAME}"
APPDIR="${DIST_DIR}/AppDir"
APPIMAGE_NAME="${APP_NAME}-x86_64.AppImage"
APPIMAGE_TOOL="${PWD}/appimagetool-x86_64.AppImage"

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
    'paho-mqtt>=2.1.0,<3' \
    'keyring>=25,<26' \
    hidapi \
    pyusb \
    opencv-python \
    numpy \
    packaging \
    pyinstaller

echo
echo "[2/4] Cleaning previous build..."
rm -rf "${OUTPUT_DIR}" "${BUILD_DIR}/pyinstaller" "${APPDIR}" "${APPIMAGE_NAME}"

echo
echo "[3/4] Building with PyInstaller..."
python3 -m PyInstaller --clean --noconfirm --workpath "${BUILD_DIR}/pyinstaller" "${SPEC_FILE}"

echo
echo "[4/4] Packing AppImage..."
if [[ ! -d "${OUTPUT_DIR}" ]]; then
    echo "ERROR: Build output not found at ${OUTPUT_DIR}"
    exit 1
fi

mkdir -p "${APPDIR}/usr/bin"
cp -r "${OUTPUT_DIR}" "${APPDIR}/usr/bin/${APP_NAME}"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "${HERE}/usr/bin/ThermalEngine/ThermalEngine" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

cat > "${APPDIR}/ThermalEngine.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ThermalEngine
Comment=Thermal Engine
Exec=ThermalEngine
Icon=thermalengine
Categories=Utility;
Terminal=false
EOF

cp "assets/icon.png" "${APPDIR}/thermalengine.png"

if [[ ! -f "${APPIMAGE_TOOL}" ]]; then
    curl -L "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -o "${APPIMAGE_TOOL}"
    chmod +x "${APPIMAGE_TOOL}"
fi

ARCH=x86_64 "${APPIMAGE_TOOL}" --appimage-extract-and-run "${APPDIR}" "${APPIMAGE_NAME}"
echo "Output: ${APPIMAGE_NAME}"
