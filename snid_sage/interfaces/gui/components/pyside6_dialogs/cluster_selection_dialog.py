"""
SNID SAGE - Cluster Selection Dialog - PySide6 Version with Matplotlib
=====================================================

Interactive GMM cluster selection dialog for SNID analysis results.
Allows users to select the best cluster from GMM clustering results.

Features:
- Interactive matplotlib 3D plots of cluster visualization
- Cluster dropdown selector for easy selection  
- Top 2 template matches panel with spectrum overlays
- Real-time cluster selection feedback
- Automatic fallback to best cluster
- Modern Qt styling matching other dialogs
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable

# Matplotlib for 3D plotting (Qt helper)
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
    _LOGGER = get_logger('gui.pyside6_cluster_selection')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_cluster_selection')

# Import math utilities
try:
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_metric_name_for_match
    MATH_UTILS_AVAILABLE = True
except ImportError:
    MATH_UTILS_AVAILABLE = False

# Import string utility to clean template names (with safe fallback)
try:
    from snid_sage.shared.utils import clean_template_name  # type: ignore
except Exception:
    def clean_template_name(name):
        return name


class PySide6ClusterSelectionDialog(QtWidgets.QDialog):
    """
    Interactive GMM cluster selection dialog for SNID analysis results.
    
    This dialog provides:
    - Interactive 3D cluster visualization using matplotlib
    - Cluster dropdown selection 
    - Top 2 template matches with spectrum overlays
    - Real-time cluster selection feedback
    - Automatic best cluster fallback
    """
    
    def __init__(self, parent=None, clusters=None, snid_result=None, callback=None):
        """
        Initialize cluster selection dialog
        
        Args:
            parent: Parent widget
            clusters: List of cluster candidates 
            snid_result: SNID analysis results
            callback: Callback function when cluster is selected
        """
        super().__init__(parent)
        # Ensure this dialog fully deletes its widgets when closed to avoid stale references
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        
        # Store input data (do not gate/throw away clusters).
        self.all_candidates = [c for c in (clusters or []) if isinstance(c, dict)]
        self.snid_result = snid_result
        self.callback = callback
        
        # Selection state
        self.selected_cluster = None
        self.selected_index = -1
        
        # Get automatic best from clustering results
        self.automatic_best = None
        if hasattr(snid_result, 'clustering_results') and snid_result.clustering_results:
            self.automatic_best = snid_result.clustering_results.get('best_cluster')
        # If automatic best isn't a dict, fall back to first candidate.
        if not isinstance(self.automatic_best, dict):
            self.automatic_best = None
        if not self.automatic_best and self.all_candidates:
            self.automatic_best = self.all_candidates[0]
        
        # Sort candidates by score
        self._sort_candidates()
        
        # UI components
        self.cluster_dropdown = None
        self.plot_widget = None  # Matplotlib canvas
        self.matches_canvas = None  # Matplotlib canvas for matches
        self.scatter_plots = []  # Store scatter plot objects for highlighting
        self.fig = None  # Main 3D plot figure
        self.ax = None   # Main 3D plot axes
        self.matches_fig = None  # Matches figure
        self.matches_axes = []   # Matches subplot axes
        self.scatter_to_index = {}  # Map matplotlib scatter artists to cluster indices
        
        # Colors for different supernova types
        self.type_colors = self._get_type_colors()
        # Cached type mapping for plots/highlights
        self._unique_types: Optional[List[str]] = None
        self._type_to_index: Optional[Dict[str, int]] = None

        # Plot filter state: hide "Very Low" clusters by default (Q_cluster < 2.5)
        self.show_very_low: bool = False
        self._very_low_checkbox: Optional[QtWidgets.QCheckBox] = None
        self._dropdown_index_to_candidate_index: List[Optional[int]] = []
        self._candidate_index_to_dropdown_index: Dict[int, int] = {}

        # Special case: if ONLY Very Low clusters exist, show them by default
        # (otherwise the user would see an empty 3D plot on open).
        try:
            has_any = bool(self.all_candidates)
            has_non_very_low = any((not self._is_very_low(c)) for c in self.all_candidates)
            has_very_low = any(self._is_very_low(c) for c in self.all_candidates)
            if has_any and has_very_low and (not has_non_very_low):
                self.show_very_low = True
        except Exception:
            pass
        
        # Validate matplotlib availability
        if not MATPLOTLIB_AVAILABLE:
            QtWidgets.QMessageBox.warning(
                self, "Missing Dependency", 
                "Matplotlib is required for cluster visualization.\n"
                "Please ensure matplotlib is installed."
            )
        
        # Validate input data
        if not self.all_candidates:
            QtWidgets.QMessageBox.warning(
                self, "No Clusters", 
                "No cluster candidates available.\n"
                "This dialog will automatically use the best available result."
            )
            # Auto-close and use automatic fallback
            QtCore.QTimer.singleShot(100, self._auto_select_and_close)
            return
        
        try:
            self._setup_ui()
            self._populate_data()
            
            # Auto-select the automatic best cluster
            if self.all_candidates:
                best_index = self._find_automatic_best_index()
                self._select_cluster(best_index)
                
        except Exception as e:
            _LOGGER.error(f"Error initializing cluster selection dialog: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Initialization Error",
                f"Failed to initialize cluster selection dialog:\n{e}\n\n"
                "Will use automatic cluster selection."
            )
            QtCore.QTimer.singleShot(100, self._auto_select_and_close)
    
    def _sort_candidates(self):
        """Sort candidates by score"""
        def _get_candidate_score(c):
            # Preferred metric hierarchy: penalised_score → composite_score → mean_metric
            return (
                c.get('penalized_score') or
                c.get('penalised_score') or  # British spelling safeguard
                c.get('composite_score') or
                c.get('mean_metric') or 0.0
            )

        try:
            self.all_candidates.sort(key=_get_candidate_score, reverse=True)
        except Exception as sort_err:
            _LOGGER.debug(f"Could not sort clusters by score: {sort_err}")
    
    # ------------------------------------------------------------------
    # Cluster helper utilities
    # ------------------------------------------------------------------
    def _get_candidate_q_score(self, candidate: Dict[str, Any]) -> float:
        """
        Return the cluster quality score used as Q_cluster in the GUI.

        Uses the same hierarchy as dropdown/sorting:
        penalized_score → penalised_score → composite_score → mean_metric.
        Returns NaN if missing/unparseable so it won't be treated as Very Low by default.
        """
        raw = (
            candidate.get('penalized_score')
            or candidate.get('penalised_score')  # British spelling safeguard
            or candidate.get('composite_score')
            or candidate.get('mean_metric')
        )
        if raw is None:
            return float('nan')
        try:
            return float(raw)
        except Exception:
            return float('nan')

    def _is_very_low(self, candidate: Dict[str, Any]) -> bool:
        """Very Low is defined as Q_cluster < 2.5, matching backend thresholds."""
        try:
            q = self._get_candidate_q_score(candidate)
            return bool(np.isfinite(q) and q < 2.5)
        except Exception:
            return False

    def _position_very_low_checkbox(self) -> None:
        """Pin the 'Show Very Low' checkbox to the top-right corner of the plot canvas."""
        try:
            if self.plot_widget is None or self._very_low_checkbox is None:
                return
            # A very small in-canvas margin; keep it almost in the corner.
            margin_x = 3
            margin_y = 0
            cb = self._very_low_checkbox
            cb.adjustSize()
            x = max(margin_x, self.plot_widget.width() - cb.width() - margin_x)
            y = margin_y
            cb.move(x, y)
            cb.raise_()
        except Exception:
            return

    def _get_cluster_display_redshift(self, candidate: Dict[str, Any]) -> float:
        """
        Get a robust display redshift for a cluster.
        
        Preference order (matching other GUI summaries conceptually):
        1. enhanced_redshift (joint cluster estimate, if available and finite)
        2. weighted_mean_redshift
        3. mean_redshift
        4. mean of match redshifts
        5. 0.0 as a last resort
        """
        try:
            import math
            
            def _finite_or_none(val):
                if isinstance(val, (int, float)) and not math.isnan(float(val)):
                    return float(val)
                return None
            
            # 1. enhanced_redshift
            z_val = _finite_or_none(candidate.get('enhanced_redshift', None))
            if z_val is not None:
                return z_val
            
            # 2. weighted_mean_redshift
            z_val = _finite_or_none(candidate.get('weighted_mean_redshift', None))
            if z_val is not None:
                return z_val
            
            # 3. mean_redshift
            z_val = _finite_or_none(candidate.get('mean_redshift', None))
            if z_val is not None:
                return z_val
            
            # 4. Mean of match redshifts if matches are present
            matches = candidate.get('matches', []) or []
            if matches:
                redshifts = []
                for m in matches:
                    rz = _finite_or_none(m.get('redshift', None))
                    if rz is not None:
                        redshifts.append(rz)
                if redshifts:
                    return float(np.mean(redshifts))
        except Exception as e:
            _LOGGER.debug(f"Error computing display redshift for cluster: {e}")
        
        # 5. Safe fallback
        return 0.0
    
    def _find_automatic_best_index(self):
        """Find index of automatic best cluster after sorting"""
        if not self.automatic_best:
            return 0
        
        # Try direct object identity first
        try:
            return self.all_candidates.index(self.automatic_best)
        except ValueError:
            pass
        
        # Fallback by (type, cluster_id)
        t_type = self.automatic_best.get('type')
        t_id = self.automatic_best.get('cluster_id')
        for idx, cand in enumerate(self.all_candidates):
            if cand.get('type') == t_type and cand.get('cluster_id') == t_id:
                return idx
        return 0
    
    def _get_type_colors(self):
        """Get color mapping for supernova types"""
        return {
            'Ia': '#FFB3B3',      # Pastel Red
            'Ib': '#FFCC99',      # Pastel Orange  
            'Ic': '#99CCFF',      # Pastel Blue
            'II': '#9370DB',      # Medium slate blue
            'Galaxy': '#8A2BE2',  # Blue-violet for galaxies
            'Star': '#FFD700',    # Gold for stars
            'AGN': '#FF6347',     # Tomato red for AGN/QSO
            'SLSN': '#20B2AA',    # Light sea green
            'LFBOT': '#FFFF99',   # Pastel Yellow
            'TDE': '#D8BFD8',     # Pastel Purple/Thistle
            'KN': '#B3FFFF',      # Pastel Cyan
            'GAP': '#FFCC80',     # Pastel Orange
            'Unknown': '#D3D3D3', # Light Gray
            'Other': '#C0C0C0'    # Silver
        }
    
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("GMM Cluster Selection")
        self.setMinimumSize(1100, 600)  # Set minimum size instead of fixed size
        self.resize(1200, 650)  # Initial size - smaller than before
        
        # Enable minimize, maximize, and close buttons (normal window behavior)
        self.setWindowFlags(
            QtCore.Qt.Dialog | 
            QtCore.Qt.WindowTitleHint | 
            QtCore.Qt.WindowSystemMenuHint | 
            QtCore.Qt.WindowMinMaxButtonsHint | 
            QtCore.Qt.WindowCloseButtonHint
        )
        
        # Apply modern styling (matching PySide6 theme)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 1px solid #e2e8f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: white;
            }
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #3b82f6;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #cbd5e1;
                background-color: white;
                selection-background-color: #dbeafe;
            }
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        
        # Main layout - vertical without header or footer
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Main content (horizontal split - 60% left, 40% right) - no header, no footer
        self._create_main_content(main_layout)
    
    def _create_main_content(self, layout):
        """Create main content with horizontal split layout (60/40 split with proper spacing)"""
        content_frame = QtWidgets.QFrame()
        content_layout = QtWidgets.QHBoxLayout(content_frame)
        content_layout.setContentsMargins(5, 5, 5, 5)  # Add margins to frame
        content_layout.setSpacing(8)  # Reduced spacing between panels
        
        # Left panel (60% width) - cluster selection and 3D plot
        self._create_left_panel(content_layout)
        
        # Right panel (40% width) - template matches
        self._create_right_panel(content_layout)
        
        layout.addWidget(content_frame)
    
    def _create_left_panel(self, layout):
        """Create left panel with cluster dropdown and 3D matplotlib plot"""
        self.left_panel = QtWidgets.QWidget()
        # Remove fixed width constraints to allow resizing
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)  # Reduced margins
        left_layout.setSpacing(10)  # Reduced spacing
        
        # Cluster selection dropdown
        selection_group = QtWidgets.QGroupBox("Select the best Type from GMM analysis")
        selection_layout = QtWidgets.QVBoxLayout(selection_group)
        selection_layout.setContentsMargins(10, 5, 10, 5)
        
        # Dropdown and button container (horizontal layout)
        dropdown_container = QtWidgets.QWidget()
        dropdown_layout = QtWidgets.QHBoxLayout(dropdown_container)
        dropdown_layout.setContentsMargins(0, 0, 0, 0)
        dropdown_layout.setSpacing(10)
        
        # Dropdown
        self.cluster_dropdown = QtWidgets.QComboBox()
        self.cluster_dropdown.setMaximumWidth(400)  # Limit dropdown width to prevent button cutoff
        self.cluster_dropdown.currentIndexChanged.connect(self._on_cluster_changed)
        dropdown_layout.addWidget(self.cluster_dropdown, 1)  # Take most space
        
        # Confirm button (smaller, inline with dropdown)
        confirm_btn = QtWidgets.QPushButton("Confirm")
        confirm_btn.setObjectName("confirm_btn")
        confirm_btn.clicked.connect(self._confirm_selection)
        confirm_btn.setDefault(True)
        dropdown_layout.addWidget(confirm_btn)
        
        selection_layout.addWidget(dropdown_container)
        
        left_layout.addWidget(selection_group)
        
        # 3D Plot area using matplotlib
        plot_group = QtWidgets.QGroupBox("📊 3D Cluster Visualization")
        plot_layout = QtWidgets.QVBoxLayout(plot_group)
        
        if MATPLOTLIB_AVAILABLE:
            # Create matplotlib 3D plot
            self._create_matplotlib_3d_plot(plot_layout)
        else:
            # Fallback message
            fallback = QtWidgets.QLabel(
                "📊 Matplotlib Required for 3D Clustering Visualization\n\n"
                "Install matplotlib to view interactive 3D cluster plots:\n\n"
                "pip install matplotlib\n\n"
                "Cluster selection is still available via the dropdown above."
            )
            fallback.setAlignment(QtCore.Qt.AlignCenter)
            fallback.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12pt;")
            fallback.setWordWrap(True)
            fallback.setMinimumHeight(250)  # Smaller height for compact dialog
            plot_layout.addWidget(fallback)
        
        left_layout.addWidget(plot_group, 1)
        
        layout.addWidget(self.left_panel, 3)  # Give left panel 3 parts of space (60%)

        # Apply enhanced styles (after UI is built)
        try:
            from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
            self.button_manager = enhance_dialog_with_preset(self, 'cluster_selection_dialog')
        except Exception:
            pass
    
    def _create_matplotlib_3d_plot(self, layout):
        """Create matplotlib 3D scatter plot"""
        # Create matplotlib figure with white background
        self.fig = Figure(figsize=(8, 6), facecolor='white')  # Smaller initial size, will scale with window
        self.fig.patch.set_facecolor('white')
        
        # MAXIMIZE the plot area - use almost the entire window space, with minimal top margin
        self.fig.subplots_adjust(left=0.03, right=0.97, top=0.995, bottom=0.08)
        
        # Create 3D axes
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_facecolor('white')
        
        # Create Qt canvas widget (parent will be managed by the layout/container)
        self.plot_widget = FigureCanvas(self.fig)
        self.plot_widget.setMinimumHeight(300)  # Smaller minimum height for initial size
        
        # Add canvas to layout
        layout.addWidget(self.plot_widget)

        # In-plot (in-canvas) toggle using Qt for consistent styling (top-right corner).
        try:
            self._very_low_checkbox = QtWidgets.QCheckBox("Show Very Low", self.plot_widget)
            self._very_low_checkbox.setChecked(bool(self.show_very_low))
            # Lightweight styling that matches the dialog's modern look
            self._very_low_checkbox.setStyleSheet("""
                QCheckBox {
                    background: rgba(255, 255, 255, 230);
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 4px 8px;
                    color: #111827;
                    font-weight: 600;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                }
            """)

            def _on_checkbox_changed(state: int) -> None:
                self.show_very_low = bool(state)
                self._plot_clusters()

            self._very_low_checkbox.stateChanged.connect(_on_checkbox_changed)

            # Keep it pinned on resize
            _orig_resize_event = self.plot_widget.resizeEvent

            def _resize_event(evt):
                try:
                    if callable(_orig_resize_event):
                        _orig_resize_event(evt)
                finally:
                    self._position_very_low_checkbox()

            self.plot_widget.resizeEvent = _resize_event  # type: ignore[assignment]
            self._position_very_low_checkbox()
        except Exception as e:
            _LOGGER.debug(f"Could not create Qt 'Show Very Low' checkbox overlay: {e}")
        
        # Connect matplotlib events for interactivity
        self.plot_widget.mpl_connect('pick_event', self._on_plot_pick)
    
    def _create_right_panel(self, layout):
        """Create right panel with template matches using matplotlib"""
        self.right_panel = QtWidgets.QWidget()
        # Remove fixed width constraints to allow resizing
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(6, 6, 6, 6)  # Reduced margins
        right_layout.setSpacing(10)  # Reduced spacing
        
        # Top 2 matches panel
        matches_group = QtWidgets.QGroupBox("🔍 Top 2 Template Matches For Selected Cluster")
        matches_layout = QtWidgets.QVBoxLayout(matches_group)
        matches_layout.setContentsMargins(5, 5, 5, 5)
        
        if MATPLOTLIB_AVAILABLE:
            # Create matplotlib figure for matches
            self.matches_fig = Figure(figsize=(3.5, 5.5), dpi=100, facecolor='white')  # Even smaller to prevent label cutoff
            self.matches_fig.clear()
            
            # Create exactly 2 subplots vertically stacked
            self.matches_axes = []
            for i in range(2):
                ax = self.matches_fig.add_subplot(2, 1, i+1)
                ax.set_facecolor('white')
                ax.tick_params(colors='#666666', labelsize=10)
                for spine in ax.spines.values():
                    spine.set_color('#666666')
                ax.grid(True, alpha=0.3, linewidth=0.5)
                self.matches_axes.append(ax)
            
            # Optimize subplot parameters with more space for labels
            self.matches_fig.subplots_adjust(left=0.15, right=0.95, top=0.92, bottom=0.08, hspace=0.35)  # More space for labels
            
            # Embed in Qt widget
            self.matches_canvas = FigureCanvas(self.matches_fig)
            matches_layout.addWidget(self.matches_canvas)
        else:
            # Fallback text widget
            fallback_text = QtWidgets.QTextEdit()
            fallback_text.setReadOnly(True)
            fallback_text.setPlainText("Matplotlib required for template match visualization")
            matches_layout.addWidget(fallback_text)
        
        right_layout.addWidget(matches_group, 1)
        
        layout.addWidget(self.right_panel, 2)  # Give right panel 2 parts of space (40%)
    
    def _populate_data(self):
        """Populate dropdown and create 3D plot"""
        self._populate_dropdown()
        if MATPLOTLIB_AVAILABLE:
            self._plot_clusters()
    
    def _populate_dropdown(self):
        """Populate the cluster dropdown"""
        self.cluster_dropdown.clear()

        self._dropdown_index_to_candidate_index = []
        self._candidate_index_to_dropdown_index = {}

        # Find where Very Low starts (first candidate with Q_cluster < 2.5)
        very_low_start = None
        for idx, cand in enumerate(self.all_candidates):
            if self._is_very_low(cand):
                very_low_start = idx
                break

        for idx, candidate in enumerate(self.all_candidates):
            cluster_type = candidate.get('type', 'Unknown')
            size = len(candidate.get('matches', []))
            z_val = self._get_cluster_display_redshift(candidate)
            
            # Get quality score
            quality = (
                candidate.get('penalized_score') or
                candidate.get('penalised_score') or
                candidate.get('composite_score') or
                candidate.get('mean_metric') or 0.0
            )
            
            # Mark if this is the automatic best cluster
            is_best = (self.automatic_best is not None and candidate == self.automatic_best)
            best_mark = " 🏆" if is_best else ""
            
            item_text = (
                f"#{idx+1}: {cluster_type} "
                f"({size} templates, z={z_val:.6f}, Q={quality:.1f}){best_mark}"
            )

            # Insert a visual separator just before the first Very Low cluster entry.
            if very_low_start is not None and idx == very_low_start and idx != 0:
                try:
                    header_text = "──────── Very Low clusters (Q<2.5) ────────"
                    self.cluster_dropdown.addItem(header_text)
                    header_combo_idx = self.cluster_dropdown.count() - 1
                    self._dropdown_index_to_candidate_index.append(None)

                    # Make it look like a section header (disabled, bold, shaded)
                    try:
                        model = self.cluster_dropdown.model()
                        item = model.item(header_combo_idx)
                        if item is not None:
                            item.setEnabled(False)
                            f = item.font()
                            f.setBold(True)
                            item.setFont(f)
                            item.setForeground(QtGui.QBrush(QtGui.QColor("#475569")))  # slate-600
                            item.setBackground(QtGui.QBrush(QtGui.QColor("#f1f5f9")))  # slate-100
                    except Exception:
                        pass

                    # Extra visual separation line
                    self.cluster_dropdown.insertSeparator(self.cluster_dropdown.count())
                    self._dropdown_index_to_candidate_index.append(None)
                except Exception:
                    pass

            self.cluster_dropdown.addItem(item_text)
            combo_idx = self.cluster_dropdown.count() - 1
            self._dropdown_index_to_candidate_index.append(idx)
            self._candidate_index_to_dropdown_index[idx] = combo_idx
        
        # Set current selection
        if self.selected_index >= 0:
            dd_idx = self._candidate_index_to_dropdown_index.get(self.selected_index, -1)
            if dd_idx >= 0:
                self.cluster_dropdown.setCurrentIndex(dd_idx)
    
    def _plot_clusters(self):
        """Plot clusters with 3D scatter plot"""
        if not MATPLOTLIB_AVAILABLE or not self.all_candidates:
            return
            
        # Preserve current view (especially azimuth) to avoid resetting angle on redraws
        try:
            current_azim = getattr(self.ax, 'azim', 45)
        except Exception:
            current_azim = 45

        self.ax.clear()
        self.scatter_plots.clear()
        self.scatter_to_index.clear()

        # Filter candidates for plotting: hide "Very Low" by default unless toggled on.
        plotted = []
        for orig_idx, cand in enumerate(self.all_candidates):
            if (not self.show_very_low) and self._is_very_low(cand):
                continue
            plotted.append((orig_idx, cand))

        # Prepare and cache type mapping based on plotted candidates (keeps Type axis clean)
        self._unique_types = sorted(list(set(c.get('type', 'Unknown') for _, c in plotted))) if plotted else []
        self._type_to_index = {sn_type: i for i, sn_type in enumerate(self._unique_types)}
        
        # Determine metric name (HσLAP-CCC or HLAP)
        metric_name_global = 'HσLAP-CCC'
        if MATH_UTILS_AVAILABLE:
            for cand in self.all_candidates:
                if cand.get('matches'):
                    metric_name_global = get_metric_name_for_match(cand['matches'][0])
                    break
        
        # Plot all clusters with enhanced styling
        for i, candidate in plotted:
            candidate_redshifts, candidate_metrics = self._get_cluster_redshifts_and_metrics(candidate)
            if not candidate_redshifts:
                continue
            
            # Map type to Y index using cached mapping (fallback to 0 if missing)
            if self._type_to_index is None:
                type_index = 0
            else:
                type_index = self._type_to_index.get(candidate.get('type', 'Unknown'), 0)
            candidate_type_indices = [type_index] * len(candidate_redshifts)
            
            # Visual style: consistent size, no transparency
            size = 30  # Slightly smaller points for better readability
            alpha = 1.0  # No transparency as requested
            
            # Gray edges for all by default (black edges added later for selected)
            edgecolor = 'gray'
            linewidth = 0.5
            
            # Use consistent type colors
            color = self.type_colors.get(candidate['type'], self.type_colors['Unknown'])
            
            # Plot all points
            scatter = self.ax.scatter(
                candidate_redshifts,
                candidate_type_indices,
                candidate_metrics,
                c=color,
                s=size,
                alpha=alpha,
                edgecolors=edgecolor,
                linewidths=linewidth,
                picker=5  # enable picking with 5px tolerance
            )
            
            self.scatter_plots.append((scatter, i, candidate))
            # Map this scatter artist to its cluster index for quick lookup on pick
            self.scatter_to_index[scatter] = i
        
        # Enhanced 3D setup
        # Larger axis labels with padding restored to 15
        self.ax.set_xlabel('Redshift (z)', color='#000000', fontsize=15, labelpad=15)
        # Use a shorter Y label ("Type") to match the GMM clustering dialog
        self.ax.set_ylabel('Type', color='#000000', fontsize=15, labelpad=15)
        # Z label uses the global metric name (e.g., "HσLAP-CCC")
        self.ax.set_zlabel(metric_name_global, color='#000000', fontsize=15, labelpad=15)
        if self._unique_types is not None:
            self.ax.set_yticks(range(len(self._unique_types)))
            # Smaller Y tick labels to reduce overlap
            self.ax.set_yticklabels(self._unique_types, fontsize=7)
        
        # Set view and enable ONLY horizontal rotation, preserving current azimuth
        self.ax.view_init(elev=25, azim=current_azim)
        # Make the Type (Y) axis visually taller and also slightly enlarge the Redshift (X) axis
        try:
            self.ax.set_box_aspect([2.9, 2.7, 2.0])
        except Exception:
            pass
        
        # Enhanced 3D styling with completely white background
        try:
            # Ensure all panes are white and remove any blue artifacts
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
        except Exception as e:
            _LOGGER.warning(f"Some 3D styling options not available: {e}")
        
        # Enhanced plot styling
        self.ax.xaxis.label.set_color('#000000')
        self.ax.yaxis.label.set_color('#000000')
        self.ax.zaxis.label.set_color('#000000')
        # Slightly smaller tick labels on all axes (z values, metric values, and type indices)
        self.ax.tick_params(colors='#666666', labelsize=10)
        self.ax.grid(True, alpha=0.4, color='gray', linestyle='-', linewidth=0.5)
        
        # Connect rotation constraint to ONLY allow horizontal (azimuth) rotation
        def on_rotate(event):
            if event.inaxes == self.ax:
                # LOCK elevation to 25 degrees, only allow azimuth changes (horizontal rotation only)
                self.ax.view_init(elev=25, azim=self.ax.azim)
                self.plot_widget.draw_idle()
        
        self.plot_widget.mpl_connect('motion_notify_event', on_rotate)
        
        # Show persistent highlight for the auto-selected best cluster
        if self.selected_cluster is not None and self.selected_index >= 0:
            self._add_persistent_highlight(self.selected_index)
        
        self.plot_widget.draw()

    def _get_cluster_redshifts_and_metrics(self, candidate: Dict[str, Any]) -> Tuple[List[float], List[float]]:
        """
        Return lists of redshifts and metric values for the given cluster candidate.
        
        Uses get_best_metric_value when math utils are available; otherwise falls back
        to hlap/hsigma_lap_ccc fields. Provides sensible defaults when matches or metrics
        are missing so that plotting and highlighting can still work.
        """
        matches = candidate.get('matches', []) or []
        try:
            if not matches:
                # Fallback to aggregate stats on the candidate
                redshift = candidate.get('mean_redshift', 0.0)
                if MATH_UTILS_AVAILABLE:
                    metric_val = candidate.get('mean_metric', 0.0)
                else:
                    metric_val = candidate.get('mean_metric', 0.0)
                return [float(redshift)], [float(metric_val)]
            
            # Extract per-match redshifts and metrics
            redshifts: List[float] = []
            metrics: List[float] = []
            for m in matches:
                try:
                    z = float(m.get('redshift', 0.0))
                except Exception:
                    z = 0.0
                redshifts.append(z)
                
                if MATH_UTILS_AVAILABLE:
                    try:
                        metric_val = float(get_best_metric_value(m))
                    except Exception:
                        metric_val = float(m.get('hsigma_lap_ccc', m.get('hlap', 0.0)))
                else:
                    metric_val = float(m.get('hsigma_lap_ccc', m.get('hlap', 0.0)))
                metrics.append(metric_val)
            
            return redshifts, metrics
        except Exception as e:
            _LOGGER.debug(f"Error computing cluster redshifts/metrics: {e}")
            return [], []
    
    def _add_persistent_highlight(self, cluster_index):
        """Add persistent highlight for selected cluster"""
        try:
            # scatter_plots contains only *plotted* clusters; find by stored original index
            candidate = None
            for _scatter, idx, cand in self.scatter_plots:
                if idx == cluster_index:
                    candidate = cand
                    break
            if candidate is None:
                return

            # Use the same helper logic as in _plot_clusters to get points
            candidate_redshifts, candidate_metrics = self._get_cluster_redshifts_and_metrics(candidate)
            if not candidate_redshifts:
                return

            # Reuse cached type-to-index mapping from last plot (fallback safely if missing)
            if self._type_to_index is None:
                type_index = 0
            else:
                type_index = self._type_to_index.get(candidate.get('type', 'Unknown'), 0)
            candidate_type_indices = [type_index] * len(candidate_redshifts)

            # Add highlighted scatter with BLACK edges
            # Add highlighted scatter with picking disabled (so picks map to the base scatter only)
            self.ax.scatter(
                candidate_redshifts,
                candidate_type_indices,
                candidate_metrics,
                c=self.type_colors.get(candidate['type'], self.type_colors['Unknown']),
                s=40,
                alpha=1.0,
                edgecolors='black',
                linewidths=1.2,
                zorder=3,
                picker=False
            )
                
        except Exception as e:
            _LOGGER.debug(f"Error adding persistent highlight: {e}")
    
    def _on_plot_pick(self, event):
        """Handle matplotlib pick events to support left-click selection of clusters"""
        try:
            # Ensure this came from a mouse event and is a left-click
            mouse_event = getattr(event, 'mouseevent', None)
            if mouse_event is None or mouse_event.button != 1:
                return

            artist = getattr(event, 'artist', None)
            if artist is None:
                return

            # If the picked artist corresponds to a cluster scatter, select that cluster
            cluster_index = self.scatter_to_index.get(artist)
            if cluster_index is None:
                return

            self._select_cluster(cluster_index)
        except Exception as pick_err:
            _LOGGER.debug(f"Pick handling error: {pick_err}")
    
    def _on_cluster_changed(self, index):
        """Handle cluster dropdown selection change"""
        try:
            cand_idx = None
            if 0 <= index < len(self._dropdown_index_to_candidate_index):
                cand_idx = self._dropdown_index_to_candidate_index[index]
            if cand_idx is None:
                return

            # Avoid reprocessing if the same cluster is selected again (prevents duplicate logs)
            if cand_idx == self.selected_index:
                return

            if 0 <= cand_idx < len(self.all_candidates):
                self._select_cluster(cand_idx)
        except Exception:
            return
    
    def _select_cluster(self, cluster_index):
        """Select a cluster and update UI"""
        if 0 <= cluster_index < len(self.all_candidates):
            # If already selected, do nothing (prevents double logging on programmatic changes)
            if self.selected_index == cluster_index and self.selected_cluster is not None:
                return

            self.selected_cluster = self.all_candidates[cluster_index]
            self.selected_index = cluster_index

            # Update dropdown without emitting signals to avoid recursive selection
            if self.cluster_dropdown is not None:
                dd_idx = self._candidate_index_to_dropdown_index.get(cluster_index, -1)
                if dd_idx >= 0 and self.cluster_dropdown.currentIndex() != dd_idx:
                    was_blocked = self.cluster_dropdown.blockSignals(True)
                    try:
                        self.cluster_dropdown.setCurrentIndex(dd_idx)
                    finally:
                        self.cluster_dropdown.blockSignals(was_blocked)

            # Clear and add highlights
            if MATPLOTLIB_AVAILABLE:
                self._plot_clusters()  # Redraw plot with selection

            # Update matches panel
            self._update_matches_panel()

            _LOGGER.info(f"🎯 Selected cluster {cluster_index + 1}: {self.selected_cluster.get('type', 'Unknown')}")
    
    def _update_matches_panel(self):
        """Update the template matches panel"""
        if not MATPLOTLIB_AVAILABLE or not self.matches_canvas or not self.selected_cluster:
            return
        
        # Get top 2 matches from selected cluster
        if MATH_UTILS_AVAILABLE:
            matches = sorted(self.selected_cluster.get('matches', []), 
                            key=get_best_metric_value, reverse=True)[:2]
        else:
            matches = sorted(self.selected_cluster.get('matches', []), 
                            key=lambda m: m.get('hsigma_lap_ccc', m.get('hlap', 0.0)), reverse=True)[:2]
        
        # Get input spectrum data
        input_wave = input_flux = None
        if (self.snid_result is not None and hasattr(self.snid_result, 'processed_spectrum') and
                self.snid_result.processed_spectrum):
            # Try different keys for processed spectrum
            if 'log_wave' in self.snid_result.processed_spectrum:
                input_wave = self.snid_result.processed_spectrum['log_wave']
                input_flux = self.snid_result.processed_spectrum['log_flux']
            elif 'wave' in self.snid_result.processed_spectrum:
                input_wave = self.snid_result.processed_spectrum['wave']
                input_flux = self.snid_result.processed_spectrum['flux']
        elif (self.snid_result is not None and hasattr(self.snid_result, 'input_spectrum') and
              isinstance(self.snid_result.input_spectrum, dict)):
            input_wave = self.snid_result.input_spectrum.get('wave')
            input_flux = self.snid_result.input_spectrum.get('flux')
        
        # Clear all axes first
        for i, ax in enumerate(self.matches_axes):
            if ax is not None:
                ax.clear()
                ax.set_facecolor('white')
                ax.spines['top'].set_visible(True)
                ax.spines['right'].set_visible(True)
                ax.spines['bottom'].set_visible(True)
                ax.spines['left'].set_visible(True)
        
        # Update exactly 2 subplots
        for idx in range(2):
            if idx >= len(self.matches_axes):
                break
                
            ax = self.matches_axes[idx]
            if ax is None:
                continue
                
            ax.set_facecolor('white')
            ax.tick_params(colors='#666666', labelsize=9)
            for spine in ax.spines.values():
                spine.set_color('#666666')
            ax.grid(True, alpha=0.3, linewidth=0.5)
            
            if idx < len(matches) and matches[idx]:
                match = matches[idx]
                
                # Plot input spectrum
                if input_wave is not None and input_flux is not None:
                    ax.plot(input_wave, input_flux, color='#0078d4', linewidth=1.0, alpha=0.8, 
                           label='Input Spectrum', zorder=2)
                
                # Plot template match
                try:
                    # Try different ways to access template spectrum
                    t_wave = t_flux = None
                    
                    if 'spectra' in match and isinstance(match['spectra'], dict):
                        if 'flux' in match['spectra']:
                            t_wave = match['spectra']['flux'].get('wave')
                            t_flux = match['spectra']['flux'].get('flux')
                        elif 'wave' in match['spectra']:
                            t_wave = match['spectra']['wave']
                            t_flux = match['spectra']['flux']
                    elif 'wave' in match:
                        t_wave = match['wave']
                        t_flux = match['flux']
                    elif 'template_wave' in match:
                        t_wave = match['template_wave']
                        t_flux = match['template_flux']
                    
                    if t_wave is not None and t_flux is not None:
                        # Clean template name to remove _epoch_X suffix
                        template_name = clean_template_name(match.get('name', 'Unknown'))
                        ax.plot(
                            t_wave,
                            t_flux,
                            color='#E74C3C',
                            linewidth=1.0,
                            alpha=0.8,
                            label=f"Template: {template_name}",
                            zorder=3,
                        )
                        
                except Exception as e:
                    _LOGGER.debug(f"Error plotting template match {idx+1}: {e}")
                
                # Simplified title showing subtype instead of metric
                template_name = clean_template_name(match.get('name', 'Unknown'))
                template_info = match.get('template', {}) if isinstance(match.get('template', {}), dict) else {}
                subtype = (
                    template_info.get('subtype') or
                    match.get('subtype') or
                    match.get('type') or
                    'Unknown'
                )
                title_text = f"#{idx+1}: {template_name} ({subtype})"
                ax.set_title(title_text, fontsize=10, color='#000000', 
                           fontweight='bold', pad=5)
                
                # Add legend for first plot only to save space
                if idx == 0:
                    ax.legend(loc='upper right', fontsize=7, framealpha=0.9)
                    
            else:
                # No match available
                ax.text(0.5, 0.5, f'No Match #{idx+1}', transform=ax.transAxes,
                       ha='center', va='center', fontsize=12, 
                       color='#666666', style='italic')
                ax.set_title(f"#{idx+1}: No Template Available", fontsize=11, 
                           color='#666666')
            
            # Set labels (only for bottom plot to save space)
            if idx == 1:  # Always the last (2nd) plot
                ax.set_xlabel('Wavelength (Å)', fontsize=10, color='#666666')
            ax.set_ylabel('Flux', fontsize=9, color='#666666')
        
        # Refresh the canvas
        try:
            if hasattr(self, 'matches_canvas') and self.matches_canvas:
                self.matches_canvas.draw()
        except Exception as e:
            _LOGGER.error(f"Error refreshing matches canvas: {e}")
    
    def get_result(self):
        """Get the selected cluster result"""
        return self.selected_cluster, self.selected_index
    
    def _confirm_selection(self):
        """Confirm the current selection and proceed with results."""
        if self.selected_cluster is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", 
                "Please select a cluster first."
            )
            return
        
        # Call callback with the user-selected cluster
        if self.callback:
            self.callback(self.selected_cluster, self.selected_index)
        
        # Close the dialog
        self.accept()
        
        # Results dialogs are shown by the normal application workflow.
        # The callback will handle the analysis completion and result display
        # through the normal workflow, so we don't need to explicitly call show_results here
        # The app controller will automatically show results after cluster selection
    
    def _auto_select_and_close(self):
        """Auto-select best cluster and close"""
        _LOGGER.info("🤖 Dialog closed - automatically using best cluster")
        
        try:
            if self.automatic_best and self.callback:
                # Find index of automatic best
                auto_index = self._find_automatic_best_index()
                self.callback(self.automatic_best, auto_index)
            elif self.all_candidates and self.callback:
                # Fallback: use first cluster if no automatic best
                _LOGGER.info("No automatic best found, using first cluster")
                self.callback(self.all_candidates[0], 0)
            else:
                _LOGGER.warning("No clusters or callback available for automatic selection")
        except Exception as e:
            _LOGGER.error(f"Error in automatic cluster selection: {e}")
        
        self.reject()
    
    def closeEvent(self, event):
        """Handle window close event"""
        self._auto_select_and_close()
        event.accept()


_NONMODAL_DIALOGS = []


def show_cluster_selection_dialog(parent, clusters, snid_result=None, callback=None, *, modal: bool = True, show_without_activating: bool = False):
    """
    Show the cluster selection dialog.
    
    Args:
        parent: Parent window
        clusters: List of cluster candidates
        snid_result: Full SNID analysis result (for spectrum access)
        callback: Callback function for cluster selection
        modal: If True (default), run as a modal dialog via exec().
               If False, show() non-modally (important to avoid blocking the game window).
        show_without_activating: If True and modal=False, request the OS/Qt not to activate
               the dialog when shown (prevents brief focus-steal when the game is on top).
        
    Returns:
        Tuple of (selected_cluster, selected_index) or (None, -1) if cancelled
        Note: If callback is provided, it will be called immediately and this may return None
    """
    dialog = PySide6ClusterSelectionDialog(parent, clusters, snid_result, callback)

    # Non-modal mode (used when the mini-game is running): do not block the Qt event loop.
    if not modal:
        try:
            dialog.setModal(False)
            dialog.setWindowModality(QtCore.Qt.NonModal)
            dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
            if show_without_activating:
                dialog.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        except Exception:
            pass

        # Keep a reference so it isn't GC'd immediately.
        _NONMODAL_DIALOGS.append(dialog)
        try:
            dialog.destroyed.connect(lambda *_: _NONMODAL_DIALOGS.remove(dialog) if dialog in _NONMODAL_DIALOGS else None)
        except Exception:
            pass

        dialog.show()
        return None, -1
    
    # Modal mode (default): callback will be called automatically
    result = dialog.exec()
    
    # If no callback was provided, return the result for backward compatibility
    if callback is None:
        if result == QtWidgets.QDialog.Accepted:
            return dialog.get_result()
        else:
            # Return automatic best if available
            if dialog.automatic_best and clusters:
                auto_index = clusters.index(dialog.automatic_best) if dialog.automatic_best in clusters else 0
                return dialog.automatic_best, auto_index
            return None, -1
    else:
        # Callback was used, return None to indicate async handling
        return None, -1 