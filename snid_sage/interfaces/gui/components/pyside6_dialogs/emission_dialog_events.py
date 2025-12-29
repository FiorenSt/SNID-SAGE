"""
Event Handlers for PySide6 Multi-Step Emission Line Analysis Dialog
==================================================================

This module contains all event handling methods for the emission line dialog,
separated from the main dialog class to reduce file size and improve organization.
"""

from typing import Dict, Any
from PySide6 import QtCore, QtWidgets

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.emission_dialog_events')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.emission_dialog_events')

# Import line detection functions
try:
    from snid_sage.shared.utils.line_detection.line_presets import (
        get_type_ia_lines,
        get_type_ii_lines,
        get_type_ibc_lines,
        get_type_iin_lines,
        get_type_iib_lines,
        get_hydrogen_lines,
        get_helium_lines,
        get_silicon_lines,
        get_iron_lines,
        get_calcium_lines,
        get_oxygen_lines,
        get_balmer_lines,
        get_fe_ii_lines,
        get_fe_iii_lines,
        get_early_sn_lines,
        get_maximum_lines,
        get_late_phase_lines,
        get_nebular_lines,
        get_main_galaxy_lines,
        get_very_strong_lines,
        get_strong_lines,
        get_diagnostic_lines,
        get_common_lines,
        get_emission_lines,
        get_flash_lines,
        get_interaction_lines
    )
    LINE_DETECTION_AVAILABLE = True
except ImportError as e:
    LINE_DETECTION_AVAILABLE = False
    _LOGGER.warning(f"Line detection utilities not available: {e}")


class EmissionDialogEventHandlers:
    """Event handler class for emission line dialog actions"""
    
    def __init__(self, dialog):
        """Initialize with reference to the main dialog"""
        self.dialog = dialog
        
        # Track current selections for smart filtering
        self.current_type = None
        self.current_phase = None
        self.current_element = None
    
    def _get_normalized_spectrum_data(self):
        """Get spectrum data in the format expected by line preset functions"""
        spectrum_data = self.dialog.spectrum_data.copy()
        
        # Ensure the spectrum data has 'wavelength' key for filtering
        if 'wave' in spectrum_data and 'wavelength' not in spectrum_data:
            spectrum_data['wavelength'] = spectrum_data['wave']
        
        return spectrum_data
    
    def on_sn_type_preset_selected(self, text):
        """Handle SN type preset selection with smart filtering"""
        if text == "Select Type..." or text.startswith("Choose"):
            return
            
        try:
            # Update current selection
            self.current_type = text
            
            # Update phase dropdown options based on selected type using JSON DB
            try:
                from snid_sage.shared.utils.line_detection.line_db_loader import get_phase_labels_for_type
                combo = self.dialog.sn_phase_dropdown
                current = combo.currentText() if combo.count() > 0 else None
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("Select Phase..." if not text.startswith("Choose") else "Choose Phase...")
                # Map UI text to internal type keys used in DB
                type_mapping = {
                    "Type Ia": "Ia",
                    "Type II": "II",
                    "Type Ib/c": None,  # combined; we'll union labels from Ib and Ic
                    "Type IIn": "IIn",
                    "Type IIb": "IIb",
                }
                key = type_mapping.get(text)
                labels = []
                if key is None and text == "Type Ib/c":
                    labels = sorted(set(get_phase_labels_for_type("Ib") + get_phase_labels_for_type("Ic")))
                elif key:
                    labels = get_phase_labels_for_type(key)
                # Pretty names
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
                # Append pretty labels
                seen = set()
                for lab in labels:
                    pretty = pretty_map.get(lab, lab)
                    if pretty not in seen:
                        combo.addItem(pretty)
                        seen.add(pretty)
                combo.blockSignals(False)
            except Exception:
                pass

            # Apply smart filtering if we have phase and/or element selections
            lines = self._get_smart_filtered_lines()
            if lines is not None:
                # Replace current SN lines with the smart-filtered result (may be empty)
                self.dialog.sn_lines.clear()
                self.dialog._add_lines_to_plot(lines, is_sn=True)
            else:
                # Fallback to type-only filtering
                spectrum_data = self._get_normalized_spectrum_data()
                
                if text == "Type Ia":
                    lines = get_type_ia_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Type II":
                    lines = get_type_ii_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Type Ib/c":
                    lines = get_type_ibc_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Type IIn":
                    lines = get_type_iin_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Type IIb":
                    lines = get_type_iib_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
            
        except Exception as e:
            _LOGGER.error(f"Error applying SN type preset '{text}': {e}")
    
    def on_sn_phase_preset_selected(self, text):
        """Handle SN phase preset selection with smart filtering"""
        if text == "Select Phase..." or text.startswith("Choose"):
            return
            
        try:
            # Update current selection
            self.current_phase = text
            
            # Apply smart filtering if we have type and/or element selections
            lines = self._get_smart_filtered_lines()
            if lines is not None:
                # Replace current SN lines with the smart-filtered result (may be empty)
                self.dialog.sn_lines.clear()
                self.dialog._add_lines_to_plot(lines, is_sn=True)
            else:
                # Fallback to phase-only filtering
                spectrum_data = self._get_normalized_spectrum_data()
                
                if text == "Early Phase":
                    lines = get_early_sn_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Maximum Light":
                    lines = get_maximum_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Late Phase":
                    lines = get_late_phase_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Nebular Phase":
                    lines = get_nebular_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
            
        except Exception as e:
            _LOGGER.error(f"Error applying SN phase preset '{text}': {e}")
    
    def on_element_preset_selected(self, text):
        """Handle element preset selection with smart filtering"""
        if text == "Select Element..." or text.startswith("Choose"):
            return
            
        try:
            # Update current selection
            self.current_element = text
            
            # Apply smart filtering if we have type and/or phase selections
            lines = self._get_smart_filtered_lines()
            if lines is not None:
                # Replace current SN lines with the smart-filtered result (may be empty)
                self.dialog.sn_lines.clear()
                self.dialog._add_lines_to_plot(lines, is_sn=True)
            else:
                # Fallback to element-only filtering
                spectrum_data = self._get_normalized_spectrum_data()
                
                if text == "Hydrogen":
                    lines = get_hydrogen_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Helium":
                    lines = get_helium_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Silicon":
                    lines = get_silicon_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Iron":
                    lines = get_iron_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Calcium":
                    lines = get_calcium_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Oxygen":
                    lines = get_oxygen_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Balmer Series":
                    lines = get_balmer_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Fe II":
                    lines = get_fe_ii_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
                elif text == "Fe III":
                    lines = get_fe_iii_lines(self.dialog.host_redshift, spectrum_data)
                    self.dialog.sn_lines.clear(); self.dialog._add_lines_to_plot(lines, is_sn=True)
        except Exception as e:
            _LOGGER.error(f"Error selecting element preset {text}: {e}")
    
    def on_other_preset_selected(self, text):
        """Handle other preset selection"""
        if not text:
            return
        
        # Reset smart filtering selections when using other presets
        self.current_type = None
        self.current_phase = None
        self.current_element = None
            
        try:
            spectrum_data = self._get_normalized_spectrum_data()
            
            if text == "Main Galaxy Lines":
                lines = get_main_galaxy_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Very Strong Lines":
                lines = get_very_strong_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Strong Lines":
                lines = get_strong_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Diagnostic Lines":
                lines = get_diagnostic_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Common Lines":
                lines = get_common_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Emission Lines":
                lines = get_emission_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Flash Lines":
                lines = get_flash_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
            elif text == "Interaction Lines":
                lines = get_interaction_lines(self.dialog.host_redshift, spectrum_data)
                self.dialog._add_lines_to_plot(lines, is_sn=False)
                
            # Keep selections visible - don't reset dropdown
            
        except Exception as e:
            _LOGGER.error(f"Error applying other preset '{text}': {e}")

    def _get_smart_filtered_lines(self):
        """Get lines based on current type, phase, and element selections using smart filtering"""
        if not (self.current_type or self.current_phase or self.current_element):
            return None
            
        try:
            from snid_sage.shared.utils.line_detection.line_db_loader import filter_lines
            
            spectrum_data = self._get_normalized_spectrum_data()
            lines_to_add = {}
            
            # Map UI text to internal values
            type_mapping = {
                "Type Ia": ["Ia"],
                "Type II": ["II", "IIn", "IIb"],
                "Type Ib/c": ["Ib", "Ic"],
                "Type IIn": ["IIn"],
                "Type IIb": ["IIb"]
            }
            
            phase_mapping = {
                "Early Phase": ["very_early", "early"],
                "Maximum Light": ["maximum", "peak"],
                "Late Phase": ["late"],
                "Nebular Phase": ["nebular"]
            }
            
            element_mapping = {
                "Hydrogen": "hydrogen",
                "Helium": "helium",
                "Silicon": "silicon",
                "Iron": "iron",
                "Calcium": "calcium",
                "Oxygen": "oxygen",
                "Balmer Series": "hydrogen",  # Special case
                "Fe II": "iron",  # Special case
                "Fe III": "iron"  # Special case
            }
            
            # Get filter criteria
            target_sn_types = type_mapping.get(self.current_type, []) if self.current_type else None
            target_phases = phase_mapping.get(self.current_phase, []) if self.current_phase else None
            target_category = element_mapping.get(self.current_element) if self.current_element else None
            
            # Filter lines based on all active criteria
            for line in filter_lines():
                line_name = line.get('key', '')
                if not line_name:
                    continue
                # Rehydrate minimal structure used downstream
                line_data = {
                    'wavelength': float(line.get('wavelength_air', 0.0) or 0.0),
                    'wavelength_air': float(line.get('wavelength_air', 0.0) or 0.0),
                    'wavelength_vacuum': float(line.get('wavelength_vacuum', 0.0) or 0.0),
                    'sn_types': list(line.get('sn_types', []) or []),
                    'category': line.get('category'),
                    'origin': line.get('origin'),
                    'phase_profiles': line.get('phase_profiles') or {},
                }
                line_matches = True
                
                # Check SN type match
                if target_sn_types:
                    line_sn_types = set(line_data.get('sn_types', []) or [])
                    profiles = line_data.get('phase_profiles') or {}
                    # match if type in sn_types or phase_profiles keys
                    if not any((t in line_sn_types) or (t in profiles) for t in target_sn_types):
                        line_matches = False
                
                # Check phase match (allow 'all' phase to match any selection)
                if target_phases and line_matches:
                    # If any of the selected types is active, restrict by that type's phase labels
                    profiles = line_data.get('phase_profiles') or {}
                    ok_phase = False
                    if target_sn_types:
                        for t in target_sn_types:
                            for prof in profiles.get(t, []) or []:
                                if prof.get('phase_label') in target_phases:
                                    ok_phase = True
                                    break
                            if ok_phase:
                                break
                    else:
                        # No type selected: any matching phase across any type counts
                        for t, arr in profiles.items():
                            for prof in arr or []:
                                if prof.get('phase_label') in target_phases:
                                    ok_phase = True
                                    break
                            if ok_phase:
                                break
                    if not ok_phase:
                        line_matches = False
                
                # Check element category match
                if target_category and line_matches:
                    line_category = line_data.get('category', '')
                    
                    # Special handling for specific element selections
                    if self.current_element == "Balmer Series":
                        # Only include Balmer lines specifically
                        if not any(balmer in line_name for balmer in ['H-alpha', 'H-beta', 'H-gamma', 'H-delta']):
                            line_matches = False
                    elif self.current_element == "Fe II":
                        # Only include Fe II lines
                        if "Fe II" not in line_name:
                            line_matches = False
                    elif self.current_element == "Fe III":
                        # Only include Fe III lines
                        if "Fe III" not in line_name:
                            line_matches = False
                    else:
                        # Standard category matching
                        if line_category != target_category:
                            line_matches = False
                
                # Add line if it matches all criteria and is in spectrum range
                if line_matches:
                    if self._is_line_in_spectrum_range(line_data, self.dialog.host_redshift, spectrum_data):
                        obs_wavelength = line_data['wavelength'] * (1 + self.dialog.host_redshift)
                        lines_to_add[line_name] = (obs_wavelength, line_data)
            
            _LOGGER.info(f"Smart filtering found {len(lines_to_add)} lines for type={self.current_type}, phase={self.current_phase}, element={self.current_element}")
            return lines_to_add
            
        except Exception as e:
            _LOGGER.error(f"Error in smart filtering: {e}")
            return None
    
    def _is_line_in_spectrum_range(self, line_data, current_redshift, spectrum_data):
        """Check if line is within spectrum wavelength range"""
        try:
            if not spectrum_data or 'wavelength' not in spectrum_data:
                # Try alternative key names
                if 'wave' in spectrum_data:
                    wavelength = spectrum_data['wave']
                else:
                    return True  # Allow all lines if no wavelength info
            else:
                wavelength = spectrum_data['wavelength']
            
            obs_wavelength = line_data['wavelength'] * (1 + current_redshift)
            return wavelength[0] <= obs_wavelength <= wavelength[-1]
        except:
            return True  # Allow line if check fails 