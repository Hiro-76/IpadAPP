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
| `--initial-prompt` | なし | 語彙を誘導する文(下記) |
| `--prompt-file` | `atc_prompt.txt` | 語彙を書いたファイル |
| `--no-condition` | off | 直前の認識結果を次に渡さない |
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

## 自己テスト

faster-whisper と ctranslate2 を偽物に差し替えて main() の全経路を通す。
GPU も実モデルも不要:

    pip install pyflakes      # 未定義名の検出に使う。無ければその検査だけ飛ばす
    python selftest.py

`transcribe.py` を編集したら実行すること。構文エラーにならない未定義名
(関数を消した、名前を打ち間違えた)は `python -m py_compile` では素通りする。

## 精度を上げる

### 固有名詞の誤認識

地名・管制機関名は崩れやすい。実例として Minneapolis Center が `munich` や
`minneapol siberia` になる。`--initial-prompt` に正しい綴りを与えると改善する:

    python transcribe.py rec.mp3 --initial-prompt "Minneapolis Center, Aberdeen, Denver, Kansas City"

出現する管制機関・空港・ウェイポイントを列挙しておく。プロンプトは
モデルへの語彙のヒントであって、出力に混ざることはない。

**プロンプトは学習ではない。** その 1 回の推論に渡す文脈にすぎず、モデルの
重みは変わらないので、実行のたびに指定し直す必要がある。毎回打たずに済ませるには
`atc_prompt.txt` をフォルダに置く。あれば自動で読まれる:

    # atc_prompt.txt
    Minneapolis Center
    Aberdeen        # 空港
    Denver
    Chicago Center

`#` 以降と空行は無視されるので、整理して書ける。別名のファイルを使うときは
`--prompt-file`、その場限りで上書きするときは `--initial-prompt` を渡す
(優先順は `--initial-prompt` > `--prompt-file` > `atc_prompt.txt`)。

### 同じ文言の繰り返し

長い録音で同一フレーズが延々と続く場合、直前の文脈に引きずられている。
`--no-condition` で切り離す:

    python transcribe.py rec.mp3 --no-condition

無線交信は1回ごとに独立しているため、ATC 音声では切った方が安定することが多い。

### その他

- `--beam-size 10` — 精度がわずかに上がり、その分遅くなる
- `--no-vad` — VAD が有効な発話を切り落としている疑いがあるとき

## 読み上げ数字を数値にする

ATC は数字を 1 桁ずつ読む。そのままでは読みにくいので `--digits` で変換する:

    python transcribe.py rec.mp3 --plain --digits

| 変換前 | 変換後 |
|---|---|
| `one three five point zero two five` | `135.025` |
| `turn left heading three zero zero` | `turn left heading 300` |
| `flight level three five zero` | `flight level 350` |
| `climb and maintain six thousand` | `climb and maintain 6000` |
| `american twenty five ninety four` | `american 2594` |

既にあるテキストを変換するには `atc_numbers.py` を単体で使う:

    python atc_numbers.py 240801_NH11_2.txt              # <名前>.digits.txt に保存
    python atc_numbers.py 240801_NH11_2.txt --stdout     # 画面に出すだけ

既定では別名で保存し、入力には触らない。

### --digits を付け忘れたとき

文字起こしをやり直す必要はない。出来上がったファイルを `-i` で上書きする:

    python atc_numbers.py -i 240801_NH11_2.*

ワイルドカードで `.txt` `.plain.txt` `.srt` をまとめて処理する。音声・動画は
拡張子で判別して飛ばすので、`.MP3` を巻き込む心配はない。SRT の番号と
タイムコードは数の語を含まないためそのまま残る。

変換は冪等なので、既に変換済みのファイルに対して流しても何も変わらない。

### 変換の仕組み

ATC には読み方が 2 通り混ざる。1 桁ずつ読む `three five zero` (=350) と、
まとめて読む `six thousand` (=6000)、`twenty five` (=25) である。
`hundred` / `thousand` を含む並びだけ算術で解釈し、それ以外は桁の連結として扱う。
連結にしないと `three zero zero zero` が 3000 でなく 3 になってしまう。

小数部は 1 桁ずつしか読まれないため、`fifteen` や `sixty` のようなまとめ読みが
現れたらそこで数字が変わったと判断する。これがないと
`one three five point zero two five fifteen sixty five` が
`135.0251565` と繋がってしまう。

`point` は数と数に挟まれたときだけ小数点とみなすので、`holding point` の
`point` は残る。
