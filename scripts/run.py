#!/usr/bin/env python3
"""手机体检 —— 一条命令跑完。

    python3 scripts/run.py ./phone-audit            采集 + 分析 + 出报告
    python3 scripts/run.py ./phone-audit --rebuild  只重新分析 + 出报告（改完核对项用）

自动认手机：iPhone 走 USB，安卓 / 鸿蒙走 adb / hdc。
全程只读，不装、不卸、不改任何设置。

为什么是 Python 不是 bash：Windows 上没有 bash，`gtimeout`、`${X[*]}`、
进程替换这些全都不存在。换成 Python 之后三个平台是同一份代码，
macOS / Linux / Windows 的命令一字不差。
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import _console
from collect_common import as_text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

LINE = "────────────────────────────────────────"


def venv_python():
    """仓库自带的 venv 优先 —— iPhone 采集要里面的 pymobiledevice3。"""
    for rel in ("bin/python", "bin/python3", "Scripts/python.exe"):
        p = ROOT / ".venv" / rel
        if p.exists():
            return str(p)
    return None


def pick_python():
    return venv_python() or sys.executable


def run(cmd, timeout=None):
    """跑子脚本，输出直接透到终端。"""
    try:
        return subprocess.run(cmd, timeout=timeout).returncode
    except FileNotFoundError:
        print(f"命令跑不起来：{cmd[0]}", file=sys.stderr)
        return 127


def quiet(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout)
        return p.returncode, p.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, b""


def ios_connected(py):
    """能看到设备就返回 True。没装 pymobiledevice3 时这条会安静地失败。"""
    code, out = quiet([py, "-m", "pymobiledevice3", "usbmux", "list"], timeout=40)
    return code == 0 and b'"Identifier"' in out


def android_connected():
    adb = shutil.which("adb")
    if not adb:
        return False
    code, out = quiet([adb, "devices"], timeout=20)
    text = as_text(out)
    return any(
        len(p) >= 2 and p[1] == "device"
        for p in (ln.split() for ln in text.splitlines()[1:] if ln.strip())
    )


def harmony_connected():
    hdc = shutil.which("hdc")
    if not hdc:
        return False
    code, out = quiet([hdc, "list", "targets"], timeout=20)
    text = as_text(out)
    return any(ln.strip() and not ln.startswith("[") for ln in text.splitlines())


def detect(py):
    if ios_connected(py):
        return "ios"
    if android_connected():
        return "android"
    if harmony_connected():
        return "harmony"
    return "none"


def no_device_help():
    print("没找到手机。挑一条对得上的：")
    print()
    print("  iPhone  数据线连上 → 手机解锁 → 屏幕弹「信任此电脑」点信任")
    print("  安卓    设置里打开「开发者选项」→「USB 调试」→ 插线 → 手机上点允许")
    print("  鸿蒙    同上，纯血鸿蒙要装 DevEco Studio 里的 hdc")
    print()
    print("Windows 上还多两步：")
    print("  · iPhone 要装 iTunes（或者只装 Apple 的「Apple Mobile Device Support」驱动）")
    print("  · adb 要从 platform-tools 解压出来，把那个目录加进 PATH")


def read_audit(out_dir):
    try:
        return json.loads((Path(out_dir) / "audit.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    # 子进程的输出直接写终端，本进程的 print 默认带缓冲。
    # 不关掉的话「认出来了：iPhone」会跑到采集结果后面去。
    _console.setup()
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(
        description="手机体检：只读采集 + 归因 + 出报告，全程不写设备")
    ap.add_argument("out_dir", nargs="?", default="./phone-audit")
    ap.add_argument("--rebuild", action="store_true",
                    help="跳过采集，只用已有结果重新分析出报告")
    a = ap.parse_args()

    out = Path(a.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    py = pick_python()

    if not a.rebuild:
        platform = detect(py)
        if platform == "none":
            no_device_help()
            return 3
        label = {"ios": "iPhone", "android": "安卓 / 鸿蒙", "harmony": "鸿蒙"}[platform]
        print(f"认出来了：{label}")
        print(LINE)

        if platform == "ios":
            if not venv_python():
                print("iPhone 采集要 pymobiledevice3，先把依赖装上：", file=sys.stderr)
                print("  python3 -m venv .venv", file=sys.stderr)
                print("  .venv/bin/pip install -r requirements.txt", file=sys.stderr)
                print("（Windows 是 .venv\\Scripts\\pip install -r requirements.txt）",
                      file=sys.stderr)
                return 2
            code = run([py, str(HERE / "collect_ios.py"), str(out)])
        elif platform == "android":
            code = run([py, str(HERE / "collect_android.py"), str(out)])
        else:
            code = run([py, str(HERE / "collect_harmony.py"), str(out)])
        if code != 0:
            return code

    print(LINE)
    if run([py, str(HERE / "analyze.py"), str(out)]) != 0:
        return 1
    if run([py, str(HERE / "build_report.py"), str(out)]) != 0:
        return 1
    print(LINE)

    # ---------- 下一步 ----------
    data = read_audit(out)
    print()
    if data.get("platform") == "ios":
        pending = [m for m in data.get("manual_checks", [])
                   if not m.get("answer") and m.get("tier") != "optional"]
        if pending:
            print(f"报告已经能看了，但还差最后一步：有 {len(pending)} 项在设置里，机器读不到。")
            print(f"接下来要做的：在手机上截这 {len(pending)} 张图，然后重新出一版完整报告。")
        else:
            print("全都核完了。报告是完整的。")
    else:
        print("报告好了。")

    report = out / "report.html"
    print()
    print(f"报告：{report}")
    if sys.platform.startswith("win"):
        print("（双击就能用浏览器打开）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
