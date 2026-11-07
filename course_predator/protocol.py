"""Small newline-delimited JSON protocol used by clients and server."""

import json
import math
import socket
import threading
from typing import Any

from .constants import CANVAS_HEIGHT, CANVAS_WIDTH

MAX_MESSAGE_BYTES = 1_048_576
MAX_NAME_LENGTH = 64
MAX_TOKEN_LENGTH = 256
MESSAGE_TYPES = {"hello", "click", "mouse", "quit", "ping", "welcome", "lobby", "state", "ack", "pong", "error"}


class JsonSocket:
    """Thread-safe JSON sender plus buffered newline JSON receiver."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buffer = b""
        self._send_lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(payload) > MAX_MESSAGE_BYTES:
            raise ValueError("JSON message is too large")
        with self._send_lock:
            self.sock.sendall(payload)

    def receive(self, timeout: float | None = None) -> dict[str, Any] | None:
        previous_timeout = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            while b"\n" not in self._buffer:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise ConnectionError("socket closed")
                self._buffer += chunk
                if len(self._buffer) > MAX_MESSAGE_BYTES:
                    raise ValueError("JSON message is too large")
        except TimeoutError:
            return None
        finally:
            self.sock.settimeout(previous_timeout)

        line, self._buffer = self._buffer.split(b"\n", 1)
        if not line.strip():
            return None
        message = json.loads(line.decode("utf-8"))
        if not isinstance(message, dict):
            raise TypeError("JSON message must be an object")
        return message


def validate_message(message: dict[str, Any], *, hello: bool = False) -> None:
    if not isinstance(message, dict):
        raise TypeError("JSON message must be an object")
    message_type = message.get("type")
    if not isinstance(message_type, str) or message_type not in MESSAGE_TYPES:
        raise ValueError("unknown message type")
    if hello and message_type != "hello":
        raise ValueError("first message must be hello")
    if message_type in {"click", "mouse"}:
        for field in ("x", "y"):
            value = message.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"{field} must be a finite number")
            upper_bound = CANVAS_WIDTH if field == "x" else CANVAS_HEIGHT
            if not 0.0 <= float(value) <= upper_bound:
                raise ValueError(f"{field} is out of range")
    if message_type == "hello":
        name = message.get("name", "")
        role = message.get("role", "player")
        token = message.get("token", "")
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME_LENGTH:
            raise ValueError("invalid player name")
        if not isinstance(role, str) or role not in {"player", "spectator"}:
            raise ValueError("invalid role")
        if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:
            raise ValueError("invalid room token")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_text(score: float) -> str:
    return str(int(score)) if float(score).is_integer() else f"{score:.1f}"
