"""
I/O functions for SNID.
"""

import os
import glob
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
import re
import logging
import json
from pathlib import Path
from datetime import datetime
from .snidtype import TYPENAME, TYPE_TO_INDICES

# Import preprocessing functions for template processing
from .preprocessing import log_rebin, fit_continuum, init_wavelength_grid

# Use centralized logging if available
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOG = get_logger('snid.io')
except ImportError:
    _LOG = logging.getLogger('snid_sage.snid.io')


def read_spectrum(filename: str, apodize: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """
    Read a spectrum from a file.
    
    Supports multiple file formats:
    - ASCII/text files (.txt, .dat, .ascii, .asci, .csv, .flm)
    - FITS files (.fits, .fit)
    
    Parameters:
        filename (str): Path to spectrum file
        apodize (bool): Whether to apodize the spectrum
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
    """
    try:
        # Check if it's a FITS file
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in ['.fits', '.fit']:
            # Use the shared spectrum loader for FITS files
            try:
                from snid_sage.shared.utils.data_io.spectrum_loader import load_spectrum
                return load_spectrum(filename)
            except ImportError:
                # Fallback to basic FITS loading if shared loader not available
                return _basic_fits_loading(filename)
        else:
            # Use the shared spectrum loader for text files
            try:
                from snid_sage.shared.utils.data_io.spectrum_loader import load_spectrum
                return load_spectrum(filename)
            except ImportError:
                # Fallback to basic ASCII loading if shared loader not available
                return _load_ascii_spectrum(filename)
    
    except Exception as e:
        logging.error(f"Error reading spectrum {filename}: {e}")
        raise


def _load_ascii_spectrum(filename: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load ASCII spectrum file (original implementation).
    
    Parameters:
        filename (str): Path to ASCII file
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
    """
    # Try to read as two-column ASCII file
    data = np.loadtxt(filename, comments='#')
    
    if data.ndim == 1:
        # Single column - assume it's flux with implicit wavelength
        flux = data
        wavelength = np.arange(len(flux), dtype=float)
    elif data.shape[1] >= 2:
        # Two or more columns - use first two
        wavelength = data[:, 0]
        flux = data[:, 1]
    else:
        raise ValueError("Invalid file format")
        
    # Remove any NaN or infinite values
    mask = np.isfinite(wavelength) & np.isfinite(flux)
    wavelength = wavelength[mask]
    flux = flux[mask]
    
    return wavelength, flux


def _basic_fits_loading(filename: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Basic FITS file loading fallback.
    
    Parameters:
        filename (str): Path to FITS file
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: Wavelength and flux arrays
    """
    try:
        from astropy.io import fits
    except ImportError:
        raise ImportError("FITS file support requires astropy. Please install astropy: pip install astropy")
    
    with fits.open(filename) as hdul:
        header = hdul[0].header
        data = hdul[0].data
        
        if data is None:
            raise ValueError("FITS file contains no data")
        
        # Handle different data structures
        if data.ndim == 1:
            # Simple 1D spectrum
            flux = data
            # Try to construct wavelength from header
            if 'CRVAL1' in header and 'CD1_1' in header:
                start = header['CRVAL1']
                step = header['CD1_1']
                wavelength = np.arange(len(flux)) * step + start
            else:
                # Default wavelength grid
                wavelength = np.arange(len(flux), dtype=float)
                
        elif data.ndim == 2:
            # 2D data - could be [wavelength, flux] or multiple spectra
            if data.shape[0] == 2:
                # Assume [wavelength, flux] format
                wavelength = data[0]
                flux = data[1]
            elif data.shape[1] == 2:
                # Assume columns are [wavelength, flux]
                wavelength = data[:, 0]
                flux = data[:, 1]
            else:
                # Take first spectrum and construct wavelength
                flux = data[0] if data.shape[0] < data.shape[1] else data[:, 0]
                if 'CRVAL1' in header and 'CD1_1' in header:
                    start = header['CRVAL1']
                    step = header['CD1_1']
                    wavelength = np.arange(len(flux)) * step + start
                else:
                    wavelength = np.arange(len(flux), dtype=float)
                    
        elif data.ndim == 3:
            # 3D data - take first band, first spatial pixel
            flux = data[0, 0, :]
            if 'CRVAL1' in header and 'CD1_1' in header:
                start = header['CRVAL1']
                step = header['CD1_1']
                wavelength = np.arange(len(flux)) * step + start
            else:
                wavelength = np.arange(len(flux), dtype=float)
        else:
            raise ValueError(f"Unsupported FITS data dimensions: {data.ndim}D")
        
        return wavelength.astype(float), flux.astype(float)


def read_template(filename: str) -> Dict[str, Any]:
    """
    Read a template spectrum file (.lnw format).
    
    Parameters:
        filename (str): Path to template file
        
    Returns:
        Dict: Template information including wavelength, flux, type, etc.
    """
    template = {}
    
    # Extract template name from filename
    basename = os.path.basename(filename)
    template['name'] = os.path.splitext(basename)[0]
    
    try:
        # Read *all* lines as text
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        # Skip any comment lines at the beginning
        line_idx = 0
        while line_idx < len(lines) and lines[line_idx].startswith('#'):
            line_idx += 1
            
        if line_idx >= len(lines) or len(lines) - line_idx < 2:
            raise ValueError(f"{filename} is too short or contains only comments")
        
        # First non-comment line is the header
        # Format from logwave.f: format(2i5,2f10.2,i7,5x,a12,f7.2,2x,a10,2(i3))
        hdr = lines[line_idx]
        line_idx += 1
        
        if len(hdr) < 80:  # Ensure the header is long enough for full parsing
            hdr = hdr.ljust(80)
            
        try:
            nepoch = int(hdr[0:5].strip())
            nw = int(hdr[5:10].strip())
            w0 = float(hdr[10:20].strip())
            w1 = float(hdr[20:30].strip())
            mostknots = int(hdr[30:37].strip())
            # 5 spaces
            sname = hdr[42:54].strip()
            delta = float(hdr[54:61].strip())
            # 2 spaces
            stype = hdr[63:73].strip()
            ittype = int(hdr[73:76].strip() or "0")
            itstype = int(hdr[76:79].strip() or "0")
        except (ValueError, IndexError) as e:
            # Fall back to more lenient parsing if the fixed format fails
            logging.warning(f"Fixed format parsing failed for {filename}, trying more flexible parsing: {e}")
            parts = hdr.split()
            if len(parts) >= 5:
                nepoch = int(parts[0])
                nw = int(parts[1])
                w0 = float(parts[2])
                w1 = float(parts[3])
                mostknots = int(parts[4])
                if len(parts) > 5:
                    sname = parts[5]
                    if len(parts) > 6:
                        delta = float(parts[6])
                        if len(parts) > 7:
                            stype = parts[7]
                            if len(parts) > 9:
                                ittype = int(parts[8])
                                itstype = int(parts[9])
                            else:
                                ittype, itstype = 0, 0
                        else:
                            stype, ittype, itstype = "Unknown", 0, 0
                    else:
                        delta, stype, ittype, itstype = 0.0, "Unknown", 0, 0
                else:
                    sname, delta, stype, ittype, itstype = "", 0.0, "Unknown", 0, 0
            else:
                raise ValueError(f"Cannot parse header line: {hdr}")

        # Store in template
        template['nepoch'] = nepoch
        template['nw'] = nw
        template['w0'] = w0
        template['w1'] = w1
        template['delta'] = delta
        
        # Handle type and subtype using enhanced TYPENAME from snidtype
        if ittype > 0 and ittype in TYPENAME:
            if itstype > 0 and itstype in TYPENAME[ittype]:
                # Get the full subtype name from the hierarchical structure
                full_subtype = TYPENAME[ittype][itstype]
                template['subtype'] = full_subtype
                
                # Get the main type using the enhanced mapping
                from snid_sage.snid.snidtype import get_main_type_from_template
                template['type'] = get_main_type_from_template(full_subtype)
            else:
                # Default case - use the first subtype as both type and subtype
                if 1 in TYPENAME[ittype]:
                    main_type = TYPENAME[ittype][1]
                    template['type'] = main_type
                    template['subtype'] = main_type
                else:
                    template['type'] = 'Unknown'
                    template['subtype'] = 'Unknown'
        else:
            # Fallback to string type if indices not found
            # Use enhanced mapping for flat types from templates
            from snid_sage.snid.snidtype import get_main_type_from_template
            template['type'] = get_main_type_from_template(stype)
            template['subtype'] = stype
            
        template['type_index'] = (ittype, itstype)
        template['sname'] = sname

        # ——— Read knot counts & fmean pairs ———
        # Format from logwave.f: format(i7,300(i3,f14.5))
        knot_line = lines[line_idx]
        line_idx += 1
        
        knot_parts = knot_line.split()
        # First part is mostknots again
        mostknots_check = int(knot_parts[0])
        if mostknots_check != mostknots:
            logging.warning(f"Mostknots mismatch in {filename}: header={mostknots}, knot line={mostknots_check}")
        
        nknots = []
        fmeans = []
        for i in range(nepoch):
            if 1 + 2*i < len(knot_parts):
                nknots.append(int(knot_parts[1 + 2*i]))
                fmeans.append(float(knot_parts[2 + 2*i]))
            else:
                break
        
        template['nknots'] = nknots
        template['fmeans'] = fmeans
        
        # ——— Skip the knot-wavelength lines ———
        # Format: format(i7,300(f8.4,f9.4))
        for i in range(mostknots):
            if line_idx < len(lines):
                line_idx += 1
            else:
                raise ValueError(f"File {filename} truncated in knot section")

        # ——— Read ages line ———
        # Format from logwave.f: format(i8,300f9.3)
        if line_idx >= len(lines):
            raise ValueError(f"File {filename} truncated before age line")
            
        age_line = lines[line_idx]
        line_idx += 1
        
        age_parts = age_line.split()
        if len(age_parts) > 0:
            tflag = int(age_parts[0])
            ages = []
            for i in range(1, min(len(age_parts), nepoch+1)):
                try:
                    ages.append(float(age_parts[i]))
                except ValueError:
                    logging.warning(f"Invalid age value in {filename}: {age_parts[i]}")
                    ages.append(0.0)
        else:
            tflag, ages = 0, []
        
        # Store age information
        if ages:
            template['age'] = ages[0]  # Just use the first age for now
        template['ages'] = ages
        template['age_flag'] = tflag

        # ——— Read the spectrum itself ———
        # Format from logwave.f: format(f8.2,300f9.3)
        wave_log = []
        flux_matrix = np.zeros((nepoch, nw))
        
        for i in range(nw):
            if line_idx + i < len(lines):
                spec_line = lines[line_idx + i]
                spec_parts = spec_line.split()
                if len(spec_parts) >= nepoch + 1:  # Must have wavelength + flux for each epoch
                    try:
                        # First value is the log wavelength
                        wave_val = float(spec_parts[0])
                        wave_log.append(wave_val)
                        
                        # Read flux for each epoch
                        for j in range(nepoch):
                            flux_val = float(spec_parts[j + 1])
                            flux_matrix[j, i] = flux_val
                    except ValueError:
                        logging.warning(f"Invalid spectrum values in {filename}, line {line_idx + i}: {spec_line}")
            else:
                logging.warning(f"File {filename} has fewer spectrum lines than expected: {i} of {nw}")
                break
        
        wave_log = np.array(wave_log)
        
        if len(wave_log) == 0:
            raise ValueError(f"No valid wavelength data found in {filename}")

        # ——— Convert from log to linear wavelength ———
        # In logwave.f, these are mean wavelengths: wmean = 0.5*(wlog(i)+wlog(i+1))
        # We don't need to recalculate them here since they're directly stored in the file
        template['wave'] = wave_log
                    
        # Store both the first flux (for backward compatibility) and the full matrix
        template['flux'] = flux_matrix[0]  # First epoch's flux for backward compatibility
        template['flux_matrix'] = flux_matrix  # All epochs' fluxes
        template['is_log_rebinned'] = True
        
        # Calculate the linear wavelength array from the log values
        template['wave_linear'] = 10.0**np.clip(wave_log, -20, 20)

    except Exception as e:
        logging.error(f"Error reading template {filename}: {e}")
        raise
    
    # Basic validation
    if 'wave' not in template or 'flux' not in template or len(template['wave']) == 0:
        raise ValueError(f"Template {filename} missing wavelength or flux data")
    
    if len(template['wave']) < 10:
        raise ValueError(f"Template {filename} has too few data points")
    
    if 'type' not in template:
        template['type'] = 'Unknown'
    
    # Normalization is already done in the .lnw file format
    # But we'll check for NaN or Inf values
    if np.any(np.isnan(template['flux'])) or np.any(np.isinf(template['flux'])):
        logging.warning(f"Template {filename} contains NaN or Inf flux values")
        # Remove NaN or Inf values
        mask = ~(np.isnan(template['flux']) | np.isinf(template['flux']))
        template['wave'] = template['wave'][mask]
        template['flux'] = template['flux'][mask]
        if 'wave_linear' in template:
            template['wave_linear'] = template['wave_linear'][mask]
    
    return template


def load_templates(
    template_dir: str,
    flatten: bool = True,
    *,
    profile_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Load all template spectra from a directory.
    
    Fallback loader that is only used if unified storage is unavailable.
    
    Parameters:
        template_dir (str): Directory containing template files
        flatten (bool): Whether to flatten non-flattened spectra
        
    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, int]]: List of templates and counts by type
    """
    # First try to use unified storage directly as a fallback
    try:
        from .core.integration import load_templates_unified
        templates = load_templates_unified(template_dir, profile_id=profile_id)
        
        # Build type statistics
        type_counts = {}
        for template in templates:
            template_type = template.get('type', 'Unknown')
            type_counts[template_type] = type_counts.get(template_type, 0) + 1
        
        _LOG.info(f"✅ Legacy fallback successfully used unified storage: {len(templates)} templates")
        return templates, type_counts
        
    except Exception as e:
        _LOG.warning(f"Unified storage failed in fallback loader: {e}, trying .lnw files")
    
    # Fallback behavior: look for .lnw files
    templates = []
    type_counts = {}
    
    # Find all template files - only include each unique file once
    template_files = set()
    for ext in ["*.lnw", "*.dat"]:
        template_files.update(glob.glob(os.path.join(template_dir, ext)))
    
    # Standard number of points for log rebinning
    std_num_points = 1024
    std_w0 = 2500.0
    std_w1 = 10000.0
    try:
        from snid_sage.shared.profiles.builtins import register_builtins
        from snid_sage.shared.profiles.registry import get_profile
        register_builtins()
        prof = get_profile(profile_id or "optical")
        std_num_points = int(prof.grid.nw)
        std_w0 = float(prof.grid.min_wave_A)
        std_w1 = float(prof.grid.max_wave_A)
    except Exception:
        # Keep optical defaults when profile resolution is unavailable
        pass
    # Ensure global grid matches the desired profile for any on-the-fly rebinning
    try:
        init_wavelength_grid(num_points=int(std_num_points), min_wave=float(std_w0), max_wave=float(std_w1))
    except Exception:
        pass
    
    for filename in template_files:
        try:
            raw_template = read_template(filename)
            
            # Handle multi-epoch templates (exactly like SNID's gettemp subroutine)
            nepoch = raw_template.get('nepoch', 1)
            
            if nepoch > 1 and 'flux_matrix' in raw_template and 'ages' in raw_template:
                # Create a separate template for each epoch
                for j in range(nepoch):
                    # Skip templates outside age range (this would be done later in identify)
                    # But we include it here for completeness
                    
                    # Create a new template dictionary for this epoch
                    epoch_template = raw_template.copy()
                    
                    # Update epoch-specific data
                    epoch_template['flux'] = raw_template['flux_matrix'][j]
                    if len(raw_template['ages']) > j:
                        epoch_template['age'] = raw_template['ages'][j]
                    
                    # Add this epoch's template to the list
                    templates.append(epoch_template)
                    
                    # Count by type
                    t_type = epoch_template.get('type', 'Unknown')
                    if t_type in type_counts:
                        type_counts[t_type] += 1
                    else:
                        type_counts[t_type] = 1
            else:
                # Handle single-epoch templates or templates without flux_matrix
                # Check if flux is valid
                if 'flux' in raw_template and len(raw_template['flux']) > 0:
                    pass
                
                # For non-.lnw files, we need to do processing
                if not filename.endswith('.lnw'):
                    # Make sure we have valid wave data
                    if 'wave' in raw_template and 'flux' in raw_template and len(raw_template['wave']) == len(raw_template['flux']):
                        wave_arr = raw_template['wave']
                        flux_arr = raw_template['flux']
                        
                        # Log-rebin to the active grid and (optionally) flatten via continuum removal
                        log_wave, log_flux = log_rebin(np.asarray(wave_arr, dtype=float), np.asarray(flux_arr, dtype=float))
                        if flatten:
                            processed_flux, _cont = fit_continuum(log_flux, method="spline")
                        else:
                            processed_flux = log_flux
                        
                        raw_template['wave'] = log_wave
                        raw_template['flux'] = processed_flux
                        raw_template['is_log_rebinned'] = True
                    else:
                        logging.warning(f"Cannot process template {filename}: Missing or invalid wavelength/flux data")
                        continue
                
                # Count by type
                t_type = raw_template.get('type', 'Unknown')
                if t_type in type_counts:
                    type_counts[t_type] += 1
                else:
                    type_counts[t_type] = 1
                    
                templates.append(raw_template)
                
        except Exception as e:
            logging.warning(f"Error reading template {filename}: {e}")
    
    logging.info(f"Loaded {len(templates)} templates of {len(type_counts)} types")
    return templates, type_counts

def write_detailed_result(result: Any, filename: str) -> None:
    """
    Write detailed SNID results to a file.
    
    Parameters:
        result: SNIDResult object
        filename (str): Output filename
    """
    with open(filename, 'w', encoding='utf-8') as f:
        # Header
        f.write("### SNID output file ###\n\n")
        
        # Input spectrum and options
        f.write("### input spectrum and options ###\n")
        if hasattr(result, 'input_file') and result.input_file:
            f.write(f"# Input spectrum                 : {result.input_file}\n")
        if hasattr(result, 'input_spectrum') and result.input_spectrum:
            wave = result.input_spectrum.get('wave', np.array([]))
            if len(wave) > 0:
                f.write(f"# Wavelength range               : {wave.min():.1f} - {wave.max():.1f} Å\n")
        
        # Write analysis parameters if available
        try:
            if hasattr(result, 'lapmin'):
                f.write(f"# Minimum overlap (lapmin)       : {float(getattr(result, 'lapmin')):.3f}\n")
        except Exception:
            pass
        try:
            if hasattr(result, 'hsigma_lap_ccc_threshold'):
                f.write(f"# Metric threshold (HσLAP-CCC)    : {float(getattr(result, 'hsigma_lap_ccc_threshold')):.3f}\n")
        except Exception:
            pass
        if hasattr(result, 'dwlog') and result.dwlog:
            f.write(f"# Log wavelength step            : {result.dwlog:.6f}\n")
        f.write("\n")
        
        # Initial/user-input redshift
        f.write("### initial/user-input redshift ###\n")
        f.write(f"zinit   {result.initial_redshift:.4f}\n")
        f.write(f"zuser   {result.initial_redshift:.4f}\n")
        f.write("\n")
        
        # Summary redshift/age (weighted means)
        f.write("### weighted redshift/age and error ###\n")
        f.write(f"zmean   {result.consensus_redshift:.4f} {result.consensus_redshift_error:.4f}\n")
        f.write(f"agemean {result.consensus_age:.2f} {result.consensus_age_error:.2f}\n")
        f.write("\n")
        
        # Type fraction, redshift, and age
        f.write("### type fraction/redshift/age ###\n")
        f.write("#type      ntemp  fraction     slope   redshift redshift_error      age  age_error\n")
        
        # Write type statistics
        if hasattr(result, 'type_statistics') and result.type_statistics:
            for tp, type_subtype_stats in result.type_statistics.items():
                # Ensure type_subtype_stats is a dictionary, not a string
                if not isinstance(type_subtype_stats, dict):
                    continue
                    
                if '_all' in type_subtype_stats:
                    type_stats = type_subtype_stats['_all']
                    count = type_stats.get('count', 0)
                    fraction = result.type_fractions.get(tp, 0.0)
                    
                    # Get slope if available
                    slope = 0.0
                    if (hasattr(result, 'match_statistics') and 
                        'type_slopes' in result.match_statistics):
                        slope = result.match_statistics['type_slopes'].get(tp, 0.0)
                    
                    f.write(f"{tp:<10} {count:7d} {fraction:10.2f} {slope:10.4f} "
                           f"{type_stats.get('z_mean', 0.0):10.4f} "
                           f"{type_stats.get('z_err', 0.0):10.4f} "
                           f"{type_stats.get('age_mean', 0.0):10.3f} "
                           f"{type_stats.get('age_err', 0.0):10.3f}\n")
                
                # Write subtype statistics
                for sub, sub_stats in type_subtype_stats.items():
                    if sub != '_all' and isinstance(sub_stats, dict):
                        count = sub_stats.get('count', 0)
                        # Calculate subtype fraction
                        total_type = type_subtype_stats['_all'].get('count', 1)
                        fraction = count / total_type if total_type > 0 else 0.0
                        
                        f.write(f"{sub:<10} {count:7d} {fraction:10.2f} {0.0:10.4f} "
                               f"{sub_stats.get('z_mean', 0.0):10.4f} "
                               f"{sub_stats.get('z_err', 0.0):10.4f} "
                               f"{sub_stats.get('age_mean', 0.0):10.3f} "
                               f"{sub_stats.get('age_err', 0.0):10.3f}\n")
        f.write("\n")
        
        # Ordered template listings - use winning cluster if available, otherwise best matches
        f.write("### best-metric-ordered template listings ###\n")
        
        # Get the winning cluster matches (cluster-aware approach like batch script)
        cluster_matches = []
        using_cluster = False
        
        if (hasattr(result, 'clustering_results') and 
            result.clustering_results and 
            result.clustering_results.get('success')):
            
            clustering_results = result.clustering_results
            
            # Priority: user_selected_cluster > best_cluster  
            winning_cluster = None
            if 'user_selected_cluster' in clustering_results:
                winning_cluster = clustering_results['user_selected_cluster']
            elif 'best_cluster' in clustering_results:
                winning_cluster = clustering_results['best_cluster']
            
            if winning_cluster:
                cluster_matches = winning_cluster.get('matches', [])
                using_cluster = True
        
        # If no cluster matches, fall back to filtered_matches, then best_matches
        if not cluster_matches:
            if hasattr(result, 'filtered_matches') and result.filtered_matches:
                cluster_matches = result.filtered_matches
            elif hasattr(result, 'best_matches') and result.best_matches:
                cluster_matches = result.best_matches
        
        # Sort cluster matches by best available metric (HσLAP-CCC preferred) descending
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        cluster_matches = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
        
        # Add header showing what type of matches we're showing
        match_source = "winning cluster" if using_cluster else "all matches"
        f.write(f"# Showing templates from {match_source}, sorted by best metric (highest first)\n")
        f.write("# no.  template      type        lap   metric    redshift   red_error      age  age_flag  grade\n")
        
        for i, match in enumerate(cluster_matches, 1):
            template = match['template']
            name = template.get('name', 'Unknown')[:12]  # Limit to 12 chars
            
            # Use subtype if available, otherwise fall back to main type
            subtype = template.get('subtype', '')
            if subtype and subtype != 'Unknown' and subtype != '':
                t_type = subtype[:10]  # Use subtype (limit to 10 chars)
            else:
                t_type = template.get('type', 'Unknown')[:10]  # Fall back to main type
            
            age = template.get('age', 0.0)
            age_flag = template.get('age_flag', 0)
            redshift = match['redshift']
            # Keep column name for compatibility; value is sigma_z.
            redshift_err = match.get('sigma_z', float('nan'))
            lap = match['lap']
            metric_val = float(get_best_metric_value(match))
            
            # Determine grade (good/bad based on security)
            grade = "good"  # Simplified - no longer using classification_secure
            
            f.write(f"{i:4d}  {name:<12} {t_type:<10} {lap:6.3f} {metric_val:6.2f} "
                   f"{redshift:9.5f} {redshift_err:9.5f} {age:7.1f} {age_flag:8d}  {grade}\n")
        
        f.write("\n")
        
        # Classification summary
        f.write("### classification summary ###\n")
        f.write(f"# Consensus type: {result.consensus_type}\n")
        f.write(f"# Best subtype: {result.best_subtype}\n")
        
        # Add clustering information if available
        if (hasattr(result, 'clustering_results') and result.clustering_results and 
            result.clustering_results.get('success')):
            best_cluster = result.clustering_results.get('best_cluster', {})
            f.write(f"# Clustering method: {result.clustering_results.get('method', 'unknown')}\n")
            # Placeholder for backward compatibility.
            f.write("# Cluster quality: \n")
            f.write(f"# Cluster size: {best_cluster.get('size', 0)}\n")
            f.write(f"# Top-5 mean score: {best_cluster.get('top_5_mean', 0):.2f}\n")
        
        
        
        # Match statistics
        if hasattr(result, 'match_statistics') and result.match_statistics:
            match_stats = result.match_statistics
            f.write(f"# Total matches: {match_stats.get('total_matches', 0)}\n")
            f.write(f"# Good matches: {match_stats.get('good_matches', 0)}\n")
            f.write(f"# Bad matches: {match_stats.get('bad_matches', 0)}\n")
            
            metric_stats = match_stats.get('metric_stats', {})
            f.write(f"# Metric range: {metric_stats.get('min', 0.0):.2f} - {metric_stats.get('max', 0.0):.2f}\n")
        
        f.write("\n")
        f.write("### End of SNID results ###\n")

def write_result(result: Any, filename: str) -> None:
    """
    Write SNID results to a file using unified formatter.
    
    Parameters:
        result: SNIDResult object
        filename (str): Output filename
    """
    try:
        # Use unified formatter for consistent output between CLI and GUI
        from snid_sage.shared.utils.results_formatter import UnifiedResultsFormatter
        from pathlib import Path
        
        # Extract spectrum name from filename
        spectrum_name = Path(filename).stem.replace('.output', '').replace('_snid', '')
        
        # Create formatter and write unified text output
        formatter = UnifiedResultsFormatter(result, spectrum_name=spectrum_name)
        formatter.save_to_file(filename, format_type='txt')
        
    except Exception as e:
        # Fallback formatter if unified formatter fails
        import logging
        logging.getLogger('snid_sage.snid.io').warning(f"Unified formatter failed, using fallback formatter: {e}")
        write_detailed_result(result, filename)


def write_fluxed_spectrum(wave: np.ndarray, flux: np.ndarray, filename: str, header: str = None) -> None:
    """
    Write a fluxed spectrum to a file.
    Only writes the non-zero flux range.
    
    Parameters:
        wave: Wavelength array (in log space)
        flux: Flux array
        filename: Output filename
        header: Optional header text
    """
    # Find non-zero flux range
    non_zero = np.where(flux != 0)[0]
    if len(non_zero) == 0:
        logging.warning(f"No non-zero flux values to write to {filename}")
        return
        
    start_idx = non_zero[0]
    end_idx = non_zero[-1] + 1
    
    # Extract the valid range
    wave_range = wave[start_idx:end_idx]
    flux_range = flux[start_idx:end_idx]
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        if header:
            f.write(f"# {header}\n")
        for w, fl in zip(wave_range, flux_range):
            f.write(f"{w:12.4f} {fl:12.4e}\n")


def write_flattened_spectrum(wave: np.ndarray, flux: np.ndarray, filename: str, header: str = None) -> None:
    """
    Write a flattened (continuum-removed) spectrum to a file.
    Only writes the non-zero flux range.
    
    Parameters:
        wave: Wavelength array
        flux: Flux array (flattened)
        filename: Output filename
        header: Optional header text
    """
    # Find non-zero flux range
    non_zero = np.where(flux != 0)[0]
    if len(non_zero) == 0:
        logging.warning(f"No non-zero flux values to write to {filename}")
        return
        
    start_idx = non_zero[0]
    end_idx = non_zero[-1] + 1
    
    # Extract the valid range
    wave_range = wave[start_idx:end_idx]
    flux_range = flux[start_idx:end_idx]
    
    with open(filename, 'w') as f:
        if header:
            f.write(f"{header}\n")
        f.write('#wavelength[A] flux[arbitrary]\n')
        for w, fl in zip(wave_range, flux_range):
            f.write(f"{w:12.5f} {fl:12.5f}\n")
    
    logging.info(f"Wrote flattened spectrum to file: {filename}")


def write_correlation(z_axis: np.ndarray, correlation: np.ndarray, filename: str, header: str = None) -> None:
    """
    Write a correlation function to a file for the full searched redshift range.
    
    Parameters:
        z_axis: Redshift axis values
        correlation: Correlation function values
        filename: Output filename
        header: Optional header text
    """
    with open(filename, 'w') as f:
        if header:
            f.write(f"{header}\n")
        f.write('#redshift correlation\n')
        for z, r in zip(z_axis, correlation):
            f.write(f"{z:10.6f} {r:12.6f}\n")
    
    logging.info(f"Wrote correlation function to file: {filename}")


def write_parameter_file(params: Dict[str, Any], filename: str = "snid.param") -> None:
    """
    Write SNID parameters to a file.
    
    Parameters:
        params: Dictionary of parameters
        filename: Output filename
    """
    with open(filename, 'w') as f:
        f.write('# SNID parameter file -- EDIT WITH CAUTION!\n')
        for key, value in params.items():
            if isinstance(value, (int, float)):
                f.write(f"{key:<12} {value:10g}\n")
            elif isinstance(value, bool):
                f.write(f"{key:<12} {int(value):10d}\n")
            elif isinstance(value, str):
                f.write(f"{key:<12} {value}\n")
            elif isinstance(value, list):
                f.write(f"{key:<12} {len(value):10d} {' '.join(str(v) for v in value)}\n")
            else:
                f.write(f"{key:<12} {str(value)}\n")
    
    logging.info(f"Wrote parameter file: {filename}")


def write_template_correlation_data(match: Dict[str, Any], template_index: int, 
                                   output_dir: str, base_filename: str) -> Dict[str, str]:
    """
    Write correlation data for a specific template.
    
    Parameters:
        match: Template match dictionary containing correlation data
        template_index: Index of the template (1-based for filenames)
        output_dir: Output directory path
        base_filename: Base filename for output files
        
    Returns:
        Dict with paths to created correlation files
    """
    output_files = {}
    output_dir = Path(output_dir)
    
    correlation_data = match.get('correlation', {})
    template = match.get('template', {})
    template_name = template.get('name', f'template_{template_index}')
    template_type = template.get('type', 'Unknown')
    template_subtype = template.get('subtype', '')
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    metric_value = float(get_best_metric_value(match))
    metric_name = str(get_best_metric_name(match))
    redshift = match.get('redshift', 0.0)
    
    # Create header with template information
    header = f"# Template: {template_name}\n"
    header += f"# Type: {template_type}"
    if template_subtype and template_subtype != 'Unknown' and template_subtype != '':
        header += f" {template_subtype}"
    header += "\n"
    header += f"# Best metric ({metric_name}): {metric_value:.3f}\n"
    header += f"# Redshift: {redshift:.6f}\n"
    header += f"# Template Index: {template_index}"
    
    # Write full correlation function
    if 'z_axis_full' in correlation_data and 'correlation_full' in correlation_data:
        corr_file = output_dir / f"{base_filename}_template_{template_index:02d}_xcor_full.dat"
        write_correlation(
            correlation_data['z_axis_full'], 
            correlation_data['correlation_full'], 
            str(corr_file),
            header=header
        )
        output_files['full_correlation'] = str(corr_file)
    
    # Write peak region correlation function
    if 'z_axis_peak' in correlation_data and 'correlation_peak' in correlation_data:
        peak_file = output_dir / f"{base_filename}_template_{template_index:02d}_xcor_peak.dat"
        write_correlation(
            correlation_data['z_axis_peak'],
            correlation_data['correlation_peak'],
            str(peak_file),
            header=header + "\n# Peak region correlation"
        )
        output_files['peak_correlation'] = str(peak_file)
    
    return output_files


def write_template_spectra_data(match: Dict[str, Any], template_index: int,
                               output_dir: str, base_filename: str) -> Dict[str, str]:
    """
    Write flux and flattened spectra data for a specific template.
    
    Parameters:
        match: Template match dictionary containing spectral data
        template_index: Index of the template (1-based for filenames)
        output_dir: Output directory path
        base_filename: Base filename for output files
        
    Returns:
        Dict with paths to created spectrum files
    """
    output_files = {}
    output_dir = Path(output_dir)
    
    template = match.get('template', {})
    template_name = template.get('name', f'template_{template_index}')
    template_type = template.get('type', 'Unknown')
    template_subtype = template.get('subtype', '')
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    metric_value = float(get_best_metric_value(match))
    metric_name = str(get_best_metric_name(match))
    redshift = match.get('redshift', 0.0)
    
    # Create header with template information
    header = f"# Template: {template_name}\n"
    header += f"# Type: {template_type}"
    if template_subtype and template_subtype != 'Unknown' and template_subtype != '':
        header += f" {template_subtype}"
    header += "\n"
    header += f"# Best metric ({metric_name}): {metric_value:.3f}\n"
    header += f"# Redshift: {redshift:.6f}\n"
    header += f"# Template Index: {template_index}"
    
    spectra_data = match.get('spectra', {})
    
    # Write flattened spectrum data
    if 'flat' in spectra_data:
        flat_data = spectra_data['flat']
        if 'wave' in flat_data and 'flux' in flat_data:
            flat_file = output_dir / f"{base_filename}_template_{template_index:02d}_flat.dat"
            write_flattened_spectrum(
                flat_data['wave'], 
                flat_data['flux'], 
                str(flat_file),
                header=header + "\n# Flattened template spectrum"
            )
            output_files['flattened'] = str(flat_file)
    
    # Write flux spectrum data
    if 'flux' in spectra_data:
        flux_data = spectra_data['flux']
        if 'wave' in flux_data and 'flux' in flux_data:
            flux_file = output_dir / f"{base_filename}_template_{template_index:02d}_flux.dat"
            write_fluxed_spectrum(
                flux_data['wave'], 
                flux_data['flux'], 
                str(flux_file),
                header=header + "\n# Unflattened template spectrum"
            )
            output_files['flux'] = str(flux_file)
    
    return output_files


def generate_template_plots(result: Any, output_dir: str, base_filename: str,
                           plot_types: List[str] = ['flux', 'flat'],
                           max_templates: int = 20,
                           figsize: Tuple[int, int] = (10, 8),
                           dpi: int = 150) -> Dict[str, List[str]]:
    """
    Generate plots for each template match.
    
    Parameters:
        result: SNIDResult object with template matches
        output_dir: Output directory path
        base_filename: Base filename for output files
        plot_types: List of plot types to generate ('flux', 'flat')
        max_templates: Maximum number of templates to plot
        figsize: Figure size for plots
        dpi: DPI for saved plots
        
    Returns:
        Dict mapping plot types to lists of generated file paths
    """
    from .plotting import plot_flux_comparison, plot_flat_comparison
    import matplotlib.pyplot as plt
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_plots = {plot_type: [] for plot_type in plot_types}
    
    if not hasattr(result, 'best_matches') or not result.best_matches:
        logging.warning("No template matches found for plot generation")
        return generated_plots
    
    # Process up to max_templates
    matches_to_plot = result.best_matches[:max_templates]
    
    for i, match in enumerate(matches_to_plot, 1):
        template_name = match.get('name', f'template_{i}')
        
        try:
            # Generate flux comparison plot
            if 'flux' in plot_types:
                flux_plot_path = output_dir / f"{base_filename}_template_{i:02d}_flux.png"
                fig = plt.figure(figsize=figsize)
                plot_flux_comparison(match, result, fig=fig)
                fig.savefig(flux_plot_path, dpi=dpi, bbox_inches='tight')
                plt.close(fig)
                generated_plots['flux'].append(str(flux_plot_path))
                logging.info(f"Generated flux plot for {template_name}: {flux_plot_path}")
            
            # Generate flattened comparison plot
            if 'flat' in plot_types:
                flat_plot_path = output_dir / f"{base_filename}_template_{i:02d}_flat.png"
                fig = plt.figure(figsize=figsize)
                plot_flat_comparison(match, result, fig=fig)
                fig.savefig(flat_plot_path, dpi=dpi, bbox_inches='tight')
                plt.close(fig)
                generated_plots['flat'].append(str(flat_plot_path))
                logging.info(f"Generated flat plot for {template_name}: {flat_plot_path}")
            

                
        except Exception as e:
            logging.error(f"Error generating plots for template {i} ({template_name}): {e}")
            continue
    
    return generated_plots


def generate_plot_metadata(result: Any, output_dir: str, base_filename: str,
                          generated_plots: Dict[str, List[str]],
                          correlation_files: Dict[str, str],
                          template_data_files: Dict[str, Dict[str, str]]) -> str:
    """
    Generate JSON metadata file listing all generated plots and data files.
    
    Parameters:
        result: SNIDResult object
        output_dir: Output directory path
        base_filename: Base filename for output files
        generated_plots: Dictionary of generated plot files by type
        correlation_files: Dictionary of correlation data files
        template_data_files: Dictionary of template data files
        
    Returns:
        Path to the generated metadata file
    """
    from datetime import datetime
    
    metadata = {
        'analysis_info': {
            'base_filename': base_filename,
            'generated_time': datetime.now().isoformat(),
            'total_matches': len(result.best_matches) if hasattr(result, 'best_matches') else 0
        },
        'plots': {
            'summary': {plot_type: len(files) for plot_type, files in generated_plots.items()},
            'files': generated_plots
        },
        'data_files': {
            'correlation_files': correlation_files,
            'template_data_files': template_data_files
        }
    }
    
    # Add analysis results if available
    if hasattr(result, 'consensus_type'):
        metadata['analysis_info']['consensus_type'] = result.consensus_type
    if hasattr(result, 'consensus_redshift'):
        metadata['analysis_info']['consensus_redshift'] = result.consensus_redshift
    
    metadata_file = Path(output_dir) / f"{base_filename}_analysis_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logging.info(f"Generated analysis metadata: {metadata_file}")
    return str(metadata_file)


def generate_output_files(result: Any, output_dir: str, base_filename: str = None, 
                         output_main: bool = True, 
                         output_fluxed: bool = False,
                         output_flattened: bool = False,
                         output_correlation: bool = False,
                         output_plots: bool = False,
                         plot_types: List[str] = None,
                         max_templates: int = 5,
                         max_plot_templates: int = 20,
                         log_wave: np.ndarray = None,
                         orig_flux: np.ndarray = None,
                         flat_flux: np.ndarray = None,
                         plot_figsize: Tuple[int, int] = (10, 8),
                         plot_dpi: int = 150) -> Dict[str, Any]:
    """
    Generate all SNID output files in the specified directory.
    
    Enhanced version that supports generating plots and correlation data 
    for all requested templates.
    
    Parameters:
        result: SNIDResult object
        output_dir: Output directory path
        base_filename: Base filename for output files
        output_main: Generate main result file
        output_fluxed: Generate fluxed spectrum file
        output_flattened: Generate flattened spectrum file
        output_correlation: Generate correlation files for templates
        output_plots: Generate plots for templates
        plot_types: Types of plots to generate ('flux', 'flat')
        max_templates: Maximum templates for correlation files
        max_plot_templates: Maximum templates for plot generation
        log_wave: Log-rebinned wavelength array
        orig_flux: Original flux array
        flat_flux: Flattened flux array
        plot_figsize: Figure size for plots
        plot_dpi: DPI for saved plots
        
    Returns:
        Enhanced dictionary with all output file information
    """
    # Create output directory if it doesn't exist
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine base filename if not provided
    if base_filename is None:
        if hasattr(result, 'input_file'):
            base_filename = Path(result.input_file).stem
        else:
            base_filename = 'snid_output'
    
    # Dictionary to store output filenames (enhanced structure)
    output_files = {
        'main_files': {},
        'template_data': {},
        'plots': {},
        'metadata': {}
    }
    
    # Set default plot types
    if plot_types is None:
        plot_types = ['flux', 'flat']
    elif 'all' in plot_types:
        plot_types = ['flux', 'flat']
    
    # Write main output file
    if output_main:
        main_file = output_dir / f"{base_filename}_snid.output"
        write_result(result, str(main_file))
        output_files['main_files']['main'] = str(main_file)
    
    # Write fluxed spectrum
    if output_fluxed and log_wave is not None and orig_flux is not None:
        fluxed_file = output_dir / f"{base_filename}_snid.fluxed"
        write_fluxed_spectrum(log_wave, orig_flux, str(fluxed_file))
        output_files['main_files']['fluxed'] = str(fluxed_file)
    
    # Write flattened spectrum
    if output_flattened and log_wave is not None and flat_flux is not None:
        flattened_file = output_dir / f"{base_filename}_snid.flattened"
        write_flattened_spectrum(log_wave, flat_flux, str(flattened_file))
        output_files['main_files']['flattened'] = str(flattened_file)
    
    # Enhanced correlation and template data output
    if output_correlation and hasattr(result, 'best_matches') and result.best_matches:
        correlation_files = {}
        template_data_files = {}
        
        # Process templates for correlation and data output
        templates_to_process = result.best_matches[:max_templates]
        
        for i, match in enumerate(templates_to_process, 1):
            template_name = match.get('name', f'template_{i}')
            
            try:
                # Write correlation data for this template
                corr_files = write_template_correlation_data(match, i, output_dir, base_filename)
                correlation_files[f'template_{i:02d}_{template_name}'] = corr_files
                
                # Write template spectra data
                spectra_files = write_template_spectra_data(match, i, output_dir, base_filename)
                template_data_files[f'template_{i:02d}_{template_name}'] = spectra_files
                
            except Exception as e:
                logging.error(f"Error writing data for template {i} ({template_name}): {e}")
                continue
        
        output_files['template_data'] = {
            'correlation_files': correlation_files,
            'spectra_files': template_data_files
        }
    
    # Generate plots if requested
    generated_plots = {}
    if output_plots and hasattr(result, 'best_matches') and result.best_matches:
        try:
            generated_plots = generate_template_plots(
                result, output_dir, base_filename,
                plot_types=plot_types,
                max_templates=max_plot_templates,
                figsize=plot_figsize,
                dpi=plot_dpi
            )
            output_files['plots'] = generated_plots
        except Exception as e:
            logging.error(f"Error generating plots: {e}")
    
    # Generate comprehensive metadata
    try:
        metadata_file = generate_plot_metadata(
            result, output_dir, base_filename,
            generated_plots,
            output_files['template_data'].get('correlation_files', {}),
            output_files['template_data'].get('spectra_files', {})
        )
        output_files['metadata']['analysis_metadata'] = metadata_file
    except Exception as e:
        logging.error(f"Error generating metadata: {e}")
    
    return output_files


def get_template_info(library_path: str) -> Dict[str, Any]:
    """
    Get information about templates in a library.
    
    This function supports unified storage and optional text-based template folders.
    It will automatically detect and use H5 storage when available.
    
    Parameters:
        library_path (str): Path to template library
        
    Returns:
        Dict: Information about the templates
    """
    # Try H5 unified storage first
    try:
        from snid_sage.snid.template_fft_storage import TemplateFFTStorage
        
        storage = TemplateFFTStorage(library_path)
        if storage.is_built():
            _LOG.info("Using H5 unified storage for template info")
            return storage.get_template_info_for_gui()
        else:
            _LOG.error("Unified storage index/files missing. SNID-SAGE expects prebuilt HDF5/index; .lnw fallback is disabled.")
            return {
                'path': library_path,
                'total': 0,
                'types': {},
                'templates': []
            }
    except ImportError:
        _LOG.error("Template storage module not available. Ensure installation includes HDF5/index support.")
    except Exception as e:
        _LOG.error(f"Error accessing H5 storage: {e}")
    
    # No fallback; return empty info structure to signal missing storage
    return {
        'path': library_path,
        'total': 0,
        'types': {},
        'templates': []
    }


def create_template_library(output_dir: str, name: str) -> str:
    """
    Create a new template library directory.
    
    Parameters:
        output_dir (str): Directory where the library should be created
        name (str): Name of the template library
        
    Returns:
        str: Path to the created library directory
    """
    library_path = os.path.join(output_dir, name)
    
    # Create directory if it doesn't exist
    os.makedirs(library_path, exist_ok=True)
    
    # Create metadata file
    metadata = {
        'name': name,
        'created': datetime.now().isoformat(),
        'version': '1.0',
        'description': f'SNID template library: {name}'
    }
    
    metadata_file = os.path.join(library_path, 'metadata.json')
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return library_path


def add_template(library_path: str, spectrum_file: str, template_info: Dict[str, Any], 
                force_rebin: bool = False) -> str:
    """
    Add a template to a library.
    
    Parameters:
        library_path (str): Path to the template library
        spectrum_file (str): Path to the spectrum file to add
        template_info (Dict): Dictionary with template metadata (name, type, subtype, age, etc.)
        force_rebin (bool): Whether to force rebinning even for .lnw files
        
    Returns:
        str: Path to the added template file
    """
    # Read the spectrum
    wave, flux = read_spectrum(spectrum_file)
    
    # Generate template filename
    name = template_info.get('name', os.path.splitext(os.path.basename(spectrum_file))[0])
    template_file = os.path.join(library_path, f"{name}.lnw")
    
    # Process spectrum if needed
    if template_info.get('flatten', True) or force_rebin:
        # Apply log rebinning and continuum fitting
        log_wave, log_flux = log_rebin(wave, flux)
        flat_flux, cont = fit_continuum(log_flux, method="spline")
        
        # Use flattened spectrum
        wave = log_wave
        flux = flat_flux
    
    # Write template file with metadata header
    with open(template_file, 'w') as f:
        # Write header with metadata
        f.write(f"# Template: {name}\n")
        f.write(f"# Type: {template_info.get('type', 'Unknown')}\n")
        f.write(f"# Subtype: {template_info.get('subtype', 'Unknown')}\n")
        if template_info.get('age') is not None:
            f.write(f"# Age: {template_info['age']:.1f}\n")
        f.write(f"# Source: {spectrum_file}\n")
        f.write(f"# Created: {datetime.now().isoformat()}\n")
        f.write("#\n")
        
        # Write spectrum data
        for w, f_val in zip(wave, flux):
            f.write(f"{w:.3f} {f_val:.6e}\n")
    
    return template_file


def remove_template(library_path: str, template_name: str) -> bool:
    """
    Remove a template from a library.
    
    Parameters:
        library_path (str): Path to the template library
        template_name (str): Name of the template to remove
        
    Returns:
        bool: True if template was removed, False if not found
    """
    template_file = os.path.join(library_path, f"{template_name}.lnw")
    
    if os.path.exists(template_file):
        os.remove(template_file)
        return True
    else:
        return False


def merge_template_libraries(output_dir: str, library_paths: List[str], name: str) -> str:
    """
    Merge multiple template libraries into one.
    
    Parameters:
        output_dir (str): Directory where the merged library should be created
        library_paths (List[str]): List of paths to libraries to merge
        name (str): Name of the merged library
        
    Returns:
        str: Path to the merged library
    """
    import shutil
    
    # Create new library
    merged_path = create_template_library(output_dir, name)
    
    # Copy templates from all libraries
    for library_path in library_paths:
        if os.path.exists(library_path):
            # Find all template files
            template_files = glob.glob(os.path.join(library_path, "*.lnw"))
            
            for template_file in template_files:
                # Copy to merged library
                dest_file = os.path.join(merged_path, os.path.basename(template_file))
                shutil.copy2(template_file, dest_file)
    
    return merged_path


def save_template(wave: np.ndarray, flux: np.ndarray, filename: str, 
                 header_info: Dict[str, Any] = None) -> None:
    """
    Save a template spectrum to a .lnw file.
    
    Parameters:
        wave (np.ndarray): Wavelength array (log space)
        flux (np.ndarray): Flux array
        filename (str): Output filename
        header_info (Dict): Optional header information
    """
    with open(filename, 'w') as f:
        # Write header with metadata
        f.write("# SNID Template File\n")
        f.write(f"# Created: {datetime.now().isoformat()}\n")
        
        if header_info:
            for key, value in header_info.items():
                f.write(f"# {key}: {value}\n")
        
        f.write("#\n")
        f.write("# Log_Wavelength Flux\n")
        
        # Write spectrum data
        for w, f_val in zip(wave, flux):
            f.write(f"{w:.6f} {f_val:.6e}\n")

