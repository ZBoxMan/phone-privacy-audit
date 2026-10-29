#!/usr/bin/env bash
# 兼容入口。真逻辑在 run.py —— 那份代码在 macOS / Linux / Windows 上一样跑。
#
#   bash scripts/run.sh ./phone-audit
#
# Windows 用户不用这个文件，直接用仓库根目录的 run.bat。

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$HERE/../.venv/bin/python" ]; then
  PY="$HERE/../.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "没找到 python3。安卓/鸿蒙装一个 python3 就行；iPhone 还要按 README 建 .venv。" >&2
  exit 2
fi

exec "$PY" "$HERE/run.py" "$@"
