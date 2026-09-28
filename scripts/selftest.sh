#!/usr/bin/env bash
# Wellphone 自测脚本：验证设备接入与虚拟屏可行性（无需 agent 介入）
# 用法：
#   bash scripts/selftest.sh                 # 连通性自测（工具/设备/信息/display 基线）
#   bash scripts/selftest.sh --full          # 完整 D1：再建虚拟屏 + 注入点击 + 感知测试
#   bash scripts/selftest.sh --full --app com.android.settings
#   bash scripts/selftest.sh --vd --keep      # 只建虚拟屏且不自动关闭
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADB_PORT="${WELLPHONE_ADB_PORT:-5038}"
VD_SIZE="${WELLPHONE_VD_SIZE:-1080x1920/240}"
ADB="$ROOT/.tools/platform-tools/adb.exe"
SCRCPY="$ROOT/.tools/scrcpy-win64-v4.1/scrcpy.exe"
LOG="$ROOT/.tools/scrcpy.log"

DO_FULL=0
DO_VD=0
KEEP=0
APP_PKG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --full) DO_FULL=1; DO_VD=1 ;;
    --vd) DO_VD=1 ;;
    --keep) KEEP=1 ;;
    --app) APP_PKG="${2:-}"; shift ;;
    --size) VD_SIZE="${2:-}"; shift ;;
    --port) ADB_PORT="${2:-}"; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
  shift
done

PASS=0; FAIL=0; WARN=0
SCRCPY_PID=""; VD_ID=""

c_pass() { printf "  \033[32m[PASS]\033[0m %s\n" "$1"; PASS=$((PASS + 1)); }
c_fail() { printf "  \033[31m[FAIL]\033[0m %s\n" "$1"; FAIL=$((FAIL + 1)); }
c_warn() { printf "  \033[33m[WARN]\033[0m %s\n" "$1"; WARN=$((WARN + 1)); }
c_info() { printf "         %s\n" "$1"; }
title()  { printf "\n\033[36m== %s ==\033[0m\n" "$1"; }

run_adb() { "$ADB" -P "$ADB_PORT" "$@" 2>&1; }

cleanup() {
  if [ -n "$SCRCPY_PID" ] && [ "$KEEP" -eq 0 ]; then
    kill "$SCRCPY_PID" 2>/dev/null
    c_info "虚拟屏已关闭（--keep 可保留）"
  fi
}
trap cleanup EXIT

title "1. 工具检查"
for pair in "adb:$ADB" "scrcpy:$SCRCPY"; do
  name="${pair%%:*}"; bin="${pair#*:}"
  if [ -x "$bin" ]; then
    c_pass "$name: $bin"
  elif command -v "$name" >/dev/null 2>&1; then
    c_pass "$name: $(command -v "$name")"
  else
    c_fail "$name 未找到（期望 $bin）"
  fi
done
[ -x "$ADB" ] || { c_fail "adb 不可用，终止"; exit 1; }

title "2. adb server 就绪（自动尝试端口）"
SERVER_OK=0
for try_port in "$ADB_PORT" $((ADB_PORT + 1)) $((ADB_PORT + 2)) 5037; do
  "$ADB" -P "$try_port" kill-server >/dev/null 2>&1 || true
  out="$("$ADB" -P "$try_port" devices 2>&1 || true)"
  if ! printf '%s' "$out" | grep -qE "could not read ok|failed to start daemon"; then
    ADB_PORT="$try_port"; SERVER_OK=1
    c_pass "server 端口 $ADB_PORT"
    break
  fi
  taskkill //f //im adb.exe >/dev/null 2>&1 || true
  sleep 1
done
[ "$SERVER_OK" -eq 1 ] || { c_fail "adb server 启动失败（端口均被占用/残留）"; exit 1; }

title "3. 设备连接状态"
devices_out="$(run_adb devices -l)"
printf "%s\n" "$devices_out" | sed 's/^/         /'
state="$(printf '%s\n' "$devices_out" | sed 1d | grep -oE '(unauthorized|offline|no permissions|device)' | head -1)"
serial="$(printf '%s\n' "$devices_out" | sed 1d | awk 'NF>=2 && $1 !~ /^\(no/ {print $1; exit}')"

case "$state" in
  device)
    c_pass "设备可用（serial=$serial）"
    ;;
  unauthorized)
    c_fail "设备未授权（unauthorized）"
    c_info "→ 手机上点「允许 USB 调试」（勾选始终允许）"
    c_info "→ 不弹窗：开发者选项 →「撤销 USB 调试授权」→ 重插"
    ;;
  offline)
    c_fail "设备离线（offline）：USB 已识别但 adbd 无响应"
    c_info "→ 开发者选项打开「USB 调试（安全设置）」（小米需插卡+登录账号）"
    c_info "→ 拔掉 → 撤销 USB 调试授权 → 重插；换 USB 2.0 口；或重启手机"
    c_info "→ 以上无效就改走无线调试（开发者选项 → 无线调试 → 配对码配对）"
    ;;
  "")
    c_fail "未发现任何设备"
    c_info "→ 下拉通知栏确认 USB 用途 =「传输文件」（仅充电模式下 adb 不可见）"
    c_info "→ 换一根数据线、换 USB 口（直插主板）"
    c_info "→ 或改走无线调试"
    ;;
  *)
    c_warn "未知状态: $state"
    ;;
esac

title "4. 设备信息"
if [ "$state" = "device" ]; then
  model="$(run_adb shell getprop ro.product.model | tr -d '\r')"
  android="$(run_adb shell getprop ro.build.version.release | tr -d '\r')"
  sdk="$(run_adb shell getprop ro.build.version.sdk | tr -d '\r')"
  c_pass "机型: $model / Android $android (SDK $sdk)"
else
  c_warn "设备不可用，跳过（先修好第 3 步）"
fi

title "5. display 基线（记住这些 id）"
if [ "$state" = "device" ]; then
  run_adb shell dumpsys display | grep -E "^Display [0-9]+" | sed 's/^/         /'
  c_pass "已列出 display（Display 0 = 主屏）"
else
  c_warn "跳过"
fi

start_vd() {
  before="$(run_adb shell dumpsys display | grep -oE "^Display [0-9]+" | awk '{print $2}')"
  "$SCRCPY" --new-display="$VD_SIZE" --display-ime-policy=local \
    --keep-active --no-audio -b 8M >"$LOG" 2>&1 &
  SCRCPY_PID=$!
  for _ in $(seq 1 30); do
    sleep 0.5
    kill -0 "$SCRCPY_PID" 2>/dev/null || { c_fail "scrcpy 提前退出，日志: $LOG"; return 1; }
    after="$(run_adb shell dumpsys display | grep -oE "^Display [0-9]+" | awk '{print $2}')"
    new_id="$(printf '%s\n' "$after" | sort -u | grep -vxF "$(printf '%s\n' "$before" | sort -u)" | head -1)"
    if [ -n "$new_id" ]; then VD_ID="$new_id"; return 0; fi
  done
  c_fail "15 秒内未发现新 display"
  return 1
}

if [ "$DO_VD" -eq 1 ] && [ "$state" = "device" ]; then
  title "6. 建虚拟屏（$VD_SIZE）"
  if start_vd; then
    c_pass "虚拟屏已创建，display_id=$VD_ID"
    c_info "→ 现在用手操作手机主屏：打字/滑动/切 App"
    c_info "→ 验收标准：主屏完全正常，虚拟屏窗口里的内容独立变化"

    if [ -n "$APP_PKG" ]; then
      title "7. 在虚拟屏启动 App（$APP_PKG）"
      activity="$(run_adb shell cmd package resolve-activity --brief "$APP_PKG" | tail -1 | tr -d '\r')"
      if printf '%s' "$activity" | grep -q "/"; then
        run_adb shell "am start --display $VD_ID -f 0x10008000 -n $activity" >/dev/null 2>&1
        sleep 3
        focus="$(run_adb shell dumpsys window | grep mCurrentFocus | tr -d '\r')"
        c_pass "已请求启动 $activity"
        c_info "当前主屏焦点: $focus"
        c_info "→ 若主屏焦点仍是用户 App、虚拟屏窗口里出现该 App = 隔离成功"
      else
        c_fail "无法解析 $APP_PKG 的启动 activity"
      fi
    fi

    title "8. 向虚拟屏注入点击（540,960）"
    run_adb shell "input -d $VD_ID tap 540 960" >/dev/null 2>&1
    c_info "已注入；若虚拟屏内容有响应、主屏无反应 = displayId 绑定成功"

    title "9. 感知测试（screencap -d）"
    if run_adb exec-out "screencap -d $VD_ID -p" >"$ROOT/.tools/vd_test.png" 2>/dev/null \
       && head -c 4 "$ROOT/.tools/vd_test.png" 2>/dev/null | grep -q "PNG"; then
      c_pass "screencap -d 可用，截图已存 .tools/vd_test.png"
    else
      c_warn "screencap -d 对虚拟屏无效（已知问题）→ 感知主路径改用 scrcpy 流抽帧"
    fi
  fi
fi

title "汇总"
c_info "PASS=$PASS  FAIL=$FAIL  WARN=$WARN"
if [ "$FAIL" -eq 0 ] && [ "$state" = "device" ]; then
  c_info "环境就绪，可以进入 D1 实测 / 跑项目："
  c_info "  python -m wellphone.main --phase 1 --dry-run"
  exit 0
fi
c_info "设备未就绪（state=${state:-none}），请按上面的 [FAIL]/[WARN] 提示修复后重跑"
exit 1
