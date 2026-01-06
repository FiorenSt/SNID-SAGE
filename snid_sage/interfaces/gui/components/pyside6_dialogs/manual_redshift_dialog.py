"""
SNID SAGE - Manual Galaxy Redshift Dialog - PySide6 Version
==========================================================

Interactive dialog for manual galaxy redshift determination.
Allows users to identify galaxy lines by dragging to adjust redshift
and calculates redshift based on the identified lines.

Features drag-to-adjust redshift functionality from galaxy_redshift_demo.py.
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import math

# Import flexible number input widget
from snid_sage.interfaces.gui.components.widgets.flexible_number_input import (
    FlexibleNumberInput,
    create_flexible_double_input
)

# Enhanced button management
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import (
        enhance_dialog_with_preset, setup_sensitivity_toggle_button
    )
    ENHANCED_BUTTONS_AVAILABLE = True
except ImportError:
    ENHANCED_BUTTONS_AVAILABLE = False

# PyQtGraph for plotting
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
    # Import enhanced plot widget
    from snid_sage.interfaces.gui.components.plots.enhanced_plot_widget import EnhancedPlotWidget
    # Set PyQtGraph to use PySide6
    # Configure PyQtGraph for complete software rendering (WSL compatibility)
    pg.setConfigOptions(
        useOpenGL=False,         # Disable OpenGL completely
        antialias=True,          # Keep antialiasing for quality
        enableExperimental=False, # Disable experimental features
        background='w',          # White background
        foreground='k',          # Black foreground for text
        crashWarning=False       # Reduce warnings
    )
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
    _LOGGER = get_logger('gui.pyside6_manual_redshift')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_manual_redshift')

# Import galaxy line constants
try:
    from snid_sage.shared.constants.physical import (
        SPEED_OF_LIGHT_KMS, LINE_DB, CATEGORY_COLORS, SN_LINE_CATEGORIES
    )
    
    # Build galaxy lines dictionary from the comprehensive LINE_DB
    GALAXY_LINES = {}
    LINE_CATEGORIES = {}
    
    # Define element-based categories for better organization
    ELEMENT_CATEGORIES = {
        'hydrogen': 'Hydrogen Lines',
        'helium': 'Helium Lines', 
        'oxygen': 'Oxygen Lines',
        'nitrogen': 'Nitrogen Lines',
        'sulfur': 'Sulfur Lines',
        'calcium': 'Calcium Lines',
        'sodium': 'Sodium Lines',
        'magnesium': 'Magnesium Lines',
        'neon': 'Neon Lines',
        'argon': 'Argon Lines',
        'other': 'Other Lines'
    }
    
    # Extract galaxy lines and build categories
    for line_entry in LINE_DB:
        if (line_entry["origin"] == "galaxy" and 
            line_entry["wavelength_air"] > 0):
            
            line_name = line_entry["key"]
            
            # Clean up the line name (remove "(gal)" suffix)
            display_name = line_name.replace(" (gal)", "")
            
            # Determine element category based on line name
            element_category = 'other'
            for element, category_name in ELEMENT_CATEGORIES.items():
                if element.lower() in display_name.lower():
                    element_category = element
                    break
            
            # Store line data
            GALAXY_LINES[display_name] = {
                'wavelength': line_entry["wavelength_air"],
                'type': line_entry.get("line_type", "unknown"),
                'category': element_category,
                'original_name': line_name
            }
            
            # Track categories
            if element_category not in LINE_CATEGORIES:
                LINE_CATEGORIES[element_category] = ELEMENT_CATEGORIES[element_category]
    
    _LOGGER.debug(f"Loaded {len(GALAXY_LINES)} galaxy lines in {len(LINE_CATEGORIES)} categories")
    
except ImportError:
    # Fallback galaxy lines if constants not available
    GALAXY_LINES = {
        'H-α': {'wavelength': 6564.614, 'type': 'emission', 'category': 'hydrogen'},
        '[OIII] 5007': {'wavelength': 5008.239, 'type': 'emission', 'category': 'oxygen'},
        'Ca II K': {'wavelength': 3933.664, 'type': 'absorption', 'category': 'calcium'},
        'H-β': {'wavelength': 4862.721, 'type': 'emission', 'category': 'hydrogen'},
        'Ca II H': {'wavelength': 3968.470, 'type': 'absorption', 'category': 'calcium'}
    }
    LINE_CATEGORIES = {
        'hydrogen': 'Hydrogen Lines',
        'oxygen': 'Oxygen Lines', 
        'calcium': 'Calcium Lines'
    }
    SPEED_OF_LIGHT_KMS = 299792.458
    _LOGGER.warning("Using fallback galaxy lines")

# Use the simplified set from the original GUI (COMMON_GALAXY_LINES)
COMMON_GALAXY_LINES = {
    'H-α': {'wavelength': 6564.614, 'type': 'emission', 'strength': 'very_strong', 'color': '#ff4444'},
    '[OIII] 5007': {'wavelength': 5008.239, 'type': 'emission', 'strength': 'very_strong', 'color': '#44ff44'}, 
    'H-β': {'wavelength': 4862.721, 'type': 'emission', 'strength': 'strong', 'color': '#ff6666'},
    'Ca II K': {'wavelength': 3933.664, 'type': 'absorption', 'strength': 'strong', 'color': '#888888'},
    'Ca II H': {'wavelength': 3968.470, 'type': 'absorption', 'strength': 'strong', 'color': '#aaaaaa'}
}


class InteractiveRedshiftPlotWidget(QtWidgets.QWidget):
    """
    Interactive PyQtGraph plot widget for galaxy redshift determination.
    Based on the working implementation from galaxy_redshift_demo.py
    
    Features:
    - Real-time drag-to-adjust redshift
    - Fixed vertical markers for galaxy lines
    - Spectrum slides underneath markers
    - Proper mouse event handling
    """
    
    def __init__(self, title="Galaxy Spectrum", parent=None):
        super().__init__(parent)
        self.title = title
        self.overlay_redshift = 0.0
        self.precision_mode = False
        self.dragging = False
        self.drag_start_x = 0.0
        self.drag_start_redshift = 0.0
        self.redshift_changed_callback = None
        self.overlay_active = False
        self.selected_line = None
        
        # Spectrum data
        self.wavelengths = None
        self.flux = None
        self.spectrum_plot = None
        
        # Setup UI
        self._setup_ui()
        # Optional rest wavelength top axis handle
        self._rest_axis = None
    
    def _setup_ui(self):
        """Setup the plot widget UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create enhanced PyQtGraph plot widget with save functionality
        # Global PyQtGraph configuration is already set at module level
        self.plot_widget = EnhancedPlotWidget()
        
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', 'Flux')
        self.plot_widget.setLabel('bottom', 'Obs. Wavelength (Å)')
        self.plot_widget.setTitle(f"{self.title} (drag here)")
        
        # Get the plot item for adding data
        self.plot_item = self.plot_widget.getPlotItem()
        # Ensure right axis is visible (no label) and styled
        try:
            self.plot_item.showAxis('right')
            ra = self.plot_item.getAxis('right')
            if ra:
                ra.setTextPen('black')
                ra.setPen('black')
                ra.setStyle(showValues=False)
        except Exception:
            pass
        # Attach rest wavelength top axis if available
        try:
            if PYQTGRAPH_AVAILABLE and _REST_AXIS_AVAILABLE:
                rest_axis = RestWavelengthAxisItem('top')  # type: ignore
                # Remove default top axis and insert ours
                try:
                    top_axis = self.plot_item.getAxis('top')
                    if top_axis is not None:
                        self.plot_item.layout.removeItem(top_axis)
                except Exception:
                    pass
                self.plot_item.layout.addItem(rest_axis, 1, 1)
                rest_axis.linkToView(self.plot_item.vb)
                rest_axis.set_redshift(self.overlay_redshift)
                self._rest_axis = rest_axis
        except Exception:
            self._rest_axis = None
        
        # Disable plot mouse interaction to prevent spectrum movement during drag
        self.plot_widget.setMouseEnabled(x=False, y=False)
        
        # Connect mouse events for drag-to-adjust redshift only
        self.plot_widget.mousePressEvent = self._on_mouse_press
        self.plot_widget.mouseReleaseEvent = self._on_mouse_release
        self.plot_widget.mouseMoveEvent = self._on_mouse_move
        
        # Add to layout
        layout.addWidget(self.plot_widget)
    
    def set_spectrum_data(self, wavelengths, flux):
        """Set the spectrum data and plot it"""
        # Remove zero padding if present
        if wavelengths is not None and flux is not None:
            # Find non-zero flux regions to remove padding
            nonzero_mask = flux > 0
            if np.any(nonzero_mask):
                # Find first and last non-zero indices
                nonzero_indices = np.where(nonzero_mask)[0]
                start_idx = nonzero_indices[0]
                end_idx = nonzero_indices[-1] + 1
                
                # Trim to remove zero padding
                self.wavelengths = wavelengths[start_idx:end_idx]
                self.flux = flux[start_idx:end_idx]
            else:
                self.wavelengths = wavelengths
                self.flux = flux
        else:
            self.wavelengths = wavelengths
            self.flux = flux
        
        self._plot_spectrum()
    
    def _plot_spectrum(self):
        """Plot the galaxy spectrum"""
        if self.wavelengths is None or self.flux is None:
            return
            
        # Clear existing plots
        self.plot_item.clear()
        
        # Plot the spectrum
        self.spectrum_plot = self.plot_item.plot(
            self.wavelengths,
            self.flux,
            pen=pg.mkPen('black', width=1),
            name='Spectrum',
            connect='all',
            autoDownsample=False,
            clipToView=False,
            downsample=1,
        )
        
        # Set plot range based on actual data
        if len(self.wavelengths) > 0:
            # For zoom plots, don't set the full range here - will be set by _update_zoom_plot
            if self.title == "Zoom Window":
                # Enable Y auto-range for zoom plots
                self.plot_widget.enableAutoRange(axis='y')
                self.plot_widget.setAutoVisible(y=True)
                # X range will be set by _update_zoom_plot method
            else:
                # For main plot, show full spectrum
                self.plot_widget.setXRange(self.wavelengths.min(), self.wavelengths.max())
                self.plot_widget.setYRange(0, self.flux.max() * 1.1)
                # Disable auto Y range for main plot to keep it stable
                self.plot_widget.enableAutoRange(axis='y', enable=False)
    
    def set_overlay_active(self, active, selected_line=None):
        """Set overlay state and update display"""
        self.overlay_active = active
        self.selected_line = selected_line
        self._update_overlay_lines()
        # Keep top axis redshift in sync
        try:
            if self._rest_axis is not None:
                self._rest_axis.set_redshift(self.overlay_redshift)
        except Exception:
            pass
    
    def _update_overlay_lines(self):
        """Update overlay lines display - lines MOVE to redshifted positions"""
        if not self.overlay_active or self.wavelengths is None:
            return
            
        # Remove any existing line items - use a simple approach
        items_to_remove = []
        for item in self.plot_item.items:
            # Check if it's an InfiniteLine or TextItem that we added
            if isinstance(item, (pg.InfiniteLine, pg.TextItem)):
                # Check if it has our custom name attribute
                if hasattr(item, '_snid_line_marker'):
                    items_to_remove.append(item)
        
        for item in items_to_remove:
            self.plot_item.removeItem(item)
        
        # Add galaxy lines at their REDSHIFTED wavelengths (these MOVE with redshift)
        focus_color = '#22c55e'  # Green for selected line
        other_color = '#94a3b8'  # Gray for other lines
        
        for line_name, line_data in COMMON_GALAXY_LINES.items():
            rest_wavelength = line_data['wavelength']
            
            # Calculate observed wavelength: λ_obs = λ_rest * (1 + z)
            observed_wavelength = rest_wavelength * (1 + self.overlay_redshift)
            
            # Lines are drawn at OBSERVED wavelength - they move with redshift
            # Only show if within spectrum range
            if self.wavelengths.min() <= observed_wavelength <= self.wavelengths.max():
                if line_name == self.selected_line:
                    color = focus_color
                    width = 3
                else:
                    color = other_color
                    width = 1
                
                # Draw vertical line at OBSERVED wavelength (moves with redshift)
                line = pg.InfiniteLine(
                    pos=observed_wavelength, 
                    angle=90, 
                    pen=pg.mkPen(color, width=width)
                )
                line._snid_line_marker = True  # Custom marker for removal
                self.plot_item.addItem(line)
                
                # Add label for selected line only (but not for zoom plots)
                if line_name == self.selected_line and self.title != "Zoom Window":
                    text = pg.TextItem(
                        text=line_name, 
                        color=color, 
                        anchor=(0.5, 0.9),  # Closer to the line (0.9 instead of 1.1)
                        angle=90  # Make text perpendicular to the line
                    )
                    text.setPos(observed_wavelength, self.flux.max() * 0.95)  # Closer position
                    text._snid_line_marker = True  # Custom marker for removal
                    self.plot_item.addItem(text)
    
    def _on_mouse_press(self, event):
        """Handle mouse press events"""        
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = True
            # Use raw pixel coordinates for stable dragging
            self.drag_start_x = event.position().x()
            self.drag_start_redshift = self.overlay_redshift
            
            # Change cursor to indicate dragging
            self.setCursor(QtGui.QCursor(QtCore.Qt.ClosedHandCursor))
    
    def _on_mouse_release(self, event):
        """Handle mouse release events"""
        if event.button() == QtCore.Qt.LeftButton:
            if self.dragging:
                self.dragging = False
                self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
    
    def _on_mouse_move(self, event):
        """Handle mouse movement for real-time redshift adjustment"""
        if not self.dragging:
            return
        
        # Use raw pixel coordinates for more stable dragging
        current_x = event.position().x()
        
        # Calculate pixel delta and convert to redshift change
        pixel_delta = current_x - self.drag_start_x
        
        # Calculate sensitivity based on precision mode
        if self.precision_mode:
            sensitivity = 0.0001  # Ultra-precise
        else:
            sensitivity = 0.002   # Normal
        
        # Calculate new redshift based on pixel movement
        new_redshift = self.drag_start_redshift + (pixel_delta * sensitivity)
        new_redshift = max(0.0, min(1.0, new_redshift))  # Limit to 0-1 (more reasonable for galaxies)
        
        # Update redshift
        self.overlay_redshift = new_redshift
        
        # Keep spectrum at original wavelengths - DO NOT shift the spectrum
        # The lines will move instead when _update_overlay_lines() is called
        
        # Update overlay lines to new redshifted positions
        if self.overlay_active:
            self._update_overlay_lines()
        # Update the top axis in real time
        try:
            if self._rest_axis is not None:
                self._rest_axis.set_redshift(self.overlay_redshift)
        except Exception:
            pass
        
        # Call callback if set
        if self.redshift_changed_callback:
            self.redshift_changed_callback(new_redshift)
    
    def set_redshift(self, redshift):
        """Set the redshift value and update line positions accordingly"""
        self.overlay_redshift = max(0.0, min(1.0, redshift))
        try:
            if self._rest_axis is not None:
                self._rest_axis.set_redshift(self.overlay_redshift)
        except Exception:
            pass
        
        # Keep spectrum at original wavelengths - DO NOT shift the spectrum
        # The lines will move instead when _update_overlay_lines() is called
        
        # Update overlay lines to new redshifted positions
        if self.overlay_active:
            self._update_overlay_lines()
    
    def set_precision_mode(self, enabled):
        """Set precision mode for fine redshift adjustment"""
        self.precision_mode = enabled
    
    def set_redshift_changed_callback(self, callback):
        """Set callback function for redshift changes"""
        self.redshift_changed_callback = callback
    
    def get_plot_widget(self):
        """Get the PyQtGraph plot widget for synchronization"""
        return self.plot_widget


class PySide6ManualRedshiftDialog(QtWidgets.QDialog):
    """PySide6 dialog for manual galaxy redshift determination"""
    
    def __init__(
        self,
        parent,
        spectrum_data,
        current_redshift=0.0,
        include_auto_search=False,
        auto_search_callback=None,
    ):
        """Initialize manual redshift dialog"""
        super().__init__(parent)
        
        self.parent_gui = parent
        self.spectrum_data = spectrum_data
        self.current_redshift = current_redshift
        self.include_auto_search = include_auto_search
        # Optional: reuse the normal pipeline via an external callback (e.g. host redshift search controller).
        # When provided, Auto Search will call this callback and use its chosen (cluster) redshift.
        self.auto_search_callback = auto_search_callback
        self.result = None
        
        # UI state
        self.selected_line = "H-α"  # Always start with H-alpha
        self.overlay_active = True  # Always show lines
        self.overlay_redshift = current_redshift if current_redshift > 0 else 0.0
        self.precision_mode = False
        self._updating = False  # Prevent infinite loops during sync
        
        # Plot components
        self.main_plot = None
        self.zoom_plot = None
        
        # Timer tracking for proper cleanup
        self._active_timers = []
        
        # Color scheme matching Advanced Preprocessing
        self.colors = {
            'bg_primary': '#f8fafc',
            'bg_secondary': '#ffffff', 
            'bg_tertiary': '#f1f5f9',
            'text_primary': '#1e293b',
            'text_secondary': '#64748b',
            'border': '#e2e8f0',
            'accent_primary': '#8b5cf6',
            'btn_success': '#16a34a',
            'btn_warning': '#f59e0b',
            'btn_danger': '#ef4444',
            'btn_primary': '#3b82f6',
            'btn_load': '#6E6E6E',
            'btn_preprocessing': '#FFA600',
            'hover': '#f1f5f9'
        }
        
        self._setup_dialog()
        self._create_interface()
        
        # Enhanced button styling and animations (must be after dialog setup)
        self._setup_enhanced_buttons()
        
        # Initial plot
        if self.spectrum_data:
            self._update_plots()
    
    def _setup_dialog(self):
        """Setup dialog window properties"""
        self.setWindowTitle("Manual Galaxy Redshift Determination - SNID SAGE")
        self.setMinimumSize(1100, 500)
        self.resize(1100, 500)
        self.setModal(True)
        
        # Apply styling matching Advanced Preprocessing
        self.setStyleSheet(f"""
            QDialog {{
                background: {self.colors['bg_primary']};
                color: {self.colors['text_primary']};
                font-family: Arial, "Helvetica Neue", Helvetica, "Segoe UI", sans-serif;
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 10pt;
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                background: {self.colors['bg_secondary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background: {self.colors['bg_secondary']};
                font-size: 10pt;
            }}
            QLabel {{
                font-size: 9pt;
            }}
            QComboBox {{
                font-size: 9pt;
                padding: 2px 6px;
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                background: {self.colors['bg_secondary']};
            }}
            QDoubleSpinBox {{
                font-size: 9pt;
                padding: 2px 4px;
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                background: {self.colors['bg_secondary']};
            }}
            /* Button styling handled by enhanced button system */
        """)
    
    def _create_interface(self):
        """Create the main interface with split panel layout"""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Left panel for controls
        self._create_left_panel(main_layout)
        
        # Right panel for plots  
        self._create_right_panel(main_layout)
    
    def _create_left_panel(self, main_layout):
        """Create left control panel matching Advanced Preprocessing style"""
        left_panel = QtWidgets.QFrame()
        left_panel.setFixedWidth(250)
        left_panel.setStyleSheet(f"""
            QFrame {{
                background: {self.colors['bg_secondary']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
            }}
        """)
        
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(6)
        
        # Compact title matching "Preview" style from Advanced Preprocessing
        title_label = QtWidgets.QLabel("Galaxy Redshift")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1e293b; margin-bottom: 8px;")
        left_layout.addWidget(title_label)
        
        # Line selection
        self._create_line_selection_group(left_layout)
        
        # Redshift controls
        self._create_redshift_controls_group(left_layout)
        
        # Auto search (if enabled)
        if self.include_auto_search:
            self._create_auto_search_group(left_layout)
        
        # Add stretch to push buttons to bottom
        left_layout.addStretch()
        
        # Control buttons
        self._create_control_buttons(left_layout)
        
        main_layout.addWidget(left_panel)
    
    def _create_line_selection_group(self, layout):
        """Create line selection controls"""
        group = QtWidgets.QGroupBox("Focus Line Selection")
        group_layout = QtWidgets.QVBoxLayout(group)
        
        # Line dropdown
        line_layout = QtWidgets.QHBoxLayout()
        line_layout.addWidget(QtWidgets.QLabel("Focus line:"))
        
        self.line_combo = QtWidgets.QComboBox()
        self.line_combo.addItems(list(COMMON_GALAXY_LINES.keys()))
        self.line_combo.setCurrentText(self.selected_line)
        self.line_combo.currentTextChanged.connect(self._on_line_selection_changed)
        line_layout.addWidget(self.line_combo)
        
        group_layout.addLayout(line_layout)
        
        layout.addWidget(group)
    
    def _create_redshift_controls_group(self, layout):
        """Create redshift adjustment controls"""
        group = QtWidgets.QGroupBox("Redshift Controls")
        group_layout = QtWidgets.QVBoxLayout(group)
        
        # Current redshift display
        redshift_layout = QtWidgets.QHBoxLayout()
        redshift_layout.addWidget(QtWidgets.QLabel("Current z:"))
        
        self.redshift_display = QtWidgets.QLabel("0.000000")
        self.redshift_display.setStyleSheet("font-weight: bold; color: #1e293b;")
        redshift_layout.addWidget(self.redshift_display)
        redshift_layout.addStretch()
        
        group_layout.addLayout(redshift_layout)
        
        # Direct input
        input_layout = QtWidgets.QHBoxLayout()
        input_layout.addWidget(QtWidgets.QLabel("Direct input:"))
        
        self.redshift_input = create_flexible_double_input(min_val=0.0, max_val=1.0, default=0.0)
        self.redshift_input.setValue(self.overlay_redshift)
        self.redshift_input.valueChanged.connect(self._on_redshift_input_changed)
        input_layout.addWidget(self.redshift_input)
        
        group_layout.addLayout(input_layout)
        
        # Precision mode toggle - styling handled by enhanced button system
        self.precision_button = QtWidgets.QPushButton("Sensitivity: Normal")
        self.precision_button.setObjectName("precision_button")
        # Click handler will be overridden by enhanced button system
        group_layout.addWidget(self.precision_button)
        
        layout.addWidget(group)
    
    def _create_auto_search_group(self, layout):
        """Create automatic search controls"""
        group = QtWidgets.QGroupBox("Automatic Search")
        group_layout = QtWidgets.QVBoxLayout(group)
        
        desc = QtWidgets.QLabel("Let SNID-SAGE find the best redshift match using galaxy templates:")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 9pt; border: none; background: transparent;")
        group_layout.addWidget(desc)
        
        auto_btn = QtWidgets.QPushButton("Auto Search")
        auto_btn.setObjectName("auto_btn")
        auto_btn.clicked.connect(self._perform_auto_search)
        # Styling will be handled by enhanced button system
        group_layout.addWidget(auto_btn)
        
        layout.addWidget(group)
    
    def _create_control_buttons(self, layout):
        """Create dialog control buttons"""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Help button - styling will be handled by enhanced button system
        help_btn = QtWidgets.QPushButton("Help")
        help_btn.setObjectName("help_btn")
        help_btn.clicked.connect(self._show_help)
        button_layout.addWidget(help_btn)
        
        button_layout.addStretch()
        
        # Accept button - styling will be handled by enhanced button system
        accept_btn = QtWidgets.QPushButton("Accept Redshift")
        accept_btn.setObjectName("accept_btn")
        accept_btn.clicked.connect(self._accept_redshift)
        button_layout.addWidget(accept_btn)
        
        layout.addLayout(button_layout)
    
    def _create_right_panel(self, main_layout):
        """Create right visualization panel with dual plots"""
        right_panel = QtWidgets.QFrame()
        right_panel.setStyleSheet(f"""
            QFrame {{
                background: {self.colors['bg_secondary']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
            }}
        """)
        
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(10)
        
        # Compact header matching Advanced Preprocessing "Preview" style
        viz_header = QtWidgets.QLabel("Live Preview")
        viz_header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #1e293b;")
        right_layout.addWidget(viz_header)
        
        if not PYQTGRAPH_AVAILABLE:
            # Fallback message
            no_plot_label = QtWidgets.QLabel("PyQtGraph not available for plotting.\nInstall with: pip install pyqtgraph")
            no_plot_label.setAlignment(QtCore.Qt.AlignCenter)
            no_plot_label.setStyleSheet("color: #f59e0b; font-size: 12pt;")
            right_layout.addWidget(no_plot_label)
        else:
            # Create plot layout
            plots_layout = QtWidgets.QHBoxLayout()
            
            # Main spectrum plot (70%)
            main_plot_frame = QtWidgets.QFrame()
            main_plot_frame.setFrameStyle(QtWidgets.QFrame.Box)
            main_plot_frame.setStyleSheet("QFrame { border: 1px solid #cbd5e1; border-radius: 4px; }")
            main_plot_layout = QtWidgets.QVBoxLayout(main_plot_frame)
            

            
            self.main_plot = InteractiveRedshiftPlotWidget("Main Spectrum")
            self.main_plot.set_redshift_changed_callback(self._on_redshift_changed)
            main_plot_layout.addWidget(self.main_plot)
            
            plots_layout.addWidget(main_plot_frame, 6)
            
            # Zoom plot (40%)
            zoom_plot_frame = QtWidgets.QFrame()
            zoom_plot_frame.setFrameStyle(QtWidgets.QFrame.Box)
            zoom_plot_frame.setStyleSheet("QFrame { border: 1px solid #cbd5e1; border-radius: 4px; }")
            zoom_plot_layout = QtWidgets.QVBoxLayout(zoom_plot_frame)
            

            
            self.zoom_plot = InteractiveRedshiftPlotWidget("Zoom Window")
            self.zoom_plot.set_redshift_changed_callback(self._on_redshift_changed)
            zoom_plot_layout.addWidget(self.zoom_plot)
            
            plots_layout.addWidget(zoom_plot_frame, 4)
            
            right_layout.addLayout(plots_layout)
        
        main_layout.addWidget(right_panel)
    
    def _on_redshift_changed(self, redshift):
        """Handle redshift changes from either plot"""
        if self._updating:
            return
        
        self._updating = True
        self.overlay_redshift = redshift
        
        # Update both plots to stay in sync
        if self.main_plot:
            self.main_plot.overlay_redshift = redshift
            # Keep spectrum at original wavelengths - lines will move instead
            if self.main_plot.overlay_active:
                self.main_plot._update_overlay_lines()
        
        if self.zoom_plot:
            self.zoom_plot.overlay_redshift = redshift
            # Keep spectrum at original wavelengths - lines will move instead
            if self.zoom_plot.overlay_active:
                self.zoom_plot._update_overlay_lines()
        
        # Update zoom plot range to follow the selected line
        self._update_zoom_plot()
        
        # Update UI controls
        self.redshift_input.setValue(redshift)
        self._update_redshift_display()
        
        self._updating = False
    
    def _on_line_selection_changed(self, line_name):
        """Handle line selection change"""
        self.selected_line = line_name
        
        # Update both plots with new selected line
        if self.main_plot:
            self.main_plot.set_overlay_active(self.overlay_active, self.selected_line)
        if self.zoom_plot:
            self.zoom_plot.set_overlay_active(self.overlay_active, self.selected_line)
        
        self._update_zoom_plot()
    

    

    
    def _toggle_precision_mode(self):
        """Toggle precision mode"""
        self.precision_mode = not self.precision_mode
        
        # Update both plots
        if self.main_plot:
            self.main_plot.set_precision_mode(self.precision_mode)
        if self.zoom_plot:
            self.zoom_plot.set_precision_mode(self.precision_mode)
        
        # Update spin box step size
        if self.precision_mode:
            self.redshift_input.setSingleStep(0.001)  # Precision step
            self.precision_button.setText("Sensitivity: Precision")
            self.precision_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.colors['btn_preprocessing']};
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 9pt;
                }}
            """)
            _LOGGER.info("Precision mode activated - Ultra-fine sensitivity")
        else:
            self.redshift_input.setSingleStep(0.1)  # Normal step
            self.precision_button.setText("Sensitivity: Normal")
            self.precision_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.colors['btn_load']};
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 9pt;
                }}
            """)
            _LOGGER.info("Normal mode activated - Standard sensitivity")
    
    def _on_redshift_input_changed(self, value):
        """Handle direct redshift input changes"""
        if not self._updating:
            self._on_redshift_changed(value)
            _LOGGER.info(f"Applied manual redshift input: z = {value:.6f}")
    
    def _perform_auto_search(self):
        """Perform automatic redshift search using galaxy templates"""
        try:
            # Show progress dialog
            progress = QtWidgets.QProgressDialog("Running automatic galaxy redshift search...", "Cancel", 0, 100, self)
            # UX: keep the dialog stable regardless of label text length
            try:
                progress.setWindowTitle("SNID SAGE — Host Redshift Search")
                progress.setMinimumWidth(520)
                progress.setMinimumHeight(120)
            except Exception:
                pass
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()
            
            def progress_callback(message, percent=None):
                if percent is not None:
                    progress.setValue(int(percent))
                progress.setLabelText(message)
                QtWidgets.QApplication.processEvents()
                if progress.wasCanceled():
                    raise InterruptedError("User canceled operation")

            # Ensure the label doesn't cause the dialog to shrink/grow across updates
            try:
                progress.setLabelText("Initializing…")
                QtWidgets.QApplication.processEvents()
            except Exception:
                pass
            
            # Import required modules
            from snid_sage.snid.snid import run_snid_analysis, preprocess_spectrum
            import os
            import numpy as np
            
            progress_callback("Checking spectrum preprocessing...", 5)
            
            # Check if preprocessing is needed
            processed_spectrum = None
            
            # First check if there's already a processed spectrum
            if (hasattr(self.parent_gui, 'app_controller') and 
                hasattr(self.parent_gui.app_controller, 'processed_spectrum') and 
                self.parent_gui.app_controller.processed_spectrum is not None):
                # Use existing processed spectrum from app controller
                processed_spectrum = self.parent_gui.app_controller.processed_spectrum
                progress_callback("Using existing preprocessed spectrum...", 15)
            elif (hasattr(self.parent_gui, 'processed_spectrum') and 
                  self.parent_gui.processed_spectrum is not None):
                # Use existing processed spectrum from parent GUI
                processed_spectrum = self.parent_gui.processed_spectrum
                progress_callback("Using existing preprocessed spectrum...", 15)
            else:
                # Need to run quick preprocessing - check for file path
                file_path = None
                
                # Try different ways to get the file path
                if hasattr(self.parent_gui, 'app_controller') and hasattr(self.parent_gui.app_controller, 'current_file_path'):
                    file_path = self.parent_gui.app_controller.current_file_path
                elif hasattr(self.parent_gui, 'file_path'):
                    file_path = self.parent_gui.file_path
                
                if not file_path:
                    progress.close()
                    QtWidgets.QMessageBox.warning(self, "Auto Search", 
                        "No spectrum file loaded. Please load a spectrum first.")
                    return
                
                progress_callback("Running quick preprocessing...", 10)
                
                # Run minimal preprocessing for galaxy analysis
                # Use isolated preprocessing that doesn't affect main GUI state
                try:
                    # Resolve active profile from parent GUI when available
                    try:
                        active_pid = None
                        if hasattr(self.parent_gui, 'app_controller') and hasattr(self.parent_gui.app_controller, 'active_profile_id'):
                            active_pid = getattr(self.parent_gui.app_controller, 'active_profile_id', None)
                    except Exception:
                        active_pid = None
                    processed_spectrum, trace = preprocess_spectrum(
                        spectrum_path=file_path,
                        # Use minimal preprocessing suitable for galaxies
                        savgol_window=0,  # No smoothing
                        aband_remove=False,  # Keep all data
                        skyclip=False,  # No sky clipping for galaxies
                        emclip_z=-1.0,  # No emission clipping
                        wavelength_masks=None,  # No masking
                        apodize_percent=10.0,  # Standard apodization (keep consistent with auto-search analysis)
                        verbose=False,
                        profile_id=active_pid or 'optical'
                    )
                    
                    # Do not store in the main GUI; this spectrum is only for temporary redshift analysis
                    
                    progress_callback("Preprocessing complete...", 25)
                    
                except Exception as e:
                    progress.close()
                    QtWidgets.QMessageBox.warning(self, "Auto Search", 
                        f"Failed to preprocess spectrum:\n{str(e)}")
                    return
            
            # Get templates directory
            templates_dir = None
            
            # Try different ways to get templates directory
            if hasattr(self.parent_gui, 'get_templates_dir'):
                templates_dir = self.parent_gui.get_templates_dir()
            elif hasattr(self.parent_gui, 'app_controller') and hasattr(self.parent_gui.app_controller, 'templates_dir'):
                templates_dir = self.parent_gui.app_controller.templates_dir
            elif hasattr(self.parent_gui, 'templates_dir'):
                templates_dir = self.parent_gui.templates_dir
            
            if not templates_dir or not os.path.exists(templates_dir):
                progress.close()
                QtWidgets.QMessageBox.warning(self, "Auto Search", 
                    "Templates directory not found. Please check your configuration.")
                return
            
            progress_callback("Loading galaxy templates...", 35)
            
            # Resolve profile-aware redshift range (ONIR can reach higher)
            try:
                active_pid = (
                    getattr(self.parent_gui.app_controller, 'active_profile_id', None)
                    if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'app_controller')
                    else None
                )
                active_pid = str(active_pid or 'optical').strip().lower()
            except Exception:
                active_pid = 'optical'
            zmax_profile = 2.5 if active_pid == 'onir' else 1.0

            # Run SNID analysis with ONLY galaxy templates
            progress_callback("Correlating with galaxy templates...", 40)

            results = None
            analysis_trace = None

            # Prefer a centralized callback (e.g. Host redshift search controller) when supplied.
            if callable(getattr(self, "auto_search_callback", None)):
                try:
                    payload = self.auto_search_callback(
                        progress_callback=lambda msg: progress_callback(msg, None)
                    )
                except TypeError:
                    payload = self.auto_search_callback()

                if isinstance(payload, dict):
                    if payload.get("success") is False:
                        progress.close()
                        QtWidgets.QMessageBox.information(
                            self,
                            "Auto Search",
                            payload.get("error", "Automatic galaxy redshift search failed."),
                        )
                        return
                    results = payload.get("snid_result") or payload.get("results")
                    analysis_trace = payload.get("analysis_trace")

            # Fallback: run locally (still uses the normal pipeline incl. clustering)
            if results is None:
                # Match the normal GUI analysis knobs (prefer last run, then config, then defaults).
                analysis_cfg = {}
                last_kwargs = {}
                try:
                    if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'app_controller'):
                        app = self.parent_gui.app_controller
                        if getattr(app, 'current_config', None):
                            analysis_cfg = (app.current_config.get('analysis', {}) or {})
                        if getattr(app, 'last_analysis_kwargs', None):
                            last_kwargs = (app.last_analysis_kwargs or {})
                except Exception:
                    analysis_cfg = {}
                    last_kwargs = {}

                try:
                    lapmin_val = float(last_kwargs.get('lapmin', analysis_cfg.get('lapmin', 0.3)) or 0.3)
                except Exception:
                    lapmin_val = 0.3
                try:
                    lapmin_val = max(0.0, min(1.0, float(lapmin_val)))
                except Exception:
                    lapmin_val = 0.3

                try:
                    hsigma_thr_val = float(
                        last_kwargs.get('hsigma_lap_ccc_threshold', analysis_cfg.get('hsigma_lap_ccc_threshold', 1.5)) or 1.5
                    )
                except Exception:
                    hsigma_thr_val = 1.5

                try:
                    peak_window_size_val = int(last_kwargs.get('peak_window_size', analysis_cfg.get('peak_window_size', 10)) or 10)
                except Exception:
                    peak_window_size_val = 10

                results, analysis_trace = run_snid_analysis(
                    processed_spectrum=processed_spectrum,
                    templates_dir=templates_dir,
                    # Template filtering - only galaxies
                    type_filter=['Galaxy', 'Gal'],  # Include both Galaxy and Gal types
                    # Redshift range suitable for galaxies
                    zmin=-0.01,
                    zmax=float(zmax_profile),
                    # Correlation parameters (normal/default GUI behavior)
                    lapmin=lapmin_val,
                    hsigma_lap_ccc_threshold=hsigma_thr_val,
                    peak_window_size=peak_window_size_val,
                    # Output control: respect configured max_output_templates when available
                    max_output_templates=(
                        int(self.parent_gui.app_controller.current_config.get('analysis', {}).get('max_output_templates', 20))
                        if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'app_controller') and hasattr(self.parent_gui.app_controller, 'current_config') and self.parent_gui.app_controller.current_config is not None
                        else 20
                    ),
                    verbose=False,
                    show_plots=False,
                    save_plots=False,
                    progress_callback=lambda msg, pct=None: progress_callback(msg, 40 + (pct or 0) * 0.5 if pct else None),
                    # Use the same active profile as preprocessing/GUI
                    profile_id=(getattr(self.parent_gui.app_controller, 'active_profile_id', None)
                                if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'app_controller') else None)
                )
            
            progress_callback("Processing results...", 95)
            
            # For host-galaxy redshift discovery we can proceed whenever we have candidate matches,
            # even if the full SNIDResult did not mark the run as "successful" (e.g. no robust type consensus).
            if results and hasattr(results, 'best_matches') and results.best_matches:
                best_match = results.best_matches[0]

                # Prefer the winning cluster redshift (normal-run behavior) and make Q_cluster handling robust.
                chosen_redshift = None
                q_cluster = None
                choice_source = None
                scored = []
                try:
                    clres = getattr(results, 'clustering_results', None)
                    if isinstance(clres, dict):
                        best_cluster = clres.get('best_cluster') if isinstance(clres.get('best_cluster'), dict) else None
                        all_candidates = clres.get('all_candidates', []) or []

                        # Gather candidates from all_candidates + best_cluster (no gating on clres['success'])
                        candidates = []
                        for c in all_candidates:
                            if isinstance(c, dict) and c:
                                candidates.append(c)
                        if best_cluster and best_cluster not in candidates:
                            candidates.append(best_cluster)

                        # Normalize candidates: require finite enhanced_redshift and compute true Q_cluster.
                        for c in candidates:
                            try:
                                zc = c.get('enhanced_redshift', None)
                                if zc is None or not np.isfinite(float(zc)):
                                    continue
                                score = c.get('penalized_score', c.get('composite_score', None))
                                if score is None:
                                    # Defensive fallback: approximate penalized score if fields exist
                                    try:
                                        score = float(c.get('top_5_mean', 0.0) or 0.0) * float(c.get('penalty_factor', 1.0) or 1.0)
                                    except Exception:
                                        score = 0.0
                                scored.append((float(score), c))
                            except Exception:
                                continue
                except Exception:
                    scored = []

                scored.sort(key=lambda t: t[0], reverse=True)

                # If we have multiple candidates and the best is weak, force the user to choose (or cancel).
                if scored:
                    best_score, best_c = scored[0]
                    if best_c.get('enhanced_redshift', None) is not None:
                        try:
                            chosen_redshift = float(best_c.get('enhanced_redshift'))
                        except Exception:
                            chosen_redshift = None
                    q_cluster = float(best_score)
                    choice_source = f"{best_c.get('type', 'Galaxy')} cluster {best_c.get('cluster_id', 0)}"

                    if best_score < 2.5 and len(scored) > 1:
                        try:
                            items = []
                            for score, c in scored:
                                try:
                                    cid = c.get('cluster_id', 0)
                                    z_show = float(c.get('enhanced_redshift', 0.0) or 0.0)
                                    n_show = int(c.get('size', len(c.get('matches', []) or [])) or 0)
                                    items.append(f"Cluster {cid}: z={z_show:.6f}   Q_cluster={float(score):.2f}   (N={n_show})")
                                except Exception:
                                    items.append(f"Cluster: z={float(c.get('enhanced_redshift', 0.0) or 0.0):.6f}   Q_cluster={float(score):.2f}")

                            selected, ok = QtWidgets.QInputDialog.getItem(
                                self,
                                "Weak Host Redshift Clusters",
                                "All host-redshift clusters are weak (Q_cluster < 2.5).\n\n"
                                "Pick which cluster redshift to apply (or Cancel to do nothing):",
                                items,
                                0,
                                False
                            )
                            if not ok:
                                # User canceled: do nothing (leave existing redshift untouched)
                                # Ensure the progress dialog is removed as well.
                                try:
                                    if 'progress' in locals():
                                        progress.close()
                                except Exception:
                                    pass
                                return

                            sel_idx = items.index(selected) if selected in items else 0
                            sel_score, sel_c = scored[max(0, min(sel_idx, len(scored) - 1))]
                            chosen_redshift = float(sel_c.get('enhanced_redshift'))
                            q_cluster = float(sel_score)
                            choice_source = f"{sel_c.get('type', 'Galaxy')} cluster {sel_c.get('cluster_id', 0)}"

                            # UX: the chooser is the explicit user decision point for weak multi-cluster cases.
                            # Apply immediately and exit without showing an additional "Weak Match Found" dialog.
                            try:
                                if 'progress' in locals():
                                    progress.close()
                            except Exception:
                                pass

                            try:
                                self.redshift_input.setValue(float(chosen_redshift))
                                self._on_redshift_changed(float(chosen_redshift))
                                if hasattr(self.parent_gui, 'redshift_status_label'):
                                    try:
                                        self.parent_gui.redshift_status_label.setText(
                                            f"Auto-detected redshift: z = {float(chosen_redshift):.6f}"
                                        )
                                    except Exception:
                                        pass
                                _LOGGER.info(
                                    f"Applied user-selected weak host cluster redshift: z = {float(chosen_redshift):.6f} "
                                    f"({choice_source}; Q_cluster: {float(q_cluster):.2f})"
                                )
                            finally:
                                # Clean up temporary data
                                processed_spectrum = None
                                results = None
                                analysis_trace = None
                            return
                        except Exception:
                            pass

                # Fallback to consensus redshift, then best-match.
                if chosen_redshift is None:
                    try:
                        zc = getattr(results, 'consensus_redshift', None)
                        if zc is not None and np.isfinite(float(zc)):
                            chosen_redshift = float(zc)
                            choice_source = "consensus redshift"
                    except Exception:
                        pass
                if chosen_redshift is None:
                    chosen_redshift = float(best_match.get('redshift', 0.0) or 0.0)
                    choice_source = "best match"
                # Match dicts coming from run_snid_analysis store the template metadata under `match["template"]`.
                try:
                    template_name = (best_match.get('template', {}) or {}).get('name', None) or best_match.get('template_name', 'Unknown')
                except Exception:
                    template_name = best_match.get('template_name', 'Unknown')

                # Prefer Q_cluster (penalized_score) when available; otherwise fall back to the best-match metric.
                if q_cluster is not None:
                    metric_score = float(q_cluster)
                    metric_label = "Q_cluster"
                else:
                    metric_label = "Metric"
                    try:
                        from snid_sage.shared.utils.math_utils import get_best_metric_value
                        metric_score = float(get_best_metric_value(best_match))
                    except Exception:
                        metric_score = best_match.get('hsigma_lap_ccc', best_match.get('hlap', 0.0))
                
                progress.close()
                
                # Auto-apply threshold:
                # Match-quality categories in the pipeline use Q_cluster thresholds:
                #   Very Low < 2.5, Low 2.5–<5, Medium 5–<8, High ≥ 8
                # Here we use Q_cluster when available; if Q_cluster < 2.5, always treat as weak (never auto-apply).
                if metric_label == "Q_cluster" and float(metric_score) < 2.5:
                    force_weak = True
                else:
                    force_weak = False

                if (not force_weak) and float(metric_score) >= 2.5:
                    # Directly apply the redshift without asking
                    self.redshift_input.setValue(chosen_redshift)
                    # Trigger the redshift change which will update the line positions
                    self._on_redshift_changed(chosen_redshift)
                    
                    # Update status
                    if hasattr(self.parent_gui, 'redshift_status_label'):
                        self.parent_gui.redshift_status_label.setText(
                            f"Auto-detected redshift: z = {chosen_redshift:.6f}")
                    
                    _LOGGER.info(
                        f"Applied automatic galaxy redshift: z = {chosen_redshift:.6f} "
                        f"({choice_source}; {metric_label}: {metric_score:.2f}) from template {template_name}"
                    )
                    
                    # Clean up temporary data
                    processed_spectrum = None
                    results = None
                    analysis_trace = None
                    
                else:
                    # Show match but ask for confirmation if correlation is weak
                    reply = QtWidgets.QMessageBox.question(self, "Weak Match Found",
                        f"⚠️ Weak galaxy template match found:\n\n"
                        f"📋 Template: {template_name}\n"
                        f"🌌 Redshift: z = {chosen_redshift:.6f}\n"
                        f"📊 {metric_label}: {float(metric_score):.2f} (<2.5; weak)\n"
                        f"🧩 Source: {choice_source}\n\n"
                        f"Apply this redshift anyway?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                    
                    if reply == QtWidgets.QMessageBox.Yes:
                        self.redshift_input.setValue(chosen_redshift)
                        self._on_redshift_changed(chosen_redshift)
                        
                        if hasattr(self.parent_gui, 'redshift_status_label'):
                            self.parent_gui.redshift_status_label.setText(
                                f"Auto-detected redshift: z = {chosen_redshift:.6f}")
                        
                        _LOGGER.info(
                            f"Applied weak galaxy redshift match: z = {chosen_redshift:.6f} "
                            f"({choice_source}; {metric_label}: {metric_score:.2f}) from template {template_name}"
                        )
                    else:
                        # User declined weak match: do not change existing redshift status
                        pass
                    
                    # Clean up temporary data
                    processed_spectrum = None
                    results = None
                    analysis_trace = None
                
            else:
                progress.close()
                QtWidgets.QMessageBox.information(
                    self,
                    "Auto Search",
                    (
                        "No good galaxy template matches found.\n\n"
                        "This could mean:\n"
                        "• The spectrum has no clear galaxy features\n"
                        "• The spectrum quality is too low\n\n"
                        "Try manual redshift adjustment instead."
                    )
                )
                # Do not change existing redshift status; this is a normal outcome
                
                # Clean up temporary data on no matches
                processed_spectrum = None
                results = None
                analysis_trace = None
            
        except InterruptedError:
            # User canceled - clean up temporary data
            if 'progress' in locals():
                progress.close()
            # Clean up any temporary processing data
            processed_spectrum = None
            results = None
            analysis_trace = None
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QtWidgets.QMessageBox.critical(self, "Auto Search Error", 
                f"Error during automatic search:\n\n{str(e)}\n\n"
                f"Please try manual redshift determination or check your spectrum file.")
            _LOGGER.error(f"Auto search error: {e}")
            # Clean up any temporary processing data
            processed_spectrum = None
            results = None
            analysis_trace = None
    
    def _show_help(self):
        """Show help dialog"""
        help_text = """Manual Galaxy Redshift Determination Help

How to use this tool:

🎯 FOCUS LINE SELECTION:
• Choose a galaxy line to focus on in the zoom window
• Strong lines like H-α and [OIII] 5007 work best
• The selected line appears brighter in the plots

🌌 REDSHIFT ADJUSTMENT:
• Direct Input: Enter known redshift and click Apply
• Interactive: Click "Show Lines" then drag on main plot
• Precision Mode: Ultra-fine adjustment sensitivity
• Normal Mode: Faster adjustment for coarse tuning

🔍 AUTOMATIC SEARCH:
• Uses SNID galaxy templates for automatic detection
• Requires preprocessed spectrum
• Provides best-match redshift suggestion

📊 PLOT INTERACTION:
• Main plot: Full spectrum with all reference lines
• Zoom plot: Focused view around selected line
• Drag horizontally to adjust redshift in real-time
• Selected line is highlighted, others are faded

💡 TIPS:
• Strong emission lines (H-α, [OIII]) are most reliable
• Use Precision Mode for final fine-tuning
• Try Auto Search if you're unsure of the redshift
• Accept when reference lines align with spectrum features
"""
        QtWidgets.QMessageBox.information(self, "Manual Redshift Help", help_text)
    
    def _accept_redshift(self):
        """Accept the current redshift and show mode selection dialog"""
        if self.overlay_redshift <= 0:
            QtWidgets.QMessageBox.warning(self, "No Redshift", 
                "Please adjust the redshift first before accepting.")
            return
        
        # Show redshift mode selection dialog
        try:
            from snid_sage.interfaces.gui.components.pyside6_dialogs.redshift_mode_dialog import show_redshift_mode_dialog
            
            mode_result = show_redshift_mode_dialog(self, self.overlay_redshift)
            if mode_result is not None:
                self.result = mode_result  # This will contain both redshift and mode info
                _LOGGER.info(f"Accepted redshift configuration: z = {self.overlay_redshift:.6f}, Mode: {mode_result.get('mode', 'search')}")
                self.accept()
            else:
                _LOGGER.info("Redshift mode selection cancelled")
                # Don't close the dialog - user can try again
        except ImportError:
            # Fallback to simple redshift acceptance if redshift mode dialog not available
            _LOGGER.warning("Redshift mode dialog not available, using simple redshift acceptance")
            self.result = self.overlay_redshift
            self.accept()
    
    def _update_plots(self):
        """Update both main and zoom plots"""
        if not PYQTGRAPH_AVAILABLE or not self.spectrum_data:
            return
            
        wavelength = self.spectrum_data['wavelength']
        flux = self.spectrum_data['flux']
        
        # Set spectrum data for both plots
        if self.main_plot:
            self.main_plot.set_spectrum_data(wavelength, flux)
            self.main_plot.set_overlay_active(self.overlay_active, self.selected_line)
            self.main_plot.set_redshift(self.overlay_redshift)
        
        if self.zoom_plot:
            self.zoom_plot.set_spectrum_data(wavelength, flux)
            self.zoom_plot.set_overlay_active(self.overlay_active, self.selected_line)
            self.zoom_plot.set_redshift(self.overlay_redshift)
        
        # Update zoom-specific view (ensure it happens after spectrum data is set)
        self._update_zoom_plot()
        
        # Force zoom range update with a slight delay to ensure it takes effect
        if self.zoom_plot:
            # Create proper QTimer objects for tracking
            timer1 = QtCore.QTimer(self)  # Set parent to dialog
            timer1.setSingleShot(True)
            timer1.timeout.connect(self._update_zoom_plot)
            timer1.start(10)
            self._active_timers.append(timer1)
            
            # Also ensure proper Y-axis scaling
            timer2 = QtCore.QTimer(self)  # Set parent to dialog
            timer2.setSingleShot(True)
            timer2.timeout.connect(self._safe_ensure_zoom_y_scaling)
            timer2.start(20)
            self._active_timers.append(timer2)
        
        self._update_redshift_display()
    
    def _update_zoom_plot(self):
        """Update the zoom plot focused on selected line"""
        if not self.zoom_plot or not self.overlay_active or self.selected_line not in COMMON_GALAXY_LINES:
            return
        
        line_data = COMMON_GALAXY_LINES[self.selected_line]
        rest_wave = line_data['wavelength']
        
        # Calculate observed wavelength: λ_obs = λ_rest * (1 + z)
        observed_wave = rest_wave * (1 + self.overlay_redshift)
        
        # Set zoom range around the OBSERVED wavelength (where the redshifted line is)
        zoom_width = 200  # ±100 Å around line as requested
        zoom_min = observed_wave - zoom_width / 2
        zoom_max = observed_wave + zoom_width / 2
        
        # Ensure the zoom range is within the spectrum bounds
        if hasattr(self.zoom_plot, 'wavelengths') and self.zoom_plot.wavelengths is not None:
            spectrum_min = self.zoom_plot.wavelengths.min()
            spectrum_max = self.zoom_plot.wavelengths.max()
            
            # Adjust zoom range if it goes outside spectrum bounds
            if zoom_min < spectrum_min:
                zoom_min = spectrum_min
                zoom_max = min(zoom_min + zoom_width, spectrum_max)
            elif zoom_max > spectrum_max:
                zoom_max = spectrum_max
                zoom_min = max(zoom_max - zoom_width, spectrum_min)
        
        # Update zoom plot range
        self.zoom_plot.get_plot_widget().setXRange(zoom_min, zoom_max)
        # Disable auto X range to prevent it from expanding back to full spectrum
        self.zoom_plot.get_plot_widget().enableAutoRange(axis='x', enable=False)
        
        # Use custom Y-axis scaling for better zoom view
        self._ensure_zoom_y_scaling()
    
    def _ensure_zoom_y_scaling(self):
        """Ensure proper Y-axis scaling for zoom plot"""
        if not self.zoom_plot or not hasattr(self.zoom_plot, 'wavelengths') or self.zoom_plot.wavelengths is None:
            return
        
        # Get current X range
        plot_widget = self.zoom_plot.get_plot_widget()
        view_range = plot_widget.getViewBox().viewRange()
        x_min, x_max = view_range[0]
        
        # Find flux values in the current zoom range
        wave_mask = (self.zoom_plot.wavelengths >= x_min) & (self.zoom_plot.wavelengths <= x_max)
        if np.any(wave_mask) and hasattr(self.zoom_plot, 'flux') and self.zoom_plot.flux is not None:
            zoom_flux = self.zoom_plot.flux[wave_mask]
            if len(zoom_flux) > 0:
                # Set Y range with a small margin
                flux_min = np.min(zoom_flux)
                flux_max = np.max(zoom_flux)
                flux_margin = (flux_max - flux_min) * 0.1
                plot_widget.setYRange(flux_min - flux_margin, flux_max + flux_margin)
    
    def _update_redshift_display(self):
        """Update the redshift display"""
        if self.overlay_redshift > 0:
            self.redshift_display.setText(f"{self.overlay_redshift:.6f}")
        else:
            self.redshift_display.setText("0.000000")
    
    def _safe_ensure_zoom_y_scaling(self):
        """Safely ensure zoom Y scaling with null checks"""
        try:
            if hasattr(self, 'zoom_plot') and self.zoom_plot:
                self._ensure_zoom_y_scaling()
        except Exception:
            # Silently handle cleanup-related errors
            pass
    
    def _cleanup_resources(self):
        """Clean up PyQtGraph widgets and timers"""
        try:
            # Stop any active timers
            for timer in getattr(self, '_active_timers', []):
                if timer and hasattr(timer, 'stop'):
                    try:
                        timer.stop()
                        timer.deleteLater()  # Properly delete the timer
                    except:
                        pass
            self._active_timers = []
            
            # Clean up plot widgets
            if hasattr(self, 'main_plot') and self.main_plot:
                try:
                    # Clear plot data
                    plot_widget = getattr(self.main_plot, 'plot_widget', None)
                    if plot_widget and hasattr(plot_widget, 'clear'):
                        plot_widget.clear()
                    # Disconnect any signals
                    if hasattr(self.main_plot, 'disconnect'):
                        self.main_plot.disconnect()
                except:
                    pass
                self.main_plot = None
            
            if hasattr(self, 'zoom_plot') and self.zoom_plot:
                try:
                    # Clear plot data
                    plot_widget = getattr(self.zoom_plot, 'plot_widget', None)
                    if plot_widget and hasattr(plot_widget, 'clear'):
                        plot_widget.clear()
                    # Disconnect any signals
                    if hasattr(self.zoom_plot, 'disconnect'):
                        self.zoom_plot.disconnect()
                except:
                    pass
                self.zoom_plot = None
                
        except Exception:
            # Silently handle cleanup errors to prevent cascading failures
            pass
    
    def closeEvent(self, event):
        """Handle dialog closing with proper cleanup"""
        try:
            self._cleanup_resources()
            super().closeEvent(event)
        except Exception:
            # Accept event even if cleanup fails
            event.accept()
    
    def reject(self):
        """Handle dialog rejection with cleanup"""
        try:
            self._cleanup_resources()
            super().reject()
        except Exception:
            # Call parent reject even if cleanup fails
            try:
                super().reject()
            except:
                pass
    
    def accept(self):
        """Handle dialog acceptance with cleanup"""
        try:
            self._cleanup_resources()
            super().accept()
        except Exception:
            # Call parent accept even if cleanup fails
            try:
                super().accept()
            except:
                pass
    
    def get_result(self):
        """Get the determined redshift"""
        return self.result
    
    def _setup_enhanced_buttons(self):
        """Setup enhanced button styling and animations"""
        if not ENHANCED_BUTTONS_AVAILABLE:
            _LOGGER.info("Enhanced buttons not available, using standard styling")
            return
        
        try:
            # Use the manual redshift dialog preset
            self.button_manager = enhance_dialog_with_preset(
                self, 'manual_redshift_dialog'
            )
            
            # Setup the special sensitivity toggle button
            if hasattr(self, 'precision_button'):
                # Make both states share the same color as the active state
                active = "#FFA600"   # ocre/orange for both states
                setup_sensitivity_toggle_button(
                    self.button_manager,
                    self.precision_button,
                    self._toggle_precision_mode_enhanced,
                    initial_state=self.precision_mode,
                    active_color=active,
                    inactive_color=active
                )
            
            _LOGGER.info("Enhanced buttons successfully applied to manual redshift dialog")
            
        except Exception as e:
            _LOGGER.error(f"Failed to setup enhanced buttons: {e}")
    
    def _toggle_precision_mode_enhanced(self, new_state: bool):
        """Enhanced precision mode toggle with proper state management"""
        self.precision_mode = new_state
        
        # Update both plots
        if self.main_plot:
            self.main_plot.set_precision_mode(self.precision_mode)
        if self.zoom_plot:
            self.zoom_plot.set_precision_mode(self.precision_mode)
        
        # Update spin box step size
        if self.precision_mode:
            self.redshift_input.setSingleStep(0.001)  # Precision step
            _LOGGER.info("Precision mode activated - Ultra-fine sensitivity")
        else:
            self.redshift_input.setSingleStep(0.1)  # Normal step
            _LOGGER.info("Normal mode activated - Standard sensitivity")


def show_manual_redshift_dialog(
    parent,
    spectrum_data,
    current_redshift=0.0,
    include_auto_search=False,
    auto_search_callback=None,
):
    """
    Show manual redshift dialog and return the determined redshift.
    
    Args:
        parent: Parent window
        spectrum_data: Dictionary with 'wavelength' and 'flux' arrays
        current_redshift: Current redshift estimate (if any)
        include_auto_search: Whether to include automatic search functionality
        
    Returns:
        Determined redshift or None if cancelled
    """
    dialog = PySide6ManualRedshiftDialog(
        parent,
        spectrum_data,
        current_redshift,
        include_auto_search,
        auto_search_callback=auto_search_callback,
    )
    
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        return dialog.get_result()
    else:
        return None 