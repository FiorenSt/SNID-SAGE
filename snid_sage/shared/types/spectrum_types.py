"""
Spectrum Type Definitions for SNID SAGE
=======================================

Data structure definitions and type hints for spectrum analysis.
These types provide structure and type safety throughout the application.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Union, Tuple
import numpy as np
from enum import Enum


class SpectrumFormat(Enum):
    """Supported spectrum file formats"""
    ASCII = "ascii"
    FITS = "fits"
    TEXT = "text"
    DAT = "dat"
    FLM = "flm"
    UNKNOWN = "unknown"


class TemplateType(Enum):
    """Template supernova types"""
    TYPE_IA = "Ia"
    TYPE_IB = "Ib" 
    TYPE_IC = "Ic"
    TYPE_II = "II"
    TYPE_IIN = "IIn"
    TYPE_IIP = "IIp"
    TYPE_UNKNOWN = "unknown"


@dataclass
class SpectrumData:
    """
    Core spectrum data structure.
    
    Contains wavelength, flux, and optional error arrays along with metadata.
    """
    wavelength: np.ndarray
    flux: np.ndarray
    error: Optional[np.ndarray] = None
    header: Optional[Dict[str, Any]] = None
    filename: Optional[str] = None
    format: SpectrumFormat = SpectrumFormat.UNKNOWN
    units: Dict[str, str] = field(default_factory=lambda: {"wavelength": "Angstrom", "flux": "arbitrary"})
    
    def __post_init__(self):
        """Validate spectrum data after initialization"""
        if len(self.wavelength) != len(self.flux):
            raise ValueError("Wavelength and flux arrays must have the same length")
        if self.error is not None and len(self.error) != len(self.flux):
            raise ValueError("Error array must have the same length as flux array")


@dataclass
class ProcessedSpectrum:
    """
    Processed spectrum data structure.
    
    Contains the processed spectrum along with processing history and parameters.
    """
    original: SpectrumData
    processed: SpectrumData
    processing_steps: List[str] = field(default_factory=list)
    processing_params: Dict[str, Any] = field(default_factory=dict)
    mask_ranges: List[Tuple[float, float]] = field(default_factory=list)
    
    
@dataclass
class TemplateMatch:
    """
    Individual template match result.
    
    Contains information about a single template match including correlation scores.
    """
    template_name: str
    template_type: TemplateType
    template_subtype: Optional[str] = None
    redshift: float = 0.0
    redshift_error: float = 0.0
    hlap: float = 0.0  # height * lap
    hsigma_lap_ccc: float = 0.0  # preferred match-quality metric when available
    r_value: float = 0.0  # Correlation coefficient
    lap: float = 0.0  # Overlap fraction
    age: Optional[float] = None  # Days from explosion
    velocity: Optional[float] = None  # km/s
    template_path: Optional[str] = None


@dataclass
class LineIdentification:
    """
    Spectral line identification.
    
    Contains information about identified spectral lines.
    """
    wavelength: float  # Observed wavelength (Angstroms)
    rest_wavelength: float  # Rest wavelength (Angstroms)
    element: str  # Element (e.g., "H", "He", "Ca")
    ion: str  # Ionization state (e.g., "I", "II")
    transition: str  # Transition name (e.g., "alpha", "beta")
    strength: float = 0.0  # Line strength/intensity
    equivalent_width: Optional[float] = None  # Equivalent width
    velocity: Optional[float] = None  # Line velocity (km/s)
    confidence: float = 0.0  # Identification confidence (0-1)


@dataclass
class MaskRegion:
    """
    Wavelength mask region.
    
    Defines a wavelength range to be excluded from analysis.
    """
    start: float  # Start wavelength (Angstroms)
    end: float    # End wavelength (Angstroms)
    reason: str = "user_defined"  # Reason for masking
    active: bool = True  # Whether mask is currently active


@dataclass
class AnalysisParameters:
    """
    SNID analysis parameters.
    
    Contains all parameters used for SNID analysis.
    """
    # Redshift parameters
    zmin: float = -0.01
    zmax: float = 1.0

    
    # Correlation parameters  
    lapmin: float = 0.3
    
    # Wavelength range
    wmin: Optional[float] = None
    wmax: Optional[float] = None
    
    # Template filtering
    type_filter: Optional[List[str]] = None
    age_min: Optional[float] = None
    age_max: Optional[float] = None
    max_output_templates: int = 10
    
    # Processing parameters
    median_fwmed: float = 0.0
    medlen: int = 1
    apodize_percent: float = 10.0
    skyclip: bool = False
    aband_remove: bool = False
    emclip_z: float = -1.0
    emwidth: float = 40.0
    
    # Output options
    verbose: bool = False
    save_plots: bool = False
    output_fluxed: bool = False
    output_flattened: bool = False


@dataclass
class QualityMetrics:
    """
    Spectrum and analysis quality metrics.
    
    Contains various quality indicators for the spectrum and analysis.
    """
    signal_to_noise: Optional[float] = None
    wavelength_coverage: Optional[float] = None  # Fraction of template wavelength range covered
    resolution: Optional[float] = None  # Spectral resolution (Angstroms)
    completeness: float = 0.0  # Fraction of spectrum that is unmasked
    template_matches: int = 0  # Number of template matches found
    correlation_quality: float = 0.0  # Overall correlation quality score


# Type aliases for commonly used types
WavelengthArray = np.ndarray
FluxArray = np.ndarray  
ErrorArray = Optional[np.ndarray]
RedshiftRange = Tuple[float, float]
WavelengthRange = Tuple[float, float]
TemplateList = List[TemplateMatch] 