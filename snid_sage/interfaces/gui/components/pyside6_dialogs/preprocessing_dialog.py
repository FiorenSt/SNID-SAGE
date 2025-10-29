"""
PySide6 Advanced Preprocessing Dialog for SNID SAGE GUI
======================================================

Complete PySide6 implementation of the advanced preprocessing dialog.

Features:
- 6-step preprocessing workflow with split-panel UI
- Real-time spectrum preview using PyQtGraph
- Interactive masking with drag selection
- Interactive continuum editing with control points
- All preprocessing operations (filtering, rebinning, apodization)
- Professional Qt styling and theming
- Step-by-step wizard interface
"""

import numpy as np
from typing import Optional, Dict, Any
from PySide6 import QtWidgets, QtCore

# PyQtGraph for plotting
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
    # Import simple plot widget (without save functionality for preprocessing previews)
    from snid_sage.interfaces.gui.components.plots.enhanced_plot_widget import SimplePlotWidget
    # Configure PyQtGraph for complete software rendering (consistent with other dialogs)
    pg.setConfigOptions(
        useOpenGL=False,         # Disable OpenGL completely
        antialias=True,          # Keep antialiasing for quality
        enableExperimental=False, # Disable experimental features
        crashWarning=False       # Reduce warnings
    )
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None
    SimplePlotWidget = None

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_preprocessing_dialog')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_preprocessing_dialog')

# Import SNID preprocessing helpers used by this dialog
try:
    from snid_sage.snid.preprocessing import (
        init_wavelength_grid, get_grid_params,
        apodize
    )
    SNID_AVAILABLE = True
except ImportError:
    SNID_AVAILABLE = False
    _LOGGER.warning("SNID preprocessing functions not available")

# Import our custom components
from snid_sage.interfaces.gui.features.preprocessing.pyside6_preview_calculator import PySide6PreviewCalculator
from snid_sage.interfaces.gui.features.preprocessing.steps import (
    create_step0_options, apply_step0, calculate_step0_preview,
    create_step1_options, apply_step1, calculate_step1_preview,
    create_step2_options, apply_step2, calculate_step2_preview,
    create_step3_options, apply_step3, calculate_step3_preview,
    create_step4_options, apply_step4, calculate_step4_preview,
    create_step5_options,
)
from snid_sage.interfaces.gui.components.widgets.pyside6_interactive_masking_widget import PySide6InteractiveMaskingWidget
from snid_sage.interfaces.gui.components.widgets.pyside6_interactive_continuum_widget import PySide6InteractiveContinuumWidget

# Enhanced button management
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except ImportError:
    ENHANCED_BUTTONS_AVAILABLE = False


class PySide6PreprocessingDialog(QtWidgets.QDialog):
    """PySide6 dialog for comprehensive preprocessing configuration"""
    
    def __init__(self, parent=None, spectrum_data=None):
        """Initialize preprocessing dialog"""
        super().__init__(parent)
        
        self.parent_gui = parent
        self.spectrum_data = spectrum_data  # (wave, flux) tuple
        self.result = None
        
        # Preprocessing state
        self.current_step = 0
        self.total_steps = 6
        self.step_names = [
            "Masking & Clipping Operations",
            "Savitzky-Golay Filtering", 
            "Log-wavelength Rebinning & Flux Scaling",
            "Continuum Fitting & Interactive Editing",
            "Apodization",
            "Final Review"
        ]
        
        # Preview data
        self.original_wave = None
        self.original_flux = None
        self.preview_wave = None
        self.preview_flux = None
        
        # Processing components
        self.preview_calculator = None
        self.plot_manager = None
        self.masking_widget = None
        self.continuum_widget = None
        
        # Processing parameters - Initialize with dialog defaults
        self.processing_params = self._get_default_params()
        # Internal guard to avoid preview updates while rebuilding options UI
        self._rebuilding_options = False
        
        # UI components
        self.left_panel = None
        self.right_panel = None
        self.step_widgets = []
        self.options_frame = None
        
        # Theme colors
        self.colors = self._get_theme_colors()
        
        # Initialize wavelength grid for preprocessing using active profile when available
        if SNID_AVAILABLE:
            try:
                # Resolve profile id: prefer parent GUI's controller → env → config → optical
                active_pid = None
                try:
                    if hasattr(parent, 'app_controller') and hasattr(parent.app_controller, 'active_profile_id'):
                        active_pid = getattr(parent.app_controller, 'active_profile_id', None)
                except Exception:
                    active_pid = None
                if active_pid is None:
                    try:
                        import os
                        active_pid = os.environ.get('SNID_SAGE_ACTIVE_PROFILE') or os.environ.get('SNID_SAGE_PROFILE')
                    except Exception:
                        active_pid = None
                if active_pid is None:
                    try:
                        from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
                        cfg = ConfigurationManager().load_config()
                        active_pid = (cfg.get('processing', {}) or {}).get('active_profile_id', None)
                    except Exception:
                        active_pid = None
                from snid_sage.shared.profiles.builtins import register_builtins
                from snid_sage.shared.profiles.registry import get_profile
                register_builtins()
                prof = get_profile(active_pid or 'optical')
                grid = prof.grid
                init_wavelength_grid(num_points=int(grid.nw), min_wave=float(grid.min_wave_A), max_wave=float(grid.max_wave_A))
            except Exception:
                # Safe fallback to defaults
                init_wavelength_grid()
        
        # Load spectrum data if provided
        if spectrum_data:
            self.original_wave, self.original_flux = spectrum_data
            self.preview_wave = self.original_wave.copy()
            self.preview_flux = self.original_flux.copy()
            
            # Initialize preview calculator with proper PySide6 version
            self.preview_calculator = PySide6PreviewCalculator(
                self.original_wave, self.original_flux
            )
            
            # Stage memory no longer used for UI controls (revert removed)
            # Auto-run spike detection and add to masks for Step 0 visualization
            try:
                from snid_sage.snid.preprocessing import find_spike_indices
                idx = find_spike_indices(
                    self.original_wave,
                    self.original_flux,
                    floor_z=50.0,
                    baseline_window=501,
                    baseline_width=None,
                    rel_edge_ratio=2.0,
                    min_separation=2,
                    max_removals=None,
                    min_abs_resid=None,
                )
                if idx is not None and len(idx) > 0:
                    # Group contiguous indices into wavelength intervals
                    w = self.original_wave
                    idx_sorted = np.array(sorted(set(map(int, idx.tolist()))), int)
                    groups = []
                    start = idx_sorted[0]
                    prev = idx_sorted[0]
                    for k in idx_sorted[1:]:
                        if k == prev + 1:
                            prev = k
                        else:
                            groups.append((start, prev))
                            start = k
                            prev = k
                    groups.append((start, prev))
                    # Convert to small mask regions around spikes
                    auto_masks = []
                    for a, b in groups:
                        # Expand region to include one bin before and after the spike run
                        a_exp = max(0, a - 1)
                        b_exp = min(len(w) - 1, b + 1)
                        wl_min = float(w[a_exp])
                        wl_max = float(w[b_exp])
                        if wl_max < wl_min:
                            wl_min, wl_max = wl_max, wl_min
                        auto_masks.append((wl_min, wl_max))
                    # Defer adding to widget until widgets are initialized
                    self._initial_auto_masks = auto_masks
                    _LOGGER.info(f"Auto spike masking proposed {len(auto_masks)} regions for initial masking display")
                else:
                    self._initial_auto_masks = []
            except Exception as e:
                self._initial_auto_masks = []
                _LOGGER.debug(f"Auto spike detection skipped: {e}")
        
        self.setup_ui()
        self._initialize_components()
        # If we have auto masks, add them now to masking widget so they're shown in red and editable
        try:
            if hasattr(self, '_initial_auto_masks') and self._initial_auto_masks and self.masking_widget:
                self.masking_widget.set_mask_regions(self._initial_auto_masks)
        except Exception as e:
            _LOGGER.debug(f"Failed to add auto masks to widget: {e}")
        self._update_preview()
        
        # Debug logging
        _LOGGER.debug(f"PyQtGraph available: {PYQTGRAPH_AVAILABLE}")
        if self.plot_manager:
            top_plot, bottom_plot = self.plot_manager.get_plot_widgets()
            _LOGGER.debug(f"Plot widgets available: top={top_plot is not None}, bottom={bottom_plot is not None}")
    
    def _get_theme_colors(self) -> Dict[str, str]:
        """Get theme colors from parent or defaults"""
        if hasattr(self.parent_gui, 'theme_colors'):
            return self.parent_gui.theme_colors
        else:
            return {
                'bg_primary': '#f8fafc',
                'bg_secondary': '#ffffff',
                'bg_tertiary': '#f1f5f9',
                'text_primary': '#1e293b',
                'text_secondary': '#475569',
                'border': '#cbd5e1',
                'accent_primary': '#3b82f6',
                'btn_primary': '#3b82f6',
                'btn_success': '#10b981',
                'btn_warning': '#f59e0b',
                'btn_danger': '#ef4444'
            }
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default preprocessing parameters"""
        return {
            # Step 0: Masking & Clipping
            'clip_negative': True,
            'clip_aband': False,
            'clip_sky_lines': False,
            'clip_host_emission': False,
            'sky_width': 40.0,
            'custom_masks': [],
            
            # Step 1: Filtering  
            'filter_type': 'none',  # none, fixed
            'filter_window': 11,
            'filter_order': 3,
            # removed wavelength/FWHM option
            
            # Step 2: Rebinning & Scaling (always applied)
            'log_rebin': True,  # Always true - required for SNID
            'flux_scaling': True,  # Scale to mean
            
            # Step 3: Continuum
            'continuum_method': 'spline',  # only spline
            'spline_knots': 13,
            'interactive_continuum': False,
            
            # Step 4: Apodization
            'apply_apodization': True,
            'apod_percent': 10.0,
            
            # Output
            'save_intermediate': False,
            'output_format': 'ascii'
        }
    
    def setup_ui(self):
        """Setup the dialog UI with split-panel layout matching original design"""
        self.setWindowTitle("Advanced Spectrum Preprocessing - SNID SAGE")
        self.setMinimumSize(900, 500)  # Match SN Lines minimum size
        self.resize(1000, 600)  # Match SN Lines default size
        self.setModal(True)
        
        # Apply theme manager styles and add minimal custom styling for reduced font sizes
        from snid_sage.interfaces.gui.utils.pyside6_theme_manager import apply_theme_to_widget
        apply_theme_to_widget(self)
        
        # Add minimal custom styling for reduced font sizes in left panel only
        self.setStyleSheet(self.styleSheet() + f"""
            /* Override font sizes for compact left panel */
            QGroupBox {{
                font-size: 10pt;  /* Reduced from default */
            }}
            QGroupBox::title {{
                font-size: 10pt;  /* Reduced */
            }}
            QLabel {{
                font-size: 9pt;  /* Reduced for all labels */
            }}
            QComboBox {{
                font-size: 9pt;  /* Reduced for combo boxes */
                padding: 2px 6px;  /* Reduced padding */
            }}
            QSpinBox, QDoubleSpinBox {{
                font-size: 9pt;  /* Reduced for spin boxes */
                padding: 2px 4px;  /* Reduced padding */
            }}
            QPushButton {{
                font-size: 9pt;  /* Reduced button font */
            }}
        """)
        
        # Main layout - split panel
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create left panel (controls) and right panel (plots)
        self._create_left_panel(main_layout)
        self._create_right_panel(main_layout)
        
        _LOGGER.debug("PySide6 Advanced Preprocessing dialog created")
    
    def _create_left_panel(self, main_layout):
        """Create the left control panel with step header only"""
        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setFixedWidth(300)  # Increased slightly for wider layout
        self.left_panel.setStyleSheet(f"""
            QFrame {{
                background: {self.colors['bg_secondary']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
            }}
        """)
        
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)  # Further reduced margins
        left_layout.setSpacing(6)  # Further reduced spacing
        
        # Simple step header with progress indicator - no navigation controls
        self.step_header = QtWidgets.QLabel(f"Step {self.current_step + 1}/{self.total_steps}: {self.step_names[self.current_step]}")
        self.step_header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1e293b; margin-bottom: 8px;")  # Reduced font size
        self.step_header.setWordWrap(True)
        left_layout.addWidget(self.step_header)
        
        # Options frame (will be populated based on current step)
        self.options_frame = QtWidgets.QFrame()
        options_layout = QtWidgets.QVBoxLayout(self.options_frame)
        options_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.options_frame)
        
        # Add stretch to push control buttons to bottom
        left_layout.addStretch()
        
        # Control buttons
        self._create_buttons(left_layout)
        
        main_layout.addWidget(self.left_panel)
    
    def _create_right_panel(self, main_layout):
        """Create the right visualization panel with dual plots"""
        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setStyleSheet(f"""
            QFrame {{
                background: {self.colors['bg_secondary']};
                border: 1px solid {self.colors['border']};
                border-radius: 8px;
            }}
        """)
        
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(10)
        
        # Header
        viz_header = QtWidgets.QLabel("Live Preview")
        viz_header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #1e293b;")
        right_layout.addWidget(viz_header)
        
        # Create dual plots directly without using PySide6PlotManager
        self._create_dual_preview_plots(right_layout)
        
        main_layout.addWidget(self.right_panel)
    
    def _create_dual_preview_plots(self, parent_layout):
        """Create dual preview plots directly using PyQtGraph"""
        try:
            if not PYQTGRAPH_AVAILABLE:
                fallback_label = QtWidgets.QLabel("PyQtGraph not available\n\nInstall with: pip install pyqtgraph")
                fallback_label.setAlignment(QtCore.Qt.AlignCenter)
                fallback_label.setStyleSheet("color: #ef4444; font-size: 12pt;")
                parent_layout.addWidget(fallback_label)
                self.plot_manager = None
                return
            
            # Create container for dual plots
            plots_container = QtWidgets.QFrame()
            plots_layout = QtWidgets.QVBoxLayout(plots_container)
            plots_layout.setContentsMargins(5, 5, 5, 5)
            plots_layout.setSpacing(10)
            parent_layout.addWidget(plots_container)
            
            # Create top plot
            top_label = QtWidgets.QLabel("Current State")
            top_label.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 12pt;")
            plots_layout.addWidget(top_label)
            
            self.top_plot_widget = SimplePlotWidget()
            self.top_plot_widget.setLabel('left', 'Flux')
            self.top_plot_widget.setLabel('bottom', 'Wavelength (Å)')
            self.top_plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self._configure_plot_widget(self.top_plot_widget)
            plots_layout.addWidget(self.top_plot_widget)
            
            # Create bottom plot
            bottom_label = QtWidgets.QLabel("Preview (After Current Step)")
            bottom_label.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 12pt;")
            plots_layout.addWidget(bottom_label)
            
            self.bottom_plot_widget = SimplePlotWidget()
            self.bottom_plot_widget.setLabel('left', 'Flux')
            self.bottom_plot_widget.setLabel('bottom', 'Wavelength (Å)')
            self.bottom_plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self._configure_plot_widget(self.bottom_plot_widget)
            plots_layout.addWidget(self.bottom_plot_widget)
            
            # Create a simple plot manager object for compatibility
            class SimplePreviewPlotManager:
                def __init__(self, parent_dialog):
                    self.parent = parent_dialog
                
                def get_plot_widgets(self):
                    return (self.parent.top_plot_widget, self.parent.bottom_plot_widget)
                
                def update_standard_preview(self, *args, **kwargs):
                    return self.parent._update_standard_preview(*args, **kwargs)
                
                def update_interactive_preview(self, *args, **kwargs):
                    return self.parent._update_interactive_preview(*args, **kwargs)
            
            self.plot_manager = SimplePreviewPlotManager(self)
            
            _LOGGER.debug("Dual preview plots created successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error creating dual preview plots: {e}")
            fallback_label = QtWidgets.QLabel("Plot preview not available")
            fallback_label.setAlignment(QtCore.Qt.AlignCenter)
            fallback_label.setStyleSheet("color: #666; font-size: 12pt;")
            parent_layout.addWidget(fallback_label)
            self.plot_manager = None
    
    def _configure_plot_widget(self, plot_widget):
        """Configure a plot widget with proper theme and settings"""
        try:
            # Note: Global PyQtGraph configuration is already set at module level
            # Set background color
            plot_widget.setBackground('white')
            
            # Get plot item and configure colors
            plot_item = plot_widget.getPlotItem()
            if plot_item:
                # Set axis colors
                plot_item.getAxis('left').setPen(pg.mkPen(color='black', width=1))
                plot_item.getAxis('bottom').setPen(pg.mkPen(color='black', width=1))
                plot_item.getAxis('left').setTextPen(pg.mkPen(color='black'))
                plot_item.getAxis('bottom').setTextPen(pg.mkPen(color='black'))
                
        except Exception as e:
            _LOGGER.debug(f"Error configuring plot widget: {e}")
    
    def _update_standard_preview(self, current_wave, current_flux, preview_wave, preview_flux, mask_regions=None):
        """Update standard preview with current and preview data"""
        try:
            # Update top plot with current data
            if hasattr(self, 'top_plot_widget') and self.top_plot_widget:
                top_plot_item = self.top_plot_widget.getPlotItem()
                top_plot_item.clear()
                
                if current_wave is not None and current_flux is not None:
                    top_plot_item.plot(
                        current_wave,
                        current_flux,
                        pen=pg.mkPen(color='#3b82f6', width=2),
                        name="Current",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                
                # Show mask regions (red bands) only in step 0 (Masking step)
                if mask_regions and self.current_step == 0:
                    for start, end in mask_regions:
                        # Create red fill region
                        mask_item = pg.LinearRegionItem(
                            values=[start, end],
                            orientation='vertical',
                            brush=pg.mkBrush(255, 100, 100, 100),  # Semi-transparent red
                            pen=pg.mkPen(255, 0, 0, 150),  # Red border
                            movable=False
                        )
                        top_plot_item.addItem(mask_item)
            
            # Update bottom plot with preview data
            if hasattr(self, 'bottom_plot_widget') and self.bottom_plot_widget:
                bottom_plot_item = self.bottom_plot_widget.getPlotItem()
                bottom_plot_item.clear()
                
                if preview_wave is not None and preview_flux is not None:
                    bottom_plot_item.plot(
                        preview_wave,
                        preview_flux,
                        pen=pg.mkPen(color='#10b981', width=2),
                        name="Preview",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                
            _LOGGER.debug("Standard preview updated with dual plots")
            
        except Exception as e:
            _LOGGER.error(f"Error updating standard preview: {e}")
    
    def _update_interactive_preview(self, current_wave, current_flux, continuum_points, preview_wave, preview_flux, interactive_mode=False):
        """Update interactive preview with continuum overlay"""
        try:
            # Update top plot with current data and continuum points
            if hasattr(self, 'top_plot_widget') and self.top_plot_widget:
                top_plot_item = self.top_plot_widget.getPlotItem()
                top_plot_item.clear()
                
                if current_wave is not None and current_flux is not None:
                    top_plot_item.plot(
                        current_wave,
                        current_flux,
                        pen=pg.mkPen(color='#3b82f6', width=2),
                        name="Current",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                
                # Plot continuum points if available (line only, no symbols)
                if continuum_points:
                    x_points = [p[0] for p in continuum_points]
                    y_points = [p[1] for p in continuum_points]
                    top_plot_item.plot(
                        x_points,
                        y_points,
                        pen=pg.mkPen(color='red', width=2, style=QtCore.Qt.DashLine),
                        name="Continuum",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
            
            # Update bottom plot with preview data
            if hasattr(self, 'bottom_plot_widget') and self.bottom_plot_widget:
                bottom_plot_item = self.bottom_plot_widget.getPlotItem()
                bottom_plot_item.clear()
                
                if preview_wave is not None and preview_flux is not None:
                    bottom_plot_item.plot(
                        preview_wave,
                        preview_flux,
                        pen=pg.mkPen(color='#10b981', width=2),
                        name="Preview",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                
            _LOGGER.debug("Interactive preview updated with dual plots")
            
        except Exception as e:
            _LOGGER.error(f"Error updating interactive preview: {e}")
    
    def _create_buttons(self, layout):
        """Create action buttons in a compact layout (removed navigation buttons)"""
        button_frame = QtWidgets.QFrame()
        button_layout = QtWidgets.QVBoxLayout(button_frame)
        button_layout.setSpacing(6)  # Reduced spacing
        
        # Action buttons row - Apply and Restart
        action_layout = QtWidgets.QHBoxLayout()
        
        # Apply Step button (becomes "Finish" on final step)
        self.apply_btn = QtWidgets.QPushButton("Apply Step")
        self.apply_btn.setObjectName("apply_btn")
        self.apply_btn.clicked.connect(self.apply_current_step)
        action_layout.addWidget(self.apply_btn)
        
        # Restart button (resets workflow to Step 1)
        self.restart_btn = QtWidgets.QPushButton("Restart")
        self.restart_btn.setObjectName("restart_btn")
        self.restart_btn.clicked.connect(self.restart_to_step_one)
        action_layout.addWidget(self.restart_btn)
        
        button_layout.addLayout(action_layout)
        
        layout.addWidget(button_frame)
    
    def _initialize_components(self):
        """Initialize interactive components after UI setup"""
        if not self.preview_calculator or not self.plot_manager:
            _LOGGER.warning("Preview calculator or plot manager not available")
            return
        
        # Get plot widgets for interactive components
        top_plot, bottom_plot = self.plot_manager.get_plot_widgets()
        
        if top_plot and PYQTGRAPH_AVAILABLE:
            # Initialize masking widget with proper connection
            self.masking_widget = PySide6InteractiveMaskingWidget(top_plot, self.colors)
            self.masking_widget.set_update_callback(self._on_mask_updated)
            
            # Initialize continuum widget with proper connection
            self.continuum_widget = PySide6InteractiveContinuumWidget(
                self.preview_calculator, top_plot, self.colors
            )
            self.continuum_widget.set_update_callback(self._on_continuum_updated)
            
            _LOGGER.debug("Interactive components initialized successfully")
        else:
            _LOGGER.warning("Plot widgets not available - interactive features will be limited")
        
        # Update step display
        self._update_step_display()
        
        # Initialize cleanup tracking
        self._plot_widgets_initialized = True
        
        # Setup enhanced buttons
        self._setup_enhanced_buttons()
    
    def _setup_enhanced_buttons(self):
        """Setup enhanced button styling and animations"""
        if not ENHANCED_BUTTONS_AVAILABLE:
            _LOGGER.info("Enhanced buttons not available, using standard styling")
            return

        try:
            # Use the preprocessing dialog preset
            self.button_manager = enhance_dialog_with_preset(
                self, 'preprocessing_dialog'
            )

            _LOGGER.info("Enhanced buttons successfully applied to preprocessing dialog")
            
            # Setup masking toggle button if available
            self._setup_masking_toggle_button()
            
            # Initial button state update
            self._update_button_states()

        except Exception as e:
            _LOGGER.error(f"Failed to setup enhanced buttons: {e}")
    
    def _setup_masking_toggle_button(self):
        """Setup the interactive masking toggle button with enhanced styling"""
        if hasattr(self, 'masking_widget') and self.masking_widget and hasattr(self, 'button_manager'):
            masking_controls = self.masking_widget.controls_frame
            if masking_controls:
                # Find all buttons in the masking controls
                all_buttons = masking_controls.findChildren(QtWidgets.QPushButton)
                
                for button in all_buttons:
                    button_text = button.text()
                    
                    if "Interactive Masking" in button_text:
                        # This is the main toggle button
                        button.setObjectName("masking_toggle_btn")
                        
                        # Register with enhanced button system
                        self.button_manager.register_button(
                            button,
                            'neutral',
                            {
                                'is_toggle': True,
                                'toggle_state': False,
                                'size_class': 'normal',
                                # Use ochre/amber for both inactive and active states
                                'active_color': '#FFA600',
                                'inactive_color': '#FFA600'
                            }
                        )
                        
                        # Store reference for state updates
                        self.masking_toggle_button = button
                        
                        # Connect to masking state changes
                        if hasattr(self.masking_widget, 'masking_mode_changed'):
                            self.masking_widget.masking_mode_changed.connect(self._on_masking_mode_changed)
                    
                    elif button_text == "Remove Selected":
                        # Register the Remove Selected button to prevent styling conflicts
                        button.setObjectName("masking_remove_btn")
                        self.button_manager.register_button(
                            button, 
                            'cancel',
                            {'size_class': 'normal'}
                        )
                    
                    elif button_text == "Clear All":
                        # Register the Clear All button
                        button.setObjectName("masking_clear_btn") 
                        self.button_manager.register_button(
                            button, 
                            'reset',
                            {'size_class': 'normal'}
                        )
                    
                    elif button_text == "Add":
                        # Register the Add button
                        button.setObjectName("masking_add_btn")
                        self.button_manager.register_button(
                            button, 
                            'apply',
                            {'size_class': 'normal'}
                        )
    
    def _on_masking_mode_changed(self, is_active: bool):
        """Handle masking mode state changes"""
        btn = getattr(self, 'masking_toggle_button', None)
        mgr = getattr(self, 'button_manager', None)
        if not btn or not mgr:
            return
        # Use the proper toggle button update method with robust guards
        try:
            mgr.update_toggle_button(btn, is_active)
        except (RuntimeError, AttributeError):
            # Button may have been deleted or is invalid; drop reference silently
            try:
                self.masking_toggle_button = None
            except Exception:
                pass
    
    def _on_mask_updated(self):
        """Callback when mask regions are updated"""
        _LOGGER.debug("Mask regions updated, refreshing preview")
        self._update_preview()
    
    def _on_continuum_updated(self):
        """Callback when continuum is updated"""
        _LOGGER.debug("Continuum updated, refreshing preview")
        # Add a small delay to prevent excessive updates during rapid mouse movements
        if hasattr(self, '_continuum_update_timer'):
            self._continuum_update_timer.stop()
        
        self._continuum_update_timer = QtCore.QTimer()
        self._continuum_update_timer.setSingleShot(True)
        self._continuum_update_timer.timeout.connect(self._update_preview)
        self._continuum_update_timer.start(16)  # ~60 FPS update rate
    
    def _update_step_display(self):
        """Update the UI to show options for the current step"""
        if not self.options_frame:
            return
        # Guard: suppress preview updates during rebuild to avoid C++ deleted object errors
        self._rebuilding_options = True
        
        # Ensure interactive continuum mode is disabled when leaving step 3
        if self.current_step != 3 and self.continuum_widget:
            if self.continuum_widget.is_interactive_mode():
                self.continuum_widget.disable_interactive_mode()
        
        # Clear current options
        layout = self.options_frame.layout()
        if layout:
            # Before deleting child widgets, ensure interactive widgets drop references
            try:
                if self.masking_widget and hasattr(self.masking_widget, 'release_ui_references'):
                    self.masking_widget.release_ui_references()
            except Exception:
                pass
            try:
                if self.continuum_widget and hasattr(self.continuum_widget, 'release_ui_references'):
                    self.continuum_widget.release_ui_references()  # type: ignore[attr-defined]
            except Exception:
                pass
            # Also drop our cached per-step control references now
            if hasattr(self, 'masking_toggle_button'):
                self.masking_toggle_button = None
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            layout = QtWidgets.QVBoxLayout(self.options_frame)
        
        # Create options for current step via modular step handlers
        try:
            if self.current_step == 0:
                create_step0_options(self, layout)
            elif self.current_step == 1:
                create_step1_options(self, layout)
            elif self.current_step == 2:
                create_step2_options(self, layout)
            elif self.current_step == 3:
                create_step3_options(self, layout)
            elif self.current_step == 4:
                create_step4_options(self, layout)
            elif self.current_step == 5:
                create_step5_options(self, layout)
        except Exception as e:
            _LOGGER.error(f"Failed to build options for step {self.current_step}: {e}")
        
        # Update button states
        self._update_button_states()
        
        # Update step header with progress indicator
        if hasattr(self, 'step_header'):
            self.step_header.setText(f"Step {self.current_step + 1}/{self.total_steps}: {self.step_names[self.current_step]}")
        # Done rebuilding; now allow preview updates and force one now
        self._rebuilding_options = False
        try:
            self._update_preview()
        except Exception:
            pass
        # Ensure plots are centered when a new step page opens
        try:
            self._trigger_auto_rescale()
        except Exception:
            pass
    
    # Step-0 UI handled in steps.step0_masking
    
    # Step-1 UI handled in steps.step1_filtering
    
    # Step-1 filter type change handled in steps.step1_filtering

    # Step-1 enable/disable handled in steps.step1_filtering

    # Step-1 params change handled in steps.step1_filtering

    # (Removed wavelength-based filter handler)
    
    # Step-2 UI handled in steps.step2_rebinning
    
    # Step-2 flux scaling change handled in steps.step2_rebinning

    # Step-0 aband toggled handled in steps.step0_masking

    # Step-0 sky toggled handled in steps.step0_masking

    # Step-0 sky width change handled in steps.step0_masking

    # Step-4 apodize toggle handled in steps.step4_apodization

    # Step-4 apod percent change handled in steps.step4_apodization
    
    # Step-3 spline knots change handled in steps.step3_continuum
    
    # Gaussian option removed; spline is the only automatic method
    
    # Step-3 UI handled in steps.step3_continuum
    

    
    # Step-3 initialization handled in steps.step3_continuum
    
    # Step-3 continuum points update handled in steps.step3_continuum
    
    # Step-4 UI handled in steps.step4_apodization
    
    # Step-5 UI handled in steps.step5_review
    
    # Note: Previous/Next navigation methods removed - steps only advance via Apply button
    
    def apply_current_step(self):
        """Apply the current step's configuration exactly like original"""
        if not self.preview_calculator:
            return
        
        try:
            # CRITICAL FIX: Cache current step to avoid accessing potentially deleted widgets
            step_to_apply = self.current_step
            _LOGGER.debug(f"Applying step {step_to_apply}")
            
            # Apply the step processing via modular handlers
            if step_to_apply == 0:
                apply_step0(self)
            elif step_to_apply == 1:
                apply_step1(self)
            elif step_to_apply == 2:
                apply_step2(self)
            elif step_to_apply == 3:
                apply_step3(self)
            elif step_to_apply == 4:
                apply_step4(self)
            
            # Immediately refresh plots to show the newly applied state in BOTH plots
            try:
                self._refresh_plots_with_current_state()
            except RuntimeError as e:
                if "Internal C++ object" in str(e):
                    _LOGGER.warning(f"Widget deletion during preview update: {e}")
                    # Try to continue without preview update
                else:
                    raise
            
            # Update button states to enable/disable restart button - wrapped in try-catch
            try:
                self._update_button_states()
            except RuntimeError as e:
                if "Internal C++ object" in str(e):
                    _LOGGER.warning(f"Widget deletion during button state update: {e}")
                    # Try to continue without button state update
                else:
                    raise
            
            # Auto-advance to next step only if not on final step
            # (Final step button becomes "Finish" and doesn't auto-advance)
            if step_to_apply < self.total_steps - 1:  # Not on final step (step 5)
                # Stop any active masking mode before moving to next step
                if hasattr(self, 'masking_widget') and self.masking_widget:
                    try:
                        self.masking_widget.stop_masking_mode()
                    except RuntimeError as e:
                        if "Internal C++ object" in str(e):
                            _LOGGER.warning(f"Widget deletion during masking stop: {e}")
                        else:
                            raise
                
                self.current_step += 1
                
        # Update step display - wrapped in try-catch for button deletion issues
                try:
                    self._update_step_display()
                except RuntimeError as e:
                    if "Internal C++ object" in str(e):
                        _LOGGER.warning(f"Widget deletion during step display update: {e}")
                        # Try to continue without step display update
                    else:
                        raise
                
                # After moving to next step, keep plots showing the applied state
                # so the user clearly sees the result of the action
                try:
                    self._refresh_plots_with_current_state()
                    # Also trigger a preview recomputation for the new step so bottom plot reflects it
                    self._update_preview()
                except RuntimeError as e:
                    if "Internal C++ object" in str(e):
                        _LOGGER.warning(f"Widget deletion during final refresh: {e}")
                    else:
                        raise
                # After moving to next step, autoscale both plots to keep spectra centered
                try:
                    self._trigger_auto_rescale()
                except Exception:
                    pass
            
        except RuntimeError as e:
            if "Internal C++ object" in str(e):
                _LOGGER.error(f"C++ object deletion error in step {self.current_step}: {e}")
                QtWidgets.QMessageBox.warning(self, "Widget Error", 
                    "A widget was unexpectedly deleted. The operation may have partially completed. Please try again.")
            else:
                _LOGGER.error(f"Runtime error applying step {self.current_step}: {e}")
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to apply step: {str(e)}")
        except Exception as e:
            _LOGGER.error(f"Error applying step {self.current_step}: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to apply step: {str(e)}")

    def _refresh_plots_with_current_state(self):
        """Force-refresh both plots so top plot shows the applied step and bottom plot shows next step preview."""
        if not self.preview_calculator or not self.plot_manager:
            return
        try:
            current_wave, current_flux = self.preview_calculator.get_current_state()
            _LOGGER.info(f"_refresh_plots_with_current_state: Got {len(current_flux)} points from get_current_state()")
            # Apply zero padding removal consistently on both
            current_wave, current_flux = self._apply_zero_padding_removal(current_wave, current_flux)
            
            # Calculate preview for the current step (what would happen if we apply it)
            preview_wave, preview_flux = self._calculate_current_step_preview()
            preview_wave, preview_flux = self._apply_zero_padding_removal(preview_wave, preview_flux)
            
            # Mask regions only relevant on masking step
            mask_regions = []
            if self.current_step == 0 and self.masking_widget:
                try:
                    mask_regions = self.masking_widget.get_mask_regions()
                except Exception:
                    mask_regions = []
            # Update with current state in top plot and preview in bottom plot
            self.plot_manager.update_standard_preview(
                current_wave, current_flux, preview_wave, preview_flux, mask_regions
            )
        except Exception as e:
            _LOGGER.debug(f"Error during immediate plot refresh: {e}")
    
    def restart_to_step_one(self):
        """Restart the advanced preprocessing workflow back to Step 1 (initial state)."""
        if not self.preview_calculator:
            return
        try:
            # Reset calculator state completely
            self.preview_calculator.reset()
            
            # Reset UI workflow to first step
            self.current_step = 0
            
            # Ensure interactive widgets are reset
            if self.continuum_widget and self.continuum_widget.is_interactive_mode():
                try:
                    self.continuum_widget.disable_interactive_mode()
                except Exception:
                    pass
            # Reset masking widget state and visuals like fresh start
            if hasattr(self, 'masking_widget') and self.masking_widget:
                try:
                    if getattr(self.masking_widget, 'masking_active', False):
                        self.masking_widget.stop_masking_mode()
                    self.masking_widget.clear_all_masks()
                except Exception:
                    pass
            
            # Update UI and preview
            self._update_step_display()
            self._update_preview()
            # Recenter plots after restart
            try:
                self._trigger_auto_rescale()
            except Exception:
                pass
            
            _LOGGER.info("Advanced preprocessing restarted to Step 1 (initial state)")
        except Exception as e:
            _LOGGER.error(f"Failed to restart preprocessing: {e}")
            QtWidgets.QMessageBox.warning(self, "Restart Failed", "Could not restart preprocessing. Please try again.")
    
    def finish_preprocessing(self):
        """Finish preprocessing and return results exactly like original"""
        if self.preview_calculator:
            # Get final processed spectrum directly from preview calculator
            final_wave, final_flux = self.preview_calculator.get_current_state()
            

            
            # CRITICAL FIX: Get the continuum from the step history instead of stored_continuum
            # which seems to get corrupted during GUI interactions
            continuum = None
            applied_steps = self.preview_calculator.applied_steps
            
            # Look for the continuum step in applied steps and extract the continuum
            for step in applied_steps:
                if step['type'] == 'continuum_fit':
                    # Re-run the continuum fitting to get the correct continuum
                    try:
                        method = step['kwargs'].get('method', 'spline')
                        if method == 'spline':
                            knotnum = step['kwargs'].get('knotnum', 13)

                            
                            # Get the state before continuum fitting
                            # This requires reconstructing the flux before continuum removal
                            log_rebin_step_idx = None
                            for i, s in enumerate(applied_steps):
                                if s['type'] == 'log_rebin_with_scaling':
                                    log_rebin_step_idx = i
                                    break
                            
                            if log_rebin_step_idx is not None:
                                # Get flux state right after log rebinning (before continuum fitting)
                                # We need to reconstruct this from the current flat flux
                                from snid_sage.snid.preprocessing import fit_continuum
                                
                                # The final_flux is the continuum-removed version
                                # We need to get the flux before continuum removal
                                # Let's recompute the continuum using the same logic as original
                                
                                # Find the flux before continuum step by re-running preprocessing up to that point
                                temp_calc = type(self.preview_calculator)(self.original_wave, self.original_flux)
                                
                                # Replay steps up to (but not including) continuum fitting
                                for i, step in enumerate(applied_steps):
                                    if step['type'] == 'continuum_fit':
                                        break
                                    step_kwargs = step['kwargs'].copy()
                                    step_kwargs.pop('step_index', None)  # Remove step_index if present
                                    temp_calc.apply_step(step['type'], **step_kwargs)
                                
                                # Now get the flux before continuum removal
                                _, flux_before_continuum = temp_calc.get_current_state()
                                
                                # Fit continuum to this flux
                                flat_flux, continuum = fit_continuum(flux_before_continuum, method=method, knotnum=knotnum)

                                break
                        # Gaussian method removed; only spline and interactive are supported
                                
                    except Exception as e:

                        continuum = None
                        break
                        
                elif step['type'] == 'interactive_continuum':
                    # Handle manual continuum editing
                    try:

                        # Get the manual continuum from the step
                        manual_continuum = step['kwargs'].get('manual_continuum', None)
                        if manual_continuum is not None:
                            continuum = manual_continuum.copy()

                            break
                        else:
                            # Try to get it from the continuum widget
                            if self.continuum_widget and hasattr(self.continuum_widget, 'get_manual_continuum_array'):
                                _, manual_continuum = self.continuum_widget.get_manual_continuum_array()
                                if len(manual_continuum) > 0:
                                    continuum = manual_continuum.copy()

                                    break
                    except Exception as e:

                        continuum = None
                        break
            
            # Fallback to stored continuum if recomputation failed
            if continuum is None:
                continuum_wave, stored_continuum = self.preview_calculator.get_continuum_from_fit()
                continuum = stored_continuum

            

            
            # Get edge information from preview calculator (properly tracked through steps)
            left_edge, right_edge = self.preview_calculator.get_current_edges()
            
            # Fallback to calculation if edges weren't tracked properly
            if left_edge is None or right_edge is None:
                # For continuum-subtracted spectra, negative values are valid
                valid_mask = (final_flux != 0) & np.isfinite(final_flux)
                if np.any(valid_mask):
                    left_edge = np.argmax(valid_mask)
                    right_edge = len(final_flux) - 1 - np.argmax(valid_mask[::-1])
                else:
                    left_edge = 0
                    right_edge = len(final_flux) - 1

            
            # Determine what the final_flux actually represents based on the applied steps
            has_continuum_step = any(step['type'] in ['continuum_fit', 'interactive_continuum'] 
                                   for step in applied_steps)
            # Also trust the calculator flag if available
            try:
                if hasattr(self.preview_calculator, 'has_continuum') and self.preview_calculator.has_continuum:
                    has_continuum_step = True
            except Exception:
                pass
            

            
            # Preserve flux just before continuum removal for correct Flux view
            # Recompute it once here by replaying until the continuum step
            flux_before_continuum_cache = None
            try:
                temp_calc = type(self.preview_calculator)(self.original_wave, self.original_flux)
                for i, s in enumerate(applied_steps):
                    if s['type'] == 'continuum_fit':
                        break
                    step_kwargs = s['kwargs'].copy()
                    step_kwargs.pop('step_index', None)
                    temp_calc.apply_step(s['type'], **step_kwargs)
                _, flux_before_continuum_cache = temp_calc.get_current_state()
            except Exception:
                flux_before_continuum_cache = None

            if has_continuum_step and continuum is not None:
                # final_flux is the flattened (continuum-removed) spectrum after continuum step
                flat_spectrum = final_flux.copy()  # This is already flat (continuum-removed)
                
                # For Gaussian method, the stored continuum may be zeroed outside the valid range.
                # Reconstruct a non-zeroed continuum for display by extending edge values.
                recon_continuum = continuum.copy()
                try:
                    nz = np.nonzero(recon_continuum > 0)[0]
                    if nz.size:
                        c0, c1 = nz[0], nz[-1]
                        # Extend to edges with edge values
                        if c0 > 0:
                            recon_continuum[:c0] = recon_continuum[c0]
                        if c1 < len(recon_continuum) - 1:
                            recon_continuum[c1+1:] = recon_continuum[c1]
                except Exception:
                    # Fallback: use original continuum array
                    recon_continuum = continuum
                
                # Generate display versions using the correct logic
                # display_flux: Reconstruct flux using (flat + 1) * (non-zeroed) continuum
                display_flux = (flat_spectrum + 1.0) * recon_continuum
                display_flat = flat_spectrum  # Already flattened
                
                # For log_flux, use the flux before continuum removal (rebinned & scaled)
                # This is the natural flux to show in Flux view
                if flux_before_continuum_cache is not None:
                    log_flux = flux_before_continuum_cache.copy()
                else:
                    log_flux = display_flux.copy()
                
            else:
                # No continuum step applied - final_flux represents the scaled flux after log rebinning
                # This happens when only log rebinning + scaling steps are applied
                log_flux = final_flux.copy()  # This is the scaled flux on log grid
                flat_spectrum = np.zeros_like(final_flux)  # No actual flattening occurred
                continuum = np.ones_like(final_flux)  # Unity continuum (no continuum removal)
                
                # For display versions when no continuum removal
                display_flux = final_flux.copy()  # Scaled flux
                display_flat = final_flux.copy()  # Same data (no actual flattening occurred)
            

            
        # Determine if apodization was already applied and which percent to use
        apodize_already_applied = any(s.get('type') == 'apodization' for s in applied_steps)
        # Use user-selected percent if available in UI; else check applied step; else default 10
        selected_percent = None
        try:
            if hasattr(self, 'apod_percent_spin') and self.apod_percent_spin is not None:
                selected_percent = float(self.apod_percent_spin.value())
        except Exception:
            selected_percent = None
        if selected_percent is None:
            try:
                for s in applied_steps:
                    if s.get('type') == 'apodization':
                        selected_percent = float(s.get('kwargs', {}).get('percent', 10.0))
                        break
            except Exception:
                selected_percent = None
        if selected_percent is None:
            selected_percent = 10.0

        # Compute tapered_flux only if not already applied; otherwise keep flat_spectrum as-is
        if not apodize_already_applied:
            nz = np.nonzero(flat_spectrum)[0]
            if nz.size:
                l1, l2 = int(nz[0]), int(nz[-1])
            else:
                l1, l2 = 0, len(flat_spectrum) - 1
            tapered_flux = apodize(flat_spectrum, l1, l2, percent=selected_percent)
        else:
            tapered_flux = flat_spectrum.copy()

        # Always define flat and flux view consistently regardless of continuum method
        display_flat = tapered_flux  # apodized flat
        # Reconstruct flux from apodized flat; if no continuum (no continuum step), use unity continuum
        recon_for_display = recon_continuum if (has_continuum_step and continuum is not None) else np.ones_like(tapered_flux)
        display_flux = (tapered_flux + 1.0) * recon_for_display

        # Create processed spectrum dictionary like old GUI with proper display versions
        # Ensure continuum stored is the extended, strictly-positive version used for reconstruction
        try:
            import numpy as _np
            safe_continuum = _np.asarray(recon_continuum if (has_continuum_step and continuum is not None) else continuum, dtype=float).copy()
            # Clip to small positive to avoid negative or zero continuum due to numeric issues
            safe_continuum = _np.where(_np.isfinite(safe_continuum), safe_continuum, 0.0)
            safe_continuum[safe_continuum <= 0] = 1e-12
        except Exception:
            safe_continuum = recon_continuum if (has_continuum_step and continuum is not None) else continuum

        # Read real grid parameters instead of hard-coding
        try:
            NW_grid, W0, W1, DWLOG_grid = get_grid_params() if SNID_AVAILABLE else (1024, 2500.0, 10000.0, np.log(10000.0/2500.0)/1024)
        except Exception:
            NW_grid, W0, W1, DWLOG_grid = (1024, 2500.0, 10000.0, np.log(10000.0/2500.0)/1024)

        processed_spectrum = {
            'log_wave': final_wave,
            'log_flux': log_flux,  # Scaled flux on log grid (or reconstructed if continuum was applied)
            'flat_flux': flat_spectrum,  # Continuum-removed version (or zeros if no continuum)
            'nonzero_mask': slice(left_edge, right_edge + 1),
            'display_flux': display_flux,
            'display_flat': display_flat,
            'flux_view': display_flux,
            'flat_view': display_flat,
            'advanced_preprocessing': True,
            'preprocessing_type': 'advanced',
            'left_edge': left_edge,
            'right_edge': right_edge,
            'input_spectrum': {'wave': self.original_wave, 'flux': self.original_flux},
            'grid_params': {
                'NW': NW_grid,
                'W0': W0,
                'W1': W1,
                'DWLOG': DWLOG_grid
            },
            'has_continuum': bool(has_continuum_step and continuum is not None)
        }
        # Only include continuum-dependent keys when continuum fitting actually occurred
        if bool(has_continuum_step and continuum is not None):
            processed_spectrum['tapered_flux'] = tapered_flux
            processed_spectrum['continuum'] = safe_continuum
            
        # Store in parent GUI's app controller
        if hasattr(self.parent(), 'app_controller'):
            self.parent().app_controller.set_processed_spectrum(processed_spectrum)
            _LOGGER.info("Processed spectrum stored in app controller")
        
        # Build a minimal result payload for GUI controller
        flux_view = None
        flat_view = None
        try:
            # Prefer proper flux/flat if continuum was applied
            if hasattr(self.preview_calculator, 'has_continuum') and self.preview_calculator.has_continuum:
                # Use final flattened spectrum as flat view
                flat_view = final_flux.copy()
                # Reconstruct flux from continuum if available
                _, cont = self.preview_calculator.get_continuum_from_fit()
                cont = np.asarray(cont, dtype=float)
                if cont.shape == flat_view.shape and np.any(cont > 0):
                    flux_view = (flat_view + 1.0) * cont
                else:
                    flux_view = flat_view.copy()
            else:
                # No continuum removal: flux and flat are the same
                flux_view = final_flux.copy()
                flat_view = np.zeros_like(final_flux)
        except Exception:
            flux_view = final_flux.copy()
            flat_view = final_flux.copy()

        # Pass both views forward; controller will select the right one
        self.result = {
            'processed_wave': final_wave,
            'processed_flux': final_flux,
            'flux_view': flux_view,
            'flat_view': flat_view,
            'success': True
        }
        
        self.accept()
    
    # Step application methods matching original exactly
    # Step-0 application handled in steps.step0_masking
    
    # Step-1 application handled in steps.step1_filtering
    
    def _apply_step_2(self):
        """Apply log-wavelength rebinning and flux scaling exactly like original"""
        # Log rebinning is always applied (required for SNID)
        # CRITICAL FIX: Cache widget values safely to avoid accessing deleted C++ objects
        scale_flux = True  # default fallback
        
        if hasattr(self, 'flux_scaling_cb') and self.flux_scaling_cb is not None:
            try:
                scale_flux = self.flux_scaling_cb.isChecked()
            except RuntimeError as e:
                _LOGGER.warning(f"Widget access error for flux_scaling_cb: {e}, using default value {scale_flux}")
        
        self.preview_calculator.apply_step("log_rebin_with_scaling", scale_to_mean=scale_flux, step_index=2)
    
    def _apply_step_3(self):
        """Apply continuum fitting exactly like original"""
        # Check if interactive continuum editing is active
        if self.continuum_widget and self.continuum_widget.is_interactive_mode():
            # Apply interactive continuum
            wave_grid, manual_continuum = self.continuum_widget.get_manual_continuum_array()
            if len(manual_continuum) > 0:
                self.preview_calculator.apply_step("interactive_continuum", 
                                                 manual_continuum=manual_continuum,
                                                 wave_grid=wave_grid, step_index=3)
        else:
            # Apply automatic continuum fitting
            method = self.processing_params['continuum_method']
            
            if method == 'spline':
                # CRITICAL FIX: Cache widget values safely to avoid accessing deleted C++ objects
                knotnum = 13  # default fallback
                
                if hasattr(self, 'spline_knots_spin') and self.spline_knots_spin is not None:
                    try:
                        knotnum = self.spline_knots_spin.value()
                    except RuntimeError as e:
                        _LOGGER.warning(f"Widget access error for spline_knots_spin: {e}, using default value {knotnum}")
                
                self.preview_calculator.apply_step("continuum_fit", method="spline", 
                                                 knotnum=knotnum, step_index=3)
    
    def _apply_step_4(self):
        """Apply apodization exactly like original"""
        # CRITICAL FIX: Cache widget values safely to avoid accessing deleted C++ objects
        apply_apodization = False  # default fallback
        percent = 10.0  # default fallback
        
        if hasattr(self, 'apodize_cb') and self.apodize_cb is not None:
            try:
                apply_apodization = self.apodize_cb.isChecked()
            except RuntimeError as e:
                _LOGGER.warning(f"Widget access error for apodize_cb: {e}, using default value {apply_apodization}")
        
        if apply_apodization:
            if hasattr(self, 'apod_percent_spin') and self.apod_percent_spin is not None:
                try:
                    percent = self.apod_percent_spin.value()
                except RuntimeError as e:
                    _LOGGER.warning(f"Widget access error for apod_percent_spin: {e}, using default value {percent}")
            
            self.preview_calculator.apply_step("apodization", percent=percent, step_index=4)
    
    # UI update methods
    def _update_button_states(self):
        """Update button states and text based on current step"""
        # Update Apply button text for final step
        if hasattr(self, 'apply_btn'):
            if self.current_step == self.total_steps - 1:  # Final step (Review)
                self.apply_btn.setText("Finish")
                # Disconnect and reconnect signals properly
                try:
                    self.apply_btn.clicked.disconnect()
                except:
                    pass  # Ignore if no connections exist
                self.apply_btn.clicked.connect(self.finish_preprocessing)
                # Update styling for finish button - enhanced buttons will handle styling
            else:
                self.apply_btn.setText("Apply Step")
                # Disconnect and reconnect signals properly
                try:
                    self.apply_btn.clicked.disconnect()
                except:
                    pass  # Ignore if no connections exist
                self.apply_btn.clicked.connect(self.apply_current_step)
                # Restore normal apply button styling - enhanced buttons will handle styling
        
        # Restart button is enabled when any step beyond the first is active or any steps were applied
        if hasattr(self, 'restart_btn'):
            can_restart = False
            if hasattr(self, 'preview_calculator') and self.preview_calculator:
                try:
                    can_restart = (self.current_step > 0) or (len(getattr(self.preview_calculator, 'applied_steps', [])) > 0)
                except Exception:
                    can_restart = self.current_step > 0
            # Use enhanced button state management if available
            if hasattr(self, 'button_manager') and self.button_manager:
                self.button_manager.update_button_state(self.restart_btn, can_restart)
            else:
                self.restart_btn.setEnabled(can_restart)
    
    def _update_preview(self):
        """Update the plot preview with dual plots"""
        if not self.preview_calculator or not self.plot_manager:
            return
        # Skip updates while rebuilding option widgets to avoid deleted object access
        if getattr(self, '_rebuilding_options', False):
            return
        
        try:
            # Get current state (what's already applied)
            current_wave, current_flux = self.preview_calculator.get_current_state()
            
            # For continuum step, show interactive preview ONLY if we're on step 3 AND continuum hasn't been applied yet
            if self.current_step == 3 and self.continuum_widget and not self._is_continuum_step_applied():
                # Check if we have continuum data to show
                continuum_points = self.continuum_widget.get_continuum_points()
                if continuum_points:
                    # CRITICAL FIX: Get preview data using the current manual continuum
                    # This ensures real-time updates during dragging
                    if self.continuum_widget.is_interactive_mode():
                        # Use the manual continuum for real-time preview during interactive editing
                        wave_grid, manual_continuum = self.continuum_widget.get_manual_continuum_array()
                        if len(manual_continuum) > 0:
                            preview_wave, preview_flux = self.preview_calculator._calculate_manual_continuum_preview(manual_continuum)
                        else:
                            preview_wave, preview_flux = self.continuum_widget.get_preview_data()
                    else:
                        preview_wave, preview_flux = self.continuum_widget.get_preview_data()
                    
                    # Apply zero padding removal for clean spectrum display
                    preview_wave, preview_flux = self._apply_zero_padding_removal(preview_wave, preview_flux)
                    # FIXED: Also apply zero padding removal to current state (top plot)
                    current_wave, current_flux = self._apply_zero_padding_removal(current_wave, current_flux)
                    
                    interactive_mode = self.continuum_widget.is_interactive_mode()
                    
                    self.plot_manager.update_interactive_preview(
                        current_wave, current_flux, continuum_points, 
                        preview_wave, preview_flux, interactive_mode
                    )
                    return
            
            # Standard preview update: current state vs preview of current step
            # Calculate preview for the current step (what would happen if we apply it)
            preview_wave, preview_flux = self._calculate_current_step_preview()
            
            # Apply zero padding removal for ALL steps to ensure clean spectrum display
            preview_wave, preview_flux = self._apply_zero_padding_removal(preview_wave, preview_flux)
            # FIXED: Also apply zero padding removal to current state (top plot) for ALL steps
            current_wave, current_flux = self._apply_zero_padding_removal(current_wave, current_flux)
            
            # Get mask regions for visualization - ONLY in step 0
            mask_regions = []
            if self.current_step == 0 and self.masking_widget:
                mask_regions = self.masking_widget.get_mask_regions()
            
            # Show current state in top plot, preview in bottom plot
            self.plot_manager.update_standard_preview(
                current_wave, current_flux, preview_wave, preview_flux, mask_regions
            )
            # If we're in masking step or step 3/6 (log rebin & scaling),
            # rescale the bottom plot to the preview's range
            if self.current_step in (0, 2):
                try:
                    QtCore.QTimer.singleShot(10, self._auto_rescale_bottom_plot_y)
                except Exception:
                    try:
                        self._auto_rescale_bottom_plot_y()
                    except Exception:
                        pass
            
        except Exception as e:
            _LOGGER.error(f"Error updating preview: {e}")

    def _auto_rescale_bottom_plot_y(self):
        """Auto-rescale the Y-axis of the bottom preview plot (masking step focus)."""
        try:
            if not hasattr(self, 'bottom_plot_widget') or not self.bottom_plot_widget:
                return
            plot_item = self.bottom_plot_widget.getPlotItem()
            if not plot_item:
                return
            try:
                plot_item.enableAutoRange(axis='y', enable=True)
            except Exception:
                pass
            try:
                vb = plot_item.getViewBox()
                if vb:
                    vb.autoRange()
                else:
                    plot_item.autoRange()
            except Exception:
                pass
        except Exception:
            pass
    
    def _apply_zero_padding_removal(self, wave, flux):
        """Apply zero padding removal like the main GUI"""
        try:
            if wave is None or flux is None:
                _LOGGER.debug("Zero padding removal: wave or flux is None")
                return wave, flux
                
            # Find valid regions manually (including negative values for continuum-subtracted spectra)
            valid_mask = (flux != 0) & np.isfinite(flux)
            if np.any(valid_mask):
                left_edge = np.argmax(valid_mask)
                right_edge = len(flux) - 1 - np.argmax(valid_mask[::-1])
                filtered_wave = wave[left_edge:right_edge+1]
                filtered_flux = flux[left_edge:right_edge+1]
                _LOGGER.debug(f"Zero padding removal: {len(wave)} -> {len(filtered_wave)} points (removed {len(wave) - len(filtered_wave)} points)")
                return filtered_wave, filtered_flux
            
            # If no nonzero data found, return original arrays
            _LOGGER.debug("Zero padding removal: no nonzero data found")
            return wave, flux
            
        except Exception as e:
            _LOGGER.warning(f"Error applying zero padding removal: {e}")
            return wave, flux
    
    def _calculate_current_step_preview(self):
        """Calculate preview for current step using PreviewCalculator exactly like original"""
        # Delegate to modular calculators
        if self.current_step == 0:
            return calculate_step0_preview(self)
        elif self.current_step == 1:
            return calculate_step1_preview(self)
        elif self.current_step == 2:
            return calculate_step2_preview(self)
        elif self.current_step == 3:
            return calculate_step3_preview(self)
        elif self.current_step == 4:
            return calculate_step4_preview(self)
        return self.preview_calculator.get_current_state()
    
    def _is_continuum_step_applied(self):
        """Check if the continuum step has been applied"""
        if not self.preview_calculator:
            return False
        
        # Check if any continuum-related steps have been applied
        for step in self.preview_calculator.applied_steps:
            step_type = step.get('type', '')
            if step_type in ['continuum_fit', 'interactive_continuum']:
                return True
        return False
    
    # Step-5 summary handled in steps.step5_review
    
    # Export functionality removed
    
    def _cleanup_resources(self):
        """Clean up PyQtGraph widgets and interactive components"""
        try:
            _LOGGER.debug("Cleaning up preprocessing dialog resources...")
            
            # Clean up interactive widgets
            if hasattr(self, 'masking_widget') and self.masking_widget:
                try:
                    # Ensure masking mode is stopped before cleanup
                    if getattr(self.masking_widget, 'masking_active', False):
                        self.masking_widget.stop_masking_mode()
                    if hasattr(self.masking_widget, 'cleanup'):
                        self.masking_widget.cleanup()
                    self.masking_widget = None
                except Exception as e:
                    _LOGGER.debug(f"Error cleaning up masking widget: {e}")
            
            if hasattr(self, 'continuum_widget') and self.continuum_widget:
                try:
                    # Ensure interactive mode is disabled before cleanup
                    if hasattr(self.continuum_widget, 'is_interactive_mode') and self.continuum_widget.is_interactive_mode():
                        self.continuum_widget.disable_interactive_mode()
                    if hasattr(self.continuum_widget, 'cleanup'):
                        self.continuum_widget.cleanup()
                    self.continuum_widget = None
                except Exception as e:
                    _LOGGER.debug(f"Error cleaning up continuum widget: {e}")
            
            # Clean up PyQtGraph plot widgets
            if hasattr(self, 'top_plot_widget') and self.top_plot_widget:
                try:
                    self.top_plot_widget.clear()
                    # Force close any OpenGL contexts
                    if hasattr(self.top_plot_widget, 'close'):
                        self.top_plot_widget.close()
                    self.top_plot_widget = None
                except Exception as e:
                    _LOGGER.debug(f"Error cleaning up top plot widget: {e}")
            
            if hasattr(self, 'bottom_plot_widget') and self.bottom_plot_widget:
                try:
                    self.bottom_plot_widget.clear()
                    # Force close any OpenGL contexts
                    if hasattr(self.bottom_plot_widget, 'close'):
                        self.bottom_plot_widget.close()
                    self.bottom_plot_widget = None
                except Exception as e:
                    _LOGGER.debug(f"Error cleaning up bottom plot widget: {e}")
            
            # Clean up preview calculator
            if hasattr(self, 'preview_calculator') and self.preview_calculator:
                try:
                    # No explicit signal disconnection needed; ensure object is dereferenced
                    self.preview_calculator = None
                except Exception as e:
                    _LOGGER.debug(f"Error cleaning up preview calculator: {e}")
            
            # Clean up plot manager
            if hasattr(self, 'plot_manager') and self.plot_manager:
                try:
                    if hasattr(self.plot_manager, 'cleanup'):
                        self.plot_manager.cleanup()
                    self.plot_manager = None
                except Exception as e:
                    _LOGGER.debug(f"Error cleaning up plot manager: {e}")
            
            _LOGGER.debug("Preprocessing dialog cleanup completed")
            
        except Exception as e:
            _LOGGER.debug(f"Error during preprocessing dialog cleanup: {e}")

    def _trigger_auto_rescale(self):
        """Schedule an auto-rescale of both preview plots to ensure they are centered.

        Uses a short single-shot timer so that it runs after plot data updates and
        layout changes, reducing risk of acting on deleted C++ objects.
        """
        try:
            QtCore.QTimer.singleShot(50, self._auto_rescale_both_plots)
        except Exception:
            # Fallback to immediate rescale
            try:
                self._auto_rescale_both_plots()
            except Exception:
                pass

    def _auto_rescale_both_plots(self):
        """Autoscale both the top and bottom preview plots safely."""
        try:
            for widget_name in ('top_plot_widget', 'bottom_plot_widget'):
                plot_widget = getattr(self, widget_name, None)
                if not plot_widget:
                    continue
                try:
                    plot_item = plot_widget.getPlotItem()
                    if not plot_item:
                        continue
                    # Give some padding and enable auto-range on both axes
                    try:
                        vb = plot_item.getViewBox()
                        if vb:
                            try:
                                vb.setDefaultPadding(0.08)
                            except Exception:
                                pass
                    except Exception:
                        vb = None
                    try:
                        plot_item.enableAutoRange(axis='x', enable=True)
                        plot_item.enableAutoRange(axis='y', enable=True)
                    except Exception:
                        pass
                    # Perform the auto-range operation
                    try:
                        if vb:
                            vb.autoRange()
                        else:
                            plot_item.autoRange()
                    except Exception:
                        pass
                except Exception:
                    continue
        except Exception:
            pass
    
    def closeEvent(self, event):
        """Handle dialog closing with proper cleanup"""
        try:
            _LOGGER.debug("Preprocessing dialog closing, cleaning up resources...")
            self._cleanup_resources()
            super().closeEvent(event)
        except Exception as e:
            _LOGGER.debug(f"Error during preprocessing dialog close: {e}")
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