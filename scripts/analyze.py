#!/usr/bin/env python3
"""手机体检 - 规则引擎

读取采集目录，输出 audit.json。支持 Android / HarmonyOS / iOS。
只做分析与归因，不产生任何设备写操作。

文案原则：面向普通人。不说权限名，说"它能干什么"。
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 人工核对项的文案以此为准；manual_checks.json 里只留 answer 和 note
MANUAL_ITEMS = HERE.parent / "references" / "manual-items.json"

# ---------------------------------------------------------------- 词表

SYSTEM_PATH_MARKERS = (
    "/system/", "/system_ext/", "/product/", "/vendor/", "/odm/",
    "/apex/", "/vendor_dlkm/", "/my_product/", "/my_heytap/",
    "/my_stock/", "/preinstall/", "/preinstalled/", "/cust/",
)

TRUSTED_INSTALLERS = {
    "com.android.vending": "Google Play",
    "com.google.android.packageinstaller": "Google 安装器",
    "com.android.packageinstaller": "系统安装器",
    "com.miui.packageinstaller": "小米安装器",
    "com.huawei.appmarket": "华为应用市场",
    "com.hihonor.appmarket": "荣耀应用市场",
    "com.heytap.market": "OPPO 软件商店",
    "com.oppo.market": "OPPO 软件商店",
    "com.bbk.appstore": "vivo 应用商店",
    "com.sec.android.app.samsungapps": "三星应用商店",
    "com.oneplus.market": "一加软件商店",
    "com.coloros.packageinstaller": "OPPO 安装器",
    "com.vivo.packageinstaller": "vivo 安装器",
    "com.samsung.android.packageinstaller": "三星安装器",
    "com.huawei.android.packageinstaller": "华为安装器",
    "com.hihonor.android.packageinstaller": "荣耀安装器",
    "com.coolapk.market": "酷安",
}

# 认得出中文名，报告才说得出人话。认不出就用"一个天气软件"这类推断。
KNOWN_APPS = {
    "com.tencent.mm": "微信", "com.tencent.mobileqq": "QQ",
    "com.tencent.tim": "TIM", "com.tencent.wework": "企业微信",
    "com.taobao.taobao": "淘宝", "com.tmall.wireless": "天猫",
    "com.eg.android.AlipayGphone": "支付宝", "com.jingdong.app.mall": "京东",
    "com.xunmeng.pinduoduo": "拼多多", "com.achievo.vipshop": "唯品会",
    "com.ss.android.ugc.aweme": "抖音", "com.ss.android.ugc.aweme.lite": "抖音极速版",
    "com.smile.gifmaker": "快手", "com.xingin.xhs": "小红书",
    "com.sina.weibo": "微博", "com.ss.android.article.news": "今日头条",
    "com.netease.cloudmusic": "网易云音乐", "com.tencent.qqmusic": "QQ音乐",
    "com.kugou.android": "酷狗音乐", "com.baidu.searchbox": "百度",
    "com.UCMobile": "UC浏览器", "com.tencent.mtt": "QQ浏览器",
    "com.android.chrome": "Chrome", "com.unionpay": "云闪付",
    "com.icbc": "工商银行", "com.chinamworld.main": "建设银行",
    "com.android.bankabc": "农业银行", "com.cmbchina.ccd.pluto.cmbActivity": "招商银行",
    "com.autonavi.minimap": "高德地图", "com.baidu.BaiduMap": "百度地图",
    "com.dianping.v1": "大众点评", "me.ele": "饿了么",
    "com.sankuai.meituan": "美团", "com.taobao.idlefish": "闲鱼",
    "com.zhihu.android": "知乎", "com.douban.frodo": "豆瓣",
    "tv.danmaku.bili": "哔哩哔哩", "com.youku.phone": "优酷",
    "com.qiyi.video": "爱奇艺", "com.tencent.qqlive": "腾讯视频",
    "com.alibaba.android.rimet": "钉钉",
    "com.ximalaya.ting.android": "喜马拉雅",
    "com.whatsapp": "WhatsApp", "com.facebook.katana": "Facebook",
    "com.instagram.android": "Instagram", "com.twitter.android": "X",
    "com.google.android.youtube": "YouTube", "com.google.android.gm": "Gmail",
    "com.google.android.apps.maps": "Google 地图",
    "com.microsoft.office.outlook": "Outlook",
    "com.spotify.music": "Spotify", "org.telegram.messenger": "Telegram",
    "com.tencent.ig": "和平精英", "com.tencent.tmgp.sgame": "王者荣耀",
    "com.miHoYo.Yuanshen": "原神",
    "com.miui.securitycenter": "手机管家", "com.miui.home": "小米桌面",
    "com.android.settings": "设置", "com.android.vending": "应用商店",
    "com.google.android.gms": "Google 服务",
    "com.huawei.android.launcher": "华为桌面",
    "com.huawei.systemmanager": "华为手机管家",
    "com.coloros.safecenter": "OPPO 手机管家",
    "com.vivo.abe": "vivo 手机管家",
    # iOS
    "com.apple.mobilesafari": "Safari", "com.apple.mobileslideshow": "照片",
    "com.apple.MobileSMS": "信息", "com.apple.mobilephone": "电话",
    "com.apple.Preferences": "设置", "com.apple.Maps": "地图",
    "com.apple.Health": "健康", "com.apple.findmy": "查找",
    "com.apple.shortcuts": "快捷指令", "com.apple.mobilemail": "邮件",
    "com.apple.reminders": "提醒事项", "com.apple.notes": "备忘录",
    "com.apple.calculator": "计算器", "com.apple.camera": "相机",
    "com.apple.DocumentsApp": "文件", "com.apple.AppStore": "App Store",
    "com.apple.Passbook": "钱包", "com.apple.Music": "音乐",
    "com.apple.Podcasts": "播客", "com.apple.Bridge": "Watch",
    "com.apple.weather": "天气", "com.apple.stocks": "股市",
}

PURPOSE_HINTS = (
    ("weather", "天气"), ("clean", "清理加速"), ("boost", "清理加速"),
    ("speed", "清理加速"), ("lock", "锁屏"), ("browser", "浏览器"),
    ("input", "输入法"), ("ime", "输入法"), ("keyboard", "输入法"),
    ("camera", "相机"), ("photo", "相册"), ("video", "视频"),
    ("music", "音乐"), ("news", "新闻资讯"), ("shop", "购物"),
    ("mall", "购物"), ("pay", "支付"), ("wallet", "钱包"),
    ("game", "游戏"), ("map", "地图"), ("health", "健康"),
    ("theme", "主题壁纸"), ("wallpaper", "主题壁纸"), ("launcher", "桌面"),
    ("file", "文件管理"), ("calendar", "日历"), ("clock", "时钟"),
    ("alarm", "闹钟"), ("radio", "收音机"), ("flashlight", "手电筒"),
    ("live", "直播"), ("reading", "阅读"), ("book", "阅读"),
    ("wallpaper", "壁纸"), ("widget", "小组件"),
)

VENDOR_COMPONENTS = {
    "com.miui.msa.global": "小米系统广告服务",
    "com.miui.systemadolution": "小米系统广告组件",
    "com.miui.systemadsolution": "小米系统广告组件",
    "com.miui.analytics": "小米统计服务",
    "com.miui.miuibbs": "小米社区",
    "com.miui.hybrid": "小米快应用引擎",
    "com.miui.hybrid.accessory": "小米快应用支撑",
    "com.miui.mipicks": "小米应用推荐",
    "com.xiaomi.market": "小米应用商店",
    "com.huawei.hwid": "华为账号服务",
    "com.huawei.android.hwouc": "华为系统更新",
    "com.huawei.intelligent": "华为负一屏",
    "com.hihonor.intelligent": "荣耀负一屏",
    "com.coloros.assistantscreen": "OPPO 负一屏",
    "com.heytap.browser": "OPPO 浏览器",
    "com.vivo.assistant": "vivo 负一屏",
    "com.bbk.launcher2": "vivo 桌面",
    "com.huawei.hms.core": "华为移动服务",
}

SENSITIVE_PERMS = {
    "android.permission.ACCESS_FINE_LOCATION": ("位置", "high"),
    "android.permission.ACCESS_COARSE_LOCATION": ("大致位置", "mid"),
    "android.permission.ACCESS_BACKGROUND_LOCATION": ("后台位置", "high"),
    "android.permission.RECORD_AUDIO": ("麦克风", "high"),
    "android.permission.CAMERA": ("相机", "high"),
    "android.permission.READ_SMS": ("短信", "high"),
    "android.permission.RECEIVE_SMS": ("短信", "high"),
    "android.permission.READ_CONTACTS": ("通讯录", "high"),
    "android.permission.READ_CALL_LOG": ("通话记录", "high"),
    "android.permission.CALL_PHONE": ("打电话", "mid"),
    "android.permission.READ_PHONE_STATE": ("手机信息", "mid"),
    "android.permission.READ_PHONE_NUMBERS": ("本机号码", "mid"),
    "android.permission.PROCESS_OUTGOING_CALLS": ("监听拨出电话", "high"),
    "android.permission.SEND_SMS": ("发短信", "high"),
    "android.permission.WRITE_SMS": ("改短信", "high"),
}

WATCHED_OPS = {
    "SYSTEM_ALERT_WINDOW": ("弹窗", "high"),
    "ACCESS_FINE_LOCATION": ("位置", "high"),
    "RECORD_AUDIO": ("麦克风", "high"),
    "CAMERA": ("相机", "high"),
    "READ_SMS": ("短信", "high"),
    "READ_CONTACTS": ("通讯录", "high"),
    "READ_CALL_LOG": ("通话记录", "high"),
    "POST_NOTIFICATION": ("通知", "mid"),
    "RUN_IN_BACKGROUND": ("后台运行", "mid"),
    "START_FOREGROUND": ("常驻后台", "mid"),
    "BOOT_COMPLETED": ("开机自启", "mid"),
    "ACTIVATE_VPN": ("VPN", "high"),
    "GET_USAGE_STATS": ("使用记录", "mid"),
}

CAMOUFLAGE_WORDS = (
    "system", "service", "services", "update", "updater", "security",
    "protect", "protection", "settings", "framework", "core",
    "provider", "manager", "guard", "safe", "engine",
)

STALKERWARE_HINTS = (
    "mspy", "flexispy", "hellospy", "spyhuman", "spyzie", "cerberus",
    "thetruthspy", "hoverwatch", "kidguard", "xnspy", "minspy", "cocospy",
    "spyic", "mobiletrack", "phonesheriff", "snoopza", "trackmyfone",
)

FIND_MY_DEVICE = (
    "com.google.android.gms", "com.miui.cloudservice", "com.huawei.hwid",
    "com.coloros.findmyphone", "com.vivo.findphone", "com.samsung.android.fmm",
    "com.hihonor.findmydevice", "com.huawei.findmydevice",
)

IME_HINTS = ("inputmethod", ".ime", "keyboard", "sogou.input", "baidu.input",
             "iflytek", "ime.")

SRC_LABEL = {
    "prop_brand": "设备品牌", "prop_model": "设备型号", "prop_manufacturer": "厂商",
    "prop_release": "系统版本", "prop_sdk": "系统 API", "prop_security_patch": "安全补丁",
    "prop_fingerprint": "系统指纹", "prop_serial": "设备序列号", "users": "用户列表",
    "packages_all": "应用清单", "packages_third": "第三方应用清单",
    "packages_system": "系统应用清单", "packages_disabled": "已停用应用",
    "launcher_entries": "桌面入口", "boot_receivers": "开机自启",
    "default_home": "默认桌面", "default_input": "默认输入法", "admins_apps": "管理员组件",
    "package_dump": "应用详情", "device_policy": "设备管理员",
    "accessibility": "无障碍服务", "notif_listeners": "通知使用权",
    "appops_dump": "权限操作记录", "deviceidle": "电池优化白名单",
    "power_whitelist": "省电白名单", "net_tcp": "TCP 连接", "net_tcp6": "IPv6 TCP 连接",
    "net_udp": "UDP 连接", "net_udp6": "IPv6 UDP 连接", "proxy": "代理设置",
    "bundle_list": "应用清单", "bundle_info": "应用详情",
}

LEVEL_LABEL = {
    "high": "先处理这个",
    "check": "有空看一眼",
    "watch": "知道就行",
    "low": "没发现异常",
}


# ---------------------------------------------------------------- 工具

def read_raw(out_dir: Path, name: str) -> str:
    p = out_dir / "raw" / f"{name}.txt"
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_ts(value: str):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def days_since(dt):
    if not dt:
        return None
    return max(0, (datetime.now(timezone.utc) - dt).days)


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def nice_app_name(pkg: str) -> str:
    """把包名翻译成人能看懂的名字。识别不出就返回包名本身。

    名字里带系统词汇的软件不做用途推断：猜出来的"系统服务"
    正好就是它伪装的身份，那等于替它洗白。这种时候直接给包名——
    包名本身就是证据，用户拿着它才能在设置里搜到这个东西。
    """
    if pkg in KNOWN_APPS:
        return KNOWN_APPS[pkg]
    low = pkg.lower()
    tail = low.rsplit(".", 1)[-1]
    if any(w in tail for w in CAMOUFLAGE_WORDS):
        return pkg
    for word, label in PURPOSE_HINTS:
        if word in low:
            return f"一个{label}软件"
    return pkg


# ---------------------------------------------------------------- 解析

def parse_package_list(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        m = re.match(r"package:(.+?)=([\w.]+)(?:\s+uid:(\d+))?", line)
        if not m:
            continue
        apk, pkg, uid = m.group(1), m.group(2), m.group(3)
        out[pkg] = {"apk": apk, "uid": int(uid) if uid else None}
    return out


def parse_pkg_set(text: str) -> set:
    return {ln.strip()[8:] for ln in text.splitlines() if ln.strip().startswith("package:")}


def parse_components(text: str) -> set:
    pkgs = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:priority=\S+\s+)?([A-Za-z][\w.]*)/", line)
        if m:
            pkgs.add(m.group(1))
    return pkgs


def parse_package_dump(text: str) -> dict:
    packages = {}
    cur = None
    in_flags = False
    in_runtime = False

    for line in text.splitlines():
        s = line.strip()

        m = re.match(r"Package \[([\w.]+)\]", s)
        if m:
            cur = m.group(1)
            packages[cur] = {
                "pkg": cur, "uid": None, "code_path": "", "version_name": "",
                "version_code": "", "target_sdk": None, "min_sdk": None,
                "first_install": None, "last_update": None, "installer": None,
                "flags": [], "granted": {},
            }
            in_flags = in_runtime = False
            continue

        if cur is None:
            continue
        rec = packages[cur]

        if s.startswith("userId="):
            rec["uid"] = _int(s.split("=", 1)[1])
        elif s.startswith("codePath="):
            rec["code_path"] = s.split("=", 1)[1].strip()
        elif s.startswith("versionName="):
            rec["version_name"] = s.split("=", 1)[1].strip()
        elif re.match(r"^versionCode=\S+", s):
            mm = re.search(r"versionCode=(\S+)\s+minSdk=(\S+)\s+targetSdk=(\S+)", s)
            if mm:
                rec["version_code"] = mm.group(1)
                rec["min_sdk"] = None if mm.group(2) == "null" else _int(mm.group(2))
                rec["target_sdk"] = None if mm.group(3) == "null" else _int(mm.group(3))
            else:
                rec["version_code"] = s.split("=", 1)[1].split()[0]
        elif s.startswith("firstInstallTime="):
            rec["first_install"] = parse_ts(s.split("=", 1)[1])
        elif s.startswith("lastUpdateTime="):
            rec["last_update"] = parse_ts(s.split("=", 1)[1])
        elif s.startswith("installerPackageName="):
            v = s.split("=", 1)[1].strip()
            rec["installer"] = None if v in ("null", "") else v
        elif s.startswith("installSource="):
            mm = re.search(r"installerPackageName=([\w.]+)", s)
            if mm and not rec["installer"]:
                rec["installer"] = mm.group(1)
        elif s == "flags=[":
            in_flags = True
        elif in_flags:
            if s == "]":
                in_flags = False
            elif s:
                rec["flags"].append(s)
        elif s == "runtime permissions:":
            in_runtime = True
        elif in_runtime:
            mm = re.match(r"^([\w.]+): granted=(true|false)", s)
            if mm:
                rec["granted"][mm.group(1)] = mm.group(2) == "true"
            elif s and not s.startswith("android.permission"):
                in_runtime = False

    return packages


def parse_settings_components(text: str) -> set:
    text = text.strip()
    if not text or text in ("null", "0"):
        return set()
    pkgs = set()
    for item in text.split(":"):
        item = item.strip()
        if "/" in item:
            pkgs.add(item.split("/")[0])
    return pkgs


def parse_device_admins(text: str) -> set:
    admins = set()
    capture = False
    for line in text.splitlines():
        low = line.lower()
        if ("enabled device admins" in low or "已启用的设备管理员" in line
                or "active admins" in low):
            capture = True
            continue
        if capture:
            if line.strip() and not line.startswith((" ", "\t")):
                capture = False
                continue
            m = re.match(r"^\s+([A-Za-z][\w.]*)/([\w.$]+)", line)
            if m:
                admins.add(m.group(1))
    return admins


def parse_appops(text: str) -> dict:
    result = {}
    cur_pkg = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^Package \[([\w.]+)\]", s)
        if m:
            cur_pkg = m.group(1)
            result.setdefault(cur_pkg, {})
            continue
        if cur_pkg is None:
            continue
        m = re.match(r"^([A-Z_]+)\s*[:(]\s*([a-z]+)", s)
        if m and m.group(1) in WATCHED_OPS:
            result[cur_pkg][m.group(1)] = m.group(2)
    return result


def parse_proc_net(text: str, proto: str) -> list:
    conns = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        rem, state, uid = parts[2], parts[3], parts[7]
        if state == "0A":
            continue
        uid_i = _int(uid)
        if not uid_i:
            continue
        rem_ip, rem_port = _parse_addr(rem)
        if rem_ip in ("0.0.0.0", "127.0.0.1", "ipv6", ""):
            continue
        conns.append({"proto": proto.upper(), "remote": f"{rem_ip}:{rem_port}",
                      "ip": rem_ip, "port": rem_port, "uid": uid_i})
    return conns


def _parse_addr(addr: str):
    if ":" not in addr:
        return "", None
    hexip, hexport = addr.rsplit(":", 1)
    try:
        port = int(hexport, 16)
    except ValueError:
        port = None
    if len(hexip) == 8:
        return ".".join(str(int(hexip[i:i + 2], 16)) for i in (6, 4, 2, 0)), port
    return "ipv6", port


# ---------------------------------------------------------------- 评分

def adjust_signals(pkg, signals, ctx):
    is_ime = pkg in ctx.get("ime_pkgs", set()) or any(h in pkg.lower() for h in IME_HINTS)
    for s in signals:
        if s["rule"] == "R_A11Y" and is_ime:
            s["score"] = round(s["score"] * 0.4)
            s["note"] = "输入法开这项权限是正常做法，已经降低关注度。"
    if pkg in FIND_MY_DEVICE:
        signals = [s for s in signals if s["rule"] != "R_ADMIN"]
    return signals


def trust_factor(installer, has_icon, is_system):
    if is_system:
        return 0.75
    if has_icon and installer in TRUSTED_INSTALLERS:
        return 0.62
    if has_icon:
        return 0.85
    return 1.0


def combine(signals, factor=1.0):
    ws = sorted((s["score"] for s in signals), reverse=True)
    return max(1, min(100, round((ws[0] + 0.6 * sum(ws[1:])) * factor)))


def level_of(score: int) -> str:
    if score >= 65:
        return "high"
    if score >= 32:
        return "check"
    if score >= 15:
        return "watch"
    return "low"


# ---------------------------------------------------------------- Android

def build_android_findings(ctx) -> list:
    findings = []

    for pkg, rec in ctx["pkg_dump"].items():
        meta = ctx["pkg_list"].get(pkg, {})
        code_path = rec.get("code_path") or meta.get("apk", "")
        is_system = pkg in ctx["system_pkgs"] or any(m in code_path for m in SYSTEM_PATH_MARKERS)
        has_icon = pkg in ctx["launcher_pkgs"]
        installer = rec.get("installer")
        ops = ctx["appops"].get(pkg, {})
        granted = rec.get("granted", {})
        target_sdk = rec.get("target_sdk")
        name = nice_app_name(pkg)

        signals = []

        def add(rule, score, title, why, how, note=""):
            signals.append({"rule": rule, "score": score, "title": title,
                            "why": why, "how": how, "note": note})

        if pkg in ctx["device_admins"]:
            add("R_ADMIN", 40, "它把自己锁住了，你删不掉",
                "它在手机里加了一道锁。你想删它，手机会拦住你。"
                "狠一点的还能远程锁屏、把手机清空。这功能本来是公司管员工手机用的。",
                "打开设置，顶上搜「设备管理」。列表里有它，就把勾去掉。去掉之后才删得掉。")

        # 系统自带应用在无障碍/通知使用权里是正常的（手机管家、系统通知服务都在这）。
        # 它们仍然要出现在「谁能动你的手机」里让用户看见，但不该被算成可疑。
        if pkg in ctx["a11y"] and not is_system:
            add("R_A11Y", 34, "它能看见你屏幕上的字",
                "这个开关本来是给读屏软件用的。开了之后，它能看到你屏幕上所有的字，"
                "还能替你点按钮。转账那个确认键，它也能点。",
                "设置 → 无障碍 → 已下载的服务。里面一排开关，不认识的先关掉。"
                "关完发现哪个功能不能用了，再打开。")

        if pkg in ctx["notif_listeners"] and not is_system:
            add("R_NOTIF", 22, "你的通知它全看得见",
                "微信消息、银行到账、短信验证码，只要弹在通知栏上，它都能看到。"
                "这开关一般是手表手环才要。",
                "设置 → 通知 → 通知使用权。把不认识的关掉。")

        if not is_system and not has_icon:
            tail = pkg.lower().rsplit(".", 1)[-1]
            camouflage = [w for w in CAMOUFLAGE_WORDS if w in tail]
            if camouflage:
                add("R_CAMO", 25, "桌面找不到它，名字却像手机自带的",
                    "桌面翻遍了也没有它的图标，名字里却带着「系统」「服务」「更新」这些词。"
                    "正常软件很少两样都占。",
                    "先别删。设置 → 应用，找到它，把详情页截图存下来，再决定怎么办。")
            else:
                add("R_HIDDEN", 16, "桌面上没有它的图标",
                    "这不一定有问题。输入法、主题、手表配套的软件本来就没图标。"
                    "但你要是完全不记得装过，就值得看一眼。",
                    "设置 → 应用，搜这个名字，看安装日期。"
                    "想想那几天有没有在网页上、群里点过「下载安装」。")

        if installer not in TRUSTED_INSTALLERS and not is_system:
            add("R_SIDELOAD", 8, "它不是从应用商店装的",
                "它是从网页上、或者别人发来的安装包装的。这种方式本身没毛病，"
                "但出了事商店不管。",
                "想想最近有没有装过别人发的软件。想不起来就看安装日期，"
                "跟那几天干过的事对一下。")

        if ops.get("SYSTEM_ALERT_WINDOW") == "allow" and not is_system:
            add("R_OVERLAY", 16, "它能在你手机上随便弹广告",
                "你正刷着微信、看着视频，它能在最上面盖一层，还关不掉。"
                "那些莫名其妙的浮窗就是这么来的。",
                "设置里搜「悬浮窗」，有的手机叫「显示在其他应用上层」。"
                "把不要的关掉。微信、QQ 的消息气泡也用这个，别关错。")

        if target_sdk is not None and target_sdk < 23 and not is_system:
            add("R_OLDSDK", 12, "这软件七八年没更新了",
                "它是按老标准做的。新版安卓管不住老软件，该拦的地方拦不住。"
                "正常更新的软件不会这样。",
                "不是非用不可的话，去应用商店装个新版，或者换个别的。")

        if pkg in ctx["boot_pkgs"] and not is_system:
            extra = "而且系统不会限制它在后台运行。" if pkg in ctx["idle_whitelist"] else ""
            add("R_BOOT", 8, "手机一开机它自己就跑",
                f"你没打开它，它也在后台待着。{extra}这种软件多了，手机会变慢、更费电。",
                "设置 → 应用 → 找到它 → 电池（有的手机叫自启动）。"
                "把「允许自启动」和「允许后台活动」关掉。")

        risky_perm = [p for p, ok in granted.items() if ok and p in SENSITIVE_PERMS]
        high_perm = [p for p in risky_perm if SENSITIVE_PERMS[p][1] == "high"]
        if len(high_perm) >= 3 and not is_system:
            names = "、".join(SENSITIVE_PERMS[p][0] for p in high_perm[:4])
            add("R_PERM_COMBO", 14, "它要的东西太多了",
                f"它一口气要了{names}。单看每一样都有理由，"
                "但一个软件要这么多，就说不通了。",
                "设置 → 应用 → 找到它 → 权限。把它用不上的关掉。"
                "关完它可能说功能受限，这是正常的。")

        if ("android.permission.ACCESS_BACKGROUND_LOCATION" in risky_perm
                and not has_icon and not is_system):
            add("R_BG_LOC", 22, "你不用它，它也在记你在哪",
                "它能后台定位，桌面上又没图标。这两样凑一起，是跟踪软件最常干的事。"
                "正常软件就算要定位，也有个看得见的界面。",
                "这条要当真。设置 → 位置信息 → 应用权限，看它什么时候开的。"
                "再看设置 → 应用 → 它 → 流量，看是不是一直在联网。")

        hit = next((h for h in STALKERWARE_HINTS if h in pkg.lower()), None)
        if hit:
            add("R_BLACKLIST", 35, "名字和曝光过的监控软件撞上了",
                f"它的名字里带着「{hit}」，这是媒体曝光过的商业监控软件的名字。"
                "这只是个线索，还不能当结论。",
                "先别删。详情页、权限页、流量记录都截图存好，再交给能判断的人。"
                "删掉等于把证据一起清了。")

        conns = [c for c in ctx["outbound"] if c.get("pkg") == pkg]
        odd = [c for c in conns if c["port"] and c["port"] not in (80, 443, 8080, 8443, 53)]
        if odd and not is_system:
            sample = "、".join(sorted({c["remote"] for c in odd})[:2])
            add("R_OUTBOUND", 12, "它在往外发东西",
                f"它现在连着 {sample}。一般软件走常见的通道，这个连接不太寻常。"
                "也可能只是游戏服务器或者消息推送。",
                "设置 → 应用 → 它 → 流量使用情况，看后台用了多少。"
                "你完全不用它流量还在涨，那就有问题。")

        if not signals:
            continue

        signals = adjust_signals(pkg, signals, ctx)
        if not signals:
            continue

        rules = {s["rule"] for s in signals}
        if (has_icon and installer in TRUSTED_INSTALLERS
                and not (rules & {"R_ADMIN", "R_A11Y", "R_CAMO", "R_BG_LOC"})):
            continue

        score = combine(signals, trust_factor(installer, has_icon, is_system))
        signals.sort(key=lambda s: -s["score"])

        findings.append({
            "pkg": pkg, "name": name, "title": signals[0]["title"],
            "level": level_of(score), "score": score,
            "has_icon": has_icon, "is_system": is_system,
            "installer_label": TRUSTED_INSTALLERS.get(installer or "", ""),
            "installed_at": rec["first_install"].strftime("%Y-%m-%d") if rec.get("first_install") else None,
            "installed_days": days_since(rec.get("first_install")),
            "signals": signals,
        })

    findings.sort(key=lambda f: (-f["score"], f["pkg"]))
    return findings


# ---------------------------------------------------------------- iOS

IOS_SYSTEM_PREFIX = "com.apple."

# 代理 / 加速工具，拿 VPN 权限是本职，不算信号
PROXY_HINTS = ("shadowrocket", "clash", "surge", "quantumult", "loon",
               "stash", "sing-box", "v2ray", "surfboard", "kitsunebi",
               "outline", "wireguard", "tailscale", "expressvpn", "nordvpn")


def is_proxy_tool(bid: str) -> bool:
    low = bid.lower()
    return any(h in low for h in PROXY_HINTS)


def ios_trust_factor(is_store: bool) -> float:
    """过了苹果审核的降权。商店里的软件要权限，多半有正当理由。"""
    return 0.55 if is_store else 1.0


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


# ---------------------------------------------------------------- 结论

def make_verdict(findings, manual, platform="android", summary=None) -> dict:
    high = [f for f in findings if f["level"] == "high"]
    check = [f for f in findings if f["level"] == "check"]
    watch = [f for f in findings if f["level"] == "watch"]
    manual_bad = [m for m in manual if m.get("answer") == "yes"]
    summary = summary or {}

    if high:
        return {"tone": "bad",
                "headline": f"有 {len(high)} 个软件，先看看",
                "detail": "下面每一条都写了它哪儿不对、你该干什么。弄完可以再查一次。"}
    if manual_bad:
        # 人工核对查出来的东西优先级高于应用层面，标题里直接点名，别让人往下找
        names = "、".join(m.get("title") or m.get("id", "") for m in manual_bad[:3])
        more = f" 等 {len(manual_bad)} 项" if len(manual_bad) > 3 else ""
        return {"tone": "bad",
                "headline": f"核对出 {len(manual_bad)} 个问题",
                "detail": f"{names}{more}。这些是你亲眼确认的，比机器猜的靠谱。"
                          "往下翻「你自己看到的那几项」看怎么处理。"
                          + (f"另外 {len(check)} 个软件可以顺带看看。" if check else "")}
    if check:
        return {"tone": "warn",
                "headline": f"{len(check)} 个软件，有空看看",
                "detail": "都不是病毒，就是有些地方说不通。不着急。"}
    if watch:
        # iPhone 上「没有非商店安装」是真正的结论，要单独说出来，
        # 不然一律写「没看出什么问题」，等于把好消息也说没了。
        if platform == "ios" and not summary.get("side_loaded"):
            return {"tone": "ok",
                    "headline": "没有商店之外的软件",
                    "detail": f"iPhone 上能绕开苹果进来的坏东西，这次一个都没有。"
                              f"剩下 {len(watch)} 个是权限要得多，不算问题，"
                              "想收一收的往下看「它想打听你多少事」。"}
        return {"tone": "ok",
                "headline": "没看出什么问题",
                "detail": f"有 {len(watch)} 个软件有点小情况，都算不上问题。"}
    return {"tone": "ok",
            "headline": "没看出什么问题",
            "detail": "这次看到的范围里，没有要你处理的。"}


# ---------------------------------------------------------------- 主流程

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


def analyze_android(out_dir: Path, manifest: dict) -> dict:
    pkg_list = parse_package_list(read_raw(out_dir, "packages_all"))
    pkg_dump = parse_package_dump(read_raw(out_dir, "package_dump"))
    system_pkgs = parse_pkg_set(read_raw(out_dir, "packages_system"))
    launcher_pkgs = parse_components(read_raw(out_dir, "launcher_entries"))
    boot_pkgs = parse_components(read_raw(out_dir, "boot_receivers"))
    admin_pkgs = parse_components(read_raw(out_dir, "admins_apps"))
    device_admins = parse_device_admins(read_raw(out_dir, "device_policy")) | admin_pkgs
    a11y = parse_settings_components(read_raw(out_dir, "accessibility"))
    notif = parse_settings_components(read_raw(out_dir, "notif_listeners"))
    appops = parse_appops(read_raw(out_dir, "appops_dump"))

    idle_whitelist = set()
    for line in read_raw(out_dir, "deviceidle").splitlines():
        line = line.strip()
        if line.startswith(("system-excidle,", "system,")):
            idle_whitelist.add(line.split(",", 1)[1].strip())

    ime_raw = read_raw(out_dir, "default_input").strip()
    ime_pkgs = {ime_raw.split("/")[0]} if ime_raw and ime_raw != "null" else set()

    uid_to_pkg = {}
    for pkg, rec in pkg_dump.items():
        uid = rec.get("uid") or pkg_list.get(pkg, {}).get("uid")
        if uid:
            uid_to_pkg[uid] = pkg

    outbound = []
    for fname, proto in (("net_tcp", "tcp"), ("net_tcp6", "tcp6"),
                         ("net_udp", "udp"), ("net_udp6", "udp6")):
        for c in parse_proc_net(read_raw(out_dir, fname), proto):
            c["pkg"] = uid_to_pkg.get(c["uid"])
            if c["pkg"]:
                outbound.append(c)

    ctx = {
        "pkg_list": pkg_list, "pkg_dump": pkg_dump, "system_pkgs": system_pkgs,
        "launcher_pkgs": launcher_pkgs, "boot_pkgs": boot_pkgs,
        "device_admins": device_admins, "a11y": a11y, "notif_listeners": notif,
        "appops": appops, "idle_whitelist": idle_whitelist,
        "outbound": outbound, "ime_pkgs": ime_pkgs,
    }

    all_findings = build_android_findings(ctx)
    findings = [f for f in all_findings if f["level"] != "low"]

    perm_matrix = []
    for pkg, rec in pkg_dump.items():
        if pkg in system_pkgs:
            continue
        held = [SENSITIVE_PERMS[p][0] for p, ok in rec.get("granted", {}).items()
                if ok and p in SENSITIVE_PERMS]
        if appops.get(pkg, {}).get("SYSTEM_ALERT_WINDOW") == "allow":
            held.append("弹窗")
        if held:
            perm_matrix.append({"pkg": pkg, "name": nice_app_name(pkg),
                                "has_icon": pkg in launcher_pkgs,
                                "perms": held, "count": len(held)})
    perm_matrix.sort(key=lambda x: (-x["count"], x["pkg"]))

    third_party = [p for p in pkg_dump if p not in system_pkgs]
    side_loaded = [p for p in third_party if pkg_dump[p].get("installer") not in TRUSTED_INSTALLERS]

    failed = manifest.get("failed", [])
    failed_nice = []
    for item in failed:
        key = item.split(":")[0]
        reason = "读不到内容" if item.endswith(":empty") else "命令没跑通"
        failed_nice.append(f"{SRC_LABEL.get(key, key)}（{reason}）")

    return {
        "device": {
            "brand": read_raw(out_dir, "prop_brand").strip(),
            "manufacturer": read_raw(out_dir, "prop_manufacturer").strip(),
            "model": read_raw(out_dir, "prop_model").strip(),
            "os": "Android " + read_raw(out_dir, "prop_release").strip(),
            "security_patch": read_raw(out_dir, "prop_security_patch").strip(),
            "scanned_at": manifest.get("collected_at", ""),
        },
        "completeness": {
            "ok": len(manifest.get("ok", [])), "failed": len(failed),
            "failed_items": failed, "failed_nice": failed_nice,
            "note": f"本次有 {len(failed)} 项没读出来，相关结论的覆盖范围要相应缩小。" if failed else "",
        },
        "summary": {
            "total_apps": len(pkg_dump), "third_party": len(third_party),
            "side_loaded": len(side_loaded),
            "high": len([f for f in findings if f["level"] == "high"]),
            "check": len([f for f in findings if f["level"] == "check"]),
            "watch": len([f for f in findings if f["level"] == "watch"]),
        },
        "control_points": [
            {"key": "admin", "title": "你删不掉的软件",
             "desc": "想删它，手机会拦住你", "items": sorted(device_admins)},
            {"key": "a11y", "title": "能偷看你屏幕的软件",
             "desc": "能看见你屏幕上的字，还能替你点按钮", "items": sorted(a11y)},
            {"key": "notif", "title": "能读你消息的软件",
             "desc": "短信验证码、聊天消息都看得见", "items": sorted(notif)},
            {"key": "overlay", "title": "能弹广告的软件",
             "desc": "那些关不掉的浮窗就是它们干的", "items": sorted(
                 p for p, o in appops.items()
                 if o.get("SYSTEM_ALERT_WINDOW") == "allow" and p in pkg_dump)},
        ],
        "permissions": perm_matrix[:30],
        "outbound": [{"pkg": c["pkg"], "name": nice_app_name(c["pkg"]),
                      "remote": c["remote"], "proto": c["proto"]}
                     for c in sorted(outbound, key=lambda x: (x["pkg"] or "", x["remote"]))][:40],
        "preinstalled": [{"pkg": p, "name": VENDOR_COMPONENTS[p]}
                         for p in sorted(pkg_dump) if p in VENDOR_COMPONENTS],
        "findings": findings,
    }


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


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

    manifest = {}
    for name in ("manifest.json", "ios.json"):
        p = out_dir / name
        if p.exists():
            try:
                manifest = json.loads(p.read_text(encoding="utf-8"))
                break
            except json.JSONDecodeError:
                pass

    if not manifest:
        print(f"ERROR: {out_dir} 下没有采集结果，请先跑采集脚本", file=sys.stderr)
        return 2

    platform = manifest.get("platform", "android")
    manual = load_manual(out_dir)

    if platform == "ios":
        data = analyze_ios(out_dir, manifest)
    else:
        data = analyze_android(out_dir, manifest)

    verdict = make_verdict(data["findings"], manual, platform, data.get("summary"))

    # 数据不充分时不能说"没发现问题"——那会把读不到说成没问题
    ok_n = data["completeness"].get("ok", 0)
    bad_n = data["completeness"].get("failed", 0)
    thin = []
    if data["summary"].get("total_apps", 0) == 0:
        thin.append("一个软件都没读到")
    if ok_n == 0:
        thin.append("所有检查项都没跑通")
    elif bad_n > ok_n:
        thin.append(f"{bad_n} 项没跑通、只有 {ok_n} 项成功")
    if thin and verdict["tone"] != "bad":
        verdict = {
            "tone": "warn",
            "headline": "这次能看到的太少，说明不了问题",
            "detail": f"{'，'.join(thin)}。下面的结论只覆盖读到的那部分，"
                      "没读到的部分不等于没问题。按「这次没查到的地方」里的说明手工核对一遍更靠谱。",
        }

    seen = set()
    for f in data["findings"]:
        seen.add(f["pkg"])
    for c in data.get("control_points", []):
        seen.update(c.get("items", []))
    for p in data.get("permissions", []):
        seen.add(p["pkg"])
    name_map = {p: KNOWN_APPS[p] for p in seen if p in KNOWN_APPS}

    # 「谁能动你的手机」里的条目也用报告里那套叫法，别一个地方说「一个清理软件」、
    # 另一个地方甩包名。包名本身留给卡片的标题属性，用户要搜的时候还找得到。
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

    audit = {
        "platform": platform,
        "name_map": name_map,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "verdict": verdict,
        "manual_checks": manual,
        "level_labels": LEVEL_LABEL,
        **data,
    }

    (out_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    s = audit["summary"]
    print(f"平台: {platform} | 应用 {s['total_apps']} 个")
    print(f"现在就看 {s['high']} | 有空看 {s['check']} | 知道就行 {s['watch']}")
    print(f"结论: {audit['verdict']['headline']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
