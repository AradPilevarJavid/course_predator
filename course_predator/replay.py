"""JSON replay writer/loader for finished matches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import REPLAY_DIR
from .types import GameState


class ReplayRecorder:
    """Stores compact snapshots so the match can be watched later."""

    def __init__(self, enabled: bool = True, replay_dir: str | Path = REPLAY_DIR) -> None:
        self.enabled = enabled
        self.replay_dir = Path(replay_dir)
        self.frames: list[dict[str, Any]] = []
        self.started_at = 0.0
        self.last_recorded_at = 0.0

    def start(self, now: float) -> None:
        self.frames.clear()
        self.started_at = now
        self.last_recorded_at = 0.0

    def record(self, now: float, state: GameState) -> None:
        if not self.enabled:
            return
        relative_time = round(now - self.started_at, 3)
        self.frames.append({"t": relative_time, "state": state})
        self.last_recorded_at = now

    def save(self, duration: int, winner: int | None) -> str:
        if not self.enabled or not self.frames:
            return ""
        self.replay_dir.mkdir(exist_ok=True)
        filename = self.replay_dir / f"match_{int(self.started_at)}.json"
        payload = {
            "format": "course-predator-replay-v1",
            "duration": duration,
            "winner": winner,
            "frames": self.frames,
        }
        filename.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(filename)


def load_replay(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
