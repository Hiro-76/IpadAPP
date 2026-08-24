"""音の切れ目で発話をひとまとまりにする。

Whisper に 1 発話ずつ渡すための前さばき。numpy だけで動くのでテストできる。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

FRAME_MS = 20


@dataclass
class Utterance:
    """ひとまとまりの音声。start / end は録音開始からの秒。"""

    audio: np.ndarray
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


class Segmenter:
    """無音で区切って発話を取り出す。

    しきい値は暗騒音に合わせて動く。静かな部屋でも、空調の効いた機内でも
    同じ設定で使えるようにするため。
    """

    def __init__(
        self,
        samplerate: int = 16000,
        silence_sec: float = 0.7,
        min_utterance_sec: float = 0.6,
        max_utterance_sec: float = 24.0,
        preroll_sec: float = 0.3,
        tail_sec: float = 0.25,
        floor_rms: float = 0.0035,
    ):
        self.rate = int(samplerate)
        self.frame = max(1, int(self.rate * FRAME_MS / 1000))
        self.silence_frames = max(1, int(silence_sec * 1000 / FRAME_MS))
        self.min_frames = max(1, int(min_utterance_sec * 1000 / FRAME_MS))
        self.max_frames = max(self.min_frames + 1, int(max_utterance_sec * 1000 / FRAME_MS))
        self.tail_frames = max(0, int(tail_sec * 1000 / FRAME_MS))
        self.floor_rms = float(floor_rms)

        self._preroll: deque = deque(maxlen=max(1, int(preroll_sec * 1000 / FRAME_MS)))
        self._rest = np.zeros(0, dtype=np.float32)
        self._frames: List[np.ndarray] = []
        self._in_speech = False
        self._silence_run = 0
        self._start_frame = 0      # 発話の先頭が何フレーム目か
        self._pos = 0              # 読み込んだフレーム数
        self._noise = floor_rms / 3.0
        self.level = 0.0           # 直近の音量（メーター用）

    # --- 内部 ---------------------------------------------------------

    def _time(self, frame_index: int) -> float:
        return frame_index * self.frame / float(self.rate)

    def _threshold(self) -> float:
        return max(self.floor_rms, self._noise * 4.0)

    def _emit(self, end_frame: int) -> Optional[Utterance]:
        if not self._frames:
            return None
        audio = np.concatenate(self._frames)
        start = self._time(self._start_frame)
        utt = Utterance(audio=audio, start=start, end=self._time(end_frame))
        self._frames = []
        return utt

    # --- 外から使う ---------------------------------------------------

    def push(self, block: np.ndarray) -> List[Utterance]:
        """16kHz モノラルの塊を流し込み、確定した発話を返す。"""
        x = np.asarray(block, dtype=np.float32).reshape(-1)
        if x.size:
            self._rest = np.concatenate([self._rest, x]) if self._rest.size else x

        out: List[Utterance] = []
        n = self._rest.size // self.frame
        if n == 0:
            return out

        frames = self._rest[: n * self.frame].reshape(n, self.frame)
        self._rest = self._rest[n * self.frame :].copy()

        for i in range(n):
            frame = frames[i]
            rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
            self.level = rms
            self._pos += 1
            threshold = self._threshold()
            voiced = rms >= threshold

            if not self._in_speech:
                # 無音のあいだだけ暗騒音を学習する
                self._noise = 0.95 * self._noise + 0.05 * min(rms, self.floor_rms)
                self._preroll.append(frame)
                if voiced:
                    self._in_speech = True
                    self._silence_run = 0
                    pre = list(self._preroll)
                    self._preroll.clear()
                    self._frames = pre
                    self._start_frame = self._pos - len(pre)
                continue

            self._frames.append(frame)
            if voiced:
                self._silence_run = 0
            else:
                self._silence_run += 1

            spoken = len(self._frames)
            long_enough = spoken - self._silence_run >= self.min_frames

            if self._silence_run >= self.silence_frames:
                if long_enough:
                    # 語尾を少しだけ残して切る
                    keep = spoken - self._silence_run + self.tail_frames
                    self._frames = self._frames[: max(1, min(spoken, keep))]
                    utt = self._emit(self._start_frame + len(self._frames))
                    if utt is not None:
                        out.append(utt)
                else:
                    self._frames = []  # 物音だけだったので捨てる
                self._in_speech = False
                self._silence_run = 0
                self._preroll.clear()
            elif spoken >= self.max_frames:
                # 話し続けている。切れ目が来ないので、ここで一度区切る
                utt = self._emit(self._pos)
                if utt is not None:
                    out.append(utt)
                self._start_frame = self._pos
                self._silence_run = 0
        return out

    def peek_pending(self, min_sec: float = 1.2) -> Optional[Tuple[np.ndarray, float]]:
        """まだ確定していない途中の発話（表示だけに使う）。"""
        if not self._in_speech:
            return None
        frames = list(self._frames)  # 別のスレッドから覗かれるので写しを取る
        if not frames or len(frames) * FRAME_MS < min_sec * 1000:
            return None
        return np.concatenate(frames), self._time(self._start_frame)

    def flush(self) -> List[Utterance]:
        """録音を止めたときに、残りを吐き出す。"""
        out: List[Utterance] = []
        if self._frames and len(self._frames) >= self.min_frames:
            utt = self._emit(self._start_frame + len(self._frames))
            if utt is not None:
                out.append(utt)
        self._frames = []
        self._in_speech = False
        self._silence_run = 0
        self._rest = np.zeros(0, dtype=np.float32)
        self._preroll.clear()
        return out

    def reset(self) -> None:
        self.flush()
        self._pos = 0
        self._noise = self.floor_rms / 3.0
        self.level = 0.0
