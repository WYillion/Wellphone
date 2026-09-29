import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.config.settings import load_settings

s = load_settings()
env = s.adb_env()

for fmt, ext in [("mp4", ".mp4"), ("mkv", ".mkv")]:
    rec = os.path.abspath(f"workspace/test_vd{ext}")
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
        f"--max-fps=8",
        f"--record={rec}",
    ]
    if fmt == "mkv":
        cmd += ["--record-format=mkv"]

    print(f"\n=== testing {fmt} ===")
    print("cmd:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    for i in range(4):
        time.sleep(3)
        size = os.path.getsize(rec) if os.path.exists(rec) else -1
        print(f"  t={3*(i+1)}s size={size}")

    proc.terminate()
    try:
        out, err = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()

    size = os.path.getsize(rec) if os.path.exists(rec) else -1
    print(f"  final size={size}")
    print("  stderr:", err.decode(errors="replace")[-400:])
