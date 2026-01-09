"""
Similarity and composite metric utilities for SNID SAGE.

Primary metric: HσLAP-CCC
    HσLAP-CCC = (height × lap × CCC) / sqrt(sigma_z)

Where:
- height = peak height
- lap = lap parameter
- CCC = concordance correlation coefficient (99.0% trimmed, capped to [0, 1])
- sigma_z = width × residual_noise_std

This is a BREAKING change replacing the previous composite metric definition.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def concordance_correlation_coefficient_trimmed(
    spec1: np.ndarray,
    spec2: np.ndarray,
    *,
    trim_percentile: float = 99.0,
) -> float:
    """
    Compute Lin's CCC after trimming (dropping) the top (100-trim_percentile)% bins
    with the highest absolute contribution |(a-μa)(b-μb)|.

    This is meant to reduce domination by extreme peaks.
    """
    a = np.asarray(spec1, dtype=float)
    b = np.asarray(spec2, dtype=float)
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[:n]
    b = b[:n]

    tol = 1e-12
    mask = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > tol) & (np.abs(b) > tol)
    if not np.any(mask):
        return 0.0
    a = a[mask]
    b = b[mask]
    if a.size < 2:
        return 0.0

    mu_a = float(np.mean(a))
    mu_b = float(np.mean(b))
    contributions = np.abs((a - mu_a) * (b - mu_b))

    trim_percentile = float(trim_percentile)
    trim_fraction = (100.0 - trim_percentile) / 100.0
    trim_fraction = max(0.0, min(0.99, trim_fraction))

    if trim_fraction > 0.0 and a.size > 2:
        # drop top trim_fraction by contribution
        drop_threshold = float(np.quantile(contributions, 1.0 - trim_fraction))
        keep = contributions < drop_threshold
        if np.sum(keep) < 2:
            keep = np.ones(a.size, dtype=bool)
    else:
        keep = np.ones(a.size, dtype=bool)

    a_t = a[keep]
    b_t = b[keep]
    if a_t.size < 2:
        return 0.0

    mu_x = float(np.mean(a_t))
    mu_y = float(np.mean(b_t))
    var_x = float(np.var(a_t, ddof=1))
    var_y = float(np.var(b_t, ddof=1))
    if a_t.size > 1:
        cov_xy = float(np.sum((a_t - mu_x) * (b_t - mu_y)) / (a_t.size - 1))
    else:
        cov_xy = 0.0
    std_x = float(np.sqrt(var_x))
    std_y = float(np.sqrt(var_y))
    if std_x == 0.0 or std_y == 0.0:
        return 0.0
    rho = cov_xy / (std_x * std_y)
    numerator = 2.0 * rho * std_x * std_y
    denominator = var_x + var_y + (mu_x - mu_y) ** 2
    if denominator == 0.0:
        return 0.0
    return float(np.clip(numerator / denominator, -1.0, 1.0))


def residual_noise_clipped_std(
    a_window: np.ndarray,
    b_window: np.ndarray,
    *,
    clip_percentile: float = 99.0,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute residual noise as std(residuals) after clipping extreme residuals.

    Clipping rule: compute threshold = quantile(|residual|, clip_percentile/100),
    then keep bins with |residual| <= threshold, compute std on kept residuals.

    Returns (noise_std, diagnostics).
    """
    a = np.asarray(a_window, dtype=float)
    b = np.asarray(b_window, dtype=float)
    n = min(len(a), len(b))
    if n == 0:
        return float("nan"), {"n_bins": 0.0, "n_kept": 0.0, "clip_threshold": float("nan")}
    a = a[:n]
    b = b[:n]
    resid = a - b
    mask = np.isfinite(resid)
    resid = resid[mask]
    if resid.size == 0:
        return float("nan"), {"n_bins": float(n), "n_kept": 0.0, "clip_threshold": float("nan")}

    abs_resid = np.abs(resid)
    try:
        thr = float(np.quantile(abs_resid, float(clip_percentile) / 100.0))
    except Exception:
        thr = float("nan")

    if np.isfinite(thr):
        keep = abs_resid <= thr
        resid_kept = resid[keep]
    else:
        resid_kept = resid

    if resid_kept.size == 0:
        resid_kept = resid

    # Use population std (ddof=0) to match typical numpy/std usage in demos.
    noise = float(np.std(resid_kept, ddof=0)) if resid_kept.size > 0 else float("nan")
    diag = {
        "n_bins": float(resid.size),
        "n_kept": float(resid_kept.size),
        "clip_threshold": float(thr),
    }
    return noise, diag


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


# Using CCC (Concordance Correlation Coefficient) exclusively


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


# =============================================================================
# Match-level metrics (HLAP, HσLAP-CCC) and overlap diagnostics (CCC, residual noise)
# =============================================================================

def _extract_match_height_width_lap(match: Dict[str, Any]) -> Tuple[float, float, float]:
    """Best-effort extract (height, width, lap) from a match dict."""
    try:
        height = float(match.get("height", match.get("peak_height", 0.0)) or 0.0)
    except Exception:
        height = 0.0
    try:
        width = float(match.get("width", match.get("peak_width", 0.0)) or 0.0)
    except Exception:
        width = 0.0
    try:
        lap = float(match.get("lap", 0.0) or 0.0)
    except Exception:
        lap = 0.0
    return height, width, lap


@dataclass(frozen=True)
class PreparedOverlap:
    """Prepared phase-2 overlap window for CCC/noise diagnostics."""
    a_window: np.ndarray
    b_window: np.ndarray
    start_idx: int
    end_idx: int


def _select_base_flux(processed_spectrum: Dict[str, Any], *, verbose: bool = False) -> Optional[np.ndarray]:
    """Select the base spectrum flux used for phase-2 overlap diagnostics."""
    if "tapered_flux" in processed_spectrum and processed_spectrum["tapered_flux"] is not None:
        if verbose:
            logger.info("Using tapered_flux for overlap diagnostics")
        return np.asarray(processed_spectrum["tapered_flux"], dtype=float)
    if "display_flat" in processed_spectrum and processed_spectrum["display_flat"] is not None:
        if verbose:
            logger.info("Using display_flat for overlap diagnostics")
        return np.asarray(processed_spectrum["display_flat"], dtype=float)
    if "flat_flux" in processed_spectrum and processed_spectrum["flat_flux"] is not None:
        if verbose:
            logger.warning("Using flat_flux (non-apodized) for overlap diagnostics")
        return np.asarray(processed_spectrum["flat_flux"], dtype=float)
    if verbose:
        logger.warning("Using tapered_flux fallback for overlap diagnostics")
    bf = processed_spectrum.get("tapered_flux")
    return None if bf is None else np.asarray(bf, dtype=float)


def _trim_flux_to_edges(base_flux: np.ndarray, processed_spectrum: Dict[str, Any]) -> np.ndarray:
    """Trim base_flux to [left_edge:right_edge] (inclusive) when needed."""
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
        return base_flux
    return base_flux[left_edge:right_edge + 1]


def prepare_overlap_window(
    match: Dict[str, Any],
    input_flux: np.ndarray,
    *,
    apodize_percent: float = 10.0,
) -> Optional[PreparedOverlap]:
    """Prepare the overlap window (a_window, b_window) for a match.

    Uses match['overlap_indices'] when available; otherwise infers the joint valid contiguous overlap.
    """
    tpl_flux = _extract_template_flux_exact(match)
    if tpl_flux is None or np.asarray(tpl_flux).size == 0:
        return None

    a = np.asarray(input_flux, dtype=float)
    b = np.asarray(tpl_flux, dtype=float)
    n = min(len(a), len(b))
    if n < 2:
        return None
    a = a[:n]
    b = b[:n]

    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    try:
        overlap_indices = match.get("overlap_indices") or {}
        if isinstance(overlap_indices, dict):
            start_idx = int(overlap_indices.get("start"))
            end_idx = int(overlap_indices.get("end")) + 1  # inclusive -> exclusive
            if start_idx < 0 or end_idx <= start_idx or end_idx > n:
                start_idx = None
                end_idx = None
    except Exception:
        start_idx = None
        end_idx = None

    if start_idx is None or end_idx is None:
        tol = 1e-12
        joint_mask = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > tol) & (np.abs(b) > tol)
        if not np.any(joint_mask):
            return None
        idxs = np.flatnonzero(joint_mask)
        start_idx = int(idxs[0])
        end_idx = int(idxs[-1]) + 1

    a_window = a[start_idx:end_idx]
    b_window = b[start_idx:end_idx]
    if a_window.size < 2 or b_window.size < 2:
        return None

    # Local apodization once; shared by CCC + residual-noise.
    try:
        from snid_sage.snid.preprocessing import apodize as _snid_apodize  # type: ignore
        ap = float(apodize_percent)
        if np.isfinite(ap) and ap > 0.0:
            n1 = 0
            n2 = a_window.size - 1
            if n2 >= n1:
                a_window = _snid_apodize(a_window, n1, n2, percent=ap)
                b_window = _snid_apodize(b_window, n1, n2, percent=ap)
    except Exception:
        pass

    return PreparedOverlap(a_window=a_window, b_window=b_window, start_idx=int(start_idx), end_idx=int(end_idx))


def compute_phase2_overlap_diagnostics(
    matches: List[Dict[str, Any]],
    processed_spectrum: Dict[str, Any],
    verbose: bool = False,
    *,
    trim_percentile: float = 99.0,
    residual_clip_percentile: float = 99.0,
    apodize_percent: float = 10.0,
    compute_ccc: bool = True,
    compute_noise: bool = True,
) -> List[Dict[str, Any]]:
    """Compute CCC (99.0% trimmed) and/or residual-noise diagnostics on the phase-2 overlap windows.

    This reuses a single prepared overlap window per match for both CCC and residual-noise.
    """
    if not matches:
        return matches

    base_flux = _select_base_flux(processed_spectrum, verbose=verbose)
    if base_flux is None:
        return matches
    input_flux = _trim_flux_to_edges(base_flux, processed_spectrum)

    enhanced_matches: List[Dict[str, Any]] = []
    for match in matches:
        enhanced = match.copy()

        prepared = prepare_overlap_window(match, input_flux, apodize_percent=float(apodize_percent))

        ccc_trim = 0.0
        ccc_trim_capped = 0.0
        noise_std = float("nan")
        noise_diag: Dict[str, float] = {"n_bins": float("nan"), "n_kept": float("nan"), "clip_threshold": float("nan")}

        if prepared is not None:
            if compute_ccc:
                try:
                    ccc_trim = concordance_correlation_coefficient_trimmed(
                        prepared.a_window, prepared.b_window, trim_percentile=float(trim_percentile)
                    )
                    ccc_trim_capped = max(0.0, float(ccc_trim))
                except Exception:
                    ccc_trim = 0.0
                    ccc_trim_capped = 0.0
            if compute_noise:
                try:
                    noise_std, noise_diag = residual_noise_clipped_std(
                        prepared.a_window, prepared.b_window, clip_percentile=float(residual_clip_percentile)
                    )
                except Exception:
                    noise_std = float("nan")

        if compute_ccc:
            enhanced["ccc_similarity_trimmed"] = float(ccc_trim)
            enhanced["ccc_similarity_trimmed_capped"] = float(ccc_trim_capped)
            # Alias keys: CCC values here are the trimmed CCC.
            enhanced["ccc_similarity"] = float(ccc_trim)
            enhanced["ccc_similarity_capped"] = float(ccc_trim_capped)
            enhanced["ccc_trim_percentile"] = float(trim_percentile)

        if compute_noise:
            enhanced["residual_noise_std"] = float(noise_std) if np.isfinite(noise_std) else float("nan")
            enhanced["residual_clip_percentile"] = float(residual_clip_percentile)
            enhanced["residual_clip_threshold"] = float(noise_diag.get("clip_threshold", float("nan")))
            enhanced["residual_n_bins"] = float(noise_diag.get("n_bins", float("nan")))
            enhanced["residual_n_kept"] = float(noise_diag.get("n_kept", float("nan")))

        enhanced_matches.append(enhanced)

    return enhanced_matches


def compute_sigma_z_metrics(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute per-match sigma_z = width * residual_noise_std.

    Failure policy: if width/noise is missing or invalid, sigma_z is NaN.
    """
    if not matches:
        return matches
    out: List[Dict[str, Any]] = []
    for match in matches:
        m = match.copy()
        _, width, _ = _extract_match_height_width_lap(m)
        try:
            noise = float(m.get("residual_noise_std", float("nan")))
        except Exception:
            noise = float("nan")
        sigma_z = float("nan")
        if np.isfinite(width) and width > 0.0 and np.isfinite(noise) and noise >= 0.0:
            sigma_z = float(width * noise)
        m["sigma_z"] = float(sigma_z) if (np.isfinite(sigma_z) and sigma_z > 0.0) else float("nan")
        out.append(m)
    return out


def _compute_hsigma_lap_ccc_from_ccc(
    hlap: float,
    ccc_trimmed_capped: float,
    sigma_z: float,
) -> float:
    """Compute HσLAP-CCC = (HLAP * CCC) / sqrt(sigma_z).

    Failure policy: return NaN when sigma_z is NaN or <= 0.
    """
    if not (np.isfinite(hlap) and hlap > 0.0):
        return float("nan")
    if not (np.isfinite(sigma_z) and sigma_z > 0.0):
        return float("nan")
    ccc_clip = float(np.clip(float(ccc_trimmed_capped), 0.0, 1.0))
    return float((hlap * ccc_clip) / float(np.sqrt(sigma_z)))


def compute_hsigma_lap_ccc_metric(
    matches: List[Dict[str, Any]],
    processed_spectrum: Dict[str, Any],
    verbose: bool = False,
    *,
    trim_percentile: float = 99.0,
    residual_clip_percentile: float = 99.0,
) -> List[Dict[str, Any]]:
    """Compute HσLAP-CCC = (height × lap × CCC) / sqrt(sigma_z) for each match.

    Requirements / computation order:
    - CCC diagnostics are computed here if missing (trimmed/capped CCC).
    - sigma_z MUST already exist on each match dict (computed via `compute_sigma_z_metrics()`).

    Failure policy:
    - If sigma_z is NaN or <= 0, the metric is NaN.
    - Downstream selection falls back to HLAP via `get_best_metric_value()`.
    """
    if not matches:
        return matches

    # Ensure CCC diagnostics exist (trimmed, capped). Avoid computing noise here.
    need_ccc = any(isinstance(m, dict) and ("ccc_similarity_trimmed_capped" not in m) for m in matches)
    if need_ccc:
        matches = compute_phase2_overlap_diagnostics(
            matches,
            processed_spectrum,
            verbose=verbose,
            trim_percentile=float(trim_percentile),
            residual_clip_percentile=float(residual_clip_percentile),
            compute_ccc=True,
            compute_noise=False,
        )

    enhanced_matches: List[Dict[str, Any]] = []
    for i, match in enumerate(matches):
        enhanced = match.copy()

        height, _, lap = _extract_match_height_width_lap(enhanced)
        hlap = float(height * lap) if (np.isfinite(height) and np.isfinite(lap)) else float("nan")

        try:
            ccc_capped = float(
                enhanced.get("ccc_similarity_trimmed_capped", enhanced.get("ccc_similarity_capped", 0.0))
            )
        except Exception:
            ccc_capped = 0.0
        if not np.isfinite(ccc_capped):
            ccc_capped = 0.0

        try:
            sigma_z = float(enhanced.get("sigma_z", float("nan")))
        except Exception:
            sigma_z = float("nan")
        hsigma_lap_ccc = _compute_hsigma_lap_ccc_from_ccc(hlap, ccc_capped, sigma_z)

        enhanced["hlap"] = hlap
        enhanced["hsigma_lap_ccc"] = hsigma_lap_ccc

        if verbose and i < 5:
            logger.debug(
                "HσLAP-CCC %d: hlap=%.3g ccc=%.3g sigma_z=%.3g metric=%.3g",
                i,
                float(hlap) if np.isfinite(hlap) else float("nan"),
                float(ccc_capped),
                float(sigma_z) if np.isfinite(sigma_z) else float("nan"),
                float(hsigma_lap_ccc) if np.isfinite(hsigma_lap_ccc) else float("nan"),
            )

        enhanced_matches.append(enhanced)

    return enhanced_matches


# Using CCC exclusively


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
    
    Returns HσLAP-CCC if available, otherwise falls back to HLAP (height × lap).
    
    Parameters
    ----------
    match : Dict[str, Any]
        Template match dictionary
        
    Returns
    -------
    float
        Best available metric value
    """
    if not isinstance(match, dict):
        return 0.0
    # Prefer HσLAP-CCC when available
    v = match.get("hsigma_lap_ccc", None)
    try:
        if v is not None:
            vf = float(v)
            # IMPORTANT: treat NaN/inf as "not available" so we can fall back to HLAP.
            # This avoids dropping all matches during thresholding when sigma_z is unavailable.
            if np.isfinite(vf):
                return vf
    except Exception:
        pass
    # Fallback: HLAP (height × lap)
    try:
        if "hlap" in match:
            hv = float(match["hlap"])
            return hv if np.isfinite(hv) else 0.0
    except Exception:
        pass
    try:
        h = float(match.get("height", match.get("peak_height", 0.0)) or 0.0)
    except Exception:
        h = 0.0
    try:
        lap = float(match.get("lap", 0.0) or 0.0)
    except Exception:
        lap = 0.0
    return float(h * lap)


def get_hlap_value(match: Dict[str, Any]) -> float:
    """
    Get HLAP (height × lap) from a match dict.

    This is intentionally independent of HσLAP-CCC / CCC diagnostics and is used
    for HLAP-based thresholding and quality labeling.
    """
    if not isinstance(match, dict):
        return 0.0
    try:
        if "hlap" in match:
            return float(match["hlap"])
    except Exception:
        pass
    try:
        h = float(match.get("height", match.get("peak_height", 0.0)) or 0.0)
    except Exception:
        h = 0.0
    try:
        lap = float(match.get("lap", 0.0) or 0.0)
    except Exception:
        lap = 0.0
    return float(h * lap)


def get_metric_name_for_match(match: Dict[str, Any]) -> str:
    """
    Get the name of the metric being used for a match.
    
    Returns 'HσLAP-CCC' if available, otherwise 'HLAP'.
    
    Parameters
    ----------
    match : Dict[str, Any]
        Template match dictionary
        
    Returns
    -------
    str
        Name of the metric
    """
    if isinstance(match, dict) and ("hsigma_lap_ccc" in match):
        return "HσLAP-CCC"
    return "HLAP"


def get_best_metric_name(match: Dict[str, Any]) -> str:
    """
    Get the name of the best available metric for a match.
    
    Returns 'HσLAP-CCC' if available, otherwise 'HLAP'.
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
    if isinstance(match, dict) and ("hsigma_lap_ccc" in match):
        return "HσLAP-CCC"
    return "HLAP"


def get_metric_display_values(match: Dict[str, Any]) -> Dict[str, float]:
    """
    Get all available metric values for display purposes.
    
    Returns a dictionary with available metric values for display purposes.
    
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
        'primary_metric': get_best_metric_value(match),
        'metric_name': get_metric_name_for_match(match)
    }
    
    if 'hsigma_lap_ccc' in match:
        values['hsigma_lap_ccc'] = match.get('hsigma_lap_ccc', 0.0)
        values['hlap'] = match.get('hlap', 0.0)
        values['ccc_similarity_trimmed'] = match.get('ccc_similarity_trimmed', match.get('ccc_similarity', 0.0))
        values['ccc_similarity_trimmed_capped'] = match.get('ccc_similarity_trimmed_capped', match.get('ccc_similarity_capped', 0.0))
        values['residual_noise_std'] = match.get('residual_noise_std', float('nan'))

    
    return values 

