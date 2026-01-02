"""
SNID SAGE - Shared Types Package
================================

This package contains all type definitions and data structures used
throughout SNID SAGE for type safety and consistency.
"""

# Import all spectrum types
from .spectrum_types import *
from .result_types import *

# Version information
__version__ = '1.0.0'
__author__ = 'SNID SAGE Team'

# Make all types easily accessible
__all__ = [
    # Enums
    'SpectrumFormat',
    'TemplateType', 
    'OutputFormat',
    'AnalysisStatus',
    
    # Spectrum data structures
    'SpectrumData',
    'ProcessedSpectrum',
    'TemplateMatch',
    
    # Line and analysis structures
    'LineIdentification',
    'MaskRegion',
    'AnalysisParameters',
    'QualityMetrics',
    
    # Result structures
    'AnalysisSession',
    'SummaryReport',
    'DetailedReport',
    'ExportOptions',
    'ComparisonResult',
    'ValidationResult',
    'PerformanceMetrics',
    
    # Type aliases
    'WavelengthArray',
    'FluxArray',
    'ErrorArray',
    'RedshiftRange',
    'WavelengthRange',
    'TemplateList'
] 