"""
SNID SAGE - PySide6 Preprocessing Controller
==========================================

Handles all spectrum preprocessing operations for the PySide6 GUI including quick preprocessing,
manual preprocessing wizard, and SNID preprocessing pipeline.
"""

import os
import logging
from PySide6 import QtWidgets, QtCore
from snid_sage.snid.snid import preprocess_spectrum
import numpy as np

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_preprocessing_controller')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_preprocessing_controller')


class PySide6PreprocessingController:
    """Controller for handling spectrum preprocessing operations in PySide6 GUI"""
    
    def __init__(self, parent_gui):
        """Initialize preprocessing controller
        
        Parameters:
        -----------
        parent_gui : PySide6SNIDSageGUI
            Reference to the main PySide6 GUI instance
        """
        self.gui = parent_gui
    
    def run_quick_preprocessing(self):
        """Run quick SNID preprocessing with default settings"""
        # Check if spectrum is loaded
        wave, flux = self.gui.app_controller.get_spectrum_data()
        if wave is None or flux is None:
            QtWidgets.QMessageBox.warning(
                self.gui, 
                "No Spectrum", 
                "Please load a spectrum file before preprocessing."
            )
            return
        
        try:
            # Update button state
            original_text = self.gui.preprocessing_btn.text()
            self.gui.preprocessing_btn.setText("Processing...")
            self.gui.preprocessing_btn.setEnabled(False)
            
            # Process the GUI to show the button state change
            QtCore.QCoreApplication.processEvents()
            
            # Run SNID preprocessing with default parameters
            processed_spectrum = self.run_snid_preprocessing_only()
            
            if processed_spectrum is not None:
                # Update status
                self.gui.preprocess_status_label.setText("Preprocessed")
                self.gui.preprocess_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                self.gui.status_label.setText("Quick preprocessing complete - ready for analysis")
                
                # Update workflow state
                from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                self.gui.app_controller.update_workflow_state(WorkflowState.PREPROCESSED)
                
                # CRITICAL: Switch to Flat view to show the preprocessed (flat) spectrum
                self.gui._on_view_change('flat')
                _LOGGER.info("Automatically switched to Flat view after quick preprocessing")
                
                # Update the plot to show the new processed spectrum
                self.gui._plot_spectrum()
                
                _LOGGER.info("Quick preprocessing completed successfully")
            
        except Exception as e:
            _LOGGER.error(f"Quick preprocessing failed: {e}")
            QtWidgets.QMessageBox.critical(
                self.gui, 
                "Preprocessing Error", 
                f"Quick preprocessing failed: {str(e)}"
            )
        finally:
            # Reset button state
            self.gui.preprocessing_btn.setText(original_text)
            self.gui.preprocessing_btn.setEnabled(True)
    
    def run_manual_preprocessing_wizard(self):
        """Open manual preprocessing wizard for step-by-step control"""
        # Check if spectrum is loaded
        wave, flux = self.gui.app_controller.get_spectrum_data()
        if wave is None or flux is None:
            QtWidgets.QMessageBox.warning(
                self.gui, 
                "No Spectrum", 
                "Please load a spectrum file before preprocessing."
            )
            return
        
        try:
            # This opens the step-by-step preprocessing wizard
            self.gui.open_preprocessing_dialog()
        except Exception as e:
            _LOGGER.error(f"Failed to open manual preprocessing wizard: {e}")
            QtWidgets.QMessageBox.critical(
                self.gui, 
                "Preprocessing Error", 
                f"Failed to open manual preprocessing wizard: {str(e)}"
            )
    
    def run_snid_preprocessing_only(self, skip_steps=None):
        """Run only the SNID preprocessing steps"""
        # Get current spectrum data
        wave, flux = self.gui.app_controller.get_spectrum_data()
        if wave is None or flux is None:
            return None
        
        try:
            _LOGGER.info("Running SNID preprocessing pipeline...")
            
            # Get file path from app controller
            file_path = self.gui.app_controller.get_current_file_path()
            
            # Use the modular preprocessing function with default parameters for quick preprocessing
            if file_path:
                # Use file path if available
                processed_spectrum, trace = preprocess_spectrum(
                    spectrum_path=file_path,
                    # Default parameters for quick preprocessing
                    savgol_window=0,  # No Savitzky-Golay filtering by default
                    savgol_order=3,
                    aband_remove=False,  # No A-band removal by default
                    skyclip=False,  # No sky line clipping by default
                    emclip_z=-1.0,  # No emission line clipping
                    emwidth=40.0,
                    wavelength_masks=[],  # No wavelength masks by default
                    apodize_percent=10.0,  # Default apodization
                    skip_steps=skip_steps or [],
                    verbose=False,
                    # Ensure preprocessing uses the active GUI profile (e.g., 'onir' vs 'optical')
                    profile_id=getattr(self.gui.app_controller, 'active_profile_id', 'optical')
                )
            else:
                # Use spectrum arrays directly if no file path available
                processed_spectrum, trace = preprocess_spectrum(
                    input_spectrum=(wave, flux),
                    # Default parameters for quick preprocessing
                    savgol_window=0,  # No Savitzky-Golay filtering by default
                    savgol_order=3,
                    aband_remove=False,  # No A-band removal by default
                    skyclip=False,  # No sky line clipping by default
                    emclip_z=-1.0,  # No emission line clipping
                    emwidth=40.0,
                    wavelength_masks=[],  # No wavelength masks by default
                    apodize_percent=10.0,  # Default apodization
                    skip_steps=skip_steps or [],
                    verbose=False,
                    # Ensure preprocessing uses the active GUI profile (e.g., 'onir' vs 'optical')
                    profile_id=getattr(self.gui.app_controller, 'active_profile_id', 'optical')
                )
            
            # Store the processed spectrum in the app controller
            if processed_spectrum is not None:
                # CRITICAL: Generate both flux and flattened versions for view switching
                log_wave = processed_spectrum['log_wave']
                log_flux = processed_spectrum['log_flux']     # Scaled flux on log grid
                flat_flux = processed_spectrum['flat_flux']   # Continuum-removed
                tapered_flux = processed_spectrum.get('tapered_flux', flat_flux)  # Final apodized version
                continuum = processed_spectrum['continuum']   # Fitted continuum
                
                # For the display versions, we want to show the apodization effect:
                # - Flux view: Reconstruct flux from apodized flat spectrum by multiplying with continuum
                # - Flat view: Use the apodized flat spectrum directly (tapered_flux)
                
                # Generate flux version: reconstruct from apodized flat spectrum using the correct unflatten formula
                # The flattened spectrum is defined as flux/continuum - 1, so to reconstruct: (flat + 1) * continuum
                # Extend continuum to edges if it was zeroed outside valid range (e.g., Gaussian method)
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
                display_flux = (tapered_flux + 1.0) * recon_continuum  # Correct unflatten with extended continuum
                display_flat = tapered_flux                      # Apodized continuum-removed
                
                # Store simplified view arrays for GUI plotting
                processed_spectrum['display_flux'] = display_flux
                processed_spectrum['display_flat'] = display_flat
                processed_spectrum['flux_view'] = display_flux      # preferred key
                processed_spectrum['flat_view'] = display_flat      # preferred key
                
                _LOGGER.debug(f"Generated display versions for quick preprocessing:")
                _LOGGER.debug(f"   • Flux view: (tapered_flux + 1.0) * continuum (correct unflatten formula)")
                _LOGGER.debug(f"   • Flat view: tapered_flux (apodized continuum-removed)")
                
                # Store the enhanced processed spectrum in the app controller
                self.gui.app_controller.set_processed_spectrum(processed_spectrum)
            
            # Update the main GUI to show the processed spectrum
            if hasattr(self.gui, 'toggle_flat_view') and hasattr(self.gui, 'update_plot'):
                # Enable flat view to show the processed spectrum
                self.gui.toggle_flat_view(enable=True)
                # Update the plot to show the new processed spectrum
                self.gui.update_plot()
            
            _LOGGER.info("SNID preprocessing completed successfully")
            return processed_spectrum
            
        except Exception as e:
            _LOGGER.error(f"SNID preprocessing failed: {e}")
            return None
    
    def reset_preprocessing_state(self):
        """Reset preprocessing controller state"""
        try:
            _LOGGER.debug("🔄 Resetting preprocessing controller state...")
            
            # Reset any cached preprocessing data
            if hasattr(self, 'cached_preprocessing'):
                self.cached_preprocessing = None
            
            _LOGGER.debug("Preprocessing controller state reset")
            
        except Exception as e:
            _LOGGER.error(f"Error resetting preprocessing controller: {e}") 