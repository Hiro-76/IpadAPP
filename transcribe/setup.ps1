<#
  文字起こしソフトの下ごしらえ。
    .\setup.ps1                 既定 (small モデルまで取得)
    .\setup.ps1 -Model medium   取っておくモデルを変える
    .\setup.ps1 -NoModel        モデルは後回し（初回起動時に取りに行く）
    .\setup.ps1 -Gpu            NVIDIA GPU 用のライブラリも入れる
#>
param(
  [string]$Model = "small",
  [switch]$NoModel,
  [switch]$Gpu
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
  foreach ($candidate in @(@("py", "-3"), @("python"), @("python3"))) {
    $exe = $candidate[0]
    $args = @($candidate[1..($candidate.Length - 1)])
    try {
      $version = & $exe @args -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
      if ($LASTEXITCODE -eq 0 -and $version) { return @{ Exe = $exe; Args = $args; Version = $version.Trim() } }
    } catch { }
  }
  return $null
}

$python = Find-Python
if (-not $python) {
  Write-Host "Python が見つからない。次のどちらかで入れること:" -ForegroundColor Red
  Write-Host "  winget install Python.Python.3.12"
  Write-Host "  https://www.python.org/downloads/windows/ （インストール時に tcl/tk を外さない）"
  exit 1
}
Write-Host "Python $($python.Version) を使う" -ForegroundColor Cyan

$venv = Join-Path $PSScriptRoot ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
  Write-Host "仮想環境を作る (.venv)…"
  & $python.Exe @($python.Args) -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "必要なものを入れる…"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "依存の取得に失敗した" -ForegroundColor Red; exit 1 }

if ($Gpu) {
  Write-Host "NVIDIA GPU 用のライブラリを入れる…"
  & $py -m pip install "nvidia-cublas-cu12" "nvidia-cudnn-cu12>=9,<10"
}

& $py -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "tkinter が入っていない。python.org 版の Python を tcl/tk 付きで入れ直すこと。" -ForegroundColor Yellow
}

if (-not $NoModel) {
  $models = Join-Path $env:APPDATA "MojiOkoshi\models"
  New-Item -ItemType Directory -Force -Path $models | Out-Null
  Write-Host "モデル $Model を取ってくる（初回だけ通信する）…"
  & $py -c @"
from faster_whisper import WhisperModel
WhisperModel('$Model', device='cpu', compute_type='int8', download_root=r'$models')
print('モデルを取得した')
"@
  if ($LASTEXITCODE -ne 0) {
    Write-Host "モデルを取得できなかった。通信を確認して、もう一度 setup.ps1 を実行すること。" -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "準備できた。run.bat をダブルクリックで起動する。" -ForegroundColor Green
