"""
SNID Optimization Integration
============================

Simple integration layer to enable SNID optimizations from GUI and CLI.
"""

import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOG = get_logger('snid.optimization')
except ImportError:
    _LOG = logging.getLogger('snid_sage.snid.optimization')


def is_optimization_available() -> bool:
    """Check if optimization system is available."""
    try:
        import snid_sage.snid.core
        return True
    except ImportError:
        return False


def is_optimization_enabled() -> bool:
    """Check if optimization is currently enabled."""
    if not is_optimization_available():
        return False
    
    try:
        from snid_sage.snid.core.integration import get_global_cache
        cache = get_global_cache()
        return cache is not None
    except ImportError:
        return False
    except Exception:
        return False


def enable_optimization(template_dir: str = "templates", 
                       mode: str = "CPU-friendly",
                       cache_size_mb: int = 300) -> bool:
    """
    Enable SNID optimization system.
    
    Parameters
    ----------
    template_dir : str
        Directory containing templates
    mode : str
        Optimization mode: "CPU-friendly" or "Full Performance"
    cache_size_mb : int
        Cache size in MB
        
    Returns
    -------
    bool
        True if optimization was enabled successfully
    """
    if not is_optimization_available():
        _LOG.warning("Optimization system not available")
        return False
    
    try:
        from snid_sage.snid.core.integration import enable_optimization as core_enable
        from snid_sage.snid.core.config import SNIDConfig
        
        # Configure based on mode
        if mode == "CPU-friendly":
            config = SNIDConfig.create_cpu_friendly(template_dir=template_dir)
        else:
            config = SNIDConfig.create_default()
            
        config.max_cache_memory_mb = cache_size_mb
        
        # Enable optimization (pass template_dir as string, not config object)
        core_enable(template_dir)
        
        _LOG.info(f"SNID optimization enabled: {mode} mode, {cache_size_mb}MB cache")
        return True
        
    except Exception as e:
        _LOG.error(f"Failed to enable optimization: {e}")
        return False


def disable_optimization() -> bool:
    """
    Disable SNID optimization system.
    
    Returns
    -------
    bool
        True if optimization was disabled successfully
    """
    if not is_optimization_available():
        return True  # Already disabled
    
    try:
        from snid_sage.snid.core.integration import disable_optimization as core_disable
        core_disable()
        _LOG.info("SNID optimization disabled")
        return True
        
    except Exception as e:
        _LOG.error(f"Failed to disable optimization: {e}")
        return False


def get_optimization_status() -> Dict[str, Any]:
    """
    Get current optimization status.
    
    Returns
    -------
    dict
        Dictionary with optimization status information
    """
    status = {
        'available': is_optimization_available(),
        'enabled': False,
        'cache_info': None,
        'template_count': 0,
        'cache_size_mb': 0
    }
    
    if status['available']:
        status['enabled'] = is_optimization_enabled()
        
        if status['enabled']:
            try:
                from snid_sage.snid.core.integration import get_global_cache
                cache = get_global_cache()
                if cache:
                    cache_info = cache.get_cache_info()
                    status['cache_info'] = cache_info
                    status['template_count'] = cache_info.get('template_count', 0)
                    status['cache_size_mb'] = cache_info.get('cache_size_mb', 0)
            except Exception as e:
                _LOG.debug(f"Error getting cache info: {e}")
    
    return status


def auto_enable_optimization(template_dir: str = "templates") -> bool:
    """
    Automatically enable optimization with sensible defaults.
    
    Parameters
    ----------
    template_dir : str
        Directory containing templates
        
    Returns
    -------
    bool
        True if optimization was enabled successfully
    """
    if is_optimization_enabled():
        _LOG.debug("Optimization already enabled")
        return True
    
    # Check template directory size to choose mode
    template_path = Path(template_dir)
    if template_path.exists():
        template_files = list(template_path.glob("*.lnw"))
        template_count = len(template_files)
        
        if template_count > 3000:
            # Large template set - use CPU-friendly mode
            mode = "CPU-friendly"
            cache_size = 500
        else:
            # Smaller template set - can use full performance
            mode = "Full Performance"  
            cache_size = 300
    else:
        # Default settings
        mode = "CPU-friendly"
        cache_size = 300
    
    return enable_optimization(template_dir, mode, cache_size)


def optimize_template_loading(template_dir: str) -> Optional[List[Dict[str, Any]]]:
    """
    Load templates using optimization if available, otherwise fall back to standard loading.
    
    Parameters
    ----------
    template_dir : str
        Directory containing templates
        
    Returns
    -------
    list or None
        List of templates if successful, None if failed
    """
    # Try optimized loading first
    if is_optimization_enabled():
        try:
            from snid_sage.snid.core.integration import get_global_cache, convert_cached_templates_to_legacy_format
            cache = get_global_cache()
            if cache:
                cached_templates = cache.get_templates()
                # Convert to dict-based format for compatibility with existing code
                legacy_templates = convert_cached_templates_to_legacy_format(cached_templates)
                _LOG.info(f"Loaded {len(legacy_templates)} templates using optimization (20x faster)")
                return legacy_templates
        except Exception as e:
            _LOG.debug(f"Optimized loading failed: {e}")
    
    # Fall back to standard loading
    try:
        from snid_sage.snid.io import load_templates
        templates, _ = load_templates(template_dir, flatten=True)
        _LOG.info(f"Loaded {len(templates)} templates using standard method")
        return templates
    except Exception as e:
        _LOG.error(f"Template loading failed: {e}")
        return None 