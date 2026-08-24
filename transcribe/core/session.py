"""録音とファイル、2 種類の仕事をまとめて動かす。

画面側は events キューを読むだけでよい。中で何スレッド動いているかは見せない。
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import List, Optional

from .audio import Recorder, Source
from .config import Config
from .engine import EngineError, WhisperEngine
from .formats import Segment
from .segmenter import Segmenter, Utterance

# 画面に渡す出来事
EV_STATUS = "status"      # 文字列（下のバーに出す）
EV_FINAL = "final"        # Segment（確定した行）
EV_PARTIAL = "partial"    # 文字列（まだ確定していない途中）
EV_LEVEL = "level"        # 0..1 の音量
EV_PROGRESS = "progress"  # 0..1（ファイルのとき）
EV_ERROR = "error"        # 文字列
EV_DONE = "done"          # None


class Job:
    """録音・ファイルに共通の骨。"""

    def __init__(self, engine: WhisperEngine, config: Config, events: "queue.Queue"):
        self.engine = engine
        self.config = config
        self.events = events
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []

    # --- 通知 ---------------------------------------------------------

    def emit(self, kind: str, payload=None) -> None:
        self.events.put((kind, payload))

    # --- 制御 ---------------------------------------------------------

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float = 10.0) -> None:
        for thread in self._threads:
            thread.join(timeout=timeout)

    def _spawn(self, target, name: str) -> threading.Thread:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        self._threads.append(thread)
        return thread


class LiveSession(Job):
    """マイクか PC の音を、話の切れ目ごとに文字にしていく。"""

    def __init__(self, engine, config, events, source: Source):
        super().__init__(engine, config, events)
        self.source = source
        self.recorder = Recorder(source)
        self.segmenter = Segmenter(
            silence_sec=config.silence_sec,
            max_utterance_sec=config.max_utterance_sec,
        )
        self._work: "queue.Queue[Optional[Utterance]]" = queue.Queue()
        self._prompt = ""
        self._busy = threading.Event()
        self._warned_backlog = False

    def start(self) -> None:
        self._spawn(self._run, "live-capture")

    # --- 取り込み -----------------------------------------------------

    def _run(self) -> None:
        try:
            self.engine.ensure_loaded(lambda msg: self.emit(EV_STATUS, msg))
        except EngineError as exc:
            self.emit(EV_ERROR, str(exc))
            self.emit(EV_DONE)
            return

        try:
            self.recorder.start()
        except Exception as exc:
            self.emit(EV_ERROR, str(exc))
            self.emit(EV_DONE)
            return

        worker = self._spawn(self._work_loop, "live-worker")
        kind = "PC の音" if self.source.is_loopback else "マイク"
        self.emit(EV_STATUS, f"{kind}を聞いている: {self.source.name}")

        last_level = 0.0
        try:
            while not self.stopping:
                block = self.recorder.read(timeout=0.2)
                if block is None:
                    continue
                for utt in self.segmenter.push(block):
                    self._work.put(utt)
                level = min(1.0, self.segmenter.level * 12.0)
                # 針が落ちるのは緩やかに、上がるのは即座に
                last_level = level if level > last_level else last_level * 0.7 + level * 0.3
                self.emit(EV_LEVEL, last_level)
                self._check_backlog()
        except Exception as exc:  # pragma: no cover - 実機依存
            self.emit(EV_ERROR, f"録音が止まった: {exc}")
        finally:
            self.recorder.stop()
            for utt in self.segmenter.flush():
                self._work.put(utt)
            self._work.put(None)  # 仕舞いの合図
            worker.join(timeout=120)
            if self.recorder.dropped:
                self.emit(EV_STATUS, f"音の取りこぼしが {self.recorder.dropped} 回あった")
            self.emit(EV_DONE)

    def _check_backlog(self) -> None:
        if self._warned_backlog or self._work.qsize() < 4:
            return
        self._warned_backlog = True
        self.emit(
            EV_STATUS,
            "変換が追いついていない。モデルを小さくすると軽くなる（tiny / base / small）",
        )

    # --- 変換 ---------------------------------------------------------

    def _work_loop(self) -> None:
        last_partial = 0.0
        while True:
            try:
                utt = self._work.get(timeout=0.3)
            except queue.Empty:
                now = time.monotonic()
                if self.config.show_partial and now - last_partial > 0.9:
                    last_partial = now
                    self._emit_partial()
                continue

            if utt is None:
                return
            self._busy.set()
            try:
                segments = self.engine.transcribe_array(
                    utt.audio, offset=utt.start, initial_prompt=self._prompt
                )
            except Exception as exc:
                self.emit(EV_ERROR, f"変換に失敗した: {exc}")
                segments = []
            finally:
                self._busy.clear()

            self.emit(EV_PARTIAL, "")
            for seg in segments:
                self._prompt = (self._prompt + " " + seg.text)[-200:]
                self.emit(EV_FINAL, seg)

    def _emit_partial(self) -> None:
        pending = self.segmenter.peek_pending()
        if pending is None:
            return
        audio, start = pending
        try:
            segments = self.engine.transcribe_array(audio, offset=start, quick=True)
        except Exception:
            return
        if self._work.qsize():  # 確定分が来たので途中経過は捨てる
            return
        text = " ".join(seg.text for seg in segments).strip()
        if text:
            self.emit(EV_PARTIAL, text)


class FileJob(Job):
    """音声・動画ファイルを頭から最後まで文字にする。"""

    def __init__(self, engine, config, events, path: str):
        super().__init__(engine, config, events)
        self.path = path

    def start(self) -> None:
        self._spawn(self._run, "file-job")

    def _run(self) -> None:
        try:
            self.engine.ensure_loaded(lambda msg: self.emit(EV_STATUS, msg))
        except EngineError as exc:
            self.emit(EV_ERROR, str(exc))
            self.emit(EV_DONE)
            return

        name = os.path.basename(self.path)
        self.emit(EV_STATUS, f"{name} を読んでいる…")
        count = 0
        try:
            def on_progress(ratio: float, seg: Segment) -> None:
                self.emit(EV_PROGRESS, ratio)

            for seg in self.engine.transcribe_file(
                self.path, should_stop=lambda: self.stopping, progress=on_progress
            ):
                count += 1
                self.emit(EV_FINAL, seg)
        except Exception as exc:
            self.emit(EV_ERROR, f"{name} を読めなかった: {exc}")
        else:
            done = "途中で止めた" if self.stopping else "終わった"
            self.emit(EV_STATUS, f"{name}: {done}（{count} 行）")
        finally:
            self.emit(EV_PROGRESS, 0.0)
            self.emit(EV_DONE)
