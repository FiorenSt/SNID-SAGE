"""
SNID SAGE - Emission Line Overlay Controller
============================================

Controller for managing emission line overlay functionality.
Handles integration with the main GUI and provides easy access to emission line tools.

Part of the SNID SAGE GUI system.
"""

from typing import Optional, Dict, Any, List
import math

# Import the centralized logging system
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.emission_line_controller')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.emission_line_controller')

# Import the multi-step emission dialog
try:
    # Refactored, matplotlib-free PySide6 dialog
    from snid_sage.interfaces.gui.components.pyside6_dialogs import show_pyside6_multi_step_emission_dialog
    _LOGGER.debug("✅ PySide6 multi-step emission line dialog imported successfully")
    DIALOG_AVAILABLE = True
except ImportError as e:
    _LOGGER.warning(f"⚠️ Could not import multi-step emission line dialog: {e}")
    show_pyside6_multi_step_emission_dialog = None
    DIALOG_AVAILABLE = False
except Exception as e:
    _LOGGER.error(f"❌ Error importing multi-step emission line dialog: {e}")
    show_pyside6_multi_step_emission_dialog = None
    DIALOG_AVAILABLE = False


class EmissionLineOverlayController:
    """
    Controller for emission line overlay functionality
    
    This controller manages the emission line overlay tool, including:
    - Opening the overlay dialog
    - Managing spectrum data
    - Coordinating with SNID results for redshift estimates
    """
    
    def __init__(self, gui_instance):
        """
        Initialize the emission line overlay controller
        
        Args:
            gui_instance: Main GUI instance
        """
        self.gui = gui_instance
        self.current_dialog = None
        
        _LOGGER.debug("Emission line overlay controller initialized")
    
    def open_emission_line_overlay(self):
        """Open the emission line overlay dialog"""
        try:
            # Check if spectrum is loaded
            if not self._is_spectrum_loaded():
                self._show_no_spectrum_error()
                return
            
            # Get spectrum data
            spectrum_data = self._get_spectrum_data()
            if not spectrum_data:
                self._show_spectrum_error()
                return
            
            # Get redshift information
            galaxy_redshift = self._get_estimated_redshift()
            cluster_median_redshift = self._get_cluster_median_redshift()
            
            # Close existing dialog if open
            if self.current_dialog and hasattr(self.current_dialog, 'dialog'):
                try:
                    self.current_dialog.dialog.destroy()
                except:
                    pass
            
            # Open new multi-step dialog
            if not DIALOG_AVAILABLE or not show_pyside6_multi_step_emission_dialog:
                self._show_import_error()
                return
                
            self.current_dialog = show_pyside6_multi_step_emission_dialog(
                parent=self.gui,  # Pass the GUI instance, not just master
                spectrum_data=spectrum_data,
                theme_manager=self.gui.theme_manager,
                galaxy_redshift=galaxy_redshift,
                cluster_median_redshift=cluster_median_redshift
            )
            
            _LOGGER.info(f"🔬 Opened multi-step emission line analysis dialog with galaxy z={galaxy_redshift:.6f}, cluster z={cluster_median_redshift:.6f}")

            # Persist user-selected line information back onto the GUI so other features
            # (including the AI assistant) can consume it as *user-provided* context.
            try:
                self._persist_dialog_line_markers(self.current_dialog)
            except Exception as persist_error:
                _LOGGER.warning(f"Could not persist emission-line markers to GUI: {persist_error}")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error opening emission line overlay: {e}")
            self._show_generic_error(str(e))

    def _persist_dialog_line_markers(self, dialog) -> None:
        """
        Persist line selections/analysis produced in the emission dialog to the GUI instance.

        This is intentionally a pass-through of *user-selected* GUI outputs (no new fitting/estimation).
        """
        if dialog is None:
            return

        line_markers: List[Dict[str, Any]] = []
        host_z = float(getattr(dialog, 'host_redshift', 0.0) or 0.0)
        velocity_kms = float(getattr(dialog, 'velocity_shift', 0.0) or 0.0)

        # Optional Step-2 peak analysis results (user-triggered via "Analyze")
        step2_results = {}
        try:
            step2 = getattr(dialog, 'step2_analysis', None)
            if step2 is not None and isinstance(getattr(step2, 'line_analysis_results', None), dict):
                step2_results = getattr(step2, 'line_analysis_results') or {}
        except Exception:
            step2_results = {}

        def add_group(lines_dict: Dict[str, Any], mode: str):
            for line_name, payload in (lines_dict or {}).items():
                try:
                    obs_wavelength, meta = payload
                except Exception:
                    # Unexpected format; skip safely
                    continue
                marker = {
                    'wavelength': float(obs_wavelength) if obs_wavelength is not None else None,
                    'identification': str(line_name),
                    'mode': mode,  # 'sn' or 'galaxy'
                    'host_redshift': host_z,
                    'velocity_shift_kms': velocity_kms,
                    'metadata': meta if isinstance(meta, dict) else {},
                    'step2_analysis': step2_results.get(line_name, None),
                    'source': 'emission_line_overlay_dialog',
                }
                line_markers.append(marker)

        add_group(getattr(dialog, 'sn_lines', {}) if hasattr(dialog, 'sn_lines') else {}, mode='sn')
        add_group(getattr(dialog, 'galaxy_lines', {}) if hasattr(dialog, 'galaxy_lines') else {}, mode='galaxy')

        # Store on GUI
        try:
            self.gui.line_markers = line_markers
        except Exception:
            pass
        try:
            self.gui.line_detection_results = {
                'host_redshift': host_z,
                'velocity_shift_kms': velocity_kms,
                'n_markers': len(line_markers),
                'markers': line_markers,
            }
        except Exception:
            pass
    
    def _is_spectrum_loaded(self) -> bool:
        """Check if a spectrum is currently loaded"""
        # Use the main GUI's has_spectrum_loaded method for consistency
        if hasattr(self.gui, 'has_spectrum_loaded') and callable(self.gui.has_spectrum_loaded):
            return self.gui.has_spectrum_loaded()
        
        # Fallback: Check processed spectrum data (after preprocessing)
        if (hasattr(self.gui, 'processed_spectrum') and self.gui.processed_spectrum and
            'log_wave' in self.gui.processed_spectrum):
            return True
        
        # Fallback: Check original spectrum data (before preprocessing)
        if (hasattr(self.gui, 'original_wave') and hasattr(self.gui, 'original_flux') and
            self.gui.original_wave is not None and self.gui.original_flux is not None and
            len(self.gui.original_wave) > 0 and len(self.gui.original_flux) > 0):
            return True
        
        # Spectrum data formats (backward compatibility)
        if hasattr(self.gui, 'current_spectrum_data') and self.gui.current_spectrum_data:
            return True
        
        if hasattr(self.gui, 'spectrum_data') and self.gui.spectrum_data:
            return True
            
        if hasattr(self.gui, 'wavelength') and hasattr(self.gui, 'flux'):
            if (self.gui.wavelength is not None and 
                self.gui.flux is not None and
                len(self.gui.wavelength) > 0 and 
                len(self.gui.flux) > 0):
                return True
        
        return False
    
    def _get_spectrum_data(self) -> Optional[Dict[str, Any]]:
        """Get the current spectrum data, ALWAYS preferring flattened spectrum"""
        try:
            # STRICT REQUIREMENT: After preprocessing, only flattened spectrum should be available
            # Priority 1: Try to get flattened spectrum from processed_spectrum
            if (hasattr(self.gui, 'processed_spectrum') and self.gui.processed_spectrum):
                # Check for display_flat (best quality flattened data)
                if ('log_wave' in self.gui.processed_spectrum and 
                    'display_flat' in self.gui.processed_spectrum):
                    
                    # Apply zero-region filtering like other parts of the GUI
                    filtered_wave, filtered_flux = self.gui.processed_spectrum['log_wave'], self.gui.processed_spectrum['display_flat']
                    
                    return {
                        'wavelength': filtered_wave,
                        'flux': filtered_flux,
                        'spectrum_type': 'flattened (display_flat)'
                    }
                # Check for flat_flux (standard flattened data)
                elif ('log_wave' in self.gui.processed_spectrum and 
                      'flat_flux' in self.gui.processed_spectrum):
                    
                    # Apply zero-region filtering like other parts of the GUI
                    filtered_wave, filtered_flux = self.gui.processed_spectrum['log_wave'], self.gui.processed_spectrum['flat_flux']
                    
                    return {
                        'wavelength': filtered_wave,
                        'flux': filtered_flux,
                        'spectrum_type': 'flattened (flat_flux)'
                    }
            
            # Priority 2: Try SNID results processed spectrum (also flattened)
            if (hasattr(self.gui, 'snid_results') and self.gui.snid_results and
                hasattr(self.gui.snid_results, 'processed_spectrum') and 
                self.gui.snid_results.processed_spectrum):
                processed = self.gui.snid_results.processed_spectrum
                if 'log_wave' in processed and 'flat_flux' in processed:
                    
                    # Apply zero-region filtering like other parts of the GUI
                    filtered_wave, filtered_flux = processed['log_wave'], processed['flat_flux']
                    
                    return {
                        'wavelength': filtered_wave,
                        'flux': filtered_flux,
                        'spectrum_type': 'flattened (SNID results)'
                    }
            
            # ONLY BEFORE PREPROCESSING: Use original spectrum data
            # This should only be available if no preprocessing has been done yet
            if (hasattr(self.gui, 'original_wave') and hasattr(self.gui, 'original_flux') and
                self.gui.original_wave is not None and self.gui.original_flux is not None):
                _LOGGER.warning("⚠️ Using original spectrum for emission lines - preprocessing recommended for better accuracy")
                
                # Apply zero-region filtering for original spectrum too
                filtered_wave, filtered_flux = self.gui.original_wave, self.gui.original_flux
                
                return {
                    'wavelength': filtered_wave,
                    'flux': filtered_flux,
                    'spectrum_type': 'original (unprocessed - preprocessing recommended)'
                }
            
            # No spectrum data available
            _LOGGER.error("❌ No spectrum data available for emission line overlay")
            return None
            
        except Exception as e:
            _LOGGER.error(f"Error getting spectrum data: {e}")
            return None
    
    def _get_estimated_redshift(self) -> float:
        """Get estimated redshift from SNID results or user input"""
        estimated_z = 0.0
        
        try:
            # Try to get redshift from SNID results
            if (hasattr(self.gui, 'snid_results') and 
                self.gui.snid_results and 
                hasattr(self.gui.snid_results, 'best_matches') and
                len(self.gui.snid_results.best_matches) > 0):
                
                best_match = self.gui.snid_results.best_matches[0]
                if 'redshift' in best_match:
                    estimated_z = float(best_match['redshift'])
                    _LOGGER.debug(f"Using SNID result redshift: z={estimated_z:.6f}")
                    return estimated_z
            
            # Try other redshift sources
            if hasattr(self.gui, 'estimated_redshift') and self.gui.estimated_redshift is not None:
                estimated_z = float(self.gui.estimated_redshift)
                _LOGGER.debug(f"Using GUI estimated redshift: z={estimated_z:.6f}")
                return estimated_z
            
            # Default to zero
            _LOGGER.debug("No redshift estimate available, using z=0.0")
            return 0.0
            
        except Exception as e:
            _LOGGER.warning(f"Error getting estimated redshift: {e}")
            return 0.0
    
    def _get_cluster_median_redshift(self) -> float:
        """Get the median redshift from the best cluster"""
        try:
            # Try to get redshift from SNID clustering results
            if (hasattr(self.gui, 'snid_results') and 
                self.gui.snid_results and 
                hasattr(self.gui.snid_results, 'clustering_results') and 
                self.gui.snid_results.clustering_results):
                
                clustering_results = self.gui.snid_results.clustering_results
                
                # Get best cluster from clustering results
                if (clustering_results.get('success') and 
                    clustering_results.get('best_cluster')):
                    
                    best_cluster = clustering_results['best_cluster']
                    # Prefer subtype-specific redshift if available and valid
                    subtype_z = best_cluster.get('subtype_redshift', None)
                    if isinstance(subtype_z, (int, float)) and not math.isnan(float(subtype_z)) and float(subtype_z) > 0:
                        cluster_z = float(subtype_z)
                        _LOGGER.debug(f"Using best subtype redshift for lines: z={cluster_z:.6f}")
                        return cluster_z
                    # Fallback to enhanced/weighted cluster redshift
                    if 'enhanced_redshift' in best_cluster and isinstance(best_cluster['enhanced_redshift'], (int, float)):
                        wz = float(best_cluster['enhanced_redshift'])
                        if not math.isnan(wz) and wz > 0:
                            _LOGGER.debug(f"Using enhanced cluster redshift fallback: z={wz:.6f}")
                            return wz
                    if 'weighted_mean_redshift' in best_cluster and isinstance(best_cluster['weighted_mean_redshift'], (int, float)):
                        wz2 = float(best_cluster['weighted_mean_redshift'])
                        if not math.isnan(wz2) and wz2 > 0:
                            _LOGGER.debug(f"Using weighted mean cluster redshift fallback: z={wz2:.6f}")
                            return wz2
            
            # Fallback to galaxy redshift if no clustering data
            galaxy_z = self._get_estimated_redshift()
            _LOGGER.debug(f"No clustering data available, using galaxy redshift as cluster median: z={galaxy_z:.6f}")
            return galaxy_z
            
        except Exception as e:
            _LOGGER.warning(f"Error getting cluster median redshift: {e}")
            # Fallback to galaxy redshift
            return self._get_estimated_redshift()
    
    def _show_no_spectrum_error(self):
        """Show error when no spectrum is loaded"""
        try:
            from snid_sage.interfaces.gui.utils.pyside6_message_utils import messagebox
            
            # Debug information for troubleshooting
            debug_info = []
            if hasattr(self.gui, 'original_wave'):
                debug_info.append(f"original_wave: {self.gui.original_wave is not None}")
            if hasattr(self.gui, 'original_flux'):
                debug_info.append(f"original_flux: {self.gui.original_flux is not None}")
            if hasattr(self.gui, 'processed_spectrum'):
                debug_info.append(f"processed_spectrum: {self.gui.processed_spectrum is not None}")
            if hasattr(self.gui, 'snid_results'):
                debug_info.append(f"snid_results: {self.gui.snid_results is not None}")
            
            debug_text = "\n".join(debug_info) if debug_info else "No spectrum attributes found"
            
            _LOGGER.debug(f"Spectrum availability check: {debug_text}")
            
            messagebox.showerror(
                "No Spectrum Loaded",
                "The emission line overlay tool requires spectrum data to be loaded.\n\n"
                "Please ensure you have:\n"
                "1. Loaded a spectrum file using 'Browse & Load Spectrum File'\n"
                "2. Run preprocessing or SNID analysis\n\n"
                f"Debug info:\n{debug_text}"
            )
        except Exception as e:
            _LOGGER.error(f"Error showing no spectrum error: {e}")
    
    def _show_spectrum_error(self):
        """Show error when spectrum data is invalid"""
        try:
            from snid_sage.interfaces.gui.utils.pyside6_message_utils import messagebox
            messagebox.showerror(
                "Invalid Spectrum Data",
                "The loaded spectrum data appears to be invalid or corrupted.\n\n"
                "This may happen if:\n"
                "• The spectrum file format is not supported\n"
                "• The data arrays are empty or have different lengths\n"
                "• Memory issues during loading\n\n"
                "Please try:\n"
                "1. Reloading the spectrum file\n"
                "2. Using a different spectrum file\n"
                "3. Checking that the file is not corrupted"
            )
        except Exception as e:
            _LOGGER.error(f"Error showing spectrum error: {e}")
    
    def _show_import_error(self):
        """Show error when dialog cannot be imported"""
        try:
            from snid_sage.interfaces.gui.utils.pyside6_message_utils import messagebox
            messagebox.showerror(
                "Feature Not Available",
                "The emission line overlay dialog could not be loaded.\n\n"
                "This feature may not be available in your installation."
            )
        except Exception as e:
            _LOGGER.error(f"Error showing import error: {e}")
    
    def _show_generic_error(self, error_message: str):
        """Show generic error message"""
        try:
            from snid_sage.interfaces.gui.utils.pyside6_message_utils import messagebox
            messagebox.showerror(
                "Error",
                f"An error occurred while opening the emission line overlay:\n\n{error_message}"
            )
        except Exception as e:
            _LOGGER.error(f"Error showing generic error: {e}")
    
    def is_available(self) -> bool:
        """Check if the emission line overlay feature is available"""
        return DIALOG_AVAILABLE
    
    def get_status_text(self) -> str:
        """Get status text for the feature"""
        if not self.is_available():
            return "Emission line overlay not available"
        
        if not self._is_spectrum_loaded():
            return "Load a spectrum to use emission line overlay"
        
        estimated_z = self._get_estimated_redshift()
        if estimated_z > 0:
            return f"Ready (estimated z={estimated_z:.6f})"
        else:
            return "Ready (no redshift estimate)" 
