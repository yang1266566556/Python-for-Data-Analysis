# fix-open-design-dsh-credentials.ps1
#
# 修复 Open Design 运行 DeepSeek Harness 时的:
#   Error: dsh: plugin tree failed to load: dsh: 1 entry did not activate
#   @deepseek-ai/dsh-credentials-local: TypeError: credentials-local:
#     the value for "version" in C:\Users\<you>\.dsh\.credentials.yaml must be a string
#   => DSH_PROFILE_MISSING_RESULT / profile exited without a terminal result
#
# 原因: Open Design 0.19.2 只支持 dsh 0.1.0-rc.6，而 rc.6 的凭据插件只认
#   “扁平”布局 (REF: value)。新版 dsh 0.2.x 已把共享的 $DSH_HOME\.credentials.yaml
#   迁移成 version:1 / refs / records 布局，rc.6 解析不了，整个插件树加载失败。
#
# 做法: 给 open-design profile 单独指定一个扁平格式的凭据文件，不动共享文件，
#   所以 0.2.x 的 Web 配置不会被影响，也不会互相来回迁移。
#
# 用法 (普通 PowerShell 即可，不需要管理员):
#   powershell -ExecutionPolicy Bypass -File .\fix-open-design-dsh-credentials.ps1

$ErrorActionPreference = 'Stop'

$dshHome     = Join-Path $env:USERPROFILE '.dsh'
$shared      = Join-Path $dshHome '.credentials.yaml'
$profDir     = Join-Path $dshHome 'profiles\open-design'
$profileCred = Join-Path $profDir '.credentials.yaml'
$patchPath   = Join-Path $profDir 'cordis.patch.yml'

if (-not (Test-Path $profDir)) { throw "找不到 profile 目录: $profDir (请先在 Open Design 里点一次刷新/修复)" }
if (-not (Test-Path $shared))  { throw "找不到共享凭据文件: $shared" }

$src = [System.IO.File]::ReadAllText($shared)
$m = [regex]::Match($src, '(?m)^[ \t]+DEEPSEEK_API_KEY:[ \t]*(\S+)[ \t]*$')
if (-not $m.Success) { throw "在 $shared 的 refs 段里找不到 DEEPSEEK_API_KEY" }
$val = $m.Groups[1].Value
if ($val.Length -lt 8) { throw '取到的 DEEPSEEK_API_KEY 太短，已中止' }

$enc   = [System.Text.UTF8Encoding]::new($false)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (Test-Path $patchPath)   { Copy-Item $patchPath   "$patchPath.bak-$stamp" -Force }
if (Test-Path $profileCred) { Copy-Item $profileCred "$profileCred.bak-$stamp" -Force }

# 1) profile 专用的扁平凭据文件
[System.IO.File]::WriteAllText($profileCred, "DEEPSEEK_API_KEY: $val`n", $enc)

# 2) 让 open-design profile 的 credentials 插件读取该文件
$credPathYaml = $profileCred -replace '\\','/'
$patch = @"
# Your patch layer for this dsh profile, applied after every bundle layer:
# a top-level YAML array of loader patch entries (id-targeted config
# overrides, disables, and insert lists; js expressions allowed).
- id: credentials
  name: "@deepseek-ai/dsh-credentials-local"
  config:
    path: "$credPathYaml"
"@
[System.IO.File]::WriteAllText($patchPath, $patch, $enc)

Write-Host "OK  凭据文件: $profileCred"
Write-Host "OK  patch   : $patchPath"
if (Test-Path "$patchPath.bak-$stamp") { Write-Host "    备份     : $patchPath.bak-$stamp" }
Write-Host ''
Write-Host '验证 (会启动一次 profile):'
Write-Host '  dsh --profile open-design --probe'
Write-Host '  dsh --profile open-design --models'
Write-Host ''
Write-Host '然后回到 Open Design 点刷新 agent 列表，再重试运行。'
