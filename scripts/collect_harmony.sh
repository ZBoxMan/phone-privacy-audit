#!/usr/bin/env bash
# 鸿蒙手机只读采集
#
# HarmonyOS 分两种：
#   1) HarmonyOS 2/3/4 —— 底座是 AOSP，adb 完全可用，直接复用 Android 采集
#   2) HarmonyOS NEXT（纯血鸿蒙）—— 不再兼容安卓，要用 hdc，能读的信息少很多
#
# 只读：仅使用 getprop/param get/bm dump/aa dump 等查询命令。

set -uo pipefail

OUT="${1:-harmony-audit-$(date +%Y%m%d-%H%M%S)}"
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT/raw"

mark_platform() {
  python3 - "$OUT" "$1" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
layer = sys.argv[2]
p = out / "manifest.json"
m = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
m["platform"] = "harmony"
m["harmony_layer"] = layer
p.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

# ---------- 路线一：AOSP 底座，直接用 adb ----------
if command -v adb >/dev/null 2>&1 && adb devices 2>/dev/null | awk 'NR>1 && $2=="device"' | grep -q .; then
  echo "检测到 HarmonyOS（AOSP 底座），按安卓方式采集…"
  bash "$DIR/collect_android.sh" "$OUT"
  mark_platform "aosp"
  echo "提示：这类机型的检查能力与安卓一致。"
  exit 0
fi

# ---------- 路线二：HarmonyOS NEXT，用 hdc ----------
if ! command -v hdc >/dev/null 2>&1; then
  cat >&2 <<'MSG'
ERROR: 没有可用的设备连接方式。

HarmonyOS NEXT 需要 hdc 工具，它随 DevEco Studio 一起安装：
  https://developer.huawei.com/consumer/cn/deveco-studio/

装好后把 hdc 加入 PATH，路径通常是：
  /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc

手机侧需要打开：设置 → 系统 → 开发者选项 → USB 调试。
MSG
  exit 3
fi

if ! hdc list targets 2>/dev/null | grep -qE '^[A-Za-z0-9]'; then
  echo "ERROR: hdc 没有检测到设备，请检查数据线与「USB 调试」开关。" >&2
  hdc list targets >&2
  exit 3
fi

OK=()
FAIL=()
grab() {
  local name="$1"; shift
  if hdc shell "$@" > "$OUT/raw/$name.txt" 2>/dev/null; then
    if [ -s "$OUT/raw/$name.txt" ]; then OK+=("$name"); else FAIL+=("$name:empty"); fi
  else
    FAIL+=("$name:cmd_failed")
  fi
}

grab prop_brand        param get const.product.brand
grab prop_model        param get const.product.model
grab prop_release      param get const.product.software.version
grab prop_sdk          param get const.ohos.apiversion
grab prop_fingerprint  param get const.product.name
grab bundles           bm dump -a
grab running           aa dump -a

# 鸿蒙 NEXT 上 bm dump 单个包的开销很大，只对数量做统计，不逐个拉详情
{
  echo "{"
  echo "  \"platform\": \"harmony\","
  echo "  \"harmony_layer\": \"next\","
  echo "  \"serial\": \"$(hdc list targets 2>/dev/null | head -1)\","
  echo "  \"collected_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"ok\": [$(printf '"%s",' "${OK[@]}" | sed 's/,$//')],"
  echo "  \"failed\": [$(printf '"%s",' "${FAIL[@]}" | sed 's/,$//')]"
  echo "}"
} > "$OUT/manifest.json"

echo "采集完成: $OUT"
echo "成功 $(( ${#OK[@]} )) 项 / 失败 $(( ${#FAIL[@]} )) 项"
echo "提示：纯血鸿蒙能读到的信息有限，报告会以手工核对为主。"
