"""
PySide6 Multi-Step Spectral Line Analysis Dialog for SNID SAGE GUI (Refactored)
==============================================================================

A modern, step-by-step workflow for spectral line analysis.
This is the refactored version that uses separate modules for organization.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import json
import datetime
from PySide6 import QtWidgets, QtCore, QtGui

# PyQtGraph for plotting
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
    # Import enhanced plot widget
    from snid_sage.interfaces.gui.components.plots.enhanced_plot_widget import EnhancedPlotWidget
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None
    EnhancedPlotWidget = None

# Optional rest wavelength top axis support
try:
    from snid_sage.interfaces.gui.utils.pyqtgraph_rest_axis import RestWavelengthAxisItem
    _REST_AXIS_AVAILABLE = True
except Exception:
    _REST_AXIS_AVAILABLE = False
    RestWavelengthAxisItem = None  # type: ignore

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_emission_dialog_refactored')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_emission_dialog_refactored')

from snid_sage.shared.constants.physical import SUPERNOVA_EMISSION_LINES, SN_LINE_CATEGORIES, SPEED_OF_LIGHT_KMS

# Import platform configuration
from snid_sage.shared.utils.config.platform_config import get_platform_config

# Import refactored modules
from .emission_dialog_events import EmissionDialogEventHandlers
from .emission_dialog_ui import EmissionDialogUIBuilder

# Step 2 analysis (optional)
try:
    from .multi_step_emission_dialog_step2 import EmissionLineStep2Analysis
    STEP2_AVAILABLE = True
except ImportError:
    STEP2_AVAILABLE = False


class PySide6MultiStepEmissionAnalysisDialog(QtWidgets.QDialog):
    """
    Modern two-step emission line analysis dialog - Refactored PySide6 version
    
    This version uses separate modules for event handling and UI building
    to keep the main class manageable.
    """
    
    def __init__(self, parent, spectrum_data: Dict[str, np.ndarray], theme_manager=None, 
                 galaxy_redshift: float = 0.0, cluster_median_redshift: float = 0.0):
        """Initialize the multi-step emission line analysis dialog"""
        try:
            super().__init__(parent)
            
            # Store basic parameters
            self.parent_gui = parent
            self.spectrum_data = spectrum_data
            self.theme_manager = theme_manager
            
            # Basic setup
            self.current_step = 1
            self.total_steps = 2
            
            # Use cluster redshift as the host redshift (metric-weighted winner)
            self.host_redshift = cluster_median_redshift if cluster_median_redshift > 0 else galaxy_redshift
            self.velocity_shift = 0.0  # km/s ejecta velocity
            
            # Line data structures
            self.sn_lines = {}  # line_name -> (observed_wavelength, line_data)
            self.galaxy_lines = {}
            
            # Current mode for line selection
            self.current_mode = 'sn'  # 'sn' or 'galaxy'
            
            # UI components (will be created by UI builder)
            self.plot_widget = None
            self.plot_item = None
            self.left_panel = None
            
            # Performance optimization: Cache for overlay lines
            self._cached_overlay_lines = {}  # mode -> {redshift_key: [(name, wavelength, color), ...]}
            self._last_redshift_params = {}  # Track redshift changes to invalidate cache
            
            # Simple color scheme
            self.colors = self._get_theme_colors()
            
            # Initialize modular components
            self.event_handlers = EmissionDialogEventHandlers(self)
            self.ui_builder = EmissionDialogUIBuilder(self)
            
            # Step 2 analysis component (optional)
            if STEP2_AVAILABLE:
                self.step2_analysis = EmissionLineStep2Analysis(self)
            else:
                self.step2_analysis = None
                
            # Setup dialog
            self._setup_dialog()
            self._create_interface()
            
            _LOGGER.info("Refactored emission line dialog initialized successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing refactored emission line dialog: {e}")
            raise

    def showEvent(self, event):
        """Ensure the spectrum view is well centered when the dialog appears."""
        super().showEvent(event)
        try:
            if getattr(self, '_did_initial_center', False):
                return
            if not PYQTGRAPH_AVAILABLE or not self.plot_item:
                return
            wave = self.spectrum_data.get('wave', None)
            flux = self.spectrum_data.get('flux', None)
            if wave is None or flux is None:
                return
            if len(wave) == 0 or len(flux) == 0:
                return
            # Compute ranges with margins
            wmin = float(np.min(wave)); wmax = float(np.max(wave))
            fmin = float(np.min(flux)); fmax = float(np.max(flux))
            xpad = (wmax - wmin) * 0.05 if wmax > wmin else 10.0
            ypad = (fmax - fmin) * 0.10 if fmax > fmin else abs(fmax) * 0.10 + 1.0
            # Apply ranges and keep auto-range disabled
            try:
                self.plot_item.disableAutoRange()
            except Exception:
                self.plot_widget.enableAutoRange(axis='x', enable=False)
                self.plot_widget.enableAutoRange(axis='y', enable=False)
            self.plot_item.setXRange(wmin - xpad, wmax + xpad, padding=0)
            self.plot_item.setYRange(fmin - ypad, fmax + ypad, padding=0)
            self._did_initial_center = True
        except Exception:
            pass
    
    def _get_theme_colors(self):
        """Get color scheme from theme manager or use defaults"""
        if self.theme_manager:
            try:
                return {
                    'background': self.theme_manager.get_color('window_background', '#ffffff'),
                    'text_primary': self.theme_manager.get_color('text_primary', '#000000'),
                    'text_secondary': self.theme_manager.get_color('text_secondary', '#666666'),
                    'accent': self.theme_manager.get_color('accent', '#2563eb'),
                    'border': self.theme_manager.get_color('border', '#cbd5e1')
                }
            except:
                pass
        
        # Default colors
        return {
            'background': '#ffffff',
            'text_primary': '#000000', 
            'text_secondary': '#666666',
            'accent': '#2563eb',
            'border': '#cbd5e1'
        }
    
    def _setup_dialog(self):
        """Setup basic dialog properties"""
        self.setWindowTitle("Spectral Line Analysis - Step by Step")
        self.setModal(True)
        self.resize(1000, 600)  # Made narrower (was 1200) and less tall (was 800)
        self.setMinimumSize(900, 500)  # Also adjusted minimum size
    
    def _create_interface(self):
        """Create the main interface using UI builder"""
        try:
            main_layout = QtWidgets.QHBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)
            main_layout.setSpacing(10)
            
            # Left panel - Controls (without quick presets)
            self._create_left_panel(main_layout)
            
            # Right side - Vertical layout for toolbar + plot
            right_container = QtWidgets.QWidget()
            right_layout = QtWidgets.QVBoxLayout(right_container)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(8)
            
            # Add toolbar container at the top (different for step 1 vs step 2)
            self.toolbar_container = QtWidgets.QWidget()
            self.toolbar_layout = QtWidgets.QVBoxLayout(self.toolbar_container)
            self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
            
            # Initially create step 1 toolbar
            self.current_toolbar = self.ui_builder.create_compact_preset_toolbar()
            self.toolbar_layout.addWidget(self.current_toolbar)
            
            right_layout.addWidget(self.toolbar_container)
            
            # Add plot below the toolbar
            self._create_plot_widget(right_layout)
            
            main_layout.addWidget(right_container)
            
            # Initialize plot with spectrum data
            self._update_plot()
            
            # Initialize status display with correct counts
            self._update_status_display()
            
        except Exception as interface_error:
            _LOGGER.error(f"Error creating refactored interface: {interface_error}")
            raise
    
    def _create_left_panel(self, main_layout):
        """Create left control panel using UI builder (without quick presets)"""
        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        self.left_panel.setFixedWidth(280)
        
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(15)
        
        # Step header
        step_label = QtWidgets.QLabel(f"Step {self.current_step} of {self.total_steps}: Line Identification")
        step_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2563eb; margin-bottom: 10px;")
        left_layout.addWidget(step_label)
        
        # Add info section at the top
        self.ui_builder.create_info_section(left_layout)
        
        # Use UI builder for components
        self.ui_builder.create_redshift_controls(left_layout)
        self.ui_builder.create_mode_selection(left_layout) 
        self.ui_builder.create_status_display(left_layout)
        
        # Stretch to push buttons to bottom
        left_layout.addStretch()
        
        # Control buttons at the bottom
        self.ui_builder.create_control_buttons(left_layout)
        
        main_layout.addWidget(self.left_panel)
    
    def _create_plot_widget(self, layout):
        """Create enhanced plot widget with save functionality and add to layout"""
        # Create plot container frame with rounded edges (like main GUI)
        plot_frame = QtWidgets.QFrame()
        plot_frame.setObjectName("emission_dialog_plot_frame")
        plot_frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        plot_frame.setMinimumHeight(400)
        
        # Apply styling similar to main GUI plot frame
        plot_frame.setStyleSheet("""
            QFrame#emission_dialog_plot_frame {
                background-color: white;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        # Create layout for the plot frame
        plot_frame_layout = QtWidgets.QVBoxLayout(plot_frame)
        plot_frame_layout.setContentsMargins(8, 8, 8, 8)
        plot_frame_layout.setSpacing(0)
        
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget = EnhancedPlotWidget()
            self.plot_item = self.plot_widget.getPlotItem()
            
            self.plot_widget.setLabel('left', 'Flux')
            self.plot_widget.setLabel('bottom', 'Obs. Wavelength (Å)')
            self.plot_widget.setMinimumWidth(600)
            self.plot_widget.setMinimumHeight(400)
            # Show right axis (no label) and style
            try:
                self.plot_item.showAxis('right')
                ra = self.plot_item.getAxis('right')
                if ra:
                    ra.setTextPen('black')
                    ra.setPen('black')
                    ra.setStyle(showValues=False)
            except Exception:
                pass

            # Enable subtle grid matching main GUI style
            try:
                self.plot_item.showGrid(x=True, y=True, alpha=0.08)
            except Exception:
                pass

            # Improve fit within frame: add slight internal margins and view padding
            try:
                # Add small content margins to avoid clipping at top
                self.plot_item.setContentsMargins(6, 10, 6, 6)
                # Give the ViewBox some default padding for autoRange
                self.plot_item.getViewBox().setDefaultPadding(0.08)
                # Disable auto-ranging to prevent rescale on overlay additions
                try:
                    self.plot_item.disableAutoRange()
                except Exception:
                    # Fallback per-axis
                    self.plot_widget.enableAutoRange(axis='x', enable=False)
                    self.plot_widget.enableAutoRange(axis='y', enable=False)
            except Exception:
                pass
            
            # Connect mouse events for line interaction
            self.plot_widget.scene().sigMouseClicked.connect(self._on_plot_click)
            
            # Install event filter for keyboard events (Shift overlay)
            self.plot_widget.installEventFilter(self)
            self.plot_widget.setFocusPolicy(QtCore.Qt.ClickFocus)
            
            plot_frame_layout.addWidget(self.plot_widget)
            # Always show the save icon for this dialog's plot
            try:
                if hasattr(self.plot_widget, 'show_save_button'):
                    self.plot_widget.show_save_button()
            except Exception:
                pass
            # Attach rest wavelength top axis if available and set initial redshift
            try:
                if _REST_AXIS_AVAILABLE:
                    rest_axis = RestWavelengthAxisItem('top')  # type: ignore
                    try:
                        top_axis = self.plot_item.getAxis('top')
                        if top_axis is not None:
                            self.plot_item.layout.removeItem(top_axis)
                    except Exception:
                        pass
                    self.plot_item.layout.addItem(rest_axis, 1, 1)
                    rest_axis.linkToView(self.plot_item.vb)
                    # Initial z: prefer host_redshift (galaxy) for emission dialog; SN lines use effective internally
                    z0 = float(getattr(self, 'host_redshift', 0.0) or 0.0)
                    rest_axis.set_redshift(z0)
                    self._rest_axis = rest_axis
            except Exception:
                self._rest_axis = None
        else:
            # Fallback
            placeholder = QtWidgets.QLabel("PyQtGraph not available")
            placeholder.setAlignment(QtCore.Qt.AlignCenter)
            plot_frame_layout.addWidget(placeholder)
        
        # Add the containerized plot to the main layout
        layout.addWidget(plot_frame)
    
    # Essential methods that need to remain in main class
    def _on_base_redshift_changed(self, value):
        """Handle base redshift change"""
        self.host_redshift = value
        self._update_redshift_displays()
        self._update_all_lines()
        try:
            if hasattr(self, '_rest_axis') and self._rest_axis is not None:
                self._rest_axis.set_redshift(float(self.host_redshift or 0.0))
        except Exception:
            pass
    
    def _on_velocity_changed(self, value):
        """Handle velocity change"""
        self.velocity_shift = value
        self._update_redshift_displays()
        self._update_all_lines()
        # Velocity affects SN lines only; keep top axis tied to host redshift for consistency
        try:
            if hasattr(self, '_rest_axis') and self._rest_axis is not None:
                self._rest_axis.set_redshift(float(self.host_redshift or 0.0))
        except Exception:
            pass
    
    def _update_redshift_displays(self):
        """Update redshift display labels"""
        try:
            # No need to update displays
            # Just log the calculation for debugging if needed
            c_km_s = 299792.458  # Speed of light in km/s
            velocity_redshift_shift = self.velocity_shift / c_km_s
            effective_sn_redshift = self.host_redshift - velocity_redshift_shift
            if effective_sn_redshift < 0:
                effective_sn_redshift = 0.0
            
            _LOGGER.debug(f"Host z: {self.host_redshift:.6f}, Ejecta velocity: {self.velocity_shift} km/s, Effective SN z: {effective_sn_redshift:.6f}")
            
        except Exception as e:
            _LOGGER.warning(f"Error updating redshift displays: {e}")
    
    def _set_sn_mode(self):
        """Set SN line mode"""
        old_mode = self.current_mode
        self.current_mode = 'sn'
        if hasattr(self, 'sn_button'):
            self.sn_button.setChecked(True)
            # Apply blue styling for active state
            self.sn_button.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    border: 2px solid #2563eb;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
        if hasattr(self, 'galaxy_button'):
            self.galaxy_button.setChecked(False)
            # Reset to default styling for inactive state
            self.galaxy_button.setStyleSheet("")
        
        # OPTIMIZATION: Invalidate cache when mode changes
        if old_mode != self.current_mode:
            self._invalidate_overlay_cache()
            
        self._update_status_display()  # Update status when mode changes
    
    def _set_galaxy_mode(self):
        """Set galaxy line mode"""
        old_mode = self.current_mode
        self.current_mode = 'galaxy'
        if hasattr(self, 'sn_button'):
            self.sn_button.setChecked(False)
            # Reset to default styling for inactive state
            self.sn_button.setStyleSheet("")
        if hasattr(self, 'galaxy_button'):
            self.galaxy_button.setChecked(True)
            # Apply blue styling for active state
            self.galaxy_button.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    border: 2px solid #2563eb;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
        
        # OPTIMIZATION: Invalidate cache when mode changes
        if old_mode != self.current_mode:
            self._invalidate_overlay_cache()
            
        self._update_status_display()  # Update status when mode changes
    
    def _update_status_display(self):
        """Update the status display with current line counts"""
        try:
            if hasattr(self, 'status_label'):
                sn_count = len(self.sn_lines)
                galaxy_count = len(self.galaxy_lines)
                
                if self.current_mode == 'sn':
                    mode_text = "Mode: SN Lines"
                else:
                    mode_text = "Mode: Galaxy Lines"
                
                status_text = f"{mode_text}\nSelected: {sn_count} SN lines, {galaxy_count} Galaxy lines"
                self.status_label.setText(status_text)
                
        except Exception as e:
            _LOGGER.error(f"Error updating status display: {e}")
    
    def _clear_all_lines(self):
        """Clear all lines"""
        self.sn_lines.clear()
        self.galaxy_lines.clear()
        self._update_plot()
        self._update_status_display()
    
    def _remove_selected_lines(self):
        """Remove selected lines from tracker"""
        pass
    
    def _update_plot(self):
        """Update the plot with current spectrum and lines"""
        if not PYQTGRAPH_AVAILABLE or not self.plot_widget:
            return
            
        try:
            # Preserve current view ranges to avoid losing user zoom/pan state
            try:
                x_range_before, y_range_before = self.plot_item.viewRange()
            except Exception:
                x_range_before, y_range_before = None, None
            
            # Clear plot
            self.plot_item.clear()
            
            # Plot spectrum
            if 'wave' in self.spectrum_data and 'flux' in self.spectrum_data:
                self.plot_item.plot(
                    self.spectrum_data['wave'], 
                    self.spectrum_data['flux'],
                    pen='k'
                )

                # Ensure some headroom so the curve isn't cut at the top
                try:
                    flux = self.spectrum_data['flux']
                    wave = self.spectrum_data['wave']
                    if len(flux) > 0:
                        fmin = float(np.min(flux))
                        fmax = float(np.max(flux))
                        pad = (fmax - fmin) * 0.1 if fmax > fmin else abs(fmax) * 0.1 + 1.0
                        self.plot_widget.setYRange(fmin - pad, fmax + pad)
                        # Also set X range with a small margin since auto-range is disabled
                        try:
                            wmin = float(np.min(wave))
                            wmax = float(np.max(wave))
                            xpad = (wmax - wmin) * 0.05 if wmax > wmin else 10.0
                            self.plot_item.setXRange(wmin - xpad, wmax + xpad, padding=0)
                        except Exception:
                            pass
                        # Keep auto-range disabled so later overlays don't rescale
                        try:
                            self.plot_item.disableAutoRange()
                        except Exception:
                            self.plot_widget.enableAutoRange(axis='y', enable=False)
                except Exception:
                    pass
            
            # Ensure the save button is visible (always on in this dialog)
            try:
                if hasattr(self.plot_widget, 'show_save_button'):
                    self.plot_widget.show_save_button()
            except Exception:
                pass
            
            # Restore previous view ranges (preserve zoom/pan) if available
            try:
                if x_range_before is not None and y_range_before is not None:
                    # Ensure auto-range stays disabled before restoring
                    try:
                        self.plot_item.disableAutoRange()
                    except Exception:
                        self.plot_widget.enableAutoRange(axis='x', enable=False)
                        self.plot_widget.enableAutoRange(axis='y', enable=False)
                    # Apply previous ranges without extra padding
                    self.plot_item.setXRange(x_range_before[0], x_range_before[1], padding=0)
                    self.plot_item.setYRange(y_range_before[0], y_range_before[1], padding=0)
            except Exception:
                pass

            # Plot line markers after restoring view range so label placement uses final y-range
            for line_name, (obs_wavelength, line_data) in self.sn_lines.items():
                self._add_line_marker(obs_wavelength, line_name, 'red', 'SN')

            for line_name, (obs_wavelength, line_data) in self.galaxy_lines.items():
                self._add_line_marker(obs_wavelength, line_name, 'blue', 'Galaxy')
                
        except Exception as e:
            _LOGGER.error(f"Error updating plot: {e}")
    
    def _add_line_marker(self, wavelength, name, color, line_type):
        """Add a line marker to the plot"""
        if not PYQTGRAPH_AVAILABLE:
            return
            
        try:
            # Define color scheme based on line type and element
            line_colors = self._get_line_color(name, line_type)
            
            # Create line style based on SN vs Galaxy
            if line_type == 'SN':
                pen_style = pg.mkPen(color=line_colors, width=2, style=QtCore.Qt.DashLine)
            else:  # Galaxy
                pen_style = pg.mkPen(color=line_colors, width=2, style=QtCore.Qt.SolidLine)
            
            # Add vertical line
            line = pg.InfiniteLine(pos=wavelength, angle=90, pen=pen_style)
            self.plot_item.addItem(line)
            
            text = pg.TextItem(
                name,
                color=line_colors,
                fill=(255, 255, 255, 120),
                anchor=(0, 1),
            )
            
            # Get plot range for positioning (use relative position within current y-range)
            y_min, y_max = self.plot_item.viewRange()[1]
            # Position at 95% of the current visible range height
            y_pos = y_min + (y_max - y_min) * 0.95
            
            text.setPos(wavelength, y_pos)
            text.setRotation(90)  # Rotate 90 degrees to make text perpendicular
            
            self.plot_item.addItem(text)
            
        except Exception as e:
            _LOGGER.error(f"Error adding line marker: {e}")
    
    def _get_line_color(self, line_name, line_type):
        """Get color for line based on element/type"""
        line_name_lower = line_name.lower()
        
        # Color scheme based on element/type
        if 'h' in line_name_lower and ('alpha' in line_name_lower or 'beta' in line_name_lower or 'gamma' in line_name_lower or 'balmer' in line_name_lower):
            return '#FF6B6B'  # Red for Hydrogen
        elif 'he' in line_name_lower or 'helium' in line_name_lower:
            return '#4ECDC4'  # Teal for Helium
        elif 'si' in line_name_lower or 'silicon' in line_name_lower:
            return '#45B7D1'  # Blue for Silicon
        elif 'fe' in line_name_lower or 'iron' in line_name_lower:
            return '#F7931E'  # Orange for Iron
        elif 'ca' in line_name_lower or 'calcium' in line_name_lower:
            return '#9B59B6'  # Purple for Calcium
        elif 'o' in line_name_lower and ('oxygen' in line_name_lower or 'o ii' in line_name_lower or 'o iii' in line_name_lower):
            return '#2ECC71'  # Green for Oxygen
        elif 'mg' in line_name_lower or 'magnesium' in line_name_lower:
            return '#E74C3C'  # Dark red for Magnesium
        elif 'na' in line_name_lower or 'sodium' in line_name_lower:
            return '#F39C12'  # Yellow-orange for Sodium
        elif 'ni' in line_name_lower or 'nickel' in line_name_lower:
            return '#8E44AD'  # Dark purple for Nickel
        elif 'co' in line_name_lower or 'cobalt' in line_name_lower:
            return '#34495E'  # Dark blue-gray for Cobalt
        elif 'ti' in line_name_lower or 'titanium' in line_name_lower:
            return '#95A5A6'  # Gray for Titanium
        elif 'cr' in line_name_lower or 'chromium' in line_name_lower:
            return '#E67E22'  # Dark orange for Chromium
        elif 'mn' in line_name_lower or 'manganese' in line_name_lower:
            return '#16A085'  # Dark teal for Manganese
        elif 'ne' in line_name_lower or 'neon' in line_name_lower:
            return '#FF00FF'  # Magenta for Neon
        elif 'ar' in line_name_lower or 'argon' in line_name_lower:
            return '#00FFFF'  # Cyan for Argon
        elif 'n' in line_name_lower and ('nitrogen' in line_name_lower or 'n ii' in line_name_lower or 'n iii' in line_name_lower):
            return '#3498DB'  # Light blue for Nitrogen
        elif 's' in line_name_lower and ('sulfur' in line_name_lower or 's ii' in line_name_lower or 's iii' in line_name_lower):
            return '#F1C40F'  # Yellow for Sulfur
        else:
            # Default colors based on line type
            if line_type == 'SN':
                return '#FF4444'  # Default red for SN lines
            else:
                return '#4444FF'  # Default blue for Galaxy lines
    
    def _add_lines_to_plot(self, lines_dict, is_sn=True):
        """Add lines to plot from detection functions"""
        try:
            target_dict = self.sn_lines if is_sn else self.galaxy_lines
            
            for line_name, line_data in lines_dict.items():
                # Handle different line data formats
                if isinstance(line_data, tuple):
                    obs_wavelength = line_data[0]
                    metadata = line_data[1] if len(line_data) > 1 else {}
                elif isinstance(line_data, dict):
                    obs_wavelength = line_data.get('wavelength', line_data.get('obs_wavelength', 0))
                    metadata = line_data
                else:
                    obs_wavelength = float(line_data)
                    metadata = {}
                
                if obs_wavelength > 0:
                    target_dict[line_name] = (obs_wavelength, metadata)
            
            self._update_plot()
            self._update_status_display()
            
        except Exception as e:
            _LOGGER.error(f"Error adding lines to plot: {e}")
        
    def _update_all_lines(self):
        """Update all line positions when redshift or velocity changes."""
        try:
            sn_redshift = self._get_effective_sn_redshift()
            gal_redshift = self.host_redshift

            def compute_new_obs(line_name, stored_obs, metadata, use_sn):
                try:
                    rest_wl = 0.0
                    if isinstance(metadata, dict):
                        rest_wl = float(metadata.get('rest_wavelength', 0.0) or 0.0)
                    if rest_wl <= 0.0:
                        rest_wl = self._get_rest_wavelength_for_line(line_name)
                    if rest_wl > 0.0:
                        z = sn_redshift if use_sn else gal_redshift
                        return rest_wl * (1.0 + z)
                except Exception:
                    pass
                return stored_obs

            # Recompute SN lines (affected by ejecta velocity)
            if self.sn_lines:
                for name in list(self.sn_lines.keys()):
                    obs_wl, meta = self.sn_lines[name]
                    new_obs = compute_new_obs(name, obs_wl, meta, use_sn=True)
                    self.sn_lines[name] = (new_obs, meta)

            # Recompute Galaxy lines (host redshift only)
            if self.galaxy_lines:
                for name in list(self.galaxy_lines.keys()):
                    obs_wl, meta = self.galaxy_lines[name]
                    new_obs = compute_new_obs(name, obs_wl, meta, use_sn=False)
                    self.galaxy_lines[name] = (new_obs, meta)

            # Invalidate overlay cache and refresh plot
            self._invalidate_overlay_cache()
            self._update_plot()
        except Exception as e:
            _LOGGER.error(f"Error updating line positions after redshift/velocity change: {e}")
    
    def _invalidate_overlay_cache(self):
        """Invalidate the overlay cache when redshift parameters change"""
        try:
            self._cached_overlay_lines.clear()
            _LOGGER.debug("Overlay cache invalidated due to redshift change")
        except Exception as e:
            _LOGGER.error(f"Error invalidating overlay cache: {e}")
    
    def _on_plot_click(self, event):
        """Handle plot click events for line interaction"""
        if not PYQTGRAPH_AVAILABLE or not self.plot_item:
            return

        try:
            # Get click position in plot coordinates
            scene_pos = event.scenePos()
            if self.plot_item.sceneBoundingRect().contains(scene_pos):
                # Convert scene position to plot coordinates
                view_pos = self.plot_item.vb.mapSceneToView(scene_pos)
                click_wavelength = view_pos.x()
                click_flux = view_pos.y()
                
                # Handle step 2 manual point selection
                if self.current_step == 2 and self.step2_analysis:
                    self._handle_step2_plot_click(event, click_wavelength, click_flux)
                    return True
                
                # Handle step 1 line identification
                elif self.current_step == 1:
                    # Handle different mouse events
                    if event.double():
                        # Double-click: Find and add nearby line
                        self._find_and_add_nearby_line(click_wavelength)
                    elif event.button() == QtCore.Qt.RightButton:
                        # Right-click/Two finger click: Remove closest line
                        self._remove_closest_line(click_wavelength)
                        # Accept the event to prevent context menu
                        event.accept()
                        return True

        except Exception as e:
            _LOGGER.error(f"Error handling plot click: {e}")

        # For other events, let them propagate normally
        return False
    
    def _handle_step2_plot_click(self, event, click_wavelength, click_flux):
        """Handle plot clicks in step 2 for manual point selection"""
        try:
            if not self.step2_analysis:
                return
                
            # Manual Points is the only method available, so always handle point selection
            # Get keyboard modifiers
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            
            if event.button() == QtCore.Qt.RightButton:
                # Right-click/Two finger click: Remove closest point
                self._remove_closest_manual_point(click_wavelength, click_flux)
            elif event.button() == QtCore.Qt.LeftButton:
                # Left-click behavior: default snap to nearest bin; Ctrl/Cmd-click free point
                if (modifiers & QtCore.Qt.ControlModifier) or (modifiers & QtCore.Qt.MetaModifier):
                    # Ctrl/Cmd + Click: Add free-floating point at exact position
                    self._add_manual_point(click_wavelength, click_flux, mode="free")
                else:
                    # Plain click: Add point snapped to nearest spectrum bin
                    self._add_manual_point_snapped(click_wavelength, click_flux)
                    
            # Refresh plot
            if self.step2_analysis:
                self.step2_analysis.plot_focused_line()
                
        except Exception as e:
            _LOGGER.error(f"Error handling step 2 plot click: {e}")
    
    def _add_manual_point(self, wavelength, flux, mode="free"):
        """Add a manual point to step 2 analysis"""
        if not self.step2_analysis:
            return
            
        # Add point to step2_analysis
        self.step2_analysis.selected_manual_points.append((wavelength, flux))
        _LOGGER.info(f"Added manual point: λ={wavelength:.2f} Å, F={flux:.3f} ({mode})")
    
    def _add_manual_point_snapped(self, click_wavelength, click_flux):
        """Add a manual point snapped to the nearest spectrum point"""
        try:
            wave = self.spectrum_data.get('wave', np.array([]))
            flux = self.spectrum_data.get('flux', np.array([]))
            
            if len(wave) == 0 or len(flux) == 0:
                # Fallback to free point
                self._add_manual_point(click_wavelength, click_flux, mode="snapped_fallback")
                return
                
            # Find closest spectrum point
            distances = np.abs(wave - click_wavelength)
            closest_idx = np.argmin(distances)
            
            snapped_wavelength = wave[closest_idx]
            snapped_flux = flux[closest_idx]
            
            self._add_manual_point(snapped_wavelength, snapped_flux, mode="snapped")
            
        except Exception as e:
            _LOGGER.error(f"Error snapping manual point: {e}")
            # Fallback to free point
            self._add_manual_point(click_wavelength, click_flux, mode="snapped_error")
    
    def _add_manual_point_smart(self, click_wavelength, click_flux):
        """Add a manual point with smart peak detection around click location"""
        try:
            wave = self.spectrum_data.get('wave', np.array([]))
            flux = self.spectrum_data.get('flux', np.array([]))
            
            if len(wave) == 0 or len(flux) == 0:
                # Fallback to free point
                self._add_manual_point(click_wavelength, click_flux, mode="smart_fallback")
                return
                
            # Define search window around click (±5 Å)
            search_window = 5.0
            mask = (wave >= click_wavelength - search_window) & (wave <= click_wavelength + search_window)
            
            if not np.any(mask):
                # Fallback to free point
                self._add_manual_point(click_wavelength, click_flux, mode="smart_no_data")
                return
                
            region_wave = wave[mask]
            region_flux = flux[mask]
            
            # Find local peak (maximum flux in region)
            max_idx = np.argmax(region_flux)
            peak_wavelength = region_wave[max_idx]
            peak_flux = region_flux[max_idx]
            
            self._add_manual_point(peak_wavelength, peak_flux, mode="smart_peak")
            
        except Exception as e:
            _LOGGER.error(f"Error in smart peak detection: {e}")
            # Fallback to free point
            self._add_manual_point(click_wavelength, click_flux, mode="smart_error")
    
    def _remove_closest_manual_point(self, click_wavelength, click_flux):
        """Remove the closest manual point to the click location"""
        try:
            if not self.step2_analysis or not self.step2_analysis.selected_manual_points:
                return
                
            # Find closest point
            min_distance = float('inf')
            closest_idx = -1
            
            for i, (wave, flux) in enumerate(self.step2_analysis.selected_manual_points):
                # Calculate distance (weight wavelength more heavily)
                distance = np.sqrt((wave - click_wavelength)**2 + (flux - click_flux)**2 * 0.1)
                if distance < min_distance:
                    min_distance = distance
                    closest_idx = i
            
            # Remove the closest point
            if closest_idx >= 0:
                removed_point = self.step2_analysis.selected_manual_points.pop(closest_idx)
                _LOGGER.info(f"Removed manual point: λ={removed_point[0]:.2f} Å, F={removed_point[1]:.3f}")
                
        except Exception as e:
            _LOGGER.error(f"Error removing manual point: {e}")
    
    def _proceed_to_step_2(self):
        """Proceed to step 2 of the emission line analysis"""
        try:
            if not hasattr(self, 'step2_analysis') or not self.step2_analysis:
                QtWidgets.QMessageBox.information(
                    self,
                    "Step 2 Not Available",
                    "Step 2 analysis is not available in this version."
                )
                return
            
            # Check if we have any lines to analyze
            total_lines = len(self.sn_lines) + len(self.galaxy_lines)
            if total_lines == 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No Lines Selected",
                    "Please add some emission lines before proceeding to Step 2."
                )
                return
            
            # Hide current interface and show step 2
            self.current_step = 2
            self._create_step_2_interface()
            
        except Exception as e:
            _LOGGER.error(f"Error proceeding to step 2: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error proceeding to step 2: {e}"
            )
    
    def _create_step_2_interface(self):
        """Create step 2 interface with proper layout replacement"""
        try:
            if not self.step2_analysis:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Step 2 Not Available",
                    "Step 2 analysis module is not available."
                )
                return
                
            # Switch to step 2 toolbar
            self._switch_to_step2_toolbar()
            
            # Hide the left panel (step 1 controls)
            if self.left_panel:
                self.left_panel.hide()
            
            # Create new left panel for step 2
            main_layout = self.layout()
            self.step2_left_panel = QtWidgets.QFrame()
            self.step2_left_panel.setFrameStyle(QtWidgets.QFrame.StyledPanel)
            self.step2_left_panel.setFixedWidth(280)
            
            step2_layout = QtWidgets.QVBoxLayout(self.step2_left_panel)
            step2_layout.setContentsMargins(15, 15, 15, 15)
            step2_layout.setSpacing(15)
            
            # Step 2 header
            step_label = QtWidgets.QLabel(f"Step {self.current_step} of {self.total_steps}: Line Analysis")
            step_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2563eb; margin-bottom: 10px;")
            step2_layout.addWidget(step_label)
            
            # Create simplified step 2 interface
            self._create_simplified_step2_interface(step2_layout)
            
            # Add bottom control buttons (Help and Back to Step 1)
            step2_layout.addStretch()
            
            # Bottom buttons layout
            bottom_buttons_layout = QtWidgets.QHBoxLayout()
            
            # Help button (bottom left)
            help_btn = QtWidgets.QPushButton("Help")
            help_btn.setToolTip("Show Step 2 analysis instructions and button explanations")
            help_btn.clicked.connect(self._show_step2_help)
            help_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    border: 2px solid #2563eb;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
            bottom_buttons_layout.addWidget(help_btn)
            
            # Back to step 1 button (bottom right)
            back_btn = QtWidgets.QPushButton("Back to Step 1")
            back_btn.clicked.connect(self._back_to_step_1)
            back_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6b7280;
                    color: white;
                    border: 2px solid #4b5563;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4b5563;
                }
            """)
            bottom_buttons_layout.addWidget(back_btn)
            
            step2_layout.addLayout(bottom_buttons_layout)
            
            # Insert the new step 2 panel at the beginning of the main layout
            main_layout.insertWidget(0, self.step2_left_panel)
            
            # Connect toolbar controls to step 2 functionality
            self._connect_step2_toolbar_controls()
            
            # Initialize step 2 data
            self._initialize_step2_interface()
            
            # Update window title
            self.setWindowTitle("Spectral Line Analysis - Step 2: Analysis")
            
            _LOGGER.info("Step 2 interface created successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error creating step 2 interface: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create step 2 interface: {str(e)}"
            )
    
    def _switch_to_step2_toolbar(self):
        """Switch from step 1 preset toolbar to step 2 analysis toolbar"""
        try:
            # Remove current toolbar
            if self.current_toolbar:
                self.toolbar_layout.removeWidget(self.current_toolbar)
                self.current_toolbar.hide()
                self.current_toolbar.deleteLater()
            
            # Create and add step 2 toolbar
            self.current_toolbar = self.ui_builder.create_step2_analysis_toolbar()
            self.toolbar_layout.addWidget(self.current_toolbar)
            
            _LOGGER.debug("Switched to step 2 toolbar")
            
        except Exception as e:
            _LOGGER.error(f"Error switching to step 2 toolbar: {e}")
    
    def _switch_to_step1_toolbar(self):
        """Switch from step 2 analysis toolbar back to step 1 preset toolbar"""
        try:
            # Remove current toolbar
            if self.current_toolbar:
                self.toolbar_layout.removeWidget(self.current_toolbar)
                self.current_toolbar.hide()
                self.current_toolbar.deleteLater()
            
            # Create and add step 1 toolbar
            self.current_toolbar = self.ui_builder.create_compact_preset_toolbar()
            self.toolbar_layout.addWidget(self.current_toolbar)
            
            _LOGGER.debug("Switched to step 1 toolbar")
            
        except Exception as e:
            _LOGGER.error(f"Error switching to step 1 toolbar: {e}")
    
    def _create_simplified_step2_interface(self, layout):
        """Create simplified step 2 interface"""

        # Quick interaction info (static multi-line info label like Step 1)
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text('right')
        info_text = (
            "ℹ️ Point Selection Hints:\n"
            "• Left-click: add point snapped to nearest bin\n"
            "• Ctrl/Cmd+Click: add free-floating point\n"
            f"• {right_click_text}: remove closest point"
        )
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-weight: normal; color: #2563eb; font-size: 10px;")
        layout.addWidget(info_label)


        # Single minimal summary panel
        summary_group = QtWidgets.QGroupBox("📋 Line Summary")
        summary_layout = QtWidgets.QVBoxLayout(summary_group)
        
        summary_controls = QtWidgets.QHBoxLayout()

        copy_summary_btn = QtWidgets.QPushButton("Copy Summary")
        summary_controls.addWidget(copy_summary_btn)

        export_btn = QtWidgets.QPushButton("Export Results")
        summary_controls.addWidget(export_btn)

        summary_controls.addStretch()
        summary_layout.addLayout(summary_controls)
        
        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.summary_text.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        summary_layout.addWidget(self.summary_text, 1)
        
        # Allow the summary group to expand and occupy available vertical space
        summary_group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(summary_group, 1)
        
        # Store control references for the step2_analysis module (no clear points here)
        self.step2_panel_controls = {
            'summary_text': self.summary_text,
            'copy_summary_btn': copy_summary_btn,
            'export_btn': export_btn
        }
    
    def _connect_step2_toolbar_controls(self):
        """Connect step 2 toolbar controls to functionality"""
        try:
            if not hasattr(self, 'step2_toolbar_refs') or not self.step2_analysis:
                return
                
            # Connect navigation buttons
            if hasattr(self, 'step2_prev_btn'):
                self.step2_prev_btn.clicked.connect(self.step2_analysis.previous_line)
            if hasattr(self, 'step2_next_btn'):
                self.step2_next_btn.clicked.connect(self.step2_analysis.next_line)
                
            # Connect line dropdown
            if hasattr(self, 'step2_line_dropdown'):
                self.step2_line_dropdown.currentTextChanged.connect(self.step2_analysis.on_line_selection_changed)
                
            # Connect analyze and toolbar clear buttons
            if hasattr(self, 'step2_toolbar_refs'):
                self.step2_toolbar_refs['analyze_btn'].clicked.connect(self.step2_analysis.analyze_current_line)
                if 'clear_points_btn' in self.step2_toolbar_refs:
                    self.step2_toolbar_refs['clear_points_btn'].clicked.connect(self.step2_analysis.clear_selected_points)
                
            # Connect panel controls (no left-panel clear points button)
            if hasattr(self, 'step2_panel_controls'):
                self.step2_panel_controls['copy_summary_btn'].clicked.connect(self.step2_analysis.copy_summary)
                self.step2_panel_controls['export_btn'].clicked.connect(self.step2_analysis.export_results)
                
            _LOGGER.debug("Connected step 2 toolbar controls")
            
        except Exception as e:
            _LOGGER.error(f"Error connecting step 2 toolbar controls: {e}")
    
    def _initialize_step2_interface(self):
        """Initialize step 2 interface with proper control references"""
        try:
            if not self.step2_analysis:
                return
                
            # Update step2_analysis references to use toolbar controls
            if hasattr(self, 'step2_line_dropdown'):
                self.step2_analysis.line_dropdown = self.step2_line_dropdown
            if hasattr(self, 'step2_line_counter'):
                self.step2_analysis.line_counter_label = self.step2_line_counter
                
            # Update panel control references
            if hasattr(self, 'step2_panel_controls'):
                # Keep only summary
                self.step2_analysis.summary_text = self.step2_panel_controls['summary_text']
                
            # Initialize step 2 data
            self.step2_analysis.populate_line_dropdown()
            # No need to call update_method_visibility since we only have Manual Points
            
            _LOGGER.debug("Initialized step 2 interface")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing step 2 interface: {e}")
    
    def _back_to_step_1(self):
        """Return to step 1 interface"""
        try:
            # Switch back to step 1 toolbar
            self._switch_to_step1_toolbar()
            
            # Hide step 2 panel
            if hasattr(self, 'step2_left_panel') and self.step2_left_panel:
                self.step2_left_panel.hide()
                self.layout().removeWidget(self.step2_left_panel)
                self.step2_left_panel.deleteLater()
                self.step2_left_panel = None
            
            # Show step 1 panel
            if self.left_panel:
                self.left_panel.show()
            
            # Reset step
            self.current_step = 1
            
            # Update window title
            self.setWindowTitle("Spectral Line Analysis - Step by Step")
            
            # Refresh plot to show step 1 view
            self._update_plot()
            
            _LOGGER.info("Returned to step 1 successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error returning to step 1: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error", 
                f"Failed to return to step 1: {str(e)}"
            )
    
    def _find_and_add_nearby_line(self, wavelength):
        """Find and add a line near the clicked wavelength"""
        try:
            # Calculate tolerance based on current mode and redshift
            tolerance = 20.0  # Angstroms tolerance
            
            # Get effective redshift for line search
            if self.current_mode == 'sn':
                search_redshift = self._get_effective_sn_redshift()
            else:
                search_redshift = self.host_redshift
            
            # Find the closest line in the comprehensive line database
            closest_line = self._find_closest_line_in_database(wavelength, search_redshift, tolerance)
            
            if closest_line:
                line_name, rest_wavelength, line_data = closest_line
                obs_wavelength = rest_wavelength * (1 + search_redshift)
                
                # Persist rest wavelength so we can recompute positions when redshift/velocity changes
                try:
                    if isinstance(line_data, dict):
                        meta_copy = dict(line_data)
                        meta_copy['rest_wavelength'] = rest_wavelength
                        line_data = meta_copy
                except Exception:
                    pass
                
                # Add line to appropriate collection
                if self.current_mode == 'sn':
                    self.sn_lines[line_name] = (obs_wavelength, line_data)
                    _LOGGER.info(f"Added SN line: {line_name} at {obs_wavelength:.2f} Å")
                else:
                    self.galaxy_lines[line_name] = (obs_wavelength, line_data)
                    _LOGGER.info(f"Added Galaxy line: {line_name} at {obs_wavelength:.2f} Å")
                
                # Update plot and status
                self._update_plot()
                self._update_status_display()  # Update status after adding line
            else:
                _LOGGER.info(f"No line found near {wavelength:.2f} Å (tolerance: {tolerance} Å)")
                
        except Exception as e:
            _LOGGER.error(f"Error finding nearby line: {e}")

    def _get_rest_wavelength_for_line(self, line_name: str) -> float:
        """Best-effort lookup of a line's rest wavelength from the database."""
        try:
            from snid_sage.shared.constants.physical import LINE_DB
            target = (line_name or '').strip()
            for entry in LINE_DB:
                rest = entry.get('wavelength_air', 0.0)
                if rest <= 0:
                    continue
                key = entry.get('key', '')
                if key.replace(' (gal)', '').strip() == target:
                    return float(rest)
        except Exception as lookup_error:
            _LOGGER.debug(f"Rest wavelength lookup failed for '{line_name}': {lookup_error}")
        return 0.0
    
    def _find_closest_line_in_database(self, obs_wavelength, redshift, tolerance):
        """Find the closest line in the line database"""
        try:
            # Import the line database
            from snid_sage.shared.constants.physical import LINE_DB
            
            closest_line = None
            min_distance = float('inf')
            
            # Convert observed wavelength back to rest wavelength for comparison
            rest_wavelength_target = obs_wavelength / (1 + redshift)
            
            _LOGGER.debug(f"Searching for line near {obs_wavelength:.1f} Å in {self.current_mode} mode (z={redshift:.6f})")
            
            # Search through all lines
            for line_entry in LINE_DB:
                line_rest_wavelength = line_entry.get("wavelength_air", 0)
                if line_rest_wavelength <= 0:
                    continue
                
                # Calculate distance in observed wavelength space
                line_obs_wavelength = line_rest_wavelength * (1 + redshift)
                distance = abs(line_obs_wavelength - obs_wavelength)
                
                # Check if this line is closer and within tolerance
                if distance < min_distance and distance <= tolerance:
                    line_name = line_entry.get("key", f"Line {line_rest_wavelength:.1f}")
                    
                    # Clean up line name and filter by mode - FIXED LOGIC
                    is_galaxy_line = " (gal)" in line_name
                    if self.current_mode == 'sn' and is_galaxy_line:
                        _LOGGER.debug(f"Skipping galaxy line {line_name} in SN mode")
                        continue  # Skip galaxy lines when in SN mode
                    if self.current_mode == 'galaxy' and not is_galaxy_line:
                        _LOGGER.debug(f"Skipping SN line {line_name} in galaxy mode")
                        continue  # Skip SN lines when in galaxy mode
                    
                    min_distance = distance
                    line_name_clean = line_name.replace(" (gal)", "")
                    
                    line_data = {
                        'strength': line_entry.get('strength', 'medium'),
                        'type': line_entry.get('line_type', 'unknown'),
                        'origin': line_entry.get('origin', 'unknown'),
                        'rest_wavelength': line_rest_wavelength,
                    }
                    
                    closest_line = (line_name_clean, line_rest_wavelength, line_data)
                    _LOGGER.debug(f"Found candidate line: {line_name_clean} at {line_obs_wavelength:.1f} Å (distance: {distance:.1f})")
            
            if closest_line:
                _LOGGER.info(f"Selected line: {closest_line[0]} at {closest_line[1] * (1 + redshift):.1f} Å")
            else:
                _LOGGER.info(f"No {self.current_mode} line found within {tolerance} Å of {obs_wavelength:.1f} Å")
            
            return closest_line
            
        except Exception as e:
            _LOGGER.error(f"Error searching line database: {e}")
            return None
    
    def _remove_closest_line(self, wavelength):
        """Remove the closest line to the clicked wavelength"""
        try:
            closest_line_name = None
            min_distance = float('inf')
            line_collection = None
            
            # Search SN lines
            for line_name, (obs_wavelength, line_data) in self.sn_lines.items():
                distance = abs(obs_wavelength - wavelength)
                if distance < min_distance:
                    min_distance = distance
                    closest_line_name = line_name
                    line_collection = 'sn'
            
            # Search Galaxy lines
            for line_name, (obs_wavelength, line_data) in self.galaxy_lines.items():
                distance = abs(obs_wavelength - wavelength)
                if distance < min_distance:
                    min_distance = distance
                    closest_line_name = line_name
                    line_collection = 'galaxy'
            
            # Remove the closest line if found within reasonable distance
            if closest_line_name and min_distance <= 50.0:  # 50 Angstrom tolerance
                if line_collection == 'sn':
                    removed_line = self.sn_lines.pop(closest_line_name)
                    _LOGGER.info(f"Removed SN line: {closest_line_name}")
                elif line_collection == 'galaxy':
                    removed_line = self.galaxy_lines.pop(closest_line_name)
                    _LOGGER.info(f"Removed Galaxy line: {closest_line_name}")
                
                # Update plot and status
                self._update_plot()
                self._update_status_display()  # Update status after removing line
            else:
                _LOGGER.info(f"No line found near {wavelength:.2f} Å for removal")
                
        except Exception as e:
            _LOGGER.error(f"Error removing line: {e}")

    def eventFilter(self, obj, event):
        """Event filter to handle keyboard events for line overlay"""
        try:
            if event.type() == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_Shift:
                    self._show_all_lines_overlay()
                    return True
            elif event.type() == QtCore.QEvent.KeyRelease:
                if event.key() == QtCore.Qt.Key_Shift:
                    self._hide_all_lines_overlay()
                    return True
        except Exception as e:
            _LOGGER.error(f"Error in event filter: {e}")
        
        return super().eventFilter(obj, event)
    
    def keyPressEvent(self, event):
        """Handle key press events for the dialog"""
        try:
            if event.key() == QtCore.Qt.Key_Shift:
                self._show_all_lines_overlay()
                event.accept()
                return
        except Exception as e:
            _LOGGER.error(f"Error in keyPressEvent: {e}")
        
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """Handle key release events for the dialog"""
        try:
            if event.key() == QtCore.Qt.Key_Shift:
                self._hide_all_lines_overlay()
                event.accept()
                return
        except Exception as e:
            _LOGGER.error(f"Error in keyReleaseEvent: {e}")
        
        super().keyReleaseEvent(event)
    
    def _show_all_lines_overlay(self):
        """Show overlay of all available lines when Shift is pressed - OPTIMIZED VERSION"""
        if not PYQTGRAPH_AVAILABLE or not self.plot_item:
            _LOGGER.debug("Overlay not available: PyQtGraph missing")
            return
        
        try:
            # Lock current view ranges to avoid any auto-rescaling during overlay
            x_range_before, y_range_before = self.plot_item.viewRange()
            try:
                self.plot_item.disableAutoRange()
            except Exception:
                self.plot_widget.enableAutoRange(axis='x', enable=False)
                self.plot_widget.enableAutoRange(axis='y', enable=False)

            # Get spectrum wavelength range
            wave = self.spectrum_data.get('wave', np.array([]))
            if len(wave) == 0:
                _LOGGER.debug("No spectrum wavelength data available")
                return
            
            wave_min, wave_max = np.min(wave), np.max(wave)
            _LOGGER.debug(f"Spectrum range: {wave_min:.1f} - {wave_max:.1f} Å")
            
            # Clear any existing overlay items first
            self._hide_all_lines_overlay()
            
            # Store overlay items for later removal
            if not hasattr(self, 'overlay_items'):
                self.overlay_items = []
            
            # OPTIMIZATION 1: Use cached lines if redshift parameters haven't changed
            overlay_lines = self._get_cached_overlay_lines(wave_min, wave_max)
            if overlay_lines is None:
                # Cache miss - calculate and cache
                overlay_lines = self._calculate_overlay_lines(wave_min, wave_max)
                
            _LOGGER.debug(f"Found {len(overlay_lines)} {self.current_mode} lines in database range")
            
            # OPTIMIZATION 2: Batch creation of plot items to reduce overhead
            self._create_overlay_plot_items_batch(overlay_lines)
            
            _LOGGER.debug(f"Displayed {len(overlay_lines)} overlay lines")
            # Restore the original view ranges explicitly to prevent any rescale
            try:
                self.plot_item.setXRange(x_range_before[0], x_range_before[1], padding=0)
                self.plot_item.setYRange(y_range_before[0], y_range_before[1], padding=0)
            except Exception:
                pass
            
        except Exception as e:
            _LOGGER.error(f"Error showing line overlay: {e}")
    
    def _get_cached_overlay_lines(self, wave_min, wave_max):
        """Get cached overlay lines if redshift parameters haven't changed"""
        try:
            # Create redshift key for cache lookup
            if self.current_mode == 'sn':
                redshift = self._get_effective_sn_redshift()
            else:
                redshift = self.host_redshift
            
            # Round redshift to avoid floating point precision issues
            redshift_key = f"{redshift:.8f}_{wave_min:.1f}_{wave_max:.1f}"
            
            # Check if we have cached data for this mode and redshift
            if (self.current_mode in self._cached_overlay_lines and 
                redshift_key in self._cached_overlay_lines[self.current_mode]):
                _LOGGER.debug(f"Using cached overlay lines for {self.current_mode} mode")
                return self._cached_overlay_lines[self.current_mode][redshift_key]
            
            return None  # Cache miss
            
        except Exception as e:
            _LOGGER.error(f"Error checking cached overlay lines: {e}")
            return None
    
    def _calculate_overlay_lines(self, wave_min, wave_max):
        """Calculate overlay lines and cache the result"""
        try:
            overlay_lines = []
            
            # Import the comprehensive line database directly
            from snid_sage.shared.constants.physical import LINE_DB
            
            # Get redshift for current mode
            if self.current_mode == 'sn':
                redshift = self._get_effective_sn_redshift()
            else:
                redshift = self.host_redshift
            
            # OPTIMIZATION 3: Vectorized wavelength calculation and filtering
            # Pre-filter lines by mode first
            relevant_lines = []
            for line_entry in LINE_DB:
                line_rest_wavelength = line_entry.get("wavelength_air", 0)
                if line_rest_wavelength <= 0:
                    continue
                
                line_name = line_entry.get("key", f"Line {line_rest_wavelength:.1f}")
                
                # Filter by mode
                is_galaxy_line = " (gal)" in line_name
                if self.current_mode == 'sn' and is_galaxy_line:
                    continue
                elif self.current_mode == 'galaxy' and not is_galaxy_line:
                    continue
                
                relevant_lines.append((line_name, line_rest_wavelength))
            
            # Vectorized wavelength calculation
            if relevant_lines:
                line_names, rest_wavelengths = zip(*relevant_lines)
                rest_wavelengths = np.array(rest_wavelengths)
                obs_wavelengths = rest_wavelengths * (1 + redshift)
                
                # Build result list with pre-calculated colors (no range filtering; rely on fixed view)
                for i in range(len(obs_wavelengths)):
                    clean_name = line_names[i].replace(" (gal)", "")
                    # Skip lines that are already added
                    if clean_name not in self.sn_lines and clean_name not in self.galaxy_lines:
                        line_color = self._get_line_color(clean_name, self.current_mode)
                        overlay_lines.append((clean_name, obs_wavelengths[i], line_color))
            
            # Cache the result
            redshift_key = f"{redshift:.8f}_{wave_min:.1f}_{wave_max:.1f}"
            if self.current_mode not in self._cached_overlay_lines:
                self._cached_overlay_lines[self.current_mode] = {}
            
            # Limit cache size to prevent memory bloat (keep last 5 entries per mode)
            if len(self._cached_overlay_lines[self.current_mode]) >= 5:
                # Remove oldest entry
                oldest_key = next(iter(self._cached_overlay_lines[self.current_mode]))
                del self._cached_overlay_lines[self.current_mode][oldest_key]
            
            self._cached_overlay_lines[self.current_mode][redshift_key] = overlay_lines
            
            return overlay_lines
            
        except ImportError:
            _LOGGER.debug("LINE_DB not available")
            return []
        except Exception as e:
            _LOGGER.error(f"Error calculating overlay lines: {e}")
            return []
    
    def _create_overlay_plot_items_batch(self, overlay_lines):
        """Create overlay plot items in batch for better performance"""
        try:
            if not overlay_lines:
                return
            
            # Get current plot view range once
            y_min, y_max = self.plot_item.viewRange()[1]
            text_y_pos = y_min + (y_max - y_min) * 0.95
            
            # OPTIMIZATION 4: Batch add items to reduce plot update overhead
            items_to_add = []
            
            for line_name, obs_wavelength, line_color in overlay_lines:
                # Create faint overlay line with appropriate style
                if self.current_mode == 'sn':
                    # SN lines - dashed, more transparent
                    overlay_line = pg.InfiniteLine(
                        pos=obs_wavelength,
                        angle=90,
                        pen=pg.mkPen(color=line_color, width=1, style=QtCore.Qt.DashLine, alpha=0.6)
                    )
                else:
                    # Galaxy lines - solid, more transparent
                    overlay_line = pg.InfiniteLine(
                        pos=obs_wavelength,
                        angle=90,
                        pen=pg.mkPen(color=line_color, width=1, style=QtCore.Qt.SolidLine, alpha=0.6)
                    )
                
                # Add text label (small and faint, perpendicular)
                text_item = pg.TextItem(
                    line_name,
                    color=line_color,
                    fill=(255, 255, 255, 30),
                    anchor=(0, 1)
                )
                text_item.setPos(obs_wavelength, text_y_pos)
                text_item.setRotation(90)  # Make text perpendicular
                
                items_to_add.extend([overlay_line, text_item])
            
            # Batch add all items at once
            for item in items_to_add:
                self.plot_item.addItem(item)
            
            self.overlay_items.extend(items_to_add)
            
        except Exception as e:
            _LOGGER.error(f"Error creating overlay plot items: {e}")
    
    def _hide_all_lines_overlay(self):
        """Hide the overlay lines when Shift is released"""
        if not PYQTGRAPH_AVAILABLE or not self.plot_item:
            return
        
        try:
            # Remove all overlay items
            if hasattr(self, 'overlay_items'):
                for item in self.overlay_items:
                    self.plot_item.removeItem(item)
                self.overlay_items.clear()
            
            _LOGGER.debug("Hidden line overlay")
            
        except Exception as e:
            _LOGGER.error(f"Error hiding line overlay: {e}")
    
    def _get_effective_sn_redshift(self):
        """Calculate effective SN redshift including velocity effect"""
        # Use shared utility with relativistic handling
        try:
            from snid_sage.shared.utils.line_detection.spectrum_utils import compute_effective_sn_redshift
            return compute_effective_sn_redshift(self.host_redshift, self.velocity_shift, use_relativistic=True)
        except Exception:
            c_km_s = 299792.458
            return float(self.host_redshift) - float(self.velocity_shift) / c_km_s

    def _show_interaction_help(self):
        """Show help dialog for mouse interactions and shortcuts"""
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text('right')
        
        help_text = f"""Emission Line Dialog Help

⌨️ KEYBOARD SHORTCUTS:
• Hold Shift: Show all available lines as overlay
• This helps identify potential lines in your spectrum

🖱️ MOUSE INTERACTIONS:
• Double-click on spectrum: Add nearest line from database
• {right_click_text} on line marker: Remove line from plot  
• Current mode (SN/Galaxy) determines line type

🎯 QUICK PRESETS:
• Type, Phase, Element work together for SN lines
• Choose combinations like "Type Ia + Maximum Light + Silicon"
• Other Presets include galaxy lines and strength-based selections

💡 WORKFLOW TIPS:
1. Set correct redshift values first
2. Choose SN or Galaxy mode 
3. Use presets for bulk line addition
4. Fine-tune with individual line clicks
5. Review added lines in the tracker below
"""
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Emission Line Dialog Help")
        msg.setText(help_text)
        msg.setTextFormat(QtCore.Qt.PlainText)
        msg.exec()

    def _show_step2_help(self):
        """Show help dialog for Step 2 analysis controls and workflow"""
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text('right')
        
        help_text = f"""Step 2: Emission Line Analysis Help

🎯 GOAL OF STEP 2:
Analyze individual emission lines in detail using manual point selection to measure line properties like velocity (from line width) and line centers.

⌨️ KEYBOARD & MOUSE INTERACTIONS:
• Left Click: Add point snapped to the nearest spectrum bin
• Ctrl/Cmd+Click: Add free-floating point at exact position
• {right_click_text}: Remove closest manual point

🔧 TOOLBAR CONTROLS:
• Line Dropdown: Select which emission line to analyze
• Previous/Next: Navigate between identified lines
• Analyze Button: Process current line with selected points

🔘 PANEL BUTTONS:
• Clear Points: Remove all manual selection points
• Auto Contour: Automatically detect line boundaries
• Copy Summary: Copy analysis results to clipboard
• Refresh: Update summary with latest results
• Export Results: Save analysis to file

💡 ANALYSIS WORKFLOW:
1. Select a line from the dropdown (from Step 1)
2. Click to add points along the line profile (points are connected by lines)
3. Click 'Analyze' to calculate line properties
4. Review minimal per-line results in the summary list
5. Repeat for other lines or export final results

📊 RESULTS INCLUDE (minimal per line):
• Line name, observed λ, and velocity (km/s) when available
"""
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Step 2 Analysis Help")
        msg.setText(help_text)
        msg.setTextFormat(QtCore.Qt.PlainText)
        msg.exec()

    def _show_step2_quick_hints(self):
        """Show compact multi-line quick hints for point selection."""
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text('right')
        hints = (
            "Point Selection Hints:\n"
            "• Left-click: add point snapped to nearest bin\n"
            "• Ctrl/Cmd+Click: add free-floating point\n"
            f"• {right_click_text}: remove closest point"
        )
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Point Selection Hints")
        msg.setText(hints)
        msg.setTextFormat(QtCore.Qt.PlainText)
        msg.exec()


def show_pyside6_multi_step_emission_dialog(parent, spectrum_data, theme_manager=None, 
                                           galaxy_redshift=0.0, cluster_median_redshift=0.0):
    """
    Show the refactored PySide6 multi-step emission line analysis dialog
    
    Args:
        parent: Parent widget
        spectrum_data: Dictionary with 'wave' and 'flux' keys
        theme_manager: Theme manager instance
        galaxy_redshift: Galaxy redshift estimate
        cluster_median_redshift: Cluster median redshift estimate
    
    Returns:
        Dialog instance
    """
    try:
        dialog = PySide6MultiStepEmissionAnalysisDialog(
            parent=parent,
            spectrum_data=spectrum_data,
            theme_manager=theme_manager,
            galaxy_redshift=galaxy_redshift,
            cluster_median_redshift=cluster_median_redshift
        )
        
        result = dialog.exec()
        return dialog
        
    except Exception as e:
        _LOGGER.error(f"Error in show_pyside6_multi_step_emission_dialog (refactored): {e}")
        raise 