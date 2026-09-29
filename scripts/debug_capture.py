import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.config.settings import load_settings
from wellphone.device.adb_client import AdbClient
from wellphone.device.virtual_display_runner import VirtualDisplayRunner
from wellphone.device.frame_source import MkvFileSource, FrameSourceError

s = load_settings()
adb = AdbClient(s)
runner = VirtualDisplayRunner(s, adb)

rec = os.path.abspath("workspace/debug_rec.mkv")
if os.path.exists(rec):
    os.remove(rec)

did = runner.create(start_app="com.android.settings", record_path=rec, fps=8)
print("display_id =", did)

source = MkvFileSource(rec, ffmpeg_bin=s.ffmpeg_bin)
source.start(did)

for i in range(6):
    time.sleep(3)
    size = os.path.getsize(rec) if os.path.exists(rec) else -1
    print(f"t={3*(i+1)}s record size: {size}")
    if size > 0:
        try:
            frame = source.capture()
            print(f"  frame captured: {len(frame)} bytes")
        except FrameSourceError as exc:
            print(f"  capture failed: {exc}")

source.stop()
runner.destroy()
