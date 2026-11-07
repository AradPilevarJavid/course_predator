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
from .protocol import JsonSocket, validate_message
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
    def __init__(self, host: str, port: int, duration: int, room_token: str | None = None) -> None:
        self.config = load_config()
        self.host = host
        self.port = port
        self.duration = max(MIN_DURATION, min(MAX_DURATION, duration))
        self.room_token = self.config.room_token if room_token is None else room_token
        self.game = Game(self.duration, self.config.min_players)
        self.connections: list[Connection] = []
        self.connection_lock = threading.RLock()
        self.shutdown_event = threading.Event()
        self._shutdown_after_replay = threading.Event()
        self.recorder = ReplayRecorder(enabled=True, replay_dir=self.config.replay_dir)
        self._saved_replay = False
        self._match_started = False
        self._last_broadcast = 0.0
        self._last_replay_frame = 0.0
        self._game_thread: threading.Thread | None = None

    def run(self) -> None:
        self.shutdown_event.clear()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            server_socket.settimeout(0.5)
            logger.info(f"Course Predator server listening on {self.host}:{self.port}")
            logger.info(
                f"Waiting for {self.config.min_players}-{self.config.max_players} players. Duration: {self.duration}s"
            )
            self._game_thread = threading.Thread(target=self._game_loop, daemon=True)
            self._game_thread.start()

            try:
                while not self.shutdown_event.is_set():
                    try:
                        client_socket, address = server_socket.accept()
                    except TimeoutError:
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
                self._close_connections()
                if self._game_thread is not None and self._game_thread is not threading.current_thread():
                    self._game_thread.join(timeout=1.0)
                self._game_thread = None

    def _close_connections(self) -> None:
        with self.connection_lock:
            connections = list(self.connections)
            self.connections.clear()
        for connection in connections:
            connection.alive = False
            try:
                connection.json_socket.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.json_socket.sock.close()
            except OSError:
                pass

    def _handle_client(self, sock: socket.socket, address: tuple[str, int]) -> None:
        sock.settimeout(10.0)
        json_socket = JsonSocket(sock)
        connection: Connection | None = None
        try:
            hello = json_socket.receive(timeout=10.0)
            if not hello:
                raise ConnectionError("client did not send hello")
            validate_message(hello, hello=True)
            if self.room_token and hello.get("token") != self.room_token:
                json_socket.send({"type": "error", "error": "invalid room token"})
                raise ConnectionError("invalid room token")

            connection = self._register_connection(json_socket, address, hello)
            json_socket.send(self._welcome_message(connection))
            self._broadcast_lobby()

            while not self.shutdown_event.is_set() and connection.alive:
                message = json_socket.receive(timeout=1.0)
                if message is None:
                    continue
                validate_message(message)
                self._process_message(connection, message)
        except (TypeError, ValueError, UnicodeError) as exc:
            logger.warning("Rejected malformed message from %s: %s", address, exc)
        except (ConnectionError, OSError) as exc:
            logger.info("Connection %s closed: %s", address, exc)
        finally:
            if connection is not None:
                self._remove_connection(connection)
            try:
                sock.close()
            except OSError:
                pass

    def _register_connection(self, json_socket, address, hello):
        requested_role = str(hello.get("role", "player")).lower()
        name = str(hello.get("name") or "Student")
        now = time.monotonic()
        with self.connection_lock, self.game.lock:
            player_count = sum(1 for c in self.connections if c.role == "player" and c.alive)
            if (
                requested_role == "spectator"
                or player_count >= self.config.max_players
                or self.game.active
                or self.game.ended
            ):
                connection = Connection(json_socket, address, "spectator", None, name[:24] or "Spectator")
            else:
                player_id = None
                for pid in range(1, self.config.max_players + 1):
                    if pid not in self.game.players:
                        player_id = pid
                        break
                connection = Connection(json_socket, address, "player", player_id, name[:24] or f"Player {player_id}")
                self.game.add_player(player_id, connection.name, now)

            self.connections.append(connection)
            if self.game.can_start():
                self.game.start(now)
                self.recorder.start(now)
                self._saved_replay = False
                self._match_started = True
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
            x = float(message["x"])
            y = float(message["y"])
            with self.game.lock:
                event = self.game.handle_click(connection.player_id, x, y, now)
            connection.json_socket.send({"type": "ack", "event": event})
            self._broadcast_state(force=True)
        elif message_type == "mouse" and connection.role == "player" and connection.player_id:
            x = float(message["x"])
            y = float(message["y"])
            with self.game.lock:
                self.game.update_mouse(connection.player_id, x, y)
        elif message_type == "quit":
            connection.alive = False
        elif message_type == "ping":
            connection.json_socket.send({"type": "pong"})

    def _remove_connection(self, connection: Connection, *, broadcast: bool = True) -> None:
        with self.connection_lock, self.game.lock:
            if connection in self.connections:
                self.connections.remove(connection)
            connection.alive = False
            if connection.role == "player" and connection.player_id:
                if self.game.active:
                    self.game.mark_disconnected(connection.player_id, time.monotonic())
                else:
                    self.game.remove_waiting_player(connection.player_id)
            if (
                self._match_started
                and self.game.ended
                and not any(c.role == "player" and c.alive for c in self.connections)
            ):
                self._shutdown_after_replay.set()
            if broadcast:
                self._broadcast_lobby()

    def _game_loop(self) -> None:
        tick_interval = 1.0 / self.config.server_tick_rate
        next_tick = time.monotonic()
        while not self.shutdown_event.is_set():
            next_tick += tick_interval
            now = time.monotonic()
            should_shutdown = False
            with self.game.lock:
                ended_this_tick = self.game.update(now)
                if self.game.active and now - self._last_replay_frame >= 1.0 / self.config.replay_record_rate:
                    self.recorder.record(now, self.game.to_state(now, None, spectator=True))
                    self._last_replay_frame = now
                if (ended_this_tick or self.game.ended) and not self._saved_replay:
                    self.recorder.record(now, self.game.to_state(now, None, spectator=True))
                    self.game.replay_file = self.recorder.save(self.duration, self.game.winner_id)
                    self._saved_replay = True
                should_shutdown = self._shutdown_after_replay.is_set() and self.game.ended and self._saved_replay

            self._broadcast_state()
            if should_shutdown:
                self.shutdown_event.set()
            sleep_for = max(0.0, next_tick - time.monotonic())
            time.sleep(sleep_for)

    def _broadcast_lobby(self) -> None:
        with self.connection_lock, self.game.lock:
            player_names = [player.name for _, player in sorted(self.game.players.items()) if player.connected]
            needed = max(0, self.game.min_players - len(player_names))
            message = {
                "type": "lobby",
                "players": player_names,
                "needed": needed,
                "duration": self.duration,
            }
            self._send_all(message)

    def _broadcast_state(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_broadcast < 1.0 / self.config.state_broadcast_rate:
            return
        self._last_broadcast = now
        with self.connection_lock, self.game.lock:
            failed_connections: list[Connection] = []
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
                except (OSError, ValueError) as exc:
                    logger.info("Removing connection %s after state send failure: %s", connection.address, exc)
                    failed_connections.append(connection)
            for connection in failed_connections:
                self._remove_connection(connection, broadcast=False)
            if failed_connections:
                self._broadcast_lobby()

    def _send_all(self, message: dict[str, Any]) -> None:
        failed_connections: list[Connection] = []
        for connection in list(self.connections):
            if not connection.alive:
                continue
            try:
                connection.json_socket.send(message)
            except (OSError, ValueError) as exc:
                logger.info("Removing connection %s after send failure: %s", connection.address, exc)
                failed_connections.append(connection)
        for connection in failed_connections:
            self._remove_connection(connection, broadcast=False)


def parse_args() -> argparse.Namespace:
    config = load_config()
    parser = argparse.ArgumentParser(description="Run the Course Predator server.")
    parser.add_argument("--host", default=config.host or DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=config.port or DEFAULT_PORT)
    parser.add_argument("--duration", type=int, default=config.duration or DEFAULT_DURATION)
    parser.add_argument("--log-level", default=config.log_level)
    parser.add_argument("--room-token", default=config.room_token)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    Server(args.host, args.port, args.duration, args.room_token).run()


if __name__ == "__main__":
    main()
