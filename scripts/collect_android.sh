#!/usr/bin/env bash
# 手机隐私与安全审计 - 只读采集器
# 严格只读：仅使用 getprop / pm list / dumpsys / settings get / cat /proc/net / cmd package query-*
# 本脚本不包含任何 uninstall、disable、set、put、clear、force-stop 命令。
#
# 用法:
#   ./collect.sh [输出目录] [设备序列号]
# 输出:
#   <输出目录>/raw/*.txt        原始输出
#   <输出目录>/manifest.json    采集清单与完整度

set -uo pipefail

OUT="${1:-android-audit-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT/raw"

if ! command -v adb >/dev/null 2>&1; then
  echo "ERROR: 未找到 adb。安装: brew install android-platform-tools" >&2
  exit 2
fi

adb start-server >/dev/null 2>&1
COUNT=$(adb devices | awk 'NR>1 && $2=="device"' | wc -l | tr -d ' ')
if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: 没有已授权的设备。请检查 USB 调试与授权弹窗。" >&2
  adb devices -l >&2
  exit 3
fi

SERIAL="${2:-$(adb devices | awk 'NR>1 && $2=="device"{print $1; exit}')}"

TO=""
command -v gtimeout >/dev/null 2>&1 && TO="gtimeout 90"
if [ -z "$TO" ] && command -v timeout >/dev/null 2>&1; then TO="timeout 90"; fi

run_adb() {
  if [ -n "$TO" ]; then $TO adb -s "$SERIAL" shell "$@"; else adb -s "$SERIAL" shell "$@"; fi
}

OK=()
FAIL=()
grab() {
  local name="$1"; shift
  local errf="$OUT/raw/$name.err"
  if run_adb "$@" > "$OUT/raw/$name.txt" 2>"$errf"; then
    local sz
    sz=$(wc -c < "$OUT/raw/$name.txt" | tr -d ' ')
    if [ "$sz" -gt 0 ]; then OK+=("$name"); else FAIL+=("$name:empty"); fi
  else
    FAIL+=("$name:cmd_failed")
  fi
}

# ---------- 设备与系统 ----------
grab prop_brand        getprop ro.product.brand
grab prop_model        getprop ro.product.model
grab prop_manufacturer getprop ro.product.manufacturer
grab prop_release      getprop ro.build.version.release
grab prop_sdk          getprop ro.build.version.sdk
grab prop_security     getprop ro.build.version.security_patch
grab prop_fingerprint  getprop ro.build.fingerprint
grab prop_serial       getprop ro.serialno
grab users             pm list users

# ---------- 应用清单 ----------
grab packages_all      pm list packages -f -U --user 0
grab packages_third    pm list packages -3
grab packages_system   pm list packages -s
grab packages_disabled pm list packages -d
grab launcher_entries  cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER
grab boot_receivers    cmd package query-receivers --brief -a android.intent.action.BOOT_COMPLETED
grab default_home      cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME
grab default_input     settings get secure default_input_method
grab admins_apps       cmd package query-receivers --brief -a android.app.action.DEVICE_ADMIN_ENABLED

# ---------- 包详情（体积最大，解析来源、安装时间、权限）----------
grab package_dump      dumpsys package

# ---------- 高危权限开关 ----------
grab device_policy     dumpsys device_policy
grab accessibility     settings get secure enabled_accessibility_services
grab notif_listeners   settings get secure enabled_notification_listeners
grab appops_dump       dumpsys appops
grab deviceidle        dumpsys deviceidle whitelist
grab power_whitelist   settings get global low_power_whitelist

# ---------- 网络外联 ----------
grab net_tcp           cat /proc/net/tcp
grab net_tcp6          cat /proc/net/tcp6
grab net_udp           cat /proc/net/udp
grab net_udp6          cat /proc/net/udp6
grab proxy             settings get global http_proxy

# ---------- 清单 ----------
{
  echo "{"
  echo "  \"serial\": \"$SERIAL\","
  echo "  \"collected_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"adb_version\": \"$(adb version 2>/dev/null | head -1 | sed 's/"/\\"/g')\","
  echo "  \"ok\": [$(printf '"%s",' "${OK[@]}" | sed 's/,$//')],"
  echo "  \"failed\": [$(printf '"%s",' "${FAIL[@]}" | sed 's/,$//')]"
  echo "}"
} > "$OUT/manifest.json"

echo "采集完成: $OUT"
echo "成功 $(( ${#OK[@]} )) 项 / 失败 $(( ${#FAIL[@]} )) 项"
if [ ${#FAIL[@]} -gt 0 ]; then
  echo "失败项: ${FAIL[*]}"
fi
