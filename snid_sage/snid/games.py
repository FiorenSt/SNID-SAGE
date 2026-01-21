"""
Games module (Qt/PySide6).

Historically, SNID SAGE shipped an SDL mini-game. This module now provides the
same public API but implemented with PySide6/Qt only, so no extra game dependency
is required.
"""

from __future__ import annotations

from typing import Callable, Optional

from .space_debris_qt import (
    DEBRIS_HEIGHT,
    DEBRIS_WIDTH,
    GAMES_AVAILABLE,
    PYSIDE6_AVAILABLE,
    clear_analysis_notifications,
    close_game,
    is_game_running,
    notify_analysis_complete,
    notify_analysis_result,
    run_debris_game,
    set_analysis_complete,
    show_game_menu,
    show_game_menu_integrated,
)

# Backward-compatibility alias (older code used PYGAME_AVAILABLE).
PYGAME_AVAILABLE = GAMES_AVAILABLE

__all__ = [
    "DEBRIS_WIDTH",
    "DEBRIS_HEIGHT",
    "GAMES_AVAILABLE",
    "PYSIDE6_AVAILABLE",
    "PYGAME_AVAILABLE",
    "run_debris_game",
    "show_game_menu",
    "show_game_menu_integrated",
    "notify_analysis_complete",
    "notify_analysis_result",
    "clear_analysis_notifications",
    "is_game_running",
    "close_game",
    "set_analysis_complete",
]


def play_game_while_waiting(task_name: str = "SNID processing") -> None:
    """
    GUI-only helper: prompt user (Qt dialog) and optionally start game.
    """
    game_func: Optional[Callable[[], None]] = show_game_menu()
    if game_func:
        game_func()


def run_game_in_thread(task_name: str = "SNID processing"):
    """
    Kept for backward compatibility. The Qt game must run on the GUI thread,
    so this now simply triggers the GUI prompt/launch and returns None.
    """
    play_game_while_waiting(task_name)
    return None