"""iPhone：从安装清单（Info.plist + Entitlements）判来源、权限声明、后台能力，套规则，产出报告数据。

分寸：这里看到的是「它声明要用的权限」，不是「用户真的授权了」。
"""

from pathlib import Path

from .scoring import combine, ios_trust_factor, level_of
from .vocab import (
    BG_MAP, IOS_SYSTEM_PREFIX, KNOWN_APPS, PERM_MAP, PRIVATE_PERMS, STALKERWARE_HINTS,
    is_proxy_tool,
)


# ---------------------------------------------------------------- 采集端也用的判定

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


# ---------------------------------------------------------------- 规则


def build_ios_findings(apps: list) -> list:
    """iOS 能自动判的是：来源、权限声明宽度、后台能力、探测范围。

    注意分寸：这里看到的是 Info.plist 里「它声明要用的权限」，不是
    「用户真的授权了」。所以措辞不能写成「它在看你相册」，只能说
    「它要过这个权限」。
    """
    findings = []
    for app in apps:
        bid = app.get("bundle_id", "")
        if not bid or bid.startswith(IOS_SYSTEM_PREFIX):
            continue
        if app.get("app_type") != "User":
            continue

        name = app.get("name") or KNOWN_APPS.get(bid) or ""
        source = app.get("source") or ""
        is_store = bool(app.get("is_store"))
        private = app.get("private_perms") or []
        n_private = len(private)
        bg = app.get("background") or []
        signals = []

        def add(rule, score, title, why, how, note=""):
            signals.append({"rule": rule, "score": score, "title": title,
                            "why": why, "how": how, "note": note})

        if app.get("suspicious_signer") and "TestFlight" not in source:
            add("I_ENTERPRISE", 40, "它不是从 App Store 装的",
                "正常软件都从 App Store 下载。这种是绕开苹果审核塞进来的，"
                "苹果随时能让它失效。真正的坏东西在 iPhone 上只能走这条路。",
                "先想清楚是谁让你装的、怎么装的。如果是从网页点链接、扫码、"
                "或者连电脑装的，又说不清要它干嘛，就删掉。想留着，先把它的"
                "描述文件截图存下来。")

        hit = next((h for h in STALKERWARE_HINTS if h in bid.lower()), None)
        if hit:
            add("I_BLACKLIST", 38, "名字和曝光过的监控软件撞上了",
                f"它的名字里带着「{hit}」，这是媒体曝光过的商业监控软件的名字。"
                "只是个线索，不能当结论。",
                "先别删。把设置里它的权限页、描述文件页都截图存好，再交给能判断的人。"
                "删掉等于把证据一起清了。")

        if n_private >= 12:
            shown = "、".join(private[:6])
            add("I_PERM_FLOOD", 22, f"它想知道的私事有 {n_private} 样",
                f"它在自己的说明书里列了 {n_private} 样：{shown} 等。"
                "单看每一样都能编出理由，凑一起就不好说了。",
                "这类软件值得花两分钟收一遍权限：设置 → 隐私与安全性，"
                "一样一样点进去，把用不着的关掉。关掉不影响主要功能。")
        elif n_private >= 9:
            shown = "、".join(private[:5])
            add("I_PERM_WIDE", 14, f"它要了 {n_private} 样私事",
                f"包括{shown}这些。不算离谱，但比一般软件多。",
                "不想给的话，设置 → 隐私与安全性 里逐项关掉就行。")

        if "后台知道位置" in bg and "后台放声音" in bg:
            add("I_BG_TRACK", 20, "你退出去它还能跟着你",
                "它能在后台一直知道你在哪，同时还能在后台放声音。"
                "这两样都有，说明它可以长时间待在你退不掉的角落里。"
                "导航、音乐、打车这类软件确实需要，别的软件就不必了。",
                "设置 → 通用 → 后台 App 刷新，把它关掉。"
                "再在 设置 → 隐私与安全性 → 定位服务 里，把它的定位改成"
                "「使用期间」或者「永不」。")

        if "同 WiFi 下的其他设备" in (app.get("perms") or []):
            add("I_LOCAL_NET", 14, "它能看见同一个 WiFi 里的其他设备",
                "这个权限本来是给投屏、打印机、智能家居用的。拿到之后，"
                "它能扫出这个网里连着几台设备、分别是什么。",
                "设置 → 隐私与安全性 → 本地网络，把用不着的关掉。")

        q = app.get("queries_count") or 0
        if q >= 60:
            add("I_QUERY_MANY", 12, f"它在数你装了哪 {q} 种软件",
                f"它内部列了一份 {q} 种软件的名单，挨个去问「这台手机上有没有装它」。"
                "购物、社交软件这么做是为了能直接跳转，但也等于知道了你的软件清单。",
                "这个改不了，只能知道。介意的话，少给它开权限。")

        if "testflight" in source.lower():
            add("I_BETA", 6, "它是测试版，不在正式商店里",
                "TestFlight 是苹果给开发者试新版本用的。本身没毛病，"
                "但版本不稳，也可能哪天就过期打不开了。",
                "只想用正式版的话，去 App Store 装一个。")

        if not signals:
            continue

        score = combine(signals, ios_trust_factor(is_store))
        signals.sort(key=lambda s: -s["score"])

        findings.append({
            "pkg": bid, "name": name, "title": signals[0]["title"],
            "level": level_of(score), "score": score,
            "has_icon": True, "is_system": False,
            "installer_label": source,
            "installed_at": None, "installed_days": None,
            "signals": signals,
        })
    findings.sort(key=lambda f: (-f["score"], f["pkg"]))
    return findings


def analyze_ios(out_dir: Path, manifest: dict) -> dict:
    apps = manifest.get("apps", [])
    findings = build_ios_findings(apps)
    user_apps = [a for a in apps
                 if a.get("app_type") == "User"
                 and not a.get("bundle_id", "").startswith(IOS_SYSTEM_PREFIX)]

    def label(a):
        return a.get("name") or KNOWN_APPS.get(a.get("bundle_id", ""), "") or a.get("bundle_id", "")

    vpn_apps = sorted((a for a in user_apps if a.get("has_vpn")),
                      key=lambda a: (is_proxy_tool(a["bundle_id"]), a["bundle_id"]))
    bg_loc = sorted((a for a in user_apps if "后台知道位置" in (a.get("background") or [])),
                    key=lambda a: a["bundle_id"])
    nosy = sorted(user_apps, key=lambda a: -len(a.get("private_perms") or []))[:6]
    counters = sorted((a for a in user_apps if (a.get("queries_count") or 0) >= 40),
                      key=lambda a: -(a.get("queries_count") or 0))

    control_points = [
        {"key": "vpn", "title": "能看见你全部上网内容的软件",
         "desc": "装过这类软件后，你打开的每个网页、填的每个密码都从它手上过",
         "items": [a["bundle_id"] for a in vpn_apps]},
        {"key": "bg_loc", "title": "退出去还在记你在哪的软件",
         "desc": "后台定位开着，就算你不打开它，它也知道你去过哪",
         "items": [a["bundle_id"] for a in bg_loc]},
        {"key": "nosy", "title": "要的权限最多的软件",
         "desc": "不是有问题，是值得你把用不着的收一收",
         "items": [a["bundle_id"] for a in nosy if len(a.get("private_perms") or []) >= 8]},
        {"key": "counter", "title": "在数你装了哪些软件的",
         "desc": "它们会挨个问「这台手机装了那个 App 吗」",
         "items": [a["bundle_id"] for a in counters[:8]]},
    ]

    perm_matrix = []
    for a in user_apps:
        perms = [p for p in (a.get("private_perms") or [])]
        if len(perms) >= 4:
            perm_matrix.append({
                "pkg": a["bundle_id"], "name": label(a),
                "has_icon": True, "source": a.get("source", ""),
                "perms": perms, "count": len(perms),
            })
    perm_matrix.sort(key=lambda x: (-x["count"], x["pkg"]))
    perm_matrix = perm_matrix[:24]

    auto_note = ("iPhone 上每个软件都关在自己的沙盒里，别的软件碰不到它的数据，"
                 "所以这一层本来就比安卓严格。这次看到的是每个软件「声明要用的权限」，"
                 "不是「你真的给了」。到底给没给，得你自己去设置里对一遍——"
                 "下面「你自己核对的那几项」就是干这个的。")

    return {
        "device": manifest.get("device", {}),
        "completeness": {
            "ok": manifest.get("coverage", {}).get("ok", 0),
            "failed": manifest.get("coverage", {}).get("failed", 0),
            "failed_nice": manifest.get("coverage", {}).get("failed_nice", []),
            "note": auto_note,
        },
        "summary": {
            "total_apps": len(apps), "third_party": len(user_apps),
            "side_loaded": len([a for a in user_apps if a.get("suspicious_signer")]),
            "from_store": len([a for a in user_apps if a.get("is_store")]),
            "high": len([f for f in findings if f["level"] == "high"]),
            "check": len([f for f in findings if f["level"] == "check"]),
            "watch": len([f for f in findings if f["level"] == "watch"]),
        },
        "control_points": [c for c in control_points if c["items"]],
        "control_order": [c["key"] for c in control_points if c["items"]],
        "permissions": perm_matrix,
        "outbound": [],
        "preinstalled": [],
        "findings": [f for f in findings if f["level"] != "low"],
    }
