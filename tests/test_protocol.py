from __future__ import annotations

import socket

import pytest

from course_predator.protocol import JsonSocket, validate_message


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


def test_json_socket_rejects_non_object_messages() -> None:
    left, right = socket.socketpair()
    try:
        left.sendall(b'["not", "an", "object"]\n')
        with pytest.raises(TypeError, match="object"):
            JsonSocket(right).receive(timeout=0.1)
    finally:
        left.close()
        right.close()


def test_validate_message_rejects_unknown_and_non_finite_input() -> None:
    with pytest.raises(ValueError, match="unknown"):
        validate_message({"type": "bogus"})
    with pytest.raises(ValueError, match="finite"):
        validate_message({"type": "click", "x": float("nan"), "y": 2})


def test_validate_hello_accepts_player_and_spectator_roles() -> None:
    validate_message({"type": "hello", "name": "P1", "role": "player"}, hello=True)
    validate_message({"type": "hello", "name": "Watcher", "role": "spectator"}, hello=True)
