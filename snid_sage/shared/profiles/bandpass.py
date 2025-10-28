from __future__ import annotations

from typing import Tuple
from .types import BandpassSpec


def k_indices(N: int, bandpass: BandpassSpec) -> Tuple[int, int, int, int]:
    """Map fractional k to integer indices for FFT band-pass.

    Uses round(k*N) then clamps, orders, and enforces k4 <= N//2.
    """
    n = int(N)
    if n <= 0:
        return 0, 0, 0, 0

    def _r(x: float) -> int:
        try:
            return int(round(float(x) * n))
        except Exception:
            return 0

    i1 = _r(bandpass.k1)
    i2 = _r(bandpass.k2)
    i3 = _r(bandpass.k3)
    i4 = _r(bandpass.k4)

    # Clamp to valid range [0, n//2]
    half = n // 2
    i1 = max(0, min(i1, half))
    i2 = max(0, min(i2, half))
    i3 = max(0, min(i3, half))
    i4 = max(0, min(i4, half))

    # Enforce ordering
    i1, i2 = sorted((i1, i2))
    i3, i4 = sorted((i3, i4))
    if i2 < i1:
        i2 = i1
    if i3 < i2:
        i3 = i2
    if i4 < i3:
        i4 = i3

    return i1, i2, i3, i4


