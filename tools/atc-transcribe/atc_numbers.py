#!/usr/bin/env python3
"""ATC 無線の読み上げ数字を数値表記に変換する。

    one three five point zero two five  ->  135.025
    turn left heading three zero zero   ->  turn left heading 300
    climb and maintain six thousand     ->  climb and maintain 6000
    delta eight seventy six             ->  delta 876

使い方:

    python atc_numbers.py 240801_NH11_2.txt              # <名前>.digits.txt に保存
    python atc_numbers.py -i 240801_NH11_2.*             # 上書き (--digits の付け忘れ用)
    python atc_numbers.py 240801_NH11_2.txt -o out.txt   # 保存先を指定
    python atc_numbers.py 240801_NH11_2.txt --stdout     # 画面に出すだけ
"""

import argparse
import glob
import os
import re
import sys

UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "tree": 3,       # ATC 式の読み
    "four": 4,
    "fower": 4,
    "five": 5,
    "fife": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "niner": 9,
}

TEENS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

MULTIPLIERS = {"hundred": 100, "thousand": 1000}

DECIMAL_WORDS = {"point", "decimal"}

# 数の語かどうか
NUMBER_WORDS = set(UNITS) | set(TEENS) | set(TENS) | set(MULTIPLIERS)

# ここで区切られたら数の並びは途切れたとみなす
BREAKING_PUNCT = set(",.;:!?")

_WORD_RE = re.compile(r"^([^A-Za-z]*)([A-Za-z']*)([^A-Za-z]*)$")


def split_word(token):
    """トークンを (前の記号, 単語, 後ろの記号) に分ける。"""
    m = _WORD_RE.match(token)
    if not m:
        return "", token, ""
    return m.group(1), m.group(2), m.group(3)


def digits_of(words):
    """数の語の並びを数値文字列にする。

    ATC では読み方が2通り混ざる:
      - 1桁ずつ読む  "three five zero" -> 350
      - まとめて読む "six thousand"    -> 6000, "twenty five" -> 25

    hundred / thousand が含まれる並びだけ算術で解釈し、
    それ以外は桁の連結として扱う。連結にしないと
    "three zero zero zero" が 3000 ではなく 3 になってしまう。
    """
    chunks = []       # 直近の倍数以降に積んだ桁
    total = 0
    saw_multiplier = False

    i = 0
    while i < len(words):
        word = words[i]

        # "twenty five" のような 十の位+一の位 は 1 つの数にまとめる
        if word in TENS and i + 1 < len(words):
            nxt = words[i + 1]
            if nxt in UNITS and UNITS[nxt] != 0:
                chunks.append(str(TENS[word] + UNITS[nxt]))
                i += 2
                continue

        if word in TENS:
            chunks.append(str(TENS[word]))
        elif word in TEENS:
            chunks.append(str(TEENS[word]))
        elif word in UNITS:
            chunks.append(str(UNITS[word]))
        elif word in MULTIPLIERS:
            saw_multiplier = True
            # "one one thousand" は 11000。桁を連結してから掛ける
            base = int("".join(chunks)) if chunks else 1
            total += base * MULTIPLIERS[word]
            chunks = []
        i += 1

    if saw_multiplier:
        tail = int("".join(chunks)) if chunks else 0
        return str(total + tail)

    return "".join(chunks)


def convert_run(words):
    """数の語の並び(point を含みうる)を文字列にする。"""
    parts = [[]]
    for word in words:
        if word in DECIMAL_WORDS:
            parts.append([])
        else:
            parts[-1].append(word)

    rendered = [digits_of(p) for p in parts]
    if any(r == "" for r in rendered):
        # 変換できない並びは触らない
        return None
    # 小数部は必ず桁の連結。125.025 の先頭の 0 を落とさないため
    return ".".join(rendered)


def convert_text(text):
    """1 行ぶんの文字列を変換して返す。"""
    tokens = re.findall(r"\s+|\S+", text)

    # 単語トークンの位置と中身を取っておく
    words = []
    for index, token in enumerate(tokens):
        if token.strip():
            lead, core, trail = split_word(token)
            words.append((index, lead, core.lower(), trail, token))

    out = list(tokens)
    consumed = set()

    i = 0
    while i < len(words):
        _, lead, core, trail, _ = words[i]
        if core not in NUMBER_WORDS:
            i += 1
            continue

        run = [i]
        breaks = bool(BREAKING_PUNCT & set(trail))
        after_point = False
        j = i + 1
        while not breaks and j < len(words):
            _, nlead, ncore, ntrail, _ = words[j]
            if nlead:
                break
            if ncore in NUMBER_WORDS:
                # 小数部は 1 桁ずつ読まれる ("point zero two five")。
                # まとめ読み ("fifteen", "sixty") が来たら、それは
                # 小数の続きではなく次の数字なので切る。
                if after_point and ncore not in UNITS:
                    break
                run.append(j)
            elif ncore in DECIMAL_WORDS and j + 1 < len(words):
                # point は数と数に挟まれたときだけ小数点とみなす
                after = words[j + 1][2]
                if after in UNITS and not words[j + 1][1]:
                    run.append(j)
                    after_point = True
                else:
                    break
            else:
                break
            breaks = bool(BREAKING_PUNCT & set(ntrail))
            j += 1

        value = convert_run([words[k][2] for k in run])
        if value is not None:
            first = words[run[0]]
            last = words[run[-1]]
            out[first[0]] = first[1] + value + last[3]
            for k in run[1:]:
                consumed.add(words[k][0])
                # 直前の空白も消す
                if words[k][0] - 1 >= 0 and not tokens[words[k][0] - 1].strip():
                    consumed.add(words[k][0] - 1)

        i = j if j > i else i + 1

    return "".join(t for idx, t in enumerate(out) if idx not in consumed)


# ワイルドカード指定で音声・動画を巻き込まないよう弾く
SKIP_EXTS = (
    ".mp3", ".mp4", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac",
    ".wma", ".mkv", ".mov", ".webm", ".avi", ".ts", ".zip", ".pdf",
)


def default_output(path):
    stem, ext = os.path.splitext(path)
    return f"{stem}.digits{ext or '.txt'}"


def expand_inputs(patterns):
    """引数を展開し、(処理するファイル, 飛ばしたファイル, 見つからない指定) を返す。"""
    files, skipped, missing = [], [], []
    for pattern in patterns:
        hits = sorted(h for h in glob.glob(pattern) if os.path.isfile(h))
        if not hits:
            if os.path.isfile(pattern):
                hits = [pattern]
            else:
                missing.append(pattern)
                continue
        for hit in hits:
            if hit in files or hit in skipped:
                continue
            if hit.lower().endswith(SKIP_EXTS):
                skipped.append(hit)
            else:
                files.append(hit)
    return files, skipped, missing


def convert_file(path, out_path):
    """1 ファイルを変換して書き出し、行数を返す。

    上書き時に途中で失敗して元を壊さないよう、全部変換してから書く。
    """
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    converted = [convert_text(line.rstrip("\n")) for line in lines]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(converted) + ("\n" if converted else ""))

    return len(converted)


def main():
    parser = argparse.ArgumentParser(
        description="ATC の読み上げ数字を数値表記に変換する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例:\n"
            "  python atc_numbers.py 240801_NH11_2.txt\n"
            "  python atc_numbers.py -i 240801_NH11_2.*\n"
            "  python atc_numbers.py 240801_NH11_2.txt -o clean.txt\n"
            "  python atc_numbers.py 240801_NH11_2.txt --stdout\n"
        ),
    )
    parser.add_argument("inputs", nargs="+", help="変換するテキストファイル (ワイルドカード可)")
    parser.add_argument("-o", "--output", help="出力先 (1 ファイルのときのみ)")
    parser.add_argument(
        "-i",
        "--in-place",
        action="store_true",
        help="元のファイルを上書きする。--digits を付け忘れたときはこれが最短",
    )
    parser.add_argument("--stdout", action="store_true", help="ファイルに書かず画面に出す")
    args = parser.parse_args()

    files, skipped, missing = expand_inputs(args.inputs)

    for name in missing:
        print(f"[エラー] 見つかりません: {name}", file=sys.stderr)
    for name in skipped:
        print(f"飛ばしました (テキストではない): {name}")

    if not files:
        return 1

    if args.output and len(files) > 1:
        print("[エラー] -o は 1 ファイルのときだけ使えます", file=sys.stderr)
        return 1

    if args.output and args.in_place:
        print("[エラー] -o と -i は同時に使えません", file=sys.stderr)
        return 1

    if args.stdout:
        for path in files:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    print(convert_text(line.rstrip("\n")))
        return 0

    for path in files:
        if args.in_place:
            out_path = path
        elif args.output:
            out_path = args.output
        else:
            out_path = default_output(path)

        if not args.in_place and os.path.abspath(out_path) == os.path.abspath(path):
            print(f"[エラー] 入力と同じファイルです。上書きするなら -i: {path}", file=sys.stderr)
            return 1

        count = convert_file(path, out_path)
        arrow = "上書き" if args.in_place else f"-> {out_path}"
        print(f"{path} {arrow} ({count} 行)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
