#!/usr/bin/env bash
_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$_root/.tools/platform-tools:$_root/.tools/scrcpy-win64-v4.1:$PATH"
export WELLPHONE_ADB="$_root/.tools/platform-tools/adb.exe"
export WELLPHONE_SCRCPY="$_root/.tools/scrcpy-win64-v4.1/scrcpy.exe"
echo "adb -> $(command -v adb)"
echo "scrcpy -> $(command -v scrcpy)"
