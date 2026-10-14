param([string]$Python = "python", [string]$InnoCompiler = "", [switch]$SkipBuild, [switch]$SkipDependencies, [string]$OutputDirectory = "dist")
$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $workspace
try {
    if (-not $InnoCompiler) {
        foreach ($candidate in @("build\tools\inno\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
            if (Test-Path $candidate) { $InnoCompiler = (Resolve-Path $candidate).Path; break }
        }
    }
    if (-not $InnoCompiler -or -not (Test-Path $InnoCompiler)) { throw "Inno Setup compiler missing. Specify -InnoCompiler <ISCC.exe>." }
    & "$PSScriptRoot\verify_windows_deps.ps1"
    if (-not $SkipBuild) { & "$PSScriptRoot\build-local.ps1" -Python $Python -SkipDependencies:$SkipDependencies -OutputDirectory $OutputDirectory }
    $versionPython = $Python
    if (Test-Path "build\venv\Scripts\python.exe") { $versionPython = Join-Path $workspace "build\venv\Scripts\python.exe" }
    $version = (& $versionPython -c "from src.utils.app_version import get_version; print(get_version())").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw "Could not read application version" }
    $applicationDirectory = (Resolve-Path (Join-Path $OutputDirectory "ThermalEngine")).Path
    & $InnoCompiler "/DMyAppVersion=$version" "/DMyAppSource=$applicationDirectory" "/O$workspace\dist" "/FThermalEngine-$version-UI-Local-Setup" installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }
    $setup = Join-Path $workspace "dist\ThermalEngine-$version-UI-Local-Setup.exe"
    if (-not (Test-Path $setup)) { throw "Installer missing" }
    Get-FileHash -LiteralPath $setup -Algorithm SHA256
} finally { Pop-Location }
