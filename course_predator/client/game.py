"""Pygame game application(main) loop."""

from __future__ import annotations

import time

import pygame

from ..constants import CANVAS_HEIGHT, WINDOW_WIDTH
from ..types import GameState, PlayerState
from .mouse import MouseController
from .network import ConnState, GameClient, NetworkClient
from .renderer import Renderer


class GameApp:
    """Runs the GUI/input thread while GameClient owns match I/O."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, network: NetworkClient) -> None:
        self.screen = screen
        self.clock = clock
        self.client = GameClient(network)
        self.renderer = Renderer(screen)
        self.cursor = MouseController()
        self.running = True
        self.last_mouse_sent = 0.0

    def run(self) -> None:
        pygame.display.set_caption("Course Predator Match")
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()
        self.client.start()
        try:
            while self.running:
                seconds_per_loop = self.clock.tick(60) / 1000.0
                now = time.monotonic()
                snapshot = self.client.snapshot()
                own_state = self._own_state(snapshot.state, snapshot.player_id)
                if self.cursor.calibrating and snapshot.state and snapshot.role != "spectator":
                    self.cursor.ensure_calibration_started(now)
                self.cursor.tick_calibration(now)
                for event in pygame.event.get():
                    self._handle_event(event, own_state, snapshot.player_id, snapshot.role, now)
                if snapshot.role != "spectator" and snapshot.player_id and snapshot.conn_state == ConnState.PLAYING:
                    self.cursor.update_jumps(float(own_state.get("stress", 0.0)), now)
                    if now - self.last_mouse_sent > 0.04:
                        self.client.send_mouse(self.cursor.x, self.cursor.y)
                        self.last_mouse_sent = now
                if snapshot.conn_state == ConnState.DISCONNECTED:
                    self.renderer.draw_connection_lost(snapshot.status)
                elif snapshot.state:
                    self.renderer.draw_state(
                        snapshot.state,
                        snapshot.player_id,
                        snapshot.role,
                        self.cursor,
                        snapshot.status,
                        seconds_per_loop,
                    )
                    if self.cursor.calibrating and snapshot.role != "spectator":
                        self.renderer.draw_calibration_overlay(self.cursor.calibration_progress(now))
                else:
                    self._draw_connecting(snapshot.lobby, snapshot.status)
                pygame.display.flip()
        finally:
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
            self.client.stop()

    def _handle_event(
        self,
        event: pygame.event.Event,
        own_state: PlayerState,
        player_id: int | None,
        role: str,
        now: float,
    ) -> None:
        if event.type == pygame.QUIT or event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.type == pygame.MOUSEMOTION and role != "spectator" and player_id:
            if self.cursor.calibrating:
                self.cursor.handle_calibration_event(event, now)
            else:
                self.cursor.move_from_event(event, own_state, now)
        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and role != "spectator"
            and player_id
            and not self.cursor.calibrating
        ):
            self.client.send_click(self.cursor.x, self.cursor.y)

    def _own_state(self, state: GameState | None, player_id: int | None) -> PlayerState:
        if not state or player_id is None:
            return _default_own_state()
        return state.get("players", {}).get(str(player_id), _default_own_state())

    def _draw_connecting(self, lobby: dict[str, object] | None, status: str) -> None:
        self.screen.fill((10, 13, 21))
        title = self.renderer.big.render("Connecting to course server...", True, (245, 248, 255))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 260)))
        if lobby:
            players = lobby.get("players", [])
            player_names = ", ".join(players) if isinstance(players, list) else "none"
            text = f"Players: {player_names or 'none'} | Needed: {lobby.get('needed', 2)}"
        else:
            text = status
        surface = self.renderer.font.render(text, True, (180, 195, 216))
        self.screen.blit(surface, surface.get_rect(center=(WINDOW_WIDTH // 2, 330)))


def _default_own_state() -> PlayerState:
    return {
        "id": 0,
        "name": "",
        "score": 0.0,
        "stamina": 100.0,
        "stress": 0.0,
        "shield": 0.0,
        "frozen": 0.0,
        "connected": False,
        "mouse": [WINDOW_WIDTH / 2, CANVAS_HEIGHT / 2],
    }
