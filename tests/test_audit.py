"""规则引擎回归测试。不碰设备，只吃 tests/fixtures 里的采集结果。

    python3 -m unittest discover -s tests -v
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from phoneaudit import android, harmony, ios, verdict  # noqa: E402
from phoneaudit.pipeline import build_audit  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def audit_of(fixture: str) -> dict:
    """把夹具复制到临时目录再分析，analyze 会往目录里写 audit.json。"""
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(FIXTURES / fixture, tmp / fixture)
    try:
        return build_audit(tmp / fixture)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rules_of(audit: dict, pkg: str) -> list:
    for f in audit["findings"]:
        if f["pkg"] == pkg:
            return [s["rule"] for s in f["signals"]]
    return []


class AndroidParsers(unittest.TestCase):
    def test_proc_net_ipv4(self):
        self.assertEqual(android._parse_addr("3C1B2C01:D4C1"), ("1.44.27.60", 54465))

    def test_proc_net_ipv6_v4_mapped(self):
        # 安卓上绝大多数连接走 tcp6 的 ::ffff:a.b.c.d 形式，必须解开
        self.assertEqual(android._parse_addr("0000000000000000FFFF00002E18D822:1F40"),
                         ("34.216.24.46", 8000))

    def test_proc_net_skips_loopback_and_unspecified(self):
        self.assertEqual(android._parse_addr("0100007F:1F90")[0], "")
        self.assertEqual(android._parse_addr("00000000:0000")[0], "")
        self.assertEqual(android._parse_addr("00000000000000000000000001000000:0050")[0], "")

    def test_appops_both_formats(self):
        new = "  Package [com.a]:\n    SYSTEM_ALERT_WINDOW (allow):\n"
        old = "  Package com.b:\n    SYSTEM_ALERT_WINDOW: mode=allow; time=1\n"
        self.assertEqual(android.parse_appops(new), {"com.a": {"SYSTEM_ALERT_WINDOW": "allow"}})
        self.assertEqual(android.parse_appops(old), {"com.b": {"SYSTEM_ALERT_WINDOW": "allow"}})

    def test_package_dump_fields(self):
        dump = (FIXTURES / "android" / "raw" / "package_dump.txt").read_text(encoding="utf-8")
        pk = android.parse_package_dump(dump)
        spy = pk["com.example.spy"]
        self.assertEqual(spy["target_sdk"], 22)
        self.assertIsNone(spy["installer"])
        self.assertTrue(spy["granted"]["android.permission.ACCESS_BACKGROUND_LOCATION"])
        self.assertEqual(pk["com.tencent.mm"]["installer"], "com.xiaomi.market")


class AndroidAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = audit_of("android")

    def test_device_and_platform(self):
        self.assertEqual(self.audit["platform"], "android")
        self.assertEqual(self.audit["device"]["os"], "Android 13")
        self.assertEqual(self.audit["device"]["security_patch"], "2024-11-01")

    def test_stalker_like_app_is_high(self):
        spy = next(f for f in self.audit["findings"] if f["pkg"] == "com.example.spy")
        self.assertEqual(spy["level"], "high")
        self.assertEqual(spy["signals"][0]["rule"], "R_ADMIN")
        self.assertIn("R_BG_LOC", rules_of(self.audit, "com.example.spy"))
        self.assertEqual(self.audit["verdict"]["tone"], "bad")

    def test_store_app_with_icon_is_filtered(self):
        # 微信：小米商店装的、有图标、只有悬浮窗/权限这类噪音 → 不进报告
        self.assertEqual(rules_of(self.audit, "com.tencent.mm"), [])

    def test_find_my_device_admin_is_not_a_finding(self):
        self.assertEqual(rules_of(self.audit, "com.google.android.gms"), [])
        admin = next(c for c in self.audit["control_points"] if c["key"] == "admin")
        self.assertIn("com.google.android.gms", admin["items"])

    def test_camouflage_without_icon(self):
        self.assertIn("R_CAMO", rules_of(self.audit, "com.fake.systemservice"))
        self.assertIn("R_OUTBOUND", rules_of(self.audit, "com.fake.systemservice"))

    def test_ime_accessibility_is_discounted(self):
        sogou = next(f for f in self.audit["findings"] if f["pkg"] == "com.sogou.inputmethod")
        a11y = next(s for s in sogou["signals"] if s["rule"] == "R_A11Y")
        self.assertTrue(a11y["note"])
        self.assertEqual(sogou["level"], "watch")

    def test_outbound_includes_tcp6(self):
        remotes = {(o["pkg"], o["remote"]) for o in self.audit["outbound"]}
        self.assertIn(("com.fake.systemservice", "34.216.24.46:8000"), remotes)
        self.assertIn(("com.tencent.mm", "34.216.184.93:443"), remotes)

    def test_name_map_uses_human_names(self):
        self.assertEqual(self.audit["name_map"]["com.tencent.mm"], "微信")


class IOSClassify(unittest.TestCase):
    def test_sources(self):
        self.assertEqual(ios.classify({"ApplicationType": "System"}), ("系统自带", False))
        self.assertEqual(ios.classify({"ITSDRMScheme": "x"}), ("App Store", False))
        self.assertEqual(ios.classify({"SignerIdentity": "TestFlight Beta Distribution"}),
                         ("TestFlight 测试版", False))
        self.assertEqual(ios.classify({"Entitlements": {"get-task-allow": True}}),
                         ("开发者证书安装", True))
        self.assertEqual(ios.classify({})[1], True)

    def test_perms_and_background(self):
        meta = {"NSCameraUsageDescription": "拍照", "NSLocationAlwaysUsageDescription": "导航",
                "UIBackgroundModes": ["location", "audio", "audio"]}
        names, why = ios.read_perms(meta)
        self.assertEqual(names, ["相机", "一直知道位置"])
        self.assertEqual(why["相机"], "拍照")
        self.assertEqual(ios.read_background(meta), ["后台知道位置", "后台放声音"])


class IOSAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = audit_of("ios")

    def test_sideloaded_tracker_is_flagged(self):
        self.assertIn("I_ENTERPRISE", rules_of(self.audit, "com.evil.tracker"))
        self.assertIn("I_BG_TRACK", rules_of(self.audit, "com.evil.tracker"))

    def test_proxy_tool_vpn_is_control_point_not_finding(self):
        self.assertEqual(rules_of(self.audit, "com.liguangming.Shadowrocket"), [])
        vpn = next(c for c in self.audit["control_points"] if c["key"] == "vpn")
        self.assertIn("com.liguangming.Shadowrocket", vpn["items"])

    def test_manual_check_wins_the_headline(self):
        self.assertEqual(self.audit["verdict"]["tone"], "bad")
        self.assertIn("核对出 1 个问题", self.audit["verdict"]["headline"])
        bad = next(m for m in self.audit["manual_checks"] if m["answer"] == "yes")
        # 文案从 manual-items.json 合并进来，采集端只写 id/answer/note
        self.assertEqual(bad["title"], "Apple ID 登录的设备")
        self.assertEqual(bad["tier"], "must")

    def test_system_apps_are_not_user_apps(self):
        self.assertEqual(self.audit["summary"]["total_apps"], 6)
        self.assertEqual(self.audit["summary"]["third_party"], 5)
        self.assertEqual(self.audit["summary"]["side_loaded"], 1)


class HarmonyNext(unittest.TestCase):
    def test_bundle_list(self):
        text = "ID: 100:\n\tcom.huawei.hmos.settings\n\tcom.tencent.wechat\n\tnot a bundle\n"
        self.assertEqual(harmony.parse_bundle_list(text),
                         ["com.huawei.hmos.settings", "com.tencent.wechat"])

    def test_audit_is_limited_not_ok(self):
        audit = audit_of("harmony_next")
        self.assertEqual(audit["device"]["os"], "HarmonyOS 5.0.0.102")
        self.assertEqual(audit["summary"]["total_apps"], 4)
        self.assertEqual(audit["summary"]["third_party"], 2)
        self.assertEqual(audit["verdict"]["tone"], "warn")
        installed = next(c for c in audit["control_points"] if c["key"] == "installed")
        self.assertEqual(installed["items"], ["com.tencent.wechat", "com.example.oddtool"])


class Verdict(unittest.TestCase):
    def test_thin_data_never_says_ok(self):
        v = verdict.make_verdict([], [], "android", {"total_apps": 0}, {"ok": 0, "failed": 5})
        self.assertEqual(v["tone"], "warn")
        self.assertIn("太少", v["headline"])

    def test_bad_is_not_overridden_by_thin_data(self):
        v = verdict.make_verdict([{"level": "high"}], [], "android",
                                 {"total_apps": 0}, {"ok": 0, "failed": 5})
        self.assertEqual(v["tone"], "bad")

    def test_ios_without_sideload_is_good_news(self):
        v = verdict.make_verdict([{"level": "watch"}], [], "ios",
                                 {"side_loaded": 0, "total_apps": 10}, {"ok": 2})
        self.assertEqual(v["headline"], "没有商店之外的软件")


class BuildReport(unittest.TestCase):
    def test_report_escapes_script_terminators(self):
        import subprocess
        tmp = Path(tempfile.mkdtemp())
        try:
            audit = audit_of("android")
            audit["verdict"]["detail"] = "</script><!-- 注入 -->"
            (tmp / "audit.json").write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "build_report.py"), str(tmp)],
                           check=True, capture_output=True)
            html = (tmp / "report.html").read_text(encoding="utf-8")
            self.assertNotIn("</script><!--", html)
            self.assertIn("\\u003c/script>", html)
            self.assertNotIn("__DATA__", html)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
