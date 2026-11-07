"""Virtual mouse controller and calibration logic."""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

import pygame

from ..constants import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CURSOR_JUMP_INTERVAL,
    MOUSE_SLOWDOWN_HEAVY,
    MOUSE_SLOWDOWN_LIGHT,
)
from ..protocol import clamp
from ..types import PlayerState

CALIBRATION_FILE = Path.home() / ".course_predator_mouse.json"
CALIBRATION_SECONDS = 1.5
MIN_CALIBRATION_SAMPLES = 20


class MouseController:
    """Virtual cursor driven by calibrated relative movement and stress effects."""

    def __init__(self) -> None:
        self.x = CANVAS_WIDTH / 2
        self.y = CANVAS_HEIGHT / 2
        self.baseline_ratio = self._load_baseline()
        self.calibrating = self.baseline_ratio is None
        self._calibration_started = 0.0
        self._samples: list[float] = []
        self._last_jump = 0.0
        self.trail: list[tuple[float, float, float]] = []
        if self.baseline_ratio is None:
            self.baseline_ratio = 1.0

    def begin_calibration(self, now: float | None = None) -> None:
        self.calibrating = True
        self._calibration_started = now if now is not None else time.monotonic()
        self._samples.clear()

    def ensure_calibration_started(self, now: float) -> None:
        if self.calibrating and not self._calibration_started:
            self.begin_calibration(now)

    def calibration_progress(self, now: float) -> float:
        if not self.calibrating:
            return 1.0
        if not self._calibration_started:
            return 0.0
        return clamp((now - self._calibration_started) / CALIBRATION_SECONDS, 0.0, 1.0)

    def tick_calibration(self, now: float) -> None:
        if self.calibrating and self._calibration_started and now - self._calibration_started >= CALIBRATION_SECONDS:
            self.finish_calibration()

    def handle_calibration_event(self, event: pygame.event.Event, now: float) -> None:
        if not self.calibrating:
            return
        if not self._calibration_started:
            self._calibration_started = now
        raw_dx, raw_dy = pygame.mouse.get_rel()
        raw_distance = math.hypot(raw_dx, raw_dy)
        visible_dx, visible_dy = getattr(event, "rel", (0, 0))
        visible_distance = math.hypot(visible_dx, visible_dy)
        if raw_distance > 1.0 and visible_distance > 1.0:
            self._samples.append(visible_distance / raw_distance)
        if now - self._calibration_started >= CALIBRATION_SECONDS:
            self.finish_calibration()

    def finish_calibration(self) -> None:
        if len(self._samples) >= MIN_CALIBRATION_SAMPLES:
            sorted_samples = sorted(self._samples)
            trim = max(1, len(sorted_samples) // 10)
            trimmed = sorted_samples[trim:-trim] if len(sorted_samples) > trim * 2 else sorted_samples
            self.baseline_ratio = clamp(statistics.median(trimmed), 0.2, 5.0)
            self._save_baseline(self.baseline_ratio)
        self.calibrating = False

    def stress_speed_factor(self, stress: float) -> float:
        if stress >= 51.0:
            return MOUSE_SLOWDOWN_HEAVY
        if stress >= 11.0:
            return MOUSE_SLOWDOWN_LIGHT
        return 1.0

    def move_from_event(self, event: pygame.event.Event, player_state: PlayerState, now: float) -> None:
        raw_dx, raw_dy = pygame.mouse.get_rel()
        if raw_dx == 0 and raw_dy == 0:
            raw_dx, raw_dy = getattr(event, "rel", (0, 0))
        stress = float(player_state.get("stress", 0.0))
        speed_factor = self.stress_speed_factor(stress)
        if float(player_state.get("frozen", 0.0)) > 0.0 or float(player_state.get("stamina", 100.0)) <= 10.0:
            speed_factor = 0.0
        self.x = clamp(self.x + raw_dx * self.baseline_ratio * speed_factor, 0.0, float(CANVAS_WIDTH))
        self.y = clamp(self.y + raw_dy * self.baseline_ratio * speed_factor, 0.0, float(CANVAS_HEIGHT))
        if stress >= 51.0:
            self.trail.append((self.x, self.y, now))
            self.trail = [item for item in self.trail if now - item[2] < 0.45]

    def update_jumps(self, stress: float, now: float) -> None:
        if stress < 31.0:
            return
        if now - self._last_jump >= CURSOR_JUMP_INTERVAL:
            self._last_jump = now
            self.x = clamp(self.x + pygame.Vector2(1, 0).rotate(pygame.time.get_ticks() % 360).x * 45, 0, CANVAS_WIDTH)
            self.y = clamp(
                self.y + pygame.Vector2(0, 1).rotate((pygame.time.get_ticks() * 2) % 360).y * 35, 0, CANVAS_HEIGHT
            )

    def _load_baseline(self) -> float | None:
        try:
            payload = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
            return clamp(float(payload["baseline_ratio"]), 0.2, 5.0)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _save_baseline(self, baseline_ratio: float) -> None:
        try:
            CALIBRATION_FILE.write_text(json.dumps({"baseline_ratio": baseline_ratio}), encoding="utf-8")
        except OSError:
            pass
