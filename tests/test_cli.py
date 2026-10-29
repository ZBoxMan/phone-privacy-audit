"""跨平台入口的回归测试。

这里测的不是规则引擎（那是 test_audit.py），是「一条命令跑起来」这条路：
入口能起、只读承诺没被破坏、三个平台的路径都算得对。

不需要真机，也不需要 adb —— 采集的 device 分支靠 SOURCES 清单静态断言。
"""

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# 采集器里出现这些动作就说明只读承诺破了。按「命令 子命令」成对匹配，
# 因为单个词会误伤：`default_input_method` 里就有 "put"。
WRITE_PAIRS = {
    ("pm", "uninstall"), ("pm", "install"), ("pm", "clear"), ("pm", "disable"),
    ("pm", "enable"), ("pm", "grant"), ("pm", "revoke"), ("pm", "reset"),
    ("appops", "set"), ("settings", "put"), ("am", "force-stop"),
    ("am", "start"), ("am", "broadcast"), ("cmd", "package", "set"),
    ("svc", "wifi"), ("svc", "data"), ("svc", "power"),
}
# 这些命令自己就是动作，当第一个词出现即算违规
WRITE_HEADS = {"reboot", "kill", "rm", "mv", "wipe", "format", "dd"}


class TestEntrypoints(unittest.TestCase):
    def test_run_py_help(self):
        """入口能起来，argparse 没被写坏。"""
        p = subprocess.run([sys.executable, str(SCRIPTS / "run.py"), "--help"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(p.returncode, 0)
        self.assertIn("--rebuild", p.stdout.decode("utf-8", "replace"))

    def test_rebuild_from_fixture(self):
        """只用夹具重跑分析 + 出报告，产物齐全。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "audit"
            shutil.copytree(FIXTURES / "android", out)
            p = subprocess.run(
                [sys.executable, str(SCRIPTS / "run.py"), str(out), "--rebuild"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))

            report = (out / "report.html").read_text(encoding="utf-8")
            self.assertIn("<html", report.lower())
            # 数据必须真的注进去了，不是空模板
            data = json.loads((out / "audit.json").read_text(encoding="utf-8"))
            self.assertEqual(data["platform"], "android")
            self.assertTrue(data["findings"] or data["control_points"])

    def test_rebuild_missing_audit_fails(self):
        """目录里什么都没有时应该报错退出，而不是生成一份空报告。"""
        with tempfile.TemporaryDirectory() as td:
            p = subprocess.run(
                [sys.executable, str(SCRIPTS / "run.py"), td, "--rebuild"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertNotEqual(p.returncode, 0)


def load_list(file_name, var_name):
    """从脚本源码里读出某个字面量列表，不执行文件本身。

    用 ast 而不是文本切片：切 `SOURCES = [` 到 `]` 会在嵌套括号上切歪，
    而且源码一重排就假失败。
    """
    src = (SCRIPTS / file_name).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == var_name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{file_name} 里没找到 {var_name}")


class TestReadOnly(unittest.TestCase):
    """只读是这个工具的立身之本，做成断言。"""

    def assert_readonly(self, name, args):
        low = [a.lower() for a in args]
        self.assertNotIn(low[0], WRITE_HEADS, f"{name} 里是写操作：{' '.join(low)}")
        for pair in zip(low, low[1:]):
            self.assertNotIn(pair, WRITE_PAIRS, f"{name} 里是写操作：{' '.join(low)}")

    def test_sources_have_no_write_commands(self):
        for name, args in load_list("collect_android.py", "SOURCES"):
            self.assert_readonly(name, args)

    def test_sources_are_unique(self):
        names = [n for n, _ in load_list("collect_android.py", "SOURCES")]
        self.assertEqual(len(names), len(set(names)), "采集项重名会互相覆盖")

    def test_harmony_next_also_readonly(self):
        for name, args in load_list("collect_harmony.py", "NEXT_SOURCES"):
            self.assert_readonly(name, args)


class TestPlatformPaths(unittest.TestCase):
    """venv 在两个平台上的位置不一样，找错了 Windows 用户就起不来。"""

    def test_venv_lookup_posix(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            import run as runner
        finally:
            sys.path.pop(0)
        real_root = runner.ROOT
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / ".venv" / "Scripts").mkdir(parents=True)
            fake = base / ".venv" / "Scripts" / "python.exe"
            fake.write_bytes(b"")
            runner.ROOT = base
            try:
                self.assertEqual(runner.venv_python(), str(fake))
            finally:
                runner.ROOT = real_root


if __name__ == "__main__":
    unittest.main()
