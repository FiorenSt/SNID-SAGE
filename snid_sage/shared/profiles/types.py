from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Literal


@dataclass(frozen=True)
class BandpassSpec:
    k1: float
    k2: float
    k3: float
    k4: float


@dataclass(frozen=True)
class GridSpec:
    min_wave_A: float
    max_wave_A: float
    nw: int
    log_base: Literal["ln"] = "ln"


@dataclass(frozen=True)
class MaskSpec:
    start_A: float
    end_A: float
    feather_A: float


@dataclass(frozen=True)
class Profile:
    id: str
    version: str
    grid: GridSpec
    bandpass: BandpassSpec
    masks: List[MaskSpec]
    apodization_edge_fraction: Optional[float] = None
    fft_length: Optional[int] = None


