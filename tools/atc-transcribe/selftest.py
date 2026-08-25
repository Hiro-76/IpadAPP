#!/usr/bin/env python3
"""transcribe.py の自己テスト。

faster-whisper と ctranslate2 を偽物に差し替えて、GPU もモデルも無い環境で
main() の全経路を通す。実行:

    python selftest.py
"""

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "transcribe.py")

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def load():
    """transcribe.py を毎回まっさらに読み込む(モジュール状態を持ち越さない)。"""
    spec = importlib.util.spec_from_file_location("tr_under_test", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def install_fakes(supported=("float32", "int8", "int8_float32"), fail_types=(), segments=200):
    """偽の ctranslate2 / faster_whisper を sys.modules に置く。"""
    ct2 = types.ModuleType("ctranslate2")
    ct2.__version__ = "0.0.0-fake"
    ct2.get_cuda_device_count = lambda: 1
    ct2.get_supported_compute_types = lambda device: set(supported)
    sys.modules["ctranslate2"] = ct2

    tried = []
    passed = {}

    class FakeModel:
        def __init__(self, name, device=None, compute_type=None):
            tried.append(compute_type)
            if compute_type in fail_types:
                raise ValueError(f"fake: {compute_type} は使えない")

        def transcribe(self, path, **kw):
            passed.update(kw)
            info = types.SimpleNamespace(duration=2612.2, language="en")

            def gen():
                for i in range(segments):
                    yield types.SimpleNamespace(
                        start=i * 3.0,
                        end=i * 3.0 + 2.5,
                        text=""
                        if i % 7 == 3
                        else " contact minneapolis one three five point zero two five ",
                    )

            return gen(), info

    fw = types.ModuleType("faster_whisper")
    fw.WhisperModel = FakeModel
    sys.modules["faster_whisper"] = fw
    return tried, passed


def run_main(mod, argv):
    """main() を argv で実行し、(戻り値, 標準出力) を返す。"""
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = ["transcribe.py"] + argv
    sys.stdout = io.StringIO()
    try:
        rc = mod.main()
        return rc, sys.stdout.getvalue()
    finally:
        sys.argv, sys.stdout = old_argv, old_out


def test_static():
    print("\n[静的解析] 未定義名・未使用 import")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pyflakes", TARGET],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("  skip pyflakes が無い (pip install pyflakes)")
        return
    if proc.returncode == 127 or "No module named" in proc.stderr:
        print("  skip pyflakes が無い (pip install pyflakes)")
        return
    check("pyflakes が警告なし", proc.returncode == 0, proc.stdout.strip())


def test_cli_without_deps():
    print("\n[CLI] 依存が無くても動く経路")
    for mod_name in ("ctranslate2", "faster_whisper"):
        sys.modules.pop(mod_name, None)
    mod = load()

    rc, out = run_main(mod, ["--list"])
    check("--list が成功する", rc == 0)
    check("--list が候補を出す", "240801_NH11_2.MP3" in out, out)

    rc, out = run_main(mod, [])
    check("引数なしは使い方を出して 1 を返す", rc == 1 and "使い方" in out)

    rc, out = run_main(mod, ["--check-cuda"])
    check("--check-cuda が成功する", rc == 0)
    check("--check-cuda が ctranslate2 に触れる", "ctranslate2" in out, out)


def test_missing_file():
    print("\n[CLI] 存在しないファイル")
    mod = load()
    rc, _ = run_main(mod, ["no_such_file.mp3"])
    check("戻り値が 1", rc == 1)


def test_compute_type_negotiation():
    print("\n[compute_type] 選択と読み込みフォールバック")
    install_fakes(supported=("float32", "int8", "int8_float32"))
    mod = load()
    check(
        "float16 非対応 GPU では候補から外れる",
        mod.pick_compute_types("cuda", None) == ["int8_float32", "float32"],
        mod.pick_compute_types("cuda", None),
    )
    check(
        "明示指定はそのまま使う",
        mod.pick_compute_types("cuda", "int8") == ["int8"],
    )

    tried, _ = install_fakes(
        supported=("float32", "int8", "int8_float32"), fail_types=("int8_float32",)
    )
    mod = load()
    rc, out = run_main(mod, ["240801_NH11_2.MP3", "--preview", "3"])
    check("失敗した候補を飛ばして成功する", rc == 0, out)
    check("試した順が優先順どおり", tried == ["int8_float32", "float32"], tried)
    check("採用した型を表示する", "compute_type: float32 を使用" in out, out)


def test_outputs():
    print("\n[出力] ファイル生成と --preview")
    install_fakes()
    mod = load()

    rc, out = run_main(mod, ["240801_NH11_2.MP3", "--plain", "--srt", "--preview", "5"])
    check("preview 実行が成功する", rc == 0, out)
    check("preview は別名で出力する", os.path.exists("240801_NH11_2.preview.txt"))
    check("本番の txt を作らない", not os.path.exists("240801_NH11_2.txt"))

    body = open("240801_NH11_2.preview.txt", encoding="utf-8").read()
    check("preview の件数が指定どおり", len(body.strip().splitlines()) == 5, body)

    plain = open("240801_NH11_2.preview.plain.txt", encoding="utf-8").read()
    check("plain にタイムスタンプが無い", "->" not in plain, plain)
    check("plain が空行を含まない", "" not in plain.strip().splitlines(), plain)

    srt = open("240801_NH11_2.preview.srt", encoding="utf-8").read()
    numbers = [ln for ln in srt.splitlines() if ln.isdigit()]
    check("SRT の番号が 1 から連番", numbers == ["1", "2", "3", "4", "5"], numbers)
    check("SRT の時刻が HH:MM:SS,mmm 形式", "00:00:00,000 --> 00:00:02,500" in srt, srt)

    rc, out = run_main(mod, ["240801_NH11_2.MP3", "--plain"])
    check("本番実行が成功する", rc == 0, out)
    check("本番は入力名の txt を作る", os.path.exists("240801_NH11_2.txt"))
    full = open("240801_NH11_2.txt", encoding="utf-8").read()
    # 200 セグメント中 i%7==3 の 29 件が空 → 171 行残る
    expected = 200 - len([i for i in range(200) if i % 7 == 3])
    check(
        "空セグメントを除外している",
        len(full.strip().splitlines()) == expected,
        f"{len(full.strip().splitlines())} != {expected}",
    )
    check("実時間比を表示する", "実時間比" in out, out)


def test_transcribe_options():
    print("\n[オプション] transcribe() への受け渡し")
    _, passed = install_fakes()
    mod = load()

    run_main(mod, ["240801_NH11_2.MP3", "--preview", "2"])
    check("既定では initial_prompt を渡さない", passed.get("initial_prompt") is None, passed)
    check("既定では前文脈を使う", passed.get("condition_on_previous_text") is True, passed)
    check("既定では VAD が有効", passed.get("vad_filter") is True, passed)

    _, passed = install_fakes()
    mod = load()
    run_main(
        mod,
        [
            "240801_NH11_2.MP3",
            "--preview",
            "2",
            "--initial-prompt",
            "Minneapolis Center",
            "--no-condition",
            "--no-vad",
            "--beam-size",
            "10",
        ],
    )
    check("initial_prompt が渡る", passed.get("initial_prompt") == "Minneapolis Center", passed)
    check("--no-condition が効く", passed.get("condition_on_previous_text") is False, passed)
    check("--no-vad が効く", passed.get("vad_filter") is False, passed)
    check("--beam-size が渡る", passed.get("beam_size") == 10, passed)


def test_prompt_sources():
    print("\n[プロンプト] 指定方法の優先順")
    _, passed = install_fakes()
    mod = load()

    # フォルダに atc_prompt.txt があれば自動で使う
    with open("atc_prompt.txt", "w", encoding="utf-8") as f:
        f.write("# 管制機関\nMinneapolis Center\nAberdeen  # 空港\n\nDenver\n")

    _, out = run_main(mod, ["240801_NH11_2.MP3", "--preview", "1"])
    check(
        "atc_prompt.txt を自動で読む",
        passed.get("initial_prompt") == "Minneapolis Center Aberdeen Denver",
        passed.get("initial_prompt"),
    )
    check("コメントと空行を落とす", "#" not in (passed.get("initial_prompt") or ""), passed)
    check("読んだことを表示する", "atc_prompt.txt" in out, out[:200])

    # --initial-prompt が最優先
    _, passed = install_fakes()
    mod = load()
    run_main(mod, ["240801_NH11_2.MP3", "--preview", "1", "--initial-prompt", "Chicago Center"])
    check("--initial-prompt が優先される", passed.get("initial_prompt") == "Chicago Center", passed)

    # --prompt-file で別ファイルを指定
    with open("other.txt", "w", encoding="utf-8") as f:
        f.write("Kansas City Center\n")
    _, passed = install_fakes()
    mod = load()
    run_main(mod, ["240801_NH11_2.MP3", "--preview", "1", "--prompt-file", "other.txt"])
    check("--prompt-file が使える", passed.get("initial_prompt") == "Kansas City Center", passed)

    # 無いファイルを指定したらエラー
    mod = load()
    rc, _ = run_main(mod, ["240801_NH11_2.MP3", "--prompt-file", "no_such.txt"])
    check("無いプロンプトファイルは 1 を返す", rc == 1)

    os.remove("atc_prompt.txt")
    _, passed = install_fakes()
    mod = load()
    run_main(mod, ["240801_NH11_2.MP3", "--preview", "1"])
    check("ファイルが無ければ渡さない", passed.get("initial_prompt") is None, passed)


def test_digits():
    print("\n[数字変換] 読み上げ数字の数値化")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "atc_numbers_under_test", os.path.join(HERE, "atc_numbers.py")
    )
    an = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(an)

    cases = [
        ("one three five point zero two five", "135.025"),
        ("turn left heading three zero zero", "turn left heading 300"),
        ("flight level three five zero", "flight level 350"),
        ("climb and maintain six thousand", "climb and maintain 6000"),
        ("squawk four five three seven", "squawk 4537"),
        ("altimeter is three zero zero zero", "altimeter is 3000"),
        ("delta eight seventy six", "delta 876"),
        ("american twenty five ninety four", "american 2594"),
        ("maintain two hundred eighty knots", "maintain 280 knots"),
        ("descend and maintain one one thousand", "descend and maintain 11000"),
        ("one contact denver one three five point zero two five fifteen sixty five",
         "1 contact denver 135.025 1565"),
        ("for the delta holding point one one time", "for the delta holding point 11 time"),
        ("radar contact munich golf contact you sir", "radar contact munich golf contact you sir"),
        ("All right, mania two three two zero", "All right, mania 2320"),
    ]
    for src, want in cases:
        got = an.convert_text(src)
        check(f"変換: {src[:44]}", got == want, f"-> {got}")

    print("\n[数字変換] transcribe.py への組み込み")
    install_fakes()
    mod = load()
    run_main(mod, ["240801_NH11_2.MP3", "--preview", "2", "--digits"])
    body = open("240801_NH11_2.preview.txt", encoding="utf-8").read()
    check("--digits が出力に効く", "135.025" in body, body[:120])
    check("--digits なしの語が残っていない", "point zero two five" not in body, body[:120])

    install_fakes()
    mod = load()
    run_main(mod, ["240801_NH11_2.MP3", "--preview", "2"])
    body = open("240801_NH11_2.preview.txt", encoding="utf-8").read()
    check("既定では変換しない", "point zero two five" in body, body[:120])


def test_digits_cli():
    print("\n[数字変換] コマンドラインと上書き")
    script = os.path.join(HERE, "atc_numbers.py")

    with open("conv_a.txt", "w", encoding="utf-8") as f:
        f.write("contact denver one three five point zero two five\n")
    with open("conv_a.srt", "w", encoding="utf-8") as f:
        f.write("1\n00:00:13,300 --> 00:00:18,500\naltimeter is three zero zero zero\n")
    with open("conv_a.MP3", "wb") as f:
        f.write(b"\0" * 64)

    def run(argv):
        return subprocess.run(
            [sys.executable, script] + argv, capture_output=True, text=True
        )

    # 既定は別名で保存し、元に触れない
    proc = run(["conv_a.txt"])
    check("既定は成功する", proc.returncode == 0, proc.stderr)
    check("別名で出力する", os.path.exists("conv_a.digits.txt"))
    check(
        "元のファイルは変わらない",
        "one three five" in open("conv_a.txt", encoding="utf-8").read(),
    )

    # -i でまとめて上書き、音声は飛ばす
    proc = run(["-i", "conv_a.txt", "conv_a.srt", "conv_a.MP3"])
    check("-i が成功する", proc.returncode == 0, proc.stderr)
    check("音声を飛ばしたと伝える", "飛ばしました" in proc.stdout, proc.stdout)
    check("txt を上書きした", "135.025" in open("conv_a.txt", encoding="utf-8").read())
    check("srt を上書きした", "3000" in open("conv_a.srt", encoding="utf-8").read())
    srt = open("conv_a.srt", encoding="utf-8").read()
    check("srt の時刻を壊さない", "00:00:13,300 --> 00:00:18,500" in srt, srt)
    check("srt の番号を壊さない", srt.startswith("1\n"), srt[:20])
    check("音声は書き換えない", os.path.getsize("conv_a.MP3") == 64)

    # 二度流しても変わらない
    before = open("conv_a.txt", encoding="utf-8").read()
    run(["-i", "conv_a.txt"])
    check("二度目で結果が変わらない", open("conv_a.txt", encoding="utf-8").read() == before)

    # 誤用を弾く
    proc = run(["conv_a.txt", "-o", "conv_a.txt"])
    check("入力と同じ -o は拒否する", proc.returncode == 1, proc.stderr)
    proc = run(["-i", "-o", "x.txt", "conv_a.txt"])
    check("-i と -o の併用を拒否する", proc.returncode == 1, proc.stderr)
    proc = run(["no_such_file.txt"])
    check("無いファイルは 1 を返す", proc.returncode == 1, proc.stderr)


def test_windows_dll():
    print("\n[Windows] CUDA DLL の探索と登録")
    mod = load()
    check("Windows 以外では何もしない", mod.add_nvidia_dll_dirs() == [])

    root = os.path.abspath("fake_site")
    layout = {
        os.path.join("nvidia", "cublas", "bin"): ["cublas64_12.dll"],
        os.path.join("nvidia", "cudnn", "bin", "12"): ["cudnn_ops64_9.dll"],
        os.path.join("nvidia", "cublas", "include"): ["cublas.h"],
    }
    for rel, names in layout.items():
        d = os.path.join(root, rel)
        os.makedirs(d, exist_ok=True)
        for n in names:
            open(os.path.join(d, n), "w").close()

    registered = []
    mod.sys.platform = "win32"
    mod.os.add_dll_directory = registered.append
    mod.site.getsitepackages = lambda: [root]
    mod.site.getusersitepackages = lambda: root
    mod._site_dirs = lambda: [root]
    os.environ["PATH"] = "C_WINDOWS_SYSTEM32"

    dirs = mod.add_nvidia_dll_dirs()
    check("dll のあるフォルダだけ拾う", len(dirs) == 2, dirs)
    check("include を拾わない", not any("include" in d for d in dirs), dirs)
    check("入れ子のフォルダも辿る", any(d.endswith(os.path.join("bin", "12")) for d in dirs), dirs)
    check("add_dll_directory に登録する", len(registered) == 2, registered)
    check("PATH の先頭に入れる", os.environ["PATH"].startswith(dirs[0]), os.environ["PATH"])
    check("既存の PATH を残す", os.environ["PATH"].endswith("C_WINDOWS_SYSTEM32"))

    before = os.environ["PATH"]
    mod.add_nvidia_dll_dirs()
    check("再実行で PATH が伸びない", os.environ["PATH"] == before)


def main():
    workdir = tempfile.mkdtemp(prefix="atc-selftest-")
    origin = os.getcwd()
    os.chdir(workdir)
    open("240801_NH11_2.MP3", "wb").write(b"\0" * 1024)
    try:
        test_static()
        test_cli_without_deps()
        test_missing_file()
        test_compute_type_negotiation()
        test_outputs()
        test_transcribe_options()
        test_prompt_sources()
        test_digits()
        test_digits_cli()
        test_windows_dll()
    finally:
        os.chdir(origin)
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if failures:
        print(f"失敗 {len(failures)} 件: {', '.join(failures)}")
        return 1
    print("すべて通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
