"""文字起こし結果の入れ物と、txt / srt / vtt への書き出し。

外部ライブラリに依存しないので、そのままテストできる。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass
class Segment:
    """1 区切りぶんの文字起こし。start / end は録音開始からの秒。"""

    start: float
    end: float
    text: str

    def clean(self) -> "Segment":
        return Segment(self.start, self.end, self.text.strip())


def _split_time(seconds: float) -> tuple:
    if seconds is None or seconds < 0 or seconds != seconds:  # NaN も 0 扱い
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return h, m, s, ms


def format_timestamp(seconds: float, *, sep: str = ",") -> str:
    """00:01:02,345 形式。VTT は sep='.' で呼ぶ。"""
    h, m, s, ms = _split_time(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def format_clock(seconds: float) -> str:
    """画面に出す用の短い時刻。1 時間未満は mm:ss。"""
    h, m, s, _ = _split_time(seconds)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def to_txt(segments: Iterable[Segment], *, with_time: bool = True) -> str:
    lines = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        if with_time:
            lines.append(f"[{format_clock(seg.start)}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines) + ("\n" if lines else "")


def to_srt(segments: Iterable[Segment]) -> str:
    out = []
    n = 0
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        n += 1
        end = max(seg.end, seg.start + 0.2)
        out.append(str(n))
        out.append(f"{format_timestamp(seg.start)} --> {format_timestamp(end)}")
        out.append(text)
        out.append("")
    return "\n".join(out)


def to_vtt(segments: Iterable[Segment]) -> str:
    out = ["WEBVTT", ""]
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        end = max(seg.end, seg.start + 0.2)
        out.append(
            f"{format_timestamp(seg.start, sep='.')} --> {format_timestamp(end, sep='.')}"
        )
        out.append(text)
        out.append("")
    return "\n".join(out)


WRITERS = {
    ".txt": lambda segs: to_txt(segs, with_time=True),
    ".srt": to_srt,
    ".vtt": to_vtt,
}


def render(segments: Iterable[Segment], suffix: str, *, with_time: bool = True) -> str:
    """拡張子に合わせて文字列を作る。未知の拡張子は txt 扱い。"""
    suffix = (suffix or "").lower()
    segs = list(segments)
    if suffix == ".srt":
        return to_srt(segs)
    if suffix == ".vtt":
        return to_vtt(segs)
    return to_txt(segs, with_time=with_time)


_FS_BAD = re.compile(r'[\\/:*?"<>|\r\n\t]')


def safe_filename(name: str, *, fallback: str = "transcript") -> str:
    """Windows のファイル名に使えない文字を落とす。"""
    name = _FS_BAD.sub("_", (name or "").strip())
    name = name.strip(" .")
    return name[:80] or fallback
