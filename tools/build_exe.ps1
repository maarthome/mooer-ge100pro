# Builds tools\dist\NAM_to_GNR.exe from tools\nam_to_gnr.py with PyInstaller (Windows, Python 3.9+).
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File <repo>\tools\build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name NAM_to_GNR nam_to_gnr.py
Remove-Item -Recurse -Force build, NAM_to_GNR.spec -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "Done: $PSScriptRoot\dist\NAM_to_GNR.exe"
