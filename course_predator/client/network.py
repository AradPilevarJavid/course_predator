"""Threaded network client and high-level game client facade."""

from __future__ import annotations

import logging
import queue
import socket
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from ..protocol import JsonSocket
from ..types import GameState, JsonMessage, LobbyState

logger = logging.getLogger(__name__)

CONNECTION_LOST_SECONDS = 3.0
KEEPALIVE_SECONDS = 1.0


# Enum = named CONSTANT values that are fixed together.
class ConnState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    WAITING_LOBBY = 2
    PLAYING = 3
    SPECTATING = 4
    ENDED = 5


@dataclass(frozen=True) # frozen = immutable
class NetworkSnapshot:
    state: GameState | None
    lobby: LobbyState | None
    status: str
    player_id: int | None
    role: str
    conn_state: ConnState


class NetworkClient:
    """Owns the logic of the network side of the client.    >Threading<
        includes the socket in a background thread and shares state with the GUI."""

    def __init__(self, host: str, port: int, name: str, role: str) -> None:
        self.host = host
        self.port = port
        self.name = name
        self.role = role
        self.player_id: int | None = None
        self.running = threading.Event()
        self.running.set()
        self.outbox: queue.Queue[JsonMessage] = queue.Queue()
        self.log_queue: queue.Queue[tuple[int, str]] = queue.Queue()
        self.state_lock = threading.RLock() # locks the block of code that the other thread might also be modifying.
        self.latest_state: GameState | None = None
        self.latest_lobby: LobbyState | None = None
        self.status = "Connecting..."
        self.conn_state = ConnState.CONNECTING
        self.last_message_at = time.monotonic()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.send({"type": "quit"})
        self.running.clear()
        if self.thread.is_alive():
            self.thread.join(timeout=0.5)

    def send(self, message: JsonMessage) -> None:
        self.outbox.put(message)

    def snapshot(self) -> NetworkSnapshot:
        with self.state_lock:
            if self.conn_state not in {ConnState.DISCONNECTED, ConnState.CONNECTING}:
                if time.monotonic() - self.last_message_at > CONNECTION_LOST_SECONDS:
                    self.conn_state = ConnState.DISCONNECTED
                    self.status = "Connection lost"
            return NetworkSnapshot(
                self.latest_state,
                self.latest_lobby,
                self.status,
                self.player_id,
                self.role,
                self.conn_state,
            )

    def drain_logs(self) -> None:
        while True:
            try:
                level, message = self.log_queue.get_nowait()
            except queue.Empty:
                return
            logger.log(level, message)

    def _run(self) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=8.0) as sock:
                json_socket = JsonSocket(sock)
                json_socket.send({"type": "hello", "name": self.name, "role": self.role})
                self._set_status("Connected", ConnState.WAITING_LOBBY)
                last_keepalive = time.monotonic()
                while self.running.is_set() or not self.outbox.empty():
                    sent_message = self._flush_outbox(json_socket)
                    now = time.monotonic()
                    if not sent_message and now - last_keepalive >= KEEPALIVE_SECONDS:
                        json_socket.send({"type": "ping"})
                        last_keepalive = now
                    message = json_socket.receive(timeout=0.03)
                    if not message:
                        continue
                    self._handle_message(message)
        except ConnectionError as exc:
            self._set_status(f"Disconnected: {exc}", ConnState.DISCONNECTED)
            self.log_queue.put((logging.INFO, f"Disconnected: {exc}"))
        except OSError as exc:
            self._set_status(f"Network error: {exc}", ConnState.DISCONNECTED)
            self.log_queue.put((logging.WARNING, f"Network error: {exc}"))
        finally:
            self._disconnect_if_needed()

    def _flush_outbox(self, json_socket: JsonSocket) -> bool:
        sent_message = False
        while True:
            try:
                json_socket.send(self.outbox.get_nowait())
                sent_message = True
            except queue.Empty:
                return sent_message

    def _set_status(self, status: str, conn_state: ConnState) -> None:
        with self.state_lock:
            self.status = status
            self.conn_state = conn_state

    def _disconnect_if_needed(self) -> None:
        with self.state_lock:
            if self.conn_state != ConnState.DISCONNECTED:
                self.status = "Disconnected"
                self.conn_state = ConnState.DISCONNECTED

    def _handle_message(self, message: dict[str, Any]) -> None:
        with self.state_lock:
            self.last_message_at = time.monotonic()
            message_type = message.get("type")
            if message_type == "welcome":
                self.role = str(message.get("role", self.role))
                raw_player_id = message.get("player_id")
                self.player_id = int(raw_player_id) if isinstance(raw_player_id, int) else None
                if self.role == "spectator":
                    self.status = "Watching as spectator"
                    self.conn_state = ConnState.SPECTATING
                else:
                    self.status = f"Playing as Player {self.player_id}"
                    self.conn_state = ConnState.WAITING_LOBBY
            elif message_type == "lobby":
                self.latest_lobby = cast(LobbyState, message)
                if self.conn_state != ConnState.SPECTATING:
                    self.conn_state = ConnState.WAITING_LOBBY
            elif message_type == "state":
                self.latest_state = cast(GameState, message)
                if bool(message.get("ended")):
                    self.conn_state = ConnState.ENDED
                elif bool(message.get("active")) and self.role != "spectator":
                    self.conn_state = ConnState.PLAYING
                elif self.role == "spectator":
                    self.conn_state = ConnState.SPECTATING
            elif message_type == "pong":
                pass
            elif message_type == "ack":
                pass


class GameClient:
    """Small testable facade(interface) for match input and state access."""

    def __init__(self, network: NetworkClient) -> None:
        self.network = network

    def start(self) -> None:
        self.network.start()

    def stop(self) -> None:
        self.network.stop()

    def send_mouse(self, x: float, y: float) -> None:
        self.network.send({"type": "mouse", "x": x, "y": y})

    def send_click(self, x: float, y: float) -> None:
        self.network.send({"type": "click", "x": x, "y": y})

    def snapshot(self) -> NetworkSnapshot:
        self.network.drain_logs()
        return self.network.snapshot()

    def get_state(self) -> GameState | None:
        return self.snapshot().state
