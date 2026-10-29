#!/usr/bin/env python3
"""采集器共用件：找工具、带超时地跑只读命令、攒采集清单。

以前这些逻辑分散在 bash 里（`gtimeout 90 adb …`、`wc -c`、
空数组在 `set -u` 下展开报错），换到 Windows 就全废了。
搬到 Python 只有一份实现，三个平台行为一致。

这里没有任何写操作：只拼 `subprocess` 调查询命令，输出重定向到文件。
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 单条采集命令的上限。`dumpsys package` 在装了三四百个应用的机器上要跑十几秒，
# 给 90 秒是留够了余量；真卡住说明设备那头有问题，早点失败比挂着好。
TIMEOUT = 90


def find_tool(*names):
    """按顺序找第一个能用的可执行文件，找不到返回 None。

    Windows 上 adb 是 adb.exe，shutil.which 会自己补扩展名，不用分平台判断。
    """
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def as_text(v):
    """bytes / str / None → str。

    有些环境会把 subprocess 的管道包成文本模式，bytes 和 str 都可能出现，
    在调用点上逐个判断太啰嗦，统一在这里收口。
    """
    if v is None:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)


def as_bytes(v):
    if v is None:
        return b""
    if isinstance(v, bytes):
        return v
    return str(v).encode("utf-8", errors="replace")


def _run(cmd, timeout=TIMEOUT):
    """跑一条命令，返回 (returncode, stdout_bytes, stderr_text)。

    超时不算崩溃：按失败处理，让上层记一笔 `xxx:timeout`，
    这样报告里能看出来「这项没读到」，而不是整个采集中断。
    """
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return p.returncode, as_bytes(p.stdout), as_text(p.stderr)
    except subprocess.TimeoutExpired:
        return 124, b"", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, b"", str(e)


class Collector:
    """一路采集：每次 grab 一个数据源，最后统一写 manifest.json。"""

    def __init__(self, out_dir, tool_path, prefix_args=(), serial=""):
        self.out = Path(out_dir).resolve()
        self.raw = self.out / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.tool = tool_path
        self.prefix = list(prefix_args)
        self.serial = serial
        self.ok = []
        self.failed = []

    def grab(self, name, args, timeout=TIMEOUT):
        """采一个数据源到 raw/<name>.txt。空输出和命令失败分开记。"""
        cmd = [self.tool] + self.prefix + list(args)
        code, out, err = _run(cmd, timeout=timeout)
        target = self.raw / f"{name}.txt"
        if code == 124:
            target.write_bytes(b"")
            (self.raw / f"{name}.err").write_text(err, encoding="utf-8")
            self.failed.append(f"{name}:timeout")
            return False
        target.write_bytes(out)
        if code != 0:
            (self.raw / f"{name}.err").write_text(err, encoding="utf-8")
            self.failed.append(f"{name}:cmd_failed")
            return False
        if not out.strip():
            self.failed.append(f"{name}:empty")
            return False
        self.ok.append(name)
        return True

    def summary(self):
        return len(self.ok), len(self.failed)


def write_manifest(out_dir, platform, serial="", tool="", ok=None, failed=None,
                   harmony_layer=""):
    """写采集清单。分析端靠它判断平台、也靠它区分「读到了」和「没读到」。"""
    manifest = {
        "platform": platform,
        "serial": serial,
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool_version": tool,
        "ok": list(ok or []),
        "failed": list(failed or []),
    }
    if harmony_layer:
        manifest["harmony_layer"] = harmony_layer

    path = Path(out_dir) / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"采集完成: {out_dir}")
    print(f"成功 {len(manifest['ok'])} 项 / 失败 {len(manifest['failed'])} 项")
    if manifest["failed"]:
        print(f"失败项: {' '.join(manifest['failed'])}")
    return manifest


def tool_version(tool, *args):
    """取工具版本号写进 manifest，排查环境问题时省得再问一遍。"""
    code, out, _ = _run([tool] + list(args), timeout=15)
    if code != 0 or not out:
        return ""
    return as_text(out).strip().splitlines()[0][:120]


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def is_windows():
    return os.name == "nt"
