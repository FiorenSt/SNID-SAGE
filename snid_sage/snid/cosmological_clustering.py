"""
Direct GMM Clustering for SNID SAGE
===================================

This module implements GMM clustering directly on redshift values for 
template matching analysis without any transformations.

Key features:
1. Direct GMM clustering on redshift values (no transformations)
2. Type-specific clustering with BIC-based model selection
3. Cluster selection and scoring (top-5 within-cluster)
4. Weighted subtype determination within winning clusters
5. Statistical confidence assessment for subtype classification

The clustering works directly with redshift values using the same approach
as the transformation_comparison_test.py reference implementation.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from sklearn.mixture import GaussianMixture
import logging
import time
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


# Uses top-5 best metric values (HσLAP-CCC preferred; fallback to HLAP) with penalties for small clusters





def calculate_joint_subtype_estimates_from_cluster(
    cluster_matches: List[Dict[str, Any]], 
    target_subtype: str
) -> Tuple[float, float, float, float, float, int, int]:
    """
    Calculate joint weighted redshift and age estimates for a specific subtype within a cluster.
    
    Parameters
    ----------
    cluster_matches : List[Dict]
        List of template match dictionaries from a cluster
    target_subtype : str
        The specific subtype to calculate estimates for (e.g., 'IIn', 'IIP')
        
    Returns
    -------
    Tuple[float, float, float, float, float, int, int]
        (weighted_redshift, weighted_age, redshift_error, age_error, 
         redshift_age_covariance, subtype_template_count, subtype_age_template_count)
    """
    if not cluster_matches or not target_subtype:
        return np.nan, np.nan, np.nan, np.nan, np.nan, 0, 0
    
    # Filter matches to only include the target subtype
    subtype_matches = []
    total_subtype_count = 0
    
    for match in cluster_matches:
        template = match.get('template', {})
        subtype = template.get('subtype', 'Unknown')
        if not subtype or subtype.strip() == '':
            subtype = 'Unknown'
        
        if subtype == target_subtype:
            total_subtype_count += 1
            age = template.get('age', 0.0)
            # Only include templates with both redshift and finite age for joint estimation
            # Negative ages are acceptable (pre-maximum light)
            if 'redshift' in match and np.isfinite(age):
                subtype_matches.append(match)
    
    if not subtype_matches:
        _LOGGER.warning(f"No matches with valid (redshift, age) pairs found for subtype '{target_subtype}' in cluster")
        return np.nan, np.nan, np.nan, np.nan, np.nan, total_subtype_count, 0
    
    # Use weighted estimators directly for the subtype
    from snid_sage.shared.utils.math_utils import (
        get_best_metric_value,
        estimate_weighted_redshift,
        estimate_weighted_epoch,
        weighted_redshift_error,
        weighted_epoch_error,
    )

    redshifts_for_estimation = []
    redshift_errors_for_estimation = []
    metric_values_for_redshift = []
    ages_for_estimation = []
    metric_values_for_age = []
    age_redshift_errors_for_estimation = []

    for match in subtype_matches:
        if 'redshift' in match:
            template = match.get('template', {})
            age = template.get('age', 0.0)
            metric_val = get_best_metric_value(match)
            z = match.get('redshift')
            z_err = match.get('sigma_z', float('nan'))
            if z is not None and np.isfinite(z) and z_err > 0:
                redshifts_for_estimation.append(z)
                redshift_errors_for_estimation.append(z_err)
                metric_values_for_redshift.append(metric_val)
            if np.isfinite(age) and z_err > 0:
                ages_for_estimation.append(age)
                metric_values_for_age.append(metric_val)
                age_redshift_errors_for_estimation.append(z_err)

    if redshifts_for_estimation:
        z_mean = estimate_weighted_redshift(
            redshifts_for_estimation,
            redshift_errors_for_estimation,
            metric_values_for_redshift
        )
        z_error = weighted_redshift_error(
            redshifts_for_estimation,
            redshift_errors_for_estimation,
            metric_values_for_redshift
        )
    else:
        _LOGGER.warning("No valid redshift data found in cluster matches")
        z_mean, z_error = np.nan, np.nan

    if ages_for_estimation and redshift_errors_for_estimation:
        t_mean = estimate_weighted_epoch(
            ages_for_estimation,
            age_redshift_errors_for_estimation,
            metric_values_for_age
        )
        t_error = weighted_epoch_error(
            ages_for_estimation,
            age_redshift_errors_for_estimation,
            metric_values_for_age
        )
    else:
        _LOGGER.warning("No valid age data found in cluster matches")
        t_mean, t_error = np.nan, np.nan

    zt_covariance = 0.0
    
    age_template_count = len(subtype_matches)
    
    return z_mean, t_mean, z_error, t_error, zt_covariance, total_subtype_count, age_template_count


def _compute_weighted_cluster_stats(
    cluster_matches: List[Dict[str, Any]]
) -> Tuple[float, float, float, float, float]:
    """Compute weighted redshift/age and their errors (unbiased weighted SD) for a set of matches.
    Returns (z_mean, t_mean, z_err, t_err, zt_covariance)."""
    from snid_sage.shared.utils.math_utils import (
        get_best_metric_value,
        estimate_weighted_redshift,
        estimate_weighted_epoch,
        weighted_redshift_error,
        weighted_epoch_error,
    )

    redshifts_for_estimation = []
    redshift_errors_for_estimation = []
    metric_values_for_redshift = []
    ages_for_estimation = []
    metric_values_for_age = []
    age_redshift_errors_for_estimation = []

    for match in cluster_matches:
        if 'redshift' in match:
            template = match.get('template', {})
            age = template.get('age', 0.0)
            metric_val = get_best_metric_value(match)
            z = match.get('redshift')
            z_err = match.get('sigma_z', float('nan'))
            if z is not None and np.isfinite(z) and z_err > 0:
                redshifts_for_estimation.append(z)
                redshift_errors_for_estimation.append(z_err)
                metric_values_for_redshift.append(metric_val)
            if np.isfinite(age) and z_err > 0:
                ages_for_estimation.append(age)
                metric_values_for_age.append(metric_val)
                age_redshift_errors_for_estimation.append(z_err)

    if redshifts_for_estimation:
        z_mean = estimate_weighted_redshift(
            redshifts_for_estimation,
            redshift_errors_for_estimation,
            metric_values_for_redshift
        )
        z_err = weighted_redshift_error(
            redshifts_for_estimation,
            redshift_errors_for_estimation,
            metric_values_for_redshift
        )
    else:
        _LOGGER.warning("No valid redshift data found in cluster matches")
        z_mean, z_err = np.nan, np.nan

    if ages_for_estimation and redshift_errors_for_estimation:
        t_mean = estimate_weighted_epoch(
            ages_for_estimation,
            age_redshift_errors_for_estimation,
            metric_values_for_age
        )
        t_err = weighted_epoch_error(
            ages_for_estimation,
            age_redshift_errors_for_estimation,
            metric_values_for_age
        )
    else:
        _LOGGER.warning("No valid age data found in cluster matches")
        t_mean, t_err = np.nan, np.nan

    zt_covariance = 0.0

    return z_mean, t_mean, z_err, t_err, zt_covariance

    


def perform_direct_gmm_clustering(
    matches: List[Dict[str, Any]], 
    min_matches_per_type: int = 2,
    max_clusters_per_type: int = 10,
    verbose: bool = False,
    hsigma_lap_ccc_threshold: float = 1.5,  # Best-metric threshold for clustering (HσLAP-CCC)
    use_weighted_gmm: Optional[bool] = None,  # Hidden option: when True, use weighted GMM + weighted BIC
    # Optional: model selection method for choosing the number of GMM components.
    # Default is 'elbow'. Optional 'bic' chooses min(BIC).
    model_selection_method: Optional[str] = None,
    # Optional progress reporting (message, percent). If provided, emit per-type updates.
    progress_callback: Optional[Callable[[str, float], None]] = None,
    progress_min: float = 90.0,
    progress_max: float = 98.0,
    # Optional strict redshift gating (defense-in-depth). When provided, matches outside
    # [zmin, zmax] are excluded BEFORE metric-threshold filtering and clustering.
    zmin: Optional[float] = None,
    zmax: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Direct GMM clustering on redshift values with automatic best metric selection.
    
    This approach works directly on redshift values without any transformations,
    matching the approach in transformation_comparison_test.py exactly.
    
    NEW: Now automatically uses the best available similarity metric via
    get_best_metric_value(): prefers HσLAP-CCC; falls back to HLAP when needed.
    
    Parameters
    ----------
    matches : List[Dict[str, Any]]
        List of template matches from SNID analysis
    min_matches_per_type : int, optional
        Minimum number of matches required per type for clustering
    max_clusters_per_type : int, optional
        Maximum clusters for GMM
    verbose : bool, optional
        Enable detailed logging
    hsigma_lap_ccc_threshold : float, optional
        Minimum HσLAP-CCC value required for matches to be considered for clustering
        (HσLAP-CCC: (height × lap × CCC) / sqrt(sigma_z)).
        
    Hidden Options
    --------------
    use_weighted_gmm : bool, optional
        When True, enables sample-weighted GMM fitting and weighted-BIC selection
        using combined weights (HσLAP-CCC)^2. By default (None/False),
        the method uses standard unweighted GMM and unweighted BIC. If None, the
        value is read from environment variable 'SNID_SAGE_WEIGHTED_GMM' (1/true/on).

    Returns
    -------
    Dict containing clustering results
    """
    
    start_time = time.time()
    
    # Resolve hidden option: default to unweighted unless explicitly enabled
    if use_weighted_gmm is None:
        try:
            import os
            env_val = str(os.getenv("SNID_SAGE_WEIGHTED_GMM", "0")).strip().lower()
            use_weighted_gmm = env_val in ("1", "true", "yes", "on")
        except Exception:
            use_weighted_gmm = False

    # Resolve model selection method (default: elbow)
    if model_selection_method is None:
        try:
            import os
            env_val = str(os.getenv("SNID_SAGE_GMM_MODEL_SELECTION", "elbow")).strip().lower()
            model_selection_method = env_val
        except Exception:
            model_selection_method = "elbow"
    model_selection_method = str(model_selection_method or "elbow").strip().lower()
    if model_selection_method not in ("bic", "elbow"):
        model_selection_method = "elbow"
    
    # Determine which metric to use - now using get_best_metric_value()
    # This automatically prioritizes HσLAP-CCC > HLAP
    metric_name = "HσLAP-CCC"
    metric_key = "best_metric"  # Not actually used anymore, see get_best_metric_value() calls
    
    _LOGGER.info(f"🔄 Starting direct GMM {metric_name} clustering")
    _LOGGER.info(f"🎯 HσLAP-CCC threshold: {hsigma_lap_ccc_threshold:.2f} (matches below this are excluded from clustering)")

    # ---------------------------------------------------------------------
    # Optional strict redshift gating
    # ---------------------------------------------------------------------
    gated_matches = matches
    try:
        zlo = float(zmin) if zmin is not None else float("-inf")
        zhi = float(zmax) if zmax is not None else float("inf")
        if np.isfinite(zlo) or np.isfinite(zhi):
            tmp: List[Dict[str, Any]] = []
            excluded_z = 0
            for m in matches:
                try:
                    zz = float(m.get("redshift", float("nan")))
                except Exception:
                    zz = float("nan")
                if not np.isfinite(zz):
                    excluded_z += 1
                    continue
                if (zz < zlo) or (zz > zhi):
                    excluded_z += 1
                    continue
                tmp.append(m)
            gated_matches = tmp
            if excluded_z > 0:
                _LOGGER.info(
                    "🙅 Filtered out %d matches outside strict redshift bounds [%.6f, %.6f] before clustering",
                    int(excluded_z),
                    float(zlo),
                    float(zhi),
                )
    except Exception:
        gated_matches = matches
    
    # Filter matches by best-metric threshold before grouping
    from snid_sage.shared.utils.math_utils import get_best_metric_value
    filtered_matches = []
    excluded_count = 0
    
    for match in gated_matches:
        metric_value = get_best_metric_value(match)
        if metric_value >= hsigma_lap_ccc_threshold:
            filtered_matches.append(match)
        else:
            excluded_count += 1
    
    if excluded_count > 0:
        _LOGGER.info(f"🙅 Filtered out {excluded_count} matches below HσLAP-CCC threshold {hsigma_lap_ccc_threshold:.2f}")
        _LOGGER.info(f"✅ Proceeding with {len(filtered_matches)} matches for clustering")
    
    if not filtered_matches:
        _LOGGER.info(f"No matches above HσLAP-CCC threshold {hsigma_lap_ccc_threshold:.2f}")
        return {'success': False, 'reason': 'no_matches_above_threshold'}
    
    # Group filtered matches by type
    type_groups = {}
    for match in filtered_matches:
        sn_type = match['template'].get('type', 'Unknown')
        if sn_type not in type_groups:
            type_groups[sn_type] = []
        type_groups[sn_type].append(match)
    
    # Accept all types with at least min_matches_per_type (now allowing 1+)
    filtered_type_groups = {
        sn_type: type_matches 
        for sn_type, type_matches in type_groups.items() 
        if len(type_matches) >= min_matches_per_type
    }
    
    if not filtered_type_groups:
        _LOGGER.info("No types have any matches for clustering")
        return {'success': False, 'reason': 'no_matches'}
    
    n_types = len(filtered_type_groups)
    _LOGGER.info(f"📊 Processing {n_types} types: {list(filtered_type_groups.keys())}")
    # Emit an initial clustering progress update if requested
    try:
        if progress_callback is not None and n_types > 0:
            progress_callback(
                f"Clustering: processing {n_types} type(s)",
                float(progress_min)
            )
    except Exception:
        pass
    
    # Perform GMM clustering for each type
    all_cluster_candidates = []
    clustering_results = {}
    
    # Iterate deterministically for stable UX
    for idx, sn_type in enumerate(sorted(filtered_type_groups.keys())):
        type_matches = filtered_type_groups[sn_type]
        type_result = _perform_direct_gmm_clustering(
            type_matches, sn_type, max_clusters_per_type, 
            verbose, "best_metric",
            use_weighted_gmm=use_weighted_gmm,
            model_selection_method=model_selection_method
        )
        
        clustering_results[sn_type] = type_result
        
        # Proceed when we have clusters, regardless of having a fitted GMM model
        if type_result.get('success') and type_result.get('clusters'):
            # For each cluster, use the EXACT same winning cluster selection as reference
            type_redshifts = np.array([m['redshift'] for m in type_matches])
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            type_metric_values = np.array([get_best_metric_value(m) for m in type_matches])
            
            # Get cluster labels for this type (prefer GMM; fallback to gamma/argmax; else single cluster)
            features = type_redshifts.reshape(-1, 1)
            if 'gmm_model' in type_result and type_result['gmm_model'] is not None:
                labels = type_result['gmm_model'].predict(features)
            elif 'gamma' in type_result and isinstance(type_result['gamma'], np.ndarray):
                try:
                    labels = np.argmax(type_result['gamma'], axis=1)
                except Exception:
                    labels = np.zeros(len(type_matches), dtype=int)
            else:
                labels = np.zeros(len(type_matches), dtype=int)
            
            # winning_cluster_id is determined by the top-5 method at the end
            
            # Create cluster candidates using the exact reference approach.
            # After contiguity/gap splitting, the number of output clusters can differ
            # from the BIC-optimal number of mixture components. Always iterate over the
            # returned cluster list rather than range(optimal_n_clusters).
            for cluster_info in (type_result.get('clusters') or []):
                if not isinstance(cluster_info, dict):
                    continue
                
                # Calculate mean metric value for this cluster
                cluster_metric_values = [match.get(metric_key, match.get('hlap', 0.0)) for match in cluster_info['matches']]
                mean_metric = np.mean(cluster_metric_values) if cluster_metric_values else 0.0
                
                cluster_candidate = {
                    'type': sn_type,
                    'cluster_id': cluster_info['id'],
                    'matches': cluster_info['matches'],
                    'size': cluster_info['size'],
                    'mean_metric': mean_metric,  # Mean of selected best metric (HσLAP-CCC / HLAP)
                    'metric_name': metric_name,  # NEW: Name of metric used
                    'redshift_span': cluster_info['redshift_span'],
                    'cluster_method': 'direct_gmm',
                    'quality_score': 0,  # Updated by method
                    'composite_score': 0,  # Updated by method
                    'is_winning_cluster': False  # Determined by method
                    # enhanced_redshift and other joint estimates will be added below
                }
                
                # Calculate subtype information for this cluster
                try:
                    # Get the type matches and gamma matrix for subtype calculation
                    type_data = clustering_results[sn_type]
                    if type_data.get('success') and 'gamma' in type_data:
                        gamma = type_data['gamma']
                        cluster_idx = cluster_info['id']  # cluster_id is the index within the type
                        
                        # Calculate subtype information for this specific cluster
                        best_subtype, subtype_confidence, subtype_margin_over_second, second_best_subtype = choose_subtype_weighted_voting(
                            sn_type, cluster_idx, type_matches, gamma
                        )
                        
                        # Calculate joint subtype-specific redshift and age estimates for the winning subtype
                        subtype_redshift = np.nan
                        subtype_redshift_err = np.nan
                        subtype_age = np.nan
                        subtype_age_err = np.nan
                        subtype_redshift_age_covariance = np.nan
                        subtype_template_count = 0
                        subtype_age_template_count = 0
                        
                        if best_subtype and best_subtype != 'Unknown':
                            # Use joint estimation for subtype
                            (subtype_redshift, subtype_age, subtype_redshift_err, subtype_age_err, 
                             _, subtype_template_count, subtype_age_template_count) = calculate_joint_subtype_estimates_from_cluster(
                                cluster_candidate['matches'], best_subtype
                            )
                        
                        # Calculate weighted estimates for the full cluster as well
                        cluster_redshift, cluster_age, cluster_redshift_err, cluster_age_err, _ = _compute_weighted_cluster_stats(
                            cluster_candidate['matches']
                        )
                        
                        # Add subtype information to cluster candidate
                        cluster_candidate.update({
                            'subtype_info': {
                                'best_subtype': best_subtype,
                                'subtype_confidence': subtype_confidence,
                                'subtype_margin_over_second': subtype_margin_over_second,
                                'second_best_subtype': second_best_subtype
                            },
                            # Add subtype-specific joint estimates
                            'subtype_redshift': subtype_redshift,
                            'subtype_redshift_err': subtype_redshift_err,
                            'subtype_age': subtype_age,
                            'subtype_age_err': subtype_age_err,
                            'subtype_template_count': subtype_template_count,
                            'subtype_age_template_count': subtype_age_template_count,
                            # Add full cluster joint estimates (update the enhanced_redshift from weighted_mean_redshift)
                            'enhanced_redshift': cluster_redshift,
                            'weighted_redshift_err': cluster_redshift_err,
                            'cluster_age': cluster_age,
                            'cluster_age_err': cluster_age_err
                        })
                        
                        if verbose:
                            _LOGGER.info(f"  Cluster {cluster_id} subtypes: {best_subtype} "
                                        f"(margin: {subtype_margin_over_second:.3f}, second: {second_best_subtype})")
                            
                            if not np.isnan(subtype_redshift) and not np.isnan(subtype_age):
                                _LOGGER.info(f"  Subtype {best_subtype} joint estimates: z={subtype_redshift:.6f}±{subtype_redshift_err:.6f}, "
                                           f"age={subtype_age:.1f}±{subtype_age_err:.1f} days "
                                           f"(from {subtype_age_template_count} templates with both redshift and age)")
                            elif not np.isnan(subtype_redshift):
                                _LOGGER.info(f"  Subtype {best_subtype} redshift: {subtype_redshift:.6f} ± {subtype_redshift_err:.6f}")
                                _LOGGER.warning(f"  Could not calculate joint age estimate for subtype {best_subtype}")
                            else:
                                _LOGGER.warning(f"  Could not calculate joint estimates for subtype {best_subtype}")
                            
                            if not np.isnan(cluster_redshift) and not np.isnan(cluster_age):
                                _LOGGER.info(f"  Full cluster joint estimates: z={cluster_redshift:.6f}±{cluster_redshift_err:.6f}, "
                                           f"age={cluster_age:.1f}±{cluster_age_err:.1f} days")
                except Exception as e:
                    # If subtype calculation fails, add default values
                    # Still calculate full cluster weighted estimates
                    try:
                        cluster_redshift, cluster_age, cluster_redshift_err, cluster_age_err, _ = _compute_weighted_cluster_stats(
                            cluster_candidate['matches']
                        )
                    except:
                        cluster_redshift = cluster_age = cluster_redshift_err = cluster_age_err = _ = np.nan
                    
                    cluster_candidate.update({
                        'subtype_info': {
                            'best_subtype': 'Unknown',
                            'subtype_confidence': 0.0,
                            'subtype_margin_over_second': 0.0,
                            'second_best_subtype': None
                        },
                        # Add default subtype values
                        'subtype_redshift': np.nan,
                        'subtype_redshift_err': np.nan,
                        'subtype_age': np.nan,
                        'subtype_age_err': np.nan,
                        'subtype_template_count': 0,
                        'subtype_age_template_count': 0,
                        # Add full cluster joint estimates (fallback)
                        'enhanced_redshift': cluster_redshift,
                        'weighted_redshift_err': cluster_redshift_err,
                        'cluster_age': cluster_age,
                        'cluster_age_err': cluster_age_err
                    })
                    if verbose:
                        _LOGGER.warning(f"  Failed to calculate subtypes for cluster {cluster_id}: {e}")
                
                all_cluster_candidates.append(cluster_candidate)

        # Per-type progress update
        try:
            if progress_callback is not None and n_types > 0:
                frac = (idx + 1) / float(n_types)
                pct = float(progress_min + (progress_max - progress_min) * frac)
                progress_callback(f"Clustering type {sn_type} ({idx + 1}/{n_types})", pct)
        except Exception:
            pass
    
    # Select best cluster using the new top-5 best metric method
    if not all_cluster_candidates:
        _LOGGER.info("No valid clusters found")
        return {'success': False, 'reason': 'no_clusters'}
    
    # Select best cluster (top-5 penalized score). Do not gate/throw away clusters.
    best_cluster, quality_assessment = find_winning_cluster_top5_method(
        all_cluster_candidates,
        hsigma_lap_ccc_threshold=float(hsigma_lap_ccc_threshold),
        verbose=verbose
    )
    
    if best_cluster is None:
        _LOGGER.warning("New cluster selection method failed")
        return {'success': False, 'reason': 'cluster_selection_failed'}

    # Expose all cluster candidates (no Q_cluster gate).
    valid_candidates = [c for c in all_cluster_candidates if isinstance(c, dict)]
    
    # Update the best cluster with new quality metrics
    best_cluster['quality_assessment'] = quality_assessment['quality_assessment']
    best_cluster['confidence_assessment'] = quality_assessment['confidence_assessment']
    best_cluster['selection_method'] = 'top5_best_metric'
    
    total_time = time.time() - start_time
    
    if verbose:
        _LOGGER.info("🏆 All cluster candidates (before new selection method):")
        for i, candidate in enumerate(all_cluster_candidates[:5]):
            _LOGGER.info(f"   {i+1}. {candidate['type']} cluster {candidate['cluster_id']}: "
                        f"size={candidate['size']}, z-span={candidate['redshift_span']:.4f}")
    
    _LOGGER.info(f"✅ Direct GMM clustering completed in {total_time:.3f}s")
    _LOGGER.info(f"Best cluster: {best_cluster['type']} cluster {best_cluster.get('cluster_id', 0)} "
                 f"(Quality: {best_cluster['quality_assessment']['quality_category']}, "
                 f"Confidence: {best_cluster['confidence_assessment']['confidence_level']})")
    
    return {
        'success': True,
        'method': 'direct_gmm',
        'metric_used': metric_name,  # NEW: Which metric was used
        'selection_method': 'top5_best_metric',  # Selection method used
        'type_clustering_results': clustering_results,
        'best_cluster': best_cluster,
        'all_candidates': valid_candidates,
        'quality_assessment': quality_assessment,  # NEW: Complete quality assessment
        'total_computation_time': total_time,
        'n_types_clustered': len(clustering_results),
        'use_weighted_gmm': bool(use_weighted_gmm),
        'total_candidates': len(valid_candidates)
    }


def _perform_direct_gmm_clustering(
    type_matches: List[Dict[str, Any]], 
    sn_type: str,
    max_clusters: int,
    verbose: bool,
    metric_key: str = 'best_metric',  # Uses get_best_metric_value() automatically
    *,
    use_weighted_gmm: bool = False,
    model_selection_method: str = "elbow",
) -> Dict[str, Any]:
    """
    Perform GMM clustering directly on redshift values using the same approach
    as transformation_comparison_test.py.
    """
    
    try:
        redshifts = np.array([m['redshift'] for m in type_matches])
        from snid_sage.shared.utils.math_utils import get_best_metric_value, calculate_combined_weights
        from snid_sage.shared.utils.match_utils import extract_redshift_sigma
        metric_values = np.array([get_best_metric_value(m) for m in type_matches])  # Use best available metric
        sigmas = np.array([extract_redshift_sigma(m) for m in type_matches], dtype=float)
        
        # Suppress sklearn convergence warnings for cleaner output
        import warnings
        from sklearn.exceptions import ConvergenceWarning
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        
        # Step 1: Optionally build double weights and select model with weighted or unweighted BIC
        n_matches = len(type_matches)
        max_clusters_actual = min(max_clusters, n_matches // 2 + 1)
        
        if max_clusters_actual < 2:
            # Single match or too few for multi-cluster GMM - create single cluster
            _LOGGER.info(f"Creating single cluster for {sn_type} ({n_matches} matches)")
            return _create_single_cluster_result(
                type_matches, sn_type, redshifts, "best_metric"
            )
        
        # Build weights only when requested; default to unweighted GMM.
        # Official weighting policy (HσLAP-CCC): w_i = (metric_i)^2
        if use_weighted_gmm:
            raw_weights = calculate_combined_weights(metric_values, sigmas)
            sum_w = float(np.sum(raw_weights)) if raw_weights.size else 0.0
            weights = raw_weights if (sum_w > 0 and np.isfinite(sum_w)) else np.ones_like(metric_values, dtype=float)
        else:
            weights = None

        bic_scores = []
        models = []
        
        for n_clusters in range(1, max_clusters_actual + 1):
            gmm = GaussianMixture(
                n_components=n_clusters, 
                random_state=42,
                max_iter=200,  # Same as transformation_comparison_test.py
                covariance_type='full',  # Same as transformation_comparison_test.py
                tol=1e-6  # Same as transformation_comparison_test.py
            )

            # Cluster directly on redshift values (no transformation)
            features = redshifts.reshape(-1, 1)

            if use_weighted_gmm and weights is not None:
                # Weighted fit and weighted BIC; fallback to resampling if needed
                d = features.shape[1]
                try:
                    gmm.fit(features, sample_weight=weights)
                    logprob = gmm.score_samples(features)
                    # Parameter count for full covariance
                    p = (n_clusters - 1) + n_clusters * d + n_clusters * d * (d + 1) / 2.0
                    bic = -2.0 * float(np.sum(weights * logprob)) + float(p) * np.log(float(np.sum(weights)))
                except TypeError:
                    # Resampling fallback
                    rng = np.random.RandomState(42)
                    # Target size similar to test script bounds
                    target = int(min(max(len(features) * 5, 300), 5000)) if len(features) > 0 else 0
                    if target > 0:
                        p_norm = weights / float(np.sum(weights)) if np.sum(weights) > 0 else np.full_like(weights, 1.0 / len(weights))
                        idx = rng.choice(np.arange(len(features)), size=target, replace=True, p=p_norm)
                        features_rs = features[idx]
                        gmm.fit(features_rs)
                        bic = float(gmm.bic(features_rs))
                    else:
                        gmm.fit(features)
                        bic = float(gmm.bic(features))
            else:
                # Unweighted default path
                gmm.fit(features)
                bic = float(gmm.bic(features))

            bic_scores.append(bic)
            models.append(gmm)
        
        # ------------------------------------------------------------------
        # Model selection: BIC (default) or elbow-knee heuristic on the BIC curve
        # ------------------------------------------------------------------
        requested_model_selection_method = None
        try:
            requested_model_selection_method = str(model_selection_method or "elbow").strip().lower()
        except Exception:
            requested_model_selection_method = "elbow"
        if requested_model_selection_method not in ("bic", "elbow"):
            requested_model_selection_method = "elbow"
        effective_model_selection_method = requested_model_selection_method

        bic_scores_arr = np.asarray(bic_scores, dtype=float)
        bic_optimal_idx = int(np.argmin(bic_scores_arr)) if bic_scores_arr.size else 0
        bic_optimal_n_clusters = bic_optimal_idx + 1

        # Elbow: max-distance-to-chord on goodness = -BIC (higher is better)
        def _elbow_max_distance_k(scores: np.ndarray) -> Optional[int]:
            if scores.size < 3:
                return None
            x = np.arange(scores.size, dtype=float)
            y = np.asarray(scores, dtype=float)
            if not np.all(np.isfinite(y)):
                return None
            x0, y0 = float(x[0]), float(y[0])
            x1, y1 = float(x[-1]), float(y[-1])
            dx = x1 - x0
            dy = y1 - y0
            norm = float(np.hypot(dx, dy))
            if norm <= 0:
                return None
            dist = np.abs(dy * x - dx * y + x1 * y0 - y1 * x0) / norm
            idx = int(np.argmax(dist))
            return idx + 1  # k (1-indexed)

        elbow_n_clusters = _elbow_max_distance_k(-bic_scores_arr) if bic_scores_arr.size else None

        # Safety: if BIC is monotone non-decreasing (min at k=1), treat elbow as k=1 too.
        try:
            if bic_scores_arr.size >= 2 and np.all(np.isfinite(bic_scores_arr)):
                if (bic_optimal_idx == 0) and bool(np.all(np.diff(bic_scores_arr) >= 0)):
                    elbow_n_clusters = 1
        except Exception:
            pass

        if requested_model_selection_method == "elbow":
            if isinstance(elbow_n_clusters, int) and 1 <= elbow_n_clusters <= len(models):
                selected_idx = int(elbow_n_clusters - 1)
            else:
                # Fallback to BIC minimum if elbow is undefined/invalid for this curve.
                selected_idx = int(bic_optimal_idx)
                effective_model_selection_method = "bic"
        else:
            selected_idx = int(bic_optimal_idx)

        best_gmm = models[selected_idx]
        selected_n_components = int(getattr(best_gmm, "n_components", selected_idx + 1))

        # Get cluster assignments and responsibilities
        features = redshifts.reshape(-1, 1)
        labels = best_gmm.predict(features)
        gamma = best_gmm.predict_proba(features)

        # Enforce contiguity in 1D redshift: split any non-contiguous cluster into
        # contiguous segments along sorted redshift order, then split by hard gaps
        order = np.argsort(redshifts)
        labels_sorted = labels[order]

        # Run-length encode labels along sorted z
        runs = []  # list of (label, start_idx_in_sorted, end_idx_in_sorted)
        start = 0
        for i in range(1, len(labels_sorted) + 1):
            if i == len(labels_sorted) or labels_sorted[i] != labels_sorted[i - 1]:
                runs.append((labels_sorted[i - 1], start, i))
                start = i

        # Build contiguous segments per original label
        segments = []  # list of (orig_label, absolute_indices)
        label_to_run_count = {k: 0 for k in range(selected_n_components)}
        min_segment_size = 1  # keep even tiny side clusters; scoring penalizes later
        for orig_label in range(selected_n_components):
            run_spans = [(s, e) for lbl, s, e in runs if lbl == orig_label]
            label_to_run_count[orig_label] = len(run_spans)
            for (s, e) in run_spans:
                idx = order[s:e]
                if len(idx) >= min_segment_size:
                    segments.append((orig_label, idx))

        split_applied = any(cnt > 1 for cnt in label_to_run_count.values())

        final_clusters = []
        # Hard gap split base (will be scaled by (1+z) for z>0).
        BASE_MAX_GAP_Z = 0.01

        # Helper: split a sorted-by-z absolute index run by redshift gaps
        def _split_by_gap(abs_idx: np.ndarray, z: np.ndarray) -> List[np.ndarray]:
            if abs_idx.size <= 1:
                return [abs_idx]
            parts: List[np.ndarray] = []
            start = 0
            for r in range(1, abs_idx.size):
                z_prev = float(z[abs_idx[r - 1]])
                z_cur = float(z[abs_idx[r]])
                # Scale gap threshold by (1+z_mid) for z>0; keep base for z<=0.
                z_mid = 0.5 * (z_prev + z_cur)
                scale = 1.0 + max(0.0, float(z_mid))
                thr = float(BASE_MAX_GAP_Z * scale)
                if abs(z_cur - z_prev) > thr:
                    parts.append(abs_idx[start:r])
                    start = r
            parts.append(abs_idx[start:])
            return parts

        # Build final segments (run-contiguity plus gap splits)
        segment_records: List[Tuple[int, np.ndarray, bool]] = []  # (orig_label, indices, is_gap_split)
        for orig_label, idx in segments:
            # idx is in absolute index order of the run; ensure it is sorted by z for consistent gap checks
            idx_sorted = idx[np.argsort(redshifts[idx])]
            parts = _split_by_gap(idx_sorted, redshifts)
            if len(parts) <= 1:
                segment_records.append((orig_label, idx_sorted, False))
            else:
                for j, part in enumerate(parts):
                    segment_records.append((orig_label, part, True))

        if segment_records:
            # Rebuild responsibilities with one column per final segment
            n_segments = len(segment_records)
            new_gamma = np.zeros((len(type_matches), n_segments), dtype=float)
            for j, (orig_label, idx, _is_gap) in enumerate(segment_records):
                new_gamma[idx, j] = gamma[idx, orig_label]
            gamma = new_gamma

            # Build clusters from final segments
            for new_id, (orig_label, idx, is_gap) in enumerate(segment_records):
                cluster_redshifts = redshifts[idx]
                cluster_metric_values = metric_values[idx]
                cluster_matches = [type_matches[i] for i in idx]

                redshift_span = float(np.max(cluster_redshifts) - np.min(cluster_redshifts)) if len(cluster_redshifts) > 0 else 0.0

                weighted_mean_redshift, _, weighted_redshift_err, _, _ = _compute_weighted_cluster_stats(cluster_matches)

                final_clusters.append({
                    'id': new_id,
                    'matches': cluster_matches,
                    'size': len(cluster_matches),
                    'mean_metric': float(np.mean(cluster_metric_values)) if len(cluster_metric_values) > 0 else 0.0,
                    'std_metric': float(np.std(cluster_metric_values)) if len(cluster_metric_values) > 1 else 0.0,
                    'metric_key': metric_key,
                    'weighted_mean_redshift': float(weighted_mean_redshift) if np.isfinite(weighted_mean_redshift) else np.nan,
                    'weighted_redshift_err': float(weighted_redshift_err) if np.isfinite(weighted_redshift_err) else np.nan,
                    'redshift_span': redshift_span,
                    'cluster_method': 'direct_gmm_contiguous',
                    'metric_range': (float(np.min(cluster_metric_values)), float(np.max(cluster_metric_values))) if len(cluster_metric_values) > 0 else (0.0, 0.0),
                    'redshift_range': (float(np.min(cluster_redshifts)), float(np.max(cluster_redshifts))) if len(cluster_redshifts) > 0 else (0.0, 0.0),
                    'top_5_values': [],
                    'top_5_mean': 0.0,
                    'penalty_factor': 1.0,
                    'penalized_score': 0.0,
                    'composite_score': 0.0,
                    # New annotations used by tests/plots
                    'segment_id': new_id,
                    'gap_split': bool(is_gap),
                    'indices': [int(v) for v in idx.tolist()],
                })

                if verbose:
                    _LOGGER.info(f"  Segment {new_id} (from label {orig_label}): z-span={redshift_span:.4f}")

            # Keep BIC-optimal count separate from post-split count
            pass
        else:
            # Create cluster info from original labels (already contiguous)
            for cluster_id in range(bic_optimal_n_clusters):
                cluster_mask = (labels == cluster_id)
                cluster_indices = np.where(cluster_mask)[0]

                if len(cluster_indices) < 1:
                    continue

                cluster_redshifts = redshifts[cluster_mask]
                cluster_metric_values = metric_values[cluster_mask]
                cluster_matches = [type_matches[i] for i in cluster_indices]

                redshift_span = np.max(cluster_redshifts) - np.min(cluster_redshifts)

                weighted_mean_redshift, _, weighted_redshift_err, _, _ = _compute_weighted_cluster_stats(cluster_matches)

                cluster_info = {
                    'id': cluster_id,
                    'matches': cluster_matches,
                    'size': len(cluster_matches),
                    'mean_metric': np.mean(cluster_metric_values),
                    'std_metric': np.std(cluster_metric_values) if len(cluster_metric_values) > 1 else 0.0,
                    'metric_key': metric_key,
                    'weighted_mean_redshift': weighted_mean_redshift,
                    'weighted_redshift_err': weighted_redshift_err,
                    'redshift_span': redshift_span,
                    'cluster_method': 'direct_gmm',
                    'metric_range': (np.min(cluster_metric_values), np.max(cluster_metric_values)),
                    'redshift_range': (np.min(cluster_redshifts), np.max(cluster_redshifts)),
                    'top_5_values': [],
                    'top_5_mean': 0.0,
                    'penalty_factor': 1.0,
                    'penalized_score': 0.0,
                    'composite_score': 0.0,
                    # Consistent annotations for UI/tests even when no gap split applied
                    'segment_id': cluster_id,
                    'gap_split': False,
                    'indices': [int(v) for v in cluster_indices.tolist()],
                }
                final_clusters.append(cluster_info)

                if verbose:
                    _LOGGER.info(f"  Cluster {cluster_id}: z-span={redshift_span:.4f}")

        return {
            'success': True,
            'type': sn_type,
            # Selected number of mixture components (before contiguity/gap splitting)
            'optimal_n_clusters': selected_n_components,
            'selected_n_components': selected_n_components,
            'requested_model_selection_method': requested_model_selection_method,
            'effective_model_selection_method': effective_model_selection_method,
            # Reference diagnostics
            'bic_optimal_n_clusters': bic_optimal_n_clusters,
            'elbow_n_clusters': elbow_n_clusters,
            'final_n_clusters': len(final_clusters),
            'bic_scores': bic_scores,
            'clusters': final_clusters,
            'gmm_model': best_gmm,
            'gamma': gamma,
            'type_matches': type_matches,  # Store the original matches used for gamma matrix
            'contiguity_split_applied': True if final_clusters else bool(split_applied),
            # Debug extras
            'weights': weights.tolist() if isinstance(weights, np.ndarray) else []
        }
                
    except Exception as e:
        _LOGGER.error(f"Direct GMM clustering failed for type {sn_type}: {e}")
        return {'success': False, 'type': sn_type, 'error': str(e)}


def _create_single_cluster_result(
    type_matches: List[Dict[str, Any]], 
    sn_type: str, 
    redshifts: np.ndarray, 
    metric_key: str = 'best_metric'  # Uses get_best_metric_value()
) -> Dict[str, Any]:
    """Create a single cluster result when clustering isn't possible/needed."""
    
    redshift_span = np.max(redshifts) - np.min(redshifts) if len(redshifts) > 1 else 0.0
    
    # Get metric values using best available metric
    from snid_sage.shared.utils.math_utils import get_best_metric_value
    metric_values = np.array([get_best_metric_value(m) for m in type_matches])
    
    # No redshift-quality classification.
    
    # Calculate enhanced redshift statistics using joint estimation (just extract redshift)
    weighted_mean_redshift, _, weighted_redshift_sd, _, _ = _compute_weighted_cluster_stats(type_matches)
    
    cluster_info = {
        'id': 0,
        'matches': type_matches,
        'size': len(type_matches),
        'mean_metric': np.mean(metric_values),  # NEW: Mean of selected metric
        'std_metric': np.std(metric_values) if len(metric_values) > 1 else 0.0,  # NEW
        'metric_key': metric_key,  # NEW: Which metric was used
                    # Enhanced redshift statistics
        'weighted_mean_redshift': weighted_mean_redshift,
        'weighted_redshift_err': weighted_redshift_sd,
        'redshift_span': redshift_span,
        'cluster_method': 'single_cluster',
        'metric_range': (np.min(metric_values), np.max(metric_values)),  # NEW
        'redshift_range': (np.min(redshifts), np.max(redshifts)),
        'top_5_values': [],
        'top_5_mean': 0.0,
        'penalty_factor': 1.0,
        'penalized_score': 0.0,
        'composite_score': 0.0
    }
    
    # Create a trivial responsibilities matrix (all weight to the single cluster)
    try:
        gamma = np.ones((len(type_matches), 1), dtype=float)
    except Exception:
        gamma = None

    return {
        'success': True,
        'type': sn_type,
        'optimal_n_clusters': 1,
        'final_n_clusters': 1,
        'clusters': [cluster_info],
        'gamma': gamma,
        'type_matches': type_matches
    }


def choose_subtype_weighted_voting(
    winning_type: str, 
    k_star: int, 
    matches: List[Dict[str, Any]], 
    gamma: np.ndarray, 
    resp_cut: float = 0.001
) -> tuple:
    """
    Choose the best subtype within the winning cluster using top-5 best metric method.
    
    Args:
        winning_type: The winning type (e.g., "Ia")
        k_star: Index of the winning cluster within that type
        matches: List of template matches for the winning type
        gamma: GMM responsibilities matrix, shape (n_matches, n_clusters)
        resp_cut: Minimum responsibility threshold
    
    Returns:
        tuple: (best_subtype, confidence (always 0.0), margin_over_second, second_best_subtype)
    """
    
    # Collect cluster members
    cluster_members = []
    
    # Safety check: ensure gamma matrix dimensions match matches list
    if len(matches) != gamma.shape[0]:
        _LOGGER.error(f"Dimension mismatch: matches={len(matches)}, gamma.shape={gamma.shape}")
        raise ValueError(f"Matches list length ({len(matches)}) does not match gamma matrix rows ({gamma.shape[0]})")
    
    # Safety check: ensure k_star is valid cluster index
    if k_star >= gamma.shape[1]:
        _LOGGER.error(f"Cluster index out of bounds: k_star={k_star}, gamma.shape[1]={gamma.shape[1]}")
        raise ValueError(f"Cluster index {k_star} is out of bounds for gamma matrix with {gamma.shape[1]} clusters")
    
    for i, match in enumerate(matches):
        # Include members assigned to the selected cluster (no responsibility threshold)
        # Assignment is by argmax of responsibilities, matching how cluster members are defined downstream
        try:
            assigned_cluster = int(np.argmax(gamma[i, :]))
        except Exception:
            assigned_cluster = -1
        if assigned_cluster != k_star:
            continue
        
        subtype = match['template'].get('subtype', 'Unknown')
        if not subtype or subtype.strip() == '':
            subtype = 'Unknown'
        
        # Use best available metric (HσLAP-CCC preferred)
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        metric_value = get_best_metric_value(match)
        # Pull per-match redshift uncertainty if available
        sigma_z = match.get('sigma_z', match.get('z_err', None))
        
        cluster_members.append({
            'subtype': subtype,
            'metric_value': metric_value,
            'cluster_membership': gamma[i, k_star],
            'sigma_z': sigma_z
        })
    
    if not cluster_members:
        return "Unknown", 0.0, 0.0, None
    
    # Group by subtype and calculate top-5 mean best metric for each
    subtype_groups = defaultdict(list)
    for member in cluster_members:
        subtype_groups[member['subtype']].append(member)
    
    # Calculate top-5 mean for each subtype using the SAME scoring rule as cluster selection:
    # simple mean of the top-5 best-metric values, with a linear penalty when fewer than 5
    # templates are available.
    subtype_scores = {}
    for subtype, members in subtype_groups.items():
        # Sort by metric value (best available) descending
        sorted_members = sorted(members, key=lambda x: x['metric_value'], reverse=True)
        
        # Take top 5 (or all if less than 5)
        top_members = sorted_members[:5]
        top_values = [m['metric_value'] for m in top_members]
        # Simple mean
        metrics_array = np.asarray(top_values, dtype=float)
        metrics_array = metrics_array[np.isfinite(metrics_array)]
        mean_top = float(np.mean(metrics_array)) if metrics_array.size else 0.0
        
        # Apply penalty if less than 5 templates
        penalty_factor = len(top_values) / 5.0  # 1.0 if 5 templates, 0.8 if 4, etc.
        
        # Final score = mean_top × penalty_factor
        subtype_scores[subtype] = mean_top * penalty_factor
    
    if not subtype_scores:
        return "Unknown", 0.0, 0.0, None
    
    # Find best subtype
    best_subtype = max(subtype_scores, key=subtype_scores.get)
    best_score = subtype_scores[best_subtype]
    
    # Calculate margin over second best
    sorted_scores = sorted(subtype_scores.values(), reverse=True)
    margin_over_second = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
    
    # Using top-5 mean and relative margin
    confidence = 0.0
    
    # Calculate relative margin as percentage (more intuitive for display)
    relative_margin_pct = 0.0
    if len(sorted_scores) > 1 and sorted_scores[1] > 0:
        second_best_score = sorted_scores[1]
        relative_margin_pct = (margin_over_second / second_best_score) * 100
    
    # Get second best subtype if available
    second_best_subtype = None
    if len(sorted_scores) > 1:
        second_best_score = sorted_scores[1]
        # Find which subtype has this score
        for subtype, score in subtype_scores.items():
            if abs(score - second_best_score) < 1e-6:  # Float comparison
                second_best_subtype = subtype
                break
    
    return best_subtype, confidence, relative_margin_pct, second_best_subtype





def create_3d_visualization_data(clustering_results: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Prepare data for 3D visualization: redshift vs type vs best metric (HσLAP-CCC / HLAP)."""
    
    redshifts = []
    metric_values = []
    types = []
    type_indices = []
    cluster_ids = []
    matches = []  # Store matches for access to best metric values
    
    type_to_index = {}
    current_type_index = 0
    
    # Check if we have the new clustering structure with all_candidates
    if 'all_candidates' in clustering_results:
        # New structure: use all_candidates
        for candidate in clustering_results.get('all_candidates', []):
            sn_type = candidate.get('type', 'Unknown')
            if sn_type not in type_to_index:
                type_to_index[sn_type] = current_type_index
                current_type_index += 1
            
            type_index = type_to_index[sn_type]
            cluster_id = candidate.get('cluster_id', 0)
            
            for match in candidate.get('matches', []):
                redshifts.append(match['redshift'])
                # Use best available metric (HσLAP-CCC preferred)
                from snid_sage.shared.utils.math_utils import get_best_metric_value
                metric_values.append(get_best_metric_value(match))
                types.append(sn_type)
                type_indices.append(type_index)
                cluster_ids.append(cluster_id)
                matches.append(match)
    
    else:
        # Fallback: structure with type_clustering_results
        for type_result in clustering_results.get('type_clustering_results', {}).values():
            if not type_result.get('success', False):
                continue
                
            sn_type = type_result['type']
            if sn_type not in type_to_index:
                type_to_index[sn_type] = current_type_index
                current_type_index += 1
            
            type_index = type_to_index[sn_type]
            
            for cluster in type_result['clusters']:
                for match in cluster['matches']:
                    redshifts.append(match['redshift'])
                    # Use best available metric (HσLAP-CCC preferred)
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    metric_values.append(get_best_metric_value(match))
                    types.append(sn_type)
                    type_indices.append(type_index)
                    cluster_ids.append(cluster['id'])
                    matches.append(match)
    
    return {
        'redshifts': np.array(redshifts),
        # Best available metric values (HσLAP-CCC preferred; fallback to HLAP)
        'metric_values': np.array(metric_values),
        'types': types,
        'type_indices': np.array(type_indices),
        'cluster_ids': np.array(cluster_ids),
        'type_mapping': type_to_index,
        'matches': matches  # Include matches for access to best metric values
    }






def find_winning_cluster_top5_method(
    all_cluster_candidates: List[Dict[str, Any]], 
    hsigma_lap_ccc_threshold: float = 1.5,
    *,
    verbose: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Find the winning cluster using the top-5 best metric method (HσLAP-CCC preferred; fallback to HLAP).
    
    This method:
    1. Takes the top 5 best metric values from each cluster (using get_best_metric_value()).
    2. Calculates the SIMPLE mean of these top-5 values.
    3. Penalizes clusters with fewer than 5 points (linear penalty = N_top/5).
    4. Selects the cluster with the highest mean
    5. Provides confidence assessment vs other clusters
    6. Provides absolute quality assessment (Low/Mid/High)
    
    Parameters
    ----------
    all_cluster_candidates : List[Dict[str, Any]]
        List of all cluster candidates from GMM clustering
    verbose : bool, optional
        Enable detailed logging
        
    Returns
    -------
    Tuple[Dict[str, Any], Dict[str, Any]]
        (winning_cluster, quality_assessment)
    """
    if not all_cluster_candidates:
        return None, {'error': 'No cluster candidates available'}
    
    # Parameters not used anymore; see get_best_metric_value() calls
    # Standardize metric naming; do not imply comparison phrasing.
    metric_name = 'HσLAP-CCC'
    
    # We intentionally do NOT "gate" / discard clusters based on Q_cluster.
    # We still compute the penalized top-5 score (a.k.a. Q_cluster) for ranking/reporting.

    # Calculate top-5 means for each cluster
    cluster_scores = []
    
    for cluster in all_cluster_candidates:
        matches = cluster.get('matches', [])
        if not matches:
            continue
            
        # Extract metric values (HσLAP-CCC preferred via get_best_metric_value) and sort descending.
        metric_vals = []
        for match in matches:
            # Top-5 penalized scoring / comparisons use metric values directly (no weighting).
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            metric = get_best_metric_value(match)
            try:
                metric_vals.append(float(metric))
            except Exception:
                continue
        
        metric_vals.sort(reverse=True)  # Highest metric first
        
        # Take top 5 (or all if fewer than 5)
        top_5_values = metric_vals[:5]

        # Simple mean of top-5.
        top_1_share = 0.0
        if top_5_values:
            metrics_array = np.asarray(top_5_values, dtype=float)
            metrics_array = metrics_array[np.isfinite(metrics_array)]
            top_5_mean = float(np.mean(metrics_array)) if metrics_array.size else 0.0
            # Diagnostic: top-1 share of the SUM of top-5 metrics (not weights).
            denom = float(np.sum(metrics_array)) if metrics_array.size else 0.0
            top_1_share = float(metrics_array[0] / denom) if denom > 0 else 0.0
        else:
            top_5_mean = 0.0
            top_1_share = 0.0
        
        # Apply penalty using the same linear scheme as subtype selection: count/5.0 (capped at 1.0)
        penalty_factor = (len(top_5_values) / 5.0) if top_5_values else 0.0
        if penalty_factor > 1.0:
            penalty_factor = 1.0
        
        penalized_score = top_5_mean * penalty_factor  # Q_cluster (penalized top-5 best metric)

        # No validity gate: always keep clusters as valid.
        is_valid_cluster = True
        validity_reason = ""
        
        # Annotate the original cluster dictionary so downstream UIs can display these metrics
        cluster['top_5_values'] = top_5_values
        cluster['top_5_mean'] = top_5_mean
        cluster['penalty_factor'] = penalty_factor
        cluster['penalized_score'] = penalized_score
        # For convenience update composite_score field used in various summaries
        cluster['composite_score'] = penalized_score
        # Validity annotations for reporting/UX
        cluster['is_valid_cluster'] = bool(is_valid_cluster)
        cluster['q_cluster_threshold'] = None
        cluster['cluster_validity_reason'] = validity_reason
        # Store the top-1 contribution share for diagnostics/reporting
        cluster['top_1_share'] = top_1_share
        
        cluster_info = {
            'cluster': cluster,
            'cluster_size': len(matches),
            'top_5_values': top_5_values,
            'top_5_mean': top_5_mean,
            'penalty_factor': penalty_factor,
            'penalized_score': penalized_score,
            'cluster_type': cluster.get('type', 'Unknown'),
            'cluster_id': cluster.get('cluster_id', 0),
            'top_1_share': top_1_share,
            'is_valid_cluster': bool(is_valid_cluster),
            'q_cluster_threshold': None,
            'cluster_validity_reason': validity_reason
        }
        
        cluster_scores.append(cluster_info)
    
    if not cluster_scores:
        return None, {'error': 'No valid clusters found'}
    
    # Sort by penalized score (highest first)
    cluster_scores.sort(key=lambda x: x['penalized_score'], reverse=True)
    
    # Winner is the cluster with highest penalized score
    winning_cluster_info = cluster_scores[0]
    winning_cluster = winning_cluster_info['cluster']

    # No validity gate: the best cluster is always the top-ranked penalized score.
    
    # Calculate confidence assessment
    confidence_assessment = _calculate_cluster_confidence(cluster_scores, metric_name)
    
    # Calculate absolute quality assessment
    quality_assessment = _calculate_absolute_quality(winning_cluster_info, metric_name)
    
    # Combine assessments
    full_assessment = {
        'winning_cluster': winning_cluster,
        'winning_cluster_info': winning_cluster_info,
        'all_cluster_scores': cluster_scores,
        'confidence_assessment': confidence_assessment,
        'quality_assessment': quality_assessment,
        'metric_used': metric_name,
        'selection_method': 'top5_hsigma_lap_ccc'
    }
    
    if verbose:
        _log_cluster_selection_details(full_assessment)
    
    return winning_cluster, full_assessment


def _calculate_cluster_confidence(cluster_scores: List[Dict[str, Any]], metric_name: str) -> Dict[str, Any]:
    """Calculate relative confidence as percent improvement vs best different-type competitor.

    Returns a minimal assessment with:
      - confidence_pct: percent improvement (NaN if no different-type competitor)
      - confidence_level: discrete flag derived from confidence_pct
      - second_best_type: type of best different-type competitor (or 'N/A')
      - confidence_description: concise human-readable summary
    """
    # Not enough clusters to compare
    if len(cluster_scores) < 2:
        return {
            'confidence_pct': float('nan'),
            'confidence_level': 'No Comp',
            'confidence_description': 'Single cluster',
            'second_best_type': 'N/A'
        }

    # Find the first runner-up of a different type than the winner
    winning_type = cluster_scores[0]['cluster_type']
    competitor_info = None
    for i in range(1, len(cluster_scores)):
        if cluster_scores[i]['cluster_type'] != winning_type:
            competitor_info = cluster_scores[i]
            break

    # No different-type competitor -> undefined percent (NaN)
    if competitor_info is None:
        return {
            'confidence_pct': float('nan'),
            'confidence_level': 'No Comp',
            'confidence_description': 'No competitor',
            'second_best_type': 'N/A'
        }

    best_score = float(cluster_scores[0]['penalized_score'])
    second_best_score = float(competitor_info['penalized_score'])

    # Percent improvement; guard zero competitor
    if second_best_score > 0.0:
        confidence_pct = (best_score - second_best_score) / second_best_score * 100.0
    else:
        # Treat as undefined; display can clamp if desired
        confidence_pct = float('nan')

    # Discrete flag from percent thresholds
    if isinstance(confidence_pct, float) and not np.isnan(confidence_pct):
        # Thresholds (percent improvement vs second best):
        #   High   ≥ 75%
        #   Medium ≥ 25%
        #   Low    ≥ 5%
        #   else     Very Low
        if confidence_pct >= 75.0:
            confidence_level = 'High'
        elif confidence_pct >= 25.0:
            confidence_level = 'Medium'
        elif confidence_pct >= 5.0:
            confidence_level = 'Low'
        else:
            confidence_level = 'Very Low'
        confidence_description = f"{confidence_pct:.1f}% better than second best"
    else:
        confidence_level = 'N/A'
        confidence_description = 'N/A'

    return {
        'confidence_pct': confidence_pct,
        'confidence_level': confidence_level,
        'confidence_description': confidence_description,
        'second_best_type': competitor_info['cluster_type']
    }


def _calculate_absolute_quality(winning_cluster_info: Dict[str, Any], metric_name: str) -> Dict[str, Any]:
    """Calculate absolute quality assessment for the winning cluster using penalized top-5 score."""
    
    # Use the already calculated penalized score from the winning cluster
    penalized_score = winning_cluster_info['penalized_score']
    top_5_mean = winning_cluster_info['top_5_mean']
    penalty_factor = winning_cluster_info['penalty_factor']
    cluster_size = winning_cluster_info['cluster_size']
    
    # Quality categories based on penalized top-5 score (Q_cluster; global rule)
    #  - Very Low: < 2.5
    #  - Low: 2.5 to < 5
    #  - Medium: 5 to < 8
    #  - High: ≥ 8
    if penalized_score >= 8.0:
        quality_category = 'High'
        quality_description = f'Excellent match quality (HσLAP-CCC: {penalized_score:.2f})'
    elif penalized_score >= 5.0:
        quality_category = 'Medium'
        quality_description = f'Good match quality (HσLAP-CCC: {penalized_score:.2f})'
    elif penalized_score >= 2.5:
        quality_category = 'Low'
        quality_description = f'Poor match quality (HσLAP-CCC: {penalized_score:.2f})'
    else:
        quality_category = 'Very Low'
        quality_description = f'Very poor match quality (HσLAP-CCC: {penalized_score:.2f})'
    
    # Add penalty information if applicable
    if penalty_factor < 1.0:
        quality_description += f' [Penalty applied: {penalty_factor:.2f} for {cluster_size} matches < 5]'
    
    return {
        'quality_category': quality_category,
        'quality_description': quality_description,
        'mean_top_5': top_5_mean,
        'penalized_score': penalized_score,
        'penalty_factor': penalty_factor,
        'cluster_size': cluster_size,
        'quality_metric': metric_name
    }


def _log_cluster_selection_details(assessment: Dict[str, Any]) -> None:
    """Log detailed information about cluster selection."""
    winning_info = assessment['winning_cluster_info']
    confidence = assessment['confidence_assessment']
    quality = assessment['quality_assessment']
    
    _LOGGER.info(f"🏆 NEW CLUSTER SELECTION METHOD RESULTS:")
    _LOGGER.info(f"   Winner: {winning_info['cluster_type']} cluster {winning_info['cluster_id']}")
    _LOGGER.info(f"   Cluster size: {winning_info['cluster_size']} templates")
    _LOGGER.info(f"   Top-5 mean: {winning_info['top_5_mean']:.3f}")
    _LOGGER.info(f"   Penalty factor: {winning_info['penalty_factor']:.3f}")
    _LOGGER.info(f"   Final score: {winning_info['penalized_score']:.3f}")
    try:
        share_pct = float(winning_info.get('top_1_share', 0.0)) * 100.0
        _LOGGER.info(f"   Top-1 share of top-5 metric sum: {share_pct:.1f}%")
    except Exception:
        pass
    
    _LOGGER.info(f"🔍 CONFIDENCE ASSESSMENT:")
    _LOGGER.info(f"   Confidence level: {confidence['confidence_level'].upper()}")
    _LOGGER.info(f"   {confidence['confidence_description']}")
    
    _LOGGER.info(f"📊 QUALITY ASSESSMENT:")
    _LOGGER.info(f"   Quality category: {quality['quality_category']}")
    _LOGGER.info(f"   {quality['quality_description']}")
    
    # Show top 3 clusters
    _LOGGER.info(f"🏅 TOP 3 CLUSTERS:")
    for i, cluster_info in enumerate(assessment['all_cluster_scores'][:3], 1):
        _LOGGER.info(f"   {i}. {cluster_info['cluster_type']} (score: {cluster_info['penalized_score']:.3f}, "
                    f"size: {cluster_info['cluster_size']}, "
                    f"top-5 mean: {cluster_info['top_5_mean']:.3f})")


