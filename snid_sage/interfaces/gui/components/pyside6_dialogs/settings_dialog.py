"""
PySide6 Settings Dialog for SNID SAGE GUI
=========================================

This module provides a PySide6 dialog for GUI settings and preferences.

Features:
- Font size and display options
- Theme preferences  
- Window resolution and DPI settings
- Plot display preferences
- Interface customization options
"""

import platform
from typing import Optional, Dict, Any, List, Callable
import PySide6.QtWidgets as QtWidgets
import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui

# Import flexible number input widget
from snid_sage.interfaces.gui.components.widgets.flexible_number_input import (
    create_flexible_double_input,
    create_flexible_int_input
)

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_settings_dialog')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_settings_dialog')


class PySide6SettingsDialog(QtWidgets.QDialog):
    """PySide6 dialog for comprehensive GUI settings"""
    
    # Define custom signals for thread communication

    
    def __init__(self, parent=None, current_settings=None):
        """Initialize settings dialog"""
        super().__init__(parent)
        
        self.parent_gui = parent
        self.settings = current_settings or {}
        self.result = None
        
        # Settings widgets storage
        self.widgets = {}
        self.font_samples = {}
        
        # Available fonts (filtered for readability)
        self.available_fonts = self._get_available_fonts()
        
        # Color scheme
        self.colors = self._get_theme_colors()
        
        # Settings change callbacks
        self.settings_changed_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        

        
        self.setup_ui()
    
    def _get_available_fonts(self) -> List[str]:
        """Get available system fonts filtered for readability"""
        # Get system fonts
        font_database = QtGui.QFontDatabase()
        all_fonts = font_database.families()
        
        # Priority fonts for different platforms
        preferred_fonts = []
        
        if platform.system() == "Windows":
            preferred_fonts = ["Segoe UI", "Calibri", "Arial", "Verdana", "Tahoma"]
        elif platform.system() == "Darwin":  # macOS
            preferred_fonts = ["Arial", "Helvetica Neue", "Verdana"]
        else:  # Linux
            preferred_fonts = ["Ubuntu", "DejaVu Sans", "Liberation Sans", "Arial", "Verdana"]
        
        # Add common programming fonts
        programming_fonts = ["Consolas", "Monaco", "Courier New", "Menlo", "Source Code Pro"]
        
        # Combine and filter available fonts
        priority_fonts = preferred_fonts + programming_fonts
        available_fonts = []
        
        # Add priority fonts that are available
        for font in priority_fonts:
            if font in all_fonts:
                available_fonts.append(font)
        
        # Add other common fonts
        common_fonts = ["Arial", "Helvetica", "Times New Roman", "Georgia", "Trebuchet MS"]
        for font in common_fonts:
            if font in all_fonts and font not in available_fonts:
                available_fonts.append(font)
        
        return available_fonts[:20]  # Limit to 20 fonts
    
    def _get_theme_colors(self) -> Dict[str, str]:
        """Get theme colors from parent or use defaults"""
        if hasattr(self.parent_gui, 'theme_colors'):
            return self.parent_gui.theme_colors
        else:
            # Default theme colors
            return {
                'bg_primary': '#f8fafc',
                'bg_secondary': '#ffffff',
                'bg_tertiary': '#f1f5f9',
                'text_primary': '#1e293b',
                'text_secondary': '#475569',
                'border': '#cbd5e1',
                'accent_primary': '#3b82f6',
                'btn_primary': '#3b82f6',
                'btn_success': '#10b981',
                'btn_warning': '#f59e0b',
                'btn_danger': '#ef4444'
            }
    
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("SNID SAGE Settings")
        self.setMinimumSize(700, 500)
        self.resize(800, 600)
        self.setModal(True)
        
        # Apply theme manager styles
        from snid_sage.interfaces.gui.utils.pyside6_theme_manager import apply_theme_to_widget
        apply_theme_to_widget(self)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Header
        self._create_header(main_layout)
        
        # Snapshot current GUI state to allow cancel-revert of live changes
        try:
            if hasattr(self.parent_gui, 'snapshot_gui_state'):
                self._initial_gui_state = self.parent_gui.snapshot_gui_state()
            else:
                self._initial_gui_state = None
        except Exception:
            self._initial_gui_state = None
        
        # Tabbed content
        self._create_tabbed_content(main_layout)
        
        # Footer buttons
        self._create_footer_buttons(main_layout)
        
        # Load current values
        self._load_current_values()
        
        _LOGGER.debug("PySide6 Settings dialog created")
    
    def _create_header(self, layout):
        """Create header section"""
        header_frame = QtWidgets.QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: {self.colors['bg_secondary']};
                border: 1px solid {self.colors['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        
        header_layout = QtWidgets.QVBoxLayout(header_frame)
        
        title_label = QtWidgets.QLabel("GUI Settings & Preferences")
        title_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: bold;
            color: {self.colors['text_primary']};
            background: transparent;
            border: none;
        """)
        header_layout.addWidget(title_label)
        
        layout.addWidget(header_frame)
    
    def _create_tabbed_content(self, layout):
        """Create tabbed content for different settings categories"""
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {self.colors['border']};
                background: {self.colors['bg_secondary']};
            }}
            QTabBar::tab {{
                background: {self.colors['bg_tertiary']};
                color: {self.colors['text_primary']};
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid {self.colors['border']};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background: {self.colors['bg_secondary']};
                color: {self.colors['accent_primary']};
                font-weight: bold;
            }}
        """)
        
        # Create tabs
        self._create_display_tab(tab_widget)
        self._create_profile_tab(tab_widget)
        
        layout.addWidget(tab_widget, 1)
    
    # Appearance tab removed per requirements
    
    def _create_display_tab(self, tab_widget):
        """Create display settings tab"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Interface scale group
        scale_group = QtWidgets.QGroupBox("Interface Scale")
        scale_layout = QtWidgets.QGridLayout(scale_group)
        
        scale_layout.addWidget(QtWidgets.QLabel("UI Scale (%):"), 0, 0)
        self.widgets['ui_scale_percent'] = create_flexible_int_input(min_val=50, max_val=300, default=100)
        self.widgets['ui_scale_percent'].setValue(100)
        try:
            self.widgets['ui_scale_percent'].valueChanged.connect(self._on_ui_scale_changed)
        except Exception:
            pass
        scale_layout.addWidget(self.widgets['ui_scale_percent'], 0, 1)
        
        # Remember window position
        self.widgets['remember_position'] = QtWidgets.QCheckBox("Remember window position on exit")
        scale_layout.addWidget(self.widgets['remember_position'], 1, 0, 1, 2)
        
        layout.addWidget(scale_group)
        
        layout.addStretch()
        tab_widget.addTab(tab, "🖥️ Display")
    
    def _create_profile_tab(self, tab_widget):
        """Create profile selection tab (optical/onir)."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        group = QtWidgets.QGroupBox("Active Processing Profile")
        group_layout = QtWidgets.QFormLayout(group)

        # Use a combo box for easy collection via _collect_settings
        self.widgets['active_profile_id'] = QtWidgets.QComboBox()
        self.widgets['active_profile_id'].addItems(["optical", "onir"])
        # Initialize from current GUI controller if available
        try:
            current_pid = 'optical'
            if hasattr(self.parent_gui, 'app_controller') and hasattr(self.parent_gui.app_controller, 'active_profile_id'):
                current_pid = str(self.parent_gui.app_controller.active_profile_id).strip().lower() or 'optical'
            idx = self.widgets['active_profile_id'].findText(current_pid)
            if idx >= 0:
                self.widgets['active_profile_id'].setCurrentIndex(idx)
        except Exception:
            pass

        self.widgets['active_profile_id'].setToolTip("Choose the active processing profile. ONIR enables ~2000–25000 Å and z up to 2.5.")
        group_layout.addRow("Profile:", self.widgets['active_profile_id'])

        hint = QtWidgets.QLabel("Switching profile will reset the GUI. If a file is loaded, it will be reloaded under the new profile.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b;")

        layout.addWidget(group)
        layout.addWidget(hint)
        layout.addStretch()
        tab_widget.addTab(tab, "✨ Profile")


    
    # Behavior tab removed per requirements
    
    # Advanced tab removed per requirements
    
    def _create_footer_buttons(self, layout):
        """Create footer button section"""
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        
        # OK button
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setObjectName("ok_btn")
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.colors['btn_primary']};
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: {self._darken_color(self.colors['btn_primary'])};
            }}
        """)
        ok_btn.clicked.connect(self._ok_clicked)
        ok_btn.setDefault(True)
        
        # Cancel button
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.colors['text_secondary']};
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: {self._darken_color(self.colors['text_secondary'])};
            }}
        """)
        cancel_btn.clicked.connect(self._cancel_clicked)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Enhance buttons for consistent click feedback
        try:
            from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
            theme_mgr = getattr(self.parent_gui, 'theme_manager', None)
            enhance_dialog_with_preset(self, 'settings_dialog', theme_mgr)
        except Exception:
            pass
    
    def _update_font_preview(self):
        """Update font preview"""
        if 'main' in self.font_samples:
            font_family = self.widgets['font_family'].currentText()
            font_size = self.widgets['font_size'].value()
            
            font = QtGui.QFont(font_family, font_size)
            self.font_samples['main'].setFont(font)
    
    def _darken_color(self, color: str) -> str:
        """Darken a hex color"""
        if color.startswith('#') and len(color) == 7:
            try:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                
                r = max(0, r - 30)
                g = max(0, g - 30)
                b = max(0, b - 30)
                
                return f"#{r:02x}{g:02x}{b:02x}"
            except:
                pass
        return color
    
    def _load_current_values(self):
        """Load current settings values into widgets"""
        # Load saved OpenRouter API key
        saved_api_key = ''
        saved_model = ''
        try:
            from snid_sage.interfaces.llm.openrouter.openrouter_llm import get_openrouter_api_key, get_openrouter_config
            saved_api_key = get_openrouter_api_key() or ''
            config = get_openrouter_config()
            saved_model = config.get('model_id', '') if config else ''
        except Exception as e:
            _LOGGER.warning(f"Could not load saved OpenRouter settings: {e}")
        
        # Set default values or load from settings (include persisted UI scale)
        try:
            qsettings = QtCore.QSettings("SNID_SAGE", "GUI")
            persisted_scale = int(qsettings.value("ui_scale_percent", 100))
        except Exception:
            persisted_scale = 100
        defaults = {
            'ui_scale_percent': persisted_scale,
            'remember_position': True,
            # AI settings (kept for future expansion; no widgets here)
            'openrouter_api_key': saved_api_key,
            'favorite_model': saved_model
        }
        
        for key, default_value in defaults.items():
            if key in self.widgets:
                widget = self.widgets[key]
                # Prefer persisted values; then current settings; then defaults
                value = default_value if key not in self.settings else self.settings.get(key, default_value)
                
                if isinstance(widget, QtWidgets.QComboBox):
                    index = widget.findText(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QtWidgets.QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, (QtWidgets.QListWidget, QtWidgets.QTableWidget)):
                    # For favorite_model, select the item if it exists
                    if key == 'favorite_model' and value:
                        if isinstance(widget, QtWidgets.QTableWidget):
                            # Search through table rows
                            for row in range(widget.rowCount()):
                                item = widget.item(row, 0)  # First column contains model data
                                if item and item.data(QtCore.Qt.UserRole) == value:
                                    widget.selectRow(row)
                                    break
                        else:
                            # Original list widget logic
                            for i in range(widget.count()):
                                item = widget.item(i)
                                if item and item.data(QtCore.Qt.UserRole) == value:
                                    widget.setCurrentItem(item)
                                    break
        
        # Appearance tab removed; no font preview update
    
    def _collect_settings(self) -> Dict[str, Any]:
        """Collect settings from widgets"""
        settings = {}
        
        for key, widget in self.widgets.items():
            if isinstance(widget, QtWidgets.QComboBox):
                settings[key] = widget.currentText()
            elif isinstance(widget, QtWidgets.QSpinBox):
                settings[key] = widget.value()
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                settings[key] = widget.value()
            elif isinstance(widget, QtWidgets.QCheckBox):
                settings[key] = widget.isChecked()
            elif isinstance(widget, QtWidgets.QLineEdit):
                settings[key] = widget.text()
            elif isinstance(widget, (QtWidgets.QListWidget, QtWidgets.QTableWidget)):
                # For favorite model, get the selected item's model ID
                if key == 'favorite_model':
                    if isinstance(widget, QtWidgets.QTableWidget):
                        selected_rows = widget.selectionModel().selectedRows()
                        if selected_rows:
                            row = selected_rows[0].row()
                            item = widget.item(row, 0)  # First column
                            if item:
                                settings[key] = item.data(QtCore.Qt.UserRole)
                            else:
                                settings[key] = ''
                        else:
                            settings[key] = ''
                    else:
                        current_item = widget.currentItem()
                        if current_item:
                            settings[key] = current_item.data(QtCore.Qt.UserRole)
                        else:
                            settings[key] = ''
                else:
                    settings[key] = ''
        
        return settings
    
    def _apply_settings(self):
        """Apply settings without closing dialog"""
        settings = self._collect_settings()
        
        # Save OpenRouter API key if provided
        api_key = settings.get('openrouter_api_key', '').strip()
        if api_key:
            try:
                from snid_sage.interfaces.llm.openrouter.openrouter_llm import save_openrouter_api_key
                save_openrouter_api_key(api_key)
                _LOGGER.info("OpenRouter API key saved successfully")
            except Exception as e:
                _LOGGER.error(f"Failed to save OpenRouter API key: {e}")
                QtWidgets.QMessageBox.warning(
                    self,
                    "API Key Save Error",
                    f"Failed to save OpenRouter API key: {str(e)}"
                )
        
        # Save selected model if provided
        selected_model = settings.get('favorite_model', '').strip()
        if selected_model:
            try:
                from snid_sage.interfaces.llm.openrouter.openrouter_llm import save_openrouter_config
                save_openrouter_config(api_key, selected_model)
                _LOGGER.info(f"OpenRouter model preference saved: {selected_model}")
            except Exception as e:
                _LOGGER.error(f"Failed to save OpenRouter model preference: {e}")
        
        # Apply to parent if available
        if hasattr(self.parent_gui, 'apply_settings'):
            self.parent_gui.apply_settings(settings)

        # Handle profile switch if changed
        try:
            target_pid = str(settings.get('active_profile_id', '')).strip().lower()
            if target_pid in {'optical', 'onir'}:
                current_pid = None
                try:
                    if hasattr(self.parent_gui, 'app_controller') and hasattr(self.parent_gui.app_controller, 'active_profile_id'):
                        current_pid = str(self.parent_gui.app_controller.active_profile_id).strip().lower()
                except Exception:
                    current_pid = None
                if current_pid and target_pid != current_pid and hasattr(self.parent_gui, 'app_controller'):
                    # Switch profile and reload current file if present
                    self.parent_gui.app_controller.switch_active_profile(target_pid, reload_current_file=True, show_notice=True)
        except Exception as e:
            _LOGGER.warning(f"Profile switch from settings failed or skipped: {e}")
        
        # Call callbacks
        for callback in self.settings_changed_callbacks:
            callback(settings)
        
        _LOGGER.info("Settings applied")
    
    def _ok_clicked(self):
        """Handle OK button click"""
        self.result = self._collect_settings()
        # Persist UI scale percent before apply
        try:
            if 'ui_scale_percent' in self.result:
                ui_scale = int(self.result['ui_scale_percent'])
                if 50 <= ui_scale <= 300:
                    QtCore.QSettings("SNID_SAGE", "GUI").setValue("ui_scale_percent", ui_scale)
        except Exception:
            pass
        self._apply_settings()
        self.accept()

    def _cancel_clicked(self):
        """Revert live changes to initial state and close dialog without applying anything."""
        try:
            if getattr(self, '_initial_gui_state', None) is not None and hasattr(self.parent_gui, 'restore_gui_state'):
                self.parent_gui.restore_gui_state(self._initial_gui_state)
        except Exception:
            pass
        self.reject()

    def _on_ui_scale_changed(self, percent: int):
        """Preview UI scale immediately without persisting."""
        try:
            base_w, base_h = (900, 600)
            if hasattr(self.parent_gui, 'unified_layout_manager'):
                try:
                    base_w, base_h = self.parent_gui.unified_layout_manager.settings.default_window_size
                except Exception:
                    pass
            scaled_w = max(100, int(base_w * int(percent) / 100))
            scaled_h = max(100, int(base_h * int(percent) / 100))
            if hasattr(self.parent_gui, 'resize'):
                self.parent_gui.resize(scaled_w, scaled_h)
        except Exception:
            pass
    
    # Reset to defaults action removed with Advanced tab
    
    def add_settings_changed_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for settings changes"""
        self.settings_changed_callbacks.append(callback)
 