"""
fft_tools.py – *all* low-level correlation & FFT helpers used by snid.py
========================================================================

Exports
-------
apply_filter             cosine-bell band-pass (k1–k4) on an FFT array
cross_correlate          FFT cross-correlation with band-pass + apodisation
overlap                  SNID's trimming / lap calculation
compute_redshift_from_lag  lag → z  (moved here from utils.py)
calculate_rms           calculate RMS of a bandpassed FFT spectrum
aspart                   calculate symmetric/antisymmetric components of a spectrum
shiftit                  shift a time-domain signal by a fractional amount

Implementation notes: FFT helpers and overlap bookkeeping.
"""

from __future__ import annotations
import numpy as np
from typing import List, Tuple
import math
import matplotlib.pyplot as plt
# ----------------------------------------------------
# ------------------
# Utility functions
# ----------------------------------------------------------------------

def compute_redshift_from_lag(lag: float, dlog: float) -> float:
    """z = exp(lag·dlog) – 1   (natural-log base)."""
    try:
        z = np.exp(lag * dlog) - 1.0
        return 0.0 if z < -0.95 or z > 10.0 else z
    except (OverflowError, ValueError):
        return 0.0


def _calculate_cosine_bell_factor(k_idx: int, k1: int, k2: int, k3: int, k4: int) -> float:
    """
    Calculate the cosine-bell taper factor for a frequency bin k_idx.
    This encapsulates the common logic used in several functions.
    
    Args:
        k_idx: Frequency bin index
        k1, k2, k3, k4: Bandpass filter parameters
        
    Returns:
        Filter factor in range [0.0, 1.0]
    """
    if k_idx < k1 or k_idx > k4:
        return 0.0
    
    if k_idx < k2:
        delta_k = (k2 - k1)
        if delta_k == 0:  # Avoid division by zero
            return 1.0 if k_idx >= k1 else 0.0
        arg = math.pi * (k_idx - k1) / delta_k
        return 0.5 * (1 - math.cos(arg))
    
    if k_idx > k3:
        delta_k = (k4 - k3)
        if delta_k == 0:  # Avoid division by zero
            return 1.0 if k_idx <= k4 else 0.0
        arg = math.pi * (k_idx - k3) / delta_k
        return 0.5 * (1 + math.cos(arg))
    
    # k2 <= k_idx <= k3
    return 1.0



# ----------------------------------------------------------------------
# 1) band-pass filtering and RMS calculations
# ----------------------------------------------------------------------

def apply_filter(ft: np.ndarray, k1: int, k2: int, k3: int, k4: int) -> np.ndarray:
    """
    Apply a cosine-bell band-pass filter to an FFT spectrum.
    
    Args:
        ft: FFT spectrum to filter (full complex FFT, not RFFT)
        k1, k2, k3, k4: Filter parameters
    """
    n = len(ft)
    filtered = ft.copy()
    
    # Process positive and negative frequencies
    for i in range(n):
        # Convert to frequency index
        if i < n//2:
            freq_idx = i
        else:
            freq_idx = i - n
            
        abs_freq = abs(freq_idx)
        factor = _calculate_cosine_bell_factor(abs_freq, k1, k2, k3, k4)
        filtered[i] *= factor
    
    return filtered


def calculate_rms(ft: np.ndarray, k1: int, k2: int, k3: int, k4: int) -> float:
    """
    Calculate the RMS of a signal after bandpass filtering its FFT.
    
    Args:
        ft: FFT spectrum (full complex FFT, not RFFT)
        k1, k2, k3, k4: Filter parameters
    """
    n = len(ft)
    power_sum = 0.0
    
    # Sum over frequency components from k1 to k4
    for k in range(k1, k4 + 1):
        # Parseval weight: 1.0 for DC and Nyquist, 2.0 for others
        weight = 1.0 if (k == 0 or k == n//2) else 2.0
        
        # Get cosine bell factor
        factor = _calculate_cosine_bell_factor(k, k1, k2, k3, k4)
            
        # Add power contribution
        power_sum += weight * factor * (ft[k].real**2 + ft[k].imag**2)
    
    return np.sqrt(power_sum) / float(n)


# ------------------------------------------------------------------
#  Symmetric / antisymmetric RMS within a cosine‑bell window
# ------------------------------------------------------------------

def aspart(x: np.ndarray, k1: int, k2: int, k3: int, k4: int, shift: float) -> Tuple[float, float]:
    """
    Calculate antisymmetric/symmetric parts of a spectrum.
    
    Args:
        x: Full complex FFT (not RFFT)
        k1, k2, k3, k4: Filter parameters
        shift: Time domain shift
    """
    n = len(x)
    arms_sum = 0.0
    srms_sum = 0.0
    
    # Process frequency components from k1 to k4
    for k in range(k1, k4 + 1):
        # Calculate phase shift
        angle = -2.0 * np.pi * k * shift / n
        phase = np.exp(1j * angle)  # Use numpy's complex exponential
        
        # Parseval weight
        weight = 1.0 if (k == 0 or k == n//2) else 2.0
        
        # Get cosine bell factor squared
        factor = _calculate_cosine_bell_factor(k, k1, k2, k3, k4)
        factor = factor * factor  # Square it
        
        # Apply phase shift and calculate symmetric/antisymmetric components
        val_shifted = phase * x[k]
        arms_sum += weight * factor * (val_shifted.imag**2)
        srms_sum += weight * factor * (val_shifted.real**2)
    
    return np.sqrt(arms_sum) / n, np.sqrt(srms_sum) / n


# ------------------------------------------------------------------
#  Shift a signal in the time domain by a fractional amount
# ------------------------------------------------------------------

def shiftit(x: np.ndarray, shift: float, tol: float = 1e-8) -> np.ndarray:
    """
    Shift a time-domain signal by a fractional amount.
    
    Args:
        x: Time domain signal
        shift: Shift amount in samples
        tol: Tolerance for identifying non-zero samples
    """
    n = len(x)
    if n == 0:
        return np.array([])
    
    # Find original non-zero region
    nz = np.flatnonzero(np.abs(x) > tol)
    if not nz.size:  # All zeros
        return np.zeros_like(x)
    
    # Use full FFT
    ft = np.fft.fft(x)
    
    # Apply phase shifts
    for i in range(n):
        freq_idx = i if i <= n//2 else i - n
        angle = -2.0 * np.pi * freq_idx * shift / n
        phase = np.exp(1j * angle)  # Use numpy's complex exponential
        ft[i] *= phase
    
    result = np.real(np.fft.ifft(ft))
    
    # Zero out everything outside the original non-zero region
    o0, o1 = int(nz[0]), int(nz[-1])
    n0 = int(np.floor(o0 + shift))
    n1 = int(np.ceil(o1 + shift))
    
    if n0 > 0:
        result[:n0] = 0.0
    if n1 < n - 1:
        result[n1+1:] = 0.0
    
    # Kill any tiny remaining ringing
    result[np.abs(result) < tol] = 0.0
    
    return result



# ----------------------------------------------------------------------
# 3) lap-trim overlap (apodised)
# ----------------------------------------------------------------------

def overlap(
    spec_t: np.ndarray,
    spec_d: np.ndarray,
    wave:   np.ndarray,
) -> Tuple[
    Tuple[int,int],    # (lt1, lt2): template non-zero start/end bins
    Tuple[int,int],    # (ld1, ld2): data     non-zero start/end bins
    Tuple[float,float],# (ov_start, ov_end): overlap wavelengths
    float              # lap: fractional overlap length
]:
    """
    Find the overlapping region between two spectra on the same wavelength grid.
    
    Args:
        spec_t, spec_d: Template and data spectra
        wave: Wavelength grid for both spectra
        
    Returns:
        Tuple of:
        - (lt1, lt2): Non-zero bin range in template
        - (ld1, ld2): Non-zero bin range in data
        - (ov_start, ov_end): Overlap wavelength range
        - lap: Fractional overlap length
    """
    n = len(spec_t)
    if n == 0 or n != len(spec_d) or n != len(wave):
        return (0, -1), (0, -1), (np.nan, np.nan), 0.0
    
    tol = 1e-3
    
    # Find non-zero regions in each spectrum
    nz_t = np.where(np.abs(spec_t) > tol)[0]
    lt1, lt2 = (int(nz_t[0]), int(nz_t[-1])) if nz_t.size else (0, n-1)
    
    nz_d = np.where(np.abs(spec_d) > tol)[0]
    ld1, ld2 = (int(nz_d[0]), int(nz_d[-1])) if nz_d.size else (0, n-1)
    
    # Calculate overlap
    ov1 = max(lt1, ld1)
    ov2 = min(lt2, ld2)
    
    # Fractional overlap
    lap = (ov2 - ov1 + 1) / n if ov2 >= ov1 else 0.0
    
    # Convert to wavelengths
    ov_start = wave[ov1] if ov2 >= ov1 and ov1 < len(wave) else np.nan
    ov_end = wave[ov2] if ov2 >= ov1 and ov2 < len(wave) else np.nan
    
    return (lt1, lt2), (ld1, ld2), (ov_start, ov_end), lap



def weighted_median_from_rlap(
    rpeaks: List[float],
    lpeaks: List[float],
    zpeaks: List[float]
) -> float:
    """
    Compute weighted median redshift from R-values and lap fractions.
    
    Args:
        rpeaks: R-values for each peak
        lpeaks: Lap fractions for each peak
        zpeaks: Redshift estimates for each peak
        
    Returns:
        Weighted median redshift
    """
    if not rpeaks or not lpeaks or not zpeaks:
        return 0.0
    
    buf = []
    for r, l, z in zip(rpeaks, lpeaks, zpeaks):
        rl = r * l
        
        # Add entries to buffer based on r*l thresholds
        nadd = 0
        if rl > 4.0:
            nadd += 1
        if rl > 5.0:
            nadd += 2
        if rl > 6.0:
            nadd += 2
        
        buf.extend([z] * nadd)
    
    # Simple median calculation - use enhanced methods instead
    return float(np.median(buf)) if buf else 0.0



# ----------------------------------------------------------------------
#  Calculate FFT and RMS for a spectrum slice (dtft_drms function)
# ------------------------------------------------------------------

def dtft_drms(flux: np.ndarray, start_zero: float, left_edge: int, right_edge: int, k1: int, k2: int, k3: int, k4: int) -> Tuple[np.ndarray, float]:
    """
    Calculate discrete Fourier transform and RMS for a spectrum slice.
    
    This function computes the FFT of a flux array and calculates the RMS
    using the provided SNID bandpass filter parameters. It's used in the
    main correlation analysis.
    
    Args:
        flux: Input flux array
        start_zero: Starting value (typically 0.0, kept for compatibility)
        left_edge: Left edge of valid data region
        right_edge: Right edge of valid data region
        k1, k2, k3, k4: Bandpass filter parameters
        
    Returns:
        Tuple of (fft_array, rms_value)
    """
    # Compute FFT
    fft_result = np.fft.fft(flux)
    
    # Calculate RMS using bandpass filter with provided parameters
    rms_value = calculate_rms(fft_result, k1, k2, k3, k4)
    
    return fft_result, rms_value



# ----------------------------------------------------------------------
__all__ = [
    "apply_filter", 
    "calculate_rms",
    "cross_correlate", 
    "overlap", 
    "aspart", 
    "shiftit",
    "allpeaks", 
    "compute_redshift_from_lag", 
    "weighted_median_from_rlap",
    "dtft_drms"  # Add the missing function
]