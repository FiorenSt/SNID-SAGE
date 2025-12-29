"""
UI Components for PySide6 Multi-Step Emission Line Analysis Dialog
=================================================================

This module contains UI creation functions for the emission line dialog,
separated from the main dialog class to reduce file size and improve organization.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from typing import Dict, Any

# Import flexible number input widget
from snid_sage.interfaces.gui.components.widgets.flexible_number_input import create_flexible_double_input
from snid_sage.shared.utils.line_detection.line_db_loader import (
    get_phase_labels_for_type,
    get_anchors,
)

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.emission_dialog_ui')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.emission_dialog_ui')


class EmissionDialogUIBuilder:
    """UI builder for emission line dialog components"""
    
    def __init__(self, dialog):
        """Initialize with reference to the main dialog"""
        self.dialog = dialog
    
    def create_redshift_controls(self, layout):
        """Create redshift input controls"""
        redshift_group = QtWidgets.QGroupBox("Redshift Configuration")
        redshift_layout = QtWidgets.QVBoxLayout(redshift_group)
        
        # Host redshift (from galaxy/cluster)
        host_layout = QtWidgets.QHBoxLayout()
        host_layout.addWidget(QtWidgets.QLabel("Host z:"))
        
        self.dialog.base_redshift_input = create_flexible_double_input(min_val=-0.1, max_val=5.0, default=0.0)
        self.dialog.base_redshift_input.setValue(self.dialog.host_redshift)
        self.dialog.base_redshift_input.valueChanged.connect(self.dialog._on_base_redshift_changed)
        host_layout.addWidget(self.dialog.base_redshift_input)
        host_layout.addStretch()
        redshift_layout.addLayout(host_layout)
        
        # Ejecta velocity (SN expansion velocity)
        velocity_layout = QtWidgets.QHBoxLayout()
        velocity_layout.addWidget(QtWidgets.QLabel("Ejecta velocity (km/s):"))
        
        self.dialog.velocity_input = create_flexible_double_input(min_val=-50000, max_val=50000, suffix=" km/s", default=0)
        self.dialog.velocity_input.setValue(self.dialog.velocity_shift)
        self.dialog.velocity_input.valueChanged.connect(self.dialog._on_velocity_changed)
        velocity_layout.addWidget(self.dialog.velocity_input)
        velocity_layout.addStretch()
        redshift_layout.addLayout(velocity_layout)
        
        # Redshift info display
        self.dialog.redshift_info_label = QtWidgets.QLabel("Galaxy lines use Host z. SN lines use Host z − v/c (v>0 blueshift).")
        self.dialog.redshift_info_label.setWordWrap(True)
        self.dialog.redshift_info_label.setStyleSheet(f"color: {self.dialog.colors['text_secondary']}; font-style: italic; margin-top: 8px; font-size: 9pt;")
        redshift_layout.addWidget(self.dialog.redshift_info_label)
        
        layout.addWidget(redshift_group)
        
        # Update initial displays
        self.dialog._update_redshift_displays()
    
    def create_mode_selection(self, layout):
        """Create line selection mode buttons"""
        mode_group = QtWidgets.QGroupBox("Line Selection Mode")
        mode_layout = QtWidgets.QVBoxLayout(mode_group)
        
        mode_buttons_layout = QtWidgets.QHBoxLayout()
        
        # Create radio buttons for mode selection - pill styling is automatic now
        self.dialog.sn_button = QtWidgets.QRadioButton("SN Lines")
        self.dialog.sn_button.setChecked(True)
        self.dialog.sn_button.clicked.connect(self.dialog._set_sn_mode)
        # Hint tooltip for quick line preview
        self.dialog.sn_button.setToolTip("Hold Shift to quickly preview all available lines as an overlay")
        mode_buttons_layout.addWidget(self.dialog.sn_button)
        
        self.dialog.galaxy_button = QtWidgets.QRadioButton("Galaxy Lines")
        self.dialog.galaxy_button.clicked.connect(self.dialog._set_galaxy_mode)
        # Hint tooltip for quick line preview
        self.dialog.galaxy_button.setToolTip("Hold Shift to quickly preview all available lines as an overlay")
        mode_buttons_layout.addWidget(self.dialog.galaxy_button)
        
        # Create button group for exclusive selection
        self.dialog.mode_button_group = QtWidgets.QButtonGroup(self.dialog)
        self.dialog.mode_button_group.addButton(self.dialog.sn_button, 0)
        self.dialog.mode_button_group.addButton(self.dialog.galaxy_button, 1)
        
        mode_layout.addLayout(mode_buttons_layout)

        # Inline hint under the mode selection
        hint_label = QtWidgets.QLabel("Tip: Hold Shift to quickly preview all available lines")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet(
            f"color: {self.dialog.colors.get('text_secondary', '#64748b')}; font-style: italic; margin-top: 6px; font-size: 9pt;"
        )
        mode_layout.addWidget(hint_label)
        layout.addWidget(mode_group)
    
    def create_quick_presets(self, layout):
        """Create quick preset dropdowns"""
        presets_group = QtWidgets.QGroupBox()
        presets_layout = QtWidgets.QVBoxLayout(presets_group)
        
        # Add help button to presets group header
        presets_header_layout = QtWidgets.QHBoxLayout()
        presets_header_layout.addWidget(QtWidgets.QLabel("⚡ Quick Line Presets"))
        presets_header_layout.addStretch()
        
        # Help button similar to main GUI
        help_btn = QtWidgets.QPushButton("ℹ")
        help_btn.setFixedSize(25, 25)
        help_btn.setToolTip("Show mouse interaction shortcuts and controls")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: 1px solid #2563eb;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                color: white;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        help_btn.clicked.connect(self.dialog._show_interaction_help)
        presets_header_layout.addWidget(help_btn)
        presets_layout.addLayout(presets_header_layout)
        
        # SN presets on same line - type, phase, element work together
        sn_presets_layout = QtWidgets.QHBoxLayout()
        
        # SN Type dropdown
        sn_presets_layout.addWidget(QtWidgets.QLabel("Type:"))
        self.dialog.sn_type_dropdown = QtWidgets.QComboBox()
        self.dialog.sn_type_dropdown.addItems([
            "Select Type...",
            "Type Ia",
            "Type II", 
            "Type Ib/c",
            "Type IIn",
            "Type IIb"
        ])
        self.dialog.sn_type_dropdown.currentTextChanged.connect(self.dialog.event_handlers.on_sn_type_preset_selected)
        sn_presets_layout.addWidget(self.dialog.sn_type_dropdown)
        
        # SN Phase dropdown
        sn_presets_layout.addWidget(QtWidgets.QLabel("Phase:"))
        self.dialog.sn_phase_dropdown = QtWidgets.QComboBox()
        self.dialog.sn_phase_dropdown.addItems(["Select Phase..."])
        self.dialog.sn_phase_dropdown.currentTextChanged.connect(self.dialog.event_handlers.on_sn_phase_preset_selected)
        sn_presets_layout.addWidget(self.dialog.sn_phase_dropdown)
        
        # Element dropdown
        sn_presets_layout.addWidget(QtWidgets.QLabel("Element:"))
        self.dialog.element_dropdown = QtWidgets.QComboBox()
        self.dialog.element_dropdown.addItems([
            "Select Element...",
            "Hydrogen",
            "Helium", 
            "Silicon",
            "Iron",
            "Calcium",
            "Oxygen",
            "Balmer Series",
            "Fe II",
            "Fe III"
        ])
        self.dialog.element_dropdown.currentTextChanged.connect(self.dialog.event_handlers.on_element_preset_selected)
        sn_presets_layout.addWidget(self.dialog.element_dropdown)
        
        presets_layout.addLayout(sn_presets_layout)
        

        
        # Clear button
        clear_layout = QtWidgets.QHBoxLayout()
        clear_btn = QtWidgets.QPushButton("Clear All Lines")
        clear_btn.clicked.connect(self.dialog._clear_all_lines)
        clear_btn.setProperty("clearButton", True)
        clear_layout.addWidget(clear_btn)
        clear_layout.addStretch()
        presets_layout.addLayout(clear_layout)
        
        layout.addWidget(presets_group)
    
    def create_line_tracker(self, layout):
        """Create line history tracker"""
        history_group = QtWidgets.QGroupBox("📋 Added Lines Tracker")
        history_layout = QtWidgets.QVBoxLayout(history_group)
        
        # Line list
        self.dialog.line_list = QtWidgets.QListWidget()
        self.dialog.line_list.setMaximumHeight(120)
        self.dialog.line_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        history_layout.addWidget(self.dialog.line_list)
        
        # List controls
        list_controls = QtWidgets.QHBoxLayout()
        
        remove_btn = QtWidgets.QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.dialog._remove_selected_lines)
        remove_btn.setProperty("clearButton", True)
        list_controls.addWidget(remove_btn)
        
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.clicked.connect(self.dialog._clear_all_lines)
        list_controls.addWidget(clear_btn)
        
        list_controls.addStretch()
        history_layout.addLayout(list_controls)
        
        layout.addWidget(history_group)
    
    def create_info_section(self, layout):
        """Create a simple info section with basic guidance"""
        info_layout = QtWidgets.QHBoxLayout()
        
        # Info label with basic guidance text
        info_label = QtWidgets.QLabel("ℹ️ Set redshift, choose SN/Galaxy mode, use presets or double-click spectrum")
        info_label.setStyleSheet("font-weight: normal; color: #2563eb; font-size: 10px;")
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
    
    def create_status_display(self, layout):
        """Create line status display"""
        status_group = QtWidgets.QGroupBox("📊 Current Status")
        status_layout = QtWidgets.QVBoxLayout(status_group)
        
        self.dialog.status_label = QtWidgets.QLabel("Mode: SN Lines\nSelected: 0 SN lines, 0 Galaxy lines")
        self.dialog.status_label.setWordWrap(True)
        self.dialog.status_label.setStyleSheet(f"color: {self.dialog.colors.get('text_secondary', '#666')}; font-size: 9pt; padding: 5px;")
        status_layout.addWidget(self.dialog.status_label)
        
        layout.addWidget(status_group)
    
    def create_control_buttons(self, layout):
        """Create control buttons"""
        controls_layout = QtWidgets.QHBoxLayout()
        
        # Help button (replaces Clear Lines which is already available as "Clear All" at top right)
        help_btn = QtWidgets.QPushButton("Help")
        help_btn.setToolTip("Show mouse interaction shortcuts and controls")
        help_btn.clicked.connect(self.dialog._show_interaction_help)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: 2px solid #2563eb;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        controls_layout.addWidget(help_btn)
        
        step2_btn = QtWidgets.QPushButton("Step 2: Analysis")
        step2_btn.clicked.connect(self.dialog._proceed_to_step_2)
        step2_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: 2px solid #059669;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        controls_layout.addWidget(step2_btn)
        
        layout.addLayout(controls_layout)

    def create_compact_preset_toolbar(self):
        """Create a compact preset toolbar for placement above the plot"""
        toolbar_frame = QtWidgets.QFrame()
        toolbar_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        toolbar_layout = QtWidgets.QVBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(8)
        
        # Remove header layout - no title or info button
        
        # Compact preset controls in a single row
        presets_layout = QtWidgets.QHBoxLayout()
        presets_layout.setSpacing(8)
        
        # SN Type dropdown (compact) - no label, placeholder text
        self.dialog.sn_type_dropdown = QtWidgets.QComboBox()
        self.dialog.sn_type_dropdown.addItems([
            "Choose Type...",
            "Type Ia",
            "Type II", 
            "Type Ib/c",
            "Type IIn",
            "Type IIb"
        ])
        self.dialog.sn_type_dropdown.setMaximumWidth(160)
        # When Type changes, update Phase options using JSON DB anchors/labels
        self.dialog.sn_type_dropdown.currentTextChanged.connect(self._on_compact_sn_type_changed)
        # Remove automatic connection - will apply on button click
        presets_layout.addWidget(self.dialog.sn_type_dropdown)
        
        # Separator
        sep1 = QtWidgets.QFrame()
        sep1.setFrameShape(QtWidgets.QFrame.VLine)
        sep1.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep1.setStyleSheet("color: #cbd5e1;")
        presets_layout.addWidget(sep1)
        
        # SN Phase dropdown (compact) - no label, placeholder text
        self.dialog.sn_phase_dropdown = QtWidgets.QComboBox()
        self.dialog.sn_phase_dropdown.addItems(["Choose Phase..."])
        self.dialog.sn_phase_dropdown.setMaximumWidth(160)
        # Remove automatic connection - will apply on button click
        presets_layout.addWidget(self.dialog.sn_phase_dropdown)
        
        # Separator
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.VLine)
        sep2.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep2.setStyleSheet("color: #cbd5e1;")
        presets_layout.addWidget(sep2)
        
        # Element dropdown (compact) - no label, placeholder text, includes "All"
        self.dialog.element_dropdown = QtWidgets.QComboBox()
        self.dialog.element_dropdown.addItems([
            "Choose Element...",
            "All",
            "Hydrogen",
            "Helium", 
            "Silicon",
            "Iron",
            "Calcium",
            "Oxygen",
            "Balmer Series",
            "Fe II",
            "Fe III"
        ])
        self.dialog.element_dropdown.setMaximumWidth(150)
        # Remove automatic connection - will apply on button click
        presets_layout.addWidget(self.dialog.element_dropdown)
        
        # Separator
        sep4 = QtWidgets.QFrame()
        sep4.setFrameShape(QtWidgets.QFrame.VLine)
        sep4.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep4.setStyleSheet("color: #cbd5e1;")
        presets_layout.addWidget(sep4)
        
        # Apply button
        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setMaximumWidth(60)
        apply_btn.clicked.connect(self._apply_preset_selection)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: 1px solid #059669;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        presets_layout.addWidget(apply_btn)
        
        # Separator
        sep5 = QtWidgets.QFrame()
        sep5.setFrameShape(QtWidgets.QFrame.VLine)
        sep5.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep5.setStyleSheet("color: #cbd5e1;")
        presets_layout.addWidget(sep5)
        
        # Clear button (compact)
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setMaximumWidth(80)
        clear_btn.clicked.connect(self.dialog._clear_all_lines)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                border: 1px solid #dc2626;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        presets_layout.addWidget(clear_btn)
        
        presets_layout.addStretch()
        toolbar_layout.addLayout(presets_layout)
        
        return toolbar_frame

    def _on_compact_sn_type_changed(self, text: str):
        """When Type changes in the compact toolbar, refresh Phase choices and select anchor."""
        try:
            if not text or text.startswith("Choose"):
                return
            # Map UI Type to internal keys used in DB
            type_mapping = {
                "Type Ia": ["Ia"],
                "Type II": ["II"],
                "Type Ib/c": ["Ib", "Ic"],
                "Type IIn": ["IIn"],
                "Type IIb": ["IIb"],
            }
            keys = type_mapping.get(text, [])
            if not keys:
                return
            # Gather phase labels for selected type(s)
            labels_set = set()
            for k in keys:
                for lab in get_phase_labels_for_type(k):
                    if lab:
                        labels_set.add(lab)
            labels = sorted(labels_set)
            # Pretty names mapping
            pretty_map = {
                "very_early": "Very Early",
                "early": "Early Phase",
                "maximum": "Maximum Light",
                "postmax": "Post-maximum",
                "late": "Late Phase",
                "nebular": "Nebular Phase",
                "interaction": "Interaction",
                "plateau": "Plateau",
                "transition": "Transition",
                "peak": "Maximum Light",
            }
            # Determine anchor phase from DB anchors
            anchors = get_anchors()
            anchor_label = None
            for k in keys:
                if k in anchors and anchors[k]:
                    anchor_label = anchors[k]
                    break
            # Fall back to first available label if anchor not found
            selected_pretty = None
            if anchor_label and anchor_label in labels:
                selected_pretty = pretty_map.get(anchor_label, anchor_label)
            elif labels:
                selected_pretty = pretty_map.get(labels[0], labels[0])
            # Rebuild Phase dropdown
            combo = self.dialog.sn_phase_dropdown
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Choose Phase...")
            for lab in labels:
                combo.addItem(pretty_map.get(lab, lab))
            # Select anchor/default if available
            if selected_pretty:
                idx = combo.findText(selected_pretty)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        except Exception as e:
            _LOGGER.error(f"Error updating Phase options for Type '{text}': {e}")
    
    def _apply_preset_selection(self):
        """Apply the selected preset combinations when Apply button is clicked with smart filtering"""
        try:
            # Get current selections
            sn_type = self.dialog.sn_type_dropdown.currentText()
            sn_phase = self.dialog.sn_phase_dropdown.currentText()
            element = self.dialog.element_dropdown.currentText()
            
            # Check if we have any SN-related selections
            has_sn_selections = (
                (sn_type and not sn_type.startswith("Choose")) or
                (sn_phase and not sn_phase.startswith("Choose")) or
                (element and not element.startswith("Choose"))
            )
            
            if has_sn_selections:
                # Use smart filtering for interconnected SN type/phase/element selections
                self._apply_smart_filtering(sn_type, sn_phase, element)
            
            # Keep selections visible - don't reset dropdowns to placeholder text
            # This allows users to see what they've selected and potentially build on it
            
        except Exception as e:
            _LOGGER.error(f"Error applying preset selection: {e}")
    
    def _apply_smart_filtering(self, sn_type, sn_phase, element):
        """Apply smart filtering for SN type, phase, and element combinations"""
        try:
            # Reset event handler selections
            self.dialog.event_handlers.current_type = None
            self.dialog.event_handlers.current_phase = None
            self.dialog.event_handlers.current_element = None
            
            # Set selections in order, letting smart filtering work
            if sn_type and not sn_type.startswith("Choose"):
                self.dialog.event_handlers.on_sn_type_preset_selected(sn_type)
            
            if sn_phase and not sn_phase.startswith("Choose"):
                self.dialog.event_handlers.on_sn_phase_preset_selected(sn_phase)
            
            if element and not element.startswith("Choose"):
                # Handle "All" selection for elements
                if element == "All":
                    # Apply all element types one by one with current type/phase context
                    for elem in ["Hydrogen", "Helium", "Silicon", "Iron", "Calcium", "Oxygen"]:
                        # Temporarily set element and get smart filtered lines
                        temp_element = self.dialog.event_handlers.current_element
                        self.dialog.event_handlers.current_element = elem
                        lines = self.dialog.event_handlers._get_smart_filtered_lines()
                        if lines:
                            self.dialog._add_lines_to_plot(lines, is_sn=True)
                        self.dialog.event_handlers.current_element = temp_element
                else:
                    self.dialog.event_handlers.on_element_preset_selected(element)
                    
        except Exception as e:
            _LOGGER.error(f"Error in smart filtering application: {e}") 

    def create_step2_analysis_toolbar(self):
        """Create a toolbar for step 2 showing current line info and key controls"""
        toolbar_frame = QtWidgets.QFrame()
        toolbar_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        toolbar_layout = QtWidgets.QVBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(8)
        
        # Current line info and navigation row
        info_layout = QtWidgets.QHBoxLayout()
        info_layout.setSpacing(12)
        
        # Current line info
        current_line_label = QtWidgets.QLabel("Current Line:")
        current_line_label.setStyleSheet("font-weight: bold; color: #374151;")
        info_layout.addWidget(current_line_label)
        
        # Line selection dropdown (moved from left panel)
        if hasattr(self.dialog, 'step2_analysis') and self.dialog.step2_analysis:
            # Get reference to the dropdown from step2_analysis
            self.dialog.step2_line_dropdown = QtWidgets.QComboBox()
            self.dialog.step2_line_dropdown.setMinimumWidth(120)
            self.dialog.step2_line_dropdown.setMaximumWidth(160)
            info_layout.addWidget(self.dialog.step2_line_dropdown)
        
        # Navigation buttons
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.setSpacing(4)
        
        self.dialog.step2_prev_btn = QtWidgets.QPushButton("◀")
        self.dialog.step2_prev_btn.setMaximumWidth(30)
        self.dialog.step2_prev_btn.setToolTip("Previous line")
        nav_layout.addWidget(self.dialog.step2_prev_btn)
        
        self.dialog.step2_line_counter = QtWidgets.QLabel("Line 1 of 0")
        self.dialog.step2_line_counter.setAlignment(QtCore.Qt.AlignCenter)
        self.dialog.step2_line_counter.setMinimumWidth(80)
        self.dialog.step2_line_counter.setStyleSheet("color: #6b7280; font-weight: bold;")
        nav_layout.addWidget(self.dialog.step2_line_counter)
        
        self.dialog.step2_next_btn = QtWidgets.QPushButton("▶")
        self.dialog.step2_next_btn.setMaximumWidth(30)
        self.dialog.step2_next_btn.setToolTip("Next line")
        nav_layout.addWidget(self.dialog.step2_next_btn)
        
        info_layout.addLayout(nav_layout)
        
        # Separator
        sep1 = QtWidgets.QFrame()
        sep1.setFrameShape(QtWidgets.QFrame.VLine)
        sep1.setFrameShadow(QtWidgets.QFrame.Sunken)
        sep1.setStyleSheet("color: #cbd5e1;")
        info_layout.addWidget(sep1)

        
        # Clear points stays on the left side
        clear_points_btn = QtWidgets.QPushButton("Clear Points")
        clear_points_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                border: 1px solid #4b5563;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        info_layout.addWidget(clear_points_btn)

        # Push Analyze/Finish to the top-right
        info_layout.addStretch()

        analyze_btn = QtWidgets.QPushButton("Analyze")
        analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: 1px solid #059669;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        info_layout.addWidget(analyze_btn)

        # Finish button (red, same styling family as Cancel)
        finish_btn = QtWidgets.QPushButton("Finish")
        finish_btn.setToolTip("Finish and close the analysis")
        finish_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                border: 1px solid #dc2626;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        finish_btn.clicked.connect(self.dialog.accept)
        info_layout.addWidget(finish_btn)
        
        toolbar_layout.addLayout(info_layout)
        
        # Store references for connection later (simplified)
        self.dialog.step2_toolbar_refs = {
            'analyze_btn': analyze_btn,
            'clear_points_btn': clear_points_btn,
            'finish_btn': finish_btn
        }
        
        return toolbar_frame 