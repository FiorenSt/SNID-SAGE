"""
Plotting functions for SNID.
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Optional, Union, Dict, List, Any, Tuple
from scipy.interpolate import interp1d
from .preprocessing import log_rebin
from .snidtype import compute_type_fractions, compute_subtype_fractions
from collections import defaultdict

# Import centralized plotting utilities for theme support
try:
    from snid_sage.shared.utils.plotting import (
        setup_plot_theme, 
        create_themed_figure, 
        apply_theme_to_plot,
        create_themed_bbox
    )
    THEME_SUPPORT = True
except ImportError:
    THEME_SUPPORT = False

# Import no-title plot manager for GUI styling (optional)
try:
    from snid_sage.interfaces.gui.utils.no_title_plot_manager import apply_no_title_styling, get_plot_manager
    UNIFIED_SYSTEMS_AVAILABLE = True
except ImportError:
    UNIFIED_SYSTEMS_AVAILABLE = False

# Import centralized font size configuration
try:
    from snid_sage.shared.utils.plotting.font_sizes import (
        PLOT_TITLE_FONTSIZE,
        PLOT_AXIS_LABEL_FONTSIZE,
        PLOT_TICK_FONTSIZE,
        PLOT_LEGEND_FONTSIZE,
        PLOT_ANNOTATION_FONTSIZE,
        PLOT_INFO_TEXT_FONTSIZE,
        PLOT_TABLE_FONTSIZE,
        PLOT_PIE_AUTOPCT_FONTSIZE,
        PLOT_BAR_VALUE_FONTSIZE,
        PLOT_ERROR_FONTSIZE,
        PLOT_STATUS_FONTSIZE,
        apply_font_config
    )
    # Apply standardized font configuration globally
    apply_font_config()
except ImportError:
    # Fallback font sizes if centralized config is not available
    PLOT_TITLE_FONTSIZE: int = 14
    PLOT_AXIS_LABEL_FONTSIZE: int = 12
    PLOT_TICK_FONTSIZE: int = 10
    PLOT_LEGEND_FONTSIZE: int = 11
    PLOT_ANNOTATION_FONTSIZE: int = 10
    PLOT_INFO_TEXT_FONTSIZE: int = 9
    PLOT_TABLE_FONTSIZE: int = 9
    PLOT_PIE_AUTOPCT_FONTSIZE: int = 10
    PLOT_BAR_VALUE_FONTSIZE: int = 8
    PLOT_ERROR_FONTSIZE: int = 14
    PLOT_STATUS_FONTSIZE: int = 12

# ---------------------------------------------------------------------------
# Color Palette Functions
# ---------------------------------------------------------------------------

def get_custom_color_palette():
    """
    Get the custom color palette for subtype plots, ordered by preference.
    Deep blue → purple → magenta → coral → amber, followed by remaining palette colours.
    """
    # Preferred primary colours (reverse of original core order)
    primary_palette = [
        "#FF6361",  # coral
        "#BC5090",  # magenta
        "#58508D",  # purple
        "#003F5C",  # deep blue
        "#FFA600",  # amber
    ]

    # Remaining core and extended colours
    secondary_palette = [
        "#B0B0B0",  # neutral grey
        "#912F40",  # cranberry
        "#5A6650",  # Muted Moss (olive-drab green)
        "#8C6D5C",  # Clay Taupe (warm neutral taupe)
        "#48788D",  # Dusty Blue (soft blue-grey)
        "#9B5E4A",  # Muted Sienna (burnt orange-brown)
        "#6E4E6F",  # Smoky Plum (grey-purple)
    ]

    return primary_palette + secondary_palette


def _apply_theme_if_available(fig, ax, theme_manager=None):
    """Apply theme to matplotlib figure and axes if available"""
    if THEME_SUPPORT and theme_manager:
        try:
            apply_theme_to_plot(fig, ax, theme_manager)
        except Exception:
            pass
    elif theme_manager:
        # Fallback theme application using theme_manager directly
        try:
            theme_manager.update_matplotlib_plot(fig, ax)
        except Exception:
            pass

def _apply_no_title_styling_if_available(fig, ax, xlabel="Wavelength (Å)", ylabel="Flux", theme_manager=None):
    """Apply no-title styling for GUI plots if unified systems are available"""
    if UNIFIED_SYSTEMS_AVAILABLE:
        try:
            apply_no_title_styling(fig, ax, xlabel, ylabel, theme_manager)
            return True
        except Exception:
            pass
    return False


def _apply_faint_grid(ax, theme_manager=None):
    """Apply a faint, publication-friendly grid to the given axes.

    Matches GUI styling (very light dashed grid) and is theme-aware if a
    theme_manager is provided.
    """
    grid_color = '#cccccc'
    try:
        if theme_manager and hasattr(theme_manager, 'get_current_colors'):
            colors = theme_manager.get_current_colors()
            grid_color = colors.get('plot_grid', grid_color)
    except Exception:
        pass

    # Make grid clearly visible in saved PNGs while keeping it subtle
    ax.grid(True, which='major', color=grid_color, alpha=0.50, linestyle='-', linewidth=0.8)
    ax.set_axisbelow(True)


def _create_themed_bbox_if_available(theme_manager=None, annotation_type='info', **kwargs):
    """
    Create a theme-aware bounding box for annotations
    
    Args:
        theme_manager: Theme manager instance
        annotation_type: Type of annotation ('info', 'warning', 'error', 'success')
        **kwargs: Additional bbox properties
    
    Returns:
        dict: Bbox properties
    """
    if theme_manager:
        try:
            colors = theme_manager.get_current_colors()
            
            # Determine colors based on annotation type
            if annotation_type == 'error':
                facecolor = colors.get('danger', '#ef4444')
                edgecolor = colors.get('border', '#cbd5e1')
            elif annotation_type == 'warning':
                facecolor = colors.get('warning', '#f59e0b')
                edgecolor = colors.get('border', '#cbd5e1')
            elif annotation_type == 'success':
                facecolor = colors.get('success', '#10b981')
                edgecolor = colors.get('border', '#cbd5e1')
            else:  # 'info' or default
                facecolor = colors.get('bg_secondary', '#f8fafc')
                edgecolor = colors.get('border', '#cbd5e1')
            
            bbox_props = dict(
                boxstyle='round,pad=0.3',
                facecolor=facecolor,
                edgecolor=edgecolor,
                alpha=kwargs.get('alpha', 0.8),
                linewidth=0.5
            )
            
            # Override with any custom kwargs
            bbox_props.update(kwargs)
            return bbox_props
            
        except Exception:
            pass
    
    # Fallback to simple white bbox
    return dict(boxstyle='round', facecolor='white', alpha=0.7)


def _get_themed_annotation_color(annotation_type='info', theme_manager=None):
    """Get theme-aware annotation colors for different types"""
    if THEME_SUPPORT and theme_manager:
        try:
            colors = theme_manager.get_current_colors()
            is_dark = theme_manager.is_dark_mode()
            
            if annotation_type == 'warning':
                return colors.get('warning', '#f59e0b') if not is_dark else '#fbbf24'
            elif annotation_type == 'info':
                return colors.get('accent_primary', '#3b82f6') if not is_dark else '#60a5fa'
            elif annotation_type == 'success':
                return colors.get('success', '#10b981') if not is_dark else '#34d399'
            else:
                return colors.get('bg_secondary', '#f8fafc')
        except:
            pass
    
    # Fallback colors
    fallback_colors = {
        'warning': '#fbbf24',
        'info': '#60a5fa', 
        'success': '#34d399'
    }
    return fallback_colors.get(annotation_type, '#f8fafc')


def plot_comparison(result: Any, figsize: Tuple[int, int] = (12, 9),
                    save_path: Optional[str] = None,
                    fig: Optional[plt.Figure] = None,
                    theme_manager=None) -> plt.Figure:
    """
    Plot comparison of input spectrum with best-matching template.
    
    Creates a figure with multiple panels:
    - Top left: Original spectra (input and best template) with dual wavelength axis (observed and rest)
    - Bottom left: Processed spectra (flattened input and template)
    - Top right: Cross-correlation function
    - Bottom right: Result summary text with comprehensive statistics
    
    Parameters:
        result: SNIDResult object
        figsize: Figure size (width, height)
        save_path: Path to save the figure (None for no saving)
        fig: Optional matplotlib Figure to draw on. If None, a new figure is created.
        theme_manager: Theme manager object for theme support
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    # Create or clear figure
    if fig is None:
        if THEME_SUPPORT:
            fig, _ = create_themed_figure(figsize=figsize, theme_manager=theme_manager)
        else:
            fig = plt.figure(figsize=figsize)
    else:
        fig.clear()
    
    # Apply theme after figure creation/clearing
    if THEME_SUPPORT and theme_manager:
        setup_plot_theme(theme_manager)
    
    # Check if we have a successful result with matches
    if not hasattr(result, 'success') or not result.success:
        # Create a single subplot for the message
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No valid matches found for comparison", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE,
               transform=ax.transAxes)
        ax.axis('off')
        
        # Apply theme to this axis too
        _apply_theme_if_available(fig, ax, theme_manager)
        
        fig.tight_layout()
        return fig
    
    # Use filtered_matches if available, otherwise fall back to best_matches
    matches_to_use = []
    if hasattr(result, 'filtered_matches') and result.filtered_matches:
        matches_to_use = result.filtered_matches
        match_source = "filtered"
    elif hasattr(result, 'best_matches') and result.best_matches:
        matches_to_use = result.best_matches
        match_source = "best"
    
    if not matches_to_use:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No matches available for plotting", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE,
               transform=ax.transAxes)
        ax.axis('off')
        fig.tight_layout()
        return fig
    
    # Create 2x2 subplot grid
    axs = fig.subplots(2, 2, gridspec_kw={'height_ratios': [1, 1],
                                          'width_ratios': [3, 1]})
    
    # Get best match info (used throughout the plotting)
    best_match = matches_to_use[0]
    original_template_data = best_match['template']
    z_template = best_match['redshift']
    rlap_value = best_match.get('rlap', 0)
    template_name = original_template_data.get('name', 'Unknown')
    template_type = original_template_data.get('type', 'Unknown')
    template_subtype = original_template_data.get('subtype', '')
    template_age = original_template_data.get('age', 0)
    
    # Check if we should show flattened or unflattened spectra
    show_flattened = getattr(result, 'show_flattened', True)
    
    # Top panel - Original/Unflattened spectra
    ax_top = axs[0, 0]
    
    # Plot input spectrum - use the preprocessed version that's been unflattened
    if hasattr(result, 'processed_spectrum') and 'log_flux' in result.processed_spectrum:
        # Use the preprocessed spectrum that has been properly processed and unflattened
        ax_top.plot(result.processed_spectrum['log_wave'], 
                   result.processed_spectrum['log_flux'],
                   'k-', linewidth=1.5, label='Input Spectrum (processed)')
    elif hasattr(result, 'input_spectrum') and result.input_spectrum:
        # Fallback to original input spectrum if processed version not available
        if isinstance(result.input_spectrum, dict) and 'wave' in result.input_spectrum and 'flux' in result.input_spectrum:
            ax_top.plot(result.input_spectrum['wave'], result.input_spectrum['flux'],
                      'k-', linewidth=1.5, label='Input Spectrum (original)')
    
    # Plot template using the spectral data from the match
    try:
        if 'spectra' in best_match and 'flux' in best_match['spectra']:
            template_wave = best_match['spectra']['flux']['wave']
            template_flux = best_match['spectra']['flux']['flux']
            
            ax_top.plot(
                template_wave,
                template_flux,
                'r-',
                linewidth=1.5,
                label=f'Template (z={z_template:.6f})'
            )
            
            # Create a secondary x-axis for rest wavelength
            ax_top_twin = ax_top.twiny()
            ax_top_twin.set_xlim([x/(1+z_template) for x in ax_top.get_xlim()])
            ax_top_twin.set_xlabel('Rest Wavelength (Å)', labelpad=6)
            # Hide top tick labels for a cleaner edge-only look if desired
            try:
                ax_top_twin.tick_params(axis='x', labeltop=True)
            except Exception:
                pass
        else:
            # Fallback method if spectral data not available
            if ('wave' in original_template_data and 'flux' in original_template_data and 
                hasattr(result, 'input_spectrum') and 
                isinstance(result.input_spectrum, dict)):
                
                redshifted_wave = original_template_data['wave'] * (1 + z_template)
                input_wave = result.input_spectrum['wave']
                input_flux = result.input_spectrum['flux']
                
                # Simple scaling and plotting
                valid_indices = (redshifted_wave >= input_wave.min() * 0.8) & \
                                (redshifted_wave <= input_wave.max() * 1.2)
                
                if np.any(valid_indices):
                    ax_top.plot(redshifted_wave[valid_indices], 
                               original_template_data['flux'][valid_indices], 
                               'r-', linewidth=1.5,
                               label=f'Template (z={z_template:.6f}, fallback)')
                    
                    ax_top_twin = ax_top.twiny()
                    ax_top_twin.set_xlim([x/(1+z_template) for x in ax_top.get_xlim()])
                    ax_top_twin.set_xlabel('Rest Wavelength (Å)', labelpad=6)
                    try:
                        ax_top_twin.tick_params(axis='x', labeltop=True)
                    except Exception:
                        pass
                    
    except Exception as e:
        print(f"Warning: Template plotting failed: {e}")
    
    ax_top.set_xlabel('Obs. Wavel.')
    ax_top.set_ylabel('Flux')
    ax_top.set_title('Original Spectra')
    ax_top.legend(loc='upper right')
    ax_top.grid(True, alpha=0.3)
    # Show right spine edge-only (no ticks/labels)
    try:
        ax_top.spines['right'].set_visible(True)
        ax_top.tick_params(axis='y', right=False, labelright=False)
    except Exception:
        pass
    
    # Bottom panel - Flattened spectra
    ax_bottom = axs[1, 0]
    
    if hasattr(result, 'processed_spectrum') and 'flat_flux' in result.processed_spectrum:
        ax_bottom.plot(result.processed_spectrum['log_wave'], 
                      result.processed_spectrum['flat_flux'],
                      'k-', linewidth=1.5, label='Input (flattened)')
    
    # Use the flattened template data from the match
    if 'spectra' in best_match and 'flat' in best_match['spectra']:
        template_wave = best_match['spectra']['flat']['wave']
        template_flux = best_match['spectra']['flat']['flux']
        
        ax_bottom.plot(
            template_wave, 
            template_flux,
            'r-', linewidth=1.5, label='Template (flattened)'
        )
    
    ax_bottom.set_xlabel('Log Wavelength (Å)')
    ax_bottom.set_ylabel('Flattened Flux')
    ax_bottom.set_title('Flattened Spectra')
    ax_bottom.legend()
    ax_bottom.grid(True, alpha=0.3)
    # Right spine edge-only for consistency
    try:
        ax_bottom.spines['right'].set_visible(True)
        ax_bottom.tick_params(axis='y', right=False, labelright=False)
    except Exception:
        pass
    
    # Cross-correlation function (top right) - Show both before and after trimming
    ax_corr = axs[0, 1]
    
    # Try to use correlation data from the best match (same as standalone plot)
    if matches_to_use and 'correlation' in matches_to_use[0]:
        corr_data = matches_to_use[0]['correlation']
        
        # Plot full correlation (before trimming) if available
        if 'z_axis_full' in corr_data and 'correlation_full' in corr_data:
            ax_corr.plot(corr_data['z_axis_full'], corr_data['correlation_full'], 
                        'b-', linewidth=1.0, alpha=0.7, label='Full correlation')
        
        # Plot trimmed correlation (after trimming) if available
        if 'z_axis_peak' in corr_data and 'correlation_peak' in corr_data:
            ax_corr.plot(corr_data['z_axis_peak'], corr_data['correlation_peak'], 
                        'k-', linewidth=1.5, label='Trimmed correlation')
        
        # Mark the best redshift
        ax_corr.axvline(x=z_template, color='r', linestyle=':', linewidth=1.5, 
                       label=f'z = {z_template:.6f}', alpha=0.8)
        
        # Set axis limits based on available data
        if 'z_axis_full' in corr_data:
            z_min, z_max = np.min(corr_data['z_axis_full']), np.max(corr_data['z_axis_full'])
            z_range = z_max - z_min
            ax_corr.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
        
        # Format the correlation plot
        ax_corr.set_xlabel('Redshift')
        ax_corr.set_ylabel('Correlation')
        ax_corr.set_title('Cross-correlation')
        ax_corr.grid(True, alpha=0.3)
        ax_corr.legend(fontsize=PLOT_LEGEND_FONTSIZE)
        try:
            ax_corr.spines['right'].set_visible(True)
            ax_corr.tick_params(axis='y', right=False, labelright=False)
        except Exception:
            pass
        
    else:
        # Fallback message if no correlation data available
        ax_corr.text(0.5, 0.5, "No correlation data available", 
               ha='center', va='center', fontsize=PLOT_STATUS_FONTSIZE,
               transform=ax_corr.transAxes)
        ax_corr.set_title('Cross-correlation')
        ax_corr.axis('off')
    
    # Result summary (bottom right)
    ax_info = axs[1, 1]
    ax_info.axis('off')
    
    # Enhanced result information using comprehensive statistics
    info_text = f"SNID-SAGE Result Summary\n"
    info_text += f"Match source: {match_source} matches\n\n"
    
    # Basic results
    info_text += f"Redshift: {result.redshift:.4f}"
    if hasattr(result, 'redshift_error'):
        info_text += f" ± {result.redshift_error:.4f}"
    info_text += "\n"
    
    if hasattr(result, 'consensus_redshift'):
        info_text += f"Consensus z: {result.consensus_redshift:.4f}"
        if hasattr(result, 'consensus_redshift_error'):
            info_text += f" ± {result.consensus_redshift_error:.4f}"
        info_text += "\n"
    
    # Use best available metric (RLAP-CCC if available, otherwise RLAP)
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    if hasattr(result, 'best_matches') and result.best_matches:
        best_metric_value = get_best_metric_value(result.best_matches[0])
        metric_name = get_best_metric_name(result.best_matches[0])
        info_text += f"{metric_name}: {best_metric_value:.2f}\n"
    else:
        info_text += f"RLAP: {result.rlap:.2f}\n"
    info_text += f"LAP: {result.lap:.2f}\n\n"
    
    # Template info
    info_text += f"Template: {template_name}\n"
    info_text += f"Type: {template_type}"
    if template_subtype:
        info_text += f" {template_subtype}"
    info_text += "\n"
    
    if template_age is not None and np.isfinite(template_age):
        info_text += f"Age: {template_age:.1f} days\n"
    
    
    # Show confidence from clustering assessment when available
    try:
        ca = None
        if hasattr(result, 'clustering_results') and result.clustering_results:
            if isinstance(result.clustering_results, dict):
                bestc = result.clustering_results.get('best_cluster')
                if isinstance(bestc, dict):
                    ca = bestc.get('confidence_assessment')
        if isinstance(ca, dict):
            level = ca.get('confidence_level', 'N/A')
            pct = ca.get('confidence_pct', None)
            if isinstance(pct, (int, float)) and np.isfinite(float(pct)):
                info_text += f"Confidence: {level} (+{float(pct):.1f}%)\n"
            else:
                info_text += f"Confidence: {level}\n"
    except Exception:
        pass
    
    # Match statistics
    if hasattr(result, 'match_statistics'):
        stats = result.match_statistics
        if 'total_matches' in stats:
            info_text += f"\nTotal matches: {stats['total_matches']}\n"
        if 'filtered_matches' in stats:
            info_text += f"Filtered: {stats['filtered_matches']}\n"
        if 'good_matches' in stats:
            info_text += f"Good: {stats['good_matches']}\n"
    
    # Type fractions (top 3)
    if hasattr(result, 'type_fractions') and result.type_fractions:
        info_text += "\nType fractions:\n"
        sorted_fractions = sorted(result.type_fractions.items(), 
                                key=lambda x: x[1], reverse=True)[:3]
        for t, f in sorted_fractions:
            info_text += f"  {t}: {f:.2f}\n"
    
    ax_info.text(0.05, 0.95, info_text, va='top', fontsize=PLOT_INFO_TEXT_FONTSIZE,
                transform=ax_info.transAxes)
    
    # Add template metadata annotation to top panel
    template_info = f"Template: {template_name}\n"
    if template_type != 'Unknown':
        template_info += f"Type: {template_type}"
        if template_subtype:
            template_info += f" {template_subtype}"
        template_info += "\n"
    
    template_info += f"Age: {template_age:.1f} days\n"
    template_info += f"z = {z_template:.6f}\n"
    # Use best available metric (RLAP-CCC if available, otherwise RLAP)
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    best_metric_value = get_best_metric_value(best_match)
    metric_name = get_best_metric_name(best_match)
    template_info += f"{metric_name} = {best_metric_value:.1f}"
    
    ax_top.text(0.02, 0.98, template_info, transform=ax_top.transAxes,
             verticalalignment='top', horizontalalignment='left',
             bbox=_create_themed_bbox_if_available(theme_manager=theme_manager))
    
    fig.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

 

def plot_type_fractions(result: Any, figsize: Tuple[int, int] = (10, 8),
                       save_path: Optional[str] = None,
                       fig: Optional[plt.Figure] = None,
                       theme_manager=None) -> plt.Figure:
    """
    Plot the type fractions for different RLAP thresholds.
    
    This demonstrates how the classification changes as the matching quality threshold
    is varied. Uses the comprehensive statistics from snid_sage.snid.py including GMM filtering
    and type slopes analysis.
    
    Parameters:
        result: SNIDResult object
        figsize: Size of the figure
        save_path: Path to save the figure
        fig: Existing figure to plot on
        
    Returns:
        matplotlib.figure.Figure: The figure
    """
    # Create figure if not provided
    if fig is None:
        fig = plt.figure(figsize=figsize, constrained_layout=True)
    
    # Deprecated: retain a minimal placeholder to avoid import breakages in older code paths
    # Create a simple message figure and return
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, "Deprecated: use cluster-aware subtype plots instead", ha='center', va='center')
    ax.axis('off')
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    return fig

    # Create a grid for multiple plots
    gs = fig.add_gridspec(2, 2)
    
    # Pie chart for main type fractions
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, :])  # Bottom row - fraction vs RLAP
    
    # Use filtered_matches if available, otherwise use best_matches
    matches_to_use = []
    match_source = "unknown"
    
    if hasattr(result, 'filtered_matches') and result.filtered_matches:
        matches_to_use = result.filtered_matches
        match_source = "GMM-filtered"
    elif hasattr(result, 'best_matches') and result.best_matches:
        matches_to_use = result.best_matches
        match_source = "best"
    
    # Check if we have results to plot
    if not matches_to_use:
        for ax in [ax1, ax2, ax3]:
            ax.text(0.5, 0.5, "No results available", ha='center', va='center')
            ax.axis('off')
        return fig
    
    # Use the comprehensive type fractions from result if available
    type_fractions_to_plot = {}
    if hasattr(result, 'type_fractions') and result.type_fractions:
        type_fractions_to_plot = result.type_fractions
    else:
        # Calculate from matches if not available
        type_fractions_to_plot = compute_type_fractions(matches_to_use, weighted=False)
    
    # Plot 1: Pie chart of type fractions
    if type_fractions_to_plot:
        sorted_fractions = sorted(type_fractions_to_plot.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_fractions]
        values = [item[1] for item in sorted_fractions]
        
        # Get colors
        try:
            colors = [plt.cm.tab10(i % 10) for i in range(len(labels))]
        except (TypeError, KeyError):
            try:
                import matplotlib.colormaps as cmaps
                colors = [cmaps['tab10'](i % 10) for i in range(len(labels))]
            except ImportError:
                from matplotlib import cm
                colors = [cm.tab10(i % 10) for i in range(len(labels))]
                
        wedges, texts, autotexts = ax1.pie(
            values, 
            labels=None,
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'fontsize': PLOT_PIE_AUTOPCT_FONTSIZE})
        
        ax1.axis('equal')
        ax1.set_title(f'Type Fractions ({match_source} matches)')
        ax1.legend(wedges, labels, title="Types", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    else:
        ax1.text(0.5, 0.5, "No type fraction data available", ha='center', va='center')
        ax1.axis('off')

    # Plot 2: Type slopes (if available)
    if hasattr(result, 'type_slopes') and result.type_slopes:
        type_slopes = result.type_slopes
        sorted_slopes = sorted(type_slopes.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_slopes:
            slope_labels = [item[0] for item in sorted_slopes]
            slope_values = [item[1] for item in sorted_slopes]
            
            # Create bar chart for slopes
            bars = ax2.bar(range(len(slope_labels)), slope_values, 
                          color=[plt.cm.tab10(i % 10) for i in range(len(slope_labels))])
            
            ax2.set_xlabel('Type')
            ax2.set_ylabel('Slope')
            ax2.set_title('Type Slopes (Fraction vs RLAP)')
            ax2.set_xticks(range(len(slope_labels)))
            ax2.set_xticklabels(slope_labels, rotation=45)
            ax2.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for i, (bar, value) in enumerate(zip(bars, slope_values)):
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                        f'{value:.3f}', ha='center', va='bottom', fontsize=PLOT_BAR_VALUE_FONTSIZE)
        else:
            ax2.text(0.5, 0.5, "No slope data available", ha='center', va='center')
            ax2.axis('off')
    else:
        # Fallback: Show subtype fractions for best type
        subtype_fractions_to_plot = {}
        if hasattr(result, 'subtype_fractions') and result.subtype_fractions:
            subtype_fractions_to_plot = result.subtype_fractions
        else:
            subtype_fractions_to_plot = compute_subtype_fractions(matches_to_use, weighted=False)
        
        if subtype_fractions_to_plot and type_fractions_to_plot:
            best_type = max(type_fractions_to_plot.items(), key=lambda x: x[1])[0]
            
            if best_type in subtype_fractions_to_plot:
                subtypes = subtype_fractions_to_plot[best_type]
                if subtypes:
                    sorted_subtypes = sorted(subtypes.items(), key=lambda x: x[1], reverse=True)
                    sub_labels = [item[0] for item in sorted_subtypes]
                    sub_values = [item[1] for item in sorted_subtypes]
                    
                    # Use custom color palette
                    custom_palette = get_custom_color_palette()
                    sub_colors = [custom_palette[i % len(custom_palette)] for i in range(len(sub_labels))]
                    
                    # Create explode parameter - explode the winning subtype based on result.best_subtype
                    winning_subtype = None
                    if hasattr(result, 'best_subtype') and result.best_subtype:
                        winning_subtype = result.best_subtype
                        
                    sub_explode = []
                    for i, label in enumerate(sub_labels):
                        if winning_subtype and label == winning_subtype:
                            sub_explode.append(0.1)  # Explode the winning subtype
                        else:
                            sub_explode.append(0)    # Keep other subtypes normal
                    
                    wedges, texts, autotexts = ax2.pie(
                        sub_values, 
                        labels=None,
                        autopct='%1.1f%%',
                        colors=sub_colors,
                        explode=sub_explode,
                        startangle=90,
                        textprops={'fontsize': PLOT_PIE_AUTOPCT_FONTSIZE})
                    
                    # Add dark edge around the winning slice
                    for i, (wedge, label) in enumerate(zip(wedges, sub_labels)):
                        if winning_subtype and label == winning_subtype:
                            wedge.set_edgecolor('black')
                            wedge.set_linewidth(2)
                        else:
                            wedge.set_edgecolor('white')
                            wedge.set_linewidth(1)
                    
                    ax2.axis('equal')
                    ax2.set_title(f'{best_type} Subtypes')
                    ax2.legend(wedges, sub_labels, title="Subtypes", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                else:
                    ax2.text(0.5, 0.5, f"No subtypes found for {best_type}", ha='center', va='center')
                    ax2.axis('off')
            else:
                ax2.text(0.5, 0.5, f"No subtype data for best type", ha='center', va='center')
                ax2.axis('off')
        else:
            ax2.text(0.5, 0.5, "No subtype data available", ha='center', va='center')
            ax2.axis('off')
    
    # Plot 3: Type fractions vs RLAP threshold (using GMM-filtered matches)
    # Use the filtered matches (winning cluster) for this analysis to match Fortran behavior
    rlap_analysis_matches = []
    if hasattr(result, 'filtered_matches') and result.filtered_matches:
        rlap_analysis_matches = result.filtered_matches
        analysis_source = "GMM-filtered (winning cluster)"
    elif hasattr(result, 'best_matches') and result.best_matches:
        rlap_analysis_matches = result.best_matches
        analysis_source = "all matches (no GMM filtering)"
    
    if not rlap_analysis_matches:
        ax3.text(0.5, 0.5, "No matches for RLAP analysis", ha='center', va='center')
        ax3.axis('off')
    else:
        # Filter out invalid matches
        valid_matches = []
        for match in rlap_analysis_matches:
            if not isinstance(match, dict) or 'template' not in match:
                continue
                
            template = match.get('template', {})
            if not isinstance(template, dict):
                continue
                
            if 'type' in template and 'rlap' in match:
                valid_matches.append(match)
        
        if valid_matches:
            # Find max RLAP value
            max_rlap = max([m.get('rlap', 0) for m in valid_matches])
            min_rlap_threshold = getattr(result, 'min_rlap', 5.0)
            
            # Create RLAP thresholds
            rlap_thresholds = np.linspace(min_rlap_threshold, min(max_rlap, 50), 15)
            
            # Get all possible types
            all_types = set()
            for match in valid_matches:
                template = match.get('template', {})
                sn_type = template.get('type', 'Unknown')
                if sn_type:
                    all_types.add(sn_type)
            
            type_fractions_by_rlap = {t: [] for t in all_types}
            
            # Calculate fractions at each threshold
            for threshold in rlap_thresholds:
                qualified_matches = [match for match in valid_matches 
                                  if match.get('rlap', 0) >= threshold]
                
                if qualified_matches:
                    fractions = compute_type_fractions(qualified_matches, weighted=False)
                    
                    for t in type_fractions_by_rlap:
                        type_fractions_by_rlap[t].append(fractions.get(t, 0))
                else:
                    for t in type_fractions_by_rlap:
                        type_fractions_by_rlap[t].append(0)
            
            # Plot for each type
            for i, t in enumerate(sorted(type_fractions_by_rlap.keys())):
                if all(f == 0 for f in type_fractions_by_rlap[t]):
                    continue
                    
                try:
                    color = plt.cm.tab10(i % 10)
                except (TypeError, KeyError):
                    try:
                        import matplotlib.colormaps as cmaps
                        color = cmaps['tab10'](i % 10)
                    except ImportError:
                        from matplotlib import cm
                        color = cm.tab10(i % 10)
                        
                ax3.plot(rlap_thresholds, type_fractions_by_rlap[t], 
                        marker='o', markersize=5, linestyle='-', linewidth=2, 
                        color=color, label=t)
            
            # Mark the min_rlap threshold
            ax3.axvline(min_rlap_threshold, color='red', linestyle='--', 
                      label=f'Min RLAP = {min_rlap_threshold:.1f}')
            
            # Add information about the analysis source
            info_text = f"Analysis source: {analysis_source}\n"
            info_text += f"Matches analyzed: {len(valid_matches)}"
            
            # Add comparison info if we have both filtered and original matches
            if (hasattr(result, 'filtered_matches') and result.filtered_matches and
                hasattr(result, 'best_matches') and result.best_matches and
                len(result.best_matches) != len(result.filtered_matches)):
                total_matches = len(result.best_matches)
                filtered_matches = len(result.filtered_matches)
                reduction_pct = 100 * (total_matches - filtered_matches) / total_matches
                info_text += f" (reduced from {total_matches}, {reduction_pct:.1f}% reduction)"
            
            ax3.text(0.02, 0.98, info_text,
                    transform=ax3.transAxes, va='top', ha='left',
                    bbox=_create_themed_bbox_if_available(theme_manager=theme_manager))
            
            ax3.set_xlabel('RLAP Threshold')
            ax3.set_ylabel('Type Fraction')
            ax3.set_title(f'Type Fractions vs. RLAP Threshold ({analysis_source})')
            ax3.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, "No valid matches for RLAP analysis", ha='center', va='center')
            ax3.axis('off')
    
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=100, bbox_inches='tight')
    
    return fig

def plot_correlation_function(result: Any, figsize: Tuple[int, int] = (8, 6),
                            save_path: Optional[str] = None,
                            fig: Optional[plt.Figure] = None,
                            theme_manager=None) -> plt.Figure:
    """
    Plot the correlation function for the best match.
    
    Shows both the original and trimmed correlation functions, 
    similar to the plotxcor function in Fortran SNID.
    
    Parameters:
        result: SNIDResult object
        figsize: Figure size (width, height)
        save_path: Path to save the figure (None for no saving)
        fig: Optional matplotlib Figure to draw on. If None, a new figure is created.
        theme_manager: Theme manager object for theme support
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    # NOTE: This function now prioritizes correlation data from the match object
    # and falls back to result.correlation only if match data is unavailable
    
    # Use provided figure or create a new one
    if fig is None:
        fig = plt.figure(figsize=figsize)
    else:
        fig.clear()  # Clear the existing figure
        
    # Create single full-size plot
    ax = fig.add_subplot(111)
    
    # Check if we have a successful result with matches
    if not hasattr(result, 'success') or not result.success or not hasattr(result, 'best_matches') or not result.best_matches:
        ax.text(0.5, 0.5, "No valid matches found for correlation plot", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE,
               transform=ax.transAxes)
        ax.axis('off')
        fig.tight_layout()
        return fig
    
    # Get best match info
    best_match = result.best_matches[0]
    raw_template_name = best_match['template'].get('name', 'Unknown')
    # Clean template name to remove _epoch_X suffix
    from snid_sage.shared.utils import clean_template_name
    template_name = clean_template_name(raw_template_name)
    template_type = best_match['template'].get('type', 'Unknown')
    template_subtype = best_match['template'].get('subtype', '')
    template_age = best_match['template'].get('age', 0)
    redshift = best_match['redshift']
    rlap = best_match['rlap']
    
    # Try to show both full and trimmed correlations from best match
    if 'correlation' in best_match:
        corr_data = best_match['correlation']
        
        # Plot full correlation (before trimming) if available
        if 'z_axis_full' in corr_data and 'correlation_full' in corr_data:
            ax.plot(corr_data['z_axis_full'], corr_data['correlation_full'], 
                   'b-', linewidth=1.0, alpha=0.7, label='Full correlation')
        
        # Plot trimmed correlation (after trimming) if available
        if 'z_axis_peak' in corr_data and 'correlation_peak' in corr_data:
            ax.plot(corr_data['z_axis_peak'], corr_data['correlation_peak'], 
                   'k-', linewidth=1.5, label='Trimmed correlation')
        
        # Mark the best redshift
        ax.axvline(x=redshift, color='r', linestyle=':', linewidth=1.5, 
                  label=f'z = {redshift:.6f}', alpha=0.8)
        
        # Set axis limits based on available data
        if 'z_axis_full' in corr_data:
            z_min, z_max = np.min(corr_data['z_axis_full']), np.max(corr_data['z_axis_full'])
            z_range = z_max - z_min
            ax.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
            
    else:
        # Fallback to other correlation data if available
        has_correlation = hasattr(result, 'correlation') and result.correlation is not None and \
                         hasattr(result, 'redshift_axis') and result.redshift_axis is not None
        has_correlations = hasattr(result, 'correlations') and len(result.correlations) > 0
        
        if has_correlation:
            # Use the stored correlation and redshift axis
            ax.plot(result.redshift_axis, result.correlation, 'k-', label='Correlation', linewidth=1.5)
            
            # Add vertical line at best redshift
            ax.axvline(x=redshift, color='r', linestyle=':', linewidth=1.5, 
                      label=f'z = {redshift:.6f}', alpha=0.8)
            
            # Set x-axis limits to focus on the relevant region
            z_min, z_max = np.min(result.redshift_axis), np.max(result.redshift_axis)
            z_range = z_max - z_min
            ax.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
            
        elif has_correlations:
            # Use the first correlation from the list
            corr_data = result.correlations[0]
            ax.plot(corr_data['z_axis'], corr_data['xcor'], 'k-', label='Correlation', linewidth=1.5)
            
            # Add vertical line at best redshift
            ax.axvline(x=redshift, color='r', linestyle=':', linewidth=1.5, 
                      label=f'z = {redshift:.6f}', alpha=0.8)
            
            # Set x-axis limits to focus on the relevant region
            z_min, z_max = np.min(corr_data['z_axis']), np.max(corr_data['z_axis'])
            z_range = z_max - z_min
            ax.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
        else:
            ax.text(0.5, 0.5, "No correlation data available", 
                   ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE,
                   transform=ax.transAxes)
            ax.axis('off')
            fig.tight_layout()
            return fig
    
    # Add template information annotation
    template_info = f"Template: {template_name}\n"
    if template_type != 'Unknown':
        template_info += f"Type: {template_type}"
        if template_subtype:
            template_info += f" {template_subtype}"
        template_info += "\n"
    
    if template_age is not None and np.isfinite(template_age):
        template_info += f"Age: {template_age:.1f} days\n"
    template_info += f"z = {redshift:.6f}\n"
    # Use best available metric (RLAP-CCC if available, otherwise RLAP)
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    best_metric_value = get_best_metric_value(best_match)
    metric_name = get_best_metric_name(best_match)
    template_info += f"{metric_name} = {best_metric_value:.1f}"
    
    # Add the annotation with a semi-transparent background
    ax.text(0.02, 0.98, template_info, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='left',
            bbox=_create_themed_bbox_if_available(theme_manager=theme_manager))
    
    # Format plot (no title per user requirement)
    # Always use standardized font sizes, regardless of GUI styling
    ax.set_xlabel('Redshift', fontsize=PLOT_AXIS_LABEL_FONTSIZE)  # X-axis: redshift
    ax.set_ylabel('Correlation', fontsize=PLOT_AXIS_LABEL_FONTSIZE)  # Y-axis: correlation
    _apply_faint_grid(ax, theme_manager)
    # Ensure faint grid regardless of styling path
    _apply_faint_grid(ax, theme_manager)
    
    # Apply no-title styling if available, but ensure font sizes are preserved
    if _apply_no_title_styling_if_available(fig, ax, "Redshift", "Correlation", theme_manager):
        # Re-apply standardized font sizes after GUI styling
        ax.set_xlabel('Redshift', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax.set_ylabel('Correlation', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    
    ax.legend(loc='upper right', fontsize=PLOT_LEGEND_FONTSIZE)
    
    # Set y-axis limits to show full correlation range with some padding
    y_data = []
    for line in ax.get_lines():
        if line.get_label() not in ['z = {:.6f}'.format(redshift)]:  # Skip vertical line
            y_data.extend(line.get_ydata())
    
    if y_data:
        y_min, y_max = np.min(y_data), np.max(y_data)
        y_range = y_max - y_min
        ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)
    
    # Adjust layout
    fig.tight_layout()
    
    # Save if requested
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def plot_redshift_age(result: Any, figsize: Tuple[int, int] = (8, 6),
                       save_path: Optional[str] = None,
                       fig: Optional[plt.Figure] = None,
                       theme_manager=None) -> plt.Figure:
    """
    Plot redshift vs. phase (age) with different SN types and subtypes in different colors.
    
    Points are displayed with uniform size, with colors indicating type and subtype.
    Includes uncertainty bars for both redshift and age.
    Only the best match is included in the legend for clarity.
    
    Parameters:
        result: SNIDResult object
        figsize: Figure size (width, height)
        save_path: Path to save the figure (None for no saving)
        fig: Optional matplotlib Figure to draw on
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    if not result.success:
        raise ValueError("Cannot plot redshift-age data for unsuccessful SNID result")
    
    # Use provided figure or create a new one
    if fig is None:
        fig = plt.figure(figsize=figsize)
    else:
        fig.clear()
    
    ax = fig.add_subplot(111)
    
    # Extract all matches - prioritize user-selected cluster, then winning cluster, then best matches
    matches = []
    match_source = ""
    
    # First priority: Check for user-selected cluster
    if (hasattr(result, 'clustering_results') and result.clustering_results and 
        'user_selected_cluster' in result.clustering_results and 
        result.clustering_results['user_selected_cluster']):
        
        user_cluster = result.clustering_results['user_selected_cluster']
        if 'matches' in user_cluster and user_cluster['matches']:
            matches = user_cluster['matches']
            cluster_type = user_cluster.get('type', 'Unknown')
            match_source = f"user-selected cluster ({cluster_type})"
    
    # Second priority: Use filtered_matches if available (winning cluster)
    if not matches and hasattr(result, 'filtered_matches') and result.filtered_matches:
        matches = result.filtered_matches
        match_source = "winning cluster"
    
    # Third priority: Fall back to best_matches
    if not matches and hasattr(result, 'best_matches') and result.best_matches:
        matches = result.best_matches
        match_source = "best matches"
    
    if not matches:
        ax.text(0.5, 0.5, "No match data available", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, 
               transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        fig.tight_layout()
        return fig
    
    # Determine if clustering succeeded; if so, do not re-apply a strict RLAP filter
    clustering_ok = bool(getattr(result, 'clustering_results', None)) and bool(getattr(result, 'clustering_results', {}).get('success', False))
    
    # Use configured RLAP threshold when clustering is not available; otherwise respect clustering survivors
    if not clustering_ok:
        rlapmin = getattr(result, 'min_rlap', getattr(result, 'rlapmin', 5.0))
        matches = [m for m in matches if m.get('rlap', 0) >= rlapmin]
        if not matches:
            ax.text(0.5, 0.5, f"No matches above RLAP threshold ({rlapmin})", 
                   ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, 
                   transform=ax.transAxes)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            fig.tight_layout()
            return fig
    
    # Extract data from all matches (GUI-style)
    data = []
    for i, match in enumerate(matches):
        if not isinstance(match, dict):
            continue
        z = match.get('redshift', None)
        age = match.get('age', None)
        if z is None or age is None:
            continue
        template = match.get('template', {})
        sn_subtype = template.get('subtype', 'Unknown') if isinstance(template, dict) else 'Unknown'
        if not sn_subtype or sn_subtype.strip() == '':
            sn_subtype = 'Unknown'
        # Use RLAP-CCC for point size if available; fallback to RLAP
        rlap_value = float(match.get('rlap', 0))
        rlap_ccc_value = match.get('rlap_ccc', None)
        size_metric = float(rlap_ccc_value) if rlap_ccc_value is not None else rlap_value
        data.append({
            'z': float(z),
            'age': float(age),
            'subtype': sn_subtype,
            'size_metric': size_metric
        })

    if not data:
        ax.text(0.5, 0.5, "No valid redshift-age data available", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, 
               transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        fig.tight_layout()
        return fig
    
    # Group data by subtype and assign colors (GUI-style)
    from collections import defaultdict
    subtype_data: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    for point in data:
        subtype_data[point['subtype']].append(point)

    custom_palette = get_custom_color_palette()
    sorted_subtypes = sorted(subtype_data.keys())
    subtype_color_map = {subtype: custom_palette[i % len(custom_palette)] for i, subtype in enumerate(sorted_subtypes)}

    # Plot each subtype with RLAP-cos-scaled sizes (fallback RLAP) and count in legend (GUI-style)
    for subtype, points in sorted(subtype_data.items()):
        redshifts = [p['z'] for p in points]
        ages = [p['age'] for p in points]
        metrics = [p['size_metric'] for p in points]
        sizes = [max(20.0, m * 3.0) for m in metrics]
        color = subtype_color_map.get(subtype, '#A9A9A9')
        ax.scatter(
            redshifts,
            ages,
            c=color,
            s=sizes,
            alpha=0.7,
            edgecolors='black',
            linewidth=0.5,
            label=f"{subtype} (n={len(points)})"
        )
    
    # Extract all ages and redshifts for calculations
    all_ages = [item['age'] for item in data]
    all_redshifts = [item['z'] for item in data]
    
    # Calculate axis limits based on actual data points (like original Fortran)
    # This prevents consensus lines from affecting the centering
    if all_ages and all_redshifts:
        # Calculate data ranges (no error bars like original Fortran)
        z_min_data = min(all_redshifts)
        z_max_data = max(all_redshifts)
        age_min_data = min(all_ages)
        age_max_data = max(all_ages)
        
        # Calculate ranges
        z_range = z_max_data - z_min_data
        age_range = age_max_data - age_min_data
        
        # Use margins like original Fortran (3% for x, 10%/15% for y)
        if z_range == 0:
            z_margin = 0.01  # Small default margin
        else:
            z_margin = z_range * 0.03  # 3% margin like Fortran
            
        if age_range == 0:
            # Single-point or flat age distribution: apply sensible default margins
            age_margin_bottom = 5.0
            age_margin_top = 5.0
        else:
            age_margin_bottom = age_range * 0.10  # 10% bottom margin like Fortran
            age_margin_top = age_range * 0.15     # 15% top margin like Fortran
        
        # Allow full redshift range (including negative redshifts)
        z_min_plot = z_min_data - z_margin
        z_max_plot = z_max_data + z_margin
        
        # Age can be negative (pre-explosion), use asymmetric margins like Fortran
        age_min_plot = age_min_data - age_margin_bottom
        age_max_plot = age_max_data + age_margin_top
        
        # Set the limits NOW, before adding consensus lines
        ax.set_xlim(z_min_plot, z_max_plot)
        ax.set_ylim(age_min_plot, age_max_plot)
        
    # Match GUI: do not draw consensus/median red reference lines in CLI plot
    
    # Format plot correctly (no title per user requirement)
    # Always use standardized font sizes, regardless of GUI styling
    # Note: Plot is now colored by subtype instead of type (legend will show subtypes)
    ax.set_xlabel('Redshift', fontsize=PLOT_AXIS_LABEL_FONTSIZE)  # X-axis: redshift
    ax.set_ylabel('Age (days)', fontsize=PLOT_AXIS_LABEL_FONTSIZE)  # Y-axis: age
    ax.set_title('Redshift vs Age Distribution (by Subtype)', fontsize=PLOT_TITLE_FONTSIZE)
    _apply_faint_grid(ax, theme_manager)
    
    # Apply no-title styling if available, but ensure font sizes are preserved
    if _apply_no_title_styling_if_available(fig, ax, "Redshift", "Age (days)", theme_manager):
        # Re-apply standardized font sizes after GUI styling
        ax.set_xlabel('Redshift', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax.set_ylabel('Age (days)', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    
    ax.legend(loc='upper right', fontsize=PLOT_LEGEND_FONTSIZE)  # Consistent legend font size
    
    # Consistent tick label font sizes
    ax.tick_params(axis='x', labelsize=PLOT_TICK_FONTSIZE)
    ax.tick_params(axis='y', labelsize=PLOT_TICK_FONTSIZE)
    
    # Axis limits were already set earlier to ensure proper centering on data points
    
    # Adjust layout
    fig.tight_layout()
    
    # Save if requested
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def _filter_nonzero_spectrum(wave, flux, processed_spectrum=None):
    """
    Filter out zero-padded regions from spectrum data.
    
    This function mirrors the GUI's filter_nonzero_spectrum functionality
    to ensure CLI plots have the same zero-padding removal as GUI plots.
    
    Parameters:
        wave: Wavelength array
        flux: Flux array  
        processed_spectrum: Dict containing edge information from preprocessing
        
    Returns:
        tuple: (filtered_wave, filtered_flux) with zero-padded regions removed
    """
    try:
        # If we have processed spectrum with edge information, use it
        if processed_spectrum and 'left_edge' in processed_spectrum and 'right_edge' in processed_spectrum:
            left_edge = processed_spectrum['left_edge']
            right_edge = processed_spectrum['right_edge']
            return wave[left_edge:right_edge+1], flux[left_edge:right_edge+1]
        
        # Fallback: find valid regions manually (including negative values for continuum-subtracted spectra)
        valid_mask = (flux != 0) & np.isfinite(flux)
        if np.any(valid_mask):
            left_edge = np.argmax(valid_mask)
            right_edge = len(flux) - 1 - np.argmax(valid_mask[::-1])
            return wave[left_edge:right_edge+1], flux[left_edge:right_edge+1]
        
        # If no nonzero data found, return original arrays
        return wave, flux
        
    except Exception as e:
        # Silently handle errors and return original arrays
        return wave, flux

def plot_flux_comparison(match: Dict[str, Any], result: Any, 
                       figsize: Tuple[int, int] = (10, 8),
                       save_path: Optional[str] = None,
                       fig: Optional[plt.Figure] = None,
                       theme_manager=None) -> plt.Figure:
    """
    Plot comparison of original input spectrum with unflattened template.
    
    This recreates the 'FLUX' view from Fortran SNID, showing the observed spectrum
    with the unflattened template in the same plot.
    
    Uses the processed spectrum from SNID analysis.
    - log_flux is the reconstructed apodized flux
    - (tapered_flux[left_edge:right_edge+1] + 1.0) * continuum[left_edge:right_edge+1]
    - Data is trimmed and filtered to match the GUI display
    
    Parameters:
        match: Dictionary containing template match information
        result: SNIDResult object with input spectrum information
        figsize: Figure size (width, height)
        save_path: Path to save the figure (None for no saving)
        fig: Optional matplotlib Figure to draw on. If None, a new figure is created.
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    if not hasattr(result, 'input_spectrum') or not result.input_spectrum:
        raise ValueError("Input spectrum data missing")
        
    # Use provided figure or create a new one
    if fig is None:
        fig = plt.figure(figsize=figsize)
    else:
        fig.clear()  # Clear the existing figure
    
    # Create single full-size plot
    ax = fig.add_subplot(111)
    
    # Get template info
    template = match.get('template', {})
    # Clean template name to remove epoch suffix like GUI
    try:
        from snid_sage.shared.utils import clean_template_name
        template_name = clean_template_name(template.get('name', 'Unknown') or match.get('name', 'Unknown'))
    except Exception:
        template_name = template.get('name', 'Unknown')
    template_type = template.get('type', 'Unknown')
    template_subtype = template.get('subtype', '')
    template_age = template.get('age', 0)
    z_template = match.get('redshift', 0)
    # Prefer RLAP-cos like GUI overlay info
    rlap_ccc_value = match.get('rlap_ccc', None)
    rlap_value = match.get('rlap', 0)
    redshift_error = match.get('redshift_error', 0)
    
    # Plot the processed input spectrum (what SNID actually worked with)
    input_wave = None
    input_flux = None
    
    # Use processed spectrum - reconstruct flux the same way as the GUI
    if hasattr(result, 'processed_spectrum') and result.processed_spectrum:
        ps = result.processed_spectrum
        input_wave = ps.get('log_wave')
        # Preferred: display_flux if available (apodized, GUI-style)
        if 'display_flux' in ps:
            input_flux = ps['display_flux']
        # If we have flat + continuum (from result.input_continuum), reconstruct flux
        elif 'flat_flux' in ps and hasattr(result, 'input_continuum') and isinstance(result.input_continuum, dict) and 'flux' in result.input_continuum:
            try:
                input_flux = (np.asarray(ps['flat_flux']) + 1.0) * np.asarray(result.input_continuum['flux'])
            except Exception:
                input_flux = ps.get('log_flux')
        # Legacy fallback: if continuum is bundled inside ps
        elif 'log_flux' in ps and 'continuum' in ps:
            input_flux = (ps['log_flux'] + 1.0) * ps['continuum']
        else:
            # Final fallback: use stored log_flux directly
            input_flux = ps.get('log_flux')
        # Match GUI colors and linewidth
        ax.plot(input_wave, input_flux, color='#3b82f6', linewidth=2, label='Observed Spectrum')
        
    elif isinstance(result.input_spectrum, dict) and 'wave' in result.input_spectrum and 'flux' in result.input_spectrum:
        input_wave = result.input_spectrum['wave']
        input_flux = result.input_spectrum['flux']
        
        # Filter out zero-padded regions (INPUT SPECTRUM ONLY)
        input_wave, input_flux = _filter_nonzero_spectrum(input_wave, input_flux)
        
        ax.plot(input_wave, input_flux, color='#3b82f6', linewidth=2, label='Observed Spectrum')
        
    else:
        raise ValueError("No input spectrum data available for plotting")
    
    # Try to plot the unflattened template
    template_plotted = False
    try:
        # First try: Use pre-computed template flux data from the match
        if 'spectra' in match and 'flux' in match['spectra']:
            template_wave = match['spectra']['flux']['wave']
            template_flux = match['spectra']['flux']['flux']
            
            # DON'T filter templates - they are already properly trimmed by SNID analysis
            # snid_sage.snid.py
            # Filtering them again with input spectrum edges cuts them incorrectly
            
            # No redshift transformation needed - wavelengths are already on same grid as input
            ax.plot(
                template_wave,
                template_flux,
                color='#E74C3C',
                linewidth=2,
                label='Template',
                alpha=0.8,
            )
            template_plotted = True
        
        # Second try: Reconstruct from processed flux and continuum
        elif ('processed_flux' in match and 
              hasattr(result, 'processed_spectrum') and 
              'continuum' in result.processed_spectrum):
            
            template_flat_flux = match['processed_flux']
            continuum = result.processed_spectrum['continuum']
            wave = result.processed_spectrum['log_wave']
            
            # Ensure arrays have same length
            if len(template_flat_flux) == len(continuum) == len(wave):
                # Reconstruct template flux: (flattened + 1.0) * continuum
                template_flux_reconstructed = (template_flat_flux + 1.0) * continuum
                
                # DON'T filter template - it's already properly processed by SNID
                
                # Use the same wavelength grid as input (no redshift transformation)
                ax.plot(
                    wave,
                    template_flux_reconstructed,
                    color='#E74C3C',
                    linewidth=2,
                    label='Template',
                    alpha=0.8,
                )
                template_plotted = True
        
        # Third try: Use original template data with scaling
        elif 'wave' in template and 'flux' in template and input_wave is not None:
            # Redshift template wavelengths to observed frame
            redshifted_wave = template['wave'] * (1 + z_template)
            template_flux = template['flux'].copy()
            
            # Find overlap region
            valid_indices = ((redshifted_wave >= input_wave.min()) & 
                           (redshifted_wave <= input_wave.max()))
            
            if np.any(valid_indices):
                plot_wave = redshifted_wave[valid_indices]
                plot_flux = template_flux[valid_indices]
                
                # DON'T filter template - only input spectrum should be filtered
                
                # Plot without any amplitude rescaling to match GUI behavior
                if len(plot_flux) > 0:
                    ax.plot(
                        plot_wave,
                        plot_flux,
                        color='#E74C3C',
                        linewidth=2,
                        label='Template',
                        alpha=0.8,
                    )
                    template_plotted = True
                           
    except Exception as e:
        # Re-raise the exception to see what's actually going wrong
        raise RuntimeError(f"Error plotting template: {e}") from e
    
    if not template_plotted:
        # Show a message on the plot
        ax.text(0.5, 0.3, "Template plotting failed - no template data found", 
               ha='center', va='center', fontsize=PLOT_STATUS_FONTSIZE, transform=ax.transAxes,
               bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8))
    
    # Add rest-wavelength top axis using the match redshift
    try:
        if z_template is not None and np.isfinite(z_template) and (1.0 + z_template) != 0.0:
            try:
                # Prefer modern secondary axis API for correct tick mapping
                secax = ax.secondary_xaxis(
                    'top',
                    functions=(
                        lambda x: x / (1.0 + z_template),
                        lambda r: r * (1.0 + z_template),
                    ),
                )
                secax.set_xlabel('Rest Wavelength (Å)', labelpad=6)
            except Exception:
                # Fallback to twiny if secondary_xaxis is unavailable
                ax_top = ax.twiny()
                x0, x1 = ax.get_xlim()
                ax_top.set_xlim(x0 / (1.0 + z_template), x1 / (1.0 + z_template))
                ax_top.set_xlabel('Rest Wavelength (Å)', labelpad=6)
                try:
                    ax_top.tick_params(axis='x', labeltop=True)
                except Exception:
                    pass
    except Exception:
        pass
    
    # Add template metadata annotation
    # Match GUI overlay info box (top-right, white background, black border)
    template_info_lines = []
    template_info_lines.append(f"Template: {template_name}")
    if template_type != 'Unknown':
        if template_subtype:
            template_info_lines.append(f"Subtype: {template_subtype}, Age: {template_age:.1f}d")
        else:
            template_info_lines.append(f"Type: {template_type}, Age: {template_age:.1f}d")
    else:
        template_info_lines.append(f"Age: {template_age:.1f}d")
    if redshift_error and np.isfinite(redshift_error) and redshift_error > 0:
        template_info_lines.append(f"z = {z_template:.6f} ±{redshift_error:.6f}")
    else:
        template_info_lines.append(f"z = {z_template:.6f}")
    # Use best available metric (RLAP-CCC if available, otherwise RLAP)
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    best_metric_value = get_best_metric_value(match)
    metric_name = get_best_metric_name(match)
    template_info_lines.append(f"{metric_name} = {best_metric_value:.2f}")
    template_info = "\n".join(template_info_lines)
    ax.text(0.98, 0.98, template_info, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='black', alpha=0.8))
    
    # Format plot (no title per user requirement)
    if not _apply_no_title_styling_if_available(fig, ax, "Obs. Wavelength (Å)", "Flux", theme_manager):
        # Fallback styling if unified systems not available
        ax.set_xlabel('Obs. Wavelength (Å)')
        ax.set_ylabel('Flux')
        _apply_faint_grid(ax, theme_manager)
    
    # Ensure faint grid is applied regardless of styling path
    _apply_faint_grid(ax, theme_manager)
    # Match GUI: no legend (info box replaces it)

    # Match GUI stable range setting with margins
    try:
        all_wave = None
        all_flux = None
        if input_wave is not None and input_flux is not None:
            all_wave = np.array(input_wave)
            all_flux = np.array(input_flux)
        if template_plotted:
            if 'spectra' in match and 'flux' in match['spectra']:
                tw = np.asarray(match['spectra']['flux']['wave'])
                tf = np.asarray(match['spectra']['flux']['flux'])
            elif ('processed_flux' in match and hasattr(result, 'processed_spectrum') and 'continuum' in result.processed_spectrum):
                tw = np.asarray(result.processed_spectrum['log_wave'])
                tf = (np.asarray(match['processed_flux']) + 1.0) * np.asarray(result.processed_spectrum['continuum'])
            else:
                tw = None
                tf = None
            if tw is not None and tf is not None:
                all_wave = tw if all_wave is None else np.concatenate([all_wave, tw])
                all_flux = tf if all_flux is None else np.concatenate([all_flux, tf])
        if all_wave is not None and all_flux is not None and all_wave.size > 1:
            x_margin = (np.max(all_wave) - np.min(all_wave)) * 0.05
            y_margin = (np.max(all_flux) - np.min(all_flux)) * 0.10
            ax.set_xlim(np.min(all_wave) - x_margin, np.max(all_wave) + x_margin)
            y_min = np.min(all_flux) - y_margin
            y_max = np.max(all_flux) + y_margin
            if y_max <= y_min:
                y_center = y_min
                y_min = y_center - (abs(y_center) * 0.1 if y_center != 0 else 1.0)
                y_max = y_center + (abs(y_center) * 0.1 if y_center != 0 else 1.0)
            ax.set_ylim(y_min, y_max)
    except Exception:
        # Fallback autoscale
        ax.autoscale(enable=True, axis='both', tight=False)
    
    fig.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def plot_flat_comparison(match: Dict[str, Any], result: Any, 
                       figsize: Tuple[int, int] = (10, 8),
                       save_path: Optional[str] = None,
                       fig: Optional[plt.Figure] = None,
                       theme_manager=None) -> plt.Figure:
    """
    Plot comparison of flattened input spectrum with flattened template.
    
    This recreates the 'FLAT' view from Fortran SNID, showing the processed spectra
    for both the input and template, which highlights spectral features.
    
    Uses the processed spectrum from SNID analysis.
    - flat_flux is the apodized flat spectrum  
    - tapered_flux[left_edge:right_edge+1] (processed and apodized)
    - Data is trimmed and filtered to match the GUI display
    
    Parameters:
        match: Dictionary containing template match information
        result: SNIDResult object with flattened spectrum information
        figsize: Figure size (width, height)
        save_path: Path to save the figure (None for no saving)
        fig: Optional matplotlib Figure to draw on. If None, a new figure is created.
        theme_manager: Theme manager object for theme support
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    
    # Use provided figure or create a new one
    if fig is None:
        fig = plt.figure(figsize=figsize)
    else:
        fig.clear()  # Clear the existing figure
    
    # Create single full-size plot
    ax = fig.add_subplot(111)
    
    # Get template info (cleaned like GUI)
    template = match.get('template', {})
    try:
        from snid_sage.shared.utils import clean_template_name
        template_name = clean_template_name(template.get('name', 'Unknown') or match.get('name', 'Unknown'))
    except Exception:
        template_name = template.get('name', 'Unknown')
    template_type = template.get('type', 'Unknown')
    template_subtype = template.get('subtype', '')
    template_age = template.get('age', 0)
    z_template = match.get('redshift', 0)
    rlap_ccc_value = match.get('rlap_ccc', None)
    rlap_value = match.get('rlap', 0)
    redshift_error = match.get('redshift_error', 0)
    
    # Plot flattened input spectrum (using the spectrum just before retransformation to flux)
    input_wave = None
    input_flux = None
    
    # Use processed spectrum - SNID analysis stores the correctly apodized versions
    if hasattr(result, 'processed_spectrum') and result.processed_spectrum:
        input_wave = result.processed_spectrum['log_wave']
        
        
        # This is different from the original preprocessing flat_flux which is non-apodized
        # The SNID analysis result.processed_spectrum contains the correctly trimmed and apodized data
        input_flux = result.processed_spectrum['flat_flux']  # This IS the apodized version from SNID analysis
        
        # No need to filter - SNID analysis already trimmed to [left_edge:right_edge+1]
        # The data in result.processed_spectrum is already the correctly processed and trimmed version
        
        ax.plot(input_wave, input_flux, color='#3b82f6', label='Observed Spectrum', linewidth=2)
        
    elif isinstance(result.flat_input, dict) and 'wave' in result.flat_input and 'flux' in result.flat_input:
        # Fallback to flat_input if processed_spectrum not available
        input_wave = result.flat_input['wave']
        input_flux = result.flat_input['flux']
        
        # Filter out zero-padded regions (INPUT SPECTRUM ONLY)
        input_wave, input_flux = _filter_nonzero_spectrum(input_wave, input_flux, 
                                                       getattr(result, 'processed_spectrum', None))
        
        ax.plot(input_wave, input_flux, color='#3b82f6', label='Observed Spectrum', linewidth=2)
        
    else:
        raise ValueError("No flattened input spectrum data available for plotting")
    
    # Try to plot the flattened template (using same approach as flux function)
    template_plotted = False
    try:
        # First try: Use pre-computed template flat data from the match (like GUI)
        if 'spectra' in match and 'flat' in match['spectra']:
            template_wave = match['spectra']['flat']['wave']
            template_flux = match['spectra']['flat']['flux']
            
            # DON'T filter templates - they are already properly trimmed by SNID analysis
            # snid_sage.snid.py
            # Filtering them again with input spectrum edges cuts them incorrectly
            
            ax.plot(
                template_wave,
                template_flux,
                color='#E74C3C',
                linewidth=2,
                label='Template',
                alpha=0.8,
            )
            template_plotted = True
        
        # Second try: Use processed_flux from match (legacy compatibility)
        elif 'processed_flux' in match and input_wave is not None:
            template_flux_proc = match['processed_flux']
            
            # Ensure it has the same length as the input flat flux
            if len(template_flux_proc) == len(input_wave):
                # DON'T filter templates - they are already properly trimmed by SNID analysis
                # snid_sage.snid.py
                # Filtering them again with input spectrum edges cuts them incorrectly
                
                ax.plot(
                    input_wave, 
                    template_flux_proc,
                    color='#E74C3C',
                    linewidth=2, 
                    label='Template',
                    alpha=0.8,
                )
                template_plotted = True
                           
    except Exception as e:
        # Re-raise the exception to see what's actually going wrong
        raise RuntimeError(f"Error plotting flattened template: {e}") from e
    
    if not template_plotted:
        # Show a message on the plot
        ax.text(0.5, 0.3, "Template plotting failed - no template data found", 
               ha='center', va='center', fontsize=PLOT_STATUS_FONTSIZE, transform=ax.transAxes,
               bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8))
    
    # Add rest-wavelength top axis using the match redshift
    try:
        if z_template is not None and np.isfinite(z_template) and (1.0 + z_template) != 0.0:
            try:
                secax = ax.secondary_xaxis(
                    'top',
                    functions=(
                        lambda x: x / (1.0 + z_template),
                        lambda r: r * (1.0 + z_template),
                    ),
                )
                secax.set_xlabel('Rest Wavelength (Å)', labelpad=6)
            except Exception:
                ax_top = ax.twiny()
                x0, x1 = ax.get_xlim()
                ax_top.set_xlim(x0 / (1.0 + z_template), x1 / (1.0 + z_template))
                ax_top.set_xlabel('Rest Wavelength (Å)', labelpad=6)
                try:
                    ax_top.tick_params(axis='x', labeltop=True)
                except Exception:
                    pass
    except Exception:
        pass

    # Add template metadata annotation
    # Match GUI overlay info box (top-right, white background, black border)
    template_info_lines = []
    template_info_lines.append(f"Template: {template_name}")
    if template_type != 'Unknown':
        if template_subtype:
            template_info_lines.append(f"Subtype: {template_subtype}, Age: {template_age:.1f}d")
        else:
            template_info_lines.append(f"Type: {template_type}, Age: {template_age:.1f}d")
    else:
        template_info_lines.append(f"Age: {template_age:.1f}d")
    if redshift_error and np.isfinite(redshift_error) and redshift_error > 0:
        template_info_lines.append(f"z = {z_template:.6f} ±{redshift_error:.6f}")
    else:
        template_info_lines.append(f"z = {z_template:.6f}")
    # Use best available metric (RLAP-CCC if available, otherwise RLAP)
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    best_metric_value = get_best_metric_value(match)
    metric_name = get_best_metric_name(match)
    template_info_lines.append(f"{metric_name} = {best_metric_value:.2f}")
    template_info = "\n".join(template_info_lines)
    ax.text(0.98, 0.98, template_info, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='black', alpha=0.8))
    
    # Format plot (no title per user requirement)
    if not _apply_no_title_styling_if_available(fig, ax, "Obs. Wavelength (Å)", "Flattened Flux", theme_manager):
        # Fallback styling if unified systems not available
        ax.set_xlabel('Obs. Wavelength (Å)')
        ax.set_ylabel('Flattened Flux')
        _apply_faint_grid(ax, theme_manager)
    
    # Ensure faint grid is applied regardless of styling path
    _apply_faint_grid(ax, theme_manager)
    # Match GUI: no legend (info box replaces it)

    # Match GUI stable range setting with margins
    try:
        all_wave = None
        all_flux = None
        if input_wave is not None and input_flux is not None:
            all_wave = np.array(input_wave)
            all_flux = np.array(input_flux)
        if template_plotted:
            if 'spectra' in match and 'flat' in match['spectra']:
                tw = np.asarray(match['spectra']['flat']['wave'])
                tf = np.asarray(match['spectra']['flat']['flux'])
            elif 'processed_flux' in match and input_wave is not None:
                tw = np.asarray(input_wave)
                tf = np.asarray(match['processed_flux'])
            else:
                tw = None
                tf = None
            if tw is not None and tf is not None:
                all_wave = tw if all_wave is None else np.concatenate([all_wave, tw])
                all_flux = tf if all_flux is None else np.concatenate([all_flux, tf])
        if all_wave is not None and all_flux is not None and all_wave.size > 1:
            x_margin = (np.max(all_wave) - np.min(all_wave)) * 0.05
            y_margin = (np.max(all_flux) - np.min(all_flux)) * 0.10
            ax.set_xlim(np.min(all_wave) - x_margin, np.max(all_wave) + x_margin)
            y_min = np.min(all_flux) - y_margin
            y_max = np.max(all_flux) + y_margin
            if y_max <= y_min:
                y_center = y_min
                y_min = y_center - (abs(y_center) * 0.1 if y_center != 0 else 1.0)
                y_max = y_center + (abs(y_center) * 0.1 if y_center != 0 else 1.0)
            ax.set_ylim(y_min, y_max)
    except Exception:
        # Fallback autoscale
        ax.autoscale(enable=True, axis='both', tight=False)
    
    fig.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def plot_correlation_view(match: Dict[str, Any], result: Any, 
                         figsize: Tuple[int, int] = (10, 8),
                         save_path: Optional[str] = None,
                         fig: Optional[plt.Figure] = None,
                         theme_manager=None) -> plt.Figure:
    """
    Plot correlation function for the selected template.
    
    This recreates the 'XCOR' view from Fortran SNID, showing the cross-correlation
    function with the identified peak.
    
    Parameters:
        match: Dictionary containing template match information
        result: SNIDResult object with correlation data
        figsize: Figure size (width, height)
        save_path: Path to save the figure (None for no saving)
        fig: Optional matplotlib Figure to draw on. If None, a new figure is created.
        theme_manager: Theme manager object for theme support
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    if not hasattr(result, 'correlation') or result.correlation is None:
        raise ValueError("Correlation data missing")
        
    # Use provided figure or create a new one
    if fig is None:
        fig = plt.figure(figsize=figsize)
    else:
        fig.clear()  # Clear the existing figure
    
    # Create single full-size plot
    ax = fig.add_subplot(111)
    
    # Get template info
    template = match.get('template', {})
    template_name = template.get('name', 'Unknown')
    template_type = template.get('type', 'Unknown')
    template_subtype = template.get('subtype', '')
    template_age = template.get('age', 0)
    z_template = match.get('redshift', 0)
    rlap_value = match.get('rlap', 0)
    
    # Use correlation from the match dictionary if available, otherwise fallback to result.correlation
    if 'correlation' in match and isinstance(match['correlation'], dict):
        corr_data = match['correlation']
        
        # Plot full correlation (before trimming) if available
        if 'z_axis_full' in corr_data and 'correlation_full' in corr_data:
            ax.plot(corr_data['z_axis_full'], corr_data['correlation_full'], 
                   'b-', linewidth=1.0, alpha=0.7, label='Full correlation')
        
        # Plot trimmed correlation (after trimming) if available
        if 'z_axis_peak' in corr_data and 'correlation_peak' in corr_data:
            ax.plot(corr_data['z_axis_peak'], corr_data['correlation_peak'], 
                   'k-', linewidth=1.5, label='Trimmed correlation')
        
        # Mark the best redshift
        ax.axvline(x=z_template, color='r', linestyle=':', linewidth=1.5, 
                 label=f'z = {z_template:.6f}', alpha=0.8)
        
        # Set axis limits based on available data
        if 'z_axis_full' in corr_data:
            z_min, z_max = np.min(corr_data['z_axis_full']), np.max(corr_data['z_axis_full'])
            z_range = z_max - z_min
            ax.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
            
    else:
        # Fallback to other correlation data if available
        has_correlation = hasattr(result, 'correlation') and result.correlation is not None and \
                         hasattr(result, 'redshift_axis') and result.redshift_axis is not None
        has_correlations = hasattr(result, 'correlations') and len(result.correlations) > 0
        
        if has_correlation:
            # Use the stored correlation and redshift axis
            ax.plot(result.redshift_axis, result.correlation, 'k-', label='Correlation', linewidth=1.5)
            
            # Add vertical line at best redshift
            ax.axvline(x=z_template, color='r', linestyle=':', linewidth=1.5, 
                      label=f'z = {z_template:.6f}', alpha=0.8)
            
            # Set x-axis limits to focus on the relevant region
            z_min, z_max = np.min(result.redshift_axis), np.max(result.redshift_axis)
            z_range = z_max - z_min
            ax.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
            
        elif has_correlations:
            # Use the first correlation from the list
            corr_data = result.correlations[0]
            ax.plot(corr_data['z_axis'], corr_data['xcor'], 'k-', label='Correlation', linewidth=1.5)
            
            # Add vertical line at best redshift
            ax.axvline(x=z_template, color='r', linestyle=':', linewidth=1.5, 
                      label=f'z = {z_template:.6f}', alpha=0.8)
            
            # Set x-axis limits to focus on the relevant region
            z_min, z_max = np.min(corr_data['z_axis']), np.max(corr_data['z_axis'])
            z_range = z_max - z_min
            ax.set_xlim(z_min - 0.1 * z_range, z_max + 0.1 * z_range)
        else:
            ax.text(0.5, 0.5, "No correlation data available", 
                   ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE,
                   transform=ax.transAxes)
            ax.axis('off')
            fig.tight_layout()
            return fig
    
    # Add template information annotation
    template_info = f"Template: {template_name}\n"
    if template_type != 'Unknown':
        template_info += f"Type: {template_type}"
        if template_subtype:
            template_info += f" {template_subtype}"
        template_info += "\n"
    
    if template_age is not None and np.isfinite(template_age):
        template_info += f"Age: {template_age:.1f} days\n"
    template_info += f"z = {z_template:.6f}\n"
    # Use best available metric (RLAP-CCC if available, otherwise RLAP)
    from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
    best_metric_value = get_best_metric_value(match)
    metric_name = get_best_metric_name(match)
    template_info += f"{metric_name} = {best_metric_value:.1f}"
    
    # Add the annotation with a semi-transparent background
    ax.text(0.02, 0.98, template_info, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='left',
            bbox=_create_themed_bbox_if_available(theme_manager=theme_manager))
    
    # Format plot (no title per user requirement)
    # Always use standardized font sizes, regardless of GUI styling
    ax.set_xlabel('Redshift', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.set_ylabel('Correlation', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.grid(True, alpha=0.3)
    
    # Apply no-title styling if available, but ensure font sizes are preserved
    if _apply_no_title_styling_if_available(fig, ax, "Redshift", "Correlation", theme_manager):
        # Re-apply standardized font sizes after GUI styling
        ax.set_xlabel('Redshift', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax.set_ylabel('Correlation', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    
    ax.legend(loc='upper right', fontsize=PLOT_LEGEND_FONTSIZE)
    
    # Set y-axis limits to show full correlation range with some padding
    y_data = []
    for line in ax.get_lines():
        if line.get_label() not in ['z = {:.6f}'.format(z_template)]:  # Skip vertical line
            y_data.extend(line.get_ydata())
    
    if y_data:
        y_min, y_max = np.min(y_data), np.max(y_data)
        y_range = y_max - y_min
        ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)
    
    # Adjust layout
    fig.tight_layout()
    
    # Save if requested
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def plot_template_epochs(template_data: Dict[str, Any], 
                        figsize: Tuple[int, int] = (12, 10),
                        apply_filter: bool = False,
                        filter_params: Optional[Dict[str, int]] = None,
                        yoff: float = 1.0,
                        save_path: Optional[str] = None,
                        fig: Optional[plt.Figure] = None,
                        theme_manager=None) -> plt.Figure:
    """
    Plot multi-epoch template spectra with vertical stacking.
    
    Replicates the functionality of Fortran plotlnw.f for displaying
    multiple spectra from the same template at different epochs/ages.
    
    Parameters:
        template_data: Dictionary containing template information with multiple epochs
        figsize: Figure size (width, height)
        apply_filter: Whether to apply bandpass filtering
        filter_params: Dictionary with k1, k2, k3, k4 filter parameters
        yoff: Vertical offset between spectra
        save_path: Path to save the figure
        fig: Optional matplotlib Figure to draw on
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    if fig is None:
        fig = plt.figure(figsize=figsize)
    else:
        fig.clear()
    
    ax = fig.add_subplot(111)
    
    # Extract template information
    template_name = template_data.get('name', 'Unknown')
    template_type = template_data.get('type', 'Unknown')
    epochs = template_data.get('epochs', [])
    
    if not epochs:
        ax.text(0.5, 0.5, "No epoch data available for this template", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE,
               transform=ax.transAxes)
        ax.axis('off')
        return fig
    
    n_epochs = len(epochs)
    
    # Set up filter parameters
    if apply_filter and filter_params is None:
        # Default filter parameters (similar to Fortran defaults)
        nw = len(epochs[0].get('wave', []))
        filter_params = {
            'k1': 1,
            'k2': 4, 
            'k3': nw // 12,
            'k4': nw // 10
        }
    
    # Get wavelength range
    if epochs:
        wave = epochs[0].get('wave', [])
        if len(wave) > 0:
            w_min, w_max = np.min(wave), np.max(wave)
        else:
            w_min, w_max = 2500, 10000
    else:
        w_min, w_max = 2500, 10000
    
    # Plot each epoch
    colors = plt.cm.viridis(np.linspace(0, 1, n_epochs))
    
    for i, epoch in enumerate(epochs):
        wave = epoch.get('wave', [])
        flux = epoch.get('flux', [])
        age = epoch.get('age', 0)
        
        if len(wave) == 0 or len(flux) == 0:
            continue
            
        # Apply bandpass filter if requested
        if apply_filter and filter_params:
            # This would require implementing the bandpass filter
            # For now, we'll skip filtering and just plot the original
            pass
        
        # Apply vertical offset (plot from top to bottom like Fortran)
        plot_flux = np.array(flux) + (n_epochs - i) * yoff
        
        # Plot spectrum
        ax.plot(wave, plot_flux, color=colors[i], linewidth=1.0, 
               label=f'{age:+.0f}d' if age >= 0 else f'{age:.0f}d')
        
        # Add age label on the right side
        y_label_pos = (n_epochs - i + 0.35) * yoff
        age_label = f'+{age:.0f}' if age >= 0 else f'{age:.0f}'
        ax.text(w_max * 1.02, y_label_pos, age_label, 
               verticalalignment='center', fontsize=10)
    
    # Set axis limits and labels
    y_max = (n_epochs + 1) * yoff
    ax.set_xlim(w_min, w_max)
    ax.set_ylim(0, y_max)
    
    # Labels (no title per user requirement)
    # Always use standardized font sizes, regardless of GUI styling
    ax.set_xlabel('Rest Wavelength [Å]', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.set_ylabel('Flattened Flux', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    
    # Apply no-title styling if available, but ensure font sizes are preserved
    if _apply_no_title_styling_if_available(fig, ax, "Rest Wavelength [Å]", "Flattened Flux", theme_manager):
        # Re-apply standardized font sizes after GUI styling
        ax.set_xlabel('Rest Wavelength [Å]', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax.set_ylabel('Flattened Flux', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    # Adjust layout to make room for age labels
    plt.subplots_adjust(right=0.9)
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def plot_cluster_subtype_proportions(result: Any, selected_cluster: Dict[str, Any] = None,
                                   figsize: Tuple[int, int] = (12, 8),
                                   save_path: Optional[str] = None,
                                   fig: Optional[plt.Figure] = None,
                                   theme_manager=None) -> plt.Figure:
    """
    Plot subtype proportions within the selected cluster.
    
    Since clusters now contain only one type, this focuses on subtype distribution
    within the winning cluster rather than type distribution across all results.
    
    Parameters:
        result: SNIDResult object
        selected_cluster: The selected cluster from GMM clustering results
        figsize: Size of the figure
        save_path: Path to save the figure
        fig: Existing figure to plot on
        theme_manager: Theme manager for styling
        
    Returns:
        matplotlib.figure.Figure: The figure
    """
    # Create figure if not provided
    if fig is None:
        fig = plt.figure(figsize=figsize, constrained_layout=True)
    
    # Create a grid for multiple plots
    # Give more space to the table (right side) and less to the pie chart (left side)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], width_ratios=[0.6, 1.4])
    
    # Main subtype pie chart
    ax1 = fig.add_subplot(gs[0, 0])
    # Subtype statistics table
    ax2 = fig.add_subplot(gs[0, 1])
    # Subtype proportions vs RLAP threshold (bottom row, spanning both columns)
    ax3 = fig.add_subplot(gs[1, :])
    
    # Determine which matches to use - prioritize cluster matches
    cluster_matches = []
    cluster_type = "Unknown"
    
    if selected_cluster and 'matches' in selected_cluster:
        cluster_matches = selected_cluster['matches']
        cluster_type = selected_cluster.get('type', 'Unknown')
        match_source = f"Selected cluster ({cluster_type})"
    elif hasattr(result, 'filtered_matches') and result.filtered_matches:
        cluster_matches = result.filtered_matches
        # Try to get type from first match
        if cluster_matches:
            cluster_type = cluster_matches[0].get('template', {}).get('type', 'Unknown')
        match_source = "Filtered matches (winning cluster)"
    elif hasattr(result, 'best_matches') and result.best_matches:
        cluster_matches = result.best_matches
        if cluster_matches:
            cluster_type = cluster_matches[0].get('template', {}).get('type', 'Unknown')
        match_source = "Best matches"
    
    if not cluster_matches:
        for ax in [ax1, ax2, ax3]:
            ax.text(0.5, 0.5, "No cluster matches available", ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE)
            ax.axis('off')
        return fig
    
    # Calculate subtype proportions within the cluster
    subtype_counts = defaultdict(int)
    subtype_rlaps = defaultdict(list)
    subtype_redshifts = defaultdict(list)
    subtype_ages = defaultdict(list)
    subtype_color_map = {}  # Initialize color mapping for consistency
    
    for match in cluster_matches:
        template = match.get('template', {})
        subtype = template.get('subtype', 'Unknown')
        if not subtype or subtype.strip() == '':
            subtype = 'Unknown'
        
        subtype_counts[subtype] += 1
        subtype_rlaps[subtype].append(match.get('rlap', 0))
        subtype_redshifts[subtype].append(match.get('redshift', 0))
        
        age = template.get('age', 0)
        # Check for valid age (negative ages are valid for pre-peak)
        if age is not None and np.isfinite(age):
            subtype_ages[subtype].append(age)
    
    # Plot 1: Subtype pie chart
    if subtype_counts:
        sorted_subtypes = sorted(subtype_counts.items(), key=lambda x: x[1], reverse=True)
        subtype_labels = [item[0] for item in sorted_subtypes]
        subtype_values = [item[1] for item in sorted_subtypes]
        
        # Create consistent color mapping for subtypes to ensure pie chart and line plot match
        # Use custom color palette
        custom_palette = get_custom_color_palette()
        for i, subtype in enumerate(subtype_labels):
            subtype_color_map[subtype] = custom_palette[i % len(custom_palette)]
        colors = [subtype_color_map[label] for label in subtype_labels]
        
        # Create explode parameter - explode the winning subtype based on result.best_subtype
        winning_subtype = None
        if hasattr(result, 'best_subtype') and result.best_subtype:
            winning_subtype = result.best_subtype
            
        explode = []
        for i, label in enumerate(subtype_labels):
            if winning_subtype and label == winning_subtype:
                explode.append(0.1)  # Explode the winning subtype
            else:
                explode.append(0)    # Keep other subtypes normal
        
        wedges, texts, autotexts = ax1.pie(
            subtype_values, 
            labels=subtype_labels,
            autopct='%1.1f%%',
            colors=colors,
            explode=explode,
            startangle=90)
        
        # Add dark edge around the winning slice
        for i, (wedge, label) in enumerate(zip(wedges, subtype_labels)):
            if winning_subtype and label == winning_subtype:
                wedge.set_edgecolor('black')
                wedge.set_linewidth(2)
            else:
                wedge.set_edgecolor('white')
                wedge.set_linewidth(1)
        
        ax1.set_title(f'{cluster_type} Subtype Proportions\n({len(cluster_matches)} matches)', fontsize=PLOT_TITLE_FONTSIZE)
        
        # Style the text
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontsize(PLOT_PIE_AUTOPCT_FONTSIZE)
            autotext.set_weight('bold')
    else:
        ax1.text(0.5, 0.5, f"No subtypes found for {cluster_type}", ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE)
        ax1.axis('off')
    
    # Plot 2: Subtype statistics table
    ax2.axis('off')
    if subtype_counts:
        table_data = []
        headers = ['Subtype', 'Count', '%', 'Avg RLAP-cos', 'Weighted z', 'Weighted age']
        
        total_matches = len(cluster_matches)
        
        for subtype, count in sorted_subtypes:
            percentage = (count / total_matches) * 100
            
            # Calculate average RLAP-cos for this subtype
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            subtype_metric_values = [get_best_metric_value(m) for m in cluster_matches 
                                         if m.get('template', {}).get('subtype', 'Unknown') == subtype]
            avg_metric = np.mean(subtype_metric_values) if subtype_metric_values else 0
            
            # Use RLAP-cos weighted redshift for subtypes if enough data
            if len(subtype_redshifts[subtype]) > 1:
                from snid_sage.shared.utils.math_utils import calculate_hybrid_weighted_redshift, get_best_metric_value
                # Get RLAP-cos weights for this subtype
                subtype_weights = [get_best_metric_value(m) for m in cluster_matches 
                                 if m.get('template', {}).get('subtype', 'Unknown') == subtype][:len(subtype_redshifts[subtype])]
                # Convert weights to redshift errors for hybrid calculation
                # Use a small default error for RLAP-based weights
                redshift_errors = np.full_like(subtype_redshifts[subtype], 0.01)
                avg_z, _, _ = calculate_hybrid_weighted_redshift(
                    subtype_redshifts[subtype], redshift_errors, include_cluster_scatter=False
                )
            else:
                avg_z = subtype_redshifts[subtype][0] if subtype_redshifts[subtype] else 0
            
            if len(subtype_ages[subtype]) > 1:
                from snid_sage.shared.utils.math_utils import calculate_rlap_weighted_age, get_best_metric_value
                # Use RLAP-cos if available, otherwise RLAP
                subtype_rlaps_list = [get_best_metric_value(m) for m in cluster_matches 
                                     if m.get('template', {}).get('subtype', 'Unknown') == subtype][:len(subtype_ages[subtype])]
                avg_age, _, _, _ = calculate_rlap_weighted_age(
                    subtype_ages[subtype], subtype_rlaps_list, include_cluster_scatter=False
                )
            else:
                avg_age = subtype_ages[subtype][0] if subtype_ages[subtype] else 0
            
            table_data.append([
                subtype[:8],  # Truncate long subtype names
                str(count),
                f"{percentage:.1f}",
                f"{avg_metric:.1f}",
                f"{avg_z:.4f}",
                f"{avg_age:.1f}" if avg_age is not None and np.isfinite(avg_age) else "N/A"
            ])
        
        # Create table
        table = ax2.table(cellText=table_data, colLabels=headers,
                         cellLoc='center', loc='center',
                         colWidths=[0.15, 0.1, 0.1, 0.15, 0.15, 0.15])
        table.auto_set_font_size(False)
        table.set_fontsize(PLOT_TABLE_FONTSIZE)
        table.scale(1, 1.5)
        
        # Style header
        for i in range(len(headers)):
            table[(0, i)].set_facecolor('#E0E0E0')
            table[(0, i)].set_text_props(weight='bold')
        
        ax2.set_title(f'Subtype Statistics\n{match_source}', fontsize=PLOT_TITLE_FONTSIZE)
    else:
        ax2.text(0.5, 0.5, "No subtype statistics available", ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE)
    
    # Plot 3: Subtype proportions vs RLAP-cos threshold
    if cluster_matches and len(set(subtype_counts.keys())) > 1:
        # Find RLAP-cos range
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        all_metric_values = [get_best_metric_value(m) for m in cluster_matches]
        max_metric = max(all_metric_values)
        min_metric = min(5.0, min(all_metric_values))  # Start from 5.0 or lower if needed
        
        # Create RLAP-cos thresholds
        metric_thresholds = np.linspace(min_metric, min(max_metric, 30), 12)
        
        subtype_proportions_by_rlap = {subtype: [] for subtype in subtype_counts.keys()}
        
        # Calculate proportions at each threshold
        for threshold in metric_thresholds:
            qualified_matches = [match for match in cluster_matches 
                               if get_best_metric_value(match) >= threshold]
            
            if qualified_matches:
                threshold_subtype_counts = defaultdict(int)
                for match in qualified_matches:
                    template = match.get('template', {})
                    subtype = template.get('subtype', 'Unknown')
                    if not subtype or subtype.strip() == '':
                        subtype = 'Unknown'
                    threshold_subtype_counts[subtype] += 1
                
                total_qualified = len(qualified_matches)
                for subtype in subtype_proportions_by_rlap:
                    proportion = threshold_subtype_counts[subtype] / total_qualified if total_qualified > 0 else 0
                    subtype_proportions_by_rlap[subtype].append(proportion)
            else:
                for subtype in subtype_proportions_by_rlap:
                    subtype_proportions_by_rlap[subtype].append(0)
        
        # Plot lines for each subtype using consistent colors from pie chart
        for subtype, proportions in subtype_proportions_by_rlap.items():
            if any(p > 0 for p in proportions):  # Only plot if subtype has non-zero proportions
                # Use the same color mapping as the pie chart for consistency
                color = subtype_color_map.get(subtype, 'gray')
                ax3.plot(metric_thresholds, proportions, 'o-', label=subtype, 
                        color=color, linewidth=2, markersize=6)
        
        ax3.set_xlabel('RLAP-cos Threshold', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax3.set_ylabel('Subtype Proportion', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='center right', frameon=True, fontsize=PLOT_LEGEND_FONTSIZE)
        # Set y-axis limits to include a bit below 0 and above 1 so lines don't get cut
        ax3.set_ylim(-0.05, 1.05)
    else:
        ax3.text(0.5, 0.5, "Insufficient subtype diversity for RLAP analysis\n(Need multiple subtypes)", 
                ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE)
        ax3.set_xlim(0, 1)
        ax3.set_ylim(0, 1)
        ax3.set_xticks([])
        ax3.set_yticks([])
    
    # Apply theme if available
    if theme_manager:
        theme = theme_manager.get_current_theme()
        fig.patch.set_facecolor(theme.get('bg_primary', 'white'))
        for ax in [ax1, ax2, ax3]:
            ax.tick_params(colors=theme.get('text_color', 'black'))
            if hasattr(ax, 'title'):
                ax.title.set_color(theme.get('text_color', 'black'))
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_color(theme.get('text_color', 'black'))
    
    # Explicitly set font sizes for the subtype plot (ax3) to override theme defaults
    if cluster_matches and len(set(subtype_counts.keys())) > 1:
        ax3.set_xlabel('RLAP-cos Threshold', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax3.set_ylabel('Subtype Proportion', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
        ax3.tick_params(axis='both', labelsize=PLOT_TICK_FONTSIZE)  # Set tick label size
    
    # Save if requested
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig


def compute_cluster_subtype_proportions(cluster_matches: List[Dict[str, Any]], 
                                      weighted: bool = True) -> Dict[str, float]:
    """
    Compute subtype proportions within a specific cluster.
    
    Parameters:
        cluster_matches: List of template matches from a specific cluster
        weighted: Whether to weight by RLAP values
        
    Returns:
        Dictionary mapping subtype names to their proportions
    """
    if not cluster_matches:
        return {}
    
    subtype_values = defaultdict(float)
    
    for match in cluster_matches:
        template = match.get('template', {})
        subtype = template.get('subtype', 'Unknown')
        if not subtype or subtype.strip() == '':
            subtype = 'Unknown'
        
        # Use RLAP-cos if available, otherwise RLAP
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        value = get_best_metric_value(match) if weighted else 1.0
        subtype_values[subtype] += value
    
    total = sum(subtype_values.values())
    if total > 0:
        return {subtype: val/total for subtype, val in subtype_values.items()}
    else:
        return {}
