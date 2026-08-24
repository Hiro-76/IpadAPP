"""音の入り口。マイクと「PC で鳴っている音」(WASAPI ループバック) を扱う。

sounddevice が無い環境でも import だけは通るようにしてある（テスト用）。
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

try:  # 実行環境に無くても import できるようにする
    import sounddevice as sd
except Exception:  # pragma: no cover - 環境依存
    sd = None

TARGET_RATE = 16000  # Whisper が受け取る周波数


class AudioError(RuntimeError):
    pass


@dataclass
class Source:
    """選べる入力ひとつ分。"""

    kind: str          # "mic" か "loopback"
    index: int         # sounddevice のデバイス番号
    name: str          # デバイス名
    label: str         # 画面に出す名前
    channels: int
    samplerate: float
    hostapi: str = ""

    @property
    def is_loopback(self) -> bool:
        return self.kind == "loopback"


def _require_sd():
    if sd is None:
        raise AudioError(
            "sounddevice を読み込めない。setup.ps1 を実行して依存をそろえること。"
        )


def _hostapi_names() -> List[str]:
    try:
        return [api["name"] for api in sd.query_hostapis()]
    except Exception:
        return []


def list_sources() -> List[Source]:
    """マイクと（Windows なら）ループバックを並べて返す。

    既定の入力デバイスが先頭に来るようにする。
    """
    _require_sd()
    apis = _hostapi_names()
    devices = sd.query_devices()

    try:
        default_in = sd.default.device[0]
    except Exception:
        default_in = None

    mics: List[Source] = []
    loops: List[Source] = []

    for index, dev in enumerate(devices):
        api = apis[dev["hostapi"]] if dev["hostapi"] < len(apis) else ""
        rate = float(dev.get("default_samplerate") or TARGET_RATE)
        name = (dev.get("name") or "").strip()
        if not name:
            continue

        if dev.get("max_input_channels", 0) > 0:
            mics.append(
                Source(
                    kind="mic",
                    index=index,
                    name=name,
                    label=f"マイク: {name}" + (f"  [{api}]" if api else ""),
                    channels=min(2, int(dev["max_input_channels"])),
                    samplerate=rate,
                    hostapi=api,
                )
            )

        # ループバックは WASAPI の「出力」デバイスを入力として開く
        if api == "Windows WASAPI" and dev.get("max_output_channels", 0) > 0:
            loops.append(
                Source(
                    kind="loopback",
                    index=index,
                    name=name,
                    label=f"PC音声: {name}（この PC で鳴っている音）",
                    channels=min(2, int(dev["max_output_channels"])),
                    samplerate=rate,
                    hostapi=api,
                )
            )

    # WASAPI を先に並べる（MME は名前が途中で切れる）。その中では既定のマイクが先頭。
    mics.sort(key=lambda s: (s.hostapi != "Windows WASAPI", s.index != default_in, s.index))
    return mics + loops


def find_source(sources: List[Source], name: str, kind: str) -> Optional[Source]:
    """前回使った入力を名前で探す（番号は起動ごとに変わる）。"""
    if not name:
        return None
    for src in sources:
        if src.name == name and src.kind == kind:
            return src
    for src in sources:
        if src.name == name:
            return src
    return None


def resample_mono(block: np.ndarray, src_rate: float, dst_rate: int = TARGET_RATE) -> np.ndarray:
    """多チャンネルを混ぜて 1 本にし、16kHz に落とす。"""
    x = np.asarray(block, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if x.size == 0:
        return x.astype(np.float32, copy=False)
    if abs(src_rate - dst_rate) < 1e-6:
        return x.astype(np.float32, copy=False)

    if src_rate > dst_rate:
        # 折り返しを減らすため、間引く前に軽く鈍らせる
        width = int(round(src_rate / dst_rate))
        if width > 1:
            kernel = np.full(width, 1.0 / width, dtype=np.float32)
            x = np.convolve(x, kernel, mode="same").astype(np.float32)

    n_out = int(round(x.size * dst_rate / float(src_rate)))
    if n_out <= 1:
        return np.zeros(0, dtype=np.float32)
    positions = np.linspace(0.0, x.size - 1.0, n_out)
    return np.interp(positions, np.arange(x.size, dtype=np.float64), x).astype(np.float32)


class Recorder:
    """入力を開いて、生ブロックをキューに流し続ける。

    コールバックの中では copy して積むだけにして、変換は取り出す側でやる。
    """

    def __init__(self, source: Source, block_ms: int = 100, max_queue: int = 200):
        self.source = source
        self.block_ms = block_ms
        self.queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=max_queue)
        self.dropped = 0
        self.error: Optional[str] = None
        self._stream = None
        self._lock = threading.Lock()

    @property
    def samplerate(self) -> float:
        return self.source.samplerate

    def _callback(self, indata, frames, time_info, status):  # pragma: no cover - 実機依存
        if status:
            # 取りこぼしは記録するだけで、録音は止めない
            self.error = str(status)
        try:
            self.queue.put_nowait(np.array(indata, dtype=np.float32, copy=True))
        except queue.Full:
            self.dropped += 1

    def start(self) -> None:
        _require_sd()
        with self._lock:
            if self._stream is not None:
                return
            extra = None
            if self.source.is_loopback:
                try:
                    extra = sd.WasapiSettings(loopback=True)
                except (AttributeError, TypeError) as exc:
                    raise AudioError(
                        "この sounddevice では PC の音を拾えない。"
                        "setup.ps1 で sounddevice 0.5 以降に上げること。"
                    ) from exc
            blocksize = max(1, int(self.source.samplerate * self.block_ms / 1000))
            try:
                self._stream = sd.InputStream(
                    device=self.source.index,
                    channels=self.source.channels,
                    samplerate=self.source.samplerate,
                    blocksize=blocksize,
                    dtype="float32",
                    callback=self._callback,
                    extra_settings=extra,
                )
                self._stream.start()
            except Exception as exc:
                self._stream = None
                raise AudioError(f"入力を開けなかった: {exc}") from exc

    def stop(self) -> None:
        with self._lock:
            stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def read(self, timeout: float = 0.2) -> Optional[np.ndarray]:
        """16kHz モノラルにしたブロックを 1 つ返す。無ければ None。"""
        try:
            raw = self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
        return resample_mono(raw, self.samplerate)
