"""
SNID SAGE - Analysis Progress Dialog - PySide6 Version
====================================================

Comprehensive progress dialog for SNID analysis with live step updates.
Provides live progress updates during analysis.
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
from typing import Optional, Callable
import time

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_analysis_progress')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_analysis_progress')

# Enhanced button management
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except ImportError:
    _LOGGER.debug("Enhanced button system not available")
    ENHANCED_BUTTONS_AVAILABLE = False


class AnalysisProgressDialog(QtWidgets.QDialog):
    """
    Comprehensive analysis progress dialog with live updates.
    
    Features:
    - Live step-by-step progress text
    - Progress bar with percentage
    - Analysis stage indicators
    - Cancel functionality
    - Auto-scrolling text area
    - Modern styling consistent with the application
    """
    
    # Signals
    cancel_requested = QtCore.Signal()
    hide_requested = QtCore.Signal()
    
    def __init__(self, parent, title="SNID-SAGE Analysis Progress"):
        """
        Initialize analysis progress dialog.
        
        Args:
            parent: Parent window
            title: Dialog title
        """
        super().__init__(parent)
        self.title = title
        self.cancelled = False
        self.hidden = False
        self.progress_text_lines = []
        
        self._setup_dialog()
        self._create_interface()
        self._setup_initial_state()
        self._setup_enhanced_buttons()
        
    def _setup_dialog(self):
        """Setup dialog properties"""
        self.setWindowTitle(self.title)
        self.resize(800, 600)
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        # Don't allow closing via X button
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint)
        
        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
                color: #1e293b;
                font-family: Arial, "Helvetica Neue", Helvetica, "Segoe UI", sans-serif;
            }
            
            QLabel {
                color: #1e293b;
                font-size: 11pt;
                background: transparent;
            }
            
            QLabel#title_label {
                font-size: 16pt;
                font-weight: bold;
                color: #3b82f6;
            }
            
            QLabel#stage_label {
                font-size: 12pt;
                font-weight: bold;
                color: #059669;
                padding: 8px;
                background: #dcfce7;
                border: 2px solid #16a34a;
                border-radius: 6px;
            }
            
            QProgressBar {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                text-align: center;
                font-size: 11pt;
                font-weight: bold;
                background: #ffffff;
                min-height: 25px;
            }
            
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:0.5 #1d4ed8, stop:1 #1e40af);
                border-radius: 6px;
                margin: 2px;
            }
            
            QTextEdit {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                background: #ffffff;
                font-family: "Consolas", "Monaco", monospace;
                font-size: 10pt;
                line-height: 1.4;
                selection-background-color: #3b82f6;
            }
            
            QPushButton {
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 11pt;
                background: #ffffff;
                min-width: 100px;
                min-height: 35px;
            }
            
            QPushButton:hover {
                background: #f1f5f9;
            }
            
            QPushButton:pressed {
                background: #e2e8f0;
            }
            
            QPushButton#cancel_btn {
                background: #fef2f2;
                border: 2px solid #ef4444;
                color: #dc2626;
            }
            
            QPushButton#cancel_btn:hover {
                background: #fee2e2;
            }
            
            QPushButton#hide_btn {
                background: #f0f9ff;
                border: 2px solid #3b82f6;
                color: #1d4ed8;
            }
            
            QPushButton#hide_btn:hover {
                background: #dbeafe;
            }
            
            QPushButton#games_btn {
                background: #f0fdf4;
                border: 2px solid #16a34a;
                color: #15803d;
            }
            
            QPushButton#games_btn:hover {
                background: #dcfce7;
            }
            
            QPushButton#games_btn:disabled {
                background: #f3f4f6;
                border: 2px solid #d1d5db;
                color: #9ca3af;
            }
        """)
    
    def _create_interface(self):
        """Create the dialog interface"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header section
        header_layout = QtWidgets.QVBoxLayout()
        
        # Title
        self.title_label = QtWidgets.QLabel("SNID-SAGE Analysis in Progress")
        self.title_label.setObjectName("title_label")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        header_layout.addWidget(self.title_label)
        
        # Current stage indicator (hidden - redundant with progress bar text)
        self.stage_label = QtWidgets.QLabel("Initializing analysis...")
        self.stage_label.setObjectName("stage_label")
        self.stage_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stage_label.setVisible(False)  # Hide the redundant stage header
        header_layout.addWidget(self.stage_label)
        
        layout.addLayout(header_layout)
        
        # Progress bar with percentage
        progress_layout = QtWidgets.QHBoxLayout()
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Progress text area
        text_layout = QtWidgets.QVBoxLayout()
        
        progress_text_label = QtWidgets.QLabel("Analysis Progress:")
        progress_text_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        text_layout.addWidget(progress_text_label)
        
        self.progress_text = QtWidgets.QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMinimumHeight(300)
        text_layout.addWidget(self.progress_text)
        
        layout.addLayout(text_layout)
        
        # Button controls
        button_layout = QtWidgets.QHBoxLayout()
        
        # Games button on the left
        self.games_btn = QtWidgets.QPushButton("Play Space Debris Game")
        self.games_btn.setObjectName("games_btn")
        self.games_btn.clicked.connect(self._start_space_debris_game)
        self.games_btn.setToolTip("Play Space Debris Cleanup while SNID analysis runs")
        self._check_games_availability()
        button_layout.addWidget(self.games_btn)
        
        button_layout.addStretch()
        
        # Hide button
        self.hide_btn = QtWidgets.QPushButton("Hide Window")
        self.hide_btn.setObjectName("hide_btn")
        self.hide_btn.clicked.connect(self._on_hide)
        self.hide_btn.setToolTip("Hide this window but continue analysis in background")
        button_layout.addWidget(self.hide_btn)
        
        button_layout.addSpacing(10)
        
        # Cancel button
        self.cancel_btn = QtWidgets.QPushButton("Cancel Analysis")
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setToolTip("Stop the analysis and return to main interface")
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # No elapsed timer
    
    def _setup_initial_state(self):
        """Setup initial state"""
        self.set_stage("Initialization", 0)
    
    def _setup_enhanced_buttons(self):
        """Setup enhanced button styling and animations"""
        if not ENHANCED_BUTTONS_AVAILABLE:
            _LOGGER.info("Enhanced buttons not available, using standard styling")
            return
        
        try:
            # Use the analysis progress dialog preset
            self.button_manager = enhance_dialog_with_preset(
                self, 'analysis_progress_dialog'
            )
            
            _LOGGER.info("Enhanced buttons successfully applied to analysis progress dialog")
            
        except Exception as e:
            _LOGGER.error(f"Failed to setup enhanced buttons: {e}")
    
    def set_stage(self, stage_name: str, progress_percent: int):
        """
        Set the current analysis stage.
        
        Args:
            stage_name: Name of the current stage
            progress_percent: Progress percentage (0-100)
        """
        try:
            self.stage_label.setText(f"📋 {stage_name}")
            self.progress_bar.setValue(progress_percent)
            # Update progress bar format to show stage name with percentage
            self.progress_bar.setFormat(f"{stage_name} - %p%")
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            _LOGGER.warning(f"Error setting stage: {e}")
    
    def add_progress_line(self, message: str, level: str = "info"):
        """
        Add a progress line to the text area.
        
        Args:
            message: Progress message
            level: Message level (info, success, warning, error)
        """
        try:
            # Filter out empty messages and unwanted intermediate messages
            if not message.strip():
                return
                
            # Filter out specific intermediate messages we don't want to show
            unwanted_messages = [
            ]
            
            # Skip messages that contain unwanted text patterns
            if any(unwanted in message for unwanted in unwanted_messages):
                return
            
            # Skip messages about individual template processing during batches
            if "Template " in message and "/" in message and ("processed" in message or "method" in message or "OPTIMIZED" in message):
                return
                
            timestamp = time.strftime("%H:%M:%S")
            
            # Format message with color based on level
            if level == "success":
                formatted_line = f'<span style="color: #059669; font-weight: bold;">[{timestamp}] {message}</span>'
            elif level == "warning":
                formatted_line = f'<span style="color: #d97706; font-weight: bold;">[{timestamp}] {message}</span>'
            elif level == "error":
                formatted_line = f'<span style="color: #dc2626; font-weight: bold;">[{timestamp}] {message}</span>'
            else:  # info
                formatted_line = f'<span style="color: #475569;">[{timestamp}] {message}</span>'
            
            # Add to text area
            cursor = self.progress_text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            cursor.insertHtml(formatted_line + "<br>")
            
            # Auto-scroll to bottom
            scrollbar = self.progress_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # Store line for logging
            self.progress_text_lines.append(f"[{timestamp}] {message}")
            
            QtWidgets.QApplication.processEvents()
            
        except Exception as e:
            _LOGGER.warning(f"Error adding progress line: {e}")
    
    def set_progress(self, current: int, maximum: int, message: str = ""):
        """
        Set determinate progress.
        
        Args:
            current: Current step
            maximum: Maximum steps
            message: Optional progress message
        """
        try:
            if maximum > 0:
                progress_percent = int((current / maximum) * 100)
                self.progress_bar.setRange(0, maximum)
                self.progress_bar.setValue(current)
                self.progress_bar.setFormat(f"{progress_percent}%")
                
                if message:
                    self.add_progress_line(message)
                    
            QtWidgets.QApplication.processEvents()
        except Exception as e:
            _LOGGER.warning(f"Error setting progress: {e}")
    
    
    
    def _on_hide(self):
        """Handle hide button click"""
        self.hidden = True
        self.hide_requested.emit()
        self.hide()
        self.add_progress_line("Window hidden - analysis continues in background", "info")
    
    def _on_cancel(self):
        """Handle cancel button click"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Cancel Analysis",
            "Are you sure you want to cancel the SNID analysis?\n\n"
            "This will stop the current analysis and return to the main interface.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.cancelled = True
            self.cancel_requested.emit()
            self.add_progress_line("Analysis cancellation requested by user", "warning")
            self.cancel_btn.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
            self.set_stage("Cancelling Analysis", self.progress_bar.value())
    
    def analysis_completed(self, success: bool, message: str = ""):
        """
        Mark analysis as completed.
        
        Args:
            success: Whether analysis was successful
            message: Completion message
        """
        try:
            if success:
                self.set_stage("Analysis Complete", 100)
                # Prefer the provided message; fallback to a neutral completion message
                if message:
                    self.add_progress_line(message, "success")
                else:
                    self.add_progress_line("Analysis completed.", "success")
                
                # Change title and button
                self.title_label.setText("SNID Analysis Complete")
                self.cancel_btn.setText("Close")
                self.cancel_btn.setObjectName("hide_btn")  # Change styling
                self.cancel_btn.clicked.disconnect()
                self.cancel_btn.clicked.connect(self.accept)
                self.hide_btn.setText("View Results")
                
            else:
                # Treat specific cases (no matches / inconclusive) as a non-error outcome
                normalized_msg = (message or "").lower()
                is_inconclusive = any(k in normalized_msg for k in [
                    "inconclusive",
                    "no good matches",
                    "no template matches",
                    "no reliable cluster",
                    "no matches found"
                ])

                if is_inconclusive:
                    self.set_stage("Analysis Inconclusive", self.progress_bar.value())
                    # Provide a clear, user-friendly line without an error tone
                    display_msg = message or "No good matches found"
                    self.add_progress_line(display_msg, "warning")
                    
                    # Update dialog visuals to reflect an inconclusive (not error) state
                    self.title_label.setText("SNID Analysis Inconclusive")
                    self.cancel_btn.setText("Close")
                    self.cancel_btn.clicked.disconnect()
                    self.cancel_btn.clicked.connect(self.reject)
                else:
                    self.set_stage("Analysis Failed", self.progress_bar.value())
                    self.add_progress_line("SNID analysis failed", "error")
                    if message:
                        self.add_progress_line(f"Error: {message}", "error")
                    
                    # Change title and button
                    self.title_label.setText("SNID Analysis Failed")
                    self.cancel_btn.setText("Close")
                    self.cancel_btn.clicked.disconnect()
                    self.cancel_btn.clicked.connect(self.reject)
                
            # Re-apply styles after changing object names
            self.setStyleSheet(self.styleSheet())
            
        except Exception as e:
            _LOGGER.error(f"Error handling analysis completion: {e}")
    
    def is_cancelled(self) -> bool:
        """Check if analysis was cancelled"""
        return self.cancelled
    
    def is_hidden(self) -> bool:
        """Check if dialog is hidden"""
        return self.hidden
    
    def show_dialog(self):
        """Show the dialog (unhide if hidden)"""
        self.hidden = False
        self.show()
        self.raise_()
        self.activateWindow()
    
    def _check_games_availability(self):
        """Check if games are available and update games button accordingly"""
        try:
            from snid_sage.snid.games import GAMES_AVAILABLE
            
            if GAMES_AVAILABLE:
                self.games_btn.setEnabled(True)
                self.games_btn.setToolTip("Play Space Debris Cleanup while SNID analysis runs")
            else:
                self.games_btn.setEnabled(False)
                self.games_btn.setText("Games Not Available")
                self.games_btn.setToolTip("Games are not available in this build.")
                
        except ImportError:
            self.games_btn.setEnabled(False)
            self.games_btn.setText("Games Not Available")
            self.games_btn.setToolTip("Games module not available")
    
    def _start_space_debris_game(self):
        """Start the Space Debris Cleanup game (Qt-native)."""
        try:
            from snid_sage.snid.games import run_debris_game
            # Keep the game window usable during analysis: ensure it comes to the front
            # relative to this progress dialog, and auto-size for the current screen.
            run_debris_game(parent_window=self, force_on_top=True)
            self.add_progress_line("🎮 Space Debris Cleanup game started!", "info")
            _LOGGER.info("Space Debris Cleanup game started from analysis progress dialog")
        except Exception as e:
            _LOGGER.error(f"Error starting Space Debris game: {e}")
            self.add_progress_line(f"Failed to start game: {str(e)}", "error")


class AnalysisProgressManager(QtCore.QObject):
    """
    Manager for analysis progress that can be used as a callback system.
    """
    
    def __init__(self, dialog: AnalysisProgressDialog):
        super().__init__()
        self.dialog = dialog
        self.current_step = 0
        self.total_steps = 10  # Default estimate
        
    def set_total_steps(self, total: int):
        """Set total number of steps"""
        self.total_steps = total
        
    def update_progress(self, message: str, step: int = None):
        """
        Update progress with a message.
        
        Args:
            message: Progress message
            step: Optional step number
        """
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1
            
        self.dialog.set_progress(self.current_step, self.total_steps, message)
        
    def set_stage(self, stage_name: str):
        """Set current stage"""
        progress_percent = int((self.current_step / self.total_steps) * 100) if self.total_steps > 0 else 0
        self.dialog.set_stage(stage_name, progress_percent)
        
    def add_message(self, message: str, level: str = "info"):
        """Add a message to the progress log"""
        self.dialog.add_progress_line(message, level)


def show_analysis_progress_dialog(parent, title="SNID-SAGE Analysis Progress") -> AnalysisProgressDialog:
    """
    Show analysis progress dialog and return the dialog instance.
    
    Args:
        parent: Parent window
        title: Dialog title
        
    Returns:
        Progress dialog instance
    """
    dialog = AnalysisProgressDialog(parent, title)
    dialog.show()
    return dialog 