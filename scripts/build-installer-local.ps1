# Local installer build script for Thermal Engine
# Builds the app with PyInstaller, then creates an installer with Inno Setup

Write-Host "=== Thermal Engine Installer Build ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Please install Python 3.10+" -ForegroundColor Red
    exit 1
}

# Check if Inno Setup is installed
$innoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $innoSetupPath)) {
    Write-Host "ERROR: Inno Setup not found at: $innoSetupPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please download and install Inno Setup from:" -ForegroundColor Yellow
    Write-Host "https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Install with default options, then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

Write-Host ""
Write-Host "[2/4] Cleaning previous build..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "ThermalEngine.spec") { Remove-Item -Force "ThermalEngine.spec" }
if (Test-Path "*.exe") { Remove-Item -Force "*.exe" }

Write-Host ""
Write-Host "[3/4] Building with PyInstaller (onedir mode)..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Gray

pyinstaller --name="ThermalEngine" `
    --onedir `
    --windowed `
    --icon="assets/icon.ico" `
    --add-data="elements;elements" `
    --add-data="assets;assets" `
    --add-data="presets;presets" `
    --add-data="libs;libs" `
    --hidden-import=PySide6.QtCore `
    --hidden-import=PySide6.QtGui `
    --hidden-import=PySide6.QtWidgets `
    --hidden-import=device_backends `
    --hidden-import=video_background `
    --collect-submodules=device_backends `
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
    Write-Host "ERROR: PyInstaller build failed!" -ForegroundColor Red
    exit 1
}

# Get dist folder size
$distPath = "dist\ThermalEngine"
if (Test-Path $distPath) {
    $distSize = (Get-ChildItem -Recurse $distPath | Measure-Object -Property Length -Sum).Sum
    $distSizeMB = [math]::Round($distSize / 1MB, 2)
    Write-Host "  Build folder size: $distSizeMB MB" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/4] Creating installer with Inno Setup..." -ForegroundColor Yellow

# Use version 1.0.0 for local builds (can be customized)
$version = "1.0.0"
Write-Host "  Building installer version: $version" -ForegroundColor Gray

# Run Inno Setup compiler
& $innoSetupPath /DMyAppVersion=$version installer.iss

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Inno Setup compilation failed!" -ForegroundColor Red
    exit 1
}

# Find the generated installer
$installerName = "ThermalEngine-$version-Setup.exe"
if (Test-Path $installerName) {
    $installerSize = (Get-Item $installerName).Length
    $installerSizeMB = [math]::Round($installerSize / 1MB, 2)

    Write-Host ""
    Write-Host "=== Build Complete! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installer: $installerName" -ForegroundColor Cyan
    Write-Host "Size: $installerSizeMB MB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now run the installer to test:" -ForegroundColor Yellow
    Write-Host "  .\$installerName" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "ERROR: Installer not found at $installerName" -ForegroundColor Red
    Write-Host "Check the Inno Setup output above for errors." -ForegroundColor Yellow
    exit 1
}
