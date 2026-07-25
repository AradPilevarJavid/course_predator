import math
import os
import time

import pygame

from ..constants import CANVAS_HEIGHT, CANVAS_WIDTH, HUD_HEIGHT, WINDOW_HEIGHT, WINDOW_WIDTH
from ..protocol import clamp, score_text
from ..types import EventDict, GameState, PlayerState, ShapeDict
from .mouse import MouseController
from .widgets import Color


class Renderer:
    """Pygame drawing HELPERS for game and replay screens."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.small = pygame.font.SysFont("arial", 17)
        self.big = pygame.font.SysFont("arial", 46, bold=True)
        self.title = pygame.font.SysFont("arial", 56, bold=True)
        self.display_stamina: dict[int, float] = {1: 100.0, 2: 100.0}
        self.display_stress: dict[int, float] = {1: 0.0, 2: 0.0}

        self.object_images = {}
        asset_dir = os.path.join(os.path.dirname(__file__), '../../assets')
        image_map = {
            'shield': 'shield.jpg',
            'ice': 'ice.png',
            'illusion': 'illusion.png',
            'normal_positive': 'normal_positive.png',
            'normal_negative': 'normal_negative.png',
        }
        for kind, filename in image_map.items():
            path = os.path.join(asset_dir, filename)
            try:
                img = pygame.image.load(path).convert_alpha()
                self.object_images[kind] = img
            except Exception:
                self.object_images[kind] = None   # will fallback to primitives if image missing
        # --- end image loading ---

    def draw_background(self) -> None:
        self.screen.fill((10, 13, 21))
        canvas_rect = pygame.Rect(0, HUD_HEIGHT, CANVAS_WIDTH, CANVAS_HEIGHT)
        pygame.draw.rect(self.screen, (16, 22, 34), canvas_rect)
        for x in range(0, CANVAS_WIDTH, 48):
            pygame.draw.line(self.screen, (22, 30, 45), (x, HUD_HEIGHT), (x, WINDOW_HEIGHT))
        for y in range(HUD_HEIGHT, WINDOW_HEIGHT, 48):
            pygame.draw.line(self.screen, (22, 30, 45), (0, y), (CANVAS_WIDTH, y))

    def draw_state(
        self,
        state: GameState,
        player_id: int | None,
        role: str,
        cursor: MouseController,
        status: str,
        dt: float,
    ) -> None:
        self.draw_background()
        players = state.get("players", {})
        own_state = (
            players.get(str(player_id), _default_player_state(player_id)) if player_id else _default_player_state(None)
        )
        self._draw_hud(state, players, player_id, role, status, dt)
        self._draw_shapes(state.get("shapes", []))
        self._draw_remote_mice(players, player_id)
        self._draw_events(state.get("events", []))
        if role != "spectator" and player_id:
            self._draw_local_cursor(cursor, own_state)
            self._draw_player_effects(own_state)
        if not state.get("active") and not state.get("ended"):
            self._draw_waiting_overlay(state)
        if state.get("ended"):
            self._draw_end_overlay(state, players, player_id)

    def _draw_hud(
        self,
        state: GameState,
        players: dict[str, PlayerState],
        player_id: int | None,
        role: str,
        status: str,
        dt: float,
    ) -> None:
        y_offset = 0

        pygame.draw.rect(self.screen, (13, 18, 29), (0, 0, WINDOW_WIDTH, HUD_HEIGHT))
        title = self.font.render("Course Predator: Registration Race", True, (242, 246, 255))
        self.screen.blit(title, (22, 55 + y_offset))
        time_left = self.big.render(f"{state.get('time_left', 0):04.1f}s", True, (255, 222, 119))
        self.screen.blit(time_left, time_left.get_rect(midtop=(WINDOW_WIDTH // 2, 10 + y_offset)))
        role_text = "Spectator" if role == "spectator" else f"Player {player_id}"
        status_surface = self.small.render(f"{role_text} • {status}", True, (163, 178, 198))
        self.screen.blit(status_surface, (22, 90 + y_offset))

        for idx, player_key in enumerate(("1", "2")):
            player = players.get(player_key, _default_player_state(idx + 1))
            left = 22 + idx * 595
            name = player.get("name", f"Player {player_key}")
            score = score_text(float(player.get("score", 0.0)))
            name_color = (99, 201, 255) if player.get("id") == player_id else (229, 236, 245)
            label = self.font.render(f"{name}: {score}", True, name_color)
            self.screen.blit(label, (left, 140 + y_offset))
            self._draw_bar(left + 160, 150 + y_offset, 150, 16, player, "stamina", idx + 1, (78, 222, 137), dt)
            self._draw_bar(left + 320, 150 + y_offset, 150, 16, player, "stress", idx + 1, (255, 99, 111), dt)
            effects = []
            if float(player.get("shield", 0)) > 0:
                effects.append(f"Shield {player['shield']:.1f}")
            if float(player.get("frozen", 0)) > 0:
                effects.append(f"Frozen {player['frozen']:.1f}")
            effect_text = self.small.render(" | ".join(effects), True, (183, 205, 255))
            self.screen.blit(effect_text, (left + 160, 170 + y_offset))

    def _draw_bar(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        player: PlayerState,
        key: str,
        player_id: int,
        color: Color,
        dt: float,
    ) -> None:
        target = float(player.get(key, 0.0))
        display = self.display_stamina if key == "stamina" else self.display_stress
        display[player_id] += (target - display[player_id]) * min(1.0, dt * 7.0)
        pygame.draw.rect(self.screen, (36, 44, 59), (x, y, width, height), border_radius=7)
        fill_width = int(width * display[player_id] / 100.0)
        pygame.draw.rect(self.screen, color, (x, y, fill_width, height), border_radius=7)
        label = self.small.render(f"{key[:3].upper()} {target:.0f}%", True, (232, 238, 247))
        self.screen.blit(label, (x + 4, y - 21))

    def _draw_shapes(self, shapes: list[ShapeDict]) -> None:
        for shape in shapes:
            x = int(shape["x"])
            y = int(shape["y"]) + HUD_HEIGHT
            radius = int(shape["radius"])
            kind = shape["kind"]

            if kind == 'shield':
                image_key = 'shield'
                text = ""
            elif kind == 'ice':
                image_key = 'ice'
                text = ""
            elif kind == 'illusion':
                image_key = 'illusion'
                text = score_text(float(shape["points"]))
            else:
                points = int(shape["points"])
                image_key = 'normal_positive' if points > 0 else 'normal_negative'
                text = score_text(float(points)) if points > 0 else str(abs(points))

            img = self.object_images.get(image_key)
            if img is not None:
                scaled_img = pygame.transform.scale(img, (radius * 2, radius * 2))
                img_rect = scaled_img.get_rect(center=(x, y))
                self.screen.blit(scaled_img, img_rect)
            else: # fallback
                if kind == 'shield':
                    color = (83, 226, 169)
                    pygame.draw.polygon(
                        self.screen,
                        color,
                        [
                            (x, y - radius),
                            (x + radius, y - radius // 3),
                            (x + radius // 2, y + radius),
                            (x, y + radius // 2),
                            (x - radius // 2, y + radius),
                            (x - radius, y - radius // 3),
                        ],
                    )
                elif kind == 'ice':
                    color = (100, 205, 255)
                    points = [
                        (x + math.cos(i * math.pi / 3) * radius, y + math.sin(i * math.pi / 3) * radius) for i in range(6)
                    ]
                    pygame.draw.polygon(self.screen, color, points)
                elif kind == 'illusion':
                    color = (184, 116, 255)
                    pygame.draw.circle(self.screen, color, (x, y), radius, 3)
                else:
                    points = int(shape["points"])
                    color = (255, 202, 84) if points > 0 else (255, 101, 113)
                    pygame.draw.circle(self.screen, color, (x, y), radius)

            text_surface = self.font.render(text, True, (255, 255, 255))
            if kind == "illusion":
                text_surface = self.font.render(text, True, (218, 190, 255))
            self.screen.blit(text_surface, text_surface.get_rect(center=(x+6, y)))
            ttl = float(shape.get("ttl", 0.0))
            lifetime = max(0.1, float(shape.get("lifetime", 1.0)))
            arc_rect = pygame.Rect(x - radius - 5, y - radius - 5, radius * 2 + 10, radius * 2 + 10)
            pygame.draw.arc(self.screen, (235, 241, 255), arc_rect, 0, math.tau * ttl / lifetime, 3)

    def _draw_remote_mice(self, players: dict[str, PlayerState], player_id: int | None) -> None:
        for key, player in players.items():
            if player.get("id") == player_id:
                continue
            mouse = player.get("mouse")
            if not mouse:
                continue
            x, y = int(mouse[0]), int(mouse[1]) + HUD_HEIGHT
            color = (255, 160, 92) if key == "2" else (97, 203, 255)
            pygame.draw.circle(self.screen, color, (x, y), 8)
            pygame.draw.line(self.screen, color, (x, y), (x + 12, y + 20), 3)
            label = self.small.render(f"P{key}", True, color)
            self.screen.blit(label, (x + 12, y - 16))

    def _draw_events(self, events: list[EventDict]) -> None:
        now = time.monotonic()
        for event in events:
            age = max(0.0, event.get("expires", now) - event.get("time", now))
            alpha = max(70, min(255, int(255 * age / 0.9)))
            text = self.small.render(str(event.get("text", "")), True, (255, 255, 255))
            text.set_alpha(alpha)
            self.screen.blit(text, (int(event.get("x", 0)) + 12, int(event.get("y", 0)) + HUD_HEIGHT - 18))

    def _draw_local_cursor(self, cursor: MouseController, player_state: PlayerState) -> None:
        for x, y, born in cursor.trail:
            age = time.monotonic() - born
            alpha = max(0, int(120 * (1.0 - age / 0.45)))
            trail_surface = pygame.Surface((26, 26), pygame.SRCALPHA)
            pygame.draw.circle(trail_surface, (124, 210, 255, alpha), (13, 13), 10)
            self.screen.blit(trail_surface, (x - 13, y + HUD_HEIGHT - 13))
        x, y = int(cursor.x), int(cursor.y) + HUD_HEIGHT
        frozen = float(player_state.get("frozen", 0.0)) > 0
        exhausted = float(player_state.get("stamina", 100.0)) <= 10.0
        color = (145, 165, 190) if frozen or exhausted else (255, 255, 255)
        pygame.draw.polygon(self.screen, color, [(x, y), (x + 18, y + 9), (x + 8, y + 13), (x + 4, y + 24)])
        pygame.draw.polygon(self.screen, (35, 42, 55), [(x, y), (x + 18, y + 9), (x + 8, y + 13), (x + 4, y + 24)], 2)

    def _draw_player_effects(self, player_state: PlayerState) -> None:
        stamina = float(player_state.get("stamina", 100.0))
        if stamina < 60.0:
            darkness = int(clamp((60.0 - stamina) / 50.0, 0.0, 1.0) * 155)
            overlay = pygame.Surface((WINDOW_WIDTH, CANVAS_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, darkness))
            self.screen.blit(overlay, (0, HUD_HEIGHT))
        if stamina <= 10.0:
            self._center_message("EXHAUSTED - wait for stamina", (255, 126, 136), -40)
        if float(player_state.get("frozen", 0.0)) > 0:
            self._center_message("FROZEN", (118, 217, 255), 10)

    def _draw_waiting_overlay(self, state: GameState) -> None:
        needed = 2 - len(state.get("players", {}))
        self._center_panel(
            f"Waiting for {max(0, needed)} more player(s)...", "The server starts automatically when two players join."
        )

    def _draw_end_overlay(self, state: GameState, players: dict[str, PlayerState], player_id: int | None) -> None:
        winner = state.get("winner")
        if winner is None:
            headline = "Tie!"
        elif winner == player_id:
            headline = "You won!"
        else:
            name = players.get(str(winner), _default_player_state(winner)).get("name", f"Player {winner}")
            headline = f"{name} wins!"
        replay_file = state.get("replay_file") or "saving..."
        self._center_panel(headline, f"{state.get('reason', '')}  Replay: {replay_file}")

    def draw_calibration_overlay(self, progress: float) -> None:
        self._center_panel("Mouse calibration", "Move your mouse in a circle for smoother control.")
        bar_w = int(WINDOW_WIDTH * 0.36)  # ~400 on 1100
        bar_h = 18
        bar_x = (WINDOW_WIDTH - bar_w) // 2
        bar_y = 420
        bar = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(self.screen, (36, 44, 59), bar, border_radius=8)
        pygame.draw.rect(self.screen, (99, 201, 255), (bar.x, bar.y, int(bar_w * progress), bar_h), border_radius=8)

    def draw_connection_lost(self, status: str) -> None:
        self.screen.fill((10, 13, 21))
        self._center_panel("Connection lost", status)

    def _center_message(self, text: str, color: Color, offset_y: int) -> None:
        surface = self.big.render(text, True, color)
        self.screen.blit(
            surface, surface.get_rect(center=(WINDOW_WIDTH // 2, HUD_HEIGHT + CANVAS_HEIGHT // 2 + offset_y))
        )

    def _center_panel(self, headline: str, subtitle: str) -> None:
        # Panel dimensions proportional to window
        panel_w = int(WINDOW_WIDTH * 0.59)
        panel_h = int(WINDOW_HEIGHT * 0.22)
        panel_x = (WINDOW_WIDTH - panel_w) // 2
        panel_y = (WINDOW_HEIGHT - panel_h) // 2
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, (25, 32, 46), panel, border_radius=18)
        pygame.draw.rect(self.screen, (99, 201, 255), panel, 3, border_radius=18)

        headline_surface = self.big.render(headline, True, (255, 255, 255))
        subtitle_surface = self.small.render(subtitle, True, (205, 216, 232))
        self.screen.blit(
            headline_surface, headline_surface.get_rect(center=(panel.centerx, panel.y + int(panel_h * 0.37)))
        )
        self.screen.blit(
            subtitle_surface, subtitle_surface.get_rect(center=(panel.centerx, panel.y + int(panel_h * 0.68)))
        )

    def draw_connection_lost(self, status: str) -> None:
        self.screen.fill((10, 13, 21))
        self._center_panel("Connection lost", status)


def _default_player_state(player_id: int | None) -> PlayerState:
    return {
        "id": player_id or 0,
        "name": f"Player {player_id}" if player_id else "",
        "score": 0.0,
        "stamina": 100.0,
        "stress": 0.0,
        "shield": 0.0,
        "frozen": 0.0,
        "connected": False,
        "mouse": [CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2],
    }