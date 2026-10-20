param(
  [string]$Source = "C:\Users\yang\.dsh\attachments\v1\objects\8f\8f43110794d2d0433b462feaf41f24ab90108b7040d7f78e05869c93d910e48a",
  [string]$OutDir = "D:\Python for Data Analysis\selflove-work\photo-8f431107"
)
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$img = [System.Drawing.Image]::FromFile($Source)
"source size: $($img.Width) x $($img.Height)"
try {
  $ori = $img.GetPropertyItem(0x0112)
  "exif orientation: " + [System.BitConverter]::ToUInt16($ori.Value, 0)
} catch { "exif orientation: <none>" }

$w = $img.Width; $h = $img.Height
$bmp = [System.Drawing.Bitmap]::new($w, $h, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.DrawImage($img, 0, 0, $w, $h)
$g.Dispose()

$bmpPath = Join-Path $OutDir "source-24bpp.bmp"
$bmp.Save($bmpPath, [System.Drawing.Imaging.ImageFormat]::Bmp)
"bmp saved: $bmpPath"

$grid = [System.Drawing.Bitmap]::new($w, $h, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$gg = [System.Drawing.Graphics]::FromImage($grid)
$gg.DrawImage($bmp, 0, 0, $w, $h)
$pen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(200, 255, 0, 0), 2)
$font = [System.Drawing.Font]::new("Consolas", 22, [System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(230, 255, 255, 0))
$shadow = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(200, 0, 0, 0))
for ($i = 0; $i -le 10; $i++) {
  $x = [int]($i * $w / 10); $y = [int]($i * $h / 10)
  if ($i -gt 0 -and $i -lt 10) {
    $gg.DrawLine($pen, $x, 0, $x, $h)
    $gg.DrawLine($pen, 0, $y, $w, $y)
  }
  if ($i -lt 10) {
    $label = "{0:N1}" -f ($i / 10.0)
    $gg.DrawString($label, $font, $shadow, ($x + 4), 6)
    $gg.DrawString($label, $font, $brush, ($x + 3), 5)
    $gg.DrawString($label, $font, $shadow, 6, ($y + 4))
    $gg.DrawString($label, $font, $brush, 5, ($y + 3))
  }
}
$gg.Dispose()
$gridPath = Join-Path $OutDir "source-grid.png"
$grid.Save($gridPath, [System.Drawing.Imaging.ImageFormat]::Png)
"grid saved: $gridPath"

$bmp.Dispose(); $grid.Dispose(); $img.Dispose()
"done"
