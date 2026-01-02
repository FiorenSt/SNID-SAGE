"""
3D Visualization for Type-Specific GMM Clustering
================================================

This module provides advanced visualization capabilities for the improved
GMM clustering approach, including 3D plots showing redshift vs type vs best metric (HσLAP-CCC/HLAP).
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from typing import Dict, List, Any, Tuple, Optional
import logging

# Import centralized font size configuration
try:
    from snid_sage.shared.utils.plotting.font_sizes import (
        PLOT_TITLE_FONTSIZE,
        PLOT_AXIS_LABEL_FONTSIZE,
        PLOT_TICK_FONTSIZE,
        PLOT_LEGEND_FONTSIZE,
        PLOT_ERROR_FONTSIZE,
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
    PLOT_ERROR_FONTSIZE: int = 14

_LOGGER = logging.getLogger(__name__)

def plot_3d_type_clustering(
    clustering_results: Dict[str, Any],
    figsize: Tuple[int, int] = (14, 10),
    save_path: Optional[str] = None,
    theme_manager=None
) -> plt.Figure:
    """
    Create a 3D visualization of redshift vs type vs best metric (HσLAP-CCC/HLAP) with clustering results.
    
    Parameters:
    -----------
    clustering_results : Dict
        Results from perform_type_specific_gmm_clustering
    figsize : Tuple[int, int]
        Figure size (width, height)
    save_path : Optional[str]
        Path to save the figure
    theme_manager : Optional
        Theme manager for styling
        
    Returns:
    --------
    plt.Figure: The figure object
    """
    
    from .cosmological_clustering import create_3d_visualization_data
    
    # Prepare visualization data
    viz_data = create_3d_visualization_data(clustering_results)
    
    if len(viz_data['redshifts']) == 0:
        # Create empty plot with message
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No clustering data available for 3D visualization", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, transform=ax.transAxes)
        ax.axis('off')
        return fig
    
    # Create 3D plot
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection='3d')
    
    # Set explicit white background
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Determine which metric is being used
    metric_name = clustering_results.get('metric_used', 'HσLAP-CCC')
    
    # Get unique types and create consistent color map
    unique_types = list(viz_data['type_mapping'].keys())
    colors = plt.cm.Set1(np.linspace(0, 1, len(unique_types)))
    
    # Plot each type with different colors
    legend_elements = []
    for type_name in unique_types:
        type_idx = viz_data['type_mapping'][type_name]
        type_mask = viz_data['type_indices'] == type_idx
        type_redshifts = viz_data['redshifts'][type_mask]
        type_indices = viz_data['type_indices'][type_mask]
        
        # Use best available metric values
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        type_matches = [m for m in viz_data['matches'] if m.get('template', {}).get('type', 'Unknown') == type_name]
        type_metric_values = np.array([get_best_metric_value(m) for m in type_matches])
        
        if len(type_redshifts) == 0:
            continue
            
        color = colors[list(unique_types).index(type_name)]
        
        # Check if we have best cluster data for this type
        if viz_data.get('best_cluster_types') and type_name in viz_data['best_cluster_types']:
            best_mask = viz_data['is_best_cluster'][type_mask]
            other_mask = ~best_mask
            
            # Plot best cluster points
            if np.any(best_mask):
                ax.scatter(type_redshifts[best_mask], type_indices[best_mask], type_metric_values[best_mask],
                          c=[color], s=60, alpha=0.9, edgecolors='black', linewidth=1.5,
                          label=f'{type_name} (Best)')
            
            # Plot other points
            if np.any(other_mask):
                ax.scatter(type_redshifts[other_mask], type_indices[other_mask], type_metric_values[other_mask],
                          c=[color], s=40, alpha=0.6, edgecolors='gray', linewidth=0.5)
        else:
            # Plot all points with same style
            ax.scatter(type_redshifts, type_indices, type_metric_values,
                      c=[color], s=50, alpha=0.7, edgecolors='black', linewidth=0.5,
                      label=type_name)
    
    # Set labels and title
    ax.set_xlabel('Redshift (z)', fontsize=PLOT_AXIS_LABEL_FONTSIZE, labelpad=10)
    ax.set_ylabel('Type', fontsize=PLOT_AXIS_LABEL_FONTSIZE, labelpad=10)
    ax.set_zlabel(f'{metric_name}', fontsize=PLOT_AXIS_LABEL_FONTSIZE, labelpad=10)
    ax.set_title(f'3D GMM Clustering: Redshift vs Type vs {metric_name}', fontsize=PLOT_TITLE_FONTSIZE, pad=20)
    
    # Set type labels
    ax.set_yticks(range(len(unique_types)))
    ax.set_yticklabels(unique_types)
    
    # Add legend
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Improve layout
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        _LOGGER.info(f"   💾 Saved 3D clustering plot: {save_path}")
    
    return fig

def plot_type_clustering_comparison(
    current_results: Dict[str, Any],
    improved_results: Dict[str, Any],
    figsize: Tuple[int, int] = (16, 8),
    save_path: Optional[str] = None,
    theme_manager=None
) -> plt.Figure:
    """
    Compare current vs improved clustering approaches side by side.
    """
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    
    # Plot current approach (left)
    _plot_current_approach(ax1, current_results)
    ax1.set_title("Current Approach\n(All Types Together)", fontsize=PLOT_TITLE_FONTSIZE, fontweight='bold')
    
    # Plot improved approach (right)
    _plot_improved_approach(ax2, improved_results)
    ax2.set_title("Improved Approach\n(Type-Specific Clustering)", fontsize=PLOT_TITLE_FONTSIZE, fontweight='bold')
    
    # Overall title
    fig.suptitle("GMM Clustering Approach Comparison", fontsize=PLOT_TITLE_FONTSIZE, fontweight='bold')
    
    # Skip tight_layout for complex plots to avoid layout warnings
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    
    return fig

def _plot_current_approach(ax, current_results):
    """Plot the current clustering approach."""
    # This would visualize the current single-pool approach
    # Implementation depends on the structure of current_results
    
    if not hasattr(current_results, 'best_matches'):
        ax.text(0.5, 0.5, "No current results available", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, transform=ax.transAxes)
        return
    
    matches = current_results.best_matches
    redshifts = [m['redshift'] for m in matches]
    from snid_sage.shared.utils.math_utils import get_best_metric_value
    metric_values = [get_best_metric_value(m) for m in matches]
    types = [m['template'].get('type', 'Unknown') for m in matches]
    
    # Color by type but show single clustering
    unique_types = list(set(types))
    colors = plt.cm.tab10(np.linspace(0, 1, len(unique_types)))
    type_colors = {t: colors[i] for i, t in enumerate(unique_types)}
    
    for i, (z, mv, t) in enumerate(zip(redshifts, metric_values, types)):
        ax.scatter(z, mv, c=[type_colors[t]], s=50, alpha=0.7, label=t if t not in ax.get_legend_handles_labels()[1] else "")
    
    # Determine metric name for Y-axis label
    metric_name = 'HLAP'  # Default fallback
    if matches and matches[0]:
        from snid_sage.shared.utils.math_utils import get_metric_name_for_match
        metric_name = get_metric_name_for_match(matches[0])
    
    ax.set_xlabel('Redshift (z)', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.set_ylabel(metric_name, fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.legend(fontsize=PLOT_LEGEND_FONTSIZE)
    ax.grid(True, alpha=0.3)

def _plot_improved_approach(ax, improved_results):
    """Plot the improved type-specific clustering approach."""
    
    if not improved_results.get('success', False):
        ax.text(0.5, 0.5, "No improved results available", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, transform=ax.transAxes)
        return
    
    best_cluster = improved_results.get('best_cluster')
    all_candidates = improved_results.get('all_candidates', [])
    
    # Plot all clusters with transparency
    for candidate in all_candidates:
        matches = candidate['matches']
        redshifts = [m['redshift'] for m in matches]
        # Use the new metric system instead of direct metric access
        from snid_sage.shared.utils.math_utils import get_best_metric_value, get_metric_name_for_match
        metric_values = [get_best_metric_value(m) for m in matches]
        
        is_best = (candidate == best_cluster)
        alpha = 1.0 if is_best else 0.4
        size = 60 if is_best else 30
        edgecolor = 'black' if is_best else 'gray'
        
        label = f"{candidate['type']} (BEST)" if is_best else candidate['type']
        
        ax.scatter(redshifts, metric_values, alpha=alpha, s=size, 
                  edgecolors=edgecolor, linewidth=1,
                  label=label if label not in ax.get_legend_handles_labels()[1] else "")
    
    # Determine metric name for Y-axis label
    metric_name = 'HLAP'  # Default fallback
    if all_candidates and all_candidates[0].get('matches'):
        metric_name = get_metric_name_for_match(all_candidates[0]['matches'][0])
    
    ax.set_xlabel('Redshift (z)', fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.set_ylabel(metric_name, fontsize=PLOT_AXIS_LABEL_FONTSIZE)
    ax.legend(fontsize=PLOT_LEGEND_FONTSIZE)
    ax.grid(True, alpha=0.3)

def plot_cluster_statistics_summary(
    clustering_results: Dict[str, Any],
    figsize: Tuple[int, int] = (12, 8),
    save_path: Optional[str] = None,
    theme_manager=None
) -> plt.Figure:
    """
    Create a comprehensive summary of clustering statistics.
    
    Shows cluster sizes, match distributions, and quality metrics.
    """
    
    if not clustering_results.get('success'):
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No clustering results to display", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, transform=ax.transAxes)
        ax.axis('off')
        return fig
    
    # Get all cluster candidates
    all_candidates = clustering_results.get('all_candidates', [])
    if not all_candidates:
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No cluster candidates found", 
               ha='center', va='center', fontsize=PLOT_ERROR_FONTSIZE, transform=ax.transAxes)
        ax.axis('off')
        return fig
    
    # Determine which metric is being used
    metric_name = clustering_results.get('metric_used', 'HσLAP-CCC')
    
    # Create subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)
    fig.suptitle(f'Clustering Statistics Summary ({metric_name})', fontsize=PLOT_TITLE_FONTSIZE, fontweight='bold')
    
    # 1. Cluster sizes by type
    type_names = []
    cluster_sizes = []
    total_matches = []
    
    for candidate in all_candidates:
        type_names.append(candidate.get('type', 'Unknown'))
        cluster_sizes.append(candidate.get('size', 0))
        total_matches.append(len(candidate.get('matches', [])))
    
    if type_names:
        bars1 = ax1.bar(type_names, cluster_sizes, alpha=0.7, color='skyblue')
        ax1.set_title('Cluster Sizes by Type')
        ax1.set_ylabel('Cluster Size')
        ax1.tick_params(axis='x', rotation=45)
        
        # Add value labels
        for bar, size in zip(bars1, cluster_sizes):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{size}', ha='center', va='bottom')
    
    # 2. Match distribution by type
    if type_names:
        bars2 = ax2.bar(type_names, total_matches, alpha=0.7, color='lightcoral')
        ax2.set_title('Total Matches by Type')
        ax2.set_ylabel('Number of Matches')
        ax2.tick_params(axis='x', rotation=45)
        
        # Add value labels
        for bar, matches in zip(bars2, total_matches):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{matches}', ha='center', va='bottom')
    
    # 3. Metric distribution across all clusters
    from snid_sage.shared.utils.math_utils import get_best_metric_value
    all_metric_values = []
    all_types = []
    for candidate in all_candidates:
        for match in candidate['matches']:
            all_metric_values.append(get_best_metric_value(match))
            all_types.append(candidate['type'])
    
    if all_metric_values:
        ax3.hist(all_metric_values, bins=20, alpha=0.7, color='lightgreen', edgecolor='black')
        ax3.set_title(f'{metric_name} Distribution (All Clusters)')
        ax3.set_xlabel(f'{metric_name}')
        ax3.set_ylabel('Frequency')
        ax3.axvline(np.mean(all_metric_values), color='red', linestyle='--', 
                   label=f'Mean: {np.mean(all_metric_values):.1f}')
        ax3.legend()
    
    # 4. Quality scores by cluster
    quality_scores = [candidate.get('quality_score', 0) for candidate in all_candidates]
    cluster_labels = [f"{candidate.get('type', 'Unknown')[:3]}-{candidate.get('cluster_id', 0)}" 
                     for candidate in all_candidates]
    
    if quality_scores:
        bars4 = ax4.bar(range(len(quality_scores)), quality_scores, alpha=0.7, color='gold')
        ax4.set_title('Quality Scores by Cluster')
        ax4.set_ylabel('Quality Score')
        ax4.set_xlabel('Cluster')
        ax4.set_xticks(range(len(cluster_labels)))
        ax4.set_xticklabels(cluster_labels, rotation=45, ha='right')
        
        # Add value labels
        for bar, score in zip(bars4, quality_scores):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{score:.1f}', ha='center', va='bottom')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        _LOGGER.info(f"   💾 Saved clustering statistics plot: {save_path}")
    
    return fig

def plot_2d_redshift_vs_metric(
    clustering_results: Dict[str, Any],
    selected_cluster: Optional[Dict[str, Any]] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
    theme_manager=None
) -> plt.Figure:
    """Create a 2D plot of redshift vs best metric with cluster highlighting."""
    
    if not clustering_results.get('success'):
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No clustering results to display", 
               ha='center', va='center', fontsize=14, transform=ax.transAxes)
        ax.axis('off')
        return fig
    
    # Determine which metric is being used
    metric_name = clustering_results.get('metric_used', 'HσLAP-CCC')
    
    fig, ax = plt.subplots(figsize=figsize)
    
    all_candidates = clustering_results.get('all_candidates', [])
    if not all_candidates:
        ax.text(0.5, 0.5, "No cluster candidates found", 
               ha='center', va='center', transform=ax.transAxes)
        return fig
    
    # Extract all matches
    all_matches = []
    for candidate in all_candidates:
        all_matches.extend(candidate.get('matches', []))
    
    if all_matches:
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        redshifts = np.array([m['redshift'] for m in all_matches])
        metric_values = np.array([get_best_metric_value(m) for m in all_matches])
        types = [m.get('template', {}).get('type', 'Unknown') for m in all_matches]
        
        # Color by type
        unique_types = list(set(types))
        colors = plt.cm.Set1(np.linspace(0, 1, len(unique_types)))
        
        for i, type_name in enumerate(unique_types):
            type_mask = np.array([t == type_name for t in types])
            ax.scatter(redshifts[type_mask], metric_values[type_mask], 
                      c=[colors[i]], alpha=0.7, s=20, label=type_name)
    
    ax.set_xlabel('Redshift (z)')
    ax.set_ylabel(f'{metric_name}')
    ax.set_title(f'Redshift vs {metric_name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        _LOGGER.info(f"   💾 Saved 2D plot: {save_path}")
    
    return fig

def plot_simple_scatter(
    clustering_results: Dict[str, Any],
    selected_cluster: Optional[Dict[str, Any]] = None,
    figsize: Tuple[int, int] = (8, 6),
    save_path: Optional[str] = None,
    theme_manager=None
) -> plt.Figure:
    """Create a simple scatter plot for quick visualization."""
    
    if not clustering_results.get('success'):
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No clustering results to display", 
               ha='center', va='center', fontsize=14, transform=ax.transAxes)
        ax.axis('off')
        return fig
    
    # Determine which metric is being used
    metric_name = clustering_results.get('metric_used', 'HσLAP-CCC')
    
    all_candidates = clustering_results.get('all_candidates', [])
    if not all_candidates:
        return plt.figure(figsize=figsize)
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot each cluster
    for candidate in all_candidates:
        matches = candidate.get('matches', [])
        if not matches:
            continue
            
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        redshifts = [m['redshift'] for m in matches]
        metric_values = [get_best_metric_value(m) for m in matches]
        
        cluster_type = candidate.get('type', 'Unknown')
        is_selected = candidate == selected_cluster
        
        alpha = 1.0 if is_selected else 0.6
        size = 50 if is_selected else 30
        
        ax.scatter(redshifts, metric_values, alpha=alpha, s=size,
                  label=f"{cluster_type} (N={len(matches)})")
    
    ax.set_xlabel('Redshift (z)')
    ax.set_ylabel(f'{metric_name}')
    ax.set_title(f'Clustering Results: Redshift vs {metric_name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        _LOGGER.info(f"   💾 Saved simple scatter plot: {save_path}")
    
    return fig 