from __future__ import annotations

from .types import Profile, GridSpec, BandpassSpec
from .registry import register_profile


def _optical_profile() -> Profile:
    # Choose fractions that round to historical integers for NW=1024: 1,4, NW//12, NW//10
    # For rounding stability near edges, pick slightly offset fractions.
    nw = 1024
    k1 = 1 / nw
    k2 = 4 / nw
    k3 = (nw // 12) / nw
    k4 = (nw // 10) / nw
    return Profile(
        id="optical",
        version="1.0.0",
        grid=GridSpec(min_wave_A=2500.0, max_wave_A=10000.0, nw=nw),
        bandpass=BandpassSpec(k1=k1, k2=k2, k3=k3, k4=k4),
        masks=[],
        apodization_edge_fraction=None,
        fft_length=None,
    )


def _onir_profile() -> Profile:
    # Tonry-style bandpass mapping for ONIR grid (N=2048):
    # keep k1=1/N, k2=4/N; scale k3,k4 to N/12, N/10
    nw = 2048
    k1 = 1 / nw
    k2 = 4 / nw
    k3 = (nw // 12) / nw
    k4 = (nw // 10) / nw
    return Profile(
        id="onir",
        version="1.0.2",
        grid=GridSpec(min_wave_A=2000.0, max_wave_A=25000.0, nw=nw),
        bandpass=BandpassSpec(k1=k1, k2=k2, k3=k3, k4=k4),
        masks=[],
        apodization_edge_fraction=None,
        fft_length=None,
    )


def register_builtins() -> None:
    register_profile(_optical_profile())
    register_profile(_onir_profile())


