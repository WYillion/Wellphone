from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    adb_bin: str = "adb"
    scrcpy_bin: str = "scrcpy"
    serial: str | None = None
    display_width: int = 1080
    display_height: int = 1920
    display_dpi: int = 240
    vlm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    vlm_api_key: str = ""
    vlm_model: str = "autoglm-phone"
    max_steps: int = 40
    step_interval_s: float = 1.5
    dry_run: bool = False


def load_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    return Settings(
        adb_bin=env.get("WELLPHONE_ADB", "adb"),
        scrcpy_bin=env.get("WELLPHONE_SCRCPY", "scrcpy"),
        serial=env.get("WELLPHONE_ADB_SERIAL") or None,
        display_width=int(env.get("WELLPHONE_DISPLAY_WIDTH", "1080")),
        display_height=int(env.get("WELLPHONE_DISPLAY_HEIGHT", "1920")),
        display_dpi=int(env.get("WELLPHONE_DISPLAY_DPI", "240")),
        vlm_base_url=env.get("VLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        vlm_api_key=env.get("VLM_API_KEY", ""),
        vlm_model=env.get("VLM_MODEL", "autoglm-phone"),
        max_steps=int(env.get("MAX_ACTION_STEPS", "40")),
        step_interval_s=float(env.get("WELLPHONE_STEP_INTERVAL", "1.5")),
        dry_run=env.get("WELLPHONE_DRY_RUN", "").lower() in ("1", "true", "yes"),
    )
