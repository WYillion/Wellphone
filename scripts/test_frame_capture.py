import io
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.config.settings import load_settings
from wellphone.device.adb_client import AdbClient
from wellphone.device.virtual_display_runner import VirtualDisplayRunner
from wellphone.device.frame_source import ScrcpyRecordSource

s = load_settings()
print("scrcpy :", s.scrcpy_bin)
print("ffmpeg :", s.ffmpeg_bin)
print("serial :", s.serial)
print("adb    :", s.adb_bin)

adb = AdbClient(s)
runner = VirtualDisplayRunner(s, adb)
did = runner.create(start_app="com.android.settings")
print("display_id =", did)

fs = None
try:
    fs = ScrcpyRecordSource(
        s.scrcpy_bin, s.serial, ffmpeg_bin=s.ffmpeg_bin, env=s.adb_env()
    )
    fs.start(did)
    time.sleep(3)
    png = fs.capture()
    with open("vd_frame.png", "wb") as handle:
        handle.write(png)
    print("captured bytes:", len(png))

    from PIL import Image

    img = Image.open(io.BytesIO(png))
    print("image size:", img.size, "format:", img.format)
finally:
    if fs is not None:
        fs.stop()
    runner.destroy()
