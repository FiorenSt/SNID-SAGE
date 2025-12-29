"""
Twemoji Manager for SNID SAGE GUI
=================================

This module provides Twemoji icon integration for consistent emoji rendering
across all platforms, especially fixing the emoji display issues on Linux.

Features:
- Automatic Twemoji asset management
- SVG to QIcon conversion
- Emoji Unicode to filename mapping
- Caching for performance
- Fallback to text emojis if icons unavailable

Usage:
    manager = TwemojiManager()
    icon = manager.get_icon("⚙️")  # Returns QIcon
    manager.set_button_icon(button, "⚙️")  # Sets icon on button

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from importlib import resources
from typing import Dict, Optional, Union, Tuple
from urllib.request import urlretrieve
from urllib.error import URLError

# PySide6 imports
try:
    from PySide6 import QtWidgets, QtGui, QtCore, QtSvg
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

# Logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.twemoji')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.twemoji')


class TwemojiManager:
    """
    Manager for Twemoji icons in PySide6 applications.
    
    This class handles downloading, caching, and converting Twemoji SVG icons
    to QIcons for use in Qt applications, providing consistent emoji rendering
    across all platforms.
    """
    
    # Twemoji CDN base URL for SVG icons
    TWEMOJI_CDN_BASE = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/"
    
    # Common emojis used in SNID SAGE with their Unicode codepoints
    # Some emojis don't use variation selectors in Twemoji filenames
    EMOJI_MAPPING = {
        # Main export/data buttons
        "📊": "1f4ca",          # Bar Chart/Export Data/Charts
        "💾": "1f4be",          # Floppy Disk/Save
        "🔍": "1f50d",          # Magnifying Glass/Search
        "📈": "1f4c8",          # Chart Up/Export Plot
        "📉": "1f4c9",          # Chart Down  
        "📋": "1f4cb",          # Clipboard/Copy
        
        # Utility buttons for dialogs  
        "🛰️": "1f6f0",         # Satellite/Space (no fe0f in Twemoji)
        "👁️": "1f441",          # Eye/Hide (no fe0f in Twemoji)
        "🗑️": "1f5d1",          # Wastebasket/Remove (no fe0f in Twemoji)
        "⭐": "2b50",           # Star
        "🤖": "1f916",          # Robot/AI
        "⚠️": "26a0",           # Warning (no fe0f in Twemoji)
        "❌": "274c",           # Cross Mark/Error
        "✅": "2705",           # Check Mark/Success
        "🚨": "1f6a8",          # Police car light / error indicator
        "🚫": "1f6ab",          # Prohibited / not allowed
        
        # Analysis results buttons
        "📋": "1f4cb",          # Clipboard/Summary Report
        "🎯": "1f3af",          # Target/GMM Clustering
        "🍰": "1f370",          # Shortcake/Pie Chart
        "🎨": "1f3a8",          # Artist Palette

        # Template manager and other UI tabs/actions
        "✨": "2728",            # Sparkles / Create
        "🔧": "1f527",          # Wrench / Manage
        "⚖️": "2696",           # Balance scale / Compare (no fe0f in Twemoji)
        # Intentionally omit ℹ/ℹ️ to keep system glyph for the info button
        "⚡": "26a1",            # High voltage / Quick

        # Plot export menu and misc
        "📷": "1f4f7",          # Camera
        "📄": "1f4c4",          # Page

        # Dialog utility
        "🔄": "1f504",          # Anticlockwise arrows button / Refresh
        "❓": "2753",           # Question mark

        # Settings
        "🖥️": "1f5a5",          # Desktop computer (no fe0f in Twemoji)

        # Rare but present in logs/UI
        "🔴": "1f534",          # Red circle
        "🐌": "1f40c",          # Snail (used in logs)
    }
    
    def __init__(self, cache_dir: Optional[Path] = None, icon_size: int = 16, allow_network_downloads: Optional[bool] = None):
        """
        Initialize the Twemoji manager.
        
        Args:
            cache_dir: Directory to cache downloaded icons (defaults to user cache)
            icon_size: Size in pixels for the icons (default 16 for buttons)
            allow_network_downloads: If True, allow CDN fallback; if False, never
                perform network operations. Defaults to environment variable
                SNID_SAGE_TWEMOJI_NETWORK (off by default).
        """
        self.icon_size = icon_size
        self.cache: Dict[str, QtGui.QIcon] = {}
        # By default, do not perform network access unless explicitly enabled
        if allow_network_downloads is None:
            env_flag = os.environ.get("SNID_SAGE_TWEMOJI_NETWORK", "").strip().lower()
            self.allow_network_downloads = env_flag in {"1", "true", "yes", "on"}
        else:
            self.allow_network_downloads = bool(allow_network_downloads)
        
        # Set up cache directory
        if cache_dir is None:
            # Use platform-appropriate cache directory
            if sys.platform == "win32":
                cache_base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            else:
                cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            
            self.cache_dir = cache_base / "snid_sage" / "twemoji"
        else:
            self.cache_dir = Path(cache_dir)
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        _LOGGER.info(f"TwemojiManager initialized with cache at: {self.cache_dir}")
    
    def _get_unicode_codepoint(self, emoji: str) -> Optional[str]:
        """
        Get the Unicode codepoint for an emoji.
        
        Args:
            emoji: The emoji character
            
        Returns:
            Unicode codepoint string or None if not found
        """
        # Check our predefined mapping first
        if emoji in self.EMOJI_MAPPING:
            return self.EMOJI_MAPPING[emoji]
        
        # For other emojis, convert to Unicode codepoint
        try:
            # Convert emoji to Unicode codepoints
            codepoints = []
            for char in emoji:
                cp = ord(char)
                if cp != 0xfe0f:  # Skip variation selector
                    codepoints.append(f"{cp:x}")
            
            if codepoints:
                result = "-".join(codepoints)
                _LOGGER.debug(f"Converted emoji '{emoji}' to codepoint: {result}")
                return result
        except Exception as e:
            _LOGGER.warning(f"Failed to convert emoji '{emoji}' to codepoint: {e}")
        
        return None
    
    def _get_packaged_svg_path(self, codepoint: str) -> Optional[Path]:
        """Return packaged SVG path if available inside snid_sage.images.twemoji."""
        try:
            # Prefer importlib.resources to work for both source and wheels
            # Use the root package ('snid_sage') to traverse into the 'images/twemoji' directory.
            # This works even if 'images' is not a Python package.
            with resources.as_file(resources.files('snid_sage') / 'images' / 'twemoji' / f'{codepoint}.svg') as svg_path:
                if svg_path.exists():
                    return svg_path
        except Exception as exc:
            _LOGGER.debug(f"Packaged Twemoji not found for {codepoint}: {exc}")
        return None

    def _ensure_cached_or_packaged_icon(self, emoji: str, codepoint: str) -> Optional[Path]:
        """
        Prefer packaged SVGs bundled with the package. If not present, fall back to
        user cache, downloading from the CDN only if needed.
        """
        # 1) Packaged asset takes priority
        packaged = self._get_packaged_svg_path(codepoint)
        if packaged is not None:
            return packaged

        # 2) User cache
        cache_file = self.cache_dir / f"{codepoint}.svg"
        if cache_file.exists():
            return cache_file

        # 3) As a last resort, optionally download to cache (never on UI thread by default)
        if not self.allow_network_downloads:
            _LOGGER.debug(
                f"Twemoji '{emoji}' ({codepoint}) not packaged or cached; network downloads disabled"
            )
            return None
        url = f"{self.TWEMOJI_CDN_BASE}{codepoint}.svg"
        try:
            _LOGGER.info(f"Downloading Twemoji icon for '{emoji}' from: {url}")
            urlretrieve(url, cache_file)
            return cache_file
        except URLError as e:
            _LOGGER.warning(f"Failed to download Twemoji icon for '{emoji}': {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Unexpected error downloading icon for '{emoji}': {e}")
            return None
    
    def get_icon(self, emoji: str) -> Optional[QtGui.QIcon]:
        """
        Get a QIcon for the specified emoji.
        
        Args:
            emoji: The emoji character
            
        Returns:
            QIcon object or None if unavailable
        """
        if not PYSIDE6_AVAILABLE:
            _LOGGER.debug("PySide6 not available, cannot create QIcon")
            return None
        
        # Check cache first
        if emoji in self.cache:
            return self.cache[emoji]
        
        # Get Unicode codepoint
        codepoint = self._get_unicode_codepoint(emoji)
        if not codepoint:
            _LOGGER.debug(f"No codepoint mapping found for emoji: {emoji}")
            return None
        
        # Get SVG path (packaged preferred, then cache, then download)
        svg_path = self._ensure_cached_or_packaged_icon(emoji, codepoint)
        if not svg_path or not svg_path.exists():
            _LOGGER.debug(f"Failed to get SVG file for emoji: {emoji}")
            return None
        
        try:
            # Create QIcon from SVG
            icon = QtGui.QIcon(str(svg_path))
            
            # Cache the icon
            self.cache[emoji] = icon
            
            _LOGGER.debug(f"Created QIcon for emoji: {emoji}")
            return icon
        
        except Exception as e:
            _LOGGER.error(f"Failed to create QIcon for emoji '{emoji}': {e}")
            return None

    def get_svg_path_for_emoji(self, emoji: str) -> Optional[Path]:
        """Return a filesystem Path to the SVG for an emoji (packaged/cache/downloaded)."""
        codepoint = self._get_unicode_codepoint(emoji)
        if not codepoint:
            return None
        svg_path = self._ensure_cached_or_packaged_icon(emoji, codepoint)
        if svg_path and svg_path.exists():
            return svg_path
        return None
    
    def set_button_icon(self, button: QtWidgets.QPushButton, emoji: str, keep_text: bool = True) -> bool:
        """
        Set a Twemoji icon on a QPushButton.
        
        Args:
            button: The QPushButton to modify
            emoji: The emoji character
            keep_text: Whether to keep the text after the emoji (default True)
            
        Returns:
            True if icon was set successfully, False otherwise
        """
        if not PYSIDE6_AVAILABLE:
            return False
        
        icon = self.get_icon(emoji)
        if not icon:
            # If we can't get an icon, only strip the emoji when there is additional label text.
            # Preserve pure-symbol buttons like "◀"/"▶" so their Unicode glyphs remain visible.
            try:
                if keep_text:
                    current_text = button.text() or ""
                    if current_text.startswith(emoji):
                        new_text = (current_text[len(emoji):]).strip()
                        if new_text:
                            button.setText(new_text)
                _LOGGER.debug(f"No Twemoji icon for '{emoji}'. Kept original text when it contained only the symbol.")
            except Exception:
                pass
            return False
        
        try:
            # Set the icon
            button.setIcon(icon)
            button.setIconSize(QtCore.QSize(self.icon_size, self.icon_size))
            
            if keep_text:
                # Remove emoji from text but keep the rest
                current_text = button.text()
                if current_text.startswith(emoji):
                    new_text = current_text[len(emoji):].strip()
                    button.setText(new_text)
            else:
                # Remove all text
                button.setText("")
            
            _LOGGER.debug(f"Set Twemoji icon for '{emoji}' on button")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to set icon on button for emoji '{emoji}': {e}")
            return False
    
    def convert_all_buttons(self, widget: QtWidgets.QWidget) -> int:
        """
        Convert all buttons in a widget hierarchy to use Twemoji icons.
        
        Args:
            widget: Root widget to search for buttons
            
        Returns:
            Number of buttons converted
        """
        converted = 0
        
        # Find all QPushButton widgets recursively
        buttons = widget.findChildren(QtWidgets.QPushButton)
        
        for button in buttons:
            text = button.text()
            if not text:
                continue

            # Skip specific navigation buttons and pure triangle/arrow-only labels
            try:
                object_name = button.objectName() if hasattr(button, 'objectName') else ""
            except Exception:
                object_name = ""
            if object_name in {"unified_prev_btn", "unified_next_btn"}:
                _LOGGER.debug(f"Skipping Twemoji conversion for navigation button: {object_name}")
                continue
            if text in {"◀", "▶", "◀◀", "▶▶"}:
                _LOGGER.debug("Skipping Twemoji conversion for pure arrow/triangle label button")
                continue

            handled = False
            # First, try known/packaged emojis for best icon fidelity
            for emoji in self.EMOJI_MAPPING.keys():
                if text.startswith(emoji):
                    if self.set_button_icon(button, emoji, keep_text=True):
                        converted += 1
                    handled = True
                    break

            # If not handled by known mapping, attempt a generic leading-emoji parse
            if not handled:
                stripped, generic_emoji = self._strip_leading_emoji(text)
                if generic_emoji:
                    if self.set_button_icon(button, generic_emoji, keep_text=True):
                        converted += 1
        
        _LOGGER.info(f"Converted {converted} buttons to use Twemoji icons")
        return converted

    def _strip_leading_emoji(self, text: str) -> Tuple[str, Optional[str]]:
        """If text begins with a known emoji, return (stripped_text, emoji) else (text, None)."""
        if not text:
            return text, None
        # Check against known mapping; also allow any emoji by first char
        for emoji in self.EMOJI_MAPPING.keys():
            if text.startswith(emoji):
                return text[len(emoji):].lstrip(), emoji
        # Fallback heuristic: if first char is outside BMP or in emoji range
        first = text[0]
        try:
            if ord(first) >= 0x2190:  # rough lower bound where arrows/symbols begin
                return text[1:].lstrip(), first
        except Exception:
            pass
        return text, None

    def preload_common_icons(self) -> int:
        """
        Preload all common SNID SAGE emoji icons for better performance.
        
        Returns:
            Number of icons successfully preloaded
        """
        # Avoid doing GUI work off the main thread. This preload method
        # only ensures the SVG files are resolvable (packaged or cached), but does
        # not create QIcon objects. Actual QIcon creation happens on demand in the
        # UI thread via get_icon().
        loaded = 0
        for emoji in self.EMOJI_MAPPING.keys():
            svg_path = self.get_svg_path_for_emoji(emoji)
            if svg_path is not None and svg_path.exists():
                loaded += 1
        _LOGGER.info(f"Preloaded Twemoji assets (paths resolved): {loaded}/{len(self.EMOJI_MAPPING)}")
        return loaded
    
    def clear_cache(self) -> None:
        """Clear the in-memory icon cache."""
        self.cache.clear()
        _LOGGER.info("Cleared Twemoji icon cache")
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if Twemoji manager can be used (PySide6 available)."""
        return PYSIDE6_AVAILABLE


# Global instance for convenience
_TWEMOJI_MANAGER: Optional[TwemojiManager] = None

def get_twemoji_manager(icon_size: int = 16) -> Optional[TwemojiManager]:
    """
    Get the global TwemojiManager instance.
    
    Args:
        icon_size: Size for icons (only used on first call)
        
    Returns:
        TwemojiManager instance or None if PySide6 unavailable
    """
    global _TWEMOJI_MANAGER
    
    if not TwemojiManager.is_available():
        return None
    
    if _TWEMOJI_MANAGER is None:
        _TWEMOJI_MANAGER = TwemojiManager(icon_size=icon_size)
    
    return _TWEMOJI_MANAGER

def _icon_to_pixmap(icon: 'QtGui.QIcon', size: int) -> Optional['QtGui.QPixmap']:
    try:
        return icon.pixmap(size, size)
    except Exception:
        return None

def _get_icon_for_emoji(emoji: str, icon_size: int) -> Optional['QtGui.QIcon']:
    manager = get_twemoji_manager(icon_size=icon_size)
    if not manager:
        return None
    return manager.get_icon(emoji)

def _get_pixmap_for_emoji(emoji: str, size: int) -> Optional['QtGui.QPixmap']:
    icon = _get_icon_for_emoji(emoji, icon_size=size)
    if icon is None:
        return None
    return _icon_to_pixmap(icon, size)

# Backward/compat convenience for other modules expecting a pixmap-like object
# Returns a QIcon, which is what Qt's setTabIcon expects.
def get_emoji_pixmap(emoji: str, size: int = 16) -> Optional['QtGui.QIcon']:
    """
    Return a QIcon representing the provided emoji using packaged Twemoji assets
    when available. The returned object can be used directly with Qt APIs that
    expect a QIcon (e.g., QTabWidget.setTabIcon).
    """
    return _get_icon_for_emoji(emoji, icon_size=size)

def convert_button_to_twemoji(button: QtWidgets.QPushButton, emoji: str) -> bool:
    """
    Convenience function to convert a single button to use Twemoji.
    
    Args:
        button: The button to convert
        emoji: The emoji character
        
    Returns:
        True if conversion was successful
    """
    manager = get_twemoji_manager()
    if manager:
        return manager.set_button_icon(button, emoji)
    return False 