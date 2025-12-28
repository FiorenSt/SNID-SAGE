"""
SNID SAGE - Dialog Manager
==========================

Dedicated dialog manager for PySide6 GUI that handles repetitive dialog opening patterns.
This includes common validation, error handling, fallback dialogs, and result processing.

This extracts the repetitive dialog logic from the main GUI class to keep it clean.

Developed by Fiorenzo Stoppa for SNID SAGE
"""

from typing import Optional, Dict, Any, Callable
import math

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.dialog_manager')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.dialog_manager')


class DialogManager:
    """
    Manages dialog opening patterns for PySide6 GUI
    
    This class handles:
    - Common spectrum validation before opening dialogs
    - Import error handling with fallback dialogs
    - Dialog result processing
    - Status updates after dialog completion
    - Error handling and logging
    """
    
    def __init__(self, main_window):
        """
        Initialize the dialog manager
        
        Args:
            main_window: Reference to the main PySide6 GUI window
        """
        self.main_window = main_window
        self.app_controller = main_window.app_controller
    
    def open_preprocessing_dialog(self):
        """Open preprocessing dialog with spectrum validation and result handling"""
        try:
            # Check if spectrum is loaded
            wave, flux = self._validate_spectrum_loaded("preprocessing")
            if wave is None:
                return
            
            # Try to open the preprocessing dialog
            success = self._try_open_dialog(
                dialog_import="snid_sage.interfaces.gui.components.pyside6_dialogs.preprocessing_dialog",
                dialog_class="PySide6PreprocessingDialog",
                dialog_args=[self.main_window, (wave, flux)],
                dialog_name="Preprocessing",
                success_callback=self._handle_preprocessing_success,
                fallback_callback=self._handle_preprocessing_fallback
            )
            
        except Exception as e:
            _LOGGER.error(f"Error opening preprocessing dialog: {e}")
    
    def open_redshift_dialog(self):
        """Open redshift selection dialog with validation and result handling"""
        try:
            # If an analysis has already been run, warn that opening Host Redshift
            # will reset the tool back to just-after-load (same UX as preprocessing)
            try:
                analysis_present = bool(getattr(self.app_controller, 'snid_results', None))
            except Exception:
                analysis_present = False

            if analysis_present:
                reply = QtWidgets.QMessageBox.question(
                    self.main_window,
                    "Reset to Post-Load?",
                    (
                        "You have already run an analysis.\n\n"
                        "Opening Host Redshift will clear previous preprocessing, analysis results, overlays, and advanced views.\n"
                        "The loaded spectrum will be kept, and the GUI will return to the state just after loading the spectrum.\n\n"
                        "Do you want to continue?"
                    ),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                # Reset to FILE_LOADED while preserving spectrum and refresh UI accordingly
                try:
                    if hasattr(self.app_controller, 'reset_to_file_loaded_state'):
                        self.app_controller.reset_to_file_loaded_state()
                except Exception:
                    pass
                # Update labels and plot to flux without overlays, mirroring preprocessing reset
                try:
                    if hasattr(self.main_window, 'preprocess_status_label'):
                        self.main_window.preprocess_status_label.setText("Preprocessing not run")
                        self.main_window.preprocess_status_label.setStyleSheet(
                            "font-style: italic; color: #475569; font-size: 10px !important; "
                            "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                            "line-height: 1.0 !important;"
                        )
                    # Reset configuration/analysis status label so it does not show 'Analysis Complete'
                    if hasattr(self.main_window, 'config_status_label'):
                        self.main_window.config_status_label.setText("Default SNID parameters loaded")
                        self.main_window.config_status_label.setStyleSheet(
                            "font-style: italic; color: #475569; font-size: 10px !important; "
                            "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                            "line-height: 1.0 !important;"
                        )
                    if hasattr(self.main_window, 'redshift_status_label'):
                        self.main_window.redshift_status_label.setText("Redshift not set (optional)")
                        self.main_window.redshift_status_label.setStyleSheet(
                            "font-style: italic; color: #475569; font-size: 10px !important; "
                            "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                            "line-height: 1.0 !important;"
                        )
                    if hasattr(self.main_window, 'status_label'):
                        self.main_window.status_label.setText("Spectrum loaded - ready to preprocess")
                    # Ensure spectrum plot without overlays in Flux view
                    if hasattr(self.main_window, 'event_handlers'):
                        self.main_window.event_handlers.on_view_change('flux')
                    if hasattr(self.main_window, 'plot_manager'):
                        self.main_window.plot_manager.plot_spectrum('flux')
                except Exception:
                    pass

            # Check if spectrum is loaded
            wave, flux = self._validate_spectrum_loaded("redshift selection")
            if wave is None:
                return
            
            # Get current redshift value
            current_redshift = getattr(self.app_controller, 'manual_redshift', 0.0) or 0.0
            
            # Try to use PySide6 manual redshift dialog
            try:
                from snid_sage.interfaces.gui.components.pyside6_dialogs.manual_redshift_dialog import show_manual_redshift_dialog
                
                spectrum_data = {'wavelength': wave, 'flux': flux}
                
                result = show_manual_redshift_dialog(
                    parent=self.main_window,
                    spectrum_data=spectrum_data,
                    current_redshift=current_redshift,
                    include_auto_search=True
                )
                
                if result is not None:
                    self._handle_redshift_result(result)
                else:
                    _LOGGER.info("Manual redshift dialog cancelled")
                    
            except ImportError:
                # Fallback to simple input dialog
                self._show_redshift_fallback(current_redshift)
                
        except Exception as e:
            _LOGGER.error(f"Error opening redshift dialog: {e}")
    
    def open_settings_dialog(self):
        """Open settings dialog with result handling"""
        try:
            success = self._try_open_dialog(
                dialog_import="snid_sage.interfaces.gui.components.pyside6_dialogs.settings_dialog",
                dialog_class="PySide6SettingsDialog",
                dialog_args=[self.main_window, getattr(self.app_controller, 'gui_settings', {})],
                dialog_name="Settings",
                success_callback=self._handle_settings_success,
                fallback_callback=lambda: None
            )
            
        except Exception as e:
            _LOGGER.error(f"Error opening settings dialog: {e}")
    
    def open_emission_line_dialog(self):
        """Open emission line dialog with spectrum validation"""
        try:
            _LOGGER.info("🔬 Starting emission line dialog opening process...")
            
            # Check if spectrum is loaded - use flat spectrum for SN line analysis
            _LOGGER.info("📊 Checking if spectrum is loaded...")
            spectrum_view = 'flat'  # Always use flat spectrum for SN lines
            _LOGGER.info(f"📊 Using {spectrum_view} spectrum for SN line analysis")
            
            wave, flux = self.app_controller.get_spectrum_for_view(spectrum_view)
            _LOGGER.info(f"📊 Retrieved spectrum data - wave: {wave is not None}, flux: {flux is not None}")
            
            if wave is None or flux is None:
                _LOGGER.warning("⚠️ No spectrum data available")
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "No Spectrum", 
                    f"Please load a spectrum file before emission line analysis."
                )
                return
            
            _LOGGER.info(f"📊 Spectrum shape - wave: {len(wave) if wave is not None else 'None'}, flux: {len(flux) if flux is not None else 'None'}")
            
            # Optionally inform user about analysis benefits
            if not hasattr(self.app_controller, 'snid_results') or self.app_controller.snid_results is None:
                _LOGGER.info("⚠️ Opening emission line analysis without SNID results - redshift estimates may be less accurate")
            
            # Try to use the PySide6 multi-step emission dialog
            try:
                _LOGGER.info("🔧 Attempting to import PySide6 emission dialog...")
                # Import directly to avoid matplotlib conflicts in other modules
                import sys
                
                # Temporarily modify path to import specific module
                from snid_sage.interfaces.gui.components.pyside6_dialogs.multi_step_emission_dialog import show_pyside6_multi_step_emission_dialog
                _LOGGER.info("✅ Successfully imported PySide6 emission dialog")
                
                # Use the current view spectrum data (flattened if in flat view)
                spectrum_data = {'wave': wave, 'flux': flux}
                _LOGGER.info(f"📊 Prepared spectrum data: {spectrum_data.keys()}")
                
                # Get redshift estimates
                galaxy_redshift = 0.0
                cluster_median_redshift = 0.0
                
                _LOGGER.info("🔧 Getting redshift estimates...")
                if hasattr(self.app_controller, 'snid_results') and self.app_controller.snid_results:
                    try:
                        # Try to get subtype redshift from clustering results first
                        if (hasattr(self.app_controller.snid_results, 'clustering_results') and 
                            self.app_controller.snid_results.clustering_results and
                            self.app_controller.snid_results.clustering_results.get('success')):
                            
                            clustering_results = self.app_controller.snid_results.clustering_results
                            
                            # Priority: user_selected_cluster > best_cluster
                            winning_cluster = None
                            if 'user_selected_cluster' in clustering_results:
                                winning_cluster = clustering_results['user_selected_cluster']
                                _LOGGER.info("📊 Using user-selected cluster for redshift")
                            elif 'best_cluster' in clustering_results:
                                winning_cluster = clustering_results['best_cluster']
                                _LOGGER.info("📊 Using best cluster for redshift")
                            
                            if winning_cluster:
                                # Prefer subtype-specific redshift for spectral lines
                                subtype_z = winning_cluster.get('subtype_redshift', None)
                                if isinstance(subtype_z, (int, float)) and not math.isnan(float(subtype_z)) and float(subtype_z) > 0:
                                    cluster_median_redshift = float(subtype_z)
                                    _LOGGER.info(f"🏷️ Using best subtype redshift: {cluster_median_redshift:.6f}")
                                else:
                                    # Fall back to enhanced/weighted cluster redshift
                                    weighted_z = winning_cluster.get('enhanced_redshift', winning_cluster.get('weighted_mean_redshift', 0.0))
                                    if isinstance(weighted_z, (int, float)) and not math.isnan(float(weighted_z)) and float(weighted_z) > 0:
                                        cluster_median_redshift = float(weighted_z)
                                        _LOGGER.info(f"📊 Found weighted cluster redshift (fallback): {cluster_median_redshift:.6f}")
                                    else:
                                        _LOGGER.info("📊 No valid subtype or weighted redshift in cluster, falling back to matches")
                        
                        # Fallback: use first match redshift if no weighted redshift available
                        if cluster_median_redshift == 0.0:
                            if hasattr(self.app_controller.snid_results, 'matches') and len(self.app_controller.snid_results.matches) > 0:
                                cluster_median_redshift = self.app_controller.snid_results.matches[0].get('redshift', 0.0)
                                _LOGGER.info(f"📊 Found fallback redshift from first match: {cluster_median_redshift}")
                        
                    except Exception as redshift_error:
                        _LOGGER.warning(f"⚠️ Error getting redshift estimates: {redshift_error}")
                
                _LOGGER.info(f"📊 Final redshifts - galaxy: {galaxy_redshift}, cluster: {cluster_median_redshift}")
                
                _LOGGER.info("Creating emission line dialog...")
                dialog = show_pyside6_multi_step_emission_dialog(
                    parent=self.main_window,
                    spectrum_data=spectrum_data,
                    theme_manager=self.main_window.theme_manager,
                    galaxy_redshift=galaxy_redshift,
                    cluster_median_redshift=cluster_median_redshift
                )
                _LOGGER.info("✅ Emission line dialog created successfully")
                
                self._update_status("emission", "Dialog opened", success_style=True)
                _LOGGER.info(f"🔬 Emission line analysis dialog opened successfully using {spectrum_view} view")
                
            except ImportError as e:
                _LOGGER.error(f"❌ Could not import emission line dialog: {e}")
                self._show_emission_line_fallback()
                
        except Exception as e:
            _LOGGER.error(f"❌ Error opening emission line dialog: {e}")
            import traceback
            _LOGGER.error(f"❌ Full traceback: {traceback.format_exc()}")
            QtWidgets.QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to open emission line dialog:\n{str(e)}"
            )
    
    def open_chat_dialog(self):
        """Open AI chat dialog"""
        try:
            success = self._try_open_dialog(
                dialog_import="snid_sage.interfaces.gui.components.pyside6_dialogs.enhanced_ai_assistant_dialog",
                dialog_class="PySide6EnhancedAIAssistantDialog",
                dialog_args=[self.main_window, getattr(self.app_controller, 'snid_results', None)],
                dialog_name="AI Assistant",
                success_callback=lambda dialog: (dialog.show(), _LOGGER.info("AI Assistant dialog opened")),
                fallback_callback=lambda: None,
                use_show=True  # Use show() instead of exec()
            )
            
        except Exception as e:
            _LOGGER.error(f"Error opening AI Assistant dialog: {e}")
    
    def open_configuration_dialog(self):
        """Open SNID-SAGE configuration dialog"""
        try:
            success = self._try_open_dialog(
                dialog_import="snid_sage.interfaces.gui.components.pyside6_dialogs.configuration_dialog",
                dialog_class="PySide6ConfigurationDialog",
                dialog_args=[self.main_window],
                dialog_name="SNID-SAGE Configuration",
                success_callback=self._handle_configuration_success,
                fallback_callback=lambda: None
            )
            
        except Exception as e:
            _LOGGER.error(f"Error opening configuration dialog: {e}")
    
    def open_mask_manager_dialog(self):
        """Open mask manager dialog"""
        try:
            # Check if spectrum is loaded
            wave, flux = self._validate_spectrum_loaded("mask management")
            if wave is None:
                return
            
            success = self._try_open_dialog(
                dialog_import="snid_sage.interfaces.gui.components.pyside6_dialogs.mask_manager_dialog",
                dialog_class="PySide6MaskManagerDialog",
                dialog_args=[self.main_window],
                dialog_name="Mask Manager",
                success_callback=self._handle_mask_manager_success,
                fallback_callback=lambda: None
            )
            
        except Exception as e:
            _LOGGER.error(f"Error opening mask manager dialog: {e}")
    
    def show_shortcuts_dialog(self):
        """Show keyboard shortcuts dialog"""
        try:
            success = self._try_open_dialog(
                dialog_import="snid_sage.interfaces.gui.components.pyside6_dialogs.shortcuts_dialog",
                dialog_class="PySide6ShortcutsDialog",
                dialog_args=[self.main_window],
                dialog_name="Keyboard Shortcuts",
                success_callback=lambda dialog: (dialog.exec(), _LOGGER.info("Shortcuts dialog opened")),
                fallback_callback=self._show_shortcuts_fallback
            )
            
        except Exception as e:
            _LOGGER.error(f"Error opening shortcuts dialog: {e}")
    
    # Helper methods
    
    def _validate_spectrum_loaded(self, operation_name):
        """Validate that a spectrum is loaded before opening a dialog"""
        wave, flux = self.app_controller.get_spectrum_data()
        if wave is None or flux is None:
            QtWidgets.QMessageBox.warning(
                self.main_window, 
                "No Spectrum", 
                f"Please load a spectrum file before {operation_name}."
            )
            return None, None
        return wave, flux
    
    def _try_open_dialog(self, dialog_import, dialog_class, dialog_args, dialog_name, 
                        success_callback, fallback_callback, use_show=False):
        """Generic method to try opening a dialog with import error handling"""
        try:
            # Dynamic import
            module = __import__(dialog_import, fromlist=[dialog_class])
            dialog_cls = getattr(module, dialog_class)
            
            # Create dialog
            dialog = dialog_cls(*dialog_args)
            
            if use_show:
                # For non-modal dialogs
                success_callback(dialog)
            else:
                # For modal dialogs
                result = dialog.exec()
                if result == QtWidgets.QDialog.Accepted:
                    success_callback(dialog)
                else:
                    _LOGGER.debug(f"{dialog_name} dialog cancelled")
            
            return True
            
        except ImportError as e:
            _LOGGER.warning(f"PySide6 {dialog_name} dialog not available: {e}")
            fallback_callback()
            return False
    
    def _handle_preprocessing_success(self, dialog):
        """Handle successful preprocessing dialog completion"""
        from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
        self.app_controller.update_workflow_state(WorkflowState.PREPROCESSED)
        self.main_window.preprocess_status_label.setText("Preprocessed")
        self.main_window.preprocess_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
        self.main_window.status_label.setText("Spectrum preprocessed - Ready for analysis")
        
        # Switch to Flat view to show the preprocessed spectrum  
        self.main_window._on_view_change('flat')
        _LOGGER.info("🔄 Automatically switched to Flat view after advanced preprocessing")
        
        # Update the plot to show the new processed spectrum
        self.main_window._plot_spectrum()
        
        _LOGGER.info("Preprocessing completed successfully")
    
    def _handle_preprocessing_fallback(self):
        """Handle preprocessing fallback when dialog not available"""
        from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
        self.app_controller.update_workflow_state(WorkflowState.PREPROCESSED)
        self.main_window.preprocess_status_label.setText("Preprocessed")
        self.main_window.preprocess_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
        self.main_window.status_label.setText("Spectrum preprocessed - Ready for analysis")
        QtWidgets.QMessageBox.information(self.main_window, "Preprocessing", "Preprocessing completed (simulated).")
    
    def _handle_redshift_result(self, result):
        """Handle redshift dialog result"""
        # Handle both old format (float) and new format (dict from mode dialog)
        if isinstance(result, dict):
            # New format with mode information
            redshift_value = result.get('redshift', 0.0)
            mode = result.get('mode', 'search')
            description = result.get('description', '')
            
            # Update status with mode information
            if mode == 'force':
                status_text = f"z = {redshift_value:.6f} (forced)"
            else:
                search_range = result.get('search_range', 0.001)
                status_text = f"z = {redshift_value:.6f} (±{search_range:.6f})"
            
            self.main_window.redshift_status_label.setText(status_text)
            self._update_status("redshift", None, success_style=True)
            
            # Store the full result for analysis
            self.app_controller.manual_redshift = redshift_value
            self.app_controller.redshift_mode_config = result  # Store full config
            
            _LOGGER.info(f"Manual redshift configured: {description}")
            # Immediately update the main plot's rest-axis to reflect the new redshift
            try:
                if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager is not None:
                    pm = self.main_window.plot_manager
                    if hasattr(pm, '_ensure_rest_axis') and hasattr(pm, '_set_rest_axis_redshift'):
                        pm._ensure_rest_axis()
                        pm._set_rest_axis_redshift(float(redshift_value or 0.0))
                        try:
                            if hasattr(pm, 'plot_widget') and pm.plot_widget is not None:
                                pm.plot_widget.update()
                                pm.plot_widget.repaint()
                        except Exception:
                            pass
            except Exception:
                pass
        else:
            # Backward compatibility format
            redshift_value = float(result)
            self.main_window.redshift_status_label.setText(f"z = {redshift_value:.6f} (manual)")
            self._update_status("redshift", None, success_style=True)
            self.app_controller.manual_redshift = redshift_value
            _LOGGER.info(f"Manual redshift determined: z = {redshift_value:.6f}")
            # Immediately update the main plot's rest-axis to reflect the new redshift
            try:
                if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager is not None:
                    pm = self.main_window.plot_manager
                    if hasattr(pm, '_ensure_rest_axis') and hasattr(pm, '_set_rest_axis_redshift'):
                        pm._ensure_rest_axis()
                        pm._set_rest_axis_redshift(float(redshift_value or 0.0))
                        try:
                            if hasattr(pm, 'plot_widget') and pm.plot_widget is not None:
                                pm.plot_widget.update()
                                pm.plot_widget.repaint()
                        except Exception:
                            pass
            except Exception:
                pass
    
    def _show_redshift_fallback(self, current_redshift):
        """Show fallback redshift input dialog"""
        redshift, ok = QtWidgets.QInputDialog.getDouble(
            self.main_window, 
            "Redshift Selection", 
            "Enter redshift value (optional):\n\nLeave as 0.0 for automatic redshift determination",
            value=current_redshift, decimals=4
        )
        
        if ok:
            if redshift > 0:
                self._handle_redshift_result(redshift)
            else:
                self.main_window.redshift_status_label.setText("Redshift not set (optional)")
                self.main_window.redshift_status_label.setStyleSheet("font-style: italic; color: #6b7280;")
                self.app_controller.manual_redshift = None
                _LOGGER.info("Manual redshift cleared - will use automatic determination")
    
    def _handle_settings_success(self, dialog):
        """Handle successful settings dialog completion"""
        if hasattr(dialog, 'result'):
            settings = dialog.result
            # Persist settings on main window for runtime use
            try:
                if hasattr(self.main_window, 'apply_settings'):
                    self.main_window.apply_settings(settings)
            except Exception:
                pass
            
            self.main_window.status_label.setText("Settings updated")
            _LOGGER.info("Settings updated successfully")
    
    def _handle_configuration_success(self, dialog):
        """Handle successful configuration dialog completion"""
        self.main_window.status_label.setText("SNID-SAGE configuration updated")
        _LOGGER.info("SNID-SAGE configuration updated successfully")
    
    def _handle_mask_manager_success(self, dialog):
        """Handle successful mask manager dialog completion"""
        self.main_window.status_label.setText("Mask regions updated")
        _LOGGER.info("Mask manager dialog completed successfully")
    
    def _show_simple_fallback(self, title, message):
        """Show simple fallback message box"""
        QtWidgets.QMessageBox.information(self.main_window, title, message)
    
    def _show_emission_line_fallback(self):
        """Show emission line analysis fallback"""
        # Quiet fallback removed; feature is expected to be available.
        pass
    
    def _show_shortcuts_fallback(self):
        """Show shortcuts fallback dialog"""
        try:
            from snid_sage.interfaces.gui.utils.cross_platform_window import CrossPlatformWindowManager as CPW
            mod = CPW.platform_modifier_label()
        except Exception:
            import sys
            mod = "Cmd" if sys.platform == "darwin" else "Ctrl"
        shortcuts_text = f"""
🔧 Keyboard Shortcuts

File Operations:
• {mod}+O: Load Spectrum
• {mod}+Shift+O: Configuration

Analysis:
• F5 or {mod}+R: Run Analysis
• F6: Preprocessing
• {mod}+Enter: Quick Analysis

View:
• F: Flux View
• T: Flat View
• Space: Toggle View

Navigation:
• Arrow Keys: Navigate Templates

Other:
• {mod}+,: Settings
• F1: This Help
• {mod}+Shift+R: Reset
        """
        QtWidgets.QMessageBox.information(self.main_window, "Keyboard Shortcuts", shortcuts_text)
    
    def _update_status(self, status_type, text=None, success_style=False):
        """Update status labels with consistent styling"""
        style = ("font-style: italic; color: #059669; font-size: 10px !important; "
                "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                "line-height: 1.0 !important;") if success_style else ""
        
        if status_type == "redshift" and hasattr(self.main_window, 'redshift_status_label'):
            if text:
                self.main_window.redshift_status_label.setText(text)
            if success_style:
                self.main_window.redshift_status_label.setStyleSheet(style)
        elif status_type == "emission" and hasattr(self.main_window, 'emission_status_label'):
            if text:
                self.main_window.emission_status_label.setText(text)
            if success_style:
                self.main_window.emission_status_label.setStyleSheet(style) 