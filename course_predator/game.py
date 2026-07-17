"""Authoritative server-side game rules and state transitions."""

from __future__ import annotations

import math
import random
import threading

from .constants import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    ICE_SECONDS,
    ILLUSION_RADIUS,
    MAX_REAL_SHAPES,
    NEGATIVE_VALUES,
    NORMAL_RADIUS,
    NORMAL_VALUES,
    POSITIVE_LOW_VALUES,
    POSITIVE_MEDIUM_VALUES,
    SHIELD_SECONDS,
    SPECIAL_RADIUS,
    STAMINA_CLICK_COST,
    STAMINA_REGEN_AMOUNT,
    STAMINA_REGEN_INTERVAL,
    STRESS_RECOVERY_AMOUNT,
    STRESS_RECOVERY_INTERVAL,
)
from .models import IceShape, IllusionShape, NormalShape, Player, Shape, ShieldShape
from .types import EventDict, GameState, ShapeDict


class Game:
    """Authoritative match state; all public methods are protected by self.lock."""

    def __init__(self, duration: int) -> None:
        self.duration = duration
        self.players: dict[int, Player] = {}
        self.real_shapes: dict[str, Shape] = {}
        self.illusions: dict[int, dict[str, IllusionShape]] = {1: {}, 2: {}}
        self.lock = threading.RLock()
        self.random = random.Random()
        self.active = False
        self.ended = False
        self.start_time = 0.0
        self.end_time = 0.0
        self.next_shape_spawn = 0.0
        self.shape_counter = 0
        self.event_counter = 0
        self.recent_events: list[EventDict] = []
        self.winner_id: int | None = None
        self.end_reason = ""
        self.replay_file = ""

    def add_player(self, player_id: int, name: str, now: float) -> Player:
        player = Player(player_id, name[:24] or f"Player {player_id}")
        player.start_timers(now)
        self.players[player_id] = player
        return player

    def remove_waiting_player(self, player_id: int) -> None:
        if not self.active and not self.ended:
            self.players.pop(player_id, None)

    def mark_disconnected(self, player_id: int, now: float) -> None:
        player = self.players.get(player_id)
        if not player:
            return
        player.connected = False
        if self.active and not self.ended:
            opponent_id = 1 if player_id == 2 else 2
            self._finish(now, f"{player.name} disconnected", opponent_id)

    def can_start(self) -> bool:
        return len(self.players) == 2 and not self.active and not self.ended

    def start(self, now: float) -> bool:
        if not self.can_start():
            return False
        self.active = True
        self.ended = False
        self.start_time = now
        self.end_time = now + self.duration
        self.next_shape_spawn = now + 0.8
        self.real_shapes.clear()
        self.illusions = {1: {}, 2: {}}
        self.recent_events.clear()
        for player in self.players.values():
            player.score = 0.0
            player.stamina = 100.0
            player.stress = 0.0
            player.hidden_shape_ids.clear()
            player.connected = True
            player.start_timers(now)
        return True

    def update(self, now: float) -> bool:
        if not self.active:
            self._prune_events(now)
            return False

        self._expire_shapes(now)
        self._update_players(now)
        self._spawn_real_shapes(now)
        self._spawn_illusions(now)

        if now >= self.end_time:
            self._finish(now, "Time expired", None)
            return True
        self._prune_events(now)
        return False

    def handle_click(self, player_id: int, x: float, y: float, now: float) -> EventDict:
        player = self.players.get(player_id)
        if not player or not self.active or self.ended:
            return self._event(now, "blocked", player_id, x, y, "Match is not active")

        player.set_mouse(x, y)

        if player.is_frozen(now):
            return self._event(now, "blocked", player_id, x, y, "Frozen")
        if player.is_exhausted():
            return self._event(now, "blocked", player_id, x, y, "Exhausted")

        shape = self._find_clicked_real_shape(player, x, y)
        if shape:
            del self.real_shapes[shape.shape_id]
            return self._apply_shape_click(player, shape, now, x, y)

        illusion = self._find_clicked_illusion(player_id, x, y)
        if illusion:
            del self.illusions[player_id][illusion.shape_id]
            return self._apply_illusion_click(player, illusion, now, x, y)

        player.apply_click_cost(now, STAMINA_CLICK_COST)
        player.change_stress(5.0)
        return self._event(now, "empty", player_id, x, y, "+5 stress")

    def update_mouse(self, player_id: int, x: float, y: float) -> None:
        player = self.players.get(player_id)
        if player:
            player.set_mouse(x, y)

    def to_state(
        self,
        now: float,
        recipient_player_id: int | None = None,
        spectator: bool = False,
    ) -> GameState:
        return {
            "type": "state",
            "active": self.active,
            "ended": self.ended,
            "duration": self.duration,
            "time_left": max(0.0, round(self.end_time - now, 2)) if self.active else 0.0,
            "winner": self.winner_id,
            "reason": self.end_reason,
            "replay_file": self.replay_file,
            "players": {
                str(player_id): player.to_public(now)
                for player_id, player in sorted(self.players.items())
            },
            "shapes": self.visible_shapes(now, recipient_player_id, spectator),
            "events": [dict(event) for event in self.recent_events],
            "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
        }

    def visible_shapes(
        self,
        now: float,
        recipient_player_id: int | None,
        spectator: bool = False,
    ) -> list[ShapeDict]:
        shapes: list[Shape] = []
        if spectator or recipient_player_id is None:
            shapes.extend(self.real_shapes.values())
        else:
            player = self.players.get(recipient_player_id)
            if player:
                shapes.extend(
                    shape
                    for shape in self.real_shapes.values()
                    if self._shape_visible_to_player(shape, player)
                )
                shapes.extend(self.illusions.get(recipient_player_id, {}).values())
        return [shape.to_dict(now) for shape in sorted(shapes, key=lambda item: item.spawn_time)]

    def _apply_shape_click(
        self,
        player: Player,
        shape: Shape,
        now: float,
        x: float,
        y: float,
    ) -> EventDict:
        if shape.kind == "shield":
            player.extend_shield(now, SHIELD_SECONDS)
            return self._event(now, "shield", player.player_id, x, y, "+5s shield")

        if shape.kind == "ice":
            player.apply_click_cost(now, STAMINA_CLICK_COST)
            opponent = self.players.get(1 if player.player_id == 2 else 2)
            if opponent:
                opponent.extend_freeze(now, ICE_SECONDS)
            return self._event(now, "ice", player.player_id, x, y, "Opponent frozen")

        high_stamina = player.stamina >= 90.0
        player.apply_click_cost(now, STAMINA_CLICK_COST)
        score_delta = self._score_delta_for(player, shape.points, high_stamina, now)
        stress_delta = self._stress_delta_for(shape.points, high_stamina)
        player.score += score_delta
        player.change_stress(stress_delta)
        label = f"{score_delta:+g} score"
        return self._event(now, "hit", player.player_id, x, y, label, shape.points)

    def _apply_illusion_click(
        self,
        player: Player,
        illusion: IllusionShape,
        now: float,
        x: float,
        y: float,
    ) -> EventDict:
        high_stamina = player.stamina >= 90.0
        player.apply_click_cost(now, STAMINA_CLICK_COST)
        player.change_stress(self._stress_delta_for(illusion.points, high_stamina))
        return self._event(now, "illusion", player.player_id, x, y, "Illusion: no score")

    def _score_delta_for(
        self,
        player: Player,
        points: int,
        high_stamina: bool,
        now: float,
    ) -> float:
        if points > 0 and high_stamina:
            return float(points * 2)
        if points < 0:
            if player.is_shielded(now):
                return 0.0
            if high_stamina:
                return points / 2.0
        return float(points)

    def _stress_delta_for(self, points: int, high_stamina: bool) -> float:
        if points < 0:
            return -3.0
        if high_stamina:
            return -5.0
        if points in POSITIVE_LOW_VALUES:
            return 1.0
        return 3.0

    def _update_players(self, now: float) -> None:
        for player in self.players.values():
            if player.is_frozen(now):
                player.next_stamina_regen = now + STAMINA_REGEN_INTERVAL
                player.next_stress_recovery = now + STRESS_RECOVERY_INTERVAL
                continue

            while now >= player.next_stamina_regen:
                if now - player.last_click_time >= STAMINA_REGEN_INTERVAL:
                    player.change_stamina(STAMINA_REGEN_AMOUNT)
                player.next_stamina_regen += STAMINA_REGEN_INTERVAL

            if player.stamina >= 90.0:
                while now >= player.next_stress_recovery:
                    player.change_stress(-STRESS_RECOVERY_AMOUNT)
                    player.next_stress_recovery += STRESS_RECOVERY_INTERVAL
            else:
                player.next_stress_recovery = now + STRESS_RECOVERY_INTERVAL

    def _spawn_real_shapes(self, now: float) -> None:
        if len(self.real_shapes) >= MAX_REAL_SHAPES:
            self.next_shape_spawn = max(self.next_shape_spawn, now + 0.2)
            return

        while now >= self.next_shape_spawn and len(self.real_shapes) < MAX_REAL_SHAPES:
            shape = self._make_random_real_shape(now)
            self.real_shapes[shape.shape_id] = shape
            self._assign_visibility_for_new_shape(shape)
            self.next_shape_spawn = now + self.random.uniform(0.45, 1.05)

    def _make_random_real_shape(self, now: float) -> Shape:
        self.shape_counter += 1
        shape_id = f"s{self.shape_counter}"
        x = self.random.uniform(55, CANVAS_WIDTH - 55)
        y = self.random.uniform(55, CANVAS_HEIGHT - 55)
        lifetime = self.random.uniform(1.8, 3.4)
        roll = self.random.random()
        if roll < 0.76:
            return NormalShape(shape_id, x, y, NORMAL_RADIUS, self.random.choice(NORMAL_VALUES), lifetime, now)
        if roll < 0.88:
            return ShieldShape(shape_id, x, y, SPECIAL_RADIUS, lifetime, now)
        return IceShape(shape_id, x, y, SPECIAL_RADIUS, lifetime, now)

    def _assign_visibility_for_new_shape(self, shape: Shape) -> None:
        for player in self.players.values():
            chance = 0.0
            if 40.0 <= player.stamina < 60.0:
                chance = 0.22
            elif 10.0 < player.stamina < 40.0:
                chance = 0.48
            elif player.stamina <= 10.0:
                chance = 1.0
            if self.random.random() < chance:
                player.hidden_shape_ids.add(shape.shape_id)

    def _spawn_illusions(self, now: float) -> None:
        for player_id, player in self.players.items():
            illusions = self.illusions.setdefault(player_id, {})
            for shape_id in [sid for sid, shape in illusions.items() if shape.is_expired(now)]:
                del illusions[shape_id]

            if player.stress < 51.0 or player.is_frozen(now) or len(illusions) >= 6:
                player.next_illusion_spawn = max(player.next_illusion_spawn, now + 0.4)
                continue

            if now < player.next_illusion_spawn:
                continue

            self.shape_counter += 1
            shape_id = f"i{player_id}-{self.shape_counter}"
            illusions[shape_id] = IllusionShape(
                shape_id,
                self.random.uniform(55, CANVAS_WIDTH - 55),
                self.random.uniform(55, CANVAS_HEIGHT - 55),
                ILLUSION_RADIUS,
                self.random.choice(POSITIVE_LOW_VALUES + POSITIVE_MEDIUM_VALUES),
                self.random.uniform(1.4, 2.3),
                now,
            )
            interval = self.random.uniform(0.65, 1.15) if player.stress >= 70.0 else self.random.uniform(1.4, 2.4)
            player.next_illusion_spawn = now + interval

    def _expire_shapes(self, now: float) -> None:
        expired_real = [shape_id for shape_id, shape in self.real_shapes.items() if shape.is_expired(now)]
        for shape_id in expired_real:
            del self.real_shapes[shape_id]
        for player in self.players.values():
            player.hidden_shape_ids.difference_update(expired_real)

        for player_id, shapes in self.illusions.items():
            expired = [shape_id for shape_id, shape in shapes.items() if shape.is_expired(now)]
            for shape_id in expired:
                del shapes[shape_id]

    def _find_clicked_real_shape(self, player: Player, x: float, y: float) -> Shape | None:
        for shape in sorted(self.real_shapes.values(), key=lambda item: item.spawn_time, reverse=True):
            if self._shape_visible_to_player(shape, player) and shape.contains(x, y):
                return shape
        return None

    def _find_clicked_illusion(self, player_id: int, x: float, y: float) -> IllusionShape | None:
        for shape in sorted(
            self.illusions.get(player_id, {}).values(),
            key=lambda item: item.spawn_time,
            reverse=True,
        ):
            if shape.contains(x, y):
                return shape
        return None

    def _shape_visible_to_player(self, shape: Shape, player: Player) -> bool:
        if player.stamina >= 60.0:
            return True
        return shape.shape_id not in player.hidden_shape_ids

    def _finish(self, now: float, reason: str, forced_winner: int | None) -> None:
        self.active = False
        self.ended = True
        self.end_time = now
        self.end_reason = reason
        if forced_winner is not None:
            self.winner_id = forced_winner
        else:
            ordered = sorted(self.players.values(), key=lambda player: player.score, reverse=True)
            if len(ordered) >= 2 and ordered[0].score == ordered[1].score:
                self.winner_id = None
            else:
                self.winner_id = ordered[0].player_id if ordered else None
        self._event(now, "finish", 0, CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, reason)

    def _event(
        self,
        now: float,
        kind: str,
        player_id: int,
        x: float,
        y: float,
        text: str,
        points: int | None = None,
    ) -> EventDict:
        self.event_counter += 1
        event: EventDict = {
            "id": self.event_counter,
            "time": now,
            "expires": now + 0.9,
            "kind": kind,
            "player": player_id,
            "x": round(x, 1),
            "y": round(y, 1),
            "text": text,
        }
        if points is not None:
            event["points"] = points
        self.recent_events.append(event)
        self._prune_events(now)
        return event

    def _prune_events(self, now: float) -> None:
        self.recent_events = [event for event in self.recent_events if event["expires"] >= now]
