"""HarmonyOS NEXT（纯血鸿蒙）：hdc 能读到的只有包名清单，报告以手工核对为主。"""

import re
from pathlib import Path

from .android import os_label, read_raw
from .vocab import SRC_LABEL

# 华为自己的包名前缀；其余按第三方算
HARMONY_SYSTEM_PREFIXES = ("com.huawei.", "com.ohos.", "ohos.", "com.hihonor.")


def parse_bundle_list(text: str) -> list:
    """`bm dump -a` 的输出：`ID: 100:` 一行，下面每行一个包名。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r"[A-Za-z][\w]*(\.[\w]+)+", s) and s not in out:
            out.append(s)
    return out


def analyze_harmony_next(out_dir: Path, manifest: dict) -> dict:
    bundles = parse_bundle_list(read_raw(out_dir, "bundles"))
    third_party = [b for b in bundles if not b.startswith(HARMONY_SYSTEM_PREFIXES)]

    failed = manifest.get("failed", [])
    failed_nice = [f"{SRC_LABEL.get(item.split(':')[0], item.split(':')[0])}"
                   f"（{'读不到内容' if item.endswith(':empty') else '命令没跑通'}）"
                   for item in failed]

    return {
        "device": {
            "brand": read_raw(out_dir, "prop_brand").strip(),
            "manufacturer": "HUAWEI",
            "model": read_raw(out_dir, "prop_model").strip(),
            "os": os_label(manifest, read_raw(out_dir, "prop_release").strip()),
            "security_patch": "",
            "scanned_at": manifest.get("collected_at", ""),
        },
        "completeness": {
            "ok": len(manifest.get("ok", [])), "failed": len(failed),
            "failed_items": failed, "failed_nice": failed_nice,
            "note": "纯血鸿蒙不开放权限和安装来源的查询，这次只读到了装了哪些软件。"
                    "谁能看屏幕、谁能读通知，得你自己在设置里对一遍。",
        },
        "summary": {
            "total_apps": len(bundles), "third_party": len(third_party),
            "side_loaded": 0, "high": 0, "check": 0, "watch": 0,
            "limited": True,
        },
        "control_points": [
            {"key": "installed", "title": "这台手机上装的第三方软件",
             "desc": "纯血鸿蒙只给看清单。谁能看屏幕、谁能读通知，得你在设置里对",
             "items": third_party},
        ],
        "permissions": [],
        "outbound": [],
        "preinstalled": [],
        "findings": [],
    }
