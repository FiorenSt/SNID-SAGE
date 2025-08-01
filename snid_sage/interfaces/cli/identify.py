"""
SNID Identify Command
====================

Command for identifying supernova spectra using SNID with cluster-aware analysis,
comprehensive plotting, and detailed outputs matching the batch mode capabilities.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
import os
import csv
import numpy as np

from snid_sage.snid.snid import preprocess_spectrum, run_snid_analysis, SNIDResult
from snid_sage.snid.io import read_spectrum
from snid_sage.shared.utils.math_utils import calculate_inverse_variance_weighted_redshift, calculate_hybrid_weighted_redshift, calculate_rlap_weighted_age

# Import and apply centralized font configuration for consistent plotting
try:
    from snid_sage.shared.utils.plotting.font_sizes import apply_font_config
    apply_font_config()
except ImportError:
    # Fallback if font configuration is not available
    pass


class CLIProgressIndicator:
    """
    Simple CLI progress indicator with template counting, similar to GUI progress bars.
    Shows a nice progress bar with template counter and estimated time remaining.
    """
    
    def __init__(self, total_templates: int = 0, show_bar: bool = True):
        self.total_templates = total_templates
        self.current_template = 0
        self.show_bar = show_bar
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_template_count = 0
        
    def update(self, message: str, template_count: Optional[int] = None):
        """Update the progress indicator"""
        current_time = time.time()
        
        # Update template count if provided
        if template_count is not None:
            self.current_template = template_count
        
        # Only update display every 0.5 seconds to avoid spam
        if current_time - self.last_update_time < 0.5 and template_count is None:
            return
            
        self.last_update_time = current_time
        
        # Calculate progress
        if self.total_templates > 0:
            progress = min(self.current_template / self.total_templates, 1.0)
            percent = progress * 100
            
            # Estimate time remaining
            elapsed = current_time - self.start_time
            if self.current_template > 0:
                avg_time_per_template = elapsed / self.current_template
                remaining_templates = self.total_templates - self.current_template
                eta_seconds = remaining_templates * avg_time_per_template
                
                if eta_seconds < 60:
                    eta_str = f"{eta_seconds:.0f}s"
                elif eta_seconds < 3600:
                    eta_str = f"{eta_seconds/60:.1f}m"
                else:
                    eta_str = f"{eta_seconds/3600:.1f}h"
            else:
                eta_str = "calculating..."
            
            # Create progress bar
            if self.show_bar:
                bar_width = 40
                filled_width = int(bar_width * progress)
                bar = "█" * filled_width + "░" * (bar_width - filled_width)
                
                # Format the progress line
                progress_line = f"\r🔍 [{bar}] {self.current_template}/{self.total_templates} ({percent:.1f}%) ETA: {eta_str}"
            else:
                progress_line = f"\r🔍 Template {self.current_template}/{self.total_templates} ({percent:.1f}%) ETA: {eta_str}"
            
            # Print progress (overwrite previous line)
            print(progress_line, end="", flush=True)
        else:
            # No total count, just show current
            print(f"\r🔍 {message}", end="", flush=True)
    
    def finish(self, message: str = "Complete"):
        """Finish the progress indicator"""
        if self.total_templates > 0:
            elapsed = time.time() - self.start_time
            if elapsed < 60:
                time_str = f"{elapsed:.1f}s"
            elif elapsed < 3600:
                time_str = f"{elapsed/60:.1f}m"
            else:
                time_str = f"{elapsed/3600:.1f}h"
            
            print(f"\r[SUCCESS] {message} ({self.total_templates} templates in {time_str})")
        else:
            print(f"\r[SUCCESS] {message}")


def _extract_spectrum_name(spectrum_path: str) -> str:
    """Extract a clean spectrum name from file path."""
    return Path(spectrum_path).stem


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the identify command."""
    # Set epilog with examples
    parser.epilog = """
Examples:
  # Basic identification with auto-discovered templates
  snid identify spectrum.txt --output-dir results/
  
  # Basic identification with explicit templates directory
  snid identify spectrum.txt templates/ --output-dir results/
  
  # With Savitzky-Golay smoothing (11-pixel window, 3rd order polynomial)
  snid identify spectrum.txt --output-dir results/ --savgol-window 11 --savgol-order 3
  
  # With wavelength-based Savitzky-Golay smoothing (5 Angstrom FWHM)
  snid identify spectrum.txt --output-dir results/ --savgol-fwhm 5.0 --savgol-order 3
  
  # Minimal mode - main result file only, no additional outputs
  snid identify spectrum.txt --output-dir results/ --minimal
  
  # Complete mode - all outputs + comprehensive GUI-style plots
  snid identify spectrum.txt --output-dir results/ --complete
  
  # Force specific redshift (skips redshift search)
  snid identify spectrum.txt --forced-redshift 0.05 --output-dir results/
  
  # Use only specific templates with complete analysis
  snid identify spectrum.txt --template-filter sn1994I sn2004aw sn2007gr --complete --output-dir results/
  
  # Filter by supernova type with comprehensive outputs
  snid identify spectrum.txt --type-filter Ia IIn --complete --output-dir results/
  
  # Age filtering with full analysis
  snid identify spectrum.txt --age-min 0 --age-max 20 --complete --output-dir results/
    """
    # Required arguments
    parser.add_argument(
        "spectrum_path", 
        help="Path to the input spectrum file"
    )
    parser.add_argument(
        "templates_dir", 
        nargs="?",  # Make optional
        help="Path to directory containing template spectra (optional - auto-discovers if not provided)"
    )
    
    # Processing modes (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--minimal", 
        action="store_true",
        help="Minimal mode: Main result file only, no additional outputs or plots (like batch --minimal)"
    )
    mode_group.add_argument(
        "--complete", 
        action="store_true",
        help="Complete mode: All outputs including comprehensive GUI-style plots (like batch --complete)"
    )
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--output-dir", "-o", 
        required=True,
        help="Directory for output files (required)"
    )
    
    # Analysis parameters
    analysis_group = parser.add_argument_group("Analysis Parameters")
    analysis_group.add_argument(
        "--zmin", 
        type=float, 
        default=-0.01, 
        help="Minimum redshift to consider"
    )
    analysis_group.add_argument(
        "--zmax", 
        type=float, 
        default=1.0, 
        help="Maximum redshift to consider"
    )
    analysis_group.add_argument(
        "--rlapmin", 
        type=float, 
        default=5.0, 
        help="Minimum rlap value required"
    )
    analysis_group.add_argument(
        "--lapmin", 
        type=float, 
        default=0.3, 
        help="Minimum overlap fraction required"
    )
    # Analysis options completed
    
    # Preprocessing options
    preproc_group = parser.add_argument_group("Preprocessing Options")
    preproc_group.add_argument(
        "--savgol-window", 
        type=int, 
        default=0, 
        help="Savitzky-Golay filter window size in pixels (0 = no filtering, default: 0)"
    )
    preproc_group.add_argument(
        "--savgol-order", 
        type=int, 
        default=3, 
        help="Savitzky-Golay filter polynomial order"
    )
    preproc_group.add_argument(
        "--savgol-fwhm", 
        type=float, 
        default=0.0, 
        help="Savitzky-Golay filter FWHM in Angstroms (alternative to --savgol-window, default: 0.0)"
    )
    preproc_group.add_argument(
        "--aband-remove", 
        action="store_true", 
        help="Remove telluric A-band"
    )
    preproc_group.add_argument(
        "--skyclip", 
        action="store_true", 
        help="Clip sky emission lines"
    )
    preproc_group.add_argument(
        "--emclip-z", 
        type=float, 
        default=-1.0, 
        help="Redshift at which to clip emission lines (-1 to disable)"
    )
    preproc_group.add_argument(
        "--emwidth", 
        type=float, 
        default=40.0, 
        help="Width in Angstroms for emission line clipping"
    )
    preproc_group.add_argument(
        "--apodize-percent", 
        type=float, 
        default=10.0, 
        help="Percentage of spectrum ends to apodize"
    )
    preproc_group.add_argument(
        "--wavelength-masks", 
        nargs="+", 
        metavar="WMIN:WMAX", 
        help="Wavelength ranges to mask out (format: 6550:6600 7600:7700)"
    )
    
    # Template filtering
    template_group = parser.add_argument_group("Template Filtering")
    template_group.add_argument(
        "--age-min", 
        type=float, 
        help="Minimum template age in days"
    )
    template_group.add_argument(
        "--age-max", 
        type=float, 
        help="Maximum template age in days"
    )
    template_group.add_argument(
        "--type-filter", 
        nargs="+", 
        help="Only use templates of these types"
    )
    template_group.add_argument(
        "--template-filter", 
        nargs="+", 
        help="Only use specific templates (by name)"
    )
    template_group.add_argument(
        "--exclude-templates", 
        nargs="+", 
        help="Exclude specific templates from analysis (by name)"
    )
    
    # Redshift analysis
    redshift_group = parser.add_argument_group("Redshift Analysis")
    redshift_group.add_argument(
        "--forced-redshift", 
        type=float, 
        help="Force analysis to this specific redshift (skips redshift search)"
    )
    
    # Advanced options
    advanced_group = parser.add_argument_group("Advanced Options")
    advanced_group.add_argument(
        "--peak-window-size", 
        type=int, 
        default=10, 
        help="Peak detection window size"
    )
    advanced_group.add_argument(
        "--max-output-templates", 
        type=int, 
        default=10, 
        help="Maximum number of templates to output"
    )

    advanced_group.add_argument(
        "--save-plots", 
        action="store_true", 
        help="Save plots to files"
    )
    
    # General options
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Print detailed processing information"
    )


def _get_winning_cluster(result: SNIDResult) -> Optional[Dict[str, Any]]:
    """
    Get the winning cluster from SNID results (user selected or automatic best).
    
    This matches the GUI's cluster selection logic.
    """
    if not (hasattr(result, 'clustering_results') and 
            result.clustering_results and 
            result.clustering_results.get('success')):
        return None
    
    clustering_results = result.clustering_results
    
    # Priority: user_selected_cluster > best_cluster
    if 'user_selected_cluster' in clustering_results:
        return clustering_results['user_selected_cluster']
    elif 'best_cluster' in clustering_results:
        return clustering_results['best_cluster']
    
    return None


def _create_cluster_aware_summary(result: SNIDResult, spectrum_name: str, spectrum_path: str) -> Dict[str, Any]:
    """
    Create GUI-style cluster-aware summary with winning cluster analysis.
    
    This matches the GUI's approach of using the winning cluster for all analysis
    rather than mixing all matches above threshold.
    """
    # Get the winning cluster (user selected or automatic best)
    winning_cluster = _get_winning_cluster(result)
    cluster_matches = []
    
    if winning_cluster:
        cluster_matches = winning_cluster.get('matches', [])
        # Sort cluster matches by best available metric (RLAP-Cos if available, otherwise RLAP) descending
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        cluster_matches = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
    
    # If no clustering or cluster, fall back to filtered_matches, then best_matches
    if not cluster_matches:
        if hasattr(result, 'filtered_matches') and result.filtered_matches:
            cluster_matches = result.filtered_matches
            # Sort by best available metric (RLAP-Cos if available, otherwise RLAP) descending
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            cluster_matches = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
        elif hasattr(result, 'best_matches') and result.best_matches:
            cluster_matches = result.best_matches
            # Sort by best available metric (RLAP-Cos if available, otherwise RLAP) descending
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            cluster_matches = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
    
    # Create the summary using winning cluster data
    summary = {
        'spectrum': spectrum_name,
        'file_path': spectrum_path,
        'success': True,
        'best_template': result.template_name,
        'best_template_type': result.template_type,
        'best_template_subtype': result.template_subtype,
        'consensus_type': result.consensus_type,
        'consensus_subtype': result.best_subtype,
        'redshift': result.redshift,
        'redshift_error': result.redshift_error,
        'rlap': result.rlap,


        'runtime': result.runtime_sec,
        'has_clustering': winning_cluster is not None,
        'cluster_size': len(cluster_matches) if cluster_matches else 0,
    }
    
    # Add cluster statistics if available
    if winning_cluster:
        summary['cluster_type'] = winning_cluster.get('type', 'Unknown')
        summary['cluster_score'] = winning_cluster.get('composite_score', 0.0)
        summary['cluster_method'] = 'Type-specific GMM'
        
        # Add new quality metrics
        if 'quality_assessment' in winning_cluster:
            qa = winning_cluster['quality_assessment']
            summary['cluster_quality_category'] = qa.get('quality_category', 'Unknown')
            summary['cluster_quality_description'] = qa.get('quality_description', '')
            summary['cluster_mean_top_5'] = qa.get('mean_top_5', 0.0)
            summary['cluster_penalized_score'] = qa.get('penalized_score', 0.0)
        
        if 'confidence_assessment' in winning_cluster:
            ca = winning_cluster['confidence_assessment']
            summary['cluster_confidence_level'] = ca.get('confidence_level', 'unknown')
            summary['cluster_confidence_description'] = ca.get('confidence_description', '')
            summary['cluster_statistical_significance'] = ca.get('statistical_significance', 'unknown')
            summary['cluster_second_best_type'] = ca.get('second_best_type', 'N/A')
        
        # Calculate enhanced cluster statistics using hybrid methods
        if cluster_matches:
            redshifts = np.array([m['redshift'] for m in cluster_matches])
            rlaps = np.array([m['rlap'] for m in cluster_matches])
            redshift_errors = np.array([m.get('redshift_error', 0) for m in cluster_matches])
            
            # Calculate cluster-level statistics using proper statistical methods
            z_final, z_final_err, cluster_scatter = calculate_hybrid_weighted_redshift(
                redshifts, redshift_errors, include_cluster_scatter=True
            )
            
            summary['cluster_redshift_weighted'] = z_final
            summary['cluster_redshift_weighted_uncertainty'] = z_final_err
            summary['cluster_redshift_scatter'] = cluster_scatter
            # Only enhanced redshift estimate is needed - no median/mean calculations
            summary['cluster_rlap_mean'] = np.mean(rlaps)
            
            # Enhanced age estimation if available  
            ages = []
            age_rlaps = []
            for m in cluster_matches:
                template = m.get('template', {})
                age = template.get('age', 0.0) if template else 0.0
                if age > 0:
                    ages.append(age)
                    # Use RLAP-cos if available, otherwise RLAP
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    age_rlaps.append(get_best_metric_value(m))
            
            if ages:
                age_mean, age_stat_error, age_total_error, age_scatter = calculate_rlap_weighted_age(
                    np.array(ages), np.array(age_rlaps), include_cluster_scatter=True
                )
                summary['cluster_age_weighted'] = age_mean
                summary['cluster_age_uncertainty'] = age_total_error
                summary['cluster_age_scatter'] = age_scatter
            
            # Subtype composition within cluster (GUI-style)
            from collections import Counter
            subtypes = []
            for m in cluster_matches:
                template = m.get('template', {})
                subtype = template.get('subtype', 'Unknown') if template else 'Unknown'
                if not subtype or subtype.strip() == '':
                    subtype = 'Unknown'
                subtypes.append(subtype)
            
            subtype_counts = Counter(subtypes)
            subtype_fractions = {}
            for subtype, count in subtype_counts.items():
                subtype_fractions[subtype] = count / len(cluster_matches)
            
            # Sort subtypes by frequency
            sorted_subtypes = sorted(subtype_fractions.items(), key=lambda x: x[1], reverse=True)
            summary['cluster_subtypes'] = sorted_subtypes[:5]  # Top 5 subtypes
    
    # Fallback to old approach only if no clustering available
    else:
        summary['cluster_method'] = 'No clustering'
        # Use type/subtype fractions as fallback
        if hasattr(result, 'type_fractions') and result.type_fractions:
            sorted_types = sorted(result.type_fractions.items(), key=lambda x: x[1], reverse=True)
            summary['top_types'] = sorted_types[:3]
        else:
            summary['top_types'] = [(result.consensus_type, 1.0)]
        
        if (hasattr(result, 'subtype_fractions') and result.subtype_fractions and 
            result.consensus_type in result.subtype_fractions):
            subtype_data = result.subtype_fractions[result.consensus_type]
            sorted_subtypes = sorted(subtype_data.items(), key=lambda x: x[1], reverse=True)
            summary['cluster_subtypes'] = sorted_subtypes[:3]
        else:
            summary['cluster_subtypes'] = [(result.best_subtype or 'Unknown', 1.0)]
    
    return summary


def _save_spectrum_outputs(
    result: SNIDResult,
    spectrum_path: str,
    output_dir: Path,
    args: argparse.Namespace
) -> None:
    """
    Save spectrum outputs based on the analysis mode using GUI-style cluster-aware approach.
    
    This matches the comprehensive output system from batch mode.
    """
    try:
        if args.minimal:
            # Minimal mode: save main result file only
            from snid_sage.snid.io import write_result
            spectrum_name = Path(spectrum_path).stem
            output_file = output_dir / f"{spectrum_name}.output"
            write_result(result, str(output_file))
            
        elif args.complete:
            # Complete mode: save all outputs including comprehensive plots and data files
            from snid_sage.snid.io import (
                write_result, write_fluxed_spectrum, write_flattened_spectrum,
                write_correlation, write_template_correlation_data, write_template_spectra_data
            )
            from snid_sage.snid.plotting import (
                plot_redshift_age, plot_cluster_subtype_proportions,
                plot_flux_comparison, plot_flat_comparison, plot_correlation_view
            )
            
            spectrum_name = Path(spectrum_path).stem
            
            # Save main result file
            output_file = output_dir / f"{spectrum_name}.output"
            write_result(result, str(output_file))
            
            # Save additional spectrum files
            if hasattr(result, 'processed_spectrum'):
                # Save fluxed spectrum
                if 'log_wave' in result.processed_spectrum and 'log_flux' in result.processed_spectrum:
                    fluxed_file = output_dir / f"{spectrum_name}.fluxed"
                    write_fluxed_spectrum(
                        result.processed_spectrum['log_wave'], 
                        result.processed_spectrum['log_flux'], 
                        str(fluxed_file)
                    )
                
                # Save flattened spectrum
                if 'log_wave' in result.processed_spectrum and 'flat_flux' in result.processed_spectrum:
                    flat_file = output_dir / f"{spectrum_name}.flattened"
                    write_flattened_spectrum(
                        result.processed_spectrum['log_wave'], 
                        result.processed_spectrum['flat_flux'], 
                        str(flat_file)
                    )
            
            if result.success:
                # Get winning cluster for GUI-style plotting
                winning_cluster = _get_winning_cluster(result)
                cluster_matches = winning_cluster.get('matches', []) if winning_cluster else []
                
                # Use cluster matches for plotting, fallback to filtered/best matches
                plot_matches = cluster_matches
                if not plot_matches:
                    if hasattr(result, 'filtered_matches') and result.filtered_matches:
                        plot_matches = result.filtered_matches
                    elif hasattr(result, 'best_matches') and result.best_matches:
                        plot_matches = result.best_matches
                
                # CRITICAL: Sort all plot matches by best available metric (RLAP-Cos if available, otherwise RLAP) descending
                if plot_matches:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    plot_matches = sorted(plot_matches, key=get_best_metric_value, reverse=True)
                
                # 1. 3D GMM Clustering Visualization (GUI-style)
                if (hasattr(result, 'clustering_results') and 
                    result.clustering_results and 
                    result.clustering_results.get('success')):
                    try:
                        # Use correct 3D GMM clustering plot like GUI does
                        from snid_sage.snid.plotting_3d import plot_3d_type_clustering
                        import matplotlib.pyplot as plt
                        
                        gmm_file = output_dir / f"{spectrum_name}_3d_gmm_clustering.png"
                        fig = plot_3d_type_clustering(result.clustering_results, save_path=str(gmm_file))
                        plt.close(fig)  # Prevent memory leak
                        
                    except Exception as e:
                        import logging
                        logging.getLogger('snid_sage.snid.identify').debug(f"3D GMM clustering plot failed: {e}")
                
                # 2. Redshift vs Age plot (cluster-aware)
                try:
                    import matplotlib.pyplot as plt
                    redshift_age_file = output_dir / f"{spectrum_name}_redshift_age.png"
                    fig = plot_redshift_age(result, save_path=str(redshift_age_file))
                    plt.close(fig)  # Prevent memory leak
                except Exception as e:
                    import logging
                    logging.getLogger('snid_sage.snid.identify').debug(f"Redshift-age plot failed: {e}")
                
                # 3. Cluster-aware subtype proportions (GUI-style)
                try:
                    import matplotlib.pyplot as plt
                    subtype_file = output_dir / f"{spectrum_name}_cluster_subtypes.png"
                    fig = plot_cluster_subtype_proportions(
                        result, 
                        selected_cluster=winning_cluster,
                        save_path=str(subtype_file)
                    )
                    plt.close(fig)  # Prevent memory leak
                except Exception as e:
                    import logging
                    logging.getLogger('snid_sage.snid.identify').debug(f"Cluster subtype plot failed: {e}")
                
                # 4. Flux spectrum plot (best match) - same as GUI
                if plot_matches:
                    try:
                        import matplotlib.pyplot as plt
                        flux_file = output_dir / f"{spectrum_name}_flux_spectrum.png"
                        fig = plot_flux_comparison(plot_matches[0], result, save_path=str(flux_file))
                        plt.close(fig)  # Prevent memory leak
                    except Exception as e:
                        import logging
                        logging.getLogger('snid_sage.snid.identify').debug(f"Flux spectrum plot failed: {e}")
                    
                    # 5. Flattened spectrum plot (best match) - same as GUI
                    try:
                        import matplotlib.pyplot as plt
                        flat_file = output_dir / f"{spectrum_name}_flattened_spectrum.png"
                        fig = plot_flat_comparison(plot_matches[0], result, save_path=str(flat_file))
                        plt.close(fig)  # Prevent memory leak
                    except Exception as e:
                        import logging
                        logging.getLogger('snid_sage.snid.identify').debug(f"Flattened spectrum plot failed: {e}")
                
                # Save correlation function data files
                if hasattr(result, 'best_matches') and result.best_matches:
                    # Main correlation function
                    best_match = result.best_matches[0]
                    if 'correlation' in best_match:
                        corr_data = best_match['correlation']
                        if 'z_axis_full' in corr_data and 'correlation_full' in corr_data:
                            corr_data_file = output_dir / f"{spectrum_name}_correlation.dat"
                            write_correlation(
                                corr_data['z_axis_full'], 
                                corr_data['correlation_full'],
                                str(corr_data_file),
                                header=f"Cross-correlation function for {spectrum_name}"
                            )
                    
                    # Template-specific correlation and spectra data (top 5)
                    for i, match in enumerate(result.best_matches[:5], 1):
                        try:
                            # Template correlation data
                            write_template_correlation_data(match, i, str(output_dir), spectrum_name)
                            
                            # Template spectra data
                            write_template_spectra_data(match, i, str(output_dir), spectrum_name)
                        except Exception as e:
                            import logging
                            logging.getLogger('snid_sage.snid.identify').warning(f"Failed to save template {i} data: {e}")
                
        else:
            # Default mode: save main outputs only
            from snid_sage.snid.io import write_result
            spectrum_name = Path(spectrum_path).stem
            output_file = output_dir / f"{spectrum_name}.output"
            write_result(result, str(output_file))
            
    except Exception as e:
        import logging
        logging.getLogger('snid_sage.snid.identify').warning(f"Failed to save outputs: {e}")





def _validate_and_fix_templates_dir(templates_dir: Optional[str]) -> str:
    """
    Validate templates directory and auto-correct if needed.
    
    Args:
        templates_dir: Path to templates directory (None to auto-discover)
        
    Returns:
        Valid templates directory path
        
    Raises:
        FileNotFoundError: If no valid templates directory can be found
    """
    # If no templates directory provided, auto-discover
    if templates_dir is None:
        try:
            from snid_sage.shared.utils.simple_template_finder import find_templates_directory_or_raise
            auto_found_dir = find_templates_directory_or_raise()
            print(f"[SUCCESS] Auto-discovered templates at: {auto_found_dir}")
            return str(auto_found_dir)
        except (ImportError, FileNotFoundError):
            raise FileNotFoundError(
                "Could not auto-discover templates directory. Please provide templates_dir explicitly."
            )
    
    # Check if provided directory exists and is valid
    if os.path.exists(templates_dir):
        return templates_dir
    
    # Try to auto-find templates directory
    try:
        from snid_sage.shared.utils.simple_template_finder import find_templates_directory_or_raise
        auto_found_dir = find_templates_directory_or_raise()
        print(f"⚠️  Templates directory '{templates_dir}' not found.")
        print(f"✅ Auto-discovered templates at: {auto_found_dir}")
        return str(auto_found_dir)
    except (ImportError, FileNotFoundError):
        # Fallback failed
        raise FileNotFoundError(f"Templates directory not found: {templates_dir}")


def main(args: argparse.Namespace) -> int:
    """Main entry point for spectrum identification."""
    try:
        # Use centralized logging system instead of creating our own handler
        from snid_sage.shared.utils.logging import configure_logging, get_logger, VerbosityLevel
        
        # Configure logging based on verbosity
        # For CLI mode, default to QUIET (warnings/errors only) unless verbose is requested
        if args.verbose:
            verbosity = VerbosityLevel.VERBOSE
        else:
            verbosity = VerbosityLevel.QUIET  # Only show warnings and errors, not INFO messages
            
        configure_logging(verbosity=verbosity, gui_mode=False)
        logger = get_logger('cli.identify')
        
        # Validate inputs
        if not os.path.exists(args.spectrum_path):
            print(f"[ERROR] Spectrum file not found: {args.spectrum_path}", file=sys.stderr)
            return 1
        
        # Validate and auto-correct templates directory
        try:
            args.templates_dir = _validate_and_fix_templates_dir(args.templates_dir)
        except FileNotFoundError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 1
        
        # Additional suppression for CLI mode - silence specific noisy loggers
        if not args.verbose:
            import logging
            # Suppress the most verbose loggers that users don't need to see
            logging.getLogger('snid_sage.snid.pipeline').setLevel(logging.WARNING)
            logging.getLogger('snid_sage.snid.pipeline').setLevel(logging.WARNING)
            logging.getLogger('snid_sage.snid.optimization_integration').setLevel(logging.WARNING)
            logging.getLogger('snid_sage.snid.optimization_integration').setLevel(logging.WARNING)
        
        if args.verbose:
            logger.info(f"Starting SNID analysis for: {args.spectrum_path}")
            logger.info(f"Templates directory: {args.templates_dir}")
            logger.info(f"Redshift range: {args.zmin} to {args.zmax}")
            logger.info(f"RLAP threshold: {args.rlapmin}")
        
        # Run preprocessing and analysis
        spectrum_name = _extract_spectrum_name(args.spectrum_path)
        
        # Load spectrum
        wavelength, flux = read_spectrum(args.spectrum_path)
        
        # Prepare savgol filter parameters  
        savgol_window = args.savgol_window if args.savgol_window > 0 else 0
        savgol_fwhm = args.savgol_fwhm if args.savgol_fwhm > 0 else 0.0
        
        # Preprocess spectrum
        processed_spectrum, preprocessing_trace = preprocess_spectrum(
            args.spectrum_path,
                savgol_window=savgol_window,
            savgol_fwhm=savgol_fwhm,
            savgol_order=args.savgol_order,
                aband_remove=args.aband_remove,
                skyclip=args.skyclip,
            emclip_z=args.emclip_z,
            emwidth=args.emwidth,
            wavelength_masks=args.wavelength_masks,
            apodize_percent=args.apodize_percent,
                verbose=args.verbose
            )
            
        # Prepare age range
        age_range = None
        if args.age_min is not None or args.age_max is not None:
            age_range = (args.age_min, args.age_max)
        
        # Create progress indicator - show by default unless verbose mode
        if args.verbose:
            # Verbose mode: no progress bar (relies on detailed logging)
            progress_callback = None
        else:
            # Default: show nice progress bar for all modes (minimal, normal, complete)
            print("🔍 Starting SNID analysis...")
            progress_indicator = CLIProgressIndicator(total_templates=0, show_bar=True)
            
            def progress_callback(message: str, template_count: Optional[int] = None):
                """Progress callback that updates our CLI progress indicator"""
                # Parse template messages to extract counts
                if "Processing template" in message and "/" in message:
                    try:
                        # Extract numbers from message like "Processing template 15/120"
                        parts = message.split("Processing template ")[1]
                        current, total = map(int, parts.split("/"))
                        
                        # Initialize total if not set
                        if progress_indicator.total_templates == 0:
                            progress_indicator.total_templates = total
                        
                        progress_indicator.update("", template_count=current)
                    except (ValueError, IndexError):
                        progress_indicator.update(message)
                elif "templates loaded" in message.lower():
                    # Extract template count from loading message
                    try:
                        import re
                        match = re.search(r'(\d+)\s+templates', message)
                        if match:
                            total = int(match.group(1))
                            progress_indicator.total_templates = total
                            progress_indicator.update(f"Loaded {total} templates")
                    except:
                        progress_indicator.update(message)
                else:
                    progress_indicator.update(message)
        
        # Run SNID analysis
        result, analysis_trace = run_snid_analysis(
            processed_spectrum,
            args.templates_dir,
                zmin=args.zmin,
                zmax=args.zmax,
            age_range=age_range,
                type_filter=args.type_filter,
                template_filter=args.template_filter,
            exclude_templates=getattr(args, 'exclude_templates', None),
            peak_window_size=args.peak_window_size,
            lapmin=args.lapmin,
                rlapmin=args.rlapmin,

            forced_redshift=args.forced_redshift,
            max_output_templates=args.max_output_templates,
                verbose=args.verbose,
            show_plots=False,  # CLI mode - no interactive plots
            save_plots=args.save_plots,
            plot_dir=args.output_dir if args.save_plots else None,
            progress_callback=progress_callback  # Add progress callback
        )
        
        # Finish progress indicator
        if not args.verbose:  # Both minimal and normal modes have progress indicators
            if result and result.success:
                progress_indicator.finish("Analysis complete")
            else:
                progress_indicator.finish("Analysis failed")
            print()  # Add newline after progress
        
        if not result or not result.success:
            print(f"\n[ERROR] SNID analysis failed for {spectrum_name}")
            if hasattr(result, 'error_message'):
                print(f"   Error: {result.error_message}")
            return 1
        

        
        # ============================================================================
        # SAVE OUTPUTS AND PLOTS (if requested)
        # ============================================================================
        if result.success:
            # Save outputs based on mode (minimal, complete, or default)
            output_dir_path = Path(args.output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            
            # CRITICAL FIX: Don't overwrite the processed_spectrum from SNID analysis!
            # The SNID analysis already correctly stores the processed spectrum with apodized versions.
            # Overwriting it with the original preprocessed spectrum loses the apodization information.
            # Instead, merge the additional preprocessing info needed for complete output generation.
            if not hasattr(result, 'processed_spectrum') or not result.processed_spectrum:
                # Fallback: only set if SNID analysis didn't create one
                result.processed_spectrum = processed_spectrum
            else:
                # Enhance the existing processed_spectrum with full preprocessing data for output generation
                # Add the missing keys that are needed for complete file output
                for key in ['tapered_flux', 'left_edge', 'right_edge', 'grid_params']:
                    if key in processed_spectrum and key not in result.processed_spectrum:
                        result.processed_spectrum[key] = processed_spectrum[key]
            
            # Save outputs
            _save_spectrum_outputs(result, args.spectrum_path, output_dir_path, args)
        
        # ============================================================================
        # UNIFIED RESULTS SUMMARY: Using unified formatter for consistency with GUI
        # ============================================================================
        if result.success:
            try:
                from snid_sage.shared.utils.results_formatter import create_unified_formatter
                formatter = create_unified_formatter(result, spectrum_name, args.spectrum_path)
                
                # Show unified display summary (same as GUI)
                print("\n" + "="*80)
                print(formatter.get_display_summary())
                print("="*80)
                
            except ImportError:
                # Fallback to basic summary if formatter not available
                print(f"\n📄 {spectrum_name}: {result.consensus_type} z={result.redshift:.4f} RLAP={result.rlap:.1f}")
                print("-"*80)
            

            
            # Show what was created
            if not args.minimal:
                print(f"\n📁 Results saved to: {args.output_dir}/")
                if args.complete:
                    print(f"   📊 3D Plots: Static PNG files with optimized viewing angle")
                    print(f"   📈 Top 5 templates: Sorted by RLAP (highest quality first)")
            else:
                print(f"📁 Main result file saved to: {args.output_dir}/")
            
            return 0
        else:
            print(f"\n[ERROR] {spectrum_name}: No good matches found")
            return 1
            
    except FileNotFoundError as e:
        print(f"[ERROR] File not found - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] Error during SNID identification: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1 