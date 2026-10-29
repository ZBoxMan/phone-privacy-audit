#!/usr/bin/env bash
# 兼容入口。真逻辑在 collect_android.py。
#
#   bash scripts/collect_android.sh [输出目录] [设备序列号]
#
# 严格只读：只用 getprop / pm list / dumpsys / settings get / cat /proc/net。

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || true)"
[ -z "$PY" ] && { echo "ERROR: 需要 python3" >&2; exit 2; }
exec "$PY" "$HERE/collect_android.py" "$@"
