"""
Template Manager Layout Manager
==============================

Layout management system for the SNID Template Manager GUI.
This module provides consistent, configurable layout control specifically
for template management operations while maintaining compatibility with
the main SNID-SAGE GUI layout system.

Key Features:
- Template-specific layout configurations
- Consistent sizing and spacing
- Platform compatibility
- Integration with main GUI layout system
- Twemoji icon support

Developed by Fiorenzo Stoppa for SNID SAGE
"""

import logging
from pathlib import Path
from PySide6 import QtWidgets, QtCore
from typing import Dict, Any, Optional, Tuple
import json

# Import shared UI core layout adapter to avoid coupling
try:
    from snid_sage.interfaces.ui_core import get_layout_manager as get_core_layout
    MAIN_LAYOUT_AVAILABLE = True
except Exception:
    MAIN_LAYOUT_AVAILABLE = False
    get_core_layout = None  # type: ignore

# Import Twemoji manager
try:
    from snid_sage.interfaces.gui.utils.twemoji_manager import get_twemoji_manager
    TWEMOJI_AVAILABLE = True
except ImportError:
    TWEMOJI_AVAILABLE = False

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('template_manager.layout')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('template_manager.layout')


class TemplateLayoutSettings:
    """Layout settings specific to the Template Manager"""
    
    def __init__(self):
        # === Template Manager Specific Dimensions ===
        self.template_browser_width = 220
        self.template_viewer_height = 350
        self.template_info_panel_height = 150
        self.template_control_panel_height = 60
        
        # === Splitter Settings ===
        self.main_splitter_sizes = [220, 680]  # browser : content
        self.vertical_splitter_sizes = [350, 200]  # viewer : info
        
        # === Tab Settings ===
        self.tab_height = 40
        self.tab_padding = 12
        
        # === Button Dimensions ===
        self.action_button_height = 35
        self.action_button_width = 120
        self.create_button_height = 45
        
        # === Spacing ===
        self.panel_spacing = 10
        self.widget_spacing = 5
        self.form_spacing = 8
        
        # === Margins ===
        self.main_margin = 10
        self.panel_margin = 8
        self.widget_margin = 5
        
        # === Tree Widget ===
        self.tree_item_height = 25
        self.tree_header_height = 30
        
        # === Table Widget ===
        self.table_row_height = 25
        self.table_header_height = 30
        
        # === Plot Widget ===
        self.plot_min_height = 300
        self.plot_preferred_height = 400


class TemplateManagerLayoutManager:
    """
    Layout manager for the Template Manager GUI
    
    This class provides consistent layout management specifically for
    template management operations while integrating with the main GUI.
    """
    
    def __init__(self):
        """Initialize the Template Manager layout manager"""
        self.settings = TemplateLayoutSettings()
        self._main_layout_manager = None
        
        if MAIN_LAYOUT_AVAILABLE and get_core_layout is not None:
            try:
                self._main_layout_manager = get_core_layout()
            except Exception as e:
                _LOGGER.warning(f"Could not initialize core layout manager: {e}")
        
        self.twemoji_manager = None
        if TWEMOJI_AVAILABLE:
            try:
                self.twemoji_manager = get_twemoji_manager()
            except Exception as e:
                _LOGGER.warning(f"Could not initialize twemoji manager: {e}")
    
    def setup_main_window(self, window: QtWidgets.QMainWindow) -> None:
        """Setup main window layout and properties"""
        # Set window properties
        window.setMinimumSize(700, 500)
        window.resize(950, 650)
        
        # Center window
        self._center_window(window)
        
        # Setup window icon if available
        if self._main_layout_manager:
            try:
                self._main_layout_manager.setup_main_window(window)
            except Exception as e:
                _LOGGER.warning(f"Could not setup main window with main layout manager: {e}")
    
    def _center_window(self, window: QtWidgets.QMainWindow) -> None:
        """Center the window on screen"""
        try:
            screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
            window_rect = window.frameGeometry()
            window_rect.moveCenter(screen.center())
            window.move(window_rect.topLeft())
        except Exception as e:
            _LOGGER.warning(f"Could not center window: {e}")
    
    def create_main_splitter(self) -> QtWidgets.QSplitter:
        """Create the main horizontal splitter"""
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setSizes(self.settings.main_splitter_sizes)
        splitter.setChildrenCollapsible(False)
        return splitter
    
    def create_vertical_splitter(self) -> QtWidgets.QSplitter:
        """Create a vertical splitter for content areas"""
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.setSizes(self.settings.vertical_splitter_sizes)
        splitter.setChildrenCollapsible(False)
        return splitter
    
    def setup_template_browser(self, tree_widget: QtWidgets.QTreeWidget) -> None:
        """Setup template browser tree widget"""
        tree_widget.setMinimumWidth(self.settings.template_browser_width)
        tree_widget.setHeaderHidden(False)
        
        # Set item height
        tree_widget.setUniformRowHeights(True)
        tree_widget.setIndentation(20)
        
        # Setup header
        header = tree_widget.header()
        header.setDefaultSectionSize(150)
        header.setStretchLastSection(True)
        header.setFixedHeight(self.settings.tree_header_height)
    
    def setup_template_viewer(self, widget: QtWidgets.QWidget) -> None:
        """Setup template viewer widget"""
        widget.setMinimumHeight(self.settings.plot_min_height)
        
        # Apply consistent styling
        if hasattr(widget, 'plot_widget'):
            widget.plot_widget.setMinimumHeight(self.settings.plot_min_height)
    
    def setup_tab_widget(self, tab_widget: QtWidgets.QTabWidget) -> None:
        """Setup tab widget with consistent styling"""
        tab_widget.setTabPosition(QtWidgets.QTabWidget.North)
        tab_widget.setMovable(False)
        tab_widget.setUsesScrollButtons(True)
        
        # Set tab bar properties
        tab_bar = tab_widget.tabBar()
        tab_bar.setExpanding(False)
        
        # Apply Twemoji icons if available
        if self.twemoji_manager:
            self._apply_tab_icons(tab_widget)
    
    def _apply_tab_icons(self, tab_widget: QtWidgets.QTabWidget) -> None:
        """Apply Twemoji icons to tabs"""
        try:
            # Define tab icons (only existing tabs)
            tab_icons = {
                0: "📊",  # Template Viewer
                1: "✨",  # Create Template
                2: "🔧",  # Manage Templates
            }
            
            for index, emoji in tab_icons.items():
                if index < tab_widget.count():
                    try:
                        icon = self.twemoji_manager.get_icon(emoji)  # QIcon
                    except Exception:
                        icon = None
                    if icon:
                        tab_widget.setTabIcon(index, icon)
        except Exception as e:
            _LOGGER.warning(f"Could not apply tab icons: {e}")

    def apply_tab_icons(self, tab_widget: QtWidgets.QTabWidget) -> None:
        """Public wrapper to apply Twemoji icons to existing tabs."""
        if self.twemoji_manager:
            self._apply_tab_icons(tab_widget)
    
    def setup_form_layout(self, form_layout: QtWidgets.QFormLayout) -> None:
        """Setup form layout with consistent spacing"""
        form_layout.setSpacing(self.settings.form_spacing)
        form_layout.setContentsMargins(
            self.settings.widget_margin,
            self.settings.widget_margin,
            self.settings.widget_margin,
            self.settings.widget_margin
        )
        form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
    
    def setup_group_box(self, group_box: QtWidgets.QGroupBox) -> None:
        """Setup group box with consistent styling"""
        group_box.setContentsMargins(
            self.settings.panel_margin,
            self.settings.panel_margin,
            self.settings.panel_margin,
            self.settings.panel_margin
        )
    
    def create_action_button(self, text: str, emoji: str = None) -> QtWidgets.QPushButton:
        """Create a consistently styled action button.

        Per user preference, do NOT add emoji icons to buttons that already have
        textual labels. Only attach an emoji icon when the label is empty (icon-only).
        """
        button = QtWidgets.QPushButton()

        # Always set the provided text label
        button.setText(text)

        # Only attach an emoji icon if there is no text label (icon-only button)
        if (emoji and not (text and text.strip()) and self.twemoji_manager):
            try:
                self.twemoji_manager.set_button_icon(button, emoji, keep_text=True)
            except Exception:
                pass
        
        # Set button dimensions
        button.setMinimumHeight(self.settings.action_button_height)
        button.setMinimumWidth(self.settings.action_button_width)
        
        return button
    
    def create_create_button(self, text: str = "Create Template") -> QtWidgets.QPushButton:
        """Create the main 'Create Template' button with special styling.

        Do not add emoji icons to labeled buttons.
        """
        button = QtWidgets.QPushButton(text)
        button.setMinimumHeight(self.settings.create_button_height)
        button.setObjectName("create_btn")  # For CSS styling
        
        return button
    
    def create_compare_button(self, text: str = "Compare Selected") -> QtWidgets.QPushButton:
        """Create the 'Compare' button with special styling.

        Do not add emoji icons to labeled buttons.
        """
        button = QtWidgets.QPushButton(text)
        button.setMinimumHeight(self.settings.action_button_height)
        button.setObjectName("compare_btn")  # For CSS styling
        
        return button
    
    def setup_table_widget(self, table: QtWidgets.QTableWidget) -> None:
        """Setup table widget with consistent styling"""
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
        # Set row height
        table.verticalHeader().setDefaultSectionSize(self.settings.table_row_height)
        table.verticalHeader().setVisible(False)
        
        # Set header height
        header = table.horizontalHeader()
        header.setFixedHeight(self.settings.table_header_height)
        header.setStretchLastSection(True)
    
    def apply_panel_layout(self, widget: QtWidgets.QWidget, layout: QtWidgets.QLayout) -> None:
        """Apply consistent panel layout settings"""
        layout.setSpacing(self.settings.panel_spacing)
        layout.setContentsMargins(
            self.settings.main_margin,
            self.settings.main_margin,
            self.settings.main_margin,
            self.settings.main_margin
        )
        widget.setLayout(layout)
    
    def get_setting(self, setting_name: str) -> Any:
        """Get a specific layout setting by name"""
        return getattr(self.settings, setting_name, None)
    
    def update_setting(self, setting_name: str, value: Any) -> None:
        """Update a specific layout setting"""
        if hasattr(self.settings, setting_name):
            setattr(self.settings, setting_name, value)
            _LOGGER.debug(f"Updated layout setting {setting_name} to {value}")
        else:
            _LOGGER.warning(f"Layout setting {setting_name} not found")


# Global instance
_template_layout_manager = None

def get_template_layout_manager() -> TemplateManagerLayoutManager:
    """Get the global Template Manager layout manager instance"""
    global _template_layout_manager
    if _template_layout_manager is None:
        _template_layout_manager = TemplateManagerLayoutManager()
    return _template_layout_manager