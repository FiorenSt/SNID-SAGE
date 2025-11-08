"""
Statistically rigorous weighted calculations for redshift and age estimation in SNID SAGE.

This module implements best-metric weighted estimation methods (preferring RLAP-CCC) for optimal redshift 
and age estimation with full covariance analysis.
"""

import numpy as np
from typing import Union, List, Tuple, Optional
import logging

# Get logger for this module
logger = logging.getLogger(__name__)


def compute_cluster_weights(
    rlap_ccc_values: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]]
) -> np.ndarray:
    """
    Compute canonical cluster weights: w_i = (rlapccc_i)^2 / sigma_z_i^2.

    This is a thin wrapper around calculate_combined_weights for clarity.
    """
    return calculate_combined_weights(rlap_ccc_values, redshift_errors)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Compute weighted mean with basic validation; returns NaN if no valid data."""
    if values.size == 0 or weights.size == 0:
        return float('nan')
    sum_w = float(np.sum(weights))
    if sum_w <= 0 or not np.isfinite(sum_w):
        return float('nan')
    return float(np.sum(weights * values) / sum_w)


def _weighted_mean_se(values: np.ndarray, weights: np.ndarray) -> float:
    """
    Standard error (SE) of the weighted mean using arbitrary positive weights.

    Steps:
    - Population variance: var_pop = Σ w_i (x_i - μ)^2 / Σ w_i
    - Effective N: N_eff = (Σ w_i)^2 / Σ (w_i^2)
    - Sample variance: var_sample = var_pop × N_eff/(N_eff - 1)
    - SE(mean) = sqrt(var_sample / N_eff)
    Returns NaN if N_eff ≤ 0 or insufficient data.
    """
    if values.size == 0 or weights.size == 0:
        return float('nan')
    valid_mask = (np.isfinite(values) & np.isfinite(weights) & (weights > 0))
    if not np.any(valid_mask):
        return float('nan')
    v = values[valid_mask]
    w = weights[valid_mask]
    sum_w = float(np.sum(w))
    if sum_w <= 0 or not np.isfinite(sum_w):
        return float('nan')
    mean = float(np.sum(w * v) / sum_w)
    dev = v - mean
    var_pop = float(np.sum(w * (dev ** 2)) / sum_w)
    sum_w_sq = float(np.sum(w ** 2))
    if sum_w_sq <= 0:
        return float('nan')
    n_eff = (sum_w ** 2) / sum_w_sq
    if n_eff <= 0:
        return float('nan')
    var_sample = var_pop * (n_eff / (n_eff - 1.0)) if n_eff > 1 else var_pop
    se = float(np.sqrt(var_sample / n_eff))
    return se


def estimate_weighted_redshift(
    redshifts: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    rlap_ccc_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Weighted mean redshift using weights w = (rlapccc)^2 / sigma_z^2.
    """
    z = np.asarray(redshifts, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(rlap_ccc_values, dtype=float)
    if not (len(z) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for estimate_weighted_redshift")
        return float('nan')
    valid = (np.isfinite(z) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0))
    if not np.any(valid):
        return float('nan')
    w = compute_cluster_weights(r[valid], sigma[valid])
    return _weighted_mean(z[valid], w)


def estimate_weighted_epoch(
    ages: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    rlap_ccc_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Weighted mean epoch (age) using the same cluster weights as redshift:
    w = (rlapccc)^2 / sigma_z^2.
    """
    t = np.asarray(ages, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(rlap_ccc_values, dtype=float)
    if not (len(t) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for estimate_weighted_epoch")
        return float('nan')
    valid = (np.isfinite(t) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0))
    if not np.any(valid):
        return float('nan')
    w = compute_cluster_weights(r[valid], sigma[valid])
    return _weighted_mean(t[valid], w)


def weighted_redshift_se(
    redshifts: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    rlap_ccc_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Standard error (SE) of the weighted mean redshift using w = (rlapccc)^2 / sigma_z^2.
    Previously returned sample SD; now returns SE(mean) for stability and interpretability.
    """
    # Delegate to components function and return the chosen SE to ensure
    # consistent behavior across all callers (handles forced-z, zero spread, etc.).
    _, _, se_chosen = weighted_redshift_se_components(redshifts, redshift_errors, rlap_ccc_values)
    # Apply a global safety floor to avoid numerically tiny, non-physical values.
    try:
        if np.isfinite(se_chosen):
            return float(max(se_chosen, 1e-6))
    except Exception:
        pass
    return se_chosen


def weighted_epoch_se(
    ages: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    rlap_ccc_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Standard error (SE) of the weighted mean age using w = (rlapccc)^2 / sigma_z^2.
    Previously returned sample SD; now returns SE(mean).
    """
    t = np.asarray(ages, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(rlap_ccc_values, dtype=float)
    if not (len(t) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for weighted_epoch_se")
        return float('nan')
    valid = (np.isfinite(t) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0))
    if not np.any(valid):
        return float('nan')
    w = compute_cluster_weights(r[valid], sigma[valid])
    return _weighted_mean_se(t[valid], w)

# Backward-compatible aliases (deprecated):
# Removed deprecated aliases weighted_redshift_sd/weighted_epoch_sd

def weighted_redshift_se_components(
    redshifts: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    rlap_ccc_values: Union[np.ndarray, List[float]]
) -> Tuple[float, float, float]:
    """
    Return (SE_sample, SE_propagated, SE_chosen) for the weighted mean redshift.

    - SE_sample: standard error from weighted sample dispersion using weights
                 w = (metric)^2 / sigma^2.
    - SE_propagated: propagated standard error of the deterministic weighted mean
                     using the same normalized weights alpha_i = w_i / sum(w).
                     Var(\\hat{\\mu}) = sum(alpha_i^2 * sigma_i^2).
    - SE_chosen: selection rule
        * If no spread or SE_sample <= 0 or non-finite -> use SE_propagated
        * Else return max(SE_sample, SE_propagated) when SE_propagated finite;
          otherwise SE_sample.
    """
    z = np.asarray(redshifts, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(rlap_ccc_values, dtype=float)
    if not (len(z) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for weighted_redshift_se_components")
        return float('nan'), float('nan'), float('nan')
    valid = (np.isfinite(z) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0))
    if not np.any(valid):
        return float('nan'), float('nan'), float('nan')
    z_v = z[valid]
    s_v = sigma[valid]
    r_v = r[valid]
    w = compute_cluster_weights(r_v, s_v)

    # Sample-based SE
    se_sample = _weighted_mean_se(z_v, w)

    # Propagated SE for weighted mean
    sum_w = float(np.sum(w))
    if sum_w > 0 and np.isfinite(sum_w):
        alpha = w / sum_w
        var_propagated = float(np.sum((alpha ** 2) * (s_v ** 2)))
        se_propagated = float(np.sqrt(var_propagated))
    else:
        se_propagated = float('nan')

    try:
        no_spread = (np.ptp(z_v) <= 1e-9)
    except Exception:
        no_spread = False

    if no_spread or not np.isfinite(se_sample) or se_sample <= 0.0:
        return se_sample, se_propagated, se_propagated

    if np.isfinite(se_propagated):
        return se_sample, se_propagated, max(se_sample, se_propagated)
    return se_sample, se_propagated, se_sample

def calculate_combined_weights(
    rlap_ccc_values: Union[np.ndarray, List[float]],
    uncertainties: Union[np.ndarray, List[float]]
) -> np.ndarray:
    """
    Calculate combined weights using both best-metric quality and individual uncertainties.
    
    This implements the statistically correct approach for weighted averaging when
    both quality indicators (best metric) and individual uncertainties are available.
    
    Parameters
    ----------
    rlap_ccc_values : array-like
        Best metric quality scores (prefer RLAP-CCC; fallback to RLAP)
    uncertainties : array-like
        Individual uncertainty estimates for each template (e.g., redshift errors)
        
    Returns
    -------
    np.ndarray
        Combined weights = (metric)² / σ²
        
    Notes
    -----
    Statistical Formulation:
    - Quality weight: q_i = (metric_i)²
    - Precision weight: p_i = 1/σ²_i
    - Combined weight: w_i = q_i × p_i = (metric_i)² / σ²_i
    
    This gives high-quality templates with low uncertainty the highest influence,
    which is statistically optimal for uncertainty propagation.
    """
    rlap_ccc_values = np.asarray(rlap_ccc_values, dtype=float)
    uncertainties = np.asarray(uncertainties, dtype=float)
    
    # Validate inputs
    if len(rlap_ccc_values) != len(uncertainties):
        raise ValueError("Metric values and uncertainties must have same length")
    
    if len(rlap_ccc_values) == 0:
        return np.array([])
    
    # Handle zero uncertainties (perfect measurements) by using a small floor value
    # This prevents infinite weights while preserving the relative ordering
    min_uncertainty = np.min(uncertainties[uncertainties > 0]) if np.any(uncertainties > 0) else 1e-6
    uncertainty_floor = min_uncertainty * 0.1
    safe_uncertainties = np.maximum(uncertainties, uncertainty_floor)
    
    # Calculate combined weights using squared best-metric values (RLAP-CCC preferred)
    quality_weights = rlap_ccc_values ** 2
    precision_weights = 1.0 / (safe_uncertainties ** 2)  # Inverse variance weighting
    combined_weights = quality_weights * precision_weights
    
    logger.debug(f"Combined weighting: Best-metric [{rlap_ccc_values.min():.2f}, {rlap_ccc_values.max():.2f}], "
                f"uncertainties [{uncertainties.min():.4f}, {uncertainties.max():.4f}], "
                f"weights [{combined_weights.min():.2e}, {combined_weights.max():.2e}]")
    
    return combined_weights


def apply_exponential_weighting(rlap_ccc_values: Union[np.ndarray, List[float]]) -> np.ndarray:
    """
    Apply squared-metric weighting to RLAP-CCC/RLAP values for template prioritization.
    
    This helper now implements w = (metric)² to match the main pipeline's
    weighting policy when per-template σ is unavailable (quality-only case).
    
    Parameters
    ----------
    rlap_ccc_values : array-like
        Raw best-metric values from template matching
        
    Returns
    -------
    np.ndarray
        Squared metric weights
        
    Notes
    -----
    Transformation: w = (metric)²
    """
    rlap_ccc_values = np.asarray(rlap_ccc_values, dtype=float)
    
    # Handle empty input
    if len(rlap_ccc_values) == 0:
        return np.array([])
    
    # Apply squared weighting: w = x^2
    exponential_weights = rlap_ccc_values ** 2
    
    # Log the transformation for debugging
    if len(rlap_ccc_values) > 0:
        logger.debug(f"Squared weighting: Best-metric range [{rlap_ccc_values.min():.2f}, {rlap_ccc_values.max():.2f}] "
                    f"→ weight range [{exponential_weights.min():.2e}, {exponential_weights.max():.2e}]")
    
    return exponential_weights




# Exports
__all__ = [
    'calculate_combined_weights',
    'apply_exponential_weighting',
    'compute_cluster_weights',
    'estimate_weighted_redshift',
    'estimate_weighted_epoch',
    'weighted_redshift_se',
    'weighted_epoch_se'
]