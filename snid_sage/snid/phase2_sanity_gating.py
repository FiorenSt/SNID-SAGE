"""
Phase-2 sanity redshift gating helpers.

These gates are applied *after* strict Phase-2 [zmin, zmax] filtering and *before*
Phase-2 metrics/clustering. They prevent physically unrealistic template types from
dominating clustering and downstream visualizations.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np


def apply_phase2_sanity_redshift_gates(
    matches: List[Dict[str, Any]],
    *,
    forced_redshift: Optional[float],
    logger,
    star_cv_zmax: float = 0.01,
    gap_lowz_zmax: float = 0.025,
    gap_lowz_subtypes: Iterable[str] = ("ILRT", "LBV", "LRN"),
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Apply Phase-2 sanity gates for Star/CV and GAP low-z subtypes.

    Parameters
    ----------
    matches:
        SNID match dicts (post Phase-2 strict [zmin, zmax] filtering).
    forced_redshift:
        If not None, a user-forced redshift. If |forced_redshift| exceeds a gate cap,
        all matches belonging to that gated family are removed (since the analysis is
        being forced into an unphysical region for those types).
    logger:
        Logger used for concise info messages.

    Returns
    -------
    (filtered_matches, trace_updates)
        `trace_updates` includes the number of filtered matches for each gate:
        - phase2_star_cv_redshift_filtered
        - phase2_gap_lowz_redshift_filtered
    """
    if not matches:
        return [], {
            "phase2_star_cv_redshift_filtered": 0,
            "phase2_gap_lowz_redshift_filtered": 0,
            "phase2_match_count_after_star_cv_filter": 0,
            "phase2_match_count_after_gap_lowz_filter": 0,
        }

    # Normalize subtype tokens we want to catch for GAP low-z transients
    try:
        gap_tokens = {str(s).strip().upper() for s in gap_lowz_subtypes if str(s).strip()}
    except Exception:
        gap_tokens = {"ILRT", "LBV", "LRN"}

    # Determine whether forced redshift violates each gate (best-effort).
    try:
        forced_star_cv_too_high = (forced_redshift is not None) and (abs(float(forced_redshift)) > float(star_cv_zmax))
    except Exception:
        forced_star_cv_too_high = False
    try:
        forced_gap_too_high = (forced_redshift is not None) and (abs(float(forced_redshift)) > float(gap_lowz_zmax))
    except Exception:
        forced_gap_too_high = False

    filtered: List[Dict[str, Any]] = []
    star_cv_filtered = 0
    gap_lowz_filtered = 0
    kept_after_star_cv = 0

    for m in matches:
        # Extract template type/subtype defensively
        try:
            tpl = m.get("template", {})
        except Exception:
            tpl = {}
        if not isinstance(tpl, dict):
            tpl = {}

        try:
            tpl_type = str(tpl.get("type", "Unknown") or "").strip().lower()
        except Exception:
            tpl_type = "unknown"
        try:
            tpl_subtype_raw = str(tpl.get("subtype", "") or "")
        except Exception:
            tpl_subtype_raw = ""

        # Pull match redshift once (best-effort).
        try:
            z = float(m.get("redshift", float("nan")))
        except Exception:
            z = float("nan")

        # ------------------------------------------------------------------
        # Gate 1: Star/CV sanity cap
        # ------------------------------------------------------------------
        keep_after_star = True
        if tpl_type in ("star", "cv"):
            if forced_star_cv_too_high:
                star_cv_filtered += 1
                keep_after_star = False
            elif np.isfinite(z) and (abs(z) > float(star_cv_zmax)):
                star_cv_filtered += 1
                keep_after_star = False

        if not keep_after_star:
            continue

        kept_after_star_cv += 1

        # ------------------------------------------------------------------
        # Gate 2: GAP ILRT/LBV/LRN low-z sanity cap
        # ------------------------------------------------------------------
        if tpl_type == "gap":
            # Tokenize conservatively (handles "GAP LRN", "LRN (foo)", "ILRT-like", etc.)
            sub_u = tpl_subtype_raw.strip().upper()
            for sep in ("/", "-", "_", "(", ")", "[", "]", "{", "}", ",", ":", ";"):
                sub_u = sub_u.replace(sep, " ")
            sub_tokens = {t for t in sub_u.split() if t}

            is_gap_lowz = bool(sub_tokens.intersection(gap_tokens))
            if is_gap_lowz:
                if forced_gap_too_high:
                    gap_lowz_filtered += 1
                    continue
                if np.isfinite(z) and (abs(z) > float(gap_lowz_zmax)):
                    gap_lowz_filtered += 1
                    continue

        # Keep match after sanity gates
        filtered.append(m)

    if star_cv_filtered:
        try:
            logger.info(
                "Phase 2: Filtered %d Star/CV matches with |z| > %.6f before metrics/clustering",
                int(star_cv_filtered),
                float(star_cv_zmax),
            )
        except Exception:
            pass
    if gap_lowz_filtered:
        try:
            logger.info(
                "Phase 2: Filtered %d GAP (ILRT/LBV/LRN) matches with |z| > %.6f before metrics/clustering",
                int(gap_lowz_filtered),
                float(gap_lowz_zmax),
            )
        except Exception:
            pass

    return filtered, {
        "phase2_star_cv_redshift_filtered": int(star_cv_filtered),
        "phase2_gap_lowz_redshift_filtered": int(gap_lowz_filtered),
        # Convenience counts (kept for backwards-compatible trace reporting)
        "phase2_match_count_after_star_cv_filter": int(kept_after_star_cv),
        "phase2_match_count_after_gap_lowz_filter": int(len(filtered)),
    }

