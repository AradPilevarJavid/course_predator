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
    def __init__(self) -> None:
        self.config = load_config()
        pygame.init()
        pygame.display.set_caption("Course Predator Lobby")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.small = pygame.font.SysFont("arial", 17)
        self.title_font = pygame.font.SysFont("arial", 54, bold=True)

        ww, wh = WINDOW_WIDTH, WINDOW_HEIGHT
        margin = 80
        input_y = 185
        input_h = 44
        gap = 15

        port_w = 140
        duration_w = 150

        total_fixed = port_w + duration_w + 3 * gap
        flexible_width = ww - 2 * margin - total_fixed
        name_w = flexible_width // 2
        host_w = flexible_width - name_w

        x_name = margin
        x_host = x_name + name_w + gap
        x_port = x_host + host_w + gap
        x_duration = x_port + port_w + gap

        self.inputs = {
            "name": TextInput("Name", "Student", pygame.Rect(x_name, input_y, name_w, input_h)),
            "host": TextInput("IP / Host", self.config.host, pygame.Rect(x_host, input_y, host_w, input_h)),
            "port": TextInput("Port", str(self.config.port), pygame.Rect(x_port, input_y, port_w, input_h)),
            "duration": TextInput(
                "Host Duration", str(self.config.duration), pygame.Rect(x_duration, input_y, duration_w, input_h)
            ),
        }

        btn_y = 280 + 330
        btn_h = 50
        btn_gap = 40
        btn_host_w = 160
        btn_join_w = 160
        btn_spec_w = 150
        btn_row_width = btn_host_w + btn_join_w + btn_spec_w + 2 * btn_gap
        btn_row_x = (ww - btn_row_width) // 2

        self.buttons = {
            "host": Button("Host Game", pygame.Rect(btn_row_x, btn_y, btn_host_w, btn_h), (51, 137+90, 255)),
            "join": Button(
                "Join Game",
                pygame.Rect(btn_row_x + btn_host_w + btn_gap, btn_y, btn_join_w, btn_h),
                (70, 193, 126),
            ),
            "spectate": Button(
                "Spectate",
                pygame.Rect(btn_row_x + btn_host_w + btn_join_w + 2 * btn_gap, btn_y, btn_spec_w, btn_h),
                (151, 104, 255),
            ),
            "replay": Button("Watch Replay", pygame.Rect((ww - 220) // 2, 375+330, 220, 50), (255, 156, 84)),
        }

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
        self.screen.fill((9, 12, 20))
        title = self.title_font.render("Course Predator", True, (245, 248, 255))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 78)))
        subtitle = self.small.render("A real-time 1v1 course-registration reaction race", True, (161, 177, 201))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WINDOW_WIDTH // 2, 130)))

        for text_input in self.inputs.values():
            text_input.draw(self.screen, self.font, self.small)
        for button in self.buttons.values():
            button.draw(self.screen, self.font, mouse_pos, seconds_per_loop)

        instr_x = int(WINDOW_WIDTH * 0.07)  # ~80 on 1100
        instr_y = int(WINDOW_HEIGHT * 0.78)  # ~485 on 620+200

        #                         < Instructions used to live here :) >
       
        # for index, line in enumerate(instructions):
        #     surface = self.small.render(line, True, (180, 193, 212))
        #     self.screen.blit(surface, (instr_x, instr_y + index * 26))

        if self.error:
            error = self.small.render(self.error, True, (255, 117, 128))
            self.screen.blit(error, (instr_x, instr_y - 40))

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
