"""
SNID SAGE Utils Package
=======================

Shared utilities for SNID SAGE (SuperNova IDentification – Spectral Analysis and Guided Exploration).

Version 1.0.0 - Developed by Fiorenzo Stoppa
Based on the original Fortran SNID by Stéphane Blondin & John L. Tonry
"""

__version__ = "1.0.0"
__author__ = "Fiorenzo Stoppa"

# Add results formatter export
from .results_formatter import UnifiedResultsFormatter, create_unified_formatter, clean_template_name 