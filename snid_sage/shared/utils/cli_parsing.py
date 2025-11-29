"""
CLI parsing utilities for SNID SAGE.

Currently provides robust parsing for wavelength mask arguments that
are passed via the command-line interfaces (identify, batch).
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple


def parse_wavelength_mask_args(
    raw_masks: Optional[Sequence[str]],
) -> Optional[List[Tuple[float, float]]]:
    """
    Parse CLI --wavelength-masks arguments into a list of (start, end) tuples.

    Supports flexible input formats for convenience:
      - Separate arguments:  --wavelength-masks 6550:6600 7600:7700
      - Comma/semicolon separated within a single argument:
            --wavelength-masks "6550:6600,7600:7700"
      - Either ':' or '-' as range separator: 4000:5000 or 4000-5000

    Any invalid entries are skipped rather than raising, so that a single
    malformed mask does not abort the entire run.

    Parameters
    ----------
    raw_masks : sequence of str or None
        Raw values from argparse for --wavelength-masks.

    Returns
    -------
    list of (float, float) or None
        Parsed wavelength ranges, or None if no valid masks were provided.
    """
    if not raw_masks:
        return None

    parsed: List[Tuple[float, float]] = []

    def _iter_parts(items: Iterable[str]) -> Iterable[str]:
        """Split items on commas/semicolons and strip whitespace."""
        for item in items:
            if not item:
                continue
            # Allow users to pass comma/semicolon separated masks inside one arg
            for part in str(item).replace(";", ",").split(","):
                part = part.strip()
                if part:
                    yield part

    for part in _iter_parts(raw_masks):
        # Try ":" first (documented form), then "-" as alternative
        if ":" in part:
            pieces = part.split(":")
        elif "-" in part:
            pieces = part.split("-")
        else:
            # Not a range; ignore silently
            continue

        if len(pieces) != 2:
            continue

        try:
            start = float(pieces[0].strip())
            end = float(pieces[1].strip())
        except (TypeError, ValueError):
            continue

        if not (start < end):
            # Degenerate or reversed range; ignore
            continue

        parsed.append((start, end))

    return parsed or None


