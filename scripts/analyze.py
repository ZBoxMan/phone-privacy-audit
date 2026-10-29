#!/usr/bin/env python3
"""手机体检 - 规则引擎入口

    python3 scripts/analyze.py <采集目录>

读取采集目录，输出 audit.json。支持 Android / HarmonyOS / iOS。
只做分析与归因，不产生任何设备写操作。规则实现在 phoneaudit/ 包里。
"""

import sys

import _console
from phoneaudit.pipeline import main

if __name__ == "__main__":
    _console.setup()
    sys.exit(main())
