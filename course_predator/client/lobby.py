"""Pygame lobby app for hosting, joining, spectating, and replay playback."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pygame

from ..config import load_config
from ..constants import DEFAULT_HOST, WINDOW_HEIGHT, WINDOW_WIDTH
from .game import GameApp
from .network import NetworkClient
from .replay import ReplayApp
from .widgets import Button, TextInput

logger = logging.getLogger(__name__)


class LobbyApp:
    """Launches a host server, joins a remote server, or opens replays."""

    def __init__(self) -> None:
        self.config = load_config()
        pygame.init()
        pygame.display.set_caption("Course Predator Lobby")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.small = pygame.font.SysFont("arial", 17)
        self.title = pygame.font.SysFont("arial", 54, bold=True)
        self.inputs = {
            "name": TextInput("Name", "Student", pygame.Rect(80, 185, 250, 44)),
            "host": TextInput("IP / Host", self.config.host, pygame.Rect(365, 185, 250, 44)),
            "port": TextInput("Port", str(self.config.port), pygame.Rect(650, 185, 180, 44)),
            "duration": TextInput("Host Duration", str(self.config.duration), pygame.Rect(80, 280, 180, 44)),
        }
        self.buttons = {
            "host": Button("Host Game", pygame.Rect(305, 280, 160, 50), (51, 137, 255)),
            "join": Button("Join Game", pygame.Rect(500, 280, 160, 50), (70, 193, 126)),
            "spectate": Button("Spectate", pygame.Rect(695, 280, 150, 50), (151, 104, 255)),
            "replay": Button("Watch Replay", pygame.Rect(370, 375, 220, 50), (255, 156, 84)),
        }
        self.error = ""
        self.server_process: subprocess.Popen[Any] | None = None

    def run(self) -> None:
        while True:
            dt = self.clock.tick(60) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._cleanup()
                    pygame.quit()
                    return
                for text_input in self.inputs.values():
                    text_input.handle_event(event)
                if self.buttons["host"].is_clicked(event):
                    self._host_game()
                elif self.buttons["join"].is_clicked(event):
                    self._start_game("player")
                elif self.buttons["spectate"].is_clicked(event):
                    self._start_game("spectator")
                elif self.buttons["replay"].is_clicked(event):
                    self._watch_latest_replay()
            self._draw(dt, mouse_pos)
            pygame.display.flip()

    def _draw(self, dt: float, mouse_pos: tuple[int, int]) -> None:
        self.screen.fill((9, 12, 20))
        title = self.title.render("Course Predator", True, (245, 248, 255))
        subtitle = self.small.render("A real-time 1v1 course-registration reaction race", True, (161, 177, 201))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 78)))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WINDOW_WIDTH // 2, 130)))
        for text_input in self.inputs.values():
            text_input.draw(self.screen, self.font, self.small)
        for button in self.buttons.values():
            button.draw(self.screen, self.font, mouse_pos, dt)
        instructions = [
            "Host starts a local TCP server and joins as Player 1.",
            "Join connects as Player 1/2. Extra clients become spectators.",
            "Use the virtual cursor: stress slows it, jumps it, and creates trails.",
        ]
        for index, line in enumerate(instructions):
            surface = self.small.render(line, True, (180, 193, 212))
            self.screen.blit(surface, (80, 485 + index * 26))
        if self.error:
            error = self.small.render(self.error, True, (255, 117, 128))
            self.screen.blit(error, (80, 445))

    def _host_game(self) -> None:
        try:
            port = int(self.inputs["port"].value)
            duration = int(self.inputs["duration"].value)
            command = [
                sys.executable,
                "-m",
                "course_predator.server",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--duration",
                str(duration),
            ]
            self.server_process = subprocess.Popen(command)
            time.sleep(0.6)
            self.inputs["host"].value = DEFAULT_HOST
            self._start_game("player")
        except (OSError, ValueError) as exc:
            self.error = f"Could not host: {exc}"
            logger.warning("Could not host game: %s", exc)
        finally:
            if self.server_process and self.server_process.poll() is None:
                self.server_process.terminate()
                self.server_process = None

    def _start_game(self, role: str) -> None:
        try:
            host = self.inputs["host"].value.strip() or self.config.host
            port = int(self.inputs["port"].value)
            name = self.inputs["name"].value.strip() or "Student"
        except ValueError:
            self.error = "Port must be a number."
            return
        client = NetworkClient(host, port, name, role)
        GameApp(self.screen, self.clock, client).run()
        pygame.mouse.set_visible(True)
        pygame.display.set_caption("Course Predator Lobby")

    def _watch_latest_replay(self) -> None:
        replay_dir = Path(self.config.replay_dir)
        replays = sorted(replay_dir.glob("match_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not replays:
            self.error = "No replay found yet."
            return
        ReplayApp(self.screen, self.clock, str(replays[0])).run()

    def _cleanup(self) -> None:
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
