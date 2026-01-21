"""
SNID SAGE - Games Selection Dialog - PySide6 Version
===================================================

Games selection dialog for the PySide6 GUI that provides access to
Qt-based mini-games while SNID analysis runs in the background.

Features:
- Space Debris Cleanup game integration
- Modern PySide6 styling matching the main GUI
- Proper error handling for games availability
- Non-blocking Qt-native game launch

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
from typing import Optional

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_games_dialog')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_games_dialog')

# Enhanced dialog button styling
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except Exception:
    ENHANCED_BUTTONS_AVAILABLE = False

class PySide6GamesDialog(QtWidgets.QDialog):
    """
    Games selection dialog for PySide6 GUI.
    
    Provides access to the Qt-based mini-game that can run while SNID
    analysis is in progress.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the games dialog.
        
        Args:
            parent: Parent window
        """
        super().__init__(parent)
        self.selected_game = None
        
        self._setup_dialog()
        self._create_interface()
        self._check_games_availability()
    
    def _setup_dialog(self):
        """Setup dialog properties"""
        self.setWindowTitle("Play Games While Analyzing")
        self.setModal(True)
        self.setFixedSize(480, 520)
        
        # Center dialog on parent
        if self.parent():
            parent_geometry = self.parent().geometry()
            x = parent_geometry.x() + (parent_geometry.width() - 480) // 2
            y = parent_geometry.y() + (parent_geometry.height() - 520) // 2
            self.move(x, y)
    
    def _create_interface(self):
        """Create the dialog interface"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        self._create_header(layout)
        
        # Game selection area
        self._create_game_selection(layout)
        
        # Buttons
        self._create_buttons(layout)
        
        # Apply styling
        self._apply_styling()
    
    def _create_header(self, layout):
        """Create dialog header"""
        # Title
        title_label = QtWidgets.QLabel("Entertainment Center")
        title_label.setObjectName("games_title")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QtWidgets.QLabel("Play while SNID analysis runs in the background")
        subtitle_label.setObjectName("games_subtitle")
        subtitle_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(subtitle_label)
        
        # Spacer
        layout.addSpacing(8)
    
    def _create_game_selection(self, layout):
        """Create game selection area"""
        # Create frame for game selection
        game_frame = QtWidgets.QFrame()
        game_frame.setObjectName("games_frame")
        game_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        
        game_layout = QtWidgets.QVBoxLayout(game_frame)
        game_layout.setSpacing(16)
        game_layout.setContentsMargins(20, 20, 20, 20)
        
        # Game title
        game_title = QtWidgets.QLabel("Space Debris Cleanup")
        game_title.setObjectName("game_title")
        game_title.setAlignment(QtCore.Qt.AlignCenter)
        game_layout.addWidget(game_title)
        
        # Game description
        description_text = (
            "Advanced space simulation with realistic spacecraft and satellite debris!\n\n"
            "Pilot a detailed spacecraft with wings and thrusters\n"
            "Clean up 4 types of realistic satellite debris\n"
            "⚡ Energy bullets with particle trail effects\n"
            "Deep space background with twinkling stars\n"
            "Earth visible in the background\n"
            "Satellites with solar panels and antennas\n"
            "Full-screen gameplay in 1024x768 window"
        )
        
        description_label = QtWidgets.QLabel(description_text)
        description_label.setObjectName("game_description")
        description_label.setWordWrap(True)
        description_label.setAlignment(QtCore.Qt.AlignLeft)
        game_layout.addWidget(description_label)
        
        # Controls info
        controls_text = "Controls: Arrow keys to move • SPACE to fire • ESC to exit"
        controls_label = QtWidgets.QLabel(controls_text)
        controls_label.setObjectName("game_controls")
        controls_label.setAlignment(QtCore.Qt.AlignCenter)
        game_layout.addWidget(controls_label)
        
        # Enhanced features
        features_text = (
            "✨ Enhanced Features:\n"
            "• Boss battles after clearing waves\n"
            "• Chain reaction explosions\n"
            "• Shield and Multishot power-ups\n"
            "• Realistic physics and particle effects"
        )
        
        features_label = QtWidgets.QLabel(features_text)
        features_label.setObjectName("game_features")
        features_label.setWordWrap(True)
        features_label.setAlignment(QtCore.Qt.AlignLeft)
        game_layout.addWidget(features_label)
        
        # Game availability status
        self.availability_label = QtWidgets.QLabel()
        self.availability_label.setObjectName("game_availability")
        self.availability_label.setAlignment(QtCore.Qt.AlignCenter)
        game_layout.addWidget(self.availability_label)
        
        layout.addWidget(game_frame, 1)
    
    def _create_buttons(self, layout):
        """Create dialog buttons"""
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Play game button
        self.play_button = QtWidgets.QPushButton("Start Space Debris Cleanup")
        self.play_button.setObjectName("play_button")
        self.play_button.clicked.connect(self._start_game)
        button_layout.addWidget(self.play_button)
        
        # Cancel button
        cancel_button = QtWidgets.QPushButton("No Thanks")
        cancel_button.setObjectName("cancel_button")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)

        # Apply enhanced styles
        try:
            if ENHANCED_BUTTONS_AVAILABLE:
                self.button_manager = enhance_dialog_with_preset(self, 'games_dialog')
        except Exception as e:
            _LOGGER.warning(f"Failed to apply enhanced button styling: {e}")
    
    def _check_games_availability(self):
        """Update UI without importing optional modules in this process."""
        # Games are Qt-native; if the games module imports, we're good.
        self.availability_label.setText("Ready to play!")
        self.availability_label.setStyleSheet("color: #059669; font-weight: bold;")
        self.play_button.setEnabled(True)
    
    def _start_game(self):
        """Start the selected game"""
        try:
            # Close dialog first
            self.accept()
            from snid_sage.snid.games import run_debris_game
            run_debris_game()
            _LOGGER.info("Space Debris Cleanup game started from PySide6 dialog")
        except Exception as e:
            _LOGGER.error(f"Error starting game from dialog: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Game Error",
                f"Failed to start game: {str(e)}"
            )
    
    def _apply_styling(self):
        """Apply dialog styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                border-radius: 8px;
            }
            
            QLabel#games_title {
                font-size: 20pt;
                font-weight: bold;
                color: #1e293b;
                margin-bottom: 8px;
            }
            
            QLabel#games_subtitle {
                font-size: 12pt;
                color: #64748b;
                margin-bottom: 16px;
            }
            
            QFrame#games_frame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
            
            QLabel#game_title {
                font-size: 16pt;
                font-weight: bold;
                color: #059669;
                margin-bottom: 12px;
            }
            
            QLabel#game_description {
                font-size: 11pt;
                color: #374151;
                line-height: 1.4;
            }
            
            QLabel#game_controls {
                font-size: 10pt;
                color: #6b7280;
                font-style: italic;
                margin: 8px 0;
            }
            
            QLabel#game_features {
                font-size: 10pt;
                color: #3b82f6;
                line-height: 1.3;
            }
            
            QLabel#game_availability {
                font-size: 11pt;
                margin-top: 12px;
            }
            
            QPushButton#play_button {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 12pt;
                font-weight: bold;
                min-height: 20px;
            }
            
            QPushButton#play_button:hover {
                background-color: #047857;
            }
            
            QPushButton#play_button:pressed {
                background-color: #065f46;
            }
            
            QPushButton#play_button:disabled {
                background-color: #9ca3af;
                color: #f3f4f6;
            }
            
            QPushButton#cancel_button {
                background-color: #6b7280;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 12pt;
                font-weight: bold;
                min-height: 20px;
            }
            
            QPushButton#cancel_button:hover {
                background-color: #4b5563;
            }
            
            QPushButton#cancel_button:pressed {
                background-color: #374151;
            }
        """) 