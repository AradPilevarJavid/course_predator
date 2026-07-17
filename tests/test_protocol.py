from __future__ import annotations

import socket

from course_predator.protocol import JsonSocket


def test_json_socket_framing_round_trip() -> None:
    left, right = socket.socketpair()
    try:
        sender = JsonSocket(left)
        receiver = JsonSocket(right)
        sender.send({"type": "state", "value": 1})
        sender.send({"type": "state", "value": 2})

        assert receiver.receive(timeout=0.1) == {"type": "state", "value": 1}
        assert receiver.receive(timeout=0.1) == {"type": "state", "value": 2}
    finally:
        left.close()
        right.close()
