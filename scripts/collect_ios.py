#!/usr/bin/env python3
"""iPhone 只读采集

必须用仓库里的 venv 运行（系统 python 没有 pymobiledevice3）：
    .venv/bin/python scripts/collect_ios.py <输出目录>

只读：不安装、不卸载、不改任何设置。

iOS 能自动读到的（都来自安装清单里的 Info.plist 与签名信息）：
  · 应用清单、版本、是不是系统自带
  · 安装来源（App Store / TestFlight / 开发者证书 / 来源不明）
  · 每个软件「声明要用的隐私权限」——注意是声明，不是你真的给了
  · 后台运行能力（后台定位、后台放音、后台刷新等）
  · 能探测量你装了哪些别的 App（LSApplicationQueriesSchemes）
  · 是否持有 VPN / 网络扩展权限
读不到的（必须人工核对）：你到底授没授权、描述文件、屏幕使用时间、通知设置。
判定规则（来源、权限、后台）在 phoneaudit/ios.py，分析端和采集端共用一份。
"""

import asyncio
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from phoneaudit import MANUAL_ITEMS
from phoneaudit.ios import classify, read_background, read_perms
from phoneaudit.vocab import KNOWN_APPS, MODEL_NAMES, PRIVATE_PERMS

VPN_ENTITLEMENTS = ("com.apple.developer.networking.vpn.api",
                    "com.apple.developer.networking.networkextension")


def app_record(bid: str, meta: dict) -> dict:
    source, suspicious = classify(meta)
    perms, perm_why = read_perms(meta)
    ent = meta.get("Entitlements") or {}
    queries = meta.get("LSApplicationQueriesSchemes") or []
    name = (meta.get("CFBundleDisplayName") or meta.get("CFBundleName")
            or KNOWN_APPS.get(bid) or "")
    return {
        "bundle_id": bid,
        "name": str(name).strip().strip("‎‏"),
        "version": meta.get("CFBundleShortVersionString", ""),
        "app_type": meta.get("ApplicationType", ""),
        "source": source,
        "suspicious_signer": suspicious,
        "is_store": source == "App Store",
        "hidden": meta.get("ApplicationType") == "Hidden",
        "is_clip": bool(meta.get("IsAppClip")),
        "perms": perms,
        "perm_why": perm_why,
        "private_perms": [p for p in perms if p in PRIVATE_PERMS],
        "background": read_background(meta),
        "queries_count": len(queries) if isinstance(queries, list) else 0,
        "has_vpn": any(k in ent for k in VPN_ENTITLEMENTS),
        "team": ent.get("com.apple.developer.team-identifier", ""),
    }


def print_summary(out_dir: Path, device: dict, apps: list):
    user_apps = [a for a in apps if a["app_type"] == "User"]
    odd = [a for a in user_apps if a["suspicious_signer"]]
    beta = [a for a in user_apps if a["source"] == "TestFlight 测试版"]
    vpn = [a for a in user_apps if a["has_vpn"]]

    print(f"采集完成: {out_dir / 'ios.json'}")
    print(f"{device['model']} · {device['os']} · 已装 {len(apps)} 个（第三方 {len(user_apps)} 个）")
    print(f"其中 {len(user_apps) - len(odd) - len(beta)} 个来自 App Store"
          + (f"，{len(beta)} 个是测试版" if beta else ""))
    if odd:
        print(f"  ⚠ {len(odd)} 个不是从 App Store 装的，要人工确认：")
        for a in odd:
            print(f"      {a['name'] or a['bundle_id']}  ({a['source']})")
    else:
        print("  ✓ 没有发现 App Store 之外的安装")
    if vpn:
        print(f"  · {len(vpn)} 个软件有 VPN 权限（能接管全部网络流量）："
              + "、".join(a["name"] or a["bundle_id"] for a in vpn))


async def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./iphone-audit").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.installation_proxy import InstallationProxyService
    except ImportError:
        print("ERROR: 缺少 pymobiledevice3。请用仓库里的 venv 运行：", file=sys.stderr)
        print("  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt", file=sys.stderr)
        print("  .venv/bin/python scripts/collect_ios.py <输出目录>", file=sys.stderr)
        return 2

    ok, failed = [], []

    try:
        lockdown = await create_using_usbmux(autopair=True)
        info = lockdown.all_values
        if inspect.isawaitable(info):
            info = await info
        if not info:
            raise RuntimeError("读不到设备信息")
        ok.append("设备信息")
    except Exception as e:
        msg = str(e).split("\n")[0][:120]
        print(f"ERROR: 连不上 iPhone —— {msg}", file=sys.stderr)
        print("请确认：数据线已连接、手机已解锁、屏幕上点了「信任」。", file=sys.stderr)
        return 3

    product = info.get("ProductType", "")
    device = {
        "brand": "Apple",
        "model": MODEL_NAMES.get(product, product or "iPhone"),
        "product_type": product,
        "os": "iOS " + info.get("ProductVersion", ""),
        "security_patch": "",
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device_name": info.get("DeviceName", "").strip(),
        "udid": info.get("UniqueDeviceID", ""),
    }

    raw_apps = {}
    try:
        async with InstallationProxyService(lockdown=lockdown) as svc:
            raw_apps = await svc.get_apps()
        ok.append("应用清单")
    except Exception as e:
        failed.append(f"应用清单:{(str(e).split(chr(10))[0])[:60]}")

    apps = [app_record(bid, meta) for bid, meta in raw_apps.items()]
    apps.sort(key=lambda a: (a["app_type"] != "User", a["bundle_id"]))

    payload = {
        "platform": "ios",
        "device": device,
        "apps": apps,
        "coverage": {
            "ok": len(ok),
            "failed": len(failed),
            "failed_nice": [f.replace(":", "（") + "）" if ":" in f else f for f in failed],
        },
    }
    (out_dir / "ios.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # 给人工核对阶段用的模板：只留 id 和空 answer，文案由 manual-items.json 提供
    template = json.loads(MANUAL_ITEMS.read_text(encoding="utf-8"))
    (out_dir / "manual_checks.json").write_text(
        json.dumps([{"id": it["id"], "answer": ""} for it in template],
                   ensure_ascii=False, indent=1), encoding="utf-8")

    print_summary(out_dir, device, apps)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
