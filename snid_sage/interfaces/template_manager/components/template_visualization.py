"""
Template Visualization Widget
============================

Widget for visualizing template spectra with multiple view modes.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui

# Import flexible number input widget
from snid_sage.interfaces.gui.components.widgets.flexible_number_input import create_flexible_int_input

from .template_data import TemplateData

# Import template service for epoch-level operations
from ..services.template_service import get_template_service

# Import layout manager
from ..utils.layout_manager import get_template_layout_manager

# PyQtGraph for high-performance plotting
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
    # Import enhanced plot widget
    from snid_sage.interfaces.gui.components.plots.enhanced_plot_widget import EnhancedPlotWidget
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None
    EnhancedPlotWidget = None

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('template_manager.visualization')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('template_manager.visualization')


class TemplateVisualizationWidget(QtWidgets.QWidget):
    """Widget for visualizing template spectra"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Cap to prevent crashes when plotting very large multi-epoch templates (e.g., sn1987A)
        self._max_epochs_to_plot = 50
        self.current_template = None
        self.template_data = None
        self.plot_manager = None
        self.plot_widget = None
        self.layout_manager = get_template_layout_manager()
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the visualization interface"""
        layout = QtWidgets.QVBoxLayout(self)
        self.layout_manager.apply_panel_layout(self, layout)
        
        # Control panel
        control_panel = QtWidgets.QGroupBox("Visualization Controls")
        self.layout_manager.setup_group_box(control_panel)
        # Match panel border thickness and radius
        control_panel.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                font-size: 10pt;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #000000;
                background: #ffffff;
            }
            """
        )
        control_layout = QtWidgets.QHBoxLayout(control_panel)
        
        self.view_mode_combo = QtWidgets.QComboBox()
        self.view_mode_combo.addItems(["All Epochs", "Individual Epoch"])
        self.view_mode_combo.currentTextChanged.connect(self.update_plot)
        
        self.epoch_selector = create_flexible_int_input(min_val=1, max_val=999, default=1)
        self.epoch_selector.valueChanged.connect(self.update_plot)

        # Epoch deletion button (only enabled for user templates)
        self.delete_epoch_btn = self.layout_manager.create_action_button("Delete Epoch")
        self.delete_epoch_btn.clicked.connect(self._on_delete_epoch_clicked)
        
        control_layout.addWidget(QtWidgets.QLabel("View Mode:"))
        control_layout.addWidget(self.view_mode_combo)
        control_layout.addWidget(QtWidgets.QLabel("Epoch:"))
        control_layout.addWidget(self.epoch_selector)
        control_layout.addWidget(self.delete_epoch_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_panel)
        
        # Subsampling information label (shown when capping is applied)
        self.cap_info_label = QtWidgets.QLabel("")
        try:
            self.cap_info_label.setStyleSheet("color: #6b7280; font-size: 9pt;")
        except Exception:
            pass
        self.cap_info_label.setVisible(False)
        layout.addWidget(self.cap_info_label)
        
        # Plot area (rounded white panel with light grey contour, matching main GUI)
        self.plot_widget = QtWidgets.QFrame()
        self.plot_widget.setObjectName("template_plot_container")
        self.layout_manager.setup_template_viewer(self.plot_widget)
        self.plot_widget.setStyleSheet(
            """
            QFrame#template_plot_container {
                background-color: white;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            """
        )
        layout.addWidget(self.plot_widget)
        
        # Initialize PyQtGraph plotting
        self._setup_pyqtgraph_plot()
        
        # Template info panel - REMOVED as requested
        # The info panel has been removed to simplify the interface
        
    def _setup_pyqtgraph_plot(self):
        """Setup PyQtGraph plotting in the widget"""
        try:
            if not PYQTGRAPH_AVAILABLE:
                raise ImportError("PyQtGraph not available")
            
            # Configure PyQtGraph for software rendering
            pg.setConfigOptions(
                antialias=True, 
                useOpenGL=False,
                enableExperimental=False,
                background='w',
                foreground='k',
                exitCleanup=True,
                crashWarning=False
            )
            
            # Create enhanced PyQtGraph plot widget with save functionality
            self.plot_widget_pg = EnhancedPlotWidget()
            
            # Add to widget layout with inner margins to avoid clipping rounded corners
            plot_layout = QtWidgets.QVBoxLayout(self.plot_widget)
            try:
                # Reduce top margin to minimize whitespace above the title
                plot_layout.setContentsMargins(8, 2, 8, 8)
                plot_layout.setSpacing(0)
            except Exception:
                pass
            plot_layout.addWidget(self.plot_widget_pg)
            
            # Get plot item for customization
            self.plot_item = self.plot_widget_pg.getPlotItem()
            
            # Setup labels and grid (match main GUI vibe: subtle grid)
            self.plot_item.setLabel('left', 'Flux')
            self.plot_item.setLabel('bottom', 'Rest Wavelength (Å)')
            self.plot_item.showGrid(x=True, y=True, alpha=0.08)

            # Add slight content margins and view padding like main GUI
            try:
                # Reduce top content margin to bring title closer to the plot
                self.plot_item.setContentsMargins(6, 2, 6, 6)
                self.plot_item.getViewBox().setDefaultPadding(0.08)
            except Exception:
                pass

            # Show borders on all sides; hide tick labels on top/right to match main GUI
            try:
                # Ensure top/right axes are visible
                try:
                    self.plot_item.showAxis('right')
                    self.plot_item.showAxis('top')
                except Exception:
                    pass
                for axis_name in ('left', 'bottom', 'right', 'top'):
                    ax = self.plot_item.getAxis(axis_name)
                    if ax is not None:
                        try:
                            ax.setTextPen(pg.mkPen(color='black'))
                        except Exception:
                            pass
                        # Draw axis line as border
                        ax.setPen(pg.mkPen(color='black', width=1))
                        # Hide values on top/right for a clean frame
                        if hasattr(ax, 'setStyle') and axis_name in ('top', 'right'):
                            ax.setStyle(showValues=False)
            except Exception:
                pass
            
            # Apply theme colors
            self._apply_pyqtgraph_theme()
            
            # Initial welcome message
            self._show_welcome_message()
            
        except ImportError as e:
            _LOGGER.warning(f"PyQtGraph not available: {e}")
            # Create placeholder
            placeholder = QtWidgets.QLabel("Plot visualization requires PyQtGraph\n\npip install pyqtgraph")
            placeholder.setAlignment(QtCore.Qt.AlignCenter)
            placeholder.setStyleSheet("background-color: #f0f0f0; padding: 50px; color: gray;")
            plot_layout = QtWidgets.QVBoxLayout(self.plot_widget)
            plot_layout.addWidget(placeholder)
            
    def _apply_pyqtgraph_theme(self):
        """Apply theme colors to PyQtGraph plot"""
        if not hasattr(self, 'plot_item'):
            return
            
        try:
            # Set background and foreground colors
            self.plot_item.getViewBox().setBackgroundColor('#ffffff')

            # Draw borders on all sides; hide tick labels on top/right
            for axis_name in ('left', 'bottom', 'right', 'top'):
                ax = self.plot_item.getAxis(axis_name)
                if ax is None:
                    continue
                ax.setTextPen(pg.mkPen(color='black'))
                try:
                    ax.setPen(pg.mkPen(color='black', width=1))
                    if hasattr(ax, 'setStyle') and axis_name in ('top', 'right'):
                        ax.setStyle(showValues=False)
                except Exception:
                    pass
                
        except Exception as e:
            _LOGGER.warning(f"Could not apply PyQtGraph theme: {e}")
            
    def _show_welcome_message(self):
        """Show welcome message on empty plot"""
        if not hasattr(self, 'plot_item'):
            return
            
        # Add text item for welcome message
        text_item = pg.TextItem('Select a template to view its spectrum', 
                               color='gray', anchor=(0.5, 0.5))
        self.plot_item.addItem(text_item)
        
        # Position text in center
        text_item.setPos(5000, 0.5)  # Approximate center wavelength
            
    def set_template(self, template_name: str, template_info: Dict[str, Any]):
        """Set the current template to visualize"""
        self.current_template = {
            'name': template_name,
            'info': template_info
        }
        
        # Info labels removed - template information now shown only in plot title
        
        # Initialize epoch selector; actual max will be set after data load
        self.epoch_selector.setRange(1, 1)
        
        # Load template data
        self._load_template_data()

        # Update delete-epoch button state based on user/built-in and epoch count
        self._update_delete_epoch_button_state()
        
        # Update plot
        self.update_plot()
        
    def _load_template_data(self):
        """Load template data from storage"""
        if not self.current_template:
            return
            
        try:
            template_info = self.current_template['info']
            storage_file = template_info.get('storage_file', '')
            
            if storage_file:
                # Find the full path to the storage file
                storage_path = self._find_storage_file(storage_file, template_info)
                if storage_path:
                    self.template_data = TemplateData(self.current_template['name'], template_info)
                    self.template_data.load_data(storage_path)
                else:
                    msg = f"Storage file not found for template {self.current_template['name']}: {storage_file}"
                    _LOGGER.warning(msg)
                    self.template_data = TemplateData(self.current_template['name'], template_info)
                    self.template_data.load_error = msg
            else:
                # No storage file available – record a clear error instead of fabricating spectra
                msg = f"No storage file specified for template {self.current_template['name']}"
                _LOGGER.warning(msg)
                self.template_data = TemplateData(self.current_template['name'], template_info)
                self.template_data.load_error = msg
            
            # After loading data, update epoch selector based on actual epochs count
            try:
                epochs_count = max(1, len(self.template_data.epochs) if self.template_data else 1)
                self.epoch_selector.setRange(1, epochs_count)
            except Exception:
                pass
            # Keep delete-epoch button state in sync
            try:
                self._update_delete_epoch_button_state()
            except Exception:
                pass
                    
        except Exception as e:
            msg = f"Error loading template data for {self.current_template.get('name') if self.current_template else ''}: {e}"
            _LOGGER.error(msg)
            if self.current_template:
                self.template_data = TemplateData(self.current_template['name'], self.current_template['info'])
                self.template_data.load_error = msg

        # Ensure epoch delete button state is refreshed on any load path
        try:
            self._update_delete_epoch_button_state()
        except Exception:
            pass

    def _update_delete_epoch_button_state(self):
        """Enable Delete Epoch only for user templates with at least one epoch."""
        enabled = False
        try:
            if not self.current_template:
                enabled = False
            else:
                name = self.current_template.get('name')
                # Only user templates (those present in the user index) can be edited
                svc = get_template_service()
                user_idx = svc.get_user_index() or {}
                user_templates = (user_idx.get('templates') or {})
                is_user = name in user_templates
                has_epochs = bool(self.template_data and getattr(self.template_data, "epochs", []))
                enabled = bool(is_user and has_epochs)
        except Exception:
            enabled = False

        try:
            self.delete_epoch_btn.setEnabled(enabled)
        except Exception:
            pass

    def _on_delete_epoch_clicked(self):
        """Handle Delete Epoch button click."""
        if not self.current_template or not self.template_data or not self.template_data.epochs:
            return

        name = self.current_template.get('name', '')
        if not name:
            return

        # Confirm with the user
        current_epoch_display = int(self.epoch_selector.value())
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Epoch",
            (
                f"Are you sure you want to delete epoch #{current_epoch_display} "
                f"from template '{name}'?\n\n"
                "The template itself will be removed only if this was the last epoch."
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Map 1-based selector to 0-based index for the service
        epoch_index = max(0, current_epoch_display - 1)

        svc = get_template_service()
        ok = False
        try:
            ok = svc.delete_epoch(name, epoch_index)
        except Exception as e:
            _LOGGER.error(f"Error deleting epoch via service: {e}")
            ok = False

        if not ok:
            QtWidgets.QMessageBox.critical(
                self,
                "Delete Epoch",
                "Failed to delete epoch.\n\n"
                "Note: only user templates can be modified, and the epoch index "
                "must be valid.",
            )
            return

        # Successfully deleted: reload data and refresh plot/state
        try:
            self._load_template_data()
        except Exception:
            pass

        try:
            self.update_plot()
        except Exception:
            pass

        QtWidgets.QMessageBox.information(
            self,
            "Delete Epoch",
            "Epoch deleted successfully.\n\n"
            "If this was the last epoch, the template has been removed.",
        )
            
    def _find_storage_file(self, storage_file: str, template_info: Dict[str, Any]) -> Optional[str]:
        """Find the full path to a storage file (packaged or user), honoring profile.

        Resolution order:
        1) Managed built-in templates bank resolved via the centralized
           :mod:`templates_manager` (GitHub-downloaded archive).
        2) Configured user templates directory (for user HDF5 banks).
        3) Legacy/repo-relative fallbacks for development checkouts.
        """
        profile_id = ((template_info or {}).get('profile_id') or '').strip().lower()
        pkg_folder_order = ['templates']

        # 1) Managed built-in templates bank (GitHub-downloaded archive)
        try:
            from snid_sage.shared.templates_manager import get_templates_dir as _get_managed_tpl_dir

            managed_base = Path(_get_managed_tpl_dir())
            candidate = managed_base / storage_file
            if candidate.exists():
                _LOGGER.info(f"Found storage file in managed templates bank: {candidate}")
                return str(candidate)
        except Exception:
            # Best-effort only; fall through to user paths.
            pass

        # 2) User templates directory resolved by TemplateService (configured path)
        try:
            from snid_sage.interfaces.template_manager.services.template_service import get_template_service

            svc = get_template_service()
            user_dir = svc.get_user_templates_dir()
            if user_dir:
                candidate = Path(user_dir) / storage_file
                if candidate.exists():
                    _LOGGER.info(f"Found storage file in user templates dir: {candidate}")
                    return str(candidate)
        except Exception:
            pass

        # 3) Legacy fallbacks (packaged or repo-relative paths)
        try:
            from importlib import resources

            for folder in pkg_folder_order:
                with resources.as_file(resources.files('snid_sage') / folder / storage_file) as p:
                    if p.exists():
                        _LOGGER.info(f"Found storage file in packaged resources: {p}")
                        return str(p)
        except Exception:
            pass

        for folder in pkg_folder_order:
            for path in [
                os.path.join("snid_sage", folder, storage_file),
                os.path.join(folder, storage_file),
                storage_file,
            ]:
                if os.path.exists(path):
                    _LOGGER.info(f"Found storage file at: {path}")
                    return path

        _LOGGER.warning(
            f"Storage file {storage_file} not found in any of the expected locations (profile={profile_id or 'optical'})"
        )
        return None
        
    def update_plot(self):
        """Update the plot based on current settings"""
        if not self.current_template:
            return
            
        try:
            # _plot_template_spectrum() is a no-op when PyQtGraph plot_item is not available.
            self._plot_template_spectrum()
        except Exception as e:
            _LOGGER.error(f"Error updating plot: {e}")
            
    def _plot_template_spectrum(self):
        """Plot the actual template spectrum using PyQtGraph"""
        if not hasattr(self, 'plot_item'):
            return
            
        # Clear previous plots and legends
        self.plot_item.clear()
        # Explicitly clear legend if it exists
        if hasattr(self.plot_item, 'legend') and self.plot_item.legend is not None:
            self.plot_item.legend.scene().removeItem(self.plot_item.legend)
            self.plot_item.legend = None
        
        if self.template_data and self.template_data.wave_data is not None:
            view_mode = self.view_mode_combo.currentText()
            
            # Collect flux arrays actually plotted so we can set a stable view range
            plotted_flux_arrays = []
            
            if view_mode == "All Epochs":
                plotted_flux_arrays = self._plot_all_epochs_pg() or []
                # Show or hide subsampling info
                try:
                    total_epochs = len(self.template_data.epochs)
                    if total_epochs > self._max_epochs_to_plot:
                        shown = min(self._max_epochs_to_plot, total_epochs)
                        self.cap_info_label.setText(f"Showing {shown} of {total_epochs} epochs (subsampled)")
                        self.cap_info_label.setVisible(True)
                    else:
                        self.cap_info_label.setVisible(False)
                except Exception:
                    self.cap_info_label.setVisible(False)
            elif view_mode == "Individual Epoch":
                flux_arr = self._plot_individual_epoch_pg()
                if flux_arr is not None:
                    plotted_flux_arrays = [flux_arr]
                # Hide subsampling info for individual view
                try:
                    self.cap_info_label.setVisible(False)
                except Exception:
                    pass
            
            # After plotting, reset the view so the template always fits the canvas
            try:
                if plotted_flux_arrays:
                    self._set_stable_view_range(self.template_data.wave_data, plotted_flux_arrays)
            except Exception:
                pass
            
            # Ensure x-range includes fixed left label anchor
            try:
                anchor_x = self._compute_left_label_x()
                vb = self.plot_item.getViewBox()
                xr, yr = vb.viewRange()
                xmin, xmax = float(xr[0]), float(xr[1])
                if anchor_x < xmin:
                    # Extend to include anchor with a small margin
                    margin = 0.02 * (xmax - xmin)
                    vb.setRange(xRange=(anchor_x - margin, xmax), yRange=yr, padding=0)
            except Exception:
                pass
            
        else:
            # No real data available – show a clear placeholder message instead of a fake spectrum
            reason = ""
            try:
                if self.template_data and getattr(self.template_data, "load_error", None):
                    reason = str(self.template_data.load_error)
            except Exception:
                reason = ""

            try:
                # Clear plot and show a centered error message
                self.plot_item.clear()
                msg = "Template data could not be loaded."
                if reason:
                    msg += f"\n\n{reason}"
                text_item = pg.TextItem(msg, color='red', anchor=(0.5, 0.5))
                self.plot_item.addItem(text_item)
                # Set a generic view range so the text is visible
                self.plot_item.setLabel('left', 'Flux')
                self.plot_item.setLabel('bottom', 'Rest Wavelength (Å)')
                self.plot_item.setXRange(3000, 10000)
                self.plot_item.setYRange(-0.5, 1.5)
            except Exception as e:
                _LOGGER.warning(f"Could not show no-data message: {e}")
            
        # Set title with comprehensive template information
        from snid_sage.shared.utils import clean_template_name
        clean_name = clean_template_name(self.current_template['name'])
        template_info = self.current_template['info']
        
        # Build comprehensive title
        title_parts = [f"Template: {clean_name}"]
        
        # Add type/subtype
        type_info = template_info.get('type', 'Unknown')
        subtype_info = template_info.get('subtype', '')
        if subtype_info and subtype_info != 'Unknown':
            type_info += f"/{subtype_info}"
        title_parts.append(f"Type: {type_info}")
        
        # Include only epochs count (omit Ages from title as requested)
        try:
            if self.template_data and self.template_data.epochs:
                epochs_count = len(self.template_data.epochs)
                if epochs_count > 1:
                    title_parts.append(f"Epochs: {epochs_count}")
                # If subsampled in All Epochs view, indicate clearly in the title
                try:
                    if view_mode == "All Epochs" and epochs_count > self._max_epochs_to_plot:
                        shown = min(self._max_epochs_to_plot, epochs_count)
                        title_parts.append(f"Showing {shown} of {epochs_count}")
                except Exception:
                    pass
        except Exception:
            pass
        
        title = " | ".join(title_parts)
        self.plot_item.setTitle(title)

        # Suggest a nice default filename for exports: <TemplateName>__<Type[-Subtype]>
        try:
            type_info_safe = template_info.get('type', 'Unknown') or 'Unknown'
            subtype_info_safe = template_info.get('subtype', '') or ''
            if subtype_info_safe and subtype_info_safe != 'Unknown':
                type_block = f"{type_info_safe}-{subtype_info_safe}"
            else:
                type_block = f"{type_info_safe}"
            basename_suggestion = f"{clean_name}__{type_block}"
            if hasattr(self, 'plot_widget_pg') and self.plot_widget_pg is not None:
                # Let the plot widget sanitize characters and apply as default
                self.plot_widget_pg.set_default_export_basename(basename_suggestion)
        except Exception:
            pass

        # Show save button once actual content is plotted
        try:
            if hasattr(self, 'plot_widget_pg') and self.plot_widget_pg is not None:
                self.plot_widget_pg.show_save_button()
        except Exception:
            pass
        
    def _set_stable_view_range(self, wave: np.ndarray, flux_arrays: list[np.ndarray]) -> None:
        """
        Set a stable view range that always fits the currently plotted template data.

        This explicitly resets the ViewBox range each time a template (or epoch/view)
        is plotted so previous zoom/pan states don't cause clipped or tiny plots.
        """
        if not hasattr(self, 'plot_item'):
            return
        if wave is None or len(wave) == 0:
            return
        if not flux_arrays:
            return

        try:
            # Clean wavelength array
            wave_arr = np.asarray(wave, dtype=float)
            wave_arr = wave_arr[np.isfinite(wave_arr)]
            if wave_arr.size == 0:
                return

            # Concatenate all finite flux values from the provided arrays
            valid_flux_chunks = []
            for f in flux_arrays:
                if f is None:
                    continue
                f_arr = np.asarray(f, dtype=float)
                f_arr = f_arr[np.isfinite(f_arr)]
                if f_arr.size:
                    valid_flux_chunks.append(f_arr)

            if not valid_flux_chunks:
                return

            all_flux = np.concatenate(valid_flux_chunks)
            if all_flux.size == 0:
                return

            vb = self.plot_item.getViewBox()

            # Disable auto-ranging to avoid PyQtGraph "spinning axes" behaviour
            try:
                vb.disableAutoRange()
            except Exception:
                pass

            # Compute X range with a small margin
            x_min = float(np.min(wave_arr))
            x_max = float(np.max(wave_arr))
            if not np.isfinite(x_min) or not np.isfinite(x_max):
                return

            if x_max > x_min:
                x_margin = 0.05 * (x_max - x_min)
            else:
                # Degenerate or single-point wavelength range – construct a small window
                scale = abs(x_max) if x_max != 0 else 1.0
                x_margin = 0.05 * scale

            x_lo = x_min - x_margin
            x_hi = x_max + x_margin

            # Compute Y range with a larger margin
            y_min = float(np.min(all_flux))
            y_max = float(np.max(all_flux))
            if not np.isfinite(y_min) or not np.isfinite(y_max):
                return

            if y_max > y_min:
                y_margin = 0.10 * (y_max - y_min)
            else:
                # Flat line case – create a reasonable vertical window
                scale = abs(y_max) if y_max != 0 else 1.0
                y_margin = 0.10 * scale

            y_lo = y_min - y_margin
            y_hi = y_max + y_margin

            # Guard against zero-height windows
            if y_hi <= y_lo:
                y_center = y_lo
                span = 0.10 * (abs(y_center) if y_center != 0 else 1.0)
                y_lo = y_center - span
                y_hi = y_center + span

            vb.setRange(xRange=(x_lo, x_hi), yRange=(y_lo, y_hi), padding=0.0)

        except Exception:
            # Never let view-range computation break plotting
            pass

    def _get_active_profile_id(self) -> str:
        """Determine active profile id for labeling (optical|onir)."""
        try:
            info = (self.current_template or {}).get('info') or {}
            pid = (info.get('profile_id') or '').strip().lower()
            if pid:
                return pid
        except Exception:
            pass
        # Fallback to service
        try:
            from snid_sage.interfaces.template_manager.services.template_service import get_template_service
            return (get_template_service().get_active_profile() or 'optical').strip().lower()
        except Exception:
            return 'optical'

    def _compute_left_label_x(self) -> float:
        """Return fixed left-side anchor wavelength by profile."""
        pid = self._get_active_profile_id()
        return 1950.0 if pid == 'onir' else 2450.0

    def _compute_label_x(self, wave: np.ndarray) -> float:
        """Choose label x-position near right end depending on profile, clamped to data range."""
        if wave is None or wave.size == 0:
            return 0.0
        try:
            anchor = 10000.0 if self._get_active_profile_id() != 'onir' else 25000.0
            xmax = float(wave[-1])
            xmin = float(wave[0])
            # Clamp anchor to [xmin, xmax]; bias slightly left of max to avoid clipping
            x = min(max(anchor, xmin), xmax)
            # If anchor equals max, step a bit left
            if abs(x - xmax) <= 1e-6:
                x = xmin + 0.98 * (xmax - xmin)
            return x
        except Exception:
            return float(wave[-1])

    def _nearest_index(self, array: np.ndarray, value: float) -> int:
        try:
            idx = int(np.searchsorted(array, value))
            if idx <= 0:
                return 0
            if idx >= array.size:
                return array.size - 1
            # Pick closer between idx and idx-1
            return (idx if abs(array[idx] - value) < abs(array[idx-1] - value) else idx-1)
        except Exception:
            return max(0, array.size - 1)

    def _add_age_label(self, x: float, y: float, age: float, color) -> None:
        try:
            txt = f"{age:.1f}"
            # Right-center anchor so the label sits to the left of x and centered on y
            label = pg.TextItem(txt, color=color, anchor=(1.0, 0.5))
            try:
                f = QtGui.QFont()
                f.setPointSize(8)
                label.setFont(f)
            except Exception:
                pass
            self.plot_item.addItem(label)
            label.setPos(float(x), float(y))
        except Exception:
            pass

    def _plot_all_epochs_pg(self):
        """Plot all epochs with vertical offset using PyQtGraph"""
        if not self.template_data or not self.template_data.epochs:
            return
            
        # Validate data
        if self.template_data.wave_data is None:
            _LOGGER.warning("No wavelength data available for plotting")
            return
            
        # Determine which epochs to plot (subsample if too many)
        total_epochs = len(self.template_data.epochs)
        if total_epochs <= self._max_epochs_to_plot:
            indices = list(range(total_epochs))
        else:
            # Evenly spaced indices over the full set
            lin = np.linspace(0, total_epochs - 1, self._max_epochs_to_plot)
            indices = sorted({int(round(x)) for x in lin})
            # Ensure we do not exceed the cap due to rounding collisions
            if len(indices) > self._max_epochs_to_plot:
                indices = indices[:self._max_epochs_to_plot]
        # Generate colors for the plotted subset
        colors = [pg.intColor(i, max(1, len(indices))) for i in range(len(indices))]
        # Determine fixed left-side label x position once
        label_x = self._compute_left_label_x()
        
        total_plotted = len(indices)
        for j, idx in enumerate(indices):
            epoch = self.template_data.epochs[idx]
            if epoch['flux'] is not None and len(epoch['flux']) == len(self.template_data.wave_data):
                # Apply vertical offset
                # Reverse order so negative ages (early epochs) are at the top
                offset = (total_plotted - 1 - j) * 0.5
                flux = epoch['flux'] + offset
                age = epoch['age']
                
                # Create plot curve
                curve = self.plot_item.plot(
                    self.template_data.wave_data,
                    flux,
                    pen=pg.mkPen(color=colors[j], width=1.5),
                    name=None,
                    connect='all',
                    autoDownsample=False,
                    clipToView=False,
                    downsample=1,
                )
                # Place label exactly at the spectrum's baseline (offset only), left of spectrum
                y = float(offset)
                self._add_age_label(label_x, y, age, colors[j])
            else:
                _LOGGER.warning(f"Skipping epoch {idx}: flux data mismatch with wavelength grid")
        
    def _plot_individual_epoch_pg(self):
        """Plot individual epoch using PyQtGraph"""
        if not self.template_data or not self.template_data.epochs:
            return
            
        # Validate data
        if self.template_data.wave_data is None:
            _LOGGER.warning("No wavelength data available for plotting")
            return
            
        epoch_value = self.epoch_selector.value()
        if epoch_value is None:
            epoch_value = 1  # Default to first epoch
        epoch_idx = int(epoch_value) - 1
        
        if epoch_idx < len(self.template_data.epochs):
            epoch = self.template_data.epochs[epoch_idx]
            if (epoch['flux'] is not None and 
                len(epoch['flux']) == len(self.template_data.wave_data)):
                age = epoch['age']
                
                # Plot the epoch
                curve = self.plot_item.plot(
                    self.template_data.wave_data,
                    epoch['flux'],
                    pen=pg.mkPen(color='blue', width=2),
                    name=None,
                    connect='all',
                    autoDownsample=False,
                    clipToView=False,
                    downsample=1,
                )
                
                # Place label exactly at baseline (no offset), left of spectrum
                label_x = self._compute_left_label_x()
                y = 0.0
                self._add_age_label(label_x, y, age, 'blue')
            else:
                _LOGGER.warning(f"Epoch {epoch_idx}: flux data mismatch with wavelength grid")
        else:
            _LOGGER.warning(f"Epoch index {epoch_idx} out of range (available: {len(self.template_data.epochs)})")
                
    
        
    def clear_plot(self):
        """Clear the current plot"""
        if hasattr(self, 'plot_item'):
            self.plot_item.clear()
            self._show_welcome_message()
    
    def export_plot(self, filename: str):
        """Export the current plot to file"""
        if hasattr(self, 'plot_widget_pg'):
            try:
                exporter = pg.exporters.ImageExporter(self.plot_widget_pg.plotItem)
                exporter.export(filename)
                _LOGGER.info(f"Plot exported to {filename}")
            except Exception as e:
                _LOGGER.error(f"Error exporting plot: {e}")
    
    def get_current_template_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently displayed template"""
        if self.current_template and self.template_data:
            return self.template_data.get_metadata_summary()
        return None