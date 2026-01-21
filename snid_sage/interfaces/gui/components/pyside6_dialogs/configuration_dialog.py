"""
SNID SAGE - Configuration Dialog - PySide6 Version
================================================

Modern configuration dialog for SNID analysis parameters using PySide6.
Provides comprehensive parameter configuration.
"""

import PySide6.QtCore as QtCore
import PySide6.QtGui as QtGui
import PySide6.QtWidgets as QtWidgets
from typing import Dict, Any, List, Optional, Tuple
import os

# Import flexible number input widget
from snid_sage.interfaces.gui.components.widgets.flexible_number_input import (
    FlexibleNumberInput, 
    create_flexible_double_input, 
    create_flexible_int_input
)


class CustomAgeSpinBox(QtWidgets.QDoubleSpinBox):
    """Custom QDoubleSpinBox that can show special text for both minimum and maximum values"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_special_text = ""
        self._max_special_value = None
        
    def setMaximumSpecialValueText(self, text: str, value: float):
        """Set special text to display when the spinbox has the maximum value"""
        self._max_special_text = text
        self._max_special_value = value
    
    def textFromValue(self, value: float) -> str:
        """Override to show special text for maximum value"""
        if (self._max_special_value is not None and 
            abs(value - self._max_special_value) < 0.001):
            return self._max_special_text
        return super().textFromValue(value)
    
    def valueFromText(self, text: str) -> float:
        """Override to handle special text input"""
        if text == self._max_special_text and self._max_special_value is not None:
            return self._max_special_value
        return super().valueFromText(text)

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_config')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_config')

# Enhanced button management
try:
    from snid_sage.interfaces.gui.utils.dialog_button_enhancer import enhance_dialog_with_preset
    ENHANCED_BUTTONS_AVAILABLE = True
except ImportError:
    ENHANCED_BUTTONS_AVAILABLE = False


class PySide6ConfigurationDialog(QtWidgets.QDialog):
    """
    Comprehensive SNID configuration dialog for PySide6.
    
    Provides all configuration options available in the GUI, including:
    - Redshift range parameters
    - Age filtering
    - Template type selection
    - Correlation parameters
    - Output options
    """
    
    def __init__(self, parent, current_params=None, app_controller=None):
        """
        Initialize configuration dialog.
        
        Args:
            parent: Parent window
            current_params: Current parameter values dict
            app_controller: Application controller for running analysis
        """
        super().__init__(parent)
        self.current_params = current_params or {}
        self.result_params = None
        self.app_controller = app_controller
        self.analysis_started = False  # Track if analysis was started from dialog
        
        # Parameter widgets storage
        self.widgets = {}
        self.type_buttons = {}
        self.selected_types = set()
        
        # Default parameters
        self.default_params = self._get_default_params()
        
        self._setup_dialog()
        self._create_interface()
        self._load_current_values()
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default SNID parameters"""
        # Profile-aware defaults: ONIR allows searches up to z=2.5 by default
        try:
            active_pid = (getattr(self.app_controller, 'active_profile_id', None) or '').strip().lower()
        except Exception:
            active_pid = ''
        default_zmax = 2.5 if active_pid == 'onir' else 1.0
        return {
            # Basic parameters
            'zmin': -0.01,
            'zmax': default_zmax,
            'age_range': None,
            'age_min': -9999,  # Default minimum age (shows "No minimum")
            'age_max': 9999,   # Default maximum age (shows "No maximum") 
            'lapmin': 0.3,
            'hsigma_lap_ccc_threshold': 1.5,  # HσLAP-CCC threshold for clustering
            'max_output_templates': 10,
            
            
            # Template filtering
            'type_filter': [],  # Empty = all types
            'template_filter': [],  # Empty = all templates
            'template_mode': 'include',  # 'include' or 'exclude'
            
            # Advanced parameters
            'forced_redshift': None,
            'verbose': False,
            'save_plots': False,
            'show_plots': False,
            'output_dir': None,
            
            # Correlation parameters
            'correlation_method': 'cross_correlation',
            'normalize_templates': True,
            'wavelength_range': (3000, 10000),
            
            # Type-specific parameters
            'ia_age_range': (-15, 100),
            'cc_age_range': (-20, 300),
            'slsn_age_range': (-50, 500)
        }
    
    def _setup_dialog(self):
        """Setup dialog window properties"""
        self.setWindowTitle("SNID Analysis Configuration")
        self.resize(900, 700)
        self.setMinimumSize(800, 600)
        
        # Apply modern styling (avoid overriding checkbox/radio indicators)
        # Use a platform-aware font stack to avoid macOS warnings about Segoe UI
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
                color: #1e293b;
                font-family: Arial, "Helvetica Neue", Helvetica, "Segoe UI", sans-serif;
            }
            
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 12px;
                background: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #3b82f6;
            }
            
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 20px;
                background: #ffffff;
                font-size: 10pt;
            }
            
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #3b82f6;
            }
            
            QPushButton {
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 24px;
                font-weight: bold;
                font-size: 10pt;
                background: #ffffff;
            }
            
            QPushButton:hover {
                background: #f1f5f9;
                border: 2px solid #3b82f6;
            }
            
            QPushButton:pressed {
                background: #e2e8f0;
            }
            
            QPushButton#primary_btn {
                background: #22c55e;
                color: white;
                border: 2px solid #22c55e;
            }
            
            QPushButton#primary_btn:hover {
                background: #16a34a;
                border: 2px solid #16a34a;
            }
            
            QPushButton#secondary_btn {
                background: #3b82f6;
                color: white;
                border: 2px solid #3b82f6;
            }
            
            QPushButton#secondary_btn:hover {
                background: #2563eb;
                border: 2px solid #2563eb;
            }
            
            /* Checkbox/radio indicators inherit from global theme manager */
            
            QLabel {
                color: #1e293b;
                font-size: 10pt;
            }
            
            QTabWidget::pane {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                background: #ffffff;
            }
            
            QTabWidget::tab-bar {
                left: 8px;
            }
            
            QTabBar::tab {
                background: #f1f5f9;
                border: 2px solid #e2e8f0;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: bold;
            }
            
            QTabBar::tab:selected {
                background: #ffffff;
                border: 2px solid #3b82f6;
                border-bottom: 2px solid #ffffff;
            }
            
            QTabBar::tab:hover {
                background: #e2e8f0;
            }
        """)
    
    def _create_interface(self):
        """Create the main interface"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Create tabbed interface
        tab_widget = QtWidgets.QTabWidget()
        
        # Basic Parameters Tab
        basic_tab = self._create_basic_parameters_tab()
        tab_widget.addTab(basic_tab, "Basic Parameters")
        
        # Advanced Filtering Tab
        filtering_tab = self._create_filtering_tab()
        tab_widget.addTab(filtering_tab, "Template Filtering")
        
        # Output Options Tab
        output_tab = self._create_output_options_tab()
        tab_widget.addTab(output_tab, "📊 Output Options")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        # Reset to defaults button
        reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        reset_btn.setObjectName("reset_btn")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addSpacing(10)
        
        # Cancel button
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Apply and Run button
        apply_btn = QtWidgets.QPushButton("Apply and Run")
        apply_btn.setObjectName("primary_btn")
        apply_btn.clicked.connect(self._apply_settings)
        apply_btn.setDefault(True)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
        # Enhanced button styling and animations
        self._setup_enhanced_buttons()
    
    def _create_basic_parameters_tab(self):
        """Create basic parameters tab"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Redshift Parameters
        redshift_group = QtWidgets.QGroupBox("Redshift Range")
        redshift_layout = QtWidgets.QFormLayout(redshift_group)
        
        self.widgets['zmin'] = create_flexible_double_input(min_val=-0.1, max_val=2.0, default=0.0)
        self.widgets['zmin'].setToolTip("Minimum redshift for analysis (enter any precision)")
        redshift_layout.addRow("Minimum Redshift (zmin):", self.widgets['zmin'])
        
        # Use profile-aware default for zmax (2.5 for ONIR, 1.0 for optical)
        self.widgets['zmax'] = create_flexible_double_input(min_val=-0.1, max_val=3.0, default=self.default_params.get('zmax', 1.0))
        self.widgets['zmax'].setToolTip("Maximum redshift for analysis (enter any precision)")
        redshift_layout.addRow("Maximum Redshift (zmax):", self.widgets['zmax'])
        
        # Optional forced redshift
        forced_redshift_layout = QtWidgets.QHBoxLayout()
        self.widgets['forced_redshift_enabled'] = QtWidgets.QCheckBox("Force specific redshift:")
        self.widgets['forced_redshift_value'] = create_flexible_double_input(min_val=-0.1, max_val=3.0, default=0.0)
        self.widgets['forced_redshift_value'].setEnabled(False)
        self.widgets['forced_redshift_value'].setToolTip("Force analysis to use this specific redshift (any precision)")
        
        # Connect checkbox to enable/disable spinbox
        self.widgets['forced_redshift_enabled'].toggled.connect(
            self.widgets['forced_redshift_value'].setEnabled
        )
        
        forced_redshift_layout.addWidget(self.widgets['forced_redshift_enabled'])
        forced_redshift_layout.addWidget(self.widgets['forced_redshift_value'])
        forced_redshift_layout.addStretch()
        
        redshift_layout.addRow(forced_redshift_layout)
        layout.addWidget(redshift_group)
        
        # Age Parameters
        age_group = QtWidgets.QGroupBox("📅 Age Filtering")
        age_layout = QtWidgets.QFormLayout(age_group)
        
        self.widgets['age_min'] = create_flexible_double_input(min_val=-9999, max_val=9999, default=-9999, suffix=" days")
        # Show a friendly label for sentinel value
        if hasattr(self.widgets['age_min'], 'setSpecialValueDisplay'):
            # Display should not include the suffix
            self.widgets['age_min'].setSpecialValueDisplay(-9999.0, "No Minimum")
        self.widgets['age_min'].setValue(-9999)
        self.widgets['age_min'].setToolTip("Minimum age in days (negative = before maximum light). Use -9999 to disable filtering.")
        age_layout.addRow("Minimum Age (days):", self.widgets['age_min'])
        
        self.widgets['age_max'] = CustomAgeSpinBox()
        # Hide up/down arrow buttons for a cleaner input field
        self.widgets['age_max'].setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.widgets['age_max'].setRange(-9999, 9999)
        self.widgets['age_max'].setSingleStep(1)
        self.widgets['age_max'].setDecimals(1)
        self.widgets['age_max'].setMaximumSpecialValueText("No Maximum", 9999.0)
        self.widgets['age_max'].setValue(9999)
        self.widgets['age_max'].setToolTip("Maximum age in days (negative = before maximum light). Set to maximum to disable age filtering.")
        age_layout.addRow("Maximum Age (days):", self.widgets['age_max'])
        
        layout.addWidget(age_group)
        
        # Correlation Parameters
        correlation_group = QtWidgets.QGroupBox("🔗 Correlation Settings")
        correlation_layout = QtWidgets.QFormLayout(correlation_group)
        
        # Keep UI default consistent with CLI/config defaults (lapmin=0.3)
        self.widgets['lapmin'] = create_flexible_double_input(min_val=0.0, max_val=1.0, default=0.3)
        self.widgets['lapmin'].setToolTip("Minimum overlap fraction required between spectrum and template (any precision)")
        correlation_layout.addRow("Minimum Overlap (lapmin):", self.widgets['lapmin'])
        
        self.widgets['hsigma_lap_ccc_threshold'] = create_flexible_double_input(min_val=0.0, max_val=500.0, default=1.5)
        self.widgets['hsigma_lap_ccc_threshold'].setToolTip(
            "Minimum best-metric value required for clustering (HσLAP-CCC: (height × lap × CCC) / sqrt(sigma_z), default: 1.5, any precision)"
        )
        correlation_layout.addRow("HσLAP-CCC Clustering Threshold:", self.widgets['hsigma_lap_ccc_threshold'])
        
        
        layout.addWidget(correlation_group)
        
        layout.addStretch()
        return tab
    
    def _create_filtering_tab(self):
        """Create template filtering tab"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Type Selection
        type_group = QtWidgets.QGroupBox("🎭 Supernova Type Selection")
        type_layout = QtWidgets.QVBoxLayout(type_group)
        
        # Instructions
        instructions = QtWidgets.QLabel(
            "Select specific supernova types to include in analysis. "
            "Leave all unchecked to use all available types."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #64748b; font-style: italic;")
        type_layout.addWidget(instructions)
        
        # Type buttons grid
        types_widget = QtWidgets.QWidget()
        types_grid = QtWidgets.QGridLayout(types_widget)
        types_grid.setSpacing(10)
        
        # Main supernova and related object types with representative subtypes
        # Expanded to include all categories supported by SNID templates
        self.sn_types = {
            'Ia': ['Ia', 'Ia-norm', 'Ia-91T', 'Ia-91bg', 'Ia-csm', 'Ia-pec', 'Ia-02cx', 'Ia-03fg', 'Ia-02es', 'Ia-Ca-rich'],
            'Ib': ['Ib', 'Ib-norm', 'Ib-pec', 'IIb', 'Ibn', 'Ib-Ca-rich', 'Ib-csm'],
            'Ic': ['Ic', 'Ic-norm', 'Ic-pec', 'Ic-broad', 'Icn', 'Ic-Ca-rich', 'Ic-csm'],
            'II': ['II', 'IIP', 'II-pec', 'IIn', 'IIL', 'IIn-pec'],
            'SLSN': ['SLSN', 'SLSN-I', 'SLSN-Ib', 'SLSN-Ic', 'SLSN-II', 'SLSN-IIn'],
            'LFBOT': ['LFBOT', '18cow', '20xnd'],
            'TDE': ['TDE', 'TDE-H', 'TDE-He', 'TDE-H-He', 'TDE-Ftless'],
            'KN': ['KN', '17gfo'],
            'GAP': ['GAP', 'LRN', 'LBV', 'ILRT'],
            'Galaxy': ['Galaxy', 'Gal', 'Gal-E', 'Gal-S0', 'Gal-Sa', 'Gal-Sb', 'Gal-Sc', 'Gal-SB'],
            'Star': ['Star', 'M-star', 'C-star'],
            'AGN': ['AGN', 'AGN-type1', 'QSO'],
            'CV': ['CV', 'AM_CVn', 'DN', 'Polar']
        }
        
        row, col = 0, 0
        for type_name in self.sn_types.keys():
            checkbox = QtWidgets.QCheckBox(type_name)
            checkbox.setToolTip(f"Include {type_name} templates in analysis")
            checkbox.toggled.connect(lambda checked, t=type_name: self._on_type_toggled(t, checked))
            self.type_buttons[type_name] = checkbox
            
            types_grid.addWidget(checkbox, row, col)
            col += 1
            if col >= 3:  # 3 columns
                col = 0
                row += 1
        
        type_layout.addWidget(types_widget)
        
        # Select/Deselect all buttons
        button_layout = QtWidgets.QHBoxLayout()
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_types)
        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all_types)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        type_layout.addLayout(button_layout)
        
        layout.addWidget(type_group)
        
        # Individual Template Selection
        template_group = QtWidgets.QGroupBox("🔍 Individual Template Selection")
        template_layout = QtWidgets.QVBoxLayout(template_group)
        
        # Instructions
        template_instructions = QtWidgets.QLabel(
            "Select specific templates to include/exclude from analysis. "
            "Leave empty to use all templates of selected types."
        )
        template_instructions.setWordWrap(True)
        template_instructions.setStyleSheet("color: #64748b; font-style: italic;")
        template_layout.addWidget(template_instructions)
        
        # Template mode selection
        mode_layout = QtWidgets.QHBoxLayout()
        self.template_mode_group = QtWidgets.QButtonGroup(self)
        
        self.include_mode_radio = QtWidgets.QRadioButton("Include only selected templates")
        self.include_mode_radio.setChecked(True)
        self.template_mode_group.addButton(self.include_mode_radio, 0)
        mode_layout.addWidget(self.include_mode_radio)
        
        self.exclude_mode_radio = QtWidgets.QRadioButton("Exclude selected templates")
        self.template_mode_group.addButton(self.exclude_mode_radio, 1)
        mode_layout.addWidget(self.exclude_mode_radio)
        
        mode_layout.addStretch()
        template_layout.addLayout(mode_layout)
        
        # Template selection interface
        template_selection_layout = QtWidgets.QHBoxLayout()
        
        # Available templates (left side)
        available_frame = QtWidgets.QFrame()
        available_layout = QtWidgets.QVBoxLayout(available_frame)
        available_layout.addWidget(QtWidgets.QLabel("Available Templates:"))
        
        # Search box
        self.template_search = QtWidgets.QLineEdit()
        self.template_search.setPlaceholderText("Search templates...")
        self.template_search.textChanged.connect(self._filter_templates)
        available_layout.addWidget(self.template_search)
        
        # Available templates list
        self.available_templates_list = QtWidgets.QListWidget()
        self.available_templates_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        available_layout.addWidget(self.available_templates_list)
        
        template_selection_layout.addWidget(available_frame)
        
        # Move buttons (center)
        buttons_frame = QtWidgets.QFrame()
        buttons_layout = QtWidgets.QVBoxLayout(buttons_frame)
        buttons_layout.addStretch()
        
        self.add_template_btn = QtWidgets.QPushButton("➤")
        self.add_template_btn.setToolTip("Add selected templates")
        self.add_template_btn.clicked.connect(self._add_templates)
        buttons_layout.addWidget(self.add_template_btn)
        
        self.add_all_templates_btn = QtWidgets.QPushButton("➤➤")
        self.add_all_templates_btn.setToolTip("Add all templates")
        self.add_all_templates_btn.clicked.connect(self._add_all_templates)
        buttons_layout.addWidget(self.add_all_templates_btn)
        
        self.remove_template_btn = QtWidgets.QPushButton("◀")
        self.remove_template_btn.setToolTip("Remove selected templates")
        self.remove_template_btn.clicked.connect(self._remove_templates)
        buttons_layout.addWidget(self.remove_template_btn)
        
        self.remove_all_templates_btn = QtWidgets.QPushButton("◀◀")
        self.remove_all_templates_btn.setToolTip("Remove all templates")
        self.remove_all_templates_btn.clicked.connect(self._remove_all_templates)
        buttons_layout.addWidget(self.remove_all_templates_btn)
        
        buttons_layout.addStretch()
        template_selection_layout.addWidget(buttons_frame)
        
        # Selected templates (right side)
        selected_frame = QtWidgets.QFrame()
        selected_layout = QtWidgets.QVBoxLayout(selected_frame)
        selected_layout.addWidget(QtWidgets.QLabel("Selected Templates:"))
        
        # Selected templates list
        self.selected_templates_list = QtWidgets.QListWidget()
        self.selected_templates_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        selected_layout.addWidget(self.selected_templates_list)
        
        template_selection_layout.addWidget(selected_frame)
        
        template_layout.addLayout(template_selection_layout)
        
        layout.addWidget(template_group)
        
        # Initialize template lists
        self.selected_templates = set()
        self._load_available_templates()
        
        layout.addStretch()
        return tab
    
    def _create_output_options_tab(self):
        """Create output options tab"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # General Options
        general_group = QtWidgets.QGroupBox("⚙️ General Options")
        general_layout = QtWidgets.QVBoxLayout(general_group)
        
        self.widgets['verbose'] = QtWidgets.QCheckBox("Verbose output")
        self.widgets['verbose'].setToolTip("Enable detailed logging during analysis")
        general_layout.addWidget(self.widgets['verbose'])
        
        layout.addWidget(general_group)
        
        # Output Limits
        limits_group = QtWidgets.QGroupBox("📊 Output Limits")
        limits_layout = QtWidgets.QFormLayout(limits_group)
        
        self.widgets['max_output_templates'] = create_flexible_int_input(min_val=1, max_val=50, default=10)
        self.widgets['max_output_templates'].setToolTip("Maximum number of best templates to output (integer)")
        limits_layout.addRow("Max Output Templates:", self.widgets['max_output_templates'])
        
        layout.addWidget(limits_group)
        
        layout.addStretch()
        return tab
    
    # Template selection methods
    def _load_available_templates(self):
        """Load available templates from the templates directory"""
        try:
            # Resolve templates directory using app controller when available (avoids stale/partial config)
            templates_dir = None
            try:
                if hasattr(self, 'app_controller') and self.app_controller and hasattr(self.app_controller, '_resolve_templates_directory'):
                    templates_dir = self.app_controller._resolve_templates_directory(getattr(self.app_controller, 'active_profile_id', None))
            except Exception:
                templates_dir = None
            if not templates_dir:
                # Fallback to configuration manager
                from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
                config_manager = ConfigurationManager()
                config = config_manager.load_config()
                templates_dir = config['paths']['templates_dir']
            
            if not os.path.exists(templates_dir):
                _LOGGER.warning(f"Templates directory not found: {templates_dir}")
                return
            
            # Load template information using unified storage (merged index with overrides)
            self.available_templates = []
            try:
                from snid_sage.snid.io import get_template_info
                info = get_template_info(templates_dir)
                templates_list = info.get('templates', []) or []
                for t in templates_list:
                    name = t.get('name', 'Unknown')
                    sn_type = t.get('type', 'Unknown')
                    subtype = t.get('subtype', 'Unknown')
                    display_name = f"{name} ({sn_type}/{subtype})"
                    self.available_templates.append({
                        'name': name,
                        'display_name': display_name,
                        'type': sn_type,
                        'subtype': subtype
                    })
            except Exception as e:
                _LOGGER.error(f"Failed to load templates via unified storage: {e}")
                self.available_templates = []

            # Sort templates by name
            self.available_templates.sort(key=lambda x: x['name'])
            
            # Update the list widget
            self._update_available_templates()
            
        except Exception as e:
            _LOGGER.error(f"Error loading available templates: {e}")
    
    def _filter_templates(self, search_text):
        """Filter available templates based on search text"""
        try:
            search_text = search_text.lower()
            filtered = []
            
            for template in self.available_templates:
                if (search_text in template['name'].lower() or 
                    search_text in template['type'].lower() or
                    search_text in template['subtype'].lower()):
                    filtered.append(template)
            
            # Update available list
            self.available_templates_list.clear()
            for template in filtered:
                if template['name'] not in self.selected_templates:
                    item = QtWidgets.QListWidgetItem(template['display_name'])
                    item.setData(QtCore.Qt.UserRole, template['name'])
                    self.available_templates_list.addItem(item)
                    
        except Exception as e:
            _LOGGER.error(f"Error filtering templates: {e}")
    
    def _update_available_templates(self):
        """Update the available templates list widget"""
        try:
            self.available_templates_list.clear()
            
            search_text = self.template_search.text().lower()
            
            for template in self.available_templates:
                # Skip if already selected
                if template['name'] in self.selected_templates:
                    continue
                
                # Apply search filter
                if search_text and search_text not in template['name'].lower() and \
                   search_text not in template['type'].lower() and \
                   search_text not in template['subtype'].lower():
                    continue
                
                item = QtWidgets.QListWidgetItem(template['display_name'])
                item.setData(QtCore.Qt.UserRole, template['name'])
                self.available_templates_list.addItem(item)
                
        except Exception as e:
            _LOGGER.error(f"Error updating available templates: {e}")
    
    def _update_selected_templates(self):
        """Update the selected templates list widget"""
        try:
            self.selected_templates_list.clear()
            
            for template_name in sorted(self.selected_templates):
                # Find display name
                display_name = template_name
                for template in self.available_templates:
                    if template['name'] == template_name:
                        display_name = template['display_name']
                        break
                
                item = QtWidgets.QListWidgetItem(display_name)
                item.setData(QtCore.Qt.UserRole, template_name)
                self.selected_templates_list.addItem(item)
                
        except Exception as e:
            _LOGGER.error(f"Error updating selected templates: {e}")
    
    def _add_templates(self):
        """Add selected templates from available to selected list"""
        try:
            selected_items = self.available_templates_list.selectedItems()
            for item in selected_items:
                template_name = item.data(QtCore.Qt.UserRole)
                self.selected_templates.add(template_name)
            
            self._update_available_templates()
            self._update_selected_templates()
            
        except Exception as e:
            _LOGGER.error(f"Error adding templates: {e}")
    
    def _add_all_templates(self):
        """Add all available templates to selected list"""
        try:
            for i in range(self.available_templates_list.count()):
                item = self.available_templates_list.item(i)
                template_name = item.data(QtCore.Qt.UserRole)
                self.selected_templates.add(template_name)
            
            self._update_available_templates()
            self._update_selected_templates()
            
        except Exception as e:
            _LOGGER.error(f"Error adding all templates: {e}")
    
    def _remove_templates(self):
        """Remove selected templates from selected list"""
        try:
            selected_items = self.selected_templates_list.selectedItems()
            for item in selected_items:
                template_name = item.data(QtCore.Qt.UserRole)
                self.selected_templates.discard(template_name)
            
            self._update_available_templates()
            self._update_selected_templates()
            
        except Exception as e:
            _LOGGER.error(f"Error removing templates: {e}")
    
    def _remove_all_templates(self):
        """Remove all templates from selected list"""
        try:
            self.selected_templates.clear()
            self._update_available_templates()
            self._update_selected_templates()
            
        except Exception as e:
            _LOGGER.error(f"Error removing all templates: {e}")
    
    
    
    def _on_type_toggled(self, type_name: str, checked: bool):
        """Handle type checkbox toggle"""
        if checked:
            self.selected_types.add(type_name)
        else:
            self.selected_types.discard(type_name)
    
    def _select_all_types(self):
        """Select all type checkboxes"""
        for checkbox in self.type_buttons.values():
            checkbox.setChecked(True)
    
    def _deselect_all_types(self):
        """Deselect all type checkboxes"""
        for checkbox in self.type_buttons.values():
            checkbox.setChecked(False)
    
    def _load_current_values(self):
        """Load current parameter values into widgets"""
        # Merge defaults with current params
        params = {**self.default_params, **self.current_params}
        
        # Include any forced redshift from the redshift mode dialog
        if (self.app_controller and 
            hasattr(self.app_controller, 'redshift_mode_config') and 
            self.app_controller.redshift_mode_config):
            
            mode_config = self.app_controller.redshift_mode_config
            mode = mode_config.get('mode', 'search')
            
            if mode == 'force':
                # Override with forced redshift from redshift mode dialog
                forced_redshift = mode_config.get('redshift', 0.0)
                params['forced_redshift'] = forced_redshift
                _LOGGER.info(f"Configuration dialog: Using forced redshift from redshift mode dialog: z = {forced_redshift:.6f}")
            else:
                _LOGGER.debug(f"Configuration dialog: Redshift mode is '{mode}', not using forced redshift")
        
        # Load basic parameters
        for key in ['zmin', 'zmax', 'lapmin', 'hsigma_lap_ccc_threshold', 'age_min', 'age_max', 
                   'max_output_templates']:
            if key in params and key in self.widgets and params[key] is not None:
                try:
                    self.widgets[key].setValue(params[key])
                except Exception as e:
                    _LOGGER.warning(f"Could not set value for {key}: {e}")
                    # Set default value based on key
                    if key == 'zmin':
                        self.widgets[key].setValue(-0.01)
                    elif key == 'zmax':
                        self.widgets[key].setValue(1.0)
                    elif key == 'lapmin':
                        self.widgets[key].setValue(0.3)
                    elif key == 'age_min':
                        self.widgets[key].setValue(-9999)
                    elif key == 'age_max':
                        self.widgets[key].setValue(9999)
                    elif key == 'max_output_templates':
                        self.widgets[key].setValue(10)
                    
        
        # Load forced redshift
        if 'forced_redshift' in params and params['forced_redshift'] is not None:
            self.widgets['forced_redshift_enabled'].setChecked(True)
            try:
                self.widgets['forced_redshift_value'].setValue(params['forced_redshift'])
            except Exception as e:
                _LOGGER.warning(f"Could not set forced_redshift_value: {e}")
                self.widgets['forced_redshift_value'].setValue(0.0)
        
        # Load age range if provided as tuple
        if 'age_range' in params and isinstance(params['age_range'], (list, tuple)) and len(params['age_range']) == 2:
            try:
                age_min, age_max = params['age_range']
                if age_min is not None:
                    self.widgets['age_min'].setValue(age_min)
                if age_max is not None:
                    self.widgets['age_max'].setValue(age_max)
            except Exception as e:
                _LOGGER.warning(f"Could not set age_range values: {e}")
                self.widgets['age_min'].setValue(-9999)  # Shows "No minimum"
                self.widgets['age_max'].setValue(9999)  # Shows "No maximum"
        elif 'age_range' in params and params['age_range'] is None:
            # Set to disabled values when age_range is None
            self.widgets['age_min'].setValue(-9999)  # Shows "No minimum"
            self.widgets['age_max'].setValue(9999)  # Shows "No maximum"
        
        # Load checkboxes
        for key in ['verbose']:
            if key in params and key in self.widgets:
                self.widgets[key].setChecked(bool(params[key]))
        
        
        # Load type selection
        if 'type_filter' in params and params['type_filter']:
            type_list = params['type_filter']
            if isinstance(type_list, str):
                type_list = [t.strip() for t in type_list.split(',') if t.strip()]
            
            for type_name in type_list:
                if type_name in self.type_buttons:
                    self.type_buttons[type_name].setChecked(True)
        
        # Load template selection
        if 'template_filter' in params and params['template_filter']:
            template_list = params['template_filter']
            if isinstance(template_list, str):
                template_list = [t.strip() for t in template_list.split(',') if t.strip()]
            
            if self.include_mode_radio.isChecked():
                self.selected_templates = set(template_list)
            else:
                self.selected_templates = set(template_list) # Exclude mode
            
            self._update_available_templates()
            self._update_selected_templates()
    
    def _reset_to_defaults(self):
        """Reset all parameters to defaults"""
        self.current_params = {}
        self._load_current_values()
    
    def _apply_settings(self):
        """Apply and validate settings"""
        try:
            # Collect all parameters
            result = {}
            
            # Basic parameters
            result['zmin'] = self.widgets['zmin'].value()
            result['zmax'] = self.widgets['zmax'].value()
            result['lapmin'] = self.widgets['lapmin'].value()
            result['hsigma_lap_ccc_threshold'] = self.widgets['hsigma_lap_ccc_threshold'].value()
            result['max_output_templates'] = self.widgets['max_output_templates'].value()
            
            # Age range
            age_min = self.widgets['age_min'].value()
            age_max = self.widgets['age_max'].value()
            # Only set age range if values are not at their "disabled" extremes
            if age_min > -100 or age_max < 2000:
                result['age_range'] = (age_min, age_max)
            else:
                result['age_range'] = None
            
            # Forced redshift
            if self.widgets['forced_redshift_enabled'].isChecked():
                result['forced_redshift'] = self.widgets['forced_redshift_value'].value()
            else:
                result['forced_redshift'] = None
            
            # Type filter
            if self.selected_types:
                result['type_filter'] = list(self.selected_types)
            else:
                result['type_filter'] = None
            
            # Template filter
            if self.selected_templates:
                result['template_filter'] = list(self.selected_templates)
            else:
                result['template_filter'] = None
            
            # Options
            result['verbose'] = self.widgets['verbose'].isChecked()
            
            
            # Validate parameters
            if result['zmin'] >= result['zmax']:
                QtWidgets.QMessageBox.warning(self, "Invalid Parameters", 
                                            "Minimum redshift must be less than maximum redshift.")
                return
            
            if age_min >= age_max:
                QtWidgets.QMessageBox.warning(self, "Invalid Parameters", 
                                            "Minimum age must be less than maximum age.")
                return
            
            # Store result and accept
            self.result_params = result
            
            # Trigger analysis if app_controller is provided
            if self.app_controller and hasattr(self.app_controller, 'run_snid_analysis'):
                try:
                    _LOGGER.info("Starting analysis from configuration dialog...")
                    # Close dialog first
                    self.accept()
                    
                    # Add small delay to allow proper cleanup of opened dialogs
                    # This prevents crashes when PyQtGraph widgets are still being cleaned up
                    QtCore.QTimer.singleShot(500, lambda: self._delayed_analysis_start(result))
                    self.analysis_started = True  # Set flag to indicate analysis will be started
                except Exception as e:
                    _LOGGER.error(f"Error running analysis from configuration dialog: {e}")
                    QtWidgets.QMessageBox.critical(
                        self.parent(),
                        "Analysis Error", 
                        f"Error starting analysis:\n{str(e)}"
                    )
            else:
                # No app controller - just accept dialog (old behavior)
                self.accept()
            
        except Exception as e:
            _LOGGER.error(f"Error applying settings: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to apply settings:\n{str(e)}")
    
    def get_parameters(self) -> Optional[Dict[str, Any]]:
        """Get the configured parameters"""
        return self.result_params
    
    def was_analysis_started(self) -> bool:
        """Check if analysis was already started from the dialog"""
        return self.analysis_started
    
    def _delayed_analysis_start(self, result):
        """Start analysis after a delay to allow for proper dialog cleanup"""
        try:
            # Force garbage collection to clean up any lingering PyQtGraph widgets
            import gc
            gc.collect()
            
            _LOGGER.info("Starting delayed analysis after dialog cleanup...")
            success = self.app_controller.run_snid_analysis(result)
            if success:
                _LOGGER.info("Delayed analysis started successfully from configuration dialog")
            else:
                _LOGGER.error("Failed to start delayed analysis from configuration dialog")
                # Show error message if parent still exists
                if self.parent():
                    QtWidgets.QMessageBox.critical(
                        self.parent(),
                        "Analysis Error",
                        "Failed to start SNID analysis.\nPlease check the logs for details."
                    )
        except Exception as e:
            _LOGGER.error(f"Error in delayed analysis start: {e}")
            if self.parent():
                QtWidgets.QMessageBox.critical(
                    self.parent(),
                    "Analysis Error", 
                    f"Error starting analysis:\n{str(e)}"
                )
    
    def _setup_enhanced_buttons(self):
        """Setup enhanced button styling and animations"""
        if not ENHANCED_BUTTONS_AVAILABLE:
            _LOGGER.info("Enhanced buttons not available, using standard styling")
            return
        
        try:
            # Use the configuration dialog preset
            self.button_manager = enhance_dialog_with_preset(
                self, 'configuration_dialog'
            )
            
            _LOGGER.info("Enhanced buttons successfully applied to configuration dialog")
            
        except Exception as e:
            _LOGGER.error(f"Failed to setup enhanced buttons: {e}")


def show_configuration_dialog(parent, current_params=None, app_controller=None) -> Optional[Tuple[Dict[str, Any], bool]]:
    """
    Show configuration dialog and return parameters.
    
    Args:
        parent: Parent window
        current_params: Current parameter values
        app_controller: Application controller for running analysis
        
    Returns:
        Tuple of (parameters dict, analysis_started bool) or None if cancelled
    """
    dialog = PySide6ConfigurationDialog(parent, current_params, app_controller)
    result = dialog.exec()
    
    if result == QtWidgets.QDialog.Accepted:
        return (dialog.get_parameters(), dialog.was_analysis_started())
    else:
        return None 