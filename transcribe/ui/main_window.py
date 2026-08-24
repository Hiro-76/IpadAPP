"""画面。tkinter だけで作ってあるので、追加の GUI ライブラリは要らない。"""

from __future__ import annotations

import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import List, Optional

from core import audio, formats, session
from core.config import LANGUAGES, MODEL_SIZES, Config, default_output_dir
from core.engine import WhisperEngine
from core.formats import Segment

BG = "#0e131a"
PANEL = "#151d27"
LINE = "#243040"
FG = "#e8eef6"
DIM = "#8fa3bb"
ACCENT = "#2f6fdd"
REC = "#d64545"
AMBER = "#e0a03a"

TASKS = {"文字起こし": "transcribe", "英語に翻訳": "translate"}
DEVICES = {"自動": "auto", "CPU": "cpu", "GPU (CUDA)": "cuda"}
AUDIO_PATTERN = "*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.wma *.aiff *.aif *.amr"
VIDEO_PATTERN = "*.mp4 *.m4v *.mov *.avi *.mkv *.webm *.wmv *.mpg *.mpeg *.ts *.3gp *.flv"
MEDIA_TYPES = [
    ("音声・動画", AUDIO_PATTERN + " " + VIDEO_PATTERN),
    ("音声", AUDIO_PATTERN),
    ("動画", VIDEO_PATTERN),
    ("すべてのファイル", "*.*"),
]


def _invert(mapping: dict, value, fallback):
    for key, val in mapping.items():
        if val == value:
            return key
    return fallback


class MainWindow:
    def __init__(self, root: tk.Tk, config: Config, initial_files=None):
        self.root = root
        self.config = config
        self.engine = WhisperEngine(config)
        self.events: "queue.Queue" = queue.Queue()
        self.job: Optional[session.Job] = None
        self.segments: List[Segment] = []
        self.sources: List[audio.Source] = []
        self.pending_files: List[str] = []
        self.autosave_path: Optional[Path] = None
        self._started_at = 0.0
        self._level = 0.0

        root.title("文字起こし — オフライン")
        root.geometry("980x680")
        root.minsize(760, 480)
        root.configure(bg=BG)

        self._build_styles()
        self._build_controls()
        self._build_text()
        self._build_status()

        self.refresh_sources(initial=True)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Control-r>", lambda e: self.toggle_record())
        root.bind("<Control-o>", lambda e: self.open_file())
        root.bind("<Control-s>", lambda e: self.save())
        root.after(80, self._drain)
        root.after(500, self._tick)
        if initial_files:
            # 「送る」やコマンドラインで渡されたファイルを、開いた直後に処理する
            self.pending_files = [str(f) for f in initial_files]
            root.after(300, self._start_next_file)

    # --- 見た目 -------------------------------------------------------

    def _build_styles(self) -> None:
        self.ui_font = tkfont.Font(family="Yu Gothic UI", size=10)
        self.text_font = tkfont.Font(family="Yu Gothic UI", size=self.config.font_size)
        self.mono_font = tkfont.Font(family="Consolas", size=max(9, self.config.font_size - 2))

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=FG, font=self.ui_font)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=DIM)
        style.configure("Status.TLabel", background=PANEL, foreground=DIM)
        style.configure(
            "TButton", background=PANEL, foreground=FG, borderwidth=0, padding=(12, 7)
        )
        style.map(
            "TButton",
            background=[("active", LINE), ("disabled", PANEL)],
            foreground=[("disabled", "#55657a")],
        )
        style.configure("Rec.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Rec.TButton", background=[("active", "#3f7ff0")])
        style.configure("Stop.TButton", background=REC, foreground="#ffffff")
        style.map("Stop.TButton", background=[("active", "#e35a5a")])
        style.configure("TCheckbutton", background=BG, foreground=DIM)
        style.map(
            "TCheckbutton",
            background=[("active", BG)],
            foreground=[("active", FG), ("selected", FG)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=PANEL,
            background=PANEL,
            foreground=FG,
            arrowcolor=DIM,
            borderwidth=0,
            padding=4,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL)],
            foreground=[("readonly", FG)],
            background=[("readonly", PANEL)],
        )
        style.configure(
            "TProgressbar", background=ACCENT, troughcolor=LINE, borderwidth=0, thickness=6
        )
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.font", self.ui_font)

    def _label(self, parent, text, column, row):
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=(0, 6))

    def _build_controls(self) -> None:
        bar = ttk.Frame(self.root, padding=(14, 12, 14, 8))
        bar.pack(fill="x")

        # 1 段目: 入力と録音ボタン
        line1 = ttk.Frame(bar)
        line1.pack(fill="x")
        self._label(line1, "入力", 0, 0)
        self.source_var = tk.StringVar()
        self.source_box = ttk.Combobox(
            line1, textvariable=self.source_var, state="readonly", width=46
        )
        self.source_box.grid(row=0, column=1, sticky="ew")
        ttk.Button(line1, text="⟳", width=3, command=self.refresh_sources).grid(
            row=0, column=2, padx=(6, 12)
        )
        self.record_btn = ttk.Button(
            line1, text="● 録音を開始", style="Rec.TButton", command=self.toggle_record
        )
        self.record_btn.grid(row=0, column=3)
        self.file_btn = ttk.Button(line1, text="ファイルを開く", command=self.open_file)
        self.file_btn.grid(row=0, column=4, padx=(8, 0))
        line1.columnconfigure(1, weight=1)

        # 2 段目: モデルなどの設定
        line2 = ttk.Frame(bar, padding=(0, 10, 0, 0))
        line2.pack(fill="x")
        self._label(line2, "モデル", 0, 0)
        self.model_var = tk.StringVar(value=self.config.model_size)
        model_box = ttk.Combobox(
            line2, textvariable=self.model_var, values=MODEL_SIZES, state="readonly", width=15
        )
        model_box.grid(row=0, column=1, padx=(0, 14))
        model_box.bind("<<ComboboxSelected>>", self._on_model_change)

        self._label(line2, "言語", 2, 0)
        self.lang_var = tk.StringVar(
            value=_invert(LANGUAGES, self.config.resolved_language(), "自動判定")
        )
        lang_box = ttk.Combobox(
            line2, textvariable=self.lang_var, values=list(LANGUAGES), state="readonly", width=10
        )
        lang_box.grid(row=0, column=3, padx=(0, 14))
        lang_box.bind("<<ComboboxSelected>>", self._on_setting_change)

        self._label(line2, "出力", 4, 0)
        self.task_var = tk.StringVar(value=_invert(TASKS, self.config.task, "文字起こし"))
        task_box = ttk.Combobox(
            line2, textvariable=self.task_var, values=list(TASKS), state="readonly", width=12
        )
        task_box.grid(row=0, column=5, padx=(0, 14))
        task_box.bind("<<ComboboxSelected>>", self._on_setting_change)

        self._label(line2, "処理", 6, 0)
        self.device_var = tk.StringVar(value=_invert(DEVICES, self.config.device, "自動"))
        device_box = ttk.Combobox(
            line2, textvariable=self.device_var, values=list(DEVICES), state="readonly", width=11
        )
        device_box.grid(row=0, column=7, padx=(0, 14))
        device_box.bind("<<ComboboxSelected>>", self._on_model_change)

        self.partial_var = tk.BooleanVar(value=self.config.show_partial)
        self.time_var = tk.BooleanVar(value=self.config.show_time)
        self.autosave_var = tk.BooleanVar(value=self.config.autosave)
        ttk.Checkbutton(
            line2, text="途中経過", variable=self.partial_var, command=self._on_setting_change
        ).grid(row=0, column=8)
        ttk.Checkbutton(
            line2, text="時刻", variable=self.time_var, command=self._on_setting_change
        ).grid(row=0, column=9)
        ttk.Checkbutton(
            line2, text="自動保存", variable=self.autosave_var, command=self._on_setting_change
        ).grid(row=0, column=10)
        line2.columnconfigure(11, weight=1)

        # 3 段目: 結果の扱い
        line3 = ttk.Frame(bar, padding=(0, 10, 0, 0))
        line3.pack(fill="x")
        ttk.Button(line3, text="保存", command=self.save).pack(side="left")
        ttk.Button(line3, text="コピー", command=self.copy).pack(side="left", padx=8)
        ttk.Button(line3, text="消す", command=self.clear).pack(side="left")
        ttk.Button(line3, text="保存先を開く", command=self.open_output_dir).pack(side="left", padx=8)
        self.progress = ttk.Progressbar(line3, mode="determinate", maximum=1.0, length=180)
        self.progress.pack(side="right")

    def _build_text(self) -> None:
        wrap = tk.Frame(self.root, bg=LINE, padx=1, pady=1)
        wrap.pack(fill="both", expand=True, padx=14, pady=(4, 8))
        self.text = tk.Text(
            wrap,
            bg=PANEL,
            fg=FG,
            insertbackground=FG,
            selectbackground=ACCENT,
            font=self.text_font,
            wrap="word",
            relief="flat",
            padx=14,
            pady=12,
            spacing1=2,
            spacing3=6,
            undo=True,
        )
        scroll = ttk.Scrollbar(wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("time", foreground=DIM, font=self.mono_font)
        self.text.tag_configure("partial", foreground=AMBER)
        self.text.tag_configure("note", foreground=DIM)

    def _build_status(self) -> None:
        bar = tk.Frame(self.root, bg=PANEL, height=30)
        bar.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").pack(
            side="left", padx=14, pady=6
        )
        self.clock_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.clock_var, style="Status.TLabel").pack(
            side="right", padx=14
        )
        self.meter = tk.Canvas(bar, width=120, height=8, bg=LINE, highlightthickness=0)
        self.meter.pack(side="right", padx=10)
        self._meter_bar = self.meter.create_rectangle(0, 0, 0, 8, fill=ACCENT, width=0)

    # --- 入力の一覧 ---------------------------------------------------

    def refresh_sources(self, initial: bool = False) -> None:
        try:
            self.sources = audio.list_sources()
        except audio.AudioError as exc:
            self.sources = []
            self.set_status(str(exc))
            if not initial:
                messagebox.showerror("入力を調べられない", str(exc))
        labels = [src.label for src in self.sources]
        self.source_box.configure(values=labels)
        if not labels:
            self.source_var.set("")
            return
        want = audio.find_source(self.sources, self.config.device_name, self.config.source_kind)
        current = self.source_var.get()
        if want is not None:
            self.source_var.set(want.label)
        elif current not in labels:
            self.source_var.set(labels[0])

    def current_source(self) -> Optional[audio.Source]:
        label = self.source_var.get()
        for src in self.sources:
            if src.label == label:
                return src
        return None

    # --- 設定の反映 ---------------------------------------------------

    def _pull_settings(self) -> None:
        self.config.model_size = self.model_var.get() or "small"
        self.config.language = LANGUAGES.get(self.lang_var.get(), "ja") or ""
        self.config.task = TASKS.get(self.task_var.get(), "transcribe")
        self.config.device = DEVICES.get(self.device_var.get(), "auto")
        self.config.show_partial = bool(self.partial_var.get())
        self.config.show_time = bool(self.time_var.get())
        self.config.autosave = bool(self.autosave_var.get())
        src = self.current_source()
        if src is not None:
            self.config.device_name = src.name
            self.config.source_kind = src.kind

    def _on_setting_change(self, event=None) -> None:
        self._pull_settings()
        self.config.save()

    def _on_model_change(self, event=None) -> None:
        self._on_setting_change()
        if self.job is not None:
            self.set_status("モデルの変更は次に開始したときから効く")

    # --- 録音 ---------------------------------------------------------

    def toggle_record(self) -> None:
        if self.job is not None:
            self.stop_job("停止した")
            return
        source = self.current_source()
        if source is None:
            messagebox.showwarning("入力が無い", "使える入力が見つからない。⟳ で読み直すこと。")
            return
        self._pull_settings()
        self.config.save()
        self._start_autosave(f"{datetime.now():%Y%m%d-%H%M} {source.name}")
        self._started_at = time.monotonic()
        job = session.LiveSession(self.engine, self.config, self.events, source)
        self._set_job(job)
        job.start()

    def open_file(self) -> None:
        """音声でも動画でも受ける。まとめて選べば順に処理する。"""
        if self.job is not None:
            messagebox.showinfo("動作中", "先に停止すること。")
            return
        paths = filedialog.askopenfilenames(
            title="音声・動画を選ぶ（複数可）", filetypes=MEDIA_TYPES
        )
        if not paths:
            return
        self.pending_files = list(paths)
        self._start_next_file()

    def _start_next_file(self) -> None:
        if self.job is not None or not self.pending_files:
            return
        path = self.pending_files.pop(0)
        if not os.path.exists(path):
            self.set_status(f"見つからない: {path}")
            self._start_next_file()
            return
        self._pull_settings()
        self.config.save()
        self._start_autosave(Path(path).stem)
        self._started_at = time.monotonic()
        job = session.FileJob(self.engine, self.config, self.events, path)
        self._set_job(job)
        job.start()
        if self.pending_files:
            self.set_status(f"{Path(path).name} を処理中（残り {len(self.pending_files)} 件）")

    def _set_job(self, job: Optional[session.Job]) -> None:
        self.job = job
        running = job is not None
        self.record_btn.configure(
            text="■ 停止" if running else "● 録音を開始",
            style="Stop.TButton" if running else "Rec.TButton",
            state="normal",  # ファイル処理も途中で止められる
        )
        self.file_btn.configure(state="disabled" if running else "normal")
        if not running:
            self.progress["value"] = 0
            self._set_level(0.0)

    def stop_job(self, note: str = "") -> None:
        self.pending_files.clear()
        if self.job is None:
            return
        self.job.stop()
        self.set_status(note or "停止中…")
        self.record_btn.configure(state="disabled")

    # --- 出来事の受け取り ---------------------------------------------

    def _drain(self) -> None:
        try:
            for _ in range(200):
                kind, payload = self.events.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(80, self._drain)

    def _handle(self, kind: str, payload) -> None:
        if kind == session.EV_FINAL:
            self._append_final(payload)
        elif kind == session.EV_PARTIAL:
            self._show_partial(payload)
        elif kind == session.EV_STATUS:
            self.set_status(payload)
        elif kind == session.EV_LEVEL:
            self._set_level(float(payload))
        elif kind == session.EV_PROGRESS:
            self.progress["value"] = float(payload)
        elif kind == session.EV_ERROR:
            self.set_status(payload)
            messagebox.showerror("エラー", payload)
        elif kind == session.EV_DONE:
            self._show_partial("")
            self._set_job(None)
            if self.autosave_path:
                self.set_status(f"保存先: {self.autosave_path}")
            if self.pending_files:
                self.root.after(200, self._start_next_file)

    def _at_bottom(self) -> bool:
        try:
            return self.text.yview()[1] > 0.995
        except tk.TclError:
            return True

    def _clear_partial(self) -> None:
        span = self.text.tag_ranges("partial")
        if span:
            self.text.delete(span[0], span[-1])

    def _append_final(self, seg: Segment) -> None:
        seg = seg.clean()
        if not seg.text:
            return
        self.segments.append(seg)
        stick = self._at_bottom()
        self._clear_partial()
        if self.config.show_time:
            self.text.insert("end", f"[{formats.format_clock(seg.start)}] ", ("time",))
        self.text.insert("end", seg.text + "\n")
        if stick:
            self.text.see("end")
        self._autosave_line(seg)

    def _show_partial(self, text: str) -> None:
        stick = self._at_bottom()
        self._clear_partial()
        text = (text or "").strip()
        if text:
            self.text.insert("end", "… " + text, ("partial",))
        if stick:
            self.text.see("end")

    def _set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))
        width = int(self._level * 120)
        color = REC if self._level > 0.92 else ACCENT
        self.meter.coords(self._meter_bar, 0, 0, width, 8)
        self.meter.itemconfigure(self._meter_bar, fill=color)

    def _tick(self) -> None:
        if self.job is not None:
            elapsed = time.monotonic() - self._started_at
            self.clock_var.set(f"{formats.format_clock(elapsed)}   {len(self.segments)} 行")
        elif self.segments:
            self.clock_var.set(f"{len(self.segments)} 行")
        self.root.after(500, self._tick)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    # --- 保存まわり ---------------------------------------------------

    def _output_dir(self) -> Path:
        directory = Path(self.config.output_dir or default_output_dir())
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _start_autosave(self, stem: str) -> None:
        self.autosave_path = None
        if not self.config.autosave:
            return
        try:
            path = self._output_dir() / (formats.safe_filename(stem) + ".txt")
            n = 2
            while path.exists():
                path = path.with_name(f"{formats.safe_filename(stem)} ({n}).txt")
                n += 1
            path.write_text("", encoding="utf-8-sig")
            self.autosave_path = path
        except Exception as exc:
            self.set_status(f"自動保存を始められなかった: {exc}")

    def _autosave_line(self, seg: Segment) -> None:
        if not self.autosave_path or not self.config.autosave:
            return
        try:
            with open(self.autosave_path, "a", encoding="utf-8-sig") as handle:
                if self.config.show_time:
                    handle.write(f"[{formats.format_clock(seg.start)}] {seg.text}\n")
                else:
                    handle.write(seg.text + "\n")
        except Exception as exc:
            self.autosave_path = None
            self.set_status(f"自動保存を止めた: {exc}")

    def _visible_text(self) -> str:
        """画面の内容（途中経過の行は除く）。手で直した分もこちらに入る。"""
        self._clear_partial()
        return self.text.get("1.0", "end-1c").strip()

    def save(self) -> None:
        if not self.segments and not self._visible_text():
            messagebox.showinfo("何も無い", "保存するものが無い。")
            return
        stem = datetime.now().strftime("%Y%m%d-%H%M 文字起こし")
        path = filedialog.asksaveasfilename(
            title="保存",
            defaultextension=".txt",
            initialdir=str(self._output_dir()),
            initialfile=stem + ".txt",
            filetypes=[("テキスト", "*.txt"), ("字幕 SRT", "*.srt"), ("字幕 VTT", "*.vtt")],
        )
        if not path:
            return
        suffix = os.path.splitext(path)[1].lower()
        try:
            if suffix in (".srt", ".vtt"):
                body = formats.render(self.segments, suffix)
                Path(path).write_text(body, encoding="utf-8")
            else:
                Path(path).write_text(self._visible_text() + "\n", encoding="utf-8-sig")
        except Exception as exc:
            messagebox.showerror("保存できない", str(exc))
            return
        self.set_status(f"保存した: {path}")

    def copy(self) -> None:
        body = self._visible_text()
        if not body:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(body)
        self.set_status("クリップボードに入れた")

    def clear(self) -> None:
        if self.segments and not messagebox.askyesno("消す", "画面の文字起こしを消す。よいか。"):
            return
        self.segments.clear()
        self.text.delete("1.0", "end")
        self.clock_var.set("")
        self.set_status("消した")

    def open_output_dir(self) -> None:
        try:
            directory = self._output_dir()
        except Exception as exc:
            messagebox.showerror("開けない", str(exc))
            return
        try:
            os.startfile(str(directory))  # type: ignore[attr-defined]
        except AttributeError:  # Windows 以外
            self.set_status(f"保存先: {directory}")
        except Exception as exc:
            self.set_status(f"開けなかった: {exc}（{directory}）")

    # --- 終了 ---------------------------------------------------------

    def on_close(self) -> None:
        self._pull_settings()
        self.config.save()
        if self.job is not None:
            self.job.stop()
            self.set_status("止めている…")
            self.root.update_idletasks()
            waiter = threading.Thread(target=self.job.join, kwargs={"timeout": 5}, daemon=True)
            waiter.start()
            waiter.join(timeout=6)
        self.root.destroy()
