#!/usr/bin/env bash
# 手机体检 —— 一条命令跑完
#
#   bash scripts/run.sh ./phone-audit            采集 + 分析 + 出报告
#   bash scripts/run.sh ./phone-audit --rebuild  只重新分析 + 出报告（改完核对项用）
#
# 自动认手机：iPhone 走 USB，安卓/鸿蒙走 adb/hdc。
# 全程只读，不装、不卸、不改任何设置。

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

# iPhone 采集要 venv 里的 pymobiledevice3；安卓/鸿蒙的分析和出报告系统 python3 就够
VENV_PY="$ROOT/.venv/bin/python"
if [ -x "$VENV_PY" ]; then PY="$VENV_PY"; else PY="$(command -v python3 || true)"; fi
if [ -z "$PY" ]; then
  echo "没找到 python3。安卓/鸿蒙装一个 python3 就行；iPhone 还要按 README 建 .venv。" >&2
  exit 2
fi

OUT="./phone-audit"
REBUILD=0
for a in "$@"; do
  case "$a" in
    --rebuild) REBUILD=1 ;;
    -*) ;;
    *) OUT="$a" ;;
  esac
done

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

say() { printf '%s\n' "$*"; }
hr()  { printf '%s\n' "────────────────────────────────────────"; }

# ── 认手机 ──────────────────────────────────────────────
ios_connected() {
  [ -x "$VENV_PY" ] || return 1
  "$VENV_PY" -m pymobiledevice3 usbmux list 2>/dev/null | grep -q '"Identifier"'
}

android_connected() {
  command -v adb >/dev/null 2>&1 || return 1
  adb devices 2>/dev/null | grep -qE '\sdevice$'
}

harmony_connected() {
  command -v hdc >/dev/null 2>&1 || return 1
  hdc list targets 2>/dev/null | grep -qvE '^\s*(\[Empty\]|)\s*$'
}

detect() {
  if ios_connected; then echo ios
  elif android_connected; then echo android
  elif harmony_connected; then echo harmony
  else echo none
  fi
}

if [ "$REBUILD" -eq 0 ]; then
  PLATFORM="$(detect)"
  case "$PLATFORM" in
    none)
      say "没找到手机。挑一条对得上的："
      say ""
      say "  iPhone  数据线连上 → 手机解锁 → 屏幕弹「信任此电脑」点信任"
      say "  安卓    设置里打开「开发者选项」→「USB 调试」→ 插线 → 手机上点允许"
      say "  鸿蒙    同上，纯血鸿蒙要装 DevEco Studio 里的 hdc"
      say ""
      exit 3
      ;;
    ios)
      say "认出来了：iPhone"
      hr
      "$VENV_PY" "$HERE/collect_ios.py" "$OUT" || exit $?
      ;;
    android)
      say "认出来了：安卓 / 鸿蒙"
      hr
      bash "$HERE/collect_android.sh" "$OUT" || exit $?
      ;;
    harmony)
      say "认出来了：鸿蒙"
      hr
      bash "$HERE/collect_harmony.sh" "$OUT" || exit $?
      ;;
  esac
fi

# ── 分析 + 出报告 ───────────────────────────────────────
hr
"$PY" "$HERE/analyze.py" "$OUT" || exit $?
"$PY" "$HERE/build_report.py" "$OUT" || exit $?
hr

# ── 下一步 ──────────────────────────────────────────────
PLATFORM_DONE="$("$PY" -c "
import json,sys
try:
    d=json.load(open('$OUT/audit.json'))
    print(d.get('platform',''))
except Exception:
    print('')
")"

say ""
if [ "$PLATFORM_DONE" = "ios" ]; then
  PENDING="$("$PY" -c "
import json
try:
    d=json.load(open('$OUT/audit.json'))
    ms=d.get('manual_checks',[])
    print(sum(1 for x in ms if not x.get('answer') and x.get('tier') != 'optional'))
except Exception:
    print(0)
")"
  if [ "$PENDING" -gt 0 ]; then
    say "报告已经能看了，但还差最后一步：有 $PENDING 项在设置里，机器读不到。"
    say "接下来要做的：在手机上截这 $PENDING 张图，然后重新出一版完整报告。"
  else
    say "全都核完了。报告是完整的。"
  fi
else
  say "报告好了。"
fi
say ""
say "报告：$OUT/report.html"
