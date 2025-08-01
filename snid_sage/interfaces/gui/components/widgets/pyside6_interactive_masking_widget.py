"""
PySide6 Interactive Masking Widget Module
========================================

Handles interactive masking functionality for PySide6 preprocessing dialogs.
Manages mouse events, region selection, and real-time masking updates using PyQtGraph.

Features:
- Interactive region selection using PyQtGraph
- Mouse event handling (click, drag)
- Real-time mask region updates
- Visual feedback and state management
- Mask region management (add, remove, clear)
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
    _LOGGER = get_logger('gui.pyside6_interactive_masking')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_interactive_masking')


class PySide6InteractiveMaskingWidget(QtCore.QObject):
    """
    Handles interactive masking functionality for PySide6 preprocessing dialogs
    
    This widget manages interactive region selection using PyQtGraph,
    allowing users to drag and select wavelength regions for masking.
    """
    
    # Signals for real-time updates
    mask_regions_updated = QtCore.Signal(list)  # List of (start, end) tuples
    masking_mode_changed = QtCore.Signal(bool)  # True when masking is active
    
    def __init__(self, plot_widget, colors: Dict[str, str]):
        """
        Initialize interactive masking widget
        
        Args:
            plot_widget: PyQtGraph PlotWidget for interaction
            colors: Color scheme dictionary
        """
        super().__init__()
        
        self.plot_widget = plot_widget
        self.colors = colors
        
        # Masking state
        self.masking_active = False
        self.mask_regions = []  # List of (start, end) tuples
        
        # Visual elements
        self.mask_fill_items = []  # Visual representations of mask regions
        
        # Interaction state
        self.selection_start = None
        self.selection_item = None  # Current selection visual
        
        # Event connections
        self.mouse_press_connection = None
        self.mouse_move_connection = None
        
        # Callbacks
        self.update_callback = None  # Called when mask regions change
        
        # UI Components for controls
        self.controls_frame = None
        
        # Colors for masking visualization
        self.mask_color = QtGui.QColor(255, 100, 100, 100)  # Semi-transparent red
        self.selection_color = QtGui.QColor(255, 150, 150, 150)  # Lighter red for selection
    
    def set_update_callback(self, callback: Callable):
        """
        Set callback function to call when mask regions are updated
        
        Args:
            callback: Function to call on mask region updates
        """
        self.update_callback = callback
    
    def create_masking_controls(self, parent_frame: QtWidgets.QFrame) -> QtWidgets.QFrame:
        """
        Create UI controls for interactive masking
        
        Args:
            parent_frame: Parent frame to contain controls
            
        Returns:
            Frame containing masking controls
        """
        self.controls_frame = QtWidgets.QFrame(parent_frame)
        layout = QtWidgets.QVBoxLayout(self.controls_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Interactive masking section
        interactive_group = QtWidgets.QGroupBox("Interactive Masking")
        interactive_layout = QtWidgets.QVBoxLayout(interactive_group)
        
        # Toggle button
        self.toggle_button = QtWidgets.QPushButton("🎯 Start Interactive Masking")
        self.toggle_button.clicked.connect(self.toggle_masking_mode)
        self.toggle_button.setToolTip("Click on start and end points for selecting a region to mask.\nRed shading shows masked regions.")
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
        interactive_layout.addWidget(self.toggle_button)
        
        # Instructions - REMOVED: Now using tooltip instead
        
        layout.addWidget(interactive_group)
        
        # Manual input section
        manual_group = QtWidgets.QGroupBox("Manual Mask Input")
        manual_layout = QtWidgets.QVBoxLayout(manual_group)
        
        # Input fields
        input_layout = QtWidgets.QHBoxLayout()
        
        input_layout.addWidget(QtWidgets.QLabel("Start:"))
        self.start_input = QtWidgets.QDoubleSpinBox()
        self.start_input.setRange(0, 99999)
        self.start_input.setDecimals(2)
        input_layout.addWidget(self.start_input)
        
        input_layout.addWidget(QtWidgets.QLabel("End:"))
        self.end_input = QtWidgets.QDoubleSpinBox()
        self.end_input.setRange(0, 99999)
        self.end_input.setDecimals(2)
        input_layout.addWidget(self.end_input)
        
        add_button = QtWidgets.QPushButton("Add")
        add_button.clicked.connect(self.add_mask_from_input)
        add_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('success', '#22c55e')};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
            }}
        """)
        input_layout.addWidget(add_button)
        
        manual_layout.addLayout(input_layout)
        layout.addWidget(manual_group)
        
        # Management buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        remove_button = QtWidgets.QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_mask)
        remove_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('warning', '#f59e0b')};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
            }}
        """)
        button_layout.addWidget(remove_button)
        
        clear_button = QtWidgets.QPushButton("Clear All")
        clear_button.clicked.connect(self.clear_all_masks)
        clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors.get('danger', '#ef4444')};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
            }}
        """)
        button_layout.addWidget(clear_button)
        
        layout.addLayout(button_layout)
        
        # Current masks list
        masks_group = QtWidgets.QGroupBox("Current Mask Regions")
        masks_layout = QtWidgets.QVBoxLayout(masks_group)
        
        self.masks_list = QtWidgets.QListWidget()
        self.masks_list.setMaximumHeight(100)
        masks_layout.addWidget(self.masks_list)
        
        layout.addWidget(masks_group)
        
        return self.controls_frame
    
    def toggle_masking_mode(self):
        """Toggle interactive masking mode"""
        if self.masking_active:
            self.stop_masking_mode()
        else:
            self.start_masking_mode()
    
    def start_masking_mode(self):
        """Start interactive masking mode"""
        if not PYQTGRAPH_AVAILABLE:
            QtWidgets.QMessageBox.warning(
                None, 
                "Feature Unavailable", 
                "Interactive masking requires PyQtGraph.\n"
                "Please install PyQtGraph: pip install pyqtgraph"
            )
            return
        
        if not self.plot_widget:
            QtWidgets.QMessageBox.warning(
                None,
                "Plot Not Ready",
                "Plot widget is not available for interactive masking."
            )
            return
        
        self.masking_active = True
        
        # Update button
        self.toggle_button.setText("🔴 Stop Interactive Masking")
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
        
        # Connect mouse events
        self._connect_mouse_events()
        
        # Emit signal
        self.masking_mode_changed.emit(True)
        
        _LOGGER.info("Interactive masking mode started")
    
    def stop_masking_mode(self):
        """Stop interactive masking mode"""
        self.masking_active = False
        
        # Update button
        self.toggle_button.setText("🎯 Start Interactive Masking")
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
        
        # Disconnect mouse events
        self._disconnect_mouse_events()
        self._disconnect_drag_events()
        
        # Clear any active selection
        if self.selection_item:
            self.plot_widget.removeItem(self.selection_item)
            self.selection_item = None
        
        # Reset selection state
        self.selection_start = None
        
        # Emit signal
        self.masking_mode_changed.emit(False)
        
        _LOGGER.info("Interactive masking mode stopped")
    
    def _connect_mouse_events(self):
        """Connect mouse events for interactive selection"""
        if self.plot_widget:
            self.mouse_press_connection = self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_press)
            # Note: PyQtGraph doesn't have separate mouse move events, we'll handle in press/release
    
    def _disconnect_mouse_events(self):
        """Disconnect mouse events"""
        if self.mouse_press_connection:
            self.plot_widget.scene().sigMouseClicked.disconnect(self._on_mouse_press)
            self.mouse_press_connection = None
    
    def _on_mouse_press(self, event):
        """Handle mouse press events for interactive masking"""
        if not self.masking_active:
            return
        
        # Only handle left mouse button clicks (not drags)
        if event.button() != QtCore.Qt.LeftButton:
            return
        
        # Get the mouse position in data coordinates
        pos = event.scenePos()
        if self.plot_widget.plotItem.vb.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_coord = mouse_point.x()
            
            # Check if this is a double-click for completion
            if event.double():
                # Double-click: complete current selection and add mask
                if self.selection_start is not None:
                    end_coord = x_coord
                    start_coord = self.selection_start
                    
                    # Ensure proper order
                    if start_coord > end_coord:
                        start_coord, end_coord = end_coord, start_coord
                    
                    # Add mask region if it has reasonable width
                    if abs(end_coord - start_coord) > 1.0:  # Minimum width threshold
                        self.add_mask_region(start_coord, end_coord)
                    
                    # Reset selection
                    self._clear_selection_visual()
                    self.selection_start = None
            else:
                # Single click: start or update selection
                if self.selection_start is None:
                    # Start new selection
                    self.selection_start = x_coord
                    self._create_selection_visual(x_coord, x_coord)
                    
                    # Connect mouse move events for drag selection
                    self.mouse_move_connection = self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_move)
                    # Note: PyQtGraph GraphicsScene doesn't have sigMouseReleased, use sigMouseClicked for completion
                else:
                    # Complete selection on second click
                    end_coord = x_coord
                    start_coord = self.selection_start
                    
                    # Ensure proper order
                    if start_coord > end_coord:
                        start_coord, end_coord = end_coord, start_coord
                    
                    # Add mask region if it has reasonable width
                    if abs(end_coord - start_coord) > 1.0:  # Minimum width threshold
                        self.add_mask_region(start_coord, end_coord)
                    
                    # Reset selection
                    self._clear_selection_visual()
                    self.selection_start = None
                    self._disconnect_drag_events()
    
    def _on_mouse_move(self, pos):
        """Handle mouse move events for drag selection"""
        if not self.masking_active or self.selection_start is None:
            return
        
        # Get mouse position in data coordinates
        if self.plot_widget.plotItem.vb.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_coord = mouse_point.x()
            
            # Update selection visual
            self._update_selection_visual(self.selection_start, x_coord)
    

    
    def _disconnect_drag_events(self):
        """Disconnect mouse move events"""
        if self.mouse_move_connection:
            try:
                self.plot_widget.scene().sigMouseMoved.disconnect(self._on_mouse_move)
            except (RuntimeError, TypeError):
                # Connection might already be disconnected or object deleted
                pass
            self.mouse_move_connection = None
    
    def _create_selection_visual(self, start_x: float, end_x: float):
        """Create visual representation of current selection"""
        if self.selection_item:
            self.plot_widget.removeItem(self.selection_item)
        
        # Create a semi-transparent rectangle for the selection
        self.selection_item = pg.LinearRegionItem(
            values=[start_x, end_x],
            brush=self.selection_color,
            movable=False
        )
        self.plot_widget.addItem(self.selection_item)
    
    def _update_selection_visual(self, start_x: float, end_x: float):
        """Update visual representation of current selection during drag"""
        if self.selection_item:
            # Ensure proper order for visual
            if start_x > end_x:
                start_x, end_x = end_x, start_x
            self.selection_item.setRegion([start_x, end_x])
        else:
            self._create_selection_visual(start_x, end_x)
    
    def _clear_selection_visual(self):
        """Clear the current selection visual"""
        if self.selection_item:
            self.plot_widget.removeItem(self.selection_item)
            self.selection_item = None
    
    def add_mask_region(self, start: float, end: float):
        """Add a new mask region"""
        # Ensure proper order
        if start > end:
            start, end = end, start
        
        # Add to mask regions list
        self.mask_regions.append((start, end))
        
        # Create visual representation
        self._create_mask_visual(start, end)
        
        # Update UI
        self._update_masks_list()
        
        # Trigger callback
        if self.update_callback:
            self.update_callback()
        
        # Emit signal
        self.mask_regions_updated.emit(self.mask_regions)
        
        _LOGGER.debug(f"Added mask region: {start:.2f} - {end:.2f}")
    
    def _create_mask_visual(self, start: float, end: float):
        """Create visual representation of a mask region"""
        mask_item = pg.LinearRegionItem(
            values=[start, end],
            brush=self.mask_color,
            movable=False
        )
        self.plot_widget.addItem(mask_item)
        self.mask_fill_items.append(mask_item)
    
    def add_mask_from_input(self):
        """Add mask region from manual input fields"""
        try:
            start = self.start_input.value()
            end = self.end_input.value()
            
            if start >= end:
                QtWidgets.QMessageBox.warning(
                    None,
                    "Invalid Range",
                    "Start wavelength must be less than end wavelength."
                )
                return
            
            self.add_mask_region(start, end)
            
            # Clear input fields
            self.start_input.setValue(0)
            self.end_input.setValue(0)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                None,
                "Error",
                f"Failed to add mask region: {str(e)}"
            )
    
    def remove_selected_mask(self):
        """Remove the selected mask region"""
        current_row = self.masks_list.currentRow()
        if current_row >= 0 and current_row < len(self.mask_regions):
            # Remove from data
            del self.mask_regions[current_row]
            
            # Remove visual
            if current_row < len(self.mask_fill_items):
                item = self.mask_fill_items.pop(current_row)
                self.plot_widget.removeItem(item)
            
            # Update UI
            self._update_masks_list()
            
            # Trigger callback
            if self.update_callback:
                self.update_callback()
            
            # Emit signal
            self.mask_regions_updated.emit(self.mask_regions)
    
    def clear_all_masks(self):
        """Clear all mask regions"""
        # Clear data
        self.mask_regions.clear()
        
        # Clear visuals
        for item in self.mask_fill_items:
            self.plot_widget.removeItem(item)
        self.mask_fill_items.clear()
        
        # Update UI
        self._update_masks_list()
        
        # Trigger callback
        if self.update_callback:
            self.update_callback()
        
        # Emit signal
        self.mask_regions_updated.emit(self.mask_regions)
        
        _LOGGER.info("All mask regions cleared")
    
    def _update_masks_list(self):
        """Update the masks list widget"""
        try:
            # Check if the masks_list widget still exists and is valid
            if hasattr(self, 'masks_list') and self.masks_list is not None:
                # Use sip.isdeleted to check if the C++ object still exists
                try:
                    from sip import isdeleted
                    if not isdeleted(self.masks_list):
                        self.masks_list.clear()
                        for i, (start, end) in enumerate(self.mask_regions):
                            self.masks_list.addItem(f"Mask {i+1}: {start:.2f} - {end:.2f} Å")
                except ImportError:
                    # Fallback if sip is not available
                    try:
                        self.masks_list.clear()
                        for i, (start, end) in enumerate(self.mask_regions):
                            self.masks_list.addItem(f"Mask {i+1}: {start:.2f} - {end:.2f} Å")
                    except RuntimeError:
                        # Object has been deleted
                        pass
        except (RuntimeError, AttributeError):
            # Widget has been deleted or doesn't exist, skip updating
            pass
    
    def get_mask_regions(self) -> List[Tuple[float, float]]:
        """Get current mask regions"""
        return self.mask_regions.copy()
    
    def stop_masking_mode(self):
        """Stop masking mode and clean up any active selection"""
        if self.masking_active:
            self.masking_active = False
            
            # Clear any active selection
            self._clear_selection_visual()
            self.selection_start = None
            
            # Disconnect events
            self._disconnect_drag_events()
            if self.mouse_press_connection:
                try:
                    self.plot_widget.scene().sigMouseClicked.disconnect(self._on_mouse_press)
                except (RuntimeError, TypeError):
                    pass
                self.mouse_press_connection = None
            
            # Emit signal
            self.masking_mode_changed.emit(False)
            
            _LOGGER.debug("Interactive masking mode stopped")
    
    def set_mask_regions(self, mask_regions: List[Tuple[float, float]]):
        """Set mask regions programmatically"""
        # Clear existing
        self.clear_all_masks()
        
        # Add new regions
        for start, end in mask_regions:
            self.add_mask_region(start, end)
    
    def refresh_visuals(self):
        """Refresh all mask visuals (useful after plot updates)"""
        # Clear existing visuals
        for item in self.mask_fill_items:
            self.plot_widget.removeItem(item)
        self.mask_fill_items.clear()
        
        # Recreate visuals
        for start, end in self.mask_regions:
            self._create_mask_visual(start, end) 