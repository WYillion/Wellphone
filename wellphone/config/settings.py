from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    adb_bin: str = "adb"
    adb_port: int = 5037
    scrcpy_bin: str = "scrcpy"
    ffmpeg_bin: str = "ffmpeg"
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

    def adb_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["ADB"] = self.adb_bin
        env["ANDROID_ADB_SERVER_PORT"] = str(self.adb_port)
        return env


def _load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _resolve_ffmpeg(env: dict[str, str]) -> str:
    explicit = env.get("WELLPHONE_FFMPEG")
    if explicit:
        return explicit
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def load_settings(env: dict[str, str] | None = None) -> Settings:
    if env is None:
        merged = _load_dotenv()
        merged.update(os.environ)
        env = merged
    return Settings(
        adb_bin=env.get("WELLPHONE_ADB", "adb"),
        adb_port=int(env.get("WELLPHONE_ADB_PORT", "5037")),
        scrcpy_bin=env.get("WELLPHONE_SCRCPY", "scrcpy"),
        ffmpeg_bin=_resolve_ffmpeg(env),
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
