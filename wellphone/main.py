from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace

from wellphone.agent.mission_plan import MissionPlan
from wellphone.agent.model_provider import ModelProvider, ScriptedProvider
from wellphone.agent.vlm_agent import VlmAgent
from wellphone.config.settings import Settings, load_settings
from wellphone.device.adb_client import AdbClient
from wellphone.device.frame_source import FrameSource, ScrcpyWindowSource, ScreencapSource
from wellphone.device.virtual_display_runner import VirtualDisplayRunner
from wellphone.executor.action_executor import ActionExecutor
from wellphone.executor.input_channel import InputChannel
from wellphone.guard.take_over_gate import TakeOverGate

PHASE_TASKS = {
    "1": (
        "打开微信，进入最近聊天列表的第一条对话。"
        "在聊天界面底部找到输入框并点击它，"
        "用 Type 动作输入文字「{text}」，"
        "然后点击发送按钮把消息发出去。"
        "必须在聊天界面中看到自己发出的「{text}」消息后，"
        "才能调用 Finish。"
        "如果还没输入和发送消息，不要调用 Finish。"
    ),
    "2": (
        "打开美团，搜索美式咖啡，选择一款加入购物车并进入订单确认页；"
        "一旦页面要求输入密码、支付或验证码，立即用 Take_over 交给用户，"
        "在此之前不要 Finish。"
    ),
}


class DryFrameSource(FrameSource):
    def start(self, display_id: int) -> None:
        return None

    def capture(self) -> bytes:
        return b""

    def stop(self) -> None:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wellphone",
        description="parallel background phone agent on a virtual display",
    )
    parser.add_argument("--task", help="free-form task description")
    parser.add_argument(
        "--phase",
        choices=sorted(PHASE_TASKS),
        default=None,
        help="preset demo task (overrides --task)",
    )
    parser.add_argument("--text", default="收到，好的", help="reply text for phase 1")
    parser.add_argument("--start-app", default=None, help="package to launch on the virtual display")
    parser.add_argument("--serial", default=None, help="adb device serial")
    parser.add_argument(
        "--perception",
        choices=["scrcpy", "screencap"],
        default="scrcpy",
        help="frame source; screencap -d is a D1 experiment and may not work",
    )
    parser.add_argument("--dry-run", action="store_true", help="print commands without executing")
    parser.add_argument("--max-steps", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings: Settings = load_settings()
    overrides = {}
    if args.dry_run:
        overrides["dry_run"] = True
    if args.serial:
        overrides["serial"] = args.serial
    if args.max_steps:
        overrides["max_steps"] = args.max_steps
    if overrides:
        settings = replace(settings, **overrides)

    adb = AdbClient(settings)
    runner = VirtualDisplayRunner(settings, adb)
    display_id = runner.create()
    if args.start_app and not settings.dry_run:
        time.sleep(2.0)
        runner.start_app(args.start_app, display_id)
        time.sleep(3.0)
    frame_source: FrameSource | None = None
    try:
        if settings.dry_run:
            frame_source = DryFrameSource()
            provider = ScriptedProvider(
                [
                    {"name": "Tap", "x": 540, "y": 1600, "reason": "focus input field"},
                    {"name": "Type", "text": args.text},
                    {"name": "Finish", "reason": "message sent"},
                ]
            )
        elif args.perception == "scrcpy":
            frame_source = ScrcpyWindowSource(
                pid=runner.process_pid,
                target_width=settings.display_width,
                target_height=settings.display_height,
            )
            provider = ModelProvider(
                settings.vlm_base_url, settings.vlm_api_key, settings.vlm_model
            )
        else:
            frame_source = ScreencapSource(adb)
            provider = ModelProvider(
                settings.vlm_base_url, settings.vlm_api_key, settings.vlm_model
            )
        frame_source.start(display_id)
        agent = VlmAgent(
            provider, display_id,
            display_width=settings.display_width,
            display_height=settings.display_height,
        )
        gate = TakeOverGate()
        executor = ActionExecutor(adb, runner, InputChannel(adb))

        def ui_dump_provider() -> str:
            if settings.dry_run:
                return ""
            try:
                return adb.ui_dump(display_id)
            except Exception:
                return ""

        plan = MissionPlan(
            frame_source,
            agent,
            gate,
            executor,
            max_steps=settings.max_steps,
            step_interval_s=settings.step_interval_s,
            ui_dump_provider=ui_dump_provider,
        )

        if args.phase:
            task = PHASE_TASKS[args.phase].format(text=args.text)
        elif args.task:
            task = args.task
        else:
            task = PHASE_TASKS["1"].format(text=args.text)

        result = plan.run(task)
        print(f"status={result.status} steps={result.steps} display_id={display_id}")
        for line in result.log:
            print(line)
        return 0 if result.status in ("finish", "take_over") else 1
    finally:
        if frame_source is not None:
            frame_source.stop()
        runner.destroy()


if __name__ == "__main__":
    sys.exit(main())
