#!/usr/bin/env python3
"""采集脚本收尾时写 manifest.json。

    python3 write_manifest.py <输出目录> --platform android --serial X \
        --tool "adb 1.0.41" --ok "a b c" --failed "d:empty"

交给 Python 写是因为 macOS 自带的 bash 3.2 下，`set -u` 加空数组展开会直接报错，
手拼 JSON 又要自己管转义。
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--platform", default="android")
    ap.add_argument("--harmony-layer", default="")
    ap.add_argument("--serial", default="")
    ap.add_argument("--tool", default="")
    ap.add_argument("--ok", default="")
    ap.add_argument("--failed", default="")
    a = ap.parse_args()

    manifest = {
        "platform": a.platform,
        "serial": a.serial,
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool_version": a.tool,
        "ok": a.ok.split(),
        "failed": a.failed.split(),
    }
    if a.harmony_layer:
        manifest["harmony_layer"] = a.harmony_layer

    path = Path(a.out_dir) / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"采集完成: {a.out_dir}")
    print(f"成功 {len(manifest['ok'])} 项 / 失败 {len(manifest['failed'])} 项")
    if manifest["failed"]:
        print(f"失败项: {' '.join(manifest['failed'])}")


if __name__ == "__main__":
    main()
