"""
Similarity and composite metric utilities for SNID SAGE.

The primary metric used is the concordance correlation coefficient (CCC),
which is combined with RLAP to form the RLAP-CCC composite metric for improved
template discrimination. CCC/RLAP-CCC is preferred when available.
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# Default alpha for rational soft-clip used in CCC-based RLAP-CCC metric
DEFAULT_CCC_SOFTCLIP_ALPHA: float = 3.0


def _rational_softclip_transform(x: np.ndarray, alpha: float = DEFAULT_CCC_SOFTCLIP_ALPHA) -> np.ndarray:
    """
    Apply a rational soft-clip directly to a (possibly zero‑centred) spectrum.

    y = x / (1 + alpha * |x|)

    - Linear near 0
    - Soft saturation to ±(1/alpha) for large |x|
    """
    arr = np.asarray(x, dtype=float)
    if alpha is None or alpha <= 0:
        return arr
    return arr / (1.0 + float(alpha) * np.abs(arr))


def _common_checks(spec1: np.ndarray, spec2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Ensure equal length, finite values, exclude near-zeros in BOTH arrays, and L2-normalise."""
    s1 = np.asarray(spec1, dtype=float)
    s2 = np.asarray(spec2, dtype=float)
    n = min(len(s1), len(s2))
    if n == 0:
        return np.array([]), np.array([])
    s1, s2 = s1[:n], s2[:n]
    # Joint mask: finite in both and above tolerance in both (avoid biasing toward one array)
    tol = 1e-12
    finite_mask = np.isfinite(s1) & np.isfinite(s2)
    non_zero_both = (np.abs(s1) > tol) & (np.abs(s2) > tol)
    mask = finite_mask & non_zero_both
    if not np.any(mask):
        return np.array([]), np.array([])
    a = s1[mask].astype(float)
    b = s2[mask].astype(float)
    # L2 normalisation — avoids scale bias
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return np.array([]), np.array([])
    return a / a_norm, b / b_norm


# Cosine similarity removed - using CCC (Concordance Correlation Coefficient) exclusively


def concordance_correlation_coefficient(spec1: np.ndarray, spec2: np.ndarray) -> float:
    """
    Compute Lin's Concordance Correlation Coefficient (CCC).
    
    CCC = (2 * ρ * σx * σy) / (σx² + σy² + (μx - μy)²)
    
    Where:
    - ρ is the Pearson correlation between x and y
    - μx, μy are the means
    - σx², σy² are the variances
    
    Parameters
    ----------
    spec1, spec2 : np.ndarray
        Input spectra arrays
        
    Returns
    -------
    float
        CCC value in [-1, 1] where:
        - 1: Perfect agreement in both amplitude and shape
        - 0: No better than random
        - <0: Systematic disagreement
    """
    # Convert to arrays and find valid overlap
    a = np.asarray(spec1, dtype=float)
    b = np.asarray(spec2, dtype=float)
    n = min(len(a), len(b))
    if n < 2:  # Need at least 2 points for correlation
        return 0.0
    
    a = a[:n]
    b = b[:n]
    
    # Remove invalid values (non-finite)
    tol = 1e-12
    mask = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > tol) & (np.abs(b) > tol)
    if not np.any(mask):
        return 0.0
    
    a = a[mask]
    b = b[mask]
    
    if a.size < 2:
        return 0.0
    
    # Compute means
    mu_x = float(np.mean(a))
    mu_y = float(np.mean(b))
    
    # Compute variances
    var_x = float(np.var(a, ddof=1))  # Sample variance
    var_y = float(np.var(b, ddof=1))
    
    # Compute Pearson correlation
    # ρ = cov(x,y) / (σx * σy)
    # Use consistent ddof=1 for covariance calculation
    if a.size > 1:
        cov_xy = float(np.sum((a - mu_x) * (b - mu_y)) / (a.size - 1))
    else:
        cov_xy = 0.0
    std_x = float(np.sqrt(var_x))
    std_y = float(np.sqrt(var_y))
    
    if std_x == 0 or std_y == 0:
        return 0.0
    
    rho = cov_xy / (std_x * std_y)
    
    # Compute CCC
    numerator = 2.0 * rho * std_x * std_y
    denominator = var_x + var_y + (mu_x - mu_y) ** 2
    
    if denominator == 0:
        return 0.0
    
    ccc = numerator / denominator
    return float(np.clip(ccc, -1.0, 1.0))


def _extract_template_flux(match: Dict[str, Any]) -> np.ndarray:
    """Extract the best available template flux from a match dict."""
    tpl_flux: Optional[np.ndarray] = None
    
    # 1. Best: template flattened flux (continuum removed)
    if "spectra" in match:
        spectra_dict = match["spectra"]
        tpl_flux = np.asarray(
            spectra_dict.get("flat", {}).get("flux", []), dtype=float
        )
    
    # 2. Fallback: processed_flux already shifted & flattened in some SNID modes
    if (tpl_flux is None or tpl_flux.size == 0) and "processed_flux" in match:
        tpl_flux = np.asarray(match["processed_flux"], dtype=float)
    
    # 3. Last resort: raw template flux (may include continuum)
    if (tpl_flux is None or tpl_flux.size == 0) and "template" in match and isinstance(match["template"], dict):
        tpl_flux = np.asarray(match["template"].get("flux", []), dtype=float)
    
    if tpl_flux is None or tpl_flux.size == 0:
        return np.zeros(1)
    
    return tpl_flux


def compute_rlap_ccc_metric(
    matches: List[Dict[str, Any]], 
    processed_spectrum: Dict[str, Any],
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Compute RLAP-CCC metric (RLAP * capped_concordance_correlation_coefficient) for template matches.
    
    Uses the exact same spectrum preparation as snid_enhanced_metrics.py:
    - Prefers tapered_flux (apodized flattened spectrum) for consistency with SNID analysis
    - Trims to valid data range (left_edge:right_edge)
    - Template flux extraction follows the same priority order
    
    Parameters
    ----------
    matches : List[Dict[str, Any]]
        List of template matches from SNID analysis
    processed_spectrum : Dict[str, Any]
        Processed spectrum data from SNID preprocessing 
    verbose : bool, optional
        Enable detailed logging
        
    Returns
    -------
    List[Dict[str, Any]]
        Enhanced matches with ccc_similarity, ccc_similarity_capped, and rlap_ccc fields
    """
    if not matches:
        return matches
    
    # Check if RLAP-CCC is already computed for all matches
    already_computed = all('rlap_ccc' in match for match in matches)
    if already_computed:
        if verbose:
            logger.info(f"🔄 RLAP-CCC already computed for all {len(matches)} matches - skipping computation")
        return matches
    
    # Check if partially computed - count how many need computation
    needs_computation = [match for match in matches if 'rlap_ccc' not in match]
    if len(needs_computation) < len(matches):
        if verbose:
            logger.info(f"🔄 RLAP-CCC partially computed - computing for {len(needs_computation)}/{len(matches)} matches")
    else:
        logger.info(f"🔄 Computing RLAP-CCC metric for {len(matches)} matches")
    
    # ============================================================================
    
    # ============================================================================
    
    # 1a) Choose the best version of the flattened input flux
    
    # snid_sage.snid.py:1145
    if "tapered_flux" in processed_spectrum and processed_spectrum["tapered_flux"] is not None:
        base_flux = processed_spectrum["tapered_flux"]  # Apodized flattened spectrum (what SNID uses)
        if verbose:
            logger.info("Using tapered_flux (apodized flattened spectrum) for RLAP-CCC metrics")
    elif "display_flat" in processed_spectrum and processed_spectrum["display_flat"] is not None:
        base_flux = processed_spectrum["display_flat"]  # GUI's apodized version
        if verbose:
            logger.info("Using display_flat (GUI apodized flattened spectrum) for RLAP-CCC metrics")
    elif "flat_flux" in processed_spectrum and processed_spectrum["flat_flux"] is not None:
        base_flux = processed_spectrum["flat_flux"]  # Non-apodized flattened spectrum
        if verbose:
            logger.warning("Using flat_flux (non-apodized flattened spectrum) - may not match SNID analysis")
    else:
        # Fall back to tapered_flux (continuum-removed but not flattened)
        base_flux = processed_spectrum["tapered_flux"]
        if verbose:
            logger.warning("Using tapered_flux fallback (continuum-removed but not flattened)")
    
    if base_flux is None:
        logger.error("No suitable input flux found for RLAP-CCC computation")
        return matches
        
    base_flux = np.asarray(base_flux, dtype=float)
    
    # 1b) Always trim to the valid data range used in plotting – unless it is
    #     *already* trimmed (e.g., when display_flat is pre-cropped by GUI preprocessing).
    le_val = processed_spectrum.get("left_edge", 0)
    re_val = processed_spectrum.get("right_edge", None)
    if le_val is None:
        le_val = 0
    if re_val is None:
        re_val = len(base_flux) - 1
    left_edge = int(le_val)
    right_edge = int(re_val)
    expected_len = right_edge - left_edge + 1
    
    if len(base_flux) == expected_len:
        input_flux = base_flux  # already trimmed
    else:
        input_flux = base_flux[left_edge : right_edge + 1]
    
    if verbose:
        logger.info(f"Input spectrum: length={len(input_flux)}, range=[{left_edge}:{right_edge}]")
    
    # ============================================================================
    # Compute enhanced metrics for each match
    # ============================================================================
    
    enhanced_matches = []
    successful_computations = 0
    
    for i, match in enumerate(matches):
        # Skip if already computed
        if 'rlap_ccc' in match:
            enhanced_matches.append(match)
            successful_computations += 1
            continue
        
        # Extract template flux using the exact same logic as snid_enhanced_metrics.py
        tpl_flux = _extract_template_flux_exact(match)
        
        if tpl_flux is None or tpl_flux.size == 0:
            if verbose:
                logger.debug(f"Template flux missing for match {i} – skipping RLAP-CCC calculation")
            # Keep original match without enhancement
            enhanced_matches.append(match.copy())
            continue
        
        # Compute CCC (Concordance Correlation Coefficient) on rational
        # soft‑clipped spectra. Prefer the exact RLAP overlap window if
        # provided on the match.
        try:
            a = np.asarray(input_flux, dtype=float)
            b = np.asarray(tpl_flux, dtype=float)
            n = min(len(a), len(b))
            if n == 0:
                ccc_sim = 0.0
            else:
                a = a[:n]
                b = b[:n]

                # If match carries overlap indices relative to plotting range, use them
                start_idx = None
                end_idx = None
                try:
                    overlap_indices = match.get('overlap_indices') or {}
                    if isinstance(overlap_indices, dict):
                        start_idx = int(overlap_indices.get('start'))
                        end_idx = int(overlap_indices.get('end'))
                        # Inclusive end in SNID trimming -> convert to Python slice end (exclusive)
                        end_idx = end_idx + 1
                        # Validate bounds
                        if start_idx < 0 or end_idx <= start_idx or end_idx > n:
                            start_idx = None
                            end_idx = None
                except Exception:
                    start_idx = None
                    end_idx = None

                if start_idx is None or end_idx is None:
                    # Fallback: contiguous region where BOTH are non-zero/finite
                    tol = 1e-12
                    joint_mask = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > tol) & (np.abs(b) > tol)
                    if not np.any(joint_mask):
                        ccc_sim = 0.0
                    else:
                        idx = np.flatnonzero(joint_mask)
                        start_idx = int(idx[0])
                        end_idx = int(idx[-1]) + 1
                        a_window = a[start_idx:end_idx]
                        b_window = b[start_idx:end_idx]
                else:
                    a_window = a[start_idx:end_idx]
                    b_window = b[start_idx:end_idx]

                # Apply rational soft-clip before CCC
                if 'ccc_sim' not in locals() or (start_idx is not None and end_idx is not None):
                    a_t = _rational_softclip_transform(a_window, alpha=DEFAULT_CCC_SOFTCLIP_ALPHA)
                    b_t = _rational_softclip_transform(b_window, alpha=DEFAULT_CCC_SOFTCLIP_ALPHA)
                    ccc_sim = concordance_correlation_coefficient(a_t, b_t)
        except Exception:
            ccc_sim = 0.0
        
        # Cap CCC to [0, 1] (negative similarities are bad, as requested by user)
        ccc_sim_capped = max(0.0, ccc_sim)
        
        # Compute RLAP-CCC = RLAP * capped_ccc_similarity
        rlap = match.get('rlap', 0.0)
        rlap_ccc = rlap * ccc_sim_capped
        
        # Create enhanced match
        enhanced_match = match.copy()
        enhanced_match.update({
            'ccc_similarity': ccc_sim,
            'ccc_similarity_capped': ccc_sim_capped,
            'rlap_ccc': rlap_ccc
        })
        
        enhanced_matches.append(enhanced_match)
        successful_computations += 1
        
        if verbose and i < 5:  # Log first few for debugging
            template_name = match.get('template', {}).get('name', 'Unknown') if isinstance(match.get('template'), dict) else match.get('name', 'Unknown')
            logger.debug(f"  Match {i}: {template_name} - RLAP={rlap:.2f}, ccc_sim={ccc_sim:.3f}, capped={ccc_sim_capped:.3f}, RLAP-CCC={rlap_ccc:.3f}")
    
    if len(needs_computation) > 0:
        logger.info(f"✅ RLAP-CCC computation complete: {successful_computations}/{len(matches)} matches enhanced")
    
    return enhanced_matches


# Cosine-based metric removed - using CCC exclusively


def _extract_template_flux_exact(match: Dict[str, Any]) -> Optional[np.ndarray]:
    """
    Extract template flux using the exact same logic as snid_enhanced_metrics.py.
    
    Priority order:
    1. Best: template flattened flux (continuum removed) - spectra.flat.flux
    2. Fallback: processed_flux already shifted & flattened in some SNID modes  
    3. Last resort: raw template flux (may include continuum) - template.flux
    """
    tpl_flux: Optional[np.ndarray] = None
    
    # 1. Best: template flattened flux (continuum removed)
    if "spectra" in match:
        spectra_dict = match["spectra"]
        tpl_flux = np.asarray(
            spectra_dict.get("flat", {}).get("flux", []), dtype=float
        )
        if tpl_flux.size > 0:
            return tpl_flux
    
    # 2. Fallback: processed_flux already shifted & flattened in some SNID modes
    if "processed_flux" in match:
        tpl_flux = np.asarray(match["processed_flux"], dtype=float)
        if tpl_flux.size > 0:
            return tpl_flux
    
    # 3. Last resort: raw template flux (may include continuum)
    if "template" in match and isinstance(match["template"], dict):
        tpl_flux = np.asarray(match["template"].get("flux", []), dtype=float)
        if tpl_flux.size > 0:
            return tpl_flux
    
    return None


def get_best_metric_value(match: Dict[str, Any]) -> float:
    """
    Get the best available metric value for sorting/display.
    
    Returns RLAP-CCC if available, otherwise falls back to RLAP.
    This ensures consistent behavior across the codebase when enhanced metrics
    are available from the enhanced clustering.
    
    Parameters
    ----------
    match : Dict[str, Any]
        Template match dictionary
        
    Returns
    -------
    float
        Best available metric value
    """
    return match.get('rlap_ccc', match.get('rlap', 0.0))


def get_metric_name_for_match(match: Dict[str, Any]) -> str:
    """
    Get the name of the metric being used for a match.
    
    Returns 'RLAP-CCC' if available, otherwise 'RLAP'.
    
    Parameters
    ----------
    match : Dict[str, Any]
        Template match dictionary
        
    Returns
    -------
    str
        Name of the metric
    """
    if 'rlap_ccc' in match:
        return 'RLAP-CCC'
    else:
        return 'RLAP'


def get_best_metric_name(match: Dict[str, Any]) -> str:
    """
    Get the name of the best available metric for a match.
    
    Returns 'RLAP-CCC' if available, otherwise 'RLAP'.
    This is a convenience function for summary reports.
    
    Parameters
    ----------
    match : Dict[str, Any]
        Template match dictionary or summary dictionary
        
    Returns
    -------
    str
        Name of the best available metric
    """
    # Check if this is a summary dict with rlap_ccc or a match dict
    if 'rlap_ccc' in match or (isinstance(match, dict) and any('rlap_ccc' in str(k) for k in match.keys())):
        return 'RLAP-CCC'
    else:
        return 'RLAP'


def get_metric_display_values(match: Dict[str, Any]) -> Dict[str, float]:
    """
    Get all available metric values for display purposes.
    
    Returns a dictionary with all available metric values including
    original RLAP and RLAP-CCC when available.
    
    Parameters
    ----------
    match : Dict[str, Any]
        Template match dictionary
        
    Returns
    -------
    Dict[str, float]
        Dictionary containing available metric values
    """
    values = {
        'rlap': match.get('rlap', 0.0),
        'primary_metric': get_best_metric_value(match),
        'metric_name': get_metric_name_for_match(match)
    }
    
    if 'rlap_ccc' in match:
        values['rlap_ccc'] = match['rlap_ccc']
        values['ccc_similarity'] = match.get('ccc_similarity', 0.0)
        values['ccc_similarity_capped'] = match.get('ccc_similarity_capped', 0.0)
    
    return values 


# =============================================================================
# Locality-aware similarity metric
# =============================================================================

def _windowed_cosines(a: np.ndarray, b: np.ndarray, window: int, step: int) -> np.ndarray:
    """Compute cosine similarity over sliding windows.
    Arrays a and b should already be 1D, finite, and aligned to the same region.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n == 0 or window <= 1:
        return np.array([], dtype=float)
    window = int(max(2, min(window, n)))
    step = int(max(1, step))
    vals: list[float] = []
    for start in range(0, n - window + 1, step):
        aw = a[start:start + window]
        bw = b[start:start + window]
        # Normalise per-window to avoid scale bias
        aw, bw = _common_checks(aw, bw)
        if aw.size == 0:
            continue
        num = float(np.dot(aw, bw))
        den = float(np.linalg.norm(aw) * np.linalg.norm(bw))
        vals.append(0.0 if den == 0.0 else float(np.clip(num / den, -1.0, 1.0)))
    return np.asarray(vals, dtype=float)


def _compute_overlap_slice(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Trim to the contiguous joint non-zero/finite region (excludes zero-padded edges)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = min(len(a), len(b))
    if n == 0:
        return np.array([]), np.array([])
    a = a[:n]
    b = b[:n]
    tol = 1e-12
    joint_mask = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > tol) & (np.abs(b) > tol)
    if not np.any(joint_mask):
        return np.array([]), np.array([])
    idx = np.flatnonzero(joint_mask)
    start_idx = int(idx[0])
    end_idx = int(idx[-1]) + 1
    return a[start_idx:end_idx], b[start_idx:end_idx]


def _locality_similarity_from_series(
    a_series: np.ndarray,
    b_series: np.ndarray,
    *,
    window: int = 64,
    step: int = 32,
    q: float = 0.25,
    include_derivative: bool = True,
    include_roughness: bool = True,
) -> float:
    """Compute a locality-aware similarity in [0, 1] from aligned series.

    Components:
      - Windowed cosine aggregated as mean-quantile blend to punish local mismatches
      - Optional derivative-cosine factor to enforce local shape agreement
      - Optional roughness-ratio factor to penalize swingy vs smooth mismatches
    """
    # Trim to joint valid, contiguous overlap and normalise
    a_win, b_win = _compute_overlap_slice(a_series, b_series)
    if a_win.size == 0:
        return 0.0

    # Windowed cosine aggregation
    wcos = _windowed_cosines(a_win, b_win, window=window, step=step)
    if wcos.size == 0:
        agg = 0.0
    else:
        mean_val = float(np.mean(wcos))
        q = float(np.clip(q, 0.0, 1.0))
        qval = float(np.quantile(wcos, q))
        agg = 0.5 * (mean_val + qval)
    agg = max(0.0, min(1.0, agg))

    # Derivative cosine factor
    deriv_factor = 1.0
    if include_derivative and a_win.size >= 3:
        da = np.diff(a_win)
        db = np.diff(b_win)
        da, db = _common_checks(da, db)
        if da.size > 0:
            num = float(np.dot(da, db))
            den = float(np.linalg.norm(da) * np.linalg.norm(db))
            deriv = 0.0 if den == 0.0 else float(np.clip(num / den, -1.0, 1.0))
            deriv_factor = max(0.0, deriv)
        else:
            deriv_factor = 0.0

    # Roughness ratio (total variation consistency)
    rough_factor = 1.0
    if include_roughness and a_win.size >= 3:
        tva = float(np.sum(np.abs(np.diff(a_win))))
        tvb = float(np.sum(np.abs(np.diff(b_win))))
        if tva > 0.0 and tvb > 0.0:
            rough_factor = float(min(tva, tvb) / max(tva, tvb))
        else:
            rough_factor = 0.0

    sim = agg * deriv_factor * rough_factor
    return float(np.clip(sim, 0.0, 1.0))


def compute_locality_metric(
    matches: List[Dict[str, Any]],
    processed_spectrum: Dict[str, Any],
    *,
    window: int = 64,
    step: int = 32,
    q: float = 0.25,
    include_derivative: bool = True,
    include_roughness: bool = True,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Compute a locality-aware metric per match and attach fields:
      - 'locality_similarity' in [0,1]
      - 'rlap_local' = rlap * locality_similarity

    Uses the same flux extraction and overlap handling as RLAP-CCC to ensure
    the zero-padded template edges are excluded and only the real overlap is used.
    """
    if not matches:
        return matches

    # Choose base flattened spectrum like in compute_rlap_ccc_metric
    if "tapered_flux" in processed_spectrum and processed_spectrum["tapered_flux"] is not None:
        base_flux = processed_spectrum["tapered_flux"]
    elif "display_flat" in processed_spectrum and processed_spectrum["display_flat"] is not None:
        base_flux = processed_spectrum["display_flat"]
    elif "flat_flux" in processed_spectrum and processed_spectrum["flat_flux"] is not None:
        base_flux = processed_spectrum["flat_flux"]
    else:
        base_flux = processed_spectrum.get("tapered_flux")

    if base_flux is None:
        return matches

    base_flux = np.asarray(base_flux, dtype=float)
    le_val = processed_spectrum.get("left_edge", 0)
    re_val = processed_spectrum.get("right_edge", None)
    if le_val is None:
        le_val = 0
    if re_val is None:
        re_val = len(base_flux) - 1
    left_edge = int(le_val)
    right_edge = int(re_val)
    expected_len = right_edge - left_edge + 1
    if len(base_flux) == expected_len:
        input_flux = base_flux
    else:
        input_flux = base_flux[left_edge:right_edge + 1]

    enhanced: list[Dict[str, Any]] = []
    for i, match in enumerate(matches):
        tpl_flux = _extract_template_flux_exact(match)
        if tpl_flux is None or tpl_flux.size == 0:
            enhanced.append(match.copy())
            continue

        try:
            a = np.asarray(input_flux, dtype=float)
            b = np.asarray(tpl_flux, dtype=float)
            n = min(len(a), len(b))
            if n == 0:
                loc_sim = 0.0
            else:
                # Honour explicit overlap indices if present on match
                start_idx = None
                end_idx = None
                try:
                    overlap_indices = match.get('overlap_indices') or {}
                    if isinstance(overlap_indices, dict):
                        start_idx = int(overlap_indices.get('start'))
                        end_idx = int(overlap_indices.get('end')) + 1  # inclusive → exclusive
                        if start_idx < 0 or end_idx <= start_idx or end_idx > n:
                            start_idx = None
                            end_idx = None
                except Exception:
                    start_idx = None
                    end_idx = None

                if start_idx is None or end_idx is None:
                    a_win, b_win = _compute_overlap_slice(a[:n], b[:n])
                else:
                    a_win = a[start_idx:end_idx]
                    b_win = b[start_idx:end_idx]

                loc_sim = _locality_similarity_from_series(
                    a_win, b_win,
                    window=window,
                    step=step,
                    q=q,
                    include_derivative=include_derivative,
                    include_roughness=include_roughness,
                )
        except Exception:
            loc_sim = 0.0

        rlap = float(match.get('rlap', 0.0))
        rlap_local = rlap * max(0.0, min(1.0, float(loc_sim)))

        new_match = match.copy()
        new_match.update({
            'locality_similarity': float(loc_sim),
            'rlap_local': float(rlap_local),
        })
        enhanced.append(new_match)

        if verbose and i < 5:
            logger.debug(
                f"Match {i}: RLAP={rlap:.2f}, locality={loc_sim:.3f}, RLAP-Local={rlap_local:.3f}"
            )

    return enhanced


# =============================================================================
# Chi-square style metric over overlap
# =============================================================================

def _fit_scale_coefficient(observed: np.ndarray, template: np.ndarray, weights: Optional[np.ndarray] = None) -> float:
    """Least-squares scaling factor alpha to fit observed ≈ alpha * template.
    Supports optional weights (1/σ^2). Returns 0.0 if degenerate.
    """
    a = np.asarray(observed, dtype=float)
    b = np.asarray(template, dtype=float)
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    a = a[:n]
    b = b[:n]
    if weights is None:
        denom = float(np.dot(b, b))
        if denom <= 0.0:
            return 0.0
        return float(np.dot(b, a) / denom)
    else:
        w = np.asarray(weights, dtype=float)
        w = w[:n]
        # Guard against invalid weights
        w = np.where(np.isfinite(w) & (w > 0), w, 0.0)
        if not np.any(w > 0):
            return 0.0
        bw = b * w
        denom = float(np.dot(b, bw))
        if denom <= 0.0:
            return 0.0
        return float(np.dot(a, bw) / denom)


def _robust_sigma(residual: np.ndarray, *, mode: str = "mad", window: int = 51, min_sigma: float = 1e-6) -> Tuple[np.ndarray, float]:
    """Estimate sigma for chi-square.
    Returns (sigma_array, sigma_summary). If a scalar sigma is used, sigma_array is filled with that scalar.
    Modes:
      - 'mad': global sigma = 1.4826 * MAD(residual)
      - 'local_mad': rolling MAD with given window (odd), padded at edges
      - 'constant1': sigma = 1.0
      - 'std': global sigma = clipped standard deviation
    """
    r = np.asarray(residual, dtype=float)
    n = len(r)
    if n == 0:
        return np.array([]), 0.0
    mode = (mode or "mad").lower()
    if mode == "constant1":
        sigma_val = 1.0
        return np.full(n, sigma_val, dtype=float), sigma_val
    if mode == "std":
        # Clip extreme outliers for stability
        rr = r[np.isfinite(r)]
        if rr.size == 0:
            sigma_val = 1.0
        else:
            m = float(np.median(rr))
            dev = np.abs(rr - m)
            thr = float(np.quantile(dev, 0.95)) if dev.size > 0 else 0.0
            mask = dev <= max(thr, 1e-12)
            sigma_val = float(np.std(rr[mask])) if np.any(mask) else float(np.std(rr))
        sigma_val = max(min_sigma, sigma_val)
        return np.full(n, sigma_val, dtype=float), sigma_val
    if mode == "local_mad":
        w = int(max(3, window | 1))  # force odd
        half = w // 2
        sig = np.empty(n, dtype=float)
        for i in range(n):
            lo = max(0, i - half)
            hi = min(n, i + half + 1)
            seg = r[lo:hi]
            med = float(np.median(seg))
            mad = float(np.median(np.abs(seg - med)))
            sig[i] = max(min_sigma, 1.4826 * mad)
        return sig, float(np.median(sig))
    # default: global MAD
    rr = r[np.isfinite(r)]
    if rr.size == 0:
        sigma_val = 1.0
    else:
        med = float(np.median(rr))
        mad = float(np.median(np.abs(rr - med)))
        sigma_val = max(min_sigma, 1.4826 * mad)
    return np.full(n, sigma_val, dtype=float), sigma_val


def compute_chi_square_metric(
    matches: List[Dict[str, Any]],
    processed_spectrum: Dict[str, Any],
    *,
    sigma_mode: str = "obs_diff_mad",
    local_window: int = 51,
    min_sigma: float = 1e-6,
    huber_delta: Optional[float] = 0.0,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Compute a chi-square style metric per match on the true overlap only, with robust sigma handling.

    Attaches fields per match:
      - 'chi2': sum((a - alpha b)^2 / sigma^2) over overlap
      - 'reduced_chi2': chi2 / max(1, N - p) with p=1 for fitted scale alpha
      - 'scale_alpha': least-squares scale that best fits template to observed within overlap
      - 'sigma_mode': the chosen sigma mode
      - 'sigma_value': scalar sigma (or median if local windowed)
      - 'rlap_chi': rlap / (1 + reduced_chi2)
    """
    if not matches:
        return matches

    # Choose base flattened spectrum like in compute_rlap_ccc_metric
    if "tapered_flux" in processed_spectrum and processed_spectrum["tapered_flux"] is not None:
        base_flux = processed_spectrum["tapered_flux"]
    elif "display_flat" in processed_spectrum and processed_spectrum["display_flat"] is not None:
        base_flux = processed_spectrum["display_flat"]
    elif "flat_flux" in processed_spectrum and processed_spectrum["flat_flux"] is not None:
        base_flux = processed_spectrum["flat_flux"]
    else:
        base_flux = processed_spectrum.get("tapered_flux")

    if base_flux is None:
        return matches

    base_flux = np.asarray(base_flux, dtype=float)
    le_val = processed_spectrum.get("left_edge", 0)
    re_val = processed_spectrum.get("right_edge", None)
    if le_val is None:
        le_val = 0
    if re_val is None:
        re_val = len(base_flux) - 1
    left_edge = int(le_val)
    right_edge = int(re_val)
    expected_len = right_edge - left_edge + 1
    if len(base_flux) == expected_len:
        input_flux = base_flux
    else:
        input_flux = base_flux[left_edge:right_edge + 1]

    enhanced: list[Dict[str, Any]] = []
    for i, match in enumerate(matches):
        tpl_flux = _extract_template_flux_exact(match)
        if tpl_flux is None or tpl_flux.size == 0:
            enhanced.append(match.copy())
            continue

        try:
            a = np.asarray(input_flux, dtype=float)
            b = np.asarray(tpl_flux, dtype=float)
            n = min(len(a), len(b))
            if n == 0:
                red_chi2 = float("inf")
                alpha = 0.0
                sigma_summary = 0.0
            else:
                # Overlap indices if provided
                start_idx = None
                end_idx = None
                try:
                    overlap_indices = match.get('overlap_indices') or {}
                    if isinstance(overlap_indices, dict):
                        start_idx = int(overlap_indices.get('start'))
                        end_idx = int(overlap_indices.get('end')) + 1
                        if start_idx < 0 or end_idx <= start_idx or end_idx > n:
                            start_idx = None
                            end_idx = None
                except Exception:
                    start_idx = None
                    end_idx = None

                if start_idx is None or end_idx is None:
                    # Compute contiguous joint valid slice
                    tol = 1e-12
                    joint_mask = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > tol) & (np.abs(b) > tol)
                    if not np.any(joint_mask):
                        red_chi2 = float("inf")
                        alpha = 0.0
                        sigma_summary = 0.0
                        new_match = match.copy()
                        new_match.update({
                            'chi2': float("inf"),
                            'reduced_chi2': red_chi2,
                            'scale_alpha': alpha,
                            'sigma_mode': sigma_mode,
                            'sigma_value': sigma_summary,
                            'rlap_chi': 0.0,
                        })
                        enhanced.append(new_match)
                        continue
                    idx = np.flatnonzero(joint_mask)
                    start_idx = int(idx[0])
                    end_idx = int(idx[-1]) + 1

                a_win = a[start_idx:end_idx]
                b_win = b[start_idx:end_idx]

                # First pass: unweighted scale fit
                alpha = _fit_scale_coefficient(a_win, b_win, None)
                resid = a_win - alpha * b_win

                # Sigma estimation (independent of template by default)
                sigma_mode_l = (sigma_mode or "").lower()
                if sigma_mode_l.startswith("obs_"):
                    # Estimate sigma from observed signal only (avoid residual circularity)
                    if sigma_mode_l == "obs_diff_mad":
                        # Use MAD on first differences (noise ~ diff/√2)
                        if len(a_win) >= 3:
                            da = np.diff(a_win)
                            med = float(np.median(da))
                            mad = float(np.median(np.abs(da - med)))
                            sigma_scalar = max(min_sigma, 1.4826 * mad / np.sqrt(2.0))
                        else:
                            sigma_scalar = 1.0
                        sigma_vec = np.full(len(a_win), sigma_scalar, dtype=float)
                        sigma_summary = float(sigma_scalar)
                    elif sigma_mode_l == "obs_local_mad":
                        # Rolling MAD on observed in a window
                        w = int(max(3, local_window | 1))
                        half = w // 2
                        sig = np.empty(len(a_win), dtype=float)
                        for ii in range(len(a_win)):
                            lo = max(0, ii - half)
                            hi = min(len(a_win), ii + half + 1)
                            seg = a_win[lo:hi]
                            m = float(np.median(seg))
                            mad = float(np.median(np.abs(seg - m)))
                            sig[ii] = max(min_sigma, 1.4826 * mad)
                        sigma_vec = sig
                        sigma_summary = float(np.median(sig))
                    else:
                        # Fallback to global MAD on observed
                        m = float(np.median(a_win))
                        mad = float(np.median(np.abs(a_win - m)))
                        sigma_scalar = max(min_sigma, 1.4826 * mad)
                        sigma_vec = np.full(len(a_win), sigma_scalar, dtype=float)
                        sigma_summary = float(sigma_scalar)
                else:
                    # Residual-based sigma modes
                    sigma_vec, sigma_summary = _robust_sigma(resid, mode=sigma_mode_l or "mad", window=local_window, min_sigma=min_sigma)

                # Weighted chi-square with sigma_vec
                w = 1.0 / (sigma_vec * sigma_vec)
                # Optional: refine alpha with weights
                alpha = _fit_scale_coefficient(a_win, b_win, w)
                resid = a_win - alpha * b_win
                if huber_delta and huber_delta > 0.0:
                    # Huber loss approximation to reduce influence of large residuals
                    scaled = resid / sigma_vec
                    d = float(huber_delta)
                    quad = np.minimum(np.abs(scaled), d)
                    lin = np.maximum(np.abs(scaled) - d, 0.0)
                    chi2 = float(np.sum(quad * quad + 2 * d * lin))
                else:
                    chi2 = float(np.sum((resid * np.sqrt(w)) ** 2))
                dof = max(1, len(a_win) - 1)  # -1 for fitted alpha
                red_chi2 = chi2 / float(dof)

            rlap = float(match.get('rlap', 0.0))
            rlap_chi = rlap / (1.0 + float(red_chi2)) if np.isfinite(red_chi2) else 0.0

            new_match = match.copy()
            new_match.update({
                'chi2': float(chi2) if 'chi2' in locals() else float('inf'),
                'reduced_chi2': float(red_chi2),
                'scale_alpha': float(alpha),
                'sigma_mode': str(sigma_mode),
                'sigma_value': float(sigma_summary),
                'rlap_chi': float(rlap_chi),
            })
            enhanced.append(new_match)

            if verbose and i < 5:
                logger.debug(
                    f"Match {i}: RLAP={rlap:.2f}, alpha={alpha:.3f}, red_chi2={red_chi2:.3f}, RLAP-Chi={rlap_chi:.3f}"
                )

        except Exception:
            new_match = match.copy()
            new_match.update({
                'chi2': float('inf'),
                'reduced_chi2': float('inf'),
                'scale_alpha': 0.0,
                'sigma_mode': str(sigma_mode),
                'sigma_value': 0.0,
                'rlap_chi': 0.0,
            })
            enhanced.append(new_match)

    return enhanced