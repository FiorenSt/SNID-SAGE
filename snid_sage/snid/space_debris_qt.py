"""
Space Debris Cleanup - Qt/PySide6 implementation (no external game dependency).

This ports the previous mini-game to a Qt-native window using:
- QWidget + QPainter for rendering
- QTimer + fixed-step simulation for gameplay timing
- keyPressEvent/keyReleaseEvent for input

The goal is visual and gameplay parity with the previous version.
"""

from __future__ import annotations

import math
import os
import random
import threading
import time
from typing import Callable, List, Optional, Tuple

from platformdirs import user_data_dir

try:
    from PySide6 import QtCore, QtGui, QtWidgets

    PYSIDE6_AVAILABLE = True
except Exception:  # pragma: no cover
    PYSIDE6_AVAILABLE = False
    QtCore = None  # type: ignore[assignment]
    QtGui = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]


# --- Public capability flag -------------------------------------------------

GAMES_AVAILABLE = PYSIDE6_AVAILABLE


# --- Space Debris Game Configuration ---------------------------------------

DEBRIS_WIDTH, DEBRIS_HEIGHT = 1024, 768
DEBRIS_FPS = 60
FRAME_MS = int(1000 / DEBRIS_FPS)

# Ship constants (Space Station/Rectangular)
STATION_WIDTH = 24
STATION_HEIGHT = 16
STATION_THRUST = 0.1
STATION_FRICTION = 0.99
STATION_ROT_SPEED = 3  # degrees per frame

# Bullet constants
BULLET_SPEED = 7
BULLET_LIFE = 90  # frames

# Debris constants
DEBRIS_MIN_SPEED = 1
DEBRIS_MAX_SPEED = 3
DEBRIS_SIZES = {3: 50, 2: 35, 1: 18}

# Boss Battle constants
BOSS_SIZE = 120
BOSS_HEALTH = 15
BOSS_SPEED = 1.5

# Power-up constants
POWERUP_SIZE = 20
POWERUP_LIFE = 300
SHIELD_DURATION = 300
MULTISHOT_DURATION = 180

# Chain reaction constants
CHAIN_RADIUS = 80
EXPLOSION_RADIUS = 40
EXPLOSION_DURATION = 30

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
STATION_COLOR = (0, 200, 255)
DEBRIS_COLOR = (150, 150, 150)
BULLET_COLOR = (255, 255, 0)
BOSS_BULLET_COLOR = (255, 50, 50)
THRUSTER_COLOR = (255, 100, 0)
SPACE_BLUE = (20, 30, 60)
STAR_COLOR = (255, 255, 255)
PANEL_COLOR = (100, 150, 200)
ANTENNA_COLOR = (220, 220, 220)
BOSS_COLOR = (200, 100, 100)
SHIELD_COLOR = (0, 255, 255)
POWERUP_SHIELD_COLOR = (0, 255, 200)
POWERUP_MULTISHOT_COLOR = (255, 0, 255)


# --- Global analysis notification system -----------------------------------

_notif_lock = threading.Lock()
_analysis_notifications: List[str] = []
_show_analysis_complete: bool = False


def notify_analysis_complete(message: str = ">> SNID Analysis Complete! <<") -> None:
    global _analysis_notifications, _show_analysis_complete
    with _notif_lock:
        _analysis_notifications.append(message)
        _show_analysis_complete = True
        if len(_analysis_notifications) > 3:
            _analysis_notifications = _analysis_notifications[-2:]


def notify_analysis_result(result_message: str) -> None:
    global _analysis_notifications
    with _notif_lock:
        _analysis_notifications.append(result_message)


def clear_analysis_notifications() -> None:
    global _analysis_notifications, _show_analysis_complete
    with _notif_lock:
        _analysis_notifications.clear()
        _show_analysis_complete = False


def is_game_running() -> bool:
    """Return True if the Space Debris window is currently visible."""
    try:
        return _active_window is not None and _active_window.isVisible()
    except Exception:
        return False


def set_analysis_complete(result_summary: Optional[str] = None) -> None:
    """Called by the analysis system when SNID analysis completes."""
    # Keep this intentionally minimal: the in-game UI should only show "Results ready"
    # without extra details that can distract the player.
    notify_analysis_complete("Results ready")


# --- High score persistence -------------------------------------------------

_high_score = 0
_high_score_filename = "space_debris_highscore.txt"


def _high_score_path() -> str:
    # Keep stable per-user storage location.
    base = user_data_dir("snid-sage", "snid-sage")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, _high_score_filename)


def load_high_score() -> int:
    """Load high score; migrate legacy local file if present."""
    global _high_score
    new_path = _high_score_path()

    # Migration: old versions wrote to CWD.
    legacy_path = _high_score_filename
    candidates = [new_path, legacy_path] if os.path.exists(legacy_path) else [new_path]

    for p in candidates:
        try:
            with open(p, "r", encoding="utf-8") as f:
                _high_score = int(f.read().strip())
                break
        except (FileNotFoundError, ValueError, OSError):
            continue

    # If legacy exists but new doesn't, persist the loaded value to new.
    try:
        if os.path.exists(legacy_path) and not os.path.exists(new_path):
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(str(_high_score))
    except OSError:
        pass

    return _high_score


def save_high_score(score: int) -> bool:
    """Save new high score if it's better than current."""
    global _high_score
    if score <= _high_score:
        return False
    _high_score = score
    try:
        with open(_high_score_path(), "w", encoding="utf-8") as f:
            f.write(str(_high_score))
        return True
    except OSError:
        return False


# --- Utility helpers --------------------------------------------------------


def _qcolor(rgb: Tuple[int, int, int], alpha: Optional[int] = None) -> "QtGui.QColor":
    c = QtGui.QColor(rgb[0], rgb[1], rgb[2])
    if alpha is not None:
        c.setAlpha(max(0, min(255, alpha)))
    return c


def _poly(points: List[Tuple[float, float]]) -> "QtGui.QPolygonF":
    return QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in points])


def wrap_position(pos: Tuple[float, float]) -> Tuple[float, float]:
    x, y = pos
    return x % DEBRIS_WIDTH, y % DEBRIS_HEIGHT


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def get_station_name(wave_number: int) -> str:
    station_names = [
        "ALPHA",
        "BETA",
        "GAMMA",
        "DELTA",
        "OMEGA",
        "TITAN",
        "NEXUS",
        "APEX",
        "VORTEX",
        "QUANTUM",
        "INFINITY",
        "SUPREMACY",
        "DOMINION",
        "OBLIVION",
        "ANNIHILATOR",
    ]
    index = min(wave_number - 1, len(station_names) - 1)
    return station_names[index]


def get_station_description(wave_number: int) -> str:
    descriptions = [
        "ARMED AND DANGEROUS",
        "HEAVILY FORTIFIED",
        "MILITARY-GRADE THREAT",
        "MAXIMUM FIREPOWER",
        "ULTIMATE BATTLE STATION",
        "COLOSSAL WAR MACHINE",
        "DREADNOUGHT CLASS",
        "PLANET KILLER",
        "REALITY WARPER",
        "QUANTUM DESTROYER",
        "DIMENSIONAL ANNIHILATOR",
        "GALACTIC SUPREMACY UNIT",
        "UNIVERSAL DOMINION CORE",
        "EXISTENCE OBLITERATOR",
        "UNSTOPPABLE FORCE OF DOOM",
    ]
    index = min(wave_number - 1, len(descriptions) - 1)
    return descriptions[index]


# --- Background starfield ---------------------------------------------------


class _ParallaxStarLayer:
    def __init__(self, count: int, speed_y: float, twinkle: bool):
        self.points = [
            [random.random() * DEBRIS_WIDTH, random.random() * DEBRIS_HEIGHT, random.random()]
            for _ in range(count)
        ]
        self.speed_y = speed_y
        self.twinkle = twinkle

    def update(self) -> None:
        for p in self.points:
            p[1] += self.speed_y
            if p[1] >= DEBRIS_HEIGHT:
                p[0] = random.random() * DEBRIS_WIDTH
                p[1] -= DEBRIS_HEIGHT

    def draw(self, painter: "QtGui.QPainter") -> None:
        t = time.time()
        for x, y, s in self.points:
            size = 1 + (1 if s > 0.7 else 0)
            if self.twinkle and int((t + s) * 5) % 4 == 0:
                color = (200, 210, 255)
            else:
                color = (160, 170, 230) if s < 0.4 else (200, 210, 255)
            painter.fillRect(QtCore.QRectF(float(x), float(y), float(size), float(size)), _qcolor(color))


# --- Entities ---------------------------------------------------------------


class SpaceStation:
    def __init__(self):
        self.pos = (DEBRIS_WIDTH // 2, DEBRIS_HEIGHT // 2)
        self.vel = (0.0, 0.0)
        self.angle = 0  # degrees
        self.shield_time = 0
        self.multishot_time = 0

    def update(self, keys: "set[int]") -> None:
        if self.shield_time > 0:
            self.shield_time -= 1
        if self.multishot_time > 0:
            self.multishot_time -= 1

        if QtCore.Qt.Key_Left in keys:
            self.angle += STATION_ROT_SPEED
        if QtCore.Qt.Key_Right in keys:
            self.angle -= STATION_ROT_SPEED

        if QtCore.Qt.Key_Up in keys:
            rad = math.radians(self.angle)
            fx = math.cos(rad) * STATION_THRUST
            fy = -math.sin(rad) * STATION_THRUST
            vx, vy = self.vel
            self.vel = (vx + fx, vy + fy)

        vx, vy = self.vel
        self.vel = (vx * STATION_FRICTION, vy * STATION_FRICTION)
        self.pos = wrap_position((self.pos[0] + self.vel[0], self.pos[1] + self.vel[1]))

    def draw(self, painter: "QtGui.QPainter", keys: Optional["set[int]"] = None) -> None:
        rad = math.radians(self.angle)
        cx, cy = self.pos

        main_length = 20
        main_width = 8
        wing_length = 12
        wing_width = 4

        nose_tip = (cx + main_length * math.cos(rad), cy - main_length * math.sin(rad))
        nose_left = (
            cx + (main_length - 4) * math.cos(rad) - main_width / 2 * math.sin(rad),
            cy - (main_length - 4) * math.sin(rad) - main_width / 2 * math.cos(rad),
        )
        nose_right = (
            cx + (main_length - 4) * math.cos(rad) + main_width / 2 * math.sin(rad),
            cy - (main_length - 4) * math.sin(rad) + main_width / 2 * math.cos(rad),
        )

        mid_left = (
            cx - 2 * math.cos(rad) - main_width / 2 * math.sin(rad),
            cy + 2 * math.sin(rad) - main_width / 2 * math.cos(rad),
        )
        mid_right = (
            cx - 2 * math.cos(rad) + main_width / 2 * math.sin(rad),
            cy + 2 * math.sin(rad) + main_width / 2 * math.cos(rad),
        )

        tail_left = (
            cx - main_length / 2 * math.cos(rad) - main_width / 3 * math.sin(rad),
            cy + main_length / 2 * math.sin(rad) - main_width / 3 * math.cos(rad),
        )
        tail_right = (
            cx - main_length / 2 * math.cos(rad) + main_width / 3 * math.sin(rad),
            cy + main_length / 2 * math.sin(rad) + main_width / 3 * math.cos(rad),
        )

        hull_points = [nose_tip, nose_left, mid_left, tail_left, tail_right, mid_right, nose_right]
        painter.save()
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(_qcolor(STATION_COLOR), 2))
        painter.drawPolygon(_poly(hull_points))

        tail_mid = ((tail_left[0] + tail_right[0]) / 2, (tail_left[1] + tail_right[1]) / 2)
        painter.setPen(QtGui.QPen(_qcolor((200, 240, 255)), 1))
        painter.drawLine(QtCore.QPointF(nose_tip[0], nose_tip[1]), QtCore.QPointF(tail_mid[0], tail_mid[1]))
        painter.setPen(QtGui.QPen(_qcolor((170, 210, 235)), 1))
        painter.drawLine(QtCore.QPointF(mid_left[0], mid_left[1]), QtCore.QPointF(mid_right[0], mid_right[1]))

        wing_offset = 6
        wing_left_outer = (
            cx - wing_offset * math.sin(rad) - wing_length * math.cos(rad + math.pi / 2),
            cy + wing_offset * math.cos(rad) - wing_length * math.sin(rad + math.pi / 2),
        )
        wing_left_inner = (cx - wing_offset * math.sin(rad), cy + wing_offset * math.cos(rad))
        wing_left_tip = (
            cx - wing_offset * math.sin(rad) + wing_width * math.cos(rad + math.pi / 2),
            cy + wing_offset * math.cos(rad) + wing_width * math.sin(rad + math.pi / 2),
        )
        left_poly = [
            wing_left_inner,
            wing_left_outer,
            (
                wing_left_outer[0] + wing_width * math.cos(rad + math.pi / 2),
                wing_left_outer[1] + wing_width * math.sin(rad + math.pi / 2),
            ),
            wing_left_tip,
        ]
        painter.setPen(QtGui.QPen(_qcolor(STATION_COLOR), 2))
        painter.drawPolygon(_poly(left_poly))
        painter.setPen(QtGui.QPen(_qcolor((180, 220, 240)), 1))
        painter.drawLine(QtCore.QPointF(wing_left_inner[0], wing_left_inner[1]), QtCore.QPointF(wing_left_tip[0], wing_left_tip[1]))

        wing_right_outer = (
            cx + wing_offset * math.sin(rad) - wing_length * math.cos(rad - math.pi / 2),
            cy - wing_offset * math.cos(rad) - wing_length * math.sin(rad - math.pi / 2),
        )
        wing_right_inner = (cx + wing_offset * math.sin(rad), cy - wing_offset * math.cos(rad))
        wing_right_tip = (
            cx + wing_offset * math.sin(rad) + wing_width * math.cos(rad - math.pi / 2),
            cy - wing_offset * math.cos(rad) + wing_width * math.sin(rad - math.pi / 2),
        )
        right_poly = [
            wing_right_inner,
            wing_right_outer,
            (
                wing_right_outer[0] + wing_width * math.cos(rad - math.pi / 2),
                wing_right_outer[1] + wing_width * math.sin(rad - math.pi / 2),
            ),
            wing_right_tip,
        ]
        painter.setPen(QtGui.QPen(_qcolor(STATION_COLOR), 2))
        painter.drawPolygon(_poly(right_poly))
        painter.setPen(QtGui.QPen(_qcolor((180, 220, 240)), 1))
        painter.drawLine(QtCore.QPointF(wing_right_inner[0], wing_right_inner[1]), QtCore.QPointF(wing_right_tip[0], wing_right_tip[1]))

        cockpit_x = cx + 12 * math.cos(rad)
        cockpit_y = cy - 12 * math.sin(rad)
        painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(QtCore.QPointF(cockpit_x, cockpit_y), 3, 3)

        engine_x = cx - 8 * math.cos(rad)
        engine_y = cy + 8 * math.sin(rad)
        painter.setPen(QtGui.QPen(_qcolor(STATION_COLOR), 1))
        painter.drawEllipse(QtCore.QPointF(engine_x, engine_y), 2, 2)

        antenna_base_x = cx - 2 * math.cos(rad) + 3 * math.sin(rad)
        antenna_base_y = cy + 2 * math.sin(rad) + 3 * math.cos(rad)
        antenna_tip_x = antenna_base_x + 6 * math.sin(rad)
        antenna_tip_y = antenna_base_y + 6 * math.cos(rad)
        painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
        painter.drawLine(QtCore.QPointF(antenna_base_x, antenna_base_y), QtCore.QPointF(antenna_tip_x, antenna_tip_y))

        if self.shield_time > 0:
            shield_radius = 35
            painter.setPen(QtGui.QPen(_qcolor(SHIELD_COLOR), 2))
            for i in range(3):
                radius = shield_radius - i * 5
                painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)
            painter.setBrush(_qcolor(WHITE))
            painter.setPen(QtCore.Qt.NoPen)
            for i in range(8):
                ang = (self.shield_time * 5 + i * 45) % 360
                spark_x = cx + math.cos(math.radians(ang)) * shield_radius
                spark_y = cy + math.sin(math.radians(ang)) * shield_radius
                painter.drawEllipse(QtCore.QPointF(spark_x, spark_y), 2, 2)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))

        if keys is not None and QtCore.Qt.Key_Up in keys:
            thruster_length = 18
            thruster_width = 8
            back_x = cx - main_length / 2 * math.cos(rad)
            back_y = cy + main_length / 2 * math.sin(rad)
            flame_x = back_x - math.cos(rad) * thruster_length
            flame_y = back_y + math.sin(rad) * thruster_length

            inner_flame_points = [
                (back_x, back_y),
                (
                    back_x + (thruster_width * 0.6) * math.cos(rad + math.pi / 2),
                    back_y - (thruster_width * 0.6) * math.sin(rad + math.pi / 2),
                ),
                (flame_x + 3 * math.cos(rad), flame_y - 3 * math.sin(rad)),
                (
                    back_x + (thruster_width * 0.6) * math.cos(rad - math.pi / 2),
                    back_y - (thruster_width * 0.6) * math.sin(rad - math.pi / 2),
                ),
            ]
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(_qcolor(WHITE, 230))
            painter.drawPolygon(_poly(inner_flame_points))

            outer_flame_points = [
                (back_x, back_y),
                (
                    back_x + thruster_width * math.cos(rad + math.pi / 2),
                    back_y - thruster_width * math.sin(rad + math.pi / 2),
                ),
                (flame_x, flame_y),
                (
                    back_x + thruster_width * math.cos(rad - math.pi / 2),
                    back_y - thruster_width * math.sin(rad - math.pi / 2),
                ),
            ]
            painter.setBrush(_qcolor(THRUSTER_COLOR, 230))
            painter.drawPolygon(_poly(outer_flame_points))

        painter.restore()

    def activate_shield(self) -> None:
        self.shield_time = SHIELD_DURATION

    def activate_multishot(self) -> None:
        self.multishot_time = MULTISHOT_DURATION

    def has_shield(self) -> bool:
        return self.shield_time > 0

    def has_multishot(self) -> bool:
        return self.multishot_time > 0


class EnergyBullet:
    def __init__(self, pos: Tuple[float, float], angle: float):
        rad = math.radians(angle)
        self.pos = pos
        self.vel = (math.cos(rad) * BULLET_SPEED, -math.sin(rad) * BULLET_SPEED)
        self.life = BULLET_LIFE
        self.trail: List[Tuple[float, float]] = []
        self.max_trail_length = 8

    def update(self) -> None:
        self.trail.append(self.pos)
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)
        self.pos = wrap_position((self.pos[0] + self.vel[0], self.pos[1] + self.vel[1]))
        self.life -= 1

    def draw(self, painter: "QtGui.QPainter") -> None:
        for i, trail_pos in enumerate(self.trail):
            alpha = int(255 * (i + 1) / max(1, len(self.trail)))
            trail_size = int(2 * (i + 1) / max(1, len(self.trail)))
            if trail_size <= 0:
                continue
            trail_color = (255, 255 - (255 - alpha), 0)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(_qcolor(trail_color, alpha))
            painter.drawEllipse(QtCore.QPointF(trail_pos[0], trail_pos[1]), trail_size, trail_size)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_qcolor(BULLET_COLOR))
        painter.drawEllipse(QtCore.QPointF(self.pos[0], self.pos[1]), 4, 4)
        painter.setBrush(_qcolor(WHITE))
        painter.drawEllipse(QtCore.QPointF(self.pos[0], self.pos[1]), 2, 2)
        painter.setBrush(_qcolor((255, 255, 200)))
        painter.drawEllipse(QtCore.QPointF(self.pos[0], self.pos[1]), 1, 1)


class BossBullet:
    def __init__(
        self,
        pos: Tuple[float, float],
        target_pos: Optional[Tuple[float, float]] = None,
        wave_number: int = 1,
        *,
        initial_angle: Optional[float] = None,
        speed: Optional[float] = None,
    ):
        self.pos = pos
        self.life = BULLET_LIFE * 2
        self.trail: List[Tuple[float, float]] = []

        speed_multiplier = 0.4 + (wave_number - 1) * 0.1
        speed_multiplier = min(speed_multiplier, 0.9)
        base_speed = BULLET_SPEED * speed_multiplier

        if initial_angle is not None:
            s = speed if speed is not None else base_speed
            self.vel = (math.cos(initial_angle) * s, math.sin(initial_angle) * s)
        else:
            if target_pos is None:
                target_pos = (pos[0], pos[1] + 1)
            dx = target_pos[0] - pos[0]
            dy = target_pos[1] - pos[1]
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.vel = (dx / dist * base_speed, dy / dist * base_speed)
            else:
                self.vel = (0, base_speed)

    @classmethod
    def from_angle(
        cls,
        pos: Tuple[float, float],
        angle_radians: float,
        wave_number: int = 1,
        speed: Optional[float] = None,
    ) -> "BossBullet":
        return cls(pos, None, wave_number, initial_angle=angle_radians, speed=speed)

    def update(self) -> None:
        self.trail.append(self.pos)
        if len(self.trail) > 8:
            self.trail.pop(0)
        self.pos = wrap_position((self.pos[0] + self.vel[0], self.pos[1] + self.vel[1]))
        self.life -= 1

    def draw(self, painter: "QtGui.QPainter") -> None:
        for i, trail_pos in enumerate(self.trail):
            alpha = (i + 1) / max(1, len(self.trail))
            size = int(3 * alpha) + 1
            color_intensity = int(255 * alpha)
            trail_color = (color_intensity, int(color_intensity * 0.2), int(color_intensity * 0.2))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(_qcolor(trail_color, int(255 * alpha)))
            painter.drawEllipse(QtCore.QPointF(trail_pos[0], trail_pos[1]), size, size)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_qcolor(BOSS_BULLET_COLOR))
        painter.drawEllipse(QtCore.QPointF(self.pos[0], self.pos[1]), 6, 6)
        painter.setBrush(_qcolor(WHITE))
        painter.drawEllipse(QtCore.QPointF(self.pos[0], self.pos[1]), 3, 3)


class SatelliteDebris:
    def __init__(self, pos: Optional[Tuple[float, float]] = None, size: int = 3):
        self.size = size
        radius = DEBRIS_SIZES[size]

        if pos is None:
            center_x, center_y = DEBRIS_WIDTH // 2, DEBRIS_HEIGHT // 2
            min_distance = 120
            attempts = 0
            while attempts < 50:
                x = random.randrange(DEBRIS_WIDTH)
                y = random.randrange(DEBRIS_HEIGHT)
                dx = x - center_x
                dy = y - center_y
                d = math.sqrt(dx * dx + dy * dy)
                if d >= min_distance:
                    self.pos = (float(x), float(y))
                    break
                attempts += 1
            else:
                self.pos = (float(random.choice([50, DEBRIS_WIDTH - 50])), float(random.randrange(DEBRIS_HEIGHT)))
        else:
            self.pos = (float(pos[0]), float(pos[1]))

        angle = random.random() * 360
        speed = random.uniform(DEBRIS_MIN_SPEED, DEBRIS_MAX_SPEED)
        self.vel = (math.cos(math.radians(angle)) * speed, -math.sin(math.radians(angle)) * speed)
        self.rotation = 0.0
        self.rotation_speed = random.uniform(-2, 2)
        self.satellite_type = random.choice(["communication", "weather", "navigation", "research"])

        self.body_width = radius * 0.6
        self.body_height = radius * 0.4
        self.panel_width = radius * 0.8
        self.panel_height = radius * 0.2
        self.antennas: List[dict] = []
        self.dishes: List[dict] = []

        if self.satellite_type == "communication":
            self.dishes.append({"pos": (0, -radius * 0.3), "size": radius * 0.4})
            self.antennas.extend(
                [
                    {"start": (radius * 0.2, 0), "end": (radius * 0.6, -radius * 0.3)},
                    {"start": (-radius * 0.2, 0), "end": (-radius * 0.6, -radius * 0.3)},
                    {"start": (0, radius * 0.2), "end": (0, radius * 0.7)},
                ]
            )
        elif self.satellite_type == "weather":
            self.antennas.extend(
                [
                    {"start": (0, -radius * 0.3), "end": (0, -radius * 0.8)},
                    {"start": (radius * 0.3, 0), "end": (radius * 0.7, 0)},
                    {"start": (-radius * 0.3, 0), "end": (-radius * 0.7, 0)},
                ]
            )
        elif self.satellite_type == "navigation":
            self.antennas.extend(
                [
                    {"start": (radius * 0.2, -radius * 0.2), "end": (radius * 0.5, -radius * 0.6)},
                    {"start": (-radius * 0.2, -radius * 0.2), "end": (-radius * 0.5, -radius * 0.6)},
                    {"start": (radius * 0.2, radius * 0.2), "end": (radius * 0.5, radius * 0.6)},
                    {"start": (-radius * 0.2, radius * 0.2), "end": (-radius * 0.5, radius * 0.6)},
                ]
            )
        else:  # research
            self.dishes.append({"pos": (radius * 0.3, 0), "size": radius * 0.25})
            self.antennas.extend(
                [
                    {"start": (-radius * 0.2, -radius * 0.2), "end": (-radius * 0.6, -radius * 0.5)},
                    {"start": (0, radius * 0.3), "end": (0, radius * 0.8)},
                ]
            )

    def update(self) -> None:
        self.pos = wrap_position((self.pos[0] + self.vel[0], self.pos[1] + self.vel[1]))
        self.rotation += self.rotation_speed

    def draw(self, painter: "QtGui.QPainter") -> None:
        rad = math.radians(self.rotation)
        cx, cy = self.pos

        body_corners = [
            (-self.body_width / 2, -self.body_height / 2),
            (self.body_width / 2, -self.body_height / 2),
            (self.body_width / 2, self.body_height / 2),
            (-self.body_width / 2, self.body_height / 2),
        ]
        rotated_body = []
        for dx, dy in body_corners:
            rx = dx * math.cos(rad) - dy * math.sin(rad)
            ry = dx * math.sin(rad) + dy * math.cos(rad)
            rotated_body.append((cx + rx, cy + ry))

        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(_qcolor(DEBRIS_COLOR), 2))
        painter.drawPolygon(_poly(rotated_body))

        if self.size >= 2:
            left_panel = [
                (-self.body_width / 2 - self.panel_width, -self.panel_height / 2),
                (-self.body_width / 2, -self.panel_height / 2),
                (-self.body_width / 2, self.panel_height / 2),
                (-self.body_width / 2 - self.panel_width, self.panel_height / 2),
            ]
            rotated_left = []
            for dx, dy in left_panel:
                rx = dx * math.cos(rad) - dy * math.sin(rad)
                ry = dx * math.sin(rad) + dy * math.cos(rad)
                rotated_left.append((cx + rx, cy + ry))
            painter.setPen(QtGui.QPen(_qcolor(PANEL_COLOR), 1))
            painter.drawPolygon(_poly(rotated_left))

            right_panel = [
                (self.body_width / 2, -self.panel_height / 2),
                (self.body_width / 2 + self.panel_width, -self.panel_height / 2),
                (self.body_width / 2 + self.panel_width, self.panel_height / 2),
                (self.body_width / 2, self.panel_height / 2),
            ]
            rotated_right = []
            for dx, dy in right_panel:
                rx = dx * math.cos(rad) - dy * math.sin(rad)
                ry = dx * math.sin(rad) + dy * math.cos(rad)
                rotated_right.append((cx + rx, cy + ry))
            painter.drawPolygon(_poly(rotated_right))

            for panel in [rotated_left, rotated_right]:
                if len(panel) >= 4:
                    mid_top = ((panel[0][0] + panel[1][0]) / 2, (panel[0][1] + panel[1][1]) / 2)
                    mid_bottom = ((panel[2][0] + panel[3][0]) / 2, (panel[2][1] + panel[3][1]) / 2)
                    painter.setPen(QtGui.QPen(_qcolor(ANTENNA_COLOR), 1))
                    painter.drawLine(QtCore.QPointF(mid_top[0], mid_top[1]), QtCore.QPointF(mid_bottom[0], mid_bottom[1]))

        for dish in self.dishes:
            dish_x = cx + dish["pos"][0] * math.cos(rad) - dish["pos"][1] * math.sin(rad)
            dish_y = cy + dish["pos"][0] * math.sin(rad) + dish["pos"][1] * math.cos(rad)
            painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(dish_x, dish_y), dish["size"] / 2, dish["size"] / 2)
            painter.setPen(QtGui.QPen(_qcolor(DEBRIS_COLOR), 1))
            painter.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(dish_x, dish_y))

        painter.setPen(QtGui.QPen(_qcolor(ANTENNA_COLOR), 1))
        for antenna in self.antennas:
            start_x = cx + antenna["start"][0] * math.cos(rad) - antenna["start"][1] * math.sin(rad)
            start_y = cy + antenna["start"][0] * math.sin(rad) + antenna["start"][1] * math.cos(rad)
            end_x = cx + antenna["end"][0] * math.cos(rad) - antenna["end"][1] * math.sin(rad)
            end_y = cy + antenna["end"][0] * math.sin(rad) + antenna["end"][1] * math.cos(rad)
            painter.drawLine(QtCore.QPointF(start_x, start_y), QtCore.QPointF(end_x, end_y))

        if self.size >= 2:
            internal_size = min(self.body_width, self.body_height) * 0.3
            cross_points_1 = [
                (cx + internal_size * math.cos(rad + math.pi / 4), cy + internal_size * math.sin(rad + math.pi / 4)),
                (cx - internal_size * math.cos(rad + math.pi / 4), cy - internal_size * math.sin(rad + math.pi / 4)),
            ]
            cross_points_2 = [
                (cx + internal_size * math.cos(rad - math.pi / 4), cy + internal_size * math.sin(rad - math.pi / 4)),
                (cx - internal_size * math.cos(rad - math.pi / 4), cy - internal_size * math.sin(rad - math.pi / 4)),
            ]
            painter.setPen(QtGui.QPen(_qcolor(DEBRIS_COLOR), 1))
            painter.drawLine(QtCore.QPointF(cross_points_1[0][0], cross_points_1[0][1]), QtCore.QPointF(cross_points_1[1][0], cross_points_1[1][1]))
            painter.drawLine(QtCore.QPointF(cross_points_2[0][0], cross_points_2[0][1]), QtCore.QPointF(cross_points_2[1][0], cross_points_2[1][1]))


class Explosion:
    def __init__(self, pos: Tuple[float, float], size: int = EXPLOSION_RADIUS):
        self.pos = pos
        self.size = float(size)
        self.max_size = float(size)
        self.duration = EXPLOSION_DURATION
        self.max_duration = EXPLOSION_DURATION

    def update(self) -> None:
        self.duration -= 1
        progress = 1 - (self.duration / self.max_duration)
        if progress < 0.5:
            self.size = self.max_size * (progress * 2)
        else:
            self.size = self.max_size * (2 - progress * 2)

    def draw(self, painter: "QtGui.QPainter") -> None:
        if self.duration <= 0:
            return
        alpha = int(255 * (self.duration / self.max_duration))
        cx, cy = self.pos
        explosion_color = (255, min(255, 150 + alpha // 3), 0)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(_qcolor(explosion_color, alpha), 3))
        painter.drawEllipse(QtCore.QPointF(cx, cy), self.size, self.size)
        if self.size > 10:
            painter.setPen(QtGui.QPen(_qcolor((255, 255, 200), alpha), 2))
            painter.drawEllipse(QtCore.QPointF(cx, cy), self.size * 0.6, self.size * 0.6)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_qcolor(explosion_color, alpha))
        for i in range(8):
            angle = i * math.pi / 4
            particle_dist = self.size * 1.2
            px = cx + math.cos(angle) * particle_dist
            py = cy + math.sin(angle) * particle_dist
            particle_size = max(1, int(self.size * 0.1))
            painter.drawEllipse(QtCore.QPointF(px, py), particle_size, particle_size)

    def is_alive(self) -> bool:
        return self.duration > 0


class PowerUp:
    def __init__(self, pos: Tuple[float, float], powerup_type: str):
        self.pos = pos
        self.type = powerup_type  # 'shield' or 'multishot'
        self.life = POWERUP_LIFE
        self.rotation = 0.0
        self.rotation_speed = 2.0
        self.bob_offset = 0.0
        self.bob_speed = 0.1

    def update(self) -> None:
        self.life -= 1
        self.rotation += self.rotation_speed
        self.bob_offset += self.bob_speed

    def draw(self, painter: "QtGui.QPainter") -> None:
        if self.life <= 0:
            return
        bob_y = math.sin(self.bob_offset) * 3
        x, y = self.pos[0], self.pos[1] + bob_y
        color = POWERUP_SHIELD_COLOR if self.type == "shield" else POWERUP_MULTISHOT_COLOR
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(_qcolor(color), 3))

        if self.type == "shield":
            points = []
            for i in range(6):
                ang = math.radians(self.rotation + i * 60)
                px = x + math.cos(ang) * POWERUP_SIZE * 0.8
                py = y + math.sin(ang) * POWERUP_SIZE * 0.8
                points.append((px, py))
            painter.drawPolygon(_poly(points))
            painter.setPen(QtGui.QPen(_qcolor(WHITE), 2))
            painter.drawEllipse(QtCore.QPointF(x, y), POWERUP_SIZE // 3, POWERUP_SIZE // 3)
        else:
            for i in range(3):
                ang = math.radians(self.rotation + i * 120)
                tip_x = x + math.cos(ang) * POWERUP_SIZE * 0.7
                tip_y = y + math.sin(ang) * POWERUP_SIZE * 0.7
                base_x = x + math.cos(ang) * POWERUP_SIZE * 0.3
                base_y = y + math.sin(ang) * POWERUP_SIZE * 0.3
                painter.setPen(QtGui.QPen(_qcolor(color), 3))
                painter.drawLine(QtCore.QPointF(base_x, base_y), QtCore.QPointF(tip_x, tip_y))
                head_angle1 = ang + math.pi * 0.8
                head_angle2 = ang - math.pi * 0.8
                head1_x = tip_x + math.cos(head_angle1) * 8
                head1_y = tip_y + math.sin(head_angle1) * 8
                head2_x = tip_x + math.cos(head_angle2) * 8
                head2_y = tip_y + math.sin(head_angle2) * 8
                painter.setPen(QtGui.QPen(_qcolor(color), 2))
                painter.drawLine(QtCore.QPointF(tip_x, tip_y), QtCore.QPointF(head1_x, head1_y))
                painter.drawLine(QtCore.QPointF(tip_x, tip_y), QtCore.QPointF(head2_x, head2_y))

    def is_alive(self) -> bool:
        return self.life > 0


class BossSatellite:
    def __init__(self, wave_number: int = 1):
        self.pos = (DEBRIS_WIDTH // 2, 50)
        self.vel = (BOSS_SPEED, 0.0)
        self.angle = 0.0
        self.rotation_speed = 1.0
        self.health = BOSS_HEALTH
        self.max_health = BOSS_HEALTH
        self.phase = 1
        self.size = BOSS_SIZE
        self.last_shot_time = 0
        self.wave_number = wave_number
        self.components = self._create_components()

        # Internal timer for wobble (replaces the old SDL tick source)
        self._t0 = time.time()

    def _create_components(self) -> List[dict]:
        health_multiplier = 1 + (self.wave_number - 1) * 0.2
        comps = []
        comps.append({"type": "body", "pos": (0, 0), "size": 40, "health": int(5 * health_multiplier), "active": True})
        comps.append({"type": "dish", "pos": (-30, -20), "size": 20, "health": int(2 * health_multiplier), "active": True})
        comps.append({"type": "dish", "pos": (30, -20), "size": 20, "health": int(2 * health_multiplier), "active": True})
        comps.append({"type": "panel", "pos": (-50, 0), "size": 25, "health": int(3 * health_multiplier), "active": True})
        comps.append({"type": "panel", "pos": (50, 0), "size": 25, "health": int(3 * health_multiplier), "active": True})
        comps.append({"type": "engine", "pos": (0, 30), "size": 15, "health": int(2 * health_multiplier), "active": True})
        return comps

    def update(self, target_pos: Optional[Tuple[float, float]] = None) -> None:
        self.angle += self.rotation_speed

        if target_pos is not None:
            dx = target_pos[0] - self.pos[0]
            dy = target_pos[1] - self.pos[1]
            dist = math.hypot(dx, dy) + 1e-6
            ux, uy = dx / dist, dy / dist
            orbit_dir = 1 if (self.wave_number % 2 == 0) else -1
            ox, oy = -uy * orbit_dir, ux * orbit_dir

            pursue_strength = 0.5 + 0.02 * self.wave_number + 0.15 * (self.phase - 1)
            orbit_strength = 0.3 + 0.1 * (self.phase - 1)
            standoff = self.size + 90
            repel = 0.0
            if dist < standoff:
                repel = (standoff - dist) / standoff

            t = (time.time() - self._t0) * 2.0
            nx = 0.3 * math.sin(t + self.wave_number)
            ny = 0.3 * math.cos(t * 1.3 + self.phase)

            desired_vx = BOSS_SPEED * (pursue_strength * ux + orbit_strength * ox - repel * ux) + nx
            desired_vy = BOSS_SPEED * (pursue_strength * uy + orbit_strength * oy - repel * uy) + ny

            cur_vx, cur_vy = self.vel
            self.vel = (cur_vx * 0.85 + desired_vx * 0.15, cur_vy * 0.85 + desired_vy * 0.15)
        else:
            self.vel = (BOSS_SPEED * math.sin(self.angle * 0.02), BOSS_SPEED * 0.5)

        self.pos = wrap_position((self.pos[0] + self.vel[0], self.pos[1] + self.vel[1]))

        hp = self.health / max(1, self.max_health)
        if hp > 0.66:
            self.phase = 1
        elif hp > 0.33:
            self.phase = 2
        else:
            self.phase = 3

        self.last_shot_time += 1

    def should_shoot(self, target_pos: Tuple[float, float]) -> bool:
        phase_cooldown = {1: 240, 2: 180, 3: 120}
        return self.last_shot_time >= phase_cooldown.get(self.phase, 240)

    def shoot_at_target(self, target_pos: Tuple[float, float]) -> List[BossBullet]:
        if not self.should_shoot(target_pos):
            return []
        self.last_shot_time = 0
        bullets: List[BossBullet] = []
        if self.phase == 1:
            bullets.append(BossBullet(self.pos, target_pos, self.wave_number))
            if random.random() < 0.25:
                off = math.radians(random.choice([-8, 8]))
                base = math.atan2(target_pos[1] - self.pos[1], target_pos[0] - self.pos[0]) + off
                bullets.append(BossBullet.from_angle(self.pos, base, self.wave_number))
        elif self.phase == 2:
            base = math.atan2(target_pos[1] - self.pos[1], target_pos[0] - self.pos[0])
            for off_deg in (-10, 0, 10):
                bullets.append(BossBullet.from_angle(self.pos, base + math.radians(off_deg), self.wave_number))
        else:
            if random.random() < 0.5:
                count = 8
                base = random.random() * math.tau
                for i in range(count):
                    ang = base + i * (math.tau / count)
                    bullets.append(BossBullet.from_angle(self.pos, ang, self.wave_number, speed=BULLET_SPEED * 0.7))
            else:
                base = math.atan2(target_pos[1] - self.pos[1], target_pos[0] - self.pos[0])
                for off_deg in (-20, -10, 0, 10, 20):
                    bullets.append(BossBullet.from_angle(self.pos, base + math.radians(off_deg), self.wave_number))
        return bullets

    def take_damage(self, bullet_pos: Tuple[float, float]) -> bool:
        for component in self.components:
            if not component["active"]:
                continue
            comp_world_pos = (self.pos[0] + component["pos"][0], self.pos[1] + component["pos"][1])
            if distance(bullet_pos, comp_world_pos) < component["size"]:
                component["health"] -= 1
                if component["health"] <= 0:
                    component["active"] = False
                self.health -= 1
                if not any(c["active"] for c in self.components):
                    self.health = 0
                return True
        return False

    def draw(self, painter: "QtGui.QPainter") -> None:
        cx, cy = self.pos
        scale = self.size / BOSS_SIZE

        any_visible = False
        for component in self.components:
            if not component["active"]:
                continue
            any_visible = True
            comp_x = cx + component["pos"][0] * scale
            comp_y = cy + component["pos"][1] * scale
            comp_size = int(component["size"] * scale)

            if component["type"] == "body":
                color_intensity = min(255, 200 + (self.wave_number * 10))
                color = (color_intensity, max(100 - self.wave_number * 5, 50), max(100 - self.wave_number * 5, 50))
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtGui.QPen(_qcolor(color), 3))
                points: List[Tuple[float, float]] = []
                if self.wave_number <= 3:
                    for i in range(6):
                        ang = math.radians(self.angle + i * 60)
                        points.append((comp_x + math.cos(ang) * comp_size, comp_y + math.sin(ang) * comp_size))
                elif self.wave_number <= 6:
                    for i in range(8):
                        ang = math.radians(self.angle + i * 45)
                        points.append((comp_x + math.cos(ang) * comp_size, comp_y + math.sin(ang) * comp_size))
                else:
                    for i in range(12):
                        ang = math.radians(self.angle + i * 30)
                        r = comp_size if i % 2 == 0 else comp_size * 0.6
                        points.append((comp_x + math.cos(ang) * r, comp_y + math.sin(ang) * r))
                painter.drawPolygon(_poly(points))

            elif component["type"] == "dish":
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtGui.QPen(_qcolor(ANTENNA_COLOR), 2))
                painter.drawEllipse(QtCore.QPointF(comp_x, comp_y), comp_size, comp_size)
                painter.setPen(QtGui.QPen(_qcolor(DEBRIS_COLOR), 2))
                painter.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(comp_x, comp_y))

            elif component["type"] == "panel":
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtGui.QPen(_qcolor(PANEL_COLOR), 2))
                rect = QtCore.QRectF(comp_x - comp_size, comp_y - comp_size / 2, comp_size * 2, comp_size)
                painter.drawRect(rect)

            elif component["type"] == "engine":
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtGui.QPen(_qcolor(THRUSTER_COLOR), 2))
                painter.drawEllipse(QtCore.QPointF(comp_x, comp_y), comp_size, comp_size)
                if self.phase >= 2 or self.wave_number >= 3:
                    flame_count = min(3 + self.wave_number, 8)
                    painter.setPen(QtCore.Qt.NoPen)
                    for _ in range(flame_count):
                        flame_x = comp_x + random.randint(-8, 8)
                        flame_y = comp_y + 20 + random.randint(0, 15)
                        flame_size = 3 + (self.wave_number // 3)
                        flame_color = (255, 100 + (self.wave_number * 10) % 155, 0)
                        painter.setBrush(_qcolor(flame_color, 200))
                        painter.drawEllipse(QtCore.QPointF(flame_x, flame_y), flame_size, flame_size)

        if not any_visible and self.health > 0:
            core_size = 15
            pulse = int(20 * math.sin((time.time() - self._t0) * 10))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(_qcolor((255, 100, 100), 180))
            painter.drawEllipse(QtCore.QPointF(cx, cy), core_size + pulse, core_size + pulse)
            painter.setBrush(_qcolor((255, 255, 255), 220))
            painter.drawEllipse(QtCore.QPointF(cx, cy), core_size // 2, core_size // 2)

        # Health bar
        bar_width = 100
        bar_height = 8
        bar_x = cx - bar_width / 2
        bar_y = cy - self.size - 20
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_qcolor((100, 100, 100), 220))
        painter.drawRect(QtCore.QRectF(bar_x, bar_y, bar_width, bar_height))
        health_width = int((self.health / max(1, self.max_health)) * bar_width)
        health_color = (255, 0, 0) if self.health < 5 else (255, 255, 0) if self.health < 10 else (0, 255, 0)
        painter.setBrush(_qcolor(health_color, 230))
        painter.drawRect(QtCore.QRectF(bar_x, bar_y, health_width, bar_height))

        # Boss name
        painter.setPen(QtGui.QPen(_qcolor(BOSS_COLOR), 1))
        font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        painter.setFont(font)
        station_name = get_station_name(self.wave_number)
        text = f">> HOSTILE STATION {station_name} <<"
        painter.drawText(QtCore.QRectF(cx - 180, bar_y - 35, 360, 20), QtCore.Qt.AlignCenter, text)

    def is_alive(self) -> bool:
        return self.health > 0 and any(c["active"] for c in self.components)

    def get_collision_radius(self) -> float:
        any_active = any(c["active"] for c in self.components)
        if not any_active and self.health > 0:
            return 25
        return self.size * 0.8


# --- Qt Game Widget/Window --------------------------------------------------


class SpaceDebrisWidget(QtWidgets.QWidget):
    def __init__(
        self,
        parent: Optional["QtWidgets.QWidget"] = None,
        *,
        display_size: Optional["QtCore.QSize"] = None,
        logical_size: Tuple[int, int] = (DEBRIS_WIDTH, DEBRIS_HEIGHT),
    ):
        super().__init__(parent)
        self._logical_width, self._logical_height = logical_size
        if display_size is None:
            display_size = QtCore.QSize(self._logical_width, self._logical_height)
        self.setFixedSize(display_size)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocus()

        self._pressed_keys: set[int] = set()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._elapsed = QtCore.QElapsedTimer()
        self._accum_ms = 0
        self._max_steps_per_tick = 3

        # Background layers
        self._stars_far = _ParallaxStarLayer(count=120, speed_y=0.05, twinkle=False)
        self._stars_mid = _ParallaxStarLayer(count=80, speed_y=0.10, twinkle=True)
        self._stars_near = _ParallaxStarLayer(count=60, speed_y=0.18, twinkle=True)

        # Fonts
        self._font = QtGui.QFont("Arial", 12)
        self._big_font = QtGui.QFont("Arial", 22, QtGui.QFont.Bold)

        self._init_game()
        self._elapsed.start()
        self._timer.start(FRAME_MS)

    # --- lifecycle ---------------------------------------------------------

    def closeEvent(self, event: "QtGui.QCloseEvent") -> None:
        try:
            self._timer.stop()
        finally:
            super().closeEvent(event)

    # --- input --------------------------------------------------------------

    def keyPressEvent(self, event: "QtGui.QKeyEvent") -> None:
        key = int(event.key())
        if not event.isAutoRepeat():
            self._pressed_keys.add(key)

            if key == int(QtCore.Qt.Key_Space) and not self.game_over:
                self._fire_bullets()
            elif key == int(QtCore.Qt.Key_Escape):
                self.window().close()
            elif key == int(QtCore.Qt.Key_R) and self.game_over:
                self._init_game()

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: "QtGui.QKeyEvent") -> None:
        key = int(event.key())
        if not event.isAutoRepeat():
            self._pressed_keys.discard(key)
        super().keyReleaseEvent(event)

    # --- game state ---------------------------------------------------------

    def _init_game(self) -> None:
        load_high_score()
        self.station = SpaceStation()
        self.bullets: List[EnergyBullet] = []
        self.boss_bullets: List[BossBullet] = []
        self.debris_field: List[SatelliteDebris] = [SatelliteDebris(size=3) for _ in range(5)]
        self.explosions: List[Explosion] = []
        self.powerups: List[PowerUp] = []
        self.boss: Optional[BossSatellite] = None
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.invulnerable_time = 0
        self.wave_number = 1
        self.boss_defeated = False
        self.new_high_score = False
        clear_analysis_notifications()

    def _create_chain_explosion(self, pos: Tuple[float, float], debris_list: List[SatelliteDebris], current_score: int) -> int:
        self.explosions.append(Explosion(pos, EXPLOSION_RADIUS))

        chain_debris: List[SatelliteDebris] = []
        debris_to_remove: List[SatelliteDebris] = []

        for debris in list(debris_list):
            if distance(pos, debris.pos) < CHAIN_RADIUS:
                chain_debris.append(debris)
                debris_to_remove.append(debris)
                current_score += 50 * debris.size
                if random.random() < 0.3:
                    powerup_type = random.choice(["shield", "multishot"])
                    self.powerups.append(PowerUp(debris.pos, powerup_type))

        for debris in debris_to_remove:
            if debris in debris_list:
                debris_list.remove(debris)

        def delayed_explosion() -> None:
            for d in chain_debris:
                if d is not None and random.random() < 0.7:
                    def safe_chain_explosion(dd: SatelliteDebris = d) -> None:
                        if dd is not None and hasattr(dd, "pos"):
                            self._create_chain_explosion(dd.pos, self.debris_field, 0)

                    threading.Timer(0.3, safe_chain_explosion).start()

        if chain_debris:
            threading.Timer(0.2, delayed_explosion).start()

        return current_score

    def _fire_bullets(self) -> None:
        if self.station.has_multishot():
            angles = [self.station.angle - 15, self.station.angle, self.station.angle + 15]
            for a in angles:
                self.bullets.append(EnergyBullet(self.station.pos, a))
        else:
            self.bullets.append(EnergyBullet(self.station.pos, self.station.angle))

    # --- simulation tick ----------------------------------------------------

    def _tick(self) -> None:
        now = self._elapsed.elapsed()
        self._elapsed.restart()
        self._accum_ms += int(now)

        steps = 0
        while self._accum_ms >= FRAME_MS and steps < self._max_steps_per_tick:
            self._step()
            self._accum_ms -= FRAME_MS
            steps += 1

        # Avoid spiral-of-death if system stalls.
        self._accum_ms = min(self._accum_ms, FRAME_MS * self._max_steps_per_tick)
        self.update()

    def _step(self) -> None:
        if self.game_over:
            return

        if self.invulnerable_time > 0:
            self.invulnerable_time -= 1

        keys = self._pressed_keys
        self.station.update(keys)

        for b in list(self.bullets):
            b.update()
            if b.life <= 0 and b in self.bullets:
                self.bullets.remove(b)

        for ex in list(self.explosions):
            ex.update()
            if not ex.is_alive() and ex in self.explosions:
                self.explosions.remove(ex)

        for p in list(self.powerups):
            p.update()
            if not p.is_alive() and p in self.powerups:
                self.powerups.remove(p)
            else:
                if distance(self.station.pos, p.pos) < 30:
                    if p.type == "shield":
                        self.station.activate_shield()
                    elif p.type == "multishot":
                        self.station.activate_multishot()
                    if p in self.powerups:
                        self.powerups.remove(p)
                    self.score += 200

        for debris in list(self.debris_field):
            debris.update()

            for b in list(self.bullets):
                if distance(debris.pos, b.pos) < DEBRIS_SIZES[debris.size] * 0.5:
                    if b in self.bullets:
                        self.bullets.remove(b)
                    if debris in self.debris_field:
                        self.debris_field.remove(debris)
                    self.score += 150 * debris.size
                    self.score = self._create_chain_explosion(debris.pos, self.debris_field, self.score)
                    if random.random() < 0.15:
                        powerup_type = random.choice(["shield", "multishot"])
                        self.powerups.append(PowerUp(debris.pos, powerup_type))
                    if debris.size > 1:
                        self.debris_field += [SatelliteDebris(pos=debris.pos, size=debris.size - 1) for _ in range(2)]
                    break

            if self.invulnerable_time <= 0 and not self.station.has_shield():
                station_collision_radius = max(STATION_WIDTH, STATION_HEIGHT) * 0.7
                debris_collision_radius = DEBRIS_SIZES[debris.size] * 0.4
                if distance(self.station.pos, debris.pos) < (station_collision_radius + debris_collision_radius):
                    self.lives -= 1
                    self.invulnerable_time = 120
                    self.score = self._create_chain_explosion(debris.pos, self.debris_field, self.score)
                    if debris in self.debris_field:
                        self.debris_field.remove(debris)
                    if self.lives <= 0:
                        self.game_over = True
                        self.new_high_score = save_high_score(self.score)
                    else:
                        self.station = SpaceStation()
                    break

        for bb in list(self.boss_bullets):
            bb.update()
            if bb.life <= 0 and bb in self.boss_bullets:
                self.boss_bullets.remove(bb)
                continue

            bullet_hit = False
            for pb in list(self.bullets):
                if distance(bb.pos, pb.pos) < 15:
                    if bb in self.boss_bullets:
                        self.boss_bullets.remove(bb)
                    if pb in self.bullets:
                        self.bullets.remove(pb)
                    self.explosions.append(Explosion(bb.pos, 15))
                    self.score += 100
                    bullet_hit = True
                    break
            if bullet_hit:
                continue

            if self.invulnerable_time <= 0 and not self.station.has_shield():
                if distance(self.station.pos, bb.pos) < 25:
                    if bb in self.boss_bullets:
                        self.boss_bullets.remove(bb)
                    self.lives -= 1
                    self.invulnerable_time = 120
                    self.explosions.append(Explosion(bb.pos, 30))
                    if self.lives <= 0:
                        self.game_over = True
                        self.new_high_score = save_high_score(self.score)
                    else:
                        self.station = SpaceStation()
                    break

        if self.boss is not None:
            self.boss.update(self.station.pos)
            new_bullets = self.boss.shoot_at_target(self.station.pos)
            if new_bullets:
                self.boss_bullets.extend(new_bullets)

            for b in list(self.bullets):
                if distance(self.boss.pos, b.pos) < self.boss.get_collision_radius():
                    if self.boss.take_damage(b.pos):
                        if b in self.bullets:
                            self.bullets.remove(b)
                        self.score += 500
                        self.explosions.append(Explosion(b.pos, 20))

            if self.invulnerable_time <= 0 and not self.station.has_shield():
                if distance(self.station.pos, self.boss.pos) < self.boss.get_collision_radius():
                    self.lives -= 1
                    self.invulnerable_time = 120
                    if self.lives <= 0:
                        self.game_over = True
                        self.new_high_score = save_high_score(self.score)
                    else:
                        self.station = SpaceStation()

            if not self.boss.is_alive():
                boss_pos = self.boss.pos
                self.score = self._create_chain_explosion(boss_pos, [], self.score)
                self.explosions.append(Explosion(boss_pos, 100))
                self.score += 5000 + (self.wave_number * 1000)
                self.boss_defeated = True
                for i in range(3):
                    ang = i * 120
                    px = boss_pos[0] + math.cos(math.radians(ang)) * 50
                    py = boss_pos[1] + math.sin(math.radians(ang)) * 50
                    powerup_type = ["shield", "multishot"][i % 2]
                    self.powerups.append(PowerUp((px, py), powerup_type))
                wave_size = min(4 + self.wave_number, 10)
                self.debris_field = [SatelliteDebris(size=3) for _ in range(wave_size)]
                self.boss = None
                self.wave_number += 1

        if not self.debris_field and not self.game_over and self.boss is None:
            self.boss = BossSatellite(self.wave_number)
            health_multiplier = 1 + (self.wave_number - 1) * 0.2
            total_component_health = int(17 * health_multiplier)
            self.boss.health = total_component_health
            self.boss.max_health = self.boss.health
            self.boss.size = BOSS_SIZE + (self.wave_number - 1) * 10
            self.boss_defeated = False

    # --- painting -----------------------------------------------------------

    def paintEvent(self, event: "QtGui.QPaintEvent") -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Fill the full window (letterbox area) in black.
        painter.fillRect(self.rect(), _qcolor(BLACK))

        # Scale + center the logical game canvas into the available widget size.
        sx = self.width() / max(1, self._logical_width)
        sy = self.height() / max(1, self._logical_height)
        scale = min(sx, sy)
        offset_x = (self.width() - self._logical_width * scale) / 2
        offset_y = (self.height() - self._logical_height * scale) / 2

        painter.save()
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)

        # Draw background + starfield in logical coordinates.
        painter.fillRect(
            QtCore.QRectF(0, 0, float(self._logical_width), float(self._logical_height)),
            _qcolor(SPACE_BLUE),
        )
        self._stars_far.update()
        self._stars_mid.update()
        self._stars_near.update()
        self._stars_far.draw(painter)
        self._stars_mid.draw(painter)
        self._stars_near.draw(painter)

        if not self.game_over:
            if self.invulnerable_time <= 0 or (self.invulnerable_time // 5) % 2 == 0:
                self.station.draw(painter, self._pressed_keys)

        for ex in self.explosions:
            ex.draw(painter)
        for b in self.bullets:
            b.draw(painter)
        for bb in self.boss_bullets:
            bb.draw(painter)
        for d in self.debris_field:
            d.draw(painter)
        for p in self.powerups:
            p.draw(painter)
        if self.boss is not None:
            self.boss.draw(painter)

        # UI
        painter.setFont(self._font)
        painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
        painter.drawText(10, 25, f"Score: {self.score}")
        hs_color = (255, 215, 0) if self.score > _high_score else (150, 150, 150)
        painter.setPen(QtGui.QPen(_qcolor(hs_color), 1))
        painter.drawText(10, 50, f"High Score: {_high_score}")
        painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
        painter.drawText(10, 75, f"Lives: {self.lives}")
        painter.drawText(10, 100, f"Wave: {self.wave_number}")
        painter.drawText(10, 125, f"Debris: {len(self.debris_field)}")

        y = 150
        if self.station.has_shield():
            painter.setPen(QtGui.QPen(_qcolor(SHIELD_COLOR), 1))
            painter.drawText(10, y, f"Shield: {self.station.shield_time // 60 + 1}s")
            y += 25
        if self.station.has_multishot():
            painter.setPen(QtGui.QPen(_qcolor(POWERUP_MULTISHOT_COLOR), 1))
            painter.drawText(10, y, f"Multishot: {self.station.multishot_time // 60 + 1}s")
            y += 25
        if self.invulnerable_time > 0 and not self.game_over:
            painter.setPen(QtGui.QPen(_qcolor((255, 100, 100)), 1))
            painter.drawText(10, y, f"Hull Breach: {self.invulnerable_time // 60 + 1}s")

        if self.boss is not None and not self.game_over:
            painter.setFont(self._big_font)
            painter.setPen(QtGui.QPen(_qcolor(BOSS_COLOR), 1))
            painter.drawText(
                QtCore.QRectF(0, 5, float(self._logical_width), 40),
                QtCore.Qt.AlignCenter,
                ">>> BOSS BATTLE <<<",
            )
            painter.setFont(self._font)

        # Story text
        painter.setFont(self._font)
        if self.boss_defeated:
            destroyed_station = get_station_name(self.wave_number - 1)
            painter.setPen(QtGui.QPen(_qcolor((100, 255, 100)), 1))
            story = f">> STATION {destroyed_station} DESTROYED! Next wave incoming... <<"
        elif self.boss is not None:
            station_name = get_station_name(self.boss.wave_number)
            station_desc = get_station_description(self.boss.wave_number)
            painter.setPen(QtGui.QPen(_qcolor(BOSS_COLOR), 1))
            story = f">> HOSTILE STATION {station_name} - {station_desc}! <<"
        else:
            painter.setPen(QtGui.QPen(_qcolor((100, 100, 255)), 1))
            story = "Mission: Clean up satellite debris - Boss stations will attack!"
        painter.drawText(10, self._logical_height - 10, story)

        # Results-ready badge (top-right; non-blocking)
        with _notif_lock:
            notifs = list(_analysis_notifications)
            show_complete = _show_analysis_complete

        if show_complete:
            # Minimal text-only indicator in the top-right, no background.
            painter.save()
            painter.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
            painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
            margin = 10
            text = "Results ready"
            painter.drawText(
                QtCore.QRectF(0, 0, float(self._logical_width - margin), 24),
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTop,
                text,
            )
            painter.restore()

        if self.game_over:
            painter.setFont(self._big_font)
            painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
            title = "MISSION COMPLETE" if self.lives > 0 else "STATION DESTROYED"
            painter.drawText(
                QtCore.QRectF(0, self._logical_height / 2 - 120, float(self._logical_width), 40),
                QtCore.Qt.AlignCenter,
                title,
            )
            painter.setFont(self._font)
            painter.drawText(
                QtCore.QRectF(0, self._logical_height / 2 - 60, float(self._logical_width), 30),
                QtCore.Qt.AlignCenter,
                f"Final Score: {self.score}",
            )
            if self.new_high_score:
                painter.setPen(QtGui.QPen(_qcolor((255, 215, 0)), 1))
                painter.drawText(
                    QtCore.QRectF(0, self._logical_height / 2 - 25, float(self._logical_width), 30),
                    QtCore.Qt.AlignCenter,
                    ">>> NEW HIGH SCORE! <<<",
                )
            else:
                painter.setPen(QtGui.QPen(_qcolor((150, 150, 150)), 1))
                painter.drawText(
                    QtCore.QRectF(0, self._logical_height / 2 - 25, float(self._logical_width), 30),
                    QtCore.Qt.AlignCenter,
                    f"High Score: {_high_score}",
                )
            painter.setPen(QtGui.QPen(_qcolor(WHITE), 1))
            painter.drawText(
                QtCore.QRectF(0, self._logical_height / 2 + 30, float(self._logical_width), 30),
                QtCore.Qt.AlignCenter,
                "Press R to Restart or ESC to Exit",
            )

        painter.restore()
        painter.end()


class SpaceDebrisWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        *,
        parent_window: Optional["QtWidgets.QWidget"] = None,
        force_on_top: bool = False,
    ):
        super().__init__(parent_window)
        self.setWindowTitle("Space Debris Cleanup – Enhanced with Boss Battles!")

        # Window stacking behavior:
        # - If launched from the analysis progress dialog, we want it above that dialog so gameplay is usable.
        flags = QtCore.Qt.Window
        if parent_window is not None:
            flags |= QtCore.Qt.Tool
        if force_on_top:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        # Choose a size that fits the current screen (important for laptops / small displays).
        display_size = self._suggest_display_size(parent_window)
        self.setFixedSize(display_size)
        self._widget = SpaceDebrisWidget(self, display_size=display_size)
        self.setCentralWidget(self._widget)

    @staticmethod
    def _suggest_display_size(parent_window: Optional["QtWidgets.QWidget"]) -> "QtCore.QSize":
        screen = None
        try:
            if parent_window is not None and parent_window.windowHandle() is not None:
                screen = parent_window.windowHandle().screen()
        except Exception:
            screen = None
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else QtCore.QRect(0, 0, DEBRIS_WIDTH, DEBRIS_HEIGHT)

        # Target: up to 90% of available area, preserve aspect ratio.
        max_w = max(320, int(avail.width() * 0.90))
        max_h = max(240, int(avail.height() * 0.90))
        scale = min(max_w / DEBRIS_WIDTH, max_h / DEBRIS_HEIGHT, 1.0)
        return QtCore.QSize(int(DEBRIS_WIDTH * scale), int(DEBRIS_HEIGHT * scale))

    def show_and_focus(self, *, force_on_top: bool = False) -> None:
        if force_on_top:
            # Ensure on-top flag is applied even for an existing window.
            self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        self.show()
        # Try hard to bring to the foreground.
        self.raise_()
        self.activateWindow()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self._widget.setFocus()
        self.show()
        self.raise_()
        self.activateWindow()
        self._widget.setFocus()


class _QtInvoker(QtCore.QObject):
    @QtCore.Slot(object)
    def invoke(self, fn: object) -> None:
        try:
            if callable(fn):
                fn()
        except Exception:
            pass


_invoker: Optional[_QtInvoker] = None
_active_window: Optional[SpaceDebrisWindow] = None


def _ensure_invoker(app: "QtWidgets.QApplication") -> _QtInvoker:
    global _invoker
    if _invoker is None:
        _invoker = _QtInvoker()
        _invoker.moveToThread(app.thread())
    return _invoker


def close_game() -> None:
    """Close the Space Debris window if it is running."""
    global _active_window
    try:
        if _active_window is not None and _active_window.isVisible():
            _active_window.close()
    except Exception:
        pass


def run_debris_game(*, parent_window: Optional["QtWidgets.QWidget"] = None, force_on_top: bool = False) -> None:
    """
    Launch the Space Debris Cleanup window (non-blocking).

    GUI-only: requires a running Qt application.
    """
    if not PYSIDE6_AVAILABLE:
        return

    app = QtWidgets.QApplication.instance()
    if app is None:
        # GUI-only mode: if there's no app, do nothing (safe for CLI/headless).
        return

    def _start() -> None:
        global _active_window
        if _active_window is not None and _active_window.isVisible():
            _active_window.show_and_focus(force_on_top=force_on_top)
            return
        _active_window = SpaceDebrisWindow(parent_window=parent_window, force_on_top=force_on_top)
        _active_window.show_and_focus(force_on_top=force_on_top)

    # If called from a non-Qt thread, queue to the main thread.
    if QtCore.QThread.currentThread() != app.thread():
        inv = _ensure_invoker(app)
        QtCore.QMetaObject.invokeMethod(
            inv,
            "invoke",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(object, _start),
        )
    else:
        _start()


def show_game_menu() -> Optional[Callable[[], None]]:
    """GUI-only: show a simple Qt prompt; returns launch function or None."""
    if not PYSIDE6_AVAILABLE:
        return None
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("🛰️ Space Debris Cleanup")
    dialog.setModal(True)
    dialog.resize(480, 380)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(20, 20, 20, 20)

    title = QtWidgets.QLabel("🛰️ Space Debris Cleanup")
    title.setStyleSheet("font-size: 18px; font-weight: bold;")
    layout.addWidget(title)

    subtitle = QtWidgets.QLabel("Advanced space simulation while SNID analysis runs")
    subtitle.setStyleSheet("color: gray;")
    layout.addWidget(subtitle)

    desc_text = (
        "🚀 Pilot a detailed spacecraft with wings and thrusters\n"
        "🛰️ Clean up realistic satellite debris\n"
        "⚡ Energy bullets with particle trail effects\n"
        "🌌 Deep space background with twinkling stars\n"
        "📡 Boss battles, chain explosions, power-ups"
    )
    desc = QtWidgets.QLabel(desc_text)
    desc.setAlignment(QtCore.Qt.AlignLeft)
    desc.setStyleSheet("background:#34495e; color:#ecf0f1; padding:10px;")
    layout.addWidget(desc)

    btn_start = QtWidgets.QPushButton("Start Space Debris Cleanup")
    btn_start.setStyleSheet("background:#e74c3c; color:white; padding:10px; font-weight: bold;")
    btn_cancel = QtWidgets.QPushButton("❌ No Thanks")
    btn_cancel.setStyleSheet("background:#7f8c8d; color:white; padding:8px;")
    row = QtWidgets.QHBoxLayout()
    row.addWidget(btn_start)
    row.addWidget(btn_cancel)
    layout.addLayout(row)

    selected = {"fn": None}

    def accept() -> None:
        selected["fn"] = run_debris_game
        dialog.accept()

    def reject() -> None:
        selected["fn"] = None
        dialog.reject()

    btn_start.clicked.connect(accept)
    btn_cancel.clicked.connect(reject)
    dialog.exec()
    return selected["fn"]


def show_game_menu_integrated(parent_window, callback=None):
    """
    Return a small embedded Qt frame with Start/Cancel buttons.
    """
    if not PYSIDE6_AVAILABLE:
        return None

    frame = QtWidgets.QFrame(parent_window if isinstance(parent_window, QtWidgets.QWidget) else None)
    frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
    frame.setStyleSheet("background-color: #2c3e50;")

    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(20, 15, 20, 15)

    title = QtWidgets.QLabel("Space Debris Cleanup!")
    title.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 16px;")
    layout.addWidget(title)

    subtitle = QtWidgets.QLabel("Realistic space simulation while SNID analysis runs")
    subtitle.setStyleSheet("color: #bdc3c7; font-size: 11px;")
    layout.addWidget(subtitle)

    desc = QtWidgets.QLabel(
        "Pilot a detailed spacecraft with wings and thrusters\n"
        "Clean up realistic satellite debris\n"
        "Energy bullets with particle trail effects\n"
        "Deep space background with twinkling stars\n"
        "Boss battles and power-ups"
    )
    desc.setAlignment(QtCore.Qt.AlignCenter)
    desc.setStyleSheet("color: #95a5a6; font-size: 11px;")
    layout.addWidget(desc)

    button_row = QtWidgets.QHBoxLayout()
    layout.addLayout(button_row)

    start_btn = QtWidgets.QPushButton("Start Space Debris Cleanup")
    start_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px; font-weight: bold;")
    cancel_btn = QtWidgets.QPushButton("❌ No Thanks")
    cancel_btn.setStyleSheet("background-color: #7f8c8d; color: white; padding: 6px;")
    button_row.addWidget(start_btn)
    button_row.addWidget(cancel_btn)

    def on_start() -> None:
        run_debris_game()
        frame.setVisible(False)
        if callback:
            callback(run_debris_game)

    def on_cancel() -> None:
        frame.setVisible(False)
        if callback:
            callback(None)

    start_btn.clicked.connect(on_start)
    cancel_btn.clicked.connect(on_cancel)
    return frame

