# Builds tools\dist\GE100Pro_Editor.exe: the editor as one program (Windows, Python 3.9+, no other packages needed
# at run time). Run from anywhere:  powershell -ExecutionPolicy Bypass -File <repo>\tools\build_editor_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m pip install --upgrade pyinstaller
# the web files without your own settings.js (that one stays next to the .exe)
$bundle = Join-Path $PSScriptRoot "build\web"
Remove-Item -Recurse -Force $bundle -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $bundle | Out-Null
Get-ChildItem ..\web -File | Where-Object { $_.Name -ne "settings.js" } | Copy-Item -Destination $bundle
python -m PyInstaller --noconfirm --clean --onefile --windowed --name GE100Pro_Editor `
    --paths ..\src --add-data "$bundle;web" editor_app.py
Remove-Item -Recurse -Force build, GE100Pro_Editor.spec -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "Done: $PSScriptRoot\dist\GE100Pro_Editor.exe"
