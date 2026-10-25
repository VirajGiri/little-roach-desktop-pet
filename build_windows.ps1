$ErrorActionPreference = "Stop"

if (Test-Path (Join-Path (Get-Location) ".build-tools\PyInstaller")) {
    $env:PYTHONPATH = Join-Path (Get-Location) ".build-tools"
}

python -m PyInstaller --noconfirm --clean --onedir --windowed --name LittleRoach --add-data "assets;assets" main.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$archive = Join-Path (Get-Location) "dist\LittleRoach-portable.zip"
$tempArchive = Join-Path (Get-Location) "dist\LittleRoach-portable.tmp.zip"
if (Test-Path $tempArchive) { Remove-Item -LiteralPath $tempArchive -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    (Join-Path (Get-Location) "dist\LittleRoach"),
    $tempArchive,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $true
)
if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
Move-Item -LiteralPath $tempArchive -Destination $archive
Write-Host "App: dist\LittleRoach\LittleRoach.exe"
Write-Host "Share: dist\LittleRoach-portable.zip"
