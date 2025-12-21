"""
SNID SAGE - Configuration Controller
====================================

Controller for coordinating configuration management between UI and business logic.
Handles user interactions, state transitions, and communication with ConfigurationManager.

Part of the modular configuration architecture following SNID SAGE patterns.
"""

from typing import Dict, Any, Optional, Callable, List
import threading
from pathlib import Path

from snid_sage.shared.utils.config import config_manager, ConfigValidationRule, ValidationResult
from snid_sage.shared.exceptions.core_exceptions import ConfigurationError


class ConfigController:
    """
    Configuration controller coordinating UI and business logic.
    
    Handles:
    - Loading and saving configurations
    - Managing configuration profiles
    - Coordinating validation between UI and manager
    - State transitions and user interactions
    """
    
    def __init__(self, theme_manager=None):
        """Initialize configuration controller"""
        self.theme_manager = theme_manager
        self.config_manager = config_manager
        
        # Current state
        self.current_config = None
        self.unsaved_changes = False
        self.validation_errors = {}
        
        # Callbacks for UI updates
        self.config_changed_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.validation_callbacks: List[Callable[[str, bool, str], None]] = []
        self.profile_callbacks: List[Callable[[List[str]], None]] = []
        
        # Load initial configuration
        self._load_initial_config()
    
    def _load_initial_config(self):
        """Load initial configuration on startup"""
        try:
            self.current_config = self.config_manager.load_config()
            self._notify_config_changed()
        except ConfigurationError as e:
            print(f"⚠️ Error loading initial configuration: {e}")
            self.current_config = self.config_manager.get_default_config()
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return self.current_config.copy() if self.current_config else {}
    
    def get_parameter_config(self) -> Dict[str, Dict[str, Any]]:
        """Get parameter configuration for UI widgets"""
        return {
            'paths': {
                'templates_dir': {
                    'label': 'Templates Directory',
                    'widget_type': 'path',
                    'path_type': 'directory',
                    'validation_rule': self.config_manager._validation_rules['paths']['templates_dir'],
                    'tooltip': 'Directory containing SNID template libraries (HDF5 with template_index.json)'
                },
                'output_dir': {
                    'label': 'Output Directory',
                    'widget_type': 'path',
                    'path_type': 'directory',
                    'validation_rule': self.config_manager._validation_rules['paths']['output_dir'],
                    'tooltip': 'Directory where analysis results and plots will be saved'
                },
                'data_dir': {
                    'label': 'Data Directory',
                    'widget_type': 'path',
                    'path_type': 'directory',
                    'validation_rule': self.config_manager._validation_rules['paths']['data_dir'],
                    'tooltip': 'Default location for input spectrum files'
                },
                'config_dir': {
                    'label': 'Config Directory',
                    'widget_type': 'path',
                    'path_type': 'directory',
                    'validation_rule': self.config_manager._validation_rules['paths']['config_dir'],
                    'tooltip': 'Location for configuration and parameter files'
                }
            },
            'analysis': {
                'redshift_min': {
                    'label': 'Minimum Redshift',
                    'widget_type': 'slider',
                    'slider_config': {'from_': -0.1, 'to': 0.5, 'resolution': 0.001},
                    'validation_rule': self.config_manager._validation_rules['analysis']['redshift_min'],
                    'tooltip': 'Minimum redshift for template matching'
                },
                'redshift_max': {
                    'label': 'Maximum Redshift',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 10.0, 'resolution': 0.1},
                    'validation_rule': self.config_manager._validation_rules['analysis']['redshift_max'],
                    'tooltip': 'Maximum redshift for template matching'
                },
                'age_min': {
                    'label': 'Minimum Age (days)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': -100.0, 'to': 100.0, 'resolution': 1.0},
                    'validation_rule': self.config_manager._validation_rules['analysis']['age_min'],
                    'tooltip': 'Minimum supernova age in days from maximum light'
                },
                'age_max': {
                    'label': 'Maximum Age (days)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 2000.0, 'resolution': 10.0},
                    'validation_rule': self.config_manager._validation_rules['analysis']['age_max'],
                    'tooltip': 'Maximum supernova age in days from maximum light'
                },
                'max_output_templates': {
                    'label': 'Max Output Templates',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 1, 'to': 1000, 'resolution': 1},
                    'validation_rule': self.config_manager._validation_rules['analysis']['max_output_templates'],
                    'tooltip': 'Maximum number of template matches to output'
                },
                'wavelength_tolerance': {
                    'label': 'Wavelength Tolerance (Å)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 1.0, 'to': 100.0, 'resolution': 1.0},
                    'validation_rule': self.config_manager._validation_rules['analysis']['wavelength_tolerance'],
                    'tooltip': 'Tolerance for wavelength matching in Angstroms'
                },
                # Analysis gating parameter
                'lapmin': {
                    'label': 'Overlap Fraction (lapmin)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 1.0, 'resolution': 0.05},
                    'validation_rule': self.config_manager._validation_rules['analysis']['lapmin'],
                    'tooltip': 'Minimum overlap fraction between spectrum and template'
                },

                'wmin': {
                    'label': 'Minimum Wavelength (Å)',
                    'widget_type': 'entry',
                    'validation_rule': self.config_manager._validation_rules['analysis']['wmin'],
                    'tooltip': 'Lower wavelength limit for analysis (leave empty for auto)'
                },
                'wmax': {
                    'label': 'Maximum Wavelength (Å)',
                    'widget_type': 'entry',
                    'validation_rule': self.config_manager._validation_rules['analysis']['wmax'],
                    'tooltip': 'Upper wavelength limit for analysis (leave empty for auto)'
                },
                'emclip_z': {
                    'label': 'Emission Line Clipping Redshift',
                    'widget_type': 'slider',
                    'slider_config': {'from_': -1.0, 'to': 10.0, 'resolution': 0.01},
                    'validation_rule': self.config_manager._validation_rules['analysis']['emclip_z'],
                    'tooltip': 'Redshift for emission line clipping (-1 to disable)'
                },
                'emwidth': {
                    'label': 'Emission Line Width (Å)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 1.0, 'to': 1000.0, 'resolution': 1.0},
                    'validation_rule': self.config_manager._validation_rules['analysis']['emwidth'],
                    'tooltip': 'Width for emission line clipping in Angstroms'
                }
            },
            'processing': {
                'enable_flattening': {
                    'label': 'Enable Flattening',
                    'widget_type': 'checkbox',
                    'tooltip': 'Apply continuum flattening during preprocessing'
                },
                'enable_smoothing': {
                    'label': 'Enable Smoothing',
                    'widget_type': 'checkbox',
                    'tooltip': 'Apply spectral smoothing during preprocessing'
                },
                'smoothing_width': {
                    'label': 'Smoothing Width',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 50.0, 'resolution': 0.5},
                    'validation_rule': self.config_manager._validation_rules['processing']['smoothing_width'],
                    'tooltip': 'Width of smoothing kernel in pixels'
                },
                'remove_continuum': {
                    'label': 'Remove Continuum',
                    'widget_type': 'checkbox',
                    'tooltip': 'Remove continuum during preprocessing'
                },
                'normalize_flux': {
                    'label': 'Normalize Flux',
                    'widget_type': 'checkbox',
                    'tooltip': 'Normalize flux values during preprocessing'
                },
                'auto_mask_telluric': {
                    'label': 'Auto-mask Telluric Lines',
                    'widget_type': 'checkbox',
                    'tooltip': 'Automatically mask telluric absorption lines'
                },
                # SNID-specific processing parameters
                'median_fwmed': {
                    'label': 'Median Filter Width (Å)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 100.0, 'resolution': 0.5},
                    'validation_rule': self.config_manager._validation_rules['processing']['median_fwmed'],
                    'tooltip': 'FWHM of wavelength-weighted median filter (0 to disable)'
                },
                'medlen': {
                    'label': 'Median Filter Length (pixels)',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 1, 'to': 51, 'resolution': 2},
                    'validation_rule': self.config_manager._validation_rules['processing']['medlen'],
                    'tooltip': 'Length of fixed-width median filter in pixels'
                },
                'aband_remove': {
                    'label': 'Remove O₂ A-band',
                    'widget_type': 'checkbox',
                    'tooltip': 'Remove telluric O₂ A-band (7550–7700 Å)'
                },
                'skyclip': {
                    'label': 'Remove Sky Lines',
                    'widget_type': 'checkbox',
                    'tooltip': 'Clip major sky emission lines during preprocessing'
                },
                'apodize_percent': {
                    'label': 'Apodization Percentage',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 50.0, 'resolution': 1.0},
                    'validation_rule': self.config_manager._validation_rules['processing']['apodize_percent'],
                    'tooltip': 'Percentage of spectrum ends to apodize for FFT'
                },
                'verbose': {
                    'label': 'Verbose Output',
                    'widget_type': 'checkbox',
                    'tooltip': 'Enable detailed output during processing'
                }
            },
            'display': {
                'theme': {
                    'label': 'Theme',
                    'widget_type': 'combobox',
                    'values': ['light', 'dark'],
                    'validation_rule': self.config_manager._validation_rules['display']['theme'],
                    'tooltip': 'Application theme (light or dark mode)'
                },
                'plot_style': {
                    'label': 'Plot Style',
                    'widget_type': 'combobox',
                    'values': ['default', 'seaborn', 'ggplot', 'bmh', 'fivethirtyeight'],
                    'validation_rule': self.config_manager._validation_rules['display']['plot_style'],
                    'tooltip': 'Matplotlib plot style for spectrum visualization'
                },
                'plot_dpi': {
                    'label': 'Plot DPI',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 50, 'to': 300, 'resolution': 10},
                    'validation_rule': self.config_manager._validation_rules['display']['plot_dpi'],
                    'tooltip': 'Resolution for saved plots (dots per inch)'
                },
                'show_grid': {
                    'label': 'Show Grid',
                    'widget_type': 'checkbox',
                    'tooltip': 'Display grid lines on plots'
                },
                'show_markers': {
                    'label': 'Show Markers',
                    'widget_type': 'checkbox',
                    'tooltip': 'Show data point markers on plots'
                },
                'watercolor_enabled': {
                    'label': 'Watercolor Theme',
                    'widget_type': 'checkbox',
                    'tooltip': 'Enable watercolor styling for the interface'
                }
            },
            'output': {
                'save_plots': {
                    'label': 'Save All Plots',
                    'widget_type': 'checkbox',
                    'tooltip': 'Automatically save all analysis plots to results directory'
                },
                'save_summary': {
                    'label': 'Save Analysis Summary',
                    'widget_type': 'checkbox',
                    'tooltip': 'Automatically save analysis summary text to results directory'
                }
            },
            'llm': {
                'enable_llm': {
                    'label': 'Enable AI Integration',
                    'widget_type': 'checkbox',
                    'tooltip': 'Enable Large Language Model integration for analysis'
                },
                'llm_provider': {
                    'label': 'LLM Provider',
                    'widget_type': 'combobox',
                    'values': ['openrouter', 'local', 'anthropic', 'openai'],
                    'validation_rule': self.config_manager._validation_rules['llm']['llm_provider'],
                    'tooltip': 'AI service provider for analysis assistance'
                },
                'model_name': {
                    'label': 'Model Name',
                    'widget_type': 'entry',
                    'validation_rule': self.config_manager._validation_rules['llm']['model_name'],
                    'tooltip': 'Specific model to use for AI analysis'
                },
                'api_key': {
                    'label': 'API Key',
                    'widget_type': 'entry',
                    'secure': True,
                    'tooltip': 'API key for the selected LLM provider'
                },
                'max_tokens': {
                    'label': 'Max Tokens',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 100, 'to': 10000, 'resolution': 100},
                    'validation_rule': self.config_manager._validation_rules['llm']['max_tokens'],
                    'tooltip': 'Maximum number of tokens in AI responses'
                },
                'temperature': {
                    'label': 'Temperature',
                    'widget_type': 'slider',
                    'slider_config': {'from_': 0.0, 'to': 2.0, 'resolution': 0.1},
                    'validation_rule': self.config_manager._validation_rules['llm']['temperature'],
                    'tooltip': 'Randomness in AI responses (0.0 = deterministic, 2.0 = creative)'
                }
            }
        }
    
    def update_parameter(self, category: str, param_name: str, value: Any) -> bool:
        """
        Update a single parameter and validate.
        
        Args:
            category: Configuration category (e.g., 'analysis', 'paths')
            param_name: Parameter name
            value: New parameter value
            
        Returns:
            True if update successful, False if validation failed
        """
        try:
            if not self.current_config:
                self.current_config = self.config_manager.get_default_config()
            
            if category not in self.current_config:
                self.current_config[category] = {}
            
            # Update value
            old_value = self.current_config[category].get(param_name)
            self.current_config[category][param_name] = value
            
            # Validate the updated configuration
            validation_result = self.config_manager.validate_config(self.current_config)
            
            if validation_result.is_valid:
                self.unsaved_changes = True
                self._notify_config_changed()
                self._clear_validation_error(category, param_name)
                return True
            else:
                # Revert on validation failure
                if old_value is not None:
                    self.current_config[category][param_name] = old_value
                else:
                    del self.current_config[category][param_name]
                
                # Find relevant error messages
                param_errors = [err for err in validation_result.errors 
                              if f"{category}.{param_name}" in err]
                error_msg = '; '.join(param_errors) if param_errors else "Validation failed"
                
                self._set_validation_error(category, param_name, error_msg)
                return False
                
        except Exception as e:
            self._set_validation_error(category, param_name, str(e))
            return False
    
    def validate_all_parameters(self) -> ValidationResult:
        """Validate entire configuration"""
        if not self.current_config:
            return ValidationResult(True, [], [])
        
        try:
            return self.config_manager.validate_config(self.current_config)
        except Exception as e:
            return ValidationResult(False, [str(e)], [])
    
    def save_configuration(self, config_file: Optional[Path] = None) -> bool:
        """Save current configuration"""
        try:
            if not self.current_config:
                return False
            
            success = self.config_manager.save_config(self.current_config, config_file)
            if success:
                self.unsaved_changes = False
                self._notify_config_changed()
            return success
            
        except ConfigurationError as e:
            print(f"❌ Error saving configuration: {e}")
            return False
    
    def load_configuration(self, config_file: Optional[Path] = None) -> bool:
        """Load configuration from file"""
        try:
            self.current_config = self.config_manager.load_config(config_file)
            self.unsaved_changes = False
            self.validation_errors.clear()
            self._notify_config_changed()
            return True
            
        except ConfigurationError as e:
            print(f"❌ Error loading configuration: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults"""
        try:
            self.current_config = self.config_manager.reset_to_defaults()
            self.unsaved_changes = True
            self.validation_errors.clear()
            self._notify_config_changed()
            return True
            
        except Exception as e:
            print(f"❌ Error resetting configuration: {e}")
            return False
    
    def get_config_profiles(self) -> List[str]:
        """Get list of available configuration profiles"""
        try:
            return self.config_manager.get_config_profiles()
        except Exception as e:
            print(f"❌ Error getting profiles: {e}")
            return []
    
    def save_config_profile(self, profile_name: str) -> bool:
        """Save current configuration as a profile"""
        try:
            if not self.current_config:
                return False
            
            success = self.config_manager.save_config_profile(self.current_config, profile_name)
            if success:
                self._notify_profiles_changed()
            return success
            
        except ConfigurationError as e:
            print(f"❌ Error saving profile: {e}")
            return False
    
    def load_config_profile(self, profile_name: str) -> bool:
        """Load configuration from a profile"""
        try:
            self.current_config = self.config_manager.load_config_profile(profile_name)
            self.unsaved_changes = False
            self.validation_errors.clear()
            self._notify_config_changed()
            return True
            
        except ConfigurationError as e:
            print(f"❌ Error loading profile: {e}")
            return False
    
    def delete_config_profile(self, profile_name: str) -> bool:
        """Delete a configuration profile"""
        try:
            success = self.config_manager.delete_config_profile(profile_name)
            if success:
                self._notify_profiles_changed()
            return success
            
        except ConfigurationError as e:
            print(f"❌ Error deleting profile: {e}")
            return False
    
    def export_configuration(self, export_path: Path) -> bool:
        """Export configuration to file"""
        try:
            if not self.current_config:
                return False
            
            return self.config_manager.export_config(self.current_config, export_path)
            
        except ConfigurationError as e:
            print(f"❌ Error exporting configuration: {e}")
            return False
    
    def import_configuration(self, import_path: Path) -> bool:
        """Import configuration from file"""
        try:
            self.current_config = self.config_manager.import_config(import_path)
            self.unsaved_changes = True
            self.validation_errors.clear()
            self._notify_config_changed()
            return True
            
        except ConfigurationError as e:
            print(f"❌ Error importing configuration: {e}")
            return False
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes"""
        return self.unsaved_changes
    
    def get_validation_errors(self) -> Dict[str, str]:
        """Get current validation errors"""
        return self.validation_errors.copy()
    
    def _set_validation_error(self, category: str, param_name: str, error_msg: str):
        """Set validation error for parameter"""
        key = f"{category}.{param_name}"
        self.validation_errors[key] = error_msg
        self._notify_validation_error(key, False, error_msg)
    
    def _clear_validation_error(self, category: str, param_name: str):
        """Clear validation error for parameter"""
        key = f"{category}.{param_name}"
        if key in self.validation_errors:
            del self.validation_errors[key]
        self._notify_validation_error(key, True, "")
    
    # Callback management
    def add_config_changed_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for configuration changes"""
        self.config_changed_callbacks.append(callback)
    
    def add_validation_callback(self, callback: Callable[[str, bool, str], None]):
        """Add callback for validation results"""
        self.validation_callbacks.append(callback)
    
    def add_profile_callback(self, callback: Callable[[List[str]], None]):
        """Add callback for profile list changes"""
        self.profile_callbacks.append(callback)
    
    def _notify_config_changed(self):
        """Notify all callbacks of configuration changes"""
        if self.current_config:
            for callback in self.config_changed_callbacks:
                try:
                    callback(self.current_config.copy())
                except Exception as e:
                    print(f"⚠️ Error in config changed callback: {e}")
    
    def _notify_validation_error(self, param_key: str, is_valid: bool, message: str):
        """Notify validation callbacks"""
        for callback in self.validation_callbacks:
            try:
                callback(param_key, is_valid, message)
            except Exception as e:
                print(f"⚠️ Error in validation callback: {e}")
    
    def _notify_profiles_changed(self):
        """Notify profile callbacks"""
        profiles = self.get_config_profiles()
        for callback in self.profile_callbacks:
            try:
                callback(profiles)
            except Exception as e:
                print(f"⚠️ Error in profile callback: {e}")


# Global configuration controller instance
config_controller = ConfigController() 
