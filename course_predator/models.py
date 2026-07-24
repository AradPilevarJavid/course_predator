"""Core OOP model classes shared by the server and renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

from .constants import CANVAS_HEIGHT, CANVAS_WIDTH
from .protocol import clamp
from .types import PlayerState, ShapeDict


@dataclass
class Shape:
    shape_id: str
    x: float
    y: float
    radius: float
    points: int
    lifetime: float
    spawn_time: float
    kind: str = "normal"

    @property # the result (function output) is the property of the function.
    def expires_at(self) -> float:
        return self.spawn_time + self.lifetime

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at

    # def contains(self, x: float, y: float) -> bool:
    #     return sqrt((self.x - x)**2, (self.y - y)**2) <= self.radius

    def contains(self, x: float, y: float) -> bool:
        return hypot(self.x - x, self.y - y) <= self.radius

    def to_dict(self, now: float) -> ShapeDict:
        return {
            "id": self.shape_id,
            "kind": self.kind,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "radius": self.radius,
            "points": self.points,
            "ttl": max(0.0, round(self.expires_at - now, 3)),
            "lifetime": self.lifetime,
        }


class NormalShape(Shape):
    def __init__(
        self,
        shape_id: str,
        x: float,
        y: float,
        radius: float,
        points: int,
        lifetime: float,
        spawn_time: float,
    ) -> None:
        super().__init__(shape_id, x, y, radius, points, lifetime, spawn_time, "normal")


class ShieldShape(Shape):
    def __init__(
        self,
        shape_id: str,
        x: float,
        y: float,
        radius: float,
        lifetime: float,
        spawn_time: float,
    ) -> None:
        super().__init__(shape_id, x, y, radius, 0, lifetime, spawn_time, "shield")


class IceShape(Shape):
    def __init__(
        self,
        shape_id: str,
        x: float,
        y: float,
        radius: float,
        lifetime: float,
        spawn_time: float,
    ) -> None:
        super().__init__(shape_id, x, y, radius, 0, lifetime, spawn_time, "ice")


class IllusionShape(Shape):
    def __init__(
        self,
        shape_id: str,
        x: float,
        y: float,
        radius: float,
        points: int,
        lifetime: float,
        spawn_time: float,
    ) -> None:
        super().__init__(shape_id, x, y, radius, points, lifetime, spawn_time, "illusion")


@dataclass
class Player:
    player_id: int
    name: str
    score: float = 0.0
    stamina: float = 100.0
    stress: float = 0.0
    shield_until: float = 0.0
    frozen_until: float = 0.0
    last_click_time: float = 0.0
    next_stamina_regen: float = 0.0
    next_stress_recovery: float = 0.0
    next_illusion_spawn: float = 0.0
    hidden_shape_ids: set[str] = field(default_factory=set)
    mouse_x: float = CANVAS_WIDTH / 2
    mouse_y: float = CANVAS_HEIGHT / 2
    connected: bool = True

    def start_timers(self, now: float) -> None:
        self.last_click_time = now
        self.next_stamina_regen = now + 2.0
        self.next_stress_recovery = now + 2.0
        self.next_illusion_spawn = now + 2.0

    def is_frozen(self, now: float) -> bool:
        return now < self.frozen_until

    def is_shielded(self, now: float) -> bool:
        return now < self.shield_until

    def is_exhausted(self) -> bool:
        return self.stamina <= 10.0

    def change_stamina(self, amount: float) -> None:
        self.stamina = clamp(self.stamina + amount, 0.0, 100.0)

    def change_stress(self, amount: float) -> None:
        self.stress = clamp(self.stress + amount, 0.0, 100.0)

    def apply_click_cost(self, now: float, amount: float) -> None:
        self.last_click_time = now
        self.next_stamina_regen = now + 2.0
        if amount:
            self.change_stamina(-amount)

    def extend_shield(self, now: float, seconds: float) -> None:
        self.shield_until = max(now, self.shield_until) + seconds

    def extend_freeze(self, now: float, seconds: float) -> None:
        self.frozen_until = max(now, self.frozen_until) + seconds

    def set_mouse(self, x: float, y: float) -> None:
        self.mouse_x = clamp(x, 0.0, float(CANVAS_WIDTH))
        self.mouse_y = clamp(y, 0.0, float(CANVAS_HEIGHT))

    def to_public(self, now: float) -> PlayerState:
        return {
            "id": self.player_id,
            "name": self.name,
            "score": round(self.score, 2),
            "stamina": round(self.stamina, 2),
            "stress": round(self.stress, 2),
            "shield": max(0.0, round(self.shield_until - now, 2)),
            "frozen": max(0.0, round(self.frozen_until - now, 2)),
            "connected": self.connected,
            "mouse": [round(self.mouse_x, 1), round(self.mouse_y, 1)],
        }
