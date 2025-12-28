"""
PySide6 Preview Calculator Module
================================

Mathematical preview calculations for PySide6 preprocessing dialogs without modifying actual data.
Handles real-time preview generation for the preprocessing pipeline.

Features:
- Step-by-step preview calculations
- Non-destructive preview generation  
- Support for all preprocessing operations (including Savitzky-Golay filtering)
- Maintains calculation history
- PyQtGraph integration for real-time updates

Supported Step Types:
- masking: Wavelength region masking
- savgol_filter: Savitzky-Golay smoothing
- clipping: Various spectrum clipping operations
- log_rebin: Log-wavelength rebinning on the SNID log grid
- continuum_fit: Continuum fitting and removal
- apodization: Spectrum edge tapering
"""

import numpy as np
import logging
from typing import Tuple, List, Dict, Any, Optional, Callable
from PySide6 import QtCore

# Import SNID preprocessing functions
try:
    from snid_sage.snid.preprocessing import (
        savgol_filter_fixed,
        clip_aband,
        clip_sky_lines,
        log_rebin,
        log_rebin_maskaware,
        enforce_positive_flux,
        get_grid_params,
        fit_continuum,
        fit_continuum_spline,
        apodize,
        apply_spike_mask,
    )
    # Import wavelength grid constants - use same source as dialog
    from snid_sage.snid.snid import NW, MINW, MAXW
    SNID_AVAILABLE = True
except ImportError:
    SNID_AVAILABLE = False
    # Fallback constants - FIXED to match actual SNID values
    NW, MINW, MAXW = 1024, 2500, 10000

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_preview_calculator')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_preview_calculator')

# Extracted calculator helpers
try:
    from snid_sage.interfaces.gui.features.preprocessing.calculators import (
        fit_continuum_improved as calc_fit_continuum_improved,
        calculate_manual_continuum_preview as calc_manual_continuum_preview,
        calculate_interactive_continuum_preview as calc_interactive_continuum_preview,
    )
except Exception:
    calc_fit_continuum_improved = None
    calc_manual_continuum_preview = None
    calc_interactive_continuum_preview = None


class PySide6PreviewCalculator(QtCore.QObject):
    """
    Handles preview calculations for PySide6 preprocessing steps without modifying the actual preprocessor.
    
    This class maintains its own state for preview calculations, allowing users to see
    the effects of preprocessing steps before applying them permanently.
    
    Enhanced with comprehensive stage memory system for precise navigation.
    """
    
    # Signals for real-time updates
    preview_updated = QtCore.Signal(np.ndarray, np.ndarray)  # wave, flux
    continuum_updated = QtCore.Signal(np.ndarray, np.ndarray)  # wave, continuum
    
    def __init__(self, original_wave: np.ndarray, original_flux: np.ndarray):
        """
        Initialize preview calculator with original spectrum data
        
        Args:
            original_wave: Original wavelength array
            original_flux: Original flux array
        """
        super().__init__()
        
        self.original_wave = original_wave.copy()
        self.original_flux = original_flux.copy()
        self.stored_continuum = None  # Store continuum for proper reconstruction
        self.continuum_method = None  # Store the method used for continuum fitting
        self.continuum_kwargs = None  # Store the parameters used
        self.has_continuum = False  # Track whether continuum removal has been applied
        # Track mask bins on the log grid (from mask-aware rebin)
        self.current_mask_logbins: Optional[np.ndarray] = None
        
        # Track edge information properly through preprocessing steps
        self.current_left_edge = None
        self.current_right_edge = None

        # Optional: delegate non-interactive previews to the canonical pipeline (CLI parity).
        # These are provided by the preprocessing dialog (which already caches preprocess_spectrum()).
        self._canonical_stage_fn: Optional[Callable[[str], Tuple[np.ndarray, np.ndarray]]] = None
        self._canonical_get_fn: Optional[Callable[[], Tuple[Dict[str, Any], Dict[str, Any]]]] = None
        
        self.reset()

    def set_canonical_providers(
        self,
        *,
        stage_fn: Callable[[str], Tuple[np.ndarray, np.ndarray]],
        get_processed_trace_fn: Callable[[], Tuple[Dict[str, Any], Dict[str, Any]]],
    ) -> None:
        """
        Configure canonical pipeline providers.

        When set, the calculator delegates all NON-interactive steps to the canonical
        preprocess_spectrum() outputs (via the dialog's cache), ensuring CLI/quick-GUI parity.
        The only intentional divergence is interactive/manual continuum editing.
        """
        self._canonical_stage_fn = stage_fn
        self._canonical_get_fn = get_processed_trace_fn
        # Sync state immediately
        try:
            self.reset()
        except Exception:
            pass
    
    def reset(self):
        """Reset calculator to original spectrum state"""
        # If canonical providers are available, reset to the canonical "raw" stage and
        # cache canonical metadata (continuum, mask bins) for downstream display.
        if callable(getattr(self, "_canonical_stage_fn", None)) and callable(getattr(self, "_canonical_get_fn", None)):
            try:
                self.current_wave, self.current_flux = self._canonical_stage_fn("raw")  # type: ignore[misc]
                processed, trace = self._canonical_get_fn()  # type: ignore[misc]
                # Continuum for overlay (even before continuum is applied)
                try:
                    cont = trace.get("step4_cont")
                    if cont is None:
                        cont = processed.get("continuum")
                    self.stored_continuum = np.asarray(cont, dtype=float).copy() if cont is not None else None
                except Exception:
                    self.stored_continuum = None
                # Mask bins on log grid (if available)
                try:
                    mlb = trace.get("mask_logbins")
                    self.current_mask_logbins = np.asarray(mlb, dtype=bool).copy() if mlb is not None else None
                except Exception:
                    self.current_mask_logbins = None
                # Optional flux offset (for debugging/parity)
                try:
                    self.flux_offset = float(trace.get("flux_offset", 0.0) or 0.0)
                except Exception:
                    self.flux_offset = 0.0
                self.applied_steps = []
                self.manual_continuum_active = False
                self.has_continuum = False
                self.current_left_edge = None
                self.current_right_edge = None
                return
            except Exception:
                # Fall back to local reset logic below
                pass

        # Start from original spectrum
        base_wave = self.original_wave.copy()
        base_flux = self.original_flux.copy()

        # Canonical start-state parity with preprocess_spectrum():
        # - clip to active log-grid bounds (W0..W1)
        # - enforce positive flux for continuum fitter (may be a no-op)
        # - apply spike masking
        if SNID_AVAILABLE:
            try:
                # Step 0b: clip to active grid bounds (profile-specific)
                try:
                    _, w0, w1, _ = get_grid_params()
                    gmin = float(w0)
                    gmax = float(w1)
                except Exception:
                    gmin = float(MINW)
                    gmax = float(MAXW)
                try:
                    clip_mask = (base_wave >= gmin) & (base_wave <= gmax)
                    if np.any(clip_mask):
                        base_wave = base_wave[clip_mask]
                        base_flux = base_flux[clip_mask]
                except Exception:
                    pass

                # Step 0c: enforce positive flux for spline continuum fitting
                try:
                    base_flux, flux_offset = enforce_positive_flux(base_flux)
                    self.flux_offset = float(flux_offset)
                except Exception:
                    self.flux_offset = 0.0

                # Step 0a: spike masking (same defaults as preprocess_spectrum)
                cleaned_wave, cleaned_flux, spike_info = apply_spike_mask(
                    base_wave,
                    base_flux,
                    floor_z=50.0,
                    neg_floor_z=100.0,  # match preprocess_spectrum: 2 * spike_floor_z
                    baseline_window=501,
                    baseline_width=None,
                    rel_edge_ratio=2.0,
                    min_separation=2,
                    max_removals=None,
                    min_abs_resid=None,
                )
                self.current_wave = cleaned_wave
                self.current_flux = cleaned_flux
                # Optionally keep diagnostics for future use
                try:
                    self.spike_info = dict(spike_info or {})
                except Exception:
                    self.spike_info = {"removed_indices": None, "core_indices": None}
            except Exception:
                # On any error, fall back to the raw spectrum without spike masking
                self.current_wave = base_wave
                self.current_flux = base_flux
                self.spike_info = {"removed_indices": None, "core_indices": None}
        else:
            # When SNID core is unavailable, skip automatic spike masking
            self.current_wave = base_wave
            self.current_flux = base_flux
            self.spike_info = {"removed_indices": None, "core_indices": None}

        self.applied_steps = []
        self.stored_continuum = None  # Reset stored continuum
        self.continuum_method = None
        self.continuum_kwargs = None
        self.manual_continuum_active = False  # Reset manual continuum flag
        self.has_continuum = False
        
        # Reset edge tracking
        self.current_left_edge = None
        self.current_right_edge = None
        # No stage memory bookkeeping
    
    
    def get_current_state(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get current wavelength and flux arrays"""
        # If manual/interactive continuum has been applied, the internal state is authoritative.
        try:
            has_interactive = any((s or {}).get("type") == "interactive_continuum" for s in (self.applied_steps or []))
        except Exception:
            has_interactive = False
        if has_interactive:
            return self.current_wave.copy(), self.current_flux.copy()

        # If canonical providers are available, derive state from applied steps via canonical stages.
        if callable(getattr(self, "_canonical_stage_fn", None)):
            try:
                stage = "raw"
                types = [str((s or {}).get("type", "")) for s in (self.applied_steps or [])]
                if any(t == "apodization" for t in types):
                    stage = "after_step4"
                elif any(t == "continuum_fit" for t in types):
                    stage = "after_step3"
                elif any(t == "log_rebin" for t in types):
                    stage = "after_step2"
                elif any(t == "savgol_filter" for t in types):
                    stage = "after_step1"
                elif any(t in ("masking", "clipping") for t in types):
                    stage = "after_step0"

                w, f = self._canonical_stage_fn(stage)  # type: ignore[misc]
                self.current_wave = np.asarray(w, dtype=float)
                self.current_flux = np.asarray(f, dtype=float)

                # Keep canonical metadata in sync (continuum + mask bins)
                if callable(getattr(self, "_canonical_get_fn", None)):
                    try:
                        processed, trace = self._canonical_get_fn()  # type: ignore[misc]
                        mlb = trace.get("mask_logbins")
                        self.current_mask_logbins = np.asarray(mlb, dtype=bool).copy() if mlb is not None else None
                        cont = trace.get("step4_cont")
                        if cont is None:
                            cont = processed.get("continuum")
                        if cont is not None:
                            self.stored_continuum = np.asarray(cont, dtype=float).copy()
                    except Exception:
                        pass

                return self.current_wave.copy(), self.current_flux.copy()
            except Exception:
                pass

        return self.current_wave.copy(), self.current_flux.copy()
    
    def _update_edge_info_after_step(self, step_type: str):
        """Update edge information after certain preprocessing steps"""
        if step_type in ["masking", "clipping"]:
            # Recalculate edges based on current data range after masking/clipping
            # For masking/clipping, we track the actual wavelength range, not flux-based edges
            if len(self.current_wave) > 0:
                # Find the mapping from current indices to original indices
                # This helps track which parts of the original spectrum are still valid
                orig_wave_min, orig_wave_max = self.current_wave[0], self.current_wave[-1]
                
                # Find corresponding indices in original wavelength array
                orig_left_idx = np.searchsorted(self.original_wave, orig_wave_min, side='left')
                orig_right_idx = np.searchsorted(self.original_wave, orig_wave_max, side='right') - 1
                
                self.current_left_edge = orig_left_idx
                self.current_right_edge = orig_right_idx
                
                _LOGGER.debug(f"Updated edges after {step_type}: left={self.current_left_edge}, right={self.current_right_edge}")
                _LOGGER.debug(f"Wavelength range: {orig_wave_min:.1f} - {orig_wave_max:.1f}")
        elif step_type == "log_rebin":
            # After log rebinning, calculate edges based on valid flux regions (including negative values)
            valid_mask = (self.current_flux != 0) & np.isfinite(self.current_flux)
            if np.any(valid_mask):
                self.current_left_edge = np.argmax(valid_mask)
                self.current_right_edge = len(self.current_flux) - 1 - np.argmax(valid_mask[::-1])
            else:
                self.current_left_edge = 0
                self.current_right_edge = len(self.current_flux) - 1
                
            _LOGGER.debug(f"Updated edges after {step_type}: left={self.current_left_edge}, right={self.current_right_edge}")
        # Other steps like savgol_filter, continuum_fit, and apodization preserve the data structure
    
    def get_current_edges(self) -> Tuple[int, int]:
        """Get current left and right edge indices"""
        left = self.current_left_edge if self.current_left_edge is not None else 0
        right = self.current_right_edge if self.current_right_edge is not None else (len(self.current_flux) - 1)
        return left, right
    
    def preview_step(self, step_type: str, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate preview for a step without applying it permanently
        
        Args:
            step_type: Type of preprocessing step
            **kwargs: Step-specific parameters
            
        Returns:
            Tuple of (preview_wave, preview_flux)
        """
        try:
            # Remove step_index from kwargs if present (it's only used for tracking)
            preview_kwargs = kwargs.copy()
            preview_kwargs.pop('step_index', None)

            # Canonical delegation for strict CLI parity (except manual/interactive continuum).
            # If interactive continuum has already been applied, we must keep using internal state.
            try:
                has_interactive = any((s or {}).get("type") == "interactive_continuum" for s in (self.applied_steps or []))
            except Exception:
                has_interactive = False
            if (not has_interactive) and callable(getattr(self, "_canonical_stage_fn", None)):
                stage_map = {
                    "masking": "after_step0",
                    "clipping": "after_step0",
                    "savgol_filter": "after_step1",
                    "log_rebin": "after_step2",
                    "continuum_fit": "after_step3",
                    "apodization": "after_step4",
                }
                if step_type in stage_map:
                    w, f = self._canonical_stage_fn(stage_map[step_type])  # type: ignore[misc]
                    # Keep canonical continuum available for reconstruction/overlay
                    if step_type in ("continuum_fit", "apodization") and callable(getattr(self, "_canonical_get_fn", None)):
                        try:
                            processed, trace = self._canonical_get_fn()  # type: ignore[misc]
                            cont = trace.get("step4_cont")
                            if cont is None:
                                cont = processed.get("continuum")
                            if cont is not None:
                                self.stored_continuum = np.asarray(cont, dtype=float).copy()
                                self.has_continuum = True
                        except Exception:
                            pass
                    return np.asarray(w, dtype=float), np.asarray(f, dtype=float)
            
            if step_type == "masking":
                return self._preview_masking(**preview_kwargs)
            elif step_type == "savgol_filter":
                return self._preview_savgol_filter(**preview_kwargs)
            elif step_type == "clipping":
                return self._preview_clipping(**preview_kwargs)
            elif step_type == "log_rebin":
                return self._preview_log_rebin(**preview_kwargs)
            elif step_type == "continuum_fit":
                return self._preview_continuum_fit(**preview_kwargs)
            elif step_type == "interactive_continuum":
                return self._preview_interactive_continuum(**preview_kwargs)
            elif step_type == "apodization":
                return self._preview_apodization(**preview_kwargs)
            else:
                _LOGGER.warning(f"Warning: Unknown step type '{step_type}'")
                return self.current_wave.copy(), self.current_flux.copy()
                
        except Exception as e:
            _LOGGER.error(f"Preview calculation error for {step_type}: {e}")
            return self.current_wave.copy(), self.current_flux.copy()
    
    def apply_step(self, step_type: str, **kwargs):
        """
        Apply a step permanently to the preview calculator state
        
        Args:
            step_type: Type of preprocessing step
            **kwargs: Step-specific parameters (including optional step_index)
        """
        # Store current state as preview state for stage memory
        preview_state = {
            'wave': self.current_wave.copy(),
            'flux': self.current_flux.copy()
        }
        if self.stored_continuum is not None:
            preview_state['continuum'] = self.stored_continuum.copy()
        
        # Apply the step
        preview_wave, preview_flux = self.preview_step(step_type, **kwargs)
        self.current_wave = preview_wave
        self.current_flux = preview_flux

        # If interactive continuum was applied, persist the manual continuum for later reconstruction
        # (Finish path asks get_continuum_from_fit()).
        if step_type == "interactive_continuum":
            try:
                mc_in = kwargs.get("manual_continuum", None)
                wg_in = kwargs.get("wave_grid", None)
                if mc_in is not None:
                    mc = np.asarray(mc_in, dtype=float)
                    if mc.size == self.current_wave.size:
                        self.stored_continuum = mc.copy()
                        self.manual_continuum_active = True
                    elif wg_in is not None:
                        wg = np.asarray(wg_in, dtype=float)
                        if wg.size == mc.size and wg.size >= 2:
                            order = np.argsort(wg)
                            wg = wg[order]
                            mc = mc[order]
                            self.stored_continuum = np.interp(self.current_wave, wg, mc, left=0.0, right=0.0)
                            self.manual_continuum_active = True
            except Exception:
                pass
        
        # Track applied steps so the finalization logic can accurately reconstruct state
        try:
            if not hasattr(self, 'applied_steps') or self.applied_steps is None:
                self.applied_steps = []
            # Store a shallow copy of kwargs to avoid accidental external mutation
            step_record = {'type': step_type, 'kwargs': dict(kwargs) if kwargs else {}}
            self.applied_steps.append(step_record)
        except Exception as e:
            _LOGGER.debug(f"Failed to record applied step '{step_type}': {e}")

        # Update edge information after applying the step
        self._update_edge_info_after_step(step_type)
        # Update continuum flag if applicable
        if step_type in ["continuum_fit", "interactive_continuum"]:
            self.has_continuum = True
        
        # No step tracking or stage memory in simplified flow
        
        # Emit signal for real-time updates
        self.preview_updated.emit(self.current_wave, self.current_flux)
    
    def _preview_masking(self, mask_regions: List[Tuple[float, float]] = None, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview masking step - removes data points in masked regions"""
        if not mask_regions:
            return self.current_wave.copy(), self.current_flux.copy()
        
        temp_wave = self.current_wave.copy()
        temp_flux = self.current_flux.copy()
        
        # Create a mask for all regions to keep (inverse of mask regions)
        keep_mask = np.ones(len(temp_wave), dtype=bool)
        
        # Apply wavelength masks by marking regions to remove
        for start, end in mask_regions:
            mask_region = (temp_wave >= start) & (temp_wave <= end)
            keep_mask &= ~mask_region  # Remove these points
        
        # Return only the points outside the masked regions
        return temp_wave[keep_mask], temp_flux[keep_mask]
    
    def _preview_savgol_filter(self, filter_type: str = "none", value: float = 11.0, polyorder: int = 3, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview Savitzky-Golay filtering step"""
        if filter_type == "none":
            return self.current_wave.copy(), self.current_flux.copy()
        
        try:
            temp_wave = self.current_wave.copy()
            temp_flux = self.current_flux.copy()
            # Ensure integer values for SciPy API to avoid silent fallbacks
            try:
                polyorder_int = int(polyorder)
            except Exception:
                polyorder_int = 3
            try:
                window_int = int(value)
            except Exception:
                window_int = 11
            if filter_type == "fixed" and window_int >= 3:
                if SNID_AVAILABLE:
                    filtered_flux = savgol_filter_fixed(temp_flux, window_int, polyorder_int)
                else:
                    try:
                        from scipy.signal import savgol_filter as _sg
                        w = window_int if window_int % 2 == 1 else window_int + 1
                        w = max(3, min(w, len(temp_flux) - (1 - (len(temp_flux) % 2))))
                        filtered_flux = _sg(temp_flux, w, min(polyorder_int, w - 1))
                    except Exception:
                        return temp_wave, temp_flux
            else:
                return temp_wave, temp_flux
            
            return temp_wave, filtered_flux
            
        except Exception as e:
            _LOGGER.error(f"Savitzky-Golay filter preview failed: {e}")
            return self.current_wave.copy(), self.current_flux.copy()
    
    def _preview_clipping(self, clip_type: str = "aband", **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview clipping operations"""
        try:
            temp_wave = self.current_wave.copy()
            temp_flux = self.current_flux.copy()
            
            if clip_type == "aband":
                if SNID_AVAILABLE:
                    clipped_wave, clipped_flux = clip_aband(
                        temp_wave,
                        temp_flux,
                        (7550.0, 7700.0),
                    )
                else:
                    # Fallback: remove telluric O2 A-band only (7550–7700 Å)
                    a, b = 7550.0, 7700.0
                    keep = ~((temp_wave >= a) & (temp_wave <= b))
                    clipped_wave, clipped_flux = temp_wave[keep], temp_flux[keep]
            elif clip_type == "sky":
                width = kwargs.get('width', 40.0)
                if SNID_AVAILABLE:
                    clipped_wave, clipped_flux = clip_sky_lines(temp_wave, temp_flux, width)
                else:
                    # Fallback: remove bands around common sky lines
                    lines = (5577.0, 6300.2, 6364.0)
                    keep = np.ones_like(temp_wave, dtype=bool)
                    for l in lines:
                        keep &= ~((temp_wave >= l - width) & (temp_wave <= l + width))
                    clipped_wave, clipped_flux = temp_wave[keep], temp_flux[keep]
            else:
                return temp_wave, temp_flux
            
            return clipped_wave, clipped_flux
            
        except Exception as e:
            _LOGGER.error(f"Clipping preview failed: {e}")
            return self.current_wave.copy(), self.current_flux.copy()
    
    def _preview_log_rebin(self, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview log-wavelength rebinning"""
        try:
            temp_wave = self.current_wave.copy()
            temp_flux = self.current_flux.copy()
            mask_regions = kwargs.get('mask_regions', None)
            
            if SNID_AVAILABLE:
                # Use the already-initialized grid from the dialog's active profile; avoid re-initializing
                from snid_sage.snid.preprocessing import get_grid_params
                try:
                    get_grid_params()
                except Exception:
                    pass
                rebinned_wave, rebinned_flux, mask_logbins = log_rebin_maskaware(temp_wave, temp_flux, mask_regions or [])
                # Store mask bins for downstream steps (continuum, apodization, display)
                try:
                    self.current_mask_logbins = mask_logbins.copy() if mask_logbins is not None else None
                except Exception:
                    self.current_mask_logbins = mask_logbins
            else:
                # Fallback when SNID is unavailable: build grid and interpolate
                try:
                    if SNID_AVAILABLE and mask_regions:
                        # (This branch no longer reachable; kept for clarity)
                        pass
                    import os
                    active_pid = os.environ.get('SNID_SAGE_ACTIVE_PROFILE') or os.environ.get('SNID_SAGE_PROFILE')
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
                    nlog = int(getattr(grid, 'nw', NW))
                    w0 = float(getattr(grid, 'min_wave_A', MINW))
                    w1 = float(getattr(grid, 'max_wave_A', MAXW))
                except Exception:
                    w0, w1 = float(MINW), float(MAXW)
                    nlog = int(NW)
                dwlog = np.log(w1 / w0) / nlog
                rebinned_wave = w0 * np.exp((np.arange(nlog) + 0.5) * dwlog)
                # If mask regions provided (SNID unavailable), drop masked samples before interpolation in log space
                if mask_regions:
                    # Clip masks to the actually observed wavelength range so that only
                    # interior gaps are treated as masked regions on the log grid.
                    keep = np.ones_like(temp_wave, dtype=bool)
                    for a, b in mask_regions:
                        aa = float(min(a, b))
                        bb = float(max(a, b))
                        keep &= ~((temp_wave >= aa) & (temp_wave <= bb))
                    w_src = temp_wave[keep]
                    f_src = temp_flux[keep]
                    if w_src.size < 2:
                        rebinned_flux = np.zeros_like(rebinned_wave, dtype=float)
                        self.current_mask_logbins = None
                    else:
                        # Build a clipped mask list consistent with the core helper:
                        obs_min = float(w_src[0])
                        obs_max = float(w_src[-1])
                        clipped_masks = []
                        for a, b in mask_regions:
                            aa = float(min(a, b))
                            bb = float(max(a, b))
                            clipped_a = max(aa, obs_min)
                            clipped_b = min(bb, obs_max)
                            if clipped_b > clipped_a:
                                clipped_masks.append((clipped_a, clipped_b))
                        rebinned_flux = np.interp(
                            np.log(rebinned_wave),
                            np.log(w_src),
                            f_src,
                            left=float(f_src[0]),
                            right=float(f_src[-1]),
                        )
                        # Compute and store mask bins against the target grid for downstream behavior
                        try:
                            from snid_sage.snid.preprocessing import compute_mask_on_loggrid
                            self.current_mask_logbins = compute_mask_on_loggrid(rebinned_wave, clipped_masks)
                        except Exception:
                            self.current_mask_logbins = None
                else:
                    rebinned_flux = np.interp(rebinned_wave, temp_wave, temp_flux, left=0.0, right=0.0)
                    self.current_mask_logbins = None
            return rebinned_wave, rebinned_flux
            
        except Exception as e:
            _LOGGER.error(f"Log rebinning preview failed: {e}")
            return self.current_wave.copy(), self.current_flux.copy()
    
    def _preview_continuum_fit(self, method: str = 'spline', **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview continuum fitting with proper continuum storage and calculation"""
        # Check if manual continuum is active
        if hasattr(self, 'manual_continuum_active') and self.manual_continuum_active:
            if hasattr(self, 'stored_continuum') and self.stored_continuum is not None:
                return self.current_wave.copy(), self.current_flux.copy()
        
        try:
            temp_wave = self.current_wave.copy()
            temp_flux = self.current_flux.copy()
            # Exclude masked bins from continuum estimation if available
            try:
                if getattr(self, 'current_mask_logbins', None) is not None and len(self.current_mask_logbins) == len(temp_flux):
                    # Set masked bins to zero so they are ignored by the fitter (which uses flux>0)
                    temp_flux = temp_flux.copy()
                    temp_flux[self.current_mask_logbins.astype(bool)] = 0.0
            except Exception:
                pass
            
            if method == "spline":
                knotnum = kwargs.get('knotnum', 13)
                flat_flux, continuum = self._fit_continuum_improved(temp_flux, method="spline", knotnum=knotnum)
                # Store continuum and method for later reconstruction
                self.stored_continuum = continuum.copy()
                self.continuum_method = "spline"
                self.continuum_kwargs = {'knotnum': knotnum}
            else:
                return temp_wave, temp_flux
            
            # CRITICAL: Always emit continuum signal for visualization even in preview mode
            self.continuum_updated.emit(temp_wave, continuum)
            
            return temp_wave, flat_flux
            
        except Exception as e:
            _LOGGER.error(f"Continuum fitting preview failed: {e}")
            return self.current_wave.copy(), self.current_flux.copy()
    
    def _preview_interactive_continuum(self, continuum_points: List[Tuple[float, float]] = None, manual_continuum: np.ndarray = None, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview interactive continuum fitting and removal"""
        # Handle new manual continuum approach (full array)
        if manual_continuum is not None:
            try:
                mc = np.asarray(manual_continuum, dtype=float)
            except Exception:
                mc = None

            if mc is not None and mc.size == self.current_wave.size:
                # Keep continuum stored so the GUI can reconstruct fluxed spectra at Finish
                try:
                    self.stored_continuum = mc.copy()
                    self.manual_continuum_active = True
                except Exception:
                    pass
                return self._calculate_manual_continuum_preview(mc)

            # Best-effort: resample onto current grid if a wave_grid is provided
            try:
                wg = np.asarray(kwargs.get("wave_grid", None), dtype=float)
                if wg is not None and mc is not None and wg.size == mc.size and wg.size >= 2:
                    order = np.argsort(wg)
                    wg = wg[order]
                    mc = mc[order]
                    resampled = np.interp(self.current_wave, wg, mc, left=0.0, right=0.0)
                    self.stored_continuum = np.asarray(resampled, dtype=float).copy()
                    self.manual_continuum_active = True
                    return self._calculate_manual_continuum_preview(self.stored_continuum)
            except Exception:
                pass
        
        # Handle continuum points approach for compatibility
        if not continuum_points or len(continuum_points) < 2:
            return self.current_wave.copy(), self.current_flux.copy()
        
        return self.calculate_interactive_continuum_preview(continuum_points)
    
    def _preview_apodization(self, percent: float = 10.0, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """Preview apodization (edge tapering)"""
        try:
            temp_wave = self.current_wave.copy()
            temp_flux = self.current_flux.copy()
            
            # Match preprocess_spectrum(): apodize over the valid non-zero finite region.
            nz = np.where((temp_flux != 0) & np.isfinite(temp_flux))[0]
            
            if nz.size > 0:
                n1, n2 = nz[0], nz[-1]
                if SNID_AVAILABLE:
                    apodized_flux = apodize(temp_flux, int(n1), int(n2), percent=float(percent))
                else:
                    # Fallback: simple raised-cosine taper
                    out = temp_flux.copy()
                    valid_len = (int(n2) - int(n1) + 1)
                    ns = int(round(valid_len * max(0.0, min(100.0, float(percent))) / 100.0))
                    ns = max(0, min(ns, valid_len // 2))
                    if ns > 1:
                        ramp = 0.5 * (1 - np.cos(np.pi * np.arange(ns) / (ns - 1.0)))
                        out[int(n1) : int(n1) + ns] *= ramp
                        out[int(n2) - ns + 1 : int(n2) + 1] *= ramp[::-1]
                    apodized_flux = out

                # After apodization, zero-out masked bins (to match CLI visuals)
                try:
                    if getattr(self, 'current_mask_logbins', None) is not None and len(self.current_mask_logbins) == len(apodized_flux):
                        apodized_flux[self.current_mask_logbins.astype(bool)] = 0.0
                except Exception:
                    pass
                return temp_wave, apodized_flux
            
            # If we can't find a valid range, return unchanged
            return temp_wave, temp_flux
            
        except Exception as e:
            _LOGGER.error(f"Apodization preview failed: {e}")
            return self.current_wave.copy(), self.current_flux.copy()
    
    def _fit_continuum_improved(self, flux: np.ndarray, method: str = "spline", **kwargs):
        """Delegate to extracted helper for continuum fitting."""
        try:
            if callable(calc_fit_continuum_improved):
                return calc_fit_continuum_improved(flux, method=method, **kwargs)
        except Exception as e:
            _LOGGER.error(f"Continuum fitting helper failed: {e}")
        # Fallback: behave like flat
        return np.zeros_like(flux), np.ones_like(flux)
    
    def _calculate_manual_continuum_preview(self, manual_continuum: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate preview with manual continuum array via helper."""
        try:
            if callable(calc_manual_continuum_preview):
                temp_wave, flat_flux = calc_manual_continuum_preview(self.current_wave, self.current_flux, manual_continuum)
                self.continuum_updated.emit(temp_wave, manual_continuum)
                return temp_wave, flat_flux
        except Exception as e:
            _LOGGER.error(f"Manual continuum preview failed: {e}")
        return self.current_wave.copy(), self.current_flux.copy()
    
    def calculate_interactive_continuum_preview(self, continuum_points: List[Tuple[float, float]]) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate preview with interactive continuum points via helper."""
        try:
            if callable(calc_interactive_continuum_preview):
                result = calc_interactive_continuum_preview(self.current_wave, self.current_flux, continuum_points)
                # Helper may return (wave, flat) or (wave, flat, continuum)
                if len(result) == 3:
                    wave, flat_flux, continuum = result
                    self.continuum_updated.emit(wave, continuum)
                    return wave, flat_flux
                else:
                    return result  # type: ignore
        except Exception as e:
            _LOGGER.error(f"Interactive continuum preview failed: {e}")
        return self.current_wave.copy(), self.current_flux.copy()
    
    def get_continuum_from_fit(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get the stored continuum from the last fitting operation"""
        
        if self.stored_continuum is not None:
            return self.current_wave.copy(), self.stored_continuum.copy()
        else:
            # Return flat continuum if none stored
            return self.current_wave.copy(), np.ones_like(self.current_wave)
    
    def get_applied_steps(self) -> List[Dict[str, Any]]:
        """Return the list of applied steps recorded by the calculator."""
        try:
            return list(self.applied_steps)
        except Exception:
            return []