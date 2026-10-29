#!/usr/bin/env python3
"""iPhone 只读采集

必须用 skill 目录下的 venv 运行：
    ~/.workbuddy/skills/phone-privacy-audit/.venv/bin/python collect_ios.py <输出目录>

只读：不安装、不卸载、不改任何设置。

iOS 能自动读到的（都来自安装清单里的 Info.plist 与签名信息）：
  · 应用清单、版本、是不是系统自带
  · 安装来源（App Store / TestFlight / 开发者证书 / 来源不明）
  · 每个软件「声明要用的隐私权限」——注意是声明，不是你真的给了
  · 后台运行能力（后台定位、后台放音、后台刷新等）
  · 能探测量你装了哪些别的 App（LSApplicationQueriesSchemes）
  · 是否持有 VPN / 网络扩展权限
读不到的（必须人工核对）：你到底授没授权、描述文件、屏幕使用时间、通知设置。
"""

import asyncio
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MODEL_NAMES = {
    "iPhone14,2": "iPhone 13 Pro", "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,4": "iPhone 13 mini", "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone SE (第 3 代)", "iPhone14,7": "iPhone 14",
    "iPhone14,8": "iPhone 14 Plus", "iPhone15,2": "iPhone 14 Pro",
    "iPhone15,3": "iPhone 14 Pro Max", "iPhone15,4": "iPhone 15",
    "iPhone15,5": "iPhone 15 Plus", "iPhone16,1": "iPhone 15 Pro",
    "iPhone16,2": "iPhone 15 Pro Max", "iPhone17,1": "iPhone 16 Pro",
    "iPhone17,2": "iPhone 16 Pro Max", "iPhone17,3": "iPhone 16",
    "iPhone17,4": "iPhone 16 Plus", "iPhone17,5": "iPhone 16e",
    "iPhone18,1": "iPhone 17 Pro", "iPhone18,2": "iPhone 17 Pro Max",
    "iPhone18,3": "iPhone 17", "iPhone18,4": "iPhone 17 Air",
    "iPhone12,1": "iPhone 11", "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max", "iPhone12,8": "iPhone SE (第 2 代)",
    "iPhone13,1": "iPhone 12 mini", "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro", "iPhone13,4": "iPhone 12 Pro Max",
}

# 隐私权限声明 → 大白话。键是 Info.plist 里的字段名。
PERM_MAP = {
    "NSCameraUsageDescription": "相机",
    "NSMicrophoneUsageDescription": "麦克风",
    "NSContactsUsageDescription": "通讯录",
    "NSLocationWhenInUseUsageDescription": "位置",
    "NSLocationAlwaysAndWhenInUseUsageDescription": "一直知道位置",
    "NSLocationAlwaysUsageDescription": "一直知道位置",
    "NSPhotoLibraryUsageDescription": "相册",
    "NSPhotoLibraryAddUsageDescription": "存照片",
    "NSAppleMusicUsageDescription": "音乐库",
    "NSBluetoothAlwaysUsageDescription": "蓝牙",
    "NSBluetoothPeripheralUsageDescription": "蓝牙",
    "NSHealthShareUsageDescription": "健康数据",
    "NSHealthUpdateUsageDescription": "改健康数据",
    "NSFaceIDUsageDescription": "面容 ID",
    "NSUserTrackingUsageDescription": "跨软件追踪你",
    "NSSpeechRecognitionUsageDescription": "语音识别",
    "NSCalendarsUsageDescription": "日历",
    "NSCalendarsFullAccessUsageDescription": "日历",
    "NSRemindersUsageDescription": "提醒事项",
    "NSRemindersFullAccessUsageDescription": "提醒事项",
    "NSMotionUsageDescription": "运动与健身",
    "NSLocalNetworkUsageDescription": "同 WiFi 下的其他设备",
    "NSNearbyInteractionUsageDescription": "附近的设备",
    "NSHomeKitUsageDescription": "家里的智能设备",
    "NSFocusStatusUsageDescription": "专注状态",
    "NSFamilyControlsUsageDescription": "家长控制",
    "NSVideoSubscriberAccountUsageDescription": "电视服务商账号",
    "NSGKFriendListUsageDescription": "游戏好友",
    "NSSystemAdministrationUsageDescription": "系统设置",
    "NSAppleEventsUsageDescription": "控制其他软件",
    "NSCriticalMessagingUsageDescription": "紧急消息",
}

# 后台运行能力 → 大白话
BG_MAP = {
    "audio": "后台放声音",
    "location": "后台知道位置",
    "voip": "后台接网络电话",
    "fetch": "后台自己刷新",
    "remote-notification": "收推送后台醒来",
    "processing": "后台干重活",
    "bluetooth-central": "后台连蓝牙设备",
    "bluetooth-peripheral": "自己当蓝牙设备",
    "external-accessory": "后台连外接设备",
    "network-authentication": "网络认证",
    "nearby-interaction": "附近感应",
    "push-to-talk": "对讲机",
}

# 声明了这些，才是"能打听到你私事"的权限
PRIVATE_PERMS = {
    "相机", "麦克风", "通讯录", "位置", "一直知道位置", "相册", "音乐库",
    "健康数据", "改健康数据", "跨软件追踪你", "语音识别", "日历", "提醒事项",
    "运动与健身", "同 WiFi 下的其他设备", "控制其他软件",
}

# 认识这些就够了，剩下的靠 Info.plist 里的显示名
KNOWN_BUNDLES = {
    "com.tencent.xin": "微信", "com.tencent.mqq": "QQ",
    "com.tencent.wework": "企业微信", "com.taobao.taobao4iphone": "淘宝",
    "com.alipay.iphoneclient": "支付宝", "com.jingdong.app.mall": "京东",
    "com.xunmeng.pinduoduo": "拼多多", "com.xingin.discover": "小红书",
    "com.ss.iphone.ugc.aweme": "抖音", "com.ss.iphone.ugc.aweme.lite": "抖音极速版",
    "com.sina.weibo": "微博", "com.zhihu.ios": "知乎",
    "com.autonavi.amap": "高德地图", "com.baidu.BaiduMap": "百度地图",
    "com.meituan.imeituan": "美团", "com.dianping.dpscope": "大众点评",
    "com.taobao.fleamarket": "闲鱼", "com.taobao.tmall": "天猫",
    "com.netease.cloudmusic": "网易云音乐", "com.tencent.QQMusic": "QQ音乐",
    "tv.danmaku.bilianime": "哔哩哔哩", "com.youku.YouKu": "优酷",
    "com.qiyi.iphone": "爱奇艺", "com.tencent.qqlive": "腾讯视频",
    "ph.telegra.Telegraph": "Telegram", "net.whatsapp.WhatsApp": "WhatsApp",
    "com.burbn.instagram": "Instagram", "com.atebits.Tweetie2": "X",
    "com.openai.chat": "ChatGPT", "com.bot.doubao": "豆包",
    "com.bytedance.flow": "豆包", "com.luffa.messenger": "Luffa",
    "com.liguangming.Shadowrocket": "Shadowrocket",
    "com.huania.earthquakewarning": "地震预警",
    "com.cmbchina.MPBBank": "招商银行",
    "com.eg.android.AlipayGphone": "支付宝",
}

# iPhone 上真正意味着「这软件不是走的苹果商店」
SIGNER_APPSTORE = "Apple iPhone OS Application Signing"


def classify(meta: dict) -> tuple:
    """返回 (来源说明, 是否该人工看一眼)。

    iOS 27 起安装清单里已经没有 ApplicationSINF 了，改看：
      · SignerIdentity —— 签名身份，TestFlight 版本会直接写出来
      · ITSDRMScheme   —— App Store 下载的包有 DRM 加密，其他渠道没有
    企业证书 / 侧载 / 自签的包，走的是 Apple 的开发者签名但没有商店 DRM，
    所以「有签名、没 DRM」就是非商店来源。
    """
    if meta.get("ApplicationType") == "System":
        return "系统自带", False

    signer = str(meta.get("SignerIdentity") or "")
    ent = meta.get("Entitlements") or {}

    if "testflight" in signer.lower() or ent.get("beta-reports-active"):
        return "TestFlight 测试版", False
    if meta.get("ITSDRMScheme") or meta.get("ApplicationSINF"):
        return "App Store", False
    if ent.get("get-task-allow"):
        return "开发者证书安装", True
    return "来源不明（不在 App Store）", True


def read_perms(meta: dict) -> tuple:
    """返回 (权限中文名列表, {中文名: 软件自己写的申请理由})。"""
    names, why = [], {}
    for key, label in PERM_MAP.items():
        desc = meta.get(key)
        if isinstance(desc, str) and desc.strip():
            if label not in names:
                names.append(label)
            why.setdefault(label, desc.strip())
    return names, why


def read_background(meta: dict) -> list:
    out = []
    for mode in (meta.get("UIBackgroundModes") or []):
        label = BG_MAP.get(mode, mode)
        if label not in out:
            out.append(label)
    return out


async def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./iphone-audit").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.installation_proxy import InstallationProxyService
    except ImportError:
        print("ERROR: 缺少 pymobiledevice3。请用 skill 目录下的 venv 运行：", file=sys.stderr)
        print("  ~/.workbuddy/skills/phone-privacy-audit/.venv/bin/python collect_ios.py", file=sys.stderr)
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

    apps = []
    for bid, meta in raw_apps.items():
        source, suspicious = classify(meta)
        perms, perm_why = read_perms(meta)
        ent = meta.get("Entitlements") or {}
        queries = meta.get("LSApplicationQueriesSchemes") or []
        name = (meta.get("CFBundleDisplayName") or meta.get("CFBundleName")
                or KNOWN_BUNDLES.get(bid) or "")

        apps.append({
            "bundle_id": bid,
            "name": str(name).strip().strip("\u200e\u200f"),
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
            "has_vpn": ("com.apple.developer.networking.vpn.api" in ent
                        or "com.apple.developer.networking.networkextension" in ent),
            "team": ent.get("com.apple.developer.team-identifier", ""),
        })
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

    # 给人工核对阶段用的模板
    template = json.loads(
        (Path(__file__).resolve().parent.parent / "references" / "manual-items.json")
        .read_text(encoding="utf-8"))
    for item in template:
        item["answer"] = ""
    (out_dir / "manual_checks.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=1), encoding="utf-8")

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
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
