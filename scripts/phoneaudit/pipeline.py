"""主流程：读采集结果 → 按平台分析 → 结论 → 写 audit.json。"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import MANUAL_ITEMS
from .android import analyze_android
from .harmony import analyze_harmony_next
from .ios import analyze_ios
from .verdict import make_verdict
from .vocab import KNOWN_APPS, LEVEL_LABEL


def load_manual(out_dir: Path) -> list:
    p = out_dir / "manual_checks.json"
    if not p.exists():
        return []
    try:
        checks = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    # 文案统一从 manual-items.json 取，避免两处各写一份、改了一处忘了另一处
    try:
        items = {it["id"]: it for it in json.loads(MANUAL_ITEMS.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError, KeyError):
        items = {}

    for c in checks:
        src = items.get(c.get("id"))
        if not src:
            continue
        for key in ("title", "desc", "question", "ok", "how", "tier", "shot"):
            if src.get(key):
                c[key] = src[key]
    return checks


def load_manifest(out_dir: Path) -> dict:
    """安卓/鸿蒙写 manifest.json，iPhone 写 ios.json；哪个在就用哪个。"""
    for name in ("manifest.json", "ios.json"):
        p = out_dir / name
        if not p.exists():
            continue
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return {}


def build_name_map(data: dict, manifest: dict, platform: str) -> dict:
    """报告里所有提到包名的地方共用一套叫法：别一处说「一个清理软件」、另一处甩包名。"""
    seen = {f["pkg"] for f in data["findings"]}
    for c in data.get("control_points", []):
        seen.update(c.get("items", []))
    seen.update(p["pkg"] for p in data.get("permissions", []))

    name_map = {p: KNOWN_APPS[p] for p in seen if p in KNOWN_APPS}
    for f in data["findings"]:
        if f.get("name") and f["name"] != f["pkg"]:
            name_map.setdefault(f["pkg"], f["name"])

    # iOS 的显示名来自设备上的 Info.plist，比内置表准得多，直接拿过来用
    if platform == "ios":
        amap = {a.get("bundle_id"): a.get("name")
                for a in manifest.get("apps", []) if a.get("name")}
        for p in seen:
            if p not in name_map and amap.get(p):
                name_map[p] = amap[p]
    return name_map


def build_audit(out_dir: Path) -> dict:
    """读采集目录，返回 audit.json 的内容；没有采集结果时抛 FileNotFoundError。"""
    manifest = load_manifest(out_dir)
    if not manifest:
        raise FileNotFoundError(f"{out_dir} 下没有采集结果，请先跑采集脚本")

    platform = manifest.get("platform", "android")
    manual = load_manual(out_dir)

    if platform == "ios":
        data = analyze_ios(out_dir, manifest)
    elif platform == "harmony" and manifest.get("harmony_layer") == "next":
        data = analyze_harmony_next(out_dir, manifest)
    else:
        data = analyze_android(out_dir, manifest)

    verdict = make_verdict(data["findings"], manual, platform, data.get("summary"),
                           data.get("completeness"))

    return {
        "platform": platform,
        "name_map": build_name_map(data, manifest, platform),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "verdict": verdict,
        "manual_checks": manual,
        "level_labels": LEVEL_LABEL,
        **data,
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out_dir = Path(argv[0] if argv else ".").resolve()

    try:
        audit = build_audit(out_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    (out_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    s = audit["summary"]
    print(f"平台: {audit['platform']} | 应用 {s['total_apps']} 个")
    print(f"现在就看 {s['high']} | 有空看 {s['check']} | 知道就行 {s['watch']}")
    print(f"结论: {audit['verdict']['headline']}")
    return 0
