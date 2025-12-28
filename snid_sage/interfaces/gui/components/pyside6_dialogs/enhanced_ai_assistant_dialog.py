"""
Enhanced AI Assistant Dialog - PySide6 Version

This module provides a modern AI assistant interface with:
- Single comprehensive summary generation
- Chat interface in separate tab
- Simplified settings
- User metadata input form
- Enhanced SNID context awareness
- Modern Qt design
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
import threading
from datetime import datetime
import json
import os
from typing import Dict, Any, Optional, List

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_ai_assistant')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_ai_assistant')

# Enhanced dialog button styling
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except Exception:
    ENHANCED_BUTTONS_AVAILABLE = False


class _ChatInput(QtWidgets.QTextEdit):
    """Text edit that captures Cmd/Ctrl+Enter to send chat messages.

    This prevents application-wide shortcuts (e.g., quick workflow) from
    intercepting the key combo while the user is typing in the chat box.
    """

    def __init__(self, send_callback, parent=None):
        super().__init__(parent)
        self._send_callback = send_callback
        # Strong focus to ensure we receive key events while typing
        try:
            self.setFocusPolicy(QtCore.Qt.StrongFocus)
        except Exception:
            pass

    def event(self, event: QtCore.QEvent) -> bool:
        """Intercept shortcut override so app-wide shortcuts don't fire."""
        try:
            if event.type() == QtCore.QEvent.ShortcutOverride:
                key_event = event  # type: ignore[assignment]
                if isinstance(key_event, QtGui.QKeyEvent):
                    modifiers = key_event.modifiers()
                    is_ctrl_or_cmd = bool(modifiers & QtCore.Qt.ControlModifier) or bool(modifiers & QtCore.Qt.MetaModifier)
                    if is_ctrl_or_cmd and key_event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                        event.accept()
                        return True
        except Exception:
            pass
        return super().event(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        try:
            modifiers = event.modifiers()
            is_ctrl_or_cmd = bool(modifiers & QtCore.Qt.ControlModifier) or bool(modifiers & QtCore.Qt.MetaModifier)
            if is_ctrl_or_cmd and event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                # Trigger send and consume the event so global shortcuts do not fire
                self._send_callback()
                event.accept()
                return
        except Exception:
            # Fall through to default handling on any error
            pass
        super().keyPressEvent(event)


class PySide6EnhancedAIAssistantDialog(QtWidgets.QDialog):
    """
    Enhanced AI Assistant Dialog with simplified interface.
    
    Features:
    - Single comprehensive summary generation
    - Chat interface in separate tab
    - Settings menu
    - User metadata input
    - Enhanced SNID context
    """
    
    def __init__(self, parent, snid_results=None):
        """Initialize the enhanced AI assistant dialog."""
        super().__init__(parent)
        self.parent_gui = parent
        self.is_generating = False
        self.current_snid_results = snid_results
        self.conversation: List[Dict[str, str]] = []
        
        # Theme colors (matching PySide6 main GUI)
        self.colors = {
            'bg_primary': '#f8fafc',
            'bg_secondary': '#ffffff',
            'bg_tertiary': '#f1f5f9',
            'text_primary': '#1e293b',
            'text_secondary': '#475569',
            'text_muted': '#94a3b8',
            'border': '#cbd5e1',
            'btn_primary': '#3b82f6',
            'btn_success': '#10b981',
            'btn_danger': '#ef4444',
            'btn_warning': '#f59e0b',
            'accent_primary': '#3b82f6',
        }
        
        self._setup_dialog()
        self._create_interface()
        
    def _setup_dialog(self):
        """Setup dialog window properties"""
        self.setWindowTitle("AI Assistant")
        # Allow full-screen and maximizing; no artificial max size
        self.setSizeGripEnabled(True)
        self.setMinimumSize(700, 500)
        self.resize(1000, 650)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMaximizeButtonHint)
        
        # Apply dialog styling (do not override checkbox/radio indicators)
        # Use platform-aware font stack for macOS
        self.setStyleSheet(f"""
            QDialog {{
                background: {self.colors['bg_primary']};
                color: {self.colors['text_primary']};
                font-family: Arial, "Helvetica Neue", Helvetica, "Segoe UI", sans-serif;
                font-size: 10pt;
            }}
            
            QTabWidget::pane {{
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                background: {self.colors['bg_secondary']};
            }}
            
            QTabWidget::tab-bar {{
                alignment: left;
            }}
            
            QTabBar::tab {{
                background: {self.colors['bg_tertiary']};
                border: 2px solid {self.colors['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                min-width: 120px;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: bold;
            }}
            
            QTabBar::tab:selected {{
                background: {self.colors['bg_secondary']};
                border-color: {self.colors['border']};
                border-bottom: 2px solid {self.colors['bg_secondary']};
            }}
            
            QTabBar::tab:hover:!selected {{
                background: {self.colors['border']};
            }}
            
            QGroupBox {{
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background: {self.colors['bg_secondary']};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: {self.colors['text_primary']};
            }}
            
            QPushButton {{
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 24px;
                font-weight: bold;
                font-size: 10pt;
                background: {self.colors['bg_tertiary']};
            }}
            
            QPushButton:hover {{
                background: {self.colors['border']};
            }}
            
            QPushButton#primary_btn {{
                background: {self.colors['btn_primary']};
                color: white;
                border: 2px solid {self.colors['btn_primary']};
            }}
            
            QPushButton#primary_btn:hover {{
                background: #2563eb;
                border: 2px solid #2563eb;
            }}
            
            QPushButton#success_btn {{
                background: {self.colors['btn_success']};
                color: white;
                border: 2px solid {self.colors['btn_success']};
            }}
            
            QPushButton#success_btn:hover {{
                background: #059669;
                border: 2px solid #059669;
            }}
            
            QPushButton#danger_btn {{
                background: {self.colors['btn_danger']};
                color: white;
                border: 2px solid {self.colors['btn_danger']};
            }}
            
            QPushButton#danger_btn:hover {{
                background: #dc2626;
                border: 2px solid #dc2626;
            }}
            
            QPushButton:disabled {{
                background: {self.colors['bg_tertiary']};
                color: {self.colors['text_muted']};
                border: 2px solid {self.colors['border']};
            }}
            
            QTextEdit {{
                background: {self.colors['bg_secondary']};
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                padding: 8px;
                font-family: "Consolas", monospace;
                font-size: 10pt;
                selection-background-color: {self.colors['btn_primary']};
            }}
            
            QLineEdit {{
                background: {self.colors['bg_secondary']};
                border: 2px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                font-size: 10pt;
            }}
            
            QLineEdit:focus {{
                border: 2px solid {self.colors['btn_primary']};
            }}
            
            QComboBox {{
                background: {self.colors['bg_secondary']};
                border: 2px solid {self.colors['border']};
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 10pt;
                min-width: 100px;
            }}
            
            QComboBox:hover {{
                border: 2px solid {self.colors['btn_primary']};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border: 1px solid {self.colors['border']};
                width: 8px;
                height: 8px;
                background: {self.colors['text_secondary']};
            }}
            
            /* Checkbox/radio indicators inherit from global theme manager */
            
            QProgressBar {{
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
                background: {self.colors['bg_tertiary']};
            }}
            
            QProgressBar::chunk {{
                background: {self.colors['btn_primary']};
                border-radius: 4px;
            }}
            
            QLabel {{
                background: transparent;
                color: {self.colors['text_primary']};
            }}
        """)
    
    def _create_interface(self):
        """Create the main interface"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header (left-side model label only)
        self._create_header(layout)

        # Tab widget for different functionality
        self.tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(self.tab_widget)

        # Status label in the tab bar corner (top-right, same height as tabs)
        corner_container = QtWidgets.QWidget()
        corner_layout = QtWidgets.QHBoxLayout(corner_container)
        corner_layout.setContentsMargins(0, 0, 6, 0)
        corner_layout.setSpacing(6)
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {self.colors['btn_success']}; font-weight: bold; font-size: 10pt;")
        corner_layout.addWidget(self.status_label)
        # Also show current model on the top-right
        self.corner_model_label = QtWidgets.QLabel("")
        self.corner_model_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-style: italic; font-size: 10pt;")
        corner_layout.addWidget(self.corner_model_label)
        self.tab_widget.setCornerWidget(corner_container, QtCore.Qt.TopRightCorner)
        # Initialize corner model label
        self._refresh_model_label()
        
        # Create tabs
        self._create_summary_tab()
        self._create_chat_tab()
        self._create_settings_tab()
        
        # Footer buttons
        self._create_footer_buttons(layout)

        # Apply enhanced dialog button styling preset
        try:
            if ENHANCED_BUTTONS_AVAILABLE:
                self.button_manager = enhance_dialog_with_preset(self, 'enhanced_ai_assistant_dialog')
        except Exception as e:
            _LOGGER.warning(f"Failed to apply enhanced button styling: {e}")
        
    def _create_header(self, layout):
        """Create header section with status indicator"""
        header_layout = QtWidgets.QHBoxLayout()
        
        # Left: show active model
        header_left = QtWidgets.QHBoxLayout()
        self.model_label = QtWidgets.QLabel("")
        self.model_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-style: italic;")
        header_left.addWidget(self.model_label)
        header_left_widget = QtWidgets.QWidget()
        header_left_widget.setLayout(header_left)
        # Hide model label on the top-left per request
        header_left_widget.setVisible(False)
        header_layout.addWidget(header_left_widget)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        self._refresh_model_label()
    
    def _create_summary_tab(self):
        """Create summary generation tab"""
        summary_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(summary_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Simple status indicator
        if self.current_snid_results:
            results_text = "SNID results ready for AI analysis"
            results_color = self.colors['btn_success']
        else:
            results_text = "⚠️ Run SNID analysis first for best results"
            results_color = self.colors['btn_warning']
        
        results_label = QtWidgets.QLabel(results_text)
        results_label.setStyleSheet(f"color: {results_color}; font-weight: bold; padding: 8px; margin-bottom: 8px;")
        layout.addWidget(results_label)
        
        # Compact metadata input
        metadata_layout = QtWidgets.QHBoxLayout()
        
        self.observer_name_input = QtWidgets.QLineEdit()
        self.observer_name_input.setPlaceholderText("Reporting group/name (optional)")
        metadata_layout.addWidget(self.observer_name_input)
        
        self.telescope_input = QtWidgets.QLineEdit()
        self.telescope_input.setPlaceholderText("Telescope (optional)")
        metadata_layout.addWidget(self.telescope_input)
        
        self.observation_date_input = QtWidgets.QLineEdit()
        self.observation_date_input.setPlaceholderText("Date (optional)")
        metadata_layout.addWidget(self.observation_date_input)
        
        layout.addLayout(metadata_layout)
        
        # Specific request input
        self.specific_request_input = QtWidgets.QTextEdit()
        self.specific_request_input.setPlaceholderText("Enter any specific requests or questions about the analysis (optional)")
        self.specific_request_input.setMaximumHeight(80)
        layout.addWidget(self.specific_request_input)

        # (Prompt preview UI removed per request)
        
        # Generate summary controls - simplified
        generate_layout = QtWidgets.QHBoxLayout()
        
        self.generate_summary_btn = QtWidgets.QPushButton("Generate Summary")
        self.generate_summary_btn.setObjectName("generate_summary_btn")
        self.generate_summary_btn.clicked.connect(self._generate_summary)
        self.generate_summary_btn.setMinimumHeight(40)
        generate_layout.addWidget(self.generate_summary_btn)
        
        self.summary_progress = QtWidgets.QProgressBar()
        self.summary_progress.setVisible(False)
        self.summary_progress.setMaximumHeight(30)
        generate_layout.addWidget(self.summary_progress)
        
        layout.addLayout(generate_layout)
        
        # Summary output - no group box
        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setPlaceholderText(
            "Your AI-generated analysis will appear here...\n\n"
            "Click 'Generate Summary' to start."
        )
        self.summary_text.setMinimumHeight(300)
        layout.addWidget(self.summary_text)
        
        # Summary controls
        summary_controls_layout = QtWidgets.QHBoxLayout()
        
        self.export_summary_btn = QtWidgets.QPushButton("Export Summary")
        self.export_summary_btn.setObjectName("export_summary_btn")
        self.export_summary_btn.clicked.connect(self._export_summary)
        self.export_summary_btn.setEnabled(False)
        summary_controls_layout.addWidget(self.export_summary_btn)
        
        self.copy_summary_btn = QtWidgets.QPushButton("Copy to Clipboard")
        self.copy_summary_btn.setObjectName("copy_summary_btn")
        self.copy_summary_btn.clicked.connect(self._copy_summary)
        self.copy_summary_btn.setEnabled(False)
        summary_controls_layout.addWidget(self.copy_summary_btn)
        
        summary_controls_layout.addStretch()
        layout.addLayout(summary_controls_layout)
        
        layout.addStretch()
        self.tab_widget.addTab(summary_widget, "📊 Summary")
        # (Prompt preview initialization removed)
    
    def _create_chat_tab(self):
        """Create interactive chat tab"""
        chat_widget = QtWidgets.QWidget()
        # Keep a reference for tab visibility checks
        self._chat_tab_widget = chat_widget
        layout = QtWidgets.QVBoxLayout(chat_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Chat history - no group box
        self.chat_history = QtWidgets.QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setMinimumHeight(350)
        self.chat_history.setPlainText(
            "AI Assistant: Hello! Ask me questions about your SNID-SAGE analysis.\n\n"
            "Examples:\n"
            "• What type of supernova is this?\n"
            "• How confident is this classification?\n"
            "• What's the estimated redshift?\n"
            "• Should I follow up with more observations?\n\n"
            "What would you like to know?"
        )
        # Initialize conversation history with assistant greeting
        self.conversation = [
            {"role": "assistant", "content": "Hello! Ask me questions about your SNID-SAGE analysis."}
        ]
        layout.addWidget(self.chat_history)
        
        # Input area - simplified, no group box
        self.chat_input = _ChatInput(self._send_chat_message)
        self.chat_input.setMaximumHeight(70)
        self.chat_input.setPlaceholderText("Type your question here...")
        layout.addWidget(self.chat_input)

        # Add keyboard shortcut: Ctrl/Cmd+Enter to send (platform-aware)
        try:
            from snid_sage.interfaces.gui.utils.cross_platform_window import (
                CrossPlatformWindowManager as CPW,
            )
            # Keep Python references to avoid shortcut objects being garbage collected
            self._chat_shortcuts = []
            for combo in ("Ctrl+Return", "Ctrl+Enter"):
                sc = CPW.create_shortcut(self.chat_input, combo, self._send_chat_message, context=QtCore.Qt.WidgetWithChildrenShortcut)
                if sc is not None:
                    self._chat_shortcuts.append(sc)
            # Be explicit on macOS with Meta token as some Qt builds differ
            try:
                if CPW.is_macos():
                    sc1 = CPW.create_shortcut(self.chat_input, "Meta+Return", self._send_chat_message, context=QtCore.Qt.WidgetWithChildrenShortcut)
                    sc2 = CPW.create_shortcut(self.chat_input, "Meta+Enter", self._send_chat_message, context=QtCore.Qt.WidgetWithChildrenShortcut)
                    for _sc in (sc1, sc2):
                        if _sc is not None:
                            self._chat_shortcuts.append(_sc)
            except Exception:
                pass

            # Additional safety: register application-level shortcuts that only fire when chat input has focus
            self._chat_app_shortcuts = []
            for combo in ("Ctrl+Return", "Ctrl+Enter"):
                sca = CPW.create_shortcut(self, combo, self._on_chat_send_shortcut, context=QtCore.Qt.ApplicationShortcut)
                if sca is not None:
                    self._chat_app_shortcuts.append(sca)
            try:
                if CPW.is_macos():
                    sca1 = CPW.create_shortcut(self, "Meta+Return", self._on_chat_send_shortcut, context=QtCore.Qt.ApplicationShortcut)
                    sca2 = CPW.create_shortcut(self, "Meta+Enter", self._on_chat_send_shortcut, context=QtCore.Qt.ApplicationShortcut)
                    for _sc in (sca1, sca2):
                        if _sc is not None:
                            self._chat_app_shortcuts.append(_sc)
            except Exception:
                pass
        except Exception:
            pass
        
        # Send controls
        send_layout = QtWidgets.QHBoxLayout()
        
        self.send_btn = QtWidgets.QPushButton("Send")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.clicked.connect(self._send_chat_message)
        send_layout.addWidget(self.send_btn)
        
        self.clear_chat_btn = QtWidgets.QPushButton("Clear")
        self.clear_chat_btn.setObjectName("clear_chat_btn")
        self.clear_chat_btn.clicked.connect(self._clear_chat)
        send_layout.addWidget(self.clear_chat_btn)
        
        send_layout.addStretch()
        
        layout.addLayout(send_layout)
        
        self.tab_widget.addTab(chat_widget, "💬 Chat")

    def _on_chat_send_shortcut(self):
        """Application-level shortcut handler that only sends when chat has focus."""
        try:
            # Only allow when chat tab is active and input has focus
            if getattr(self, 'tab_widget', None) is not None and self.tab_widget.currentWidget() is getattr(self, '_chat_tab_widget', None):
                if self.chat_input.hasFocus():
                    self._send_chat_message()
        except Exception:
            # Best-effort; ignore errors
            pass
    
    def _create_settings_tab(self):
        """Create AI settings configuration tab"""
        settings_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(settings_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # OpenRouter API configuration group
        api_group = QtWidgets.QGroupBox("🔑 OpenRouter API Configuration")
        api_layout = QtWidgets.QVBoxLayout(api_group)
        api_layout.setSpacing(12)
        
        # Information label with clickable link
        info_frame = QtWidgets.QFrame()
        info_frame.setStyleSheet(f"""
            color: {self.colors['text_secondary']};
            font-style: italic;
            padding: 8px;
            background: {self.colors['bg_tertiary']};
            border-radius: 4px;
        """)
        
        info_layout = QtWidgets.QHBoxLayout(info_frame)
        info_layout.setContentsMargins(8, 8, 8, 8)
        info_layout.setSpacing(4)
        
        # Main text
        info_text = QtWidgets.QLabel("Configure your OpenRouter API key to enable AI-powered analysis features. Get your free API key at:")
        info_text.setStyleSheet(f"color: {self.colors['text_secondary']}; font-style: italic;")
        info_layout.addWidget(info_text)
        
        # Clickable link
        link_label = QtWidgets.QLabel("https://openrouter.ai")
        link_label.setStyleSheet(f"""
            color: {self.colors['accent_primary']};
            text-decoration: underline;
            font-style: italic;
        """)
        link_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        link_label.mousePressEvent = lambda event: self._open_openrouter_website()
        info_layout.addWidget(link_label)
        
        info_layout.addStretch()
        api_layout.addWidget(info_frame)
        
        # API Key input
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(QtWidgets.QLabel("API Key:"))
        
        self.api_key_input = QtWidgets.QLineEdit()
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter your OpenRouter API key")
        # Reduce the visible length of the API key field
        self.api_key_input.setMaximumWidth(360)
        key_layout.addWidget(self.api_key_input)
        
        # Show/hide API key button
        self.show_key_btn = QtWidgets.QPushButton("Show")
        self.show_key_btn.setObjectName("show_key_btn")
        self.show_key_btn.setMaximumWidth(90)
        self.show_key_btn.clicked.connect(self._toggle_api_key_visibility)
        key_layout.addWidget(self.show_key_btn)
        # Move test connection controls next to the Show button
        self.test_connection_btn = QtWidgets.QPushButton("Test Connection")
        self.test_connection_btn.setObjectName("test_connection_btn")
        self.test_connection_btn.clicked.connect(self._test_openrouter_connection)
        key_layout.addWidget(self.test_connection_btn)

        self.connection_status_label = QtWidgets.QLabel("Not tested")
        self.connection_status_label.setStyleSheet(f"color: {self.colors['text_secondary']};")
        key_layout.addWidget(self.connection_status_label)
        key_layout.addStretch()

        api_layout.addLayout(key_layout)
        layout.addWidget(api_group)
        
        # Model selection group
        model_group = QtWidgets.QGroupBox("🤖 Model Selection & Testing")
        model_layout = QtWidgets.QVBoxLayout(model_group)
        model_layout.setSpacing(12)
        
        # Model selection info
        model_info_label = QtWidgets.QLabel(
            "Choose your preferred model for AI analysis. "
            "Click 'Fetch Models' to see available options."
        )
        model_info_label.setStyleSheet(f"color: {self.colors['text_secondary']}; font-style: italic;")
        model_info_label.setWordWrap(True)
        model_layout.addWidget(model_info_label)
        
        # Create split layout: table on the left, controls on the right
        split_layout = QtWidgets.QHBoxLayout()

        # Left side (filters + table)
        left_side_layout = QtWidgets.QVBoxLayout()

        # Filter controls
        filter_layout = QtWidgets.QHBoxLayout()

        filter_layout.addWidget(QtWidgets.QLabel("Filter:"))

        self.filter_input = QtWidgets.QLineEdit()
        self.filter_input.setPlaceholderText("Search models...")
        self.filter_input.textChanged.connect(self._filter_models)
        filter_layout.addWidget(self.filter_input)

        # Remove Free Only and Reasoning support checkboxes per request

        left_side_layout.addLayout(filter_layout)

        # Model table
        self.model_table = QtWidgets.QTableWidget()
        # Remove Reasoning column; keep pricing column
        self.model_table.setColumnCount(5)
        self.model_table.setHorizontalHeaderLabels([
            "Model Name", "Provider", "Context", "Price", "Status"
        ])
        self.model_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.model_table.setAlternatingRowColors(False)
        self.model_table.setSortingEnabled(True)
        # Let the table expand to fill vertical space
        self.model_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        # Set column widths
        header = self.model_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 250)  # Model Name
        header.resizeSection(1, 100)  # Provider
        header.resizeSection(2, 80)   # Context
        header.resizeSection(3, 120)  # Price
        header.resizeSection(4, 80)   # Status
        
        self.model_table.setStyleSheet(f"""
            QTableWidget {{
                background: {self.colors['bg_secondary']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                font-size: 9pt;
                gridline-color: {self.colors['bg_tertiary']};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background: {self.colors['btn_primary']};
                color: white;
            }}
            QHeaderView::section {{
                background: {self.colors['bg_tertiary']};
                border: 1px solid {self.colors['border']};
                padding: 4px 8px;
                font-weight: bold;
            }}
        """)
        left_side_layout.addWidget(self.model_table)

        # Right side (controls and status)
        right_container = QtWidgets.QWidget()
        right_container.setMaximumWidth(260)
        right_side_layout = QtWidgets.QVBoxLayout(right_container)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(6)

        self.fetch_models_btn = QtWidgets.QPushButton("Fetch All Models")
        self.fetch_models_btn.setObjectName("fetch_models_btn")
        self.fetch_models_btn.clicked.connect(self._fetch_all_models)
        right_side_layout.addWidget(self.fetch_models_btn)

        self.fetch_free_btn = QtWidgets.QPushButton("Free Only")
        self.fetch_free_btn.setObjectName("fetch_free_btn")
        self.fetch_free_btn.clicked.connect(self._fetch_free_models)
        right_side_layout.addWidget(self.fetch_free_btn)

        self.test_model_btn = QtWidgets.QPushButton("Test Selected")
        self.test_model_btn.setObjectName("test_model_btn")
        self.test_model_btn.clicked.connect(self._test_selected_model)
        self.test_model_btn.setEnabled(False)
        right_side_layout.addWidget(self.test_model_btn)

        # Status label at the bottom of the right pane
        right_side_layout.addStretch()
        self.model_status_label = QtWidgets.QLabel("No models loaded")
        self.model_status_label.setStyleSheet(f"color: {self.colors['text_secondary']};")
        right_side_layout.addWidget(self.model_status_label)

        # Add left and right to split
        split_layout.addLayout(left_side_layout)
        split_layout.addWidget(right_container)
        # Make the left side (table) take remaining space
        split_layout.setStretch(0, 1)
        split_layout.setStretch(1, 0)

        # Add split layout to the group
        model_layout.addLayout(split_layout)

        # Connect selection change
        self.model_table.itemSelectionChanged.connect(self._on_model_selection_changed)
        
        # Ensure the model group (and table) stretch to the bottom of the dialog
        model_group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(model_group, 1)
        self.tab_widget.addTab(settings_widget, "⚙️ Settings")
        
        # Load current settings
        self._load_current_settings()
        self._update_ai_buttons_enabled()

    def _load_current_settings(self):
        """Load current AI settings from configuration"""
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import (
                get_openrouter_api_key,
                get_openrouter_config,
            )
            # Prefer secure storage for API key
            api_key = get_openrouter_api_key() or ''
            self.api_key_input.setText(api_key)
            if api_key:
                self.connection_status_label.setText("API key loaded")
                self.connection_status_label.setStyleSheet(f"color: {self.colors['btn_success']};")
            
        except Exception as e:
            _LOGGER.warning(f"Could not load AI settings: {e}")
        finally:
            self._update_ai_buttons_enabled()
    
    def _toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        if self.api_key_input.echoMode() == QtWidgets.QLineEdit.Password:
            self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.show_key_btn.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.show_key_btn.setText("Show")
    
    def _test_openrouter_connection(self):
        """Test OpenRouter API connection"""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QtWidgets.QMessageBox.warning(
                self, 
                "No API Key", 
                "Please enter your OpenRouter API key first."
            )
            return
        
        self.connection_status_label.setText("Testing...")
        self.connection_status_label.setStyleSheet(f"color: {self.colors['btn_warning']};")
        self.test_connection_btn.setEnabled(False)
        
        # Test connection in a separate thread
        def test_connection():
            try:
                import requests
                response = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_connection_success", QtCore.Qt.QueuedConnection
                    )
                else:
                    error_msg = f"API Error: {response.status_code}"
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_connection_error", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, error_msg)
                    )
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_connection_error", QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, str(e))
                )
        
        import threading
        thread = threading.Thread(target=test_connection, daemon=True)
        thread.start()
    
    @QtCore.Slot()
    def _on_connection_success(self):
        """Handle successful connection test"""
        self.connection_status_label.setText("Connected successfully")
        self.connection_status_label.setStyleSheet(f"color: {self.colors['btn_success']};")
        self.test_connection_btn.setEnabled(True)
        
        # Save API key to config
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import (
                save_openrouter_config,
                save_openrouter_api_key,
            )
            api_key = self.api_key_input.text().strip()
            # Persist securely
            save_openrouter_api_key(api_key)
            save_openrouter_config(api_key, "", "", False)
        except Exception as e:
            _LOGGER.warning(f"Could not save API key: {e}")
        finally:
            self._update_ai_buttons_enabled()
    
    @QtCore.Slot(str)
    def _on_connection_error(self, error):
        """Handle connection test error"""
        self.connection_status_label.setText(f"Error: {error}")
        self.connection_status_label.setStyleSheet(f"color: {self.colors['btn_danger']};")
        self.test_connection_btn.setEnabled(True)
    
    def _fetch_free_models(self):
        """Fetch available free models from OpenRouter"""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QtWidgets.QMessageBox.warning(
                self, 
                "No API Key", 
                "Please enter your OpenRouter API key first."
            )
            return
        
        self.model_status_label.setText("Fetching models...")
        self.model_status_label.setStyleSheet(f"color: {self.colors['btn_warning']};")
        self.fetch_models_btn.setEnabled(False)
        self.fetch_free_btn.setEnabled(False)
        self.model_table.setRowCount(0)
        
        # Fetch models in separate thread
        def fetch_models():
            try:
                from snid_sage.interfaces.llm.openrouter.openrouter_llm import fetch_free_models
                models = fetch_free_models(api_key)
                if models is None:
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_fetch_error", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, "Failed to fetch models")
                    )
                    return
                import json
                models_json = json.dumps(models)
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_models_fetched", QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, models_json)
                )
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_fetch_error", QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, str(e))
                )
        
        import threading
        thread = threading.Thread(target=fetch_models, daemon=True)
        thread.start()
    
    def _fetch_all_models(self):
        """Fetch all available models from OpenRouter"""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QtWidgets.QMessageBox.warning(
                self, 
                "No API Key", 
                "Please enter your OpenRouter API key first."
            )
            return
        
        self.model_status_label.setText("Fetching all models...")
        self.model_status_label.setStyleSheet(f"color: {self.colors['btn_warning']};")
        self.fetch_models_btn.setEnabled(False)
        self.fetch_free_btn.setEnabled(False)
        self.model_table.setRowCount(0)
        
        # Fetch models in separate thread
        def fetch_all():
            try:
                from snid_sage.interfaces.llm.openrouter.openrouter_llm import fetch_all_models
                models = fetch_all_models(api_key, free_only=False)
                
                if models:
                    import json
                    models_json = json.dumps(models)
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_models_fetched", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, models_json)
                    )
                else:
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_fetch_error", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, "No models found")
                    )
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_fetch_error", QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, str(e))
                )
        
        import threading
        thread = threading.Thread(target=fetch_all, daemon=True)
        thread.start()
    
    @QtCore.Slot(str)
    def _on_models_fetched(self, models_json):
        """Handle successful model fetch"""
        # Parse JSON string back to list
        try:
            import json
            models = json.loads(models_json)
        except (json.JSONDecodeError, ValueError) as e:
            _LOGGER.error(f"Failed to parse models JSON: {e}")
            self.model_status_label.setText("Error parsing models data")
            self.model_status_label.setStyleSheet(f"color: {self.colors['btn_danger']};")
            self.fetch_models_btn.setEnabled(True)
            self.fetch_free_btn.setEnabled(True)
            return
        
        if models:
            # Store models for filtering
            self.all_models = models
            
            # Populate table
            self._populate_model_table(models)
            
            self.model_status_label.setText(f"Found {len(models)} models")
            self.model_status_label.setStyleSheet(f"color: {self.colors['btn_success']};")
        else:
            self.model_status_label.setText("No models found")
            self.model_status_label.setStyleSheet(f"color: {self.colors['btn_warning']};")
        
        self.fetch_models_btn.setEnabled(True)
        self.fetch_free_btn.setEnabled(True)
    
    def _populate_model_table(self, models):
        """Populate the model table with data"""
        table = self.model_table
        table.setRowCount(len(models))
        
        # Get current selected model to preserve selection
        config = {}
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import get_openrouter_config, get_model_test_status
            config = get_openrouter_config()
        except Exception as e:
            _LOGGER.warning(f"Could not load OpenRouter config: {e}")
        
        current_model_id = config.get('model_id', '')
        
        for row, model in enumerate(models):
            # Model Name (with fallback)
            model_name = model.get('name', model.get('id', 'Unknown Model'))
            model_id = model.get('id', '')
            name_item = QtWidgets.QTableWidgetItem(model_name)
            name_item.setData(QtCore.Qt.UserRole, model_id)
            table.setItem(row, 0, name_item)
            
            # Provider (with fallback)
            provider = model.get('provider', 'Unknown')
            if not provider and 'id' in model:
                # Extract provider from model ID as fallback
                provider = model['id'].split('/')[0] if '/' in model['id'] else 'Unknown'
            provider_item = QtWidgets.QTableWidgetItem(provider)
            table.setItem(row, 1, provider_item)
            
            # Context Length (with fallback)
            context_display = model.get('context_display', str(model.get('context_length', 'Unknown')))
            context_item = QtWidgets.QTableWidgetItem(context_display)
            context_item.setData(QtCore.Qt.UserRole, model.get('context_length', 0))  # Store raw number for sorting
            table.setItem(row, 2, context_item)
            
            # Price (with fallback)
            price_display = model.get('price_display', 'Unknown')
            price_item = QtWidgets.QTableWidgetItem(price_display)
            prompt_price = model.get('prompt_price', 0)
            price_item.setData(QtCore.Qt.UserRole, prompt_price)  # Store raw price for sorting
            is_free = model.get('is_free', False)
            if is_free:
                price_item.setBackground(QtGui.QColor(200, 255, 200))  # Light green for free
            table.setItem(row, 3, price_item)
            
            # Status
            try:
                from snid_sage.interfaces.llm.openrouter.openrouter_llm import get_model_test_status
                is_tested = get_model_test_status(model_id)
                if model_id == current_model_id and is_tested:
                    status_text = "Active"
                    status_item = QtWidgets.QTableWidgetItem(status_text)
                    status_item.setBackground(QtGui.QColor(144, 238, 144))  # Light green
                elif is_tested:
                    status_text = "Tested"
                    status_item = QtWidgets.QTableWidgetItem(status_text)
                    status_item.setBackground(QtGui.QColor(200, 255, 200))  # Light green
                else:
                    status_text = "⏳ Untested"
                    status_item = QtWidgets.QTableWidgetItem(status_text)
            except:
                status_text = "⏳ Untested"
                status_item = QtWidgets.QTableWidgetItem(status_text)
            
            table.setItem(row, 4, status_item)
            
            # Select current model if it matches
            if model['id'] == current_model_id:
                table.selectRow(row)
    
    @QtCore.Slot(str)
    def _on_fetch_error(self, error):
        """Handle model fetch error"""
        self.model_status_label.setText(f"Error: {error}")
        self.model_status_label.setStyleSheet(f"color: {self.colors['btn_danger']};")
        self.fetch_models_btn.setEnabled(True)
        self.fetch_free_btn.setEnabled(True)
    
    def _on_model_selection_changed(self):
        """Handle model selection change"""
        selected_rows = self.model_table.selectionModel().selectedRows()
        self.test_model_btn.setEnabled(len(selected_rows) > 0)
    
    def _test_selected_model(self):
        """Test the selected model"""
        selected_rows = self.model_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QtWidgets.QMessageBox.warning(
                self, 
                "No API Key", 
                "Please enter your OpenRouter API key first."
            )
            return
        
        row = selected_rows[0].row()
        model_item = self.model_table.item(row, 0)
        if not model_item:
            return
            
        model_id = model_item.data(QtCore.Qt.UserRole)
        model_name = model_item.text()
        
        self.test_model_btn.setEnabled(False)
        self.test_model_btn.setText("Testing...")
        
        # Test model in separate thread
        def test_model():
            try:
                from snid_sage.interfaces.llm.openrouter.openrouter_llm import call_openrouter_api, save_openrouter_config
                
                # Save this model for testing
                save_openrouter_config(api_key, model_id, model_name, False)
                
                # Test with a simple prompt
                test_prompt = "Hello! Please respond with a simple 'OK' if you can process this request."
                response = call_openrouter_api(test_prompt, max_tokens=50)
                
                if response and len(response.strip()) > 0:
                    # Mark as tested
                    save_openrouter_config(api_key, model_id, model_name, True)
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_model_test_success", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, model_id), QtCore.Q_ARG(str, model_name)
                    )
                else:
                    QtCore.QMetaObject.invokeMethod(
                        self, "_on_model_test_error", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, model_id), QtCore.Q_ARG(str, "Empty response from model")
                    )
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_model_test_error", QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, model_id), QtCore.Q_ARG(str, str(e))
                )
        
        import threading
        thread = threading.Thread(target=test_model, daemon=True)
        thread.start()
    
    @QtCore.Slot(str, str)
    def _on_model_test_success(self, model_id, model_name):
        """Handle successful model test"""
        self.test_model_btn.setEnabled(True)
        self.test_model_btn.setText("Test Selected")
        
        # Update the status column in the table
        for row in range(self.model_table.rowCount()):
            item = self.model_table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == model_id:
                status_item = self.model_table.item(row, 5)  # Status column
                if status_item:
                    status_item.setText("Tested")
                    status_item.setBackground(QtGui.QColor(200, 255, 200))  # Light green
                break
        
        QtWidgets.QMessageBox.information(
            self,
            "Model Test Successful",
            f"Model '{model_name}' tested successfully!\nIt will be used for future AI operations."
        )
        self._refresh_model_label()
    
    @QtCore.Slot(str, str)
    def _on_model_test_error(self, model_id, error_message):
        """Handle model test error"""
        self.test_model_btn.setEnabled(True)
        self.test_model_btn.setText("Test Selected")
        
        # Update the status column in the table
        for row in range(self.model_table.rowCount()):
            item = self.model_table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == model_id:
                status_item = self.model_table.item(row, 5)  # Status column
                if status_item:
                    status_item.setText("Failed")
                    status_item.setBackground(QtGui.QColor(255, 200, 200))  # Light red
                break
        
        QtWidgets.QMessageBox.warning(
            self,
            "Model Test Failed",
            f"Failed to test model:\n{error_message}"
        )
        self._refresh_model_label()
    
    def _open_openrouter_website(self):
        """Open OpenRouter website in default browser"""
        import webbrowser
        try:
            webbrowser.open("https://openrouter.ai")
        except Exception as e:
            _LOGGER.error(f"Failed to open OpenRouter website: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "Browser Error",
                "Failed to open browser. Please visit https://openrouter.ai manually."
            )
    
    def _filter_models(self):
        """Filter models based on search criteria"""
        if not hasattr(self, 'all_models') or not self.all_models:
            return
        
        search_text = self.filter_input.text().lower()
        
        # Filter models
        filtered_models = []
        for model in self.all_models:
            # Text search
            if search_text and search_text not in model['name'].lower() and search_text not in model.get('provider', '').lower():
                continue
            
            
            filtered_models.append(model)
        
        # Update table with filtered models
        self._populate_model_table(filtered_models)

    
    def _create_footer_buttons(self, layout):
        """Create footer buttons"""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Help button
        help_btn = QtWidgets.QPushButton("Help")
        help_btn.setObjectName("help_btn")
        help_btn.clicked.connect(self._show_help)
        button_layout.addWidget(help_btn)
        
        button_layout.addStretch()
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setObjectName("close_btn")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _generate_summary(self):
        """Generate comprehensive AI summary"""
        if self.is_generating:
            return
        
        self.is_generating = True
        self.generate_summary_btn.setEnabled(False)
        self.summary_progress.setVisible(True)
        self.summary_progress.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Generating...")
        self.status_label.setStyleSheet(f"color: {self.colors['btn_warning']}; font-weight: bold;")
        
        # Generate real AI summary using current settings
        def generate_real_summary():
            try:
                # Get current AI settings
                ai_settings = self._get_current_ai_settings()
                
                # Collect user metadata
                user_metadata = {
                    'observer_name': self.observer_name_input.text(),
                    'telescope': self.telescope_input.text(),
                    'observation_date': self.observation_date_input.text(),
                    'specific_request': self.specific_request_input.toPlainText()
                }
                
                # Generate summary using LLM integration
                if hasattr(self.parent_gui, 'llm_integration') and self.parent_gui.llm_integration:
                    summary_text = self.parent_gui.llm_integration.generate_summary(
                        self.current_snid_results,
                        user_metadata=user_metadata
                    )
                else:
                    # Fallback if no LLM integration - use non-Tk LLM module
                    from snid_sage.interfaces.llm.llm_integration import LLMIntegration
                    llm = LLMIntegration(self.parent())
                    summary_text = llm.generate_summary(
                        self.current_snid_results,
                        user_metadata=user_metadata
                    )
                
                summary = f"""
 SNID AI ANALYSIS SUMMARY
 ========================
 
 Reporting Group/Name: {user_metadata.get('reporting_group') or user_metadata.get('observer_name', 'Not specified')}
 Telescope: {user_metadata.get('telescope', 'Not specified')}  
 Observation Date: {user_metadata.get('observation_date', 'Not specified')}
 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 
 CLASSIFICATION ANALYSIS:
 {summary_text}
 """
                
                # Update UI from main thread  
                QtCore.QMetaObject.invokeMethod(
                    self, "_update_summary_result", 
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, summary)
                )
                
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self, "_handle_summary_error", 
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, str(e))
                )
        
        # Start generation in background thread
        thread = threading.Thread(target=generate_real_summary, daemon=True)
        thread.start()
    
    @QtCore.Slot(str)
    def _update_summary_result(self, summary):
        """Update summary result in main thread"""
        self.summary_text.setPlainText(summary)
        self.is_generating = False
        self.generate_summary_btn.setEnabled(True)
        self.summary_progress.setVisible(False)
        self.export_summary_btn.setEnabled(True)
        self.copy_summary_btn.setEnabled(True)
        self.status_label.setText("Summary Generated")
        self.status_label.setStyleSheet(f"color: {self.colors['btn_success']}; font-weight: bold;")
        _LOGGER.info("AI summary generated successfully")
    
    @QtCore.Slot(str)
    def _handle_summary_error(self, error):
        """Handle summary generation error"""
        self.is_generating = False
        self.generate_summary_btn.setEnabled(True)
        self.summary_progress.setVisible(False)
        self.status_label.setText("Error")
        self.status_label.setStyleSheet(f"color: {self.colors['btn_danger']}; font-weight: bold;")
        
        QtWidgets.QMessageBox.critical(
            self, 
            "AI Error", 
            f"Error generating summary:\n{error}"
        )
    
    def _send_chat_message(self):
        """Send chat message to AI"""
        message = self.chat_input.toPlainText().strip()
        if not message:
            return
        
        # Add user message to chat
        self._append_chat_line(f"You: {message}")
        self.chat_input.clear()
        # Maintain conversation history
        self.conversation.append({"role": "user", "content": message})
        # Disable send while processing
        self.send_btn.setEnabled(False)
        
        # Get AI response using current settings
        def get_ai_response():
            try:
                ai_settings = self._get_current_ai_settings()
                # Collect optional user metadata from summary tab controls if available
                user_metadata = {
                    'observer_name': getattr(self, 'observer_name_input', None).text() if hasattr(self, 'observer_name_input') else '',
                    'telescope': getattr(self, 'telescope_input', None).text() if hasattr(self, 'telescope_input') else '',
                    'observation_date': getattr(self, 'observation_date_input', None).text() if hasattr(self, 'observation_date_input') else '',
                }

                # Use LLM integration to get real response
                if hasattr(self.parent_gui, 'llm_integration') and self.parent_gui.llm_integration:
                    ai_response = self.parent_gui.llm_integration.chat_with_llm(
                        message,
                        conversation_history=self.conversation,
                        user_metadata=user_metadata,
                        max_tokens=ai_settings['max_tokens']
                    )
                else:
                    # Fallback if no LLM integration - use non-Tk LLM module
                    from snid_sage.interfaces.llm.llm_integration import LLMIntegration
                    llm = LLMIntegration(self.parent())
                    ai_response = llm.chat_with_llm(
                        message,
                        conversation_history=self.conversation,
                        user_metadata=user_metadata,
                        max_tokens=ai_settings['max_tokens']
                    )

                # Post response back to main thread (only the new assistant message)
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_assistant_response",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, ai_response)
                )
                
            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                QtCore.QMetaObject.invokeMethod(
                    self, "_on_assistant_response",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, error_msg)
                )
        
        # Start chat response in background
        thread = threading.Thread(target=get_ai_response, daemon=True)
        thread.start()
        
        # Scroll to bottom
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    @QtCore.Slot(str)
    def _on_assistant_response(self, assistant_text: str):
        """Append assistant response on the main thread and update state"""
        # Update conversation history
        self.conversation.append({"role": "assistant", "content": assistant_text})
        # Append to chat area
        self._append_chat_line(f"AI Assistant: {assistant_text}")
        # Scroll to bottom and re-enable send
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.send_btn.setEnabled(True)

    def _append_chat_line(self, text: str):
        """Efficiently append a new line to the chat history without rebuilding all text"""
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        # Ensure spacing between messages
        if self.chat_history.toPlainText().strip():
            cursor.insertText("\n\n")
        cursor.insertText(text)
        self.chat_history.setTextCursor(cursor)
    
    def _clear_chat(self):
        """Clear chat history"""
        self.chat_history.setPlainText(
            "AI Assistant: Hello! Ask me questions about your SNID-SAGE analysis.\n\n"
            "Examples:\n"
            "• What type of supernova is this?\n"
            "• How confident is this classification?\n"
            "• What's the estimated redshift?\n"
            "• Should I follow up with more observations?\n\n"
            "What would you like to know?"
        )
        self.conversation = [
            {"role": "assistant", "content": "Hello! Ask me questions about your SNID-SAGE analysis."}
        ]

        # Update AI availability state
        self._update_ai_buttons_enabled()
    
    def _export_summary(self):
        """Export summary to file"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export AI Summary",
            f"snid_ai_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.summary_text.toPlainText())
                
                QtWidgets.QMessageBox.information(
                    self, 
                    "Export Successful", 
                    f"Summary exported to {filename}"
                )
                _LOGGER.info(f"AI summary exported to {filename}")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, 
                    "Export Error", 
                    f"Error exporting summary:\n{e}"
                )
    
    def _copy_summary(self):
        """Copy summary to clipboard"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.summary_text.toPlainText())
        
        # Show status
        original_text = self.status_label.text()
        self.status_label.setText("Copied to Clipboard")
        QtCore.QTimer.singleShot(2000, lambda: self.status_label.setText(original_text))
    

    
    def _show_help(self):
        """Show help information"""
        help_text = """
SNID AI Assistant Help
=====================

SUMMARY TAB:
- Fill in optional user information for personalized reports
- Select analysis options to include in the summary
- Click 'Generate Comprehensive Summary' to create AI analysis
- Export or copy the summary for use in reports

CHAT TAB:
- Interactive conversation with AI about your results
- Ask specific questions about classification, redshift, etc.
- Chat history is maintained during the session

SETTINGS:
- Use the main application settings to configure AI options

For best results, ensure SNID analysis has been completed
before using the AI assistant.
"""
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("AI Assistant Help")
        msg.setText(help_text)
        msg.setTextFormat(QtCore.Qt.PlainText)
        msg.exec()
    

    
    def _get_current_ai_settings(self):
        """Get current AI settings with default values"""
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import (
                get_openrouter_config, DEFAULT_MODEL
            )
            config = get_openrouter_config()
            return {
                'temperature': 0.7,
                'max_tokens': 2000,
                'model_id': config.get('model_id', DEFAULT_MODEL)
            }
        except Exception:
            return {
                'temperature': 0.7,
                'max_tokens': 2000,
                'model_id': 'openai/gpt-3.5-turbo'
            } 

    def _refresh_model_label(self):
        """Refresh model label with the current configured model"""
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import get_openrouter_config, DEFAULT_MODEL
            config = get_openrouter_config()
            model_name = config.get('model_name') or config.get('model_id') or DEFAULT_MODEL
            self.model_label.setText(f"Model: {model_name}")
            if hasattr(self, 'corner_model_label') and self.corner_model_label is not None:
                self.corner_model_label.setText(f"Model: {model_name}")
        except Exception:
            self.model_label.setText("")
            if hasattr(self, 'corner_model_label') and self.corner_model_label is not None:
                self.corner_model_label.setText("")

    # Removed fullscreen/maximize controls per user request

    def _update_ai_buttons_enabled(self):
        """Enable/disable AI actions based on whether an API key is configured"""
        api_key = ''
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import get_openrouter_api_key
            api_key = get_openrouter_api_key() or ''
        except Exception:
            api_key = ''

        ai_ready = bool(api_key)

        # Respect in-progress states when enabling
        if hasattr(self, 'generate_summary_btn'):
            self.generate_summary_btn.setEnabled(ai_ready and not self.is_generating)
            if not ai_ready:
                self.generate_summary_btn.setToolTip("Configure OpenRouter API key in Settings to enable AI")
            else:
                self.generate_summary_btn.setToolTip("")

        if hasattr(self, 'send_btn'):
            # Don't override if disabled due to an in-flight request
            if ai_ready and self.send_btn.isEnabled() is False:
                # Leave disabled; it will be re-enabled when the response arrives
                pass
            else:
                self.send_btn.setEnabled(ai_ready)
            if not ai_ready:
                self.send_btn.setToolTip("Configure OpenRouter API key in Settings to enable AI chat")
            else:
                self.send_btn.setToolTip("")