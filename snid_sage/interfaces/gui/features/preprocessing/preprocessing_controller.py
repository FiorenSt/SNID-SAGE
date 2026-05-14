"""
SNID SAGE - Preprocessing Controller
==================================

Handles all spectrum preprocessing operations including quick preprocessing,
manual preprocessing wizard, and SNID preprocessing pipeline.
"""

import os
import json
import numpy as np
# Use PySide6 message dialogs
from snid_sage.interfaces.gui.utils.pyside6_message_utils import messagebox
from snid_sage.snid.snid import preprocess_spectrum
import logging

_LOGGER = logging.getLogger(__name__)


class PreprocessingController:
    """Controller for handling spectrum preprocessing operations"""
    
    def __init__(self, parent_gui):
        """Initialize preprocessing controller
        
        Parameters:
        -----------
        parent_gui : ModernSNIDSageGUI
            Reference to the main GUI instance
        """
        self.gui = parent_gui
    
    def run_quick_snid_preprocessing(self):
        """Run quick SNID preprocessing with default settings"""
        if not self.gui.file_path:
            messagebox.showwarning("No Spectrum", "Please load a spectrum file first.")
            return
        
        try:
            # Update button state if it exists (for backward compatibility)
            original_text = "⚡ Quick Preprocessing"
            if hasattr(self.gui, 'quick_preprocess_btn'):
                original_text = self.gui.quick_preprocess_btn.cget('text')
                self.gui.quick_preprocess_btn.configure(text="⏳ Processing...", state='disabled')
                self.gui.master.update()
            
            # Run SNID preprocessing with default parameters
            processed_spectrum = self.run_snid_preprocessing_only()
            
            if processed_spectrum is not None:
                # No pop-up; show inline status and label instead.
                
                if hasattr(self.gui, 'preprocess_status_label'):
                    self.gui.preprocess_status_label.configure(
                        text="Preprocessed",
                        fg=self.gui.theme_manager.get_color('success') if hasattr(self.gui, 'theme_manager') else 'green',
                    )
                
                # Also update header status in GUI
                self.gui.update_header_status("Quick preprocessing complete - ready for analysis")
                
                # CRITICAL: Set view to Flat mode after preprocessing since flattened spectrum is usually shown
                if hasattr(self.gui, 'view_style') and self.gui.view_style:
                    self.gui.view_style.set("Flat")
                    _LOGGER.info("🔄 View mode set to Flat after preprocessing completion")
                    
                    # Update segmented control buttons
                    if hasattr(self.gui, '_update_segmented_control_buttons'):
                        self.gui._update_segmented_control_buttons()
                        _LOGGER.debug("✅ Segmented control buttons updated for Flat view")
                
                # Trigger state transition to PREPROCESSED
                # This will enable SNID configuration and analysis buttons
                if hasattr(self.gui, 'workflow_integrator') and self.gui.workflow_integrator:
                    # Use the workflow integrator to trigger PREPROCESSED state
                    self.gui.workflow_integrator.set_preprocessed()
                    _LOGGER.info("🔄 Quick preprocessing complete: Workflow state set to PREPROCESSED")

                    # Update the analysis-status label to indicate readiness
                    if hasattr(self.gui, 'config_status_label'):
                        self.gui.config_status_label.configure(
                            text="Ready to run SNID-SAGE",
                            fg=self.gui.theme_manager.get_color('text_primary') if hasattr(self.gui, 'theme_manager') else 'black'
                        )
                else:
                    _LOGGER.error("❌ No workflow integrator available - buttons will not update correctly!")
                
                # Switch to Flat view to show the continuum-removed spectrum
                if hasattr(self.gui, 'view_style') and self.gui.view_style:
                    self.gui.view_style.set("Flat")
                    # Trigger the view change through the plot controller
                    if hasattr(self.gui, 'plot_controller') and self.gui.plot_controller:
                        self.gui.plot_controller._on_view_style_change()
                        _LOGGER.info("🔄 Automatically switched to Flat view after preprocessing")
                
                # Update GUI to ensure changes are visible
                self.gui.master.update_idletasks()
                
                _LOGGER.debug(f"🔄 Button states updated - SNID analysis button enabled")
            
        except Exception as e:
            messagebox.showerror("Preprocessing Error", f"Quick preprocessing failed: {str(e)}")
        finally:
            # Reset button if it exists (for backward compatibility)
            if hasattr(self.gui, 'quick_preprocess_btn'):
                self.gui.quick_preprocess_btn.configure(text=original_text, state='normal')
    
    def run_quick_snid_preprocessing_silent(self):
        """Run quick SNID preprocessing with default settings without showing completion message"""
        if not self.gui.file_path:
            messagebox.showwarning("No Spectrum", "Please load a spectrum file first.")
            return
        
        try:
            # Run SNID preprocessing with default parameters
            processed_spectrum = self.run_snid_preprocessing_only()
            
            if processed_spectrum is not None:
                # Inline status – no modal dialog
                self.gui.update_header_status("Quick preprocessing complete - ready for analysis")
                
                if hasattr(self.gui, 'preprocess_status_label'):
                    self.gui.preprocess_status_label.configure(
                        text="Preprocessed",
                        fg=self.gui.theme_manager.get_color('success') if hasattr(self.gui, 'theme_manager') else 'green',
                    )
                
                # CRITICAL: Set view to Flat mode after preprocessing since flattened spectrum is usually shown
                if hasattr(self.gui, 'view_style') and self.gui.view_style:
                    self.gui.view_style.set("Flat")
                    _LOGGER.info("🔄 View mode set to Flat after preprocessing completion")
                    
                    # Update segmented control buttons
                    if hasattr(self.gui, '_update_segmented_control_buttons'):
                        self.gui._update_segmented_control_buttons()
                        _LOGGER.debug("✅ Segmented control buttons updated for Flat view")
                
                # Trigger state transition to PREPROCESSED
                # This will enable SNID configuration and analysis buttons
                if hasattr(self.gui, 'workflow_integrator') and self.gui.workflow_integrator:
                    # Use the workflow integrator to trigger PREPROCESSED state
                    self.gui.workflow_integrator.set_preprocessed()
                    _LOGGER.info("🔄 Quick preprocessing complete: Workflow state set to PREPROCESSED")

                    # Update the analysis-status label to indicate readiness
                    if hasattr(self.gui, 'config_status_label'):
                        self.gui.config_status_label.configure(
                            text="Ready to run SNID-SAGE",
                            fg=self.gui.theme_manager.get_color('text_primary') if hasattr(self.gui, 'theme_manager') else 'black'
                        )
                else:
                    _LOGGER.error("❌ No workflow integrator available - buttons will not update correctly!")
                
                # Switch to Flat view to show the continuum-removed spectrum
                if hasattr(self.gui, 'view_style') and self.gui.view_style:
                    self.gui.view_style.set("Flat")
                    # Trigger the view change through the plot controller
                    if hasattr(self.gui, 'plot_controller') and self.gui.plot_controller:
                        self.gui.plot_controller._on_view_style_change()
                        _LOGGER.info("🔄 Automatically switched to Flat view after preprocessing")
                
                # Update GUI to ensure changes are visible
                self.gui.master.update_idletasks()
                
                _LOGGER.debug(f"🔄 Button states updated - SNID analysis button enabled")
                _LOGGER.info("Silent quick preprocessing completed successfully")
            
        except Exception as e:
            messagebox.showerror("Preprocessing Error", f"Quick preprocessing failed: {str(e)}")
    
    def reset_preprocessing_state(self):
        """Reset preprocessing controller state"""
        try:
            _LOGGER.debug("🔄 Resetting preprocessing controller state...")
            
            # Clear any cached preprocessing data
            if hasattr(self, 'cached_preprocessing'):
                self.cached_preprocessing = None
            
            # Reset preprocessing parameters to defaults
            if hasattr(self.gui, 'params'):
                # Reset to default preprocessing parameters
                default_params = {
                    'savgol_window': '0',
                    'savgol_order': '3',
                    'aband_remove': False,
                    'skyclip': False,
                    'emclip_z': '-1.0',
                    'emwidth': '40.0',
                    'wavelength_masks': '',
                    'apodize_percent': '10.0',
                    'verbose': False
                }
                for key, value in default_params.items():
                    if key in self.gui.params:
                        self.gui.params[key] = value
            
            # Clear any preprocessing dialog state
            if hasattr(self.gui, 'preprocessing_dialog_open'):
                self.gui.preprocessing_dialog_open = False
            
            # Reset any cached mask data
            if hasattr(self.gui, '_last_preprocessing_masks'):
                self.gui._last_preprocessing_masks = None
            
            _LOGGER.debug("Preprocessing controller state reset")
            
        except Exception as e:
            # Log error without printing to console
            _LOGGER.error(f"Error resetting preprocessing controller: {e}")
    
    def run_manual_preprocessing_wizard(self):
        """Open manual preprocessing wizard for step-by-step control"""
        if not self.gui.file_path:
            messagebox.showwarning("No Spectrum", "Please load a spectrum file first.")
            return
        
        try:
            # This opens the step-by-step preprocessing wizard
            self.gui.open_preprocessing_dialog()
        except Exception as e:
            messagebox.showerror("Preprocessing Error", f"Failed to open manual preprocessing wizard: {str(e)}")
    
    def run_snid_preprocessing_only(self, skip_steps=None):
        """Run only the SNID preprocessing steps"""
        if not self.gui.file_path:
            messagebox.showwarning("No Spectrum", "Please load a spectrum file first.")
            return None
        
        try:
            _LOGGER.info("Running SNID preprocessing pipeline...")
            
            # Get current masks
            current_masks = self.gui._parse_wavelength_masks(self.gui.params.get('wavelength_masks', ''))
            
            # Use the modular preprocessing function with safe parameter parsing
            processed_spectrum, trace = preprocess_spectrum(
                spectrum_path=self.gui.file_path,
                # Get parameters from GUI with safe parsing
                # Using Savitzky-Golay parameters
                savgol_window=self._safe_int(self.gui.params.get('savgol_window', ''), 0),
                savgol_order=self._safe_int(self.gui.params.get('savgol_order', ''), 3),
                aband_remove=self._safe_bool(self.gui.params.get('aband_remove', '')),
                skyclip=self._safe_bool(self.gui.params.get('skyclip', '')),
                emclip_z=self._safe_float(self.gui.params.get('emclip_z', ''), -1.0),
                emwidth=self._safe_float(self.gui.params.get('emwidth', ''), 40.0),
                wavelength_masks=current_masks,
                apodize_percent=self._safe_float(self.gui.params.get('apodize_percent', ''), 10.0),
                skip_steps=skip_steps or [],
                verbose=self._safe_bool(self.gui.params.get('verbose', ''))
            )
            
            # Store the processed spectrum for later use
            self.gui.processed_spectrum = processed_spectrum
            self.gui.preprocessing_trace = trace
            
            # Add marker to identify this as standard preprocessing
            if self.gui.processed_spectrum is not None:
                self.gui.processed_spectrum['preprocessing_type'] = 'standard'
                self.gui.processed_spectrum['advanced_preprocessing'] = False
            
            # CRITICAL: Track the masks used in this preprocessing run
            self.gui._last_preprocessing_masks = current_masks
            
            # CRITICAL: Generate both flux and flattened versions for view switching
            log_wave = processed_spectrum['log_wave']
            log_flux = processed_spectrum['log_flux']     # Scaled flux on log grid
            flat_flux = processed_spectrum['flat_flux']   # Continuum-removed
            tapered_flux = processed_spectrum['tapered_flux']  # Final apodized version
            continuum = processed_spectrum['continuum']   # Fitted continuum
            
            # For the display versions, we want to show the apodization effect:
            # - Flux view: Reconstruct flux from apodized flat spectrum by multiplying with continuum
            # - Flat view: Use the apodized flat spectrum directly (tapered_flux)
            
            # Generate flux version: reconstruct from apodized flat spectrum using the correct unflatten formula
            # The flattened spectrum is defined as flux/continuum - 1, so to reconstruct: (flat + 1) * continuum
            # Extend continuum to edges if it was zeroed outside valid range
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
            try:
                mask_logbins = processed_spectrum.get('mask_logbins')
                if mask_logbins is not None:
                    mask_arr = np.asarray(mask_logbins, dtype=bool)
                    if mask_arr.size == display_flux.size:
                        display_flux = display_flux.copy()
                        display_flux[mask_arr] = 0.0
            except Exception:
                pass
            
            # Store both versions in processed_spectrum for view switching
            processed_spectrum['display_flux'] = display_flux   # For "Flux" button - apodized flux with continuum
            processed_spectrum['display_flat'] = display_flat   # For "Flat" button - apodized continuum-removed
            
            _LOGGER.debug(f"Generated display versions:")
            _LOGGER.debug(f"   • Flux view: (tapered_flux + 1.0) * continuum (correct unflatten formula)")
            _LOGGER.debug(f"   • Flat view: tapered_flux (apodized continuum-removed)")
            
            # Apply final filtering to remove zero regions for display
            filtered_wave, filtered_flux = self.gui.filter_nonzero_spectrum(
                log_wave, display_flux, processed_spectrum
            )
            
            # Plot the final spectrum  
            self.gui.plot_preprocessed_spectrum(filtered_wave, filtered_flux)
            
            # CRITICAL: Clear original spectrum data after preprocessing
            # According to spec: "Original flux spectrum is not available after preprocessing"
            if hasattr(self.gui, 'original_wave'):
                self.gui.original_wave = None
            if hasattr(self.gui, 'original_flux'):
                self.gui.original_flux = None
            
            _LOGGER.info("SNID preprocessing completed successfully")
            return processed_spectrum
            
        except Exception as e:
            _LOGGER.error(f"SNID preprocessing failed: {e}")
            messagebox.showerror("Preprocessing Error", f"SNID preprocessing failed: {str(e)}")
            return None
    
    def _safe_float(self, value, default=0.0):
        """Safely convert value to float, return default if conversion fails"""
        if value is None or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0):
        """Safely convert value to int, return default if conversion fails"""
        if value is None or value == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_bool(self, value, default=False):
        """Safely convert value to bool, return default if conversion fails"""
        if value is None or value == '':
            return default
        try:
            if isinstance(value, str):
                return value.lower() in ('1', 'true', 'yes', 'on')
            return bool(int(value))
        except (ValueError, TypeError):
            return default 
