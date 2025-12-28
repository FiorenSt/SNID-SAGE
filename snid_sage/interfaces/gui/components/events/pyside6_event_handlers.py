"""
SNID SAGE - PySide6 Event Handlers
=================================

Dedicated event handlers for PySide6 GUI that handle all UI events including
view changes, button clicks, keyboard shortcuts, and workflow interactions.

This extracts all event handling logic from the main GUI class to keep it clean and focused.

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import os
import sys
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_event_handlers')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_event_handlers')

# Import platform configuration
from snid_sage.shared.utils.config.platform_config import get_platform_config


class PySide6EventHandlers(QtCore.QObject):
    """
    Handles all events for PySide6 GUI
    
    This class manages:
    - View change events (Flux/Flat toggle)
    - Button click events
    - Keyboard shortcuts
    - Dialog interactions
    - File operations
    - Workflow state changes
    - Template navigation
    """
    
    def __init__(self, main_window):
        """
        Initialize the event handlers
        
        Args:
            main_window: Reference to the main PySide6 GUI window
        """
        super().__init__()
        self.main_window = main_window
        self.app_controller = main_window.app_controller
        
        # Setup all event handlers
        self.setup_keyboard_shortcuts()
    
    def setup_keyboard_shortcuts(self):
        """Setup comprehensive keyboard shortcuts"""
        try:
            # Platform-aware helper
            from snid_sage.interfaces.gui.utils.cross_platform_window import (
                CrossPlatformWindowManager as CPW,
            )

            # File operations
            CPW.standard_shortcut(self.main_window, QtGui.QKeySequence.StandardKey.Open, self.on_browse_file)
            CPW.create_shortcut(self.main_window, "Ctrl+Shift+O", self.on_open_configuration_dialog)

            # Quick workflow (combined preprocessing + analysis)
            CPW.create_shortcut(self.main_window, "Ctrl+Return", self.on_run_quick_workflow, context=QtCore.Qt.ApplicationShortcut)
            CPW.create_shortcut(self.main_window, "Ctrl+Enter", self.on_run_quick_workflow, context=QtCore.Qt.ApplicationShortcut)
            # Separate extended variants are registered below

            # Extended quick workflow (preprocessing + analysis + auto cluster selection)
            CPW.create_shortcut(self.main_window, "Ctrl+Shift+Return", self.on_run_quick_workflow_with_auto_cluster, context=QtCore.Qt.ApplicationShortcut)
            CPW.create_shortcut(self.main_window, "Ctrl+Shift+Enter", self.on_run_quick_workflow_with_auto_cluster, context=QtCore.Qt.ApplicationShortcut)

            # Analysis operations
            QtGui.QShortcut("F5", self.main_window, self.on_run_analysis)
            CPW.create_shortcut(self.main_window, "Ctrl+R", self.on_run_analysis)
            QtGui.QShortcut("F6", self.main_window, self.on_open_preprocessing_dialog)

            # Settings and configuration
            CPW.standard_shortcut(self.main_window, QtGui.QKeySequence.StandardKey.Preferences, self.on_open_settings_dialog)

            # Template navigation
            QtGui.QShortcut("Left", self.main_window, self.on_previous_template)
            QtGui.QShortcut("Right", self.main_window, self.on_next_template)

            # View toggles
            QtGui.QShortcut("F", self.main_window, lambda: self.on_view_change('flux'))
            QtGui.QShortcut("T", self.main_window, lambda: self.on_view_change('flat'))
            QtGui.QShortcut("Space", self.main_window, self.on_switch_view_mode)

            # Reset functionality
            CPW.create_shortcut(self.main_window, "Ctrl+Shift+R", self.on_reset_to_initial_state)

            # Help and documentation
            QtGui.QShortcut("F1", self.main_window, self.on_show_shortcuts_dialog)
            CPW.create_shortcut(self.main_window, "Ctrl+/", self.on_show_shortcuts_dialog)

            # Games (cross-platform Ctrl/Cmd+G) – make it application-wide so it works from anywhere
            CPW.create_shortcut(
                self.main_window,
                "Ctrl+G",
                self.on_start_games,
                context=QtCore.Qt.ApplicationShortcut,
            )

            # Plot saving shortcuts
            CPW.create_shortcut(self.main_window, "Ctrl+S", self.on_save_plot_as_png, context=QtCore.Qt.ApplicationShortcut)
            CPW.create_shortcut(self.main_window, "Ctrl+Shift+S", self.on_save_plot_as_svg, context=QtCore.Qt.ApplicationShortcut)

            # Quit application (cross-platform Ctrl/Cmd+Q)
            CPW.standard_shortcut(self.main_window, QtGui.QKeySequence.StandardKey.Quit, self.on_quit_application)

            _LOGGER.debug("Keyboard shortcuts setup completed")

        except Exception as e:
            _LOGGER.error(f"Error setting up keyboard shortcuts: {e}")

    def on_start_games(self):
        """Start the Space Debris game immediately (no dialog)."""
        try:
            if hasattr(self.main_window, '_start_space_debris_game'):
                self.main_window._start_space_debris_game()
            elif hasattr(self.main_window, 'start_games'):
                # Fallback to start which may show a menu
                self.main_window.start_games()
            else:
                QtWidgets.QMessageBox.information(
                    self.main_window,
                    "Games",
                    "Games feature is not available in this build."
                )
        except Exception as e:
            _LOGGER.error(f"Error starting games: {e}")

    def on_quit_application(self):
        """Quit the application in a cross-platform friendly way."""
        try:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()
            else:
                # Fallback
                self.main_window.close()
        except Exception as e:
            _LOGGER.error(f"Error quitting application: {e}")
    
    def on_view_change(self, view_type):
        """Handle view toggle changes"""
        try:
            _LOGGER.info(f"🔄 View change requested: {view_type}")
            
            # CRITICAL: Only prevent switching to Flat view if we don't have any spectrum data
            # or if we have spectrum data but preprocessing has never been completed
            from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
            current_state = self.app_controller.get_current_state()
            
            # Block flat view only if:
            # 1. No spectrum loaded at all (INITIAL state), OR
            # 2. Spectrum loaded but never preprocessed (FILE_LOADED state)
            if view_type == 'flat' and current_state in [WorkflowState.INITIAL, WorkflowState.FILE_LOADED]:
                _LOGGER.warning("🚫 Flat view requested but preprocessing not completed")
                # Show warning and revert to Flux view
                QtWidgets.QMessageBox.warning(
                    self.main_window,
                    "Preprocessing Required",
                    "Flat view requires preprocessing.\n\n"
                    "Please run preprocessing first to enable flat spectrum view."
                )
                # Force Flux view
                view_type = 'flux'
            
            self.main_window.current_view = view_type
            
            # CRITICAL: Use unified layout manager for consistent button state management
            # instead of direct styling that overrides workflow state management
            if view_type == 'flux':
                # Determine if both buttons should be enabled based on workflow state
                flux_enabled = True  # Flux should be enabled after FILE_LOADED
                flat_enabled = current_state not in [WorkflowState.INITIAL, WorkflowState.FILE_LOADED]
                
                self.main_window.unified_layout_manager.update_flux_flat_button_states(
                    self.main_window,
                    flux_active=True,    # Flux becomes active
                    flat_active=False,   # Flat becomes inactive
                    flux_enabled=flux_enabled,
                    flat_enabled=flat_enabled
                )
            else:  # flat view
                # Both buttons should be enabled if we reached this point (flat view allowed)
                self.main_window.unified_layout_manager.update_flux_flat_button_states(
                    self.main_window,
                    flux_active=False,   # Flux becomes inactive
                    flat_active=True,    # Flat becomes active
                    flux_enabled=True,   # Both enabled since flat is accessible
                    flat_enabled=True
                )
            
            
            from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
            if self.main_window.plot_manager.current_plot_mode != PlotMode.SPECTRUM:
                _LOGGER.info("Flux/Flat button pressed - returning to spectrum mode")
                self.main_window.plot_manager.switch_to_plot_mode(PlotMode.SPECTRUM)
            
            # Always try to update plot
            # This ensures view changes are reflected immediately
            wave, flux = self.app_controller.get_spectrum_for_view(view_type)
            if wave is not None and flux is not None:
                _LOGGER.info(f"📊 Plotting spectrum in {view_type} view")
                self.main_window.plot_manager.plot_spectrum(view_type)
                
        except Exception as e:
            _LOGGER.error(f"❌ Error handling view change: {e}")
            import traceback
            traceback.print_exc()
    
    def on_switch_view_mode(self):
        """Switch between view modes (Space key)"""
        try:
            if self.main_window.current_view == 'flux':
                # Check workflow state - only block if no spectrum or spectrum never preprocessed
                from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                current_state = self.app_controller.get_current_state()
                
                if current_state not in [WorkflowState.INITIAL, WorkflowState.FILE_LOADED]:
                    self.on_view_change('flat')
                else:
                    _LOGGER.info("🚫 Cannot switch to Flat view - preprocessing required")
            else:
                self.on_view_change('flux')
        except Exception as e:
            _LOGGER.error(f"❌ Error switching view mode: {e}")
    
    def on_browse_file(self):
        """Handle file browsing"""
        try:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self.main_window,
                "Load Spectrum File",
                "",
                "Spectrum Files (*.dat *.txt *.ascii *.asci *.csv *.fits *.flm);;All Files (*)"
            )
            
            if file_path:
                self.handle_open_spectrum_file(file_path)
                    
        except Exception as e:
            _LOGGER.error(f"Error handling file browse: {e}")

    def handle_open_spectrum_file(self, file_path: str):
        """Common handler to load a spectrum file path and update UI/state."""
        try:
            if not file_path:
                return
            # If a spectrum is already loaded or there are preprocessing/analysis results,
            # confirm with the user that loading a new spectrum will reset the GUI/state.
            try:
                has_loaded_spectrum = (
                    getattr(self.app_controller, 'original_wave', None) is not None and
                    getattr(self.app_controller, 'original_flux', None) is not None
                )
                preprocessed_present = bool(getattr(self.app_controller, 'processed_spectrum', None))
                analysis_present = bool(getattr(self.app_controller, 'snid_results', None))
                if has_loaded_spectrum or preprocessed_present or analysis_present:
                    reply = QtWidgets.QMessageBox.question(
                        self.main_window,
                        "Load New Spectrum?",
                        (
                            "A spectrum is already loaded and may have preprocessing or analysis results.\n\n"
                            "Loading a new spectrum will reset the GUI and clear the current spectrum, preprocessing, "
                            "analysis results, overlays and related settings.\n\n"
                            "Do you want to continue?"
                        ),
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No
                    )
                    if reply != QtWidgets.QMessageBox.Yes:
                        return
                    # Reset to a clean initial state before loading the new file
                    if hasattr(self.app_controller, 'reset_to_initial_state'):
                        self.app_controller.reset_to_initial_state()
                    # Ensure the main view is Flux for new loads
                    try:
                        self.main_window.current_view = 'flux'
                    except Exception:
                        pass
            except Exception:
                # If any issue occurs during state inspection, proceed without confirmation
                pass
            self.main_window.status_label.setText(f"Loading: {Path(file_path).name}")
            self.main_window.file_status_label.setText(f"File: {Path(file_path).name}")
            # Try to load the spectrum data using app controller
            if self.app_controller.load_spectrum_file(file_path):
                # Reset preprocessing status for new file
                self.main_window.preprocess_status_label.setText("Preprocessing not run")
                self.main_window.preprocess_status_label.setStyleSheet("font-style: italic; color: #475569; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                # Reset redshift status for new file (clear any previous forced/search text)
                if hasattr(self.main_window, 'redshift_status_label'):
                    self.main_window.redshift_status_label.setText("Redshift not set (optional)")
                    self.main_window.redshift_status_label.setStyleSheet(
                        "font-style: italic; color: #475569; font-size: 10px !important; "
                        "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                        "line-height: 1.0 !important;"
                    )
                # Reset analysis/config status label under Run Analysis button
                if hasattr(self.main_window, 'config_status_label'):
                    self.main_window.config_status_label.setText("Default SNID parameters loaded")
                    self.main_window.config_status_label.setStyleSheet(
                        "font-style: italic; color: #475569; font-size: 10px !important; "
                        "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                        "line-height: 1.0 !important;"
                    )
                # Ensure FILE_LOADED state is processed immediately
                from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                self.main_window._update_workflow_state(WorkflowState.FILE_LOADED)
                # Ensure stacked widget shows the spectrum (PyQtGraph) view
                try:
                    from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                    if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager:
                        if self.main_window.plot_manager.current_plot_mode != PlotMode.SPECTRUM:
                            self.main_window.plot_manager.switch_to_plot_mode(PlotMode.SPECTRUM)
                except Exception:
                    pass
                # Plot the loaded spectrum
                self.main_window.plot_manager.plot_spectrum(self.main_window.current_view)
                self.main_window.status_label.setText(f"Loaded: {Path(file_path).name}")
                # Re-apply button states after plotting
                self.main_window.unified_layout_manager.update_flux_flat_button_states(
                    self.main_window,
                    flux_active=True,
                    flat_active=False,
                    flux_enabled=True,
                    flat_enabled=False
                )
                # Update file status label
                self.main_window.file_status_label.setText(f"File: {Path(file_path).name}")
                self.main_window.file_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                _LOGGER.info(f"Spectrum file loaded successfully: {file_path}")
            else:
                # Load failed: ensure the application does NOT retain any "loaded spectrum" state.
                # Otherwise the next load will incorrectly warn about overwriting an empty plot.
                self.main_window.status_label.setText("Error loading file")
                QtWidgets.QMessageBox.warning(
                    self.main_window,
                    "File Loading Error",
                    "Could not load spectrum file."
                )

                # Reset controller state back to initial/empty (best-effort)
                try:
                    if hasattr(self.app_controller, 'reset_to_initial_state'):
                        self.app_controller.reset_to_initial_state()
                except Exception:
                    pass

                # Ensure workflow/UI returns to INITIAL so buttons/menus reflect "no spectrum"
                try:
                    from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                    if hasattr(self.main_window, '_update_workflow_state'):
                        self.main_window._update_workflow_state(WorkflowState.INITIAL)
                except Exception:
                    pass

                # Restore an empty plot view (welcome/empty canvas)
                try:
                    from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                    if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager:
                        if self.main_window.plot_manager.current_plot_mode != PlotMode.SPECTRUM:
                            self.main_window.plot_manager.switch_to_plot_mode(PlotMode.SPECTRUM)
                        self.main_window.plot_manager.plot_clean_welcome_message()
                except Exception:
                    pass

                # Reset status labels to their *exact* initial startup text/styles
                try:
                    self.main_window.status_label.setText("No spectrum loaded")
                    if hasattr(self, '_reset_all_status_labels_to_initial'):
                        self._reset_all_status_labels_to_initial()
                except Exception:
                    pass
        except Exception as e:
            _LOGGER.error(f"Error handling open spectrum file: {e}")
    
    def on_open_preprocessing_dialog(self):
        """Handle opening preprocessing dialog"""
        try:
            from snid_sage.interfaces.gui.components.pyside6_dialogs.preprocessing_dialog import PySide6PreprocessingDialog
            
            # Prefer the ORIGINAL spectrum for preprocessing, not any processed/log-rebinned data
            wave = getattr(self.app_controller, 'original_wave', None)
            flux = getattr(self.app_controller, 'original_flux', None)
            if wave is None or flux is None:
                # Fallback to whatever is available
                wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "No Spectrum", 
                    "Please load a spectrum file before preprocessing."
                )
                return

            # If analysis was already run or overlays exist, warn user about reset
            analysis_present = bool(getattr(self.app_controller, 'snid_results', None))
            preprocessed_present = bool(getattr(self.app_controller, 'processed_spectrum', None))
            if analysis_present or preprocessed_present:
                reply = QtWidgets.QMessageBox.question(
                    self.main_window,
                    "Redo Preprocessing?",
                    (
                        "You are about to redo preprocessing.\n\n"
                        "This will clear previous preprocessing, analysis results, overlays, and advanced views.\n"
                        "The loaded spectrum will be kept, and the GUI will return to the preprocessing stage.\n\n"
                        "Do you want to continue?"
                    ),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return

                # Reset controller/UI back to FILE_LOADED while keeping spectrum
                if hasattr(self.app_controller, 'reset_to_file_loaded_state'):
                    self.app_controller.reset_to_file_loaded_state()

                # Reset status labels to reflect file-loaded state
                if hasattr(self.main_window, 'preprocess_status_label'):
                    self.main_window.preprocess_status_label.setText("Preprocessing not run")
                    self.main_window.preprocess_status_label.setStyleSheet(
                        "font-style: italic; color: #475569; font-size: 10px !important; "
                        "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                        "line-height: 1.0 !important;"
                    )
                # Also reset the configuration/analysis status label so it no longer shows 'Analysis Complete'
                if hasattr(self.main_window, 'config_status_label'):
                    self.main_window.config_status_label.setText("Default SNID parameters loaded")
                    self.main_window.config_status_label.setStyleSheet(
                        "font-style: italic; color: #475569; font-size: 10px !important; "
                        "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                        "line-height: 1.0 !important;"
                    )
                if hasattr(self.main_window, 'status_label'):
                    self.main_window.status_label.setText("Spectrum loaded - ready to preprocess")

                # Ensure spectrum plot is shown without overlays in Flux view
                self.on_view_change('flux')
                self.main_window.plot_manager.plot_spectrum('flux')

                # Re-fetch ORIGINAL spectrum after reset to ensure dialog starts from untouched data
                wave = getattr(self.app_controller, 'original_wave', None)
                flux = getattr(self.app_controller, 'original_flux', None)
                if wave is None or flux is None:
                    # As a last resort, fallback to current available data
                    wave, flux = self.app_controller.get_spectrum_data()
            
            dialog = PySide6PreprocessingDialog(self.main_window, (wave, flux))
            result = dialog.exec()
            
            if result == QtWidgets.QDialog.Accepted:
                # Apply preprocessing results
                from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
                self.app_controller.update_workflow_state(WorkflowState.PREPROCESSED)
                self.main_window.preprocess_status_label.setText("Preprocessed")
                self.main_window.preprocess_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
                self.main_window.status_label.setText("Spectrum preprocessed - Ready for analysis")
                
                # CRITICAL: Switch to Flat view to show the preprocessed (flat) spectrum  
                self.on_view_change('flat')
                _LOGGER.info("🔄 Automatically switched to Flat view after advanced preprocessing")
                
                # Update the plot to show the new processed spectrum
                self.main_window.plot_manager.plot_spectrum(self.main_window.current_view)
                
                _LOGGER.info("Preprocessing completed successfully")
            else:
                _LOGGER.debug("Preprocessing dialog cancelled")
                
        except ImportError as e:
            _LOGGER.warning(f"PySide6 preprocessing dialog not available: {e}")
            # Fallback to simple simulation
            from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
            self.app_controller.update_workflow_state(WorkflowState.PREPROCESSED)
            self.main_window.preprocess_status_label.setText("Preprocessed")
            self.main_window.preprocess_status_label.setStyleSheet("font-style: italic; color: #059669; font-size: 10px !important; font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; line-height: 1.0 !important;")
            self.main_window.status_label.setText("Spectrum preprocessed - Ready for analysis")
            QtWidgets.QMessageBox.information(self.main_window, "Preprocessing", "Preprocessing completed (simulated).")
        except Exception as e:
            _LOGGER.error(f"Error opening preprocessing dialog: {e}")
    
    def on_run_analysis(self):
        """Handle running SNID analysis - directly open advanced configuration"""
        try:
            wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "Analysis Error", 
                    "Please load a spectrum file before running analysis."
                )
                return
            
            # If an analysis is already running, do not start another
            try:
                if hasattr(self.app_controller, 'is_analysis_running') and self.app_controller.is_analysis_running():
                    # Prefer updating existing progress dialog if available
                    dlg = getattr(self.main_window, 'progress_dialog', None)
                    if dlg:
                        try:
                            # Route via controller for strict ordering
                            if hasattr(self.app_controller, 'post_progress'):
                                self.app_controller.post_progress("Another analysis start was requested; already running. Please wait or cancel.", 0.0)
                            else:
                                dlg.add_progress_line("Another analysis start was requested; already running. Please wait or cancel.", "warning")
                            dlg.raise_()
                            dlg.activateWindow()
                        except Exception:
                            pass
                    else:
                        QtWidgets.QMessageBox.information(
                            self.main_window,
                            "Analysis In Progress",
                            "An analysis is already running. Please wait for it to finish or cancel it."
                        )
                    return
            except Exception:
                pass
            
            # If analysis exists already, confirm re-running analysis with reset of previous results
            analysis_present = bool(getattr(self.app_controller, 'snid_results', None))
            if analysis_present:
                reply = QtWidgets.QMessageBox.question(
                    self.main_window,
                    "Re-run Analysis?",
                    (
                        "You have already run an analysis.\n\n"
                        "Re-running analysis will clear previous analysis results and overlays.\n"
                        "Preprocessing will be kept so you can re-run with new settings.\n\n"
                        "Do you want to continue?"
                    ),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                # Clear only analysis state, keep preprocessing
                if hasattr(self.app_controller, 'reset_analysis_state'):
                    self.app_controller.reset_analysis_state()
                
                # Update UI: remove overlays, keep current view; refresh plot
                from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                if self.main_window.plot_manager.current_plot_mode != PlotMode.SPECTRUM:
                    self.main_window.plot_manager.switch_to_plot_mode(PlotMode.SPECTRUM)
                self.main_window.plot_manager.plot_spectrum(self.main_window.current_view)

            # Check if spectrum is preprocessed
            if not hasattr(self.app_controller, 'processed_spectrum') or self.app_controller.processed_spectrum is None:
                # Ask user if they want to preprocess first
                reply = QtWidgets.QMessageBox.question(
                    self.main_window,
                    "Preprocessing Required",
                    "Spectrum needs to be preprocessed before analysis.\n\n"
                    "Run quick preprocessing with default settings?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    # Run quick preprocessing first
                    success = self.app_controller.run_preprocessing()
                    if not success:
                        QtWidgets.QMessageBox.critical(
                            self.main_window,
                            "Preprocessing Error",
                            "Failed to preprocess spectrum"
                        )
                        return
                else:
                    return  # User cancelled
            
            # Directly open configuration dialog for advanced options
            try:
                from snid_sage.interfaces.gui.components.pyside6_dialogs.configuration_dialog import show_configuration_dialog
                
                # Get current parameters if available
                current_params = {}
                if hasattr(self.app_controller, 'current_config'):
                    current_params = self.app_controller.current_config.get('analysis', {})
                
                # Show configuration dialog
                dialog_result = show_configuration_dialog(self.main_window, current_params, self.app_controller)
                
                if dialog_result is None:
                    # User cancelled configuration
                    _LOGGER.debug("Analysis configuration cancelled")
                    return
                
                config_params, analysis_started = dialog_result
                
                if analysis_started:
                    # Analysis was already started from the dialog - no need to run it again
                    _LOGGER.info("Analysis already started from configuration dialog")
                    return
                
                # Update status
                self.main_window.status_label.setText("Running SNID-SAGE analysis with configured settings...")
                
                # Apply configuration and run analysis
                if hasattr(self.app_controller, 'current_config'):
                    if 'analysis' not in self.app_controller.current_config:
                        self.app_controller.current_config['analysis'] = {}
                    self.app_controller.current_config['analysis'].update(config_params)
                
                # Run the analysis with configured parameters
                started = self._run_configured_analysis(config_params)

                if started:
                    # Do not prematurely mark success; wait for completion signal
                    self.main_window.status_label.setText("Running SNID-SAGE analysis...")
                    _LOGGER.info("SNID-SAGE analysis started (waiting for completion)")
                else:
                    QtWidgets.QMessageBox.critical(
                        self.main_window,
                        "Analysis Error",
                        "Failed to start SNID-SAGE analysis with configured parameters"
                    )
                    
            except ImportError as e:
                _LOGGER.error(f"Configuration dialog not available: {e}")
                QtWidgets.QMessageBox.critical(
                    self.main_window,
                    "Configuration Error",
                    "Configuration dialog is not available"
                )
                
        except Exception as e:
            _LOGGER.error(f"Error running analysis: {e}")
            QtWidgets.QMessageBox.critical(
                self.main_window,
                "Analysis Error",
                f"Failed to run analysis:\n{str(e)}"
            )
    
    def _run_configured_analysis(self, config_params):
        """Run SNID analysis with configured parameters"""
        try:
            # Check if we have an analysis controller
            if hasattr(self.app_controller, 'run_snid_analysis'):
                return self.app_controller.run_snid_analysis(config_params)
            else:
                # Show error if analysis controller is not available
                _LOGGER.error("Analysis controller not available - cannot run analysis")
                QtWidgets.QMessageBox.critical(
                    self.main_window,
                    "Analysis Error",
                    "Analysis controller not available.\nPlease check the application setup."
                )
                return False
        except Exception as e:
            _LOGGER.error(f"Error running configured analysis: {e}")
            QtWidgets.QMessageBox.critical(
                self.main_window,
                "Analysis Error",
                f"Error running analysis:\n{str(e)}"
            )
            return False

    def on_run_quick_workflow(self):
        """Handle quick workflow (simulate right-click preprocessing + right-click analysis)"""
        try:
            platform_config = get_platform_config()
            right_click_text = platform_config.get_click_text("right")
            _LOGGER.info(f"Starting quick workflow (simulating {right_click_text.lower()} on preprocessing + analysis buttons)")
            
            # Check if spectrum is loaded
            wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "No Spectrum", 
                    "Please load a spectrum file before running quick workflow."
                )
                return
            
            # Simulate right-click on preprocessing button (quick preprocessing)
            if hasattr(self.main_window, 'preprocessing_controller') and hasattr(self.main_window.preprocessing_controller, 'run_quick_preprocessing'):
                platform_config = get_platform_config()
                right_click_text = platform_config.get_click_text("right")
                _LOGGER.info(f"🔧 Simulating {right_click_text.lower()} on preprocessing button...")
                self.main_window.preprocessing_controller.run_quick_preprocessing()
            else:
                _LOGGER.warning("Quick preprocessing not available")
                return
            
            # Simulate right-click on analysis button (quick analysis)
            if hasattr(self.main_window, 'run_quick_analysis'):
                platform_config = get_platform_config()
                right_click_text = platform_config.get_click_text("right")
                _LOGGER.info(f"🚀 Simulating {right_click_text.lower()} on analysis button...")
                self.main_window.run_quick_analysis()
            else:
                _LOGGER.warning("Quick analysis not available")
                return
            
        except Exception as e:
            _LOGGER.error(f"Error in quick workflow: {e}")

    def on_run_quick_workflow_with_auto_cluster(self):
        """Handle extended quick workflow (simulate right-click preprocessing + right-click analysis + auto cluster selection)"""
        try:
            platform_config = get_platform_config()
            right_click_text = platform_config.get_click_text("right")
            _LOGGER.info(f"Starting extended quick workflow (simulating {right_click_text.lower()} on buttons + auto cluster)")
            
            # Check if spectrum is loaded
            wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "No Spectrum", 
                    "Please load a spectrum file before running extended quick workflow."
                )
                return
            
            # Set flag to automatically select best cluster
            self.app_controller.auto_select_best_cluster = True
            _LOGGER.info("🤖 Auto cluster selection enabled")
            
            # Simulate right-click on preprocessing button (quick preprocessing)
            if hasattr(self.main_window, 'preprocessing_controller') and hasattr(self.main_window.preprocessing_controller, 'run_quick_preprocessing'):
                platform_config = get_platform_config()
                right_click_text = platform_config.get_click_text("right")
                _LOGGER.info(f"🔧 Simulating {right_click_text.lower()} on preprocessing button...")
                self.main_window.preprocessing_controller.run_quick_preprocessing()
            else:
                _LOGGER.warning("Quick preprocessing not available")
                # Reset the auto select flag on error
                self.app_controller.auto_select_best_cluster = False
                return
            
            # Simulate right-click on analysis button (quick analysis with auto cluster)
            if hasattr(self.main_window, 'run_quick_analysis'):
                platform_config = get_platform_config()
                right_click_text = platform_config.get_click_text("right")
                _LOGGER.info(f"🚀 Simulating {right_click_text.lower()} on analysis button (with auto cluster)...")
                self.main_window.run_quick_analysis()
            else:
                _LOGGER.warning("Quick analysis not available")
                # Reset the auto select flag on error
                self.app_controller.auto_select_best_cluster = False
                return
            
        except Exception as e:
            _LOGGER.error(f"Error in extended quick workflow: {e}")
            # Reset the auto select flag on error
            self.app_controller.auto_select_best_cluster = False
    
    def on_reset_to_initial_state(self):
        """Handle reset to initial state - comprehensive reset that restores GUI to exact startup state"""
        try:
            reply = QtWidgets.QMessageBox.question(
                self.main_window, 
                "Reset Application", 
                "Are you sure you want to reset to initial state?\nThis will clear all data and analysis results.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                # Perform comprehensive reset to true initial state
                self._perform_comprehensive_reset()
                _LOGGER.info("Application reset to initial state")
                
        except Exception as e:
            _LOGGER.error(f"Error resetting application: {e}")
    
    def _perform_comprehensive_reset(self):
        """
        Perform a comprehensive reset that brings the GUI back to the exact state
        it was in when first opened, removing all lingering status text and settings
        """
        try:
            _LOGGER.info("🔄 Starting comprehensive reset to initial state...")
            
            # 1. Stop any blinking effects (must be done early to prevent UI conflicts)
            self._stop_all_blinking_effects()
            
            # 2. Reset app controller data
            self.app_controller.reset_to_initial_state()
            
            # 3. Clear additional persistent settings that the basic reset misses
            self._clear_persistent_settings()
            
            # 4. Reset all status labels to their exact initial text and styling
            self._reset_all_status_labels_to_initial()
            
            # 5. Reset view buttons to initial state
            self._reset_view_buttons_to_initial()
            
            # 6. Ensure plot mode is Spectrum and show welcome message
            try:
                from snid_sage.interfaces.gui.components.plots.pyside6_plot_manager import PlotMode
                # Switch stacked widget to PyQtGraph so the welcome message is visible
                if getattr(self.main_window.plot_manager, 'current_plot_mode', None) != PlotMode.SPECTRUM:
                    self.main_window.plot_manager.switch_to_plot_mode(PlotMode.SPECTRUM)
            except Exception:
                pass
            # Clear the PyQtGraph plot and show the startup welcome state
            self.main_window.plot_manager.plot_pyqtgraph_welcome_message()
            
            # 7. Reset main status to initial message
            self.main_window.status_label.setText("Ready - Load a spectrum to begin analysis")
            
            # 8. Update button states to reflect initial state
            self._update_buttons_for_initial_state()
            
            # 9. Force workflow state update to INITIAL (ensures everything is in sync)
            self._force_workflow_state_to_initial()
            
            _LOGGER.info("✅ Comprehensive reset completed successfully")
            
        except Exception as e:
            _LOGGER.error(f"❌ Error during comprehensive reset: {e}")
            import traceback
            traceback.print_exc()
    
    def _stop_all_blinking_effects(self):
        """Stop all blinking effects that might be active"""
        try:
            # Stop cluster summary blinking
            if hasattr(self.main_window, 'stop_cluster_summary_blinking'):
                self.main_window.stop_cluster_summary_blinking()
                _LOGGER.debug("  🔴 Stopped cluster summary blinking effect")
            
            # Reset cluster summary state variables explicitly
            if hasattr(self.main_window, 'cluster_summary_blinking'):
                self.main_window.cluster_summary_blinking = False
            if hasattr(self.main_window, 'cluster_summary_clicked_once'):
                self.main_window.cluster_summary_clicked_once = False
            if hasattr(self.main_window, 'cluster_summary_blink_timer'):
                if self.main_window.cluster_summary_blink_timer:
                    self.main_window.cluster_summary_blink_timer.stop()
                    self.main_window.cluster_summary_blink_timer = None
            if hasattr(self.main_window, 'cluster_summary_original_style'):
                self.main_window.cluster_summary_original_style = None
                
            _LOGGER.debug("  ✅ All blinking effects stopped and state variables reset")
            
        except Exception as e:
            _LOGGER.warning(f"  ⚠️ Warning stopping blinking effects: {e}")
    
    def _clear_persistent_settings(self):
        """Clear persistent settings that survive basic reset"""
        try:
            # Clear redshift mode configuration
            if hasattr(self.app_controller, 'redshift_mode_config'):
                self.app_controller.redshift_mode_config = None
                
            # Clear manual redshift
            if hasattr(self.app_controller, 'manual_redshift'):
                self.app_controller.manual_redshift = None
                
            # Clear any forced redshift settings
            if hasattr(self.app_controller, 'forced_redshift'):
                self.app_controller.forced_redshift = None
                
            # Clear analysis controller redshift config if it exists
            if hasattr(self.main_window, 'analysis_controller') and self.main_window.analysis_controller:
                if hasattr(self.main_window.analysis_controller, 'redshift_config'):
                    self.main_window.analysis_controller.redshift_config = {}
                    
            _LOGGER.debug("  ✅ Persistent settings cleared")
            
        except Exception as e:
            _LOGGER.warning(f"  ⚠️ Warning clearing persistent settings: {e}")
    
    def _reset_all_status_labels_to_initial(self):
        """Reset all status labels to their exact initial text and styling"""
        try:
            # Define the initial styling for status labels
            initial_status_style = (
                "font-style: italic; color: #475569; font-size: 10px !important; "
                "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                "line-height: 1.0 !important; margin-top: 0px;"
            )
            
            # Reset file status label - CRITICAL: This was missing!
            if hasattr(self.main_window, 'file_status_label'):
                self.main_window.file_status_label.setText("No file loaded")
                self.main_window.file_status_label.setStyleSheet(initial_status_style)
            
            # Reset redshift status label
            if hasattr(self.main_window, 'redshift_status_label'):
                self.main_window.redshift_status_label.setText("Redshift not set (optional)")
                self.main_window.redshift_status_label.setStyleSheet(initial_status_style)
            
            # Reset preprocessing status label
            if hasattr(self.main_window, 'preprocess_status_label'):
                self.main_window.preprocess_status_label.setText("Preprocessing not run")
                self.main_window.preprocess_status_label.setStyleSheet(initial_status_style)
            
            # Reset configuration status label
            if hasattr(self.main_window, 'config_status_label'):
                self.main_window.config_status_label.setText("Default SNID parameters loaded")
                self.main_window.config_status_label.setStyleSheet(initial_status_style)
            
            # Reset emission line status label
            if hasattr(self.main_window, 'emission_status_label'):
                self.main_window.emission_status_label.setText("Not analyzed")
                self.main_window.emission_status_label.setStyleSheet(initial_status_style)
            
            # Reset AI status label
            if hasattr(self.main_window, 'ai_status_label'):
                self.main_window.ai_status_label.setText("Not analyzed")
                self.main_window.ai_status_label.setStyleSheet(initial_status_style)
            
            _LOGGER.debug("  ✅ All status labels reset to initial state")
            
        except Exception as e:
            _LOGGER.warning(f"  ⚠️ Warning resetting status labels: {e}")
    
    def _reset_view_buttons_to_initial(self):
        """Reset view buttons (Flux/Flat) to their initial disabled state with proper styling"""
        try:
            # Reset current view to initial state
            if hasattr(self.main_window, 'current_view'):
                self.main_window.current_view = 'flux'  # Reset to default view
            
            # Use the layout manager to properly reset button states and styling
            if hasattr(self.main_window, 'unified_layout_manager'):
                self.main_window.unified_layout_manager.update_flux_flat_button_states(
                    self.main_window,
                    flux_active=False,    # Flux NOT active (gray, not blue)
                    flat_active=False,    # Flat NOT active (gray, not blue)
                    flux_enabled=False,   # Flux disabled until spectrum loaded
                    flat_enabled=False    # Flat disabled until preprocessing
                )
                _LOGGER.debug("  ✅ Used layout manager to reset Flux/Flat button states")
            else:
                # Fallback: manually reset if layout manager not available
                if hasattr(self.main_window, 'flux_btn'):
                    self.main_window.flux_btn.setEnabled(False)
                    self.main_window.flux_btn.setChecked(False)
                    self.main_window.flux_btn.setToolTip("Flux view requires spectrum\nLoad a spectrum file first")
                
                if hasattr(self.main_window, 'flat_btn'):
                    self.main_window.flat_btn.setEnabled(False)
                    self.main_window.flat_btn.setChecked(False)
                    self.main_window.flat_btn.setToolTip("Flat view requires preprocessing\nLoad a spectrum and run preprocessing first")
                
                _LOGGER.debug("  ✅ Manually reset Flux/Flat button states (fallback)")
                
            _LOGGER.debug("  ✅ View buttons reset to initial state")
            
        except Exception as e:
            _LOGGER.warning(f"  ⚠️ Warning resetting view buttons: {e}")
    
    def _update_buttons_for_initial_state(self):
        """Update all button states to reflect the initial application state"""
        try:
            # Update button states through the workflow integrator system (PySide6 pattern)
            if hasattr(self.main_window, 'workflow_integrator') and self.main_window.workflow_integrator:
                self.main_window.workflow_integrator._workflow_update_button_states()
                _LOGGER.debug("  ✅ Button states updated via workflow integrator")
            else:
                # Fallback pattern
                if hasattr(self.app_controller, 'update_button_states'):
                    self.app_controller.update_button_states()
                elif hasattr(self.main_window, 'app_controller') and hasattr(self.main_window.app_controller, 'update_button_states'):
                    self.main_window.app_controller.update_button_states()
                _LOGGER.debug("  ✅ Button states updated via fallback method")
                
        except Exception as e:
            _LOGGER.warning(f"  ⚠️ Warning updating button states: {e}")
    
    def _force_workflow_state_to_initial(self):
        """Force workflow state to INITIAL and ensure all UI reflects this state"""
        try:
            # Import the WorkflowState enum
            from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
            
            # Force workflow state through multiple pathways to ensure it sticks
            if hasattr(self.app_controller, 'update_workflow_state'):
                self.app_controller.update_workflow_state(WorkflowState.INITIAL)
            
            # Also force through main window if it has workflow management
            if hasattr(self.main_window, '_update_workflow_state'):
                self.main_window._update_workflow_state(WorkflowState.INITIAL)
            
            # Force through workflow integrator if available
            if hasattr(self.main_window, 'workflow_integrator'):
                self.main_window.workflow_integrator.workflow.update_workflow_state(WorkflowState.INITIAL)
            
            _LOGGER.debug("  ✅ Workflow state forced to INITIAL")
            
        except Exception as e:
            _LOGGER.warning(f"  ⚠️ Warning forcing workflow state: {e}")
    
    def on_previous_template(self):
        """Handle previous template navigation"""
        try:
            if hasattr(self.app_controller, 'snid_results') and self.app_controller.snid_results:
                current_idx = getattr(self.app_controller, 'current_template', 0)
                max_templates = len(self.app_controller.snid_results.best_matches)
                
                if current_idx > 0:
                    self.app_controller.current_template = current_idx - 1
                    self.main_window.plot_manager.plot_spectrum(self.main_window.current_view)
                    _LOGGER.debug(f"Moved to previous template: {self.app_controller.current_template}")
                    
        except Exception as e:
            _LOGGER.error(f"Error navigating to previous template: {e}")
    
    def on_next_template(self):
        """Handle next template navigation"""
        try:
            if hasattr(self.app_controller, 'snid_results') and self.app_controller.snid_results:
                current_idx = getattr(self.app_controller, 'current_template', 0)
                max_templates = len(self.app_controller.snid_results.best_matches)
                
                if current_idx < max_templates - 1:
                    self.app_controller.current_template = current_idx + 1
                    self.main_window.plot_manager.plot_spectrum(self.main_window.current_view)
                    _LOGGER.debug(f"Moved to next template: {self.app_controller.current_template}")
                    
        except Exception as e:
            _LOGGER.error(f"Error navigating to next template: {e}")
    

    
    def on_open_configuration_dialog(self):
        """Handle opening configuration dialog"""
        try:
            # Open configuration dialog directly via dialog manager
            if hasattr(self.main_window, 'dialog_manager'):
                self.main_window.dialog_manager.open_configuration_dialog()
        except Exception as e:
            _LOGGER.error(f"Error opening configuration dialog: {e}")
    
    def on_open_settings_dialog(self):
        """Handle opening settings dialog"""
        try:
            # Open settings dialog directly via dialog manager
            if hasattr(self.main_window, 'dialog_manager'):
                self.main_window.dialog_manager.open_settings_dialog()
        except Exception as e:
            _LOGGER.error(f"Error opening settings dialog: {e}")
    
    def on_show_shortcuts_dialog(self):
        """Handle showing keyboard shortcuts dialog"""
        try:
            # Prefer centralized dialog manager
            if hasattr(self.main_window, 'dialog_manager'):
                self.main_window.dialog_manager.show_shortcuts_dialog()
            else:
                # Fallback simple info dialog
                QtWidgets.QMessageBox.information(
                    self.main_window,
                    "Keyboard Shortcuts",
                    "See documentation for keyboard shortcuts."
                )
            _LOGGER.debug("Shortcuts dialog shown")
        except Exception as e:
            _LOGGER.error(f"Error showing shortcuts dialog: {e}") 

    def on_save_plot_as_png(self):
        """Save the currently visible plot as PNG/JPG via dialog."""
        try:
            if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager:
                self.main_window.plot_manager.save_current_plot_as_png_dialog()
        except Exception as e:
            _LOGGER.error(f"Error saving plot as PNG: {e}")

    def on_save_plot_as_svg(self):
        """Save the currently visible plot as SVG via dialog."""
        try:
            if hasattr(self.main_window, 'plot_manager') and self.main_window.plot_manager:
                self.main_window.plot_manager.save_current_plot_as_svg_dialog()
        except Exception as e:
            _LOGGER.error(f"Error saving plot as SVG: {e}")