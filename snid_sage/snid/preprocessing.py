"""
preprocessing.py – low-level helpers for the Python SNID port
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Public API
----------
  • init_wavelength_grid
  • clip_aband
  • clip_sky_lines
  • clip_host_emission_lines
  • apply_wavelength_mask
  • log_rebin
  • fit_continuum_spline
  • apodize
"""

from __future__ import annotations
import numpy as np
from numpy.typing import NDArray
from typing import List, Tuple, Optional, Dict
import logging
from numpy import ma


_LOG = logging.getLogger("snid.preprocessing")


def enforce_positive_flux(
    flux: NDArray[np.floating],
    *,
    eps_fraction: float = 1e-6,
) -> Tuple[NDArray[np.floating], float]:
    """
    Ensure that a flux array is strictly positive everywhere.

    This helper is designed for the SNID continuum fitter, which assumes
    non–negative real flux values when placing knots and taking log10
    averages.  It is intentionally unconditional: if *any* finite sample
    is ≤ 0, we shift the entire spectrum upward by a constant offset.

    Parameters
    ----------
    flux : array_like
        Input flux array (may contain negative/zero values and NaNs).
    eps_fraction : float, optional
        Small fractional safety margin relative to a robust flux scale
        (default 1e-6).  This avoids edge–case zeros after shifting.

    Returns
    -------
    shifted_flux : np.ndarray
        Flux array guaranteed to satisfy shifted_flux > 0 wherever the
        original data were finite.
    offset : float
        Constant added to the input flux (0.0 if no shift was required).
    """
    f = np.asarray(flux, dtype=float)
    if f.size == 0:
        return f.copy(), 0.0

    finite_mask = np.isfinite(f)
    if not np.any(finite_mask):
        return f.copy(), 0.0

    f_finite = f[finite_mask]

    # If fewer than 1% of finite samples are negative, treat this as a
    # normal fluxed spectrum and leave it unchanged. The continuum fitter
    # already ignores isolated negatives via its flux>0 masks.
    neg_frac = float(np.mean(f_finite < 0.0))
    if neg_frac < 0.01:
        return f.copy(), 0.0

    fmin = float(np.min(f_finite))
    if fmin > 0.0:
        # Already strictly positive; nothing to do.
        return f.copy(), 0.0

    # Robust scale for choosing a tiny positive epsilon.
    abs_vals = np.abs(f_finite)
    scale = float(np.median(abs_vals))
    if scale <= 0.0:
        # Fallback to max amplitude or 1.0 to avoid eps=0.
        scale = float(np.max(abs_vals)) if np.max(abs_vals) > 0.0 else 1.0

    # Guard against a *single* very deep negative outlier dominating fmin.
    # We clip the negative tail at -k * scale when determining the offset so that
    # continuum fitting still sees a strictly positive spectrum, but one or two
    # pathological pixels do not force an enormous upward shift that flattens all
    # real features (common in very long/high-resolution spectra).
    k = 1.2
    try:
        neg_clip_level = -k * scale
        f_finite_clipped = f_finite.copy()
        deep_neg_mask = f_finite_clipped < neg_clip_level
        if np.any(deep_neg_mask):
            _LOG.debug(
                "enforce_positive_flux: clipping %d deep negative sample(s) below %.3g "
                "to %.3g before computing offset",
                int(np.count_nonzero(deep_neg_mask)),
                float(f_finite_clipped[deep_neg_mask].min()),
                float(neg_clip_level),
            )
            f_finite_clipped[deep_neg_mask] = neg_clip_level
        fmin = float(np.min(f_finite_clipped))
    except Exception:
        # Fall back to the original minimum if clipping fails for any reason.
        fmin = float(np.min(f_finite))

    eps = float(eps_fraction) * scale
    if eps < 0.0:
        eps = 0.0

    offset = -fmin + eps
    shifted = f + offset
    return shifted, float(offset)

# ------------------------------------------------------------------
# global logarithmic grid
# ------------------------------------------------------------------
# NW: int        = 1024
# W0: float      = 2500.0      # Å
# W1: float      = 10000.0     # Å
# DWLOG: float | None = None   # filled by init_wavelength_grid()

def init_wavelength_grid(num_points: int = 1024,
                         min_wave: float = 2500.0,
                         max_wave: float = 10000.0) -> None:
    """Define the fixed log-λ grid shared by all spectra."""
    global NW, W0, W1, DWLOG
    NW, W0, W1 = int(num_points), float(min_wave), float(max_wave)
    DWLOG = np.log(W1 / W0) / (NW)
    _LOG.debug("Grid initialised: NW=%d  W0=%.1f  W1=%.1f  DWLOG=%.6e",
               NW, W0, W1, DWLOG)

def _ensure_grid() -> None:
    if DWLOG is None:
        init_wavelength_grid()

def get_grid_params() -> tuple[int, float, float, float]:
    """
    Return (NW, W0, W1, DWLOG); initialises the grid if necessary.
    """
    _ensure_grid()
    return NW, W0, W1, DWLOG

# ------------------------------------------------------------------
# filters & masks
# ------------------------------------------------------------------
def savgol_filter_fixed(data: NDArray[np.floating], window_length: int = 11, polyorder: int = 3) -> NDArray[np.floating]:
    """
    Apply Savitzky-Golay filter with fixed window length (pixel-based smoothing).
    
    Parameters:
    -----------
    data : NDArray[np.floating]
        Input flux array to filter
    window_length : int
        Length of the filter window in pixels (must be odd, default: 11)
    polyorder : int
        Order of the polynomial used to fit the samples (default: 3)
        
    Returns:
    --------
    NDArray[np.floating]
        Filtered flux array
    """
    from scipy.signal import savgol_filter
    
    if window_length < 3:
        return data.copy()
    
    # Ensure window length is odd and valid
    if window_length % 2 == 0:
        window_length += 1
    
    # Ensure window length is not larger than data
    window_length = min(window_length, len(data))
    if window_length < 3:
        return data.copy()
    
    # Ensure polynomial order is less than window length
    polyorder = min(polyorder, window_length - 1)
    
    try:
        return savgol_filter(data, window_length, polyorder)
    except Exception:
        # Return original data if filtering fails
        return data.copy()


# Wavelength-based filtering no longer supported

# --- clipping helpers --------------------------------------------------------
def clip_aband(
    w: np.ndarray,
    f: np.ndarray,
    band: Tuple[float, float] | Tuple[Tuple[float, float], ...] | list = (7550.0, 7700.0),
) -> Tuple[np.ndarray, np.ndarray]:
    """Remove telluric O2 A-band.

    Default removes the O2 A-band (≈7550–7700 Å). Accepts either a single
    (start, end) tuple to remove one region or an iterable of (start, end)
    tuples to remove multiple regions if desired.
    """
    # Normalize "band" to an iterable of (a, b) windows
    if isinstance(band, tuple) and len(band) == 2 and all(isinstance(x, (int, float)) for x in band):
        bands: list[tuple[float, float]] = [tuple(float(x) for x in band)]  # type: ignore
    else:
        bands = [(float(a), float(b)) for (a, b) in band]  # type: ignore[arg-type]

    keep = np.ones_like(w, dtype=bool)
    for a, b in bands:
        keep &= ~((w >= a) & (w <= b))
    return w[keep], f[keep]

def clip_sky_lines(w: np.ndarray, f: np.ndarray,
                   width: float = 40.0,
                   lines: Tuple[float,...] = (5577.0, 6300.2, 6364.0)
                  ) -> Tuple[np.ndarray, np.ndarray]:
    keep = np.ones_like(w, bool)
    for l in lines:
        keep &= ~((w >= l-width) & (w <= l+width))
    return w[keep], f[keep]

def clip_host_emission_lines(w: np.ndarray, f: np.ndarray,
                             z: float,
                             width: float = 40.0
                            ) -> Tuple[np.ndarray, np.ndarray]:
    if z < 0:
        return w, f
    rest = [3727.3, 4861.3, 4958.9, 5006.8,
            6548.1, 6562.8, 6583.6, 6716.4, 6730.8]
    keep = np.ones_like(w, bool)
    for l in rest:
        ll = l*(1+z)
        keep &= ~((w >= ll-width) & (w <= ll+width))
    return w[keep], f[keep]

def apply_wavelength_mask(w: np.ndarray, f: np.ndarray,
                          ranges: List[Tuple[float,float]]
                         ) -> Tuple[np.ndarray, np.ndarray]:
    keep = np.ones_like(w, bool)
    for a, b in ranges:
        if b < a:
            raise ValueError(f"mask ({a},{b}) has b < a")
        keep &= ~((w >= a) & (w <= b))
    return w[keep], f[keep]

# ------------------------------------------------------------------
# interpolation-based log rebin helpers (mask-aware)
# ------------------------------------------------------------------
def compute_mask_on_loggrid(log_wave: np.ndarray,
                            ranges: List[Tuple[float, float]]) -> np.ndarray:
    """
    Return a boolean mask over log_wave where bins fall inside any masked range.
    """
    if log_wave is None or len(log_wave) == 0 or not ranges:
        return np.zeros(0, dtype=bool) if log_wave is None else np.zeros_like(log_wave, dtype=bool)
    w = np.asarray(log_wave, dtype=float)
    mask = np.zeros_like(w, dtype=bool)
    for a, b in ranges:
        a_f = float(a)
        b_f = float(b)
        if b_f < a_f:
            a_f, b_f = b_f, a_f
        mask |= ((w >= a_f) & (w <= b_f))
    return mask


def _cumulative_trap_at_samples(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    dx = np.diff(x)
    mid = 0.5 * (y[:-1] + y[1:])
    contrib = mid * dx
    return np.concatenate([[0.0], np.cumsum(contrib)])


def _integral_linear_any_x(x: np.ndarray, y: np.ndarray, I_at_x: np.ndarray, xq: np.ndarray) -> np.ndarray:
    xq = np.asarray(xq, dtype=float)
    out = np.empty_like(xq)
    # Clip to domain
    xq_clipped = np.clip(xq, x[0], x[-1])
    idx = np.searchsorted(x, xq_clipped, side='right') - 1
    idx = np.clip(idx, 0, x.size - 2)
    x0 = x[idx]
    x1 = x[idx + 1]
    y0 = y[idx]
    y1 = y[idx + 1]
    dx = (x1 - x0)
    t = (xq_clipped - x0) / dx
    du = (xq_clipped - x0)
    seg = du * (y0 + 0.5 * (y1 - y0) * t)
    out[:] = I_at_x[idx] + seg
    out[xq < x[0]] = 0.0
    out[xq > x[-1]] = I_at_x[-1]
    return out


def log_rebin_maskaware(
    wave: NDArray[np.floating],
    flux: NDArray[np.floating],
    masks: Optional[List[Tuple[float, float]]] = None,
    *,
    min_coverage: float = 0.2,
) -> Tuple[NDArray[np.floating], NDArray[np.floating], NDArray[np.bool_]]:
    """
    Flux-conserving log rebin that respects wavelength masks.

    - Integrates flux*weight and weight over each log bin on the global grid.
      weight(λ) = 1 outside masked ranges; 0 inside.
    - Bin value = integral(flux*weight) / integral(weight), i.e., average over unmasked portion.
    - Bins with insufficient unmasked coverage (< min_coverage) are filled by linear
      interpolation ONLY inside masked log-bins; edge bins outside observed range remain zero.

    Returns (log_wave, log_flux_filled, mask_logbins)
    """
    _ensure_grid()
    NW_g, W0_g, W1_g, DWLOG_g = get_grid_params()

    # Build target centers and edges on the global SNID grid
    log_wave = W0_g * np.exp((np.arange(NW_g) + 0.5) * DWLOG_g)
    edges = W0_g * np.exp((np.arange(NW_g + 1) - 0.5) * DWLOG_g)
    binw = np.diff(edges)

    # Prepare inputs: finite, sorted ascending, unique
    w = np.asarray(wave, float)
    f = np.asarray(flux, float)
    keep = np.isfinite(w) & np.isfinite(f) & (w > 0)
    if not np.any(keep):
        mask_logbins = compute_mask_on_loggrid(log_wave, masks or [])
        return log_wave, np.zeros_like(log_wave), mask_logbins
    w = w[keep]
    f = f[keep]
    order = np.argsort(w)
    w = w[order]
    f = f[order]
    # drop duplicates
    if w.size > 1:
        uniq = np.concatenate([[True], np.diff(w) > 0])
        w = w[uniq]
        f = f[uniq]

    # Clip any wavelength masks to the actually observed data range so that
    # only interior gaps (within [w.min(), w.max()]) are treated as masked
    # regions to be interpolated across on the log grid. Parts of a mask that
    # lie strictly outside the observed range are effectively "off-spectrum"
    # and should not cause edge bins to be refilled.
    clipped_masks: List[Tuple[float, float]] = []
    if masks:
        obs_min = float(w[0])
        obs_max = float(w[-1])
        for a, b in masks:
            aa = float(min(a, b))
            bb = float(max(a, b))
            clipped_a = max(aa, obs_min)
            clipped_b = min(bb, obs_max)
            if clipped_b > clipped_a:
                clipped_masks.append((clipped_a, clipped_b))

    # Ensure mask edges exist as samples so integration doesn't "bridge" big gaps
    # created when upstream clipping physically removes masked regions.
    if clipped_masks and w.size >= 2:
        try:
            boundary_points: list[float] = []
            w0 = float(w[0])
            w1 = float(w[-1])
            for a, b in clipped_masks:
                for x in (float(a), float(b)):
                    if np.isfinite(x) and (w0 < x < w1):
                        boundary_points.append(x)
            if boundary_points:
                # Deduplicate while keeping numeric stability
                bp = np.array(sorted(set(boundary_points)), dtype=float)
                if bp.size:
                    fb = np.interp(bp, w, f)
                    w = np.concatenate([w, bp])
                    f = np.concatenate([f, fb])
                    order = np.argsort(w)
                    w = w[order]
                    f = f[order]
                    # drop duplicates again (boundary might coincide with existing samples)
                    uniq = np.concatenate([[True], np.diff(w) > 0])
                    w = w[uniq]
                    f = f[uniq]
        except Exception:
            # Safe fallback: proceed without boundary insertion
            pass

    # Build weight samples from masks: 1 outside, 0 inside
    weight = np.ones_like(w, float)
    if clipped_masks:
        for a, b in clipped_masks:
            aa = float(a)
            bb = float(b)
            weight[(w >= aa) & (w <= bb)] = 0.0

    # Precompute cumulative integrals at sample positions
    I_fw = _cumulative_trap_at_samples(w, f * weight)
    I_w  = _cumulative_trap_at_samples(w, weight)

    # Evaluate integrals at log-bin edges via linear-interp integral
    I_fw_edges = _integral_linear_any_x(w, f * 1.0 * weight, I_fw, edges)
    I_w_edges  = _integral_linear_any_x(w, weight, I_w, edges)

    num = np.diff(I_fw_edges)
    den = np.diff(I_w_edges)
    with np.errstate(invalid='ignore', divide='ignore'):
        reb = num / den
    coverage = den / binw

    # Identify masked bins on the log grid and low-coverage bins.  We use the
    # masks clipped to the observed wavelength range so that only true interior
    # gaps are interpolated across; bins outside the data range remain zeros.
    mask_logbins = compute_mask_on_loggrid(log_wave, clipped_masks)
    invalid = (~np.isfinite(reb)) | (coverage < float(min_coverage))

    # Fill only inside masked bins; preserve zeros at edges/outside masks
    out = reb.copy()
    to_fill = invalid & mask_logbins
    if np.any(to_fill):
        valid = ~invalid & np.isfinite(reb)
        if np.count_nonzero(valid) >= 2:
            x = log_wave
            out[to_fill] = np.interp(x[to_fill], x[valid], out[valid])
        else:
            # not enough neighbors; leave as zero for safety
            out[to_fill] = 0.0

    # Any remaining invalid outside masked regions → zero (edge padding convention)
    out[invalid & (~mask_logbins)] = 0.0

    return log_wave.astype(float, copy=False), out.astype(float, copy=False), mask_logbins.astype(bool, copy=False)


# ------------------------------------------------------------------
# cosine bell taper
# ------------------------------------------------------------------
def apodize(arr, n1, n2, percent=5.0):
    """Raised-cosine taper exactly like SNID's APOWID, but only over the valid region.
    Apodizes `arr` between `n1` and `n2` (inclusive), where these are the start and end indices of the valid (nonzero) region.
    The percentage is relative to the valid region length (n2-n1+1).
    """
    out = arr.copy()
    if not (0 <= n1 <= n2 < len(arr)):
        _LOG.warning(f"Apodize range [{n1},{n2}] invalid for array of length {len(arr)}. Skipping.")
        return out

    if percent is None or percent <= 0:
        return out

    valid_data_len = (n2 - n1 + 1)
    if valid_data_len <= 0:
        return out
    ns = int(round(valid_data_len * percent / 100.0))
    ns = min(ns, int(valid_data_len / 2.0))

    if ns < 1:
        return out

    if ns == 1:
        ramp = np.array([0.0])
    elif ns > 1:
        ramp = 0.5 * (1 - np.cos(np.pi * np.arange(ns) / (ns - 1.0)))
    else:
        return out

    if n1 + ns > len(arr) or n2 - ns + 1 < 0:
        _LOG.warning("Apodize slice out of bounds after ns calculation.")
        return out

    out[n1 : n1 + ns] *= ramp
    out[n2 - ns + 1 : n2 + 1] *= ramp[::-1]
    return out

# ------------------------------------------------------------------
# spike masking (floor-relative outlier removal)
# ------------------------------------------------------------------
def _robust_scale(x: np.ndarray) -> Tuple[float, float]:
    """Return (robust_sigma, median) using MAD; fallback to std if MAD=0.

    Ensures sigma is never zero by adding a tiny term scaled to data magnitude.
    """
    x = np.asarray(x, float)
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    sigma = 1.4826 * mad if mad > 0 else float(np.std(x))
    scale_ref = float(np.median(np.abs(x))) if np.median(np.abs(x)) != 0 else float(np.max(np.abs(x)) or 1.0)
    return float(max(sigma, 1e-6 * scale_ref + 1e-30)), med


def _nms_runs(core: np.ndarray, strength: np.ndarray) -> np.ndarray:
    """Non-maximum suppression across contiguous True runs in `core`.

    Keeps, for each run, the index with the highest `strength` value.
    """
    idx_keep: list[int] = []
    n = int(core.size)
    i = 0
    while i < n:
        if bool(core[i]):
            j = i
            while j + 1 < n and bool(core[j + 1]):
                j += 1
            run = np.arange(i, j + 1)
            idx_keep.append(int(run[np.argmax(strength[run])]))
            i = j + 1
        else:
            i += 1
    return np.array(sorted(idx_keep), dtype=int)


def _running_median_pixels(x: np.ndarray, window: int) -> np.ndarray:
    """Running median on a pixel window (odd); reflective padding at edges."""
    w = int(max(3, int(window) | 1))
    n = x.size
    if n == 0:
        return x.astype(float)
    if w > n:
        w = n if (n % 2 == 1) else (n - 1)
        w = max(3, int(w))
    half = w // 2
    padded = np.pad(x.astype(float), (half, half), mode="reflect")
    out = np.empty(n, float)
    for i in range(n):
        out[i] = float(np.median(padded[i:i + w]))
    return out


def _effective_window_from_wavelengths(wave_sorted: np.ndarray, baseline_width: float) -> int:
    """Compute odd integer pixel window from median Δλ and desired width."""
    if wave_sorted.size < 3 or baseline_width <= 0:
        return 3
    diffs = np.diff(wave_sorted.astype(float))
    positive_diffs = diffs[diffs > 0]
    if positive_diffs.size == 0:
        return 3
    dw = float(np.median(positive_diffs))
    if dw <= 0:
        return 3
    approx = int(max(3, round(baseline_width / dw)))
    return int(approx | 1)


def _running_median_wavelength(wave_sorted: np.ndarray, flux_sorted: np.ndarray, width: float) -> np.ndarray:
    """Running median using fixed wavelength window width on sorted wavelengths."""
    n = flux_sorted.size
    out = np.empty(n, float)
    if n == 0:
        return flux_sorted.astype(float)
    if not np.all(np.diff(wave_sorted.astype(float)) >= 0):
        raise ValueError("wave_sorted must be sorted ascending for wavelength-based median")
    halfw = float(width) * 0.5
    for i in range(n):
        wl = float(wave_sorted[i])
        left = int(np.searchsorted(wave_sorted, wl - halfw, side="left"))
        right = int(np.searchsorted(wave_sorted, wl + halfw, side="right"))
        if right <= left:
            out[i] = float(flux_sorted[i])
        else:
            out[i] = float(np.median(flux_sorted[left:right]))
    return out


def find_spike_indices(
    wave: np.ndarray,
    flux: np.ndarray,
    *,
    floor_z: float = 50.0,
    neg_floor_z: float | None = None,
    baseline_window: int = 501,
    baseline_width: float | None = None,
    rel_edge_ratio: float = 2.0,
    min_separation: int = 2,
    max_removals: int | None = None,
    min_abs_resid: float | None = None,
) -> np.ndarray:
    """Detect spike indices as extreme floor-relative outliers.

    Returns indices in the original (unsorted) ordering.
    """
    w = np.asarray(wave, float)
    f = np.asarray(flux, float)
    mask = np.isfinite(w) & np.isfinite(f)
    if not np.any(mask):
        return np.array([], dtype=int)
    w = w[mask]
    f = f[mask]
    order = np.argsort(w)
    w_sorted = w[order]
    f_sorted = f[order]

    if baseline_width is not None and float(baseline_width) > 0:
        floor = _running_median_wavelength(w_sorted, f_sorted, float(baseline_width))
        eff_window = _effective_window_from_wavelengths(w_sorted, float(baseline_width))
    else:
        eff_window = int(baseline_window)
        floor = _running_median_pixels(f_sorted, eff_window)

    resid = f_sorted - floor
    sR, _ = _robust_scale(resid)
    if sR <= 0:
        return np.array([], dtype=int)
    z = resid / sR

    # Asymmetric thresholds: positive spikes at floor_z; negative spikes at neg_floor_z (defaults to floor_z)
    nfz = float(floor_z) if neg_floor_z is None else float(neg_floor_z)
    core = (z >= float(floor_z)) | (z <= -nfz)
    if min_abs_resid is not None and float(min_abs_resid) > 0:
        core &= (np.abs(resid) >= float(min_abs_resid))

    cand = _nms_runs(core, np.abs(z))

    extrema: list[int] = []
    n = int(f_sorted.size)
    for i in cand:
        if n == 1:
            extrema.append(int(i))
        elif i == 0:
            if (resid[0] > 0 and resid[0] > resid[1] and resid[0] >= rel_edge_ratio * max(resid[1], 0.0)) or \
               (resid[0] < 0 and resid[0] < resid[1] and abs(resid[0]) >= rel_edge_ratio * abs(min(resid[1], 0.0))):
                extrema.append(int(i))
        elif i == n - 1:
            if (resid[-1] > 0 and resid[-1] > resid[-2] and resid[-1] >= rel_edge_ratio * max(resid[-2], 0.0)) or \
               (resid[-1] < 0 and resid[-1] < resid[-2] and abs(resid[-1]) >= rel_edge_ratio * abs(min(resid[-2], 0.0))):
                extrema.append(int(i))
        else:
            edge_max = max(resid[i - 1], resid[i + 1], 0.0)
            edge_min = min(resid[i - 1], resid[i + 1], 0.0)
            if (resid[i] > 0 and resid[i] > resid[i - 1] and resid[i] > resid[i + 1] and resid[i] >= rel_edge_ratio * edge_max) or \
               (resid[i] < 0 and resid[i] < resid[i - 1] and resid[i] < resid[i + 1] and abs(resid[i]) >= rel_edge_ratio * abs(edge_min)):
                extrema.append(int(i))

    idx_sorted = np.array(sorted(extrema), dtype=int)

    # Enforce minimum separation by descending |z|
    if idx_sorted.size > 1 and int(min_separation) > 1:
        order_by_strength = idx_sorted[np.argsort(-np.abs(z[idx_sorted]))]
        keep: list[int] = []
        taken = np.zeros(n, dtype=bool)
        for i in order_by_strength:
            lo = max(0, int(i) - int(min_separation))
            hi = min(n, int(i) + int(min_separation) + 1)
            if not taken[lo:hi].any():
                keep.append(int(i))
                taken[lo:hi] = True
        idx_sorted = np.array(sorted(keep), dtype=int)

    if max_removals is not None and idx_sorted.size > int(max_removals):
        strongest = idx_sorted[np.argsort(-np.abs(z[idx_sorted]))][: int(max_removals)]
        idx_sorted = np.array(sorted(strongest), dtype=int)

    # Map back to original indices
    original_indices_sorted = np.where(mask)[0][order][idx_sorted]
    return original_indices_sorted.astype(int)


def apply_spike_mask(
    wave: np.ndarray,
    flux: np.ndarray,
    *,
    floor_z: float = 50.0,
    neg_floor_z: float | None = None,
    baseline_window: int = 501,
    baseline_width: float | None = None,
    rel_edge_ratio: float = 2.0,
    min_separation: int = 2,
    max_removals: int | None = None,
    min_abs_resid: float | None = None,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Remove spike indices and return cleaned (wave, flux) plus diagnostics dict."""
    idx_core = find_spike_indices(
        wave,
        flux,
        floor_z=floor_z,
        neg_floor_z=neg_floor_z,
        baseline_window=baseline_window,
        baseline_width=baseline_width,
        rel_edge_ratio=rel_edge_ratio,
        min_separation=min_separation,
        max_removals=max_removals,
        min_abs_resid=min_abs_resid,
    )
    if idx_core.size == 0:
        return wave, flux, {"removed_indices": np.array([], dtype=int), "core_indices": np.array([], dtype=int)}
    # Expand to include one bin before and after each detected spike index
    n = len(flux)
    expanded = set()
    for i in idx_core.tolist():
        expanded.add(int(i))
        if i - 1 >= 0:
            expanded.add(int(i - 1))
        if i + 1 < n:
            expanded.add(int(i + 1))
    idx_expanded = np.array(sorted(expanded), dtype=int)
    mask = np.ones(n, dtype=bool)
    mask[idx_expanded] = False
    return wave[mask], flux[mask], {"removed_indices": idx_expanded, "core_indices": idx_core}

# ------------------------------------------------------------------
# log-λ rebin, continuum spline  (unchanged from previous version)
# ------------------------------------------------------------------
def log_rebin(
    wave: NDArray[np.floating],
    fsrc: NDArray[np.floating],
) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
    """
    Log-grid rebinning routine:
      - Splits each input pixel [s0,s1] in linear λ
      - Maps its boundaries into log‐bin indices s0log, s1log
      - Distributes fsrc[l] * Δλ over all overlapping log‐bins
        in proportion to fractional overlap (alen/(s1log-s0log))
      - Converts the result to flux density by dividing by each bin's width
    Returns
    -------
    log_wave : 1-D array of length NW
        Bin centers on the log‐λ grid: W0 * exp(i * DWLOG), i=0..NW-1
    log_flux : 1-D array of length NW
        Flux density per Å on that grid
    """
    # 1) Ensure the global log-grid is set
    _ensure_grid()

    # 2) Grab grid params
    nlog  = NW
    w0    = W0
    dwlog = DWLOG

    # 3) Build output log‐wavelength axis
    log_wave = w0 * np.exp((np.arange(nlog) + 0.5) * dwlog)

    # 4) Prepare destination accumulator
    fdest = np.zeros(nlog, dtype=fsrc.dtype)

    # 5) Compute linear‐λ pixel edges s[k], k=0..len(wave)
    s = np.empty(wave.size + 1, dtype=float)
    s[1:-1] = 0.5 * (wave[:-1] + wave[1:])
    # extrapolate first/last
    s[0]    = 1.5 * wave[0] - 0.5 * wave[1]
    s[-1]   = 1.5 * wave[-1] - 0.5 * wave[-2]

    # 6) Map those edges into log-bin coordinates (1-indexed)
    slog = np.log(s / w0) / dwlog + 1.0

    # 7) Loop each source pixel ℓ
    for l in range(wave.size):
        s0log = slog[l]
        s1log = slog[l + 1]
        dλ     = s[l + 1] - s[l]   # Δλ for this pixel

        # Iterate bins covering the [s0log, s1log] interval
        i0 = max(1, int(np.floor(s0log)))
        i1 = min(nlog, int(np.floor(s1log)))

        width_log = (s1log - s0log)  # total width in log‐units
        for i in range(i0, i1 + 1):
            # overlap of [s0log,s1log] with bin i..i+1
            alen = min(s1log, i + 1.0) - max(s0log, float(i))
            if alen <= 0:
                continue
            # fraction of pixel's flux to put in this bin
            frac = alen / width_log
            fdest[i - 1] += fsrc[l] * frac * dλ

    # 8) Convert accumulated integrated flux into flux density per Å
    edges = w0 * np.exp((np.arange(nlog + 1) - 0.5) * dwlog)
    binw   = np.diff(edges)
    fdest  = fdest / binw

    return log_wave, fdest


def fit_continuum(
    flux: NDArray[np.floating],
    *,
    method: str = "spline",
    # spline args:
    knotnum: int = 13,
    izoff:    int = 0,
    edge_guard_frac: float = 0.02,
) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
    """
    Remove a smooth continuum from `flux` on the fixed log‐λ grid.

    Returns
    -------
    flat : flux/cont - 1
    cont : continuum estimate

    Parameters
    ----------
    method : "spline"
       - "spline": use the original SNID cubic‐spline (fit_continuum_spline) (DEFAULT)
    knotnum, izoff
      passed to fit_continuum_spline
    """
    if method == "spline":
        flat, cont = fit_continuum_spline(
            flux,
            knotnum=knotnum,
            izoff=izoff,
            edge_guard_frac=edge_guard_frac,
        )
    else:
        raise ValueError(f"Unknown method={method!r}; only 'spline' is supported")

    # ——— zero‐out anything outside the observed data range ———
    # find first/last valid data bins (including negative values for continuum-subtracted spectra)
    valid_indices = np.where((flux != 0) & np.isfinite(flux))[0]
    if valid_indices.size:
        i0, i1 = valid_indices[0], valid_indices[-1]
        # outside [i0,i1] we have no data → zero flat, unity continuum
        flat[:i0]   = 0.0
        flat[i1+1:] = 0.0
        cont[:i0]   = 0.0
        cont[i1+1:] = 0.0

    return flat, cont



def fit_continuum_spline(
    flux: NDArray[np.floating],
    knotnum: int = 13,
    izoff:    int = 0,
    *,
    edge_guard_frac: float = 0.02,
) -> Tuple[NDArray[np.floating], NDArray[np.floating]]:
    """
    Continuum removal and scaling steps:
      1) find usable range [l1..l2] by chopping off up to one zero
         or negative pixel at each end,
      2) place knots by averaging within kw = n//knotnum bins,
         with a phase offset istart = (izoff % kw) - kw,
      3) build a natural cubic spline through (xknot, yknot) in log10,
      4) evaluate the spline to get cont[i] = 10**spl(i),
      5) return flat = flux/cont - 1, plus cont itself.
    Parameters
    ----------
    flux : 1D array of flux (must be ≥0 for real data points)
    knotnum : number of average-knots
    izoff   : integer offset in log-bins
    Returns
    -------
    flat : flux with continuum removed (flat[i] = flux[i]/cont[i] - 1)
    cont : the continuum model sampled at every i (same shape as flux)
    """
    n = flux.size

    # trivial case
    if n < 10 or knotnum < 3:
        return np.zeros_like(flux), np.ones_like(flux)

    # --- 1) chop off up to one zero/neg at each end ---
    l1 = 0
    nuked = 0
    while l1 < n - 1 and (flux[l1] <= 0 or nuked < 1):
        if flux[l1] > 0:
            nuked += 1
        l1 += 1

    l2 = n - 1
    nuked = 0
    while l2 > 1 and (flux[l2] <= 0 or nuked < 1):
        if flux[l2] > 0:
            nuked += 1
        l2 -= 1

    if (l2 - l1) < 3 * knotnum:
        return np.zeros_like(flux), np.ones_like(flux)

    # --- 2) place knots using robust averages ---
    #
    # Edge-guard: spectrum ends are often junk (throughput roll-off / extraction artifacts).
    # We avoid letting the first/last knots be anchored to those bins by shrinking the
    # knot-placement window inside the usable region [l1..l2]. We still evaluate the spline
    # everywhere (full log grid); this only affects knot placement.
    usable = int(max(0, (l2 - l1 + 1)))
    try:
        eg = float(edge_guard_frac)
    except Exception:
        eg = 0.0
    eg = max(0.0, min(0.2, eg))  # keep it sane; 0.02 default
    guard = int(round(eg * usable))
    # Avoid guarding away too much (keep >= ~1/3 usable span)
    guard = max(0, min(guard, max(0, usable // 3)))
    l1_knot = int(l1 + guard)
    l2_knot = int(l2 - guard)
    # If we made the window too small to support knots, fall back to original.
    if (l2_knot - l1_knot) < 3 * knotnum:
        l1_knot, l2_knot = int(l1), int(l2)

    # Use log10(mean(flux)) per block (NOT mean(log10(flux))).
    kwidth = n // knotnum
    istart = ((izoff % kwidth) - kwidth) if izoff > 0 else 0

    xknot = []
    yknot = []
    nave = 0.0
    sum_x = 0.0
    sum_flux = 0.0

    for i in range(n):
        if l1_knot < i < l2_knot and flux[i] > 0:
            nave += 1.0
            sum_x += (i - 0.5)
            sum_flux += flux[i]
        if ((i - istart) % kwidth) == 0 and nave > 0:
            xknot.append(sum_x / nave)
            yknot.append(np.log10(sum_flux / nave))
            nave = 0.0
            sum_x = 0.0
            sum_flux = 0.0

    nk = len(xknot)
    if nk < 3:
        return np.zeros_like(flux), np.ones_like(flux)

    xknot = np.array(xknot, dtype=float)
    yknot = np.array(yknot, dtype=float)


    # --- 3) build spline second derivatives y2 ---
    h = np.diff(xknot)
    rhs = 6.0 * (
        (yknot[2:] - yknot[1:-1]) / h[1:]
      - (yknot[1:-1] - yknot[:-2]) / h[:-1]
    )
    A = 2.0 * (h[:-1] + h[1:])
    C = h[1:]

    u = np.empty_like(A)
    z = np.empty_like(rhs)
    u[0], z[0] = A[0], rhs[0]
    for i in range(1, len(rhs)):
        li = C[i-1] / u[i-1]
        u[i]  = A[i] - li * C[i-1]
        z[i]  = rhs[i] - li * z[i-1]

    y2 = np.zeros(nk, dtype=float)
    if len(rhs) > 0:
        y2[-2] = z[-1] / u[-1]
        for i in range(len(rhs)-2, -1, -1):
            y2[i+1] = (z[i] - C[i] * y2[i+2]) / u[i]


    # --- 4) evaluate spline to get continuum cont ---
    cont = np.empty(n, dtype=float)
    for j in range(n):
        xp = j - 0.5
        idx = np.clip(np.searchsorted(xknot, xp) - 1, 0, nk-2)
        h_i = xknot[idx+1] - xknot[idx]
        a = (xknot[idx+1] - xp) / h_i
        b = (xp - xknot[idx])   / h_i
        logc = (
            a * yknot[idx]
          + b * yknot[idx+1]
          + ((a**3 - a)*y2[idx] + (b**3 - b)*y2[idx+1]) * (h_i**2) / 6.0
        )
        with np.errstate(over='ignore'):
            cont[j] = float(np.power(10.0, logc))


    # --- 5) form normalized residuals ---
    flat = np.zeros_like(flux)
    mask = (flux > 0) & (cont > 0)
    flat[mask] = flux[mask] / cont[mask] - 1.0

    return flat, cont


# Strengthened gaussian edge handling is default

def unflatten_on_loggrid(flat_tpl: np.ndarray,
                         cont: np.ndarray) -> np.ndarray:
    """
    Given a template flux on the log-λ grid that has been flattened
    (i.e. continuum removed), restore it by multiplying back the
    continuum model.  flat_tpl must be on the same log_wave grid as cont.
    """
    return (flat_tpl + 1.0) * cont


def pad_to_NW(arr: np.ndarray, NW: int) -> np.ndarray:
    """Return an NW-long view: arr left-justified, rest filled with 0."""
    if arr.size == NW:
        return arr                     # already full length
    out = np.zeros(NW, arr.dtype)
    out[:arr.size] = arr
    return out


def prep_template(tpl_wave: np.ndarray, flux_tpl: np.ndarray, skip_if_rebinned: bool = False) -> np.ndarray:
    """
    Rebin the template onto the log-λ grid.
    
    Parameters
    ----------
    tpl_wave : np.ndarray
        Template wavelength array
    flux_tpl : np.ndarray  
        Template flux array
    skip_if_rebinned : bool, optional
        If True, skip rebinning if flux is already on standard grid
        
    Returns
    -------
    np.ndarray
        Rebinned flux array
    """
    # Check if already rebinned to standard grid
    if skip_if_rebinned and len(flux_tpl) == NW:
        _LOG.debug("Template already rebinned to standard grid, skipping rebinning")
        return flux_tpl
    
    _, rebinned_flux = log_rebin(tpl_wave, flux_tpl)
    return rebinned_flux

def flatten_spectrum(wave: np.ndarray, flux: np.ndarray, 
                    apodize_percent: float = 5.0,
                    median_filter_type: str = "none",
                    median_filter_value: float = 0.0,
                    num_points: int = 1024) -> Dict[str, np.ndarray]:
    """
    Flatten a spectrum by removing continuum and applying log rebinning.
    
    Parameters:
        wave: Wavelength array
        flux: Flux array
        apodize_percent: Percentage of spectrum ends to apodize
        median_filter_type: Type of smoothing filter ("none", "pixel", "angstrom")
                           Uses Savitzky-Golay filtering
        median_filter_value: Value for smoothing filter (window size or FWHM)
        num_points: Number of points in log grid
        
    Returns:
        Dict containing processed wavelength and flux arrays
    """
    # Ensure flux satisfies the ≥0 requirement expected by the SNID continuum fitter.
    try:
        flux, flux_offset = enforce_positive_flux(flux)
        if flux_offset != 0.0:
            _LOG.info(
                "flatten_spectrum: shifted template flux up by %.6g "
                "to remove non-positive values before continuum fitting",
                flux_offset,
            )
    except Exception as e:
        _LOG.warning("flatten_spectrum: positive-flux enforcement failed (%s); proceeding without shift", e)
        flux_offset = 0.0

    # Apply apodization if requested (requires valid region indices)
    if apodize_percent > 0:
        try:
            valid_mask = (flux != 0) & np.isfinite(flux)
            if np.any(valid_mask):
                n1 = int(np.argmax(valid_mask))
                n2 = int(len(flux) - 1 - np.argmax(valid_mask[::-1]))
                flux = apodize(flux, n1, n2, percent=apodize_percent)
        except Exception:
            # If anything goes wrong, skip apodization
            pass
    
    # Apply Savitzky-Golay filtering if requested (replaces old median filtering)
    if median_filter_type != "none" and median_filter_value > 0:
        if median_filter_type == "pixel":
            # Pixel-based Savitzky-Golay filter (3rd order polynomial)
            window_length = max(3, int(median_filter_value))
            flux = savgol_filter_fixed(flux, window_length, polyorder=3)
    
    # Apply log rebinning (grid size comes from init_wavelength_grid)
    log_wave, log_flux = log_rebin(wave, flux)
    
    # Fit and remove continuum
    flat_flux, continuum = fit_continuum(log_flux, method="spline")
    
    return {
        'wave': log_wave,
        'flux': flat_flux,
        'continuum': continuum,
        'original_wave': wave,
        'original_flux': flux
    }

__all__ = [
    "init_wavelength_grid",
    "clip_aband", "clip_sky_lines", "clip_host_emission_lines",
    "apply_wavelength_mask",
    "log_rebin", "log_rebin_maskaware", "fit_continuum", "fit_continuum_spline", "apodize", "unflatten_on_loggrid", "prep_template", "flatten_spectrum",
    "enforce_positive_flux",
    "compute_mask_on_loggrid",
]
