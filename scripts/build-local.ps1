# Local build script for Thermal Engine
# Mirrors the GitHub Actions workflow for testing

Write-Host "=== Thermal Engine Local Build ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

Write-Host ""
Write-Host "[2/5] Downloading libusb..." -ForegroundColor Yellow
if (-not (Test-Path "libusb-1.0.dll")) {
    Invoke-WebRequest -Uri "https://github.com/libusb/libusb/releases/download/v1.0.27/libusb-1.0.27.7z" -OutFile "libusb.7z"
    7z x libusb.7z -olibusb -y
    Copy-Item "libusb\VS2019\MS64\dll\libusb-1.0.dll" -Destination "." -Force
    Remove-Item -Recurse -Force "libusb" -ErrorAction SilentlyContinue
    Remove-Item -Force "libusb.7z" -ErrorAction SilentlyContinue
    Write-Host "  libusb-1.0.dll downloaded" -ForegroundColor Green
} else {
    Write-Host "  libusb-1.0.dll already present" -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/5] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "ThermalEngine.spec") { Remove-Item -Force "ThermalEngine.spec" }

Write-Host ""
Write-Host "[4/5] Building with PyInstaller..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Gray

pyinstaller --name="ThermalEngine" `
    --onefile `
    --windowed `
    --icon="assets/icon.ico" `
    --add-data="elements;elements" `
    --add-data="assets;assets" `
    --add-data="libs;libs" `
    --add-binary="libusb-1.0.dll;." `
    --hidden-import=PySide6.QtCore `
    --hidden-import=PySide6.QtGui `
    --hidden-import=PySide6.QtWidgets `
    --hidden-import=src `
    --hidden-import=src.core `
    --hidden-import=src.core.constants `
    --hidden-import=src.core.element `
    --hidden-import=src.core.sensors `
    --hidden-import=src.core.libre_hw_monitor `
    --hidden-import=src.core.device_backends `
    --hidden-import=src.core.security `
    --hidden-import=src.ui `
    --hidden-import=src.ui.main_window `
    --hidden-import=src.ui.canvas `
    --hidden-import=src.ui.element_list `
    --hidden-import=src.ui.properties `
    --hidden-import=src.ui.presets `
    --hidden-import=src.ui.video_background `
    --hidden-import=src.utils `
    --hidden-import=src.utils.app_path `
    --hidden-import=src.utils.app_version `
    --hidden-import=src.utils.settings `
    --hidden-import=src.utils.updater `
    --hidden-import=src.utils.profiles `
    --hidden-import=src.utils.theme_package `
    --collect-submodules=src `
    --collect-submodules=src.core.device_backends `
    --hidden-import=usb `
    --hidden-import=usb.core `
    --hidden-import=usb.backend `
    --hidden-import=usb.backend.libusb1 `
    --collect-submodules=usb `
    --collect-binaries=usb `
    --collect-data=usb `
    --exclude-module=tkinter `
    --exclude-module=matplotlib `
    --exclude-module=pandas `
    --exclude-module=scipy `
    --exclude-module=PySide6.QtNetwork `
    --exclude-module=PySide6.QtQml `
    --exclude-module=PySide6.QtQuick `
    --exclude-module=PySide6.QtWebEngineWidgets `
    --exclude-module=PySide6.Qt3D `
    --exclude-module=PySide6.QtCharts `
    --exclude-module=PySide6.QtDataVisualization `
    main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[5/5] Build complete!" -ForegroundColor Green
Write-Host ""

# Get file size
$exePath = "dist\ThermalEngine.exe"
if (Test-Path $exePath) {
    $fileSize = (Get-Item $exePath).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)

    Write-Host "Output: $exePath" -ForegroundColor Cyan
    Write-Host "Size: $fileSizeMB MB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now test the executable:" -ForegroundColor Yellow
    Write-Host "  .\dist\ThermalEngine.exe" -ForegroundColor White
} else {
    Write-Host "ERROR: Executable not found at $exePath" -ForegroundColor Red
    exit 1
}
