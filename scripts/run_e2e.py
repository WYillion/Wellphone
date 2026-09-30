"""端到端测试运行器，避免命令行中文转义问题。

用法:
    python scripts/run_e2e.py [--task "任务描述"] [--app com.android.settings] [--steps 5]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wellphone.main import main

DEFAULT_TASK = "点击设置页面里的WLAN选项，进入WLAN设置页面，进入后调用Finish"


def build_argv() -> list[str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--app", default="com.android.settings")
    parser.add_argument("--steps", type=int, default=5)
    args = parser.parse_args()
    return [
        "--task", args.task,
        "--start-app", args.app,
        "--max-steps", str(args.steps),
    ]


if __name__ == "__main__":
    os.environ.setdefault("WELLPHONE_DEBUG_API", "1")
    os.environ.setdefault("WELLPHONE_SAVE_FRAMES", "workspace/frames")
    sys.exit(main(build_argv()))
