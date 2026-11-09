from __future__ import annotations

import pytest

from course_predator.client.viewport import Viewport, initial_window_size
from course_predator.constants import CANVAS_HEIGHT, CANVAS_WIDTH


@pytest.mark.parametrize("size", [(1920, 1080), (1600, 900), (1920, 1200), (1366, 768), (1280, 720)])
def test_arena_preserves_aspect_ratio_and_round_trips_coordinates(size: tuple[int, int]) -> None:
    viewport = Viewport.from_window(size)
    assert viewport.arena_rect.width / viewport.arena_rect.height == pytest.approx(
        CANVAS_WIDTH / CANVAS_HEIGHT, rel=0.01
    )
    logical = (CANVAS_WIDTH * 0.37, CANVAS_HEIGHT * 0.62)
    physical = viewport.logical_to_screen(*logical)
    assert viewport.screen_to_logical(physical) == pytest.approx(logical, abs=1.5)


def test_wide_windows_put_hud_beside_arena() -> None:
    viewport = Viewport.from_window((1920, 1080))
    assert viewport.is_wide
    assert viewport.hud_rect.left >= viewport.arena_rect.right
    assert viewport.screen_to_logical((0, 0)) is None


def test_narrow_windows_stack_hud_above_arena() -> None:
    viewport = Viewport.from_window((900, 700))
    assert not viewport.is_wide
    assert viewport.hud_rect.bottom <= viewport.arena_rect.top


def test_small_windows_still_produce_a_valid_arena() -> None:
    viewport = Viewport.from_window((640, 480))
    assert viewport.arena_rect.width > 0
    assert viewport.arena_rect.height > 0
    assert viewport.arena_rect.bottom <= 480


def test_logical_delta_uses_uniform_scale() -> None:
    viewport = Viewport.from_window((1920, 1080))
    dx, dy = viewport.logical_delta((round(viewport.scale * 10), round(viewport.scale * -5)))
    assert dx == pytest.approx(10, abs=0.3)
    assert dy == pytest.approx(-5, abs=0.3)


def test_initial_window_is_not_fullscreen() -> None:
    width, height = initial_window_size((1920, 1080))
    assert 1280 <= width < 1920
    assert 720 <= height < 1080
