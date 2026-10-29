"""Android / HarmonyOS（AOSP 底座）：解析 adb 只读采集结果，套规则，产出报告数据。"""

import ipaddress
import re
from datetime import datetime, timezone
from pathlib import Path

from .scoring import combine, level_of, trust_factor
from .vocab import (
    CAMOUFLAGE_WORDS, FIND_MY_DEVICE, IME_HINTS, SENSITIVE_PERMS, SRC_LABEL,
    STALKERWARE_HINTS, SYSTEM_PATH_MARKERS, TRUSTED_INSTALLERS, VENDOR_COMPONENTS,
    WATCHED_OPS, nice_app_name,
)


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
        m = re.match(r"^Package \[?([\w.]+?)\]?:", s)
        if m:
            cur_pkg = m.group(1)
            result.setdefault(cur_pkg, {})
            continue
        if cur_pkg is None:
            continue
        # Android 10+ 写成 `OP (allow):`，更早的版本写成 `OP: mode=allow`
        m = re.match(r"^([A-Z_]+)\s*(?:\(|:\s*mode=)\s*([a-z]+)", s)
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
        if not rem_ip:
            continue
        conns.append({"proto": proto.upper(), "remote": f"{rem_ip}:{rem_port}",
                      "ip": rem_ip, "port": rem_port, "uid": uid_i})
    return conns


def _parse_addr(addr: str):
    """/proc/net/tcp* 里的地址是按 32 位小端分段写的十六进制。

    IPv4 一段，IPv6 四段；安卓上绝大多数连接走 tcp6 的 v4-mapped 形式
    （::ffff:a.b.c.d），不解开就等于把外联看漏了大半。
    """
    if ":" not in addr:
        return "", None
    hexip, hexport = addr.rsplit(":", 1)
    try:
        port = int(hexport, 16)
    except ValueError:
        port = None
    try:
        raw = b"".join(bytes.fromhex(hexip[i:i + 8])[::-1] for i in range(0, len(hexip), 8))
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return "", port
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_loopback or ip.is_unspecified or ip.is_link_local:
        return "", port
    return str(ip), port


def adjust_signals(pkg, signals, ctx):
    is_ime = pkg in ctx.get("ime_pkgs", set()) or any(h in pkg.lower() for h in IME_HINTS)
    for s in signals:
        if s["rule"] == "R_A11Y" and is_ime:
            s["score"] = round(s["score"] * 0.4)
            s["note"] = "输入法开这项权限是正常做法，已经降低关注度。"
    if pkg in FIND_MY_DEVICE:
        signals = [s for s in signals if s["rule"] != "R_ADMIN"]
    return signals


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


def os_label(manifest: dict, release: str) -> str:
    family = "HarmonyOS" if manifest.get("platform") == "harmony" else "Android"
    return f"{family} {release}".strip()


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
            "os": os_label(manifest, read_raw(out_dir, "prop_release").strip()),
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
