"""まとめて文字起こしする用。画面を出さずにファイルを処理する。

    python cli.py 会議.mp4
    python cli.py 録音フォルダ --model medium --format srt --out D:\\出力
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

for _stream in (sys.stdout, sys.stderr):
    try:  # コンソールが Shift-JIS でも、出せない文字で落ちないようにする
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

from core import formats  # noqa: E402
from core.config import MODEL_SIZES, Config  # noqa: E402
from core.engine import EngineError, WhisperEngine  # noqa: E402

# 音声も動画も同じように扱う（動画は音声トラックだけを読む）
MEDIA_SUFFIXES = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma",
    ".aiff", ".aif", ".amr",
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm", ".wmv",
    ".mpg", ".mpeg", ".ts", ".3gp", ".flv",
}


def collect(paths) -> list:
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(
                sorted(p for p in path.iterdir() if p.suffix.lower() in MEDIA_SUFFIXES)
            )
        elif path.exists():
            found.append(path)
        else:
            print(f"見つからない: {path}", file=sys.stderr)
    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="音声・動画をこの PC の中だけで文字にする",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("paths", nargs="+", help="ファイルかフォルダ")
    parser.add_argument("--model", default=None, choices=MODEL_SIZES, help="モデルの大きさ")
    parser.add_argument("--lang", default=None, help="ja / en など。auto で自動判定")
    parser.add_argument(
        "--format", default="txt", choices=["txt", "srt", "vtt"], help="出力の形"
    )
    parser.add_argument("--out", default=None, help="出力先フォルダ（既定は元と同じ場所）")
    parser.add_argument("--translate", action="store_true", help="英語に翻訳して出す")
    parser.add_argument("--device", default=None, choices=["auto", "cpu", "cuda"])
    parser.add_argument("--no-time", action="store_true", help="txt に時刻を入れない")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    config = Config.load()
    if args.model:
        config.model_size = args.model
    if args.lang is not None:
        config.language = "" if args.lang.lower() == "auto" else args.lang
    if args.device:
        config.device = args.device
    config.task = "translate" if args.translate else "transcribe"

    targets = collect(args.paths)
    if not targets:
        print("処理するファイルが無い", file=sys.stderr)
        return 1

    engine = WhisperEngine(config)
    try:
        engine.ensure_loaded(lambda msg: print(msg, file=sys.stderr))
    except EngineError as exc:
        print(exc, file=sys.stderr)
        return 2

    suffix = "." + args.format
    failed = 0
    for path in targets:
        out_dir = Path(args.out) if args.out else path.parent
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            print(f"{out_dir} を作れない: {exc}", file=sys.stderr)
            return 2
        destination = out_dir / (formats.safe_filename(path.stem) + suffix)

        print(f"→ {path.name}", file=sys.stderr)
        segments = []
        last = -1
        try:
            def progress(ratio, _seg):
                nonlocal last
                percent = int(ratio * 100)
                if percent // 5 != last // 5:
                    last = percent
                    print(f"   {percent:3d}%", end="\r", file=sys.stderr)

            for seg in engine.transcribe_file(str(path), progress=progress):
                segments.append(seg)
        except Exception as exc:
            failed += 1
            print(f"   失敗: {exc}", file=sys.stderr)
            continue

        body = formats.render(segments, suffix, with_time=not args.no_time)
        encoding = "utf-8-sig" if suffix == ".txt" else "utf-8"
        destination.write_text(body, encoding=encoding)
        print(f"   {len(segments)} 行 → {destination}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
