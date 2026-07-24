"""Reusable Pygame UI widgets."""

from __future__ import annotations

import pygame

Color = tuple[int, int, int]


class TextInput:
    """Custom pygame text input widget for the lobby."""

    def __init__(self, label: str, value: str, rect: pygame.Rect) -> None:
        self.label = label
        self.value = value
        self.rect = rect
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.unicode and len(self.value) < 32 and event.unicode.isprintable():
                self.value += event.unicode

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        label_surface = small.render(self.label, True, (190, 204, 220))
        surface.blit(label_surface, (self.rect.x, self.rect.y - 22))
        border = (80, 170, 255) if self.active else (91, 104, 124)
        pygame.draw.rect(surface, (24, 29, 38), self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=8)
        text_surface = font.render(self.value, True, (238, 242, 247))
        surface.blit(text_surface, (self.rect.x + 12, self.rect.y + 9))


class Button:
    """Simple animated button."""

    def __init__(self, label: str, rect: pygame.Rect, color: Color) -> None:
        self.label = label
        self.rect = rect
        self.color = color
        self.hover = 0.0

    def is_clicked(self, event: pygame.event.Event) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos: tuple[int, int], dt: float) -> None:
        target = 1.0 if self.rect.collidepoint(mouse_pos) else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 12.0)
        color = tuple(min(255, int(channel + 30 * self.hover)) for channel in self.color)
        inflated = self.rect.inflate(int(8 * self.hover), int(6 * self.hover))
        pygame.draw.rect(surface, color, inflated, border_radius=12)
        text = font.render(self.label, True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=inflated.center))
