"""
SNID SAGE - PySide6 Plot Manager
===============================

Dedicated plot manager for PySide6 GUI that handles all plotting functionality
including PyQtGraph spectrum plots, Matplotlib analysis plots, and plot mode switching.

This extracts all plotting logic from the main GUI class to keep it clean and focused.

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import os
import sys
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from enum import Enum

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

# PyQtGraph for high-performance plotting
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
    # Import enhanced and simple plot widgets
    from snid_sage.interfaces.gui.components.plots.enhanced_plot_widget import EnhancedPlotWidget, SimplePlotWidget
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None
    EnhancedPlotWidget = None
    SimplePlotWidget = None

# Matplotlib for analysis plots (unified Qt helper)
try:
    from snid_sage.interfaces.gui.utils.matplotlib_qt import get_qt_mpl
    plt, Figure, FigureCanvas, _NavigationToolbar = get_qt_mpl()
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FigureCanvas = None
    Figure = None

# Rest wavelength axis for PyQtGraph top axis
try:
    from snid_sage.interfaces.gui.utils.pyqtgraph_rest_axis import RestWavelengthAxisItem
    _REST_AXIS_AVAILABLE = True
except Exception:
    _REST_AXIS_AVAILABLE = False
    RestWavelengthAxisItem = None  # type: ignore

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_plot_manager')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_plot_manager')

# Import analysis plotter
try:
    from snid_sage.interfaces.gui.components.plots.pyside6_analysis_plotter import PySide6AnalysisPlotter
    ANALYSIS_PLOTTER_AVAILABLE = True
except ImportError:
    ANALYSIS_PLOTTER_AVAILABLE = False
    PySide6AnalysisPlotter = None


# Plot mode enumeration
class PlotMode(Enum):
    SPECTRUM = "spectrum"           # PyQtGraph spectrum/template overlays
    REDSHIFT_AGE = "redshift_age"   # Matplotlib redshift vs age plot
    SUBTYPE_PROPS = "subtype_props" # Matplotlib subtype proportions plot


class PySide6PlotManager:
    """
    Manages all plotting functionality for PySide6 GUI
    
    This class handles:
    - PyQtGraph plot initialization and management
    - Matplotlib plot initialization and management
    - Plot mode switching between spectrum and analysis plots
    - Spectrum plotting with template overlays
    - Analysis plot generation (redshift vs age, subtype proportions)
    - Interactive masking setup
    """
    
    def __init__(self, main_window, plot_layout):
        """
        Initialize the plot manager
        
        Args:
            main_window: Reference to the main PySide6 GUI window
            plot_layout: The layout where plots will be added
        """
        self.main_window = main_window
        self.plot_layout = plot_layout
        
        # Plot state
        self.current_plot_mode = PlotMode.SPECTRUM
        self.current_plot_data = None
        self.mask_regions_pg = []
        self._current_template_text_item = None  # Store current template info text item
        
        # Plot widgets and components
        self.plot_stack = None
        self.plot_widget = None
        self.plot_item = None
        self.matplotlib_widget = None
        self.matplotlib_figure = None
        self.matplotlib_canvas = None
        self.matplotlib_axes = None
        self.fallback_widget = None
        
        # Plot indices in stacked widget
        self.pyqtgraph_index = 0
        self.matplotlib_index = 1
        
        # Theme colors (will be set by main window)
        self.theme_colors = {}
        
        # Analysis plotter (will be initialized after matplotlib)
        self.analysis_plotter = None

        # Custom rest-wavelength top axis (PyQtGraph)
        self._rest_axis = None
        
        # Initialize the dual plot system
        self.init_dual_plot_system()
    
    def set_theme_colors(self, theme_colors: Dict[str, str]):
        """Set theme colors for plots"""
        self.theme_colors = theme_colors
        if self.plot_widget and self.plot_item:
            self.apply_pyqtgraph_theme()
    
    def init_dual_plot_system(self):
        """Initialize dual plot system with PyQtGraph for spectra and matplotlib for analysis plots"""
        try:
            # Create a stacked widget to hold different plot types
            self.plot_stack = QtWidgets.QStackedWidget()
            
            # Initialize PyQtGraph plot for spectrum/template overlays
            if PYQTGRAPH_AVAILABLE:
                self.init_pyqtgraph_plot()
                self.plot_stack.addWidget(self.plot_widget)  # Index 0
                self.pyqtgraph_index = 0
            else:
                self.init_fallback_plot()
                self.plot_stack.addWidget(self.fallback_widget)
                self.pyqtgraph_index = 0
            
            # Initialize matplotlib plots for analysis
            if MATPLOTLIB_AVAILABLE:
                self.init_matplotlib_plots()
                self.plot_stack.addWidget(self.matplotlib_widget)  # Index 1
                self.matplotlib_index = 1
            else:
                # Add placeholder for matplotlib if not available
                matplotlib_fallback = QtWidgets.QLabel(
                    "Matplotlib not available\n\nInstall matplotlib for analysis plots:\npip install matplotlib"
                )
                matplotlib_fallback.setAlignment(QtCore.Qt.AlignCenter)
                matplotlib_fallback.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 12pt;")
                self.plot_stack.addWidget(matplotlib_fallback)
                self.matplotlib_index = 1
            
            # Add the stacked widget to the plot layout if it's a valid layout
            if self.plot_layout and hasattr(self.plot_layout, 'addWidget'):
                self.plot_layout.addWidget(self.plot_stack)
            elif self.plot_layout:
                _LOGGER.warning(f"plot_layout is not a valid layout object: {type(self.plot_layout)}")
            
            # Start with spectrum plot mode
            self.switch_to_plot_mode(PlotMode.SPECTRUM)
            
            _LOGGER.debug("Dual plot system initialized successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing dual plot system: {e}")
            self.init_fallback_plot()
    
    def init_pyqtgraph_plot(self):
        """Initialize PyQtGraph plot for better performance and Qt integration"""
        try:
            # Configure PyQtGraph for complete software rendering (WSL compatibility)
            _LOGGER.debug("🔧 Configuring PyQtGraph for software rendering...")
            pg.setConfigOptions(
                antialias=True, 
                useOpenGL=False,  # Disable OpenGL completely
                enableExperimental=False,  # Disable experimental features that might use hardware acceleration
                background='w',  # White background
                foreground='k',   # Black foreground
                exitCleanup=True,  # Clean exit
                crashWarning=False  # Reduce warnings
            )
            _LOGGER.debug("✅ PyQtGraph configured for software rendering")
            
            # Create enhanced plot widget with save functionality and disabled context menus
            self.plot_widget = EnhancedPlotWidget()
            try:
                # Hook drag-and-drop of files on the plot to main window handler
                if hasattr(self.plot_widget, 'files_dropped'):
                    self.plot_widget.files_dropped.connect(self._on_files_dropped)
            except Exception:
                pass
            
            # Force software rendering at widget level (WSL compatibility)
            try:
                # Try to set software OpenGL on the widget
                if hasattr(self.plot_widget, 'setRenderHint'):
                    self.plot_widget.setRenderHint(QtGui.QPainter.Antialiasing, False)
                
                # Force repaint method to be CPU-based
                if hasattr(self.plot_widget, 'setViewportUpdateMode'):
                    self.plot_widget.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
                    
                _LOGGER.debug("Widget-level software rendering configured")
            except Exception as e:
                _LOGGER.debug(f"Some widget rendering settings not available: {e}")
            
            # Get plot item for customization
            self.plot_item = self.plot_widget.getPlotItem()
            
            # ADDITIONAL FIX: Explicitly set plot background and colors
            self.plot_widget.setBackground('white')
            _LOGGER.debug("🔧 Plot background set to white")
            
            # Set axis colors explicitly
            left_axis = self.plot_item.getAxis('left')
            bottom_axis = self.plot_item.getAxis('bottom')
            right_axis = self.plot_item.getAxis('right')
            left_axis.setTextPen('black')
            bottom_axis.setTextPen('black')
            if right_axis:
                right_axis.setTextPen('black')
            left_axis.setPen('black')
            bottom_axis.setPen('black')
            if right_axis:
                right_axis.setPen('black')
            # Show right axis (no label)
            try:
                self.plot_item.showAxis('right')
                ra = self.plot_item.getAxis('right')
                if ra:
                    # Hide numbers on the right axis
                    ra.setStyle(showValues=False)
                    # Ensure the axis line area remains visible
                    try:
                        ra.setWidth(8)
                    except Exception:
                        pass
            except Exception:
                pass
            _LOGGER.debug("🔧 Axis colors set to black")
            
            # Initialize interactive masking
            self.init_interactive_masking()
            
            # Apply plot theming (will be called later when theme colors are set)
            if self.theme_colors:
                self.apply_pyqtgraph_theme()
            
            # Initial plot - show welcome message
            self.plot_pyqtgraph_welcome_message()
            
            _LOGGER.debug("PyQtGraph plot initialized successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing PyQtGraph plot: {e}")
            self.init_fallback_plot()

    def set_antialiasing(self, enabled: bool) -> None:
        """Enable or disable antialiasing for plots (both global and widget level)."""
        try:
            if PYQTGRAPH_AVAILABLE and pg is not None:
                try:
                    pg.setConfigOptions(antialias=bool(enabled))
                except Exception:
                    pass
            if getattr(self, 'plot_widget', None):
                try:
                    # Fallback helper used elsewhere in this file
                    if hasattr(self.plot_widget, 'setConfigOption'):
                        self.plot_widget.setConfigOption('antialias', bool(enabled))
                except Exception:
                    pass
            # Matplotlib (if present): set global rcParam so new lines honor the choice
            try:
                if MATPLOTLIB_AVAILABLE and plt is not None:
                    plt.rcParams['lines.antialiased'] = bool(enabled)
            except Exception:
                pass
            _LOGGER.debug(f"Plot antialiasing set to {enabled}")
        except Exception as e:
            _LOGGER.debug(f"Non-fatal: could not set antialiasing: {e}")

    def apply_plot_settings(self, settings: Dict[str, Any]) -> None:
        """Apply plot-related runtime settings from GUI settings dict."""
        try:
            aa = bool(settings.get('plot_antialiasing', True))
            self.set_antialiasing(aa)
        except Exception as e:
            _LOGGER.debug(f"Non-fatal: apply_plot_settings failed: {e}")

    def get_antialiasing(self) -> Optional[bool]:
        """Return current antialiasing setting if available."""
        try:
            if PYQTGRAPH_AVAILABLE and pg is not None:
                val = pg.getConfigOption('antialias')
                return bool(val)
        except Exception:
            pass
        return None

    def _on_files_dropped(self, paths):
        """Handle files dropped onto the PyQtGraph plot widget.
        Accepts first supported spectrum file and forwards to the standard loader.
        """
        try:
            if not paths:
                return
            # Prefer known spectrum extensions; otherwise take the first path
            supported_exts = {'.dat', '.txt', '.ascii', '.asci', '.csv', '.fits', '.flm'}
            chosen = None
            for p in paths:
                try:
                    ext_parts = str(p).lower().rsplit('.', 1)
                    ext = f".{ext_parts[1]}" if len(ext_parts) == 2 else ''
                except Exception:
                    ext = ''
                if ext in supported_exts:
                    chosen = p
                    break
            if chosen is None:
                chosen = paths[0]
            # Delegate to main window's event handler if available
            if hasattr(self.main_window, 'event_handlers') and hasattr(self.main_window.event_handlers, 'handle_open_spectrum_file'):
                self.main_window.event_handlers.handle_open_spectrum_file(chosen)
        except Exception as e:
            _LOGGER.error(f"Error handling dropped files: {e}")

    def _ensure_rest_axis(self):
        """Create and attach the rest wavelength top axis if available."""
        try:
            if not PYQTGRAPH_AVAILABLE or not _REST_AXIS_AVAILABLE or not self.plot_item:
                return
            if self._rest_axis is not None:
                # already attached
                return
            # Create custom top axis and link to the same ViewBox
            self._rest_axis = RestWavelengthAxisItem('top')  # type: ignore
            # Replace the existing top axis in the PlotItem layout
            try:
                # Remove existing top axis if present
                top_axis = self.plot_item.getAxis('top')
                if top_axis is not None:
                    self.plot_item.layout.removeItem(top_axis)
            except Exception:
                pass
            # Add our axis at the top
            self.plot_item.layout.addItem(self._rest_axis, 1, 1)
            # Link to main viewbox so ticks align and update on pan/zoom
            self._rest_axis.linkToView(self.plot_item.vb)
        except Exception as axis_error:
            _LOGGER.debug(f"Could not attach rest axis: {axis_error}")

    def _set_rest_axis_redshift(self, z: float):
        """Update the rest-axis redshift (if axis is present)."""
        try:
            if self._rest_axis is None:
                self._ensure_rest_axis()
            if self._rest_axis is not None:
                # type: ignore[attr-defined]
                self._rest_axis.set_redshift(z)  # type: ignore
        except Exception as e:
            _LOGGER.debug(f"Could not set rest axis redshift: {e}")
    
    def init_fallback_plot(self):
        """Initialize fallback plot area when PyQtGraph is not available"""
        self.fallback_widget = QtWidgets.QLabel(
            "PyQtGraph not available\n\n"
            "Install PyQtGraph for enhanced plotting:\n"
            "pip install pyqtgraph\n\n"
            "The application will continue with basic functionality."
        )
        self.fallback_widget.setAlignment(QtCore.Qt.AlignCenter)
        self.fallback_widget.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 12pt;")
        
        # Initialize minimal plot data storage
        self.plot_widget = None
        self.plot_item = None
        self.current_plot_data = None
        self.mask_regions_pg = []
    
    def init_matplotlib_plots(self):
        """Initialize matplotlib plots for analysis visualizations"""
        try:
            # Create matplotlib widget
            self.matplotlib_widget = QtWidgets.QWidget()
            matplotlib_layout = QtWidgets.QVBoxLayout(self.matplotlib_widget)
            matplotlib_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create matplotlib figure
            self.matplotlib_figure = Figure(figsize=(10, 6), dpi=100, facecolor='white')
            self.matplotlib_canvas = FigureCanvas(self.matplotlib_figure)
            self.matplotlib_canvas.setParent(self.matplotlib_widget)
            
            # Add to layout
            matplotlib_layout.addWidget(self.matplotlib_canvas)
            
            # Store reference to axes (will be created dynamically)
            self.matplotlib_axes = None
            
            # Initialize analysis plotter
            self._init_analysis_plotter()
            
            _LOGGER.debug("Matplotlib plots initialized")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing matplotlib plots: {e}")
    
    def _init_analysis_plotter(self):
        """Initialize the analysis plotter for matplotlib-based analysis plots"""
        try:
            if not ANALYSIS_PLOTTER_AVAILABLE:
                _LOGGER.warning("Analysis plotter not available")
                return
                
            if not self.matplotlib_figure or not self.matplotlib_canvas:
                _LOGGER.warning("Cannot initialize analysis plotter without matplotlib components")
                return
            
            # Check if main window has app_controller before initializing analysis plotter
            if not hasattr(self.main_window, 'app_controller') or self.main_window.app_controller is None:
                _LOGGER.debug("Main window does not have app_controller - skipping analysis plotter initialization")
                return
                
            self.analysis_plotter = PySide6AnalysisPlotter(
                main_window=self.main_window,
                matplotlib_figure=self.matplotlib_figure,
                matplotlib_canvas=self.matplotlib_canvas
            )
            
            _LOGGER.debug("Analysis plotter initialized successfully")
            
        except Exception as e:
            _LOGGER.error(f"Error initializing analysis plotter: {e}")
            self.analysis_plotter = None
    
    def init_interactive_masking(self):
        """Initialize interactive masking with PyQtGraph LinearRegionItem"""
        try:
            # Initialize mask regions list
            self.mask_regions_pg = []
            
            _LOGGER.debug("Interactive masking initialized")
            
        except Exception as e:
            _LOGGER.warning(f"Could not initialize interactive masking: {e}")
    
    def apply_pyqtgraph_theme(self):
        """Apply theme colors to PyQtGraph plot"""
        try:
            if not self.theme_colors:
                return
                
            colors = self.theme_colors
            
            # Set plot background
            self.plot_widget.setBackground(colors.get('plot_bg', 'white'))
            
            # Configure axes styling
            left_axis = self.plot_item.getAxis('left')
            bottom_axis = self.plot_item.getAxis('bottom')
            
            # Set axis text colors
            left_axis.setTextPen(pg.mkPen(color='black'))
            bottom_axis.setTextPen(pg.mkPen(color='black'))
            
            # Set axis line colors
            left_axis.setPen(pg.mkPen(color='black'))
            bottom_axis.setPen(pg.mkPen(color='black'))
                        
            # Set grid
            self.plot_item.showGrid(x=True, y=True, alpha=0.08)
            
            # Set labels
            self.plot_item.setLabels(left='Flux', bottom='Obs. Wavelength (Å)')
            
            # Configure plot item style
            self.plot_item.getViewBox().setBackgroundColor(colors.get('plot_bg', 'white'))
            
            _LOGGER.debug("PyQtGraph theme applied")
            
        except Exception as e:
            _LOGGER.warning(f"Could not apply PyQtGraph theme: {e}")
    
    def plot_pyqtgraph_welcome_message(self):
        """Show PyQtGraph welcome message - alias for plot_clean_welcome_message"""
        self.plot_clean_welcome_message()
    
    def plot_clean_welcome_message(self):
        """Show clean welcome message without demo spectrum"""
        try:
            if not self.plot_item:
                return
                
            # Clear plot
            self.plot_item.clear()
            
            # Hide save button for welcome message (no data to save)
            if hasattr(self.plot_widget, 'hide_save_button'):
                self.plot_widget.hide_save_button()
            
            # Ensure axes are visible and styled: left, bottom, right (no values), top rest axis present
            try:
                # Right axis visible but without values
                self.plot_item.showAxis('right')
                ra = self.plot_item.getAxis('right')
                if ra:
                    ra.setTextPen('black')
                    ra.setPen('black')
                    ra.setStyle(showValues=False)
            except Exception:
                pass

            # Attach an empty rest top axis as placeholder (z=0)
            try:
                self._ensure_rest_axis()
                self._set_rest_axis_redshift(0.0)
            except Exception:
                pass

            # Add welcome text without fake spectrum
            text_item = pg.TextItem(
                html='<div style="text-align: center; color: black; font-size: 14pt; font-weight: bold; '
                     'background-color: rgba(240,240,240,180); border: 1px solid gray; padding: 10px; border-radius: 5px;">'
                     'Welcome to SNID SAGE<br>'
                     '<span style="font-size: 12pt; font-weight: normal;">'
                     'Click Load Spectrum or drag a spectrum here'
                     '</span></div>',
                anchor=(0.5, 0.5)
            )
            
            # Position in center of plot area
            text_item.setPos(6500, 0.5)  # Center position
            self.plot_item.addItem(text_item)
            
            # Set labels for empty plot
            self.plot_item.setLabels(left='Flux', bottom='Obs. Wavelength (Å)')
            
            # Set reasonable default ranges for empty plot
            self.plot_item.setXRange(3000, 10000)
            self.plot_item.setYRange(-0.5, 1.5)
            
            # Ensure axis visibility policy for empty plot:
            # - Left and bottom: values shown
            # - Right and top: edge line only (no values)
            try:
                # Bottom/left already visible with values by default
                # Right axis: show edge line, hide tick values
                self.plot_item.showAxis('right')
                ra = self.plot_item.getAxis('right')
                if ra:
                    ra.setStyle(showValues=False)
                    try:
                        ra.setWidth(8)
                    except Exception:
                        pass
                # Top axis: ensure present; if rest axis available, use it at z=0
                self._ensure_rest_axis()
                self._set_rest_axis_redshift(0.0)
            except Exception:
                pass
            
        except Exception as e:
            _LOGGER.warning(f"Could not plot welcome message: {e}")
    
    def switch_to_plot_mode(self, plot_mode: PlotMode):
        """Switch to the specified plot mode"""
        try:
            self.current_plot_mode = plot_mode
            
            if plot_mode == PlotMode.SPECTRUM:
                # Switch to PyQtGraph for spectrum/template overlays
                self.plot_stack.setCurrentIndex(self.pyqtgraph_index)
                _LOGGER.debug("Switched to spectrum plot mode (PyQtGraph)")
            else:
                # Switch to matplotlib for analysis plots
                self.plot_stack.setCurrentIndex(self.matplotlib_index)
                _LOGGER.debug(f"Switched to analysis plot mode: {plot_mode.value}")
                
                # Create the appropriate analysis plot
                if plot_mode == PlotMode.REDSHIFT_AGE:
                    self.create_redshift_age_plot()
                elif plot_mode == PlotMode.SUBTYPE_PROPS:
                    self.create_subtype_proportions_plot()
                    
        except Exception as e:
            _LOGGER.error(f"Error switching to plot mode {plot_mode}: {e}")
    
    def refresh_plot(self):
        """Refresh the current plot with updated data"""
        try:
            _LOGGER.info("🔄 Refreshing plot after cluster selection...")
            
            if self.current_plot_mode == PlotMode.SPECTRUM:
                # For spectrum plots, get the current view type from main window
                current_view = getattr(self.main_window, 'current_view', 'flux')
                
                # Reset template index to 0 to show the best template from the new cluster
                if hasattr(self.main_window.app_controller, 'current_template'):
                    self.main_window.app_controller.current_template = 0
                
                # Re-plot the spectrum with template overlay
                self.plot_spectrum(current_view)
                _LOGGER.info("✅ Spectrum plot refreshed successfully")
                
            else:
                # For analysis plots, recreate the current plot
                if self.current_plot_mode == PlotMode.REDSHIFT_AGE:
                    self.create_redshift_age_plot()
                    _LOGGER.info("✅ Redshift vs age plot refreshed successfully")
                elif self.current_plot_mode == PlotMode.SUBTYPE_PROPS:
                    self.create_subtype_proportions_plot()
                    _LOGGER.info("✅ Subtype proportions plot refreshed successfully")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error refreshing plot: {e}")
    
    def plot_spectrum(self, view_type='flux'):
        """Plot the loaded spectrum data with template overlays if available"""
        try:
            _LOGGER.info("🎯 Starting spectrum plotting...")
            
            if not self.plot_item:
                _LOGGER.error("❌ Plot item not available")
                return
            
            # Clear any existing template text item
            self._clear_template_text_item()
            
            # Clear plot first
            self.plot_item.clear()
            # Hide save button when clearing (will be shown again when data is plotted)
            if hasattr(self.plot_widget, 'hide_save_button'):
                self.plot_widget.hide_save_button()
            _LOGGER.debug("Plot cleared")
            
            # Check if we have SNID results for template overlays
            app_controller = self.main_window.app_controller
            if hasattr(app_controller, 'snid_results') and app_controller.snid_results:
                # Prefer best_matches; fallback to filtered_matches or top_matches so single survivors still show
                has_best = hasattr(app_controller.snid_results, 'best_matches') and app_controller.snid_results.best_matches
                has_filtered = hasattr(app_controller.snid_results, 'filtered_matches') and app_controller.snid_results.filtered_matches
                has_top = hasattr(app_controller.snid_results, 'top_matches') and app_controller.snid_results.top_matches

                if has_best or has_filtered or has_top:
                    # If best is empty but filtered/top exist, temporarily expose them as best for overlay rendering
                    if not has_best:
                        try:
                            if has_filtered:
                                app_controller.snid_results.best_matches = app_controller.snid_results.filtered_matches
                            elif has_top:
                                app_controller.snid_results.best_matches = app_controller.snid_results.top_matches
                        except Exception:
                            pass
                    # Plot spectrum with template overlay
                    self.plot_spectrum_with_template_overlay(view_type)
                    return
            
            # Get spectrum data for current view (no templates)
            wave, flux = app_controller.get_spectrum_for_view(view_type)
            if wave is None or flux is None:
                _LOGGER.error("❌ No spectrum data available to plot")
                return
            
            _LOGGER.info(f"✅ Got spectrum data for {view_type} view: {len(wave)} points, wavelength range {wave[0]:.1f}-{wave[-1]:.1f}")
            _LOGGER.info(f"✅ Flux range: {np.min(flux):.2e} to {np.max(flux):.2e}")
            
            # Clean up data arrays and remove non-finite values
            wave = np.asarray(wave, dtype=float)
            flux = np.asarray(flux, dtype=float)
            
            finite = np.isfinite(wave) & np.isfinite(flux)
            wave, flux = wave[finite], flux[finite]
            _LOGGER.debug(f"After cleaning: {len(wave)} finite points")
            
            # Check if we have valid data after cleaning
            if len(wave) == 0 or len(flux) == 0:
                _LOGGER.error("❌ No valid data points after cleaning non-finite values")
                return
            
            # Plot based on current view with appropriate labels
            if view_type == 'flux':
                flux_data = flux.copy()
                y_label = 'Flux'
            else:  # flat view
                flux_data = flux.copy()  # Already flat data from get_spectrum_for_view
                y_label = 'Flattened Flux'
            
            _LOGGER.debug(f"Using view: {view_type}, y_label: {y_label}")
            
            # Set labels (no title per user requirement)
            self.plot_item.setLabels(left=y_label, bottom='Obs. Wavelength (Å)')

            # Ensure rest-wavelength top axis and set redshift from controller (manual or host)
            try:
                appc = self.main_window.app_controller
                z_val = None
                # Prefer manual redshift if set
                if hasattr(appc, 'manual_redshift') and appc.manual_redshift:
                    z_val = float(appc.manual_redshift)
                elif hasattr(appc, 'get_redshift'):
                    z_val = appc.get_redshift() or 0.0
                else:
                    z_val = 0.0
                self._ensure_rest_axis()
                self._set_rest_axis_redshift(float(z_val or 0.0))
            except Exception:
                pass
            
            # Use same blue as Flux/Flat buttons for consistency
            pen = pg.mkPen(color='#3b82f6', width=2)  # Same blue as Flux/Flat buttons
            curve = self.plot_item.plot(
                wave,
                flux_data,
                pen=pen,
                name='Spectrum',
                connect='all',
                autoDownsample=False,
                clipToView=False,
                downsample=1,
            )
            _LOGGER.debug("Data plotted with blue pen matching Flux/Flat buttons")
            
            # FIXED: Replace problematic auto-ranging with stable range setting
            # Disable all auto-ranging to prevent spinning axes
            self.plot_item.disableAutoRange()
            
            # Set reasonable ranges manually
            x_margin = (np.max(wave) - np.min(wave)) * 0.05  # 5% margin
            y_margin = (np.max(flux_data) - np.min(flux_data)) * 0.1  # 10% margin
            
            # Set X range with margins
            self.plot_item.setXRange(np.min(wave) - x_margin, np.max(wave) + x_margin, padding=0)
            
            # Set Y range with margins, ensuring we don't have zero range
            y_min = np.min(flux_data) - y_margin
            y_max = np.max(flux_data) + y_margin
            if y_max <= y_min:  # Handle edge case where all flux values are the same
                y_center = y_min
                y_min = y_center - abs(y_center) * 0.1 if y_center != 0 else -1.0
                y_max = y_center + abs(y_center) * 0.1 if y_center != 0 else 1.0
                
            self.plot_item.setYRange(y_min, y_max, padding=0)
            _LOGGER.debug(f"Set stable ranges: X=[{np.min(wave) - x_margin:.1f}, {np.max(wave) + x_margin:.1f}], Y=[{y_min:.2e}, {y_max:.2e}]")
            
            # Force a plot update
            self.plot_widget.update()
            self.plot_widget.repaint()
            _LOGGER.debug("Plot updated and repainted")
            
            # Store current data for masking
            self.current_plot_data = (wave, flux_data)
            
            # Re-add any existing mask regions
            self.reapply_mask_regions()
            
            # Show save button now that we have actual spectrum data
            try:
                # Suggest export filename based on spectrum name and view type
                if hasattr(self.main_window, 'app_controller') and hasattr(self.plot_widget, 'set_default_export_basename'):
                    from pathlib import Path as _Path
                    spectrum_path = getattr(self.main_window.app_controller, 'current_file_path', None)
                    spec_name = None
                    try:
                        if spectrum_path:
                            spec_name = _Path(str(spectrum_path)).stem
                    except Exception:
                        spec_name = None
                    if not spec_name:
                        spec_name = 'spectrum'
                    view_tag = 'Flux' if view_type == 'flux' else 'Flat'
                    self.plot_widget.set_default_export_basename(f"{spec_name}__{view_tag}")
            except Exception:
                pass
            if hasattr(self.plot_widget, 'show_save_button'):
                self.plot_widget.show_save_button()
            
            _LOGGER.info(f"✅ Spectrum plotted successfully: {len(wave)} data points")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error plotting spectrum: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_spectrum_with_template_overlay(self, view_type='flux'):
        """Plot spectrum with template overlay."""
        try:
            _LOGGER.info("🎯 Plotting spectrum with template overlay...")
            
            # Clear any existing template text item
            self._clear_template_text_item()
            
            app_controller = self.main_window.app_controller
            
            # Get current template index (default to 0 if not set)
            if not hasattr(app_controller, 'current_template'):
                app_controller.current_template = 0
            
            current_template_idx = app_controller.current_template
            best_matches = app_controller.snid_results.best_matches
            
            # Ensure template index is valid
            if current_template_idx >= len(best_matches):
                current_template_idx = 0
                app_controller.current_template = 0
            
            current_match = best_matches[current_template_idx]
            
            # Get observed spectrum data for current view
            obs_wave, obs_flux = app_controller.get_spectrum_for_view(view_type)
            if obs_wave is None or obs_flux is None:
                _LOGGER.error("❌ No observed spectrum data available")
                return
            
            # Clean observed spectrum data
            obs_wave = np.asarray(obs_wave, dtype=float)
            obs_flux = np.asarray(obs_flux, dtype=float)
            finite = np.isfinite(obs_wave) & np.isfinite(obs_flux)
            obs_wave, obs_flux = obs_wave[finite], obs_flux[finite]
            
            # Get template spectrum data
            try:
                if view_type == 'flux':
                    template_wave = current_match['spectra']['flux']['wave']
                    template_flux = current_match['spectra']['flux']['flux']
                    y_label = 'Flux'
                else:  # flat view
                    template_wave = current_match['spectra']['flat']['wave']
                    template_flux = current_match['spectra']['flat']['flux']
                    y_label = 'Flattened Flux'
                
                # Clean template data
                template_wave = np.asarray(template_wave, dtype=float)
                template_flux = np.asarray(template_flux, dtype=float)
                finite_template = np.isfinite(template_wave) & np.isfinite(template_flux)
                template_wave, template_flux = template_wave[finite_template], template_flux[finite_template]
                
            except (KeyError, TypeError) as e:
                _LOGGER.error(f"Error accessing template spectrum data: {e}")
                return
            
            # Set plot labels
            self.plot_item.setLabels(left=y_label, bottom='Obs. Wavelength (Å)')

            # Attach/update rest-wavelength top axis using current match redshift
            try:
                redshift = float(current_match.get('redshift', 0.0) or 0.0)
                self._ensure_rest_axis()
                self._set_rest_axis_redshift(redshift)
            except Exception:
                pass
            
            # Plot observed spectrum (same blue as Flux/Flat buttons)
            obs_pen = pg.mkPen(color='#3b82f6', width=2)  # Same blue as Flux/Flat buttons
            obs_curve = self.plot_item.plot(
                obs_wave,
                obs_flux,
                pen=obs_pen,
                name='Observed Spectrum',
                connect='all',
                autoDownsample=False,
                clipToView=False,
                downsample=1,
            )
            
            # Plot template spectrum (red, slightly transparent so it doesn't obscure observed)
            template_pen = pg.mkPen(color=(231, 76, 60, int(255 * 0.8)), width=2)  # RGBA with alpha≈0.8
            template_curve = self.plot_item.plot(
                template_wave,
                template_flux,
                pen=template_pen,
                name='Template',
                connect='all',
                autoDownsample=False,
                clipToView=False,
                downsample=1,
            )
            
            # FIXED: Replace problematic auto-ranging with stable range setting
            # Disable all auto-ranging to prevent spinning axes
            self.plot_item.disableAutoRange()
            
            # Calculate combined data ranges for both observed and template
            all_wave = np.concatenate([obs_wave, template_wave])
            all_flux = np.concatenate([obs_flux, template_flux])
            
            # Set reasonable ranges manually with margins
            x_margin = (np.max(all_wave) - np.min(all_wave)) * 0.05  # 5% margin
            y_margin = (np.max(all_flux) - np.min(all_flux)) * 0.1  # 10% margin
            
            # Set X range with margins
            self.plot_item.setXRange(np.min(all_wave) - x_margin, np.max(all_wave) + x_margin, padding=0)
            
            # Set Y range with margins, ensuring we don't have zero range
            y_min = np.min(all_flux) - y_margin
            y_max = np.max(all_flux) + y_margin
            if y_max <= y_min:  # Handle edge case where all flux values are the same
                y_center = y_min
                y_min = y_center - abs(y_center) * 0.1 if y_center != 0 else -1.0
                y_max = y_center + abs(y_center) * 0.1 if y_center != 0 else 1.0
                
            self.plot_item.setYRange(y_min, y_max, padding=0)
            _LOGGER.debug(f"Set stable template overlay ranges: X=[{np.min(all_wave) - x_margin:.1f}, {np.max(all_wave) + x_margin:.1f}], Y=[{y_min:.2e}, {y_max:.2e}]")
            
            # Add template info text like the original implementation
            template = current_match.get('template', {})
            raw_template_name = current_match.get('name', 'Unknown')
            # Clean template name to remove _epoch_X suffix
            from snid_sage.shared.utils import clean_template_name
            template_name = clean_template_name(raw_template_name)
            subtype = template.get('subtype', current_match.get('type', 'Unknown'))
            redshift = current_match.get('redshift', 0.0)
            age = template.get('age', 0.0)
            # Keep as local variable for layout only
            hlap_for_layout = float(current_match.get('hlap', 0.0) or 0.0)
            
            # Get current match index for display
            app_controller = self.main_window.app_controller
            current_index = getattr(app_controller, 'current_template', 0) + 1
            total_matches = len(app_controller.snid_results.best_matches) if hasattr(app_controller, 'snid_results') and app_controller.snid_results else 1
            
            # Get redshift uncertainty if available (show 6 decimals like CLI)
            sigma_z = current_match.get('sigma_z', float('nan'))
            if np.isfinite(sigma_z) and sigma_z > 0:
                redshift_text = f"z = {redshift:.6f} ±{sigma_z:.6f}"
            else:
                redshift_text = f"z = {redshift:.6f}"
            
            # Use best available metric (HσLAP-CCC preferred)
            from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
            best_metric_value = get_best_metric_value(current_match)
            metric_name = get_best_metric_name(current_match)
            metric_text = f"{metric_name} = {best_metric_value:.2f}"
            
            # Create multi-line info text like the original
            info_text = (f"Template {current_index}/{total_matches}: {template_name}\n"
                        f"Subtype: {subtype}, Age: {age:.1f}d\n"
                        f"{redshift_text}\n"
                        f"{metric_text}")
            
            # Add info text to plot with proper positioning to fit within plot area
            from ...utils.plot_legend_utils import get_pyqtgraph_legend_position
            
            text_item = pg.TextItem(
                html=f'<div style="background-color: rgba(255,255,255,200); border: 1px solid black; padding: 5px; color: black; font-size: 10pt;">{info_text.replace(chr(10), "<br>")}</div>',
                anchor=(1, 0)  # Anchor to top-right of text box (top-right corner stays within plot)
            )
            
            # Position text in upper right corner with proper padding to stay within plot bounds
            x_pos, y_pos = get_pyqtgraph_legend_position(self.plot_item, 'upper_right', padding_fraction=0.02)
            text_item.setPos(x_pos, y_pos)
            self.plot_item.addItem(text_item)
            
            # Store text item for potential repositioning on view changes
            self._current_template_text_item = text_item
            
            # Store current data for masking
            self.current_plot_data = (obs_wave, obs_flux)
            
            # Re-add any existing mask regions
            self.reapply_mask_regions()
            
            # Show save button now that we have actual spectrum data
            try:
                # Suggest export filename based on spectrum and matched template/type
                if hasattr(self.plot_widget, 'set_default_export_basename'):
                    from pathlib import Path as _Path
                    spectrum_path = getattr(self.main_window.app_controller, 'current_file_path', None)
                    try:
                        spec_name = _Path(str(spectrum_path)).stem if spectrum_path else 'spectrum'
                    except Exception:
                        spec_name = 'spectrum'
                    # Build type-subtype block
                    type_info = current_match.get('type', 'Unknown')
                    subtype_info = template.get('subtype', '') or ''
                    type_block = f"{type_info}-{subtype_info}" if subtype_info and subtype_info != 'Unknown' else f"{type_info}"
                    # Create basename: Spectrum__Template__Type[-Subtype]
                    export_base = f"{spec_name}__{template_name}__{type_block}"
                    self.plot_widget.set_default_export_basename(export_base)
            except Exception:
                pass
            if hasattr(self.plot_widget, 'show_save_button'):
                self.plot_widget.show_save_button()
            
            _LOGGER.info(f"✅ Spectrum with template overlay plotted successfully")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error plotting spectrum with template overlay: {e}")
            import traceback
            traceback.print_exc()
    
    def reapply_mask_regions(self):
        """Re-apply mask regions after plot update"""
        try:
            if not self.plot_item:
                return
                
            # Clear PyQtGraph regions but keep mask_regions data from app controller
            for region in self.mask_regions_pg:
                self.plot_item.removeItem(region)
            self.mask_regions_pg.clear()
            
            # Re-add regions from app controller mask data
            temp_regions = self.main_window.app_controller.get_mask_regions()
            for mask_min, mask_max in temp_regions:
                self.add_mask_region(mask_min, mask_max)
                
        except Exception as e:
            _LOGGER.warning(f"Error reapplying mask regions: {e}")
    
    def add_mask_region(self, x_min, x_max):
        """Add a mask region to the plot"""
        try:
            if not self.plot_item:
                return
                
            # Create linear region item
            region = pg.LinearRegionItem([x_min, x_max], brush=(255, 0, 0, 50))
            region.setZValue(10)
            
            # Add to plot
            self.plot_item.addItem(region)
            self.mask_regions_pg.append(region)
            
        except Exception as e:
            _LOGGER.warning(f"Error adding mask region: {e}")
    
    def _update_template_legend_position(self):
        """Update template legend position when view changes"""
        try:
            if self._current_template_text_item and self.plot_item:
                from ...utils.plot_legend_utils import update_pyqtgraph_legend_on_view_change
                update_pyqtgraph_legend_on_view_change(
                    self.plot_item, 
                    self._current_template_text_item, 
                    'upper_right'
                )
        except Exception as e:
            _LOGGER.debug(f"Error updating template legend position: {e}")
    
    def _clear_template_text_item(self):
        """Clear the current template text item"""
        try:
            if self._current_template_text_item and self.plot_item:
                self.plot_item.removeItem(self._current_template_text_item)
            self._current_template_text_item = None
        except Exception as e:
            _LOGGER.debug(f"Error clearing template text item: {e}")
    
    def create_redshift_age_plot(self):
        """Create redshift vs age plot - delegate to analysis plotter"""
        try:
            if self.analysis_plotter:
                self.analysis_plotter.create_redshift_age_plot()
            else:
                self.show_matplotlib_error("Analysis plotter not available.\nCannot create redshift vs age plot.")
        except Exception as e:
            _LOGGER.error(f"Error creating redshift vs age plot: {e}")
            self.show_matplotlib_error(f"Error creating plot: {str(e)}")
    
    def create_subtype_proportions_plot(self):
        """Create subtype proportions plot - delegate to analysis plotter"""
        try:
            if self.analysis_plotter:
                self.analysis_plotter.create_subtype_proportions_plot()
            else:
                self.show_matplotlib_error("Analysis plotter not available.\nCannot create subtype proportions plot.")
        except Exception as e:
            _LOGGER.error(f"Error creating subtype proportions plot: {e}")
            self.show_matplotlib_error(f"Error creating plot: {str(e)}")
    
    # === Save/export helpers for current plot (invoked by keyboard shortcuts) ===
    def save_current_plot_as_png_dialog(self):
        """Open a dialog to save the currently visible plot as PNG/JPG.
        - For spectrum (PyQtGraph): uses the plot widget's export routine.
        - For analysis (Matplotlib): saves the current figure via savefig.
        """
        try:
            if self.current_plot_mode == PlotMode.SPECTRUM and self.plot_widget is not None:
                if hasattr(self.plot_widget, 'save_as_png_dialog'):
                    self.plot_widget.save_as_png_dialog()
                    return
            # Matplotlib (analysis plots)
            if self.current_plot_mode != PlotMode.SPECTRUM and self.matplotlib_figure is not None:
                filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self.main_window,
                    "Save Plot as Image",
                    "snid_sage_plot.png",
                    "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
                )
                if not filename:
                    return
                try:
                    # Use figure dpi
                    self.matplotlib_figure.savefig(filename, dpi=self.matplotlib_figure.dpi)
                    _LOGGER.info(f"Matplotlib plot saved as image: {filename}")
                    QtWidgets.QMessageBox.information(
                        self.main_window,
                        "Export Successful",
                        f"Plot saved successfully:\n{os.path.basename(filename)}"
                    )
                except Exception as save_err:
                    _LOGGER.error(f"Failed to save matplotlib image: {save_err}")
                    QtWidgets.QMessageBox.warning(self.main_window, "Export Failed", str(save_err))
        except Exception as e:
            _LOGGER.error(f"Error during save_current_plot_as_png_dialog: {e}")
    
    def save_current_plot_as_svg_dialog(self):
        """Open a dialog to save the currently visible plot as SVG.
        - For spectrum (PyQtGraph): uses the plot widget's SVG export.
        - For analysis (Matplotlib): saves the current figure as SVG.
        """
        try:
            if self.current_plot_mode == PlotMode.SPECTRUM and self.plot_widget is not None:
                if hasattr(self.plot_widget, 'save_as_svg_dialog'):
                    self.plot_widget.save_as_svg_dialog()
                    return
            # Matplotlib (analysis plots)
            if self.current_plot_mode != PlotMode.SPECTRUM and self.matplotlib_figure is not None:
                filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self.main_window,
                    "Save Plot as SVG",
                    "snid_sage_plot.svg",
                    "SVG Files (*.svg);;All Files (*)"
                )
                if not filename:
                    return
                try:
                    self.matplotlib_figure.savefig(filename, format='svg')
                    _LOGGER.info(f"Matplotlib plot saved as SVG: {filename}")
                    QtWidgets.QMessageBox.information(
                        self.main_window,
                        "Export Successful",
                        f"Plot saved successfully:\n{os.path.basename(filename)}"
                    )
                except Exception as save_err:
                    _LOGGER.error(f"Failed to save matplotlib SVG: {save_err}")
                    QtWidgets.QMessageBox.warning(self.main_window, "Export Failed", str(save_err))
        except Exception as e:
            _LOGGER.error(f"Error during save_current_plot_as_svg_dialog: {e}")
    

    
    def show_matplotlib_error(self, error_msg):
        """Show error message in matplotlib plot area"""
        try:
            self.matplotlib_figure.clear()
            ax = self.matplotlib_figure.add_subplot(111)
            ax.text(0.5, 0.5, error_msg, ha='center', va='center', 
                   transform=ax.transAxes, fontsize=12, color='red',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            ax.axis('off')
            self.matplotlib_canvas.draw()
        except Exception as e:
            _LOGGER.error(f"Error showing matplotlib error: {e}")

    def get_plot_widgets(self):
        """Get plot widgets for dual plot setup (for preprocessing dialog)"""
        try:
            # Create two separate plot widgets for dual preview
            if not PYQTGRAPH_AVAILABLE:
                _LOGGER.warning("PyQtGraph not available - cannot create dual plots")
                return None, None
            
            # Create top simple plot widget without save functionality (for preprocessing previews)
            top_plot_widget = SimplePlotWidget()
            top_plot_widget.setLabel('left', 'Flux')
            top_plot_widget.setLabel('bottom', 'Wavelength (Å)')
            top_plot_widget.showGrid(x=True, y=True, alpha=0.08)
            
            # Apply theme if available
            if self.theme_colors:
                self._apply_theme_to_plot_widget(top_plot_widget)
            
            # Create bottom simple plot widget without save functionality (for preprocessing previews)
            bottom_plot_widget = SimplePlotWidget()
            bottom_plot_widget.setLabel('left', 'Flux')
            bottom_plot_widget.setLabel('bottom', 'Wavelength (Å)')
            bottom_plot_widget.showGrid(x=True, y=True, alpha=0.08)
            
            # Apply theme if available
            if self.theme_colors:
                self._apply_theme_to_plot_widget(bottom_plot_widget)
            
            # Store references for updating
            self.top_preview_widget = top_plot_widget
            self.bottom_preview_widget = bottom_plot_widget
            
            _LOGGER.debug("Created dual plot widgets for preprocessing dialog")
            return top_plot_widget, bottom_plot_widget
            
        except Exception as e:
            _LOGGER.error(f"Error creating dual plot widgets: {e}")
            return None, None
    
    def _apply_theme_to_plot_widget(self, plot_widget):
        """Apply theme colors to a plot widget"""
        try:
            # Configure PyQtGraph for software rendering
            plot_widget.setConfigOption('useOpenGL', False)
            plot_widget.setConfigOption('antialias', True)
            
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
            _LOGGER.debug(f"Error applying theme to plot widget: {e}")
    
    def update_standard_preview(self, current_wave, current_flux, preview_wave, preview_flux, mask_regions=None):
        """Update standard preview with current and preview data"""
        try:
            # Update top plot with current data
            if hasattr(self, 'top_preview_widget') and self.top_preview_widget:
                top_plot_item = self.top_preview_widget.getPlotItem()
                top_plot_item.clear()
                
                if current_wave is not None and current_flux is not None:
                    top_plot_item.plot(
                        current_wave,
                        current_flux,
                        pen=pg.mkPen(color='blue', width=2),
                        name="Current",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                    self.top_preview_widget.setTitle("Current State")
            
            # Update bottom plot with preview data
            if hasattr(self, 'bottom_preview_widget') and self.bottom_preview_widget:
                bottom_plot_item = self.bottom_preview_widget.getPlotItem()
                bottom_plot_item.clear()
                
                if preview_wave is not None and preview_flux is not None:
                    bottom_plot_item.plot(
                        preview_wave,
                        preview_flux,
                        pen=pg.mkPen(color='cyan', width=2),
                        name="Preview",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                    self.bottom_preview_widget.setTitle("Preview (After Current Step)")
                
            _LOGGER.debug("Standard preview updated with dual plots")
            
        except Exception as e:
            _LOGGER.error(f"Error updating standard preview: {e}")
            
    def update_interactive_preview(self, current_wave, current_flux, continuum_points, preview_wave, preview_flux, interactive_mode=False):
        """Update interactive preview with continuum overlay"""
        try:
            # Update top plot with current data and continuum points
            if hasattr(self, 'top_preview_widget') and self.top_preview_widget:
                top_plot_item = self.top_preview_widget.getPlotItem()
                top_plot_item.clear()
                
                if current_wave is not None and current_flux is not None:
                    top_plot_item.plot(
                        current_wave,
                        current_flux,
                        pen=pg.mkPen(color='blue', width=2),
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
                
                self.top_preview_widget.setTitle("Current State with Continuum")
            
            # Update bottom plot with preview data
            if hasattr(self, 'bottom_preview_widget') and self.bottom_preview_widget:
                bottom_plot_item = self.bottom_preview_widget.getPlotItem()
                bottom_plot_item.clear()
                
                if preview_wave is not None and preview_flux is not None:
                    bottom_plot_item.plot(
                        preview_wave,
                        preview_flux,
                        pen=pg.mkPen(color='cyan', width=2),
                        name="Preview",
                        connect='all',
                        autoDownsample=False,
                        clipToView=False,
                        downsample=1,
                    )
                    self.bottom_preview_widget.setTitle("Preview (After Continuum Removal)")
                
            _LOGGER.debug("Interactive preview updated with dual plots")
            
        except Exception as e:
            _LOGGER.error(f"Error updating interactive preview: {e}") 