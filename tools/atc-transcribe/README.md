# ATC 無線 オフライン文字起こし

ATC(航空管制)無線の音声/動画を、ネット接続なしでローカル文字起こしするスクリプト。

汎用 Whisper は航空無線特有の用語・数字読み上げ・雑音で WER が悪いため、
ATC 特化ファインチューニング済みモデルを既定で使う:

    jacktol/whisper-medium.en-fine-tuned-for-ATC-faster-whisper

## セットアップ (Windows / PowerShell)

    cd C:\Users\room\whisper-work
    .\whisper-env\Scripts\Activate.ps1
    pip install faster-whisper

ffmpeg が PATH に必要(mp4/mp3 のデコードに使う)。

## 使い方

    python transcribe.py --list              # フォルダ内の対象ファイル一覧
    python transcribe.py 01-02.mp3           # 1ファイル
    python transcribe.py "*.mp3" --plain     # まとめて + プレーンテキストも出力
    python transcribe.py rec.mp4 --device cuda --srt
    python transcribe.py long.mp3 --preview 15   # 冒頭15セグメントだけ下見

引数なしで実行すると、フォルダ内の候補ファイルを一覧表示する。

`ffmpeg` の実行ファイルは不要。faster-whisper は PyAV(libav 同梱)でデコードするため、
mp3/mp4 ともそのまま読める。

## 出力

入力が `01-02.mp3` の場合、同じフォルダに:

| ファイル | 内容 | 条件 |
|---|---|---|
| `01-02.txt` | タイムスタンプ付き | 常に |
| `01-02.plain.txt` | 本文のみ | `--plain` |
| `01-02.srt` | 字幕形式 | `--srt` |

同名ファイルがあると上書きされる。

`--preview N` を付けた場合は `01-02.preview.txt` のように別名で出力されるため、
下見の結果が本番の全文文字起こしを潰すことはない。

## 主なオプション

| オプション | 既定 | 説明 |
|---|---|---|
| `--device` | `auto` | `auto` / `cpu` / `cuda`。auto は GPU を自動検出 |
| `--compute-type` | 自動 | 対応形式を自動選択(下記参照) |
| `--model` | ATC特化モデル | 別モデルを試す場合 |
| `--language` | `en` | 言語コード |
| `--beam-size` | `5` | 大きいほど精度↑速度↓ |
| `--no-vad` | off | VAD フィルタを無効化 |
| `--preview N` | off | 先頭 N セグメントで打ち切る(下見用) |
| `--check-cuda` | - | CUDA まわりの状態を診断して終了 |

## GPU を使う

NVIDIA GPU の有無を確認:

    nvidia-smi

表示されれば `--device auto` が自動で `cuda` を選ぶ。

CUDA 用の cuBLAS / cuDNN が必要:

    pip install nvidia-cublas-cu12 nvidia-cudnn-cu12

Windows では、pip で入れた `nvidia-*` パッケージの DLL フォルダが検索パスに入らず、
GPU があっても `cublas64_12.dll is not found or cannot be loaded` で落ちることがある。

本スクリプトは起動時に、`site-packages/nvidia` 以下から `.dll` を含むフォルダを走査し、
`os.add_dll_directory()` と `PATH` の**両方**に登録する。ctranslate2 は CUDA ライブラリを
実行時に `LoadLibrary` で遅延ロードし、この経路は `add_dll_directory()` で追加した
パスを見ないことがあるため、片方だけでは足りない。

配置を確認したいときは:

    python transcribe.py --check-cuda

DLL の在り処、ctranslate2 のバージョン、CUDA デバイス数、デバイスごとに使える
compute_type が一覧表示される。

読み込みに失敗する場合の切り分け:

| 症状 | 対処 |
|---|---|
| DLL が見つからない | 上記2パッケージが入っているか確認 |
| VRAM 不足 (out of memory) | `--compute-type int8` |
| 原因不明 | `--device cpu` で動作するか確認 |

### compute_type の自動選択

`float16` は Pascal 世代(GTX 10xx 等)以前の GPU では効率的に扱えず、
ctranslate2 が読み込み時に例外を投げる。

そのため起動時に `ctranslate2.get_supported_compute_types()` へ問い合わせ、
このデバイスで動く型だけに絞ってから、優先順に読み込みを試す:

- GPU: `float16` → `int8_float32` → `float32`
- CPU: `int8` → `float32`

実際に採用された型は `compute_type: ... を使用` として表示される。
`--compute-type` を明示した場合は自動選択せず、その型だけを使う。
