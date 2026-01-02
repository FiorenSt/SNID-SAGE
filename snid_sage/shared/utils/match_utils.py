"""
Utilities for extracting robust per-match fields used across SNID SAGE.

Currently includes:
- extract_redshift_sigma: robust extraction of per-match redshift uncertainty
  with sensible fallbacks when explicit uncertainties are missing.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

# Global scaling for redshift uncertainties; fixed to 1.0 (no configurability).
Z_K = 1.0


def extract_redshift_sigma(match: Dict[str, Any]) -> float:
    """
    Extract a per-match redshift uncertainty with robust fallbacks.

    Tries common keys first; if unavailable, derives a conservative
    proxy from the best similarity metric; final fallback is a small
    constant.
    """
    # Common alternative keys observed in data/products
    for key in ("redshift_uncertainty", "z_unc", "sigma_z", "z_err", "redshift_error"):
        try:
            val = match.get(key)
            if isinstance(val, (int, float)):
                v = float(val)
                if np.isfinite(v) and v > 0:
                    return v
        except Exception:
            # Continue probing other keys
            pass

    # Fallback: derive a loose proxy from similarity metric.
    # Higher metric -> smaller sigma; keep a conservative upper bound.
    # Note: metric scale is HσLAP-CCC (preferred) or HLAP fallback.
    try:
        from snid_sage.shared.utils.math_utils import get_best_metric_value  # lazy import

        m = float(get_best_metric_value(match))
        if np.isfinite(m) and m > 0:
            return float(Z_K * 0.02 / np.sqrt(1.0 + m))
    except Exception:
        pass

    # Final conservative fallback
    return 0.02 * Z_K


__all__ = ["extract_redshift_sigma"]


