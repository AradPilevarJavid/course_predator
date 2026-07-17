"""Typed JSON payloads shared by the server, client, and replay system."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class ShapeDict(TypedDict):
    id: str
    kind: str
    x: float
    y: float
    radius: float
    points: int
    ttl: float
    lifetime: float


class EventDict(TypedDict):
    id: int
    time: float
    expires: float
    kind: str
    player: int
    x: float
    y: float
    text: str
    points: NotRequired[int]


class PlayerState(TypedDict):
    id: int
    name: str
    score: float
    stamina: float
    stress: float
    shield: float
    frozen: float
    connected: bool
    mouse: list[float]


class CanvasDict(TypedDict):
    width: int
    height: int


class GameState(TypedDict):
    type: Literal["state"]
    active: bool
    ended: bool
    duration: int
    time_left: float
    winner: int | None
    reason: str
    replay_file: str
    players: dict[str, PlayerState]
    shapes: list[ShapeDict]
    events: list[EventDict]
    canvas: CanvasDict


class LobbyState(TypedDict):
    type: Literal["lobby"]
    players: list[str]
    needed: int
    duration: int


class WelcomeMessage(TypedDict):
    type: Literal["welcome"]
    role: str
    player_id: int | None
    name: str
    duration: int


class ClientMessage(TypedDict, total=False):
    type: str
    name: str
    role: str
    x: float
    y: float


JsonMessage = dict[str, object]
