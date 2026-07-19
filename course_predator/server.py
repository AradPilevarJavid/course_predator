"""Authoritative threaded TCP server for Course Predator."""

from __future__ import annotations

import argparse
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

from .config import configure_logging, load_config
from .constants import (
    DEFAULT_DURATION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_DURATION,
    MIN_DURATION,
)
from .game import Game
from .protocol import JsonSocket
from .replay import ReplayRecorder

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    json_socket: JsonSocket
    address: tuple[str, int]
    role: str
    player_id: int | None = None
    name: str = "Spectator"
    alive: bool = True


class Server:
    """Accepts players/spectators and runs the authoritative game loop."""

    def __init__(self, host: str, port: int, duration: int) -> None:
        self.config = load_config()
        self.host = host
        self.port = port
        self.duration = max(MIN_DURATION, min(MAX_DURATION, duration))
        self.game = Game(self.duration)
        self.connections: list[Connection] = []
        self.connection_lock = threading.RLock()
        self.shutdown_event = threading.Event()
        self.recorder = ReplayRecorder(enabled=True, replay_dir=self.config.replay_dir)
        self._saved_replay = False
        self._last_broadcast = 0.0
        self._last_replay_frame = 0.0

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            server_socket.settimeout(0.5)
            logger.info("Course Predator server listening on %s:%s", self.host, self.port)
            logger.info("Waiting for exactly 2 players. Duration: %ss", self.duration)

            threading.Thread(target=self._game_loop, daemon=True).start()

            try:
                while not self.shutdown_event.is_set():
                    try:
                        client_socket, address = server_socket.accept()
                    except socket.timeout:
                        continue
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True,
                    ).start()
            except KeyboardInterrupt:
                logger.info("Server shutting down")
            finally:
                self.shutdown_event.set()

    def _handle_client(self, sock: socket.socket, address: tuple[str, int]) -> None:
        json_socket = JsonSocket(sock)
        connection: Connection | None = None
        try:
            hello = json_socket.receive(timeout=10.0)
            if not hello or hello.get("type") != "hello":
                raise ConnectionError("client did not send hello")

            connection = self._register_connection(json_socket, address, hello)
            json_socket.send(self._welcome_message(connection))
            self._broadcast_lobby()

            while not self.shutdown_event.is_set() and connection.alive:
                message = json_socket.receive(timeout=1.0)
                if message is None:
                    continue
                self._process_message(connection, message)
        except (ConnectionError, OSError, ValueError) as exc:
            logger.info("Connection %s closed: %s", address, exc)
        finally:
            if connection is not None:
                self._remove_connection(connection)
            try:
                sock.close()
            except OSError:
                pass

    def _register_connection(
        self,
        json_socket: JsonSocket,
        address: tuple[str, int],
        hello: dict[str, Any],
    ) -> Connection:
        requested_role = str(hello.get("role", "player")).lower()
        name = str(hello.get("name") or "Student")
        now = time.monotonic()
        with self.connection_lock, self.game.lock:
            player_count = sum(1 for item in self.connections if item.role == "player" and item.alive)
            if requested_role == "spectator" or player_count >= 2 or self.game.active or self.game.ended:
                connection = Connection(json_socket, address, "spectator", None, name[:24] or "Spectator")
            else:
                player_id = 1 if 1 not in self.game.players else 2
                connection = Connection(json_socket, address, "player", player_id, name[:24] or f"Player {player_id}")
                self.game.add_player(player_id, connection.name, now)

            self.connections.append(connection)
            if self.game.can_start():
                self.game.start(now)
                self.recorder.start(now)
                self._saved_replay = False
                logger.info("Game started")
            return connection

    def _welcome_message(self, connection: Connection) -> dict[str, Any]:
        return {
            "type": "welcome",
            "role": connection.role,
            "player_id": connection.player_id,
            "name": connection.name,
            "duration": self.duration,
        }

    def _process_message(self, connection: Connection, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        now = time.monotonic()
        if message_type == "click" and connection.role == "player" and connection.player_id:
            x = float(message.get("x", 0.0))
            y = float(message.get("y", 0.0))
            with self.game.lock:
                event = self.game.handle_click(connection.player_id, x, y, now)
            connection.json_socket.send({"type": "ack", "event": event})
            self._broadcast_state(force=True)
        elif message_type == "mouse" and connection.role == "player" and connection.player_id:
            x = float(message.get("x", 0.0))
            y = float(message.get("y", 0.0))
            with self.game.lock:
                self.game.update_mouse(connection.player_id, x, y)
        elif message_type == "quit":
            connection.alive = False
        elif message_type == "ping":
            connection.json_socket.send({"type": "pong"})

    def _remove_connection(self, connection: Connection) -> None:
        with self.connection_lock, self.game.lock:
            if connection in self.connections:
                self.connections.remove(connection)
            connection.alive = False
            if connection.role == "player" and connection.player_id:
                if self.game.active:
                    self.game.mark_disconnected(connection.player_id, time.monotonic())
                else:
                    self.game.remove_waiting_player(connection.player_id)
            self._broadcast_lobby()

    def _game_loop(self) -> None:
        tick_interval = 1.0 / self.config.server_tick_rate
        next_tick = time.monotonic()
        while not self.shutdown_event.is_set():
            next_tick += tick_interval
            now = time.monotonic()
            with self.game.lock:
                ended_this_tick = self.game.update(now)
                if self.game.active and now - self._last_replay_frame >= 1.0 / self.config.replay_record_rate:
                    self.recorder.record(now, self.game.to_state(now, None, spectator=True))
                    self._last_replay_frame = now
                if (ended_this_tick or self.game.ended) and not self._saved_replay:
                    self.recorder.record(now, self.game.to_state(now, None, spectator=True))
                    self.game.replay_file = self.recorder.save(self.duration, self.game.winner_id)
                    self._saved_replay = True

            self._broadcast_state()
            sleep_for = max(0.0, next_tick - time.monotonic())
            time.sleep(sleep_for)

    def _broadcast_lobby(self) -> None:
        with self.connection_lock, self.game.lock:
            player_names = [player.name for _, player in sorted(self.game.players.items()) if player.connected]
            message = {
                "type": "lobby",
                "players": player_names,
                "needed": max(0, 2 - len(player_names)),
                "duration": self.duration,
            }
            self._send_all(message)

    def _broadcast_state(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_broadcast < 1.0 / self.config.state_broadcast_rate:
            return
        self._last_broadcast = now
        with self.connection_lock, self.game.lock:
            for connection in list(self.connections):
                if not connection.alive:
                    continue
                try:
                    state = self.game.to_state(
                        now,
                        recipient_player_id=connection.player_id,
                        spectator=connection.role == "spectator",
                    )
                    connection.json_socket.send(state)
                except OSError:
                    connection.alive = False

    def _send_all(self, message: dict[str, Any]) -> None:
        for connection in list(self.connections):
            if not connection.alive:
                continue
            try:
                connection.json_socket.send(message)
            except OSError:
                connection.alive = False


def parse_args() -> argparse.Namespace:
    config = load_config()
    parser = argparse.ArgumentParser(description="Run the Course Predator server.")
    parser.add_argument("--host", default=config.host or DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=config.port or DEFAULT_PORT)
    parser.add_argument("--duration", type=int, default=config.duration or DEFAULT_DURATION)
    parser.add_argument("--log-level", default=config.log_level)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    Server(args.host, args.port, args.duration).run()


if __name__ == "__main__":
    main()
