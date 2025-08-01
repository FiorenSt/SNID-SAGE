"""
Direct GMM Clustering for SNID SAGE
===================================

This module implements GMM clustering directly on redshift values for 
template matching analysis without any transformations.

Key features:
1. Direct GMM clustering on redshift values (no transformations)
2. Type-specific clustering with BIC-based model selection
3. Top 10% RLAP-based cluster selection
4. Weighted subtype determination within winning clusters
5. Statistical confidence assessment for subtype classification

The clustering works directly with redshift values using the same approach
as the transformation_comparison_test.py reference implementation.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from sklearn.mixture import GaussianMixture
import logging
import time
from collections import defaultdict
import scipy.stats as stats

_LOGGER = logging.getLogger(__name__)


# Note: find_winning_cluster_exact_match has been replaced by find_winning_cluster_top5_method
# The new method uses top-5 RLAP-Cos values with penalties for small clusters


def calculate_inverse_variance_weighted_redshift_from_matches(
    cluster_matches: List[Dict[str, Any]]
) -> Tuple[float, float]:
    """
    Calculate inverse variance weighted redshift from cluster template matches.
    
    This extracts redshift and redshift_error from each match and applies
    pure inverse variance weighting (1/sigma^2).
    
    Parameters
    ----------
    cluster_matches : List[Dict]
        List of template match dictionaries containing 'redshift' and 'redshift_error'
        
    Returns
    -------
    Tuple[float, float]
        (weighted_redshift, uncertainty_on_weighted_mean)
    """
    if not cluster_matches:
        return np.nan, np.nan
    
    # Extract redshifts and errors from matches
    redshifts = []
    redshift_errors = []
    
    for match in cluster_matches:
        if 'redshift' in match and 'redshift_error' in match:
            redshifts.append(match['redshift'])
            redshift_errors.append(match['redshift_error'])
    
    if not redshifts:
        _LOGGER.warning("No valid redshift/error pairs found in cluster matches")
        return np.nan, np.nan
    
    # Use the hybrid weighted redshift with cluster scatter
    from snid_sage.shared.utils.math_utils import calculate_hybrid_weighted_redshift
    z_final, z_final_err, cluster_scatter = calculate_hybrid_weighted_redshift(
        redshifts=np.array(redshifts),
        redshift_errors=np.array(redshift_errors),
        include_cluster_scatter=True
    )
    return z_final, z_final_err


def perform_direct_gmm_clustering(
    matches: List[Dict[str, Any]], 
    min_matches_per_type: int = 2,
    quality_threshold: float = 0.02,  # Direct redshift threshold
    max_clusters_per_type: int = 10,
    top_percentage: float = 0.10,
    verbose: bool = False,
    use_rlap_cos: bool = True  # NEW: Use RLAP-Cos instead of RLAP
) -> Dict[str, Any]:
    """
    Direct GMM clustering on redshift values with top 10% RLAP/RLAP-Cos selection.
    
    This approach works directly on redshift values without any transformations,
    matching the approach in transformation_comparison_test.py exactly.
    
    NEW: Now supports RLAP-Cos metric (RLAP * capped_cosine_similarity) for
    improved template discrimination in GMM clustering.
    
    Parameters
    ----------
    matches : List[Dict[str, Any]]
        List of template matches from SNID analysis
    min_matches_per_type : int, optional
        Minimum number of matches required per type for clustering
    quality_threshold : float, optional
        Redshift span threshold for cluster quality assessment
    max_clusters_per_type : int, optional
        Maximum clusters for GMM
    top_percentage : float, optional
        Percentage of top matches to consider (0.10 = top 10%)
    verbose : bool, optional
        Enable detailed logging
    use_rlap_cos : bool, optional
        Use RLAP-Cos metric instead of RLAP for clustering (default: True)
        
    Returns
    -------
    Dict containing clustering results
    """
    
    start_time = time.time()
    
    # Determine which metric to use
    metric_name = "RLAP-Cos" if use_rlap_cos else "RLAP"
    metric_key = "rlap_cos" if use_rlap_cos else "rlap"
    
    _LOGGER.info(f"🔄 Starting direct GMM top-{top_percentage*100:.0f}% {metric_name} clustering")
    _LOGGER.info(f"📐 Quality threshold: {quality_threshold:.3f} in redshift space")
    
    # Group matches by type
    type_groups = {}
    for match in matches:
        sn_type = match['template'].get('type', 'Unknown')
        if sn_type not in type_groups:
            type_groups[sn_type] = []
        type_groups[sn_type].append(match)
    
    # Filter types with insufficient matches
    filtered_type_groups = {
        sn_type: type_matches 
        for sn_type, type_matches in type_groups.items() 
        if len(type_matches) >= min_matches_per_type
    }
    
    if not filtered_type_groups:
        _LOGGER.warning("No types have sufficient matches for clustering")
        return {'success': False, 'reason': 'insufficient_matches'}
    
    _LOGGER.info(f"📊 Processing {len(filtered_type_groups)} types: {list(filtered_type_groups.keys())}")
    
    # Perform GMM clustering for each type
    all_cluster_candidates = []
    clustering_results = {}
    
    for sn_type, type_matches in filtered_type_groups.items():
        type_result = _perform_direct_gmm_clustering(
            type_matches, sn_type, max_clusters_per_type, 
            quality_threshold, verbose, metric_key
        )
        
        clustering_results[sn_type] = type_result
        
        if type_result['success']:
            # For each cluster, use the EXACT same winning cluster selection as reference
            type_redshifts = np.array([m['redshift'] for m in type_matches])
            type_metric_values = np.array([m.get(metric_key, m.get('rlap', 0)) for m in type_matches])
            
            # Get cluster labels for this type
            features = type_redshifts.reshape(-1, 1)
            labels = type_result['gmm_model'].predict(features)
            
            # Note: winning_cluster_id is now determined by the new top-5 method at the end
            # We don't need this old selection here anymore
            
            # Create cluster candidates using the exact reference approach
            for cluster_id in range(type_result['optimal_n_clusters']):
                cluster_info = next((c for c in type_result['clusters'] if c['id'] == cluster_id), None)
                if cluster_info is None:
                    continue
                
                # Calculate mean metric value for this cluster
                cluster_metric_values = [match.get(metric_key, match.get('rlap', 0)) for match in cluster_info['matches']]
                mean_metric = np.mean(cluster_metric_values) if cluster_metric_values else 0.0
                
                cluster_candidate = {
                    'type': sn_type,
                    'cluster_id': cluster_info['id'],
                    'matches': cluster_info['matches'],
                    'size': cluster_info['size'],
                    'mean_rlap': cluster_info['mean_rlap'],  # Keep original RLAP for compatibility
                    'mean_metric': mean_metric,  # NEW: Mean of selected metric (RLAP or RLAP-Cos)
                    'metric_name': metric_name,  # NEW: Name of metric used
                    'enhanced_redshift': cluster_info.get('weighted_mean_redshift', 0),
                    'weighted_redshift_uncertainty': cluster_info.get('weighted_redshift_uncertainty', 0.01),
                    'redshift_span': cluster_info['redshift_span'],
                    'redshift_quality': cluster_info['redshift_quality'],
                    'cluster_method': 'direct_gmm',
                    'quality_score': 0, # This will be updated by the new method
                    'composite_score': 0, # This will be updated by the new method
                    'is_winning_cluster': False  # Will be determined by new method
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
                        
                        # Add subtype information to cluster candidate
                        cluster_candidate.update({
                            'subtype_info': {
                                'best_subtype': best_subtype,
                                'subtype_confidence': subtype_confidence,
                                'subtype_margin_over_second': subtype_margin_over_second,
                                'second_best_subtype': second_best_subtype
                            }
                        })
                        
                        if verbose:
                            _LOGGER.info(f"  Cluster {cluster_id} subtypes: {best_subtype} "
                                        f"(confidence: {subtype_confidence:.3f}, margin: {subtype_margin_over_second:.3f}, second: {second_best_subtype})")
                except Exception as e:
                    # If subtype calculation fails, add default values
                    cluster_candidate.update({
                        'subtype_info': {
                            'best_subtype': 'Unknown',
                            'subtype_confidence': 0.0,
                            'subtype_margin_over_second': 0.0,
                            'second_best_subtype': None
                        }
                    })
                    if verbose:
                        _LOGGER.warning(f"  Failed to calculate subtypes for cluster {cluster_id}: {e}")
                
                all_cluster_candidates.append(cluster_candidate)
    
    # Select best cluster using the new top-5 RLAP-Cos method
    if not all_cluster_candidates:
        _LOGGER.warning("No valid clusters found")
        return {'success': False, 'reason': 'no_clusters'}
    
    # Use the new top-5 method for cluster selection
    best_cluster, quality_assessment = find_winning_cluster_top5_method(
        all_cluster_candidates, 
        use_rlap_cos=use_rlap_cos, 
        verbose=verbose
    )
    
    if best_cluster is None:
        _LOGGER.warning("New cluster selection method failed")
        return {'success': False, 'reason': 'cluster_selection_failed'}
    
    # Update the best cluster with new quality metrics
    best_cluster['quality_assessment'] = quality_assessment['quality_assessment']
    best_cluster['confidence_assessment'] = quality_assessment['confidence_assessment']
    best_cluster['selection_method'] = 'top5_rlap_cos'
    
    total_time = time.time() - start_time
    
    if verbose:
        _LOGGER.info("🏆 All cluster candidates (before new selection method):")
        for i, candidate in enumerate(all_cluster_candidates[:5]):
            _LOGGER.info(f"   {i+1}. {candidate['type']} cluster {candidate['cluster_id']}: "
                        f"size={candidate['size']}, z-span={candidate['redshift_span']:.4f}, "
                        f"quality={candidate['redshift_quality']}")
    
    _LOGGER.info(f"✅ Direct GMM clustering completed in {total_time:.3f}s")
    _LOGGER.info(f"Best cluster: {best_cluster['type']} cluster {best_cluster.get('cluster_id', 0)} "
                 f"(Quality: {best_cluster['quality_assessment']['quality_category']}, "
                 f"Confidence: {best_cluster['confidence_assessment']['confidence_level']})")
    
    return {
        'success': True,
        'method': 'direct_gmm',
        'metric_used': metric_name,  # NEW: Which metric was used
        'use_rlap_cos': use_rlap_cos,  # NEW: Flag for metric selection
        'selection_method': 'top5_rlap_cos',  # NEW: Selection method used
        'type_clustering_results': clustering_results,
        'best_cluster': best_cluster,
        'all_candidates': all_cluster_candidates,
        'quality_assessment': quality_assessment,  # NEW: Complete quality assessment
        'quality_threshold': quality_threshold,
        'total_computation_time': total_time,
        'n_types_clustered': len(clustering_results),
        'total_candidates': len(all_cluster_candidates)
    }


def _perform_direct_gmm_clustering(
    type_matches: List[Dict[str, Any]], 
    sn_type: str,
    max_clusters: int,
    quality_threshold: float,
    verbose: bool,
    metric_key: str = 'rlap_cos'  # NEW: Which metric to use for calculations
) -> Dict[str, Any]:
    """
    Perform GMM clustering directly on redshift values using the same approach
    as transformation_comparison_test.py.
    """
    
    try:
        redshifts = np.array([m['redshift'] for m in type_matches])
        rlaps = np.array([m['rlap'] for m in type_matches])  # Keep for compatibility
        metric_values = np.array([m.get(metric_key, m.get('rlap', 0)) for m in type_matches])  # NEW: Selected metric
        
        # Suppress sklearn convergence warnings for cleaner output
        import warnings
        from sklearn.exceptions import ConvergenceWarning
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        
        # Step 1: Find optimal number of clusters using BIC
        n_matches = len(type_matches)
        max_clusters_actual = min(max_clusters, n_matches // 2 + 1)
        
        if max_clusters_actual < 2:
            # Too few matches for clustering
            return _create_single_cluster_result(
                type_matches, sn_type, redshifts, rlaps, quality_threshold, metric_key
            )
        
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
            gmm.fit(features)
            
            bic = gmm.bic(features)
            bic_scores.append(bic)
            models.append(gmm)
        
        # Select optimal model (minimum BIC)
        optimal_idx = np.argmin(bic_scores)
        optimal_n_clusters = optimal_idx + 1
        best_gmm = models[optimal_idx]
        
        # Get cluster assignments
        features = redshifts.reshape(-1, 1)
        labels = best_gmm.predict(features)
        
        # Create cluster info
        final_clusters = []
        for cluster_id in range(optimal_n_clusters):
            cluster_mask = (labels == cluster_id)
            cluster_indices = np.where(cluster_mask)[0]
            
            if len(cluster_indices) < 1:
                continue
            
            cluster_redshifts = redshifts[cluster_mask]
            cluster_rlaps = rlaps[cluster_mask]  # Keep for compatibility
            cluster_metric_values = metric_values[cluster_mask]  # NEW: Selected metric values
            cluster_matches = [type_matches[i] for i in cluster_indices]
            
            # Calculate redshift span
            redshift_span = np.max(cluster_redshifts) - np.min(cluster_redshifts)
            
            # Classify quality based on redshift span
            if redshift_span <= quality_threshold:
                redshift_quality = 'tight'
            elif redshift_span <= quality_threshold * 2:
                redshift_quality = 'moderate'  
            elif redshift_span <= quality_threshold * 4:
                redshift_quality = 'loose'
            else:
                redshift_quality = 'very_loose'
              
            # Calculate enhanced redshift statistics (statistically optimal)
            weighted_mean_redshift, weighted_redshift_uncertainty = calculate_inverse_variance_weighted_redshift_from_matches(
                cluster_matches
            )
            
            cluster_info = {
                'id': cluster_id,
                'matches': cluster_matches,
                'size': len(cluster_matches),
                'mean_rlap': np.mean(cluster_rlaps),
                'std_rlap': np.std(cluster_rlaps) if len(cluster_rlaps) > 1 else 0.0,
                'mean_metric': np.mean(cluster_metric_values),  # NEW: Mean of selected metric
                'std_metric': np.std(cluster_metric_values) if len(cluster_metric_values) > 1 else 0.0,  # NEW
                'metric_key': metric_key,  # NEW: Which metric was used
                # Enhanced redshift statistics
                'weighted_mean_redshift': weighted_mean_redshift,
                'weighted_redshift_uncertainty': weighted_redshift_uncertainty,
                'redshift_span': redshift_span,
                'redshift_quality': redshift_quality,
                'cluster_method': 'direct_gmm',
                'rlap_range': (np.min(cluster_rlaps), np.max(cluster_rlaps)),
                'metric_range': (np.min(cluster_metric_values), np.max(cluster_metric_values)),  # NEW
                'redshift_range': (np.min(cluster_redshifts), np.max(cluster_redshifts)),
                'top_5_values': [],
                'top_5_mean': 0.0,
                'penalty_factor': 1.0,
                'penalized_score': 0.0,
                'composite_score': 0.0
            }
            final_clusters.append(cluster_info)
            
            if verbose:
                _LOGGER.info(f"  Cluster {cluster_id}: {redshift_quality} "
                            f"(z-span={redshift_span:.4f})")
        
        # Get GMM responsibilities for subtype determination
        gamma = best_gmm.predict_proba(features)
        
        return {
            'success': True,
            'type': sn_type,
            'optimal_n_clusters': optimal_n_clusters,
            'final_n_clusters': len(final_clusters),
            'bic_scores': bic_scores,
            'clusters': final_clusters,
            'gmm_model': best_gmm,
            'gamma': gamma,
            'quality_threshold': quality_threshold
        }
                
    except Exception as e:
        _LOGGER.error(f"Direct GMM clustering failed for type {sn_type}: {e}")
        return {'success': False, 'type': sn_type, 'error': str(e)}


def _create_single_cluster_result(
    type_matches: List[Dict[str, Any]], 
    sn_type: str, 
    redshifts: np.ndarray, 
    rlaps: np.ndarray,
    quality_threshold: float,
    metric_key: str = 'rlap_cos'  # NEW: Which metric to use
) -> Dict[str, Any]:
    """Create a single cluster result when clustering isn't possible/needed."""
    
    redshift_span = np.max(redshifts) - np.min(redshifts) if len(redshifts) > 1 else 0.0
    
    # Get metric values
    metric_values = np.array([m.get(metric_key, m.get('rlap', 0)) for m in type_matches])
    
    # Quality based on redshift span
    if redshift_span <= quality_threshold:
        redshift_quality = 'tight'
    elif redshift_span <= quality_threshold * 2:
        redshift_quality = 'moderate'
    else:
        redshift_quality = 'loose'
    
                # Calculate enhanced redshift statistics (statistically optimal)
    weighted_mean_redshift, weighted_redshift_uncertainty = calculate_inverse_variance_weighted_redshift_from_matches(
        type_matches
    )
    
    cluster_info = {
        'id': 0,
        'matches': type_matches,
        'size': len(type_matches),
        'mean_rlap': np.mean(rlaps),
        'std_rlap': np.std(rlaps) if len(rlaps) > 1 else 0.0,
        'mean_metric': np.mean(metric_values),  # NEW: Mean of selected metric
        'std_metric': np.std(metric_values) if len(metric_values) > 1 else 0.0,  # NEW
        'metric_key': metric_key,  # NEW: Which metric was used
                    # Enhanced redshift statistics
        'weighted_mean_redshift': weighted_mean_redshift,
        'weighted_redshift_uncertainty': weighted_redshift_uncertainty,
        'redshift_span': redshift_span,
        'redshift_quality': redshift_quality,
        'cluster_method': 'single_cluster',
        'rlap_range': (np.min(rlaps), np.max(rlaps)),
        'metric_range': (np.min(metric_values), np.max(metric_values)),  # NEW
        'redshift_range': (np.min(redshifts), np.max(redshifts)),
        'top_5_values': [],
        'top_5_mean': 0.0,
        'penalty_factor': 1.0,
        'penalized_score': 0.0,
        'composite_score': 0.0
    }
    
    return {
        'success': True,
        'type': sn_type,
        'optimal_n_clusters': 1,
        'final_n_clusters': 1,
        'clusters': [cluster_info],
        'quality_threshold': quality_threshold
    }


def choose_subtype_weighted_voting(
    winning_type: str, 
    k_star: int, 
    matches: List[Dict[str, Any]], 
    gamma: np.ndarray, 
    resp_cut: float = 0.1
) -> tuple:
    """
    Choose the best subtype within the winning cluster using top-5 RLAP-Cos method.
    
    Args:
        winning_type: The winning type (e.g., "Ia")
        k_star: Index of the winning cluster within that type
        matches: List of template matches for the winning type
        gamma: GMM responsibilities matrix, shape (n_matches, n_clusters)
        resp_cut: Minimum responsibility threshold
    
    Returns:
        tuple: (best_subtype, confidence, margin_over_second, second_best_subtype)
    """
    
    # Collect cluster members
    cluster_members = []
    for i, match in enumerate(matches):
        if gamma[i, k_star] >= resp_cut:
            subtype = match['template'].get('subtype', 'Unknown')
            if not subtype or subtype.strip() == '':
                subtype = 'Unknown'
            
            # Use RLAP-Cos if available, otherwise RLAP
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            metric_value = get_best_metric_value(match)
            
            cluster_members.append({
                'subtype': subtype,
                'metric_value': metric_value,
                'cluster_membership': gamma[i, k_star]
            })
    
    if not cluster_members:
        return "Unknown", 0.0, 0.0, None
    
    # Group by subtype and calculate top-5 mean RLAP-Cos for each
    subtype_groups = defaultdict(list)
    for member in cluster_members:
        subtype_groups[member['subtype']].append(member)
    
    # Calculate top-5 mean for each subtype
    subtype_scores = {}
    for subtype, members in subtype_groups.items():
        # Sort by metric value (RLAP-Cos) descending
        sorted_members = sorted(members, key=lambda x: x['metric_value'], reverse=True)
        
        # Take top 5 (or all if less than 5)
        top_members = sorted_members[:5]
        top_values = [m['metric_value'] for m in top_members]
        
        # Calculate mean of top values
        mean_top = sum(top_values) / len(top_values)
        
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
    
    # Convert score to confidence (0-1 range)
    total_score = sum(subtype_scores.values())
    confidence = best_score / total_score if total_score > 0 else 0.0
    
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
    """Prepare data for 3D visualization: redshift vs type vs RLAP/RLAP-Cos."""
    
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
                # Use best available metric (RLAP-Cos if available, otherwise RLAP)
                from snid_sage.shared.utils.math_utils import get_best_metric_value
                metric_values.append(get_best_metric_value(match))
                types.append(sn_type)
                type_indices.append(type_index)
                cluster_ids.append(cluster_id)
                matches.append(match)
    
    else:
        # Fallback: old structure with type_clustering_results
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
                    # Use best available metric (RLAP-Cos if available, otherwise RLAP)
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    metric_values.append(get_best_metric_value(match))
                    types.append(sn_type)
                    type_indices.append(type_index)
                    cluster_ids.append(cluster['id'])
                    matches.append(match)
    
    return {
        'redshifts': np.array(redshifts),
        'rlaps': np.array(metric_values),  # Keep key name for backward compatibility
        'types': types,
        'type_indices': np.array(type_indices),
        'cluster_ids': np.array(cluster_ids),
        'type_mapping': type_to_index,
        'matches': matches  # NEW: Include matches for access to best metric values
    }


def demo_direct_gmm_clustering():
    """
    Demonstrate the direct GMM clustering approach.
    """
    print("🔬 DIRECT GMM CLUSTERING DEMO")
    print("=" * 60)
    
    # Create realistic synthetic SNID data
    np.random.seed(42)
    
    print("📊 GENERATING SYNTHETIC SNID DATA:")
    print("   • Low-z cluster: SN Ia-norm templates (z~0.02, high RLAP)")
    print("   • Medium-z cluster: SN Ia-91T templates (z~0.15, moderate RLAP)")
    print("   • High-z cluster: SN Ia-91bg templates (z~0.45, lower RLAP)")
    
    # Simulate realistic SNID template matches
    synthetic_matches = []
    
    # Low-z cluster: SN Ia-norm templates with high RLAP
    for i in range(25):
        z = np.random.normal(0.02, 0.003)
        rlap = np.random.normal(8.5, 0.8)
        synthetic_matches.append({
            'redshift': max(z, 0.001),
            'rlap': max(rlap, 4.0),
            'template': {'type': 'Ia', 'subtype': 'norm'}
        })
    
    # Medium-z cluster: SN Ia-91T templates with moderate RLAP  
    for i in range(30):
        z = np.random.normal(0.15, 0.008)
        rlap = np.random.normal(7.2, 1.0)
        synthetic_matches.append({
            'redshift': z,
            'rlap': max(rlap, 3.0),
            'template': {'type': 'Ia', 'subtype': '91T'}
        })
    
    # High-z cluster: SN Ia-91bg templates with lower RLAP
    for i in range(35):
        z = np.random.normal(0.45, 0.015)
        rlap = np.random.normal(6.0, 1.2)
        synthetic_matches.append({
            'redshift': z,
            'rlap': max(rlap, 2.0),
            'template': {'type': 'Ia', 'subtype': '91bg'}
        })
    
    print(f"\n✅ Generated {len(synthetic_matches)} synthetic template matches")
    
    # Run direct GMM clustering
    print("\n🔄 RUNNING DIRECT GMM CLUSTERING...")
    clustering_result = perform_direct_gmm_clustering(
        synthetic_matches,
        verbose=True
    )
    
    if clustering_result['success']:
        print(f"\n🎯 CLUSTERING RESULTS:")
        print(f"   • Method: {clustering_result['method']}")
        print(f"   • Best cluster: {clustering_result['best_cluster']['type']}")
        print(f"   • Top-5 mean score: {clustering_result['best_cluster'].get('top_5_mean', 0):.2f}")
        print(f"   • Cluster size: {clustering_result['best_cluster']['size']}")
        print(f"   • Redshift span: {clustering_result['best_cluster']['redshift_span']:.4f}")
        print(f"   • Quality: {clustering_result['best_cluster']['redshift_quality']}")
        
        # Show all candidates
        print(f"\n📋 ALL CLUSTER CANDIDATES:")
        for i, candidate in enumerate(clustering_result['all_candidates']):
            print(f"   {i+1}. {candidate['type']} cluster {candidate['cluster_id']}: "
                  f"top-5 mean={candidate.get('top_5_mean', 0):.2f}, "
                  f"size={candidate['size']}, "
                  f"z-span={candidate['redshift_span']:.4f}")
    else:
        print(f"❌ Clustering failed: {clustering_result.get('reason', 'unknown')}")
    
    print(f"\n💡 KEY ADVANTAGES OF DIRECT GMM:")
    print("   • ✅ Simple and straightforward - no transformations needed")
    print("   • ✅ GMM naturally handles different redshift scales")
    print("   • ✅ BIC-based model selection finds optimal cluster count")
    print("   • ✅ Top-5 RLAP-Cos method ensures quality-based clustering")
    print("   • ✅ Weighted voting for robust subtype determination")
    print("   • ✅ Statistical confidence assessment")
    print("   • ✅ Matches transformation_comparison_test.py approach exactly")


def find_winning_cluster_top5_method(
    all_cluster_candidates: List[Dict[str, Any]], 
    use_rlap_cos: bool = True,
    verbose: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Find the winning cluster using the new top-5 RLAP-Cos method.
    
    This method:
    1. Takes the top 5 RLAP-Cos values from each cluster
    2. Calculates the mean of these top 5 values
    3. Penalizes clusters with fewer than 5 points
    4. Selects the cluster with the highest mean
    5. Provides confidence assessment vs other clusters
    6. Provides absolute quality assessment (Low/Mid/High)
    
    Parameters
    ----------
    all_cluster_candidates : List[Dict[str, Any]]
        List of all cluster candidates from GMM clustering
    use_rlap_cos : bool, optional
        Use RLAP-Cos metric instead of RLAP (default: True)
    verbose : bool, optional
        Enable detailed logging
        
    Returns
    -------
    Tuple[Dict[str, Any], Dict[str, Any]]
        (winning_cluster, quality_assessment)
    """
    if not all_cluster_candidates:
        return None, {'error': 'No cluster candidates available'}
    
    metric_key = 'rlap_cos' if use_rlap_cos else 'rlap'
    metric_name = 'RLAP-Cos' if use_rlap_cos else 'RLAP'
    
    # Calculate top-5 means for each cluster
    cluster_scores = []
    
    for cluster in all_cluster_candidates:
        matches = cluster.get('matches', [])
        if not matches:
            continue
            
        # Extract metric values and sort in descending order
        metric_values = []
        for match in matches:
            value = match.get(metric_key, match.get('rlap', 0))
            metric_values.append(value)
        
        metric_values.sort(reverse=True)  # Highest first
        
        # Take top 5 (or all if fewer than 5)
        top_5_values = metric_values[:5]
        
        # Calculate mean of top 5
        if top_5_values:
            top_5_mean = np.mean(top_5_values)
        else:
            top_5_mean = 0.0
        
        # Apply penalty for clusters with fewer than 5 points
        penalty_factor = 1.0
        if len(metric_values) < 5:
            # Penalty: reduce score by 5% for each missing match (so clusters with <5 still participate)
            penalty_factor = 0.95 ** (5 - len(metric_values))
            
        penalized_score = top_5_mean * penalty_factor  # No hard quality threshold – keep ALL clusters
        
        # Annotate the original cluster dictionary so downstream UIs can display these metrics
        cluster['top_5_values'] = top_5_values
        cluster['top_5_mean'] = top_5_mean
        cluster['penalty_factor'] = penalty_factor
        cluster['penalized_score'] = penalized_score
        # For convenience update composite_score field used in various summaries
        cluster['composite_score'] = penalized_score
        
        cluster_info = {
            'cluster': cluster,
            'cluster_size': len(matches),
            'top_5_values': top_5_values,
            'top_5_mean': top_5_mean,
            'penalty_factor': penalty_factor,
            'penalized_score': penalized_score,
            'cluster_type': cluster.get('type', 'Unknown'),
            'cluster_id': cluster.get('cluster_id', 0)
        }
        
        cluster_scores.append(cluster_info)
    
    if not cluster_scores:
        return None, {'error': 'No valid clusters found'}
    
    # Sort by penalized score (highest first)
    cluster_scores.sort(key=lambda x: x['penalized_score'], reverse=True)
    
    # Winner is the cluster with highest penalized score
    winning_cluster_info = cluster_scores[0]
    winning_cluster = winning_cluster_info['cluster']
    
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
        'selection_method': 'top5_rlap_cos'
    }
    
    if verbose:
        _log_cluster_selection_details(full_assessment)
    
    return winning_cluster, full_assessment


def _calculate_cluster_confidence(cluster_scores: List[Dict[str, Any]], metric_name: str) -> Dict[str, Any]:
    """Calculate confidence in cluster selection vs alternatives."""
    if len(cluster_scores) < 2:
        return {
            'confidence_level': 'high',
            'confidence_description': 'Only one cluster available',
            'margin_vs_second': float('inf'),
            'statistical_significance': 'N/A'
        }
    
    best_score = cluster_scores[0]['penalized_score']
    second_best_score = cluster_scores[1]['penalized_score']
    
    # Calculate margin
    margin = best_score - second_best_score
    relative_margin = margin / second_best_score if second_best_score > 0 else float('inf')
    
    # Determine confidence level based on margin
    if relative_margin >= 0.3:  # 30% better than second best
        confidence_level = 'high'
        confidence_description = f'Winning cluster is {relative_margin*100:.1f}% better than second best'
    elif relative_margin >= 0.15:  # 15% better
        confidence_level = 'medium'
        confidence_description = f'Winning cluster is {relative_margin*100:.1f}% better than second best'
    elif relative_margin >= 0.05:  # 5% better
        confidence_level = 'low'
        confidence_description = f'Winning cluster is {relative_margin*100:.1f}% better than second best'
    else:
        confidence_level = 'very_low'
        confidence_description = f'Winning cluster is only {relative_margin*100:.1f}% better than second best'
    
    # Simple t-test approximation for statistical significance
    # This is a simplified approach - in practice you'd want more sophisticated statistics
    if len(cluster_scores) >= 2:
        best_values = cluster_scores[0]['top_5_values']
        second_values = cluster_scores[1]['top_5_values']
        
        if len(best_values) >= 2 and len(second_values) >= 2:
            # Perform simple t-test
            try:
                t_stat, p_value = stats.ttest_ind(best_values, second_values)
                if p_value < 0.01:
                    statistical_significance = 'highly_significant'
                elif p_value < 0.05:
                    statistical_significance = 'significant'
                elif p_value < 0.1:
                    statistical_significance = 'marginally_significant'
                else:
                    statistical_significance = 'not_significant'
            except:
                statistical_significance = 'unknown'
        else:
            statistical_significance = 'insufficient_data'
    else:
        statistical_significance = 'N/A'
    
    return {
        'confidence_level': confidence_level,
        'confidence_description': confidence_description,
        'margin_vs_second': margin,
        'relative_margin': relative_margin,
        'statistical_significance': statistical_significance,
        'second_best_type': cluster_scores[1]['cluster_type'] if len(cluster_scores) > 1 else 'N/A'
    }


def _calculate_absolute_quality(winning_cluster_info: Dict[str, Any], metric_name: str) -> Dict[str, Any]:
    """Calculate absolute quality assessment for the winning cluster using penalized top-5 score."""
    
    # Use the already calculated penalized score from the winning cluster
    penalized_score = winning_cluster_info['penalized_score']
    top_5_mean = winning_cluster_info['top_5_mean']
    penalty_factor = winning_cluster_info['penalty_factor']
    cluster_size = winning_cluster_info['cluster_size']
    
    # Quality categories based on penalized top-5 mean
    if penalized_score >= 10.0:
        quality_category = 'high'
        quality_description = f'Excellent match quality (penalized top-5 {metric_name}: {penalized_score:.1f})'
    elif penalized_score >= 5.0:
        quality_category = 'medium'
        quality_description = f'Good match quality (penalized top-5 {metric_name}: {penalized_score:.1f})'
    else:
        quality_category = 'low'
        quality_description = f'Poor match quality (penalized top-5 {metric_name}: {penalized_score:.1f})'
    
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
    
    _LOGGER.info(f"🔍 CONFIDENCE ASSESSMENT:")
    _LOGGER.info(f"   Confidence level: {confidence['confidence_level'].upper()}")
    _LOGGER.info(f"   {confidence['confidence_description']}")
    _LOGGER.info(f"   Statistical significance: {confidence['statistical_significance']}")
    
    _LOGGER.info(f"📊 QUALITY ASSESSMENT:")
    _LOGGER.info(f"   Quality category: {quality['quality_category']}")
    _LOGGER.info(f"   {quality['quality_description']}")
    
    # Show top 3 clusters
    _LOGGER.info(f"🏅 TOP 3 CLUSTERS:")
    for i, cluster_info in enumerate(assessment['all_cluster_scores'][:3], 1):
        disqualified = " [DISQUALIFIED: below quality threshold]" if cluster_info['penalized_score'] == 0.0 and cluster_info['top_5_mean'] > 0 else ""
        _LOGGER.info(f"   {i}. {cluster_info['cluster_type']} (score: {cluster_info['penalized_score']:.3f}, "
                    f"size: {cluster_info['cluster_size']}, "
                    f"top-5 mean: {cluster_info['top_5_mean']:.3f}){disqualified}")


if __name__ == "__main__":
    # Run demonstration
    demo_direct_gmm_clustering()