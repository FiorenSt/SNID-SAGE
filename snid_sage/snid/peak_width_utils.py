"""
Peak-width utilities for SNID-SAGE (pipeline-facing).

This module provides a robust, **non-Gaussian** half-height FWHM estimator for
correlation peaks, plus the standard conversion to Δz:

    width_dz = fwhm_bins * DWLOG * (1 + z)
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np


def _halfheight_fwhm_from_peak(
    x: np.ndarray,
    y: np.ndarray,
    *,
    peak_idx: int,
    baseline: float = 0.0,
) -> Dict[str, float]:
    """
    Direct (non-Gaussian) half-height FWHM around a peak.

    half-height level:
        y_half = baseline + 0.5 * (y_peak - baseline)

    Finds nearest left/right crossings around peak_idx and linearly interpolates
    their x positions.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = int(y.size)
    if n < 5 or x.size != y.size:
        return {
            "x_left_half": float("nan"),
            "x_right_half": float("nan"),
            "fwhm_x": float("nan"),
            "y_half": float("nan"),
            "y_peak": float("nan"),
        }

    p = int(np.clip(int(peak_idx), 0, max(0, n - 1)))
    b = float(baseline) if np.isfinite(baseline) else 0.0
    y_peak = float(y[p])
    if not np.isfinite(y_peak) or not (y_peak > b):
        return {
            "x_left_half": float("nan"),
            "x_right_half": float("nan"),
            "fwhm_x": float("nan"),
            "y_half": float("nan"),
            "y_peak": float(y_peak),
        }

    y_half = float(b + 0.5 * (y_peak - b))
    x_left = float("nan")
    x_right = float("nan")

    # Left crossing: y[i] >= y_half and y[i-1] < y_half
    for i in range(p, 0, -1):
        y0 = float(y[i - 1])
        y1 = float(y[i])
        if not (np.isfinite(y0) and np.isfinite(y1)):
            continue
        if (y1 >= y_half) and (y0 < y_half):
            x0 = float(x[i - 1])
            x1 = float(x[i])
            if np.isfinite(x0) and np.isfinite(x1) and (y1 - y0) != 0:
                t = float((y_half - y0) / (y1 - y0))
                x_left = float(x0 + t * (x1 - x0))
            else:
                x_left = float(x[i])
            break

    # Right crossing: y[i] >= y_half and y[i+1] < y_half
    for i in range(p, n - 1):
        y0 = float(y[i])
        y1 = float(y[i + 1])
        if not (np.isfinite(y0) and np.isfinite(y1)):
            continue
        if (y0 >= y_half) and (y1 < y_half):
            x0 = float(x[i])
            x1 = float(x[i + 1])
            if np.isfinite(x0) and np.isfinite(x1) and (y1 - y0) != 0:
                t = float((y_half - y0) / (y1 - y0))
                x_right = float(x0 + t * (x1 - x0))
            else:
                x_right = float(x[i])
            break

    fwhm_x = float(x_right - x_left) if (np.isfinite(x_left) and np.isfinite(x_right)) else float("nan")
    if not (np.isfinite(fwhm_x) and fwhm_x > 0.0):
        fwhm_x = float("nan")

    return {
        "x_left_half": float(x_left),
        "x_right_half": float(x_right),
        "fwhm_x": float(fwhm_x),
        "y_half": float(y_half),
        "y_peak": float(y_peak),
    }


def halfheight_fwhm_bins_from_corr(
    corr: np.ndarray,
    *,
    peak_idx: int,
    window_radius_bins: int = 200,
    baseline: float = 0.0,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute half-height FWHM (in lag-bin units) for a correlation array.

    Assumes the correlation is in "rolled" form where the zero-lag index is n//2,
    i.e. the typical SNID phase-2 convention.
    """
    c = np.asarray(corr, dtype=float)
    if c.size < 7 or not np.any(np.isfinite(c)):
        return float("nan"), {"fwhm_bins": float("nan")}

    n = int(c.size)
    mid = int(n // 2)
    lag_bins = np.arange(n, dtype=float) - float(mid)

    p = int(np.clip(int(peak_idx), 0, max(0, n - 1)))
    rad = int(min(int(window_radius_bins), max(40, n // 6)))
    lo = max(0, p - rad)
    hi = min(n, p + rad + 1)

    xw = lag_bins[lo:hi]
    yw = c[lo:hi]
    peak_w = int(p - lo)

    hh = _halfheight_fwhm_from_peak(xw, yw, peak_idx=int(peak_w), baseline=float(baseline))
    fwhm_bins = float(hh.get("fwhm_x", float("nan")))

    extras = {
        "fwhm_bins": float(fwhm_bins),
        "fwhm_x_left": float(hh.get("x_left_half", float("nan"))),
        "fwhm_x_right": float(hh.get("x_right_half", float("nan"))),
        "y_half": float(hh.get("y_half", float("nan"))),
        "y_peak": float(hh.get("y_peak", float("nan"))),
        "mid": float(mid),
        "window_lo": float(lo),
        "window_hi": float(hi),
    }
    return fwhm_bins if (np.isfinite(fwhm_bins) and fwhm_bins > 0.0) else float("nan"), extras


def width_dz_from_fwhm_bins(fwhm_bins: float, *, dwlog: float, z: float) -> float:
    """Convert FWHM in lag bins to Δz width: fwhm_bins * dwlog * (1+z)."""
    try:
        fb = float(fwhm_bins)
        dw = float(dwlog)
        zz = float(z)
    except Exception:
        return float("nan")
    if not (np.isfinite(fb) and fb > 0.0 and np.isfinite(dw) and dw > 0.0 and np.isfinite(zz)):
        return float("nan")
    out = float(fb * dw * (1.0 + zz))
    return out if (np.isfinite(out) and out > 0.0) else float("nan")


