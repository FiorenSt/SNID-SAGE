"""
SNID SAGE - SuperNova IDentification – Spectral Analysis and Guided Exploration
================================================================================

A comprehensive Python package for supernova spectrum identification and analysis,
focused on spectrum identification and analysis.

Features:
- Spectrum identification and classification
- Template library management
- Batch processing capabilities
- Modern GUI interface
- Command-line interface
- LLM integration for enhanced analysis

Author: Fiorenzo Stoppa
Email: fiorenzo.stoppa@physics.ox.ac.uk
License: MIT
"""

# Get version from setuptools_scm
try:
    from ._version import version as __version__
except ImportError:
    # Fallback for development installs
    try:
        from setuptools_scm import get_version
        __version__ = get_version(root='..', relative_to=__file__)
    except (ImportError, LookupError):
        __version__ = "unknown"

__author__ = "Fiorenzo Stoppa"
__email__ = "fiorenzo.stoppa@physics.ox.ac.uk"
__license__ = "MIT"

# Import main modules
try:
    from . import snid
except ImportError:
    snid = None

try:
    from . import interfaces
except ImportError:
    interfaces = None

try:
    from . import shared
except ImportError:
    shared = None

__all__ = ['snid', 'interfaces', 'shared'] 