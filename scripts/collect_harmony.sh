#!/usr/bin/env bash
# 兼容入口。真逻辑在 collect_harmony.py。
#
#   bash scripts/collect_harmony.sh [输出目录]
#
# HarmonyOS 2/3/4（AOSP 底座）走 adb，HarmonyOS NEXT 走 hdc。

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || true)"
[ -z "$PY" ] && { echo "ERROR: 需要 python3" >&2; exit 2; }
exec "$PY" "$HERE/collect_harmony.py" "$@"
