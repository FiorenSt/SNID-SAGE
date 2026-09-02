"""
SNID Core Module - Unified FFT Storage Architecture
===================================================

This module provides the core components for SNID analysis:
- Unified FFT storage system for optimal performance
- FFT optimization for fast correlations  
- Centralized configuration management
"""

from ..template_fft_storage import TemplateFFTStorage, TemplateEntry
from .config import SNIDConfig

from .integration import (
    integrate_fft_optimization,
    enable_optimization,
    auto_integrate,
    enable_caching_for_cli,
    enable_caching_for_gui,
    get_cache_status,
    clear_global_cache,
    load_templates_unified,
    usable_template_fft,
    resolve_template_fft,
    unique_templates_by_name,
)

__all__ = [
    'TemplateFFTStorage',
    'TemplateEntry', 
    'SNIDConfig',
    'integrate_fft_optimization',
    'enable_optimization',
    'auto_integrate',
    'enable_caching_for_cli',
    'enable_caching_for_gui',
    'get_cache_status',
    'clear_global_cache',
    'load_templates_unified',
    'usable_template_fft',
    'resolve_template_fft',
    'unique_templates_by_name',
] 