"""
Statistically rigorous weighted calculations for redshift and age estimation in SNID SAGE.

This module implements best-metric weighted estimation methods (preferring HσLAP-CCC) for optimal redshift
and age estimation with full covariance analysis.
"""

import numpy as np
from typing import Union, List, Tuple, Optional
import logging

# Get logger for this module
logger = logging.getLogger(__name__)


def compute_cluster_weights(
    metric_values: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]]
) -> np.ndarray:
    """
    Compute canonical cluster weights: w_i = (HσLAP-CCC_i)^2.

    This is a thin wrapper around calculate_combined_weights for clarity.
    """
    return calculate_combined_weights(metric_values, redshift_errors)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Compute weighted mean with basic validation; returns NaN if no valid data."""
    if values.size == 0 or weights.size == 0:
        return float('nan')
    sum_w = float(np.sum(weights))
    if sum_w <= 0 or not np.isfinite(sum_w):
        return float('nan')
    return float(np.sum(weights * values) / sum_w)


 


def _weighted_sd_unbiased(values: np.ndarray, weights: np.ndarray) -> float:
    """
    Unbiased weighted standard deviation:
      μ = Σ w_i x_i / Σ w_i
      var_pop = Σ w_i (x_i − μ)^2 / Σ w_i
      N_eff = (Σ w_i)^2 / Σ w_i^2
      var_unbiased = var_pop × N_eff / (N_eff − 1)  (for N_eff > 1; else var_pop)
      sd = sqrt(max(0, var_unbiased))
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
    var_pop = float(np.sum(w * (v - mean) ** 2) / sum_w)
    if not np.isfinite(var_pop) or var_pop < 0:
        return float('nan')
    sum_w_sq = float(np.sum(w ** 2))
    if sum_w_sq <= 0 or not np.isfinite(sum_w_sq):
        return float('nan')
    n_eff = (sum_w ** 2) / sum_w_sq
    var_unbiased = var_pop * (n_eff / (n_eff - 1.0)) if n_eff > 1 else var_pop
    return float(np.sqrt(max(0.0, var_unbiased)))


def estimate_weighted_redshift(
    redshifts: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    metric_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Weighted mean redshift using weights w = (HσLAP-CCC)^2.
    """
    z = np.asarray(redshifts, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(metric_values, dtype=float)
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
    metric_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Weighted mean epoch (age) using the same cluster weights as redshift:
    w = (HσLAP-CCC)^2.
    """
    t = np.asarray(ages, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(metric_values, dtype=float)
    if not (len(t) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for estimate_weighted_epoch")
        return float('nan')
    valid = (np.isfinite(t) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0))
    if not np.any(valid):
        return float('nan')
    w = compute_cluster_weights(r[valid], sigma[valid])
    return _weighted_mean(t[valid], w)


def weighted_redshift_error(
    redshifts: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    metric_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Uncertainty for redshift reported as unbiased weighted SD within the set.
    Uses weights w = (HσLAP-CCC)^2.
    Single-member rule: return that member's sigma_z.
    """
    z = np.asarray(redshifts, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(metric_values, dtype=float)
    if not (len(z) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for weighted_redshift_error")
        return float('nan')
    valid = (np.isfinite(z) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0) & (r > 0))
    n_valid = int(np.sum(valid))
    if n_valid == 0:
        return float('nan')
    if n_valid == 1:
        return float(sigma[valid][0])
    w = compute_cluster_weights(r[valid], sigma[valid])
    return _weighted_sd_unbiased(z[valid], w)


def weighted_epoch_error(
    ages: Union[np.ndarray, List[float]],
    redshift_errors: Union[np.ndarray, List[float]],
    metric_values: Union[np.ndarray, List[float]]
) -> float:
    """
    Uncertainty for age reported as unbiased weighted SD within the set.
    Uses redshift-based weights w = (HσLAP-CCC)^2.
    Single-member rule: return NaN (cannot estimate SD from one point).
    """
    t = np.asarray(ages, dtype=float)
    sigma = np.asarray(redshift_errors, dtype=float)
    r = np.asarray(metric_values, dtype=float)
    if not (len(t) == len(sigma) == len(r)):
        logger.error("Mismatched input lengths for weighted_epoch_error")
        return float('nan')
    valid = (np.isfinite(t) & np.isfinite(sigma) & np.isfinite(r) & (sigma > 0) & (r > 0))
    n_valid = int(np.sum(valid))
    if n_valid == 0:
        return float('nan')
    if n_valid == 1:
        return float('nan')
    w = compute_cluster_weights(r[valid], sigma[valid])
    return _weighted_sd_unbiased(t[valid], w)


 

def calculate_combined_weights(
    metric_values: Union[np.ndarray, List[float]],
    uncertainties: Union[np.ndarray, List[float]]
) -> np.ndarray:
    """
    Calculate cluster weights from best-metric values.
    
    For HσLAP-CCC, sigma_z normalization is already included in the metric:
        HσLAP-CCC = (height × lap × CCC) / sqrt(sigma_z)
    so the canonical cluster weight is simply:
        w_i = (HσLAP-CCC_i)^2
    
    Parameters
    ----------
    metric_values : array-like
        Best metric quality scores (HσLAP-CCC preferred; fallback to HLAP)
    uncertainties : array-like
        Kept for API compatibility; not used in the current weighting formula.
        
    Returns
    -------
    np.ndarray
        Weights = (HσLAP-CCC)²
    """
    metric_values = np.asarray(metric_values, dtype=float)
    uncertainties = np.asarray(uncertainties, dtype=float)
    
    # Validate inputs
    if len(metric_values) != len(uncertainties):
        raise ValueError("Metric values and uncertainties must have same length")
    
    if len(metric_values) == 0:
        return np.array([])
    
    # Canonical weights for HσLAP-CCC: w = metric^2
    combined_weights = metric_values ** 2
    
    logger.debug(f"Combined weighting: Best-metric [{metric_values.min():.2f}, {metric_values.max():.2f}], "
                f"weights [{combined_weights.min():.2e}, {combined_weights.max():.2e}]")
    
    return combined_weights


def apply_exponential_weighting(metric_values: Union[np.ndarray, List[float]]) -> np.ndarray:
    """
    Apply squared-metric weighting to HσLAP-CCC/HLAP values for template prioritization.
    
    This helper now implements w = (metric)² to match the main pipeline's
    weighting policy when per-template σ is unavailable (quality-only case).
    
    Parameters
    ----------
    metric_values : array-like
        Raw best-metric values from template matching
        
    Returns
    -------
    np.ndarray
        Squared metric weights
        
    Notes
    -----
    Transformation: w = (HσLAP-CCC)²
    """
    metric_values = np.asarray(metric_values, dtype=float)
    
    # Handle empty input
    if len(metric_values) == 0:
        return np.array([])
    
    # Apply squared weighting: w = x^2
    exponential_weights = metric_values ** 2
    
    # Log the transformation for debugging
    if len(metric_values) > 0:
        logger.debug(f"Squared weighting: Best-metric range [{metric_values.min():.2f}, {metric_values.max():.2f}] "
                    f"→ weight range [{exponential_weights.min():.2e}, {exponential_weights.max():.2e}]")
    
    return exponential_weights




# Exports
__all__ = [
    'calculate_combined_weights',
    'apply_exponential_weighting',
    'compute_cluster_weights',
    'estimate_weighted_redshift',
    'estimate_weighted_epoch',
    'weighted_redshift_error',
    'weighted_epoch_error'
]