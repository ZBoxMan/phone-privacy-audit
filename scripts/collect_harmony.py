#!/usr/bin/env python3
"""鸿蒙只读采集。

HarmonyOS 分两种，处理方式不一样：

  1) HarmonyOS 2/3/4 —— 底座是 AOSP，adb 完全可用，直接走安卓那套
  2) HarmonyOS NEXT（纯血鸿蒙）—— 不再兼容安卓，只能用 hdc，
     能读到的信息少很多，报告会以手工核对为主

只读：只用 param get / bm dump / aa dump 这类查询命令。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collect_common import (  # noqa: E402
    Collector, _run, as_text, die, find_tool, tool_version, write_manifest,
)

HINT_NO_HDC = """ERROR: 没有可用的设备连接方式。

HarmonyOS NEXT 需要 hdc，它随 DevEco Studio 一起装：
  https://developer.huawei.com/consumer/cn/deveco-studio/

装好后把 hdc 所在目录加进 PATH，通常在：
  macOS   /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/
  Windows C:\\Program Files\\Huawei\\DevEco Studio\\sdk\\default\\openharmony\\toolchains\\

手机侧：设置 → 系统 → 开发者选项 → USB 调试。
"""

# 纯血鸿蒙上 `bm dump` 单个包开销很大，只拉清单，不逐个拉详情
NEXT_SOURCES = [
    ("prop_brand", ["param", "get", "const.product.brand"]),
    ("prop_model", ["param", "get", "const.product.model"]),
    ("prop_release", ["param", "get", "const.product.software.version"]),
    ("prop_sdk", ["param", "get", "const.ohos.apiversion"]),
    ("prop_fingerprint", ["param", "get", "const.product.name"]),
    ("bundles", ["bm", "dump", "-a"]),
    ("running", ["aa", "dump", "-a"]),
]


def aosp_available():
    """底座是 AOSP 的鸿蒙，adb 就能用。"""
    adb = find_tool("adb")
    if not adb:
        return False
    code, out, _ = _run([adb, "devices"], timeout=20)
    text = as_text(out)
    return any(
        len(parts) >= 2 and parts[1] == "device"
        for parts in (ln.split() for ln in text.splitlines()[1:] if ln.strip())
    )


def collect(out_dir, serial=""):
    # ---------- 路线一：AOSP 底座 ----------
    if aosp_available():
        print("检测到 HarmonyOS（AOSP 底座），按安卓方式采集…")
        from collect_android import collect as collect_android
        # 安卓那边已经写过 manifest，这里只补一个平台标记
        code = collect_android(out_dir, serial)
        _mark_layer(out_dir, "aosp")
        print("提示：这类机型的检查能力与安卓一致。")
        return code

    # ---------- 路线二：HarmonyOS NEXT ----------
    hdc = find_tool("hdc")
    if not hdc:
        die(HINT_NO_HDC, 3)

    code, out, _ = _run([hdc, "list", "targets"], timeout=20)
    targets = [ln.strip() for ln in as_text(out).splitlines()
               if ln.strip() and not ln.startswith("[")]
    if not targets:
        die("ERROR: hdc 没检测到设备。检查数据线和「USB 调试」开关。\n"
            f"当前 hdc list targets 输出：\n{as_text(out)}", 3)

    serial = serial or targets[0]
    coll = Collector(out_dir, hdc, serial=serial)
    for i, (name, args) in enumerate(NEXT_SOURCES, 1):
        print(f"[{i}/{len(NEXT_SOURCES)}] {name}", flush=True)
        coll.grab(name, ["shell"] + args)

    write_manifest(
        out_dir, platform="harmony", harmony_layer="next", serial=serial,
        tool=tool_version(hdc, "-v"),
        ok=coll.ok, failed=coll.failed,
    )
    print("提示：纯血鸿蒙能读到的信息有限，报告会以手工核对为主。")
    return 0 if coll.ok else 1


def _mark_layer(out_dir, layer):
    """安卓采集写的是 platform=android，鸿蒙 AOSP 底座要补一个 harmony_layer。"""
    import json

    p = Path(out_dir) / "manifest.json"
    if not p.exists():
        return
    m = json.loads(p.read_text(encoding="utf-8"))
    m["platform"] = "harmony"
    m["harmony_layer"] = layer
    p.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="鸿蒙只读采集")
    ap.add_argument("out_dir", nargs="?", default="phone-audit")
    ap.add_argument("serial", nargs="?", default="")
    a = ap.parse_args()
    return collect(a.out_dir, a.serial)


if __name__ == "__main__":
    sys.exit(main())
