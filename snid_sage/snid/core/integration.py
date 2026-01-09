"""
Unified FFT Storage Integration
===============================

Simple integration layer for unified template FFT storage system.
Replaces complex caching with a single unified storage approach.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
import numpy as np
from pathlib import Path

# Use centralized logging if available
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOG = get_logger('snid.integration')
except ImportError:
    _LOG = logging.getLogger('snid_sage.snid.integration')

# Global unified storage instances keyed by (template_dir, profile_id)
_GLOBAL_STORAGE = {}

def get_unified_storage(template_dir: str | None, profile_id: str | None = None):
    """
    Get or create unified storage instance.
    
    Parameters
    ----------
    template_dir : str
        Directory containing templates
        
    Returns
    -------
    TemplateFFTStorage
        Unified storage instance
    """
    global _GLOBAL_STORAGE

    # Resolve default profile id from config if not provided
    if profile_id is None:
        try:
            from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
            cfg = ConfigurationManager().load_config()
            profile_id = cfg.get('processing', {}).get('active_profile_id', 'optical')
        except Exception:
            profile_id = 'optical'

    # Resolve default templates_dir automatically if not provided.
    # Prefer the centralized templates manager, which will lazily download the
    # managed bank on first use. This avoids relying on legacy packaged paths.
    if not template_dir:
        try:
            from snid_sage.shared.templates_manager import get_templates_dir

            template_dir = str(get_templates_dir())
        except Exception:
            # Last-resort fallback for dev/edge cases: relative "templates"
            template_dir = "templates"

    key = (str(template_dir), str(profile_id))

    if key not in _GLOBAL_STORAGE:
        from ..template_fft_storage import TemplateFFTStorage
        storage = TemplateFFTStorage(template_dir, profile_id=profile_id)

        # Rebuild disabled; expect HDF5/index to be present
        if not storage.is_built():
            _LOG.warning("Unified storage index not found. Ensure HDF5 and index files exist in the template directory.")

        _GLOBAL_STORAGE[key] = storage
    
    return _GLOBAL_STORAGE[key]

def integrate_fft_optimization(templates: List[Dict[str, Any]],
                             k1: int, k2: int, k3: int, k4: int,
                             use_vectorized: Optional[bool] = None,
                              config: Optional[Any] = None) -> 'SimpleFFTCorrelator':
    """
    Create an FFT correlator from templates with optimization options.
    
    Parameters
    ----------
    templates : List[Dict[str, Any]]
        Template list in dict-based format
    k1, k2, k3, k4 : int
        FFT band limits
    use_vectorized : bool, optional
        Whether to use vectorized FFT operations (6.6x faster)
        If None, uses config.use_vectorized_fft or defaults to True
    config : SNIDConfig, optional
        Configuration object to get optimization settings
        
    Returns
    -------
    SimpleFFTCorrelator
        FFT correlator with optional vectorization optimization
    """
    # Determine vectorization setting from config or parameter
    if use_vectorized is None:
        if config is not None:
            use_vectorized = config.use_vectorized_fft
        else:
            use_vectorized = True  # Default to optimized method
    
    _LOG.debug(f"Creating FFT correlator with vectorization: {use_vectorized}")
    return SimpleFFTCorrelator(templates, k1, k2, k3, k4, use_vectorized=use_vectorized)

class SimpleFFTCorrelator:
    """
    Optimized FFT correlator with vectorized cross-correlation support.
    
    Features:
    - Direct FFT computation (no caching complexity)
    - Pre-computed template FFTs
    - VECTORIZED cross-correlation (6.6x faster on average)
    - Legacy method fallback for compatibility
    - Simple correlation interface
    """
    
    def __init__(self, templates: List[Dict[str, Any]], k1: int, k2: int, k3: int, k4: int, 
                 use_vectorized: bool = True):
        """
        Initialize FFT correlator with optimization options.
        
        Parameters
        ----------
        templates : List[Dict[str, Any]]
            Templates in dict-based format
        k1, k2, k3, k4 : int
            FFT band limits
        use_vectorized : bool, optional
            Whether to use vectorized operations (default: True, 6.6x faster)
        """
        self.k1, self.k2, self.k3, self.k4 = k1, k2, k3, k4
        self.use_vectorized = use_vectorized
        self.templates = {}
        self.template_names = []
        
        # Pre-compute FFTs for all templates
        from ..fft_tools import calculate_rms
        
        template_fft_list = []
        template_rms_list = []
        
        for template in templates:
            name = template.get('name', '')
            flux = template.get('flux', np.array([]))
            
            if len(flux) == 0:
                continue
            
            # Store template metadata
            self.templates[name] = template
            self.template_names.append(name)
            
            # Pre-compute FFT
            fft_data = np.fft.fft(flux)
            template_fft_list.append(fft_data)
            
            # Pre-compute RMS
            rms = calculate_rms(fft_data, k1, k2, k3, k4)
            template_rms_list.append(rms)
        
        if self.use_vectorized and template_fft_list:
            # Convert to numpy arrays for vectorized operations
            self.template_fft_matrix = np.array(template_fft_list, dtype=np.complex128)
            self.template_rms_array = np.array(template_rms_list)
            
            # Pre-compute bandpass filter mask (same for all templates)
            self.filter_mask = self._compute_filter_mask()
            
            _LOG.debug(f"🚀 Optimized vectorized FFT correlator ready with {len(self.template_names)} templates")
        else:
            # Legacy mode: store individual FFTs in dictionaries
            self.template_ffts = {}
            self.template_rms = {}
            for i, name in enumerate(self.template_names):
                self.template_ffts[name] = template_fft_list[i]
                self.template_rms[name] = template_rms_list[i]
            
            _LOG.info(f"Legacy FFT correlator ready with {len(self.template_names)} templates")
    
    def _compute_filter_mask(self) -> np.ndarray:
        """Pre-compute the bandpass filter mask to avoid repeated calculations"""
        if self.template_fft_matrix.size == 0:
            return np.array([])
        
        spectrum_length = self.template_fft_matrix.shape[1]
        filter_mask = np.ones(spectrum_length, dtype=np.float64)
        
        for j in range(spectrum_length):
            freq_idx = j if j <= spectrum_length//2 else j - spectrum_length
            abs_freq = abs(freq_idx)
            
            if abs_freq < self.k1 or abs_freq > self.k4:
                filter_mask[j] = 0.0
            elif abs_freq < self.k2:
                delta_k = self.k2 - self.k1
                if delta_k > 0:
                    arg = np.pi * (abs_freq - self.k1) / delta_k
                    filter_mask[j] = 0.5 * (1 - np.cos(arg))
            elif abs_freq > self.k3:
                delta_k = self.k4 - self.k3
                if delta_k > 0:
                    arg = np.pi * (abs_freq - self.k3) / delta_k
                    filter_mask[j] = 0.5 * (1 + np.cos(arg))
        
        return filter_mask
    
    def correlate_snid_style(self, spectrum_fft: np.ndarray, spectrum_rms: float,
                           template_names: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        Correlate spectrum with templates using optimized or fallback correlation.
        
        Parameters
        ----------
        spectrum_fft : np.ndarray
            Pre-computed spectrum FFT
        spectrum_rms : float
            Spectrum RMS value
        template_names : List[str], optional
            Specific templates to correlate (None for all)
            
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Correlation results keyed by template name
        """
        if self.use_vectorized and hasattr(self, 'template_fft_matrix'):
            return self._correlate_vectorized(spectrum_fft, spectrum_rms, template_names)
        else:
            return self._correlate_legacy(spectrum_fft, spectrum_rms, template_names)
    
    def _correlate_vectorized(self, spectrum_fft: np.ndarray, spectrum_rms: float,
                            template_names: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        OPTIMIZED: Vectorized cross-correlation using batch FFT operations.
        
        This method provides 6.6x average speedup over template-by-template processing.
        """
        # Determine which templates to process
        if template_names is None:
            target_indices = list(range(len(self.template_names)))
            target_names = self.template_names
        else:
            target_indices = []
            target_names = []
            for name in template_names:
                if name in self.templates:
                    idx = self.template_names.index(name)
                    target_indices.append(idx)
                    target_names.append(name)
        
        if not target_indices:
            return {}
        
        # Extract relevant template FFTs
        relevant_template_ffts = self.template_fft_matrix[target_indices]
        relevant_template_rms = self.template_rms_array[target_indices]
        
        # VECTORIZED CROSS-CORRELATION - Key optimization!
        # Shape: (n_templates, spectrum_length)
        cross_power_matrix = spectrum_fft[np.newaxis, :] * np.conj(relevant_template_ffts)
        
        # VECTORIZED BANDPASS FILTERING
        # Apply pre-computed filter mask to all templates at once
        filtered_cross_power = cross_power_matrix * self.filter_mask[np.newaxis, :]
        
        # BATCH INVERSE FFT - Major performance gain here!
        # Process all templates simultaneously instead of one-by-one
        correlation_matrix = np.real(np.fft.ifft(filtered_cross_power, axis=1))
        
        # Build results dictionary
        results = {}
        for i, name in enumerate(target_names):
            template = self.templates[name]
            
            # Create wrapper object (maintains compatibility with existing code)
            template_wrapper = SimpleTemplateWrapper(template, relevant_template_ffts[i])
            
            results[name] = {
                'template': template_wrapper,
                'correlation': correlation_matrix[i],
                'template_fft': relevant_template_ffts[i],
                'template_rms': relevant_template_rms[i]
            }
        
        return results
    
    def _correlate_legacy(self, spectrum_fft: np.ndarray, spectrum_rms: float,
                        template_names: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        LEGACY: Template-by-template cross-correlation for compatibility.
        
        This is the original method kept for backward compatibility.
        """
        from ..fft_tools import apply_filter
        
        results = {}
        
        # Determine which templates to process
        target_names = template_names if template_names else list(self.templates.keys())
        
        for name in target_names:
            if name not in self.templates:
                continue
            
            try:
                template = self.templates[name]
                template_fft = self.template_ffts[name]
                template_rms = self.template_rms[name]
                
                # Cross-correlation in frequency domain
                cross_power = spectrum_fft * np.conj(template_fft)
                
                # Apply band-pass filter
                filtered_cross_power = apply_filter(cross_power, self.k1, self.k2, self.k3, self.k4)
                
                # Inverse FFT to get correlation
                correlation = np.real(np.fft.ifft(filtered_cross_power))
                
                # Store results
                results[name] = {
                    'template': SimpleTemplateWrapper(template, template_fft),
                    'correlation': correlation,
                    'template_fft': template_fft,
                    'template_rms': template_rms
                }
                
            except Exception as e:
                _LOG.warning(f"Failed to correlate template {name}: {e}")
                continue
        
        return results

class SimpleTemplateWrapper:
    """Simple wrapper to match the expected template interface."""
    
    def __init__(self, template_dict: Dict[str, Any], fft: np.ndarray):
        self.flux = template_dict.get('flux', np.array([]))
        self.metadata = template_dict
        self.fft = fft

def load_templates_unified(template_dir: str, 
                          type_filter: Optional[List[str]] = None,
                          template_names: Optional[List[str]] = None,
                          exclude_templates: Optional[List[str]] = None,
                          progress_callback: Optional[Callable[[str, float], None]] = None,
                          profile_id: str | None = None) -> List[Dict[str, Any]]:
    """
    Load templates using unified storage - OPTIMIZED VERSION.
    Templates are already rebinned to standard grid, so no rebinning needed during SNID runs.
    
    Parameters
    ----------
    template_dir : str
        Template directory
    type_filter : List[str], optional
        Types to include
    template_names : List[str], optional
        Specific template names to include (supports both base names and epoch-expanded names)
    exclude_templates : List[str], optional
        Specific template names to exclude
        
    Returns
    -------
    List[Dict[str, Any]]
        Templates in dict-based format (already rebinned to standard grid)
    """
    try:
        # Add defensive checks for widget cleanup issues
        import gc
        gc.collect()  # Clean up any lingering PyQtGraph widgets before template loading
        
        storage = get_unified_storage(template_dir, profile_id=profile_id)
        
    except Exception as e:
        _LOG.error(f"Error initializing unified storage: {e}")
        raise RuntimeError(f"Failed to initialize template storage: {e}")
    
    # Handle exclusive logic: if template_names is specified, exclude_templates is ignored
    final_template_names = template_names
    if template_names is None and exclude_templates is not None:
        # Get all template names and remove excluded ones
        all_names = storage.get_all_template_names()
        final_template_names = [name for name in all_names if name not in exclude_templates]
        _LOG.info(f"Excluding {len(exclude_templates)} templates: {len(final_template_names)} remaining")
    
    # ENHANCED TEMPLATE NAME FILTERING: Handle both base names and epoch-expanded names
    enhanced_template_names = None
    if final_template_names is not None:
        # Get all available template names from storage
        all_available_names = storage.get_all_template_names()
        
        # Create a mapping of base names to their epoch-expanded versions
        base_to_expanded = {}
        for name in all_available_names:
            if '_epoch_' in name:
                # Extract base name (everything before _epoch_)
                base_name = name.split('_epoch_')[0]
                if base_name not in base_to_expanded:
                    base_to_expanded[base_name] = []
                base_to_expanded[base_name].append(name)
            else:
                # Single epoch template - base name is the same as full name
                base_to_expanded[name] = [name]
        
        # Expand the requested template names to include epoch variants
        enhanced_template_names = []
        for requested_name in final_template_names:
            if requested_name in all_available_names:
                # Direct match (epoch-expanded name or single-epoch template)
                enhanced_template_names.append(requested_name)
            elif requested_name in base_to_expanded:
                # Base name match - include all epoch variants
                enhanced_template_names.extend(base_to_expanded[requested_name])
                _LOG.debug(f"Expanded base name '{requested_name}' to {len(base_to_expanded[requested_name])} epoch variants")
            else:
                # No match found - log warning but continue
                _LOG.warning(f"Template '{requested_name}' not found in storage")
        
        _LOG.info(f"Enhanced template filtering: {len(final_template_names)} requested -> {len(enhanced_template_names)} expanded")
    
    # Get templates from unified storage with prefetching
    template_entries = storage.get_templates(
        type_filter=type_filter,
        template_names=enhanced_template_names,  # Use enhanced names
        use_prefetching=True,  # Enable prefetching for better performance
        progress_callback=progress_callback
    )
    
    # Get the standard wavelength grid (same for all templates)
    standard_wave = storage.get_standard_wavelength_grid()
    
    # Convert to dict-based format - NO REBINNING NEEDED (already done in storage)
    legacy_templates = []
    for entry in template_entries:
        # Handle multi-epoch templates by expanding them
        if entry.epochs > 1 and entry.epoch_data:
            # Create separate template for each epoch (per-epoch template layout)
            for i, epoch_data in enumerate(entry.epoch_data):
                epoch_template_dict = {
                    'name': f"{entry.name}_epoch_{i}",
                    'type': entry.type,
                    'subtype': entry.subtype,
                    'age': epoch_data['age'],
                    'redshift': entry.redshift,
                    # phase removed
                    'wave': standard_wave,              # Standard grid wavelength
                    'flux': epoch_data['flux'],         # Already rebinned flux
                    'file_path': entry.file_path,
                    'nepoch': 1,                        # Single epoch after expansion
                    'is_log_rebinned': True,           # Flag to skip rebinning
                    'pre_computed_fft': epoch_data['fft']  # Pre-computed FFT
                }
                legacy_templates.append(epoch_template_dict)
        else:
            # Single epoch template, use as-is
            template_dict = {
                'name': entry.name,
                'type': entry.type,
                'subtype': entry.subtype,
                'age': entry.age,
                'redshift': entry.redshift,
                # phase removed
                'wave': standard_wave,              # Standard grid wavelength
                'flux': entry.flux,                 # Already rebinned flux
                'file_path': entry.file_path,
                'nepoch': entry.epochs,
                'is_log_rebinned': True,           # Flag to skip rebinning
                'pre_computed_fft': entry.fft      # Pre-computed FFT
            }
            legacy_templates.append(template_dict)
    
    if exclude_templates:
        exclude_msg = f" (excluded {len(exclude_templates)} templates)"
    else:
        exclude_msg = ""
    
    _LOG.info(f"Loaded {len(legacy_templates)} templates from unified storage{exclude_msg}")
    return legacy_templates

def get_cache_status() -> Dict[str, Any]:
    """Get unified storage status."""
    status = {
        'storage_initialized': _GLOBAL_STORAGE is not None,
        'unified_storage': True,
        'complex_caching_removed': True
    }
    
    if _GLOBAL_STORAGE:
        status.update(_GLOBAL_STORAGE.get_storage_stats())
    
    return status

def clear_global_cache():
    """Clear global storage (for API compatibility)."""
    global _GLOBAL_STORAGE
    _GLOBAL_STORAGE = None
    _LOG.info("Cleared global unified storage")

# Legacy compatibility functions
def get_global_cache():
    """Legacy compatibility - get unified storage.""" 
    return _GLOBAL_STORAGE

def enable_optimization(template_dir: str = "templates", use_vectorized_fft: bool = True, **kwargs):
    """
    Enable FFT optimization with vectorized cross-correlation.
    
    Parameters
    ----------
    template_dir : str, optional
        Template directory
    use_vectorized_fft : bool, optional
        Whether to use vectorized FFT operations (6.6x faster, default: True)
    **kwargs
        Additional optimization parameters
        
    Returns
    -------
    bool
        True if optimization is enabled and ready
    """
    storage = get_unified_storage(template_dir)
    is_built = storage.is_built()
    
    if is_built and use_vectorized_fft:
        _LOG.info("🚀 FFT optimization enabled with vectorized cross-correlation (6.6x speedup)")
    elif is_built:
        _LOG.info("FFT optimization enabled with fallback method")
    else:
        _LOG.warning("FFT optimization not available - unified storage not built")
    
    return is_built

def auto_integrate(template_dir: str = "templates", **kwargs):
    """Legacy compatibility - auto integrate optimization."""
    return enable_optimization(template_dir, **kwargs)

def enable_caching_for_cli(template_dir: str = "templates", **kwargs):
    """Legacy compatibility - enable caching for CLI."""
    return enable_optimization(template_dir, **kwargs)

def enable_caching_for_gui(template_dir: str = "templates", **kwargs):
    """Legacy compatibility - enable caching for GUI."""
    return enable_optimization(template_dir, **kwargs)
