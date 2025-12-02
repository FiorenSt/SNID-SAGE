"""
Template Data Models
===================

Data models for template information and management.
"""

import logging
from typing import Dict, List, Optional, Any
import numpy as np

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('template_manager.data')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('template_manager.data')

# H5PY for template storage access
try:
    import h5py
    H5PY_AVAILABLE = True
except ImportError:
    H5PY_AVAILABLE = False


class TemplateData:
    """Container for template data and metadata"""
    
    def __init__(self, name: str, template_info: Dict[str, Any]):
        self.name = name
        self.info = template_info
        self.flux_data = None
        self.wave_data = None
        self.epochs = []
        # Optional error message when loading fails; used by the GUI to show
        # a clear message instead of plotting fake/mock spectra.
        self.load_error: Optional[str] = None
        
    def load_data(self, storage_path: str):
        """Load template flux data from storage"""
        try:
            if not H5PY_AVAILABLE:
                raise ImportError("h5py not available for template data loading")
            
            _LOGGER.info(f"Loading template data for {self.name} from {storage_path}")
            
            # Reset previous state
            self.wave_data = None
            self.flux_data = None
            self.epochs = []
            self.load_error = None

            # Load data from HDF5 storage file
            with h5py.File(storage_path, 'r') as f:
                _LOGGER.debug(f"HDF5 file keys: {list(f.keys())}")
                
                # Load wavelength grid from metadata
                if 'metadata' in f and 'standard_wavelength' in f['metadata']:
                    self.wave_data = f['metadata']['standard_wavelength'][:]
                    _LOGGER.info(f"Loaded wavelength data: {len(self.wave_data)} points")
                else:
                    _LOGGER.warning("No wavelength data found in metadata")
                
                # Check if template exists in templates group
                template_found = False
                if 'templates' in f and self.name in f['templates']:
                    template_group = f['templates'][self.name]
                    template_found = True
                    _LOGGER.info(f"Found template {self.name} in templates group")
                    _LOGGER.debug(f"Template group keys: {list(template_group.keys())}")
                    
                    # Load flux data
                    self.epochs = []
                    
                    # Check for multiple epochs first
                    if 'epochs' in template_group:
                        epochs_group = template_group['epochs']
                        _LOGGER.info(f"Found epochs group with {len(epochs_group)} epochs")
                        
                        for epoch_name in sorted(epochs_group.keys()):
                            epoch_group = epochs_group[epoch_name]
                            flux_data = epoch_group['flux'][:]
                            # Prefer HDF5 attr; default to NaN if missing/unparseable
                            try:
                                age_attr = epoch_group.attrs.get('age', np.nan)
                                age = float(age_attr)
                            except Exception:
                                age = float('nan')
                            epoch_info = {
                                'age': age,
                                'flux': flux_data
                            }
                            self.epochs.append(epoch_info)
                            _LOGGER.debug(f"Loaded epoch {epoch_name} with age {age} and {len(flux_data)} flux points")
                        
                        # Sort epochs by age (finite first, ascending), NaNs last
                        try:
                            self.epochs = sorted(
                                self.epochs,
                                key=lambda e: (0 if np.isfinite(e.get('age', np.nan)) else 1,
                                               float(e.get('age', np.inf)) if np.isfinite(e.get('age', np.nan)) else np.inf)
                            )
                        except Exception:
                            pass
                        # Set default flux to first (earliest) epoch
                        if self.epochs:
                            self.flux_data = self.epochs[0]['flux']
                        
                    elif 'flux' in template_group:
                        # Single epoch template (pre-epochs layout)
                        flux_data = template_group['flux'][:]
                        # Prefer age from HDF5 attrs; default to NaN if missing
                        try:
                            age_attr = template_group.attrs.get('age', np.nan)
                            age = float(age_attr)
                        except Exception:
                            age = float('nan')
                        # Phase stored as attr when present; otherwise Unknown
                        epoch_info = {
                            'age': age,
                            'flux': flux_data
                        }
                        self.epochs.append(epoch_info)
                        _LOGGER.info(f"Loaded single epoch with age {age} and {len(flux_data)} flux points")
                        
                        # Set default flux
                        self.flux_data = flux_data
                    else:
                        _LOGGER.warning(f"No flux data found for template {self.name}")
                
                if not template_found:
                    msg = f"Template {self.name} not found in {storage_path}"
                    _LOGGER.warning(msg)
                    # Record error so the GUI can show it; do not fabricate spectra
                    self.load_error = msg
                        
        except Exception as e:
            msg = f"Error loading template data for {self.name}: {e}"
            _LOGGER.error(msg)
            # Record error instead of creating mock spectra so the GUI can
            # present a clear message to the user.
            self.load_error = msg
    
    def get_epoch_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get epoch data by index"""
        if 0 <= index < len(self.epochs):
            return self.epochs[index]
        return None
    
    def get_epoch_by_age(self, age: float, tolerance: float = 1.0) -> Optional[Dict[str, Any]]:
        """Get epoch data closest to specified age"""
        if not self.epochs:
            return None
        
        closest_epoch = None
        min_diff = float('inf')
        
        for epoch in self.epochs:
            diff = abs(epoch['age'] - age)
            if diff < min_diff and diff <= tolerance:
                min_diff = diff
                closest_epoch = epoch
        
        return closest_epoch
    
    def get_age_range(self) -> tuple:
        """Get the age range of available epochs"""
        if not self.epochs:
            return (float('nan'), float('nan'))
        
        # Consider only finite ages
        finite_ages = []
        for epoch in self.epochs:
            try:
                a = float(epoch.get('age', float('nan')))
                if np.isfinite(a):
                    finite_ages.append(a)
            except Exception:
                continue
        if not finite_ages:
            return (float('nan'), float('nan'))
        
        return (min(finite_ages), max(finite_ages))
    
    def get_flux_range(self) -> tuple:
        """Get the flux range across all epochs"""
        all_flux = []
        
        for epoch in self.epochs:
            if epoch['flux'] is not None:
                all_flux.extend(epoch['flux'])
        
        if not all_flux:
            return (0.0, 1.0)
        
        return (min(all_flux), max(all_flux))
    
    def normalize_epoch_flux(self, epoch_index: int) -> Optional[np.ndarray]:
        """Get normalized flux for a specific epoch"""
        epoch = self.get_epoch_by_index(epoch_index)
        if epoch and epoch['flux'] is not None:
            flux = epoch['flux']
            return flux / np.median(flux)
        return None
    
    def has_valid_data(self) -> bool:
        """Check if template has valid spectral data"""
        return (self.wave_data is not None and 
                len(self.epochs) > 0 and 
                any(epoch['flux'] is not None for epoch in self.epochs))
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """Get a summary of template metadata"""
        age_range = self.get_age_range()
        flux_range = self.get_flux_range()
        
        return {
            'name': self.name,
            'type': self.info.get('type', 'Unknown'),
            'subtype': self.info.get('subtype', 'Unknown'),
            'epochs_count': len(self.epochs),
            'age_range': age_range,
            'flux_range': flux_range,
            'wavelength_range': (
                float(np.min(self.wave_data)) if self.wave_data is not None else 0,
                float(np.max(self.wave_data)) if self.wave_data is not None else 0
            ),
            'redshift': self.info.get('redshift', 0.0),
            'has_valid_data': self.has_valid_data()
        }