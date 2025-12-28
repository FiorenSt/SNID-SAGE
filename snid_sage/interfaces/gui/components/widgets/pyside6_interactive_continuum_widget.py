"""
PySide6 Interactive Continuum Widget Module
==========================================

Handles interactive continuum editing functionality for PySide6 preprocessing dialogs.
Uses PyQtGraph's PolyLineROI for reliable mouse interaction and real-time continuum updates.

Features:
- Interactive continuum point editing using PolyLineROI
- Real-time continuum updates with smooth interpolation
- Visual feedback and state management
- Simple and robust mouse interaction
"""

import numpy as np
from typing import List, Tuple, Optional, Callable, Dict, Any
from PySide6 import QtWidgets, QtCore, QtGui

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
    _LOGGER = get_logger('gui.pyside6_interactive_continuum')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_interactive_continuum')


class PySide6InteractiveContinuumWidget(QtCore.QObject):
    """
    Handles interactive continuum editing functionality for PySide6 preprocessing dialogs
    
    This widget uses PyQtGraph's PolyLineROI for reliable interactive continuum editing,
    allowing users to modify continuum values by dragging points up and down.
    """
    
    # Signals for real-time updates
    continuum_updated = QtCore.Signal(np.ndarray, np.ndarray)  # wave, continuum
    interactive_mode_changed = QtCore.Signal(bool)  # True when interactive mode is active
    
    def __init__(self, preview_calculator, plot_widget, colors: Dict[str, str]):
        """
        Initialize interactive continuum widget
        
        Args:
            preview_calculator: Calculator for mathematical operations
            plot_widget: PyQtGraph PlotWidget for interaction
            colors: Color scheme dictionary
        """
        super().__init__()
        
        self.preview_calculator = preview_calculator
        self.plot_widget = plot_widget
        self.colors = colors
        
        # Interactive state
        self.interactive_mode = False
        self.manual_continuum = None  # Full continuum array matching wavelength grid
        self.wave_grid = None  # Wavelength grid
        self.original_continuum = None  # Store original fitted continuum for reset
        
        # PolyLineROI for interactive editing
        self.roi = None

        # Editable region on the full grid (set when ROI is created)
        self._editable_slice: Optional[slice] = None
        
        # Additional state
        self._current_method: str = "spline"  # Only spline supported
        self._has_manual_changes: bool = False
        
        # Callbacks
        self.update_callback = None
        
        # UI Components for controls
        self.controls_frame = None
        
        # Colors for continuum visualization
        self.continuum_color = QtGui.QColor(255, 0, 0)  # Red for continuum line
        

    
    def set_update_callback(self, callback: Callable):
        """
        Set callback function to call when continuum is updated
        
        Args:
            callback: Function to call on continuum updates
        """
        self.update_callback = callback
    
    def create_interactive_controls(self, parent_frame: QtWidgets.QFrame) -> QtWidgets.QFrame:
        """
        Create UI controls for interactive continuum editing
        
        Args:
            parent_frame: Parent frame to contain controls
            
        Returns:
            Frame containing interactive controls
        """
        self.controls_frame = QtWidgets.QFrame(parent_frame)
        layout = QtWidgets.QVBoxLayout(self.controls_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Interactive continuum editing section
        interactive_group = QtWidgets.QGroupBox("Interactive Continuum Editing")
        interactive_layout = QtWidgets.QVBoxLayout(interactive_group)
        
        # Control buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        
        # Enable/Disable button
        self.toggle_button = QtWidgets.QPushButton("Enable Editing")
        self.toggle_button.clicked.connect(self.toggle_interactive_mode)
        self.toggle_button.setToolTip("Drag the square handles to modify continuum points.\nClick on the red dashed line to add a new handle at that position.")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('accent', '#3b82f6')};
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.colors.get('accent_dark', '#2563eb')};
            }}
        """)
        buttons_layout.addWidget(self.toggle_button)
        
        # Reset button
        reset_button = QtWidgets.QPushButton("Reset")
        reset_button.clicked.connect(self.reset_to_fitted_continuum)
        reset_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('warning', '#f59e0b')};
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #d97706;
            }}
        """)
        buttons_layout.addWidget(reset_button)
        
        interactive_layout.addLayout(buttons_layout)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Interactive mode disabled")
        self.status_label.setStyleSheet("color: #64748b; font-size: 10pt;")
        interactive_layout.addWidget(self.status_label)
        
        # Instructions - REMOVED: Now using tooltip instead
        
        layout.addWidget(interactive_group)
        
        # Edge handling note
        note_group = QtWidgets.QGroupBox("Note")
        note_layout = QtWidgets.QVBoxLayout(note_group)
        # Add generous margins so longer notes fit comfortably
        try:
            note_layout.setContentsMargins(10, 12, 10, 14)
        except Exception:
            pass
        
        note_text = QtWidgets.QLabel(
            "💡 Don't worry about spectrum edges or masked regions (e.g., telluric) during continuum editing.\n"
            "They are excluded from the fit and will be properly handled/zeroed in the apodization step."
        )
        note_text.setStyleSheet("color: #64748b; font-style: italic; font-size: 10pt;")
        note_text.setWordWrap(True)
        note_layout.addWidget(note_text)
        # Add extra vertical space to ensure the note doesn't feel cramped
        try:
            note_layout.addSpacing(8)
        except Exception:
            pass
        
        layout.addWidget(note_group)
        
        return self.controls_frame
    
    def toggle_interactive_mode(self):
        """Toggle interactive continuum editing mode"""
        if self.interactive_mode:
            self.disable_interactive_mode()
        else:
            self.enable_interactive_mode()
    
    def enable_interactive_mode(self):
        """Enable interactive continuum editing"""
        if not PYQTGRAPH_AVAILABLE:
            QtWidgets.QMessageBox.warning(
                None, 
                "Feature Unavailable", 
                "Interactive continuum editing requires PyQtGraph.\n"
                "Please install PyQtGraph: pip install pyqtgraph"
            )
            return
        
        if not self.plot_widget:
            QtWidgets.QMessageBox.warning(
                None,
                "Plot Not Ready", 
                "Plot widget is not available for interactive continuum editing."
            )
            return
        
        self.interactive_mode = True

        # Tell the preview calculator we are in manual continuum mode (prevents accidental overwrites)
        try:
            setattr(self.preview_calculator, "manual_continuum_active", True)
        except Exception:
            pass
        
        # Update button appearance
        self.toggle_button.setText("Stop Editing")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('danger', '#ef4444')};
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
        """)
        
        # Update status
        self.status_label.setText("Interactive mode enabled - drag to modify continuum")
        self.status_label.setStyleSheet("color: #22c55e; font-size: 10pt; font-weight: bold;")
        
        # Get the current stored continuum when enabling interactive mode
        try:
            wave, current_continuum = self.preview_calculator.get_continuum_from_fit()
            if len(current_continuum) > 0:
                self.wave_grid = wave.copy()
                self.manual_continuum = current_continuum.copy()
                self.original_continuum = current_continuum.copy()
                self._has_manual_changes = False
            else:
                self.reset_to_fitted_continuum()
        except Exception as e:
            self.reset_to_fitted_continuum()
        
        # Create PolyLineROI for interactive editing
        self._create_interactive_roi()
        
        # Emit signal
        self.interactive_mode_changed.emit(True)
        
        # Trigger update
        self._trigger_update()
    
    def disable_interactive_mode(self):
        """Disable interactive continuum editing"""
        self.interactive_mode = False

        # Release manual-continuum lock on the preview calculator
        try:
            setattr(self.preview_calculator, "manual_continuum_active", False)
        except Exception:
            pass
        
        # Update button appearance
        self.toggle_button.setText("Enable Editing")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('accent', '#3b82f6')};
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.colors.get('accent_dark', '#2563eb')};
            }}
        """)
        
        # Update status
        self.status_label.setText("Interactive mode disabled")
        self.status_label.setStyleSheet("color: #64748b; font-size: 10pt;")
        
        # Remove ROI
        self._clear_interactive_roi()
        
        # Emit signal
        self.interactive_mode_changed.emit(False)
    
    def _create_interactive_roi(self):
        """Create PolyLineROI for interactive continuum editing"""
        if self.wave_grid is None or self.manual_continuum is None:
            return
        
        # Clear existing ROI
        self._clear_interactive_roi()
        
        # Get current spectrum flux to determine where spectrum is non-zero
        current_wave, current_flux = self.preview_calculator.get_current_state()
        if current_wave is None or current_flux is None:
            return
        
        # Find first and last VALID data bins in the SPECTRUM (not continuum) to define the editable region.
        # Use non-zero finite, not "flux > 0" — filtering/log steps can produce negative values.
        spectrum_valid_mask = (current_flux != 0) & np.isfinite(current_flux)
        if not np.any(spectrum_valid_mask):
            return
        
        spectrum_valid_indices = np.where(spectrum_valid_mask)[0]
        first_nonzero = int(spectrum_valid_indices[0])
        last_nonzero = int(spectrum_valid_indices[-1])

        # Store for later interpolation so we keep 0-continuum outside the observed region
        self._editable_slice = slice(first_nonzero, last_nonzero + 1)
        
        # Use the spectrum nonzero region for ROI (from first to last nonzero point)
        wave_roi = self.wave_grid[self._editable_slice]
        continuum_roi = self.manual_continuum[self._editable_slice]
        
        if len(wave_roi) < 2:
            return  # Not enough points
        
        # Downsample for performance while maintaining shape
        if len(wave_roi) > 50:
            step = max(1, len(wave_roi) // 20)  # Target around 20 control points
            indices = np.arange(0, len(wave_roi), step)
            # Always include first and last points
            if indices[0] != 0:
                indices = np.insert(indices, 0, 0)
            if indices[-1] != len(wave_roi) - 1:
                indices = np.append(indices, len(wave_roi) - 1)
        else:
            indices = np.arange(len(wave_roi))
        
        # Create list of (x, y) tuples for PolyLineROI
        pts = list(zip(wave_roi[indices], continuum_roi[indices]))
        
        # Create PolyLineROI with red dashed line and custom handle styling
        self.roi = pg.PolyLineROI(pts, closed=False, removable=False)
        
        # Style the ROI with red dashed line
        self.roi.setPen(pg.mkPen(color='red', width=2, style=QtCore.Qt.DashLine))
        
        # Configure handle appearance - set defaults for all handles (current and future)
        handle_pen = pg.mkPen(color='blue', width=2)
        handle_brush = pg.mkBrush(color='lightblue', alpha=200)
        handle_radius = 6
        
        # Set the default handle style for the ROI (affects new handles too)
        self.roi.handlePen = handle_pen
        self.roi.handleBrush = handle_brush
        self.roi.handleSize = handle_radius
        
        # Apply styling to existing handles
        for handle in self.roi.getHandles():
            handle.pen = handle_pen
            handle.brush = handle_brush
            handle.radius = handle_radius
            # Set both normal and hover states to the same appearance
            handle.currentPen = handle_pen
            handle.currentBrush = handle_brush
            handle.buildPath()  # Refresh the handle appearance
        
        # Override the ROI's addHandle method to ensure new handles get proper styling
        original_addHandle = self.roi.addHandle
        def styled_addHandle(*args, **kwargs):
            handle = original_addHandle(*args, **kwargs)
            if handle:
                handle.pen = handle_pen
                handle.brush = handle_brush
                handle.radius = handle_radius
                handle.currentPen = handle_pen
                handle.currentBrush = handle_brush
                handle.buildPath()
            return handle
        self.roi.addHandle = styled_addHandle
        
        # Connect to ROI's change signal
        self.roi.sigRegionChanged.connect(self._update_continuum)
        
        # Add to view
        vb = self.plot_widget.getPlotItem().getViewBox()
        vb.addItem(self.roi)
        
        # Initial update to ensure consistency
        self._update_continuum()
    
    def _clear_interactive_roi(self):
        """Clear the interactive ROI and related items"""
        if self.roi:
            try:
                self.roi.sigRegionChanged.disconnect(self._update_continuum)
            except:
                pass  # Signal might not be connected
            
            vb = self.plot_widget.getPlotItem().getViewBox()
            vb.removeItem(self.roi)
            self.roi = None
    
    def _update_continuum(self):
        """Update continuum from ROI vertices - core logic from the demo"""
        if not self.roi or self.wave_grid is None:
            return
        
        try:
            # Get ROI vertices in data coordinates
            pts = self.roi.getState()['points']
            if len(pts) < 2:
                return
            
            # Extract x and y coordinates
            roi_x = np.array([pt[0] for pt in pts])
            roi_y = np.array([pt[1] for pt in pts])

            # Drop non-finite points and sort by wavelength (np.interp requires increasing x)
            finite = np.isfinite(roi_x) & np.isfinite(roi_y)
            roi_x = roi_x[finite]
            roi_y = roi_y[finite]
            if roi_x.size < 2:
                return
            order = np.argsort(roi_x)
            roi_x = roi_x[order]
            roi_y = roi_y[order]

            # Merge duplicate x values (can happen if handles overlap)
            xs: list[float] = []
            ys_groups: list[list[float]] = []
            for x, y in zip(roi_x.tolist(), roi_y.tolist()):
                if not xs or x != xs[-1]:
                    xs.append(float(x))
                    ys_groups.append([float(y)])
                else:
                    ys_groups[-1].append(float(y))
            roi_x_u = np.asarray(xs, dtype=float)
            roi_y_u = np.asarray([float(np.mean(g)) for g in ys_groups], dtype=float)
            if roi_x_u.size < 2:
                return

            # Interpolate ONLY over the editable region; keep continuum=0 outside observed data.
            editable = self._editable_slice if self._editable_slice is not None else slice(None)
            cont = np.zeros_like(self.wave_grid, dtype=float)
            wv = np.asarray(self.wave_grid[editable], dtype=float)
            interp = np.interp(wv, roi_x_u, roi_y_u, left=float(roi_y_u[0]), right=float(roi_y_u[-1]))
            # Continuum must stay positive to be meaningful; floor tiny values.
            eps = 1e-30
            interp = np.where(np.isfinite(interp), interp, 0.0)
            interp = np.maximum(interp, eps)
            cont[editable] = interp
            self.manual_continuum = cont

            # Keep preview calculator's continuum in sync so finishing/reconstruction uses the manual continuum.
            try:
                self.preview_calculator.stored_continuum = cont.copy()
            except Exception:
                pass
            
            # Mark that we have manual changes
            self._has_manual_changes = True
            
            # Trigger callback for preview updates
            self._trigger_update()
            
        except Exception as e:
            _LOGGER.error(f"Error updating continuum from ROI: {e}")
    
    def reset_to_fitted_continuum(self):
        """Reset continuum to original fitted values"""
        try:
            # Recalculate the continuum instead of using stored values
            # Ensures the fitted continuum follows the current spectrum
            current_wave, current_flux = self.preview_calculator.get_current_state()
            method = getattr(self, '_current_method', 'spline')
            
            # Calculate fresh continuum using the current method
            if method == "spline":
                # Use last known knotnum or default
                knotnum = getattr(self, '_last_knotnum', 13)
                flat_flux, fitted_continuum = self.preview_calculator._fit_continuum_improved(current_flux, method="spline", knotnum=knotnum)
            else:
                # Fallback
                fitted_continuum = np.ones_like(current_flux)
            
            if len(fitted_continuum) > 0:
                self.wave_grid = current_wave.copy()
                # For reset, use full continuum for calculations (no edge removal)
                self.manual_continuum = fitted_continuum.copy()
                self.original_continuum = fitted_continuum.copy()
                self._has_manual_changes = False
                
                # Store in preview calculator for consistency (use full continuum for calculations)
                self.preview_calculator.stored_continuum = fitted_continuum.copy()
                
                # If in interactive mode, recreate ROI with new points
                if self.interactive_mode:
                    self._create_interactive_roi()
                
                # Trigger update
                self._trigger_update()
                
                _LOGGER.debug(f"Reset continuum to fitted values using {method}, range: {np.min(fitted_continuum):.3f} - {np.max(fitted_continuum):.3f}")
                
        except Exception as e:
            _LOGGER.error(f"Error resetting continuum: {e}")
            # Create unity continuum as fallback
            try:
                current_wave, current_flux = self.preview_calculator.get_current_state()
                unity_continuum = np.ones_like(current_flux)
                
                self.wave_grid = current_wave.copy()
                self.manual_continuum = unity_continuum.copy()
                self.original_continuum = unity_continuum.copy()
                self._has_manual_changes = False
                _LOGGER.warning("Reset to unity continuum as fallback")
            except:
                pass
    
    def has_manual_changes(self) -> bool:
        """Check if the continuum has been manually modified"""
        return self._has_manual_changes
    
    def set_current_method(self, method: str):
        """Set the current continuum fitting method"""
        self._current_method = method
    
    def update_continuum_from_fit(self, parameter_value):
        """
        Update continuum from current method and parameters
        
        Args:
            parameter_value: knotnum for spline (None for default)
        """
        try:
            # Get current spectrum state
            current_wave, current_flux = self.preview_calculator.get_current_state()
            
            # Determine method
            method = getattr(self, '_current_method', 'spline')
            
            # Calculate the continuum from the current spectrum state
            if method == "spline":
                knotnum = parameter_value if parameter_value is not None else 13
                flat_flux, continuum = self.preview_calculator._fit_continuum_improved(current_flux, method="spline", knotnum=knotnum)
                self._last_knotnum = knotnum
            else:
                # Fallback: unity continuum
                continuum = np.ones_like(current_flux)
            
            # Store the continuum arrays - use full continuum for calculations
            self.wave_grid = current_wave.copy()
            self.manual_continuum = continuum.copy()
            self.original_continuum = continuum.copy()
            self._has_manual_changes = False
            
            # Store in preview calculator for consistency (use full continuum for calculations)
            self.preview_calculator.stored_continuum = continuum.copy()
            
            # Update visualization if in interactive mode
            if self.interactive_mode:
                self._create_interactive_roi()  # Recreate ROI with new continuum
            
            # Trigger update
            self._trigger_update()
            
            _LOGGER.debug(f"Continuum updated from fit using {method} method, continuum range: {np.min(continuum):.3f} - {np.max(continuum):.3f}")
            
        except Exception as e:
            _LOGGER.error(f"Error updating continuum from fit: {e}")
            # Fallback: try to create unity continuum
            try:
                current_wave, current_flux = self.preview_calculator.get_current_state()
                unity_continuum = np.ones_like(current_flux)
                
                self.wave_grid = current_wave.copy()
                self.manual_continuum = unity_continuum.copy()
                self.original_continuum = unity_continuum.copy()
                self._has_manual_changes = False
                _LOGGER.warning("Falling back to unity continuum")
            except:
                pass 
    
    def _trigger_update(self):
        """Trigger update callback"""
        if self.update_callback:
            self.update_callback()
        
        # Emit signal
        if self.wave_grid is not None and self.manual_continuum is not None:
            self.continuum_updated.emit(self.wave_grid, self.manual_continuum)
    
    # Public interface methods required by preprocessing dialog
    
    def is_interactive_mode(self) -> bool:
        """Check if interactive mode is active"""
        return self.interactive_mode
    
    def get_continuum_points(self) -> List[Tuple[float, float]]:
        """Get current continuum points for visualization (from first to last nonzero points)"""
        if self.wave_grid is None or self.manual_continuum is None:
            return []
        
        # Get current spectrum flux to determine where spectrum is non-zero
        current_wave, current_flux = self.preview_calculator.get_current_state()
        if current_wave is None or current_flux is None:
            return []
        
        # Find valid observed region in the SPECTRUM (not continuum)
        spectrum_valid_mask = (current_flux != 0) & np.isfinite(current_flux)
        if not np.any(spectrum_valid_mask):
            return []
        
        spectrum_valid_indices = np.where(spectrum_valid_mask)[0]
        first_nonzero = int(spectrum_valid_indices[0])
        last_nonzero = int(spectrum_valid_indices[-1])
        
        # Use the spectrum nonzero region (from first to last nonzero point)
        wave_plot = self.wave_grid[first_nonzero:last_nonzero+1]
        continuum_plot = self.manual_continuum[first_nonzero:last_nonzero+1]
        
        return list(zip(wave_plot, continuum_plot))
    
    def get_manual_continuum_array(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get the manual continuum array (full grid including zero edges)"""
        if self.wave_grid is None or self.manual_continuum is None:
            return np.array([]), np.array([])
        
        return self.wave_grid.copy(), self.manual_continuum.copy()
    
    def get_preview_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get preview data with continuum applied"""
        if self.preview_calculator and self.manual_continuum is not None:
            # Calculate flattened spectrum using manual continuum
            return self.preview_calculator._calculate_manual_continuum_preview(self.manual_continuum)
        else:
            return self.preview_calculator.get_current_state() if self.preview_calculator else (np.array([]), np.array([]))
    
    def set_manual_continuum(self, wave_grid: np.ndarray, manual_continuum: np.ndarray):
        """Set manual continuum from external source"""
        if len(wave_grid) > 0 and len(manual_continuum) > 0:
            self.wave_grid = wave_grid.copy()
            self.manual_continuum = manual_continuum.copy()
            self._has_manual_changes = True

            # Best-effort: infer editable slice from current spectrum validity
            try:
                current_wave, current_flux = self.preview_calculator.get_current_state()
                if current_flux is not None and len(current_flux) == len(self.wave_grid):
                    valid = (np.asarray(current_flux) != 0) & np.isfinite(np.asarray(current_flux))
                    if np.any(valid):
                        idx = np.where(valid)[0]
                        self._editable_slice = slice(int(idx[0]), int(idx[-1]) + 1)
            except Exception:
                pass

            # Keep preview calculator continuum in sync (finish/reconstruction path uses stored_continuum)
            try:
                self.preview_calculator.stored_continuum = self.manual_continuum.copy()
            except Exception:
                pass
            
            # Update ROI if in interactive mode
            if self.interactive_mode:
                self._create_interactive_roi()
            
            # Trigger update
            self._trigger_update()
            
            _LOGGER.debug("Manual continuum set from external source") 