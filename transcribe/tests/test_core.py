"""外部ライブラリ無しで動く部分のテスト。

    python -m pytest transcribe/tests      （pytest があるとき）
    python transcribe/tests/test_core.py   （無いとき）
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import queue as _queue  # noqa: E402
import time as _time  # noqa: E402

from core import formats, session  # noqa: E402
from core.audio import Source, resample_mono  # noqa: E402
from core.config import Config  # noqa: E402
from core.formats import Segment  # noqa: E402
from core.segmenter import Segmenter  # noqa: E402

RATE = 16000


def _tone(seconds: float, amp: float = 0.25, freq: float = 220.0) -> np.ndarray:
    t = np.arange(int(RATE * seconds), dtype=np.float32) / RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _hush(seconds: float, amp: float = 0.0002) -> np.ndarray:
    rng = np.random.default_rng(7)
    return (rng.standard_normal(int(RATE * seconds)) * amp).astype(np.float32)


def test_timestamps():
    assert formats.format_timestamp(0) == "00:00:00,000"
    assert formats.format_timestamp(3661.5) == "01:01:01,500"
    assert formats.format_timestamp(-3) == "00:00:00,000"
    assert formats.format_timestamp(1.25, sep=".") == "00:00:01.250"
    assert formats.format_clock(75) == "01:15"
    assert formats.format_clock(3675) == "1:01:15"


def test_writers():
    segs = [formats.Segment(0.0, 1.5, "おはよう"), formats.Segment(2.0, 3.0, " 出発準備 ")]
    txt = formats.to_txt(segs)
    assert txt.splitlines() == ["[00:00] おはよう", "[00:02] 出発準備"]
    assert formats.to_txt(segs, with_time=False).splitlines() == ["おはよう", "出発準備"]

    srt = formats.to_srt(segs).splitlines()
    assert srt[0] == "1"
    assert srt[1] == "00:00:00,000 --> 00:00:01,500"
    assert srt[2] == "おはよう"
    assert srt[4] == "2"

    vtt = formats.to_vtt(segs).splitlines()
    assert vtt[0] == "WEBVTT"
    assert "00:00:00.000 --> 00:00:01.500" in vtt

    # 空の行は落とす
    assert formats.to_srt([formats.Segment(0, 1, "   ")]) == ""
    assert formats.render(segs, ".SRT").startswith("1\n")
    assert formats.render(segs, ".unknown").startswith("[00:00]")


def test_safe_filename():
    assert formats.safe_filename('a/b:c*?"<>|d') == "a_b_c______d"
    assert formats.safe_filename("  ...  ") == "transcript"
    assert len(formats.safe_filename("あ" * 200)) == 80


def test_resample():
    src = 48000
    t = np.arange(src, dtype=np.float32) / src
    x = np.sin(2 * np.pi * 100 * t).astype(np.float32)
    y = resample_mono(x, src)
    assert abs(y.size - RATE) <= 1
    assert y.dtype == np.float32
    # 100Hz の正弦波は落としても振幅がほぼ残る
    assert 0.6 < float(np.max(np.abs(y))) <= 1.0

    stereo = np.stack([x, -x], axis=1)
    assert float(np.max(np.abs(resample_mono(stereo, src)))) < 1e-3  # 打ち消し合う
    assert resample_mono(np.zeros(0, dtype=np.float32), src).size == 0
    same = resample_mono(x[:1000], RATE)
    assert same.size == 1000


def test_segmenter_splits_on_silence():
    seg = Segmenter(silence_sec=0.5, min_utterance_sec=0.4)
    stream = np.concatenate(
        [_hush(1.0), _tone(1.2), _hush(1.0), _tone(0.9), _hush(1.0)]
    )
    got = []
    for i in range(0, stream.size, 1600):  # 100ms ずつ
        got.extend(seg.push(stream[i : i + 1600]))
    got.extend(seg.flush())

    assert len(got) == 2, [round(u.duration, 2) for u in got]
    first, second = got
    assert 1.1 <= first.duration <= 2.0
    assert first.start < 1.05  # 立ち上がりの手前から拾えている
    assert second.start > first.end
    assert 0.8 <= second.duration <= 1.7
    for utt in got:
        assert utt.audio.dtype == np.float32
        assert float(np.max(np.abs(utt.audio))) > 0.1


def test_segmenter_drops_noise_and_cuts_long_speech():
    seg = Segmenter(silence_sec=0.4, min_utterance_sec=0.8)
    tick = np.concatenate([_hush(0.5), _tone(0.15), _hush(1.0)])
    assert seg.push(tick) == []
    assert seg.flush() == []

    seg = Segmenter(silence_sec=0.5, min_utterance_sec=0.4, max_utterance_sec=2.0)
    out = []
    for i in range(0, RATE * 5, 1600):
        out.extend(seg.push(_tone(0.1)))
    assert len(out) >= 2
    assert all(u.duration <= 2.1 for u in out)
    assert out[1].start >= out[0].end - 1e-6  # 途切れずに続く


def test_segmenter_pending_and_reset():
    seg = Segmenter()
    assert seg.peek_pending() is None
    seg.push(_tone(2.0))
    pending = seg.peek_pending()
    assert pending is not None and pending[0].size > RATE
    seg.reset()
    assert seg.peek_pending() is None


def test_config_roundtrip(tmp_path=None):
    cfg = Config()
    cfg.update({"model_size": "medium", "show_partial": 0, "beam_size": "3", "bogus": 1})
    assert cfg.model_size == "medium"
    assert cfg.show_partial is False
    assert cfg.beam_size == 3
    assert not hasattr(cfg, "bogus")
    cfg.update({"beam_size": "not a number"})
    assert cfg.beam_size == 3
    cfg.language = ""
    assert cfg.resolved_language() is None
    assert cfg.resolved_compute_type("cuda") == "float16"
    assert cfg.resolved_compute_type("cpu") == "int8"
    cfg.compute_type = "float32"
    assert cfg.resolved_compute_type("cpu") == "float32"


class _FakeRecorder:
    """マイクの代わり。決まった音を出して、尽きたら None を返し続ける。"""

    def __init__(self, source, **kwargs):
        self.source = source
        self.dropped = 0
        self._blocks = []
        stream = np.concatenate([_hush(0.6), _tone(1.2), _hush(1.2), _tone(1.0), _hush(1.0)])
        for i in range(0, stream.size, 1600):
            self._blocks.append(stream[i : i + 1600])

    def start(self):
        pass

    def stop(self):
        pass

    def read(self, timeout=0.2):
        if self._blocks:
            return self._blocks.pop(0)
        return None


class _FakeEngine:
    """Whisper の代わり。渡された長さぶんの文字を返す。"""

    def __init__(self):
        self.calls = 0

    def ensure_loaded(self, progress=None):
        if progress:
            progress("読み込んだ")

    def transcribe_array(self, audio, *, offset=0.0, quick=False, initial_prompt=None):
        self.calls += 1
        return [Segment(offset, offset + audio.size / RATE, f"発話{self.calls}")]


def test_live_session_end_to_end():
    events = _queue.Queue()
    engine = _FakeEngine()
    config = Config()
    config.show_partial = False
    source = Source(kind="mic", index=0, name="テスト入力", label="🎤 テスト入力",
                    channels=1, samplerate=RATE)

    original = session.Recorder
    session.Recorder = _FakeRecorder
    try:
        live = session.LiveSession(engine, config, events, source)
        live.start()
        started = _time.monotonic()
        deadline = started + 20
        seen = []
        done = False
        asked_stop = False
        while _time.monotonic() < deadline and not done:
            try:
                kind, payload = events.get(timeout=0.2)
            except _queue.Empty:
                pass
            else:
                if kind == session.EV_FINAL:
                    seen.append(payload)
                elif kind == session.EV_ERROR:
                    raise AssertionError(f"エラーが出た: {payload}")
                elif kind == session.EV_DONE:
                    done = True
            # 録音は止めるまで続くので、音を出し切ったところで止める
            if not asked_stop and (len(seen) >= 2 or _time.monotonic() - started > 8):
                asked_stop = True
                live.stop()
        live.stop()
        live.join(timeout=5)
    finally:
        session.Recorder = original

    assert done, "終わりの合図が来ない"
    assert len(seen) == 2, [s.text for s in seen]
    assert seen[0].start < seen[1].start
    assert all(s.text.startswith("発話") for s in seen)


def test_file_job_reports_progress_and_finish():
    events = _queue.Queue()

    class _FileEngine(_FakeEngine):
        def transcribe_file(self, path, *, should_stop=None, progress=None):
            for i in range(3):
                seg = Segment(float(i), float(i) + 0.9, f"行{i}")
                if progress:
                    progress((i + 1) / 3.0, seg)
                yield seg

    job = session.FileJob(_FileEngine(), Config(), events, "会議.mp4")
    job.start()
    job.join(timeout=10)

    kinds = []
    finals = []
    while True:
        try:
            kind, payload = events.get_nowait()
        except _queue.Empty:
            break
        kinds.append(kind)
        if kind == session.EV_FINAL:
            finals.append(payload)
    assert session.EV_ERROR not in kinds, kinds
    assert kinds[-1] == session.EV_DONE
    assert [f.text for f in finals] == ["行0", "行1", "行2"]
    assert session.EV_PROGRESS in kinds


def _main():
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print("---")
    print("すべて通った" if not failures else f"{failures} 件失敗")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main())
