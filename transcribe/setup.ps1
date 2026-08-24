<#
  文字起こしソフトの下ごしらえ。

    .\setup.ps1                 既定 (small モデルまで取得)
    .\setup.ps1 -Model medium   取っておくモデルを変える
    .\setup.ps1 -NoModel        モデルは後回し（初回起動時に取りに行く）
    .\setup.ps1 -Gpu            NVIDIA GPU 用のライブラリも入れる

  このファイルは BOM 付き UTF-8 で保存すること。Windows PowerShell 5.1 は
  BOM が無いと Shift-JIS として読むため、日本語の行で構文が壊れる。
#>
param(
  [string]$Model = "small",
  [switch]$NoModel,
  [switch]$Gpu
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
  $candidates = @(
    @{ Exe = "py";      Pre = @("-3") },
    @{ Exe = "python";  Pre = @() },
    @{ Exe = "python3"; Pre = @() }
  )
  foreach ($item in $candidates) {
    if (-not (Get-Command $item.Exe -ErrorAction SilentlyContinue)) { continue }
    $pre = @($item.Pre)
    $version = $null
    try {
      $version = & $item.Exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    } catch {
      continue
    }
    if ($LASTEXITCODE -eq 0 -and $version) {
      $text = ($version | Select-Object -First 1).ToString().Trim()
      if ($text.StartsWith("3.")) {
        return @{ Exe = $item.Exe; Pre = $pre; Version = $text }
      }
    }
  }
  return $null
}

$python = Find-Python
if (-not $python) {
  Write-Host "Python が見つからない。次のどちらかで入れること:" -ForegroundColor Red
  Write-Host "  winget install Python.Python.3.12"
  Write-Host "  https://www.python.org/downloads/windows/ （tcl/tk のチェックを外さない）"
  exit 1
}
Write-Host ("Python " + $python.Version + " を使う") -ForegroundColor Cyan

$venv = Join-Path $PSScriptRoot ".venv"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "仮想環境を作る (.venv) ..."
  $pre = @($python.Pre)
  & $python.Exe @pre -m venv $venv
}
if (-not (Test-Path $py)) {
  Write-Host ".venv を作れなかった。Python の入れ直しを試すこと。" -ForegroundColor Red
  exit 1
}

Write-Host "必要なものを入れる ..."
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
  Write-Host "依存の取得に失敗した。通信を確認して、もう一度実行すること。" -ForegroundColor Red
  exit 1
}

if ($Gpu) {
  Write-Host "NVIDIA GPU 用のライブラリを入れる ..."
  & $py -m pip install "nvidia-cublas-cu12" "nvidia-cudnn-cu12==9.*"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "GPU 用は入らなかった。CPU のままでも使える。" -ForegroundColor Yellow
  }
}

& $py -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "tkinter が入っていない。python.org 版の Python を tcl/tk 付きで入れ直すこと。" -ForegroundColor Yellow
}

if (-not $NoModel) {
  $models = Join-Path $env:APPDATA "MojiOkoshi\models"
  New-Item -ItemType Directory -Force -Path $models | Out-Null
  Write-Host ("モデル " + $Model + " を取ってくる（初回だけ通信する） ...")
  $code = "from faster_whisper import WhisperModel; " +
          "WhisperModel('" + $Model + "', device='cpu', compute_type='int8', " +
          "download_root=r'" + $models + "'); print('model ready')"
  & $py -c $code
  if ($LASTEXITCODE -ne 0) {
    Write-Host "モデルを取得できなかった。通信を確認して、もう一度実行すること。" -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "準備できた。run.bat をダブルクリックで起動する。" -ForegroundColor Green
