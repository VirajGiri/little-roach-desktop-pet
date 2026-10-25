$ErrorActionPreference = "Stop"
$assetPath = Join-Path (Get-Location) "assets"
$previewPath = Join-Path (Get-Location) "artwork\roach_animation_preview.png"
$cell = 192
$views = 8

Add-Type -AssemblyName System.Drawing
$bitmap = [System.Drawing.Bitmap]::new($cell * $views, $cell * $views)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::FromArgb(48, 51, 57))
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
try {
    for ($row = 0; $row -lt $views; $row++) {
        $direction = $row * 4
        for ($pose = 0; $pose -lt $views; $pose++) {
            $path = Join-Path $assetPath "roach_walk_${pose}_dir_${direction}.png"
            $sprite = [System.Drawing.Image]::FromFile($path)
            try {
                $graphics.DrawImage($sprite, $pose * $cell, $row * $cell, $cell, $cell)
            } finally {
                $sprite.Dispose()
            }
        }
    }
    $bitmap.Save($previewPath, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
Write-Host "Preview: artwork\roach_animation_preview.png"
