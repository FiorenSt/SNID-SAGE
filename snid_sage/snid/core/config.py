"""
Configuration Management for SNID
=================================

This module provides centralized configuration management for SNID analysis,
supporting both file-based and programmatic configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import json
import yaml
import logging

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOG = get_logger('snid.config')
except ImportError:
    _LOG = logging.getLogger('snid_sage.snid.config')


@dataclass
class SNIDConfig:
    """
    Centralized configuration for SNID analysis.
    
    This configuration class supports all SNID analysis parameters
    and can be loaded from files or created programmatically.
    """
    
    # Template settings
    template_dir: Union[str, Path] = "templates/"
    use_unified_storage: bool = True
    max_cache_memory_mb: int = 500
    precompute_template_ffts: bool = True
    
    # Preprocessing options
    median_fwmed: float = 0.0
    medlen: int = 1
    aband_remove: bool = False
    skyclip: bool = False
    emclip_z: float = -1.0
    emwidth: float = 40.0
    wavelength_masks: Optional[List[tuple]] = None
    apodize_percent: float = 10.0
    skip_preprocessing_steps: List[str] = field(default_factory=list)
    
    # Analysis parameters
    zmin: float = -0.01
    zmax: float = 1.0
    age_range: Optional[tuple] = None
    type_filter: Optional[List[str]] = None
    template_filter: Optional[List[str]] = None
    peak_window_size: int = 10
    lapmin: float = 0.3
    # Best-metric threshold for clustering (HσLAP-CCC: (height × lap × CCC) / sqrt(sigma_z))
    hsigma_lap_ccc_threshold: float = 1.5

    forced_redshift: Optional[float] = None
    
    # Correlation settings
    correlation_method: str = "fft"  # "fft" or "direct"
    use_fft_caching: bool = True
    
    # FFT Optimization settings
    use_vectorized_fft: bool = True  # NEW: Use vectorized FFT cross-correlation (6.6x faster)
    fft_fallback: bool = True
    
    # Clustering options
    use_clustering: bool = True
    clustering_method: str = "type_specific_gmm"
    min_cluster_size: int = 3
    max_clusters_per_type: int = 4
    adaptive_clustering: bool = True
    
    # Output options
    max_output_templates: int = 5
    max_plot_templates: int = 20
    output_main: bool = True
    output_fluxed: bool = False
    output_flattened: bool = False
    output_correlation: bool = False
    output_plots: bool = True
    plot_types: List[str] = field(default_factory=lambda: ['flux', 'flat'])
    
    # Performance settings
    max_memory_usage_mb: int = 1000
    use_parallel_processing: bool = False
    n_cores: Optional[int] = None
    
    # Logging and verbosity
    verbose: bool = False
    log_level: str = "INFO"
    
    # New CPU-friendly configuration options
    use_batch_loading: bool = True
    use_disk_cache: bool = True
    cache_validation_interval: int = 3600
    memory_cleanup_threshold: int = 400
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Convert string paths to Path objects
        if isinstance(self.template_dir, str):
            self.template_dir = Path(self.template_dir)
        
        # Validate filters
        if self.type_filter and not isinstance(self.type_filter, list):
            self.type_filter = [self.type_filter]
        
        if self.template_filter and not isinstance(self.template_filter, list):
            self.template_filter = [self.template_filter]
        
        # Validate ranges
        if self.age_range and len(self.age_range) != 2:
            raise ValueError("age_range must be a tuple of (min_age, max_age)")
        
        if self.zmin >= self.zmax:
            raise ValueError("zmin must be less than zmax")
    
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'SNIDConfig':
        """
        Load configuration from a YAML or JSON file.
        
        Parameters
        ----------
        config_path : str or Path
            Path to configuration file
            
        Returns
        -------
        SNIDConfig
            Loaded configuration
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif config_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    raise ValueError(f"Unsupported config file format: {config_path.suffix}")
            
            # Remove any None values to use defaults
            data = {k: v for k, v in data.items() if v is not None}
            
            _LOG.info(f"Loaded configuration from {config_path}")
            return cls(**data)
            
        except Exception as e:
            _LOG.error(f"Failed to load configuration from {config_path}: {e}")
            raise
    
    def save_to_file(self, config_path: Union[str, Path], format: str = "yaml") -> None:
        """
        Save configuration to a file.
        
        Parameters
        ----------
        config_path : str or Path
            Path to save configuration
        format : str, optional
            File format ("yaml" or "json")
        """
        config_path = Path(config_path)
        
        # Convert to dictionary
        data = self.to_dict()
        
        try:
            with open(config_path, 'w') as f:
                if format.lower() == "yaml":
                    yaml.dump(data, f, default_flow_style=False, indent=2)
                elif format.lower() == "json":
                    json.dump(data, f, indent=2)
                else:
                    raise ValueError(f"Unsupported format: {format}")
            
            _LOG.info(f"Saved configuration to {config_path}")
            
        except Exception as e:
            _LOG.error(f"Failed to save configuration to {config_path}: {e}")
            raise
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                data[key] = str(value)
            else:
                data[key] = value
        return data
    
    def update(self, **kwargs) -> 'SNIDConfig':
        """
        Create a new configuration with updated parameters.
        
        Parameters
        ----------
        **kwargs
            Parameters to update
            
        Returns
        -------
        SNIDConfig
            New configuration with updated parameters
        """
        current_dict = self.to_dict()
        current_dict.update(kwargs)
        return SNIDConfig(**current_dict)
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get configuration parameters for template cache."""
        return {
            'template_dir': str(self.template_dir),
            'precompute_ffts': self.precompute_template_ffts,
            'max_memory_mb': self.max_cache_memory_mb,
            'use_disk_cache': True
        }
    
    def get_preprocessing_config(self) -> Dict[str, Any]:
        """Get configuration parameters for preprocessing."""
        return {
            'median_fwmed': self.median_fwmed,
            'medlen': self.medlen,
            'aband_remove': self.aband_remove,
            'skyclip': self.skyclip,
            'emclip_z': self.emclip_z,
            'emwidth': self.emwidth,
            'wavelength_masks': self.wavelength_masks,
            'apodize_percent': self.apodize_percent,
            'skip_steps': self.skip_preprocessing_steps
        }
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get configuration parameters for analysis."""
        return {
            'zmin': self.zmin,
            'zmax': self.zmax,
            'age_range': self.age_range,
            'type_filter': self.type_filter,
            'template_filter': self.template_filter,
            'peak_window_size': self.peak_window_size,
            'lapmin': self.lapmin,
            'hsigma_lap_ccc_threshold': self.hsigma_lap_ccc_threshold,

            'forced_redshift': self.forced_redshift
        }
    
    def get_clustering_config(self) -> Dict[str, Any]:
        """Get configuration parameters for clustering."""
        return {
            'use_clustering': self.use_clustering,
            'clustering_method': self.clustering_method,
            'min_cluster_size': self.min_cluster_size,
            'max_clusters_per_type': self.max_clusters_per_type,
            'adaptive_clustering': self.adaptive_clustering
        }
    
    @classmethod
    def create_default(cls) -> 'SNIDConfig':
        """Create a default configuration."""
        return cls()
    
    @classmethod
    def create_fast(cls, template_dir: Union[str, Path]) -> 'SNIDConfig':
        """
        Create a configuration optimized for speed.
        
        Parameters
        ----------
        template_dir : str or Path
            Directory containing templates
            
        Returns
        -------
        SNIDConfig
            Speed-optimized configuration
        """
        return cls(
            template_dir=template_dir,
            use_unified_storage=True,
            precompute_template_ffts=True,
            max_cache_memory_mb=1000,
            use_fft_caching=True,
            use_clustering=True,
            adaptive_clustering=True,
            use_parallel_processing=True,
            output_plots=False,  # Skip plots for speed
            verbose=False
        )
    
    @classmethod
    def create_detailed(cls, template_dir: Union[str, Path]) -> 'SNIDConfig':
        """
        Create a configuration for detailed analysis.
        
        Parameters
        ----------
        template_dir : str or Path
            Directory containing templates
            
        Returns
        -------
        SNIDConfig
            Detailed analysis configuration
        """
        return cls(
            template_dir=template_dir,
            use_unified_storage=True,
            precompute_template_ffts=True,
            use_clustering=True,
            output_main=True,
            output_fluxed=True,
            output_flattened=True,
            output_correlation=True,
            output_plots=True,
            max_plot_templates=50,
            verbose=True
        )
    
    @classmethod
    def create_cpu_friendly(cls, template_dir: str) -> 'SNIDConfig':
        """
        Create CPU-friendly configuration that reduces CPU load and fan activity.
        
        This configuration disables CPU-intensive operations to prevent laptop
        fans from spinning up while still providing significant speedup.
        
        Parameters
        ----------
        template_dir : str
            Directory containing templates
            
        Returns
        -------
        SNIDConfig
            CPU-friendly configuration
        """
        return cls(
            template_dir=template_dir,
            use_unified_storage=True,
            precompute_template_ffts=False,  # ⚡ DISABLE: CPU-intensive FFT pre-computation
            max_cache_memory_mb=300,         # 🧠 REDUCE: Lower memory usage  
            use_clustering=False,            # ⚡ DISABLE: CPU-intensive clustering
            
            # Template loading optimizations (keep these - they're not CPU intensive)
            use_batch_loading=True,
            use_disk_cache=True,
            
            # Reduce background processing
            cache_validation_interval=3600,  # Check cache less frequently
            
            # Memory management (less aggressive = less CPU)
            memory_cleanup_threshold=400,    # Clean up less often
            
            verbose=False                    # Reduce logging overhead
        )


def load_config(config_path: Optional[Union[str, Path]] = None) -> SNIDConfig:
    """
    Load SNID configuration from file or create default.
    
    Parameters
    ----------
    config_path : str, Path, or None
        Path to configuration file. If None, creates default config.
        
    Returns
    -------
    SNIDConfig
        Loaded or default configuration
    """
    if config_path is None:
        return SNIDConfig.create_default()
    else:
        return SNIDConfig.from_file(config_path)


# Example configuration templates
EXAMPLE_CONFIGS = {
    'default': {
        'template_dir': 'templates/',
        'use_unified_storage': True,
        'verbose': False,
        'output_plots': True
    },
    
    'fast': {
        'template_dir': 'templates/',
        'use_unified_storage': True,
        'precompute_template_ffts': True,
        'max_cache_memory_mb': 1000,
        'use_clustering': True,
        'adaptive_clustering': True,
        'output_plots': False,
        'verbose': False
    },
    
    'detailed': {
        'template_dir': 'templates/',
        'use_unified_storage': True,
        'use_clustering': True,
        'output_main': True,
        'output_fluxed': True,
        'output_flattened': True,
        'output_correlation': True,
        'output_plots': True,
        'max_plot_templates': 50,
        'verbose': True
    }
} 
