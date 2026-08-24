"""設定の保存と読み込み。

Windows では %APPDATA%\\MojiOkoshi\\config.json に置く。
書けない場所（USB から直接動かした等）では黙って既定値のまま動く。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict

APP_NAME = "MojiOkoshi"

MODEL_SIZES = [
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
]

LANGUAGES = {
    "自動判定": None,
    "日本語": "ja",
    "英語": "en",
}


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def default_output_dir() -> Path:
    docs = Path.home() / "Documents"
    if not docs.exists():
        docs = Path.home()
    return docs / "文字起こし"


def models_dir() -> Path:
    return app_dir() / "models"


@dataclass
class Config:
    model_size: str = "small"
    device: str = "auto"           # auto / cpu / cuda
    compute_type: str = "auto"     # auto / int8 / int8_float16 / float16 / float32
    language: str = "ja"           # None なら自動判定
    task: str = "transcribe"       # transcribe / translate
    source_kind: str = "mic"       # mic / loopback
    device_name: str = ""          # 前回選んだ入力の名前（番号は起動ごとに変わるため）
    show_partial: bool = True
    show_time: bool = True
    autosave: bool = True
    output_dir: str = ""
    silence_sec: float = 0.7
    max_utterance_sec: float = 24.0
    beam_size: int = 5
    font_size: int = 13

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        path = app_dir() / "config.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        cfg.update(raw)
        if not cfg.output_dir:
            cfg.output_dir = str(default_output_dir())
        return cfg

    def update(self, raw: Dict[str, Any]) -> None:
        if not isinstance(raw, dict):
            return
        known = {f.name: f.type for f in fields(self)}
        for key, value in raw.items():
            if key not in known or value is None:
                continue
            current = getattr(self, key)
            try:
                if isinstance(current, bool):
                    value = bool(value)
                elif isinstance(current, int) and not isinstance(value, bool):
                    value = int(value)
                elif isinstance(current, float):
                    value = float(value)
                elif isinstance(current, str):
                    value = str(value)
            except (TypeError, ValueError):
                continue
            setattr(self, key, value)

    def save(self) -> None:
        try:
            directory = app_dir()
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "config.json").write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # 設定が残らないだけで、動作には影響させない

    def resolved_language(self):
        lang = (self.language or "").strip()
        return lang or None

    def resolved_compute_type(self, device: str) -> str:
        if self.compute_type and self.compute_type != "auto":
            return self.compute_type
        return "float16" if device == "cuda" else "int8"
