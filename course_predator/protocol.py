"""Small newline-delimited JSON protocol used by clients and server."""


import json
import socket
import threading
from typing import Any


class JsonSocket:
    """Thread-safe JSON sender plus buffered newline JSON receiver."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buffer = b""
        self._send_lock = threading.Lock()

    def send(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
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
        except socket.timeout:
            return None
        finally:
            self.sock.settimeout(previous_timeout)

        line, self._buffer = self._buffer.split(b"\n", 1)
        if not line.strip():
            return None
        return json.loads(line.decode("utf-8"))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_text(score: float) -> str:
    return str(int(score)) if float(score).is_integer() else f"{score:.1f}"
