"""
SNID SAGE - Redshift vs Age Plot Dialog - PySide6 Version
========================================================

Interactive redshift vs age visualization dialog for SNID analysis results.
Displays template ages vs redshift with different SN types in different colors.

Features:
- Interactive matplotlib plot with type-based coloring
- Cluster-aware data selection (user-selected > winning > best matches)
- HLAP/metric threshold filtering
- Detailed statistics and export functionality
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
    _LOGGER = get_logger('gui.pyside6_redshift_age')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_redshift_age')

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


class PySide6RedshiftAgeDialog(QtWidgets.QDialog):
    """
    Interactive redshift vs age visualization dialog for SNID analysis results.
    
    This dialog provides:
    - Interactive matplotlib plot with type-based coloring  
    - Cluster-aware data selection prioritizing user selection
    - Metric threshold filtering for quality control
    - Detailed statistics and export functionality
    """
    
    def __init__(self, parent=None, analysis_results=None):
        """
        Initialize redshift vs age dialog
        
        Args:
            parent: Parent widget
            analysis_results: SNID analysis results object
        """
        super().__init__(parent)
        
        # Store input data
        self.analysis_results = analysis_results
        self.all_matches = []
        self.plot_data = []
        
        # UI components
        self.info_text = None
        self.plot_canvas = None
        self.stats_table = None
        self.figure = None
        self.ax = None
        
        # Type color mapping for consistency
        self.type_colors = {
            'Ia': '#FF6B6B',      # Red
            'Ib': '#4ECDC4',      # Teal  
            'Ic': '#45B7D1',      # Blue
            'II': '#96CEB4',      # Green
            'IIn': '#FFEAA7',     # Yellow
            'IIP': '#DDA0DD',     # Plum
            'Galaxy': '#8A2BE2',  # Blue-violet
            'Star': '#FFD700',    # Gold
            'AGN': '#FF6347',     # Tomato
            'SLSN': '#00CED1',    # Dark turquoise
            'Unknown': '#A9A9A9'  # Gray
        }
        
        # Setup dialog
        self._setup_dialog()
        self._create_interface()
        self._extract_plot_data()
        self._populate_dialog()
        
    def _setup_dialog(self):
        """Setup dialog properties"""
        self.setWindowTitle("Redshift vs Age Analysis")
        self.setModal(True)
        self.resize(1000, 700)
        
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
        
        # Left panel for plot
        self._create_plot_panel(main_layout)
        
        # Right panel for controls and info
        self._create_info_panel(main_layout)
        
        # Bottom buttons
        self._create_bottom_buttons(main_layout)
    
    def _create_plot_panel(self, main_layout):
        """Create plot panel with matplotlib"""
        plot_group = QtWidgets.QGroupBox("Redshift vs Age Distribution")
        plot_layout = QtWidgets.QVBoxLayout(plot_group)
        
        if MATPLOTLIB_AVAILABLE:
            # Create matplotlib figure
            self.figure = Figure(figsize=(8, 6), dpi=100, facecolor='white')
            self.ax = self.figure.add_subplot(111)
            
            # Embed in Qt widget
            self.plot_canvas = FigureCanvas(self.figure)
            self.plot_canvas.setParent(self)
            plot_layout.addWidget(self.plot_canvas)
            
        else:
            # Fallback message
            fallback_label = QtWidgets.QLabel(
                "📊 Matplotlib Required for Plotting\n\n"
                "Install Matplotlib to view redshift vs age plots:\n\n"
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
        info_group = QtWidgets.QGroupBox("Analysis Summary & Statistics")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        # Summary text area
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
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
        stats_label = QtWidgets.QLabel("Type Distribution Statistics:")
        stats_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        info_layout.addWidget(stats_label)
        
        self.stats_table = QtWidgets.QTableWidget()
        self.stats_table.setColumnCount(4)
        self.stats_table.setHorizontalHeaderLabels([
            "Type", "Count", "Avg Redshift", "Avg Age (days)"
        ])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setAlternatingRowColors(False)
        self.stats_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        info_layout.addWidget(self.stats_table)
        
        main_layout.addWidget(info_group, 1)  # 1/3 of width
    
    def _create_bottom_buttons(self, layout):
        """Create bottom button panel"""
        # Buttons added to the right panel instead of bottom
        # to maintain the two-column layout
        
        # Add export and close buttons to info panel
        info_group = layout.itemAt(1).widget()  # Get the info group
        info_layout = info_group.layout()
        
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
        
        info_layout.addLayout(button_layout)

        # Apply enhanced styles
        try:
            if ENHANCED_BUTTONS_AVAILABLE:
                self.button_manager = enhance_dialog_with_preset(self, 'redshift_age_dialog')
        except Exception as e:
            _LOGGER.warning(f"Failed to apply enhanced button styling: {e}")
    
    def _extract_plot_data(self):
        """Extract plot data from analysis results"""
        try:
            if not self.analysis_results or not hasattr(self.analysis_results, 'success'):
                return
            
            if not self.analysis_results.success:
                return
            
            # Extract matches following the same priority as the original plotting function
            matches = []
            match_source = ""
            
            # First priority: User-selected cluster
            if (hasattr(self.analysis_results, 'clustering_results') and 
                self.analysis_results.clustering_results and 
                'user_selected_cluster' in self.analysis_results.clustering_results and 
                self.analysis_results.clustering_results['user_selected_cluster']):
                
                user_cluster = self.analysis_results.clustering_results['user_selected_cluster']
                if 'matches' in user_cluster and user_cluster['matches']:
                    matches = user_cluster['matches']
                    cluster_type = user_cluster.get('type', 'Unknown')
                    match_source = f"user-selected cluster ({cluster_type})"
            
            # Second priority: Winning cluster (filtered_matches)
            if not matches and hasattr(self.analysis_results, 'filtered_matches') and self.analysis_results.filtered_matches:
                matches = self.analysis_results.filtered_matches
                match_source = "winning cluster"
            
            # Third priority: All best matches
            if not matches and hasattr(self.analysis_results, 'best_matches') and self.analysis_results.best_matches:
                matches = self.analysis_results.best_matches
                match_source = "best matches"
            
            self.all_matches = matches
            self.match_source = match_source
            
            # Apply best-metric threshold filtering only if clustering did not succeed
            clustering_ok = bool(getattr(self.analysis_results, 'clustering_results', None)) and bool(getattr(self.analysis_results, 'clustering_results', {}).get('success', False))
            if not clustering_ok:
                try:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    threshold = float(getattr(self.analysis_results, 'hsigma_lap_ccc_threshold', 1.5))
                    filtered_matches = [m for m in matches if float(get_best_metric_value(m)) >= threshold]
                except Exception:
                    filtered_matches = matches
            else:
                filtered_matches = matches
            
            # Extract plot data
            self.plot_data = []
            for i, match in enumerate(filtered_matches):
                if not isinstance(match, dict):
                    continue
                
                # Extract key data
                z = match.get('redshift', None)
                age = match.get('age', None)
                sn_type = match.get('type', 'Unknown')
                template = match.get('template', {})
                sn_subtype = template.get('subtype', '') if isinstance(template, dict) else ''
                name = template.get('name', f'Template {i}') if isinstance(template, dict) else f'Template {i}'
                from snid_sage.shared.utils.math_utils import get_best_metric_value
                metric = float(get_best_metric_value(match))
                
                # Filter out invalid data
                if z is None or age is None:
                    continue
                
                # Create plot data point
                plot_point = {
                    'redshift': float(z),
                    'age': float(age),
                    'type': sn_type,
                    'subtype': sn_subtype,
                    'name': name,
                    'metric': float(metric),
                    'color': self.type_colors.get(sn_type, self.type_colors['Unknown'])
                }
                
                self.plot_data.append(plot_point)
            
            _LOGGER.info(f"Extracted {len(self.plot_data)} data points from {match_source}")
            
        except Exception as e:
            _LOGGER.error(f"Error extracting plot data: {e}")
            self.plot_data = []
    
    def _populate_dialog(self):
        """Populate the dialog with data"""
        try:
            self._populate_summary()
            self._populate_statistics_table()
            
            if MATPLOTLIB_AVAILABLE and self.ax:
                self._create_plot()
            
        except Exception as e:
            _LOGGER.error(f"Error populating dialog: {e}")
            self._show_error(f"Error displaying redshift vs age data: {str(e)}")
    
    def _populate_summary(self):
        """Populate the summary text"""
        if not self.analysis_results or not self.analysis_results.success:
            error_text = """
Redshift vs Age Analysis Failed

Analysis results are not available or the analysis was not successful.
Please run a successful SNID analysis first.
            """.strip()
            self.info_text.setPlainText(error_text)
            return
        
        if not self.plot_data:
            error_text = """
⚠️ No Valid Redshift vs Age Data

No valid data points found for plotting.
This may be due to:
• Insufficient template matches above the metric threshold
• Missing redshift or age information in templates
• Data format issues

Please check your analysis results and try again.
            """.strip()
            self.info_text.setPlainText(error_text)
            return
        
        # Build summary text
        threshold = float(getattr(self.analysis_results, 'hsigma_lap_ccc_threshold', 1.5))
        total_matches = len(self.all_matches)
        valid_points = len(self.plot_data)
        
        # Calculate statistics
        redshifts = [p['redshift'] for p in self.plot_data]
        ages = [p['age'] for p in self.plot_data]
        
        lines = [
            "📈 REDSHIFT vs AGE ANALYSIS",
            "=" * 35,
            "",
            f"📊 DATA SOURCE: {self.match_source}",
            f"📝 TOTAL MATCHES: {total_matches}",
            f"🎯 VALID DATA POINTS: {valid_points}",
            f"📏 METRIC THRESHOLD (HσLAP-CCC): {threshold}",
            "",
            "📊 DISTRIBUTION STATISTICS:",
            f"   Redshift Range: {min(redshifts):.4f} - {max(redshifts):.4f}",
            f"   Mean Redshift: {np.mean(redshifts):.4f} ± {np.std(redshifts):.4f}",
            f"   Age Range: {min(ages):.1f} - {max(ages):.1f} days",
            f"   Mean Age: {np.mean(ages):.1f} ± {np.std(ages):.1f} days",
            "",
        ]
        
        # Type distribution
        type_counts = defaultdict(int)
        for point in self.plot_data:
            type_counts[point['type']] += 1
        
        lines.append("🔍 TYPE DISTRIBUTION:")
        for sn_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / valid_points) * 100
            lines.append(f"   {sn_type}: {count} matches ({percentage:.1f}%)")
        
        summary_text = "\n".join(lines)
        self.info_text.setPlainText(summary_text)
    
    def _populate_statistics_table(self):
        """Populate the statistics table"""
        if not self.plot_data:
            self.stats_table.setRowCount(0)
            return
        
        # Calculate statistics by type
        type_stats = defaultdict(lambda: {'redshifts': [], 'ages': [], 'count': 0})
        
        for point in self.plot_data:
            sn_type = point['type']
            type_stats[sn_type]['redshifts'].append(point['redshift'])
            type_stats[sn_type]['ages'].append(point['age'])
            type_stats[sn_type]['count'] += 1
        
        # Sort by count (descending)
        sorted_types = sorted(type_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        
        # Populate table
        self.stats_table.setRowCount(len(sorted_types))
        
        for row, (sn_type, stats) in enumerate(sorted_types):
            # Type name
            type_item = QtWidgets.QTableWidgetItem(sn_type)
            type_item.setBackground(QtGui.QColor(self.type_colors.get(sn_type, self.type_colors['Unknown'])))
            type_item.setForeground(QtGui.QColor('white'))
            self.stats_table.setItem(row, 0, type_item)
            
            # Count
            count_item = QtWidgets.QTableWidgetItem(str(stats['count']))
            count_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 1, count_item)
            
            # Average redshift
            avg_z = np.mean(stats['redshifts'])
            z_item = QtWidgets.QTableWidgetItem(f"{avg_z:.4f}")
            z_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 2, z_item)
            
            # Average age
            avg_age = np.mean(stats['ages'])
            age_item = QtWidgets.QTableWidgetItem(f"{avg_age:.1f}")
            age_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.stats_table.setItem(row, 3, age_item)
        
        # Resize columns to content
        self.stats_table.resizeColumnsToContents()
    
    def _create_plot(self):
        """Create the redshift vs age plot"""
        if not self.plot_data or not self.ax:
            return
        
        try:
            # Clear previous plot
            self.ax.clear()
            
            # Import the custom color palette
            try:
                from snid_sage.snid.plotting import get_custom_color_palette
                custom_palette = get_custom_color_palette()
            except ImportError:
                # Fallback colors if import fails
                custom_palette = [
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
            
            # Group data by subtype instead of type for consistent coloring
            subtype_groups = defaultdict(list)
            for point in self.plot_data:
                subtype = point.get('subtype', 'Unknown')
                if not subtype or subtype.strip() == '':
                    subtype = 'Unknown'
                subtype_groups[subtype].append(point)
            
            # Create color mapping for subtypes using custom palette
            sorted_subtypes = sorted(subtype_groups.keys())
            subtype_color_map = {}
            for i, subtype in enumerate(sorted_subtypes):
                subtype_color_map[subtype] = custom_palette[i % len(custom_palette)]
            
            # Plot each subtype group
            for subtype, points in subtype_groups.items():
                redshifts = [p['redshift'] for p in points]
                ages = [p['age'] for p in points]
                color = subtype_color_map.get(subtype, '#A9A9A9')  # Gray fallback
                
                self.ax.scatter(
                    redshifts, ages,
                    c=color,
                    s=80,  # Point size
                    alpha=0.7,
                    edgecolors='black',
                    linewidths=1.0,
                    label=f"{subtype} ({len(points)})"
                )
            
            # Set labels and title
            self.ax.set_xlabel('Redshift (z)', fontsize=12, fontweight='bold')
            self.ax.set_ylabel('Template Age (days)', fontsize=12, fontweight='bold')
            self.ax.set_title('Template Ages vs Redshift Distribution (by Subtype)', fontsize=14, fontweight='bold', pad=15)
            
            # Add grid
            self.ax.grid(True, alpha=0.3, linewidth=0.5)
            
            # Add legend
            self.ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
            
            # Set axis colors and styling
            self.ax.tick_params(colors='black', labelsize=10)
            for spine in self.ax.spines.values():
                spine.set_color('black')
                spine.set_linewidth(1)
            
            # Tight layout to prevent cutoff
            self.figure.tight_layout()
            
            # Refresh canvas
            self.plot_canvas.draw()
            
            _LOGGER.info(f"Created redshift vs age plot with {len(self.plot_data)} points")
            
        except Exception as e:
            _LOGGER.error(f"Error creating plot: {e}")
            self.ax.text(0.5, 0.5, f"Error creating plot:\n{str(e)}", 
                        ha='center', va='center', transform=self.ax.transAxes,
                        fontsize=12, color='red')
            self.plot_canvas.draw()
    
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
            "Export Redshift vs Age Plot",
            "redshift_vs_age_plot.png",
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
        """Export the plot data to CSV file"""
        if not self.plot_data:
            QtWidgets.QMessageBox.warning(
                self, "Export Error", 
                "No data available to export."
            )
            return
        
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Redshift vs Age Data",
            "redshift_vs_age_data.csv",
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
                        'Age_days', 'Metric'
                    ])
                    
                    # Write data
                    for point in self.plot_data:
                        writer.writerow([
                            point['name'],
                            point['type'],
                            point['subtype'],
                            point['redshift'],
                            point['age'],
                            point['metric']
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
Error Loading Redshift vs Age Data

{error_msg}

Please try running the analysis again or check the logs for more details.
        """.strip()
        
        self.info_text.setPlainText(error_text)


def show_redshift_age_dialog(parent=None, analysis_results=None):
    """
    Show the redshift vs age dialog.
    
    Args:
        parent: Parent window
        analysis_results: SNID analysis results object
        
    Returns:
        PySide6RedshiftAgeDialog instance
    """
    dialog = PySide6RedshiftAgeDialog(parent, analysis_results)
    dialog.show()
    return dialog 