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
from snid_sage.snid.preprocessing import enforce_positive_flux
from snid_sage.shared.exceptions.core_exceptions import SpectrumProcessingError

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
    """Workflow state enumeration"""
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
    # New: strictly ordered progress updates (seq, message, progress)
    ordered_progress_updated = QtCore.Signal(int, str, float)
    cluster_selection_needed = QtCore.Signal(object)  # SNID result with clustering
    
    def __init__(self, main_window, profile_id: Optional[str] = None):
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
        # Cancellation control for analysis thread
        self.cancel_event = threading.Event()
        self.analysis_cancelled = False
        
        # Interactive state
        self.current_template = 0
        self.max_templates = 0
        self.manual_redshift = None
        
        # Auto cluster selection flag for extended quick workflow
        self.auto_select_best_cluster = False
        
        # Data storage
        self.spectrum_data = None
        self.analysis_results = None

        # Ordered progress state
        self._progress_seq_counter = 0
        self._next_expected_seq = 1
        self._pending_progress_by_seq = {}

        # Remember params used for the last analysis run (e.g., max_output_templates)
        self.last_analysis_kwargs = {}

        # Active processing profile for this GUI session (CLI-only; ignore config/env)
        try:
            self.active_profile_id = (str(profile_id).strip().lower() if profile_id else 'optical')
        except Exception:
            self.active_profile_id = 'optical'
        
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

    def _resolve_templates_directory(self, profile_id: Optional[str] = None) -> str:
        """Resolve a reliable templates directory, preferring the lazy-downloaded bank.
    
        Strategy:
        - Prefer the centralized templates manager (lazy download into a writable cache).
        - If a configured templates_dir exists and looks complete, honor it instead.
        - Final fallbacks are only used in dev environments.
        """
        try:
            active_pid = (profile_id or getattr(self, 'active_profile_id', None) or 'optical')
            active_pid = str(active_pid).strip().lower() or 'optical'

            # 1) Check configured directory for completeness
            try:
                cfg_dir = None
                try:
                    cfg_dir = self.current_config['paths']['templates_dir'] if (hasattr(self, 'current_config') and self.current_config) else None
                except Exception:
                    cfg_dir = None
                if cfg_dir:
                    cfg_path = Path(cfg_dir)
                    if cfg_path.exists() and cfg_path.is_dir():
                        idx_path = cfg_path / 'template_index.json'
                        # Quick completeness check: prefer index when present; else count HDF5 files
                        complete = False
                        if idx_path.exists():
                            try:
                                with open(idx_path, 'r', encoding='utf-8') as f:
                                    idx = json.load(f)
                                by_type = (idx or {}).get('by_type') or {}
                                # Consider complete if more than one type is present (optical should have many)
                                # For ONIR, also accept when at least one non-Ia type exists
                                if isinstance(by_type, dict) and len(by_type.keys()) >= (1 if active_pid == 'onir' else 2):
                                    complete = True
                            except Exception:
                                complete = False
                        else:
                            try:
                                h5_count = sum(1 for _ in cfg_path.glob('templates_*.hdf5'))
                                # Treat as complete if multiple type files exist (heuristic)
                                if h5_count >= (1 if active_pid == 'onir' else 3):
                                    complete = True
                            except Exception:
                                complete = False
                        if complete:
                            return str(cfg_path)
            except Exception:
                pass

            # 2) Prefer centralized templates manager (lazy download + cache)
            try:
                from snid_sage.shared.templates_manager import get_templates_dir

                managed_dir = get_templates_dir()
                _LOGGER.info(f"Using managed templates directory: {managed_dir}")
                return str(managed_dir)
            except Exception:
                pass

            # 3) Fallback: simple template finder (optical)
            try:
                from snid_sage.shared.utils.simple_template_finder import find_templates_directory
                found = find_templates_directory()
                if found:
                    _LOGGER.info(f"Using discovered templates directory: {found}")
                    return str(found)
            except Exception:
                pass

            # 4) Last resort: repo-relative defaults by profile
            repo_fallback = (Path(__file__).resolve().parents[3] / 'templates')
            return str(repo_fallback)
        except Exception as e:
            _LOGGER.warning(f"Failed to resolve templates directory robustly: {e}")
            # Preserve previous behavior if resolution fails entirely
            try:
                return str(self.current_config['paths']['templates_dir'])
            except Exception:
                return 'templates'
    
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
    def load_spectrum_file(self, file_path: str, *, offer_profile_switch: bool = True) -> bool:
        """
        Load spectrum data from file using robust spectrum loader
        
        Args:
            file_path: Path to spectrum file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            _LOGGER.info(f"🔄 Loading spectrum file: {file_path}")

            # Helper: ensure a failed/aborted load does not leave the app thinking a spectrum exists.
            # This prevents the GUI from prompting to "overwrite" an actually-empty plot/state.
            def _clear_failed_load_state() -> None:
                try:
                    self.current_file_path = None
                    self.original_wave = None
                    self.original_flux = None
                    self.flux_offset = 0.0
                    # Best-effort: move back to INITIAL (do not assume caller reset state)
                    try:
                        self.update_workflow_state(WorkflowState.INITIAL)
                    except Exception:
                        pass
                except Exception:
                    pass
            
            # Use the robust spectrum loader from shared utilities
            from snid_sage.shared.utils.data_io.spectrum_loader import load_spectrum

            # Store the file path early so profile-switch workflows can reload the same file.
            # We will clear it again if *any* validation fails.
            self.current_file_path = file_path

            # Load into local variables first; do not commit to controller state until validated.
            wave, flux = load_spectrum(file_path)

            # Ensure flux is strictly positive for downstream SNID preprocessing/continuum.
            flux_offset = 0.0
            try:
                shifted_flux, flux_offset = enforce_positive_flux(flux)
                flux = shifted_flux
            except Exception as e:
                _LOGGER.warning(f"Positive-flux enforcement failed at load stage ({e}); proceeding with raw flux")
                flux_offset = 0.0

            _LOGGER.info(f"✅ Spectrum file parsed successfully: {file_path}")
            _LOGGER.info(f"✅ Spectrum data: {len(wave)} points, "
                        f"wavelength range {wave[0]:.1f}-{wave[-1]:.1f} Å")
            _LOGGER.info(f"✅ Flux range: {np.min(flux):.2e} to {np.max(flux):.2e}")
            if float(flux_offset) != 0.0:
                _LOGGER.info(
                    "✅ Applied flux offset of %.6g at load stage to remove non-positive values "
                    "before any preprocessing or continuum fitting",
                    float(flux_offset),
                )
            
            # Early grid range check based on active profile (optical or onir)
            try:
                # Use the GUI session's active profile (set at launch); avoid env/config mismatch
                active_pid = (getattr(self, 'active_profile_id', None) or 'optical')

                # Get profile grid
                try:
                    from snid_sage.shared.profiles.builtins import register_builtins
                    from snid_sage.shared.profiles.registry import get_profile
                    register_builtins()
                    prof = get_profile(active_pid)
                    gmin = float(getattr(prof.grid, 'min_wave_A', 2500.0))
                    gmax = float(getattr(prof.grid, 'max_wave_A', 10000.0))
                except Exception:
                    gmin, gmax = 2500.0, 10000.0

                wmin = float(np.min(wave))
                wmax = float(np.max(wave))

                # Offer ONIR profile when using optical and spectrum extends well beyond optical
                suppress_clip_info = False
                try:
                    if (
                        str(active_pid).strip().lower() == 'optical'
                        and bool(offer_profile_switch)
                        and wmax > 12000.0
                    ):
                        try:
                            dlg = QtWidgets.QMessageBox(self.main_window)
                            dlg.setIcon(QtWidgets.QMessageBox.Question)
                            dlg.setWindowTitle("Better profile available")
                            dlg.setText(
                                (
                                    "This spectrum extends beyond 12000 Å and matches the ONIR profile better.\n\n"
                                    "Switch to ONIR (enables redshift up to 2.5 and ~2000–25000 Å) and reload, or clip to optical and continue?"
                                )
                            )
                            switch_btn = dlg.addButton("Switch to ONIR", QtWidgets.QMessageBox.AcceptRole)
                            clip_btn = dlg.addButton("Clip in Optical", QtWidgets.QMessageBox.YesRole)
                            cancel_btn = dlg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
                            dlg.setDefaultButton(switch_btn)
                            dlg.exec()

                            clicked = dlg.clickedButton()
                            if clicked is switch_btn:
                                # Hand off to profile switching; it will reset/reload as needed.
                                return self.switch_active_profile('onir', reload_current_file=True, show_notice=True)
                            elif clicked is clip_btn:
                                # User explicitly requested clipping to the **optical** grid.
                                # Clip the *loaded* spectrum immediately so:
                                #   - The main GUI plot only shows the optical range
                                #   - Advanced preprocessing starts from the clipped range
                                #   - All downstream normalization/log-rebin steps see only optical data
                                try:
                                    import numpy as _np
                                    w_arr = _np.asarray(wave, dtype=float)
                                    f_arr = _np.asarray(flux, dtype=float)
                                    clip_mask = (w_arr >= gmin) & (w_arr <= gmax)
                                    if _np.any(clip_mask):
                                        w_clipped = w_arr[clip_mask]
                                        f_clipped = f_arr[clip_mask]
                                        wave = w_clipped
                                        flux = f_clipped
                                        # Recompute bounds for subsequent overlap checks and logging
                                        wmin = float(_np.min(w_clipped))
                                        wmax = float(_np.max(w_clipped))
                                        _LOGGER.info(
                                            "User selected 'Clip in Optical' – spectrum clipped at load "
                                            "to %.1f–%.1f Å inside grid %.0f–%.0f Å (profile: %s)",
                                            wmin, wmax, gmin, gmax, active_pid,
                                        )
                                    else:
                                        _LOGGER.warning(
                                            "User selected 'Clip in Optical' but no samples fall within "
                                            "grid %.0f–%.0f Å; keeping full wavelength range",
                                            gmin, gmax,
                                        )
                                except Exception as clip_err:
                                    _LOGGER.warning(f"Failed to clip spectrum to optical grid at load: {clip_err}")
                                suppress_clip_info = True
                            else:
                                _clear_failed_load_state()
                                return False
                        except Exception:
                            # If dialog fails, continue with default behavior
                            pass
                except Exception:
                    pass

                has_overlap = (wmax >= gmin) and (wmin <= gmax)
                if not has_overlap:
                    QtWidgets.QMessageBox.critical(
                        self.main_window,
                        "Spectrum Out of Range",
                        (
                            f"The loaded spectrum range {wmin:.1f}-{wmax:.1f} Å is outside "
                            f"the active grid {gmin:.0f}-{gmax:.0f} Å (profile: {active_pid})."
                        ),
                    )
                    _clear_failed_load_state()
                    return False
                # Enforce minimum overlap of 2000 Å with active grid
                overlap_angstrom = max(0.0, min(wmax, gmax) - max(wmin, gmin))
                if overlap_angstrom < 2000.0:
                    suggestion = ""
                    try:
                        if str(active_pid).strip().lower() != 'onir':
                            from snid_sage.shared.profiles.builtins import register_builtins
                            from snid_sage.shared.profiles.registry import get_profile
                            register_builtins()
                            onir_prof = get_profile('onir')
                            onir_min = float(getattr(onir_prof.grid, 'min_wave_A', 2000.0))
                            onir_max = float(getattr(onir_prof.grid, 'max_wave_A', 25000.0))
                            onir_overlap = max(0.0, min(wmax, onir_max) - max(wmin, onir_min))
                            if onir_overlap >= 2000.0:
                                suggestion = (
                                    f" Tip: the spectrum overlaps the ONIR grid by {onir_overlap:.1f} Å; "
                                    f"consider using the ONIR profile for extended coverage (~2000–25000 Å)."
                                )
                    except Exception:
                        pass
                    QtWidgets.QMessageBox.critical(
                        self.main_window,
                        "Insufficient Overlap",
                        (
                            f"The spectrum overlaps the active grid by only {overlap_angstrom:.1f} Å, "
                            f"which is insufficient (< 2000 Å)." + suggestion
                        ),
                    )
                    _clear_failed_load_state()
                    return False
                if (wmin < gmin) or (wmax > gmax):
                    if not suppress_clip_info:
                        QtWidgets.QMessageBox.information(
                            self.main_window,
                            "Spectrum Will Be Clipped",
                            (
                                f"The spectrum extends beyond the active grid {gmin:.0f}-{gmax:.0f} Å (profile: {active_pid}).\n"
                                f"It will be clipped to the grid during preprocessing."
                            ),
                        )
            except Exception:
                pass

            # Commit validated spectrum state
            try:
                self.original_wave = np.asarray(wave, dtype=float)
                self.original_flux = np.asarray(flux, dtype=float)
            except Exception:
                # Fall back (should be rare; loader already returns arrays)
                self.original_wave = wave
                self.original_flux = flux
            self.flux_offset = float(flux_offset)

            # Update workflow state
            self.update_workflow_state(WorkflowState.FILE_LOADED)
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"❌ Error loading spectrum file: {e}")
            import traceback
            traceback.print_exc()
            try:
                # Never leave partial spectrum state on hard failure
                self.current_file_path = None
                self.original_wave = None
                self.original_flux = None
                self.flux_offset = 0.0
                try:
                    self.update_workflow_state(WorkflowState.INITIAL)
                except Exception:
                    pass
            except Exception:
                pass
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
                # Simplified preferred key
                if 'flat_view' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['flat_view']
                    _LOGGER.debug(f"Using flat_view for flat view")
                elif 'display_flat' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['display_flat']
                    _LOGGER.debug(f"Using display_flat for flat view")
                elif 'tapered_flux' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['tapered_flux']
                    _LOGGER.debug(f"Using tapered_flux for flat view")
                elif 'flat_flux' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['flat_flux']
                    _LOGGER.debug(f"Using flat_flux for flat view")
                else:
                    flux_data = self.processed_spectrum.get('log_flux')
                    _LOGGER.debug(f"Fallback to log_flux for flat view")
            else:
                # Prefer reconstructing from apodized flat + continuum only when a continuum fit exists
                if (
                    self.processed_spectrum.get('has_continuum') is True
                    and 'tapered_flux' in self.processed_spectrum
                    and 'continuum' in self.processed_spectrum
                ):
                    tapered_flat = self.processed_spectrum['tapered_flux']
                    continuum = self.processed_spectrum['continuum']
                    recon_continuum = continuum.copy()
                    try:
                        nz = (recon_continuum > 0).nonzero()[0]
                        if nz.size:
                            c0, c1 = int(nz[0]), int(nz[-1])
                            if c0 > 0:
                                recon_continuum[:c0] = recon_continuum[c0]
                            if c1 < recon_continuum.size - 1:
                                recon_continuum[c1+1:] = recon_continuum[c1]
                    except Exception:
                        pass
                    flux_data = (tapered_flat + 1.0) * recon_continuum
                    _LOGGER.debug(f"Reconstructed flux from tapered_flat + extended continuum for flux view (preferred)")
                elif 'flux_view' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['flux_view']
                    _LOGGER.debug(f"Using flux_view (apodized) for flux view")
                elif 'display_flux' in self.processed_spectrum:
                    flux_data = self.processed_spectrum['display_flux']
                    _LOGGER.debug(f"Using display_flux for flux view")
                else:
                    # Final fallback to scaled log_flux (may include negatives if present)
                    flux_data = self.processed_spectrum.get('log_flux')
                    _LOGGER.debug(f"Fallback to log_flux for flux view")
            
            # Apply zero padding filtering
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
        # Keep a best-effort record of the preprocessing parameters that produced this spectrum.
        # This is used by the analysis-thread fallback path when preprocessing wasn't explicitly run.
        try:
            if not hasattr(self, "last_preprocessing_kwargs") or self.last_preprocessing_kwargs is None:
                self.last_preprocessing_kwargs = {}
        except Exception:
            self.last_preprocessing_kwargs = {}
    
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
            
            # Fallback: find valid regions manually (including negative values for continuum-subtracted spectra)
            valid_mask = (flux != 0) & np.isfinite(flux)
            if np.any(valid_mask):
                left_edge = np.argmax(valid_mask)
                right_edge = len(flux) - 1 - np.argmax(valid_mask[::-1])
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
                try:
                    processed_spectrum, trace = preprocess_spectrum(
                        spectrum_path=self.current_file_path,
                        # Default parameters for quick preprocessing
                        savgol_window=kwargs.get('savgol_window', 0),
                        savgol_order=kwargs.get('savgol_order', 3),
                        aband_remove=kwargs.get('aband_remove', False),
                        skyclip=kwargs.get('skyclip', False),
                        emclip_z=kwargs.get('emclip_z', -1.0),
                        emwidth=kwargs.get('emwidth', 40.0),
                        wavelength_masks=kwargs.get('wavelength_masks', []),
                        apodize_percent=kwargs.get('apodize_percent', 10.0),
                        skip_steps=kwargs.get('skip_steps', []),
                        verbose=kwargs.get('verbose', False),
                        clip_to_grid=True,
                        profile_id=self.active_profile_id
                    )
                except SpectrumProcessingError as e:
                    QtWidgets.QMessageBox.critical(self.main_window, "Preprocessing Error", str(e))
                    return False
            else:
                # Preprocess from arrays using input_spectrum API
                try:
                    processed_spectrum, trace = preprocess_spectrum(
                        input_spectrum=(self.original_wave, self.original_flux),
                        skip_steps=kwargs.get('skip_steps', []),
                        verbose=kwargs.get('verbose', False),
                        clip_to_grid=True,
                        profile_id=self.active_profile_id
                    )
                except SpectrumProcessingError as e:
                    QtWidgets.QMessageBox.critical(self.main_window, "Preprocessing Error", str(e))
                    return False
            
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
            
            # Prevent concurrent analysis runs
            try:
                already_running = bool(self.is_analysis_running()) or (
                    self.analysis_thread is not None and getattr(self.analysis_thread, 'is_alive', lambda: False)()
                )
            except Exception:
                already_running = False
            
            if already_running:
                _LOGGER.warning("Analysis start requested while another analysis is running - ignoring")
                try:
                    # Prefer progress dialog line if available
                    if getattr(self, 'main_window', None) and getattr(self.main_window, 'progress_dialog', None):
                        self.main_window.progress_dialog.add_progress_line(
                            "Analysis already running; please wait or cancel the current run.", "warning"
                        )
                    elif getattr(self, 'main_window', None):
                        QtWidgets.QMessageBox.information(
                            self.main_window,
                            "Analysis In Progress",
                            "An analysis is already running. Please wait for it to finish or cancel it."
                        )
                except Exception:
                    pass
                return False
            
            # Create progress dialog for analysis tracking (if not already created)
            try:
                from snid_sage.interfaces.gui.components.pyside6_dialogs.analysis_progress_dialog import show_analysis_progress_dialog
                
                # Create progress dialog on the main window only if one doesn't exist
                if self.main_window and (not hasattr(self.main_window, 'progress_dialog') or not self.main_window.progress_dialog):
                    self.main_window.progress_dialog = show_analysis_progress_dialog(
                        self.main_window, 
                        "SNID-SAGE Analysis Progress"
                    )
                    self.main_window.progress_dialog.add_progress_line("Initializing SNID-SAGE analysis...", "info")
                    _LOGGER.info("Progress dialog created for analysis")
                elif self.main_window and self.main_window.progress_dialog:
                    # Reuse existing progress dialog, ensuring it is visible
                    dlg = self.main_window.progress_dialog
                    try:
                        # If the dialog was previously hidden/closed, bring it back
                        if hasattr(dlg, 'isVisible') and not dlg.isVisible():
                            if hasattr(dlg, 'show_dialog'):
                                dlg.show_dialog()
                            else:
                                dlg.show()
                        else:
                            # Ensure it comes to the front
                            try:
                                dlg.raise_()
                                dlg.activateWindow()
                            except Exception:
                                pass
                        dlg.add_progress_line("Initializing SNID-SAGE analysis...", "info")
                        _LOGGER.info("Using existing progress dialog for analysis")
                    except Exception:
                        # If reusing fails for any reason, create a fresh dialog
                        self.main_window.progress_dialog = show_analysis_progress_dialog(
                            self.main_window,
                            "SNID-SAGE Analysis Progress"
                        )
                        self.main_window.progress_dialog.add_progress_line("Initializing SNID-SAGE analysis...", "info")
                        _LOGGER.info("Progress dialog recreated for analysis")
                else:
                    _LOGGER.warning("Main window not available for progress dialog")

                # Wire up Cancel button from the progress dialog to controller cancellation
                if self.main_window and getattr(self.main_window, 'progress_dialog', None):
                    try:
                        # Avoid duplicate connections by tagging the dialog
                        if not hasattr(self.main_window.progress_dialog, '_cancel_connected'):
                            self.main_window.progress_dialog.cancel_requested.connect(self.cancel_analysis)
                            setattr(self.main_window.progress_dialog, '_cancel_connected', True)
                            _LOGGER.debug("Connected progress dialog cancel signal to controller")
                    except Exception as e:
                        _LOGGER.warning(f"Unable to connect cancel signal: {e}")
            except ImportError:
                # Fallback if progress dialog not available
                _LOGGER.warning("Analysis progress dialog not available")
            
            # Reset cancellation state before starting
            self.cancel_event.clear()
            self.analysis_cancelled = False

            # Remember last-used analysis parameters for downstream UI logic (e.g., cluster trimming)
            try:
                self.last_analysis_kwargs = dict(kwargs) if kwargs is not None else {}
            except Exception:
                self.last_analysis_kwargs = {}

            # Run analysis in separate thread
            # Set running flag early to avoid race conditions from rapid clicks
            self.analysis_running = True
            self.analysis_thread = threading.Thread(
                target=self._run_analysis_thread, 
                args=(kwargs,)
            )
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error starting analysis: {e}")
            # Ensure running flag is reset on failure to start
            self.analysis_running = False
            return False

    # Public helper to post a sequenced progress message from the GUI/main thread
    def post_progress(self, message: str, progress: float = 0.0) -> None:
        try:
            self._enqueue_ordered_progress_from_thread(message or "", float(progress or 0.0))
        except Exception as e:
            _LOGGER.debug(f"post_progress failed: {e}")

    def run_snid_analysis(self, config_params: Dict[str, Any]) -> bool:
        """
        Run SNID analysis with configuration parameters
        
        Args:
            config_params: Dictionary of analysis configuration parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            _LOGGER.info(f"Starting SNID-SAGE analysis with configuration: {config_params}")
            
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

            # Ensure last_analysis_kwargs is available even if run_analysis wasn't the entrypoint
            try:
                if not getattr(self, 'last_analysis_kwargs', None):
                    self.last_analysis_kwargs = dict(analysis_kwargs) if analysis_kwargs is not None else {}
            except Exception:
                pass
            
            # Use PyQtGraph for all plotting needs to prevent OpenGL context issues
            
            # Create progress callback function that safely updates GUI from thread
            def progress_callback(message: str, progress: float = None):
                """Progress callback to update GUI - thread-safe"""
                try:
                    # Respect cancellation as early as possible
                    if self.cancel_event.is_set():
                        raise InterruptedError("Analysis cancelled by user")

                    # Log only meaningful progress updates to avoid noise
                    if (message and message.strip()) or (progress is not None):
                        _LOGGER.info(f"Analysis progress: {message} ({progress}%)")

                    # Skip UI updates when both message and progress are empty/None
                    if (not message or not message.strip()) and (progress is None):
                        return
                    
                    # Use Qt's thread-safe signal mechanism to update GUI
                    # Allocate a strictly increasing sequence number here in the worker thread
                    # Use a small critical section via invokeMethod to increment atomically on the GUI thread
                    QtCore.QMetaObject.invokeMethod(
                        self,
                        "_enqueue_ordered_progress_from_thread",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, message),
                        QtCore.Q_ARG(float, float(progress) if progress is not None else 0.0)
                    )
                except InterruptedError:
                    # Propagate cancellation without logging warnings
                    raise
                except Exception as e:
                    # Non-fatal UI update error; log at debug to avoid noise
                    _LOGGER.debug(f"Non-fatal progress callback issue: {e}")
            
            # Early cancellation check
            if self.cancel_event.is_set():
                raise InterruptedError("Analysis cancelled by user")

            # First, preprocess the spectrum if not already done
            if not hasattr(self, 'processed_spectrum') or self.processed_spectrum is None:
                progress_callback("Running preprocessing as part of analysis...")
                _LOGGER.info("Running preprocessing as part of analysis...")
                from snid_sage.snid.snid import preprocess_spectrum

                # Use last-used GUI preprocessing parameters when available; fall back to safe defaults.
                try:
                    pp = getattr(self, "last_preprocessing_kwargs", None) or {}
                except Exception:
                    pp = {}
                try:
                    savgol_window = int(pp.get("savgol_window", 0) or 0)
                except Exception:
                    savgol_window = 0
                try:
                    savgol_order = int(pp.get("savgol_order", 3) or 3)
                except Exception:
                    savgol_order = 3
                try:
                    aband_remove = bool(pp.get("aband_remove", False))
                except Exception:
                    aband_remove = False
                try:
                    skyclip = bool(pp.get("skyclip", False))
                except Exception:
                    skyclip = False
                try:
                    emclip_z = float(pp.get("emclip_z", -1.0))
                except Exception:
                    emclip_z = -1.0
                try:
                    emwidth = float(pp.get("emwidth", 40.0))
                except Exception:
                    emwidth = 40.0
                try:
                    wavelength_masks = pp.get("wavelength_masks", []) or []
                except Exception:
                    wavelength_masks = []
                try:
                    apodize_percent = float(pp.get("apodize_percent", 10.0))
                except Exception:
                    apodize_percent = 10.0

                self.processed_spectrum, preprocessing_trace = preprocess_spectrum(
                    input_spectrum=(self.original_wave, self.original_flux),
                    savgol_window=savgol_window,
                    savgol_order=savgol_order,
                    aband_remove=aband_remove,
                    skyclip=skyclip,
                    emclip_z=emclip_z,
                    emwidth=emwidth,
                    wavelength_masks=wavelength_masks,
                    apodize_percent=apodize_percent,
                    skip_steps=[],  # Include all preprocessing steps
                    verbose=False,
                    clip_to_grid=True,
                    profile_id=self.active_profile_id
                )
                progress_callback("Preprocessing completed", 10)
                _LOGGER.info("Preprocessing completed")
            
            # Cancellation check after preprocessing
            if self.cancel_event.is_set():
                raise InterruptedError("Analysis cancelled by user")

            # Get templates directory from configuration
            progress_callback("Loading configuration and templates...", 15)
            try:
                # Force garbage collection before template loading
                import gc
                gc.collect()
                
                if not hasattr(self, 'current_config') or not self.current_config:
                    from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
                    config_manager = ConfigurationManager()
                    self.current_config = config_manager.load_config()

                # Resolve a robust templates directory (avoids partial/incorrect config paths)
                templates_dir = self._resolve_templates_directory(profile_id=self.active_profile_id)
                if not os.path.exists(templates_dir):
                    raise ValueError(f"Templates directory not found: {templates_dir}")
                # Ensure directory looks valid at a glance
                try:
                    idx_ok = os.path.exists(os.path.join(templates_dir, 'template_index.json'))
                    any_h5 = any(fname.endswith('.hdf5') for fname in os.listdir(templates_dir))
                    if not (idx_ok or any_h5):
                        _LOGGER.warning(f"Templates directory appears incomplete: {templates_dir}")
                except PermissionError:
                    raise ValueError(f"Permission denied accessing templates directory: {templates_dir}")
                
                progress_callback(f"Templates loaded from: {templates_dir}", 20)
                _LOGGER.info(f"Running SNID analysis with templates from: {templates_dir}")
                
            except Exception as e:
                _LOGGER.error(f"Error during template loading setup: {e}")
                progress_callback(f"Error loading templates: {str(e)}", 30)
                raise
            
            # Cancellation check before starting analysis engine
            if self.cancel_event.is_set():
                raise InterruptedError("Analysis cancelled by user")

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
                    # Profile-aware cap: ONIR allows higher z (2.5) than optical (1.0)
                    try:
                        # Use the GUI session's active profile directly
                        active_pid_for_cap = getattr(self, 'active_profile_id', None) or 'optical'
                        cap_zmax = 2.5 if str(active_pid_for_cap).lower() == 'onir' else 1.0
                    except Exception:
                        cap_zmax = 1.0
                    zmax = min(cap_zmax, redshift_value + search_range)
                    progress_callback(f"Searching around z = {redshift_value:.6f} ± {search_range:.6f}", 45)
                    _LOGGER.info(f"Using SEARCH MODE around z = {redshift_value:.6f} (range: {zmin:.4f} to {zmax:.4f})")
            
            # Fallback to manual_redshift if no mode config
            elif hasattr(self, 'manual_redshift') and self.manual_redshift:
                # manual_redshift is treated as forced
                forced_redshift = self.manual_redshift
                progress_callback(f"Using MANUAL REDSHIFT: z = {forced_redshift:.6f}", 45)
            
            # Check for forced_redshift parameter in analysis_kwargs (from config dialog)
            elif analysis_kwargs.get('forced_redshift') is not None:
                forced_redshift = analysis_kwargs.get('forced_redshift')
                progress_callback(f"Using CONFIG FORCED REDSHIFT: z = {forced_redshift:.6f}", 45)
                _LOGGER.info(f"Using config forced redshift: z = {forced_redshift:.6f}")
            
            else:
                # Pure automatic redshift determination
                # Align displayed range with profile-aware extension used in the engine (e.g., ONIR uses zmax=2.5)
                active_pid_for_msg = (self.active_profile_id or 'optical')
                if str(active_pid_for_msg).lower() == 'onir' and zmax < 2.5:
                    zmax = 2.5
                progress_callback(f"Automatic redshift search (range: {zmin:.6f} to {zmax:.6f})", 45)
                _LOGGER.info(f"Using automatic redshift determination (range {zmin:.4f} to {zmax:.4f})")
            
            progress_callback("Running template correlation analysis...", 50)
            
            # Resolve active profile strictly from GUI session (CLI-only; ignore config/env)
            active_profile_id = self.active_profile_id

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
                hsigma_lap_ccc_threshold=float(analysis_kwargs.get('hsigma_lap_ccc_threshold', 1.5)),
                forced_redshift=forced_redshift,  # NEW: Pass forced redshift parameter
                max_output_templates=analysis_kwargs.get('max_output_templates', 10),
                verbose=analysis_kwargs.get('verbose', False),
                # Explicitly disable all plotting to prevent OpenGL context issues
                show_plots=False,
                save_plots=False,
                plot_dir=None,
                # REMOVED: output_plots parameter (doesn't exist in run_snid_analysis function)
                progress_callback=progress_callback,  # Pass progress callback (enforces cancellation)
                profile_id=active_profile_id
            )
            
            progress_callback("Processing analysis results...", 90)

            # Verbose logging of error (unbiased weighted SD) for cluster and winning subtype (if available)
            try:
                if analysis_kwargs.get('verbose', False) and hasattr(self, 'snid_results') and self.snid_results:
                    clres = getattr(self.snid_results, 'clustering_results', None)
                    if clres and clres.get('success'):
                        winning_cluster = clres.get('user_selected_cluster') or clres.get('best_cluster')
                        if winning_cluster:
                            matches = winning_cluster.get('matches', []) or []
                            # Cluster-level
                            from snid_sage.shared.utils.math_utils import get_best_metric_value, weighted_redshift_error
                            redshifts_with_errors = []
                            redshift_errors = []
                            metric_values = []
                            for m in matches:
                                z = m.get('redshift')
                                z_err = m.get('sigma_z', float('nan'))
                                if z is not None and np.isfinite(z) and np.isfinite(z_err) and z_err > 0:
                                    redshifts_with_errors.append(float(z))
                                    redshift_errors.append(float(z_err))
                                    try:
                                        metric_values.append(float(get_best_metric_value(m)))
                                    except Exception:
                                        metric_values.append(float(m.get('hlap', 0.0) or 0.0))
                            if redshifts_with_errors:
                                z_err = weighted_redshift_error(redshifts_with_errors, redshift_errors, metric_values)
                                _LOGGER.info(f"[Cluster z_err] {z_err:.6g}")

                            # Winning subtype-level
                            winning_type = winning_cluster.get('type', '')
                            best_subtype = None
                            try:
                                best_subtype = winning_cluster.get('subtype_info', {}).get('best_subtype', None)
                            except Exception:
                                best_subtype = None
                            if not best_subtype:
                                best_subtype = getattr(self.snid_results, 'best_subtype', None)

                            if best_subtype:
                                z_vals = []
                                z_errs = []
                                metrics = []
                                for m in matches:
                                    tpl = m.get('template', {}) if isinstance(m.get('template'), dict) else {}
                                    if tpl.get('type') == winning_type and tpl.get('subtype') == best_subtype:
                                        z = m.get('redshift')
                                        z_err = m.get('sigma_z', float('nan'))
                                        if z is not None and np.isfinite(z) and np.isfinite(z_err) and z_err > 0:
                                            z_vals.append(float(z))
                                            z_errs.append(float(z_err))
                                            try:
                                                metrics.append(float(get_best_metric_value(m)))
                                            except Exception:
                                                metrics.append(float(m.get('hlap', 0.0) or 0.0))
                                if z_vals:
                                    z_err = weighted_redshift_error(z_vals, z_errs, metrics)
                                    _LOGGER.info(f"[Winning subtype {best_subtype} z_err] {z_err:.6g}")
            except Exception:
                pass
            
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

            # Determine final success considering cluster quality
            has_good_cluster = self._has_good_cluster(self.snid_results)
            clustering_attempted = self._was_clustering_attempted(self.snid_results)
            is_engine_success = bool(self.snid_results and getattr(self.snid_results, 'success', False))
            num_best = 0
            try:
                if self.snid_results and hasattr(self.snid_results, 'best_matches') and self.snid_results.best_matches:
                    num_best = len(self.snid_results.best_matches)
            except Exception:
                num_best = 0
            # Treat as success only if engine succeeded AND (a good cluster exists OR thresholded matches exist)
            try:
                thresholded_count = len(getattr(self.snid_results, 'filtered_matches', []) or [])
            except Exception:
                thresholded_count = 0
            final_success = bool(is_engine_success and (has_good_cluster or thresholded_count >= 1))

            if final_success:
                progress_callback("Analysis completed successfully!", 100)
                self.analysis_running = False
                self.analysis_completed.emit(True)
                _LOGGER.info("SNID analysis completed successfully (valid cluster found)")
            else:
                progress_callback("Analysis inconclusive: no reliable matches above threshold", 100)
                self.analysis_running = False
                self.analysis_completed.emit(False)
                _LOGGER.info("SNID analysis inconclusive - no reliable matches above threshold")
            
        except InterruptedError:
            # Graceful cancellation path
            self.analysis_running = False
            self.snid_results = None
            self.analysis_cancelled = True

            try:
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_update_progress_from_thread",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, "🔴 Analysis cancelled by user"),
                    QtCore.Q_ARG(float, 0.0)
                )
            except Exception:
                pass

            # Notify GUI that work ended (not a failure dialog; GUI will detect cancelled state)
            self.analysis_completed.emit(False)
            _LOGGER.info("Analysis cancelled by user")

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

    @QtCore.Slot(str, float)
    def _enqueue_ordered_progress_from_thread(self, message: str, progress: float):
        """Allocate sequence and emit ordered progress; coalesce out-of-order arrivals."""
        try:
            # Assign sequence number
            self._progress_seq_counter += 1
            seq = self._progress_seq_counter
            # Buffer
            self._pending_progress_by_seq[seq] = (message, progress)
            # Try to flush in order
            self._flush_ordered_progress()
        except Exception as e:
            _LOGGER.debug(f"Non-fatal ordered progress enqueue issue: {e}")

    def _flush_ordered_progress(self):
        """Emit buffered progress updates in strict increasing sequence order."""
        try:
            while self._next_expected_seq in self._pending_progress_by_seq:
                message, progress = self._pending_progress_by_seq.pop(self._next_expected_seq)
                # Emit ordered signal
                try:
                    self.ordered_progress_updated.emit(self._next_expected_seq, message or "", float(progress or 0.0))
                except Exception as e:
                    _LOGGER.debug(f"Ordered progress emit issue: {e}")
                self._next_expected_seq += 1
        except Exception as e:
            _LOGGER.debug(f"Non-fatal ordered progress flush issue: {e}")
    
    def is_analysis_running(self) -> bool:
        """Check if analysis is currently running"""
        return self.analysis_running

    def cancel_analysis(self):
        """Request cancellation of the running analysis (thread-safe)."""
        try:
            # Set cancellation flag/event
            self.cancel_event.set()
            self.analysis_cancelled = True

            # Update progress dialog UI if available (non-blocking)
            dlg = getattr(self.main_window, 'progress_dialog', None)
            if dlg:
                try:
                    dlg.add_progress_line("Cancellation requested... waiting for current step to finish", "warning")
                    if hasattr(dlg, 'cancel_btn'):
                        dlg.cancel_btn.setEnabled(False)
                        dlg.cancel_btn.setText("Cancelling...")
                    dlg.set_stage("Cancelling Analysis", dlg.progress_bar.value())
                except Exception:
                    pass

            _LOGGER.debug("Cancellation event set for analysis thread")
        except Exception as e:
            _LOGGER.warning(f"Error during cancel request: {e}")
    
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
            _LOGGER.info(f"Redshift set to z = {redshift:.6f}")
        else:
            _LOGGER.info("Redshift cleared")
    
    def get_redshift(self) -> Optional[float]:
        """Get current redshift value"""
        return self.galaxy_redshift_result
    
    def switch_active_profile(self, new_profile_id: str, *, reload_current_file: bool = True, show_notice: bool = True) -> bool:
        """Switch the active processing profile (e.g., 'optical' ⇄ 'onir') and optionally reload the current file.

        Parameters:
        -----------
        new_profile_id: str
            Target profile id ('optical' or 'onir').
        reload_current_file: bool
            When True and a file is loaded, reloads it under the new profile without prompting again.
        show_notice: bool
            When True, shows a small confirmation notice after switching.
        """
        try:
            pid = str(new_profile_id).strip().lower() if new_profile_id else 'optical'
            # Validate the profile exists
            try:
                from snid_sage.shared.profiles.builtins import register_builtins
                from snid_sage.shared.profiles.registry import get_profile
                register_builtins()
                _ = get_profile(pid)
            except Exception:
                try:
                    QtWidgets.QMessageBox.critical(
                        self.main_window,
                        "Invalid Profile",
                        f"Requested profile '{pid}' is not available."
                    )
                except Exception:
                    pass
                return False

            # If already on requested profile, optionally just reload
            if str(getattr(self, 'active_profile_id', 'optical')).strip().lower() == pid:
                if reload_current_file and getattr(self, 'current_file_path', None):
                    return self.load_spectrum_file(self.current_file_path, offer_profile_switch=False)
                return True

            # Preserve current file path before resetting
            prev_path = getattr(self, 'current_file_path', None)

            # Switch the active profile for this session
            self.active_profile_id = pid

            # Optional notice
            if show_notice:
                try:
                    QtWidgets.QMessageBox.information(
                        self.main_window,
                        "Profile Switched",
                        f"Active profile set to '{pid}'."
                    )
                except Exception:
                    pass

            # Reset state to avoid mixing processed/analysis data across profiles
            # If a file is loaded, reset back to FILE_LOADED state (preprocessing cleared)
            # Otherwise, reset to INITIAL.
            try:
                if prev_path:
                    self.reset_to_file_loaded_state()
                else:
                    self.reset_to_initial_state()
            except Exception:
                self.reset_to_initial_state()

            # Reload prior file under the new profile without re-prompting
            if reload_current_file and prev_path:
                ok = self.load_spectrum_file(prev_path, offer_profile_switch=False)
                try:
                    if ok and hasattr(self, 'main_window') and self.main_window:
                        # Ensure spectrum-only plot is shown (no overlays)
                        try:
                            from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                            if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager:
                                if self.main_window.plot_manager.current_plot_mode != PlotMode.SPECTRUM:
                                    self.main_window.plot_manager.switch_to_plot_mode(PlotMode.SPECTRUM)
                                # Plot spectrum for current view (reset sets view to 'flux')
                                self.main_window.plot_manager.plot_spectrum(getattr(self.main_window, 'current_view', 'flux'))
                        except Exception:
                            pass

                        # Update button states for flux/flat to reflect FILE_LOADED
                        try:
                            if hasattr(self.main_window, 'unified_layout_manager'):
                                self.main_window.unified_layout_manager.update_flux_flat_button_states(
                                    self.main_window,
                                    flux_active=True,
                                    flat_active=False,
                                    flux_enabled=True,
                                    flat_enabled=False
                                )
                        except Exception:
                            pass

                        # Update status labels
                        try:
                            from pathlib import Path as _Path
                            fname = _Path(str(prev_path)).name
                            if hasattr(self.main_window, 'status_label'):
                                self.main_window.status_label.setText(f"Loaded: {fname}")
                            if hasattr(self.main_window, 'file_status_label'):
                                self.main_window.file_status_label.setText(f"File: {fname}")
                                self.main_window.file_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                            # Clear any analysis classification header/status
                            if hasattr(self.main_window, 'update_header_status'):
                                self.main_window.update_header_status("File loaded")
                        except Exception:
                            pass
                except Exception:
                    pass
                return ok

            return True
        except Exception as e:
            _LOGGER.error(f"Error switching active profile: {e}")
            return False

    # Reset operations
    def reset_to_initial_state(self):
        """Reset application to initial state - comprehensive reset including persistent settings"""
        # Stop any blinking effects first (prevents UI conflicts during reset)
        self._stop_blinking_effects()
        
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
        
        # Clear persistent settings
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

    def reset_to_file_loaded_state(self):
        """Reset application back to 'file loaded' state while preserving the loaded spectrum.

        This clears preprocessing products, analysis results, overlays/navigation state, and
        any redshift configuration so the user can restart from preprocessing, but it keeps
        the original spectrum and file path intact.
        """
        try:
            # Stop any blinking effects first
            self._stop_blinking_effects()

            # Preserve: current_file_path, original_wave, original_flux
            # Clear preprocessing/analysis-related state
            self.processed_spectrum = None
            self.preprocessing_trace = None if hasattr(self, 'preprocessing_trace') else None
            self.snid_results = None
            self.analysis_trace = None
            self.analysis_results = None
            self.galaxy_redshift_result = None
            self.current_template = 0
            self.max_templates = 0
            self.analysis_running = False
            self.analysis_cancelled = False
            self.cancel_event.clear()

            # Clear redshift and mode configs
            if hasattr(self, 'redshift_mode_config'):
                self.redshift_mode_config = None
            if hasattr(self, 'manual_redshift'):
                self.manual_redshift = None
            if hasattr(self, 'forced_redshift'):
                self.forced_redshift = None

            # Reset auto-cluster behavior
            if hasattr(self, 'auto_select_best_cluster'):
                self.auto_select_best_cluster = False

            # View state back to flux
            if hasattr(self, 'current_view'):
                self.current_view = 'flux'

            # Preprocessing flag (if used)
            if hasattr(self, 'is_preprocessed'):
                self.is_preprocessed = False

            # Keep any user masks as they may be part of preprocessing workflow; don't clear mask_regions

            # Workflow moves back to FILE_LOADED
            self.update_workflow_state(WorkflowState.FILE_LOADED)

            _LOGGER.info("Application reset to FILE_LOADED state (spectrum preserved; analysis cleared)")
        except Exception as e:
            _LOGGER.error(f"Error resetting to file-loaded state: {e}")

    def reset_analysis_state(self):
        """Clear only analysis-related state and overlays while preserving preprocessing.

        Keeps the currently loaded spectrum and any processed_spectrum intact so the
        user can immediately re-run analysis. Workflow state is set to PREPROCESSED
        if processed data exists; otherwise falls back to FILE_LOADED.
        """
        try:
            # Stop any blinking effects first
            self._stop_blinking_effects()

            # Clear analysis-only state
            self.snid_results = None
            self.analysis_trace = None
            self.analysis_results = None
            self.current_template = 0
            self.max_templates = 0
            self.analysis_running = False
            self.analysis_cancelled = False
            self.cancel_event.clear()

            # Preserve preprocessing output (processed_spectrum) and original spectrum
            # Clear redshift estimates derived from analysis but preserve manual settings
            self.galaxy_redshift_result = None

            # Determine appropriate workflow state
            if getattr(self, 'processed_spectrum', None) is not None:
                self.update_workflow_state(WorkflowState.PREPROCESSED)
            elif self.original_wave is not None and self.original_flux is not None:
                self.update_workflow_state(WorkflowState.FILE_LOADED)
            else:
                self.update_workflow_state(WorkflowState.INITIAL)

            _LOGGER.info("Analysis state cleared (preprocessing preserved)")
        except Exception as e:
            _LOGGER.error(f"Error resetting analysis state: {e}")
    
    def _stop_blinking_effects(self):
        """Stop any blinking effects that might be active"""
        try:
            # Stop cluster summary blinking via main window
            main_window = getattr(self, 'main_window', None)
            if main_window and hasattr(main_window, 'stop_cluster_summary_blinking'):
                main_window.stop_cluster_summary_blinking()
                _LOGGER.debug("Stopped cluster summary blinking effect via app controller")
            
            # Reset cluster summary state variables if accessible
            if main_window:
                if hasattr(main_window, 'cluster_summary_blinking'):
                    main_window.cluster_summary_blinking = False
                if hasattr(main_window, 'cluster_summary_clicked_once'):
                    main_window.cluster_summary_clicked_once = False
                if hasattr(main_window, 'cluster_summary_blink_timer'):
                    if main_window.cluster_summary_blink_timer:
                        main_window.cluster_summary_blink_timer.stop()
                        main_window.cluster_summary_blink_timer = None
                if hasattr(main_window, 'cluster_summary_original_style'):
                    main_window.cluster_summary_original_style = None
                    
        except Exception as e:
            _LOGGER.warning(f"Warning stopping blinking effects from app controller: {e}")
    
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
                
            # Check if we have at least one cluster (show dialog even with a single cluster)
            all_candidates = clustering_results.get('all_candidates', [])
            if len(all_candidates) == 0:
                return False
                
            # Verify clusters have required data
            for cluster in all_candidates:
                if not isinstance(cluster, dict) or not cluster.get('matches'):
                    return False
                    
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error checking clustering availability: {e}")
            return False

    def _has_good_cluster(self, result) -> bool:
        """Determine if analysis produced a proper matching cluster.

        Returns True only if clustering succeeded and a best_cluster with
        any valid matches is available (changed from >= 3 to >= 1).
        """
        try:
            if not result or not hasattr(result, 'clustering_results'):
                return False
            clustering_results = result.clustering_results
            if not clustering_results or not clustering_results.get('success', False):
                return False
            best_cluster = clustering_results.get('best_cluster')
            if not best_cluster:
                return False
            matches = best_cluster.get('matches', [])
            return isinstance(matches, list) and len(matches) >= 1  # Accept any valid matches
        except Exception:
            return False

    def _was_clustering_attempted(self, result) -> bool:
        """Return True if the analysis attempted clustering.

        Uses the presence of a non-'none' clustering_method when available.
        """
        try:
            if not result:
                return False
            method = getattr(result, 'clustering_method', 'none')
            return method is not None and str(method).lower() != 'none'
        except Exception:
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
            # emit a signal to schedule GUI updates on the main thread.
            # Only schedule GUI updates for successful results when either clustering was not attempted
            # or a good cluster exists.
            if (
                result and hasattr(result, 'success') and result.success and
                (not self._was_clustering_attempted(result) or self._has_good_cluster(result))
            ):
                # Store the result for the signal handler to access
                self._pending_gui_update_result = result
                
                # Emit signal to trigger GUI updates on main thread (thread-safe)
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_handle_gui_updates_from_main_thread",
                    QtCore.Qt.QueuedConnection
                )
                
                _LOGGER.info(f"Analysis complete: {getattr(result, 'consensus_type', 'Unknown')} at z={getattr(result, 'redshift', 0.0):.6f}")
            
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
            
            # Update status using GUI's classification header helper for consistent wording
            status_msg = None
            try:
                if gui_instance and hasattr(gui_instance, '_compose_classification_header'):
                    status_msg = gui_instance._compose_classification_header(result)
                else:
                    t = getattr(result, 'consensus_type', 'Unknown')
                    st = getattr(result, 'best_subtype', '') or ''
                    disp = f"{t} / {st}".strip().rstrip('/')
                    status_msg = f"Classification: {disp}"
            except Exception:
                t = getattr(result, 'consensus_type', 'Unknown')
                status_msg = f"Classification: {t}"

            if gui_instance and hasattr(gui_instance, 'update_header_status') and status_msg:
                gui_instance.update_header_status(status_msg)
            
            _LOGGER.debug("GUI updates completed from main thread")
            
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
                
                # Sort cluster matches by best available metric (HσLAP-CCC preferred) descending
                try:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    cluster_matches_sorted = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
                except ImportError:
                    # Fallback sorting if math utils not available
                    cluster_matches_sorted = sorted(
                        cluster_matches,
                        key=lambda m: m.get('hsigma_lap_ccc', m.get('hlap', 0.0)),
                        reverse=True
                    )
                
                # Update best_matches to only contain cluster templates
                # Prefer the max_output_templates from the current run params; fallback to saved config then 10
                try:
                    if hasattr(self, 'last_analysis_kwargs') and self.last_analysis_kwargs is not None and 'max_output_templates' in self.last_analysis_kwargs:
                        configured_max = int(self.last_analysis_kwargs.get('max_output_templates', 10) or 10)
                    else:
                        configured_max = (
                            int(self.current_config.get('analysis', {}).get('max_output_templates', 10))
                            if hasattr(self, 'current_config') and self.current_config is not None
                            else 10
                        )
                except Exception:
                    configured_max = 10
                result.best_matches = cluster_matches_sorted[:configured_max]
                
                # Also update top_matches and filtered_matches for consistency
                result.top_matches = cluster_matches_sorted[:configured_max]
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
                    # Store top-level match-quality diagnostics for display
                    result.hlap = best_cluster_match.get('hlap', 0.0)
                    result.hsigma_lap_ccc = best_cluster_match.get('hsigma_lap_ccc', 0.0)
                    
                    _LOGGER.info(f"🎯 Updated result properties: {result.template_name} ({result.consensus_type}) "
                                f"z={result.redshift:.6f}")
            
            _LOGGER.info(f"✅ User selected cluster {cluster_index + 1}: {selected_cluster.get('type')} "
                        f"(Size: {len(selected_cluster.get('matches', []))}, "
                        f"Quality: {selected_cluster.get('mean_metric', 0):.2f})")
            
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