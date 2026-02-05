# Clean up local build artifacts
# Usage: .\clean-local.ps1

Write-Host "Cleaning local build artifacts..." -ForegroundColor Yellow

# Build output folders
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue

# Build output zips and installers
Remove-Item -Force ThermalEngine-*.zip, ThermalEngine-*-Setup.exe -ErrorAction SilentlyContinue

Write-Host "Done." -ForegroundColor Green
