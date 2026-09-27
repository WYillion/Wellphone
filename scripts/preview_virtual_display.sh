#!/usr/bin/env bash
set -euo pipefail

DISPLAY_ID="${1:?usage: preview_virtual_display.sh <display_id>}"

scrcpy --display-id="$DISPLAY_ID" --no-audio --stay-awake -b8M
