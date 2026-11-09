import time

import pygame

from ..replay import load_replay
from .mouse import MouseController
from .renderer import Renderer


class ReplayApp:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, replay_path: str) -> None:
        self.screen = screen
        self.clock = clock
        self.replay_path = replay_path
        self.renderer = Renderer(screen)
        self.replay = load_replay(replay_path)
        self.frames = self.replay.get("frames", [])
        self.running = True

    def run(self) -> None:
        if not self.frames:
            return
        pygame.display.set_caption(f"Course Predator Replay - {self.replay_path}")
        start = time.monotonic()
        frame_index = 0
        cursor = MouseController()
        while self.running:
            seconds_per_loop = self.clock.tick(60) / 1000.0
            end = time.monotonic()
            elapsed = end - start
            for event in pygame.event.get():
                if (
                    event.type == pygame.QUIT
                    or event.type == pygame.KEYDOWN
                    and event.key in (pygame.K_ESCAPE, pygame.K_RETURN)
                ):
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    self.renderer.resize(self.screen)
            while frame_index + 1 < len(self.frames) and self.frames[frame_index + 1]["t"] <= elapsed:
                frame_index += 1
            state = self.frames[frame_index]["state"]
            self.renderer.draw_state(state, None, "spectator", cursor, f"Replay {self.replay_path}", seconds_per_loop)
            note = self.renderer.small.render("Replay mode: Esc/Enter returns to lobby", True, (230, 236, 248))
            self.screen.blit(note, note.get_rect(topright=(self.screen.get_width() - 24, 48)))
            pygame.display.flip()
            if frame_index >= len(self.frames) - 1 and elapsed > self.frames[-1]["t"] + 2.0:
                self.running = False
