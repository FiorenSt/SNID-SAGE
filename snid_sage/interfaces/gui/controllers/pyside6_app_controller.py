"""
SNID SAGE - PySide6 Application Controller
=========================================

Main application controller that manages the overall state and coordinates
between different components of the PySide6 GUI interface.

This controller handles:
- Application initialization and configuration
- Workflow state management
- Component coordination
- File loading and data management
- Analysis coordination

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

# Set environment variable to indicate PySide6 GUI is running
os.environ['SNID_SAGE_GUI_BACKEND'] = 'PySide6'

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

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
    _LOGGER = get_logger('gui.pyside6_controller')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_controller')


class WorkflowState(Enum):
    """Workflow state enumeration matching Tkinter implementation"""
    INITIAL = "initial"
    FILE_LOADED = "file_loaded"
    PREPROCESSED = "preprocessed"
    REDSHIFT_SET = "redshift_set"
    ANALYSIS_COMPLETE = "analysis_complete"
    AI_READY = "ai_ready"


class PySide6AppController(QtCore.QObject):
    """
    Main application controller for PySide6 SNID SAGE GUI
    
    Manages application state, workflow progression, and component coordination.
    """
    
    # Qt signals for GUI updates
    analysis_completed = QtCore.Signal(bool)  # True for success, False for failure
    preprocessing_completed = QtCore.Signal(bool)  # True for success, False for failure
    workflow_state_changed = QtCore.Signal(object)  # WorkflowState object
    progress_updated = QtCore.Signal(str, float)  # message, progress percentage
    cluster_selection_needed = QtCore.Signal(object)  # SNID result with clustering
    
    def __init__(self, main_window):
        """Initialize the application controller"""
        super().__init__()
        self.main_window = main_window
        
        # Initialize core attributes
        self.current_config = None
        self.templates_dir = None
        self.mask_regions = []
        self.current_file_path = None  # Store current file path
        self.original_wave = None
        self.original_flux = None
        self.processed_spectrum = None
        self.snid_results = None
        self.analysis_trace = None
        self.galaxy_redshift_result = None
        
        # Workflow state management
        self.current_state = WorkflowState.INITIAL
        self.analysis_thread = None
        self.analysis_running = False
        
        # Interactive state
        self.current_template = 0
        self.max_templates = 0
        self.manual_redshift = None
        
        # Auto cluster selection flag for extended quick workflow
        self.auto_select_best_cluster = False
        
        # Data storage
        self.spectrum_data = None
        self.analysis_results = None
        
        # Initialize configuration
        self._init_configuration()
        
        _LOGGER.info("PySide6 Application Controller initialized")
    
    def _init_configuration(self):
        """Initialize configuration manager and settings"""
        try:
            self.config_manager = ConfigurationManager()
            self.current_config = self.config_manager.load_config()
            self.templates_dir = self.current_config['paths']['templates_dir']
            self.platform_config = get_platform_config()
            _LOGGER.debug("Configuration initialized")
        except Exception as e:
            _LOGGER.error(f"Error initializing configuration: {e}")
            # Use fallback configuration
            self.current_config = {'paths': {'templates_dir': Path(__file__).parent.parent.parent.parent / 'templates'}}
            self.templates_dir = self.current_config['paths']['templates_dir']
            self.platform_config = None
    
    # Workflow state management
    def update_workflow_state(self, new_state: WorkflowState):
        """Update workflow state and notify main window"""
        old_state = self.current_state
        self.current_state = new_state
        _LOGGER.debug(f"Workflow state updated: {old_state.value} → {new_state.value}")
        
        # Notify main window to update button states
        if hasattr(self.main_window, 'update_workflow_state'):
            self.main_window.update_workflow_state(new_state)
    
    def get_current_state(self) -> WorkflowState:
        """Get current workflow state"""
        return self.current_state
    
    # File operations
    def load_spectrum_file(self, file_path: str) -> bool:
        """
        Load spectrum data from file using robust spectrum loader
        
        Args:
            file_path: Path to spectrum file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            _LOGGER.info(f"🔄 Loading spectrum file: {file_path}")
            
            # Use the robust spectrum loader from shared utilities
            from snid_sage.shared.utils.data_io.spectrum_loader import load_spectrum
            
            self.original_wave, self.original_flux = load_spectrum(file_path)
            
            # Store the file path
            self.current_file_path = file_path
            
            _LOGGER.info(f"✅ Spectrum file loaded successfully: {file_path}")
            _LOGGER.info(f"✅ Spectrum data: {len(self.original_wave)} points, "
                        f"wavelength range {self.original_wave[0]:.1f}-{self.original_wave[-1]:.1f} Å")
            _LOGGER.info(f"✅ Flux range: {np.min(self.original_flux):.2e} to {np.max(self.original_flux):.2e}")
            
            # Update workflow state
            self.update_workflow_state(WorkflowState.FILE_LOADED)
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"❌ Error loading spectrum file: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_spectrum_data(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get current spectrum data - prioritizes processed spectrum over original"""
        # Priority 1: If we have processed spectrum, return appropriate version based on current view
        if self.processed_spectrum is not None:
            log_wave = self.processed_spectrum.get('log_wave')
            
            # For now, return the log_flux version (which represents the processed data)
            # The main GUI will determine whether to show flux or flat view
            if 'log_flux' in self.processed_spectrum:
                _LOGGER.debug(f"Returning processed spectrum data: {len(log_wave)} points")
                return log_wave, self.processed_spectrum['log_flux']
            
        # Fallback: Return original spectrum if no processed data
        if self.original_wave is not None and self.original_flux is not None:
            _LOGGER.debug(f"Returning original spectrum data: {len(self.original_wave)} points")
            return self.original_wave, self.original_flux
            
        _LOGGER.debug("No spectrum data available")
        return None, None
    
    def get_spectrum_for_view(self, view_type: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Get spectrum data for a specific view type
        
        Args:
            view_type: 'flux' or 'flat'
            
        Returns:
            Tuple of (wavelength, flux) arrays
        """
        # If we have processed spectrum, return appropriate version
        if self.processed_spectrum is not None:
            log_wave = self.processed_spectrum.get('log_wave')
            
            if view_type.lower() == 'flat':
                # Return flat (continuum-removed) version
                if 'display_flat' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['display_flat']
                    _LOGGER.debug(f"Using display_flat for flat view")
                elif 'flat_flux' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['flat_flux']
                    _LOGGER.debug(f"Using flat_flux for flat view")
                else:
                    flux_data = self.processed_spectrum['log_flux']
                    _LOGGER.debug(f"Fallback to log_flux for flat view")
            else:
                # Return flux version
                if 'display_flux' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['display_flux']
                    _LOGGER.debug(f"Using display_flux for flux view")
                elif 'log_flux' in self.processed_spectrum and 'continuum' in self.processed_spectrum:
                    # Reconstruct flux from flat and continuum
                    flat_flux = self.processed_spectrum['log_flux']
                    continuum = self.processed_spectrum['continuum']
                    flux_data = (flat_flux + 1.0) * continuum
                    _LOGGER.debug(f"Reconstructed flux from flat+continuum for flux view")
                else:
                    flux_data = self.processed_spectrum['log_flux']
                    _LOGGER.debug(f"Fallback to log_flux for flux view")
            
            # CRITICAL: Apply zero padding filtering like the old GUI
            try:
                filtered_wave, filtered_flux = self._apply_zero_padding_filter(log_wave, flux_data, self.processed_spectrum)
                return filtered_wave, filtered_flux
            except Exception as e:
                _LOGGER.warning(f"Error applying zero padding filter: {e}")
                return log_wave, flux_data
        
        # Fallback to original spectrum for both views
        return self.original_wave, self.original_flux
    
    def get_current_file_path(self) -> Optional[str]:
        """Get current file path"""
        return self.current_file_path
    
    def set_processed_spectrum(self, processed_spectrum: Dict[str, Any]):
        """Set processed spectrum data"""
        self.processed_spectrum = processed_spectrum
        _LOGGER.debug("Processed spectrum data stored")
    
    def _apply_zero_padding_filter(self, wave, flux, processed_spectrum=None):
        """Filter out zero-padded regions from spectrum data
        
        Uses the nonzero region boundaries calculated during preprocessing.
        
        Parameters:
        -----------
        wave : array
            Wavelength array
        flux : array  
            Flux array
        processed_spectrum : dict, optional
            Processed spectrum dictionary containing edge information
            
        Returns:
        --------
        tuple : (filtered_wave, filtered_flux)
            Arrays with zero-padded regions removed
        """
        try:
            import numpy as np
            
            # If we have processed spectrum with edge information, use it
            if processed_spectrum and 'left_edge' in processed_spectrum and 'right_edge' in processed_spectrum:
                left_edge = processed_spectrum['left_edge']
                right_edge = processed_spectrum['right_edge']
                return wave[left_edge:right_edge+1], flux[left_edge:right_edge+1]
            
            # Fallback: find nonzero regions manually
            nonzero_mask = flux > 0
            if np.any(nonzero_mask):
                left_edge = np.argmax(nonzero_mask)
                right_edge = len(flux) - 1 - np.argmax(nonzero_mask[::-1])
                return wave[left_edge:right_edge+1], flux[left_edge:right_edge+1]
            
            # If no nonzero data found, return original arrays
            return wave, flux
            
        except Exception as e:
            _LOGGER.warning(f"Warning: Error filtering nonzero spectrum: {e}")
            return wave, flux
    
    def run_preprocessing(self, **kwargs) -> bool:
        """
        Run spectrum preprocessing with default or custom parameters
        
        Args:
            **kwargs: Preprocessing parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.original_wave is None or self.original_flux is None:
                _LOGGER.error("No spectrum data loaded for preprocessing")
                return False
            
            from snid_sage.snid.snid import preprocess_spectrum
            
            # Use file path if available, otherwise use wave/flux arrays
            if self.current_file_path:
                # Preprocess from file
                processed_spectrum, trace = preprocess_spectrum(
                    spectrum_path=self.current_file_path,
                    # Default parameters for quick preprocessing
                    savgol_window=kwargs.get('savgol_window', 0),
                    savgol_fwhm=kwargs.get('savgol_fwhm', 0.0),
                    savgol_order=kwargs.get('savgol_order', 3),
                    aband_remove=kwargs.get('aband_remove', False),
                    skyclip=kwargs.get('skyclip', False),
                    emclip_z=kwargs.get('emclip_z', -1.0),
                    emwidth=kwargs.get('emwidth', 40.0),
                    wavelength_masks=kwargs.get('wavelength_masks', []),
                    apodize_percent=kwargs.get('apodize_percent', 10.0),
                    skip_steps=kwargs.get('skip_steps', []),
                    verbose=kwargs.get('verbose', False)
                )
            else:
                # Preprocess from arrays
                processed_spectrum, trace = preprocess_spectrum(
                    wave=self.original_wave,
                    flux=self.original_flux,
                    skip_steps=kwargs.get('skip_steps', []),
                    verbose=kwargs.get('verbose', False)
                )
            
            # Store processed spectrum
            self.processed_spectrum = processed_spectrum
            self.preprocessing_trace = trace
            
            # Update workflow state
            self.update_workflow_state(WorkflowState.PREPROCESSED)
            
            # Emit signal for GUI update
            self.preprocessing_completed.emit(True)
            
            _LOGGER.info("Spectrum preprocessing completed successfully")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error during preprocessing: {e}")
            # Emit signal for GUI update
            self.preprocessing_completed.emit(False)
            return False
    
    # Analysis operations
    def run_analysis(self, **kwargs) -> bool:
        """
        Run SNID analysis
        
        Args:
            **kwargs: Analysis parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.original_wave is None or self.original_flux is None:
                _LOGGER.error("No spectrum data loaded for analysis")
                return False
            
            # Create progress dialog for analysis tracking (if not already created)
            try:
                from snid_sage.interfaces.gui.components.pyside6_dialogs.analysis_progress_dialog import show_analysis_progress_dialog
                
                # Create progress dialog on the main window only if one doesn't exist
                if self.main_window and (not hasattr(self.main_window, 'progress_dialog') or not self.main_window.progress_dialog):
                    self.main_window.progress_dialog = show_analysis_progress_dialog(
                        self.main_window, 
                        "SNID Analysis Progress"
                    )
                    self.main_window.progress_dialog.add_progress_line("Initializing SNID analysis...", "info")
                    _LOGGER.info("Progress dialog created for analysis")
                elif self.main_window and self.main_window.progress_dialog:
                    # Update existing progress dialog
                    self.main_window.progress_dialog.add_progress_line("Initializing SNID analysis...", "info")
                    _LOGGER.info("Using existing progress dialog for analysis")
                else:
                    _LOGGER.warning("Main window not available for progress dialog")
            except ImportError:
                # Fallback if progress dialog not available
                _LOGGER.warning("Analysis progress dialog not available")
            
            # Run analysis in separate thread
            self.analysis_thread = threading.Thread(
                target=self._run_analysis_thread, 
                args=(kwargs,)
            )
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error starting analysis: {e}")
            return False

    def run_snid_analysis(self, config_params: Dict[str, Any]) -> bool:
        """
        Run SNID analysis with configuration parameters
        
        Args:
            config_params: Dictionary of analysis configuration parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            _LOGGER.info(f"Starting SNID analysis with configuration: {config_params}")
            
            # Set current parameters on main GUI for parsing methods to access
            if hasattr(self, 'main_window'):
                self.main_window.current_type_filter = config_params.get('type_filter', None)
                self.main_window.current_template_filter = config_params.get('template_filter', None)
                self.main_window.current_age_range = config_params.get('age_range', None)
                _LOGGER.debug(f"Set GUI parameters: type_filter={self.main_window.current_type_filter}, "
                            f"template_filter={self.main_window.current_template_filter}, "
                            f"age_range={self.main_window.current_age_range}")
            
            return self.run_analysis(**config_params)
        except Exception as e:
            _LOGGER.error(f"Error starting SNID analysis with config: {e}")
            return False
    
    def _run_analysis_thread(self, analysis_kwargs):
        """Run SNID analysis in background thread"""
        try:
            self.analysis_running = True
            
            # Note: Removed matplotlib backend forcing to prevent OpenGL context issues in PySide6
            # The analysis runs purely with PyQtGraph for all plotting needs
            
            # Create progress callback function that safely updates GUI from thread
            def progress_callback(message: str, progress: float = None):
                """Progress callback to update GUI - thread-safe"""
                try:
                    # Log the progress message for debugging
                    _LOGGER.info(f"Analysis progress: {message} ({progress}%)")
                    
                    # Use Qt's thread-safe signal mechanism to update GUI
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        "_update_progress_from_thread",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, message),
                        QtCore.Q_ARG(float, progress or 0.0)
                    )
                except Exception as e:
                    _LOGGER.warning(f"Error in progress callback: {e}")
            
            # First, preprocess the spectrum if not already done
            if not hasattr(self, 'processed_spectrum') or self.processed_spectrum is None:
                progress_callback("Running preprocessing as part of analysis...")
                _LOGGER.info("Running preprocessing as part of analysis...")
                from snid_sage.snid.snid import preprocess_spectrum
                
                # Basic preprocessing with default parameters
                self.processed_spectrum, preprocessing_trace = preprocess_spectrum(
                    wave=self.original_wave,
                    flux=self.original_flux,
                    skip_steps=[],  # Include all preprocessing steps
                    verbose=False
                )
                progress_callback("Preprocessing completed", 10)
                _LOGGER.info("Preprocessing completed")
            
            # Get templates directory from configuration
            progress_callback("Loading configuration and templates...", 20)
            try:
                # Force garbage collection before template loading to clean up any widget remnants
                import gc
                gc.collect()
                
                if not hasattr(self, 'current_config') or not self.current_config:
                    from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
                    config_manager = ConfigurationManager()
                    self.current_config = config_manager.load_config()
                
                templates_dir = self.current_config['paths']['templates_dir']
                if not os.path.exists(templates_dir):
                    raise ValueError(f"Templates directory not found: {templates_dir}")
                
                # Additional defensive check: ensure template directory is accessible
                try:
                    test_files = os.listdir(templates_dir)
                    if not any(f.endswith('.hdf5') for f in test_files):
                        _LOGGER.warning(f"No HDF5 template files found in {templates_dir}")
                except PermissionError:
                    raise ValueError(f"Permission denied accessing templates directory: {templates_dir}")
                
                progress_callback(f"Templates loaded from: {templates_dir}", 30)
                _LOGGER.info(f"Running SNID analysis with templates from: {templates_dir}")
                
            except Exception as e:
                _LOGGER.error(f"Error during template loading setup: {e}")
                progress_callback(f"Error loading templates: {str(e)}", 30)
                raise
            
            # Run actual SNID analysis
            progress_callback("Starting SNID analysis engine...", 40)
            from snid_sage.snid.snid import run_snid_analysis
            
            # Determine redshift parameters from mode configuration
            forced_redshift = None
            zmin = analysis_kwargs.get('zmin', -0.01)
            zmax = analysis_kwargs.get('zmax', 1.0)
            
            # Check if we have redshift mode configuration (from redshift mode dialog)
            if hasattr(self, 'redshift_mode_config') and self.redshift_mode_config:
                mode_config = self.redshift_mode_config
                mode = mode_config.get('mode', 'search')
                redshift_value = mode_config.get('redshift', 0.0)
                
                if mode == 'force':
                    # Force exact redshift mode
                    forced_redshift = redshift_value
                    progress_callback(f"Using FORCED REDSHIFT: z = {forced_redshift:.6f}", 45)
                    _LOGGER.info(f"Using FORCED REDSHIFT analysis: z = {forced_redshift:.6f}")
                else:
                    # Search around redshift mode
                    search_range = mode_config.get('search_range', 0.001)
                    zmin = max(-0.01, redshift_value - search_range)
                    zmax = min(1.0, redshift_value + search_range)
                    progress_callback(f"Searching around z = {redshift_value:.6f} ± {search_range:.3f}", 45)
                    _LOGGER.info(f"Using SEARCH MODE around z = {redshift_value:.6f} (range: {zmin:.4f} to {zmax:.4f})")
            
            # Fallback to legacy manual_redshift if no mode config
            elif hasattr(self, 'manual_redshift') and self.manual_redshift:
                # Legacy behavior: manual_redshift is treated as forced
                forced_redshift = self.manual_redshift
                progress_callback(f"Using MANUAL REDSHIFT (legacy): z = {forced_redshift:.6f}", 45)
            
            # Check for forced_redshift parameter in analysis_kwargs (from config dialog)
            elif analysis_kwargs.get('forced_redshift') is not None:
                forced_redshift = analysis_kwargs.get('forced_redshift')
                progress_callback(f"Using CONFIG FORCED REDSHIFT: z = {forced_redshift:.6f}", 45)
                _LOGGER.info(f"Using config forced redshift: z = {forced_redshift:.6f}")
            
            else:
                # Pure automatic redshift determination
                progress_callback(f"Automatic redshift search (range: {zmin:.3f} to {zmax:.3f})", 45)
                _LOGGER.info(f"Using automatic redshift determination (range {zmin:.4f} to {zmax:.4f})")
            
            progress_callback("Running template correlation analysis...", 50)
            
            self.snid_results, self.analysis_trace = run_snid_analysis(
                processed_spectrum=self.processed_spectrum,
                templates_dir=templates_dir,
                # Analysis parameters
                zmin=zmin,
                zmax=zmax,
                age_range=analysis_kwargs.get('age_range', None),
                type_filter=analysis_kwargs.get('type_filter', None),
                template_filter=analysis_kwargs.get('template_filter', None),
                peak_window_size=analysis_kwargs.get('peak_window_size', 10),
                lapmin=analysis_kwargs.get('lapmin', 0.3),
                rlapmin=analysis_kwargs.get('rlapmin', 5.0),
                forced_redshift=forced_redshift,  # NEW: Pass forced redshift parameter
                max_output_templates=analysis_kwargs.get('max_output_templates', 10),
                verbose=analysis_kwargs.get('verbose', False),
                # Explicitly disable all plotting to prevent OpenGL context issues
                show_plots=False,
                save_plots=False,
                plot_dir=None,
                # REMOVED: output_plots parameter (doesn't exist in run_snid_analysis function)
                progress_callback=progress_callback  # Pass progress callback
            )
            
            progress_callback("Processing analysis results...", 90)
            
            if self.snid_results and hasattr(self.snid_results, 'best_matches'):
                self.max_templates = len(self.snid_results.best_matches)
                progress_callback(f"Found {self.max_templates} template matches", 95)
            else:
                self.max_templates = 0
                progress_callback("No template matches found", 95)
            
            # Check if we have GMM clustering results that need user selection
            if self._is_clustering_available(self.snid_results):
                # Store results temporarily and trigger cluster selection dialog
                progress_callback("GMM clustering found - preparing cluster selection...", 97)
                _LOGGER.info(f"🎯 Clustering available with {len(self.snid_results.clustering_results.get('all_candidates', []))} candidates")
                self.analysis_running = False
                
                # Emit signal to trigger cluster selection in main thread
                self.cluster_selection_needed.emit(self.snid_results)
                return
            else:
                _LOGGER.info("🔄 No clustering available or insufficient clusters - proceeding without cluster selection")
            
            # Complete analysis workflow directly if no clustering
            self._complete_analysis_workflow(self.snid_results)
            
            progress_callback("Analysis completed successfully!", 100)
            self.analysis_running = False
            
            # Emit signal for GUI update
            self.analysis_completed.emit(True)
            
            _LOGGER.info("SNID analysis completed successfully")
            
        except Exception as e:
            self.analysis_running = False
            self.snid_results = None
            
            # Enhanced error handling with specific context
            error_context = "analysis"
            
            # Check if this was a forced redshift error
            if hasattr(self, 'redshift_mode_config') and self.redshift_mode_config:
                mode_config = self.redshift_mode_config
                if mode_config.get('mode') == 'force':
                    forced_z = mode_config.get('redshift', 'unknown')
                    error_context = f"forced redshift analysis (z={forced_z})"
                    _LOGGER.error(f"Error in forced redshift analysis at z={forced_z}: {e}")
                else:
                    error_context = f"redshift search analysis"
                    _LOGGER.error(f"Error in redshift search analysis: {e}")
            elif analysis_kwargs.get('forced_redshift') is not None:
                forced_z = analysis_kwargs.get('forced_redshift')
                error_context = f"forced redshift analysis (z={forced_z})"
                _LOGGER.error(f"Error in forced redshift analysis at z={forced_z}: {e}")
            else:
                _LOGGER.error(f"Error in analysis thread: {e}")
            
            # Store error context for better GUI messaging
            self.last_analysis_error = {
                'error': str(e),
                'context': error_context,
                'type': 'forced_redshift' if 'forced redshift' in error_context else 'normal'
            }
            
            import traceback
            _LOGGER.debug(f"Analysis error traceback: {traceback.format_exc()}")
            
            # Emit signal for GUI update
            self.analysis_completed.emit(False)
    
    @QtCore.Slot(str, float)
    def _update_progress_from_thread(self, message: str, progress: float):
        """Update progress from analysis thread (called via Qt signal)"""
        try:
            self.progress_updated.emit(message, progress)
        except Exception as e:
            _LOGGER.warning(f"Error emitting progress update: {e}")
    
    def is_analysis_running(self) -> bool:
        """Check if analysis is currently running"""
        return self.analysis_running
    
    def get_analysis_results(self) -> Optional[Dict[str, Any]]:
        """Get current analysis results"""
        return self.snid_results
    
    # Template navigation
    def get_current_template_index(self) -> int:
        """Get current template index"""
        return self.current_template
    
    def get_max_templates(self) -> int:
        """Get maximum number of templates"""
        return self.max_templates
    
    def navigate_to_template(self, index: int) -> bool:
        """Navigate to specific template"""
        if 0 <= index < self.max_templates:
            self.current_template = index
            return True
        return False
    
    def next_template(self) -> bool:
        """Navigate to next template"""
        if self.current_template < self.max_templates - 1:
            self.current_template += 1
            return True
        return False
    
    def previous_template(self) -> bool:
        """Navigate to previous template"""
        if self.current_template > 0:
            self.current_template -= 1
            return True
        return False
    
    def next_template(self) -> bool:
        """Navigate to next template"""
        if self.current_template < self.max_templates - 1:
            self.current_template += 1
            return True
        return False
    
    # Masking operations
    def add_mask_region(self, min_wave: float, max_wave: float):
        """Add a mask region"""
        self.mask_regions.append([min_wave, max_wave])
        _LOGGER.debug(f"Added mask region: {min_wave:.1f} - {max_wave:.1f} Å")
    
    def clear_mask_regions(self):
        """Clear all mask regions"""
        self.mask_regions.clear()
        _LOGGER.debug("All mask regions cleared")
    
    def get_mask_regions(self) -> List[List[float]]:
        """Get current mask regions"""
        return self.mask_regions.copy()
    
    # Configuration operations
    def set_redshift(self, redshift: Optional[float]):
        """Set galaxy redshift"""
        self.galaxy_redshift_result = redshift
        if redshift is not None:
            self.update_workflow_state(WorkflowState.REDSHIFT_SET)
            _LOGGER.info(f"Redshift set to z = {redshift:.4f}")
        else:
            _LOGGER.info("Redshift cleared")
    
    def get_redshift(self) -> Optional[float]:
        """Get current redshift value"""
        return self.galaxy_redshift_result
    
    # Reset operations
    def reset_to_initial_state(self):
        """Reset application to initial state - comprehensive reset including persistent settings"""
        # Clear data
        self.current_file_path = None
        self.original_wave = None
        self.original_flux = None
        self.processed_spectrum = None
        self.snid_results = None
        self.galaxy_redshift_result = None
        self.analysis_results = None
        self.current_template = 0
        self.max_templates = 0
        self.mask_regions.clear()
        
        # Clear persistent settings that were previously missed
        if hasattr(self, 'redshift_mode_config'):
            self.redshift_mode_config = None
            
        if hasattr(self, 'manual_redshift'):
            self.manual_redshift = None
            
        if hasattr(self, 'forced_redshift'):
            self.forced_redshift = None
            
        # Clear auto cluster selection state
        if hasattr(self, 'auto_select_best_cluster'):
            self.auto_select_best_cluster = False
        
        # Reset current view state (important for button appearances)
        if hasattr(self, 'current_view'):
            self.current_view = 'flux'  # Reset to default view
        
        # Clear spectrum data variables that might persist
        if hasattr(self, 'spectrum_data'):
            self.spectrum_data = None
            
        # Clear any preprocessing state
        if hasattr(self, 'is_preprocessed'):
            self.is_preprocessed = False
        
        # Reset workflow state to INITIAL (this is critical)
        self.update_workflow_state(WorkflowState.INITIAL)
        
        _LOGGER.info("Application reset to initial state - all persistent settings and states cleared")
    
    # Clustering and cluster selection methods
    def _is_clustering_available(self, result):
        """Check if clustering results are available and valid"""
        try:
            if not hasattr(result, 'clustering_results') or not result.clustering_results:
                return False
                
            clustering_results = result.clustering_results
            
            # Check if clustering was successful
            if not clustering_results.get('success', False):
                return False
                
            # Check if we have multiple clusters to choose from
            all_candidates = clustering_results.get('all_candidates', [])
            if len(all_candidates) <= 1:
                return False
                
            # Verify clusters have required data
            for cluster in all_candidates:
                if not isinstance(cluster, dict) or not cluster.get('matches'):
                    return False
                    
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error checking clustering availability: {e}")
            return False
    
    def _complete_analysis_workflow(self, result):
        """Complete the analysis workflow after cluster selection (or if no clustering)"""
        try:
            # Update workflow state
            self.update_workflow_state(WorkflowState.ANALYSIS_COMPLETE)
            
            # Store results
            self.snid_results = result
            
            if result and hasattr(result, 'best_matches'):
                self.max_templates = len(result.best_matches)
                _LOGGER.info(f"Analysis completed with {self.max_templates} template matches")
            else:
                self.max_templates = 0
                _LOGGER.warning("Analysis completed but no template matches found")
            
            # THREADING FIX: Instead of directly calling GUI methods (which can be from background thread),
            # emit a signal to schedule GUI updates on the main thread
            if result and hasattr(result, 'success') and result.success:
                # Store the result for the signal handler to access
                self._pending_gui_update_result = result
                
                # Emit signal to trigger GUI updates on main thread (thread-safe)
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_handle_gui_updates_from_main_thread",
                    QtCore.Qt.QueuedConnection
                )
                
                _LOGGER.info(f"✅ Analysis complete: {getattr(result, 'consensus_type', 'Unknown')} at z={getattr(result, 'redshift', 0.0):.4f}")
            
        except Exception as e:
            _LOGGER.error(f"Error completing analysis workflow: {e}")
    
    @QtCore.Slot()
    def _handle_gui_updates_from_main_thread(self):
        """Handle GUI updates from the main thread (called via QueuedConnection)"""
        try:
            # Get the stored result
            result = getattr(self, '_pending_gui_update_result', None)
            if not result:
                _LOGGER.warning("No pending result for GUI updates")
                return
            
            # Clear the pending result
            self._pending_gui_update_result = None
            
            # Now safely call GUI update methods from the main thread
            gui_instance = getattr(self, 'main_window', getattr(self, 'gui', None))
            if gui_instance and hasattr(gui_instance, 'update_results_display'):
                gui_instance.update_results_display(result)
            
            if gui_instance and hasattr(gui_instance, 'enable_plot_navigation'):
                gui_instance.enable_plot_navigation()
            
            if gui_instance and hasattr(gui_instance, 'show_results_summary'):
                gui_instance.show_results_summary(result)
            
            # Update status
            cluster_info = ""
            if hasattr(result, 'clustering_results') and result.clustering_results:
                if result.clustering_results.get('user_selected_cluster'):
                    cluster_info = " [User Selected]"
                elif result.clustering_results.get('best_cluster'):
                    cluster_info = " [Auto Selected]"
            
            status_msg = f"✅ Best: {getattr(result, 'template_name', 'Unknown')} ({getattr(result, 'consensus_type', 'Unknown')}){cluster_info}"
            if gui_instance and hasattr(gui_instance, 'update_header_status'):
                gui_instance.update_header_status(status_msg)
            
            _LOGGER.debug("✅ GUI updates completed from main thread")
            
        except Exception as e:
            _LOGGER.error(f"Error handling GUI updates from main thread: {e}")
            
    def on_cluster_selected(self, selected_cluster, cluster_index, result):
        """Handle user's cluster selection from cluster selection dialog"""
        try:
            _LOGGER.info(f"🎯 User selected cluster {cluster_index + 1}: {selected_cluster.get('type', 'Unknown')}")
            
            # Update the clustering results with user's selection
            if hasattr(result, 'clustering_results'):
                result.clustering_results['user_selected_cluster'] = selected_cluster
                result.clustering_results['user_selected_index'] = cluster_index
                
                # DO NOT overwrite best_cluster - keep the original automatic best
                # This allows the formatter to distinguish between automatic and manual selection
            
            # CRITICAL: Filter best_matches to only show templates from selected cluster
            if hasattr(result, 'best_matches') and selected_cluster.get('matches'):
                cluster_matches = selected_cluster.get('matches', [])
                
                # Sort cluster matches by best available metric (RLAP-Cos if available, otherwise RLAP) descending
                try:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    cluster_matches_sorted = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
                except ImportError:
                    # Fallback sorting if math utils not available
                    cluster_matches_sorted = sorted(cluster_matches, 
                                                  key=lambda m: m.get('rlap_cos', m.get('rlap', 0)), 
                                                  reverse=True)
                
                # Update best_matches to only contain cluster templates
                max_templates = 10  # Default limit
                result.best_matches = cluster_matches_sorted[:max_templates]
                
                # Also update top_matches and filtered_matches for consistency
                result.top_matches = cluster_matches_sorted[:max_templates]
                result.filtered_matches = cluster_matches_sorted
                
                _LOGGER.info(f"🎯 Filtered templates: {len(cluster_matches)} cluster matches -> "
                            f"{len(result.best_matches)} displayed templates")
                
                # Update top-level result properties to reflect the best match from the selected cluster
                if cluster_matches_sorted:
                    best_cluster_match = cluster_matches_sorted[0]
                    template = best_cluster_match.get('template', {})
                    
                    # Update main result properties
                    result.template_name = template.get('name', 'Unknown')
                    result.consensus_type = template.get('type', 'Unknown')
                    result.redshift = best_cluster_match.get('redshift', 0.0)
                    result.rlap = best_cluster_match.get('rlap', 0.0)
                    
                    # Update RLAP-Cos if available
                    if 'rlap_cos' in best_cluster_match:
                        result.rlap_cos = best_cluster_match.get('rlap_cos', 0.0)
                    
                    _LOGGER.info(f"🎯 Updated result properties: {result.template_name} ({result.consensus_type}) "
                                f"z={result.redshift:.4f}, RLAP={result.rlap:.2f}")
            
            _LOGGER.info(f"✅ User selected cluster {cluster_index + 1}: {selected_cluster.get('type')} "
                        f"(Size: {len(selected_cluster.get('matches', []))}, "
                        f"Quality: {selected_cluster.get('mean_rlap', 0):.2f})")
            
            # Complete the analysis workflow
            self._complete_analysis_workflow(result)
            
            # Emit signal for GUI update
            self.analysis_completed.emit(True)
            
        except Exception as e:
            _LOGGER.error(f"Error handling cluster selection: {e}")
            import traceback
            _LOGGER.debug(f"Cluster selection error traceback: {traceback.format_exc()}")
            
            # Still complete the workflow even if there was an error
            self._complete_analysis_workflow(result)
            self.analysis_completed.emit(True)