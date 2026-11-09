"""Window and coordinate geometry for the Pygame client."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from ..constants import CANVAS_HEIGHT, CANVAS_WIDTH


@dataclass(frozen=True)
class Viewport:
    """Uniformly maps the authoritative arena into the current window."""

    window_size: tuple[int, int]
    arena_rect: pygame.Rect
    scale: float

    @classmethod
    def from_window(cls, size: tuple[int, int], hud_preferred: int = 300) -> Viewport:
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))
        wide = width >= CANVAS_WIDTH + hud_preferred
        if wide:
            arena_area = (width - hud_preferred, height)
        else:
            arena_area = (width, max(1, height - 180))
        scale = min(arena_area[0] / CANVAS_WIDTH, arena_area[1] / CANVAS_HEIGHT)
        arena_size = (max(1, round(CANVAS_WIDTH * scale)), max(1, round(CANVAS_HEIGHT * scale)))
        if wide:
            arena_rect = pygame.Rect(
                (width - hud_preferred - arena_size[0]) // 2,
                (height - arena_size[1]) // 2,
                *arena_size,
            )
        else:
            arena_rect = pygame.Rect(
                (width - arena_size[0]) // 2, 170 + (height - 170 - arena_size[1]) // 2, *arena_size
            )
        return cls((width, height), arena_rect, scale)

    @property
    def hud_rect(self) -> pygame.Rect:
        if self.window_size[0] >= CANVAS_WIDTH + 300:
            return pygame.Rect(
                self.arena_rect.right, 0, self.window_size[0] - self.arena_rect.right, self.window_size[1]
            )
        return pygame.Rect(0, 0, self.window_size[0], min(170, self.window_size[1]))

    @property
    def is_wide(self) -> bool:
        return self.window_size[0] >= CANVAS_WIDTH + 300

    def logical_to_screen(self, x: float, y: float) -> tuple[int, int]:
        return (round(self.arena_rect.x + x * self.scale), round(self.arena_rect.y + y * self.scale))

    def screen_to_logical(self, pos: tuple[int, int]) -> tuple[float, float] | None:
        if not self.arena_rect.collidepoint(pos):
            return None
        return (
            (pos[0] - self.arena_rect.x) / self.scale,
            (pos[1] - self.arena_rect.y) / self.scale,
        )

    def logical_delta(self, rel: tuple[int, int]) -> tuple[float, float]:
        return rel[0] / self.scale, rel[1] / self.scale


def initial_window_size(display_size: tuple[int, int] | None = None) -> tuple[int, int]:
    """Choose a useful non-fullscreen starting size for the current display."""
    if display_size is None:
        display_size = pygame.display.get_desktop_sizes()[0] if pygame.display.get_desktop_sizes() else (1600, 900)
    width = min(max(1280, int(display_size[0] * 0.85)), max(1280, int(display_size[0] - 80)))
    height = min(max(720, int(display_size[1] * 0.85)), max(720, int(display_size[1] - 80)))
    return width, height
