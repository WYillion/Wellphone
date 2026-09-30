"""微信 phase 1 端到端测试：打开微信→进入第一条聊天→回复→发送→Finish。

用法:
    python scripts/run_wechat.py [--text "回复内容"] [--steps 15]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.main import main


def build_argv() -> list[str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="收到，好的")
    parser.add_argument("--steps", type=int, default=15)
    args = parser.parse_args()
    return [
        "--phase", "1",
        "--text", args.text,
        "--start-app", "com.tencent.mm",
        "--max-steps", str(args.steps),
    ]


if __name__ == "__main__":
    os.environ.setdefault("WELLPHONE_DEBUG_API", "1")
    os.environ.setdefault("WELLPHONE_SAVE_FRAMES", "workspace/frames_wechat")
    sys.exit(main(build_argv()))
