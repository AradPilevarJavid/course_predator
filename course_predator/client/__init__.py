"""Pygame client package for Course Predator."""

from __future__ import annotations

import argparse

import pygame

from ..config import configure_logging, load_config
from ..constants import DEFAULT_HOST, DEFAULT_PORT
from .game import GameApp
from .lobby import LobbyApp
from .network import NetworkClient
from .replay import ReplayApp
from .viewport import initial_window_size


def parse_args() -> argparse.Namespace:
    config = load_config()
    parser = argparse.ArgumentParser(description="Run the Course Predator Pygame client.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=config.port)
    parser.add_argument("--name", default="Student")
    parser.add_argument("--spectator", action="store_true")
    parser.add_argument("--replay", default=None)
    parser.add_argument("--room-token", default=config.room_token)
    parser.add_argument("--log-level", default=config.log_level)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    if args.host or args.replay:
        pygame.init()
        screen = pygame.display.set_mode(initial_window_size(), pygame.RESIZABLE)
        clock = pygame.time.Clock()
        if args.replay:
            ReplayApp(screen, clock, args.replay).run()
        else:
            role = "spectator" if args.spectator else "player"
            network = NetworkClient(
                args.host or DEFAULT_HOST,
                args.port or DEFAULT_PORT,
                args.name,
                role,
                args.room_token,
            )
            GameApp(screen, clock, network).run()
        pygame.quit()
    else:
        LobbyApp().run()


__all__ = [
    "GameApp",
    "LobbyApp",
    "NetworkClient",
    "ReplayApp",
    "main",
    "parse_args",
]
