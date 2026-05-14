"""Display-only spectrum trimming helpers for GUI views."""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('gui.display_spectrum')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('gui.display_spectrum')


def _same_length_array(value, expected_size: int):
    try:
        arr = np.asarray(value, dtype=float)
        if arr.size == expected_size:
            return arr
    except Exception:
        pass
    return None


def _display_support_mask(flux_arr: np.ndarray, processed_spectrum: Optional[Dict[str, Any]]):
    support_mask = np.isfinite(flux_arr) & (flux_arr != 0)

    if not processed_spectrum:
        return support_mask

    # Flux view can be reconstructed as positive continuum where the apodized
    # flat spectrum is zero. Use flat/apodized arrays as the display support so
    # cut ends stay hidden in both Flux and Flat views.
    for key in ('flat_view', 'display_flat', 'tapered_flux', 'flat_flux'):
        support_arr = _same_length_array(processed_spectrum.get(key), flux_arr.size)
        if support_arr is not None:
            return np.isfinite(support_arr) & (support_arr != 0)

    return support_mask


def filter_processed_spectrum_display_range(wave, flux, processed_spectrum: Optional[Dict[str, Any]] = None):
    """Trim display-only leading/trailing padding from a processed spectrum."""
    try:
        wave_arr = np.asarray(wave, dtype=float)
        flux_arr = np.asarray(flux, dtype=float)

        if wave_arr.size == 0 or flux_arr.size == 0 or wave_arr.size != flux_arr.size:
            return wave, flux

        valid_mask = np.isfinite(wave_arr) & np.isfinite(flux_arr)
        valid_mask &= _display_support_mask(flux_arr, processed_spectrum)

        if processed_spectrum:
            mask_logbins = processed_spectrum.get('mask_logbins')
            if mask_logbins is not None:
                try:
                    mask_arr = np.asarray(mask_logbins, dtype=bool)
                    if mask_arr.size == valid_mask.size:
                        valid_mask &= ~mask_arr
                except Exception:
                    pass

        if not np.any(valid_mask):
            return wave_arr, flux_arr

        left_edge = int(np.argmax(valid_mask))
        right_edge = int(valid_mask.size - 1 - np.argmax(valid_mask[::-1]))

        if processed_spectrum:
            try:
                stored_left = int(processed_spectrum.get('left_edge', left_edge))
                stored_right = int(processed_spectrum.get('right_edge', right_edge))
                if 0 <= stored_left <= stored_right < valid_mask.size:
                    left_edge = max(left_edge, stored_left)
                    right_edge = min(right_edge, stored_right)
            except Exception:
                pass

        if left_edge <= right_edge:
            return wave_arr[left_edge:right_edge + 1], flux_arr[left_edge:right_edge + 1]

        return wave_arr, flux_arr
    except Exception as e:
        _LOGGER.warning(f"Warning: Error filtering display spectrum: {e}")
        return wave, flux


def clip_spectrum_to_reference_range(wave, flux, reference_wave):
    """Clip a spectrum to the finite wavelength span of a reference spectrum."""
    try:
        wave_arr = np.asarray(wave, dtype=float)
        flux_arr = np.asarray(flux, dtype=float)
        ref_arr = np.asarray(reference_wave, dtype=float)

        if wave_arr.size == 0 or flux_arr.size == 0 or wave_arr.size != flux_arr.size:
            return wave, flux

        finite_ref = ref_arr[np.isfinite(ref_arr)]
        if finite_ref.size == 0:
            return wave_arr, flux_arr

        ref_min = float(np.min(finite_ref))
        ref_max = float(np.max(finite_ref))
        keep = np.isfinite(wave_arr) & np.isfinite(flux_arr) & (wave_arr >= ref_min) & (wave_arr <= ref_max)
        if np.any(keep):
            return wave_arr[keep], flux_arr[keep]

        return wave_arr, flux_arr
    except Exception as e:
        _LOGGER.warning(f"Warning: Error clipping spectrum to reference range: {e}")
        return wave, flux
