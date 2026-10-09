from __future__ import annotations

import threading

from course_predator import server as server_module
from course_predator.config import Config
from course_predator.server import Connection, Server


class FakeJsonSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, message: dict) -> None:
        self.messages.append(message)


def _server(monkeypatch, tmp_path, min_players: int = 2) -> Server:
    config = Config(
        min_players=min_players,
        max_players=4,
        replay_dir=str(tmp_path),
        server_tick_rate=100,
        state_broadcast_rate=100,
        replay_record_rate=100,
    )
    monkeypatch.setattr(server_module, "load_config", lambda: config)
    return Server("127.0.0.1", 0, 30)


def _connection(role: str, player_id: int | None = None) -> Connection:
    return Connection(FakeJsonSocket(), ("127.0.0.1", 1), role, player_id)


def _start_match(server: Server) -> tuple[Connection, Connection]:
    first = _connection("player", 1)
    second = _connection("player", 2)
    server.connections.extend((first, second))
    server.game.add_player(1, "P1", 0.0)
    server.game.add_player(2, "P2", 0.0)
    assert server.game.start(0.0)
    server._match_started = True
    server.recorder.start(0.0)
    return first, second


def test_all_disconnected_requests_shutdown_after_replay(monkeypatch, tmp_path) -> None:
    server = _server(monkeypatch, tmp_path)
    first, second = _start_match(server)
    server._broadcast_lobby = lambda: None
    server._broadcast_state = lambda: None
    replay_save_shutdown_states: list[bool] = []
    original_save = server.recorder.save

    def save_replay_before_shutdown(duration: int, winner: int | None) -> str:
        replay_save_shutdown_states.append(server.shutdown_event.is_set())
        return original_save(duration, winner)

    server.recorder.save = save_replay_before_shutdown

    server._remove_connection(first)
    server._remove_connection(second)

    assert server.game.ended
    assert server.game.end_reason == "All players disconnected"
    assert not server.shutdown_event.is_set()
    assert server._shutdown_after_replay.is_set()

    game_thread = threading.Thread(target=server._game_loop)
    game_thread.start()
    assert server.shutdown_event.wait(1.0)
    game_thread.join(1.0)

    assert server.game.replay_file
    assert server._saved_replay
    assert replay_save_shutdown_states == [False]


def test_remaining_player_prevents_shutdown(monkeypatch, tmp_path) -> None:
    server = _server(monkeypatch, tmp_path)
    first, _ = _start_match(server)
    server._broadcast_lobby = lambda: None

    server._remove_connection(first)

    assert server.game.active
    assert not server._shutdown_after_replay.is_set()
    assert not server.shutdown_event.is_set()


def test_spectator_disconnect_does_not_request_shutdown(monkeypatch, tmp_path) -> None:
    server = _server(monkeypatch, tmp_path)
    _, _ = _start_match(server)
    spectator = _connection("spectator")
    server.connections.append(spectator)
    server._broadcast_lobby = lambda: None

    server._remove_connection(spectator)

    assert server.game.active
    assert not server._shutdown_after_replay.is_set()


def test_waiting_player_disconnect_keeps_server_available(monkeypatch, tmp_path) -> None:
    server = _server(monkeypatch, tmp_path, min_players=2)
    waiting_player = _connection("player", 1)
    server.connections.append(waiting_player)
    server.game.add_player(1, "P1", 0.0)
    server._broadcast_lobby = lambda: None

    server._remove_connection(waiting_player)

    assert not server.game.active
    assert not server.game.ended
    assert not server._shutdown_after_replay.is_set()
    assert not server.shutdown_event.is_set()
