param(
  [string]$TilesJson = "D:\Python for Data Analysis\selflove-work\photo-8f431107\tiles.json",
  [string]$OutPrefix = "D:\Python for Data Analysis\selflove-work\photo-8f431107\review",
  [int]$Cell = 260,
  [int]$Cols = 4,
  [int]$PerSheet = 12
)
Add-Type -AssemblyName PresentationCore, PresentationFramework, WindowsBase
$items = Get-Content -Raw -Encoding UTF8 $TilesJson | ConvertFrom-Json
$cache = @{}
function Get-Frame([string]$path) {
  if (-not $cache.ContainsKey($path)) {
    $uri = [System.Uri]::new($path)
    $dec = [System.Windows.Media.Imaging.BitmapDecoder]::Create($uri, 'None', 'OnLoad')
    $cache[$path] = $dec.Frames[0]
  }
  return $cache[$path]
}
$labelH = 30
$cellsPerSheet = $Cols * ([math]::Ceiling($PerSheet / $Cols))
$sheetIndex = 0
for ($start = 0; $start -lt $items.Count; $start += $PerSheet) {
  $sheetIndex++
  $chunk = $items[$start..([math]::Min($start + $PerSheet - 1, $items.Count - 1))]
  $rows = [math]::Ceiling($chunk.Count / $Cols)
  $w = $Cols * $Cell
  $h = [int]($rows * ($Cell + $labelH))
  $dv = [System.Windows.Media.DrawingVisual]::new()
  $dc = $dv.RenderOpen()
  $dc.DrawRectangle([System.Windows.Media.Brushes]::Black, $null,
                    [System.Windows.Rect]::new(0, 0, $w, $h))
  $typeface = [System.Windows.Media.Typeface]::new("Consolas")
  $i = 0
  foreach ($item in $chunk) {
    $col = $i % $Cols
    $row = [math]::Floor($i / $Cols)
    $dx = $col * $Cell
    $dy = [int]($row * ($Cell + $labelH))
    try {
      $frame = Get-Frame $item.atlas
      $tx = $item.tile[0]; $ty = $item.tile[1]; $tw = $item.tile[2]; $th = $item.tile[3]
      $rect = [System.Windows.Int32Rect]::new($tx, $ty, $tw, $th)
      $crop = [System.Windows.Media.Imaging.CroppedBitmap]::new($frame, $rect)
      $dc.DrawImage($crop, [System.Windows.Rect]::new($dx, $dy, $Cell, $Cell))
      $scale = $Cell / [double]$tw
      $sx = $item.sample_in_tile[0]; $sy = $item.sample_in_tile[1]
      $cx = $dx + ($sx + 0.5) * $scale; $cy = $dy + ($sy + 0.5) * $scale
      $pen = [System.Windows.Media.Pen]::new([System.Windows.Media.Brushes]::Red, 2)
      $dc.DrawEllipse($null, $pen, [System.Windows.Point]::new($cx, $cy), 7, 7)
      $pen2 = [System.Windows.Media.Pen]::new([System.Windows.Media.Brushes]::White, 1)
      $dc.DrawEllipse($null, $pen2, [System.Windows.Point]::new($cx, $cy), 10, 10)
    } catch {
      $dc.DrawRectangle([System.Windows.Media.Brushes]::DarkRed, $null,
                        [System.Windows.Rect]::new($dx, $dy, $Cell, $Cell))
    }
    $label = "$($item.label) L*$([math]::Round($item.anchor_lab[0],0))"
    $ft = [System.Windows.Media.FormattedText]::new($label,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Windows.FlowDirection]::LeftToRight,
            $typeface, 13, [System.Windows.Media.Brushes]::White, 1.0)
    $dc.DrawText($ft, [System.Windows.Point]::new($dx + 3, $dy + $Cell + 4))
    $i++
  }
  $dc.Close()
  $rtb = [System.Windows.Media.Imaging.RenderTargetBitmap]::new($w, $h, 96, 96,
           [System.Windows.Media.PixelFormats]::Pbgra32)
  $rtb.Render($dv)
  $enc = [System.Windows.Media.Imaging.PngBitmapEncoder]::new()
  $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($rtb))
  $out = "{0}-{1:D2}.png" -f $OutPrefix, $sheetIndex
  $fs = [System.IO.File]::Create($out)
  $enc.Save($fs)
  $fs.Close()
  "saved $out  ($($chunk.Count) tiles, ${w}x${h})"
}
