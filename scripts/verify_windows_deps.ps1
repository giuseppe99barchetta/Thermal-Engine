$ErrorActionPreference = "Stop"

$lhm = Resolve-Path "libs\LibreHardwareMonitorLib.dll"
$lhmSha256 = "6ebc194316536ba61af5be24508ad9fcbb2ecc685e716c12e787c79530f66bf0"
if ((Get-FileHash -Algorithm SHA256 $lhm).Hash.ToLowerInvariant() -ne $lhmSha256) {
    throw "LibreHardwareMonitorLib.dll is not the pinned v0.9.6 net472 binary."
}
$assembly = [Reflection.Assembly]::ReflectionOnlyLoadFrom($lhm)
$references = @($assembly.GetReferencedAssemblies() | ForEach-Object { $_.FullName })
if (-not ($references -match "^mscorlib, Version=4\.0\.0\.0")) {
    throw "LibreHardwareMonitorLib.dll is not the .NET Framework build."
}
if ($references -match "^System\.Runtime, Version=10\.0\.0\.0") {
    throw "LibreHardwareMonitorLib.dll incorrectly targets .NET 10."
}

$pawnIoUrl = "https://github.com/namazso/PawnIO.Setup/releases/download/2.2.0/PawnIO_setup.exe"
$pawnIoSha256 = "1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032"
$pawnIoPath = "third_party\PawnIO_setup.exe"
New-Item -ItemType Directory -Path "third_party" -Force | Out-Null
if (-not (Test-Path $pawnIoPath)) {
    Invoke-WebRequest -Uri $pawnIoUrl -OutFile $pawnIoPath
}
if ((Get-FileHash -Algorithm SHA256 $pawnIoPath).Hash.ToLowerInvariant() -ne $pawnIoSha256) {
    throw "PawnIO_setup.exe checksum mismatch."
}

Write-Host "Windows dependencies verified: LHM net472, PawnIO 2.2.0."
