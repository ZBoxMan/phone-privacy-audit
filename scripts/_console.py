"""把标准输出钉成 UTF-8。

Windows 上的 CPython 默认用系统 locale 编码（中文机器 cp936，英文机器 cp1252）。
往控制台打字通常没事，但只要输出被重定向到文件、进了管道，或者被别的程序抓走，
print 一句中文就当场 UnicodeEncodeError 崩掉——报错还长得完全不像编码问题。

三个平台都重设一次没有副作用，代价可以忽略，所以不判断平台。
"""

import sys


def setup():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # 被替换成非 TextIOWrapper 的流（有些测试框架会这么做），跳过
            pass
