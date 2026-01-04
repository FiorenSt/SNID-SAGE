"""
Vectorized Peak Finding for SNID Template Correlation

This module provides matrix-based peak finding operations that can process
multiple correlation functions simultaneously, providing significant speedup
over template-by-template processing.
"""

import numpy as np

# Global scaling for redshift uncertainties; fixed to 1.0 (no configurability).
Z_K = 1.0
from typing import List, Dict, Tuple, Any, Optional
from scipy.signal import find_peaks, peak_prominences
import logging

_LOG = logging.getLogger(__name__)

_WIDTH_FWHM_FALLBACK_WARN_COUNT = 0
_WIDTH_FWHM_FALLBACK_WARN_MAX = 10


def _warn_width_fwhm_fallback(message: str) -> None:
    global _WIDTH_FWHM_FALLBACK_WARN_COUNT
    try:
        if _WIDTH_FWHM_FALLBACK_WARN_COUNT < _WIDTH_FWHM_FALLBACK_WARN_MAX:
            _LOG.warning(message)
        elif _WIDTH_FWHM_FALLBACK_WARN_COUNT == _WIDTH_FWHM_FALLBACK_WARN_MAX:
            _LOG.warning("Half-height FWHM width fallback used frequently; suppressing further warnings.")
    finally:
        _WIDTH_FWHM_FALLBACK_WARN_COUNT += 1


class VectorizedPeakFinder:
    """
    Matrix-based peak finder for correlation functions.
    
    Processes multiple correlation functions simultaneously using vectorized
    operations for significant performance improvements.
    """
    
    def __init__(
        self,
        NW_grid: int,
        DWLOG_grid: float,
        lz1: int,
        lz2: int,
        k1: int,
        k2: int,
        k3: int,
        k4: int,
        *,
        phase1_peak_min_distance: int = 3,
        phase1_peak_min_height: float = 0.3,
    ):
        """
        Initialize vectorized peak finder.
        
        Parameters
        ----------
        NW_grid : int
            Grid size (1024)
        DWLOG_grid : float
            Log wavelength step
        lz1, lz2 : int
            Redshift search range indices
        k1, k2, k3, k4 : int
            Bandpass filter parameters
        """
        self.NW_grid = NW_grid
        self.DWLOG_grid = DWLOG_grid
        self.lz1 = lz1
        self.lz2 = lz2
        self.k1, self.k2, self.k3, self.k4 = k1, k2, k3, k4
        self.mid = NW_grid // 2

        # Phase-1 peak detection knobs.
        # These apply to the *normalized* phase-1 correlation (Rz) passed to find_peaks.
        try:
            self.phase1_peak_min_distance = int(phase1_peak_min_distance)
        except Exception:
            self.phase1_peak_min_distance = 3
        try:
            self.phase1_peak_min_height = float(phase1_peak_min_height)
        except Exception:
            self.phase1_peak_min_height = 0.3
        
    def find_peaks_batch(self, correlation_matrix: np.ndarray, 
                        template_names: List[str],
                        template_rms_array: np.ndarray,
                        spectrum_rms: float) -> Dict[str, Dict[str, Any]]:
        """
        Find peaks in multiple correlation functions simultaneously.
        
        Parameters
        ----------
        correlation_matrix : np.ndarray
            Shape (n_templates, NW_grid) - correlation functions for all templates
        template_names : List[str]
            Names corresponding to each row in correlation_matrix
        template_rms_array : np.ndarray
            RMS values for each template
        spectrum_rms : float
            Spectrum RMS value
            
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Peak information for each template
        """
        # Normalize all correlation functions at once
        rms_products = spectrum_rms * template_rms_array
        valid_rms_mask = rms_products > 0
        
        results = {}
        if not np.any(valid_rms_mask):
            return results
            
        # Get valid templates and their data
        valid_indices = np.where(valid_rms_mask)[0]
        valid_correlations = correlation_matrix[valid_indices]
        valid_names = [template_names[i] for i in valid_indices]
        valid_rms = rms_products[valid_indices]
        
        # Normalize correlations (vectorized)
        rolled_correlations = np.roll(valid_correlations, self.mid, axis=1)
        normalized_correlations = rolled_correlations / (self.NW_grid * valid_rms[:, np.newaxis])
        
        # Process all correlation functions
        for i, (name, correlation) in enumerate(zip(valid_names, normalized_correlations)):
            # Find peaks in this correlation function
            peaks_indices, properties = find_peaks(
                correlation, 
                distance=self.phase1_peak_min_distance,
                height=self.phase1_peak_min_height,
            )
            
            # Filter peaks to allowed redshift range
            valid_peaks = peaks_indices[(peaks_indices >= self.lz1) & (peaks_indices <= self.lz2)]
            
            if len(valid_peaks) > 0:
                results[name] = {
                    'peaks': valid_peaks,
                    'correlation': correlation,
                    'template_index': valid_indices[i],
                    'template_rms': template_rms_array[valid_indices[i]],
                    'properties': properties
                }
        
        return results
    
    def process_peaks_batch(self, peak_results: Dict[str, Dict[str, Any]],
                           template_data_dict: Dict[str, Dict[str, Any]],
                           tapered_flux: np.ndarray,
                           log_wave: np.ndarray,
                           cont: np.ndarray,
                           left_edge: int,
                           right_edge: int,
                           lapmin: float,
                           zmin: float,
                           zmax: float,
                           peak_window_size: int) -> List[Dict[str, Any]]:
        """
        Process found peaks with vectorized operations where possible.
        
        Parameters
        ----------
        peak_results : Dict[str, Dict[str, Any]]
            Results from find_peaks_batch
        template_data_dict : Dict[str, Dict[str, Any]]
            Template metadata and flux data
        tapered_flux : np.ndarray
            Processed spectrum flux
        log_wave : np.ndarray
            Log wavelength array
        cont : np.ndarray
            Continuum array
        left_edge, right_edge : int
            Spectrum edges
        lapmin : float
            Minimum overlap fraction threshold
        zmin, zmax : float
            Redshift range
        peak_window_size : int
            Peak search window size
            
        Returns
        -------
        List[Dict[str, Any]]
            Processed matches
        """
        from .fft_tools import shiftit, overlap, calculate_rms
        from .preprocessing import apodize, pad_to_NW
        
        matches = []
        
        # Group peaks by their lag values for potential batch processing
        lag_groups = {}
        
        for template_name, peak_data in peak_results.items():
            correlation = peak_data['correlation']
            peaks = peak_data['peaks']
            template_meta = template_data_dict[template_name]
            template_rms = peak_data['template_rms']

            # Phase-1 selection policy: keep only the single best peak per template
            # (hard top-1; see snid.py::_process_template_peaks).
            MAX_PHASE1_PEAKS_PER_TEMPLATE = 1
            selected_peaks: List[int] = []
            # Phase-1 uses a hard top-1 peak policy per template.
            try:
                peaks_int = [int(p) for p in peaks]
                peaks_int = [p for p in peaks_int if 0 <= p < int(self.NW_grid)]
                if peaks_int:
                    mid0 = int(self.NW_grid // 2)
                    peaks_int.sort(
                        key=lambda i: (
                            -float(correlation[i]) if np.isfinite(correlation[i]) else float("inf"),
                            abs(int(i) - mid0),
                        )
                    )
                    selected_peaks = peaks_int[:MAX_PHASE1_PEAKS_PER_TEMPLATE]
            except Exception:
                selected_peaks = []

            if not selected_peaks:
                try:
                    selected_peaks = [int(p) for p in peaks][:MAX_PHASE1_PEAKS_PER_TEMPLATE]
                except Exception:
                    selected_peaks = []
            
            for peak_idx in selected_peaks:
                # Derive refined lag at this correlation peak (bins relative to zero-lag center)
                # Use a local quadratic fit around the peak on the normalized correlation, 
                # mirroring the standard approach for initial centering.
                try:
                    fit_indices = (np.arange(int(peak_idx) - 2, int(peak_idx) + 3) % self.NW_grid).astype(int)
                    y_fit0 = correlation[fit_indices]
                    a0, b0, c0 = np.polyfit(fit_indices.astype(float), y_fit0, 2)
                    if abs(a0) < 1e-12:
                        ctr0 = float(peak_idx)
                    else:
                        ctr0 = -b0 / (2.0 * a0)
                        # Guardrail: avoid excessive extrapolation
                        if abs(ctr0 - float(peak_idx)) > max(3, int(np.ceil(0.5 * (fit_indices[-1] - fit_indices[0])))):
                            ctr0 = float(peak_idx)
                except Exception:
                    ctr0 = float(peak_idx)

                peak_lag = ctr0 - self.mid
                
                # Get overlap after shifting template to this lag
                template_flux = template_meta.get('flux', np.array([]))
                if len(template_flux) == 0:
                    continue
                
                tpl_shifted = shiftit(template_flux, peak_lag)
                # Compute fractional overlap on the true wavelength grid
                _, _, _, lap = overlap(tpl_shifted, tapered_flux, log_wave)
                
                # Threshold on lap (fraction), not lpeak
                if lap < lapmin:
                    continue
                
                # Compute lpeak with correct scaling
                lpeak = lap * self.DWLOG_grid * self.NW_grid
                
                # Store peak info for processing
                peak_info = {
                    'template_name': template_name,
                    'template_meta': template_meta,
                    'template_rms': template_rms,
                    # Use integer index only for initial trimming window hints
                    'peak_idx': int(np.clip(int(round(ctr0)), 0, self.NW_grid - 1)),
                    'correlation': correlation,
                    'lag_for_shifting_template': float(peak_lag),
                    'lap': float(lap),
                    'lpeak': float(lpeak)
                }
                
                # Group by lag for potential batch processing
                lag_key = int(peak_lag * 100)  # Group similar lags
                if lag_key not in lag_groups:
                    lag_groups[lag_key] = []
                lag_groups[lag_key].append(peak_info)
        
        # Process peaks (could be further optimized with batching)
        for lag_key, peak_group in lag_groups.items():
            for peak_info in peak_group:
                match = self._process_single_peak(
                    peak_info, tapered_flux, log_wave, cont,
                    left_edge, right_edge, zmin, zmax, peak_window_size
                )
                if match:
                    matches.append(match)
        
        return matches
    
    def _process_single_peak(self, peak_info: Dict[str, Any],
                            tapered_flux: np.ndarray,
                            log_wave: np.ndarray,
                            cont: np.ndarray,
                            left_edge: int,
                            right_edge: int,
                            zmin: float,
                            zmax: float,
                            peak_window_size: int) -> Optional[Dict[str, Any]]:
        """
        Process a single peak with correlation trimming and fitting.
        
        This method handles the detailed peak processing that's difficult to vectorize
        due to the variable shifting and trimming operations.
        """
        from .fft_tools import shiftit, overlap, calculate_rms, apply_filter as bandpass
        from .preprocessing import apodize, pad_to_NW
        
        try:
            template_name = peak_info['template_name']
            template_meta = peak_info['template_meta']
            template_rms = peak_info['template_rms']
            peak_idx = peak_info['peak_idx']
            correlation = peak_info['correlation']
            lag_for_shifting_template = peak_info['lag_for_shifting_template']
            lap = peak_info['lap']
            lpeak = peak_info['lpeak']
            
            # Shift template to peak position
            template_flux = template_meta.get('flux', np.array([]))
            tpl_shifted = shiftit(template_flux, lag_for_shifting_template)
            
            # Trim around correlation peak
            search_radius = peak_window_size
            trim_start = max(0, peak_idx - search_radius)
            trim_end = min(self.NW_grid, peak_idx + search_radius + 1)
            
            # Extract trimmed regions
            work_d = tapered_flux[trim_start:trim_end]
            work_t = tpl_shifted[trim_start:trim_end]
            
            # Pad to consistent size
            target_size = 2 * search_radius + 1
            if len(work_d) < target_size:
                pad_size = target_size - len(work_d)
                work_d = np.pad(work_d, (0, pad_size), mode='constant')
                work_t = np.pad(work_t, (0, pad_size), mode='constant')
            
            # Apply apodization
            work_d = apodize(work_d, 0, len(work_d) - 1, percent=10.0)  # 10% apodization
            work_t = apodize(work_t, 0, len(work_t) - 1, percent=10.0)
            
            # Pad to power of 2 for FFT efficiency
            work_d = pad_to_NW(work_d, self.NW_grid)
            work_t = pad_to_NW(work_t, self.NW_grid)
            
            # FFT and correlation
            dtft_peak = np.fft.fft(work_d)
            ttft_peak = np.fft.fft(work_t)
            
            drms_peak = calculate_rms(dtft_peak, self.k1, self.k2, self.k3, self.k4)
            trms_peak = calculate_rms(ttft_peak, self.k1, self.k2, self.k3, self.k4)
            
            if drms_peak == 0 or trms_peak == 0:
                return None
            
            # Calculate correlation on trimmed spectra
            cross_power_peak = dtft_peak * np.conj(ttft_peak)
            cspec_filtered_peak = bandpass(cross_power_peak, self.k1, self.k2, self.k3, self.k4)
            ccf_peak = np.fft.ifft(cspec_filtered_peak).real
            Rz_peak = np.roll(ccf_peak, self.NW_grid//2)
            if drms_peak * trms_peak > 0:
                Rz_peak /= (self.NW_grid * drms_peak * trms_peak)
            
            # Find peak in trimmed correlation
            mid = self.NW_grid // 2
            search_radius = peak_window_size
            search_start = max(0, mid - search_radius)
            search_end = min(self.NW_grid, mid + search_radius + 1)
            window = Rz_peak[search_start:search_end]
            if not window.size:
                return None
                
            local_peak_idx = search_start + np.argmax(window)
            
            # Quadratic fit around peak
            idx_fit = np.arange(local_peak_idx-2, local_peak_idx+3) % self.NW_grid
            y_fit = Rz_peak[idx_fit]
            
            # Fit parabola to points around peak
            a_p, b_p, c_p = np.polyfit(idx_fit.astype(float), y_fit, 2)
            
            if abs(a_p) < 1e-12:
                ctr_p = float(local_peak_idx)
                hgt_p = Rz_peak[local_peak_idx]
            else:
                ctr_p = -b_p / (2*a_p)
                hgt_p = a_p*ctr_p**2 + b_p*ctr_p + c_p
                
                # Validate quadratic fit to prevent unrealistic extrapolation
                max_allowed_offset = peak_window_size
                if abs(ctr_p - local_peak_idx) > max_allowed_offset:
                    ctr_p = float(local_peak_idx)
                    hgt_p = Rz_peak[local_peak_idx]
                
                # Check for unreasonably high peak heights
                original_height = Rz_peak[local_peak_idx]
                if hgt_p > 10 * original_height:
                    ctr_p = float(local_peak_idx)
                    hgt_p = original_height
            
            # Calculate lag relative to zero-lag position
            peak_lag = ctr_p - mid
            
            # Calculate final redshift estimate
            final_lag = lag_for_shifting_template + peak_lag
            z_est = np.exp(final_lag * self.DWLOG_grid) - 1.0
            
            # Check if redshift is within allowed range
            if z_est < zmin or z_est > zmax:
                return None
            
            # Width: half-height FWHM of the phase-2 correlation peak (Δz units).
            z_width = 0.0
            used_fallback = False
            try:
                from .peak_width_utils import halfheight_fwhm_bins_from_corr, width_dz_from_fwhm_bins

                fwhm_bins, _ = halfheight_fwhm_bins_from_corr(
                    Rz_peak,
                    peak_idx=int(local_peak_idx),
                    window_radius_bins=200,
                    baseline=0.0,
                )
                z_width_tmp = width_dz_from_fwhm_bins(fwhm_bins, dwlog=float(self.DWLOG_grid), z=float(z_est))
                if np.isfinite(z_width_tmp) and z_width_tmp > 0.0:
                    z_width = float(z_width_tmp)
                else:
                    used_fallback = True
            except Exception:
                used_fallback = True
                z_width = 0.0

            if used_fallback and np.isfinite(hgt_p) and hgt_p > 0.0:
                fwhm_bins_fallback = 2.0 * 2.35
                z_width = float(fwhm_bins_fallback * float(self.DWLOG_grid) * (1.0 + float(z_est)))
                _warn_width_fwhm_fallback(
                    f"Half-height FWHM width failed; using fallback width for template={template_name} "
                    f"(z≈{float(z_est):.6f})"
                )
            
            # Arms / antisymmetric-noise machinery is intentionally disabled in SNID-SAGE:
            # it is not used by the HLAP/HσLAP-CCC pipeline and is computationally expensive.
            r_value = 0.0
            
            # HLAP is computed for downstream scoring (HσLAP-CCC) and reporting.
            hlap = float(hgt_p) * float(lap) if (np.isfinite(hgt_p) and np.isfinite(lap)) else 0.0
            
            # Prepare spectra data for plotting
            plot_wave = log_wave[left_edge:right_edge+1]
            plot_template_flat = tpl_shifted[left_edge:right_edge+1]
            plot_template_flux = (plot_template_flat + 1.0) * cont[left_edge:right_edge+1]
            
            # Create match object
            match = {
                'template': template_meta,
                'hlap': hlap,
                'lag': final_lag,
                'redshift': z_est,
                # Per-match uncertainty is computed later from overlap residuals:
                # sigma_z = width * residual_noise_std (NaN if unavailable).
                'sigma_z': float('nan'),
                'r': r_value,
                'width': z_width,
                'height': hgt_p,
                'lap': lap,
                'type': template_meta.get('type', ''),
                'age': template_meta.get('age', 0),
                'name': template_meta.get('name', ''),
                'median_wave': template_meta.get('median_wave', 0),
                'slope': template_meta.get('slope', 0),
                'position': local_peak_idx,
                'normalized_height': hgt_p,
                'processed_flux': plot_template_flat,
                'spectra': {
                    'flux': {
                        'wave': plot_wave,
                        'flux': plot_template_flux
                    },
                    'flat': {
                        'wave': plot_wave,
                        'flux': plot_template_flat
                    }
                },
                'correlation_data': {
                    'correlation': Rz_peak,
                    'center': ctr_p,
                    'drms': drms_peak,
                    'trms': trms_peak
                }
            }
            
            return match
            
        except Exception as e:
            _LOG.debug(f"Error processing peak for template {template_name}: {e}")
            return None


def create_vectorized_peak_finder(NW_grid: int, DWLOG_grid: float,
                                 lz1: int, lz2: int, 
                                 k1: int, k2: int, k3: int, k4: int) -> VectorizedPeakFinder:
    """
    Create a vectorized peak finder instance.
    
    Parameters
    ----------
    NW_grid : int
        Grid size
    DWLOG_grid : float
        Log wavelength step
    lz1, lz2 : int
        Redshift search range
    k1, k2, k3, k4 : int
        Bandpass filter parameters
        
    Returns
    -------
    VectorizedPeakFinder
        Configured peak finder instance
    """
    return VectorizedPeakFinder(NW_grid, DWLOG_grid, lz1, lz2, k1, k2, k3, k4) 