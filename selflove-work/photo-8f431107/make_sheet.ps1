param(
  [string]$Bmp = "D:\Python for Data Analysis\selflove-work\photo-8f431107\source-24bpp.bmp",
  [string]$Out = "D:\Python for Data Analysis\selflove-work\photo-8f431107\sheet-regions.png",
  [int]$Cell = 520,
  [int]$Cols = 3,
  [string[]]$Spec = @()
)
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Bitmap]::FromFile($Bmp)
$w = $src.Width; $h = $src.Height
$rows = [math]::Ceiling($Spec.Count / $Cols)
$cellH = [int]($Cell * 0.62)
$sheet = [System.Drawing.Bitmap]::new($Cols * $Cell, $rows * ($cellH + 34), [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g = [System.Drawing.Graphics]::FromImage($sheet)
$g.Clear([System.Drawing.Color]::FromArgb(20, 20, 20))
$font = [System.Drawing.Font]::new("Consolas", 15, [System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
$i = 0
foreach ($item in $Spec) {
  $parts = $item -split '='
  $name = $parts[0]
  $nums = $parts[1] -split ','
  $l = [double]$nums[0]; $t = [double]$nums[1]; $r = [double]$nums[2]; $b = [double]$nums[3]
  $sx = [int]($l * $w); $sy = [int]($t * $h)
  $sw = [int](($r - $l) * $w); $sh = [int](($b - $t) * $h)
  $col = $i % $Cols; $row = [math]::Floor($i / $Cols)
  $rect = [System.Drawing.Rectangle]::new($sx, $sy, $sw, $sh)
  $crop = $src.Clone($rect, $src.PixelFormat)
  $dx = $col * $Cell; $dy = $row * ($cellH + 34)
  $g.DrawImage($crop, $dx, $dy + 34, $Cell, $cellH)
  $g.DrawString($name, $font, $brush, $dx + 4, $dy + 6)
  $crop.Dispose()
  $i++
}
$g.Dispose()
$sheet.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$sheet.Dispose(); $src.Dispose()
"saved $Out  ($($Spec.Count) crops)"
