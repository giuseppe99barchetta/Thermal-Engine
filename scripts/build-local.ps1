param([string]$Python = "python", [switch]$SkipDependencies, [string]$OutputDirectory = "dist")
$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $workspace
try {
    if (-not $SkipDependencies) {
        if (-not (Test-Path "build\venv\Scripts\python.exe")) {
            & $Python -m venv build/venv
            if ($LASTEXITCODE -ne 0) { throw "Could not create build environment" }
        }
        $Python = Join-Path $workspace "build\venv\Scripts\python.exe"
        & $Python -m pip install -r requirements-build-windows.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    }
    if (-not (Test-Path "libusb-1.0.dll") -and -not (Test-Path "build\deps\libusb-1.0.dll")) {
        New-Item -ItemType Directory -Path "build\deps" -Force | Out-Null
        Invoke-WebRequest "https://github.com/libusb/libusb/releases/download/v1.0.27/libusb-1.0.27.7z" -OutFile "build\deps\libusb.7z"
        & 7z x "build\deps\libusb.7z" "-obuild\deps\libusb" -y
        if ($LASTEXITCODE -ne 0) { throw "libusb extraction failed (7-Zip required)" }
        Copy-Item -LiteralPath "build\deps\libusb\VS2019\MS64\dll\libusb-1.0.dll" -Destination "build\deps\libusb-1.0.dll" -Force
    }
    if (-not (Test-Path "build\deps\PresentMon.exe")) {
        New-Item -ItemType Directory -Path "build\deps" -Force | Out-Null
        Invoke-WebRequest "https://github.com/GameTechDev/PresentMon/releases/download/v2.6.0/PresentMon-2.6.0-x64.exe" -OutFile "build\deps\PresentMon.exe"
        if ((Get-FileHash "build\deps\PresentMon.exe" -Algorithm SHA256).Hash -ne "B2A706BC6AD475749E3B7E3409263AA1E6906D45BDCF993F6DBC0F660188F1AF") {
            Remove-Item "build\deps\PresentMon.exe"; throw "PresentMon checksum mismatch"
        }
    }
    $ErrorActionPreference = "Continue"
    & $Python -m PyInstaller --noconfirm --clean --workpath build/pyinstaller --distpath $OutputDirectory ThermalEngine.spec
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    $executable = Join-Path $OutputDirectory "ThermalEngine\ThermalEngine.exe"
    if (-not (Test-Path $executable)) { throw "Application executable missing" }
    Write-Host "Application: $((Resolve-Path $executable).Path)"
} finally { Pop-Location }
