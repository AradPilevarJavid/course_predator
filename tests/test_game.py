from __future__ import annotations

from course_predator.game import Game
from course_predator.models import IceShape, NormalShape


def _started_game() -> Game:
    game = Game(duration=30)
    game.add_player(1, "P1", now=0.0)
    game.add_player(2, "P2", now=0.0)
    assert game.start(now=0.0)
    return game


def test_shield_negates_negative_score() -> None:
    game = _started_game()
    player = game.players[1]
    player.extend_shield(now=0.0, seconds=10.0)
    shape = NormalShape("neg", 100.0, 100.0, 30.0, -3, 5.0, 0.0)
    game.real_shapes[shape.shape_id] = shape

    event = game.handle_click(1, 100.0, 100.0, now=1.0)

    assert event["kind"] == "hit"
    assert player.score == 0.0
    assert "neg" not in game.real_shapes


def test_ice_click_freezes_opponent() -> None:
    game = _started_game()
    ice = IceShape("ice", 120.0, 120.0, 32.0, 5.0, 0.0)
    game.real_shapes[ice.shape_id] = ice

    event = game.handle_click(1, 120.0, 120.0, now=1.0)

    assert event["kind"] == "ice"
    assert game.players[2].frozen_until > 1.0
    assert game.players[1].stamina == 95.0


def test_spawn_respects_max_real_shapes() -> None:
    game = _started_game()
    game.next_shape_spawn = 0.0

    game.update(now=10.0)

    assert len(game.real_shapes) <= 10


def test_event_pruning_removes_expired_events() -> None:
    game = _started_game()
    game.handle_click(1, 1.0, 1.0, now=0.0)

    game.update(now=1.0)

    assert game.recent_events == []
