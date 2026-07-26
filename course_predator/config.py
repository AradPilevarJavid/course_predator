"""Default configurations, in order: 1,Environment variable, 2.config.json, 3.constants.py."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_DURATION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    REPLAY_DIR,
    REPLAY_RECORD_RATE,
    SERVER_TICK_RATE,
    STATE_BROADCAST_RATE,
)


CONFIG_PATH_ENV = "COURSE_PREDATOR_CONFIG"


@dataclass(frozen=True)
class Config:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    duration: int = DEFAULT_DURATION
    replay_dir: str = REPLAY_DIR
    server_tick_rate: int = SERVER_TICK_RATE
    state_broadcast_rate: int = STATE_BROADCAST_RATE
    replay_record_rate: int = REPLAY_RECORD_RATE
    log_level: str = "INFO"


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _get_int(values: dict[str, Any], key: str, env_key: str, default: int) -> int:
    raw_value = os.getenv(env_key, values.get(key, default))
    return int(raw_value)


def _get_str(values: dict[str, Any], key: str, env_key: str, default: str) -> str:
    return str(os.getenv(env_key, values.get(key, default)))


def load_config(path: str | Path | None = None) -> Config:
    config_path = Path(path or os.getenv(CONFIG_PATH_ENV, "config.json"))
    values = _read_config_file(config_path)
    return Config(
        host=_get_str(values, "host", "COURSE_PREDATOR_HOST", DEFAULT_HOST),
        port=_get_int(values, "port", "COURSE_PREDATOR_PORT", DEFAULT_PORT),
        duration=_get_int(values, "duration", "COURSE_PREDATOR_DURATION", DEFAULT_DURATION),
        replay_dir=_get_str(values, "replay_dir", "COURSE_PREDATOR_REPLAY_DIR", REPLAY_DIR),
        server_tick_rate=_get_int(
            values,
            "server_tick_rate",
            "COURSE_PREDATOR_SERVER_TICK_RATE",
            SERVER_TICK_RATE,
        ),
        state_broadcast_rate=_get_int(
            values,
            "state_broadcast_rate",
            "COURSE_PREDATOR_STATE_BROADCAST_RATE",
            STATE_BROADCAST_RATE,
        ),
        replay_record_rate=_get_int(
            values,
            "replay_record_rate",
            "COURSE_PREDATOR_REPLAY_RECORD_RATE",
            REPLAY_RECORD_RATE,
        ),
        log_level=_get_str(values, "log_level", "COURSE_PREDATOR_LOG_LEVEL", "INFO"),
    )


def configure_logging(level: str = "INFO") -> None:
    import logging

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
