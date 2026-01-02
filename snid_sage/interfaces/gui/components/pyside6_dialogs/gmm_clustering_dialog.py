"""
SNID SAGE - GMM Clustering Dialog - PySide6 Version
=================================================

Interactive GMM clustering visualization dialog for SNID analysis results.
Displays redshift distribution, cluster assignments, and clustering quality metrics.

Features:
- Interactive PyQtGraph plots of redshift vs metric values
- Cluster identification with different colors
- Winning cluster highlighting
- Quality metrics and statistics
- Export functionality for plots and data
- Modern Qt styling
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import json

# PyQtGraph for high-performance plotting (software rendering only for WSL compatibility)
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
    # Configure PyQtGraph for complete software rendering
    pg.setConfigOptions(
        useOpenGL=False,     # Disable OpenGL completely
        antialias=True,      # Keep antialiasing for quality
        enableExperimental=False,  # Disable experimental features
        crashWarning=False   # Reduce warnings
    )
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None

# Matplotlib for 3D plotting (Qt helper, consistent with other dialogs)
try:
    from snid_sage.interfaces.gui.utils.matplotlib_qt import get_qt_mpl
    plt, Figure, FigureCanvas, _NavigationToolbar = get_qt_mpl()
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FigureCanvas = None
    Figure = None

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_gmm')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_gmm')

# Enhanced dialog button styling
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except Exception:
    ENHANCED_BUTTONS_AVAILABLE = False
# Import GMM clustering utilities
try:
    from snid_sage.snid.cosmological_clustering import perform_direct_gmm_clustering
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_metric_name_for_match
    GMM_AVAILABLE = True
except ImportError:
    _LOGGER.warning("GMM clustering not available")
    GMM_AVAILABLE = False


class PySide6GMMClusteringDialog(QtWidgets.QDialog):
    """
    PySide6 dialog for GMM clustering visualization.
    
    Shows redshift distribution, cluster assignments, quality metrics, and allows
    interactive exploration of clustering results.
    """
    
    def __init__(self, parent, analysis_results=None):
        """
        Initialize GMM clustering dialog.
        
        Args:
            parent: Parent window
            analysis_results: SNID analysis results object
        """
        super().__init__(parent)
        # Ensure full cleanup on close to avoid stale Matplotlib/Qt references when reopening
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        
        self.parent_gui = parent
        self.analysis_results = analysis_results
        
        # Clustering data
        self.all_matches = []
        self.clustering_results = {}
        self.plot_data = {}
        
        # UI components
        self.plot_widget = None
        self.info_text = None
        self.cluster_table = None
        self.overlay_canvas = None
        self.overlay_fig = None
        self.overlay_ax = None
        
        # Color scheme matching other dialogs
        self.colors = {
            'bg': '#f8fafc',
            'panel_bg': '#ffffff',
            'text_primary': '#1e293b',
            'text_secondary': '#64748b',
            'border': '#e2e8f0',
            'success': '#22c55e',
            'warning': '#f59e0b',
            'danger': '#ef4444',
            'accent': '#3b82f6'
        }
        
        # Cluster colors for plotting
        self.cluster_colors = [
            '#3b82f6',  # Blue
            '#ef4444',  # Red  
            '#22c55e',  # Green
            '#f59e0b',  # Orange
            '#8b5cf6',  # Purple
            '#06b6d4',  # Cyan
            '#ec4899',  # Pink
            '#84cc16',  # Lime
            '#f97316',  # Orange alt
            '#6366f1'   # Indigo
        ]
        
        self._setup_dialog()
        self._create_interface()
        self._extract_data_and_cluster()
        self._populate_results()
    
    def _setup_dialog(self):
        """Setup dialog window properties"""
        self.setWindowTitle("GMM Clustering Analysis")
        # Match cluster selection dialog sizing/behavior
        self.setMinimumSize(1100, 600)
        self.resize(1200, 650)
        try:
            self.setWindowFlags(
                QtCore.Qt.Dialog |
                QtCore.Qt.WindowTitleHint |
                QtCore.Qt.WindowSystemMenuHint |
                QtCore.Qt.WindowMinMaxButtonsHint |
                QtCore.Qt.WindowCloseButtonHint
            )
        except Exception:
            pass
        self.setModal(False)  # Allow interaction with main window
        
        # Apply styling
        # Use platform-aware font stack for macOS
        self.setStyleSheet(f"""
            QDialog {{
                background: {self.colors['bg']};
                color: {self.colors['text_primary']};
                font-family: Arial, "Helvetica Neue", Helvetica, "Segoe UI", sans-serif;
            }}
            
            QGroupBox {{
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background: {self.colors['panel_bg']};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: {self.colors['text_primary']};
            }}
            
            QTextEdit {{
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                background: {self.colors['panel_bg']};
                font-family: "Consolas", "Monaco", monospace;
                font-size: 10pt;
                padding: 8px;
                selection-background-color: {self.colors['accent']};
            }}
            
            QTableWidget {{
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                background: {self.colors['panel_bg']};
                selection-background-color: {self.colors['accent']};
                gridline-color: {self.colors['border']};
            }}
            
            QTableWidget::item {{
                padding: 6px;
                border: none;
            }}
            
            QHeaderView::section {{
                background: #e2e8f0;
                border: 1px solid {self.colors['border']};
                padding: 8px;
                font-weight: bold;
                font-size: 9pt;
            }}
            
            QPushButton {{
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 10pt;
                background: {self.colors['panel_bg']};
                min-width: 80px;
            }}
            
            QPushButton:hover {{
                background: #f1f5f9;
            }}
            
            QPushButton:pressed {{
                background: #e2e8f0;
            }}
            
            QPushButton#primary_btn {{
                background: {self.colors['success']};
                border: 2px solid {self.colors['success']};
                color: white;
            }}
            
            QPushButton#primary_btn:hover {{
                background: #16a34a;
            }}
        """)
    
    def _create_interface(self):
        """Create the dialog interface"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Main content - horizontal split
        content_layout = QtWidgets.QHBoxLayout()
        
        # Left panel - plot
        self._create_plot_panel(content_layout)
        
        # Right panel - info and controls
        self._create_info_panel(content_layout)
        
        layout.addLayout(content_layout, 1)
    
    def _create_header(self, layout):
        """Create dialog header"""
        header_frame = QtWidgets.QFrame()
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QtWidgets.QLabel("GMM Clustering Analysis")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 18pt;
            font-weight: bold;
            color: #3b82f6;
            margin: 10px 0;
        """)
        header_layout.addWidget(title)
        
        subtitle = QtWidgets.QLabel("Gaussian Mixture Model clustering of template matches")
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 12pt;
            color: #64748b;
            margin-bottom: 10px;
        """)
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header_frame)
    
    def _create_plot_panel(self, layout):
        """Create plot panel with matplotlib 3D (Qt backend, no OpenGL)"""
        plot_group = QtWidgets.QGroupBox("3D GMM Clustering Visualization")
        plot_layout = QtWidgets.QVBoxLayout(plot_group)
        
        # Guard against headless environments or missing Matplotlib
        screens = QtGui.QGuiApplication.screens()
        if not screens or not MATPLOTLIB_AVAILABLE:
            fallback_label = QtWidgets.QLabel(
                ("No display screens available" if not screens else "Matplotlib Required for 3D Plotting") +
                "\n\n3D GMM clustering visualization is unavailable in the current environment.\n\n"
                "Clustering analysis will still be available in the text summary."
            )
            fallback_label.setAlignment(QtCore.Qt.AlignCenter)
            fallback_label.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12pt;")
            fallback_label.setWordWrap(True)
            plot_layout.addWidget(fallback_label)
        else:
            # Create matplotlib figure with white background
            self.fig = Figure(figsize=(10, 8), facecolor='white')
            self.fig.patch.set_facecolor('white')
            # Use tighter margins so the 3D plot fills more of the available canvas,
            # and further minimize empty space above the plot
            try:
                self.fig.subplots_adjust(left=0.06, right=0.98, top=0.999, bottom=0.07)
            except Exception:
                pass
            
            # Create 3D axes
            self.ax = self.fig.add_subplot(111, projection='3d')
            self.ax.set_facecolor('white')
            
            # Create Qt canvas widget (ownership managed by layout)
            self.plot_widget = FigureCanvas(self.fig)
            # Slightly smaller to accommodate labels
            self.plot_widget.setMinimumHeight(280)
            
            plot_layout.addWidget(self.plot_widget)
        
        layout.addWidget(plot_group, 2)  # Slightly reduce left plot panel width
    
    def _create_info_panel(self, layout):
        """Create information and controls panel"""
        info_widget = QtWidgets.QWidget()
        info_layout = QtWidgets.QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Right panel is vertically split: overlay (2/3) on top, summary (1/3) bottom
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(8)
        
        # Spectrum overlay panel (top)
        overlay_group = QtWidgets.QGroupBox("")
        overlay_layout = QtWidgets.QVBoxLayout(overlay_group)
        
        # Small header above overlay with template name + metric
        self.overlay_header = QtWidgets.QLabel("")
        self.overlay_header.setAlignment(QtCore.Qt.AlignLeft)
        self.overlay_header.setStyleSheet("font-weight: bold; color: #000000; padding: 2px 4px;")
        overlay_layout.addWidget(self.overlay_header)
        
        if MATPLOTLIB_AVAILABLE:
            try:
                self.overlay_fig = Figure(figsize=(5, 3), dpi=100, facecolor='white')
                self.overlay_ax = self.overlay_fig.add_subplot(111)
                self.overlay_ax.set_facecolor('white')
                self.overlay_ax.grid(True, alpha=0.3, linewidth=0.5)
                for spine in self.overlay_ax.spines.values():
                    spine.set_color('#666666')
                self.overlay_canvas = FigureCanvas(self.overlay_fig)
                try:
                    # Provide a bit more room and margins like matches panel
                    self.overlay_fig.subplots_adjust(left=0.12, right=0.96, top=0.92, bottom=0.12)
                except Exception:
                    pass
                try:
                    self.overlay_canvas.setMinimumHeight(260)
                except Exception:
                    pass
                overlay_layout.addWidget(self.overlay_canvas)
            except Exception as e:
                fallback_label = QtWidgets.QLabel(f"Overlay unavailable: {e}")
                fallback_label.setAlignment(QtCore.Qt.AlignCenter)
                fallback_label.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 10pt;")
                overlay_layout.addWidget(fallback_label)
        else:
            fallback_label = QtWidgets.QLabel("Matplotlib is required to display the overlay.")
            fallback_label.setAlignment(QtCore.Qt.AlignCenter)
            fallback_label.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 10pt;")
            overlay_layout.addWidget(fallback_label)
        # Add overlay to right panel with higher stretch
        right_panel.addWidget(overlay_group, 2)
        
        # Clustering summary (bottom)
        summary_group = QtWidgets.QGroupBox("Clustering Summary")
        summary_layout = QtWidgets.QVBoxLayout(summary_group)
        
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        # Slightly smaller summary for better balance with overlay
        self.info_text.setMaximumHeight(220)
        summary_layout.addWidget(self.info_text)
        # Add summary to right panel with lower stretch
        right_panel.addWidget(summary_group, 1)
        
        # Add the right panel container to info_layout
        info_layout.addLayout(right_panel)
        
        layout.addWidget(info_widget, 2)  # Match cluster selection proportion for right panel
    
    def _create_button_bar(self, layout):
        """Create bottom button bar"""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Refresh clustering button
        refresh_btn = QtWidgets.QPushButton("Refresh Clustering")
        refresh_btn.setObjectName("refresh_btn")
        refresh_btn.clicked.connect(self._refresh_clustering)
        button_layout.addWidget(refresh_btn)
        
        # Export plot button
        if PYQTGRAPH_AVAILABLE:
            export_plot_btn = QtWidgets.QPushButton("Export Plot")
            export_plot_btn.setObjectName("export_plot_btn")
            export_plot_btn.clicked.connect(self._export_plot)
            button_layout.addWidget(export_plot_btn)
        
        button_layout.addStretch()
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setObjectName("close_btn")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

        # Apply enhanced styles
        try:
            if ENHANCED_BUTTONS_AVAILABLE:
                self.button_manager = enhance_dialog_with_preset(self, 'gmm_clustering_dialog')
        except Exception as e:
            _LOGGER.warning(f"Failed to apply enhanced button styling: {e}")
    
    def _extract_data_and_cluster(self):
        """Extract template matches and perform GMM clustering"""
        if not self.analysis_results:
            _LOGGER.warning("No analysis results available for GMM clustering")
            return
        
        try:
            # Extract template matches from analysis results.
            #
            # For parity with the core pipeline (CLI + GUI main analysis), prefer:
            # 1) all_matches (full post-phase-2-gating list)
            # 2) best_matches (top-N display list)
            # 3) filtered_matches / top_matches as fallbacks
            if hasattr(self.analysis_results, 'all_matches') and isinstance(self.analysis_results.all_matches, list) and self.analysis_results.all_matches:
                self.all_matches = self.analysis_results.all_matches
            elif hasattr(self.analysis_results, 'best_matches') and isinstance(self.analysis_results.best_matches, list):
                self.all_matches = self.analysis_results.best_matches
            elif hasattr(self.analysis_results, 'clusters') and self.analysis_results.clusters:
                # If we have clusters, extract matches from all clusters
                self.all_matches = []
                for cluster in self.analysis_results.clusters:
                    if 'matches' in cluster:
                        self.all_matches.extend(cluster['matches'])
            elif hasattr(self.analysis_results, 'filtered_matches') and isinstance(self.analysis_results.filtered_matches, list) and self.analysis_results.filtered_matches:
                self.all_matches = self.analysis_results.filtered_matches
            elif hasattr(self.analysis_results, 'top_matches') and isinstance(self.analysis_results.top_matches, list) and self.analysis_results.top_matches:
                self.all_matches = self.analysis_results.top_matches
            else:
                _LOGGER.warning("No template matches found in analysis results")
                return
            
            if not self.all_matches:
                _LOGGER.warning("No template matches available for clustering")
                return
            
            # Perform GMM clustering if available
            if GMM_AVAILABLE and len(self.all_matches) >= 1:  # Allow clustering with any matches
                _LOGGER.info(f"Running GMM clustering on {len(self.all_matches)} template matches")
                
                # Use the same threshold/bounds as the pipeline when available
                try:
                    thr = float(getattr(self.analysis_results, "hsigma_lap_ccc_threshold", 1.5) or 1.5)
                except Exception:
                    thr = 1.5
                try:
                    zmin_used = getattr(self.analysis_results, "zmin_used", None)
                    zmax_used = getattr(self.analysis_results, "zmax_used", None)
                    zmin_used = float(zmin_used) if zmin_used is not None else None
                    zmax_used = float(zmax_used) if zmax_used is not None else None
                except Exception:
                    zmin_used, zmax_used = None, None

                self.clustering_results = perform_direct_gmm_clustering(
                    matches=self.all_matches,
                    min_matches_per_type=1,  # Accept any type with at least 1 match
                    max_clusters_per_type=10,
                    verbose=True,
                    hsigma_lap_ccc_threshold=thr,
                    zmin=zmin_used,
                    zmax=zmax_used,
                )
                
                # If clustering failed (e.g., too few/weak survivors), create a weak fallback so UI can still render
                if not self.clustering_results or not self.clustering_results.get('success', False):
                    reason = None
                    try:
                        reason = self.clustering_results.get('reason') if self.clustering_results else None
                    except Exception:
                        reason = None
                    _LOGGER.info(f"GMM clustering not reliable (reason={reason}); creating weak fallback for visualization")
                    self._create_fallback_clustering(failure_reason=reason, method='weak_fallback')
                else:
                    _LOGGER.info(f"GMM clustering completed successfully")
                
            else:
                _LOGGER.warning("GMM clustering not available or insufficient matches")
                # Create basic grouping by type as fallback
                self._create_fallback_clustering(method='type_grouping_fallback')
        
        except Exception as e:
            _LOGGER.error(f"Error during GMM clustering: {e}")
            self._create_fallback_clustering()
    
    def _create_fallback_clustering(self, failure_reason: Optional[str] = None, method: str = 'type_grouping_fallback'):
        """Create basic type-based clustering as fallback
        
        Includes single-template groups so that even 1 survivor is visualized.
        """
        type_groups = {}
        for match in self.all_matches:
            sn_type = match.get('template', {}).get('type', 'Unknown')
            if sn_type not in type_groups:
                type_groups[sn_type] = []
            type_groups[sn_type].append(match)
        
        # Create simple clustering results structure
        clusters = []
        for i, (sn_type, matches) in enumerate(type_groups.items()):
            if len(matches) >= 1:  # Include even single survivors
                redshifts = [m.get('redshift', 0) for m in matches]
                mean_redshift = np.mean(redshifts)
                redshift_scatter = np.std(redshifts)
                
                clusters.append({
                    'cluster_id': i,
                    'type': sn_type,
                    'matches': matches,
                    'size': len(matches),
                    'mean_redshift': mean_redshift,
                    'redshift_scatter': redshift_scatter,
                    'quality_score': max(1, len(matches)) * 10,  # Simple quality metric (non-zero)
                    'is_winning': i == 0  # First (largest) cluster as winning
                })
        
        self.clustering_results = {
            'success': True,
            'clusters': clusters,
            'winning_cluster': clusters[0] if clusters else None,
            'method': method,
            'reason': failure_reason or 'insufficient_data',
            'weak_fallback': True
        }
    
    def _populate_results(self):
        """Populate the dialog with clustering results"""
        try:
            # Populate summary text
            self._populate_summary()
            
            # Create or refresh spectrum overlay on the right
            self._create_overlay_plot()
            
            # Create plot if matplotlib 3D is available
            if hasattr(self, 'ax'):
                self._create_clustering_plot()
            
        except Exception as e:
            _LOGGER.error(f"Error populating results: {e}")
            self._show_error(f"Error displaying clustering results: {str(e)}")
    
    def _populate_summary(self):
        """Populate the clustering summary text"""
        if not self.clustering_results.get('success', False):
            reason = self.clustering_results.get('reason', 'insufficient_data')
            self.info_text.setPlainText(
                f"⚠️ Weak match: GMM did not run or was not reliable.\n"
                f"Only one (or very few) survivors were found; clustering was not performed (reason: {reason})."
            )
            return
        
        # Do not gate/throw away clusters in the UI.
        clusters = [
            c for c in (self.clustering_results.get('clusters', []) or [])
            if isinstance(c, dict)
        ]
        winning_cluster = self.clustering_results.get('winning_cluster')
        method = self.clustering_results.get('method', 'direct_gmm')
        
        # Keep summary minimal but informative for normal/success paths as well
        lines = []
        if method != 'direct_gmm':
            reason = self.clustering_results.get('reason', None)
            lines.append("⚠️ Weak match: GMM did not run or was not reliable.")
            if reason:
                lines.append(f"Reason: {reason}")
        
        if winning_cluster:
            # Prefer enhanced/weighted cluster redshift for display, with safe fallbacks
            try:
                import math
                
                def _finite(val):
                    return isinstance(val, (int, float)) and not math.isnan(float(val))
                
                z_val = winning_cluster.get('enhanced_redshift', None)
                if not _finite(z_val):
                    z_val = winning_cluster.get('weighted_mean_redshift', None)
                if not _finite(z_val):
                    z_val = winning_cluster.get('mean_redshift', 0.0)
                if not _finite(z_val):
                    z_val = 0.0
                z_val = float(z_val)
            except Exception:
                # Conservative fallback
                try:
                    z_val = float(
                        winning_cluster.get(
                            'enhanced_redshift',
                            winning_cluster.get(
                                'weighted_mean_redshift',
                                winning_cluster.get('mean_redshift', 0.0),
                            ),
                        )
                    )
                except Exception:
                    z_val = 0.0
            
            lines.append(
                f"Winning Type: {winning_cluster.get('type', 'Unknown')}  |  "
                f"Size: {winning_cluster.get('size', 0)}  |  z={z_val:.6f}"
            )

        self.info_text.setPlainText("\n".join(lines))
    
    def _populate_cluster_table(self):
        """Populate the cluster details table"""
        # No-op
        return
        
    def _create_overlay_plot(self):
        """Render a small overlay of input spectrum vs best template on the right panel."""
        try:
            if not MATPLOTLIB_AVAILABLE or self.overlay_ax is None or self.overlay_canvas is None:
                return
        
            # Clear axis
            self.overlay_ax.clear()
            self.overlay_ax.set_facecolor('white')
            self.overlay_ax.grid(True, alpha=0.3, linewidth=0.5)
            for spine in self.overlay_ax.spines.values():
                spine.set_color('#666666')
            
            # Determine candidate matches to display
            matches = []
            try:
                # Prefer winning cluster matches
                if self.clustering_results and self.clustering_results.get('winning_cluster'):
                    matches = self.clustering_results['winning_cluster'].get('matches', [])
                # Fallbacks from analysis_results
                if (not matches) and self.analysis_results is not None:
                    if hasattr(self.analysis_results, 'best_matches') and self.analysis_results.best_matches:
                        matches = self.analysis_results.best_matches
                    elif hasattr(self.analysis_results, 'filtered_matches') and self.analysis_results.filtered_matches:
                        matches = self.analysis_results.filtered_matches
                    elif hasattr(self.analysis_results, 'top_matches') and self.analysis_results.top_matches:
                        matches = self.analysis_results.top_matches
            except Exception:
                matches = []
            
            # Choose the single best match
            best_match = None
            if matches:
                try:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    matches_sorted = sorted(matches, key=get_best_metric_value, reverse=True)
                except Exception:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    matches_sorted = sorted(matches, key=get_best_metric_value, reverse=True)
                best_match = matches_sorted[0]
            
            # Get input spectrum data
            input_wave = input_flux = None
            if (self.analysis_results is not None and hasattr(self.analysis_results, 'processed_spectrum') and
                    self.analysis_results.processed_spectrum):
                ps = self.analysis_results.processed_spectrum
                if 'log_wave' in ps and 'log_flux' in ps:
                    input_wave = ps['log_wave']
                    input_flux = ps['log_flux']
                elif 'wave' in ps and 'flux' in ps:
                    input_wave = ps['wave']
                    input_flux = ps['flux']
            elif (self.analysis_results is not None and hasattr(self.analysis_results, 'input_spectrum') and
                  isinstance(self.analysis_results.input_spectrum, dict)):
                input_wave = self.analysis_results.input_spectrum.get('wave')
                input_flux = self.analysis_results.input_spectrum.get('flux')
            
            # Plot input spectrum
            if input_wave is not None and input_flux is not None:
                try:
                    w = np.asarray(input_wave, dtype=float)
                    f = np.asarray(input_flux, dtype=float)
                    finite = np.isfinite(w) & np.isfinite(f)
                    w, f = w[finite], f[finite]
                    self.overlay_ax.plot(w, f, color='#0078d4', linewidth=1.0, alpha=0.8, label='Input')
                except Exception:
                    pass
            
            # Plot best template
            if best_match is not None:
                try:
                    t_wave = t_flux = None
                    if 'spectra' in best_match and isinstance(best_match['spectra'], dict):
                        if 'flux' in best_match['spectra']:
                            t_wave = best_match['spectra']['flux'].get('wave')
                            t_flux = best_match['spectra']['flux'].get('flux')
                        elif 'wave' in best_match['spectra']:
                            t_wave = best_match['spectra']['wave']
                            t_flux = best_match['spectra']['flux']
                    elif 'wave' in best_match:
                        t_wave = best_match['wave']
                        t_flux = best_match['flux']
                    elif 'template_wave' in best_match:
                        t_wave = best_match['template_wave']
                        t_flux = best_match['template_flux']
                    if t_wave is not None and t_flux is not None:
                        t_w = np.asarray(t_wave, dtype=float)
                        t_f = np.asarray(t_flux, dtype=float)
                        finite_t = np.isfinite(t_w) & np.isfinite(t_f)
                        t_w, t_f = t_w[finite_t], t_f[finite_t]
                        self.overlay_ax.plot(
                            t_w,
                            t_f,
                            color='#E74C3C',
                            linewidth=1.0,
                            alpha=0.8,
                            label='Template',
                        )
                except Exception:
                    pass
            
            # Update overlay header with template name and metric
            try:
                if best_match is not None and hasattr(self, 'overlay_header') and self.overlay_header is not None:
                    from snid_sage.shared.utils import clean_template_name
                    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
                    template_name = clean_template_name(best_match.get('name', 'Unknown'))
                    metric_value = get_best_metric_value(best_match)
                    metric_name = get_best_metric_name(best_match)
                    self.overlay_header.setText(f"{template_name}  —  {metric_name}: {metric_value:.2f}")
                elif hasattr(self, 'overlay_header') and self.overlay_header is not None:
                    self.overlay_header.setText("")
            except Exception:
                pass
            
            # Labels and legend
            self.overlay_ax.set_xlabel('Wavelength (Å)', fontsize=9, color='#666666')
            self.overlay_ax.set_ylabel('Flux', fontsize=9, color='#666666')
            # No legend to keep compact
            
            # Redraw
            self.overlay_canvas.draw()
        except Exception as e:
            _LOGGER.error(f"Error creating overlay plot: {e}")
    
    def _create_clustering_plot(self):
        """Create the 3D clustering plot using matplotlib (no OpenGL required)"""
        if not hasattr(self, 'ax') or not self.clustering_results.get('success', False):
            return
        
        try:
            # Clear the existing plot
            self.ax.clear()
            
            # Cluster list for plotting (may be clusters or candidates depending on the producer).
            clusters = (
                self.clustering_results.get('clusters', None)
                or self.clustering_results.get('all_candidates', None)
                or []
            )

            # Do not gate/throw away clusters in the 3D plot.
            clusters = [c for c in clusters if isinstance(c, dict)]
            
            if not clusters:
                self.ax.text(0.5, 0.5, 0.5, 'No clustering data available', 
                           ha='center', va='center', transform=self.ax.transAxes)
                self.plot_widget.draw()
                return
            
            # Prepare type mapping with consistent ordering (Type on Y)
            unique_types = sorted(list(set(c.get('type', 'Unknown') for c in clusters)))
            type_to_index = {sn_type: i for i, sn_type in enumerate(unique_types)}
            
            # Define color map for clusters
            import matplotlib.cm as cm
            colors = cm.Set1(np.linspace(0, 1, len(clusters)))
            
            legend_elements = []
            
            for i, cluster in enumerate(clusters):
                matches = cluster.get('matches', [])
                if not matches:
                    continue
                
                # Extract axes: X=redshift, Y=type index, Z=best metric (HσLAP-CCC preferred)
                xs = []
                ys = []
                zs = []
                
                for match in matches:
                    z = match.get('redshift', 0.0)
                    mval = get_best_metric_value(match)
                    sn_type = cluster.get('type', 'Unknown')
                    y_idx = type_to_index.get(sn_type, 0)
                    xs.append(z)
                    ys.append(y_idx)
                    zs.append(mval)

                if not xs:
                    continue
                
                color = colors[i % len(colors)]
                is_winning = cluster.get('is_winning', False)
                size = 60 if is_winning else 40
                alpha = 0.9 if is_winning else 0.8
                marker = 'o' if is_winning else '^'
                
                scatter = self.ax.scatter(xs, ys, zs,
                    c=[color], s=size, alpha=alpha, marker=marker,
                                          edgecolors='gray', linewidths=0.5,
                                          label=f'Cluster {i+1}{"" if not is_winning else " (Best)"}')
                legend_elements.append(scatter)
            
            # Set labels and title
            # Larger axis labels with padding restored to 15
            self.ax.set_xlabel('Redshift (z)', fontsize=15, labelpad=15)
            # Keep shorter label text ("Type") but with larger font
            self.ax.set_ylabel('Type', fontsize=15, labelpad=15)
            # Z is the best metric (HσLAP-CCC preferred)
            self.ax.set_zlabel('HσLAP-CCC', fontsize=15, labelpad=15)
            # No title for clean look
            try:
                self.ax.set_title('')
            except Exception:
                pass

            # Set Y ticks to types (smaller font to reduce overlap)
            self.ax.set_yticks(range(len(unique_types)))
            self.ax.set_yticklabels(unique_types, fontsize=7)

            # Enhanced 3D styling like cluster selection dialog (white panes, light gray edges)
            try:
                self.ax.xaxis.pane.fill = True
                self.ax.yaxis.pane.fill = True
                self.ax.zaxis.pane.fill = True
                self.ax.xaxis.pane.set_facecolor('white')
                self.ax.yaxis.pane.set_facecolor('white')
                self.ax.zaxis.pane.set_facecolor('white')
                self.ax.xaxis.pane.set_edgecolor('lightgray')
                self.ax.yaxis.pane.set_edgecolor('lightgray')
                self.ax.zaxis.pane.set_edgecolor('lightgray')
                self.ax.xaxis.pane.set_alpha(1.0)
                self.ax.yaxis.pane.set_alpha(1.0)
                self.ax.zaxis.pane.set_alpha(1.0)
            except Exception:
                pass

            self.ax.xaxis.label.set_color('#000000')
            self.ax.yaxis.label.set_color('#000000')
            self.ax.zaxis.label.set_color('#000000')
            # Slightly smaller tick labels on all axes (z values, HσLAP-CCC values, and type indices)
            self.ax.tick_params(colors='#666666', labelsize=10)
            self.ax.grid(True, alpha=0.4, color='gray', linestyle='-', linewidth=0.5)
            
            # Add legend
            # No legend for weak survivor view

            # Lock rotation to horizontal (match main cluster selection behavior)
            self.ax.view_init(elev=25, azim=45)
            # Make the Type (Y) axis visually taller and also slightly enlarge the Redshift (X) axis
            try:
                self.ax.set_box_aspect([2.9, 2.7, 2.0])
            except Exception:
                pass

            def on_rotate(event):
                if event.inaxes == self.ax:
                    self.ax.view_init(elev=25, azim=self.ax.azim)
                    self.plot_widget.draw_idle()

            self.plot_widget.mpl_connect('motion_notify_event', on_rotate)
            
            # Refresh the plot
            self.plot_widget.draw()
            
            _LOGGER.info(f"Created 3D GMM plot with matplotlib: {len(clusters)} clusters")
            
        except Exception as e:
            _LOGGER.error(f"Error creating 3D clustering plot: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_error(self, error_msg):
        """Show error message in info text"""
        error_text = f"""
❌ Error Loading Clustering Results

{error_msg}

Please try running the analysis again or check the logs for more details.
        """.strip()
        
        self.info_text.setPlainText(error_text)
    
    def _highlight_winning_cluster(self):
        """Highlight the winning cluster in the plot"""
        if not hasattr(self, 'ax'):
            return
        
        # Refresh the plot to show the winning cluster highlighted
        self._create_clustering_plot()
        
        # Show a message
        QtWidgets.QMessageBox.information(
            self,
            "Winning Cluster",
            "The winning cluster is marked with larger circles and highlighted in the table."
        )
    
    def _refresh_clustering(self):
        """Refresh the clustering analysis"""
        try:
            self._extract_data_and_cluster()
            self._populate_results()
            
            QtWidgets.QMessageBox.information(
                self,
                "Clustering Refreshed",
                "GMM clustering analysis has been refreshed with current data."
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Refresh Error",
                f"Failed to refresh clustering:\n{str(e)}"
            )
    
    def _export_clustering_data(self):
        """Export clustering data to JSON file"""
        if not self.clustering_results:
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Clustering Data",
            "gmm_clustering_results.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                # Prepare export data (make it JSON serializable)
                export_data = {
                    'clustering_method': self.clustering_results.get('method', 'unknown'),
                    'total_matches': len(self.all_matches),
                    'num_clusters': len([
                        c for c in (self.clustering_results.get('clusters', []) or [])
                        if isinstance(c, dict)
                    ]),
                    'clusters': []
                }
                
                for cluster in [
                    c for c in (self.clustering_results.get('clusters', []) or [])
                    if isinstance(c, dict)
                ]:
                    cluster_data = {
                        'cluster_id': cluster.get('cluster_id', -1),
                        'type': cluster.get('type', 'Unknown'),
                        'size': cluster.get('size', 0),
                        'mean_redshift': float(cluster.get('mean_redshift', 0)),
                        'redshift_scatter': float(cluster.get('redshift_scatter', 0)),
                        'quality_score': float(cluster.get('quality_score', 0)),
                        'is_winning': cluster.get('is_winning', False)
                    }
                    export_data['clusters'].append(cluster_data)
                
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                self._show_status_message(f"Clustering data exported to {file_path}")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export clustering data:\n{str(e)}"
                )
    
    def _export_plot(self):
        """Export the plot to image file"""
        if not hasattr(self, 'fig'):
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            "gmm_clustering_plot.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)"
        )
        
        if file_path:
            try:
                # Export matplotlib figure
                self.fig.savefig(file_path, dpi=300, bbox_inches='tight', 
                               facecolor='white', edgecolor='none')
                
                self._show_status_message(f"Plot exported to {file_path}")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export plot:\n{str(e)}"
                )
    
    def _show_status_message(self, message):
        """Show a temporary status message"""
        _LOGGER.info(message)


def show_gmm_clustering_dialog(parent, analysis_results=None):
    """
    Show the GMM clustering dialog.
    
    Args:
        parent: Parent window
        analysis_results: SNID analysis results object
        
    Returns:
        PySide6GMMClusteringDialog instance
    """
    dialog = PySide6GMMClusteringDialog(parent, analysis_results)
    dialog.show()
    return dialog 