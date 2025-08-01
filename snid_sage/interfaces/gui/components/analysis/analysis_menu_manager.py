"""
SNID SAGE - Analysis Menu Manager
=================================

Dedicated menu manager for analysis operations in PySide6 GUI that handles:
- Analysis context menu creation and styling
- Quick analysis and advanced analysis workflows
- Analysis results dialogs and visualization launching
- Games integration during analysis

This extracts the complex analysis menu logic from the main GUI class.

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import time
from typing import Optional, Dict, Any, List, Tuple

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.analysis_menu_manager')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.analysis_menu_manager')


class AnalysisMenuManager:
    """
    Manages analysis menu creation and workflow for PySide6 GUI
    
    This class handles:
    - Context menu creation for analysis options
    - Quick analysis with default settings
    - Advanced analysis with configuration dialog
    - Analysis results viewing and visualization
    - Games integration during analysis
    """
    
    def __init__(self, main_window):
        """
        Initialize the analysis menu manager
        
        Args:
            main_window: Reference to the main PySide6 GUI window
        """
        self.main_window = main_window
        self.app_controller = main_window.app_controller
        
        # Menu styling
        self.menu_stylesheet = """
            QMenu {
                background: #ffffff;
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px;
                font-size: 11pt;
            }
            QMenu::item {
                padding: 8px 16px;
                margin: 2px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #3b82f6;
                color: white;
            }
            QMenu::item:disabled {
                color: #9ca3af;
            }
        """
    
    def show_analysis_menu(self):
        """Show analysis options menu when clicking the analysis button"""
        try:
            # Check if spectrum is loaded
            wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "Analysis Error", 
                    "Please load a spectrum file before running analysis."
                )
                return
            
            # Create context menu
            menu = QtWidgets.QMenu(self.main_window)
            menu.setStyleSheet(self.menu_stylesheet)
            
            # Add menu actions
            self._add_analysis_actions(menu)
            self._add_games_action(menu)
            self._add_results_actions(menu)
            
            # Show menu at button position
            button_rect = self.main_window.analysis_btn.geometry()
            menu_pos = self.main_window.analysis_btn.mapToGlobal(
                QtCore.QPoint(0, button_rect.height())
            )
            menu.exec(menu_pos)
            
        except Exception as e:
            _LOGGER.error(f"Error showing analysis menu: {e}")
            # Fallback to advanced analysis
            self.run_advanced_analysis()
    
    def _add_analysis_actions(self, menu):
        """Add analysis execution actions to menu"""
        # Quick analysis option
        quick_action = QtGui.QAction("Quick Analysis (Default Settings)", self.main_window)
        quick_action.setToolTip("Run analysis immediately with optimized default parameters")
        quick_action.triggered.connect(self.run_quick_analysis)
        menu.addAction(quick_action)
        
        menu.addSeparator()
        
        # Advanced analysis option
        advanced_action = QtGui.QAction("⚙️ Advanced Analysis Configuration", self.main_window)
        advanced_action.setToolTip("Configure custom analysis parameters before running")
        advanced_action.triggered.connect(self.run_advanced_analysis)
        menu.addAction(advanced_action)
        
        menu.addSeparator()
    
    def _add_games_action(self, menu):
        """Add games integration action to menu"""
        games_action = QtGui.QAction("🎮 Play Games While Analyzing", self.main_window)
        games_action.setToolTip("Play Space Debris Cleanup game while SNID analysis runs")
        games_action.triggered.connect(self.main_window.start_games_menu)
        menu.addAction(games_action)
        
        menu.addSeparator()
    
    def _add_results_actions(self, menu):
        """Add analysis results actions to menu"""
        # Check if analysis results are available
        has_results = (hasattr(self.app_controller, 'snid_results') and 
                      self.app_controller.snid_results is not None)
        
        if has_results:
            results_action = QtGui.QAction("📋 View Analysis Results", self.main_window)
            results_action.setToolTip("View detailed classification results")
            results_action.triggered.connect(self.show_analysis_results)
            menu.addAction(results_action)
            
            gmm_action = QtGui.QAction("🎯 View GMM Clustering", self.main_window)
            gmm_action.setToolTip("View GMM clustering visualization")
            gmm_action.triggered.connect(self.show_gmm_clustering)
            menu.addAction(gmm_action)
        else:
            # Show disabled actions if no results
            no_results_action = QtGui.QAction("📋 View Analysis Results (No results yet)", self.main_window)
            no_results_action.setEnabled(False)
            menu.addAction(no_results_action)
            
            no_gmm_action = QtGui.QAction("🎯 View GMM Clustering (No results yet)", self.main_window)
            no_gmm_action.setEnabled(False)
            menu.addAction(no_gmm_action)
    
    def run_quick_analysis(self):
        """Run SNID analysis immediately with default settings"""
        try:
            wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "Analysis Error", 
                    "Please load a spectrum file before running analysis."
                )
                return
            
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
                        QtWidgets.QMessageBox.warning(
                            self.main_window,
                            "Preprocessing Error",
                            "Failed to preprocess spectrum. Cannot proceed with analysis."
                        )
                        return
                else:
                    return
            
            # Show comprehensive progress dialog
            try:
                from snid_sage.interfaces.gui.components.pyside6_dialogs.analysis_progress_dialog import show_analysis_progress_dialog
                self.main_window.progress_dialog = show_analysis_progress_dialog(
                    self.main_window, 
                    "Quick SNID Analysis"
                )
                self.main_window.progress_dialog.add_progress_line("Starting quick analysis with default settings...", "info")
            except ImportError:
                # Fallback if progress dialog not available
                self.main_window.progress_dialog = None
            
            # Run analysis with default parameters immediately
            _LOGGER.info("Running quick SNID analysis with default settings...")
            self.main_window.status_label.setText("Running quick SNID analysis...")
            
            # Run analysis via app controller with default parameters
            success = self.app_controller.run_analysis(
                zmin=-0.01,
                zmax=1.0,
                age_range=None,
                lapmin=0.3,
                rlapmin=5.0,
                max_output_templates=10,
                verbose=False,
                show_plots=False,
                save_plots=False
            )
            
            if success:
                self._handle_analysis_success()
            else:
                self.main_window.status_label.setText("Quick analysis failed")
                
        except Exception as e:
            _LOGGER.error(f"Error running quick analysis: {e}")
            self.main_window.status_label.setText("Quick analysis error occurred")
            QtWidgets.QMessageBox.critical(
                self.main_window,
                "Analysis Error",
                f"Failed to run quick analysis:\n{str(e)}"
            )
    
    def run_advanced_analysis(self):
        """Run SNID analysis with configuration dialog"""
        try:
            wave, flux = self.app_controller.get_spectrum_data()
            if wave is None or flux is None:
                QtWidgets.QMessageBox.warning(
                    self.main_window, 
                    "Analysis Error", 
                    "Please load a spectrum file before running analysis."
                )
                return
            
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
            
            # Directly open configuration dialog
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
                self.main_window.status_label.setText("Running SNID analysis with configured settings...")
                
                # Apply configuration and run analysis
                if hasattr(self.app_controller, 'current_config'):
                    if 'analysis' not in self.app_controller.current_config:
                        self.app_controller.current_config['analysis'] = {}
                    self.app_controller.current_config['analysis'].update(config_params)
                
                # Run the analysis with configured parameters
                success = self._run_configured_analysis(config_params)
                
                if success:
                    self._handle_analysis_success()
                    _LOGGER.info("Advanced SNID analysis completed successfully")
                else:
                    QtWidgets.QMessageBox.critical(
                        self.main_window,
                        "Analysis Error",
                        "Failed to run SNID analysis with configured parameters"
                    )
                    
            except ImportError as e:
                _LOGGER.error(f"Configuration dialog not available: {e}")
                QtWidgets.QMessageBox.critical(
                    self.main_window,
                    "Configuration Error",
                    "Configuration dialog is not available"
                )
                
        except Exception as e:
            _LOGGER.error(f"Error running advanced analysis: {e}")
            self.main_window.status_label.setText("Analysis error occurred")
    
    def _run_configured_analysis(self, config_params):
        """Run SNID analysis with configured parameters"""
        try:
            # Show comprehensive progress dialog similar to quick analysis
            try:
                from snid_sage.interfaces.gui.components.pyside6_dialogs.analysis_progress_dialog import show_analysis_progress_dialog
                self.main_window.progress_dialog = show_analysis_progress_dialog(
                    self.main_window, 
                    "Advanced SNID Analysis"
                )
                self.main_window.progress_dialog.add_progress_line("Starting advanced analysis with configured settings...", "info")
            except ImportError:
                # Fallback if progress dialog not available
                self.main_window.progress_dialog = None
            
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

    def _handle_analysis_success(self):
        """Handle successful analysis completion"""
        try:
            # Update workflow state
            from snid_sage.interfaces.gui.controllers.pyside6_app_controller import WorkflowState
            self.app_controller.update_workflow_state(WorkflowState.ANALYSIS_COMPLETE)
            self.main_window.status_label.setText("SNID analysis completed successfully")
            
            # Enable analysis plot buttons
            for btn in self.main_window.analysis_plot_buttons:
                btn.setEnabled(True)
            for btn in self.main_window.nav_buttons:
                btn.setEnabled(True)
            
            # Enable advanced features
            self.main_window.emission_line_overlay_btn.setEnabled(True)
            self.main_window.ai_assistant_btn.setEnabled(True)
            
            # Update status indicators
            self.main_window.config_status_label.setText("✅ Analysis Complete")
            self.main_window.config_status_label.setStyleSheet(
                "font-style: italic; color: #059669; font-size: 10px !important; "
                "font-weight: normal !important; font-family: 'Segoe UI', Arial, sans-serif !important; "
                "line-height: 1.0 !important;"
            )
            
        except Exception as e:
            _LOGGER.error(f"Error handling analysis success: {e}")
    

    def show_analysis_results(self):
        """Show analysis results dialog"""
        try:
            from snid_sage.interfaces.gui.components.pyside6_dialogs import PySide6ResultsDialog
            
            # Pass current SNID results to the dialog
            snid_results = getattr(self.app_controller, 'snid_results', None)
            dialog = PySide6ResultsDialog(self.main_window, snid_results)
            dialog.show()
            
            _LOGGER.info("Analysis results dialog opened")
            
        except ImportError as e:
            _LOGGER.warning(f"PySide6 results dialog not available: {e}")
            QtWidgets.QMessageBox.information(
                self.main_window, 
                "Analysis Results", 
                "Analysis results dialog will be implemented."
            )
        except Exception as e:
            _LOGGER.error(f"Error opening analysis results dialog: {e}")
    
    def show_gmm_clustering(self):
        """Show GMM clustering - either cluster selection or visualization"""
        try:
            # Get current SNID results
            snid_results = getattr(self.app_controller, 'snid_results', None)
            if not snid_results:
                QtWidgets.QMessageBox.information(
                    self.main_window,
                    "GMM Clustering",
                    "No analysis results available. Please run analysis first."
                )
                return
            
            # Check if we have clustering results with multiple candidates
            clustering_results = getattr(snid_results, 'clustering_results', None)
            all_candidates = None
            
            if clustering_results:
                all_candidates = clustering_results.get('all_candidates', [])
                
            # If we have multiple cluster candidates, show selection dialog
            if all_candidates and len(all_candidates) > 1:
                _LOGGER.info(f"Opening cluster selection dialog with {len(all_candidates)} candidates")
                self._show_cluster_selection_dialog(all_candidates, snid_results)
            else:
                # Otherwise show the visualization dialog (current behavior)
                _LOGGER.info("Opening GMM clustering visualization dialog")
                self._show_gmm_visualization_dialog(snid_results)
                
        except Exception as e:
            _LOGGER.error(f"Error opening GMM clustering: {e}")
            QtWidgets.QMessageBox.warning(
                self.main_window,
                "GMM Clustering Error", 
                f"Error opening GMM clustering: {str(e)}"
            )
    
    def _show_cluster_selection_dialog(self, all_candidates, snid_results):
        """Show cluster selection dialog for choosing winning cluster"""
        try:
            from snid_sage.interfaces.gui.components.pyside6_dialogs.cluster_selection_dialog import show_cluster_selection_dialog
            
            def on_cluster_selected(selected_cluster, selected_index):
                """Callback when user selects a cluster"""
                try:
                    _LOGGER.info(f"User selected cluster {selected_index + 1}: {selected_cluster.get('type', 'Unknown')}")
                    
                    # Update the clustering results with the new winning cluster
                    if hasattr(snid_results, 'clustering_results'):
                        snid_results.clustering_results['winning_cluster'] = selected_cluster
                        snid_results.clustering_results['best_cluster'] = selected_cluster
                        snid_results.clustering_results['user_selected_cluster'] = selected_cluster
                        snid_results.clustering_results['user_selected_index'] = selected_index
                        
                        # Mark all clusters as not winning, then mark the selected one
                        for cluster in snid_results.clustering_results.get('clusters', []):
                            cluster['is_winning'] = False
                        selected_cluster['is_winning'] = True
                    
                    # CRITICAL: Update best_matches to only contain cluster templates (like app controller does)
                    if hasattr(snid_results, 'best_matches') and selected_cluster.get('matches'):
                        cluster_matches = selected_cluster.get('matches', [])
                        
                        # Sort cluster matches by best available metric (RLAP-Cos if available, otherwise RLAP) descending
                        try:
                            from snid_sage.shared.utils.math_utils import get_best_metric_value
                            cluster_matches_sorted = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
                        except ImportError:
                            # Fallback sorting if math utils not available
                            cluster_matches_sorted = sorted(cluster_matches, 
                                                          key=lambda m: m.get('rlap_cos', m.get('rlap', 0)), 
                                                          reverse=True)
                        
                        # Update best_matches to only contain cluster templates
                        max_templates = 10  # Default limit
                        snid_results.best_matches = cluster_matches_sorted[:max_templates]
                        
                        # Also update top_matches and filtered_matches for consistency
                        snid_results.top_matches = cluster_matches_sorted[:max_templates]
                        snid_results.filtered_matches = cluster_matches_sorted
                        
                        _LOGGER.info(f"🎯 Filtered templates: {len(cluster_matches)} cluster matches -> "
                                    f"{len(snid_results.best_matches)} displayed templates")
                        
                        # Update top-level result properties to reflect the best match from the selected cluster
                        if cluster_matches_sorted:
                            best_cluster_match = cluster_matches_sorted[0]
                            template = best_cluster_match.get('template', {})
                            
                            # Update main result properties
                            snid_results.template_name = template.get('name', 'Unknown')
                            snid_results.consensus_type = template.get('type', 'Unknown')
                            snid_results.redshift = best_cluster_match.get('redshift', 0.0)
                            snid_results.rlap = best_cluster_match.get('rlap', 0.0)
                            
                            # Update RLAP-Cos if available
                            if 'rlap_cos' in best_cluster_match:
                                snid_results.rlap_cos = best_cluster_match.get('rlap_cos', 0.0)
                            
                            _LOGGER.info(f"🎯 Updated result properties: {snid_results.template_name} ({snid_results.consensus_type}) "
                                        f"z={snid_results.redshift:.4f}, RLAP={snid_results.rlap:.2f}")
                    
                    # Update the main GUI display with the new results
                    self._update_gui_after_cluster_selection(snid_results, selected_cluster)
                    
                    _LOGGER.info("✅ Cluster selection completed and GUI updated")
                    
                except Exception as e:
                    _LOGGER.error(f"Error processing cluster selection: {e}")
                    QtWidgets.QMessageBox.warning(
                        self.main_window,
                        "Cluster Selection Error",
                        f"Error updating results with selected cluster: {str(e)}"
                    )
            
            # Show cluster selection dialog with callback
            show_cluster_selection_dialog(
                parent=self.main_window,
                clusters=all_candidates, 
                snid_result=snid_results,
                callback=on_cluster_selected
            )
            
        except ImportError as e:
            _LOGGER.warning(f"Cluster selection dialog not available: {e}")
            # Fallback to visualization dialog
            self._show_gmm_visualization_dialog(snid_results)
        except Exception as e:
            _LOGGER.error(f"Error showing cluster selection dialog: {e}")
            # Fallback to visualization dialog
            self._show_gmm_visualization_dialog(snid_results)
    
    def _show_gmm_visualization_dialog(self, snid_results):
        """Show GMM clustering visualization dialog (original behavior)"""
        try:
            from snid_sage.interfaces.gui.components.pyside6_dialogs.gmm_clustering_dialog import PySide6GMMClusteringDialog
            
            dialog = PySide6GMMClusteringDialog(self.main_window, snid_results)
            dialog.show()
            
            _LOGGER.info("GMM clustering visualization dialog opened")
            
        except ImportError as e:
            _LOGGER.warning(f"PySide6 GMM clustering dialog not available: {e}")
            QtWidgets.QMessageBox.information(
                self.main_window, 
                "GMM Clustering", 
                "GMM clustering visualization not available."
            )
        except Exception as e:
            _LOGGER.error(f"Error opening GMM clustering visualization dialog: {e}")
    
    def _update_gui_after_cluster_selection(self, snid_results, selected_cluster):
        """Update GUI state after user selects a different cluster"""
        try:
            # Update app controller results
            if hasattr(self.app_controller, 'snid_results'):
                self.app_controller.snid_results = snid_results
            
            # CRITICAL: Also update the main window's stored results
            if hasattr(self.main_window, 'snid_results'):
                self.main_window.snid_results = snid_results
            if hasattr(self.main_window, 'analysis_results'):
                self.main_window.analysis_results = snid_results
            
            # Reset template index to 0 to show the best template from the new cluster
            if hasattr(self.app_controller, 'current_template'):
                self.app_controller.current_template = 0
            
            # CRITICAL: Call update_results_display to refresh the entire display
            if hasattr(self.main_window, 'update_results_display'):
                self.main_window.update_results_display(snid_results)
                _LOGGER.debug("Main GUI results display updated after cluster selection")
            
            # Trigger GUI updates
            if hasattr(self.main_window, 'plot_manager'):
                # Refresh the main plot with updated results
                self.main_window.plot_manager.refresh_plot()
                _LOGGER.debug("Main plot refreshed after cluster selection")
            
            # Update any visible results dialogs
            if hasattr(self.main_window, 'refresh_results_displays'):
                self.main_window.refresh_results_displays()
                _LOGGER.debug("Results displays refreshed after cluster selection")
            
            # Show confirmation message
            cluster_type = selected_cluster.get('type', 'Unknown')
            cluster_size = selected_cluster.get('size', 0)
            
            QtWidgets.QMessageBox.information(
                self.main_window,
                "Cluster Selection Updated",
                f"Successfully updated winning cluster to:\n\n"
                f"Type: {cluster_type}\n"
                f"Matches: {cluster_size}\n\n"
                f"The main display has been updated with the new results."
            )
            
        except Exception as e:
            _LOGGER.error(f"Error updating GUI after cluster selection: {e}") 