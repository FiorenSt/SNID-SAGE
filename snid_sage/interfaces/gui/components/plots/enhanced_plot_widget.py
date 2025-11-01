"""
SNID SAGE - Enhanced PlotWidget
===============================

Enhanced PyQtGraph PlotWidget with:
- Disabled right-click context menus
- Built-in save functionality with emoji button
- High-resolution image export (300 DPI)
- SVG vector export
- Consistent theming support

Based on custom_autoscale_with_export.py demo, adapted for SNID SAGE.

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import os
import sys
from typing import Optional, Dict, Any
import re
import csv
from itertools import zip_longest

# PySide6 imports
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets

# Twemoji support
try:
    from snid_sage.interfaces.gui.utils.twemoji_manager import get_emoji_pixmap
    _TWEMOJI_AVAILABLE = True
except Exception:
    _TWEMOJI_AVAILABLE = False

# PyQtGraph imports
try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    pg = None

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.enhanced_plot_widget')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.enhanced_plot_widget')


def _get_ui_font_family() -> str:
    """Return a UI font family that exists on the current platform."""
    if sys.platform == 'darwin':
        return 'Arial'
    if sys.platform == 'win32':
        return 'Segoe UI'
    # Linux and others: pick commonly available sans
    return 'DejaVu Sans'


class SimplePlotWidget(pg.PlotWidget):
    """
    Simple PyQtGraph PlotWidget with only disabled context menus (no save functionality)
    
    Used for dialogs where save functionality is not desired, like preprocessing previews.
    Features enhanced tick styling from the demo.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize simple plot widget"""
        super().__init__(*args, **kwargs)
        
        # Disable context menus completely
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        
        # Ensure consistent drag-and-drop event sequence to avoid Qt warnings
        # Accept drops at both widget and viewport levels
        try:
            self.setAcceptDrops(True)
            if hasattr(self, 'viewport') and callable(self.viewport):
                self.viewport().setAcceptDrops(True)
        except Exception:
            pass
        
        # Disable plot item and viewbox menus
        plot_item = self.getPlotItem()
        if plot_item:
            plot_item.setMenuEnabled(False)
            vb = plot_item.getViewBox()
            if vb:
                vb.setMenuEnabled(False)
        
        # Apply enhanced tick styling
        self._apply_tick_styling()

    # Drag-and-drop handlers to keep Qt from emitting dragLeave before dragEnter warnings
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # type: ignore[override]
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # type: ignore[override]
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:  # type: ignore[override]
        event.accept()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # type: ignore[override]
        # We do not handle drops here; just ignore after a consistent accept sequence
        event.ignore()
    
    def _apply_tick_styling(self):
        """Apply enhanced tick styling from the demo"""
        try:
            plot_item = self.getPlotItem()
            if not plot_item:
                return
            
            # Configure enhanced axis styling similar to tick demo
            axis_font = QtGui.QFont(_get_ui_font_family(), 9)
            
            for name in ('left', 'bottom'):
                axis = plot_item.getAxis(name)
                axis.setPen(pg.mkPen(color='black', width=1))
                axis.setTextPen(pg.mkPen(color='black'))
                axis.setTickFont(axis_font)
            
            # Enhanced grid with stronger alpha like the demo
            plot_item.showGrid(x=True, y=True, alpha=0.3)
            
            _LOGGER.debug("Enhanced tick styling applied to SimplePlotWidget")
            
        except Exception as e:
            _LOGGER.error(f"Failed to apply tick styling to SimplePlotWidget: {e}")
    
    def apply_wavelength_ticks(self, wavelength_range: tuple):
        """Apply custom wavelength tick styling"""
        try:
            plot_item = self.getPlotItem()
            if not plot_item:
                return
            
            min_wave, max_wave = wavelength_range
            # Major ticks every 1000 Å, minor every 500 Å like the demo
            major_step = 1000
            minor_step = 500
            
            # Calculate major tick positions
            start_major = int((min_wave // major_step + 1) * major_step)
            end_major = int((max_wave // major_step) * major_step)
            major_ticks = [(w, f"{w}") for w in range(start_major, end_major + 1, major_step)]
            
            # Calculate minor tick positions (excluding major tick positions)
            start_minor = int((min_wave // minor_step + 1) * minor_step)
            end_minor = int((max_wave // minor_step) * minor_step)
            minor_ticks = [(w, "") for w in range(start_minor, end_minor + 1, minor_step) 
                           if w % major_step != 0]
            
            plot_item.getAxis('bottom').setTicks([major_ticks, minor_ticks])
            
            _LOGGER.debug(f"Custom wavelength ticks applied for range {wavelength_range}")
            
        except Exception as e:
            _LOGGER.error(f"Failed to apply wavelength ticks: {e}")


class EnhancedPlotWidget(pg.PlotWidget):
    """
    Enhanced PyQtGraph PlotWidget with disabled context menus and save functionality
    
    Features:
    - Disabled right-click context menus on plot and viewbox
    - Save emoji button in bottom-right corner
    - Export menu with high-resolution PNG/JPG (300 DPI) and SVG options
    - Automatic positioning and theming support
    """
    
    # Emit local file paths when files are dropped onto the widget
    files_dropped = QtCore.Signal(list)

    def __init__(self, *args, **kwargs):
        """Initialize enhanced plot widget"""
        super().__init__(*args, **kwargs)
        
        # Disable context menus completely
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        
        # Ensure consistent drag-and-drop event sequence to avoid Qt warnings
        # Accept drops at both widget and viewport levels
        try:
            self.setAcceptDrops(True)
            if hasattr(self, 'viewport') and callable(self.viewport):
                self.viewport().setAcceptDrops(True)
        except Exception:
            pass
        
        # Disable plot item and viewbox menus
        plot_item = self.getPlotItem()
        if plot_item:
            plot_item.setMenuEnabled(False)
            vb = plot_item.getViewBox()
            if vb:
                vb.setMenuEnabled(False)
        
        # Track whether save button should be shown
        self.save_proxy = None
        self._show_save_button = False
        # Suggested base name for export dialogs (without extension)
        self._default_export_basename: str = "snid_sage_plot"
        
        # Initialize save functionality after a short delay to ensure plot is ready
        QtCore.QTimer.singleShot(100, self._setup_save_functionality)
        
        # Apply enhanced tick styling
        self._apply_tick_styling()

    def set_default_export_basename(self, basename: str) -> None:
        """Set the default basename used in export dialogs (extension added automatically).

        Unsafe characters will be removed. Spaces become underscores. If empty, a fallback is used.
        """
        try:
            if not isinstance(basename, str):
                return
            # Normalize spaces and slashes
            name = basename.strip().replace('/', '-').replace('\\', '-')
            name = re.sub(r"\s+", "_", name)
            # Remove characters not allowed in filenames (keep alnum, dash, underscore, dot)
            name = re.sub(r"[^A-Za-z0-9._-]", "", name)
            # Collapse multiple underscores/dashes
            name = re.sub(r"[_-]{2,}", "_", name)
            name = name.strip('._-')
            if not name:
                name = "snid_sage_plot"
            self._default_export_basename = name
        except Exception:
            self._default_export_basename = "snid_sage_plot"

    # Drag-and-drop handlers to keep Qt from emitting dragLeave before dragEnter warnings
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # type: ignore[override]
        try:
            mime = event.mimeData()
            if mime and mime.hasUrls():
                # Accept only local file URLs
                for url in mime.urls():
                    if url.isLocalFile():
                        event.acceptProposedAction()
                        return
        except Exception:
            pass
        event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # type: ignore[override]
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:  # type: ignore[override]
        event.accept()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # type: ignore[override]
        try:
            mime = event.mimeData()
            if not mime or not mime.hasUrls():
                event.ignore()
                return
            paths = []
            for url in mime.urls():
                if url.isLocalFile():
                    paths.append(url.toLocalFile())
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        except Exception:
            pass
        event.ignore()
    
    def _setup_save_functionality(self):
        """Setup save button after plot is fully initialized"""
        try:
            self._add_save_button()
        except Exception as e:
            _LOGGER.warning(f"Failed to setup save functionality: {e}")
    
    def _add_save_button(self):
        """Add a save emoji button using QGraphicsProxyWidget approach"""
        plot_item = self.getPlotItem()
        if not plot_item:
            return
        
        # Create a QLabel with save icon/emoji - no button background for clean look
        save_emoji = QtWidgets.QLabel()
        save_emoji.setFixedSize(16, 16)
        save_emoji.setToolTip("Save plot as image")
        save_emoji.setAlignment(QtCore.Qt.AlignCenter)
        save_emoji.setStyleSheet("""
            QLabel { background-color: transparent; border: none; }
            QLabel:hover { background-color: rgba(200, 200, 200, 0.5); border-radius: 8px; }
        """)

        # Prefer packaged Twemoji icon; fallback to text glyph
        used_pixmap = False
        if _TWEMOJI_AVAILABLE:
            try:
                icon = get_emoji_pixmap("💾", size=16)
                if icon is not None:
                    pixmap = icon.pixmap(16, 16)  # type: ignore[attr-defined]
                    if hasattr(pixmap, 'isNull') and not pixmap.isNull():  # type: ignore[attr-defined]
                        save_emoji.setPixmap(pixmap)
                        used_pixmap = True
            except Exception:
                used_pixmap = False
        if not used_pixmap:
            save_emoji.setText("💾")
            save_emoji.setStyleSheet("""
                QLabel { background-color: transparent; border: none; font-size: 13px; color: #333; font-weight: bold; }
                QLabel:hover { background-color: rgba(200, 200, 200, 0.5); border-radius: 8px; }
            """)
        
        # Make it clickable
        save_emoji.mousePressEvent = lambda event: self._show_export_menu()
        
        # Wrap in QGraphicsProxyWidget for scene integration
        self.save_proxy = QtWidgets.QGraphicsProxyWidget()
        self.save_proxy.setWidget(save_emoji)
        
        # Add to plot scene
        plot_item.scene().addItem(self.save_proxy)
        
        def position_save_emoji():
            """Position save emoji in bottom-right corner"""
            try:
                plot_rect = plot_item.sceneBoundingRect()
                
                # Position at bottom-right corner with margin
                x_pos = plot_rect.right() - 16  
                y_pos = plot_rect.bottom() - 16 
                
                self.save_proxy.setPos(x_pos, y_pos)
                self.save_proxy.setZValue(1000)  # Ensure it's on top
            except Exception as e:
                _LOGGER.debug(f"Error positioning save emoji: {e}")
        
        # Connect positioning to layout changes
        plot_item.vb.sigResized.connect(position_save_emoji)
        QtCore.QTimer.singleShot(200, position_save_emoji)  # Initial positioning
        
        # Hide save button initially (will be shown when data is plotted)
        self.save_proxy.hide()

        # If visibility was requested before proxy was created, honor it now
        if getattr(self, '_show_save_button', False):
            try:
                self.save_proxy.show()
            except Exception:
                pass
    
    def _show_export_menu(self):
        """Show context menu with export options"""
        menu = QtWidgets.QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 12px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
            }
        """)
        
        # Add CSV export action
        csv_action = menu.addAction("📊 Save spectrum data (CSV)")
        csv_action.triggered.connect(self._save_csv_data)
        
        # Add image export action
        image_action = menu.addAction("📷 Save as High-Res Image (Screen Resolution)")
        image_action.triggered.connect(self._save_high_res_image)
        
        # Add SVG export action
        svg_action = menu.addAction("📄 Save as Vector Graphics (SVG)")
        svg_action.triggered.connect(self._save_svg)
        
        # Position menu near the save button
        if hasattr(self, 'save_proxy'):
            try:
                proxy_pos = self.save_proxy.pos()
                global_pos = self.mapToGlobal(QtCore.QPoint(int(proxy_pos.x()), int(proxy_pos.y())))
                menu.exec(global_pos)
            except Exception:
                menu.exec(QtWidgets.QCursor.pos())
        else:
            menu.exec(QtWidgets.QCursor.pos())
    
    def _save_csv_data(self):
        """Save plotted spectrum data to CSV.
        - If only one spectrum is present: write wavelength,flux
        - If overlay is present: write wavelength_obs,flux_obs,wavelength_template,flux_template
        """
        try:
            plot_item = self.getPlotItem()
            if not plot_item:
                QtWidgets.QMessageBox.information(self, "Export Data", "No plot available to export.")
                return

            # Collect data items from the plot
            try:
                data_items = plot_item.listDataItems()
            except Exception:
                data_items = []

            if not data_items:
                QtWidgets.QMessageBox.information(self, "Export Data", "No data to export.")
                return

            obs_x = obs_y = None
            tpl_x = tpl_y = None

            for item in data_items:
                try:
                    # PlotDataItem exposes getData(); guard if not available
                    x, y = item.getData()  # type: ignore[attr-defined]
                except Exception:
                    continue

                name = ""
                try:
                    name = (item.name() or "").lower()  # type: ignore[attr-defined]
                except Exception:
                    name = ""

                # Heuristics to classify curves
                if "template" in name:
                    tpl_x, tpl_y = x, y
                elif "observed" in name:
                    if obs_x is None:
                        obs_x, obs_y = x, y
                elif "spectrum" in name:
                    if obs_x is None:
                        obs_x, obs_y = x, y
                else:
                    # Fallback assignment if names are missing
                    if obs_x is None:
                        obs_x, obs_y = x, y
                    elif tpl_x is None:
                        tpl_x, tpl_y = x, y

            default_name = f"{getattr(self, '_default_export_basename', 'snid_sage_plot')}.csv"
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Spectrum Data (CSV)", default_name,
                "CSV Files (*.csv);;All Files (*)"
            )

            if not filename:
                return

            # Hide save button during export to avoid capturing it or interaction issues
            if hasattr(self, 'save_proxy') and self.save_proxy:
                try:
                    self.save_proxy.hide()
                except Exception:
                    pass

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                if obs_x is not None and obs_y is not None and tpl_x is not None and tpl_y is not None:
                    # Overlay present: single wavelength column (shared grid), two flux columns
                    writer.writerow(["wavelength", "flux_obs", "flux_template"])
                    for xo, yo, yt in zip_longest(obs_x, obs_y, tpl_y, fillvalue=""):
                        writer.writerow([xo, yo, yt])
                elif obs_x is not None and obs_y is not None:
                    # Single spectrum
                    writer.writerow(["wavelength", "flux"])
                    for x, y in zip(obs_x, obs_y):
                        writer.writerow([x, y])
                else:
                    # Template only (edge case)
                    writer.writerow(["wavelength", "flux"])
                    if tpl_x is not None and tpl_y is not None:
                        for x, y in zip(tpl_x, tpl_y):
                            writer.writerow([x, y])

            QtWidgets.QMessageBox.information(
                self, "Export Successful",
                f"Data saved successfully:\n{os.path.basename(filename)}"
            )

        except Exception as e:
            _LOGGER.error(f"Failed to save CSV data: {e}")
            QtWidgets.QMessageBox.warning(self, "Export Failed", str(e))
        finally:
            if hasattr(self, 'save_proxy') and self.save_proxy:
                try:
                    self.save_proxy.show()
                except Exception:
                    pass

    def _save_high_res_image(self):
        """Save plot as high-resolution image (100 DPI for screen-like appearance)"""
        default_name = f"{getattr(self, '_default_export_basename', 'snid_sage_plot')}.png"
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Plot as High-Resolution Image", default_name,
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if filename:
            try:
                # Hide save button during export
                if hasattr(self, 'save_proxy'):
                    self.save_proxy.hide()
                
                # Import here to avoid circular dependencies
                import pyqtgraph.exporters
                plot_item = self.getPlotItem()
                
                # Use 100 DPI to match screen appearance and avoid thin lines
                # Calculate width based on current widget size and 100 DPI
                current_width = self.width()
                current_height = self.height()
                
                # Scale to 100 DPI (approximately screen resolution)
                # This ensures lines appear the same thickness as on screen
                exporter = pyqtgraph.exporters.ImageExporter(plot_item)
                exporter.parameters()['width'] = current_width
                exporter.parameters()['height'] = current_height
                exporter.export(filename)
                
                _LOGGER.info(f"Plot saved as high-resolution image: {filename}")
                
                # Show success message
                QtWidgets.QMessageBox.information(
                    self, "Export Successful", 
                    f"Plot saved successfully:\n{os.path.basename(filename)}"
                )
                
            except Exception as e:
                error_msg = f"Failed to save image: {str(e)}"
                _LOGGER.error(error_msg)
                QtWidgets.QMessageBox.warning(self, "Export Failed", error_msg)
            finally:
                # Show button again
                if hasattr(self, 'save_proxy'):
                    self.save_proxy.show()
    
    def _save_svg(self):
        """Save plot as SVG vector graphics"""
        default_name = f"{getattr(self, '_default_export_basename', 'snid_sage_plot')}.svg"
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Plot as Vector Graphics", default_name,
            "SVG Files (*.svg);;All Files (*)"
        )
        
        if filename:
            try:
                # Hide save button during export
                if hasattr(self, 'save_proxy'):
                    self.save_proxy.hide()
                
                # Import here to avoid circular dependencies
                import pyqtgraph.exporters
                plot_item = self.getPlotItem()
                
                # Export as SVG vector format
                exporter = pyqtgraph.exporters.SVGExporter(plot_item)
                exporter.export(filename)
                
                _LOGGER.info(f"Plot saved as SVG: {filename}")
                
                # Show success message
                QtWidgets.QMessageBox.information(
                    self, "Export Successful", 
                    f"Plot saved successfully:\n{os.path.basename(filename)}"
                )
                
            except Exception as e:
                error_msg = f"Failed to save SVG: {str(e)}"
                _LOGGER.error(error_msg)
                QtWidgets.QMessageBox.warning(self, "Export Failed", error_msg)
            finally:
                # Show button again
                if hasattr(self, 'save_proxy'):
                    self.save_proxy.show()
    
    # === Public wrappers for programmatic saving via keyboard shortcuts ===
    def save_as_png_dialog(self):
        """Open a dialog and save the current plot as PNG/JPG (screen-resolution)."""
        try:
            self._save_high_res_image()
        except Exception as e:
            _LOGGER.error(f"Error saving plot as PNG via dialog: {e}")
    
    def save_as_svg_dialog(self):
        """Open a dialog and save the current plot as SVG vector graphics."""
        try:
            self._save_svg()
        except Exception as e:
            _LOGGER.error(f"Error saving plot as SVG via dialog: {e}")
    
    def show_save_button(self):
        """Show the save button (call when data is plotted)"""
        # Persist desired visibility even if proxy not yet created
        self._show_save_button = True
        if hasattr(self, 'save_proxy') and self.save_proxy:
            self.save_proxy.show()
    
    def hide_save_button(self):
        """Hide the save button (call when plot is cleared)"""
        self._show_save_button = False
        if hasattr(self, 'save_proxy') and self.save_proxy:
            self.save_proxy.hide()
    
    def apply_theme_colors(self, theme_colors: Optional[Dict[str, str]] = None):
        """Apply theme colors to the plot if needed"""
        if not theme_colors:
            return
        
        try:
            # Update save button styling based on theme if needed
            if hasattr(self, 'save_proxy') and self.save_proxy.widget():
                # You can customize the save button appearance based on theme here
                pass
        except Exception as e:
            _LOGGER.debug(f"Error applying theme to save button: {e}")
    
    def _apply_tick_styling(self):
        """Apply enhanced tick styling from the demo"""
        try:
            plot_item = self.getPlotItem()
            if not plot_item:
                return
            
            # Configure enhanced axis styling similar to tick demo
            axis_font = QtGui.QFont(_get_ui_font_family(), 9)
            
            for name in ('left', 'bottom'):
                axis = plot_item.getAxis(name)
                axis.setPen(pg.mkPen(color='black', width=1))
                axis.setTextPen(pg.mkPen(color='black'))
                axis.setTickFont(axis_font)
            
            # Enhanced grid with stronger alpha like the demo
            plot_item.showGrid(x=True, y=True, alpha=0.3)
            
            _LOGGER.debug("Enhanced tick styling applied to EnhancedPlotWidget")
            
        except Exception as e:
            _LOGGER.error(f"Failed to apply tick styling to EnhancedPlotWidget: {e}")
    
    def apply_enhanced_tick_styling(self, wavelength_range: Optional[tuple] = None):
        """Apply enhanced tick styling from tick demo"""
        try:
            plot_item = self.getPlotItem()
            if not plot_item:
                return
            
            # Configure enhanced axis styling similar to tick demo
            axis_font = QtGui.QFont(_get_ui_font_family(), 9)
            
            for name in ('left', 'bottom'):
                axis = plot_item.getAxis(name)
                axis.setPen(pg.mkPen(color='black', width=1))
                axis.setTextPen(pg.mkPen(color='black'))
                axis.setTickFont(axis_font)
            
            # Enhanced grid with stronger alpha like the demo
            plot_item.showGrid(x=True, y=True, alpha=0.3)
            
            # Apply custom wavelength ticks if range is provided
            if wavelength_range:
                min_wave, max_wave = wavelength_range
                # Major ticks every 1000 Å, minor every 500 Å like the demo
                major_step = 1000
                minor_step = 500
                
                # Calculate major tick positions
                start_major = int((min_wave // major_step + 1) * major_step)
                end_major = int((max_wave // major_step) * major_step)
                major_ticks = [(w, f"{w}") for w in range(start_major, end_major + 1, major_step)]
                
                # Calculate minor tick positions (excluding major tick positions)
                start_minor = int((min_wave // minor_step + 1) * minor_step)
                end_minor = int((max_wave // minor_step) * minor_step)
                minor_ticks = [(w, "") for w in range(start_minor, end_minor + 1, minor_step) 
                               if w % major_step != 0]
                
                plot_item.getAxis('bottom').setTicks([major_ticks, minor_ticks])
            
            _LOGGER.debug("Enhanced tick styling applied successfully")
            
        except Exception as e:
            _LOGGER.error(f"Failed to apply enhanced tick styling: {e}")

    