import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.config.settings import load_settings

s = load_settings()
env = s.adb_env()

rec = os.path.abspath("workspace/test_vd2.mp4")
if os.path.exists(rec):
    os.remove(rec)

cmd = [
    s.scrcpy_bin,
    "-s", s.serial,
    "--new-display=1080x1920/373",
    "--display-ime-policy=local",
    "--keep-active",
    "--no-audio",
    "-b", "8M",
    "--no-playback",
    "--max-fps=8",
    "--start-app=com.android.settings",
    f"--record={rec}",
]
print("cmd:", " ".join(cmd))
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

for i in range(5):
    time.sleep(3)
    size = os.path.getsize(rec) if os.path.exists(rec) else -1
    print(f"t={3*(i+1)}s size={size}")

proc.terminate()
try:
    out, err = proc.communicate(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
    out, err = proc.communicate()

size = os.path.getsize(rec) if os.path.exists(rec) else -1
print(f"final size={size}")
print("=== stdout ===")
print(out.decode(errors="replace")[-800:])
print("=== stderr ===")
print(err.decode(errors="replace")[-800:])
