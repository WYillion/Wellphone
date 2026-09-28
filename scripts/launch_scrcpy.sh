#!/bin/bash
export ADB="D:/Documents/AI learning/Wellphone/.tools/platform-tools/adb.exe"
export ANDROID_ADB_SERVER_PORT=5038
exec "D:/Documents/AI learning/Wellphone/.tools/scrcpy-win64-v4.1/scrcpy.exe" \
  -s 192.168.1.101:42883 \
  --new-display=1080x1920 \
  --no-audio \
  --stay-awake
