"""
PySide6 Multi-Step SN Emission Line Analysis Dialog for SNID SAGE GUI (Refactored)
==================================================================================

A modern, step-by-step workflow for supernova emission line analysis.
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
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_emission_dialog_refactored')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_emission_dialog_refactored')

# Import supernova emission line constants
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
            
            # Use cluster redshift as the host redshift (RLAP-cos weighted winner)
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
        self.setWindowTitle("Emission Line Analysis - Step by Step")
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
        self.left_panel.setFixedWidth(280)  # Even narrower since presets moved to toolbar
        
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(15)
        
        # Step header
        step_label = QtWidgets.QLabel(f"Step {self.current_step} of {self.total_steps}: Line Identification")
        step_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2563eb; margin-bottom: 10px;")
        left_layout.addWidget(step_label)
        
        # Add info section at the top
        self.ui_builder.create_info_section(left_layout)
        
        # Use UI builder for components (excluding quick presets and line tracker)
        self.ui_builder.create_redshift_controls(left_layout)
        self.ui_builder.create_mode_selection(left_layout) 
        # NOTE: Removed quick presets from here - now in toolbar above plot
        # NOTE: Removed line tracker - too many lines to track effectively
        self.ui_builder.create_status_display(left_layout)
        
        # Stretch to push buttons to bottom
        left_layout.addStretch()
        
        # Control buttons at the bottom
        self.ui_builder.create_control_buttons(left_layout)
        
        main_layout.addWidget(self.left_panel)
    
    def _create_plot_widget(self, layout):
        """Create plot widget and add to layout"""
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget = pg.PlotWidget()
            self.plot_item = self.plot_widget.getPlotItem()
            
            self.plot_widget.setLabel('left', 'Flux')
            self.plot_widget.setLabel('bottom', 'Wavelength (Å)')
            self.plot_widget.setMinimumWidth(600)
            self.plot_widget.setMinimumHeight(400)
            
            # Connect mouse events for line interaction
            self.plot_widget.scene().sigMouseClicked.connect(self._on_plot_click)
            
            # Install event filter for keyboard events (Shift overlay)
            self.plot_widget.installEventFilter(self)
            self.plot_widget.setFocusPolicy(QtCore.Qt.ClickFocus)
            
            layout.addWidget(self.plot_widget)
        else:
            # Fallback
            placeholder = QtWidgets.QLabel("PyQtGraph not available")
            placeholder.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(placeholder)
    
    def _create_plot_panel(self, main_layout):
        """Legacy method - now using _create_plot_widget"""
        self._create_plot_widget(main_layout)
    
    # Event handling methods - delegate to event handlers
    def _on_sn_type_preset_selected(self, text):
        """Delegate to event handler"""
        self.event_handlers.on_sn_type_preset_selected(text)
    
    def _on_sn_phase_preset_selected(self, text):
        """Delegate to event handler"""
        self.event_handlers.on_sn_phase_preset_selected(text)
    
    def _on_element_preset_selected(self, text):
        """Delegate to event handler"""
        self.event_handlers.on_element_preset_selected(text)
    
    def _on_other_preset_selected(self, text):
        """Delegate to event handler"""
        self.event_handlers.on_other_preset_selected(text)
    
    # Legacy compatibility methods
    def _on_sn_type_selected(self, text):
        """Legacy compatibility - delegate to event handler"""
        self.event_handlers.on_sn_type_selected(text)
    
    def _on_sn_phase_selected(self, text):
        """Legacy compatibility - delegate to event handler"""
        self.event_handlers.on_sn_phase_selected(text)
    
    def _on_element_selected(self, text):
        """Legacy compatibility - delegate to event handler"""
        self.event_handlers.on_element_selected(text)
    
    def _on_galaxy_selected(self, text):
        """Legacy compatibility - delegate to event handler"""
        self.event_handlers.on_galaxy_selected(text)
    
    # Essential methods that need to remain in main class
    def _on_base_redshift_changed(self, value):
        """Handle base redshift change"""
        self.host_redshift = value
        self._update_redshift_displays()
        self._update_all_lines()
    
    def _on_velocity_changed(self, value):
        """Handle velocity change"""
        self.velocity_shift = value
        self._update_redshift_displays()
        self._update_all_lines()
    
    def _update_redshift_displays(self):
        """Update redshift display labels"""
        try:
            # No need to update displays since we removed the effective redshift display
            # Just log the calculation for debugging if needed
            c_km_s = 299792.458  # Speed of light in km/s
            velocity_redshift_shift = self.velocity_shift / c_km_s
            effective_sn_redshift = self.host_redshift + velocity_redshift_shift
            if effective_sn_redshift < 0:
                effective_sn_redshift = 0.0
            
            _LOGGER.debug(f"Host z: {self.host_redshift:.6f}, Ejecta velocity: {self.velocity_shift} km/s, Effective SN z: {effective_sn_redshift:.6f}")
            
        except Exception as e:
            _LOGGER.warning(f"Error updating redshift displays: {e}")
    
    def _set_sn_mode(self):
        """Set SN line mode"""
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
        self._update_status_display()  # Update status when mode changes
    
    def _set_galaxy_mode(self):
        """Set galaxy line mode"""
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
        self._update_status_display()  # Update status after clearing lines
        # Line tracker removed - no need to clear it
    
    def _remove_selected_lines(self):
        """Remove selected lines from tracker - method no longer needed"""
        # This method is no longer functional since we removed the line tracker
        pass
    
    def _update_plot(self):
        """Update the plot with current spectrum and lines"""
        if not PYQTGRAPH_AVAILABLE or not self.plot_widget:
            return
            
        try:
            # Clear plot
            self.plot_item.clear()
            
            # Plot spectrum
            if 'wave' in self.spectrum_data and 'flux' in self.spectrum_data:
                self.plot_item.plot(
                    self.spectrum_data['wave'], 
                    self.spectrum_data['flux'],
                    pen='k'
                )
            
            # Plot SN lines
            for line_name, (obs_wavelength, line_data) in self.sn_lines.items():
                self._add_line_marker(obs_wavelength, line_name, 'red', 'SN')
            
            # Plot galaxy lines
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
            
            # Add text label perpendicular to the line (rotated 90 degrees) - MOVED CLOSER TO LINE
            text = pg.TextItem(name, color=line_colors, fill=(255, 255, 255, 120))
            
            # Get plot range for positioning
            y_range = self.plot_item.viewRange()[1]
            # Position closer to the middle-upper part of the plot for better visibility
            y_pos = y_range[1] * 0.75  # Moved from 0.85 to 0.75 to be closer to the spectrum
            
            # Set position and rotation - slightly offset from the line for better readability
            text.setPos(wavelength + 2, y_pos)  # Small horizontal offset for readability
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
            self._update_status_display()  # Update status after adding lines
            # Removed line tracker update since we no longer have a line tracker
            
        except Exception as e:
            _LOGGER.error(f"Error adding lines to plot: {e}")
    
    # def _update_line_tracker(self): # Line tracker removed
    #     """Update the line tracker list"""
    #     if not hasattr(self, 'line_list'):
    #         return
            
    #     try:
    #         self.line_list.clear()
            
    #         for line_name in self.sn_lines.keys():
    #             item = QtWidgets.QListWidgetItem(f"SN: {line_name}")
    #             item.setForeground(QtGui.QColor('red'))
    #             self.line_list.addItem(item)
            
    #         for line_name in self.galaxy_lines.keys():
    #             item = QtWidgets.QListWidgetItem(f"Galaxy: {line_name}")
    #             item.setForeground(QtGui.QColor('blue'))
    #             self.line_list.addItem(item)
                
    #     except Exception as e:
    #         _LOGGER.error(f"Error updating line tracker: {e}")
    
    def _update_all_lines(self):
        """Update all line positions when redshift changes"""
        # This method would update line positions based on redshift changes
        # Implementation depends on how the line wavelengths are stored
        pass
    
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
                # Left-click with modifiers
                if modifiers & QtCore.Qt.ControlModifier:
                    # Ctrl+Click: Add free-floating point
                    self._add_manual_point(click_wavelength, click_flux, mode="free")
                elif modifiers & QtCore.Qt.ShiftModifier:
                    # Shift+Click: Add spectrum-snapped point
                    self._add_manual_point_snapped(click_wavelength, click_flux)
                else:
                    # Plain click: Smart peak detection
                    self._add_manual_point_smart(click_wavelength, click_flux)
                    
            # Refresh plot
            if self.step2_analysis:
                self.step2_analysis.plot_focused_line()
                self.step2_analysis.update_point_counter()
                
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
            
            # Create new left panel for step 2 (simplified - key controls moved to toolbar)
            main_layout = self.layout()
            self.step2_left_panel = QtWidgets.QFrame()
            self.step2_left_panel.setFrameStyle(QtWidgets.QFrame.StyledPanel)
            self.step2_left_panel.setFixedWidth(280)  # Keep original width since controls moved out
            
            step2_layout = QtWidgets.QVBoxLayout(self.step2_left_panel)
            step2_layout.setContentsMargins(15, 15, 15, 15)
            step2_layout.setSpacing(15)
            
            # Step 2 header
            step_label = QtWidgets.QLabel(f"Step {self.current_step} of {self.total_steps}: Line Analysis")
            step_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2563eb; margin-bottom: 10px;")
            step2_layout.addWidget(step_label)
            
            # Create simplified step 2 interface (main controls moved to toolbar)
            self._create_simplified_step2_interface(step2_layout)
            
            # Add back to step 1 button
            step2_layout.addStretch()
            back_btn = QtWidgets.QPushButton("← Back to Step 1")
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
            step2_layout.addWidget(back_btn)
            
            # Insert the new step 2 panel at the beginning of the main layout
            main_layout.insertWidget(0, self.step2_left_panel)
            
            # Connect toolbar controls to step 2 functionality
            self._connect_step2_toolbar_controls()
            
            # Initialize step 2 data
            self._initialize_step2_interface()
            
            # Update window title
            self.setWindowTitle("Emission Line Analysis - Step 2: Analysis")
            
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
        """Create simplified step 2 interface with main controls moved to toolbar"""
        
        # Manual Points Instructions (only show when relevant)
        # Get platform-appropriate click text
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text("right")
        
        self.manual_instructions = QtWidgets.QLabel(
            "Manual Selection Instructions:\n"
            "• Left Click: Smart peak detection\n"
            "• Ctrl+Click: Add free-floating point\n"
            "• Shift+Click: Add spectrum-snapped point\n" 
            f"• {right_click_text}: Remove closest point"
        )
        self.manual_instructions.setWordWrap(True)
        self.manual_instructions.setStyleSheet(f"color: {self.colors.get('text_secondary', '#666')}; padding: 5px;")
        layout.addWidget(self.manual_instructions)
        
        # Manual point controls
        manual_controls = QtWidgets.QHBoxLayout()
        
        self.clear_points_btn = QtWidgets.QPushButton("Clear Points")
        manual_controls.addWidget(self.clear_points_btn)
        
        self.auto_contour_btn = QtWidgets.QPushButton("Auto Contour")
        manual_controls.addWidget(self.auto_contour_btn)
        
        self.point_counter_label = QtWidgets.QLabel("Points: 0")
        manual_controls.addWidget(self.point_counter_label)
        
        manual_controls.addStretch()
        layout.addLayout(manual_controls)
        
        # Current results display
        analysis_group = QtWidgets.QGroupBox("📊 Current Line Results")
        analysis_layout = QtWidgets.QVBoxLayout(analysis_group)
        
        self.current_result_text = QtWidgets.QTextEdit()
        self.current_result_text.setMaximumHeight(120)
        self.current_result_text.setReadOnly(True)
        self.current_result_text.setPlainText("Select a line and analysis method, then click 'Analyze' in the toolbar...")
        analysis_layout.addWidget(self.current_result_text)
        
        layout.addWidget(analysis_group)
        
        # All Lines Summary
        summary_group = QtWidgets.QGroupBox("📋 All Lines Summary")
        summary_layout = QtWidgets.QVBoxLayout(summary_group)
        
        summary_controls = QtWidgets.QHBoxLayout()
        
        copy_summary_btn = QtWidgets.QPushButton("Copy Summary")
        summary_controls.addWidget(copy_summary_btn)
        
        refresh_summary_btn = QtWidgets.QPushButton("Refresh")
        summary_controls.addWidget(refresh_summary_btn)
        
        export_btn = QtWidgets.QPushButton("💾 Export Results")
        summary_controls.addWidget(export_btn)
        
        summary_controls.addStretch()
        summary_layout.addLayout(summary_controls)
        
        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setMaximumHeight(120)
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)
        
        layout.addWidget(summary_group)
        
        # Store control references for the step2_analysis module
        self.step2_panel_controls = {
            'manual_instructions': self.manual_instructions,
            'clear_points_btn': self.clear_points_btn,
            'auto_contour_btn': self.auto_contour_btn,
            'point_counter_label': self.point_counter_label,
            'current_result_text': self.current_result_text,
            'summary_text': self.summary_text,
            'copy_summary_btn': copy_summary_btn,
            'refresh_summary_btn': refresh_summary_btn,
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
                
            # Connect analyze button (only remaining toolbar button)
            if hasattr(self, 'step2_toolbar_refs'):
                self.step2_toolbar_refs['analyze_btn'].clicked.connect(self.step2_analysis.analyze_current_line)
                
            # Connect panel controls
            if hasattr(self, 'step2_panel_controls'):
                self.step2_panel_controls['clear_points_btn'].clicked.connect(self.step2_analysis.clear_selected_points)
                self.step2_panel_controls['auto_contour_btn'].clicked.connect(self.step2_analysis.auto_detect_contour)
                self.step2_panel_controls['copy_summary_btn'].clicked.connect(self.step2_analysis.copy_summary)
                self.step2_panel_controls['refresh_summary_btn'].clicked.connect(self.step2_analysis.refresh_summary)
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
                self.step2_analysis.current_result_text = self.step2_panel_controls['current_result_text']
                self.step2_analysis.summary_text = self.step2_panel_controls['summary_text']
                self.step2_analysis.point_counter_label = self.step2_panel_controls['point_counter_label']
                self.step2_analysis.manual_instructions = self.step2_panel_controls['manual_instructions']
                self.step2_analysis.clear_points_btn = self.step2_panel_controls['clear_points_btn']
                self.step2_analysis.auto_contour_btn = self.step2_panel_controls['auto_contour_btn']
                
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
            self.setWindowTitle("Emission Line Analysis - Step by Step")
            
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
                        'origin': line_entry.get('origin', 'unknown')
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
        """Show overlay of all available lines when Shift is pressed"""
        if not PYQTGRAPH_AVAILABLE or not self.plot_item:
            _LOGGER.debug("Overlay not available: PyQtGraph missing")
            return
        
        try:
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
            
            # Get all available lines from comprehensive line database
            overlay_lines = {}
            
            try:
                # Import the comprehensive line database directly
                from snid_sage.shared.constants.physical import LINE_DB
                
                # Convert all lines in database to observed wavelengths
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
                    
                    # Clean up line name
                    clean_name = line_name.replace(" (gal)", "")
                    
                    # Calculate observed wavelength
                    if self.current_mode == 'sn':
                        obs_wavelength = line_rest_wavelength * (1 + self._get_effective_sn_redshift())
                    else:
                        obs_wavelength = line_rest_wavelength * (1 + self.host_redshift)
                    
                    # Only include lines in spectrum range
                    if wave_min <= obs_wavelength <= wave_max:
                        overlay_lines[clean_name] = obs_wavelength
                
                _LOGGER.debug(f"Found {len(overlay_lines)} {self.current_mode} lines in database range")
                
            except ImportError:
                _LOGGER.debug("LINE_DB not available")
                return
            
            # Add overlay lines to plot
            for line_name, obs_wavelength in overlay_lines.items():
                # Skip lines that are already added
                if line_name in self.sn_lines or line_name in self.galaxy_lines:
                    continue
                
                # Get color based on element/type
                line_color = self._get_line_color(line_name, self.current_mode)
                
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
                text_item.setPos(obs_wavelength, self.plot_item.viewRange()[1][1] * 0.6)
                text_item.setRotation(90)  # Make text perpendicular
                
                self.plot_item.addItem(overlay_line)
                self.plot_item.addItem(text_item)
                self.overlay_items.extend([overlay_line, text_item])
            
            _LOGGER.debug(f"Displayed {len(overlay_lines)} overlay lines")
            
        except Exception as e:
            _LOGGER.error(f"Error showing line overlay: {e}")
    
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
        c_km_s = 299792.458  # Speed of light in km/s
        velocity_redshift_shift = self.velocity_shift / c_km_s
        effective_sn_redshift = self.host_redshift + velocity_redshift_shift
        return max(0.0, effective_sn_redshift)  # Ensure non-negative

    def _show_interaction_help(self):
        """Show help dialog for mouse interactions and shortcuts"""
        platform_config = get_platform_config()
        right_click_text = platform_config.get_click_text('right')
        
        help_text = f"""Mouse Interactions & Shortcuts

🖱️ MOUSE INTERACTIONS:
• Double-click on spectrum: Add nearest line from database
• {right_click_text} on line marker: Remove line from plot  
• Current mode (SN/Galaxy) determines line type

⌨️ KEYBOARD SHORTCUTS:
• Hold Shift: Show all available lines as overlay
• This helps identify potential lines in your spectrum

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