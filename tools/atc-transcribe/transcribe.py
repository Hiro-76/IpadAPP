#!/usr/bin/env python3
"""
ATC (航空管制) 無線の音声/動画をローカルでオフライン文字起こしするスクリプト。

ATC特化ファインチューニング済みモデル
  jacktol/whisper-medium.en-fine-tuned-for-ATC-faster-whisper
を既定で使う。

使い方 (PowerShell / whisper-env 有効化済み):
    python transcribe.py 01-02.mp3
    python transcribe.py *.mp3 --plain
    python transcribe.py rec.mp4 --device cuda
    python transcribe.py --list          # フォルダ内の対象ファイル一覧だけ表示
"""

import argparse
import glob
import os
import site
import sys
import time

DEFAULT_MODEL = "jacktol/whisper-medium.en-fine-tuned-for-ATC-faster-whisper"

# ffmpeg 経由で読める代表的な拡張子
MEDIA_EXTS = (
    ".mp3", ".mp4", ".wav", ".m4a", ".flac", ".ogg", ".opus",
    ".aac", ".wma", ".mkv", ".mov", ".webm", ".avi", ".ts",
)


def find_media(directory="."):
    """カレント(または指定)フォルダ内の音声/動画ファイルを名前順で返す。"""
    found = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return found
    for name in sorted(entries):
        path = os.path.join(directory, name)
        if os.path.isfile(path) and name.lower().endswith(MEDIA_EXTS):
            found.append(name)
    return found


def expand_inputs(patterns):
    """引数をglob展開し、実在するファイルだけを重複なしで返す。"""
    files = []
    missing = []
    for pattern in patterns:
        # Windows の cmd/PowerShell はワイルドカードを展開しないので自前で行う
        hits = sorted(glob.glob(pattern))
        hits = [h for h in hits if os.path.isfile(h)]
        if hits:
            for h in hits:
                if h not in files:
                    files.append(h)
        elif os.path.isfile(pattern):
            if pattern not in files:
                files.append(pattern)
        else:
            missing.append(pattern)
    return files, missing


def add_nvidia_dll_dirs():
    """Windows で pip 版 CUDA ライブラリの DLL を検索パスに追加する。

    ctranslate2 は cudnn_ops64_9.dll や cublas64_12.dll を実行時にロードするが、
    pip でインストールした nvidia-* パッケージの bin フォルダは既定の DLL 検索
    パスに含まれない。その結果 GPU があっても「DLL が見つかりません」で落ちる。
    ここで明示的に追加しておく。
    """
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return []

    site_dirs = []
    try:
        site_dirs.extend(site.getsitepackages())
    except AttributeError:
        pass
    try:
        site_dirs.append(site.getusersitepackages())
    except AttributeError:
        pass

    added = []
    seen = set()
    for site_dir in site_dirs:
        nvidia_root = os.path.join(site_dir, "nvidia")
        if not os.path.isdir(nvidia_root):
            continue
        for pkg in sorted(os.listdir(nvidia_root)):
            bin_dir = os.path.join(nvidia_root, pkg, "bin")
            key = os.path.normcase(bin_dir)
            if key in seen or not os.path.isdir(bin_dir):
                continue
            seen.add(key)
            try:
                os.add_dll_directory(bin_dir)
                added.append(bin_dir)
            except OSError:
                pass
    return added


def detect_device(requested):
    """
    requested: "auto" | "cpu" | "cuda"
    戻り値: (device, 説明文)
    """
    if requested == "cpu":
        return "cpu", "指定により CPU を使用"
    if requested == "cuda":
        return "cuda", "指定により CUDA を使用"

    # auto: ctranslate2 に GPU が見えるかで判定する。
    # faster-whisper は ctranslate2 に依存しているので追加インストールは不要。
    try:
        import ctranslate2

        count = ctranslate2.get_cuda_device_count()
        if count > 0:
            return "cuda", f"CUDA デバイスを {count} 個検出したので GPU を使用"
        return "cpu", "CUDA デバイスが見つからないので CPU を使用"
    except Exception as exc:  # ctranslate2 が古い等
        return "cpu", f"GPU 判定に失敗したので CPU を使用 ({exc})"


# 上から順に試す。float16 は Pascal 世代など古い GPU では効率的に扱えず、
# ctranslate2 が読み込み時に例外を投げるため、代替を用意しておく。
CUDA_COMPUTE_PREFERENCE = ("float16", "int8_float32", "float32")
CPU_COMPUTE_PREFERENCE = ("int8", "float32")


def pick_compute_types(device, requested):
    """試す compute_type を優先順のリストで返す。

    ctranslate2 に「このデバイスで効率的に動く型」を問い合わせ、
    対応しているものだけに絞る。問い合わせに失敗した場合は
    優先リストをそのまま返し、実際の読み込みで判定させる。
    """
    if requested:
        return [requested]

    prefs = CUDA_COMPUTE_PREFERENCE if device == "cuda" else CPU_COMPUTE_PREFERENCE
    try:
        import ctranslate2

        supported = set(ctranslate2.get_supported_compute_types(device))
    except Exception:
        return list(prefs)

    ordered = [c for c in prefs if c in supported]
    return ordered or list(prefs)


def format_timestamp(seconds, sep=","):
    """SRT 用 HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"


def transcribe_one(model, path, args):
    stem, _ = os.path.splitext(path)
    # プレビュー実行が本番の全文文字起こしを上書きしないよう、出力名を分ける
    suffix = ".preview" if args.preview else ""
    ts_path = f"{stem}{suffix}.txt"
    plain_path = f"{stem}{suffix}.plain.txt"
    srt_path = f"{stem}{suffix}.srt"

    print(f"\n=== {path} ===", flush=True)
    started = time.time()

    segments, info = model.transcribe(
        path,
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
    )

    duration = getattr(info, "duration", None)
    if duration:
        print(f"音声長: {duration:.1f}s / 検出言語: {info.language}", flush=True)

    lines = []
    plain_lines = []
    srt_blocks = []

    # segments はジェネレータなので、ここで初めて実際の推論が走る
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        # 空セグメントを除外した後の連番。SRT の番号は連続している必要がある
        index = len(lines) + 1
        line = f"[{seg.start:7.1f}s -> {seg.end:7.1f}s] {text}"
        print(line, flush=True)
        lines.append(line)
        plain_lines.append(text)
        if args.srt:
            srt_blocks.append(
                f"{index}\n"
                f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}\n"
                f"{text}\n"
            )

        # segments はジェネレータなので、break した時点で以降の推論は走らない
        if args.preview and len(lines) >= args.preview:
            print(f"... --preview {args.preview} に達したので打ち切り", flush=True)
            break

    with open(ts_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    written = [ts_path]

    if args.plain:
        with open(plain_path, "w", encoding="utf-8") as f:
            f.write("\n".join(plain_lines) + ("\n" if plain_lines else ""))
        written.append(plain_path)

    if args.srt:
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_blocks))
        written.append(srt_path)

    elapsed = time.time() - started
    if args.preview:
        # 途中で打ち切ったので全体の所要時間は測れていない
        speed = " (プレビューのため実時間比は未測定)"
    else:
        speed = f" (実時間比 {duration / elapsed:.1f}x)" if duration and elapsed > 0 else ""
    print(f"--- {len(lines)} セグメント / {elapsed:.1f}s{speed}", flush=True)
    for p in written:
        print(f"    出力: {p}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="ATC無線の音声/動画をオフラインで文字起こしする",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例:\n"
            "  python transcribe.py 01-02.mp3\n"
            "  python transcribe.py *.mp3 --plain --srt\n"
            "  python transcribe.py rec.mp4 --device cuda\n"
            "  python transcribe.py --list\n"
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="文字起こしする音声/動画ファイル (ワイルドカード可)。省略時はフォルダ内の候補を表示",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"使用モデル (既定: {DEFAULT_MODEL})")
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="推論デバイス (既定: auto = GPUがあれば自動でcuda)",
    )
    parser.add_argument(
        "--compute-type",
        default=None,
        help="量子化方式。既定は cuda→float16 / cpu→int8",
    )
    parser.add_argument("--language", default="en", help="言語コード (既定: en)")
    parser.add_argument("--beam-size", type=int, default=5, help="ビームサイズ (既定: 5)")
    parser.add_argument("--no-vad", action="store_true", help="VADフィルタを無効化する")
    parser.add_argument(
        "--plain",
        action="store_true",
        help="タイムスタンプなしのプレーンテキスト (<名前>.plain.txt) も出力する",
    )
    parser.add_argument("--srt", action="store_true", help="字幕ファイル (<名前>.srt) も出力する")
    parser.add_argument(
        "--preview",
        type=int,
        metavar="N",
        default=0,
        help="先頭 N セグメントだけ処理して打ち切る。精度の下見用。"
        "出力は <名前>.preview.txt となり本番の結果を上書きしない",
    )
    parser.add_argument("--list", action="store_true", help="フォルダ内の対象ファイルを一覧表示して終了")

    args = parser.parse_args()

    if args.list or not args.inputs:
        candidates = find_media(".")
        if candidates:
            print("このフォルダ内の音声/動画ファイル:")
            for name in candidates:
                size_mb = os.path.getsize(name) / (1024 * 1024)
                print(f"  {name}  ({size_mb:.1f} MB)")
            print("\n使い方: python transcribe.py <ファイル名>")
        else:
            print("このフォルダに音声/動画ファイルが見つかりません。")
            print(f"対応拡張子: {', '.join(MEDIA_EXTS)}")
        return 0 if args.list else 1

    files, missing = expand_inputs(args.inputs)

    if missing:
        for m in missing:
            print(f"[エラー] 見つかりません: {m}", file=sys.stderr)
        candidates = find_media(".")
        if candidates:
            print("\nこのフォルダにあるのは:", file=sys.stderr)
            for name in candidates:
                print(f"  {name}", file=sys.stderr)
        if not files:
            return 1

    # ctranslate2 を import する前に DLL 検索パスを整える
    dll_dirs = add_nvidia_dll_dirs()

    device, reason = detect_device(args.device)
    candidates = pick_compute_types(device, args.compute_type)
    print(f"デバイス: {device} ({reason})")
    if device == "cuda" and dll_dirs:
        print(f"CUDA DLL 検索パスを {len(dll_dirs)} 件追加しました")
    print(f"compute_type 候補: {', '.join(candidates)}")
    print(f"モデル: {args.model}")
    print("モデルを読み込み中... (初回はダウンロードで時間がかかります)", flush=True)

    # 重い import はここまで遅延させる。--help や --list を即座に返すため。
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[エラー] faster-whisper が読み込めません。", file=sys.stderr)
        print("仮想環境が有効になっているか確認してください:", file=sys.stderr)
        print("    .\\whisper-env\\Scripts\\Activate.ps1", file=sys.stderr)
        print("未インストールなら:  pip install faster-whisper", file=sys.stderr)
        return 1

    model = None
    compute_type = None
    exc = None
    for candidate in candidates:
        try:
            model = WhisperModel(args.model, device=device, compute_type=candidate)
            compute_type = candidate
            break
        except Exception as err:
            exc = err
            print(f"  {candidate} は使えませんでした: {err}", file=sys.stderr)

    if model is not None:
        print(f"compute_type: {compute_type} を使用", flush=True)
    else:
        print(f"[エラー] モデルの読み込みに失敗しました: {exc}", file=sys.stderr)
        if device == "cuda":
            print("", file=sys.stderr)
            print("GPU での読み込みに失敗しました。よくある原因:", file=sys.stderr)
            print("  1. cuBLAS/cuDNN が未インストール", file=sys.stderr)
            print("     pip install nvidia-cublas-cu12 nvidia-cudnn-cu12", file=sys.stderr)
            print("  2. VRAM 不足 → --compute-type int8 を試す", file=sys.stderr)
            print("  3. 切り分け用に CPU で動かす → --device cpu", file=sys.stderr)
        return 1

    failed = 0
    for path in files:
        try:
            transcribe_one(model, path, args)
        except Exception as exc:
            failed += 1
            print(f"[エラー] {path} の処理に失敗: {exc}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
