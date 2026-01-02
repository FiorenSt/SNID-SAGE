"""
SNID SAGE - Configuration Manager
=================================

Core configuration management system providing business logic for:
- Configuration persistence and loading
- Validation and default values  
- Configuration profiles management
- Shared configuration format across CLI and GUI

Part of the modular configuration architecture following SNID SAGE patterns.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, asdict
import copy

from snid_sage.shared.exceptions.core_exceptions import ConfigurationError
from snid_sage.shared.utils.paths.state_root import get_state_root_dir


@dataclass
class ConfigValidationRule:
    """Validation rule for configuration parameters"""
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    custom_validator: Optional[Callable[[Any], bool]] = None
    error_message: str = "Invalid value"


class ConfigurationManager:
    """
    Core configuration management system for SNID SAGE.
    
    Handles all configuration business logic including:
    - Loading and saving configurations
    - Default value management
    - Validation with custom rules
    - Configuration profiles
    - Cross-platform path handling
    """
    
    def __init__(self):
        """Initialize configuration manager"""
        self.config_dir = self._get_config_directory()
        self.default_config_file = self.config_dir / "snid_sage_config.json"
        self.profiles_dir = self.config_dir / "profiles"
        
        # CONFIG-LESS MODE: Do not create any config files or directories eagerly.
        # Directories/files will not be created; the manager operates purely with defaults
        # unless a caller explicitly writes something. This avoids persistent state surprises.
        
        # Initialize validation rules
        self._validation_rules = self._create_validation_rules()
        
        # Current configuration
        self._current_config = None
        
    def _get_config_directory(self) -> Path:
        """Get platform-appropriate configuration directory.

        By default this is ``~/.snid_sage`` to preserve existing behaviour.
        Advanced users can override the *root* via ``SNID_SAGE_STATE_DIR``,
        in which case the config directory becomes ``<state_root>``.
        """
        return get_state_root_dir()
    
    def _create_validation_rules(self) -> Dict[str, Dict[str, ConfigValidationRule]]:
        """Create validation rules for all configuration categories"""
        return {
            'paths': {
                'templates_dir': ConfigValidationRule(
                    custom_validator=lambda x: not x or Path(x).exists() if x else True,
                    error_message="Templates directory must exist or be empty"
                ),
                'user_templates_dir': ConfigValidationRule(
                    custom_validator=lambda x: self._validate_writable_directory(x),
                    error_message="User templates directory must be writable"
                ),
                'output_dir': ConfigValidationRule(
                    custom_validator=lambda x: self._validate_writable_directory(x),
                    error_message="Output directory must be writable"
                ),
                'data_dir': ConfigValidationRule(
                    custom_validator=lambda x: self._validate_readable_directory(x),
                    error_message="Data directory must be readable"
                ),
                'config_dir': ConfigValidationRule(
                    custom_validator=lambda x: self._validate_writable_directory(x),
                    error_message="Config directory must be writable"
                )
            },
            'analysis': {
                'redshift_min': ConfigValidationRule(
                    min_value=-0.1, max_value=0.5,
                    error_message="Minimum redshift must be between -0.1 and 0.5"
                ),
                'redshift_max': ConfigValidationRule(
                    min_value=0.0, max_value=10.0,
                    error_message="Maximum redshift must be between 0.0 and 10.0"
                ),
                'age_min': ConfigValidationRule(
                    min_value=-1500.0, max_value=1000.0,
                    error_message="Minimum age must be between -1500 and 1000 days"
                ),
                'age_max': ConfigValidationRule(
                    min_value=0.0, max_value=15000.0,
                    error_message="Maximum age must be between 0 and 15000 days"
                ),
                'max_output_templates': ConfigValidationRule(
                    min_value=1, max_value=1000,
                    error_message="Max output templates must be between 1 and 1000"
                ),
                'wavelength_tolerance': ConfigValidationRule(
                    min_value=1.0, max_value=100.0,
                    error_message="Wavelength tolerance must be between 1.0 and 100.0 Å"
                ),
                'lapmin': ConfigValidationRule(
                    min_value=0.0, max_value=1.0,
                    error_message="lapmin must be between 0.0 and 1.0"
                ),

                'wmin': ConfigValidationRule(
                    min_value=1000.0, max_value=50000.0,
                    custom_validator=lambda x: x is None or (1000.0 <= x <= 50000.0),
                    error_message="wmin must be between 1000.0 and 50000.0 Å or None"
                ),
                'wmax': ConfigValidationRule(
                    min_value=1000.0, max_value=50000.0,
                    custom_validator=lambda x: x is None or (1000.0 <= x <= 50000.0),
                    error_message="wmax must be between 1000.0 and 50000.0 Å or None"
                ),
                'emclip_z': ConfigValidationRule(
                    min_value=-1.0, max_value=10.0,
                    error_message="emclip_z must be between -1.0 and 10.0 (-1 to disable)"
                ),
                'emwidth': ConfigValidationRule(
                    min_value=1.0, max_value=1000.0,
                    error_message="emwidth must be between 1.0 and 1000.0 Å"
                )
            },
            'processing': {
                'smoothing_width': ConfigValidationRule(
                    min_value=0.0, max_value=50.0,
                    error_message="Smoothing width must be between 0.0 and 50.0"
                ),
                # SNID-specific processing parameters
                'median_fwmed': ConfigValidationRule(
                    min_value=0.0, max_value=100.0,
                    error_message="median_fwmed must be between 0.0 and 100.0 Å"
                ),
                'medlen': ConfigValidationRule(
                    min_value=1, max_value=51,
                    error_message="medlen must be between 1 and 51 pixels"
                ),
                'apodize_percent': ConfigValidationRule(
                    min_value=0.0, max_value=50.0,
                    error_message="apodize_percent must be between 0.0 and 50.0%"
                )
            },
            'display': {
                'theme': ConfigValidationRule(
                    allowed_values=['light', 'dark'],
                    error_message="Theme must be 'light' or 'dark'"
                ),
                'plot_style': ConfigValidationRule(
                    allowed_values=['default', 'seaborn', 'ggplot', 'bmh', 'fivethirtyeight'],
                    error_message="Invalid plot style"
                ),
                'plot_dpi': ConfigValidationRule(
                    min_value=50, max_value=300,
                    error_message="Plot DPI must be between 50 and 300"
                )
            },
            'output': {
                # Output options are boolean, no special validation needed
            },
            'llm': {
                'llm_provider': ConfigValidationRule(
                    allowed_values=['openrouter', 'local', 'anthropic', 'openai'],
                    error_message="Invalid LLM provider"
                ),
                'model_name': ConfigValidationRule(
                    custom_validator=lambda x: len(x) > 0 if x else True,
                    error_message="Model name cannot be empty if specified"
                ),
                'max_tokens': ConfigValidationRule(
                    min_value=100, max_value=10000,
                    error_message="Max tokens must be between 100 and 10000"
                ),
                'temperature': ConfigValidationRule(
                    min_value=0.0, max_value=2.0,
                    error_message="Temperature must be between 0.0 and 2.0"
                )
            }
        }
    
    def _validate_writable_directory(self, path: str) -> bool:
        """Validate that a directory exists and is writable"""
        if not path:
            return True  # Empty path is valid
        
        try:
            path_obj = Path(path)
            if path_obj.exists():
                return os.access(path_obj, os.W_OK)
            else:
                # Try to create the directory
                path_obj.mkdir(parents=True, exist_ok=True)
                return True
        except (OSError, PermissionError):
            return False
    
    def _validate_readable_directory(self, path: str) -> bool:
        """Validate that a directory exists and is readable"""
        if not path:
            return True  # Empty path is valid
        
        try:
            path_obj = Path(path)
            return path_obj.exists() and os.access(path_obj, os.R_OK)
        except (OSError, PermissionError):
            return False
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        # Use simple template finder to locate templates directory
        try:
            from snid_sage.shared.utils.simple_template_finder import find_templates_directory
            templates_dir = find_templates_directory()
            if templates_dir:
                default_templates_path = str(templates_dir)
            else:
                # Fallback to relative path for GitHub installations
                default_templates_path = str(Path(__file__).parent.parent.parent.parent / 'templates')
        except ImportError:
            # Fallback if simple_template_finder is not available
            default_templates_path = str(Path(__file__).parent.parent.parent.parent / 'templates')
        
        return {
            'paths': {
                'templates_dir': default_templates_path,
                'output_dir': str(Path.cwd() / 'results'),
                'data_dir': str(Path.cwd() / 'data'),
                'config_dir': str(self.config_dir),
                # Optional: explicit user templates dir override
                'user_templates_dir': None
            },
            'analysis': {
                'redshift_min': -0.01,
                'redshift_max': 2.0,
                'age_min': None,
                'age_max': None,
                'max_output_templates': 10,
                'wavelength_tolerance': 10.0,
                # Analysis gating parameters
                'lapmin': 0.3,
                'hsigma_lap_ccc_threshold': 1.5,  # Best-metric threshold for clustering (HσLAP-CCC)

                'wmin': None,  # Optional wavelength limits
                'wmax': None,
                'type_filter': None,  # Optional type filtering
                'emclip_z': -1.0,
                'emwidth': 40.0
            },
            'processing': {
                'enable_flattening': True,
                'enable_smoothing': False,
                'smoothing_width': 0.0,
                'remove_continuum': True,
                'normalize_flux': True,
                'auto_mask_telluric': False,
                # SNID-specific processing parameters
                'median_fwmed': 0.0,
                'medlen': 1,
                'aband_remove': False,
                'skyclip': False,
                'apodize_percent': 10.0,
                'verbose': False,
                'active_profile_id': 'optical'
            },
            'display': {
                'theme': 'light',
                'plot_style': 'default',
                'plot_dpi': 100,
                'show_grid': True,
                'show_markers': True,
                'watercolor_enabled': False
            },
            'output': {
                'save_plots': False,
                'output_fluxed': False,
                'output_flattened': False,
                'output_main': True
            },
            'llm': {
                'llm_provider': 'openrouter',
                'model_name': 'anthropic/claude-3-sonnet:beta',
                'api_key': '',
                'max_tokens': 4000,
                'temperature': 0.7,
                'enable_llm': True
            }
        }
    
    def load_config(self, config_file: Optional[Path] = None) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Args:
            config_file: Optional specific config file path
            
        Returns:
            Configuration dictionary
        """
        # CONFIG-LESS MODE: Always ignore on-disk configuration and return in-memory defaults.
        # This prevents accidental overrides (e.g., profile) from stale files.
        default_config = self.get_default_config()
        self._current_config = default_config
        return default_config
    
    def save_config(self, config: Dict[str, Any], config_file: Optional[Path] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
            config_file: Optional specific config file path
            
        Returns:
            True if successful, False otherwise
        """
        # CONFIG-LESS MODE: No-op persistence. Accept and remember in-memory only.
        # Return True so callers proceed without error, but do not write to disk.
        validation_result = self.validate_config(config)
        if not validation_result.is_valid:
            raise ConfigurationError(f"Configuration validation failed: {validation_result.errors}")
        self._current_config = copy.deepcopy(config)
        return True
    
    def validate_config(self, config: Dict[str, Any]) -> 'ValidationResult':
        """
        Validate configuration against rules.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            ValidationResult with is_valid flag and error details
        """
        errors = []
        warnings = []
        
        for category, category_rules in self._validation_rules.items():
            if category not in config:
                continue
                
            category_config = config[category]
            
            for param_name, rule in category_rules.items():
                if param_name not in category_config:
                    continue
                
                value = category_config[param_name]
                
                # Treat None as "unset": skip min/max/allowed checks; run custom validator if present
                if value is None:
                    if rule.custom_validator is not None:
                        try:
                            if not rule.custom_validator(value):
                                errors.append(f"{category}.{param_name}: {rule.error_message}")
                        except Exception as e:
                            errors.append(f"{category}.{param_name}: Validation error - {e}")
                    continue

                # Check min/max values
                try:
                    if rule.min_value is not None and value < rule.min_value:
                        errors.append(f"{category}.{param_name}: {rule.error_message}")
                        continue
                    
                    if rule.max_value is not None and value > rule.max_value:
                        errors.append(f"{category}.{param_name}: {rule.error_message}")
                        continue
                except TypeError:
                    # Incompatible types (e.g., string vs number); defer to custom validator if provided
                    if rule.custom_validator is not None:
                        try:
                            if not rule.custom_validator(value):
                                errors.append(f"{category}.{param_name}: {rule.error_message}")
                        except Exception as e:
                            errors.append(f"{category}.{param_name}: Validation error - {e}")
                        continue
                    # Otherwise, treat as invalid type
                    errors.append(f"{category}.{param_name}: {rule.error_message}")
                    continue
                
                # Check allowed values
                if rule.allowed_values is not None and value not in rule.allowed_values:
                    errors.append(f"{category}.{param_name}: {rule.error_message}")
                    continue
                
                # Check custom validator
                if rule.custom_validator is not None:
                    try:
                        if not rule.custom_validator(value):
                            errors.append(f"{category}.{param_name}: {rule.error_message}")
                    except Exception as e:
                        errors.append(f"{category}.{param_name}: Validation error - {e}")
        
        # Additional cross-parameter validation (robust to None/non-numeric)
        if 'analysis' in config:
            analysis = config['analysis']

            def _to_float(val):
                try:
                    return float(val)
                except Exception:
                    return None

            zmin = _to_float(analysis.get('redshift_min')) if 'redshift_min' in analysis else None
            zmax = _to_float(analysis.get('redshift_max')) if 'redshift_max' in analysis else None
            if zmin is not None and zmax is not None and zmin >= zmax:
                errors.append("analysis.redshift_min must be less than redshift_max")

            amin = _to_float(analysis.get('age_min')) if 'age_min' in analysis else None
            amax = _to_float(analysis.get('age_max')) if 'age_max' in analysis else None
            if amin is not None and amax is not None and amin >= amax:
                errors.append("analysis.age_min must be less than age_max")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    
    def _deep_merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries"""
        result = copy.deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_configs(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        
        return result
    
    def get_config_profiles(self) -> List[str]:
        """Get list of available configuration profiles"""
        try:
            profiles = []
            for profile_file in self.profiles_dir.glob('*.json'):
                profiles.append(profile_file.stem)
            return sorted(profiles)
        except OSError:
            return []
    
    def save_config_profile(self, config: Dict[str, Any], profile_name: str) -> bool:
        """Save configuration as a named profile"""
        try:
            profile_file = self.profiles_dir / f"{profile_name}.json"
            
            # Update profile metadata
            config = copy.deepcopy(config)
            if 'metadata' not in config:
                config['metadata'] = {}
            config['metadata']['profile_name'] = profile_name
            
            return self.save_config(config, profile_file)
        except Exception as e:
            raise ConfigurationError(f"Failed to save profile '{profile_name}': {e}")
    
    def load_config_profile(self, profile_name: str) -> Dict[str, Any]:
        """Load configuration from a named profile"""
        try:
            profile_file = self.profiles_dir / f"{profile_name}.json"
            if not profile_file.exists():
                raise ConfigurationError(f"Profile '{profile_name}' does not exist")
            
            return self.load_config(profile_file)
        except Exception as e:
            raise ConfigurationError(f"Failed to load profile '{profile_name}': {e}")
    
    def delete_config_profile(self, profile_name: str) -> bool:
        """Delete a configuration profile"""
        try:
            profile_file = self.profiles_dir / f"{profile_name}.json"
            if profile_file.exists():
                profile_file.unlink()
                return True
            return False
        except OSError as e:
            raise ConfigurationError(f"Failed to delete profile '{profile_name}': {e}")
    
    def export_config(self, config: Dict[str, Any], export_path: Path) -> bool:
        """Export configuration to a specific file"""
        try:
            return self.save_config(config, export_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to export configuration: {e}")
    
    def import_config(self, import_path: Path) -> Dict[str, Any]:
        """Import configuration from a specific file"""
        try:
            return self.load_config(import_path)
        except Exception as e:
            raise ConfigurationError(f"Failed to import configuration: {e}")
    
    def get_current_config(self) -> Optional[Dict[str, Any]]:
        """Get the currently loaded configuration"""
        return copy.deepcopy(self._current_config) if self._current_config else None
    
    def reset_to_defaults(self) -> Dict[str, Any]:
        """Reset configuration to default values"""
        default_config = self.get_default_config()
        self._current_config = default_config
        return default_config


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __str__(self) -> str:
        if self.is_valid:
            return "Configuration is valid"
        else:
            return f"Configuration has {len(self.errors)} errors: {'; '.join(self.errors)}"


# Global configuration manager instance
config_manager = ConfigurationManager() 