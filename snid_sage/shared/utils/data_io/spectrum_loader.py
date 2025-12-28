"""
Spectrum Loader Module for SNID SAGE
====================================

Unified spectrum loading functionality supporting multiple file formats:
- ASCII/text files (.txt, .dat, .ascii, .asci, .csv, .flm)
- FITS files (.fits, .fit)
- Various delimited formats

This module provides a consistent interface for loading spectrum data
regardless of the file format.
"""

import os
import numpy as np
from typing import Tuple, Optional, Dict, Any
import warnings
from pathlib import Path

from snid_sage.shared.types.spectrum_types import SpectrumData, SpectrumFormat
from snid_sage.shared.exceptions.core_exceptions import SpectrumLoadError

# Use centralized logging system
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('data_io.spectrum_loader')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('data_io.spectrum_loader')


def load_spectrum(filename: str, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load a spectrum from various file formats.
    
    Parameters:
        filename (str): Path to spectrum file
        **kwargs: Additional arguments passed to format-specific loaders
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
        
    Raises:
        SpectrumLoadError: If the file cannot be loaded or parsed
    """
    if not os.path.exists(filename):
        raise SpectrumLoadError(f"File not found: {filename}")
    
    file_ext = Path(filename).suffix.lower()
    
    try:
        if file_ext in ['.fits', '.fit']:
            return load_fits_spectrum(filename, **kwargs)
        else:
            return load_text_spectrum(filename, **kwargs)
    except Exception as e:
        raise SpectrumLoadError(f"Failed to load spectrum from {filename}: {str(e)}")


def load_fits_spectrum(filename: str, band: int = 0, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load a spectrum from a FITS file.
    
    Parameters:
        filename (str): Path to FITS file
        band (int): Which band/extension to load (default: 0 for primary spectrum)
        **kwargs: Additional arguments (for compatibility)
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
        
    Raises:
        SpectrumLoadError: If FITS file cannot be loaded or parsed
    """
    try:
        from astropy.io import fits
    except ImportError:
        raise SpectrumLoadError(
            "FITS file support requires astropy. Please install astropy: pip install astropy"
        )
    
    try:
        with fits.open(filename) as hdul:
            primary = hdul[0]
            primary_header = primary.header
            data = primary.data

            # Helper to merge primary and extension headers (extension overrides primary)
            def _merge_headers_dict(hdr_primary, hdr_ext):
                merged = {}
                try:
                    for k in hdr_primary.keys():
                        merged[k] = hdr_primary.get(k)
                except Exception:
                    pass
                try:
                    for k in hdr_ext.keys():
                        merged[k] = hdr_ext.get(k)
                except Exception:
                    pass
                return merged

            # If primary HDU has no data, look for the first HDU with usable data
            chosen_hdu = None
            if data is not None:
                chosen_hdu = primary
            else:
                # Prefer an IMAGE-like HDU with numpy array data
                try:
                    from astropy.io.fits import ImageHDU
                    try:
                        from astropy.io.fits.hdu.compressed import CompImageHDU
                    except Exception:
                        CompImageHDU = tuple()  # type: ignore
                    image_like_types = (ImageHDU,)
                    if CompImageHDU:
                        image_like_types = (ImageHDU, CompImageHDU)  # type: ignore
                except Exception:
                    image_like_types = tuple()

                for hdu in hdul[1:]:
                    # Skip table HDUs here; we'll handle them in the table branch below
                    if image_like_types and not isinstance(hdu, image_like_types):
                        continue
                    if getattr(hdu, 'data', None) is not None:
                        try:
                            arr = np.asarray(hdu.data)
                            if arr.size > 0 and arr.dtype.fields is None:
                                chosen_hdu = hdu
                                break
                        except Exception:
                            continue

                # If still not found, try table HDUs with columns like wavelength/flux
                if chosen_hdu is None:
                    for hdu in hdul[1:]:
                        try:
                            from astropy.io.fits.hdu.table import BinTableHDU, TableHDU
                            if isinstance(hdu, (BinTableHDU, TableHDU)):
                                # Build a case-insensitive name map
                                names = hdu.columns.names or []
                                name_map = {str(n).lower(): str(n) for n in names}
                                colnames = set(name_map.keys())
                                wave_candidates = [
                                    'wave', 'wavelength', 'lambda', 'lam', 'wl', 'angstrom', 'ang'
                                ]
                                flux_candidates = [
                                    'flux', 'fnu', 'flam', 'counts', 'spec', 'spectrum', 'intensity'
                                ]
                                wave_key = next((c for c in wave_candidates if c in colnames), None)
                                flux_key = next((c for c in flux_candidates if c in colnames), None)
                                if wave_key and flux_key:
                                    tbl = hdu.data
                                    wave_name = name_map[wave_key]
                                    flux_name = name_map[flux_key]

                                    # Extract possibly vector-valued columns; prefer first row if multiple
                                    wave_col = tbl[wave_name]
                                    flux_col = tbl[flux_name]

                                    # Helper to convert a column that may be an array of vectors
                                    def _to_1d_vector(col):
                                        arr = np.asarray(col)
                                        # If 2D with single row, take first row
                                        if arr.ndim == 2 and arr.shape[0] == 1:
                                            return np.asarray(arr[0], dtype=float)
                                        # If 1D object array (vector per row), take first element
                                        if arr.ndim == 1 and arr.dtype == object:
                                            return np.asarray(arr[0], dtype=float)
                                        # Fallback: flatten
                                        return np.asarray(arr, dtype=float).squeeze()

                                    wavelength = _to_1d_vector(wave_col)
                                    flux = _to_1d_vector(flux_col)

                                    wavelength, flux = _validate_and_clean_arrays(wavelength, flux)
                                    _LOGGER.info(
                                        f"✅ FITS table spectrum loaded from HDU '{getattr(hdu, 'name', '')}': {len(wavelength)} points"
                                    )
                                    return wavelength, flux
                        except Exception:
                            continue

            if chosen_hdu is None:
                raise SpectrumLoadError("FITS file contains no data")

            # Use chosen HDU for image-like data
            hdu_data = np.asarray(chosen_hdu.data)
            header = _merge_headers_dict(primary_header, chosen_hdu.header)

            # If this is actually a table (structured dtype), route through table logic
            if hdu_data.dtype.fields is not None:
                # Attempt to find vector columns in this HDU
                try:
                    from astropy.io.fits.hdu.table import BinTableHDU, TableHDU
                    if isinstance(chosen_hdu, (BinTableHDU, TableHDU)):
                        names = chosen_hdu.columns.names or []
                        name_map = {str(n).lower(): str(n) for n in names}
                        colnames = set(name_map.keys())
                        wave_candidates = ['wave', 'wavelength', 'lambda', 'lam', 'wl', 'angstrom', 'ang']
                        flux_candidates = ['flux', 'fnu', 'flam', 'counts', 'spec', 'spectrum', 'intensity']
                        wave_key = next((c for c in wave_candidates if c in colnames), None)
                        flux_key = next((c for c in flux_candidates if c in colnames), None)
                        if wave_key and flux_key:
                            tbl = chosen_hdu.data
                            wave_name = name_map[wave_key]
                            flux_name = name_map[flux_key]

                            def _to_1d_vector_any(col):
                                arr = np.asarray(col)
                                if arr.ndim == 2:
                                    return np.asarray(arr[0], dtype=float)
                                if arr.dtype == object and arr.ndim == 1:
                                    return np.asarray(arr[0], dtype=float)
                                return np.asarray(arr, dtype=float)

                            wavelength = _to_1d_vector_any(tbl[wave_name])
                            flux = _to_1d_vector_any(tbl[flux_name])
                            wavelength, flux = _validate_and_clean_arrays(wavelength, flux)
                            _LOGGER.info(
                                f"✅ FITS table spectrum loaded from chosen HDU '{getattr(chosen_hdu, 'name', '')}': {len(wavelength)} points"
                            )
                            return wavelength, flux
                except Exception:
                    pass

            # Handle different data structures
            if hdu_data.ndim == 1:
                flux = hdu_data
                wavelength = _construct_wavelength_axis(header, len(flux))

            elif hdu_data.ndim == 2:
                if hdu_data.shape[0] == 2:
                    wavelength = hdu_data[0]
                    flux = hdu_data[1]
                elif hdu_data.shape[1] == 2:
                    wavelength = hdu_data[:, 0]
                    flux = hdu_data[:, 1]
                else:
                    flux = hdu_data[0] if hdu_data.shape[0] < hdu_data.shape[1] else hdu_data[:, 0]
                    wavelength = _construct_wavelength_axis(header, len(flux))

            elif hdu_data.ndim == 3:
                # Validate band selection
                if band >= hdu_data.shape[0]:
                    available_bands = hdu_data.shape[0]
                    warnings.warn(
                        f"Band {band} requested but only {available_bands} bands available. Using band 0."
                    )
                    band = 0
                flux = hdu_data[band, 0, :]
                wavelength = _construct_wavelength_axis(header, len(flux))

                band_info = _get_band_info(header, band)
                if band_info:
                    _LOGGER.info(f"✅ Loaded FITS band {band}: {band_info}")

            else:
                raise SpectrumLoadError(f"Unsupported FITS data dimensions: {hdu_data.ndim}D")

            # Validate the extracted data
            wavelength, flux = _validate_and_clean_arrays(wavelength, flux)

            _LOGGER.info(
                f"✅ FITS spectrum loaded: {len(wavelength)} points, λ = {wavelength[0]:.1f}-{wavelength[-1]:.1f} Å"
            )

            return wavelength, flux
            
    except SpectrumLoadError:
        raise
    except Exception as e:
        raise SpectrumLoadError(f"Error reading FITS file {filename}: {str(e)}")


def load_text_spectrum(filename: str, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load a spectrum from a text file.
    
    Parameters:
        filename (str): Path to text file
        **kwargs: Additional arguments for numpy.loadtxt
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
        
    Raises:
        SpectrumLoadError: If text file cannot be loaded or parsed
    """
    def _count_leading_header_lines(path: str, max_lines: int = 10) -> int:
        """
        Count how many initial non-empty, non-comment lines look like headers.

        This handles cases like:
          wave,flux,flux_err
          wavelength,flux,
          3500.0,1.23e-16,
        """
        def _is_numeric_data_line(line: str) -> bool:
            # Normalize common delimiters and tolerate trailing delimiters / empty last column
            s = line.replace('"', '').strip().rstrip(',;')
            s = s.replace(',', ' ').replace('\t', ' ').replace(';', ' ')
            parts = [p for p in s.split() if p]
            if len(parts) < 2:
                return False
            try:
                float(parts[0])
                float(parts[1])
                return True
            except Exception:
                return False

        header_lines = 0
        with open(path, 'r', encoding='utf-8-sig', errors='ignore') as fh:
            for _ in range(max_lines):
                raw = fh.readline()
                if not raw:
                    break
                s = raw.strip()
                if not s:
                    continue
                if s.lstrip().startswith('#'):
                    continue
                if _is_numeric_data_line(s):
                    break  # First numeric data line -> stop
                header_lines += 1
        return header_lines

    # First, check if file has headers by examining the first line
    try:
        # Be explicit about encoding to avoid silently skipping header detection on UTF-8/BOM files
        with open(filename, 'r', encoding='utf-8-sig', errors='ignore') as f:
            first_line = f.readline().strip()
            # Detect delimiter (comma, tab, semicolon, or whitespace)
            delimiter = ',' if ',' in first_line else ('\t' if '\t' in first_line else (';' if ';' in first_line else None))
            # Split by detected delimiter (or whitespace if none)
            parts = first_line.split(delimiter) if delimiter else first_line.split()
            
            # Check if first line contains obvious header keywords (case-insensitive)
            header_keywords = ['wave', 'flux', 'wavelength', 'spectrum', 'lambda', 'counts', 'err', 'error']
            first_line_lower = first_line.lower()
            has_header = any(keyword in first_line_lower for keyword in header_keywords)
            
            # Also check if first line doesn't look like numbers
            looks_like_numbers = False
            if len(parts) >= 2:
                try:
                    float(parts[0])
                    float(parts[1])
                    looks_like_numbers = True
                except (ValueError, IndexError):
                    looks_like_numbers = False
            
            # If first line has text that looks like a header, try header-aware loader first
            if has_header or not looks_like_numbers:
                # Use robust header-aware loader first (handles CSV headers like 'wave,flux,flux_err')
                try:
                    return _try_header_aware_loading(filename)
                except Exception:
                    pass
                # Fallback: try skipping 1+ header-like rows with detected delimiter
                try:
                    skiprows = _count_leading_header_lines(filename)
                    if delimiter:
                        data = np.loadtxt(filename, comments='#', skiprows=skiprows, delimiter=delimiter, **kwargs)
                    else:
                        data = np.loadtxt(filename, comments='#', skiprows=skiprows, **kwargs)
                    if data.ndim == 2 and data.shape[1] >= 2:
                        wavelength = data[:, 0]
                        flux = data[:, 1]
                        wavelength, flux = _validate_and_clean_arrays(wavelength, flux)
                        _LOGGER.info(
                            f"✅ Text spectrum loaded (skipped {skiprows} header-like rows): {len(wavelength)} points"
                        )
                        return wavelength, flux
                except Exception:
                    pass  # Fall through to other methods
    except:
        pass  # Fall through to standard loading
    
    try:
        # Try standard space/tab delimited loading
        data = np.loadtxt(filename, comments='#', **kwargs)
        
        if data.ndim == 1:
            # Single column - assume flux only
            flux = data
            wavelength = np.arange(len(flux), dtype=float)
            warnings.warn("Single column detected - generating sequential wavelength values")
            
        elif data.ndim == 2:
            if data.shape[1] >= 2:
                # Two or more columns - assume [wavelength, flux, ...]
                wavelength = data[:, 0]
                flux = data[:, 1]
            else:
                # Single column in 2D array
                flux = data[:, 0]
                wavelength = np.arange(len(flux), dtype=float)
                warnings.warn("Single column detected - generating sequential wavelength values")
        else:
            raise SpectrumLoadError(f"Unsupported data dimensions: {data.ndim}D")
        
        # Validate the data
        wavelength, flux = _validate_and_clean_arrays(wavelength, flux)
        
        _LOGGER.info(f"✅ Text spectrum loaded: {len(wavelength)} points")
        
        return wavelength, flux
        
    except (ValueError, TypeError) as e:
        # First, try a robust header/delimiter-aware loader (handles 'wave,flux,flux_err')
        try:
            return _try_header_aware_loading(filename)
        except Exception:
            pass

        # Then, try alternative loading methods
        try:
            return _try_alternative_text_loading(filename)
        except Exception:
            raise SpectrumLoadError(f"Error reading text file {filename}: {str(e)}")
    except SpectrumLoadError:
        raise
    except Exception as e:
        # Try alternative loading methods
        try:
            return _try_alternative_text_loading(filename)
        except Exception:
            raise SpectrumLoadError(f"Error reading text file {filename}: {str(e)}")


def _construct_wavelength_axis(header: Dict[str, Any], n_pixels: int) -> np.ndarray:
    """
    Construct wavelength axis from FITS header WCS information.
    
    Parameters:
        header: FITS header dictionary
        n_pixels: Number of pixels in the spectrum
        
    Returns:
        np.ndarray: Wavelength array
    """
    # Try different WCS keywords
    if 'CRVAL1' in header:
        # Linear WCS
        start_wave = header['CRVAL1']
        ref_pixel = header.get('CRPIX1', 1.0)  # 1-based indexing
        
        # Try different step size keywords
        if 'CD1_1' in header:
            step = header['CD1_1']
        elif 'CDELT1' in header:
            step = header['CDELT1']
        else:
            step = 1.0
            warnings.warn("No wavelength step found in header, using step=1")
        
        # Calculate wavelengths
        # FITS uses 1-based indexing, convert to 0-based
        pixel_indices = np.arange(n_pixels, dtype=float)
        wavelength = start_wave + (pixel_indices - (ref_pixel - 1)) * step
        
    else:
        # Fallback to sequential values
        wavelength = np.arange(n_pixels, dtype=float)
        warnings.warn("No WCS information found in FITS header, using sequential values")
    
    return wavelength


def _get_band_info(header: Dict[str, Any], band: int) -> Optional[str]:
    """
    Extract band information from FITS header.
    
    Parameters:
        header: FITS header dictionary
        band: Band index
        
    Returns:
        Optional[str]: Band description if available
    """
    band_key = f'BANDID{band + 1}'  # FITS uses 1-based indexing
    return header.get(band_key, None)


def _validate_and_clean_arrays(wavelength: np.ndarray, flux: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Validate and clean wavelength and flux arrays.
    
    Parameters:
        wavelength: Wavelength array
        flux: Flux array
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Cleaned arrays
        
    Raises:
        SpectrumLoadError: If arrays are invalid
    """
    # Convert to numpy arrays and ensure they are numeric
    try:
        wavelength = np.asarray(wavelength, dtype=float)
        flux = np.asarray(flux, dtype=float)
    except (ValueError, TypeError) as e:
        raise SpectrumLoadError(f"Cannot convert data to numeric arrays: {str(e)}")
    
    # Check lengths match
    if len(wavelength) != len(flux):
        raise SpectrumLoadError(
            f"Wavelength and flux arrays have different lengths: "
            f"{len(wavelength)} vs {len(flux)}"
        )
    
    # Check for empty arrays
    if len(wavelength) == 0:
        raise SpectrumLoadError("Empty spectrum data")
    
    # Remove NaN and infinite values
    try:
        mask = np.isfinite(wavelength) & np.isfinite(flux)
        n_bad = np.sum(~mask)
        
        if n_bad > 0:
            # Log as info so it respects global verbosity (hidden in quiet mode, visible with --verbose)
            _LOGGER.info(f"Removed {n_bad} non-finite data points")
            wavelength = wavelength[mask]
            flux = flux[mask]
    except TypeError as e:
        # Handle cases where isfinite fails on non-numeric data
        raise SpectrumLoadError(f"Data contains non-numeric values: {str(e)}")
    
    # Check if anything remains
    if len(wavelength) == 0:
        raise SpectrumLoadError("No valid data points after cleaning")
    
    # Automatic unit detection and conversion
    wavelength = _detect_and_convert_wavelength_units(wavelength)
    
    return wavelength, flux


def _detect_and_convert_wavelength_units(wavelength: np.ndarray) -> np.ndarray:
    """
    Detect wavelength units and convert to Angstroms if necessary.
    
    Parameters:
        wavelength: Wavelength array
        
    Returns:
        np.ndarray: Wavelength array in Angstroms
    """
    if len(wavelength) == 0:
        return wavelength
        
    min_wave = np.min(wavelength)
    max_wave = np.max(wavelength)
    
    # Detect likely units based on typical ranges
    if min_wave > 100 and max_wave < 1000:
        # Likely nanometers (nm) - convert to Angstroms
        wavelength_converted = wavelength * 10.0
        _LOGGER.info(f"🔄 Wavelength units detected as nanometers (nm)")
        _LOGGER.info(f"   Converting: {min_wave:.1f}-{max_wave:.1f} nm → "
              f"{wavelength_converted[0]:.1f}-{wavelength_converted[-1]:.1f} Å")
        return wavelength_converted
        
    elif min_wave > 0.1 and max_wave < 10:
        # Likely micrometers (μm) - convert to Angstroms
        wavelength_converted = wavelength * 10000.0
        _LOGGER.info(f"🔄 Wavelength units detected as micrometers (μm)")
        _LOGGER.info(f"   Converting: {min_wave:.2f}-{max_wave:.2f} μm → "
              f"{wavelength_converted[0]:.1f}-{wavelength_converted[-1]:.1f} Å")
        return wavelength_converted
        
    elif min_wave > 1000 and max_wave < 100000:
        # Likely already in Angstroms
        _LOGGER.info(f"✅ Wavelength units detected as Angstroms (Å): {min_wave:.1f}-{max_wave:.1f} Å")
        return wavelength
        
    else:
        # Unknown units - warn but don't convert
        warnings.warn(f"Unknown wavelength units detected (range: {min_wave:.2f}-{max_wave:.2f}). "
                     "Assuming Angstroms. Please verify units manually.")
        return wavelength


def _try_header_aware_loading(filename: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Try loading text files by detecting headers and delimiters, supporting cases like
    'wave,flux,flux_err' (e.g., some Wiserep exports).

    Parameters:
        filename: Path to text file

    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
    """
    # Helper: detect delimiter from a sample line
    def _detect_delimiter(sample: str) -> Optional[str]:
        if ',' in sample:
            return ','
        if '\t' in sample:
            return '\t'
        if ';' in sample:
            return ';'
        # None means whitespace splitting
        return None

    # Helper: split a line by detected delimiter
    def _split(line: str, delim: Optional[str]) -> list:
        return line.split(delim) if delim is not None else line.split()

    # Helper: determine whether tokens are numeric
    def _all_numeric(tokens: list) -> bool:
        for tok in tokens[:3]:  # sample a few tokens
            try:
                float(tok)
            except Exception:
                return False
        return True if tokens else False

    def _count_leading_header_lines(path: str, max_lines: int = 10) -> int:
        def _is_numeric_data_line(line: str) -> bool:
            s = line.replace('"', '').strip().rstrip(',;')
            s = s.replace(',', ' ').replace('\t', ' ').replace(';', ' ')
            parts = [p for p in s.split() if p]
            if len(parts) < 2:
                return False
            try:
                float(parts[0])
                float(parts[1])
                return True
            except Exception:
                return False

        header_lines = 0
        with open(path, 'r', encoding='utf-8-sig', errors='ignore') as fh:
            for _ in range(max_lines):
                raw = fh.readline()
                if not raw:
                    break
                s = raw.strip()
                if not s:
                    continue
                if s.lstrip().startswith('#'):
                    continue
                if _is_numeric_data_line(s):
                    break
                header_lines += 1
        return header_lines

    # Read first non-empty, non-comment line
    first_content_line = None
    # Use utf-8-sig to handle BOM-prefixed CSV headers (common on Windows exports)
    with open(filename, 'r', encoding='utf-8-sig', errors='ignore') as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.lstrip().startswith('#'):
                continue
            first_content_line = line
            break

    if first_content_line is None:
        raise SpectrumLoadError("Empty or comment-only file")

    delimiter = _detect_delimiter(first_content_line)
    tokens = _split(first_content_line, delimiter)
    header_lines = _count_leading_header_lines(filename)
    extra_skiprows = list(range(1, header_lines)) if header_lines > 1 else None

    # Identify if the first line is a header
    header_candidates = {"wave", "wavelength", "lambda", "lam", "wl", "angstrom", "ang",
                         "flux", "fnu", "flam", "counts", "spec", "spectrum", "intensity",
                         "flux_err", "error", "err", "uncertainty"}
    looks_like_header = (not _all_numeric(tokens)) or any(
        any(ch.isalpha() for ch in t) for t in tokens
    ) or any(t.strip().lower() in header_candidates for t in tokens)

    # If there is a header, prefer pandas (if available) to select by column names
    if looks_like_header:
        # Try pandas path
        try:
            import pandas as pd
            sep = delimiter if delimiter is not None else r'\s+'
            df = pd.read_csv(
                filename,
                sep=sep,
                comment='#',
                header=0,
                encoding='utf-8-sig',
                skiprows=extra_skiprows
            )

            # Build a case-insensitive name map
            name_map = {str(c).strip().lower(): c for c in df.columns}
            wave_keys = ["wave", "wavelength", "lambda", "lam", "wl", "angstrom", "ang"]
            flux_keys = ["flux", "fnu", "flam", "counts", "spec", "spectrum", "intensity"]

            wave_col_name = next((name_map[k] for k in wave_keys if k in name_map), None)
            flux_col_name = next((name_map[k] for k in flux_keys if k in name_map), None)

            if wave_col_name is not None and flux_col_name is not None:
                # Robustly coerce to numeric and drop non-numeric rows (e.g. extra header line)
                w_ser = pd.to_numeric(df[wave_col_name], errors='coerce')
                f_ser = pd.to_numeric(df[flux_col_name], errors='coerce')
                mask = np.isfinite(w_ser.to_numpy()) & np.isfinite(f_ser.to_numpy())
                if np.any(mask):
                    wavelength = w_ser.to_numpy()[mask]
                    flux = f_ser.to_numpy()[mask]
                    return _validate_and_clean_arrays(wavelength, flux)

            # Fallback: choose the first two numeric-like columns
            numeric_df = df.apply(pd.to_numeric, errors='coerce')
            valid_cols = [c for c in numeric_df.columns if numeric_df[c].notna().any()]
            if len(valid_cols) >= 2:
                wavelength = numeric_df[valid_cols[0]].to_numpy()
                flux = numeric_df[valid_cols[1]].to_numpy()
                return _validate_and_clean_arrays(wavelength, flux)
        except ImportError:
            pass
        except Exception:
            # Fall back to numpy-based methods below
            pass

        # Try numpy genfromtxt with named columns
        try:
            # genfromtxt can't easily skip "extra header lines" after the names row.
            # In that case, prefer pandas/manual parsing.
            if header_lines > 1:
                raise SpectrumLoadError("Multiple header lines detected; skipping genfromtxt")
            arr = np.genfromtxt(
                filename,
                delimiter=delimiter if delimiter is not None else None,
                names=True,
                comments='#',
                dtype=None,
                encoding='utf-8-sig'
            )
            if arr is not None and getattr(arr, 'dtype', None) is not None and arr.dtype.names:
                name_map = {str(n).strip().lower(): str(n) for n in arr.dtype.names}
                wave_keys = ["wave", "wavelength", "lambda", "lam", "wl", "angstrom", "ang"]
                flux_keys = ["flux", "fnu", "flam", "counts", "spec", "spectrum", "intensity"]
                wave_field = next((name_map[k] for k in wave_keys if k in name_map), None)
                flux_field = next((name_map[k] for k in flux_keys if k in name_map), None)
                if wave_field and flux_field:
                    wavelength = np.asarray(arr[wave_field])
                    flux = np.asarray(arr[flux_field])
                    return _validate_and_clean_arrays(wavelength, flux)
                # Fallback: first two fields
                if len(arr.dtype.names) >= 2:
                    wavelength = np.asarray(arr[arr.dtype.names[0]])
                    flux = np.asarray(arr[arr.dtype.names[1]])
                    return _validate_and_clean_arrays(wavelength, flux)
        except Exception:
            pass

        raise SpectrumLoadError("Header detected but could not parse columns")

    # No header detected; use delimiter-aware numeric loading
    try:
        data = np.loadtxt(filename, delimiter=delimiter if delimiter is not None else None, comments='#')
        if data.ndim == 1:
            flux = data
            wavelength = np.arange(len(flux), dtype=float)
        elif data.ndim == 2 and data.shape[1] >= 2:
            wavelength = data[:, 0]
            flux = data[:, 1]
        else:
            raise SpectrumLoadError(f"Unsupported data shape: {getattr(data, 'shape', None)}")
        return _validate_and_clean_arrays(wavelength, flux)
    except Exception as e:
        raise SpectrumLoadError(str(e))


def _try_alternative_text_loading(filename: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Try alternative methods for loading text files.
    
    Parameters:
        filename: Path to text file
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
    """
    def _count_leading_header_lines(path: str, max_lines: int = 10) -> int:
        def _is_numeric_data_line(line: str) -> bool:
            s = line.replace('"', '').strip().rstrip(',;')
            s = s.replace(',', ' ').replace('\t', ' ').replace(';', ' ')
            parts = [p for p in s.split() if p]
            if len(parts) < 2:
                return False
            try:
                float(parts[0])
                float(parts[1])
                return True
            except Exception:
                return False

        header_lines = 0
        with open(path, 'r', encoding='utf-8-sig', errors='ignore') as fh:
            for _ in range(max_lines):
                raw = fh.readline()
                if not raw:
                    break
                s = raw.strip()
                if not s:
                    continue
                if s.lstrip().startswith('#'):
                    continue
                if _is_numeric_data_line(s):
                    break
                header_lines += 1
        return header_lines

    skiprows = _count_leading_header_lines(filename)

    # Try comma-separated
    try:
        data = np.loadtxt(filename, delimiter=',', comments='#', skiprows=skiprows)
        if data.ndim == 2 and data.shape[1] >= 2:
            return _validate_and_clean_arrays(data[:, 0], data[:, 1])
    except:
        pass
    
    # Try pandas if available
    try:
        import pandas as pd
        
        # Try whitespace-delimited using regex separator (avoids FutureWarning)
        df = pd.read_csv(filename, sep=r'\s+', header=None, comment='#')
        if len(df.columns) >= 2:
            return _validate_and_clean_arrays(df.iloc[:, 0].values, df.iloc[:, 1].values)
            
        # Try comma-delimited
        # If we detected a header, read it as such and try name-based selection first.
        if skiprows >= 1:
            try:
                extra_skiprows = list(range(1, skiprows)) if skiprows > 1 else None
                dfh = pd.read_csv(filename, comment='#', header=0, encoding='utf-8-sig', skiprows=extra_skiprows)
                name_map = {str(c).strip().lower(): c for c in dfh.columns}
                wave_keys = ["wave", "wavelength", "lambda", "lam", "wl", "angstrom", "ang"]
                flux_keys = ["flux", "fnu", "flam", "counts", "spec", "spectrum", "intensity"]
                wave_col = next((name_map[k] for k in wave_keys if k in name_map), None)
                flux_col = next((name_map[k] for k in flux_keys if k in name_map), None)
                if wave_col is not None and flux_col is not None:
                    w_ser = pd.to_numeric(dfh[wave_col], errors='coerce')
                    f_ser = pd.to_numeric(dfh[flux_col], errors='coerce')
                    mask = np.isfinite(w_ser.to_numpy()) & np.isfinite(f_ser.to_numpy())
                    if np.any(mask):
                        return _validate_and_clean_arrays(w_ser.to_numpy()[mask], f_ser.to_numpy()[mask])
            except Exception:
                pass

        df = pd.read_csv(filename, header=None, comment='#', encoding='utf-8-sig')
        if len(df.columns) >= 2:
            # If header was present but read as data, drop first row
            if skiprows >= 1 and len(df) > skiprows:
                df = df.iloc[skiprows:, :]
            return _validate_and_clean_arrays(df.iloc[:, 0].values, df.iloc[:, 1].values)
            
    except ImportError:
        pass
    except:
        pass
    
    # Fallback: manual robust parser tolerant to quotes and mixed delimiters
    try:
        waves: list = []
        fluxes: list = []
        with open(filename, 'r', encoding='utf-8', errors='ignore') as fh:
            for raw in fh:
                s = raw.strip()
                if not s:
                    continue
                # Skip comments
                if s.startswith('#'):
                    continue
                # Remove surrounding quotes and trailing delimiter cruft
                # Many PESSTO/Wiserep exports look like: "w,f,e,bg",,
                s = s.replace('"', '').rstrip(',;')
                # Normalize delimiters to whitespace
                s = s.replace(',', ' ').replace('\t', ' ')
                parts = [p for p in s.split() if p]
                if len(parts) < 2:
                    continue
                # Skip header-like rows
                if any(ch.isalpha() for ch in parts[0]):
                    continue
                try:
                    w = float(parts[0])
                    f = float(parts[1])
                except Exception:
                    continue
                waves.append(w)
                fluxes.append(f)
        if len(waves) > 0:
            return _validate_and_clean_arrays(np.asarray(waves, dtype=float), np.asarray(fluxes, dtype=float))
    except Exception:
        pass

    raise SpectrumLoadError("All text loading methods failed")


def create_spectrum_data(wavelength: np.ndarray, flux: np.ndarray, 
                        error: Optional[np.ndarray] = None,
                        header: Optional[Dict[str, Any]] = None,
                        filename: Optional[str] = None,
                        format: SpectrumFormat = SpectrumFormat.UNKNOWN) -> SpectrumData:
    """
    Create a SpectrumData object from arrays.
    
    Parameters:
        wavelength: Wavelength array
        flux: Flux array
        error: Optional error array
        header: Optional header information
        filename: Optional source filename
        format: Spectrum format
        
    Returns:
        SpectrumData: Structured spectrum data object
    """
    return SpectrumData(
        wavelength=wavelength,
        flux=flux,
        error=error,
        header=header,
        filename=filename,
        format=format
    ) 