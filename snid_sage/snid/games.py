"""
Space Debris Cleanup Game - Enhanced realistic space simulation
Play while waiting for SNID to complete processing.
"""

import sys
import random
import threading
import time
import math
import os
from typing import Optional, List, Tuple, Callable

# Suppress pygame welcome messages before importing
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Check if pygame is available, otherwise games won't work
try:
    # Suppress pkg_resources deprecation warning from pygame
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)
        import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# Check if PySide6 (Qt) is available for dialogs
try:
    from PySide6 import QtWidgets, QtCore
    PYSIDE6_AVAILABLE = True
except Exception:
    PYSIDE6_AVAILABLE = False

# Cross-platform window focusing
class CrossPlatformGameFocus:
    """Cross-platform window focus management for games"""
    
    @staticmethod
    def bring_to_foreground(window_id=None):
        """Bring game window to foreground (cross-platform)"""
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                try:
                    SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
                    if window_id:
                        SetForegroundWindow(window_id)
                    else:
                        # Fallback: bring any pygame window to front
                        hwnd = ctypes.windll.user32.GetForegroundWindow()
                        SetForegroundWindow(hwnd)
                except:
                    pass  # Silently fail if it doesn't work
            elif sys.platform == 'darwin':  # macOS
                try:
                    from AppKit import NSApplication
                    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
                except ImportError:
                    pass  # Not available
            else:  # Linux/Unix
                try:
                    # Try X11 approach for Linux
                    import subprocess
                    subprocess.run(['wmctrl', '-a', 'pygame'], capture_output=True, timeout=1)
                except:
                    pass  # Not implemented or wmctrl not available
        except:
            pass  # Fallback if any approach fails

# Backward compatibility function
def bring_to_foreground(window_id=None):
    """Legacy function for backward compatibility"""
    CrossPlatformGameFocus.bring_to_foreground(window_id)

# -- Space Debris Game Configuration --------------------------
DEBRIS_WIDTH, DEBRIS_HEIGHT = 1024, 768  # Bigger window for better gameplay
DEBRIS_FPS = 60

# Ship constants (NEW DESIGN - Space Station/Rectangular)
STATION_WIDTH = 24
STATION_HEIGHT = 16
STATION_THRUST = 0.1
STATION_FRICTION = 0.99
STATION_ROT_SPEED = 3  # degrees per frame

# Bullet constants
BULLET_SPEED = 7
BULLET_LIFE = 90  # frames  # Increased lifetime for longer travel distance

# Debris constants
DEBRIS_MIN_SPEED = 1
DEBRIS_MAX_SPEED = 3
DEBRIS_SIZES = {3: 50, 2: 35, 1: 18}  # Smaller than asteroids for realism

# Boss Battle constants
BOSS_SIZE = 120
BOSS_HEALTH = 15
BOSS_SPEED = 1.5

# Power-up constants
POWERUP_SIZE = 20
POWERUP_LIFE = 300  # frames before despawn
SHIELD_DURATION = 300  # frames
MULTISHOT_DURATION = 180  # frames

# Chain reaction constants
CHAIN_RADIUS = 80
EXPLOSION_RADIUS = 40
EXPLOSION_DURATION = 30

# Colors for debris game
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
STATION_COLOR = (0, 200, 255)    # Cyan for space station
DEBRIS_COLOR = (150, 150, 150)   # Gray for satellite debris
BULLET_COLOR = (255, 255, 0)     # Yellow for energy bullets
BOSS_BULLET_COLOR = (255, 50, 50)  # Red for boss bullets
THRUSTER_COLOR = (255, 100, 0)   # Orange for thruster flame
SPACE_BLUE = (20, 30, 60)        # Deep space background
STAR_COLOR = (255, 255, 255)     # White stars
PANEL_COLOR = (100, 150, 200)    # Blue solar panels
ANTENNA_COLOR = (220, 220, 220)  # Light gray antennas
# New colors for enhancements
BOSS_COLOR = (200, 100, 100)     # Red for boss
EXPLOSION_COLOR = (255, 200, 0)  # Orange explosion
SHIELD_COLOR = (0, 255, 255)     # Cyan shield
POWERUP_SHIELD_COLOR = (0, 255, 200)  # Teal for shield powerup
POWERUP_MULTISHOT_COLOR = (255, 0, 255)  # Magenta for multishot powerup
# -----------------------------------------------------

# Deluxe parallax starfield (for nicer background only)
class _ParallaxStarLayer:
    def __init__(self, count: int, speed_y: float, twinkle: bool):
        self.points = [
            [random.random() * DEBRIS_WIDTH, random.random() * DEBRIS_HEIGHT, random.random()]
            for _ in range(count)
        ]
        self.speed_y = speed_y
        self.twinkle = twinkle

    def update(self):
        for p in self.points:
            p[1] += self.speed_y
            if p[1] >= DEBRIS_HEIGHT:
                p[0] = random.random() * DEBRIS_WIDTH
                p[1] -= DEBRIS_HEIGHT

    def draw(self, surface):
        t = time.time()
        for x, y, s in self.points:
            size = 1 + (1 if s > 0.7 else 0)
            if self.twinkle and int((t + s) * 5) % 4 == 0:
                color = (200, 210, 255)
            else:
                color = (160, 170, 230) if s < 0.4 else (200, 210, 255)
            surface.fill(color, (int(x), int(y), size, size))

# Global analysis notification system
_analysis_notifications = []
_show_analysis_complete = False

# High score system
_high_score = 0
_high_score_file = "space_debris_highscore.txt"

def load_high_score():
    """Load high score from file"""
    global _high_score
    try:
        with open(_high_score_file, 'r') as f:
            _high_score = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        _high_score = 0
    return _high_score

def save_high_score(score):
    """Save new high score if it's better than current"""
    global _high_score
    if score > _high_score:
        _high_score = score
        try:
            with open(_high_score_file, 'w') as f:
                f.write(str(_high_score))
            return True  # New high score
        except:
            pass
    return False

def get_station_name(wave_number):
    """Get progressively more impressive station name based on wave number"""
    station_names = [
        "ALPHA",      # Wave 1
        "BETA",       # Wave 2  
        "GAMMA",      # Wave 3
        "DELTA",      # Wave 4
        "OMEGA",      # Wave 5
        "TITAN",      # Wave 6
        "NEXUS",      # Wave 7
        "APEX",       # Wave 8
        "VORTEX",     # Wave 9
        "QUANTUM",    # Wave 10
        "INFINITY",   # Wave 11
        "SUPREMACY",  # Wave 12
        "DOMINION",   # Wave 13
        "OBLIVION",   # Wave 14
        "ANNIHILATOR" # Wave 15+
    ]
    index = min(wave_number - 1, len(station_names) - 1)
    return station_names[index]

def get_station_description(wave_number):
    """Get progressively more impressive station descriptions"""
    descriptions = [
        "ARMED AND DANGEROUS",           # Wave 1
        "HEAVILY FORTIFIED",             # Wave 2
        "MILITARY-GRADE THREAT",         # Wave 3
        "MAXIMUM FIREPOWER",             # Wave 4
        "ULTIMATE BATTLE STATION",       # Wave 5
        "COLOSSAL WAR MACHINE",          # Wave 6
        "DREADNOUGHT CLASS",             # Wave 7
        "PLANET KILLER",                 # Wave 8
        "REALITY WARPER",                # Wave 9
        "QUANTUM DESTROYER",             # Wave 10
        "DIMENSIONAL ANNIHILATOR",       # Wave 11
        "GALACTIC SUPREMACY UNIT",       # Wave 12
        "UNIVERSAL DOMINION CORE",       # Wave 13
        "EXISTENCE OBLITERATOR",         # Wave 14
        "UNSTOPPABLE FORCE OF DOOM"      # Wave 15+
    ]
    index = min(wave_number - 1, len(descriptions) - 1)
    return descriptions[index]

def notify_analysis_complete(message=">> SNID Analysis Complete! <<"):
    """Notify the game that analysis is complete"""
    global _analysis_notifications, _show_analysis_complete
    _analysis_notifications.append(message)
    _show_analysis_complete = True
    
    # Add a visual celebration effect by clearing old notifications
    # to make the new notification more prominent
    if len(_analysis_notifications) > 3:
        _analysis_notifications = _analysis_notifications[-2:]  # Keep only recent ones

def notify_analysis_result(result_message):
    """Notify the game with analysis results"""
    global _analysis_notifications
    _analysis_notifications.append(result_message)

def clear_analysis_notifications():
    """Clear all analysis notifications"""
    global _analysis_notifications, _show_analysis_complete
    _analysis_notifications.clear()
    _show_analysis_complete = False

# Helper functions for Space Debris
def wrap_position(pos):
    x, y = pos
    return x % DEBRIS_WIDTH, y % DEBRIS_HEIGHT

def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

class SpaceStation:
    def __init__(self):
        self.pos = (DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2)
        self.vel = (0.0, 0.0)
        self.angle = 0  # degrees
        self.shield_time = 0  # Frames of shield remaining
        self.multishot_time = 0  # Frames of multishot remaining

    def update(self, keys):
        # Update power-up timers
        if self.shield_time > 0:
            self.shield_time -= 1
        if self.multishot_time > 0:
            self.multishot_time -= 1
            
        # Rotation
        if keys[pygame.K_LEFT]:
            self.angle += STATION_ROT_SPEED
        if keys[pygame.K_RIGHT]:
            self.angle -= STATION_ROT_SPEED

        # Thrust
        if keys[pygame.K_UP]:
            rad = math.radians(self.angle)
            fx = math.cos(rad) * STATION_THRUST
            fy = -math.sin(rad) * STATION_THRUST
            vx, vy = self.vel
            self.vel = (vx + fx, vy + fy)

        # Apply friction
        vx, vy = self.vel
        self.vel = (vx * STATION_FRICTION, vy * STATION_FRICTION)

        # Move
        self.pos = wrap_position((self.pos[0] + self.vel[0],
                                  self.pos[1] + self.vel[1]))

    def draw(self, surface, keys=None):
        # Draw realistic spacecraft
        rad = math.radians(self.angle)
        cx, cy = self.pos
        
        # Define spacecraft components
        main_length = 20
        main_width = 8
        wing_length = 12
        wing_width = 4
        
        # Main fuselage (elongated hexagon)
        nose_tip = (cx + main_length * math.cos(rad), cy - main_length * math.sin(rad))
        nose_left = (cx + (main_length-4) * math.cos(rad) - main_width/2 * math.sin(rad), 
                     cy - (main_length-4) * math.sin(rad) - main_width/2 * math.cos(rad))
        nose_right = (cx + (main_length-4) * math.cos(rad) + main_width/2 * math.sin(rad), 
                      cy - (main_length-4) * math.sin(rad) + main_width/2 * math.cos(rad))
        
        mid_left = (cx - 2 * math.cos(rad) - main_width/2 * math.sin(rad), 
                    cy + 2 * math.sin(rad) - main_width/2 * math.cos(rad))
        mid_right = (cx - 2 * math.cos(rad) + main_width/2 * math.sin(rad), 
                     cy + 2 * math.sin(rad) + main_width/2 * math.cos(rad))
        
        tail_left = (cx - main_length/2 * math.cos(rad) - main_width/3 * math.sin(rad), 
                     cy + main_length/2 * math.sin(rad) - main_width/3 * math.cos(rad))
        tail_right = (cx - main_length/2 * math.cos(rad) + main_width/3 * math.sin(rad), 
                      cy + main_length/2 * math.sin(rad) + main_width/3 * math.cos(rad))
        
        # Draw main hull
        hull_points = [nose_tip, nose_left, mid_left, tail_left, tail_right, mid_right, nose_right]
        pygame.draw.polygon(surface, STATION_COLOR, hull_points, 2)
        
        # Subtle detailing: center spine and panel line
        tail_mid = ((tail_left[0] + tail_right[0]) / 2, (tail_left[1] + tail_right[1]) / 2)
        pygame.draw.line(surface, (200, 240, 255), (nose_tip[0], nose_tip[1]), (tail_mid[0], tail_mid[1]), 1)
        pygame.draw.line(surface, (170, 210, 235), (mid_left[0], mid_left[1]), (mid_right[0], mid_right[1]), 1)
        
        # Draw wings/solar panels
        wing_offset = 6
        # Left wing
        wing_left_outer = (cx - wing_offset * math.sin(rad) - wing_length * math.cos(rad + math.pi/2), 
                          cy + wing_offset * math.cos(rad) - wing_length * math.sin(rad + math.pi/2))
        wing_left_inner = (cx - wing_offset * math.sin(rad), cy + wing_offset * math.cos(rad))
        wing_left_tip = (cx - wing_offset * math.sin(rad) + wing_width * math.cos(rad + math.pi/2), 
                         cy + wing_offset * math.cos(rad) + wing_width * math.sin(rad + math.pi/2))
        
        pygame.draw.polygon(surface, STATION_COLOR, [wing_left_inner, wing_left_outer, 
                           (wing_left_outer[0] + wing_width * math.cos(rad + math.pi/2), 
                            wing_left_outer[1] + wing_width * math.sin(rad + math.pi/2)), wing_left_tip], 2)
        # Wing detailing line
        pygame.draw.line(surface, (180, 220, 240), (wing_left_inner[0], wing_left_inner[1]), (wing_left_tip[0], wing_left_tip[1]), 1)
        
        # Right wing  
        wing_right_outer = (cx + wing_offset * math.sin(rad) - wing_length * math.cos(rad - math.pi/2), 
                           cy - wing_offset * math.cos(rad) - wing_length * math.sin(rad - math.pi/2))
        wing_right_inner = (cx + wing_offset * math.sin(rad), cy - wing_offset * math.cos(rad))
        wing_right_tip = (cx + wing_offset * math.sin(rad) + wing_width * math.cos(rad - math.pi/2), 
                          cy - wing_offset * math.cos(rad) + wing_width * math.sin(rad - math.pi/2))
        
        pygame.draw.polygon(surface, STATION_COLOR, [wing_right_inner, wing_right_outer,
                           (wing_right_outer[0] + wing_width * math.cos(rad - math.pi/2), 
                            wing_right_outer[1] + wing_width * math.sin(rad - math.pi/2)), wing_right_tip], 2)
        # Wing detailing line
        pygame.draw.line(surface, (180, 220, 240), (wing_right_inner[0], wing_right_inner[1]), (wing_right_tip[0], wing_right_tip[1]), 1)
        
        # Draw cockpit/command module
        cockpit_x = cx + 12 * math.cos(rad)
        cockpit_y = cy - 12 * math.sin(rad)
        pygame.draw.circle(surface, WHITE, (int(cockpit_x), int(cockpit_y)), 3, 1)
        
        # Draw engine details
        engine_x = cx - 8 * math.cos(rad)
        engine_y = cy + 8 * math.sin(rad)
        pygame.draw.circle(surface, STATION_COLOR, (int(engine_x), int(engine_y)), 2, 1)
        
        # Draw communication antenna
        antenna_base_x = cx - 2 * math.cos(rad) + 3 * math.sin(rad)
        antenna_base_y = cy + 2 * math.sin(rad) + 3 * math.cos(rad)
        antenna_tip_x = antenna_base_x + 6 * math.sin(rad)
        antenna_tip_y = antenna_base_y + 6 * math.cos(rad)
        pygame.draw.line(surface, WHITE, (antenna_base_x, antenna_base_y), (antenna_tip_x, antenna_tip_y), 1)
        
        # Draw shield effect if active
        if self.shield_time > 0:
            shield_radius = 35
            shield_alpha = int(100 + 50 * math.sin(self.shield_time * 0.3))  # Pulsing effect
            # Create multiple shield rings
            for i in range(3):
                radius = shield_radius - i * 5
                pygame.draw.circle(surface, SHIELD_COLOR, (int(cx), int(cy)), radius, 2)
            
            # Add sparkling effect
            for i in range(8):
                angle = (self.shield_time * 5 + i * 45) % 360
                spark_x = cx + math.cos(math.radians(angle)) * shield_radius
                spark_y = cy + math.sin(math.radians(angle)) * shield_radius
                pygame.draw.circle(surface, WHITE, (int(spark_x), int(spark_y)), 2)
        
        # Draw thruster flame when accelerating
        if keys and keys[pygame.K_UP]:
            thruster_length = 18
            thruster_width = 8
            
            # Main thruster at the back
            back_x = cx - main_length/2 * math.cos(rad)
            back_y = cy + main_length/2 * math.sin(rad)
            
            # Flame tip position
            flame_x = back_x - math.cos(rad) * thruster_length
            flame_y = back_y + math.sin(rad) * thruster_length
            
            # Inner flame (blue-white core)
            inner_flame_points = [
                (back_x, back_y),
                (back_x + (thruster_width*0.6) * math.cos(rad + math.pi/2), 
                 back_y - (thruster_width*0.6) * math.sin(rad + math.pi/2)),
                (flame_x + 3 * math.cos(rad), flame_y - 3 * math.sin(rad)),
                (back_x + (thruster_width*0.6) * math.cos(rad - math.pi/2), 
                 back_y - (thruster_width*0.6) * math.sin(rad - math.pi/2))
            ]
            pygame.draw.polygon(surface, WHITE, inner_flame_points)
            
            # Outer flame (orange)
            outer_flame_points = [
                (back_x, back_y),
                (back_x + thruster_width * math.cos(rad + math.pi/2), 
                 back_y - thruster_width * math.sin(rad + math.pi/2)),
                (flame_x, flame_y),
                (back_x + thruster_width * math.cos(rad - math.pi/2), 
                 back_y - thruster_width * math.sin(rad - math.pi/2))
            ]
            pygame.draw.polygon(surface, THRUSTER_COLOR, outer_flame_points)

    def activate_shield(self):
        self.shield_time = SHIELD_DURATION

    def activate_multishot(self):
        self.multishot_time = MULTISHOT_DURATION

    def has_shield(self):
        return self.shield_time > 0

    def has_multishot(self):
        return self.multishot_time > 0

class EnergyBullet:
    def __init__(self, pos, angle):
        rad = math.radians(angle)
        self.pos = pos
        self.vel = (math.cos(rad) * BULLET_SPEED,
                    -math.sin(rad) * BULLET_SPEED)
        self.life = BULLET_LIFE
        self.trail = []  # Trail of previous positions
        self.max_trail_length = 8

    def update(self):
        # Add current position to trail
        self.trail.append(self.pos)
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)
            
        self.pos = wrap_position((self.pos[0] + self.vel[0],
                                  self.pos[1] + self.vel[1]))
        self.life -= 1

    def draw(self, surface):
        # Draw energy trail
        for i, trail_pos in enumerate(self.trail):
            alpha = int(255 * (i + 1) / len(self.trail))
            trail_size = int(2 * (i + 1) / len(self.trail))
            if trail_size > 0:
                # Create fading trail effect
                trail_color = (255, 255 - (255 - alpha), 0)  # Yellow to orange fade
                pygame.draw.circle(surface, trail_color, 
                                 (int(trail_pos[0]), int(trail_pos[1])), trail_size)
        
        # Draw main energy bullet as glowing circle
        pygame.draw.circle(surface, BULLET_COLOR,
                           (int(self.pos[0]), int(self.pos[1])), 4)
        pygame.draw.circle(surface, WHITE,
                           (int(self.pos[0]), int(self.pos[1])), 2)
        pygame.draw.circle(surface, (255, 255, 200),
                           (int(self.pos[0]), int(self.pos[1])), 1)

class BossBullet:
    def __init__(self, pos, target_pos=None, wave_number=1, *, initial_angle=None, speed=None):
        self.pos = pos
        self.life = BULLET_LIFE * 2  # Boss bullets last longer
        self.trail = []
        
        # Progressive bullet speed - slower for early waves
        speed_multiplier = 0.4 + (wave_number - 1) * 0.1  # Start at 40%, increase by 10% per wave
        speed_multiplier = min(speed_multiplier, 0.9)  # Cap at 90% of player bullet speed
        base_speed = BULLET_SPEED * speed_multiplier

        if initial_angle is not None:
            # Spawn by angle (rings, spreads)
            s = speed if speed is not None else base_speed
            self.vel = (math.cos(initial_angle) * s, math.sin(initial_angle) * s)
        else:
            # Aim at target position
            if target_pos is None:
                target_pos = (pos[0], pos[1] + 1)
            dx = target_pos[0] - pos[0]
            dy = target_pos[1] - pos[1]
            distance_to_target = math.hypot(dx, dy)
            if distance_to_target > 0:
                self.vel = (dx / distance_to_target * base_speed, dy / distance_to_target * base_speed)
            else:
                self.vel = (0, base_speed)

    @classmethod
    def from_angle(cls, pos, angle_radians, wave_number=1, speed=None):
        return cls(pos, None, wave_number, initial_angle=angle_radians, speed=speed)

    def update(self):
        # Add current position to trail
        self.trail.append(self.pos)
        if len(self.trail) > 8:  # Longer trail for boss bullets
            self.trail.pop(0)
        
        # Move bullet
        self.pos = wrap_position((self.pos[0] + self.vel[0], 
                                self.pos[1] + self.vel[1]))
        self.life -= 1

    def draw(self, surface):
        # Draw energy trail
        for i, trail_pos in enumerate(self.trail):
            alpha = (i + 1) / len(self.trail)
            size = int(3 * alpha) + 1
            color_intensity = int(255 * alpha)
            trail_color = (color_intensity, int(color_intensity * 0.2), int(color_intensity * 0.2))
            pygame.draw.circle(surface, trail_color, (int(trail_pos[0]), int(trail_pos[1])), size)
        
        # Draw main bullet (larger than player bullets)
        pygame.draw.circle(surface, BOSS_BULLET_COLOR, (int(self.pos[0]), int(self.pos[1])), 6)
        pygame.draw.circle(surface, WHITE, (int(self.pos[0]), int(self.pos[1])), 3)

class SatelliteDebris:
    def __init__(self, pos=None, size=3):
        self.size = size
        radius = DEBRIS_SIZES[size]
        
        if pos is None:
            # Ensure satellites don't spawn too close to center (player start position)
            center_x, center_y = DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2
            min_distance = 120  # Minimum distance from center
            
            attempts = 0
            while attempts < 50:  # Prevent infinite loop
                x = random.randrange(DEBRIS_WIDTH)
                y = random.randrange(DEBRIS_HEIGHT)
                
                # Check distance from center
                dx = x - center_x
                dy = y - center_y
                distance_from_center = math.sqrt(dx*dx + dy*dy)
                
                if distance_from_center >= min_distance:
                    self.pos = (x, y)
                    break
                attempts += 1
            else:
                # Fallback: place at edge if no good position found
                self.pos = (random.choice([50, DEBRIS_WIDTH-50]), random.randrange(DEBRIS_HEIGHT))
        else:
            self.pos = pos
        angle = random.random() * 360
        speed = random.uniform(DEBRIS_MIN_SPEED, DEBRIS_MAX_SPEED)
        self.vel = (math.cos(math.radians(angle)) * speed,
                    -math.sin(math.radians(angle)) * speed)
        self.rotation = 0
        self.rotation_speed = random.uniform(-2, 2)
        
        # Satellite type determines shape and components
        self.satellite_type = random.choice(['communication', 'weather', 'navigation', 'research'])
        
        # Create realistic satellite body
        self.body_width = radius * 0.6
        self.body_height = radius * 0.4
        
        # Solar panel dimensions
        self.panel_width = radius * 0.8
        self.panel_height = radius * 0.2
        
        # Antenna and dish positions (relative to center)
        self.antennas = []
        self.dishes = []
        
        if self.satellite_type == 'communication':
            # Large communication dish
            self.dishes.append({'pos': (0, -radius*0.3), 'size': radius*0.4})
            # Multiple antennas
            self.antennas.extend([
                {'start': (radius*0.2, 0), 'end': (radius*0.6, -radius*0.3)},
                {'start': (-radius*0.2, 0), 'end': (-radius*0.6, -radius*0.3)},
                {'start': (0, radius*0.2), 'end': (0, radius*0.7)}
            ])
        elif self.satellite_type == 'weather':
            # Weather sensors
            self.antennas.extend([
                {'start': (0, -radius*0.3), 'end': (0, -radius*0.8)},
                {'start': (radius*0.3, 0), 'end': (radius*0.7, 0)},
                {'start': (-radius*0.3, 0), 'end': (-radius*0.7, 0)}
            ])
        elif self.satellite_type == 'navigation':
            # GPS-style antennas
            self.antennas.extend([
                {'start': (radius*0.2, -radius*0.2), 'end': (radius*0.5, -radius*0.6)},
                {'start': (-radius*0.2, -radius*0.2), 'end': (-radius*0.5, -radius*0.6)},
                {'start': (radius*0.2, radius*0.2), 'end': (radius*0.5, radius*0.6)},
                {'start': (-radius*0.2, radius*0.2), 'end': (-radius*0.5, radius*0.6)}
            ])
        else:  # research
            # Various scientific instruments
            self.dishes.append({'pos': (radius*0.3, 0), 'size': radius*0.25})
            self.antennas.extend([
                {'start': (-radius*0.2, -radius*0.2), 'end': (-radius*0.6, -radius*0.5)},
                {'start': (0, radius*0.3), 'end': (0, radius*0.8)}
            ])

    def update(self):
        self.pos = wrap_position((self.pos[0] + self.vel[0],
                                  self.pos[1] + self.vel[1]))
        self.rotation += self.rotation_speed

    def draw(self, surface):
        rad = math.radians(self.rotation)
        cx, cy = self.pos
        
        # Draw main satellite body (rectangular)
        body_corners = [
            (-self.body_width/2, -self.body_height/2),
            (self.body_width/2, -self.body_height/2),
            (self.body_width/2, self.body_height/2),
            (-self.body_width/2, self.body_height/2)
        ]
        
        rotated_body = []
        for dx, dy in body_corners:
            rx = dx * math.cos(rad) - dy * math.sin(rad)
            ry = dx * math.sin(rad) + dy * math.cos(rad)
            rotated_body.append((cx + rx, cy + ry))
        
        pygame.draw.polygon(surface, DEBRIS_COLOR, rotated_body, 2)
        
        # Draw solar panels
        if self.size >= 2:  # Only larger debris has intact panels
            # Left solar panel
            left_panel_corners = [
                (-self.body_width/2 - self.panel_width, -self.panel_height/2),
                (-self.body_width/2, -self.panel_height/2),
                (-self.body_width/2, self.panel_height/2),
                (-self.body_width/2 - self.panel_width, self.panel_height/2)
            ]
            
            rotated_left_panel = []
            for dx, dy in left_panel_corners:
                rx = dx * math.cos(rad) - dy * math.sin(rad)
                ry = dx * math.sin(rad) + dy * math.cos(rad)
                rotated_left_panel.append((cx + rx, cy + ry))
            
            pygame.draw.polygon(surface, PANEL_COLOR, rotated_left_panel, 1)  # Blue solar panels
            
            # Right solar panel
            right_panel_corners = [
                (self.body_width/2, -self.panel_height/2),
                (self.body_width/2 + self.panel_width, -self.panel_height/2),
                (self.body_width/2 + self.panel_width, self.panel_height/2),
                (self.body_width/2, self.panel_height/2)
            ]
            
            rotated_right_panel = []
            for dx, dy in right_panel_corners:
                rx = dx * math.cos(rad) - dy * math.sin(rad)
                ry = dx * math.sin(rad) + dy * math.cos(rad)
                rotated_right_panel.append((cx + rx, cy + ry))
            
            pygame.draw.polygon(surface, PANEL_COLOR, rotated_right_panel, 1)
            
            # Draw panel grid lines
            for panel_corners in [rotated_left_panel, rotated_right_panel]:
                # Draw grid lines on solar panels
                if len(panel_corners) >= 4:
                    # Horizontal lines
                    mid_top = ((panel_corners[0][0] + panel_corners[1][0])/2, 
                              (panel_corners[0][1] + panel_corners[1][1])/2)
                    mid_bottom = ((panel_corners[2][0] + panel_corners[3][0])/2, 
                                 (panel_corners[2][1] + panel_corners[3][1])/2)
                    pygame.draw.line(surface, ANTENNA_COLOR, mid_top, mid_bottom, 1)
        
        # Draw communication dishes
        for dish in self.dishes:
            dish_x = cx + dish['pos'][0] * math.cos(rad) - dish['pos'][1] * math.sin(rad)
            dish_y = cy + dish['pos'][0] * math.sin(rad) + dish['pos'][1] * math.cos(rad)
            pygame.draw.circle(surface, WHITE, (int(dish_x), int(dish_y)), int(dish['size']/2), 1)
            # Draw dish support
            pygame.draw.line(surface, DEBRIS_COLOR, (cx, cy), (dish_x, dish_y), 1)
        
        # Draw antennas
        for antenna in self.antennas:
            start_x = cx + antenna['start'][0] * math.cos(rad) - antenna['start'][1] * math.sin(rad)
            start_y = cy + antenna['start'][0] * math.sin(rad) + antenna['start'][1] * math.cos(rad)
            end_x = cx + antenna['end'][0] * math.cos(rad) - antenna['end'][1] * math.sin(rad)
            end_y = cy + antenna['end'][0] * math.sin(rad) + antenna['end'][1] * math.cos(rad)
            pygame.draw.line(surface, ANTENNA_COLOR, (start_x, start_y), (end_x, end_y), 1)
        
        # Draw internal components (wiring, etc.)
        if self.size >= 2:
            # Internal cross pattern
            internal_size = min(self.body_width, self.body_height) * 0.3
            cross_points_1 = [
                (cx + internal_size * math.cos(rad + math.pi/4), 
                 cy + internal_size * math.sin(rad + math.pi/4)),
                (cx - internal_size * math.cos(rad + math.pi/4), 
                 cy - internal_size * math.sin(rad + math.pi/4))
            ]
            cross_points_2 = [
                (cx + internal_size * math.cos(rad - math.pi/4), 
                 cy + internal_size * math.sin(rad - math.pi/4)),
                (cx - internal_size * math.cos(rad - math.pi/4), 
                 cy - internal_size * math.sin(rad - math.pi/4))
            ]
            pygame.draw.line(surface, DEBRIS_COLOR, cross_points_1[0], cross_points_1[1], 1)
            pygame.draw.line(surface, DEBRIS_COLOR, cross_points_2[0], cross_points_2[1], 1)

class Explosion:
    def __init__(self, pos, size=EXPLOSION_RADIUS):
        self.pos = pos
        self.size = size
        self.max_size = size
        self.duration = EXPLOSION_DURATION
        self.max_duration = EXPLOSION_DURATION

    def update(self):
        self.duration -= 1
        # Explosion grows then shrinks
        progress = 1 - (self.duration / self.max_duration)
        if progress < 0.5:
            self.size = self.max_size * (progress * 2)
        else:
            self.size = self.max_size * (2 - progress * 2)

    def draw(self, surface):
        if self.duration > 0:
            alpha = int(255 * (self.duration / self.max_duration))
            # Draw explosion as expanding circle with particles
            center = (int(self.pos[0]), int(self.pos[1]))
            
            # Main explosion
            explosion_color = (255, min(255, 150 + alpha//3), 0)
            pygame.draw.circle(surface, explosion_color, center, int(self.size), 3)
            
            # Inner explosion
            if self.size > 10:
                inner_color = (255, 255, 200)
                pygame.draw.circle(surface, inner_color, center, int(self.size * 0.6), 2)
            
            # Particles
            for i in range(8):
                angle = i * math.pi / 4
                particle_dist = self.size * 1.2
                px = center[0] + math.cos(angle) * particle_dist
                py = center[1] + math.sin(angle) * particle_dist
                particle_size = max(1, int(self.size * 0.1))
                pygame.draw.circle(surface, explosion_color, (int(px), int(py)), particle_size)

    def is_alive(self):
        return self.duration > 0

class PowerUp:
    def __init__(self, pos, powerup_type):
        self.pos = pos
        self.type = powerup_type  # 'shield' or 'multishot'
        self.life = POWERUP_LIFE
        self.rotation = 0
        self.rotation_speed = 2
        self.bob_offset = 0
        self.bob_speed = 0.1

    def update(self):
        self.life -= 1
        self.rotation += self.rotation_speed
        self.bob_offset += self.bob_speed

    def draw(self, surface):
        if self.life > 0:
            # Calculate bobbing position
            bob_y = math.sin(self.bob_offset) * 3
            x, y = self.pos[0], self.pos[1] + bob_y
            
            # Choose color based on type
            color = POWERUP_SHIELD_COLOR if self.type == 'shield' else POWERUP_MULTISHOT_COLOR
            
            # Draw spinning powerup
            if self.type == 'shield':
                # Shield powerup - spinning hexagon
                points = []
                for i in range(6):
                    angle = math.radians(self.rotation + i * 60)
                    px = x + math.cos(angle) * POWERUP_SIZE * 0.8
                    py = y + math.sin(angle) * POWERUP_SIZE * 0.8
                    points.append((px, py))
                pygame.draw.polygon(surface, color, points, 3)
                
                # Inner shield symbol
                pygame.draw.circle(surface, WHITE, (int(x), int(y)), POWERUP_SIZE//3, 2)
            
            else:  # multishot
                # Multishot powerup - three rotating arrows
                for i in range(3):
                    angle = math.radians(self.rotation + i * 120)
                    # Arrow pointing outward
                    tip_x = x + math.cos(angle) * POWERUP_SIZE * 0.7
                    tip_y = y + math.sin(angle) * POWERUP_SIZE * 0.7
                    base_x = x + math.cos(angle) * POWERUP_SIZE * 0.3
                    base_y = y + math.sin(angle) * POWERUP_SIZE * 0.3
                    
                    pygame.draw.line(surface, color, (base_x, base_y), (tip_x, tip_y), 3)
                    
                    # Arrow head
                    head_angle1 = angle + math.pi * 0.8
                    head_angle2 = angle - math.pi * 0.8
                    head1_x = tip_x + math.cos(head_angle1) * 8
                    head1_y = tip_y + math.sin(head_angle1) * 8
                    head2_x = tip_x + math.cos(head_angle2) * 8
                    head2_y = tip_y + math.sin(head_angle2) * 8
                    
                    pygame.draw.line(surface, color, (tip_x, tip_y), (head1_x, head1_y), 2)
                    pygame.draw.line(surface, color, (tip_x, tip_y), (head2_x, head2_y), 2)

    def is_alive(self):
        return self.life > 0

class BossSatellite:
    def __init__(self, wave_number=1):
        self.pos = (DEBRIS_WIDTH//2, 50)  # Start at top center
        self.vel = (BOSS_SPEED, 0)
        self.angle = 0
        self.rotation_speed = 1
        self.health = BOSS_HEALTH
        self.max_health = BOSS_HEALTH
        self.phase = 1  # Boss has 3 phases
        self.size = BOSS_SIZE
        self.last_shot_time = 0
        self.shot_cooldown = 90  # Frames between shots (1.5 seconds at 60 FPS)
        self.wave_number = wave_number  # Track which wave this boss is from
        self.components = self._create_components()
        
    def _create_components(self):
        # Create boss components that can be destroyed individually
        # Component health scales with wave number
        health_multiplier = 1 + (self.wave_number - 1) * 0.2  # 20% increase per wave
        
        components = []
        # Main body
        components.append({'type': 'body', 'pos': (0, 0), 'size': 40, 'health': int(5 * health_multiplier), 'active': True})
        # Communication dishes
        components.append({'type': 'dish', 'pos': (-30, -20), 'size': 20, 'health': int(2 * health_multiplier), 'active': True})
        components.append({'type': 'dish', 'pos': (30, -20), 'size': 20, 'health': int(2 * health_multiplier), 'active': True})
        # Solar panels
        components.append({'type': 'panel', 'pos': (-50, 0), 'size': 25, 'health': int(3 * health_multiplier), 'active': True})
        components.append({'type': 'panel', 'pos': (50, 0), 'size': 25, 'health': int(3 * health_multiplier), 'active': True})
        # Engine sections
        components.append({'type': 'engine', 'pos': (0, 30), 'size': 15, 'health': int(2 * health_multiplier), 'active': True})
        
        return components

    def update(self, target_pos=None):
        # Rotate for visual interest
        self.angle += self.rotation_speed
        
        if target_pos is not None:
            # Target-aware pursuit with orbiting and noise
            dx = target_pos[0] - self.pos[0]
            dy = target_pos[1] - self.pos[1]
            dist = math.hypot(dx, dy) + 1e-6
            ux, uy = dx / dist, dy / dist
            # Orbit perpendicular to pursuit
            orbit_dir = 1 if (self.wave_number % 2 == 0) else -1
            ox, oy = -uy * orbit_dir, ux * orbit_dir
            
            pursue_strength = 0.5 + 0.02 * self.wave_number + 0.15 * (self.phase - 1)
            orbit_strength = 0.3 + 0.1 * (self.phase - 1)
            standoff = self.size + 90
            repel = 0.0
            if dist < standoff:
                repel = (standoff - dist) / standoff
            
            # Gentle procedural wobble
            t = pygame.time.get_ticks() * 0.002
            nx = 0.3 * math.sin(t + self.wave_number)
            ny = 0.3 * math.cos(t * 1.3 + self.phase)
            
            desired_vx = BOSS_SPEED * (pursue_strength * ux + orbit_strength * ox - repel * ux) + nx
            desired_vy = BOSS_SPEED * (pursue_strength * uy + orbit_strength * oy - repel * uy) + ny
            
            # Smoothly steer toward desired velocity
            cur_vx, cur_vy = self.vel
            self.vel = (cur_vx * 0.85 + desired_vx * 0.15, cur_vy * 0.85 + desired_vy * 0.15)
        else:
            # Fallback: sine wave drift
            self.vel = (BOSS_SPEED * math.sin(self.angle * 0.02), BOSS_SPEED * 0.5)

        self.pos = wrap_position((self.pos[0] + self.vel[0], self.pos[1] + self.vel[1]))
        
        # Update phase based on health
        health_percent = self.health / self.max_health
        if health_percent > 0.66:
            self.phase = 1
        elif health_percent > 0.33:
            self.phase = 2
        else:
            self.phase = 3
        
        # Update shooting timer
        self.last_shot_time += 1

    def should_shoot(self, target_pos):
        """Check if boss should shoot at target"""
        # Adjust shooting frequency based on phase (much slower shooting overall)
        phase_cooldown = {1: 240, 2: 180, 3: 120}  # Much slower shooting for all phases
        return self.last_shot_time >= phase_cooldown.get(self.phase, 240)

    def shoot_at_target(self, target_pos):
        """Create bullets aimed at target position. Returns a list (may be empty)."""
        if not self.should_shoot(target_pos):
            return []
        self.last_shot_time = 0
        bullets = []
        # Phase-based patterns
        if self.phase == 1:
            # Mostly single aimed shots; occasional 2-shot burst
            bullets.append(BossBullet(self.pos, target_pos, self.wave_number))
            if random.random() < 0.25:
                # slight offset second shot
                off = math.radians(random.choice([-8, 8]))
                angle = math.atan2(target_pos[1] - self.pos[1], target_pos[0] - self.pos[0]) + off
                bullets.append(BossBullet.from_angle(self.pos, angle, self.wave_number))
        elif self.phase == 2:
            # 3-shot spread
            base_angle = math.atan2(target_pos[1] - self.pos[1], target_pos[0] - self.pos[0])
            for off_deg in (-10, 0, 10):
                bullets.append(BossBullet.from_angle(self.pos, base_angle + math.radians(off_deg), self.wave_number))
        else:  # phase 3
            # Ring burst or heavy spread (all straight)
            if random.random() < 0.5:
                count = 8
                base = random.random() * math.tau
                for i in range(count):
                    ang = base + i * (math.tau / count)
                    bullets.append(BossBullet.from_angle(self.pos, ang, self.wave_number, speed=BULLET_SPEED * 0.7))
            else:
                base_angle = math.atan2(target_pos[1] - self.pos[1], target_pos[0] - self.pos[0])
                for off_deg in (-20, -10, 0, 10, 20):
                    bullets.append(BossBullet.from_angle(self.pos, base_angle + math.radians(off_deg), self.wave_number))
        return bullets

    def take_damage(self, bullet_pos):
        # Check which component was hit
        for component in self.components:
            if not component['active']:
                continue
                
            comp_world_pos = (
                self.pos[0] + component['pos'][0], 
                self.pos[1] + component['pos'][1]
            )
            
            if distance(bullet_pos, comp_world_pos) < component['size']:
                component['health'] -= 1
                if component['health'] <= 0:
                    component['active'] = False
                
                self.health -= 1
                
                # Check if all components are destroyed - if so, kill the boss
                if not any(component['active'] for component in self.components):
                    self.health = 0
                
                return True
        return False

    def draw(self, surface):
        cx, cy = self.pos
        
        # Scale factor based on boss size
        scale_factor = self.size / BOSS_SIZE
        
        # Draw components that are still active
        any_components_visible = False
        for component in self.components:
            if not component['active']:
                continue
                
            any_components_visible = True
            comp_x = cx + component['pos'][0] * scale_factor
            comp_y = cy + component['pos'][1] * scale_factor
            comp_size = int(component['size'] * scale_factor)
            
            # Choose color based on component type and damage
            if component['type'] == 'body':
                # Enhanced coloring for higher waves
                color_intensity = min(255, 200 + (self.wave_number * 10))
                color = (color_intensity, max(100 - self.wave_number * 5, 50), max(100 - self.wave_number * 5, 50))
                
                # Main body - shape complexity increases with wave number
                if self.wave_number <= 3:
                    # Hexagon for early waves
                    points = []
                    for i in range(6):
                        angle = math.radians(self.angle + i * 60)
                        px = comp_x + math.cos(angle) * comp_size
                        py = comp_y + math.sin(angle) * comp_size
                        points.append((px, py))
                    pygame.draw.polygon(surface, color, points, 3)
                elif self.wave_number <= 6:
                    # Octagon for mid waves
                    points = []
                    for i in range(8):
                        angle = math.radians(self.angle + i * 45)
                        px = comp_x + math.cos(angle) * comp_size
                        py = comp_y + math.sin(angle) * comp_size
                        points.append((px, py))
                    pygame.draw.polygon(surface, color, points, 3)
                else:
                    # Complex star shape for high waves
                    points = []
                    for i in range(12):
                        angle = math.radians(self.angle + i * 30)
                        radius = comp_size if i % 2 == 0 else comp_size * 0.6
                        px = comp_x + math.cos(angle) * radius
                        py = comp_y + math.sin(angle) * radius
                        points.append((px, py))
                    pygame.draw.polygon(surface, color, points, 3)
                
            elif component['type'] == 'dish':
                color = ANTENNA_COLOR
                # Communication dish
                pygame.draw.circle(surface, color, (int(comp_x), int(comp_y)), comp_size, 2)
                # Dish support
                pygame.draw.line(surface, DEBRIS_COLOR, (cx, cy), (comp_x, comp_y), 2)
                
            elif component['type'] == 'panel':
                color = PANEL_COLOR
                # Solar panel - rectangle
                panel_rect = pygame.Rect(comp_x - comp_size, comp_y - comp_size//2, 
                                       comp_size * 2, comp_size)
                pygame.draw.rect(surface, color, panel_rect, 2)
                
            elif component['type'] == 'engine':
                color = THRUSTER_COLOR
                # Engine - circle with thruster effect (enhanced for higher waves)
                pygame.draw.circle(surface, color, (int(comp_x), int(comp_y)), comp_size, 2)
                if self.phase >= 2 or self.wave_number >= 3:
                    # Add thruster flames in later phases or higher waves
                    flame_count = min(3 + self.wave_number, 8)
                    for i in range(flame_count):
                        flame_x = comp_x + random.randint(-8, 8)
                        flame_y = comp_y + 20 + random.randint(0, 15)
                        flame_size = 3 + (self.wave_number // 3)
                        flame_color = (255, 100 + (self.wave_number * 10) % 155, 0)
                        pygame.draw.circle(surface, flame_color, (int(flame_x), int(flame_y)), flame_size)
        
        # If all components are destroyed but boss is somehow still alive, draw emergency core
        if not any_components_visible and self.health > 0:
            # Draw emergency core - a small glowing orb that's still dangerous
            core_size = 15
            glow_color = (255, 100, 100)  # Red glow
            # Pulsing effect
            pulse = int(20 * math.sin(pygame.time.get_ticks() * 0.01))
            pygame.draw.circle(surface, glow_color, (int(cx), int(cy)), core_size + pulse, 0)
            pygame.draw.circle(surface, (255, 255, 255), (int(cx), int(cy)), core_size//2, 0)
        
        # Draw health bar
        bar_width = 100
        bar_height = 8
        bar_x = cx - bar_width // 2
        bar_y = cy - self.size - 20
        
        # Background
        pygame.draw.rect(surface, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height))
        # Health
        health_width = int((self.health / self.max_health) * bar_width)
        health_color = (255, 0, 0) if self.health < 5 else (255, 255, 0) if self.health < 10 else (0, 255, 0)
        pygame.draw.rect(surface, health_color, (bar_x, bar_y, health_width, bar_height))
        
        # Boss name
        font = pygame.font.SysFont(None, 24)
        station_name = get_station_name(self.wave_number)
        name_surf = font.render(f">> HOSTILE STATION {station_name} <<", True, BOSS_COLOR)
        name_rect = name_surf.get_rect(center=(cx, bar_y - 15))
        surface.blit(name_surf, name_rect)

    def is_alive(self):
        # Boss is alive if it has health AND at least one component is active
        return self.health > 0 and any(component['active'] for component in self.components)

    def get_collision_radius(self):
        # Check if any components are still visible
        any_components_active = any(component['active'] for component in self.components)
        if not any_components_active and self.health > 0:
            # Emergency core mode - smaller collision radius
            return 25
        return self.size * 0.8

def run_debris_game(use_deluxe_background: bool = True):
    """
    Run the Space Debris Cleanup game - ENHANCED with Boss Battles and Power-ups!
    
    Controls:
    - Arrow keys to move and rotate space station
    - SPACE to fire energy beams
    - ESC to exit
    
    Features:
    - Boss battle after clearing first wave
    - Chain reaction explosions
    - Shield and Multishot power-ups
    - Realistic physics and visuals
    
    Parameters:
        use_deluxe_background: if True, render parallax starfield background from the demo
    """
    if not PYGAME_AVAILABLE:
        print("Pygame is not installed. Cannot run Space Debris game.")
        return

    pygame.init()
    screen = pygame.display.set_mode((DEBRIS_WIDTH, DEBRIS_HEIGHT), pygame.SHOWN)
    pygame.display.update()  # Force the window to appear
    
    # Enhanced window focus management
    try:
        # Get window handle for focus management
        import os
        window_id = pygame.display.get_wm_info()['window']
        
        # Bring to foreground initially
        bring_to_foreground(window_id)
        
        # Cross-platform window management for games
        class GameWindowManager:
            """Cross-platform game window management"""
            
            @staticmethod
            def keep_on_top():
                """Keep game window on top (cross-platform)"""
                try:
                    if os.name == 'nt':  # Windows
                        import ctypes
                        SetWindowPos = ctypes.windll.user32.SetWindowPos
                        SWP_NOMOVE = 0x0002
                        SWP_NOSIZE = 0x0001
                        HWND_TOPMOST = -1
                        SetWindowPos(window_id, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                    elif sys.platform == 'darwin':  # macOS
                        # macOS doesn't typically need this for games
                        bring_to_foreground(window_id)
                    else:  # Linux
                        # Try X11 window manager hints
                        try:
                            import subprocess
                            subprocess.run(['wmctrl', '-r', ':ACTIVE:', '-b', 'add,above'], 
                                         capture_output=True, timeout=1)
                        except:
                            bring_to_foreground(window_id)
                except:
                    bring_to_foreground(window_id)
            
            @staticmethod
            def restore_normal():
                """Restore window to normal level (cross-platform)"""
                try:
                    if os.name == 'nt':  # Windows
                        import ctypes
                        SetWindowPos = ctypes.windll.user32.SetWindowPos
                        SWP_NOMOVE = 0x0002
                        SWP_NOSIZE = 0x0001
                        HWND_NOTOPMOST = -2
                        SetWindowPos(window_id, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                    elif sys.platform == 'darwin':  # macOS
                        pass  # Usually not needed
                    else:  # Linux
                        try:
                            import subprocess
                            subprocess.run(['wmctrl', '-r', ':ACTIVE:', '-b', 'remove,above'], 
                                         capture_output=True, timeout=1)
                        except:
                            pass
                except:
                    pass
        
        # Create convenience functions
        keep_on_top = GameWindowManager.keep_on_top
        restore_normal = GameWindowManager.restore_normal
    except:
        # If all window management fails, create dummy functions
        window_id = None
        def keep_on_top():
            pass
        def restore_normal():
            pass
        
    clock = pygame.time.Clock()
    pygame.display.set_caption("Space Debris Cleanup – Enhanced with Boss Battles!")
    
    # Make window active and focused
    pygame.event.set_grab(True)  # Grab input focus
    pygame.event.set_grab(False)  # Release but keep focus

    # Load high score
    load_high_score()

    # Game state
    station = SpaceStation()
    bullets = []
    boss_bullets = []  # Separate list for boss bullets
    debris_field = [SatelliteDebris(size=3) for _ in range(5)]
    explosions = []
    powerups = []
    boss = None
    score = 0
    lives = 3
    game_over = False
    invulnerable_time = 0
    wave_number = 1
    boss_defeated = False
    first_wave_cleared = False
    new_high_score = False

    font = pygame.font.SysFont(None, 24)
    big_font = pygame.font.SysFont(None, 48)

    # Parallax starfield background setup (always on)
    stars_far = _ParallaxStarLayer(count=120, speed_y=0.05, twinkle=False)
    stars_mid = _ParallaxStarLayer(count=80, speed_y=0.10, twinkle=True)
    stars_near = _ParallaxStarLayer(count=60, speed_y=0.18, twinkle=True)
    
    def create_chain_explosion(pos, debris_list, current_score):
        """Create chain reaction explosions"""
        explosion = Explosion(pos, EXPLOSION_RADIUS)
        explosions.append(explosion)
        
        # Check for nearby debris to chain explode
        chain_debris = []
        debris_to_remove = []  # Track debris to remove separately
        
        for debris in debris_list[:]:  # Create copy to iterate safely
            if distance(pos, debris.pos) < CHAIN_RADIUS:
                chain_debris.append(debris)
                debris_to_remove.append(debris)
                # Add points for chain reaction
                current_score += 50 * debris.size
                
                # Chance to spawn power-up from chained debris
                if random.random() < 0.3:  # 30% chance
                    powerup_type = random.choice(['shield', 'multishot'])
                    powerups.append(PowerUp(debris.pos, powerup_type))
        
        # Remove debris safely - only if they're still in the list
        for debris in debris_to_remove:
            if debris in debris_list:
                debris_list.remove(debris)
        
        # Schedule delayed explosions for chain reaction
        def delayed_explosion():
            for debris in chain_debris:
                if debris is not None and random.random() < 0.7:  # 70% chance to continue chain
                    # Delayed explosion after 0.3 seconds - check debris still exists
                    def safe_chain_explosion(d=debris):
                        if d is not None and hasattr(d, 'pos'):
                            create_chain_explosion(d.pos, debris_field, 0)
                    threading.Timer(0.3, safe_chain_explosion).start()
        
        if chain_debris:
            threading.Timer(0.2, delayed_explosion).start()
            
        return current_score
    
    def fire_bullets():
        """Fire bullets based on current power-ups"""
        if station.has_multishot():
            # Fire 3 bullets in spread pattern
            angles = [station.angle - 15, station.angle, station.angle + 15]
            for angle in angles:
                bullets.append(EnergyBullet(station.pos, angle))
        else:
            # Single bullet
            bullets.append(EnergyBullet(station.pos, station.angle))
    
    run = True
    while run:
        clock.tick(DEBRIS_FPS)
        keys = pygame.key.get_pressed()
        
        # Global declarations for analysis notifications
        global _analysis_notifications, _show_analysis_complete

        for evt in pygame.event.get():
            if evt.type == pygame.QUIT:
                run = False
            if evt.type == pygame.KEYDOWN and evt.key == pygame.K_SPACE and not game_over:
                fire_bullets()
            if evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                run = False
            if evt.type == pygame.KEYDOWN and evt.key == pygame.K_RETURN:
                # Handle analysis notification dismissal
                if _analysis_notifications:
                    clear_analysis_notifications()
                    # Brief flash to show notification was dismissed
                    screen.fill((50, 50, 50))
                    dismiss_surf = font.render("Notifications dismissed - continue playing!", True, (100, 255, 100))
                    dismiss_rect = dismiss_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2))
                    screen.blit(dismiss_surf, dismiss_rect)
                    pygame.display.flip()
                    time.sleep(0.5)  # Brief pause to show dismissal
            if evt.type == pygame.KEYDOWN and evt.key == pygame.K_r and game_over:
                # Restart game
                station = SpaceStation()
                bullets = []
                boss_bullets = []
                debris_field = [SatelliteDebris(size=3) for _ in range(5)]
                explosions = []
                powerups = []
                boss = None
                score = 0
                lives = 3
                game_over = False
                invulnerable_time = 0
                wave_number = 1
                boss_defeated = False
                first_wave_cleared = False
                new_high_score = False

        if not game_over:
            # Update invulnerability timer
            if invulnerable_time > 0:
                invulnerable_time -= 1
            
            # Update game objects
            station.update(keys)
            
            # Update bullets
            for b in bullets[:]:
                b.update()
                if b.life <= 0:
                    bullets.remove(b)
            
            # Update explosions
            for explosion in explosions[:]:
                explosion.update()
                if not explosion.is_alive():
                    explosions.remove(explosion)
            
            # Update power-ups
            for powerup in powerups[:]:
                powerup.update()
                if not powerup.is_alive():
                    powerups.remove(powerup)
                else:
                    # Check if player collected power-up
                    if distance(station.pos, powerup.pos) < 30:
                        if powerup.type == 'shield':
                            station.activate_shield()
                        elif powerup.type == 'multishot':
                            station.activate_multishot()
                        powerups.remove(powerup)
                        score += 200  # Bonus for collecting power-up
            
            # Update debris and check collisions
            station_hit = False
            for debris in debris_field[:]:
                debris.update()
                
                # Collision with bullets
                for b in bullets[:]:
                    if distance(debris.pos, b.pos) < DEBRIS_SIZES[debris.size] * 0.5:
                        bullets.remove(b)
                        # Debris may have been removed by a concurrent chain explosion timer
                        if debris in debris_field:
                            debris_field.remove(debris)
                        score += 150 * debris.size
                        
                        # Create explosion and potential chain reaction
                        score = create_chain_explosion(debris.pos, debris_field, score)
                        
                        # Chance to spawn power-up
                        if random.random() < 0.15:  # 15% chance
                            powerup_type = random.choice(['shield', 'multishot'])
                            powerups.append(PowerUp(debris.pos, powerup_type))
                        
                        # Break into smaller pieces
                        if debris.size > 1:
                            debris_field += [SatelliteDebris(pos=debris.pos, size=debris.size-1) for _ in range(2)]
                        break
                
                # Check station-debris collision (only if not invulnerable and no shield)
                if invulnerable_time <= 0 and not station.has_shield():
                    station_collision_radius = max(STATION_WIDTH, STATION_HEIGHT) * 0.7
                    debris_collision_radius = DEBRIS_SIZES[debris.size] * 0.4
                    collision_distance = station_collision_radius + debris_collision_radius
                    
                    if distance(station.pos, debris.pos) < collision_distance:
                        station_hit = True
                        lives -= 1
                        invulnerable_time = 120  # 2 seconds of invulnerability at 60 FPS
                        
                        # Create explosion
                        score = create_chain_explosion(debris.pos, debris_field, score)
                        
                        if debris in debris_field:
                            debris_field.remove(debris)
                        
                        if lives <= 0:
                            game_over = True
                            # Check for new high score
                            new_high_score = save_high_score(score)
                        else:
                            # Reset station position and velocity
                            station = SpaceStation()
                        break

            # Update boss bullets
            for bb in boss_bullets[:]:
                bb.update()
                if bb.life <= 0:
                    boss_bullets.remove(bb)
                
                # Boss bullet vs player bullet collision (they cancel each other out)
                bullet_hit = False
                for pb in bullets[:]:
                    if distance(bb.pos, pb.pos) < 15:  # Bullet collision radius
                        boss_bullets.remove(bb)
                        bullets.remove(pb)
                        # Create small explosion at collision point
                        explosions.append(Explosion(bb.pos, 15))
                        score += 100  # Bonus points for defensive shooting
                        bullet_hit = True
                        break
                
                if bullet_hit:
                    continue
                
                # Boss bullet collision with station (only if not invulnerable and no shield)
                if invulnerable_time <= 0 and not station.has_shield():
                    if distance(station.pos, bb.pos) < 25:  # Station collision radius
                        boss_bullets.remove(bb)
                        lives -= 1
                        invulnerable_time = 120
                        
                        # Create explosion at hit location
                        explosions.append(Explosion(bb.pos, 30))
                        
                        if lives <= 0:
                            game_over = True
                            # Check for new high score
                            new_high_score = save_high_score(score)
                        else:
                            station = SpaceStation()
                        break

            # Boss battle logic
            if boss and boss is not None:
                boss.update(station.pos)
                
                # Boss shooting (may return multiple bullets)
                new_bullets = boss.shoot_at_target(station.pos)
                if new_bullets:
                    boss_bullets.extend(new_bullets)
                
                # Boss collision with bullets
                for b in bullets[:]:
                    if distance(boss.pos, b.pos) < boss.get_collision_radius():
                        if boss.take_damage(b.pos):
                            bullets.remove(b)
                            score += 500  # Big points for hitting boss
                            
                            # Create explosion at hit location
                            explosions.append(Explosion(b.pos, 20))
                
                # Boss collision with station (only if not invulnerable and no shield)
                if invulnerable_time <= 0 and not station.has_shield():
                    if distance(station.pos, boss.pos) < boss.get_collision_radius():
                        lives -= 1
                        invulnerable_time = 120
                        
                        if lives <= 0:
                            game_over = True
                            # Check for new high score
                            new_high_score = save_high_score(score)
                        else:
                            station = SpaceStation()
                
                # Check if boss is defeated
                if not boss.is_alive():
                    # Store boss position before setting to None
                    boss_pos = boss.pos
                    
                    # Boss defeated! Big explosion and rewards
                    score = create_chain_explosion(boss_pos, [], score)
                    explosions.append(Explosion(boss_pos, 100))  # Big explosion
                    score += 5000 + (wave_number * 1000)  # More bonus for later waves
                    boss_defeated = True
                    
                    # Spawn multiple power-ups as reward
                    for i in range(3):
                        angle = i * 120
                        powerup_x = boss_pos[0] + math.cos(math.radians(angle)) * 50
                        powerup_y = boss_pos[1] + math.sin(math.radians(angle)) * 50
                        powerup_type = ['shield', 'multishot'][i % 2]
                        powerups.append(PowerUp((powerup_x, powerup_y), powerup_type))
                    
                    # Spawn next wave of debris (more challenging each time)
                    wave_size = min(4 + wave_number, 10)
                    debris_field = [SatelliteDebris(size=3) for _ in range(wave_size)]
                    
                    # Set boss to None after using its position
                    boss = None

            # Check if all debris cleared
            if not debris_field and not game_over and not boss:
                # Every wave cleared spawns a bigger, stronger boss!
                boss = BossSatellite(wave_number)
                # Make boss stronger with each wave - health matches component total
                health_multiplier = 1 + (wave_number - 1) * 0.2
                total_component_health = int(17 * health_multiplier)  # 5+2+2+3+3+2 = 17 base
                boss.health = total_component_health
                boss.max_health = boss.health
                boss.size = BOSS_SIZE + (wave_number - 1) * 10
                boss_defeated = False
                wave_number += 1

        # Draw everything
        screen.fill(SPACE_BLUE)  # Deep space background
        
        # Parallax starfield layers
        stars_far.update(); stars_far.draw(screen)
        stars_mid.update(); stars_mid.draw(screen)
        stars_near.update(); stars_near.draw(screen)
        
        # Earth circle removed as requested
        
        # Draw game objects
        if not game_over:
            if invulnerable_time <= 0 or (invulnerable_time // 5) % 2 == 0:
                station.draw(screen, keys)
        
        # Draw explosions first (behind other objects)
        for explosion in explosions:
            explosion.draw(screen)
        
        for b in bullets:  
            b.draw(screen)
            
        # Draw boss bullets
        for bb in boss_bullets:
            bb.draw(screen)
            
        for debris in debris_field: 
            debris.draw(screen)
            
        for powerup in powerups:
            powerup.draw(screen)
            
        if boss and boss is not None:
            boss.draw(screen)
        
        # Draw UI
        score_surf = font.render(f"Score: {score}", True, WHITE)
        screen.blit(score_surf, (10, 10))
        
        # High score display
        high_score_color = (255, 215, 0) if score > _high_score else (150, 150, 150)
        high_score_surf = font.render(f"High Score: {_high_score}", True, high_score_color)
        screen.blit(high_score_surf, (10, 35))
        
        lives_surf = font.render(f"Lives: {lives}", True, WHITE)
        screen.blit(lives_surf, (10, 60))
        
        wave_surf = font.render(f"Wave: {wave_number}", True, WHITE)
        screen.blit(wave_surf, (10, 85))
        
        debris_count_surf = font.render(f"Debris: {len(debris_field)}", True, WHITE)
        screen.blit(debris_count_surf, (10, 110))
        
        # Show active power-ups
        power_up_y = 135
        if station.has_shield():
            shield_surf = font.render(f"Shield: {station.shield_time//60 + 1}s", True, SHIELD_COLOR)
            screen.blit(shield_surf, (10, power_up_y))
            power_up_y += 25
        
        if station.has_multishot():
            multishot_surf = font.render(f"Multishot: {station.multishot_time//60 + 1}s", True, POWERUP_MULTISHOT_COLOR)
            screen.blit(multishot_surf, (10, power_up_y))
            power_up_y += 25
        
        # Show invulnerability status
        if invulnerable_time > 0 and not game_over:
            invuln_surf = font.render(f"Hull Breach: {invulnerable_time//60 + 1}s", True, (255, 100, 100))
            screen.blit(invuln_surf, (10, power_up_y))
        
        # Boss warning
        if boss and not game_over:
            warning_surf = big_font.render(">>> BOSS BATTLE <<<", True, BOSS_COLOR)
            warning_rect = warning_surf.get_rect(center=(DEBRIS_WIDTH//2, 30))
            screen.blit(warning_surf, warning_rect)
        
        # Story text
        if boss_defeated:
            destroyed_station = get_station_name(wave_number-1)
            story_surf = font.render(f">> STATION {destroyed_station} DESTROYED! Next wave incoming... <<", True, (100, 255, 100))
        elif boss:
            station_name = get_station_name(boss.wave_number)
            station_desc = get_station_description(boss.wave_number)
            story_surf = font.render(f">> HOSTILE STATION {station_name} - {station_desc}! <<", True, BOSS_COLOR)
        else:
            story_surf = font.render("Mission: Clean up satellite debris - Boss stations will attack!", True, (100, 100, 255))
        screen.blit(story_surf, (10, DEBRIS_HEIGHT - 25))
        
        # Analysis completion notifications
        if _analysis_notifications:
            # Keep game window on top when showing notifications
            keep_on_top()
            
            # Create semi-transparent overlay
            overlay = pygame.Surface((DEBRIS_WIDTH, DEBRIS_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))
            
            # Main notification
            notif_y = 150
            for i, notification in enumerate(_analysis_notifications[-3:]):  # Show last 3 notifications
                if i == 0 and _show_analysis_complete:
                    # Main completion message - larger font
                    notif_surf = big_font.render(notification, True, (100, 255, 100))
                    notif_rect = notif_surf.get_rect(center=(DEBRIS_WIDTH//2, notif_y))
                    screen.blit(notif_surf, notif_rect)
                    notif_y += 60
                else:
                    # Additional messages
                    notif_surf = font.render(notification, True, WHITE)
                    notif_rect = notif_surf.get_rect(center=(DEBRIS_WIDTH//2, notif_y))
                    screen.blit(notif_surf, notif_rect)
                    notif_y += 30
            
            # Instructions
            if _show_analysis_complete:
                instruction_surf = font.render("Press ENTER to view results or continue playing", True, (255, 255, 0))
                instruction_rect = instruction_surf.get_rect(center=(DEBRIS_WIDTH//2, notif_y + 20))
                screen.blit(instruction_surf, instruction_rect)
        else:
            # Restore normal window behavior when no notifications
            restore_normal()
        
        if game_over:
            # Game over screen
            game_over_surf = big_font.render("MISSION COMPLETE", True, WHITE)
            if lives <= 0:
                game_over_surf = big_font.render("STATION DESTROYED", True, (255, 100, 100))
            game_over_rect = game_over_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2 - 75))
            screen.blit(game_over_surf, game_over_rect)
            
            final_score_surf = font.render(f"Final Score: {score}", True, WHITE)
            final_score_rect = final_score_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2 - 25))
            screen.blit(final_score_surf, final_score_rect)
            
            # Show high score status
            if new_high_score:
                high_score_surf = font.render(">>> NEW HIGH SCORE! <<<", True, (255, 215, 0))
                high_score_rect = high_score_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2))
                screen.blit(high_score_surf, high_score_rect)
            else:
                high_score_surf = font.render(f"High Score: {_high_score}", True, (150, 150, 150))
                high_score_rect = high_score_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2))
                screen.blit(high_score_surf, high_score_rect)
            
            if boss_defeated:
                achievement_surf = font.render(">>> BOSS DEFEATED! Outstanding pilot! <<<", True, (255, 215, 0))
                achievement_rect = achievement_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2 + 25))
                screen.blit(achievement_surf, achievement_rect)
            
            restart_surf = font.render("Press R to Restart or ESC to Exit", True, WHITE)
            restart_rect = restart_surf.get_rect(center=(DEBRIS_WIDTH//2, DEBRIS_HEIGHT//2 + 50))
            screen.blit(restart_surf, restart_rect)

        pygame.display.flip()

    pygame.quit()

def show_game_menu_integrated(parent_window, callback=None):
    """
    Show an integrated game selection UI within a Qt parent window.
    Now only shows the Space Debris game.

    Parameters:
        parent_window: The parent Qt widget (QWidget)
        callback: Optional function called with selected game callable or None

    Returns:
        A Qt widget (QFrame) that can be embedded in the parent, or None if unavailable
    """
    if not PYGAME_AVAILABLE:
        if PYSIDE6_AVAILABLE:
            QtWidgets.QMessageBox.warning(
                parent_window if isinstance(parent_window, QtWidgets.QWidget) else None,
                "Games Not Available",
                "Pygame is not installed. Games require pygame.\n\n"
                "You can install it with: pip install pygame"
            )
        else:
            print("\nPygame is not installed. Games require pygame.")
            print("You can install it with: pip install pygame")
        return None

    if not PYSIDE6_AVAILABLE:
        # No Qt available to render integrated UI
        return None

    # Create a container frame
    frame = QtWidgets.QFrame(parent_window if isinstance(parent_window, QtWidgets.QWidget) else None)
    frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
    frame.setStyleSheet("background-color: #2c3e50;")

    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(20, 15, 20, 15)

    # Title
    title = QtWidgets.QLabel("Space Debris Cleanup!")
    title.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 16px;")
    layout.addWidget(title)

    # Subtitle
    subtitle = QtWidgets.QLabel("Realistic space simulation while SNID analysis runs")
    subtitle.setStyleSheet("color: #bdc3c7; font-size: 11px;")
    layout.addWidget(subtitle)

    # Description
    desc = QtWidgets.QLabel(
        "Pilot a detailed spacecraft with wings and thrusters\n"
        "Clean up 4 types of realistic satellite debris\n"
        "Energy bullets with particle trail effects\n"
        "Deep space background with twinkling stars\n"
        "Satellites with solar panels and antennas"
    )
    desc.setAlignment(QtCore.Qt.AlignCenter)
    desc.setStyleSheet("color: #95a5a6; font-size: 11px;")
    layout.addWidget(desc)

    # Buttons
    button_row = QtWidgets.QHBoxLayout()
    layout.addLayout(button_row)

    start_btn = QtWidgets.QPushButton("Start Space Debris Cleanup")
    start_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px; font-weight: bold;")
    cancel_btn = QtWidgets.QPushButton("❌ No Thanks")
    cancel_btn.setStyleSheet("background-color: #7f8c8d; color: white; padding: 6px;")
    button_row.addWidget(start_btn)
    button_row.addWidget(cancel_btn)

    def on_start():
        try:
            t = threading.Thread(target=run_debris_game, daemon=True)
            t.start()
            frame.setVisible(False)
            if callback:
                callback(run_debris_game)
        except Exception as e:
            print(f"Error starting game: {e}")

    def on_cancel():
        frame.setVisible(False)
        if callback:
            callback(None)

    start_btn.clicked.connect(on_start)
    cancel_btn.clicked.connect(on_cancel)

    return frame

def show_game_menu() -> Optional[Callable]:
    """
    Show a GUI dialog (Qt if available) to select the Space Debris game.

    Returns:
        Function to launch the Space Debris game or None if canceled
    """
    if not PYGAME_AVAILABLE:
        if PYSIDE6_AVAILABLE:
            QtWidgets.QMessageBox.warning(
                None,
                "Games Not Available",
                "Pygame is not installed. Games require pygame.\n\n"
                "You can install it with: pip install pygame"
            )
        else:
            print("\nPygame is not installed. Games require pygame.")
            print("You can install it with: pip install pygame")
        return None

    if PYSIDE6_AVAILABLE:
        try:
            app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv if hasattr(sys, 'argv') else [])

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
                "🛰️ Clean up 4 types of realistic satellite debris\n"
                "⚡ Energy bullets with particle trail effects\n"
                "🌌 Deep space background with twinkling stars\n"
                "📡 Satellites with solar panels and antennas"
            )
            desc = QtWidgets.QLabel(desc_text)
            desc.setAlignment(QtCore.Qt.AlignLeft)
            desc.setStyleSheet("background:#34495e; color:#ecf0f1; padding:10px;")
            layout.addWidget(desc)

            btn_start = QtWidgets.QPushButton("Start Space Debris Cleanup")
            btn_start.setStyleSheet("background:#e74c3c; color:white; padding:10px; font-weight: bold;")
            btn_cancel = QtWidgets.QPushButton("❌ No Thanks")
            btn_cancel.setStyleSheet("background:#7f8c8d; color:white; padding:8px;")

            button_row = QtWidgets.QHBoxLayout()
            button_row.addWidget(btn_start)
            button_row.addWidget(btn_cancel)
            layout.addLayout(button_row)

            selected = {"fn": None}

            def accept():
                selected["fn"] = run_debris_game
                dialog.accept()

            def reject():
                selected["fn"] = None
                dialog.reject()

            btn_start.clicked.connect(accept)
            btn_cancel.clicked.connect(reject)

            dialog.exec()
            return selected["fn"]
        except Exception as e:
            print(f"Qt dialog failed ({e}), falling back to console...")

    # Console fallback
    is_noninteractive = (
        not sys.stdin.isatty() or
        os.environ.get('CI') or
        os.environ.get('GITHUB_ACTIONS') or
        os.environ.get('RUNNER_OS') or
        os.environ.get('SNID_NONINTERACTIVE')
    )

    if is_noninteractive:
        print("Running in non-interactive environment, skipping game selection.")
        return None

    print("\nWould you like to play Space Debris Cleanup while you wait?")
    print("1. Space Debris Cleanup")
    print("2. No thanks")

    while True:
        choice = input("Enter choice (1-2): ").strip()
        if choice == '1':
            return run_debris_game
        elif choice == '2' or choice.lower() in ('n', 'no', 'q', 'quit'):
            return None
        else:
            print("Invalid choice. Please try again.")

def play_game_while_waiting(task_name: str = "SNID processing"):
    """
    Ask the user if they want to play the Space Debris game while waiting for a task to complete.
    This function is typically called from a background worker (thread or process).
    
    Parameters:
        task_name: Name of the task being waited for
    """
    game_func = show_game_menu()
    if game_func:
        print(f"\nStarting Space Debris Cleanup while {task_name} continues in the background.")
        print("Game will close when you exit it manually (ESC key or close button).")
        game_func()
        
def run_game_in_thread(task_name: str = "SNID processing"):
    """
    Run the Space Debris game while a task is running.
    
    On macOS, avoid running the Pygame window from a background thread (can crash with Cocoa/SDL).
    Instead, launch a separate process so the game runs in that process's main thread.
    
    Parameters:
        task_name: Name of the task being waited for
    
    Returns:
        threading.Thread | multiprocessing.Process: handle that can be monitored
    """
    try:
        if sys.platform == 'darwin':
            # Launch a separate process to keep the Pygame window on a main thread in that process
            import multiprocessing as mp
            game_proc = mp.Process(target=play_game_while_waiting, args=(task_name,))
            game_proc.daemon = True
            game_proc.start()
            return game_proc
        else:
            game_thread = threading.Thread(target=play_game_while_waiting, args=(task_name,))
            game_thread.daemon = True  # Thread will be killed when the main program exits
            game_thread.start()
            return game_thread
    except Exception:
        # Fallback: run synchronously if spawning fails
        play_game_while_waiting(task_name)
        return None

def set_analysis_complete(result_summary=None):
    """Called by the analysis system when SNID analysis completes"""
    if result_summary:
        notify_analysis_complete("🎉 SNID Analysis Complete!")
        notify_analysis_result(f"📊 {result_summary}")
        notify_analysis_result("Press ENTER to continue playing")
    else:
        notify_analysis_complete("🎉 SNID Analysis Complete!")
        notify_analysis_result("Check the main window for results")
        notify_analysis_result("Press ENTER to continue playing")

# For testing the game directly
if __name__ == "__main__":
    play_game_while_waiting() 