"""
SNID SAGE - PySide6 Modern GUI Interface
========================================

Modern PySide6-based GUI for SNID SAGE.

Features:
- High-DPI scaling support
- Consistent cross-platform appearance using Fusion style
- PyQtGraph integration for high-performance plotting
- Complete workflow system with proper button state management
- Interactive masking and spectrum analysis tools
- Modern Qt widgets and layouts
- Unified theming system adapted for Qt

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import os
import sys

import json
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
import time
import threading
from enum import Enum

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

# Plot mode enumeration
class PlotMode(Enum):
    SPECTRUM = "spectrum"           # PyQtGraph spectrum/template overlays
    REDSHIFT_AGE = "redshift_age"   # Matplotlib redshift vs age plot
    SUBTYPE_PROPS = "subtype_props" # Matplotlib subtype proportions plot

# PyQtGraph for high-performance plotting
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None

# Matplotlib for analysis plots (Qt helper)
try:
    from snid_sage.interfaces.gui.utils.matplotlib_qt import get_qt_mpl
    plt, Figure, FigureCanvas, _NavigationToolbar = get_qt_mpl()
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FigureCanvas = None
    Figure = None

# SNID SAGE imports
try:
    from snid_sage import __version__
except ImportError:
    __version__ = "unknown"

# Import core SNID functionality
from snid_sage.snid.snid import run_snid as python_snid, preprocess_spectrum, run_snid_analysis

# Import configuration and utilities
from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
from snid_sage.shared.utils.config.platform_config import get_platform_config

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6')


class WorkflowState(Enum):
    """Workflow state enumeration"""
    INITIAL = "initial"
    FILE_LOADED = "file_loaded"
    PREPROCESSED = "preprocessed"
    ANALYSIS_COMPLETE = "analysis_complete"


class PySide6SNIDSageGUI(QtWidgets.QMainWindow):
    """
    PySide6-based GUI for SNID SAGE.
    """
    
    def __init__(self, profile_id: Optional[str] = None):
        """Initialize the PySide6 SNID SAGE GUI"""
        super().__init__()
        # Persist launcher-provided profile for this GUI session (CLI-only; ignore config/env)
        try:
            self.launch_profile_id = (str(profile_id).strip().lower() if profile_id else 'optical')
        except Exception:
            self.launch_profile_id = 'optical'
        
        # Initialize controllers and managers first
        self._init_controllers_and_managers()
        
        # Setup window properties
        self._setup_window_properties()
        
        # Initialize theme colors
        self._init_theme_colors()
        
        # Create the interface
        self._create_interface()
        
        # Initialize variables and state
        self._init_variables_and_state()
        
        
        _LOGGER.info("🔍 BEFORE STYLESHEET: Checking button states...")
        if hasattr(self, 'flux_btn'):
            _LOGGER.info(f"🔍 FLUX BUTTON: size={self.flux_btn.size()}, minimumSize={self.flux_btn.minimumSize()}, enabled={self.flux_btn.isEnabled()}, checked={self.flux_btn.isChecked()}")
        if hasattr(self, 'flat_btn'):
            _LOGGER.info(f"🔍 FLAT BUTTON: size={self.flat_btn.size()}, minimumSize={self.flat_btn.minimumSize()}, enabled={self.flat_btn.isEnabled()}, checked={self.flat_btn.isChecked()}")
        
        
        _LOGGER.info("🎨 APPLYING STYLESHEET: About to apply main stylesheet...")
        self._apply_qt_stylesheet()
        
        
        _LOGGER.info("🎨 APPLYING BUTTON STYLES: Delegating to layout manager...")
        self.unified_layout_manager.apply_flux_flat_button_styles(self)
        
        
        _LOGGER.info("🔍 AFTER STYLESHEET: Checking button states...")
        if hasattr(self, 'flux_btn'):
            _LOGGER.info(f"🔍 FLUX BUTTON: size={self.flux_btn.size()}, minimumSize={self.flux_btn.minimumSize()}, enabled={self.flux_btn.isEnabled()}, checked={self.flux_btn.isChecked()}")
        if hasattr(self, 'flat_btn'):
            _LOGGER.info(f"🔍 FLAT BUTTON: size={self.flat_btn.size()}, minimumSize={self.flat_btn.minimumSize()}, enabled={self.flat_btn.isEnabled()}, checked={self.flat_btn.isChecked()}")
        
        # Enable Twemoji icons for consistent emoji rendering across platforms
        _LOGGER.info("🎨 ENABLING TWEMOJI: Converting emoji buttons to use Twemoji icons...")
        try:
            converted_count = self.unified_layout_manager.enable_twemoji_icons(self, icon_size=16)
            if converted_count > 0:
                _LOGGER.info(f"TWEMOJI SUCCESS: Converted {converted_count} buttons to use Twemoji icons")
            else:
                _LOGGER.info("ℹ️ TWEMOJI: No emoji buttons found to convert")
        except Exception as e:
            _LOGGER.warning(f"⚠️ TWEMOJI FAILED: Could not enable Twemoji icons: {e}")
        
        # Setup plotting - both PyQtGraph and matplotlib
        self._init_dual_plot_system()
        
        # Initialize workflow system
        self._init_workflow_system()
        
        # Initialize event handlers
        self._init_event_handlers()
        
        # Initialize analysis menu manager
        self._init_analysis_menu_manager()

        # Ensure ESC never closes result dialogs. ESC is reserved for closing the mini-game only.
        self._install_escape_key_filter()
        
        _LOGGER.info("PySide6 SNID SAGE GUI initialized successfully")

    def _install_escape_key_filter(self) -> None:
        """Install a global filter so ESC only closes the game window."""
        try:
            app = QtWidgets.QApplication.instance()
            if app is None:
                return
            if getattr(app, "_snid_sage_escape_filter_installed", False):
                return

            class _EscapeToGameFilter(QtCore.QObject):
                def eventFilter(self, obj, event):  # type: ignore[override]
                    try:
                        if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
                            try:
                                from snid_sage.snid.games import close_game, is_game_running
                                if is_game_running():
                                    close_game()
                            except Exception:
                                pass
                            # Always consume ESC so dialogs/results windows don't close unexpectedly.
                            return True
                    except Exception:
                        pass
                    return False

            app._snid_sage_escape_filter = _EscapeToGameFilter(app)  # type: ignore[attr-defined]
            app.installEventFilter(app._snid_sage_escape_filter)  # type: ignore[attr-defined]
            app._snid_sage_escape_filter_installed = True  # type: ignore[attr-defined]
        except Exception:
            pass
    
    def _init_controllers_and_managers(self):
        """Initialize controllers and managers"""
        # Set environment variable early to prevent backend conflicts
        os.environ['SNID_SAGE_GUI_BACKEND'] = 'PySide6'
        
        # Import controllers
        from snid_sage.interfaces.gui.controllers.pyside6_app_controller import PySide6AppController
        from snid_sage.interfaces.gui.utils.pyside6_workflow_manager import PySide6WorkflowManager
        
        # Initialize application controller with the active profile for this session
        self.app_controller = PySide6AppController(self, profile_id=self.launch_profile_id)
        
        # Connect app controller signals for GUI updates
        self.app_controller.analysis_completed.connect(self._on_analysis_completed)
        self.app_controller.preprocessing_completed.connect(self._on_preprocessing_completed)
        self.app_controller.workflow_state_changed.connect(self._on_workflow_state_changed)
        # Keep connection for any code still emitting unordered updates
        self.app_controller.progress_updated.connect(self._on_progress_updated)
        # Consume strictly ordered progress messages
        if hasattr(self.app_controller, 'ordered_progress_updated'):
            self.app_controller.ordered_progress_updated.connect(self._on_ordered_progress_updated)
        self.app_controller.cluster_selection_needed.connect(self._on_cluster_selection_needed)
        
        # Initialize workflow manager
        self.workflow_manager = PySide6WorkflowManager(self)
        
        # Initialize preprocessing controller
        from snid_sage.interfaces.gui.controllers.pyside6_preprocessing_controller import PySide6PreprocessingController
        self.preprocessing_controller = PySide6PreprocessingController(self)
        
        # Initialize dialog manager
        from snid_sage.interfaces.gui.components.pyside6_dialogs.dialog_manager import DialogManager
        self.dialog_manager = DialogManager(self)
        
        # Interactive state
        self.masking_enabled = False
        self.line_markers = []
        self.progress_dialog = None  # Track progress dialog
        # Stable stage label for the progress bar (avoid flicker)
        self._current_progress_stage = "Initialization"
        
        # Get platform config from app controller
        self.platform_config = self.app_controller.platform_config
        
        _LOGGER.debug("Controllers and managers initialized")
    
    def _init_dual_plot_system(self):
        """Initialize dual plot system using the dedicated plot manager"""
        try:
            # Import and initialize the dedicated plot manager
            from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PySide6PlotManager
            
            self.plot_manager = PySide6PlotManager(self, self.plot_layout)
            
            # Set theme colors for plots
            self.plot_manager.set_theme_colors(self.theme_colors)
            
            _LOGGER.debug("Dual plot system initialized successfully using plot manager")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing dual plot system: {e}")
            # Create fallback label
            fallback_label = QtWidgets.QLabel(
                "Plot system not available\n\nPlease check PyQtGraph installation"
            )
            fallback_label.setAlignment(QtCore.Qt.AlignCenter)
            fallback_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 12pt;")
            self.plot_layout.addWidget(fallback_label)
    
    # Obsolete matplotlib initialization - handled by plot manager
    
    def _switch_to_plot_mode(self, plot_mode):
        """Switch to the specified plot mode - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                self.plot_manager.switch_to_plot_mode(plot_mode)
        except Exception as e:
            _LOGGER.error(f"Error switching to plot mode {plot_mode}: {e}")
    
    def _create_redshift_age_plot(self):
        """Create redshift vs age plot - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager') and self.plot_manager:
                self.plot_manager.create_redshift_age_plot()
        except Exception as e:
            _LOGGER.error(f"Error creating redshift vs age plot: {e}")
    
    def _create_subtype_proportions_plot(self):
        """Create subtype proportions plot - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager') and self.plot_manager:
                self.plot_manager.create_subtype_proportions_plot()
        except Exception as e:
            _LOGGER.error(f"Error creating subtype proportions plot: {e}")
    

    

    
    def _show_matplotlib_error(self, error_msg):
        """Show error message in matplotlib plot area"""
        try:
            if hasattr(self, 'matplotlib_figure'):
                self.matplotlib_figure.clear()
                ax = self.matplotlib_figure.add_subplot(111)
                ax.text(0.5, 0.5, error_msg, ha='center', va='center', 
                       transform=ax.transAxes, fontsize=12, color='red')
                ax.set_title('Plot Error', fontsize=14, fontweight='bold', color='red')
                ax.axis('off')
                self.matplotlib_canvas.draw()
        except Exception as e:
            _LOGGER.error(f"Error showing matplotlib error: {e}")
    
    # Parameter parsing methods (required by analysis controller)
    def _parse_template_filter(self):
        """Parse template filter from parameters (compatibility with earlier configs)."""
        try:
            # For PySide6, template filtering is handled by the configuration dialog
            # This method provides compatibility for the analysis controller
            template_filter = getattr(self, 'current_template_filter', None)
            
            if template_filter:
                if isinstance(template_filter, list):
                    return template_filter
                elif isinstance(template_filter, str):
                    return [t.strip() for t in template_filter.split(',') if t.strip()]
            
            return None
        except Exception as e:
            _LOGGER.error(f"Error parsing template filter: {e}")
            return None
    
    def _parse_type_filter(self):
        """Parse type filter from parameters (compatibility with earlier configs)."""
        try:
            # For PySide6, type filtering is handled by the configuration dialog
            # This method provides compatibility for the analysis controller
            type_filter = getattr(self, 'current_type_filter', None)
            
            if type_filter:
                if isinstance(type_filter, list):
                    return type_filter
                elif isinstance(type_filter, str):
                    return [t.strip() for t in type_filter.split(',') if t.strip()]
            
            return None
        except Exception as e:
            _LOGGER.error(f"Error parsing type filter: {e}")
            return None
    
    def _parse_age_range(self):
        """Parse age range from parameters (compatibility with earlier configs)."""
        try:
            # For PySide6, age range is handled by the configuration dialog
            # This method provides compatibility for the analysis controller
            age_range = getattr(self, 'current_age_range', None)
            
            if age_range and isinstance(age_range, (list, tuple)) and len(age_range) == 2:
                return tuple(age_range)
            
            return None
        except Exception as e:
            _LOGGER.error(f"Error parsing age range: {e}")
            return None
    
    # Safe parameter parsing helper methods
    def _safe_float(self, value, default=0.0):
        """Safely parse float value"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                return float(value.strip()) if value.strip() else default
            return default
        except (ValueError, AttributeError):
            return default
    
    def _safe_int(self, value, default=0):
        """Safely parse int value"""
        try:
            if isinstance(value, int):
                return value
            elif isinstance(value, (float, str)):
                return int(float(str(value).strip())) if str(value).strip() else default
            return default
        except (ValueError, AttributeError):
            return default
    
    def _safe_bool(self, value, default=False):
        """Safely parse bool value"""
        try:
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(value, (int, float)):
                return bool(value)
            return default
        except (ValueError, AttributeError):
            return default

    def _setup_window_properties(self):
        """Setup window title, icon, size, and positioning with cross-platform consistency"""
        # Set window title
        self.setWindowTitle(f"SNID SAGE v{__version__}")
        
        # Set window icon
        try:
            # Use centralized logo manager so paths work in dev and installed package
            from snid_sage.interfaces.ui_core.logo import get_logo_manager
            icon_path = get_logo_manager().get_icon_path()
            if icon_path:
                self.setWindowIcon(QtGui.QIcon(str(icon_path)))
                _LOGGER.debug(f"Window icon set from {icon_path}")
        except Exception as e:
            _LOGGER.warning(f"Could not set window icon: {e}")
        
        # Use unified layout manager settings for window sizing and apply persisted UI scale
        if hasattr(self, 'unified_layout_manager'):
            settings = self.unified_layout_manager.settings
            default_size = settings.default_window_size
            min_size = settings.minimum_window_size
        else:
            default_size = (900, 600)
            min_size = (700, 500)
        
        # Apply persisted UI scale percentage (QSettings) to default size
        try:
            app_settings = QtCore.QSettings("SNID_SAGE", "GUI")
            ui_scale_percent = int(app_settings.value("ui_scale_percent", 100))
            ui_scale_percent = max(50, min(300, ui_scale_percent))
            scaled_w = int(default_size[0] * ui_scale_percent / 100)
            scaled_h = int(default_size[1] * ui_scale_percent / 100)
            self.resize(scaled_w, scaled_h)
        except Exception:
            self.resize(*default_size)
        self.setMinimumSize(*min_size)
        # Remove maximum size restriction to allow full maximization
        # self.setMaximumSize(*max_size)  # Commented out to enable maximize button
        
        _LOGGER.debug(f"Window size set to {default_size[0]}x{default_size[1]} using unified layout settings")
        
        # Center window on screen
        self._center_window()
    
    def _center_window(self):
        """Center the window on the primary screen"""
        try:
            screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            window_geometry = self.frameGeometry()
            center_point = screen.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())
            _LOGGER.debug("Window centered on screen")
        except Exception as e:
            _LOGGER.warning(f"Could not center window: {e}")
    
    def _init_theme_colors(self):
        """Initialize theme colors using unified theme manager"""
        # Import and use the unified theme manager
        from snid_sage.interfaces.gui.utils.pyside6_theme_manager import get_pyside6_theme_manager
        
        self.theme_manager = get_pyside6_theme_manager()
        self.theme_colors = self.theme_manager.get_all_colors()
        
        # Apply Qt stylesheet for unified theming
        self._apply_qt_stylesheet()
    
    def _apply_qt_stylesheet(self):
        """Apply Qt stylesheet using unified theme manager with cross-platform enhancements"""
        # Use the theme manager's complete stylesheet method that includes all enhancements
        complete_stylesheet = self.theme_manager.generate_complete_stylesheet()
        self.setStyleSheet(complete_stylesheet)
        _LOGGER.debug("Complete Qt stylesheet applied with cross-platform enhancements via theme manager")
    
    def _create_interface(self):
        """Create the main GUI interface"""
        # Import unified layout manager
        from snid_sage.interfaces.gui.utils.unified_pyside6_layout_manager import (
            get_unified_layout_manager, LayoutSettings
        )
        
        # Initialize unified layout manager with settings
        layout_settings = LayoutSettings()
        layout_settings.default_window_size = (900, 600)
        layout_settings.minimum_window_size = (700, 500)
        self.unified_layout_manager = get_unified_layout_manager(layout_settings)
        
        # Create central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout using unified manager
        main_layout = self.unified_layout_manager.create_main_layout(self, central_widget)
        
        _LOGGER.debug("Interface layout created with unified layout manager - no conflicts")

        # Re-apply persisted UI scale after layout manager (which sets default size)
        try:
            app_settings = QtCore.QSettings("SNID_SAGE", "GUI")
            ui_scale_percent = int(app_settings.value("ui_scale_percent", 100))
            ui_scale_percent = max(50, min(300, ui_scale_percent))
            if hasattr(self, 'unified_layout_manager'):
                base_size = self.unified_layout_manager.settings.default_window_size
            else:
                base_size = (900, 600)
            scaled_w = int(base_size[0] * ui_scale_percent / 100)
            scaled_h = int(base_size[1] * ui_scale_percent / 100)
            self.resize(scaled_w, scaled_h)
        except Exception:
            pass

        # Initialize in-memory GUI settings dict
        self.gui_settings: Dict[str, Any] = {}

    def apply_settings(self, settings: Dict[str, Any]):
        """Apply GUI settings coming from the Settings dialog at runtime."""
        try:
            self.gui_settings.update(settings or {})
        except Exception:
            self.gui_settings = dict(settings or {})

        # Apply font appearance
        try:
            font_family = self.gui_settings.get('font_family')
            font_size = self.gui_settings.get('font_size')
            if font_family or font_size:
                current_font = self.font() if hasattr(self, 'font') else None
                f_family = font_family or (current_font.family() if current_font else 'Arial')
                f_size = int(font_size) if font_size else (current_font.pointSize() if current_font else 10)
                qf = QtGui.QFont(f_family, f_size)
                self.setFont(qf)
        except Exception as e:
            _LOGGER.debug(f"Non-fatal: could not apply font settings: {e}")

        # Apply window size and optional center; remember_position is handled by QSettings if added later
        try:
            ui_scale_percent = self.gui_settings.get('ui_scale_percent')
            if isinstance(ui_scale_percent, int) and 50 <= ui_scale_percent <= 300:
                # Persist via QSettings and resize according to baseline default size
                app_settings = QtCore.QSettings("SNID_SAGE", "GUI")
                app_settings.setValue("ui_scale_percent", ui_scale_percent)
                # Compute size relative to current default baseline (use unified layout manager or fallback)
                if hasattr(self, 'unified_layout_manager'):
                    base_size = self.unified_layout_manager.settings.default_window_size
                else:
                    base_size = (900, 600)
                scaled_w = int(base_size[0] * ui_scale_percent / 100)
                scaled_h = int(base_size[1] * ui_scale_percent / 100)
                self.resize(scaled_w, scaled_h)
        except Exception as e:
            _LOGGER.debug(f"Non-fatal: could not apply window size: {e}")

        # Apply plot preferences
        try:
            if hasattr(self, 'plot_manager') and self.plot_manager:
                self.plot_manager.apply_plot_settings(self.gui_settings)
        except Exception as e:
            _LOGGER.debug(f"Non-fatal: could not apply plot settings: {e}")

    def snapshot_gui_state(self) -> Dict[str, Any]:
        """Capture current window/plot settings for temporary restore."""
        state: Dict[str, Any] = {}
        try:
            geom = self.geometry()
            state['window_width'] = int(geom.width())
            state['window_height'] = int(geom.height())
        except Exception:
            pass
        try:
            if hasattr(self, 'plot_manager') and self.plot_manager:
                aa = self.plot_manager.get_antialiasing()
                if aa is not None:
                    state['plot_antialiasing'] = bool(aa)
        except Exception:
            pass
        return state

    def restore_gui_state(self, state: Dict[str, Any]) -> None:
        """Restore previously captured window/plot settings."""
        try:
            w = state.get('window_width')
            h = state.get('window_height')
            if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
                self.resize(w, h)
        except Exception:
            pass
        try:
            if hasattr(self, 'plot_manager') and self.plot_manager:
                aa = state.get('plot_antialiasing')
                if aa is not None:
                    self.plot_manager.set_antialiasing(bool(aa))
        except Exception:
            pass
    
    def _plot_clean_welcome_message(self):
        """Show clean welcome message without demo spectrum - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                self.plot_manager.plot_clean_welcome_message()
        except Exception as e:
            _LOGGER.warning(f"Could not plot welcome message: {e}")
    
    def add_mask_region(self, min_wave, max_wave):
        """Add a mask region to the plot - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                self.plot_manager.add_mask_region(min_wave, max_wave)
            _LOGGER.debug(f"Added mask region: {min_wave:.1f} - {max_wave:.1f} Å")
        except Exception as e:
            _LOGGER.error(f"Error adding mask region: {e}")
    
    def clear_all_masks(self):
        """Clear all mask regions - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                self.plot_manager.clear_all_masks()
            self.status_label.setText("All mask regions cleared")
            _LOGGER.debug("All mask regions cleared")
        except Exception as e:
            _LOGGER.error(f"Error clearing masks: {e}")
    
    def _reapply_mask_regions(self):
        """Re-apply mask regions after plot update - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                self.plot_manager.reapply_mask_regions()
        except Exception as e:
            _LOGGER.warning(f"Error reapplying mask regions: {e}")
    
    def _init_variables_and_state(self):
        """Initialize variables and application state"""
        # View style tracking
        self.current_view = 'flux'
        
        # Plot mode tracking
        self.current_plot_mode = PlotMode.SPECTRUM
        
        # Data storage
        self.spectrum_data = None
        self.analysis_results = None
        
        # Placeholder attributes for mask buttons
        self.mask_btn = None
        self.clear_masks_btn = None
        
        # Button state tracking
        self.workflow_buttons = [
            self.preprocessing_btn,
            self.redshift_selection_btn, 
            self.analysis_btn,
            self.emission_line_overlay_btn,  # Use correct attribute name
            self.ai_assistant_btn  # Use correct attribute name
        ]
        
        self.analysis_plot_buttons = [
            self.cluster_summary_btn,
            self.gmm_btn,
            self.redshift_age_btn,
            self.subtype_proportions_btn
        ]
        
        self.nav_buttons = [
            self.prev_btn,
            self.next_btn
        ]
        
        # Blinking button state management
        self.cluster_summary_blinking = False
        self.cluster_summary_blink_timer = None
        self.cluster_summary_original_style = None
        self.cluster_summary_clicked_once = False
        
        # Connect view toggle buttons
        self.flux_btn.clicked.connect(lambda: self._on_view_change('flux'))
        self.flat_btn.clicked.connect(lambda: self._on_view_change('flat'))
        
        
        self.flux_btn.setEnabled(False)
        self.flux_btn.setChecked(False)
        self.flux_btn.setToolTip("Flux view requires spectrum\nLoad a spectrum file first")
        
        self.flat_btn.setEnabled(False)
        self.flat_btn.setChecked(False)
        self.flat_btn.setToolTip("Flat view requires preprocessing\nLoad a spectrum and run preprocessing first")
        
        # Keyboard shortcuts handled by event handlers
        
        _LOGGER.debug("Variables and state initialized")
    
    def _init_workflow_system(self):
        """Initialize workflow system and register all buttons"""
        try:
            # Register all workflow buttons (EXCLUDE flux_btn and flat_btn - they have special toggle styling)
            workflow_buttons = {
                'load_btn': self.load_spectrum_btn,
                'preprocessing_btn': self.preprocessing_btn,
                'redshift_selection_btn': self.redshift_selection_btn,
                'analysis_btn': self.analysis_btn,
                'emission_line_btn': self.emission_line_overlay_btn,  # Use correct attribute name
                'chat_btn': self.ai_assistant_btn,  # Use correct attribute name
                'reset_btn': self.reset_btn,
                'settings_btn': self.settings_btn,
                'cluster_summary_btn': self.cluster_summary_btn,
                'gmm_btn': self.gmm_btn,
                'redshift_age_btn': self.redshift_age_btn,
                'subtype_proportions_btn': self.subtype_proportions_btn,
                'prev_btn': self.prev_btn,
                'next_btn': self.next_btn,
                
                # special CSS-based toggle styling that would be overridden by workflow manager
                
            }
            
            for button_name, button_widget in workflow_buttons.items():
                if button_widget is not None:
                    self.workflow_manager.register_button(button_name, button_widget)
            
            # Add workflow state change callback to update display
            self.workflow_manager.add_state_change_callback(self._on_workflow_state_change)
            
            _LOGGER.debug("Workflow system initialized and buttons registered")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing workflow system: {e}")
    
    def _init_event_handlers(self):
        """Initialize event handlers"""
        try:
            # Import and initialize the dedicated event handlers
            from snid_sage.interfaces.gui.components.events.pyside6_event_handlers import PySide6EventHandlers
            
            self.event_handlers = PySide6EventHandlers(self)
            
            _LOGGER.debug("Event handlers initialized successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing event handlers: {e}")
    
    def _init_analysis_menu_manager(self):
        """Initialize analysis menu manager"""
        try:
            # Import and initialize the analysis menu manager
            from snid_sage.interfaces.gui.components.analysis.analysis_menu_manager import AnalysisMenuManager
            
            self.analysis_menu_manager = AnalysisMenuManager(self)
            
            _LOGGER.debug("Analysis menu manager initialized successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing analysis menu manager: {e}")
            self.analysis_menu_manager = None
    
    def _on_workflow_state_change(self, new_state):
        """Handle workflow state changes"""
        try:
            _LOGGER.info(f"🔄 WORKFLOW STATE CHANGE: {new_state.value}")
            
            # Update status label based on state
            state_messages = {
                'initial': "Ready - Load a spectrum to begin analysis",
                'file_loaded': "File loaded - Configure preprocessing or analysis",
                'preprocessed': "Spectrum preprocessed - Ready for analysis",
                'redshift_set': "Redshift configured - Ready for analysis", 
                'analysis_complete': "Analysis complete - Explore results and advanced features",
                'ai_ready': "AI features activated"
            }
            
            message = state_messages.get(new_state.value, f"State: {new_state.value}")
            self.status_label.setText(message)
            
            # CRITICAL: Also call the button state update method to handle Flux/Flat buttons
            _LOGGER.info(f"🔄 Calling _update_workflow_state({new_state.value})")
            self._update_workflow_state(new_state)
            
        except Exception as e:
            _LOGGER.error(f"Error handling workflow state change: {e}")
    
    def update_workflow_state(self, new_state):
        """Update workflow state through the workflow manager"""
        self.workflow_manager.update_workflow_state(new_state)
        
        # CRITICAL: Also update the GUI's button states directly
        self._update_workflow_state(new_state)
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts - handled by event handlers"""
        # This method is now obsolete as event handlers manage keyboard shortcuts
        pass
    
    # Workflow state management
    def _update_workflow_state(self, new_state: WorkflowState):
        """Update workflow state and button availability"""
        _LOGGER.info(f"🔧 WORKFLOW STATE UPDATE: {self.current_state.value if hasattr(self, 'current_state') else 'unknown'} → {new_state.value}")
        self.current_state = new_state
        
        # Enable buttons based on workflow state
        if new_state == WorkflowState.FILE_LOADED:
            _LOGGER.info("🔧 FILE_LOADED: Processing workflow state...")
            
            self.preprocessing_btn.setEnabled(True)
            self.redshift_selection_btn.setEnabled(True)
            # Enable emission line analysis after spectrum is loaded
            self.emission_line_overlay_btn.setEnabled(True)
            
            # CRITICAL: Log current button states BEFORE layout manager update
            if hasattr(self, 'flux_btn') and hasattr(self, 'flat_btn'):
                _LOGGER.info(f"🔍 BEFORE UPDATE: flux_btn enabled={self.flux_btn.isEnabled()}, checked={self.flux_btn.isChecked()}")
                _LOGGER.info(f"🔍 BEFORE UPDATE: flat_btn enabled={self.flat_btn.isEnabled()}, checked={self.flat_btn.isChecked()}")
            
            # CRITICAL: Use layout manager to handle Flux/Flat button states
            _LOGGER.info("🔧 FILE_LOADED: Delegating button state management to layout manager")
            self.unified_layout_manager.update_flux_flat_button_states(
                self,
                flux_active=True,    # Flux becomes active (blue)
                flat_active=False,   # Flat stays inactive
                flux_enabled=True,   # Flux becomes enabled
                flat_enabled=False   # Flat stays disabled until preprocessing
            )
            
            # CRITICAL: Ensure button states are actually updated by checking and forcing if needed
            if hasattr(self, 'flux_btn') and hasattr(self, 'flat_btn'):
                # Double-check that the states were actually applied
                _LOGGER.info(f"🔍 AFTER LAYOUT MANAGER: flux_btn.isEnabled()={self.flux_btn.isEnabled()}, flux_btn.isChecked()={self.flux_btn.isChecked()}")
                _LOGGER.info(f"🔍 AFTER LAYOUT MANAGER: flat_btn.isEnabled()={self.flat_btn.isEnabled()}, flat_btn.isChecked()={self.flat_btn.isChecked()}")
                
                # Force the correct states if layout manager didn't work
                if not self.flux_btn.isEnabled() or not self.flux_btn.isChecked():
                    _LOGGER.warning("🚨 Layout manager didn't properly update Flux button - forcing correct state")
                    self.flux_btn.setEnabled(True)
                    self.flux_btn.setChecked(True)
                    # Force blue styling - use CSS selector approach
                    flux_blue_style = """
                    QPushButton {
                        background-color: #3b82f6 !important;
                        border: 2px solid #2563eb !important;
                        color: white !important;
                        border-radius: 4px !important;
                        font-weight: bold !important;
                        font-size: 9pt !important;
                        padding: 2px 8px !important;
                    }
                    QPushButton:hover {
                        background-color: #2563eb !important;
                        border-color: #1d4ed8 !important;
                    }
                    """
                    self.flux_btn.setStyleSheet(flux_blue_style)
                    _LOGGER.info("Forced Flux button to active state with blue styling")
                    
                if self.flat_btn.isEnabled() or self.flat_btn.isChecked():
                    _LOGGER.warning("🚨 Layout manager incorrectly enabled/checked Flat button - forcing correct state")
                    self.flat_btn.setEnabled(False)
                    self.flat_btn.setChecked(False)
                    # Force inactive styling
                    flat_gray_style = """
                    QPushButton {
                        background-color: #f3f4f6 !important;
                        border: 2px solid #e5e7eb !important;
                        color: #9ca3af !important;
                        border-radius: 4px !important;
                        font-weight: bold !important;
                        font-size: 9pt !important;
                        padding: 2px 8px !important;
                    }
                    """
                    self.flat_btn.setStyleSheet(flat_gray_style)
                    _LOGGER.info("Forced Flat button to inactive state")
                    
                # Final verification
                _LOGGER.info(f"🔍 FINAL STATE: flux_btn enabled={self.flux_btn.isEnabled()}, checked={self.flux_btn.isChecked()}")
                _LOGGER.info(f"🔍 FINAL STATE: flat_btn enabled={self.flat_btn.isEnabled()}, checked={self.flat_btn.isChecked()}")
            
            # Set current view to flux
            self.current_view = 'flux'
            _LOGGER.info(f"🔧 FILE_LOADED: Set current_view to '{self.current_view}'")

            # Reset left-panel status labels to pre-analysis defaults
            try:
                if hasattr(self, 'preprocess_status_label'):
                    self.preprocess_status_label.setText("Preprocessing not run")
                if hasattr(self, 'redshift_status_label'):
                    self.redshift_status_label.setText("Redshift not set (optional)")
                if hasattr(self, 'config_status_label'):
                    self.config_status_label.setText("Default SNID parameters loaded")
                if hasattr(self, 'emission_status_label'):
                    self.emission_status_label.setText("Run analysis to enable")
                if hasattr(self, 'ai_status_label'):
                    self.ai_status_label.setText("Run analysis to enable")
            except Exception:
                pass
            
            
        elif new_state == WorkflowState.PREPROCESSED:
            self.analysis_btn.setEnabled(True)
            
            # CRITICAL: Use layout manager to handle Flux/Flat button states after preprocessing
            _LOGGER.info("🔧 PREPROCESSED: Delegating button state management to layout manager")
            self.unified_layout_manager.update_flux_flat_button_states(
                self,
                flux_active=False,   # Flux becomes inactive
                flat_active=True,    # Flat becomes active (blue)
                flux_enabled=True,   # Both buttons enabled
                flat_enabled=True
            )
            
            # Set current view to flat
            self.current_view = 'flat'
            
        elif new_state == WorkflowState.ANALYSIS_COMPLETE:
            # Enable all analysis features
            for btn in self.analysis_plot_buttons:
                btn.setEnabled(True)
            for btn in self.nav_buttons:
                btn.setEnabled(True)
            self.ai_assistant_btn.setEnabled(True)
            
            # CRITICAL: After analysis, both Flux and Flat should remain available
            # Keep current view active, but ensure both buttons are enabled
            current_flux_active = self.current_view == 'flux'
            current_flat_active = self.current_view == 'flat'
            self.unified_layout_manager.update_flux_flat_button_states(
                self,
                flux_active=current_flux_active,
                flat_active=current_flat_active,
                flux_enabled=True,   # Both buttons enabled after analysis
                flat_enabled=True
            )
        
        _LOGGER.debug(f"Workflow state updated to: {new_state.value}")
    
    def get_color(self, color_key: str) -> str:
        """Get theme color by key"""
        return self.theme_manager.get_color(color_key)
    
    # File operations - delegate to event handlers
    def browse_file(self):
        """Browse for a spectrum file - delegate to event handlers"""
        if hasattr(self, 'event_handlers'):
            self.event_handlers.on_browse_file()
    
    def open_preprocessing_dialog(self):
        """Open preprocessing dialog - delegate to event handlers"""
        if hasattr(self, 'event_handlers'):
            self.event_handlers.on_open_preprocessing_dialog()
    
    def run_analysis(self):
        """Run SNID analysis - delegate to event handlers"""
        if hasattr(self, 'event_handlers'):
            self.event_handlers.on_run_analysis()
    
    def reset_to_initial_state(self):
        """Reset to initial state - delegate to event handlers"""
        if hasattr(self, 'event_handlers'):
            self.event_handlers.on_reset_to_initial_state()
    
    
    def open_redshift_dialog(self):
        """Open redshift selection dialog - delegate to dialog manager"""
        if hasattr(self, 'dialog_manager'):
            self.dialog_manager.open_redshift_dialog()
        else:
            _LOGGER.error("Dialog manager not available")

    def open_settings_dialog(self):
        """Open settings dialog - delegate to dialog manager"""
        if hasattr(self, 'dialog_manager'):
            self.dialog_manager.open_settings_dialog()
        else:
            _LOGGER.error("Dialog manager not available")

    def open_emission_line_dialog(self):
        """Open emission line dialog - delegate to dialog manager"""
        _LOGGER.info("🔬 PySide6SNIDSageGUI.open_emission_line_dialog called")
        
        try:
            if hasattr(self, 'dialog_manager'):
                _LOGGER.info("Dialog manager found - delegating to dialog_manager.open_emission_line_dialog")
                self.dialog_manager.open_emission_line_dialog()
                _LOGGER.info("Dialog manager call completed successfully")
            else:
                _LOGGER.error("❌ Dialog manager not available")
                
        except Exception as e:
            _LOGGER.error(f"❌ Error in open_emission_line_dialog: {e}")
            import traceback
            _LOGGER.error(f"❌ Full traceback: {traceback.format_exc()}")
            # Don't re-raise to prevent GUI crash
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to open emission line dialog:\n{str(e)}"
            )

    def open_chat_dialog(self):
        """Open AI chat dialog - delegate to dialog manager"""
        if hasattr(self, 'dialog_manager'):
            self.dialog_manager.open_chat_dialog()
        else:
            _LOGGER.error("Dialog manager not available")

    def open_configuration_dialog(self):
        """Open SNID configuration dialog - delegate to dialog manager"""
        if hasattr(self, 'dialog_manager'):
            self.dialog_manager.open_configuration_dialog()
        else:
            _LOGGER.error("Dialog manager not available")

    def run_quick_workflow(self):
        """Run quick workflow: preprocessing + analysis in one step"""
        try:
            _LOGGER.info("Starting quick workflow (preprocessing + analysis)")
            # First run preprocessing with default settings
            self.open_preprocessing_dialog()
            # Then run analysis
            self.run_analysis()
        except Exception as e:
            _LOGGER.error(f"Error in quick workflow: {e}")
    
    def open_mask_manager_dialog(self):
        """Open mask manager dialog - delegate to dialog manager"""
        if hasattr(self, 'dialog_manager'):
            self.dialog_manager.open_mask_manager_dialog()
        else:
            _LOGGER.error("Dialog manager not available")
    
    def start_games(self):
        """Start GAMES integration"""
        try:
            # Directly open the games menu if available
            self.start_games_menu()
        except Exception as e:
            _LOGGER.error(f"Error starting GAMES: {e}")
    
    def start_games_menu(self):
        """Start the games menu."""
        try:
            import sys
            # On macOS start immediately; on other platforms show the dialog like before
            if sys.platform == 'darwin':
                self._start_space_debris_game()
            else:
                # Create games selection dialog or fallback to simple question
                try:
                    from snid_sage.interfaces.gui.components.pyside6_dialogs.games_dialog import PySide6GamesDialog
                    dialog = PySide6GamesDialog(self)
                    result = dialog.exec()
                    if result == QtWidgets.QDialog.Accepted:
                        pass
                except ImportError:
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "🎮 Play Games",
                        "Would you like to play Space Debris Cleanup while running analysis?\n\n"
                        "Controls: Arrow keys to move, SPACE to fire, ESC to exit",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes
                    )
                    if reply == QtWidgets.QMessageBox.Yes:
                        self._start_space_debris_game()
                
        except Exception as e:
            _LOGGER.error(f"Error starting games menu: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Games Error",
                f"Failed to start games menu: {str(e)}"
            )
    
    def _start_space_debris_game(self):
        """Start the Space Debris Cleanup game (Qt-native)."""
        try:
            from snid_sage.snid.games import run_debris_game
            run_debris_game()
            # Update status if available
            if hasattr(self, "status_label"):
                self.status_label.setText("🎮 Space Debris Cleanup game started!")
            _LOGGER.info("Space Debris Cleanup game started")
        except Exception as e:
            _LOGGER.error(f"Error starting Space Debris game: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Game Error",
                f"Failed to start Space Debris game: {str(e)}"
            )
    
    def _show_analysis_menu(self):
        """Show analysis options menu - delegate to analysis menu manager"""
        try:
            if self.analysis_menu_manager:
                self.analysis_menu_manager.show_analysis_menu()
            else:
                # Fallback to simple analysis if manager not available
                self.run_analysis()
        except Exception as e:
            _LOGGER.error(f"Error showing analysis menu: {e}")
            self.run_analysis()

    def run_analysis(self):
        """Run SNID analysis - delegate to analysis menu manager"""
        try:
            if self.analysis_menu_manager:
                self.analysis_menu_manager.run_advanced_analysis()
            else:
                # Fallback if manager not available
                QtWidgets.QMessageBox.warning(
                    self, 
                    "Analysis Error", 
                    "Analysis menu manager not available. Please check installation."
                )
        except Exception as e:
            _LOGGER.error(f"Error running analysis: {e}")
            self.status_label.setText("Analysis error occurred")
    
    def run_quick_analysis(self):
        """Run SNID analysis immediately with default settings - delegate to analysis menu manager"""
        try:
            if self.analysis_menu_manager:
                self.analysis_menu_manager.run_quick_analysis()
            else:
                # Fallback if manager not available
                QtWidgets.QMessageBox.warning(
                    self, 
                    "Analysis Error", 
                    "Analysis menu manager not available. Please check installation."
                )
        except Exception as e:
            _LOGGER.error(f"Error running quick analysis: {e}")
            self.status_label.setText("Quick analysis error occurred")
    
    def _compose_classification_header(self, result) -> str:
        """Compose the status header showing best/selected type and subtype without confidence values."""
        try:
            from snid_sage.shared.utils.results_formatter import create_unified_formatter
            formatter = create_unified_formatter(result, getattr(result, 'spectrum_name', None), getattr(result, 'spectrum_path', None))
            summary = formatter.get_export_data()
            import math

            # Active (selected or auto-best) classification
            active_type = (summary.get('consensus_type') or 'Unknown').strip()
            active_subtype = (summary.get('consensus_subtype') or '').strip()
            active_display = f"{active_type} / {active_subtype}".strip().rstrip('/')

            # Determine winning-subtype redshift (prefer subtype-specific; fallback to enhanced; then result.redshift)
            active_z = None
            try:
                z_sub = summary.get('subtype_redshift', None)
                if isinstance(z_sub, (int, float)) and math.isfinite(float(z_sub)):
                    active_z = float(z_sub)
                else:
                    z_enh = summary.get('enhanced_redshift', None)
                    if isinstance(z_enh, (int, float)) and math.isfinite(float(z_enh)):
                        active_z = float(z_enh)
                    else:
                        z0 = getattr(result, 'redshift', None)
                        if isinstance(z0, (int, float)) and math.isfinite(float(z0)):
                            active_z = float(z0)
            except Exception:
                pass
            z_fragment = f" — z = {active_z:.6f}" if isinstance(active_z, float) else ""

            # If no manual override, show professional classification label
            if not summary.get('is_manual_selection', False):
                return f"Classification: {active_display}{z_fragment}"

            # Manual selection differs from auto best → show Selected vs Suggested best
            suggested_type = ''
            suggested_subtype = ''
            clres = getattr(result, 'clustering_results', {}) or {}
            best_cluster = clres.get('best_cluster') if isinstance(clres, dict) else None
            if isinstance(best_cluster, dict):
                suggested_type = (best_cluster.get('type') or '').strip()
                st_info = best_cluster.get('subtype_info', {}) or {}
                suggested_subtype = (st_info.get('best_subtype') or '').strip()
                if not suggested_subtype:
                    try:
                        matches = best_cluster.get('matches', []) or []
                        if matches:
                            tpl = matches[0].get('template', {}) if isinstance(matches[0].get('template'), dict) else {}
                            suggested_subtype = (tpl.get('subtype') or '').strip()
                    except Exception:
                        suggested_subtype = ''
            suggested_display = f"{suggested_type} / {suggested_subtype}".strip().rstrip('/')
            return f"Selected: {active_display}{z_fragment} — Suggested: {suggested_display}" if suggested_display else f"Selected: {active_display}{z_fragment}"
        except Exception:
            # Fallback to type-only display
            t = getattr(result, 'consensus_type', None) or 'Unknown'
            st = getattr(result, 'best_subtype', None) or ''
            disp = f"{t} / {st}".strip().rstrip('/')
            try:
                import math
                z0 = getattr(result, 'redshift', None)
                z_fragment = f" — z = {float(z0):.6f}" if isinstance(z0, (int, float)) and math.isfinite(float(z0)) else ""
            except Exception:
                z_fragment = ""
            return f"Classification: {disp}{z_fragment}"

    # Signal handlers for app controller updates
    def _on_analysis_completed(self, success: bool):
        """Handle analysis completion signal from app controller"""
        try:
            # Handle user-cancelled analysis distinctly (no failure dialogs)
            if hasattr(self, 'app_controller') and getattr(self.app_controller, 'analysis_cancelled', False):
                # Close/cleanup progress dialog gracefully
                if hasattr(self, 'progress_dialog') and self.progress_dialog:
                    try:
                        # Add a final line and close quickly
                        self.progress_dialog.add_progress_line("🔴 Analysis cancelled", "warning")
                        QtCore.QTimer.singleShot(200, self.progress_dialog.reject)
                    except Exception:
                        pass
                # Update GUI state
                self.status_label.setText("Analysis cancelled")
                self.config_status_label.setText("Analysis Cancelled")
                self.config_status_label.setStyleSheet("font-style: italic; color: #dc2626; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                # Ensure buttons are re-enabled
                for btn in self.analysis_plot_buttons:
                    btn.setEnabled(False)
                for btn in self.nav_buttons:
                    btn.setEnabled(False)
                # Stop further handling
                return

            # Check if a good cluster exists to determine progress dialog handling
            has_good_cluster = False
            try:
                if hasattr(self.app_controller, '_has_good_cluster'):
                    has_good_cluster = self.app_controller._has_good_cluster(self.app_controller.snid_results)
            except Exception:
                has_good_cluster = False
            
            # Update progress dialog if it exists
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                try:
                    if success:
                        if has_good_cluster:
                            # If clustering is available, close progress dialog immediately to show cluster selection
                            self.progress_dialog.analysis_completed(True, "Analysis completed - selecting cluster...")
                            QtCore.QTimer.singleShot(100, self.progress_dialog.accept)  # Close quickly for cluster selection
                        else:
                            # No clustering - tailor message based on match quality and keep open briefly
                            results = getattr(self.app_controller, 'snid_results', None)
                            # Legacy `type_confidence` (0–1) removed; use unified confidence/quality signals instead.
                            def _is_weak_match(_results) -> bool:
                                try:
                                    if _results is None:
                                        return True
                                    from snid_sage.shared.utils.results_formatter import create_unified_formatter
                                    fmt = create_unified_formatter(
                                        _results,
                                        getattr(_results, 'spectrum_name', None),
                                        getattr(_results, 'spectrum_path', None),
                                    )
                                    s = fmt.get_export_data() or {}
                                    lvl = (s.get('cluster_confidence_level') or '').strip().lower()
                                    if lvl:
                                        return lvl == 'very low'
                                    qlvl = (s.get('cluster_quality_level') or '').strip().lower()
                                    if qlvl:
                                        return qlvl == 'very low'
                                except Exception:
                                    return True
                                return False
                            # Weak if low confidence OR no matches above best-metric threshold
                            fm = getattr(results, 'filtered_matches', []) if results else []
                            is_above_threshold = bool(fm and len(fm) > 0)
                            is_weak = _is_weak_match(results) or (not is_above_threshold)
                            msg = (
                                "Only a weak match was found – try Advanced Preprocessing (smoothing, masking, continuum) to improve results."
                                if is_weak else
                                "Analysis completed."
                            )
                            self.progress_dialog.analysis_completed(True, msg)
                            QtCore.QTimer.singleShot(2000, self.progress_dialog.accept)  # Auto-close after 2 seconds
                    else:
                        # Distinguish between a true failure and an inconclusive/no-match outcome
                        results = getattr(self.app_controller, 'snid_results', None)
                        # Build an indicative message if we can detect the inconclusive path
                        inconclusive_msg = None
                        try:
                            if results is None or not getattr(results, 'success', False):
                                # Check analysis trace or controller log state for no-match conditions
                                # Prefer explicit flags when present
                                if hasattr(self.app_controller, '_has_good_cluster') and not self.app_controller._has_good_cluster(results):
                                    # If engine ran but we have zero matches, treat as inconclusive
                                    num_best = 0
                                    try:
                                        if results and hasattr(results, 'best_matches') and results.best_matches:
                                            num_best = len(results.best_matches)
                                    except Exception:
                                        num_best = 0
                                    if num_best == 0:
                                        inconclusive_msg = "Analysis inconclusive: no good matches found"
                        except Exception:
                            inconclusive_msg = None

                        if inconclusive_msg:
                            self.progress_dialog.analysis_completed(False, inconclusive_msg)
                        else:
                            self.progress_dialog.analysis_completed(False, "Analysis failed - see logs for details")
                except Exception as e:
                    _LOGGER.warning(f"Error updating progress dialog: {e}")
            
            if success:
                # Store analysis results for easy access
                self.analysis_results = self.app_controller.get_analysis_results()
                
                # Update workflow state
                from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                self.app_controller.update_workflow_state(WorkflowState.ANALYSIS_COMPLETE)
                # Update status label based on result quality
                results = getattr(self.app_controller, 'snid_results', None)
                def _is_weak_match(_results) -> bool:
                    try:
                        if _results is None:
                            return True
                        from snid_sage.shared.utils.results_formatter import create_unified_formatter
                        fmt = create_unified_formatter(
                            _results,
                            getattr(_results, 'spectrum_name', None),
                            getattr(_results, 'spectrum_path', None),
                        )
                        s = fmt.get_export_data() or {}
                        lvl = (s.get('cluster_confidence_level') or '').strip().lower()
                        if lvl:
                            return lvl == 'very low'
                        qlvl = (s.get('cluster_quality_level') or '').strip().lower()
                        if qlvl:
                            return qlvl == 'very low'
                    except Exception:
                        return True
                    return False
                fm = getattr(results, 'filtered_matches', []) if results else []
                if (not has_good_cluster):
                    if not fm:
                        self.status_label.setText("Analysis inconclusive – no reliable matches above threshold")
                    elif _is_weak_match(results):
                        self.status_label.setText("Analysis weak – only low-quality matches above threshold")
                    else:
                        # Show best type/subtype without confidence
                        try:
                            self.status_label.setText(self._compose_classification_header(results))
                        except Exception:
                            self.status_label.setText("Analysis complete")
                else:
                    # Good cluster path – show best now; later selection may update it
                    try:
                        self.status_label.setText(self._compose_classification_header(results))
                    except Exception:
                        self.status_label.setText("Analysis complete")
                
                # Enable analysis plot/navigation buttons only when we have reliable matches
                reliable = bool(getattr(results, 'clustering_results', None) and results.clustering_results.get('success')) or bool(fm)
                for btn in self.analysis_plot_buttons:
                    btn.setEnabled(reliable)
                for btn in self.nav_buttons:
                    btn.setEnabled(reliable)
                
                # CRITICAL: Refresh workflow manager button states after analysis completion
                # This ensures navigation buttons get proper styling when templates become available
                if hasattr(self, 'workflow_manager'):
                    self.workflow_manager.refresh_button_states()
                    _LOGGER.debug("🔄 Workflow manager button states refreshed after analysis completion")
                
                # Enable advanced features only when we have reliable matches above threshold
                self.emission_line_overlay_btn.setEnabled(reliable)
                self.ai_assistant_btn.setEnabled(reliable)
                
                # Update status indicators
                self.config_status_label.setText("Analysis Complete")
                self.config_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                
                if has_good_cluster:
                    # Good cluster available - cluster selection dialog will automatically show results after selection
                    _LOGGER.info("🎯 Analysis completed with valid cluster - cluster selection will handle results display")
                else:
                    # No clustering - provide quality-aware guidance instead of success prompt
                    results = getattr(self.app_controller, 'snid_results', None)
                    fm = getattr(results, 'filtered_matches', []) if results else []
                    if not fm:
                        QtWidgets.QMessageBox.information(
                            self,
                            "No Reliable Matches",
                            (
                                "The analysis completed, but no reliable matches were found above the best-metric threshold.\n\n"
                                "Try Advanced Preprocessing (smoothing, wavelength masks, continuum adjustments) to improve the results."
                            )
                        )
                    elif _is_weak_match(results):
                        QtWidgets.QMessageBox.information(
                            self,
                            "Weak Matches",
                            (
                                "Only weak match(es) were found above the best-metric threshold. Results may be unreliable.\n\n"
                                "You can try Advanced Preprocessing (smoothing, wavelength masks, continuum adjustments) to improve the results."
                            )
                        )
                    else:
                        reply = QtWidgets.QMessageBox.question(
                            self,
                            "Analysis Complete",
                            "Analysis completed. View classification results now?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            QtWidgets.QMessageBox.Yes
                        )
                        if reply == QtWidgets.QMessageBox.Yes:
                            QtCore.QTimer.singleShot(100, self.show_analysis_results)
                
                _LOGGER.info("🎉 GUI updated after successful analysis completion")
            else:
                # Determine if this is an inconclusive outcome (no good matches) vs a hard failure
                results = getattr(self.app_controller, 'snid_results', None)
                has_good_cluster = False
                try:
                    if hasattr(self.app_controller, '_has_good_cluster'):
                        has_good_cluster = self.app_controller._has_good_cluster(results)
                except Exception:
                    has_good_cluster = False

                num_best = 0
                try:
                    if results and hasattr(results, 'best_matches') and results.best_matches:
                        num_best = len(results.best_matches)
                except Exception:
                    num_best = 0

                is_inconclusive = bool((results is not None) and (not has_good_cluster or num_best == 0))

                if is_inconclusive:
                    # Inconclusive: no good matches found – guide the user
                    self.status_label.setText("Analysis inconclusive – no good matches found")
                    self.config_status_label.setText("Inconclusive")
                    self.config_status_label.setStyleSheet("font-style: italic; color: #d97706; font-size: 10px !important; font-weight: normal !important; font-family: 'Arial', 'Helvetica', 'Segoe UI', 'Ubuntu', 'DejaVu Sans', sans-serif !important; line-height: 1.0 !important;")

                    # Offer the user next actions: rerun with looser thresholds or jump to advanced preprocessing
                    msg = QtWidgets.QMessageBox(self)
                    msg.setIcon(QtWidgets.QMessageBox.Information)
                    msg.setWindowTitle("No Good Matches Found")
                    msg.setText("The analysis completed, but no reliable matches were found.")
                    msg.setInformativeText(
                        "What would you like to do?\n\n"
                        "Try the following to improve results:\n"
                        "• Use Advanced Preprocessing (smoothing, wavelength masks, continuum).\n"
                        "• Adjust the redshift search range or try a manual redshift estimate.\n"
                        "• Mask strong sky/telluric features; increase S/N if possible.\n"
                        "• Reduce spectrum–template overlap threshold (lapmin) to allow more partial matches."
                    )

                    rerun_btn = msg.addButton("Rerun with looser parameters", QtWidgets.QMessageBox.AcceptRole)
                    prep_btn = msg.addButton("Advanced preprocessing", QtWidgets.QMessageBox.ActionRole)
                    cancel_btn = msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
                    msg.setDefaultButton(rerun_btn)

                    msg.exec()

                    clicked = msg.clickedButton()
                    if clicked == rerun_btn:
                        self._rerun_with_looser_parameters()
                    elif clicked == prep_btn:
                        self.open_preprocessing_dialog()
                    else:
                        # Cancel / close: keep the UI in the inconclusive state
                        _ = cancel_btn
                else:
                    # Hard failure
                    self.status_label.setText("SNID-SAGE analysis failed")
                    self.config_status_label.setText("Analysis Failed")
                    self.config_status_label.setStyleSheet("font-style: italic; color: #ef4444;")

                    # Enhanced error messaging based on analysis type
                    error_info = getattr(self.app_controller, 'last_analysis_error', None)

                    if error_info and error_info.get('type') == 'forced_redshift':
                        # Specific messaging for forced redshift failures
                        context = error_info.get('context', 'forced redshift analysis')
                        error_msg = error_info.get('error', 'Unknown error')

                        QtWidgets.QMessageBox.critical(
                            self,
                            "Forced Redshift Analysis Failed",
                            f"The {context} failed to complete.\n\n"
                            f"Error: {error_msg}\n\n"
                            "Common solutions:\n"
                            "• Check that the forced redshift value is reasonable (0 < z < 2)\n"
                            "• Verify your spectrum preprocessing settings\n"
                            "• Try using automatic redshift search instead\n"
                            "• Check that templates are properly loaded\n\n"
                            "Please check the analysis logs for detailed error information."
                        )
                    else:
                        # Standard error messaging for normal analysis
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Analysis Failed",
                            "SNID analysis failed to complete.\n\n"
                            "Please check the analysis logs for detailed error information.\n"
                            "You may need to verify your spectrum preprocessing or template configuration."
                        )
        except Exception as e:
            _LOGGER.error(f"Error handling analysis completion: {e}")

    def _rerun_with_looser_parameters(self) -> None:
        """Rerun the last analysis with looser match thresholds (GUI helper).

        Uses the last analysis kwargs when available; otherwise falls back to the
        currently configured analysis parameters stored on the controller config.
        """
        try:
            if not hasattr(self, 'app_controller') or self.app_controller is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Rerun Not Available",
                    "Cannot rerun because the analysis controller is not available."
                )
                return

            base_kwargs: Dict[str, Any] = {}

            # Preferred: reuse the exact kwargs used for the previous run (preserves z-range, filters, etc.)
            last_kwargs = getattr(self.app_controller, 'last_analysis_kwargs', None)
            if isinstance(last_kwargs, dict) and last_kwargs:
                base_kwargs = dict(last_kwargs)
            else:
                # Fallback: use currently configured parameters from the controller config (if any)
                current_cfg = getattr(self.app_controller, 'current_config', None)
                if isinstance(current_cfg, dict):
                    analysis_cfg = current_cfg.get('analysis', {})
                    if isinstance(analysis_cfg, dict) and analysis_cfg:
                        base_kwargs = dict(analysis_cfg)

            if not base_kwargs:
                QtWidgets.QMessageBox.information(
                    self,
                    "Rerun Not Available",
                    "No previous analysis parameters were found.\n\n"
                    "Please run an analysis first (or open the configuration dialog) and then try again."
                )
                return

            # Looser thresholds (as requested)
            base_kwargs['hsigma_lap_ccc_threshold'] = 1.0
            base_kwargs['lapmin'] = 0.25

            # Keep controller config in sync so subsequent opens show the looser values
            try:
                if hasattr(self.app_controller, 'current_config') and isinstance(self.app_controller.current_config, dict):
                    if 'analysis' not in self.app_controller.current_config or not isinstance(self.app_controller.current_config.get('analysis'), dict):
                        self.app_controller.current_config['analysis'] = {}
                    self.app_controller.current_config['analysis'].update({
                        'hsigma_lap_ccc_threshold': 1.0,
                        'lapmin': 0.25,
                    })
            except Exception:
                pass

            try:
                if hasattr(self, 'status_label'):
                    self.status_label.setText("Rerunning analysis with looser parameters (HσLAP-CCC ≥ 1.0, lapmin ≥ 0.25)...")
                if hasattr(self, 'config_status_label'):
                    self.config_status_label.setText("Rerun (looser parameters)")
                    self.config_status_label.setStyleSheet(
                        "font-style: italic; color: #2563eb; font-size: 10px !important; font-weight: normal !important; "
                        "font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;"
                    )
            except Exception:
                pass

            started = False
            try:
                started = bool(self.app_controller.run_analysis(**base_kwargs))
            except Exception as e:
                _LOGGER.error(f"Error starting rerun with looser parameters: {e}")
                started = False

            if not started:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Rerun Failed",
                    "Failed to start the rerun with looser parameters.\n\n"
                    "Please check the logs for details."
                )
        except Exception as e:
            _LOGGER.error(f"Unexpected error while rerunning analysis: {e}")
            try:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Rerun Error",
                    f"An unexpected error occurred while trying to rerun analysis:\n{str(e)}"
                )
            except Exception:
                pass
    
    def _on_preprocessing_completed(self, success: bool):
        """Handle preprocessing completion signal from app controller"""
        try:
            if success:
                self.status_label.setText("Spectrum preprocessing completed")
                self.preprocess_status_label.setText("Preprocessed")
                self.preprocess_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                _LOGGER.info("GUI updated after successful preprocessing completion")
            else:
                self.status_label.setText("Spectrum preprocessing failed")
                self.preprocess_status_label.setText("Failed")
                self.preprocess_status_label.setStyleSheet("font-style: italic; color: #dc2626; font-size: 10px;")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Preprocessing Failed",
                    "Spectrum preprocessing failed. Please check the parameters and try again."
                )
        except Exception as e:
            _LOGGER.error(f"Error handling preprocessing completion: {e}")
    
    def _on_workflow_state_changed(self, new_state):
        """Handle workflow state change signal from app controller"""
        try:
            _LOGGER.debug(f"Workflow state changed to: {new_state}")
            # The workflow manager will handle button state updates
            if hasattr(self, 'workflow_manager'):
                self.workflow_manager.update_state(new_state)
        except Exception as e:
            _LOGGER.error(f"Error handling workflow state change: {e}")
    
    def _on_progress_updated(self, message: str, progress: float):
        """Handle progress update signal from app controller"""
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                # Derive a stable, human-friendly stage name from message content
                normalized = (message or "").lower()
                stage = self._current_progress_stage

                if any(k in normalized for k in ["initializing", "starting snid correlation analysis", "starting snid analysis engine", "starting quick", "starting advanced"]):
                    stage = "Initialization"
                elif "preprocess" in normalized:
                    stage = "Preprocessing"
                elif any(k in normalized for k in [
                    "loading configuration",
                    "loading template library",
                    "loading templates",
                    "templates loaded",
                    "preparing to load"
                ]):
                    # Treat template library load as part of Initialization so the bar advances meaningfully
                    stage = "Initialization"
                elif any(k in normalized for k in ["correlation", "template matching", "running template"]):
                    stage = "Correlation Analysis"
                elif any(k in normalized for k in ["processing analysis results", "clustering", "gmm", "statistics"]):
                    stage = "Results & Clustering"
                elif any(k in normalized for k in ["completed", "analysis complete"]):
                    stage = "Complete"

                # Only update stage label if it actually changed to avoid flicker
                if stage != self._current_progress_stage:
                    self._current_progress_stage = stage

                # Compute display percentage, restarting from 0 for clustering stage
                display_progress = 0
                if stage == "Results & Clustering":
                    # On first entry to clustering, ensure we start from 0
                    # Reset happens implicitly when changing stage; no separate bar used
                    # Prefer exact i/n parsing from message
                    pct_local = None
                    try:
                        if "clustering type" in normalized and "(" in (message or "") and "/" in (message or "") and ")" in (message or ""):
                            import re
                            m = re.search(r"\((\d+)\s*/\s*(\d+)\)", message)
                            if m:
                                i = int(m.group(1))
                                n = max(1, int(m.group(2)))
                                pct_local = int(round((i / n) * 100))
                    except Exception:
                        pct_local = None

                    # Fallback: map overall progress window (e.g., 90-98%) to 0-100%
                    if pct_local is None:
                        try:
                            cluster_min = 90.0
                            cluster_max = 98.0
                            base = max(cluster_min, min(cluster_max, float(progress)))
                            pct_local = int(round(((base - cluster_min) / max(1.0, (cluster_max - cluster_min))) * 100))
                        except Exception:
                            pct_local = 0

                    display_progress = max(0, min(100, pct_local))
                elif stage == "Complete":
                    display_progress = 100
                else:
                    display_progress = int(progress)

                self.progress_dialog.set_stage(self._current_progress_stage, display_progress)

                # Still show the raw progress message in the log panel (when non-empty)
                if message and message.strip():
                    self.progress_dialog.add_progress_line(message, "info")

                # Track last stage (used implicitly for future logic if needed)
                self._last_stage = stage
        except Exception as e:
            _LOGGER.error(f"Error handling progress update: {e}")

    @QtCore.Slot(int, str, float)
    def _on_ordered_progress_updated(self, seq: int, message: str, progress: float):
        """Handle strictly ordered progress updates (seq-enforced)."""
        try:
            # Reuse same rendering logic but trust ordering from controller
            self._on_progress_updated(message, progress)
        except Exception as e:
            _LOGGER.error(f"Error handling ordered progress update: {e}")
    
    # View management - delegate to event handlers
    def _on_view_change(self, view_type):
        """Handle view change - delegate to event handlers"""
        if hasattr(self, 'event_handlers'):
            self.event_handlers.on_view_change(view_type)
    
    def switch_view_mode(self):
        """Switch view mode - delegate to event handlers"""
        if hasattr(self, 'event_handlers'):
            self.event_handlers.on_switch_view_mode()
    
    # Original view management for reference
    def _on_view_change_original(self, view_type):
        """Handle view toggle changes"""
        try:
            _LOGGER.info(f"🔄 View change requested: {view_type}")
            
            # CRITICAL: Only prevent switching to Flat view if we don't have any spectrum data
            # or if we have spectrum data but preprocessing has never been completed
            from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
            current_state = self.app_controller.get_current_state()
            
            # Block flat view only if:
            # 1. No spectrum loaded at all (INITIAL state), OR
            # 2. Spectrum loaded but never preprocessed (FILE_LOADED state)
            if view_type == 'flat' and current_state in [WorkflowState.INITIAL, WorkflowState.FILE_LOADED]:
                _LOGGER.warning("🚫 Flat view requested but preprocessing not completed")
                # Show warning and revert to Flux view
                QtWidgets.QMessageBox.warning(
                    self,
                    "Preprocessing Required",
                    "Flat view requires preprocessing.\n\n"
                    "Please run preprocessing first to enable flat spectrum view."
                )
                # Force Flux view
                view_type = 'flux'
            
            self.current_view = view_type
            
            # CRITICAL: Use unified layout manager for consistent button state management
            # instead of direct styling that overrides workflow state management
            if view_type == 'flux':
                # Determine if both buttons should be enabled based on workflow state
                flux_enabled = True  # Flux should be enabled after FILE_LOADED
                flat_enabled = current_state not in [WorkflowState.INITIAL, WorkflowState.FILE_LOADED]
                
                self.unified_layout_manager.update_flux_flat_button_states(
                    self,
                    flux_active=True,    # Flux becomes active
                    flat_active=False,   # Flat becomes inactive
                    flux_enabled=flux_enabled,
                    flat_enabled=flat_enabled
                )
            else:  # flat view
                # Both buttons should be enabled if we reached this point (flat view allowed)
                self.unified_layout_manager.update_flux_flat_button_states(
                    self,
                    flux_active=False,   # Flux becomes inactive
                    flat_active=True,    # Flat becomes active
                    flux_enabled=True,   # Both enabled since flat is accessible
                    flat_enabled=True
                )
            
            
            if self.current_plot_mode != PlotMode.SPECTRUM:
                _LOGGER.info("Flux/Flat button pressed - returning to spectrum mode")
                self._switch_to_plot_mode(PlotMode.SPECTRUM)
            
            # Always try to update plot
            # This ensures view changes are reflected immediately
            wave, flux = self.app_controller.get_spectrum_for_view(view_type)
            if wave is not None and flux is not None:
                _LOGGER.info(f"📊 Plotting spectrum in {view_type} view")
                self._plot_spectrum()
                
        except Exception as e:
            _LOGGER.error(f"❌ Error handling view change: {e}")
            import traceback
            traceback.print_exc()
    
    def switch_view_mode(self):
        """Switch between view modes (Space key)"""
        try:
            if self.current_view == 'flux':
                # Check workflow state - only block if no spectrum or spectrum never preprocessed
                from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                current_state = self.app_controller.get_current_state()
                
                if current_state not in [WorkflowState.INITIAL, WorkflowState.FILE_LOADED]:
                    self._on_view_change('flat')
                else:
                    _LOGGER.info("🚫 Cannot switch to Flat view - preprocessing required")
            else:
                self._on_view_change('flux')
        except Exception as e:
            _LOGGER.error(f"❌ Error switching view mode: {e}")
    
    # Template navigation methods
    def show_previous_template(self):
        """Navigate to previous template (alias for button connection)"""
        try:
            _LOGGER.debug("Previous template requested via button")
            
            # Check if we have SNID results and templates
            if (hasattr(self.app_controller, 'snid_results') and 
                self.app_controller.snid_results and 
                hasattr(self.app_controller.snid_results, 'best_matches') and 
                self.app_controller.snid_results.best_matches):
                
                # Get current template index
                if not hasattr(self.app_controller, 'current_template'):
                    self.app_controller.current_template = 0
                
                # Navigate to previous template
                if self.app_controller.current_template > 0:
                    self.app_controller.current_template -= 1
                    _LOGGER.info(f"📖 Navigated to template {self.app_controller.current_template + 1}")
                    
                    # Update plot with new template using plot_manager directly (like keyboard shortcuts)
                    if hasattr(self, 'plot_manager'):
                        self.plot_manager.plot_spectrum(self.current_view)
                else:
                    _LOGGER.debug("Already at first template")
            else:
                _LOGGER.debug("No SNID results available for template navigation")
                
        except Exception as e:
            _LOGGER.error(f"❌ Error navigating to previous template: {e}")
    
    def show_next_template(self):
        """Navigate to next template (alias for button connection)"""
        try:
            _LOGGER.debug("Next template requested via button")
            
            # Check if we have SNID results and templates
            if (hasattr(self.app_controller, 'snid_results') and 
                self.app_controller.snid_results and 
                hasattr(self.app_controller.snid_results, 'best_matches') and 
                self.app_controller.snid_results.best_matches):
                
                # Get current template index
                if not hasattr(self.app_controller, 'current_template'):
                    self.app_controller.current_template = 0
                
                max_templates = len(self.app_controller.snid_results.best_matches)
                
                # Navigate to next template
                if self.app_controller.current_template < max_templates - 1:
                    self.app_controller.current_template += 1
                    _LOGGER.info(f"📖 Navigated to template {self.app_controller.current_template + 1}")
                    
                    # Update plot with new template using plot_manager directly (like keyboard shortcuts)
                    if hasattr(self, 'plot_manager'):
                        self.plot_manager.plot_spectrum(self.current_view)
                else:
                    _LOGGER.debug("Already at last template")
            else:
                _LOGGER.debug("No SNID results available for template navigation")
                
        except Exception as e:
            _LOGGER.error(f"❌ Error navigating to next template: {e}")
    
    # Users can switch between Flux and Flat using the dedicated Flux/Flat buttons
    
        # Analysis workflow methods
    def update_results_display(self, result):
        """Update the main GUI with analysis results"""
        if not result or not hasattr(result, 'success') or not result.success:
            _LOGGER.warning("⚠️ Analysis did not succeed - no results to display")
            return
            
        try:
            # Store results
            self.app_controller.snid_results = result
            
            # Reset template index to show first template
            self.app_controller.current_template = 0
            
            # CRITICAL: Refresh workflow manager button states now that templates are available
            # This will trigger the template availability check for navigation buttons
            if hasattr(self, 'workflow_manager'):
                self.workflow_manager.refresh_button_states()
                _LOGGER.debug("🔄 Workflow manager button states refreshed after results available")
            
            # Update status with type/subtype (handles manual selection messaging)
            try:
                self.status_label.setText(self._compose_classification_header(result))
            except Exception:
                self.status_label.setText(f"Classification: {getattr(result, 'consensus_type', 'Unknown')}")
            
            # Enable plot buttons if available
            for btn in getattr(self, 'analysis_plot_buttons', []):
                btn.setEnabled(True)
            for btn in getattr(self, 'nav_buttons', []):
                btn.setEnabled(True)
            
            # Enable advanced features
            if hasattr(self, 'emission_line_overlay_btn'):
                self.emission_line_overlay_btn.setEnabled(True)
            if hasattr(self, 'ai_assistant_btn'):
                self.ai_assistant_btn.setEnabled(True)
            
            # CRITICAL: Immediately plot template overlays on the main plot
            # This ensures the user sees the overlaid spectrum+template immediately after cluster selection
            _LOGGER.info("🎯 Plotting template overlays in main GUI after analysis completion")
            self._plot_spectrum()  # This will now show template overlays since we have results
            
            _LOGGER.debug(f"Results display updated - best match: {getattr(result, 'template_name', 'Unknown')}")
            
        except Exception as e:
            _LOGGER.error(f"Error updating results display: {e}")
    
    def enable_plot_navigation(self):
        """Enable plot navigation controls after analysis completion"""
        try:
            # Enable navigation buttons
            for btn in getattr(self, 'nav_buttons', []):
                btn.setEnabled(True)
            
            # Enable analysis plot buttons
            for btn in getattr(self, 'analysis_plot_buttons', []):
                btn.setEnabled(True)
            
            # CRITICAL: Refresh workflow manager button states to ensure proper styling
            if hasattr(self, 'workflow_manager'):
                self.workflow_manager.refresh_button_states()
                _LOGGER.debug("🔄 Workflow manager button states refreshed in enable_plot_navigation")
            
            _LOGGER.debug("Plot navigation enabled")
            
        except Exception as e:
            _LOGGER.error(f"Error enabling plot navigation: {e}")
    
    def refresh_results_displays(self):
        """Refresh all results displays after cluster selection"""
        try:
            _LOGGER.info("🔄 Refreshing results displays after cluster selection...")
            
            # Get the current results
            snid_results = getattr(self.app_controller, 'snid_results', None)
            if not snid_results:
                _LOGGER.warning("No SNID results available to refresh displays")
                return
            
            # Update status label with new classification header
            try:
                self.status_label.setText(self._compose_classification_header(snid_results))
            except Exception:
                self.status_label.setText(f"Classification: {getattr(snid_results, 'consensus_type', 'Unknown')}")
            
            # Update config status
            self.config_status_label.setText("Analysis Complete (Cluster Updated)")
            self.config_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
            
            # Ensure all navigation and plot buttons are enabled
            for btn in getattr(self, 'nav_buttons', []):
                btn.setEnabled(True)
            for btn in getattr(self, 'analysis_plot_buttons', []):
                btn.setEnabled(True)
            
            # Refresh workflow manager button states
            if hasattr(self, 'workflow_manager'):
                self.workflow_manager.refresh_button_states()
            
            _LOGGER.info("Results displays refreshed successfully")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error refreshing results displays: {e}")
    
    def show_results_summary(self, result):
        """Show unified analysis summary by staying in main window (skip automatic results dialog)"""
        try:
            _LOGGER.info("Cluster selection completed - staying in main window (skipping automatic results dialog)")
            
            # Do not automatically show the results dialog; users can access it via the Analysis menu
            
            # Just update the main window status to indicate completion
            cluster_info = ""
            if hasattr(result, 'clustering_results') and result.clustering_results:
                if result.clustering_results.get('user_selected_cluster'):
                    cluster_info = " [User Selected Cluster]"
                elif result.clustering_results.get('best_cluster'):
                    cluster_info = " [Auto Selected Cluster]"
            
            # Update main window to show analysis is complete
            status_msg = f"Analysis Complete: {getattr(result, 'template_name', 'Unknown')} ({getattr(result, 'consensus_type', 'Unknown')}){cluster_info}"
            if hasattr(self, 'update_header_status'):
                self.update_header_status(status_msg)
            
            # Start blinking effect on cluster summary button to draw user attention
            self.start_cluster_summary_blinking()
            
            # Ensure main window has focus and is brought to the front
            try:
                self.raise_()  # Bring window to front on all platforms
                self.activateWindow()  # Give the window focus
                _LOGGER.debug("Main window brought to front and focused")
            except Exception as focus_error:
                _LOGGER.warning(f"Could not bring main window to front: {focus_error}")
            
            _LOGGER.info(f"Analysis complete - user remains in main window. Results available via Analysis menu.")
            
        except Exception as e:
            _LOGGER.error(f"Error showing results summary: {e}")
            # Fallback to simple message if status update fails
            try:
                cluster_info = ""
                if hasattr(result, 'clustering_results') and result.clustering_results:
                    if result.clustering_results.get('user_selected_cluster'):
                        cluster_info = " [User Selected Cluster]"
                    elif result.clustering_results.get('best_cluster'):
                        cluster_info = " [Auto Selected Cluster]"
                
                # Use best available metric (HσLAP-CCC preferred)
                from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
                if hasattr(result, 'best_matches') and result.best_matches:
                    best_metric_value = get_best_metric_value(result.best_matches[0])
                    metric_name = get_best_metric_name(result.best_matches[0])
                    metric_text = f"{metric_name}: {best_metric_value:.2f}"
                else:
                    metric_text = f"HLAP: {float(getattr(result, 'hlap', 0.0) or 0.0):.2f}"
                
                summary = (f"SNID Analysis Complete!\n\n"
                          f"Best match: {getattr(result, 'template_name', 'Unknown')}\n"
                          f"Type: {getattr(result, 'consensus_type', 'Unknown')}\n"
                          f"Redshift: {getattr(result, 'redshift', 0.0):.6f}\n"
                          f"{metric_text}{cluster_info}")
                
                # Show non-blocking message as fallback
                QtWidgets.QMessageBox.information(self, "Analysis Complete", summary)
            except Exception as fallback_error:
                _LOGGER.error(f"Error in fallback message: {fallback_error}")
    
    def update_header_status(self, status_message):
        """Update header status message"""
        try:
            self.status_label.setText(status_message)
        except Exception as e:
            _LOGGER.error(f"Error updating header status: {e}")

    # Analysis methods
    def show_analysis_results(self):
        """Show analysis results dialog - delegate to analysis menu manager"""
        try:
            if self.analysis_menu_manager:
                self.analysis_menu_manager.show_analysis_results()
            else:
                QtWidgets.QMessageBox.information(
                    self, 
                    "Analysis Results", 
                    "Analysis menu manager not available."
                )
        except Exception as e:
            _LOGGER.error(f"Error showing analysis results: {e}")
    
    def show_gmm_clustering(self):
        """Show GMM clustering visualization - delegate to analysis menu manager"""
        try:
            if self.analysis_menu_manager:
                self.analysis_menu_manager.show_gmm_clustering()
            else:
                QtWidgets.QMessageBox.information(
                    self, 
                    "GMM Clustering", 
                    "Analysis menu manager not available."
                )
        except Exception as e:
            _LOGGER.error(f"Error showing GMM clustering: {e}")
    
    def show_gmm_clusters(self):
        """Show GMM clusters - alias for show_gmm_clustering (matches button configuration)"""
        self.show_gmm_clustering()
    
    def show_cluster_summary(self):
        """Show cluster summary dialog - delegates to analysis results dialog"""
        try:
            _LOGGER.debug("📊 Cluster summary requested via button")
            
            # Stop blinking effect when user clicks the button for the first time
            if self.cluster_summary_blinking and not self.cluster_summary_clicked_once:
                self.stop_cluster_summary_blinking()
                self.cluster_summary_clicked_once = True
                _LOGGER.debug("🔴 Stopped cluster summary button blinking on first click")
            
            # Check if analysis results are available
            if not hasattr(self.app_controller, 'snid_results') or self.app_controller.snid_results is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No Results",
                    "No analysis results available.\nPlease run the SNID analysis first."
                )
                return
            
            # Delegate to the comprehensive analysis results dialog
            self.show_analysis_results()
            _LOGGER.info("📊 Cluster summary (analysis results) dialog opened")
                
        except Exception as e:
            _LOGGER.error(f"❌ Error showing cluster summary: {e}")
    
    def start_cluster_summary_blinking(self):
        """Start blinking red edge effect on cluster summary button"""
        try:
            if self.cluster_summary_blinking or self.cluster_summary_clicked_once:
                _LOGGER.debug(f"🔴 Skipping blinking start: already_blinking={self.cluster_summary_blinking}, clicked_once={self.cluster_summary_clicked_once}")
                return  # Already blinking or user has already clicked once
            
            if not hasattr(self, 'cluster_summary_btn') or self.cluster_summary_btn is None:
                _LOGGER.warning("Cluster summary button not found, cannot start blinking")
                return
            
            # Debug: Log button state before starting
            _LOGGER.debug(f"🔴 Starting blinking - button enabled: {self.cluster_summary_btn.isEnabled()}, object name: {self.cluster_summary_btn.objectName()}")
            
            # Store original style
            self.cluster_summary_original_style = self.cluster_summary_btn.styleSheet()
            _LOGGER.debug(f"🔴 Stored original style: {self.cluster_summary_original_style[:100]}...")
            
            # Ensure button has proper object name for targeting
            object_name = self.cluster_summary_btn.objectName()
            if not object_name:
                object_name = "unified_cluster_summary_btn"
                self.cluster_summary_btn.setObjectName(object_name)
                _LOGGER.debug(f"🔴 Set button object name to: {object_name}")
            
            # Initialize blinking state
            self.cluster_summary_blinking = True
            self.cluster_summary_blink_state = False
            
            # Create and start timer - 1 second intervals as requested
            self.cluster_summary_blink_timer = QtCore.QTimer()
            self.cluster_summary_blink_timer.timeout.connect(self._toggle_cluster_summary_blink)
            self.cluster_summary_blink_timer.start(1000)  # 1 second intervals
            
            _LOGGER.info("🔴 Started cluster summary button blinking effect")
            
            # Force initial blink state to make it immediately visible
            self._toggle_cluster_summary_blink()
            
        except Exception as e:
            _LOGGER.error(f"Error starting cluster summary blinking: {e}")
            import traceback
            _LOGGER.debug(f"Blinking start error traceback: {traceback.format_exc()}")
    
    def stop_cluster_summary_blinking(self):
        """Stop blinking red edge effect on cluster summary button"""
        try:
            if not self.cluster_summary_blinking:
                return
            
            # Stop timer
            if self.cluster_summary_blink_timer:
                self.cluster_summary_blink_timer.stop()
                self.cluster_summary_blink_timer = None
            
            # Restore original style using workflow manager if available
            if hasattr(self, 'cluster_summary_btn') and self.cluster_summary_btn is not None:
                if hasattr(self, 'workflow_manager') and self.workflow_manager:
                    # Let workflow manager handle the styling restoration
                    try:
                        button_def = self.workflow_manager._get_button_definitions().get('cluster_summary_btn')
                        if button_def:
                            self.workflow_manager._set_button_state(self.cluster_summary_btn, True, button_def.color_type)
                            _LOGGER.debug("🔴 Restored cluster summary button to workflow styling")
                        else:
                            # Fallback to default style
                            self.cluster_summary_btn.setStyleSheet("font-size: 12pt; font-weight: bold;")
                    except Exception as e:
                        _LOGGER.debug(f"Could not restore workflow styling: {e}")
                        # Fallback to original or default style
                        if self.cluster_summary_original_style is not None:
                            self.cluster_summary_btn.setStyleSheet(self.cluster_summary_original_style)
                        else:
                            self.cluster_summary_btn.setStyleSheet("font-size: 12pt; font-weight: bold;")
                else:
                    # No workflow manager - use stored original style or fallback
                    if self.cluster_summary_original_style is not None:
                        self.cluster_summary_btn.setStyleSheet(self.cluster_summary_original_style)
                    else:
                        self.cluster_summary_btn.setStyleSheet("font-size: 12pt; font-weight: bold;")
            
            # Reset state
            self.cluster_summary_blinking = False
            self.cluster_summary_original_style = None
            
            _LOGGER.debug("🔴 Stopped cluster summary button blinking effect")
            
        except Exception as e:
            _LOGGER.error(f"Error stopping cluster summary blinking: {e}")
    
    def _toggle_cluster_summary_blink(self):
        """Toggle the blinking state of cluster summary button"""
        try:
            if not self.cluster_summary_blinking or not hasattr(self, 'cluster_summary_btn'):
                return
            
            self.cluster_summary_blink_state = not self.cluster_summary_blink_state
            
            # Get button object name for specific targeting
            object_name = self.cluster_summary_btn.objectName()
            if not object_name:
                object_name = "unified_cluster_summary_btn"
                self.cluster_summary_btn.setObjectName(object_name)
            
            if self.cluster_summary_blink_state:
                # Red border while preserving the original blue workflow styling
                # Get the workflow manager's style for this button and add red border
                if hasattr(self, 'workflow_manager') and self.workflow_manager:
                    try:
                        button_def = self.workflow_manager._get_button_definitions().get('cluster_summary_btn')
                        if button_def:
                            # Get the original workflow button style
                            workflow_style = self.workflow_manager.theme_manager.get_workflow_button_style(button_def.color_type)
                            
                            # Add red border to the workflow style while maintaining Enhanced Button Manager sizing
                            blink_style = f"""
                            QPushButton#{object_name} {{
                                {workflow_style}
                                border: 2px solid #ef4444 !important;
                                font-size: 12pt !important;
                                font-weight: bold !important;
                                padding: 2px 4px !important;
                                min-height: 24px !important;
                                border-radius: 4px !important;
                            }}
                            """
                        else:
                            # Fallback with red border and consistent sizing
                            blink_style = f"""
                            QPushButton#{object_name} {{
                                font-size: 12pt !important;
                                font-weight: bold !important;
                                border: 2px solid #ef4444 !important;
                                padding: 2px 4px !important;
                                min-height: 24px !important;
                                border-radius: 4px !important;
                                background-color: #58508D !important;
                                color: white !important;
                            }}
                            """
                    except Exception as e:
                        _LOGGER.debug(f"Could not get workflow styling for blink: {e}")
                        # Fallback with red border and consistent sizing
                        blink_style = f"""
                        QPushButton#{object_name} {{
                            font-size: 12pt !important;
                            font-weight: bold !important;
                            border: 2px solid #ef4444 !important;
                            padding: 2px 4px !important;
                            min-height: 24px !important;
                            border-radius: 4px !important;
                            background-color: #58508D !important;
                            color: white !important;
                        }}
                        """
                else:
                    # No workflow manager - simple red border with consistent sizing
                    blink_style = f"""
                    QPushButton#{object_name} {{
                        font-size: 12pt !important;
                        font-weight: bold !important;
                        border: 2px solid #ef4444 !important;
                        padding: 2px 4px !important;
                        min-height: 24px !important;
                        border-radius: 4px !important;
                        background-color: #58508D !important;
                        color: white !important;
                    }}
                    """
            else:
                # Original style - restore to workflow manager style
                if hasattr(self, 'workflow_manager') and self.workflow_manager:
                    # Let workflow manager handle the styling restoration
                    try:
                        button_def = self.workflow_manager._get_button_definitions().get('cluster_summary_btn')
                        if button_def:
                            self.workflow_manager._set_button_state(self.cluster_summary_btn, True, button_def.color_type)
                            return
                    except Exception as e:
                        _LOGGER.debug(f"Could not restore workflow styling: {e}")
                
                # Fallback to original style with consistent sizing
                blink_style = self.cluster_summary_original_style or f"""
                QPushButton#{object_name} {{
                    font-size: 12pt !important;
                    font-weight: bold !important;
                    padding: 2px 4px !important;
                    min-height: 24px !important;
                    border-radius: 4px !important;
                    background-color: #58508D !important;
                    color: white !important;
                    border: 2px solid #58508D !important;
                }}
                """
            
            self.cluster_summary_btn.setStyleSheet(blink_style)
            
        except Exception as e:
            _LOGGER.error(f"Error toggling cluster summary blink: {e}")
            # Stop blinking on error to prevent infinite errors
            self.stop_cluster_summary_blinking()
    
    def _on_cluster_selection_needed(self, snid_result):
        """Handle cluster selection needed signal from app controller"""
        try:
            try:
                from snid_sage.snid.games import is_game_running, set_analysis_complete
                game_running = bool(is_game_running())
            except Exception:
                game_running = False

            # Check if auto-selection is enabled for extended quick workflow
            if getattr(self.app_controller, 'auto_select_best_cluster', False):
                _LOGGER.info("🤖 Auto-selecting best cluster for extended quick workflow")
                
                # Reset the flag
                self.app_controller.auto_select_best_cluster = False
                
                # Get the best cluster automatically
                clustering_results = snid_result.clustering_results
                clusters = clustering_results.get('all_candidates', [])
                
                if clusters:
                    # Find the best cluster (usually first one as they're pre-sorted)
                    best_cluster = clusters[0]
                    best_index = 0
                    
                    # If there's a specific 'best_cluster' in results, use that
                    if 'best_cluster' in clustering_results:
                        best_cluster = clustering_results['best_cluster']
                        # Find its index in all_candidates
                        for idx, cluster in enumerate(clusters):
                            if (cluster.get('type') == best_cluster.get('type') and 
                                cluster.get('cluster_id') == best_cluster.get('cluster_id')):
                                best_index = idx
                                break
                    
                    _LOGGER.info(f"🤖 Automatically selected best cluster: {best_cluster.get('type', 'Unknown')} "
                                f"(Size: {len(best_cluster.get('matches', []))}, "
                                f"Quality: {best_cluster.get('mean_metric', 0):.2f})")
                    
                    # Directly call the cluster selection handler
                    self.app_controller.on_cluster_selected(best_cluster, best_index, snid_result)
                else:
                    _LOGGER.warning("No clusters available for auto-selection")
                    self.app_controller._complete_analysis_workflow(snid_result)
                    self.app_controller.analysis_completed.emit(True)
                return
            
            _LOGGER.info("🎯 Cluster selection needed - showing cluster selection dialog")
            
            # Import the PySide6 cluster selection dialog
            from snid_sage.interfaces.gui.components.pyside6_dialogs.cluster_selection_dialog import show_cluster_selection_dialog
            
            clustering_results = snid_result.clustering_results
            
            # Extract cluster candidates from clustering results
            clusters = clustering_results.get('all_candidates', [])

            # If the user is playing the game, show a passive in-game badge so they know
            # results are ready, while letting the selection dialog open behind the game.
            if game_running:
                try:
                    set_analysis_complete()
                except Exception:
                    pass

            # If the analysis progress dialog is open, use it as the parent for the cluster
            # selection window. This ensures the cluster selection stays above the progress
            # dialog (but still behind the always-on-top game window while you play).
            dialog_parent = self
            try:
                progress_dialog = getattr(self, "progress_dialog", None)
                if progress_dialog is not None and hasattr(progress_dialog, "isVisible") and progress_dialog.isVisible():
                    dialog_parent = progress_dialog
            except Exception:
                dialog_parent = self
            
            # Show cluster selection dialog. If the game is running, show it non-modally and
            # without activating so it never steals focus (it will sit behind the always-on-top game).
            show_cluster_selection_dialog(
                parent=dialog_parent,
                clusters=clusters,
                snid_result=snid_result,
                callback=lambda cluster, index: self.app_controller.on_cluster_selected(cluster, index, snid_result),
                modal=(not game_running),
                show_without_activating=bool(game_running),
            )
            
        except Exception as e:
            _LOGGER.error(f"❌ Error showing cluster selection dialog: {e}")
            # Fallback - complete analysis without cluster selection
            self.app_controller._complete_analysis_workflow(snid_result)
            self.app_controller.analysis_completed.emit(True)
    
    def show_redshift_vs_age(self):
        """Show redshift vs age plot - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                self.plot_manager.switch_to_plot_mode(PlotMode.REDSHIFT_AGE)
        except Exception as e:
            _LOGGER.error(f"❌ Error showing redshift vs age: {e}")
    
    def show_subtype_proportions(self):
        """Show subtype proportions plot - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                self.plot_manager.switch_to_plot_mode(PlotMode.SUBTYPE_PROPS)
        except Exception as e:
            _LOGGER.error(f"❌ Error showing subtype proportions: {e}")
    
    # Utility callback functions

    
    def reset_gui(self):
        """Reset GUI to initial state."""
        # Delegate to the new method name
        self.reset_to_initial_state()
    
    def show_shortcuts_dialog(self):
        """Show keyboard shortcuts dialog"""
        try:
            from snid_sage.interfaces.gui.components.pyside6_dialogs.shortcuts_dialog import PySide6ShortcutsDialog
            
            dialog = PySide6ShortcutsDialog(self)
            dialog.exec()
            
            _LOGGER.debug("PySide6 Shortcuts dialog shown")
        except ImportError:
            # Fallback to simple message box if PySide6 dialog not available
            try:
                from snid_sage.interfaces.gui.utils.cross_platform_window import CrossPlatformWindowManager as CPW
                mod = CPW.platform_modifier_label()
            except Exception:
                mod = "Cmd" if sys.platform == "darwin" else "Ctrl"
            shortcuts_text = f"""
            <h3>SNID SAGE - Keyboard Shortcuts</h3>
            <p><b>Navigation:</b></p>
            <ul>
            <li>← → : Previous/Next template</li>
            
            <li>F : Toggle Flux view</li>
            <li>T : Toggle Flat view</li>
            </ul>
            <p><b>Analysis:</b></p>
            <ul>
            <li>{mod}+O : Load spectrum file</li>
            <li>{mod}+R : Run analysis</li>
            <li>{mod}+, : Open settings</li>
            <li>{mod}+S : Save plot (PNG/JPG)</li>
            <li>{mod}+Shift+S : Save plot (SVG)</li>
            </ul>
            <p><b>Note:</b></p>
            <ul>
            <li>Masking controls available in preprocessing and analysis dialogs</li>
            </ul>
            <p><b>Help:</b></p>
            <ul>
            <li>F1 or {mod}+/ : Show this help</li>
            </ul>
            """
            
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Keyboard Shortcuts")
            msg.setTextFormat(QtCore.Qt.RichText)
            msg.setText(shortcuts_text)
            msg.exec()
            
            _LOGGER.debug("Fallback shortcuts dialog shown")
        except Exception as e:
            _LOGGER.error(f"Error showing shortcuts dialog: {e}")



    def _plot_spectrum(self):
        """Plot the loaded spectrum data - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                if hasattr(self.app_controller, 'snid_results') and self.app_controller.snid_results:
                    # If we have analysis results, plot with template overlay
                    self.plot_manager.plot_spectrum_with_template_overlay(self.current_view)
                else:
                    # Just plot the spectrum without template
                    self.plot_manager.plot_spectrum(self.current_view)
        except Exception as e:
            _LOGGER.error(f"❌ Error plotting spectrum: {e}")
    
    def _plot_spectrum_with_template_overlay(self):
        """Plot spectrum with template overlay - delegate to plot manager"""
        try:
            if hasattr(self, 'plot_manager'):
                self.plot_manager.plot_spectrum_with_template_overlay(self.current_view)
        except Exception as e:
                        _LOGGER.error(f"❌ Error plotting template overlay: {e}")

    def closeEvent(self, event):
        """Handle window closing to clean up resources properly"""
        try:
            _LOGGER.info("🔴 PySide6 GUI window is closing, cleaning up resources...")
            
            # Stop cluster summary blinking timer if active
            if hasattr(self, 'cluster_summary_blink_timer') and self.cluster_summary_blink_timer:
                self.cluster_summary_blink_timer.stop()
                self.cluster_summary_blink_timer = None
                _LOGGER.debug("🔴 Cleaned up cluster summary blinking timer")
            
            # Stop any running analysis if in progress
            if hasattr(self, 'app_controller') and self.app_controller:
                if hasattr(self.app_controller, 'cancel_analysis'):
                    self.app_controller.cancel_analysis()
                    _LOGGER.debug("🛑 Cancelled any running analysis")
            
            # Close any child dialogs that might be open
            for child in self.findChildren(QtWidgets.QDialog):
                if child.isVisible():
                    child.close()
                    _LOGGER.debug(f"🔴 Closed child dialog: {child.__class__.__name__}")
            
            # Accept the close event
            event.accept()
            _LOGGER.info("✅ PySide6 GUI closed successfully")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error during GUI cleanup: {e}")
            # Accept the event anyway to ensure the window closes
            event.accept()


def setup_dpi_awareness():
    """Setup high-DPI awareness before creating application"""
    # In PySide6/Qt 6, high-DPI scaling is enabled by default and automatic
    # No manual configuration needed - let Qt handle it properly
    _LOGGER.debug("Using PySide6 automatic high-DPI scaling (no manual configuration needed)")

def main(verbosity_args=None):
    """
    Main function to run the PySide6 SNID SAGE GUI
    
    Args:
        verbosity_args: Optional argparse.Namespace with verbosity settings
    """
    
    # Configure logging
    logger = None
    try:
        from snid_sage.shared.utils.logging import configure_from_args, get_logger, VerbosityLevel
        
        if verbosity_args:
            configure_from_args(verbosity_args, gui_mode=True)
        else:
            from snid_sage.shared.utils.logging import configure_logging
            configure_logging(verbosity=VerbosityLevel.QUIET, gui_mode=True)
            
        logger = get_logger('gui.pyside6_main')
        logger.info("PySide6 SNID SAGE GUI starting...")
        
    except ImportError:
        logger = None
    
    # Setup DPI awareness before creating application
    if logger:
        logger.debug("Setting up DPI awareness...")
    setup_dpi_awareness()
    
    # Set environment variable to indicate PySide6 GUI is running
    # This can be used by other modules to avoid backend conflicts
    os.environ['SNID_SAGE_GUI_BACKEND'] = 'PySide6'
    
    # Suppress Qt warnings before creating application
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.windows.debug=false'
    
    # Determine active profile strictly from CLI flag (ignore config/env); pass down explicitly
    try:
        launch_profile_id = None
        if verbosity_args is not None:
            launch_profile_id = getattr(verbosity_args, 'profile_id', None)
        launch_profile_id = (str(launch_profile_id).strip().lower() if launch_profile_id else 'optical')
    except Exception:
        launch_profile_id = 'optical'

    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)
    # Set a default application icon for all windows/dialogs
    try:
        from snid_sage.interfaces.ui_core.logo import get_logo_manager
        _icon_path = get_logo_manager().get_icon_path()
        if _icon_path:
            app.setWindowIcon(QtGui.QIcon(str(_icon_path)))
    except Exception:
        pass
    
    # Install custom message handler to suppress specific Qt warnings
    def qt_message_handler(mode, context, message):
        # Suppress specific Qt warnings that are non-critical
        if any(warning in message for warning in [
            "No Qt Window found for event",
            "WM_ACTIVATEAPP",
            "QWindowsContext::windowsProc",
            "Unhandled scheme",
            "QWindowsNativeFileDialogBase::shellItem"
        ]):
            return  # Silently ignore these warnings
        
        # For other messages, use default behavior
        if logger:
            if mode == QtCore.QtMsgType.QtDebugMsg:
                logger.debug(f"Qt: {message}")
            elif mode == QtCore.QtMsgType.QtWarningMsg:
                logger.warning(f"Qt: {message}")
            elif mode == QtCore.QtMsgType.QtCriticalMsg:
                logger.error(f"Qt: {message}")
            elif mode == QtCore.QtMsgType.QtFatalMsg:
                logger.critical(f"Qt: {message}")
    
    # Install the message handler
    try:
        QtCore.qInstallMessageHandler(qt_message_handler)
        if logger:
            logger.debug("Qt message handler installed to suppress non-critical warnings")
    except Exception as e:
        if logger:
            logger.warning(f"Could not install Qt message handler: {e}")
    
    
    if logger:
        try:
            # Check what OpenGL backend Qt is using
            import PySide6.QtOpenGL as QtOpenGL
            opengl_info = QtOpenGL.QOpenGLContext.globalShareContext()
            if opengl_info:
                logger.debug(f"Qt OpenGL Context: {opengl_info}")
            else:
                logger.debug("Qt OpenGL Context: None (software rendering active)")
        except Exception as e:
            logger.debug(f"Qt OpenGL check: {e} (likely using software rendering)")
        
        # Check Qt platform
        platform_name = app.platformName()
        logger.debug(f"Qt Platform: {platform_name}")
        logger.debug(f"Qt using software rendering: {os.environ.get('QT_OPENGL', 'none') == 'software'}")
    
    # Set Fusion style for consistent appearance across platforms
    app.setStyle("Fusion")
    if logger:
        logger.debug("Fusion style applied for cross-platform consistency")
    
    # Check PyQtGraph availability
    if not PYQTGRAPH_AVAILABLE:
        if logger:
            logger.warning("PyQtGraph not available - some features will be limited")
        else:
            print("⚠️ PyQtGraph not available - install with: pip install pyqtgraph")
    
    try:
        # Create main window
        if logger:
            logger.debug("Creating main window...")
        window = PySide6SNIDSageGUI(launch_profile_id)
        
        # Show window
        window.show()
        
        if logger:
            logger.info("PySide6 GUI created successfully and is visible!")

        # Non-blocking PyPI update check; show dialog only if an update is available
        try:
            from snid_sage.shared.utils.version_checker import VersionChecker

            def _notify_if_update_available(info: dict) -> None:
                try:
                    # Show a modal info dialog only when an update is available
                    def _show_dialog_if_needed():
                        try:
                            if info and info.get('update_available'):
                                try:
                                    from snid_sage.interfaces.gui.utils.pyside6_message_utils import showinfo
                                    current = info.get('current_version', 'unknown')
                                    # Suppress update dialog for development builds
                                    if isinstance(current, str) and 'dev' in current.lower():
                                        if logger:
                                            logger.debug("Skipping update dialog for development version: %s", current)
                                        return
                                    latest = info.get('latest_version', 'unknown')
                                    showinfo(
                                        "Update Available",
                                        f"SNID SAGE {current} → {latest}\nUpdate with: pip install --upgrade snid-sage",
                                        parent=window,
                                    )
                                except Exception:
                                    if logger:
                                        logger.debug("Failed to show update-available dialog", exc_info=True)
                                    pass
                        except Exception:
                            if logger:
                                logger.debug("Failed while handling update notification", exc_info=True)
                            pass

                    # Ensure UI interactions happen on the main Qt thread by
                    # binding the singleShot to a QObject that lives on the GUI thread
                    QtCore.QTimer.singleShot(0, window, _show_dialog_if_needed)
                except Exception:
                    if logger:
                        logger.debug("Update check callback failed", exc_info=True)
                    pass

            try:
                VersionChecker(timeout=3.0).check_for_updates_async(_notify_if_update_available)
            except Exception:
                if logger:
                    logger.debug("Failed to start asynchronous update check", exc_info=True)
                pass
        except Exception:
            # Silently ignore if version checker or GUI utils are unavailable
            if logger:
                logger.debug("Version checker not available; skipping update check")
            pass
        
        # Start event loop
        return app.exec()
        
    except Exception as e:
        error_msg = f"Error creating PySide6 GUI: {e}"
        if logger:
            logger.error(error_msg)
            logger.debug("GUI creation traceback:", exc_info=True)
        else:
            print(f"❌ {error_msg}")
        
        return 1


if __name__ == "__main__":
    sys.exit(main()) 