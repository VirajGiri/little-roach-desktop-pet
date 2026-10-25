$ErrorActionPreference = "Stop"

if (Test-Path (Join-Path (Get-Location) ".build-tools\PyInstaller")) {
    $env:PYTHONPATH = Join-Path (Get-Location) ".build-tools"
}

python -m PyInstaller --noconfirm --clean --onedir --windowed --name LittleRoach main.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$archive = Join-Path (Get-Location) "dist\LittleRoach-portable.zip"
if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path "dist\LittleRoach" -DestinationPath $archive -CompressionLevel Optimal
Write-Host "App: dist\LittleRoach\LittleRoach.exe"
Write-Host "Share: dist\LittleRoach-portable.zip"

