"""
SNID SAGE - Subtype Proportions Plot Dialog - PySide6 Version
============================================================

Interactive subtype proportions visualization dialog for SNID analysis results.
Displays pie charts and statistics for SN subtype distribution within clusters.

Features:
- Interactive matplotlib pie chart with subtype proportions
- Cluster-aware data selection (user-selected > winning > best matches)
- Detailed statistics table with quality metrics
- Multi-panel layout with pie chart, statistics, and threshold analysis
- Export functionality for plots and data
- Modern Qt styling
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# Matplotlib for plotting (Qt helper)
try:
    from snid_sage.interfaces.gui.utils.matplotlib_qt import get_qt_mpl
    plt, Figure, FigureCanvas, _NavigationToolbar = get_qt_mpl()
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FigureCanvas = None
    Figure = None

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_subtype_proportions')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_subtype_proportions')

# Enhanced dialog button styling
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except Exception:
    ENHANCED_BUTTONS_AVAILABLE = False
try:
    from snid_sage.shared.utils.math_utils import get_best_metric_value
    MATH_UTILS_AVAILABLE = True
except ImportError:
    MATH_UTILS_AVAILABLE = False


class PySide6SubtypeProportionsDialog(QtWidgets.QDialog):
    """
    Interactive subtype proportions visualization dialog for SNID analysis results.
    
    This dialog provides:
    - Interactive matplotlib pie chart with subtype distribution
    - Cluster-aware data selection prioritizing user selection
    - Detailed statistics table with quality metrics
    - Metric-threshold analysis (best metric; HσLAP-CCC preferred)
    - Export functionality for plots and data
    """
    
    def __init__(self, parent=None, analysis_results=None):
        """
        Initialize subtype proportions dialog
        
        Args:
            parent: Parent widget
            analysis_results: SNID analysis results object
        """
        super().__init__(parent)
        
        # Store input data
        self.analysis_results = analysis_results
        self.all_matches = []
        self.cluster_matches = []
        self.cluster_type = "Unknown"
        self.match_source = ""
        
        # UI components
        self.info_text = None
        self.plot_canvas = None
        self.stats_table = None
        self.figure = None
        self.axes = []  # Multiple subplots
        
        # Subtype color mapping for consistency (custom palette)
        try:
            from snid_sage.snid.plotting import get_custom_color_palette
            custom_palette = get_custom_color_palette()
            self.custom_palette = custom_palette
        except ImportError:
            # Fallback colors if import fails
            self.custom_palette = [
                "#FF6361",  # coral
                "#BC5090",  # magenta
                "#58508D",  # purple
                "#003F5C",  # deep blue
                "#FFA600",  # amber
                "#B0B0B0",  # neutral grey
                "#912F40",  # cranberry
                "#5A6650",  # Muted Moss
                "#8C6D5C",  # Clay Taupe
                "#48788D",  # Dusty Blue
                "#9B5E4A",  # Muted Sienna
                "#6E4E6F",  # Smoky Plum
            ]
        
        # Keep basic subtype mapping for fallback
        self.subtype_colors = {
            'Unknown': '#A9A9A9',    # Gray
            '': '#CCCCCC'            # Light gray for empty
        }
        
        # Setup dialog
        self._setup_dialog()
        self._create_interface()
        self._extract_cluster_data()
        self._populate_dialog()
        
    def _setup_dialog(self):
        """Setup dialog properties"""
        self.setWindowTitle("Subtype Proportions Analysis")
        self.setModal(True)
        self.resize(1200, 800)
        
        # Set window icon using centralized logo manager (works in dev and installed package)
        try:
            from snid_sage.interfaces.ui_core.logo import get_logo_manager
            icon_path = get_logo_manager().get_icon_path()
            if icon_path:
                self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        except Exception:
            pass
    
    def _create_interface(self):
        """Create the dialog interface"""
        # Main layout
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Left panel for plots
        self._create_plot_panel(main_layout)
        
        # Right panel for controls and info
        self._create_info_panel(main_layout)
    
    def _create_plot_panel(self, main_layout):
        """Create plot panel with matplotlib"""
        plot_group = QtWidgets.QGroupBox("Subtype Distribution Analysis")
        plot_layout = QtWidgets.QVBoxLayout(plot_group)
        
        if MATPLOTLIB_AVAILABLE:
            # Create matplotlib figure with multiple subplots
            self.figure = Figure(figsize=(10, 8), dpi=100, facecolor='white')
            
            # Create subplot grid: 2x2 layout
            # Top: pie chart (left) and statistics bar chart (right)
            # Bottom: metric threshold analysis (spanning both columns)
            self.figure.clear()
            
            # Embed in Qt widget
            self.plot_canvas = FigureCanvas(self.figure)
            self.plot_canvas.setParent(self)
            plot_layout.addWidget(self.plot_canvas)
            
        else:
            # Fallback message
            fallback_label = QtWidgets.QLabel(
                "📊 Matplotlib Required for Plotting\n\n"
                "Install Matplotlib to view subtype proportion plots:\n\n"
                "pip install matplotlib\n\n"
                "Analysis data will still be available in the summary."
            )
            fallback_label.setAlignment(QtCore.Qt.AlignCenter)
            fallback_label.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12pt;")
            fallback_label.setWordWrap(True)
            plot_layout.addWidget(fallback_label)
        
        main_layout.addWidget(plot_group, 2)  # 2/3 of width
    
    def _create_info_panel(self, main_layout):
        """Create information and statistics panel"""
        info_group = QtWidgets.QGroupBox("Cluster Summary & Statistics")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        # Summary text area
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(300)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        info_layout.addWidget(self.info_text)
        
        # Statistics table
        stats_label = QtWidgets.QLabel("Subtype Details:")
        stats_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        info_layout.addWidget(stats_label)
        
        self.stats_table = QtWidgets.QTableWidget()
        self.stats_table.setColumnCount(5)
        self.stats_table.setHorizontalHeaderLabels([
            "Subtype", "Count", "Percentage", "Avg metric", "Avg Redshift"
        ])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setAlternatingRowColors(False)
        self.stats_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        info_layout.addWidget(self.stats_table)
        
        # Bottom buttons
        self._create_bottom_buttons(info_layout)
        
        main_layout.addWidget(info_group, 1)  # 1/3 of width
    
    def _create_bottom_buttons(self, layout):
        """Create bottom button panel"""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Export plot button
        export_plot_btn = QtWidgets.QPushButton("Export Plot")
        export_plot_btn.setObjectName("export_plot_btn")
        export_plot_btn.clicked.connect(self._export_plot)
        button_layout.addWidget(export_plot_btn)
        
        # Export data button
        export_data_btn = QtWidgets.QPushButton("Export Data")
        export_data_btn.setObjectName("export_data_btn")
        export_data_btn.clicked.connect(self._export_data)
        button_layout.addWidget(export_data_btn)
        
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
                self.button_manager = enhance_dialog_with_preset(self, 'subtype_proportions_dialog')
        except Exception as e:
            _LOGGER.warning(f"Failed to apply enhanced button styling: {e}")
    
    def _extract_cluster_data(self):
        """Extract cluster data from analysis results"""
        try:
            if not self.analysis_results or not hasattr(self.analysis_results, 'success'):
                return
            
            if not self.analysis_results.success:
                return
            
            # Extract cluster matches following the same priority as the original plotting function
            cluster_matches = []
            cluster_type = "Unknown"
            match_source = ""
            
            # First priority: User-selected cluster
            selected_cluster = None
            if (hasattr(self.analysis_results, 'clustering_results') and 
                self.analysis_results.clustering_results and 
                'user_selected_cluster' in self.analysis_results.clustering_results and 
                self.analysis_results.clustering_results['user_selected_cluster']):
                
                selected_cluster = self.analysis_results.clustering_results['user_selected_cluster']
                if 'matches' in selected_cluster and selected_cluster['matches']:
                    cluster_matches = selected_cluster['matches']
                    cluster_type = selected_cluster.get('type', 'Unknown')
                    match_source = f"user-selected cluster ({cluster_type})"
            
            # Second priority: Winning cluster (filtered_matches)
            if not cluster_matches and hasattr(self.analysis_results, 'filtered_matches') and self.analysis_results.filtered_matches:
                cluster_matches = self.analysis_results.filtered_matches
                # Try to get type from first match
                if cluster_matches:
                    first_match = cluster_matches[0]
                    cluster_type = first_match.get('type', 'Unknown')
                match_source = "winning cluster"
            
            # Third priority: All best matches
            if not cluster_matches and hasattr(self.analysis_results, 'best_matches') and self.analysis_results.best_matches:
                cluster_matches = self.analysis_results.best_matches
                if cluster_matches:
                    first_match = cluster_matches[0]
                    cluster_type = first_match.get('type', 'Unknown')
                match_source = "best matches"
            
            self.cluster_matches = cluster_matches
            self.cluster_type = cluster_type
            self.match_source = match_source
            self.selected_cluster = selected_cluster
            
            _LOGGER.info(f"Extracted {len(cluster_matches)} cluster matches from {match_source}")
            
        except Exception as e:
            _LOGGER.error(f"Error extracting cluster data: {e}")
            self.cluster_matches = []
    
    def _populate_dialog(self):
        """Populate the dialog with data"""
        try:
            self._populate_summary()
            self._populate_statistics_table()
            
            if MATPLOTLIB_AVAILABLE and self.figure:
                self._create_plots()
            
        except Exception as e:
            _LOGGER.error(f"Error populating dialog: {e}")
            self._show_error(f"Error displaying subtype proportions: {str(e)}")
    
    def _populate_summary(self):
        """Populate the summary text"""
        if not self.analysis_results or not self.analysis_results.success:
            error_text = """
Subtype Proportions Analysis Failed

Analysis results are not available or the analysis was not successful.
Please run a successful SNID analysis first.
            """.strip()
            self.info_text.setPlainText(error_text)
            return
        
        if not self.cluster_matches:
            error_text = """
⚠️ No Cluster Matches Available

No cluster matches found for subtype analysis.
This may be due to:
• No clustering results available
• Empty cluster selection
• Analysis configuration issues

Please check your analysis results and try again.
            """.strip()
            self.info_text.setPlainText(error_text)
            return
        
        # Calculate subtype proportions
        subtype_counts = defaultdict(int)
        subtype_metric_values = defaultdict(list)
        subtype_redshifts = defaultdict(list)
        
        for match in self.cluster_matches:
            template = match.get('template', {})
            subtype = template.get('subtype', 'Unknown')
            if not subtype or subtype.strip() == '':
                subtype = 'Unknown'
            
            subtype_counts[subtype] += 1
            if MATH_UTILS_AVAILABLE:
                try:
                    subtype_metric_values[subtype].append(float(get_best_metric_value(match)))
                except Exception:
                    subtype_metric_values[subtype].append(float(match.get('hlap', 0.0) or 0.0))
            else:
                subtype_metric_values[subtype].append(float(match.get('hlap', 0.0) or 0.0))
            subtype_redshifts[subtype].append(match.get('redshift', 0))
        
        # Build summary text
        total_matches = len(self.cluster_matches)
        num_subtypes = len(subtype_counts)
        
        # Get winning subtype
        winning_subtype = max(subtype_counts.items(), key=lambda x: x[1])[0] if subtype_counts else "Unknown"
        winning_count = subtype_counts[winning_subtype] if winning_subtype in subtype_counts else 0
        winning_percentage = (winning_count / total_matches * 100) if total_matches > 0 else 0
        
        lines = [
            "🍰 SUBTYPE PROPORTIONS ANALYSIS",
            "=" * 40,
            "",
            f"📊 DATA SOURCE: {self.match_source}",
            f"🎯 CLUSTER TYPE: {self.cluster_type}",
            f"📝 TOTAL MATCHES: {total_matches}",
            f"🔍 UNIQUE SUBTYPES: {num_subtypes}",
            "",
            f"🏆 WINNING SUBTYPE: {winning_subtype}",
            f"   Count: {winning_count} matches ({winning_percentage:.1f}%)",
            "",
            "🍰 SUBTYPE DISTRIBUTION:",
        ]
        
        # Sort subtypes by count (descending)
        sorted_subtypes = sorted(subtype_counts.items(), key=lambda x: x[1], reverse=True)
        for subtype, count in sorted_subtypes:
            percentage = (count / total_matches) * 100
            avg_metric = np.mean(subtype_metric_values[subtype]) if subtype_metric_values[subtype] else 0
            lines.append(f"   {subtype}: {count} matches ({percentage:.1f}%) - Avg metric: {avg_metric:.2f}")
        
        lines.extend([
            "",
            "📏 QUALITY METRICS:",
            f"   Metric Range: {min([min(vs) for vs in subtype_metric_values.values() if vs]):.2f} - {max([max(vs) for vs in subtype_metric_values.values() if vs]):.2f}",
            f"   Redshift Range: {min([min(zs) for zs in subtype_redshifts.values() if zs]):.4f} - {max([max(zs) for zs in subtype_redshifts.values() if zs]):.4f}",
        ])
        
        summary_text = "\n".join(lines)
        self.info_text.setPlainText(summary_text)
    
    def _populate_statistics_table(self):
        """Populate the statistics table"""
        if not self.cluster_matches:
            self.stats_table.setRowCount(0)
            return
        
        # Calculate statistics by subtype
        subtype_stats = defaultdict(lambda: {'count': 0, 'metric_values': [], 'redshifts': []})
        total_matches = len(self.cluster_matches)
        
        for match in self.cluster_matches:
            template = match.get('template', {})
            subtype = template.get('subtype', 'Unknown')
            if not subtype or subtype.strip() == '':
                subtype = 'Unknown'
            
            subtype_stats[subtype]['count'] += 1
            if MATH_UTILS_AVAILABLE:
                try:
                    subtype_stats[subtype]['metric_values'].append(float(get_best_metric_value(match)))
                except Exception:
                    subtype_stats[subtype]['metric_values'].append(float(match.get('hlap', 0.0) or 0.0))
            else:
                subtype_stats[subtype]['metric_values'].append(float(match.get('hlap', 0.0) or 0.0))
            subtype_stats[subtype]['redshifts'].append(match.get('redshift', 0))
        
        # Sort by count (descending)
        sorted_subtypes = sorted(subtype_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        
        # Populate table
        self.stats_table.setRowCount(len(sorted_subtypes))
        
        for row, (subtype, stats) in enumerate(sorted_subtypes):
            # Subtype name
            subtype_item = QtWidgets.QTableWidgetItem(subtype)
            color = self.subtype_colors.get(subtype, self.subtype_colors['Unknown'])
            subtype_item.setBackground(QtGui.QColor(color))
            subtype_item.setForeground(QtGui.QColor('white'))
            self.stats_table.setItem(row, 0, subtype_item)
            
            # Count
            count_item = QtWidgets.QTableWidgetItem(str(stats['count']))
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 1, count_item)
            
            # Percentage
            percentage = (stats['count'] / total_matches) * 100
            percent_item = QtWidgets.QTableWidgetItem(f"{percentage:.1f}%")
            percent_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 2, percent_item)
            
            # Average metric
            avg_metric = np.mean(stats['metric_values']) if stats['metric_values'] else 0
            metric_item = QtWidgets.QTableWidgetItem(f"{avg_metric:.2f}")
            metric_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 3, metric_item)
            
            # Average redshift
            avg_z = np.mean(stats['redshifts']) if stats['redshifts'] else 0
            z_item = QtWidgets.QTableWidgetItem(f"{avg_z:.4f}")
            z_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 4, z_item)
        
        # Resize columns to content
        self.stats_table.resizeColumnsToContents()
    
    def _create_plots(self):
        """Create the subtype proportion plots"""
        if not self.cluster_matches or not self.figure:
            return
        
        try:
            # Clear figure
            self.figure.clear()
            
            # Create subplot grid - smaller pie chart on left, table on right, threshold analysis below
            gs = self.figure.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[1, 1])
            
            # Top left: Smaller pie chart
            ax1 = self.figure.add_subplot(gs[0, 0])
            # Top right: Statistics table (will be text-based)
            ax2 = self.figure.add_subplot(gs[0, 1])
            # Bottom: metric threshold analysis (spanning both columns)
            ax3 = self.figure.add_subplot(gs[1, :])
            
            self.axes = [ax1, ax2, ax3]
            
            # Calculate subtype data
            subtype_counts = defaultdict(int)
            subtype_metric_values = defaultdict(list)
            subtype_redshifts = defaultdict(list)
            
            for match in self.cluster_matches:
                template = match.get('template', {})
                subtype = template.get('subtype', 'Unknown')
                if not subtype or subtype.strip() == '':
                    subtype = 'Unknown'
                
                subtype_counts[subtype] += 1
                if MATH_UTILS_AVAILABLE:
                    try:
                        subtype_metric_values[subtype].append(float(get_best_metric_value(match)))
                    except Exception:
                        subtype_metric_values[subtype].append(float(match.get('hlap', 0.0) or 0.0))
                else:
                    subtype_metric_values[subtype].append(float(match.get('hlap', 0.0) or 0.0))
                subtype_redshifts[subtype].append(match.get('redshift', 0))
            
            if not subtype_counts:
                for ax in self.axes:
                    ax.text(0.5, 0.5, "No subtype data available", 
                           ha='center', va='center', transform=ax.transAxes)
                    ax.axis('off')
                self.plot_canvas.draw()
                return
            
            # Plot 1: Smaller pie chart
            self._create_pie_chart(ax1, subtype_counts)
            
            # Plot 2: Statistics table
            self._create_statistics_table(ax2, subtype_counts, subtype_metric_values, subtype_redshifts)
            
            # Plot 3: metric threshold analysis
            self._create_threshold_analysis(ax3, subtype_metric_values)
            
            # Adjust layout
            self.figure.tight_layout()
            
            # Refresh canvas
            self.plot_canvas.draw()
            
            _LOGGER.info(f"Created subtype proportion plots with {len(subtype_counts)} subtypes")
            
        except Exception as e:
            _LOGGER.error(f"Error creating plots: {e}")
            if self.axes:
                self.axes[0].text(0.5, 0.5, f"Error creating plots:\n{str(e)}", 
                                ha='center', va='center', transform=self.axes[0].transAxes,
                                fontsize=12, color='red')
            self.plot_canvas.draw()
    
    def _create_pie_chart(self, ax, subtype_counts):
        """Create pie chart of subtype proportions"""
        # Sort by count (descending)
        sorted_subtypes = sorted(subtype_counts.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_subtypes]
        values = [item[1] for item in sorted_subtypes]
        
        # Create colors using custom palette
        colors = []
        for i, label in enumerate(labels):
            if label in self.subtype_colors:
                colors.append(self.subtype_colors[label])
            else:
                colors.append(self.custom_palette[i % len(self.custom_palette)])
        
        # Create explode parameter - explode the winning subtype based on result.best_subtype (like CLI)
        winning_subtype = None
        if (hasattr(self.analysis_results, 'best_subtype') and 
            self.analysis_results.best_subtype):
            winning_subtype = self.analysis_results.best_subtype
            
        explode = []
        for i, label in enumerate(labels):
            if winning_subtype and label == winning_subtype:
                explode.append(0.1)  # Explode the winning subtype
            else:
                explode.append(0)    # Keep other subtypes normal
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            values, 
            labels=labels,
            autopct='%1.1f%%',
            colors=colors,
            explode=explode,
            startangle=90,
            textprops={'fontsize': 10}
        )
        
        # Style winning slice - match CLI by highlighting the winning subtype
        for i, (wedge, label) in enumerate(zip(wedges, labels)):
            if winning_subtype and label == winning_subtype:
                wedge.set_edgecolor('black')
                wedge.set_linewidth(2)
            else:
                wedge.set_edgecolor('white')
                wedge.set_linewidth(1)
        
        ax.set_title(f'Subtype Distribution\n{self.cluster_type} Cluster', 
                    fontsize=12, fontweight='bold', pad=15)
    

    
    def _create_threshold_analysis(self, ax, subtype_metric_values):
        """Create metric threshold analysis plot showing proportions."""
        if not subtype_metric_values or not self.cluster_matches:
            ax.text(0.5, 0.5, "No metric data available", 
                   ha='center', va='center', transform=ax.transAxes)
            ax.axis('off')
            return
        
        # Find metric range from all cluster matches
        try:
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            all_metrics = [float(get_best_metric_value(m)) for m in self.cluster_matches]
        except Exception:
            all_metrics = [float(m.get('hlap', 0.0) or 0.0) for m in self.cluster_matches]
        
        all_metrics = [m for m in all_metrics if np.isfinite(m)]
        
        if not all_metrics:
            ax.text(0.5, 0.5, "No valid metric values", 
                   ha='center', va='center', transform=ax.transAxes)
            ax.axis('off')
            return
        
        # Create metric thresholds
        min_metric = min(all_metrics)
        max_metric = max(all_metrics)
        thresholds = np.linspace(min_metric, max_metric, 15) if max_metric > min_metric else np.array([min_metric])
        
        # Get sorted subtypes for consistent color assignment
        sorted_subtypes = sorted(subtype_metric_values.keys())
        subtype_color_map = {}
        for i, subtype in enumerate(sorted_subtypes):
            if subtype in self.subtype_colors:
                subtype_color_map[subtype] = self.subtype_colors[subtype]
            else:
                subtype_color_map[subtype] = self.custom_palette[i % len(self.custom_palette)]
        
        # Calculate proportions at each threshold
        subtype_proportions_by_threshold = {subtype: [] for subtype in sorted_subtypes}
        
        for threshold in thresholds:
            # Get all matches above this threshold
            try:
                from snid_sage.shared.utils.math_utils import get_best_metric_value
                qualified_matches = [match for match in self.cluster_matches if get_best_metric_value(match) >= threshold]
            except Exception:
                qualified_matches = [match for match in self.cluster_matches if (match.get('hlap', 0.0) or 0.0) >= threshold]
            
            if qualified_matches:
                # Count subtypes in qualified matches
                threshold_subtype_counts = defaultdict(int)
                for match in qualified_matches:
                    template = match.get('template', {})
                    subtype = template.get('subtype', 'Unknown')
                    if not subtype or subtype.strip() == '':
                        subtype = 'Unknown'
                    threshold_subtype_counts[subtype] += 1
                
                # Calculate proportions
                total_qualified = len(qualified_matches)
                for subtype in sorted_subtypes:
                    proportion = threshold_subtype_counts[subtype] / total_qualified if total_qualified > 0 else 0
                    subtype_proportions_by_threshold[subtype].append(proportion)
            else:
                # No matches above threshold
                for subtype in sorted_subtypes:
                    subtype_proportions_by_threshold[subtype].append(0)
        
        # Plot lines for each subtype that has non-zero proportions
        plotted_any = False
        for subtype, proportions in subtype_proportions_by_threshold.items():
            if any(p > 0 for p in proportions):  # Only plot if subtype has non-zero proportions
                color = subtype_color_map[subtype]
                ax.plot(thresholds, proportions, 'o-', label=subtype, 
                       color=color, linewidth=2, markersize=5)
                plotted_any = True
        
        if plotted_any:
            # Get the actual metric name from the matches
            metric_name = "HLAP"
            if self.cluster_matches:
                try:
                    from snid_sage.shared.utils.math_utils import get_best_metric_name
                    metric_name = get_best_metric_name(self.cluster_matches[0])
                except Exception:
                    pass
            ax.set_title(f'Subtype Proportions vs {metric_name} Threshold', fontsize=12, fontweight='bold', pad=15)
            ax.set_xlabel(f'{metric_name} Threshold', fontsize=10, fontweight='bold')
            ax.set_ylabel('Subtype Proportion', fontsize=10, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=9, loc='upper right')
            ax.set_ylim(-0.05, 1.05)  # Set y-axis limits
            
        else:
            ax.text(0.5, 0.5, "Insufficient subtype diversity\nfor threshold analysis", 
                   ha='center', va='center', transform=ax.transAxes)
            ax.axis('off')
    
    def _create_statistics_table(self, ax, subtype_counts, subtype_metric_values, subtype_redshifts):
        """Create a text-based statistics table on the right side of the plot."""
        ax.axis('off')  # Hide the axis
        
        # Calculate statistics
        total_matches = len(self.cluster_matches)
        if total_matches == 0:
            ax.text(0.5, 0.5, "No data to display.", ha='center', va='center', 
                   transform=ax.transAxes, fontsize=10)
            return
        
        # Create table data
        table_data = []
        headers = ['Subtype', 'Count', '%', 'Avg metric', 'Avg Z']
        
        # Sort subtypes by count (descending)
        sorted_subtypes = sorted(subtype_counts.items(), key=lambda x: x[1], reverse=True)
        
        for subtype, count in sorted_subtypes:
            percentage = (count / total_matches) * 100
            avg_metric = np.mean(subtype_metric_values[subtype]) if subtype_metric_values[subtype] else 0
            avg_z = np.mean(subtype_redshifts[subtype]) if subtype_redshifts[subtype] else 0
            
            table_data.append([
                subtype,
                str(count),
                f"{percentage:.1f}%",
                f"{avg_metric:.2f}",
                f"{avg_z:.4f}"
            ])
        
        # Create formatted table text
        col_widths = [12, 6, 8, 10, 10]  # Column widths
        
        # Format header
        header_text = ""
        for i, header in enumerate(headers):
            header_text += f"{header:<{col_widths[i]}}"
        header_text += "\n" + "-" * sum(col_widths) + "\n"
        
        # Format data rows
        table_text = header_text
        for row in table_data:
            row_text = ""
            for i, cell in enumerate(row):
                row_text += f"{cell:<{col_widths[i]}}"
            table_text += row_text + "\n"
        
        # Display the table
        ax.text(0.02, 0.98, "Subtype Statistics", ha='left', va='top', 
               transform=ax.transAxes, fontsize=11, fontweight='bold')
        ax.text(0.02, 0.85, table_text, ha='left', va='top', 
               transform=ax.transAxes, fontsize=8, fontfamily='monospace')

    def _export_plot(self):
        """Export the plot to image file"""
        if not MATPLOTLIB_AVAILABLE or not self.figure:
            QtWidgets.QMessageBox.warning(
                self, "Export Error", 
                "Matplotlib not available for plot export."
            )
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Subtype Proportions Plot",
            "subtype_proportions_plot.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                QtWidgets.QMessageBox.information(
                    self, "Export Successful", 
                    f"Plot exported to:\n{file_path}"
                )
                _LOGGER.info(f"Plot exported to {file_path}")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", 
                    f"Failed to export plot:\n{str(e)}"
                )
    
    def _export_data(self):
        """Export the subtype data to CSV file"""
        if not self.cluster_matches:
            QtWidgets.QMessageBox.warning(
                self, "Export Error", 
                "No data available to export."
            )
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Subtype Proportions Data",
            "subtype_proportions_data.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                import csv
                
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'Template_Name', 'Type', 'Subtype', 'Redshift', 
                        'Age_days', 'Metric', 'LAP'
                    ])
                    
                    # Write data
                    for match in self.cluster_matches:
                        template = match.get('template', {})
                        writer.writerow([
                            template.get('name', 'Unknown'),
                            match.get('type', 'Unknown'),
                            template.get('subtype', 'Unknown'),
                            match.get('redshift', 0),
                            template.get('age', 0),
                            (float(get_best_metric_value(match)) if MATH_UTILS_AVAILABLE else float(match.get('hlap', 0.0) or 0.0)),
                            match.get('lap', 0)
                        ])
                
                QtWidgets.QMessageBox.information(
                    self, "Export Successful", 
                    f"Data exported to:\n{file_path}"
                )
                _LOGGER.info(f"Data exported to {file_path}")
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", 
                    f"Failed to export data:\n{str(e)}"
                )
    
    def _show_error(self, error_msg):
        """Show error message in info text"""
        error_text = f"""
Error Loading Subtype Proportions Data

{error_msg}

Please try running the analysis again or check the logs for more details.
        """.strip()
        
        self.info_text.setPlainText(error_text)


def show_subtype_proportions_dialog(parent=None, analysis_results=None):
    """
    Show the subtype proportions dialog.
    
    Args:
        parent: Parent window
        analysis_results: SNID analysis results object
        
    Returns:
        PySide6SubtypeProportionsDialog instance
    """
    dialog = PySide6SubtypeProportionsDialog(parent, analysis_results)
    dialog.show()
    return dialog 