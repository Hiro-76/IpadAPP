"""faster-whisper の薄いかぶせ物。

モデルの読み込み、配列 1 本の文字起こし、ファイル 1 個の文字起こしだけを持つ。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from typing import Callable, Iterator, List, Optional, Tuple

import numpy as np

from .config import Config, models_dir
from .formats import Segment

ProgressCb = Optional[Callable[[str], None]]


class EngineError(RuntimeError):
    pass


def _import_whisper():
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:  # pragma: no cover - 環境依存
        raise EngineError(
            "faster-whisper が入っていない。setup.ps1 を実行すること。\n"
            f"（{exc}）"
        ) from exc
    return WhisperModel


class WhisperEngine:
    """モデル 1 つを抱えて、呼ばれたら文字に起こす。

    GPU が指定されていて動かなければ、黙って CPU に落ちる（止まるよりまし）。
    """

    def __init__(self, config: Config):
        self.config = config
        self.model = None
        self.model_size: Optional[str] = None
        self.device: Optional[str] = None
        self._lock = threading.Lock()

    # --- 読み込み -----------------------------------------------------

    def _wanted_device(self) -> str:
        want = (self.config.device or "auto").lower()
        if want in ("cpu", "cuda"):
            return want
        return "cuda" if self._cuda_available() else "cpu"

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import ctranslate2  # type: ignore

            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            return False

    def ensure_loaded(self, progress: ProgressCb = None) -> None:
        size = self.config.model_size
        device = self._wanted_device()
        with self._lock:
            if self.model is not None and self.model_size == size and self.device == device:
                return
            WhisperModel = _import_whisper()
            directory = models_dir()
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception:
                directory = None

            attempts: List[Tuple[str, str]] = [
                (device, self.config.resolved_compute_type(device))
            ]
            if device == "cuda":
                attempts.append(("cpu", self.config.resolved_compute_type("cpu")))

            last_error: Optional[Exception] = None
            for dev, compute in attempts:
                if progress:
                    where = "GPU" if dev == "cuda" else "CPU"
                    progress(f"モデル {size} を読み込み中（{where} / {compute}）…")
                try:
                    self.model = WhisperModel(
                        size,
                        device=dev,
                        compute_type=compute,
                        download_root=str(directory) if directory else None,
                    )
                    self.model_size = size
                    self.device = dev
                    if progress:
                        progress(f"モデル {size} を読み込んだ（{'GPU' if dev == 'cuda' else 'CPU'}）")
                    return
                except Exception as exc:  # GPU が無い / VRAM 不足 / 初回の取得に失敗
                    last_error = exc
                    self.model = None
                    if dev == "cuda" and progress:
                        progress("GPU で開けなかったので CPU に切り替える")
            raise EngineError(
                "モデルを読み込めなかった。初回はモデルの取得に通信が要る。\n"
                f"（{last_error}）"
            )

    def unload(self) -> None:
        with self._lock:
            self.model = None
            self.model_size = None
            self.device = None

    # --- 文字起こし ---------------------------------------------------

    def _options(self, *, quick: bool = False) -> dict:
        return dict(
            language=self.config.resolved_language(),
            task=self.config.task or "transcribe",
            beam_size=1 if quick else max(1, int(self.config.beam_size)),
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
            condition_on_previous_text=False,
        )

    def transcribe_array(
        self,
        audio: np.ndarray,
        *,
        offset: float = 0.0,
        quick: bool = False,
        initial_prompt: Optional[str] = None,
    ) -> List[Segment]:
        """16kHz モノラルの配列を文字にする。offset は録音開始からの秒。"""
        if self.model is None:
            raise EngineError("モデルが読み込まれていない")
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if audio.size < 160:
            return []
        options = self._options(quick=quick)
        if initial_prompt:
            options["initial_prompt"] = initial_prompt[-200:]
        segments, _info = self.model.transcribe(audio, **options)
        out: List[Segment] = []
        for seg in segments:
            text = (seg.text or "").strip()
            if text:
                out.append(Segment(offset + float(seg.start), offset + float(seg.end), text))
        return out

    def transcribe_file(
        self,
        path: str,
        *,
        should_stop: Optional[Callable[[], bool]] = None,
        progress: Optional[Callable[[float, Segment], None]] = None,
    ) -> Iterator[Segment]:
        """音声ファイルでも動画ファイルでも、頭から文字にする。

        動画は音声のトラックだけを取り出して読む（mp4 / mov / mkv / avi など）。
        同梱の PyAV で開けない入れ物だったときだけ、PC に ffmpeg があればそれを使う。
        progress には (進捗 0-1, 区切り) を渡す。
        """
        if self.model is None:
            raise EngineError("モデルが読み込まれていない")

        temporary: Optional[str] = None
        try:
            try:
                segments, info = self.model.transcribe(path, **self._options())
            except EngineError:
                raise
            except Exception as exc:
                temporary = self._extract_audio(path)
                if temporary is None:
                    raise EngineError(
                        f"このファイルの音声を取り出せなかった: {exc}\n"
                        "ffmpeg を入れると読める場合がある（winget install Gyan.FFmpeg）。"
                    ) from exc
                segments, info = self.model.transcribe(temporary, **self._options())

            duration = float(getattr(info, "duration", 0.0) or 0.0)
            for seg in segments:
                if should_stop and should_stop():
                    return
                text = (seg.text or "").strip()
                if not text:
                    continue
                item = Segment(float(seg.start), float(seg.end), text)
                if progress:
                    ratio = min(1.0, item.end / duration) if duration > 0 else 0.0
                    progress(ratio, item)
                yield item
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @staticmethod
    def _extract_audio(path: str) -> Optional[str]:
        """最後の手段。ffmpeg があれば 16kHz モノラルの wav に落とす。"""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        handle, out = tempfile.mkstemp(prefix="mojiokoshi-", suffix=".wav")
        os.close(handle)
        command = [
            ffmpeg, "-nostdin", "-y", "-i", path,
            "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", out,
        ]
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            proc = None
        if proc is not None and proc.returncode == 0 and os.path.getsize(out) > 1024:
            return out
        try:
            os.unlink(out)
        except OSError:
            pass
        return None
