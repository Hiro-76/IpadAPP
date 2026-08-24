"""文字起こし（Windows 11 向け）— 起動口。

    python app.py

マイク、PC で鳴っている音、音声・動画ファイルを、この PC の中だけで文字にする。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import Config  # noqa: E402


def _enable_dpi_awareness() -> None:
    """高解像度の画面で文字がぼやけないようにする（Windows のみ）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
    except Exception:
        pass


def main() -> int:
    _enable_dpi_awareness()
    try:
        import tkinter as tk
    except ImportError:
        print(
            "tkinter が無い。python.org の Windows 版 Python を入れ直すこと"
            "（インストール時に tcl/tk を外さない）。",
            file=sys.stderr,
        )
        return 2

    from ui.main_window import MainWindow

    config = Config.load()
    root = tk.Tk()
    try:
        icon = Path(__file__).resolve().parent / "icon.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
    except Exception:
        pass

    # 「送る」やコマンドラインで渡された音声・動画は、開いた直後から処理する
    initial_files = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    window = MainWindow(root, config, initial_files=initial_files)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        window.on_close()
    return 0


def _report_fatal(detail: str) -> None:
    """pythonw で起動していると画面が無いので、窓を出して知らせる。"""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("文字起こし — 起動できない", detail[-1500:])
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        report = traceback.format_exc()
        print(report, file=sys.stderr)
        _report_fatal(report)
        sys.exit(1)
