"""
Mathematical utility functions for SNID SAGE.

This module provides statistically rigorous weighted calculations for
redshift and age estimation using template quality metrics.

Primary match-quality metric (preferred when available): HσLAP-CCC
    HσLAP-CCC = (height × lap × CCC) / sqrt(sigma_z)

Weighting policy for clustering/aggregation: w = (HσLAP-CCC)^2
"""

from .weighted_statistics import (
    calculate_combined_weights,
    apply_exponential_weighting,
    compute_cluster_weights,
    estimate_weighted_redshift,
    estimate_weighted_epoch,
    weighted_redshift_error,
    weighted_epoch_error
)

from .similarity_metrics import (
    concordance_correlation_coefficient,
    concordance_correlation_coefficient_trimmed,
    compute_phase2_overlap_diagnostics,
    compute_hsigma_lap_ccc_metric,
    compute_sigma_z_metrics,
    residual_noise_clipped_std,
    get_best_metric_value,
    get_hlap_value,
    get_best_metric_name,
    get_metric_name_for_match,
    get_metric_display_values
)

__all__ = [
    # Weighted statistics
    'calculate_combined_weights',
    'apply_exponential_weighting',
    'compute_cluster_weights',
    'estimate_weighted_redshift',
    'estimate_weighted_epoch',
    'weighted_redshift_error',
    'weighted_epoch_error',
    # Similarity metrics
    'concordance_correlation_coefficient',
    'concordance_correlation_coefficient_trimmed',
    'compute_phase2_overlap_diagnostics',
    'compute_hsigma_lap_ccc_metric',
    'compute_sigma_z_metrics',
    'residual_noise_clipped_std',
    'get_best_metric_value',
    'get_hlap_value',
    'get_best_metric_name',
    'get_metric_name_for_match',
    'get_metric_display_values'
]