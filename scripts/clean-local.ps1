$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path (Join-Path $workspace "main.py"))) { throw "Project root not found" }
foreach ($relative in @("dist", "build\pyinstaller", "build\local-package")) {
    $target = [IO.Path]::GetFullPath((Join-Path $workspace $relative))
    if (-not $target.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe artifact path" }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
Get-ChildItem -LiteralPath $workspace -File | Where-Object { $_.Name -like 'ThermalEngine-*.zip' -or $_.Name -like 'ThermalEngine-*-Setup.exe' } | Remove-Item -Force
Write-Host "Generated artifacts removed. Build tools, virtual environment and tracked spec preserved."
