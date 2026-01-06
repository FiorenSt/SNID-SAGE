"""
SNID SAGE - Line Detection and Galaxy Redshift Analysis
======================================================

Handles spectral line detection and automatic
galaxy redshift detection using SNID analysis with galaxy templates.
"""

import os
from PySide6 import QtWidgets
from snid_sage.snid.snid import preprocess_spectrum, run_snid_analysis
import numpy as np
import traceback

# Import the centralized logging system
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.line_detection')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.line_detection')

# Import manual redshift dialog
try:
    from snid_sage.interfaces.gui.components.pyside6_dialogs import show_manual_redshift_dialog
except ImportError:
    _LOGGER.warning("Manual redshift dialog not available")
    show_manual_redshift_dialog = None


class LineDetectionController:
    """Controller for handling line detection and galaxy redshift analysis"""
    
    def __init__(self, parent_gui):
        """Initialize line detection controller
        
        Parameters:
        -----------
        parent_gui : ModernSNIDSageGUI
            Reference to the main GUI instance
        """
        self.gui = parent_gui
        

        
    def auto_detect_and_compare_lines(self):
        """Auto-detect spectral lines in the current spectrum"""
        try:
            if not hasattr(self.gui, 'snid_results') or not self.gui.snid_results:
                QtWidgets.QMessageBox.warning(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                              "No Data", "Please run SNID analysis first to detect lines.")
                return
            # Remove temporary placeholder: no-op for now
            return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                           "Line Detection Error", f"Failed to run line detection: {str(e)}")
    
    def search_nist_for_lines(self):
        """Search NIST database for spectral lines"""
        return
    
    def clear_line_markers(self):
        """Clear all line markers from the plot"""
        try:
            _LOGGER.debug("Clearing line markers...")
            # Clear markers and refresh plot
            if hasattr(self.gui, 'line_markers'):
                self.gui.line_markers.clear()
            
            # Refresh the current view to remove markers
            if hasattr(self.gui, 'snid_results') and self.gui.snid_results:
                self.gui.refresh_current_view()
            
        except Exception as e:
            print(f"Error clearing line markers: {e}")
    
    def reset_line_detection(self):
        """Reset line detection controller state"""
        try:
            _LOGGER.debug("🔄 Resetting line detection controller state...")
            
            # Clear line markers
            self.clear_line_markers()
            
            # Reset any cached line detection data
            if hasattr(self.gui, 'detected_lines'):
                self.gui.detected_lines = None
            
            # Reset line detection parameters to defaults
            if hasattr(self, 'line_detection_params'):
                self.line_detection_params = {}
            
            # Clear any galaxy redshift results
            if hasattr(self.gui, 'galaxy_redshift_result'):
                self.gui.galaxy_redshift_result = None
            
            # Reset any NIST search results
            if hasattr(self, 'nist_search_results'):
                self.nist_search_results = None
            
            _LOGGER.debug("Line detection controller state reset")
            
        except Exception as e:
            print(f"❌ Error resetting line detection controller: {e}")
    
    def open_combined_redshift_selection(self):
        """Open the combined redshift selection dialog with both manual and automatic options"""
        if not show_manual_redshift_dialog:
            QtWidgets.QMessageBox.critical(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                           "Feature Unavailable",
                                           "Manual redshift dialog is not available.\nPlease check your installation.")
            return
        
        if not self.gui.file_path:
            QtWidgets.QMessageBox.warning(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                          "No Spectrum", "Please load a spectrum first.")
            return
        
        try:
            _LOGGER.info("🌌 Starting combined redshift selection...")



            # Get current spectrum data 
            spectrum_data = self._get_current_spectrum_data()
            if not spectrum_data:
                QtWidgets.QMessageBox.critical(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                               "Spectrum Error",
                                               "Could not access current spectrum data.")
                return

            # Get current redshift estimate if available
            current_redshift = 0.0
            if hasattr(self.gui, 'params') and 'redshift' in self.gui.params:
                try:
                    current_redshift = float(self.gui.params['redshift'])
                except (ValueError, TypeError):
                    current_redshift = 0.0

            # Show enhanced manual redshift dialog with auto search capability
            # Using exactly the same approach as preprocessing dialog - no theme interactions
            result_redshift = show_manual_redshift_dialog(
                parent=self.gui.master,
                spectrum_data=spectrum_data,
                current_redshift=current_redshift,
                include_auto_search=True,  # Enable auto search functionality
                auto_search_callback=self._perform_automatic_redshift_search  # Callback for auto search
            )

            if result_redshift is not None:
                # Handle both float format and dict format
                if isinstance(result_redshift, dict):
                    # New format with mode information
                    redshift_value = result_redshift['redshift']
                    mode = result_redshift.get('mode', 'search')
                    forced_redshift = result_redshift.get('forced_redshift')
                    search_range = result_redshift.get('search_range', 0.01)  # Default to 0.01 if not specified

                    # Apply redshift configuration to analysis controller
                    if hasattr(self.gui, 'analysis_controller'):
                        if mode == 'force':
                            self.gui.analysis_controller.redshift_config.update({
                                'mode': 'forced',
                                'forced_redshift': forced_redshift
                            })
                            _LOGGER.info(f"Manual redshift applied with FORCED mode: z = {forced_redshift:.6f}")
                        else:
                            self.gui.analysis_controller.redshift_config.update({
                                'mode': 'automatic',
                                'forced_redshift': None,
                                'search_range': search_range
                            })
                            _LOGGER.info(f"Manual redshift applied with SEARCH mode: z = {redshift_value:.6f} ±{search_range:.6f}")

                    self._apply_manual_redshift(redshift_value, result_redshift)
                else:
                    # Float redshift value (backward compatibility)
                    self._apply_manual_redshift(result_redshift)
                    _LOGGER.info(f"Manual redshift applied: z = {result_redshift:.6f}")
            else:
                _LOGGER.info("Redshift selection cancelled")



        except Exception as e:
            _LOGGER.error(f"Error in combined redshift selection: {e}")
            QtWidgets.QMessageBox.critical(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                           "Redshift Selection Error",
                                           f"Failed to start redshift selection:\n{str(e)}")
    
    def _perform_automatic_redshift_search(self, progress_callback=None):
        """Perform automatic redshift search using already preprocessed spectrum"""
        try:
            if progress_callback:
                progress_callback("Initializing automatic redshift search...")
            
            # Import necessary modules  
            from snid_sage.snid.snid import run_snid_analysis
            import os
            import numpy as np
            
            # Check for preprocessed spectrum first (new workflow)
            if hasattr(self.gui, 'processed_spectrum') and self.gui.processed_spectrum is not None:
                if progress_callback:
                    progress_callback("Using preprocessed spectrum for galaxy template correlation...")
                
                # Use the flattened, tapered spectrum for correlation (like actual SNID)
                processed = self.gui.processed_spectrum
                
                # Get the spectrum ready for FFT correlation
                if 'tapered_flux' in processed:
                    tapered_flux = processed['tapered_flux']
                    spectrum_source = "tapered_flux (apodized flattened)"
                elif 'display_flat' in processed:
                    tapered_flux = processed['display_flat'] 
                    spectrum_source = "display_flat (flattened)"
                elif 'flat_flux' in processed:
                    tapered_flux = processed['flat_flux']
                    spectrum_source = "flat_flux (flattened)"
                else:
                    _LOGGER.error("No flattened spectrum data available for correlation")
                    if progress_callback:
                        progress_callback("Error: No flattened spectrum data available")
                    return {'success': False, 'error': 'No flattened spectrum data available for correlation'}
                
                log_wave = processed.get('log_wave')
                
                if log_wave is None or tapered_flux is None:
                    _LOGGER.error("Missing wavelength or flux data in preprocessed spectrum")
                    if progress_callback:
                        progress_callback("Error: Missing wavelength or flux data")
                    return {'success': False, 'error': 'Missing wavelength or flux data in preprocessed spectrum'}
                
                _LOGGER.info(f"🔍 Auto redshift search: Using {spectrum_source}")
                _LOGGER.info(f"🔍 Spectrum length: {len(tapered_flux)} points")
                
                if progress_callback:
                    progress_callback("Running galaxy template correlation analysis...")
                
                # Run SNID analysis with ONLY galaxy templates and NO preprocessing
                try:
                    # Align Host redshift search with the *normal* GUI pipeline:
                    # - same active profile id (grid)
                    # - same templates directory resolution
                    # - same analysis knobs (lapmin / peak_window_size / hsigma threshold / max_output_templates)
                    app = getattr(self.gui, 'app_controller', None)
                    try:
                        active_profile_id = getattr(app, 'active_profile_id', None) or getattr(self.gui, 'active_profile_id', None)
                    except Exception:
                        active_profile_id = None
                    active_profile_id = str(active_profile_id or self._resolve_active_profile_id() or 'optical').strip()

                    pid = str(active_profile_id).strip().lower()
                    zmax_profile = 2.5 if pid == 'onir' else 1.0

                    # Resolve templates dir in the same way as the main analysis controller when possible
                    templates_dir = None
                    try:
                        if app is not None and hasattr(app, '_resolve_templates_directory'):
                            templates_dir = app._resolve_templates_directory(profile_id=active_profile_id)  # type: ignore[attr-defined]
                    except Exception:
                        templates_dir = None
                    if not templates_dir:
                        templates_dir = self.gui.get_templates_dir()
                    if not templates_dir or not os.path.exists(templates_dir):
                        raise Exception("Templates directory not found")

                    # Pull current analysis knobs for parity (fallback to the normal defaults)
                    analysis_cfg = {}
                    try:
                        if app is not None and getattr(app, 'current_config', None):
                            analysis_cfg = (app.current_config.get('analysis', {}) or {})
                    except Exception:
                        analysis_cfg = {}
                    last_kwargs = {}
                    try:
                        if app is not None and getattr(app, 'last_analysis_kwargs', None):
                            last_kwargs = (app.last_analysis_kwargs or {})
                    except Exception:
                        last_kwargs = {}

                    # Match the normal GUI analysis knobs (prefer last run, then config, then defaults).
                    try:
                        lapmin = float(last_kwargs.get('lapmin', analysis_cfg.get('lapmin', 0.3)) or 0.3)
                    except Exception:
                        lapmin = 0.3
                    # Clamp overlap fraction defensively
                    try:
                        lapmin = max(0.0, min(1.0, float(lapmin)))
                    except Exception:
                        lapmin = 0.3
                    try:
                        peak_window_size = int(last_kwargs.get('peak_window_size', analysis_cfg.get('peak_window_size', 10)) or 10)
                    except Exception:
                        peak_window_size = 10
                    try:
                        hsigma_thr = float(
                            last_kwargs.get('hsigma_lap_ccc_threshold', analysis_cfg.get('hsigma_lap_ccc_threshold', 1.5)) or 1.5
                        )
                    except Exception:
                        hsigma_thr = 1.5
                    try:
                        max_out = int(last_kwargs.get('max_output_templates', analysis_cfg.get('max_output_templates', 10)) or 10)
                    except Exception:
                        max_out = 10

                    results, analysis_trace = run_snid_analysis(
                        processed_spectrum=processed,  # Use the processed spectrum dict directly
                        templates_dir=templates_dir,
                        # Template filtering - galaxy types only
                        type_filter=['Galaxy', 'Gal'],  # Include both Galaxy and Gal types
                        # Analysis parameters
                        zmin=-0.01,
                        zmax=float(zmax_profile),
                        # Correlation parameters
                        lapmin=lapmin,
                        peak_window_size=peak_window_size,
                        hsigma_lap_ccc_threshold=hsigma_thr,
                        # Output control
                        max_output_templates=max_out,
                        verbose=False,
                        show_plots=False,
                        save_plots=False,
                        # Use active profile from config/env if available to keep grid consistent
                        profile_id=active_profile_id
                    )
                    
                    if progress_callback:
                        progress_callback("Analysis complete - processing results...")
                    
                    if results and hasattr(results, 'best_matches') and results.best_matches:
                        best_match = results.best_matches[0]

                        # Prefer the winning cluster's hybrid redshift (normal-run behavior)
                        chosen_z = None
                        q_cluster = None
                        template_desc = None
                        try:
                            clres = getattr(results, 'clustering_results', None)
                            if clres and clres.get('success') and clres.get('best_cluster'):
                                bc = clres.get('best_cluster') or {}
                                zc = bc.get('enhanced_redshift', None)
                                if zc is not None and np.isfinite(float(zc)):
                                    chosen_z = float(zc)
                                    # True Q_cluster is the penalized top-5 score.
                                    q_cluster = float(bc.get('penalized_score', bc.get('composite_score', 0.0)) or 0.0)
                                    template_desc = f"{bc.get('type', 'Galaxy')} cluster {bc.get('cluster_id', 0)}"
                        except Exception:
                            pass

                        # Fallbacks
                        if chosen_z is None:
                            try:
                                zc = getattr(results, 'consensus_redshift', None)
                                if zc is not None and np.isfinite(float(zc)):
                                    chosen_z = float(zc)
                                    template_desc = "consensus redshift"
                            except Exception:
                                pass
                        if chosen_z is None:
                            chosen_z = float(best_match.get('redshift', 0.0) or 0.0)
                            template_desc = "best match"

                        return {
                            'success': True,
                            'redshift': chosen_z,
                            'q_cluster': q_cluster,
                            'template': template_desc,
                            'snid_result': results,
                            'analysis_trace': analysis_trace,
                        }

                    _LOGGER.warning("⚠️ No template matches found in SNID results")
                    return {'success': False, 'error': 'No galaxy template matches found'}
                        
                except Exception as e:
                    _LOGGER.error(f"SNID analysis failed: {e}")
                    if progress_callback:
                        progress_callback(f"Analysis failed: {str(e)}")
                    return {'success': False, 'error': f'SNID analysis failed: {str(e)}'}
            
            # Fallback: No preprocessed spectrum available
            else:
                _LOGGER.error("No preprocessed spectrum available for automatic redshift search")
                _LOGGER.error("Please run preprocessing first before using automatic redshift search")
                if progress_callback:
                    progress_callback("Error: No preprocessed spectrum available. Run preprocessing first.")
                return {'success': False, 'error': 'No preprocessed spectrum available. Run preprocessing first.'}
                
        except Exception as e:
            _LOGGER.error(f"Automatic redshift search failed: {e}")
            _LOGGER.error(f"   Exception details: {traceback.format_exc()}")
            if progress_callback:
                progress_callback(f"Search failed: {str(e)}")
            return {'success': False, 'error': f'Automatic redshift search failed: {str(e)}'}

    def _resolve_active_profile_id(self) -> str:
        """Resolve active profile id from env/config; default to 'optical'."""
        try:
            import os
            pid = os.environ.get('SNID_SAGE_ACTIVE_PROFILE') or os.environ.get('SNID_SAGE_PROFILE')
            if pid:
                return str(pid)
            try:
                from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
                cfg = ConfigurationManager().load_config()
                return str((cfg.get('processing', {}) or {}).get('active_profile_id', 'optical') or 'optical')
            except Exception:
                return 'optical'
        except Exception:
            return 'optical'
    
    def _get_current_spectrum_data(self):
        """Get the current spectrum data for manual redshift determination"""
        try:
            # PRIORITY 1: Try to get preprocessed FLATTENED spectrum data (new workflow)
            if hasattr(self.gui, 'processed_spectrum') and self.gui.processed_spectrum is not None:
                processed = self.gui.processed_spectrum
                
                # Get the flattened spectrum data (continuum-removed) like the main GUI
                if 'log_wave' in processed:
                    log_wave = processed['log_wave']
                    
                    # Use display_flat if available (best quality flattened), otherwise fall back to flat_flux
                    if 'display_flat' in processed:
                        flat_flux = processed['display_flat']
                        spectrum_type = 'display_flat (continuum-removed)'
                    elif 'flat_flux' in processed:
                        flat_flux = processed['flat_flux']
                        spectrum_type = 'flat_flux (continuum-removed)'
                    else:
                        _LOGGER.error("No flattened spectrum data available in processed_spectrum")
                        return None
                    
                    # Apply zero-region filtering like the main GUI
                    filtered_wave, filtered_flux = self._filter_nonzero_spectrum(
                        log_wave, flat_flux, processed
                    )
                    
                    if filtered_wave is not None and filtered_flux is not None and len(filtered_wave) > 0:
                        _LOGGER.info(f"🎯 Redshift dialog: Using preprocessed flattened spectrum ({spectrum_type})")
                        _LOGGER.info(f"🎯 Wavelength range: {filtered_wave.min():.1f} - {filtered_wave.max():.1f} Å")
                        _LOGGER.info(f"🎯 Data points: {len(filtered_wave)} (zero-padding removed)")
                        
                        return {
                            'wavelength': filtered_wave,
                            'flux': filtered_flux,
                            'source': 'preprocessed_spectrum',
                            'spectrum_type': spectrum_type
                        }
            
            # PRIORITY 2: Try original spectrum (before preprocessing)
            if hasattr(self.gui, 'original_wave') and hasattr(self.gui, 'original_flux'):
                if self.gui.original_wave is not None and self.gui.original_flux is not None:
                    _LOGGER.info(f"🎯 Redshift dialog: Using original spectrum for display")
                    _LOGGER.info(f"🎯 Wavelength range: {self.gui.original_wave.min():.1f} - {self.gui.original_wave.max():.1f} Å")
                    
                    return {
                        'wavelength': self.gui.original_wave,
                        'flux': self.gui.original_flux,
                        'source': 'original_spectrum',
                        'spectrum_type': 'original'
                    }
            
            # PRIORITY 3: No spectrum data available
            _LOGGER.error("No spectrum data available for redshift dialog")
            return None
            
        except Exception as e:
            _LOGGER.error(f"Error getting spectrum data: {e}")
            _LOGGER.error(f"   Exception details: {traceback.format_exc()}")
            return None
    
    def _apply_manual_redshift(self, redshift: float, mode_result=None):
        """Apply manually determined redshift"""
        try:
            # Update SNID parameters with manual redshift
            self.gui.params['redshift'] = redshift
            
            # Store galaxy redshift result
            if mode_result and isinstance(mode_result, dict):
                self.gui.galaxy_redshift_result = {
                    'redshift': redshift,
                    'method': 'manual',
                    'confidence': 'user_determined',
                    'mode_result': mode_result  # Store the complete result
                }
            else:
                self.gui.galaxy_redshift_result = {
                    'redshift': redshift,
                    'method': 'manual',
                    'confidence': 'user_determined'
                }
            
            # Update redshift entry field if it exists (skip tkinter-specific code in PySide6)
            if hasattr(self.gui, 'redshift_entry'):
                try:
                    # If redshift_entry is a Qt widget with setText
                    if hasattr(self.gui.redshift_entry, 'setText'):
                        self.gui.redshift_entry.setText(f"{redshift:.6f}")
                except Exception:
                    pass
            
            # Compose status text with additional context (range or forced)
            status_text = None

            # Determine if we are in FORCED mode
            is_forced = False
            forced_z = None
            search_range = None

            if hasattr(self.gui, 'analysis_controller'):
                ac_cfg = self.gui.analysis_controller.redshift_config
                is_forced = ac_cfg.get('mode') == 'forced'
                forced_z = ac_cfg.get('forced_redshift', redshift) if is_forced else None

            if is_forced:
                status_text = f"z = {forced_z:.6f} (forced)"
            else:
                # If range information is available from mode_result, include it
                if mode_result and isinstance(mode_result, dict):
                    search_range = mode_result.get('search_range', 0.01)
                else:
                    # Fall back to global analysis controller configuration if present
                    ac_obj = getattr(self.gui, 'analysis_controller', None)
                    if ac_obj:
                        search_range = ac_obj.redshift_config.get('search_range', 0.01)

                status_text = f"z = {redshift:.6f} ±{search_range:.6f}" if search_range is not None else f"z = {redshift:.6f}"

            # Update status label without accessing theme manager - use simple fixed colors
            if hasattr(self.gui, 'redshift_status_label'):
                self.gui.redshift_status_label.configure(
                    text=status_text,
                    fg=self.gui.theme_manager.get_color('text_primary') if hasattr(self.gui, 'theme_manager') else 'black'
                )
            
            # Trigger workflow state update without any theme operations
            if hasattr(self.gui, 'workflow_integrator') and self.gui.workflow_integrator:
                self.gui.workflow_integrator.set_redshift_determined()
            elif hasattr(self.gui, 'update_button_states'):
                # Fallback for safety if the workflow integrator is somehow
                # unavailable (should not happen in normal operation).
                self.gui.update_button_states()
            
            # Log the redshift application without disrupting themes
            _LOGGER.info(f"Manual redshift applied: z = {redshift:.6f}")
            
            
            
        except Exception as e:
            _LOGGER.error(f"Error applying manual redshift: {e}")
            QtWidgets.QMessageBox.critical(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                           "Error", f"Failed to apply redshift: {str(e)}")
    
    def _show_no_results_dialog(self, progress_window):
        """Show dialog when no galaxy results are found"""
        progress_window.destroy()
        
        # Show options including manual redshift determination using Qt
        msg = QtWidgets.QMessageBox(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None)
        msg.setWindowTitle("No Results")
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText(
            "No galaxy redshift matches found.\n\n"
            "This could mean:\n"
            "• The spectrum has no clear galaxy features\n"
            "• The spectrum quality is too low\n\n"
            "Would you like to try manual redshift determination?"
        )
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
        res = msg.exec()

        # Do not change existing redshift status label; lack of match is a normal condition
        
        if res == QtWidgets.QMessageBox.Yes:  # Yes - manual redshift
            self.open_combined_redshift_selection()
        elif res == QtWidgets.QMessageBox.Cancel:  # Cancel - show help
            QtWidgets.QMessageBox.information(self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
                                              "Try Different Parameters",
                                              "Suggestions for improving galaxy redshift detection:\n\n"
                                              "• Check if the spectrum is actually a galaxy\n"
                                              "• Try adjusting the redshift range (zmin/zmax)\n"
                                              "• Use different preprocessing parameters\n"
                                              "• Consider manual redshift determination\n"
                                              "• Check if the spectrum has sufficient quality")
    
    def _show_error_dialog(self, progress_window, error_msg):
        """Show dialog when an error occurs"""
        progress_window.destroy()
        
        # Show error with manual redshift option via Qt
        res = QtWidgets.QMessageBox.question(
            self.gui if isinstance(self.gui, QtWidgets.QWidget) else None,
            "Analysis Error",
            f"Galaxy redshift detection failed:\n\n{error_msg}\n\nWould you like to try manual redshift determination instead?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if res == QtWidgets.QMessageBox.Yes:
            self.open_combined_redshift_selection()
    
    def _show_results_dialog(self, progress_window, best_z, best_metric, best_template, confidence, 
                            redshifts, metrics, template_names, snid_result):
        """Show dialog with galaxy redshift results (Qt minimal dialog)"""
        progress_window.destroy()
        parent = self.gui if isinstance(self.gui, QtWidgets.QWidget) else None
        summary = (
            f"Redshift (z): {best_z:.6f}\n"
            f"Metric (HσLAP-CCC): {best_metric:.2f}\n"
            f"Template: {best_template}\n"
            f"Confidence: {confidence}%\n\n"
            f"Accept this redshift?"
        )
        msg = QtWidgets.QMessageBox(parent)
        msg.setWindowTitle("Galaxy Redshift Results")
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText(summary)
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
        msg.button(QtWidgets.QMessageBox.Yes).setText("Accept")
        msg.button(QtWidgets.QMessageBox.No).setText("Manual...")
        msg.button(QtWidgets.QMessageBox.Cancel).setText("Close")
        res = msg.exec()

        if res == QtWidgets.QMessageBox.Yes:
            # Update any redshift-related parameters
            self.gui.params['redshift'] = best_z

            # Update redshift status label
            if hasattr(self.gui, 'redshift_status_label'):
                try:
                    self.gui.redshift_status_label.setText(f"✅ z = {best_z:.6f} (auto, HσLAP-CCC {best_metric:.2f})")
                except Exception:
                    pass

            # Store auto redshift result
            self.gui.galaxy_redshift_result = {
                'redshift': best_z,
                'method': 'auto',
                'confidence': confidence,
                'hsigma_lap_ccc': best_metric,
                'template': best_template
            }

            QtWidgets.QMessageBox.information(
                parent,
                "Redshift Accepted",
                (
                    f"Galaxy redshift z = {best_z:.6f} has been set.\n\n"
                    f"SNID analysis will now search in a tight range around this redshift.\n"
                    f"Search range: z = {max(-0.01, best_z-0.05):.6f} to {best_z+0.05:.6f}"
                )
            )
        elif res == QtWidgets.QMessageBox.No:
            self.open_combined_redshift_selection()
    
    def _safe_float(self, value, default=0.0):
        """Safely convert value to float"""
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0):
        """Safely convert value to int"""
        try:
            return int(float(value)) if value else default
        except (ValueError, TypeError):
            return default
    
    def _safe_bool(self, value, default=False):
        """Safely convert value to bool"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value) if value is not None else default 

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _ensure_flat_view_active(self):
        """Guarantee that the GUI remains in 'Flat' view and refresh the segmented buttons."""
        try:
            if hasattr(self.gui, 'view_style') and self.gui.view_style:
                if self.gui.view_style.get() != "Flat":
                    self.gui.view_style.set("Flat")
                # Always refresh colours
                if hasattr(self.gui, '_update_segmented_control_buttons'):
                    self.gui._update_segmented_control_buttons()
        except Exception:
            pass 
