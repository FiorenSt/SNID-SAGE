"""
Unified PySide6 Layout Manager
=============================

This module provides the single, authoritative layout management system for the SNID SAGE GUI.
It consolidates functionality from all previous layout managers to eliminate conflicts and 
provide consistent, configurable layout control.

Key Features:
- Single source of truth for all layout operations
- Configurable sizing with conflict detection
- Persistent settings management
- Cross-platform compatibility
- Extensible design for future enhancements
- Twemoji icon integration for consistent emoji rendering

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import logging
from pathlib import Path
from PySide6 import QtWidgets, QtCore
from typing import Dict, Any, Optional, Tuple, Set
import json

# Import Twemoji manager
try:
    from .twemoji_manager import get_twemoji_manager
    TWEMOJI_AVAILABLE = True
except ImportError:
    TWEMOJI_AVAILABLE = False

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.unified_layout')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.unified_layout')

# Import platform configuration
from snid_sage.shared.utils.config.platform_config import get_platform_config


class LayoutSettings:
    """Centralized settings for all layout configuration"""
    
    def __init__(self):
        # === Panel Dimensions ===
        self.left_panel_width = 220
        self.status_bar_height = 42  # Reduced by 6 points
        self.controls_frame_height = 36
        
        # === Spacing Configuration ===
        self.plot_controls_spacing = 15
        self.button_group_spacing = 15
        self.panel_margins = (10, 10, 10, 10)  # left, top, right, bottom
        self.panel_spacing = 10
        
        # === Plot Margins ===
        self.plot_margin_top = 8
        self.plot_margin_bottom = 5
        self.plot_margin_left = 5
        self.plot_margin_right = 5
        
        # === Control Widths ===
        self.view_controls_width = 120
        self.nav_controls_width = 80
        self.analysis_controls_width = 160
        
        # === Button Sizes ===
        # Standardized button heights for consistent UI
        self.micro_button_size = (22, 16)   # Unused (previously for up/down arrows)
        self.small_button_size = (32, 24)   # For left/right navigation arrows  
        self.medium_button_size = (35, 24)  # For toolbar buttons (analysis, view toggles)
        self.toolbar_button_size = (35, 24) # Unified size for all toolbar buttons
        self.large_button_size = (120, 48)  # For main workflow buttons
        
        # === Window Configuration ===
        self.default_window_size = (900, 600)
        self.minimum_window_size = (700, 500)
        # Maximum window size removed to allow full maximization
        # self.maximum_window_size = (1400, 1000)
        
        # === Advanced Options ===
        self.button_layout_style = "horizontal"
        self.plot_expansion_mode = "fill_remaining"
        self.independent_plot_positioning = True
        
        # === Conflict Detection ===
        self._applied_settings = set()  # Track what has been applied
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for serialization"""
        return {
            'left_panel_width': self.left_panel_width,
            'status_bar_height': self.status_bar_height,
            'controls_frame_height': self.controls_frame_height,
            'plot_controls_spacing': self.plot_controls_spacing,
            'button_group_spacing': self.button_group_spacing,
            'panel_margins': self.panel_margins,
            'panel_spacing': self.panel_spacing,
            'plot_margin_top': self.plot_margin_top,
            'plot_margin_bottom': self.plot_margin_bottom,
            'plot_margin_left': self.plot_margin_left,
            'plot_margin_right': self.plot_margin_right,
            'view_controls_width': self.view_controls_width,
            'nav_controls_width': self.nav_controls_width,
            'analysis_controls_width': self.analysis_controls_width,
            'micro_button_size': self.micro_button_size,
            'small_button_size': self.small_button_size,
            'medium_button_size': self.medium_button_size,
            'toolbar_button_size': self.toolbar_button_size,
            'large_button_size': self.large_button_size,
            'default_window_size': self.default_window_size,
            'minimum_window_size': self.minimum_window_size,
            'maximum_window_size': self.maximum_window_size,
            'button_layout_style': self.button_layout_style,
            'plot_expansion_mode': self.plot_expansion_mode,
            'independent_plot_positioning': self.independent_plot_positioning
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """Load settings from dictionary with validation"""
        for key, value in data.items():
            if hasattr(self, key):
                # Validate tuple values
                if key.endswith('_size') and isinstance(value, (list, tuple)) and len(value) == 2:
                    setattr(self, key, tuple(value))
                elif key == 'panel_margins' and isinstance(value, (list, tuple)) and len(value) == 4:
                    setattr(self, key, tuple(value))
                else:
                    setattr(self, key, value)
    
    def mark_setting_applied(self, setting_name: str, widget_id: str):
        """Mark a setting as applied to detect conflicts"""
        key = f"{setting_name}:{widget_id}"
        if key in self._applied_settings:
            _LOGGER.warning(f"Potential conflict: {setting_name} already applied to {widget_id}")
        self._applied_settings.add(key)
    
    def reset_applied_settings(self):
        """Reset tracking of applied settings"""
        self._applied_settings.clear()


class UnifiedPySide6LayoutManager:
    """
    Unified layout manager that consolidates all layout functionality.
    
    This class provides a single interface for all layout operations,
    eliminating conflicts and providing consistent behavior.
    """
    
    def __init__(self, settings: Optional[LayoutSettings] = None):
        self.settings = settings or self._load_settings_from_config()
        self._config_file = self._get_config_file_path()
        _LOGGER.info("Unified layout manager initialized")
    
    def setup_main_window(self, window: QtWidgets.QMainWindow) -> None:
        """Apply standard window setup (size, icon, centering).

        This method provides a minimal, cross-interface hook so other
        layout managers can delegate common window setup here.
        """
        try:
            min_w, min_h = self.settings.minimum_window_size
            window.setMinimumSize(min_w, min_h)
        except Exception as exc:
            _LOGGER.debug(f"Could not set minimum window size: {exc}")

        try:
            def_w, def_h = self.settings.default_window_size
            window.resize(def_w, def_h)
        except Exception as exc:
            _LOGGER.debug(f"Could not apply default window size: {exc}")

        # Best-effort window icon
        try:
            from PySide6 import QtGui  # local import to avoid hard dependency at module load
            from .logo_manager import get_logo_manager  # type: ignore
            icon_path = get_logo_manager().get_icon_path()
            if icon_path:
                window.setWindowIcon(QtGui.QIcon(str(icon_path)))
        except Exception as exc:
            _LOGGER.debug(f"Could not set window icon: {exc}")

        # Center window on the available screen
        try:
            screen_geom = QtWidgets.QApplication.primaryScreen().availableGeometry()
            win_geom = window.frameGeometry()
            win_geom.moveCenter(screen_geom.center())
            window.move(win_geom.topLeft())
        except Exception as exc:
            _LOGGER.debug(f"Could not center window: {exc}")

    def _get_config_file_path(self) -> Path:
        """Get the configuration file path"""
        try:
            import os
            if os.name == 'nt':  # Windows
                config_dir = Path.home() / "AppData" / "Local" / "SNID_SAGE"
            else:  # Unix-like
                config_dir = Path.home() / ".config" / "snid_sage"
            
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir / "unified_layout_settings.json"
        except Exception as e:
            _LOGGER.warning(f"Could not determine config path: {e}")
            return Path("unified_layout_settings.json")
    
    def _load_settings_from_config(self) -> LayoutSettings:
        """Load settings from configuration file"""
        settings = LayoutSettings()
        
        try:
            if self._get_config_file_path().exists():
                with open(self._get_config_file_path(), 'r') as f:
                    data = json.load(f)
                    settings.from_dict(data)
                    _LOGGER.debug("Layout settings loaded from config file")
            else:
                _LOGGER.debug("No saved layout settings found, using defaults")
        except Exception as e:
            _LOGGER.warning(f"Error loading layout settings: {e}")
        
        return settings
    
    def save_settings_to_config(self) -> bool:
        """Save current settings to configuration file"""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
            _LOGGER.debug("Layout settings saved to config file")
            return True
        except Exception as e:
            _LOGGER.error(f"Error saving layout settings: {e}")
            return False
    
    def update_settings(self, new_settings: LayoutSettings):
        """Update settings and save to config"""
        self.settings = new_settings
        self.save_settings_to_config()
        _LOGGER.debug("Layout settings updated")
    
    # === MAIN LAYOUT CREATION METHODS ===
    
    def create_main_layout(self, gui_instance, central_widget):
        """Create the complete main layout structure"""
        # Reset conflict tracking
        self.settings.reset_applied_settings()
        
        # Main layout (vertical)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(*self.settings.panel_margins)
        main_layout.setSpacing(2)
        
        # Status bar at top
        status_bar = self.create_status_bar(gui_instance)
        main_layout.addWidget(status_bar)
        
        # Content area (horizontal for left and center panels)
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(self.settings.panel_spacing)
        
        # Left panel
        left_panel = self.create_left_panel(gui_instance)
        content_layout.addWidget(left_panel)
        
        # Center panel with plot
        center_panel = self.create_center_panel(gui_instance)
        content_layout.addWidget(center_panel, 1)  # stretch to fill
        
        # Add content area to main layout
        main_layout.addWidget(content_widget, 1)
        
        _LOGGER.debug("Main layout created successfully")
        return main_layout
    
    def create_status_bar(self, gui_instance) -> QtWidgets.QFrame:
        """Create unified status bar with separate contours"""
        # Main status container (no border)
        status_container = QtWidgets.QFrame()
        status_container.setObjectName("unified_status_container")
        status_container.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        # Apply size setting with conflict detection
        self._apply_size_setting(status_container, "setFixedHeight", self.settings.status_bar_height, "status_container")
        
        # Main layout
        status_layout = QtWidgets.QHBoxLayout(status_container)
        status_layout.setContentsMargins(10, 4, 10, 4)
        status_layout.setSpacing(10)
        
        # Info button with its own styling (no border frame)
        gui_instance.info_btn = QtWidgets.QPushButton("ℹ")
        gui_instance.info_btn.setObjectName("unified_info_btn")
        gui_instance.info_btn.setToolTip("Show keyboard shortcuts\nView all available hotkeys and commands")
        gui_instance.info_btn.setFixedWidth(24)  # Much narrower for compact info button
        gui_instance.info_btn.setStyleSheet("""
            QPushButton#unified_info_btn {
                background-color: #3b82f6;
                border: 1px solid #2563eb;
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: bold;
                font-family: Arial, "Helvetica Neue", Helvetica, "Segoe UI", sans-serif;
                font-size: 14px;
                color: white;
            }
            QPushButton#unified_info_btn:hover {
                background-color: #2563eb;
            }
            QPushButton#unified_info_btn:pressed {
                background-color: #1d4ed8;
                border: 1px solid #1e40af;
            }
        """)
        # Connect to the correct method name based on the interface
        if hasattr(gui_instance, 'show_shortcuts_dialog'):
            gui_instance.info_btn.clicked.connect(gui_instance.show_shortcuts_dialog)
        elif hasattr(gui_instance, '_show_shortcuts_dialog'):
            gui_instance.info_btn.clicked.connect(gui_instance._show_shortcuts_dialog)
        else:
            # Provide a fallback
            gui_instance.info_btn.clicked.connect(lambda: _LOGGER.info("Shortcuts dialog not available"))
        status_layout.addWidget(gui_instance.info_btn)
        
        # Status label in its own frame with border
        status_frame = QtWidgets.QFrame()
        status_frame.setObjectName("unified_status_frame")
        status_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        status_frame.setStyleSheet("""
            QFrame#unified_status_frame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                margin: 1px;
            }
        """)
        
        status_frame_layout = QtWidgets.QHBoxLayout(status_frame)
        status_frame_layout.setContentsMargins(12, 2, 12, 2)
        
        gui_instance.status_label = QtWidgets.QLabel("Ready - Load a spectrum to begin analysis")
        gui_instance.status_label.setObjectName("unified_status_label")
        gui_instance.status_label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        status_frame_layout.addWidget(gui_instance.status_label)
        
        status_layout.addWidget(status_frame, 1)  # Give it stretch to fill space
        
        return status_container
    
    def create_left_panel(self, gui_instance) -> QtWidgets.QFrame:
        """Create unified left panel"""
        left_panel = QtWidgets.QFrame()
        left_panel.setObjectName("unified_left_panel")
        left_panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        left_panel.setStyleSheet("""
            QFrame#unified_left_panel {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        # Apply size setting with conflict detection
        self._apply_size_setting(left_panel, "setFixedWidth", self.settings.left_panel_width, "left_panel")
        
        # Layout
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(*self.settings.panel_margins)
        left_layout.setSpacing(self.settings.panel_spacing)
        
        # Create sections
        self._create_load_section(gui_instance, left_layout)
        self._create_galaxy_analysis_section(gui_instance, left_layout)
        self._create_preprocessing_section(gui_instance, left_layout)
        self._create_configuration_section(gui_instance, left_layout)
        self._create_emission_line_section(gui_instance, left_layout)
        self._create_chat_section(gui_instance, left_layout)
        
        # Stretch before settings
        left_layout.addStretch()
        
        # Settings section at bottom
        self._create_settings_section(gui_instance, left_layout)
        
        # Store reference
        gui_instance.left_panel = left_panel
        
        return left_panel
    
    def create_center_panel(self, gui_instance) -> QtWidgets.QWidget:
        """Create unified center panel with plot"""
        center_panel = QtWidgets.QWidget()
        center_panel.setObjectName("unified_center_panel")
        center_layout = QtWidgets.QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        
        # No spacing - start plot section immediately to make it higher
        
        # Plot area with integrated controls
        plot_frame = self._create_plot_area(gui_instance)
        center_layout.addWidget(plot_frame, 1)
        
        return center_panel
    
    def _create_plot_area(self, gui_instance) -> QtWidgets.QFrame:
        """Create unified plot area with controls"""
        plot_frame = QtWidgets.QFrame()
        plot_frame.setObjectName("unified_plot_frame")
        plot_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        plot_frame.setMinimumHeight(500)
        
        # Apply styling
        plot_frame.setStyleSheet("""
            QFrame#unified_plot_frame {
                background-color: white;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        # Main layout
        main_plot_layout = QtWidgets.QVBoxLayout(plot_frame)
        main_plot_layout.setContentsMargins(
            self.settings.plot_margin_left,
            self.settings.plot_margin_top,
            self.settings.plot_margin_right,
            self.settings.plot_margin_bottom
        )
        main_plot_layout.setSpacing(15)  # Increased spacing between controls and plot
        
        # Controls at top
        controls_container = self._create_plot_controls(gui_instance)
        main_plot_layout.addWidget(controls_container)
        
        # Plot container
        plot_container = QtWidgets.QWidget()
        plot_layout = QtWidgets.QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        
        # Store references
        gui_instance.plot_layout = plot_layout
        gui_instance.plot_frame = plot_frame
        gui_instance.plot_container = plot_container
        
        # Add plot container with stretch
        main_plot_layout.addWidget(plot_container, 1)
        
        return plot_frame
    
    def _create_plot_controls(self, gui_instance) -> QtWidgets.QFrame:
        """Create unified plot controls"""
        controls_frame = QtWidgets.QFrame()
        controls_frame.setObjectName("unified_plot_controls")
        
        # Set the background to white to match the general GUI
        controls_frame.setStyleSheet("""
            QFrame#unified_plot_controls {
                background-color: white;
                border: none;
            }
        """)
        
        # Apply size setting with conflict detection
        self._apply_size_setting(controls_frame, "setFixedHeight", self.settings.controls_frame_height, "plot_controls")
        
        # Main layout
        controls_layout = QtWidgets.QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(10, 0, 10, 0)
        controls_layout.setSpacing(0)
        
        # Single row with all controls
        controls_row = QtWidgets.QWidget()
        controls_row.setStyleSheet("background-color: white;")  # Ensure row background is white too
        controls_row_layout = QtWidgets.QHBoxLayout(controls_row)
        controls_row_layout.setContentsMargins(0, 0, 0, 0)
        controls_row_layout.setSpacing(self.settings.button_group_spacing)
        
        # View controls (Flux/Flat) - positioned on the left
        self._create_view_controls(gui_instance, controls_row_layout)
        
        # Stretch to center the navigation arrows
        controls_row_layout.addStretch(1)
        
        # Navigation controls (left/right arrows) - centered
        self._create_navigation_controls(gui_instance, controls_row_layout)
        
        # Stretch to push analysis buttons to the right
        controls_row_layout.addStretch(1)
        
        # Analysis controls - positioned on the right
        self._create_analysis_controls(gui_instance, controls_row_layout)
        
        controls_layout.addWidget(controls_row)
        
        return controls_frame
    
    # === HELPER METHODS ===
    
    def _apply_size_setting(self, widget, method_name: str, value, widget_id: str):
        """Apply a size setting with conflict detection"""
        setting_name = f"{method_name}:{value}"
        self.settings.mark_setting_applied(setting_name, widget_id)
        
        # Monitor for conflicts
        try:
            from .layout_conflict_detector import monitor_widget_operation
            monitor_widget_operation(widget, widget_id, method_name, value, "UnifiedLayoutManager")
        except ImportError:
            _LOGGER.debug("Conflict detector not available")
        
        method = getattr(widget, method_name)
        if isinstance(value, (list, tuple)):
            method(*value)
        else:
            method(value)
    
    def _apply_button_size(self, button, size_type: str, button_id: str):
        """Apply button size with conflict detection"""
        size_map = {
            'micro': self.settings.micro_button_size,
            'small': self.settings.small_button_size,
            'medium': self.settings.medium_button_size,
            'toolbar': self.settings.toolbar_button_size,
            'large': self.settings.large_button_size
        }
        
        size = size_map.get(size_type, self.settings.medium_button_size)
        
        self._apply_size_setting(button, "setMinimumSize", size, button_id)
    
    # === SECTION CREATION METHODS ===
    # (These methods create the individual sections of the left panel)
    
    def _create_load_section(self, gui_instance, layout):
        """Create Load Spectrum section"""
        gui_instance.load_spectrum_btn = QtWidgets.QPushButton("Load Spectrum")
        gui_instance.load_spectrum_btn.setObjectName("unified_load_spectrum_btn")

        gui_instance.load_spectrum_btn.clicked.connect(gui_instance.browse_file)
        gui_instance.load_spectrum_btn.setToolTip(
            "Click Load Spectrum or drag a spectrum here\n"
            "Supported formats: .txt, .dat, .ascii, .asci, .fits, .flm"
        )
        layout.addWidget(gui_instance.load_spectrum_btn)
        
        # File status label - add with reduced spacing
        gui_instance.file_status_label = QtWidgets.QLabel("No file loaded")
        gui_instance.file_status_label.setObjectName("unified_file_status_label")
        gui_instance.file_status_label.setWordWrap(True)
        gui_instance.file_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important; margin-top: 0px;")
        self._apply_size_setting(gui_instance.file_status_label, "setMaximumHeight", 25, "file_status_label")
        layout.addWidget(gui_instance.file_status_label)
        layout.addSpacing(1)  # Reduced spacing after status label
    
    def _create_preprocessing_section(self, gui_instance, layout):
        """Create Preprocessing section"""
        gui_instance.preprocessing_btn = QtWidgets.QPushButton("Preprocessing")
        gui_instance.preprocessing_btn.setObjectName("unified_preprocessing_btn")

        gui_instance.preprocessing_btn.clicked.connect(gui_instance.open_preprocessing_dialog)
        
        # Add right-click functionality for quick preprocessing
        def preprocessing_context_menu(event):
            if event.button() == QtCore.Qt.RightButton:
                try:
                    # Simulate quick visual press feedback on right-click
                    try:
                        gui_instance.preprocessing_btn.setDown(True)
                        # Flush UI so the pressed state is visible immediately
                        app = QtCore.QCoreApplication.instance()
                        if app and not app.closingDown():
                            QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                        QtCore.QTimer.singleShot(120, lambda: gui_instance.preprocessing_btn.setDown(False))
                    except Exception:
                        pass

                    appc = getattr(gui_instance, 'app_controller', None)
                    preprocessed_present = bool(getattr(appc, 'processed_spectrum', None)) if appc else False
                    analysis_present = bool(getattr(appc, 'snid_results', None)) if appc else False

                    if preprocessed_present or analysis_present:
                        reply = QtWidgets.QMessageBox.question(
                            gui_instance,
                            "Redo Preprocessing?",
                            (
                                "You are about to redo preprocessing.\n\n"
                                "This will clear previous preprocessing, analysis results, overlays, and advanced views.\n"
                                "The loaded spectrum will be kept, and the GUI will return to the preprocessing stage.\n\n"
                                "Do you want to continue?"
                            ),
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            QtWidgets.QMessageBox.No
                        )
                        if reply != QtWidgets.QMessageBox.Yes:
                            return
                        # Reset to FILE_LOADED while preserving spectrum
                        if hasattr(appc, 'reset_to_file_loaded_state'):
                            appc.reset_to_file_loaded_state()
                        # Update labels and plot to flux without overlays
                        if hasattr(gui_instance, 'preprocess_status_label'):
                            gui_instance.preprocess_status_label.setText("Preprocessing not run")
                            gui_instance.preprocess_status_label.setStyleSheet(
                                "font-style: italic; color: #475569; font-size: 10px !important; "
                                "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                                "line-height: 1.0 !important;"
                            )
                        # Reset configuration/analysis status label so it does not show 'Analysis Complete'
                        if hasattr(gui_instance, 'config_status_label'):
                            gui_instance.config_status_label.setText("Default SNID parameters loaded")
                            gui_instance.config_status_label.setStyleSheet(
                                "font-style: italic; color: #475569; font-size: 10px !important; "
                                "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                                "line-height: 1.0 !important;"
                            )
                        if hasattr(gui_instance, 'status_label'):
                            gui_instance.status_label.setText("Spectrum loaded - ready to preprocess")
                        # Ensure spectrum plot without overlays in Flux view
                        if hasattr(gui_instance, 'event_handlers'):
                            gui_instance.event_handlers.on_view_change('flux')
                        if hasattr(gui_instance, 'plot_manager'):
                            gui_instance.plot_manager.plot_spectrum('flux')

                    # Run quick preprocessing
                    if hasattr(gui_instance, 'preprocessing_controller') and hasattr(gui_instance.preprocessing_controller, 'run_quick_preprocessing'):
                        gui_instance.preprocessing_controller.run_quick_preprocessing()
                    else:
                        _LOGGER.info("Quick preprocessing not available")
                except Exception as e:
                    _LOGGER.warning(f"Right-click preprocessing handler error: {e}")
            else:
                # Call the original mousePressEvent for normal button behavior
                QtWidgets.QPushButton.mousePressEvent(gui_instance.preprocessing_btn, event)
        
        gui_instance.preprocessing_btn.mousePressEvent = preprocessing_context_menu
        # Get platform-appropriate click text
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text("right")
        
        gui_instance.preprocessing_btn.setToolTip(f"Left-click: Open preprocessing dialog\n{right_click_text}: Quick preprocessing with default settings")
        layout.addWidget(gui_instance.preprocessing_btn)
        
        # Preprocessing status label - add with reduced spacing
        gui_instance.preprocess_status_label = QtWidgets.QLabel("Preprocessing not run")
        gui_instance.preprocess_status_label.setObjectName("unified_preprocess_status_label")
        gui_instance.preprocess_status_label.setWordWrap(True)
        gui_instance.preprocess_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important; margin-top: 0px;")
        self._apply_size_setting(gui_instance.preprocess_status_label, "setMaximumHeight", 25, "preprocess_status_label")
        layout.addWidget(gui_instance.preprocess_status_label)
        layout.addSpacing(1)  # Reduced spacing after status label
    
    def _create_galaxy_analysis_section(self, gui_instance, layout):
        """Create Host Redshift section"""
        # Create redshift selection button (matching original interface)
        gui_instance.redshift_selection_btn = QtWidgets.QPushButton("Host Redshift")
        gui_instance.redshift_selection_btn.setObjectName("unified_redshift_selection_btn")

        if hasattr(gui_instance, 'open_manual_redshift_dialog'):
            gui_instance.redshift_selection_btn.clicked.connect(gui_instance.open_manual_redshift_dialog)
        elif hasattr(gui_instance, 'open_redshift_dialog'):
            gui_instance.redshift_selection_btn.clicked.connect(gui_instance.open_redshift_dialog)
        else:
            gui_instance.redshift_selection_btn.clicked.connect(lambda: _LOGGER.info("Redshift dialog not available"))
        gui_instance.redshift_selection_btn.setToolTip("Redshift analysis and host-galaxy subtraction\nDetermine redshift manually or automatically")
        layout.addWidget(gui_instance.redshift_selection_btn)
        
        # Galaxy/redshift status label - add with reduced spacing
        gui_instance.redshift_status_label = QtWidgets.QLabel("Redshift not set (optional)")
        gui_instance.redshift_status_label.setObjectName("unified_redshift_status_label")
        gui_instance.redshift_status_label.setWordWrap(True)
        gui_instance.redshift_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important; margin-top: 0px;")
        self._apply_size_setting(gui_instance.redshift_status_label, "setMaximumHeight", 25, "redshift_status_label")
        layout.addWidget(gui_instance.redshift_status_label)
        layout.addSpacing(1)  # Reduced spacing after status label
        
        # Keep alias for compatibility
        gui_instance.galaxy_analysis_btn = gui_instance.redshift_selection_btn
    
    def _create_configuration_section(self, gui_instance, layout):
        """Create Configuration section"""
        gui_instance.analysis_btn = QtWidgets.QPushButton("Run Analysis")
        gui_instance.analysis_btn.setObjectName("unified_analysis_btn")

        
        # Set up left-click functionality
        if hasattr(gui_instance, 'open_snid_analysis_dialog'):
            gui_instance.analysis_btn.clicked.connect(gui_instance.open_snid_analysis_dialog)
        elif hasattr(gui_instance, 'run_analysis'):
            gui_instance.analysis_btn.clicked.connect(gui_instance.run_analysis)
        else:
            gui_instance.analysis_btn.clicked.connect(lambda: _LOGGER.info("Analysis dialog not available"))
        
        # Add right-click functionality for quick analysis
        def analysis_context_menu(event):
            if event.button() == QtCore.Qt.RightButton:
                # Preserve quick analysis behavior on right-click
                # but still ensure the re-run confirmation if analysis already exists
                try:
                    # Simulate quick visual press feedback on right-click
                    try:
                        gui_instance.analysis_btn.setDown(True)
                        # Flush UI so the pressed state is visible immediately
                        app = QtCore.QCoreApplication.instance()
                        if app and not app.closingDown():
                            QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                        QtCore.QTimer.singleShot(120, lambda: gui_instance.analysis_btn.setDown(False))
                    except Exception:
                        pass

                    appc = getattr(gui_instance, 'app_controller', None)
                    has_results = bool(getattr(appc, 'snid_results', None)) if appc else False
                    if has_results and hasattr(gui_instance, 'event_handlers'):
                        # Reuse confirmation + reset logic from event handler
                        gui_instance.event_handlers.on_run_analysis()
                    elif hasattr(gui_instance, 'run_quick_analysis'):
                        gui_instance.run_quick_analysis()
                    else:
                        _LOGGER.info("Quick analysis not available")
                except Exception as e:
                    _LOGGER.warning(f"Right-click analysis handler error: {e}")
            else:
                # Call the original mousePressEvent for normal button behavior
                QtWidgets.QPushButton.mousePressEvent(gui_instance.analysis_btn, event)
        
        gui_instance.analysis_btn.mousePressEvent = analysis_context_menu
        # Get platform-appropriate click text
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text("right")
        
        gui_instance.analysis_btn.setToolTip(f"Left-click: Open analysis dialog\n{right_click_text}: Quick analysis with default settings")
        layout.addWidget(gui_instance.analysis_btn)
        
        # Configuration status label - add with reduced spacing
        gui_instance.config_status_label = QtWidgets.QLabel("Default SNID parameters loaded")
        gui_instance.config_status_label.setObjectName("unified_config_status_label")
        gui_instance.config_status_label.setWordWrap(True)
        gui_instance.config_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important; margin-top: 0px;")
        self._apply_size_setting(gui_instance.config_status_label, "setMaximumHeight", 25, "config_status_label")
        layout.addWidget(gui_instance.config_status_label)
        layout.addSpacing(1)  # Reduced spacing after status label
    
    def _create_emission_line_section(self, gui_instance, layout):
        """Create Emission Line section"""
        _LOGGER.info("🔬 Creating emission line section...")
        
        # Create emission line overlay button (matching original interface)
        gui_instance.emission_line_overlay_btn = QtWidgets.QPushButton("Spectral Lines")
        gui_instance.emission_line_overlay_btn.setObjectName("unified_emission_line_overlay_btn")

        _LOGGER.info("🔧 Checking available emission line dialog methods...")
        if hasattr(gui_instance, 'open_emission_lines_dialog'):
            _LOGGER.info("✅ Found open_emission_lines_dialog method - connecting")
            gui_instance.emission_line_overlay_btn.clicked.connect(gui_instance.open_emission_lines_dialog)
        elif hasattr(gui_instance, 'open_emission_line_dialog'):
            _LOGGER.info("✅ Found open_emission_line_dialog method - connecting")
            gui_instance.emission_line_overlay_btn.clicked.connect(gui_instance.open_emission_line_dialog)
        else:
            _LOGGER.warning("⚠️ No emission line dialog method found - using fallback")
            gui_instance.emission_line_overlay_btn.clicked.connect(lambda: _LOGGER.info("Emission lines dialog not available"))
        
        gui_instance.emission_line_overlay_btn.setEnabled(False)  # Initially disabled
        gui_instance.emission_line_overlay_btn.setToolTip("Interactive spectral line analysis\nIdentify and analyze supernova and galaxy lines\nRedshift verification and P-Cygni profile analysis\n(Available after loading spectrum)")
        layout.addWidget(gui_instance.emission_line_overlay_btn)
        _LOGGER.info("✅ Emission line button created and connected")
        
        # Emission lines status label - add with reduced spacing
        gui_instance.emission_status_label = QtWidgets.QLabel("Run analysis to enable")
        gui_instance.emission_status_label.setObjectName("unified_emission_status_label")
        gui_instance.emission_status_label.setWordWrap(True)
        gui_instance.emission_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important; margin-top: 0px;")
        self._apply_size_setting(gui_instance.emission_status_label, "setMaximumHeight", 25, "emission_status_label")
        layout.addWidget(gui_instance.emission_status_label)
        layout.addSpacing(1)  # Reduced spacing after status label
        
        # Keep alias for compatibility
        gui_instance.emission_lines_btn = gui_instance.emission_line_overlay_btn
    
    def _create_chat_section(self, gui_instance, layout):
        """Create Chat section"""
        
        gui_instance.ai_assistant_btn = QtWidgets.QPushButton("AI Assistant")
        gui_instance.ai_assistant_btn.setObjectName("unified_ai_assistant_btn")

        if hasattr(gui_instance, 'open_ai_assistant_dialog'):
            gui_instance.ai_assistant_btn.clicked.connect(gui_instance.open_ai_assistant_dialog)
        elif hasattr(gui_instance, 'open_chat_dialog'):
            gui_instance.ai_assistant_btn.clicked.connect(gui_instance.open_chat_dialog)
        else:
            gui_instance.ai_assistant_btn.clicked.connect(lambda: _LOGGER.info("AI Assistant dialog not available"))
        gui_instance.ai_assistant_btn.setEnabled(False)  # Initially disabled
        gui_instance.ai_assistant_btn.setToolTip("AI-powered analysis assistant\nGet help interpreting classification results\n(Available after analysis)")
        layout.addWidget(gui_instance.ai_assistant_btn)
        
        
        gui_instance.ai_status_label = QtWidgets.QLabel("Run analysis to enable")
        gui_instance.ai_status_label.setObjectName("unified_ai_status_label")
        gui_instance.ai_status_label.setWordWrap(True)
        gui_instance.ai_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important; margin-top: 0px;")
        self._apply_size_setting(gui_instance.ai_status_label, "setMaximumHeight", 25, "ai_status_label")
        layout.addWidget(gui_instance.ai_status_label)
        layout.addSpacing(1)  # Reduced spacing after status label
        
        # Keep alias for compatibility  
        gui_instance.chat_btn = gui_instance.ai_assistant_btn
    
    def _create_settings_section(self, gui_instance, layout):
        """Create Settings section"""
        # Create horizontal container for settings and reset buttons
        settings_container = QtWidgets.QWidget()
        settings_layout = QtWidgets.QHBoxLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(3)  # Small spacing between buttons
        
        # Settings button - smaller size and font
        gui_instance.settings_btn = QtWidgets.QPushButton("Settings")
        gui_instance.settings_btn.setObjectName("unified_settings_btn")
        self._apply_size_setting(gui_instance.settings_btn, "setMaximumHeight", 40, "settings_btn")  # Further increased height to prevent cutting
        gui_instance.settings_btn.setStyleSheet("font-size: 9pt; font-weight: bold; max-width: 100px; min-width: 80px; padding: 2px;")  # Added padding for better spacing
        gui_instance.settings_btn.clicked.connect(gui_instance.open_settings_dialog)
        gui_instance.settings_btn.setToolTip("Open application settings\nConfigure GUI preferences and analysis defaults")
        settings_layout.addWidget(gui_instance.settings_btn)
        
        # Reset button - smaller size and font
        gui_instance.reset_btn = QtWidgets.QPushButton("Reset")
        gui_instance.reset_btn.setObjectName("unified_reset_btn")
        self._apply_size_setting(gui_instance.reset_btn, "setMaximumHeight", 40, "reset_btn")  # Further increased height to prevent cutting
        gui_instance.reset_btn.setStyleSheet("font-size: 9pt; font-weight: bold; max-width: 100px; min-width: 80px; padding: 2px;")  # Added padding for better spacing
        gui_instance.reset_btn.clicked.connect(gui_instance.reset_to_initial_state)
        gui_instance.reset_btn.setToolTip("Reset to initial state\nClears all loaded data and analysis results")
        settings_layout.addWidget(gui_instance.reset_btn)
        
        # Add the horizontal container to the main layout
        layout.addWidget(settings_container)
    
    def _create_view_controls(self, gui_instance, layout):
        """Create view toggle controls (Flux/Flat)"""
        _LOGGER.info("🔧 CREATING VIEW CONTROLS: Starting Flux/Flat button creation")
        
        # View controls container with white background
        view_container = QtWidgets.QWidget()
        view_container.setStyleSheet("background-color: white;")
        view_layout = QtWidgets.QHBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(5)
        
        # Flux button - CRITICAL: Start disabled until spectrum is loaded
        gui_instance.flux_btn = QtWidgets.QPushButton("Flux")
        gui_instance.flux_btn.setObjectName("flux_btn")
        gui_instance.flux_btn.setCheckable(True)
        gui_instance.flux_btn.setChecked(False)  # Start unchecked
        gui_instance.flux_btn.setEnabled(False)  # Start disabled until spectrum loaded
        
        self._apply_button_size(gui_instance.flux_btn, 'small', 'flux_btn')
        
        gui_instance.flux_btn.clicked.connect(lambda: gui_instance._on_view_change('flux'))
        gui_instance.flux_btn.setToolTip("Flux view requires spectrum\nLoad a spectrum file first")
        view_layout.addWidget(gui_instance.flux_btn)
        
        # Flat button
        gui_instance.flat_btn = QtWidgets.QPushButton("Flat")
        gui_instance.flat_btn.setObjectName("flat_btn")
        gui_instance.flat_btn.setCheckable(True)
        gui_instance.flat_btn.setChecked(False)  # Start unchecked
        gui_instance.flat_btn.setEnabled(False)  # Start disabled until preprocessing
        
        self._apply_button_size(gui_instance.flat_btn, 'small', 'flat_btn')
        
        gui_instance.flat_btn.clicked.connect(lambda: gui_instance._on_view_change('flat'))
        gui_instance.flat_btn.setToolTip("Flat view requires preprocessing\nLoad a spectrum and run preprocessing first")
        view_layout.addWidget(gui_instance.flat_btn)
        
        layout.addWidget(view_container)
    
    def _create_navigation_controls(self, gui_instance, layout):
        """Create navigation controls (left/right arrows only)"""
        # Navigation container with white background
        nav_container = QtWidgets.QWidget()
        nav_container.setStyleSheet("background-color: white;")
        nav_layout = QtWidgets.QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(5)  # Slightly more spacing between left/right arrows
        
        # Left arrow button
        prev_button = QtWidgets.QPushButton("◀")
        prev_button.setObjectName("unified_prev_btn")
        prev_button.setEnabled(False)
        self._apply_button_size(prev_button, 'small', 'prev_btn')
        prev_button.setToolTip("Previous template\nNavigate to the previous matching template")
        if hasattr(gui_instance, 'show_previous_template'):
            prev_button.clicked.connect(getattr(gui_instance, 'show_previous_template'))
        setattr(gui_instance, 'prev_btn', prev_button)
        nav_layout.addWidget(prev_button)
        
        # Right arrow button
        next_button = QtWidgets.QPushButton("▶")
        next_button.setObjectName("unified_next_btn")
        next_button.setEnabled(False)
        self._apply_button_size(next_button, 'small', 'next_btn')
        next_button.setToolTip("Next template\nNavigate to the next matching template")
        if hasattr(gui_instance, 'show_next_template'):
            next_button.clicked.connect(getattr(gui_instance, 'show_next_template'))
        setattr(gui_instance, 'next_btn', next_button)
        nav_layout.addWidget(next_button)
        
        layout.addWidget(nav_container)
    
    def _create_analysis_controls(self, gui_instance, layout):
        """Create analysis plot controls"""
        # Analysis container with white background
        analysis_container = QtWidgets.QWidget()
        analysis_container.setStyleSheet("background-color: white;")
        analysis_layout = QtWidgets.QHBoxLayout(analysis_container)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(5)
        
        # Analysis buttons with tooltips and larger emoji font size
        analysis_buttons = [
            ("📋", "cluster_summary_btn", "show_cluster_summary", "Cluster Summary\nView detailed statistics of template matches"),
            ("🎯", "gmm_btn", "show_gmm_clusters", "GMM Clustering\nView Gaussian Mixture Model clustering results"),
            ("📈", "redshift_age_btn", "show_redshift_vs_age", "Redshift vs Age\nPlot redshift correlation with template age"),
            ("🍰", "subtype_proportions_btn", "show_subtype_proportions", "Subtype Proportions\nView pie chart of SN subtype distribution")
        ]
        
        for text, attr_name, method_name, tooltip in analysis_buttons:
            button = QtWidgets.QPushButton(text)
            button.setObjectName(f"unified_{attr_name}")
            button.setEnabled(False)
            self._apply_button_size(button, 'small', attr_name)
            button.setToolTip(tooltip)
            
            # Increase emoji size for specific buttons - use object properties instead of inline styles
            # This allows the CSS theme manager hover effects to work properly
            if attr_name in ['gmm_btn', 'redshift_age_btn', 'subtype_proportions_btn']:
                button.setProperty("emoji_size", "large")  # 14pt
            else:
                button.setProperty("emoji_size", "medium")  # 12pt
            
            # Connect to method if it exists
            if hasattr(gui_instance, method_name):
                button.clicked.connect(getattr(gui_instance, method_name))
            
            setattr(gui_instance, attr_name, button)
            analysis_layout.addWidget(button)
        
        layout.addWidget(analysis_container)
    
    # === BUTTON STYLING METHODS ===
    
    def apply_flux_flat_button_styles(self, gui_instance):
        """Apply proper styling to Flux/Flat buttons"""
        _LOGGER.info("🎨 LAYOUT MANAGER: Applying Flux/Flat button styles...")
        
        if not hasattr(gui_instance, 'flux_btn') or not hasattr(gui_instance, 'flat_btn'):
            _LOGGER.warning("🎨 LAYOUT MANAGER: Flux/Flat buttons not found!")
            return
        
        # Flux button styling
        flux_inactive_style = """
        QPushButton {
            background-color: #f1f5f9 !important;
            border: 2px solid #cbd5e1 !important;
            color: #475569 !important;
            border-radius: 4px !important;
            font-weight: bold !important;
            font-size: 9pt !important;
            padding: 4px 8px !important;
            min-height: 24px !important;
        }
        QPushButton:hover {
            background-color: #e2e8f0 !important;
            border-color: #94a3b8 !important;
        }
        QPushButton:pressed {
            background-color: #d1d5db !important;
            border-color: #9ca3af !important;
        }
        QPushButton:focus {
            outline: none !important;
        }
        """
        
        flux_active_style = """
        QPushButton {
            background-color: #3b82f6 !important;
            border: 2px solid #2563eb !important;
            color: white !important;
            border-radius: 4px !important;
            font-weight: bold !important;
            font-size: 9pt !important;
            padding: 4px 8px !important;
            min-height: 24px !important;
        }
        QPushButton:hover {
            background-color: #2563eb !important;
        }
        QPushButton:pressed {
            background-color: #1d4ed8 !important;
            border-color: #1e40af !important;
        }
        QPushButton:focus {
            outline: none !important;
        }
        """
        
        flat_inactive_style = """
        QPushButton {
            background-color: #f1f5f9 !important;
            border: 2px solid #cbd5e1 !important;
            color: #475569 !important;
            border-radius: 4px !important;
            font-weight: bold !important;
            font-size: 9pt !important;
            padding: 4px 8px !important;
            min-height: 24px !important;
        }
        QPushButton:hover {
            background-color: #e2e8f0 !important;
            border-color: #94a3b8 !important;
        }
        QPushButton:pressed {
            background-color: #d1d5db !important;
            border-color: #9ca3af !important;
        }
        QPushButton:focus {
            outline: none !important;
        }
        """
        
        flat_active_style = """
        QPushButton {
            background-color: #3b82f6 !important;
            border: 2px solid #2563eb !important;
            color: white !important;
            border-radius: 4px !important;
            font-weight: bold !important;
            font-size: 9pt !important;
            padding: 4px 8px !important;
            min-height: 24px !important;
        }
        QPushButton:hover {
            background-color: #2563eb !important;
        }
        QPushButton:pressed {
            background-color: #1d4ed8 !important;
            border-color: #1e40af !important;
        }
        QPushButton:focus {
            outline: none !important;
        }
        """
        
        # Apply initial inactive styles
        gui_instance.flux_btn.setStyleSheet(flux_inactive_style)
        gui_instance.flat_btn.setStyleSheet(flat_inactive_style)
        
        # Store styles as instance variables for later use
        gui_instance._flux_active_style = flux_active_style
        gui_instance._flux_inactive_style = flux_inactive_style
        gui_instance._flat_active_style = flat_active_style
        gui_instance._flat_inactive_style = flat_inactive_style
        
        _LOGGER.info("🎨 LAYOUT MANAGER: Flux/Flat button styles applied successfully")
    
    def update_flux_flat_button_states(self, gui_instance, flux_active=False, flat_active=False, flux_enabled=True, flat_enabled=True):
        """Update Flux/Flat button states and styling"""
        _LOGGER.info(f"🎨 BUTTON STATES: Updating flux_active={flux_active}, flat_active={flat_active}, flux_enabled={flux_enabled}, flat_enabled={flat_enabled}")
        
        if not hasattr(gui_instance, 'flux_btn') or not hasattr(gui_instance, 'flat_btn'):
            _LOGGER.warning("🎨 BUTTON STATES: Flux/Flat buttons not found!")
            return
        
        # CRITICAL: Ensure style variables are available - if not, apply them first
        if not hasattr(gui_instance, '_flux_active_style') or not hasattr(gui_instance, '_flux_inactive_style'):
            _LOGGER.warning("🎨 BUTTON STATES: Style variables not found - applying styles first")
            self.apply_flux_flat_button_styles(gui_instance)
        
        # Update enabled states
        gui_instance.flux_btn.setEnabled(flux_enabled)
        gui_instance.flat_btn.setEnabled(flat_enabled)
        
        # Update checked states
        gui_instance.flux_btn.setChecked(flux_active)
        gui_instance.flat_btn.setChecked(flat_active)
        
        # Update tooltips based on state
        if flux_enabled:
            gui_instance.flux_btn.setToolTip("Show flux spectrum\nClick to switch to flux view")
        else:
            gui_instance.flux_btn.setToolTip("Flux view requires spectrum\nLoad a spectrum file first")
        
        if flat_enabled:
            gui_instance.flat_btn.setToolTip("Show flattened spectrum\nClick to switch to flat view")
        else:
            gui_instance.flat_btn.setToolTip("Flat view requires preprocessing\nLoad a spectrum and run preprocessing first")
        
        # Apply appropriate styles
        if hasattr(gui_instance, '_flux_active_style'):
            if flux_active:
                gui_instance.flux_btn.setStyleSheet(gui_instance._flux_active_style)
                _LOGGER.info("🎨 BUTTON STATES: Applied ACTIVE style to Flux button")
            else:
                gui_instance.flux_btn.setStyleSheet(gui_instance._flux_inactive_style)
                _LOGGER.info("🎨 BUTTON STATES: Applied INACTIVE style to Flux button")
        else:
            _LOGGER.error("🚨 BUTTON STATES: _flux_active_style not found even after applying styles!")
        
        if hasattr(gui_instance, '_flat_active_style'):
            if flat_active:
                gui_instance.flat_btn.setStyleSheet(gui_instance._flat_active_style)
                _LOGGER.info("🎨 BUTTON STATES: Applied ACTIVE style to Flat button")
            else:
                gui_instance.flat_btn.setStyleSheet(gui_instance._flat_inactive_style)
                _LOGGER.info("🎨 BUTTON STATES: Applied INACTIVE style to Flat button")
        else:
            _LOGGER.error("🚨 BUTTON STATES: _flat_active_style not found even after applying styles!")
        
        # CRITICAL: Force immediate visual update after style changes
        # This ensures the button appearance changes immediately
        gui_instance.flux_btn.repaint()
        gui_instance.flat_btn.repaint()
        
        # Force a repaint of the parent widget to ensure changes are visible
        if gui_instance.flux_btn.parent():
            gui_instance.flux_btn.parent().repaint()
        
        # Process any pending events to ensure visual changes are applied immediately
        # Use a safer approach to avoid Qt window activation warnings
        from PySide6 import QtCore
        try:
            # Only process events if we have an active application instance
            app = QtCore.QCoreApplication.instance()
            if app and not app.closingDown():
                QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except Exception:
            # If processEvents fails, skip it - the visual update will happen anyway
            pass
        
        _LOGGER.info("🎨 BUTTON STATES: Visual update forced to ensure immediate appearance changes")
    
    def enable_twemoji_icons(self, gui_instance, icon_size: int = 16) -> int:
        """
        Enable Twemoji icons for all emoji-containing buttons in the GUI.
        
        This method converts all buttons that contain emojis to use Twemoji SVG icons
        instead of text emojis, providing consistent rendering across all platforms.
        
        Args:
            gui_instance: The main GUI instance
            icon_size: Size in pixels for the icons (default 16)
            
        Returns:
            Number of buttons successfully converted
        """
        if not TWEMOJI_AVAILABLE:
            _LOGGER.warning("Twemoji manager not available - keeping text emojis")
            return 0
        
        try:
            # Get Twemoji manager
            twemoji_manager = get_twemoji_manager(icon_size=icon_size)
            if not twemoji_manager:
                _LOGGER.warning("Could not initialize Twemoji manager")
                return 0
            
            # Preload common icons for better performance without blocking the UI
            # Schedule on idle and run the preload in a background thread
            _LOGGER.info("Scheduling background preload of common Twemoji assets...")
            try:
                from PySide6 import QtCore
                import threading

                def _background_preload():
                    try:
                        count = twemoji_manager.preload_common_icons()
                        _LOGGER.debug(f"Background Twemoji preload completed: {count} assets")
                    except Exception as exc:
                        _LOGGER.debug(f"Background Twemoji preload skipped/failed: {exc}")

                QtCore.QTimer.singleShot(0, lambda: threading.Thread(target=_background_preload, daemon=True).start())
            except Exception:
                # Fall back silently if scheduling fails (e.g., during headless tests)
                pass
            
            # Convert all buttons in the main window
            _LOGGER.info("Converting buttons to use Twemoji icons...")
            converted = twemoji_manager.convert_all_buttons(gui_instance)

            
            if converted > 0:
                _LOGGER.info(f"✅ Twemoji applied - buttons converted: {converted}")
            else:
                _LOGGER.info("No buttons found that need Twemoji conversion")
            
            return converted
            
        except Exception as e:
            _LOGGER.error(f"Failed to enable Twemoji icons: {e}")
            return 0


# === CONVENIENCE FUNCTIONS ===

def get_unified_layout_manager(settings: Optional[LayoutSettings] = None) -> UnifiedPySide6LayoutManager:
    """Get a unified layout manager instance"""
    return UnifiedPySide6LayoutManager(settings)

def create_default_settings() -> LayoutSettings:
    """Create default layout settings"""
    return LayoutSettings() 