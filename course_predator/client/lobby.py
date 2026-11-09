from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pygame

from ..config import load_config
from ..constants import DEFAULT_HOST
from .game import GameApp
from .network import NetworkClient
from .replay import ReplayApp
from .viewport import initial_window_size
from .widgets import Button, TextInput

logger = logging.getLogger(__name__)


class LobbyApp:
    def __init__(self) -> None:
        self.config = load_config()
        pygame.init()
        pygame.display.set_caption("Course Predator Lobby")
        self.screen = pygame.display.set_mode(initial_window_size(), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.small = pygame.font.SysFont("arial", 17)
        self.title_font = pygame.font.SysFont("arial", 54, bold=True)

        self.inputs = {
            "name": TextInput("Name", "Student", pygame.Rect(0, 0, 0, 0)),
            "host": TextInput("IP / Host", self.config.host, pygame.Rect(0, 0, 0, 0)),
            "port": TextInput("Port", str(self.config.port), pygame.Rect(0, 0, 0, 0)),
            "duration": TextInput("Host Duration", str(self.config.duration), pygame.Rect(0, 0, 0, 0)),
        }
        self.buttons = {
            "host": Button("Host Game", pygame.Rect(0, 0, 0, 0), (51, 227, 255)),
            "join": Button("Join Game", pygame.Rect(0, 0, 0, 0), (70, 193, 126)),
            "spectate": Button("Spectate", pygame.Rect(0, 0, 0, 0), (151, 104, 255)),
            "replay": Button("Watch Replay", pygame.Rect(0, 0, 0, 0), (255, 156, 84)),
        }
        self._layout()

        self.error = ""
        self.server_process: subprocess.Popen[Any] | None = None

    def run(self) -> None:
        while True:
            seconds_per_loop = self.clock.tick(60) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._cleanup()
                    pygame.quit()
                    return
                if event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    self._layout()
                    continue
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
            self._draw(seconds_per_loop, mouse_pos)
            pygame.display.flip()

    def _draw(self, seconds_per_loop: float, mouse_pos: tuple[int, int]) -> None:
        width, height = self.screen.get_size()
        self.screen.fill((9, 12, 20))
        title = self.title_font.render("Course Predator", True, (245, 248, 255))
        self.screen.blit(title, title.get_rect(center=(width // 2, 78)))
        subtitle = self.small.render("A real-time 1v1 course-registration reaction race", True, (161, 177, 201))
        self.screen.blit(subtitle, subtitle.get_rect(center=(width // 2, 130)))

        for text_input in self.inputs.values():
            text_input.draw(self.screen, self.font, self.small)
        for button in self.buttons.values():
            button.draw(self.screen, self.font, mouse_pos, seconds_per_loop)

        instr_x = int(width * 0.07)
        instr_y = int(height * 0.78)

        #                         < Instructions used to live here :) >

        # for index, line in enumerate(instructions):
        #     surface = self.small.render(line, True, (180, 193, 212))
        #     self.screen.blit(surface, (instr_x, instr_y + index * 26))

        if self.error:
            error = self.small.render(self.error, True, (255, 117, 128))
            self.screen.blit(error, (instr_x, instr_y - 40))

    def _layout(self) -> None:
        width, height = self.screen.get_size()
        margin = max(28, int(width * 0.07))
        gap = 15
        input_y = max(175, int(height * 0.24))
        input_h = 44
        usable = max(320, width - 2 * margin)
        if width < 1000:
            row_width = min(620, usable)
            input_width = (row_width - gap) // 2
            positions = [
                (margin, input_y),
                (margin + input_width + gap, input_y),
                (margin, input_y + input_h + 34),
                (margin + input_width + gap, input_y + input_h + 34),
            ]
            widths = [input_width] * 4
        else:
            port_w, duration_w = 140, 150
            flexible = max(260, usable - port_w - duration_w - 3 * gap)
            name_w, host_w = flexible // 2, flexible - flexible // 2
            positions = [
                (margin, input_y),
                (margin + name_w + gap, input_y),
                (margin + name_w + gap + host_w + gap, input_y),
                (margin + name_w + gap + host_w + gap + port_w + gap, input_y),
            ]
            widths = [name_w, host_w, port_w, duration_w]
        for key, (position, item_width) in zip(self.inputs, zip(positions, widths)):
            self.inputs[key].rect = pygame.Rect(position[0], position[1], item_width, input_h)

        button_y = min(height - 170, input_y + 180)
        button_gap = 20
        button_widths = [160, 160, 150]
        total = sum(button_widths) + button_gap * 2
        start = (width - total) // 2
        for key, button_width in zip(("host", "join", "spectate"), button_widths):
            self.buttons[key].rect = pygame.Rect(start, button_y, button_width, 50)
            start += button_width + button_gap
        self.buttons["replay"].rect = pygame.Rect((width - 220) // 2, button_y + 72, 220, 50)

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
        client = NetworkClient(host, port, name, role, self.config.room_token)
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
