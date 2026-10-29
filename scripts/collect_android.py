#!/usr/bin/env python3
"""安卓 / 鸿蒙（AOSP 底座）只读采集。

    python3 scripts/collect_android.py <输出目录> [设备序列号]

严格只读，只用这几类查询：getprop / pm list / cmd package query-* /
dumpsys / settings get / cat /proc/net。
脚本里没有任何 uninstall、disable、appops set、settings put、force-stop。

从 bash 搬到 Python 是为了 Windows：原来 `gtimeout`、`${OK[*]}`、
进程替换这些只在 bash 里有，Windows 用户一条命令都跑不起来。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _console  # noqa: E402

from collect_common import (  # noqa: E402
    Collector, _run, as_text, die, find_tool, tool_version, write_manifest,
)


def pick_serial(adb):
    """取第一台已授权设备。返回 (serial, 全部设备列表)。"""
    code, out, _ = _run([adb, "devices"], timeout=20)
    text = as_text(out)
    rows = [ln.split() for ln in text.splitlines()[1:] if ln.strip()]
    good = [r[0] for r in rows if len(r) >= 2 and r[1] == "device"]
    return (good[0] if good else ""), text


# 数据源清单。名字是 raw/ 下的文件名，顺序对报告里的排查有影响，别随便调。
SOURCES = [
    # ---------- 设备与系统 ----------
    ("prop_brand", ["getprop", "ro.product.brand"]),
    ("prop_model", ["getprop", "ro.product.model"]),
    ("prop_manufacturer", ["getprop", "ro.product.manufacturer"]),
    ("prop_release", ["getprop", "ro.build.version.release"]),
    ("prop_sdk", ["getprop", "ro.build.version.sdk"]),
    ("prop_security_patch", ["getprop", "ro.build.version.security_patch"]),
    ("prop_fingerprint", ["getprop", "ro.build.fingerprint"]),
    ("prop_serial", ["getprop", "ro.serialno"]),
    ("users", ["pm", "list", "users"]),

    # ---------- 应用清单 ----------
    ("packages_all", ["pm", "list", "packages", "-f", "-U", "--user", "0"]),
    ("packages_third", ["pm", "list", "packages", "-3"]),
    ("packages_system", ["pm", "list", "packages", "-s"]),
    ("packages_disabled", ["pm", "list", "packages", "-d"]),
    ("launcher_entries", ["cmd", "package", "query-activities", "--brief",
                          "-a", "android.intent.action.MAIN",
                          "-c", "android.intent.category.LAUNCHER"]),
    ("boot_receivers", ["cmd", "package", "query-receivers", "--brief",
                        "-a", "android.intent.action.BOOT_COMPLETED"]),
    ("default_home", ["cmd", "package", "resolve-activity", "--brief",
                      "-a", "android.intent.action.MAIN",
                      "-c", "android.intent.category.HOME"]),
    ("default_input", ["settings", "get", "secure", "default_input_method"]),
    ("admins_apps", ["cmd", "package", "query-receivers", "--brief",
                     "-a", "android.app.action.DEVICE_ADMIN_ENABLED"]),

    # ---------- 包详情（最重的一项，来源/安装时间/权限都在这儿）----------
    ("package_dump", ["dumpsys", "package"]),

    # ---------- 高危权限开关 ----------
    ("device_policy", ["dumpsys", "device_policy"]),
    ("accessibility", ["settings", "get", "secure", "enabled_accessibility_services"]),
    ("notif_listeners", ["settings", "get", "secure", "enabled_notification_listeners"]),
    ("appops_dump", ["dumpsys", "appops"]),
    ("deviceidle", ["dumpsys", "deviceidle", "whitelist"]),
    ("power_whitelist", ["settings", "get", "global", "low_power_whitelist"]),

    # ---------- 网络外联 ----------
    ("net_tcp", ["cat", "/proc/net/tcp"]),
    ("net_tcp6", ["cat", "/proc/net/tcp6"]),
    ("net_udp", ["cat", "/proc/net/udp"]),
    ("net_udp6", ["cat", "/proc/net/udp6"]),
    ("proxy", ["settings", "get", "global", "http_proxy"]),
]

def collect(out_dir, serial=""):
    adb = find_tool("adb")
    if not adb:
        die("ERROR: 没找到 adb。\n"
            "  macOS:  brew install android-platform-tools\n"
            "  Windows: 下载 platform-tools 解压，把目录加进 PATH\n"
            "  或直接装 Android Studio，它自带一份", 2)

    _run([adb, "start-server"], timeout=30)

    detected, listing = pick_serial(adb)
    if not detected:
        die("ERROR: 没有已授权的设备。\n"
            "  1. 手机上打开「开发者选项」→「USB 调试」\n"
            "  2. 插线后手机会弹窗，点「允许」\n"
            "  3. 还是不行就换根线，或换 USB 口试试\n\n"
            f"当前 adb devices 输出：\n{listing}", 3)

    serial = serial or detected
    prefix = ["-s", serial]

    coll = Collector(out_dir, adb, prefix=prefix, serial=serial)
    total = len(SOURCES)
    for i, (name, args) in enumerate(SOURCES, 1):
        # 长任务给个进度，否则 dumpsys package 那几秒会让人以为卡死了
        print(f"[{i:2d}/{total}] {name}", flush=True)
        coll.grab(name, ["shell"] + args)

    write_manifest(
        out_dir, platform="android", serial=serial,
        tool=tool_version(adb, "version"),
        ok=coll.ok, failed=coll.failed,
    )
    return 0 if coll.ok else 1


def main():
    ap = argparse.ArgumentParser(description="安卓 / 鸿蒙只读采集")
    ap.add_argument("out_dir", nargs="?", default="phone-audit")
    ap.add_argument("serial", nargs="?", default="")
    a = ap.parse_args()
    return collect(a.out_dir, a.serial)


if __name__ == "__main__":
    _console.setup()
    sys.exit(main())
