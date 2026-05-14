"""
SNID SAGE - PySide6 Helper Utilities
====================================

Collection of helper functions for GUI operations, data validation,
and common UI tasks specific to the PySide6 interface.

This module provides framework-agnostic utilities.
"""

import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from PySide6 import QtWidgets, QtCore

# Import the centralized logging system
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.pyside6_helpers')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.pyside6_helpers')

try:
    from snid_sage.interfaces.gui.utils.display_spectrum import filter_processed_spectrum_display_range
except Exception:
    filter_processed_spectrum_display_range = None


class PySide6Helpers:
    """Collection of helper methods for PySide6 GUI operations"""
    
    @staticmethod
    def safe_float(value, default=0.0):
        """Safely convert value to float, return default if conversion fails
        
        Parameters:
        -----------
        value : any
            Value to convert to float
        default : float
            Default value to return if conversion fails
            
        Returns:
        --------
        float : Converted value or default
        """
        if value is None or value == '':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_int(value, default=0):
        """Safely convert value to int, return default if conversion fails
        
        Parameters:
        -----------
        value : any
            Value to convert to int
        default : int
            Default value to return if conversion fails
            
        Returns:
        --------
        int : Converted value or default
        """
        if value is None or value == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_bool(value, default=False):
        """Safely convert value to bool, return default if conversion fails
        
        Parameters:
        -----------
        value : any
            Value to convert to bool
        default : bool
            Default value to return if conversion fails
            
        Returns:
        --------
        bool : Converted value or default
        """
        if value is None or value == '':
            return default
        try:
            if isinstance(value, str):
                return value.lower() in ('1', 'true', 'yes', 'on')
            return bool(int(value))
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def filter_nonzero_spectrum(wave, flux, processed_spectrum=None):
        """Filter out zero-padded regions from spectrum data
        
        Uses the selected display flux and mask bins to hide leading/trailing
        regions that are padding or were cut during preprocessing.
        
        Parameters:
        -----------
        wave : array
            Wavelength array
        flux : array  
            Flux array
        processed_spectrum : dict, optional
            Processed spectrum dictionary containing edge information
            
        Returns:
        --------
        tuple : (filtered_wave, filtered_flux)
            Arrays with zero-padded regions removed
        """
        try:
            if filter_processed_spectrum_display_range is not None:
                return filter_processed_spectrum_display_range(wave, flux, processed_spectrum)

            valid_mask = (flux != 0) & np.isfinite(flux)
            if np.any(valid_mask):
                left_edge = np.argmax(valid_mask)
                right_edge = len(flux) - 1 - np.argmax(valid_mask[::-1])
                return wave[left_edge:right_edge + 1], flux[left_edge:right_edge + 1]

            return wave, flux
            
        except Exception as e:
            _LOGGER.warning(f"Warning: Error filtering nonzero spectrum: {e}")
            return wave, flux
    
    @staticmethod
    def center_window(window, width=None, height=None):
        """Center a PySide6 window on the screen
        
        Parameters:
        -----------
        window : QWidget
            Window to center
        width : int, optional
            Window width (uses current width if not specified)
        height : int, optional
            Window height (uses current height if not specified)
        """
        try:
            # Get window dimensions
            if width is None:
                width = window.width()
            if height is None:
                height = window.height()
            
            # Get screen dimensions
            screen = QtWidgets.QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
            
            # Calculate center position
            x = (screen_width // 2) - (width // 2)
            y = (screen_height // 2) - (height // 2)
            
            # Ensure window is not off-screen
            x = max(0, min(x, screen_width - width))
            y = max(0, min(y, screen_height - height))
            
            window.setGeometry(x, y, width, height)
            
        except Exception as e:
            _LOGGER.warning(f"Warning: Could not center window: {e}")
    
    @staticmethod
    def validate_numeric_input(value, min_val=None, max_val=None, parent=None):
        """Validate numeric input and show error if invalid
        
        Parameters:
        -----------
        value : str
            Input value to validate
        min_val : float, optional
            Minimum allowed value
        max_val : float, optional
            Maximum allowed value
        parent : QWidget, optional
            Parent widget for error dialog
            
        Returns:
        --------
        tuple : (is_valid, converted_value)
            Whether input is valid and the converted numeric value
        """
        try:
            num_val = float(value)
            
            if min_val is not None and num_val < min_val:
                QtWidgets.QMessageBox.critical(parent, "Invalid Input", f"Value must be >= {min_val}")
                return False, None
            
            if max_val is not None and num_val > max_val:
                QtWidgets.QMessageBox.critical(parent, "Invalid Input", f"Value must be <= {max_val}")
                return False, None
            
            return True, num_val
            
        except ValueError:
            QtWidgets.QMessageBox.critical(parent, "Invalid Input", "Please enter a valid number")
            return False, None
    
    @staticmethod
    def show_info_dialog(title, message, details=None, parent=None):
        """Show an information dialog with optional details
        
        Parameters:
        -----------
        title : str
            Dialog title
        message : str
            Main message
        details : str, optional
            Additional details to show
        parent : QWidget, optional
            Parent widget
        """
        if details:
            # Use detailed message box
            msg_box = QtWidgets.QMessageBox(parent)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.setDetailedText(details)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.exec()
        else:
            QtWidgets.QMessageBox.information(parent, title, message)
    
    @staticmethod
    def parse_wavelength_masks(mask_str):
        """Parse wavelength mask string into list of tuples
        
        Parameters:
        -----------
        mask_str : str
            String containing wavelength masks in various formats
            
        Returns:
        --------
        list : List of (start, end) tuples for wavelength ranges
        """
        try:
            if not mask_str or mask_str.strip() == '':
                return []
            
            masks = []
            # Split by commas or semicolons
            parts = mask_str.replace(';', ',').split(',')
            
            for part in parts:
                part = part.strip()
                if '-' in part:
                    # Range format: "4000-5000"
                    range_parts = part.split('-')
                    if len(range_parts) == 2:
                        try:
                            start = float(range_parts[0].strip())
                            end = float(range_parts[1].strip())
                            if start < end:
                                masks.append((start, end))
                        except ValueError:
                            continue
                elif ':' in part:
                    # Alternative range format: "4000:5000"
                    range_parts = part.split(':')
                    if len(range_parts) == 2:
                        try:
                            start = float(range_parts[0].strip())
                            end = float(range_parts[1].strip())
                            if start < end:
                                masks.append((start, end))
                        except ValueError:
                            continue
            
            return masks
            
        except Exception as e:
            _LOGGER.warning(f"Warning: Error parsing wavelength masks: {e}")
            return []
    
    @staticmethod
    def format_wavelength_masks(masks):
        """Format wavelength masks list back to string
        
        Parameters:
        -----------
        masks : list
            List of (start, end) tuples
            
        Returns:
        --------
        str : Formatted mask string
        """
        try:
            if not masks:
                return ""
            
            mask_strings = []
            for start, end in masks:
                mask_strings.append(f"{start:.1f}-{end:.1f}")
            
            return ", ".join(mask_strings)
            
        except Exception as e:
            _LOGGER.warning(f"Warning: Error formatting wavelength masks: {e}")
            return ""
    
    @staticmethod
    def handle_exception(exception, context="", parent=None):
        """Handle exceptions with user-friendly error display
        
        Parameters:
        -----------
        exception : Exception
            Exception that occurred
        context : str
            Context where exception occurred
        parent : QWidget, optional
            Parent widget for error dialog
        """
        error_msg = str(exception)
        if context:
            full_msg = f"Error in {context}:\n\n{error_msg}"
        else:
            full_msg = f"An error occurred:\n\n{error_msg}"
        
        _LOGGER.error(f"❌ Exception: {full_msg}")
        QtWidgets.QMessageBox.critical(parent, "Error", full_msg) 