"""
Enhanced LLM analysis utilities for spectrum analysis with simplified prompts
"""
import textwrap
import json
from typing import Dict, List, Optional, Any, Tuple, Union
import numpy as np

# System prompt for AstroSage (used by OpenRouter summary)
ASTROSAGE_SYSTEM_PROMPT = """You are AstroSage, a world-renowned expert in supernova spectroscopy with decades of experience in stellar evolution, spectral analysis, and observational astronomy. You have published extensively on Type Ia, Type II, and exotic supernovae classifications.

You are analyzing results from SNID-SAGE, a spectral template matching pipeline that performs cross-correlation analysis between observed spectra and template libraries to identify supernova types and estimate redshifts.

Provide a concise, scientifically rigorous summary that includes the key classification results, confidence assessment, and main findings. Focus on the most important information for researchers and observers."""

def build_enhanced_context(snid_results: Union[Dict[str, Any], Any], 
                          mask_regions: Optional[List[Tuple[float, float]]] = None,
                          line_markers: Optional[List] = None,
                          analysis_params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Build comprehensive context for LLM analysis from SNID results.
    
    Args:
        snid_results: SNID analysis results (can be Dict or SNIDResult object)
        mask_regions: Wavelength regions that were masked during preprocessing
        line_markers: Identified spectral line markers
        analysis_params: Analysis parameters used
        
    Returns:
        Dict containing structured context for LLM analysis
    """
    # Initialize context structure
    context = {
        'redshift_analysis': {},
        'spectrum_properties': {},
        'template_matches': {},
        'analysis_quality': {},
        'observational_context': {},
        'preprocessing_info': {},
        'clustering_analysis': {},  # NEW: Enhanced clustering information
        'classification_summary': {}  # NEW: Clear classification summary
    }
    
    # ENHANCED: Handle both dictionary and SNIDResult object inputs
    if hasattr(snid_results, 'consensus_type'):
        # snid_results is a SNIDResult object
        result = snid_results
        # Create a mock dictionary structure for compatibility
        snid_results_dict = {
            'result': result,
            'templates': getattr(result, 'top_matches', []),
            'input_flux': getattr(result, 'input_spectrum', {}).get('flux', None) if hasattr(result, 'input_spectrum') else None
        }
    else:
        # snid_results is a dictionary
        snid_results_dict = snid_results
        result = snid_results.get('result')  # SNIDResult object
    
    if result:
        # Primary classification summary
        context['classification_summary'] = {
            'consensus_type': getattr(result, 'consensus_type', 'Unknown'),
            'best_subtype': getattr(result, 'best_subtype', 'Unknown'),
            'subtype_confidence': getattr(result, 'subtype_confidence', 0.0),
            
        }
        
        # Clustering analysis if available
        if hasattr(result, 'clustering_results') and result.clustering_results:
            clustering_results = result.clustering_results
            
            # Handle clustering_results as either dict or object
            if isinstance(clustering_results, dict):
                success = clustering_results.get('success', False)
                best_cluster = clustering_results.get('best_cluster', {})
                n_types_clustered = clustering_results.get('n_types_clustered', 0)
                total_candidates = clustering_results.get('total_candidates', 0)
            else:
                # Handle as object with attributes
                success = getattr(clustering_results, 'success', False)
                best_cluster = getattr(clustering_results, 'best_cluster', {})
                n_types_clustered = getattr(clustering_results, 'n_types_clustered', 0)
                total_candidates = getattr(clustering_results, 'total_candidates', 0)
            
            if success:
                # Handle best_cluster as either dict or object
                if isinstance(best_cluster, dict):
                    cluster_type = best_cluster.get('type', 'Unknown')
                    cluster_size = best_cluster.get('size', 0)
                    quality_score = best_cluster.get('composite_score', 0)
                    top_5_mean = best_cluster.get('top_5_mean', 0)
                    enhanced_redshift = best_cluster.get('weighted_mean_redshift', 0)
                    redshift_span = best_cluster.get('redshift_span', 0)
                    cluster_matches = best_cluster.get('matches', [])
                    # Extract pipeline-computed quality and confidence assessments
                    quality_assessment = best_cluster.get('quality_assessment', {})
                    confidence_assessment = best_cluster.get('confidence_assessment', {})
                else:
                    # Handle as object with attributes
                    cluster_type = getattr(best_cluster, 'type', 'Unknown')
                    cluster_size = getattr(best_cluster, 'size', 0)
                    quality_score = getattr(best_cluster, 'composite_score', 0)
                    top_5_mean = getattr(best_cluster, 'top_5_mean', 0)
                    enhanced_redshift = getattr(best_cluster, 'weighted_mean_redshift', 0)
                    redshift_span = getattr(best_cluster, 'redshift_span', 0)
                    cluster_matches = getattr(best_cluster, 'matches', [])
                    # Extract pipeline-computed quality and confidence assessments
                    quality_assessment = getattr(best_cluster, 'quality_assessment', {})
                    confidence_assessment = getattr(best_cluster, 'confidence_assessment', {})
                
                # Handle quality_assessment and confidence_assessment as dict or object
                if not isinstance(quality_assessment, dict):
                    quality_assessment = {
                        'quality_category': getattr(quality_assessment, 'quality_category', ''),
                        'quality_description': getattr(quality_assessment, 'quality_description', ''),
                        'penalized_score': getattr(quality_assessment, 'penalized_score', 0.0),
                    } if quality_assessment else {}
                if not isinstance(confidence_assessment, dict):
                    confidence_assessment = {
                        'confidence_level': getattr(confidence_assessment, 'confidence_level', ''),
                        'confidence_pct': getattr(confidence_assessment, 'confidence_pct', None),
                        'confidence_description': getattr(confidence_assessment, 'confidence_description', ''),
                    } if confidence_assessment else {}
                
                context['clustering_analysis'] = {
                    'method': 'top5_hsigma_lap_ccc_gmm',
                    'success': True,
                    'winning_cluster': {
                        'type': cluster_type,
                        'size': cluster_size,
                        'quality_score': quality_score,
                        'top_5_mean': top_5_mean,
                        'enhanced_redshift': enhanced_redshift,
                        'redshift_span': redshift_span,
                        # Use pipeline-computed quality and confidence
                        'quality_category': quality_assessment.get('quality_category', ''),
                        'quality_description': quality_assessment.get('quality_description', ''),
                        'confidence_level': confidence_assessment.get('confidence_level', ''),
                        'confidence_pct': confidence_assessment.get('confidence_pct', None),
                    },
                    'n_types_clustered': n_types_clustered,
                    'total_candidates': total_candidates,
                    'clustering_method': 'Type-specific GMM with Q selection'
                }
                
                # Add subtype composition within cluster
                if cluster_matches:
                    from collections import Counter
                    subtypes = []
                    for match in cluster_matches:
                        # Handle match as either dict or object
                        if isinstance(match, dict):
                            template = match.get('template', {})
                            if isinstance(template, dict):
                                subtype = template.get('subtype', 'Unknown')
                            else:
                                subtype = getattr(template, 'subtype', 'Unknown')
                        else:
                            template = getattr(match, 'template', {})
                            if isinstance(template, dict):
                                subtype = template.get('subtype', 'Unknown')
                            else:
                                subtype = getattr(template, 'subtype', 'Unknown')
                        
                        if not subtype or subtype.strip() == '':
                            subtype = 'Unknown'
                        subtypes.append(subtype)
                    
                    subtype_counts = Counter(subtypes)
                    total = len(cluster_matches)
                    subtype_fractions = {
                        subtype: count / total 
                        for subtype, count in subtype_counts.items()
                    }
                    
                    context['clustering_analysis']['subtype_composition'] = subtype_fractions
        
        # Redshift analysis (prefer cluster-weighted if available)
        if hasattr(result, 'consensus_redshift') and result.consensus_redshift > 0:
            context['redshift_analysis'] = {
                'primary_redshift': result.redshift,
                'primary_error': getattr(result, 'redshift_error', 0),
                'consensus_redshift': result.consensus_redshift,
                'consensus_error': getattr(result, 'consensus_redshift_error', 0),
                'method': 'cluster_weighted' if context.get('clustering_analysis', {}).get('success') else 'template_based'
            }
    
    # Enhanced spectrum properties
    if 'input_flux' in snid_results_dict and snid_results_dict['input_flux'] is not None:
        flux_data = snid_results_dict['input_flux']
        
        # Convert to numpy array if needed
        if isinstance(flux_data, list):
            flux = np.array(flux_data)
        else:
            flux = flux_data
            
        # Ensure we have a 2D array
        if flux.ndim == 1:
            # If 1D, assume it's just flux values and create wavelength array
            wavelengths = np.arange(len(flux))
            flux = np.column_stack([wavelengths, flux])
        elif flux.ndim != 2 or flux.shape[1] != 2:
            # Invalid format, skip spectrum properties
            context['spectrum_properties'] = {
                'error': 'Invalid flux data format',
                'data_shape': str(flux.shape) if hasattr(flux, 'shape') else str(type(flux))
            }
        else:
            # Valid 2D array with wavelength and flux columns
            try:
                context['spectrum_properties'] = {
                    'wavelength_range': {
                        'min': float(flux[:, 0].min()),
                        'max': float(flux[:, 0].max()),
                        'coverage': float(flux[:, 0].max() - flux[:, 0].min())
                    },
                    'flux_statistics': {
                        'mean': float(flux[:, 1].mean()),
                        'std': float(flux[:, 1].std()),
                        'snr_estimate': float(abs(flux[:, 1].mean()) / flux[:, 1].std()) if flux[:, 1].std() > 0 else 0,
                        'data_points': len(flux)
                    },
                    'spectral_quality': _assess_spectral_quality(flux)
                }
            except Exception as e:
                context['spectrum_properties'] = {
                    'error': f'Error processing flux data: {str(e)}',
                    'data_shape': str(flux.shape) if hasattr(flux, 'shape') else str(type(flux))
                }
    
    # Enhanced template match information
    if 'templates' in snid_results_dict:
        templates = snid_results_dict['templates']
        context['template_matches'] = {
            'primary_match': _extract_template_info(templates[0]) if templates else None,
            'alternative_matches': [_extract_template_info(t) for t in templates[1:5]] if len(templates) > 1 else [],
            'match_statistics': _calculate_match_statistics(templates) if templates else {}
        }
    
    # Analysis quality assessment
    context['analysis_quality'] = _assess_analysis_quality(snid_results_dict)
    
    # Wavelength mask information
    if mask_regions:
        context['preprocessing_info']['masked_regions'] = [
            {
                'start': start, 
                'end': end, 
                'width': end - start,
                'likely_reason': _identify_mask_reason(start, end)
            }
            for start, end in mask_regions
        ]
    
    # Identified spectral lines
    if line_markers:
        context['observational_context']['identified_lines'] = []
        for line in line_markers:
            if isinstance(line, dict):
                # Line marker is already a dictionary with information
                context['observational_context']['identified_lines'].append({
                    'wavelength': line.get('wavelength', 0),
                    'identification': line.get('identification', 'Unknown'),
                    'type': line.get('type', 'unknown'),
                    'strength': line.get('strength', 'unknown'),
                    'redshift': line.get('redshift', 0.0)
                })
            elif hasattr(line, 'get_xdata'):
                # Line marker is a matplotlib object
                wavelength = line.get_xdata()[0] if line.get_xdata() else 0
                context['observational_context']['identified_lines'].append({
                    'wavelength': wavelength,
                    'identification': _identify_spectral_line(wavelength),
                    'type': 'matplotlib_marker',
                    'strength': 'unknown',
                    'redshift': 0.0
                })
    
    return context

def _assess_spectral_quality(flux: np.ndarray) -> Dict[str, Any]:
    """Assess the quality of spectral data."""
    quality = {}
    
    # Basic quality metrics
    wavelengths = flux[:, 0]
    fluxes = flux[:, 1]
    
    # Wavelength coverage assessment
    coverage = wavelengths.max() - wavelengths.min()
    if coverage > 4000:  # Good coverage
        quality['wavelength_coverage'] = 'excellent'
    elif coverage > 2000:
        quality['wavelength_coverage'] = 'good'
    else:
        quality['wavelength_coverage'] = 'limited'
    
    # Signal-to-noise estimation
    snr = abs(fluxes.mean()) / fluxes.std() if fluxes.std() > 0 else 0
    if snr > 10:
        quality['signal_to_noise'] = 'High'
    elif snr > 5:
        quality['signal_to_noise'] = 'Moderate'
    else:
        quality['signal_to_noise'] = 'Low'
    
    # Spectral resolution estimate (rough)
    resolution = len(wavelengths) / coverage if coverage > 0 else 0
    quality['resolution_estimate'] = f"{resolution:.1f} points/Å"
    
    return quality

def _extract_template_info(template: Dict) -> Dict[str, Any]:
    """Extract enhanced information from template match."""
    if not template:
        return {}
    
    # Handle template as either dict or object
    if isinstance(template, dict):
        return {
            'name': template.get('name', 'Unknown'),
            'type': template.get('type', 'Unknown'),
            'subtype': template.get('subtype', ''),
            'redshift': template.get('z', 0.0),
            'redshift_error': template.get('zerr', 0.0),
            'age': template.get('age', 0.0),
            'lap_score': template.get('lap', 0.0),
            'metric_score': template.get('hsigma_lap_ccc', template.get('hlap', 0.0)),
            'grade': template.get('grade', '')
        }
    else:
        # Handle as object with attributes
        return {
            'name': getattr(template, 'name', 'Unknown'),
            'type': getattr(template, 'type', 'Unknown'),
            'subtype': getattr(template, 'subtype', ''),
            'redshift': getattr(template, 'z', 0.0),
            'redshift_error': getattr(template, 'zerr', 0.0),
            'age': getattr(template, 'age', 0.0),
            'lap_score': getattr(template, 'lap', 0.0),
            'metric_score': getattr(template, 'hsigma_lap_ccc', getattr(template, 'hlap', 0.0)),
            'grade': getattr(template, 'grade', '')
        }

def _calculate_match_statistics(templates: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics across template matches."""
    if not templates:
        return {}
    
    # Handle templates as either dicts or objects
    metric_values = []
    lap_values = []
    for t in templates:
        if isinstance(t, dict):
            metric_values.append(t.get('hsigma_lap_ccc', t.get('hlap', 0.0)))
            lap_values.append(t.get('lap', 0))
        else:
            metric_values.append(getattr(t, 'hsigma_lap_ccc', getattr(t, 'hlap', 0.0)))
            lap_values.append(getattr(t, 'lap', 0))
    
    return {
        'best_metric': max(metric_values) if metric_values else 0,
        'metric_spread': max(metric_values) - min(metric_values) if len(metric_values) > 1 else 0,
        'consistent_type': _check_type_consistency(templates),
        'redshift_consistency': _check_redshift_consistency(templates)
    }

def _check_type_consistency(templates: List[Dict]) -> bool:
    """Check if top matches agree on supernova type."""
    if len(templates) < 2:
        return True
    
    # Handle first template as either dict or object
    if isinstance(templates[0], dict):
        primary_type = templates[0].get('type', '').split('-')[0]  # Get main type
    else:
        primary_type = getattr(templates[0], 'type', '').split('-')[0]  # Get main type
    
    # Check consistency across top 3 templates
    for t in templates[:3]:
        if isinstance(t, dict):
            template_type = t.get('type', '').split('-')[0]
        else:
            template_type = getattr(t, 'type', '').split('-')[0]
        
        if template_type != primary_type:
            return False
    
    return True

def _check_redshift_consistency(templates: List[Dict]) -> Dict[str, Any]:
    """Check redshift consistency across top matches."""
    if len(templates) < 2:
        return {'consistent': True, 'spread': 0.0}
    
    # Handle templates as either dicts or objects
    redshifts = []
    for t in templates[:5]:
        if isinstance(t, dict):
            redshifts.append(t.get('z', 0))
        else:
            redshifts.append(getattr(t, 'z', 0))
    
    # Use weighted redshift estimate if weights available, otherwise simple mean
    try:
        # Try to get metric values as weights if available in the template data
        weights = []
        for t in templates[:5]:
            if isinstance(t, dict):
                weights.append(t.get('primary_metric', t.get('hlap', 1.0)))  # Default weight of 1.0 if missing
            else:
                weights.append(getattr(t, 'hsigma_lap_ccc', getattr(t, 'hlap', 1.0)))
        
        # If we have meaningful weights (not all 1.0), use weighted calculation
        if any(w != 1.0 for w in weights):
            from snid_sage.shared.utils.math_utils import estimate_weighted_redshift
            # Use dummy unit errors when only weights are given: sigma=1 → weights proportional to metric^2
            z_mean = estimate_weighted_redshift(redshifts, [1.0]*len(weights), weights)
        else:
            # No meaningful weights available, use simple mean
            z_mean = np.mean(redshifts)
    except ImportError:
        # Fallback to simple mean if function not available
        z_mean = np.mean(redshifts)
    
    z_std = np.std(redshifts)
    
    return {
        'consistent': z_std < 0.01,  # Within 1% variation
        'spread': float(z_std),
        'mean': float(z_mean)
    }

def _assess_analysis_quality(snid_results: Dict) -> Dict[str, Any]:
    """
    Assess overall quality of the SNID-SAGE analysis.
    
    Prefers pipeline-computed quality categories from cluster analysis.
    Falls back to basic checks if no cluster data available.
    """
    quality = {
        'template_database_coverage': 'good',  # Assume good coverage
        'correlation_quality': 'unknown',
        'potential_issues': []
    }
    
    # Try to get pipeline-computed quality from cluster analysis
    result = snid_results.get('result') if isinstance(snid_results, dict) else snid_results
    if result and hasattr(result, 'clustering_results') and result.clustering_results:
        clustering_results = result.clustering_results
        if isinstance(clustering_results, dict):
            best_cluster = clustering_results.get('best_cluster', {})
        else:
            best_cluster = getattr(clustering_results, 'best_cluster', {})
        
        if best_cluster:
            # Extract pipeline-computed quality assessment
            if isinstance(best_cluster, dict):
                quality_assessment = best_cluster.get('quality_assessment', {})
            else:
                quality_assessment = getattr(best_cluster, 'quality_assessment', {})
            
            if quality_assessment:
                if not isinstance(quality_assessment, dict):
                    quality_category = getattr(quality_assessment, 'quality_category', '')
                    quality_description = getattr(quality_assessment, 'quality_description', '')
                else:
                    quality_category = quality_assessment.get('quality_category', '')
                    quality_description = quality_assessment.get('quality_description', '')
                
                if quality_category:
                    quality['correlation_quality'] = quality_category
                    quality['quality_description'] = quality_description
                    # Add potential issues based on quality category
                    if quality_category in ['Very Low', 'Low']:
                        quality['potential_issues'].append(f'Low match quality: {quality_description}')
                    return quality
    
    # Fallback: basic checks if no cluster data
    if 'templates' in snid_results and snid_results['templates']:
        best_match = snid_results['templates'][0]
        
        # Handle best_match as either dict or object
        if isinstance(best_match, dict):
            metric = best_match.get('hsigma_lap_ccc', best_match.get('hlap', 0.0))
            zerr = best_match.get('zerr', 1)
        else:
            metric = getattr(best_match, 'hsigma_lap_ccc', getattr(best_match, 'hlap', 0.0))
            zerr = getattr(best_match, 'zerr', 1)
        
        if float(metric) < 0.7:
            quality['potential_issues'].append('Low correlation score - weak match')
        if zerr > 0.1:
            quality['potential_issues'].append('Large redshift uncertainty')
    
    return quality

def _identify_mask_reason(start: float, end: float) -> str:
    """Identify likely reason for wavelength masking."""
    # Common problematic regions
    if 5570 <= start <= 5590 and 5570 <= end <= 5590:
        return 'Sky line region (5577Å)'
    elif 6860 <= start <= 6880 and 6860 <= end <= 6880:
        return 'Telluric absorption (6867Å)'
    elif 7590 <= start <= 7610 and 7590 <= end <= 7610:
        return 'Telluric absorption (7600Å)'
    elif end - start > 500:
        return 'Large gap or detector issue'
    else:
        return 'Custom mask'

def _identify_spectral_line(wavelength: float) -> str:
    """Identify likely spectral line based on wavelength."""
    # Common supernova lines (approximate rest wavelengths)
    line_identifications = {
        (3925, 3935): 'Ca II H',
        (3965, 3975): 'Ca II K', 
        (4100, 4110): 'Hδ',
        (4330, 4350): 'Hγ',
        (4860, 4870): 'Hβ',
        (5015, 5025): 'He I',
        (5170, 5180): 'Mg II',
        (5890, 5900): 'Na I D',
        (6150, 6170): 'Si II',
        (6560, 6570): 'Hα',
        (8540, 8550): 'Ca II IR',
        (8660, 8670): 'Ca II IR'
    }
    
    for (min_wave, max_wave), identification in line_identifications.items():
        if min_wave <= wavelength <= max_wave:
            return identification
    
    return 'Unidentified'





def analyse_spectrum_advanced(snid_results: Union[Dict, Any]) -> Optional[Dict]:
    """Advanced spectrum analysis with detailed quality assessment."""
    if not snid_results:
        return None

    # Handle both dictionary and SNIDResult object inputs
    if hasattr(snid_results, 'consensus_type'):
        # snid_results is a SNIDResult object
        result = snid_results
        # Create a mock dictionary structure for compatibility
        snid_results_dict = {
            'input_flux': getattr(result, 'input_spectrum', {}).get('flux', None) if hasattr(result, 'input_spectrum') else None,
            'input_flat': getattr(result, 'processed_spectrum', {}).get('flux', None) if hasattr(result, 'processed_spectrum') else None,
            'templates': getattr(result, 'top_matches', [])
        }
    else:
        # snid_results is a dictionary
        snid_results_dict = snid_results

    flux_data = snid_results_dict.get('input_flux', None)
    flat_data = snid_results_dict.get('input_flat', None)
    templates = snid_results_dict.get('templates', [])

    if flux_data is None:
        return None

    # Convert to numpy array if needed
    if isinstance(flux_data, list):
        flux = np.array(flux_data)
    else:
        flux = flux_data
        
    # Ensure we have a valid 2D array
    if flux.ndim == 1:
        wavelengths = np.arange(len(flux))
        flux = np.column_stack([wavelengths, flux])
    elif flux.ndim != 2 or flux.shape[1] != 2:
        return None
        
    if flux.size == 0:
        return None

    analysis = {
        'basic_properties': {
        'wavelength_range': {
                'min': float(flux[:, 0].min()),
                'max': float(flux[:, 0].max()),
                'coverage': float(flux[:, 0].max() - flux[:, 0].min())
        },
            'flux_statistics': {
                'mean': float(flux[:, 1].mean()),
                'std': float(flux[:, 1].std()),
                'snr_estimate': float(abs(flux[:, 1].mean()) / flux[:, 1].std()) if flux[:, 1].std() > 0 else 0,
                'dynamic_range': float(flux[:, 1].max() - flux[:, 1].min())
            }
        },
        'quality_assessment': _assess_spectral_quality(flux),
        'template_analysis': {}
    }

    # Enhanced template analysis
    if templates:
        # Try to get cluster confidence level from result if available
        cluster_confidence_level = None
        if hasattr(snid_results, 'clustering_results') and snid_results.clustering_results:
            clustering_results = snid_results.clustering_results
            if isinstance(clustering_results, dict):
                best_cluster = clustering_results.get('best_cluster', {})
            else:
                best_cluster = getattr(clustering_results, 'best_cluster', {})
            
            if best_cluster:
                if isinstance(best_cluster, dict):
                    confidence_assessment = best_cluster.get('confidence_assessment', {})
                else:
                    confidence_assessment = getattr(best_cluster, 'confidence_assessment', {})
                
                if confidence_assessment:
                    if not isinstance(confidence_assessment, dict):
                        cluster_confidence_level = getattr(confidence_assessment, 'confidence_level', None)
                    else:
                        cluster_confidence_level = confidence_assessment.get('confidence_level', None)
        elif isinstance(snid_results, dict) and 'result' in snid_results:
            result = snid_results['result']
            if hasattr(result, 'clustering_results') and result.clustering_results:
                clustering_results = result.clustering_results
                if isinstance(clustering_results, dict):
                    best_cluster = clustering_results.get('best_cluster', {})
                else:
                    best_cluster = getattr(clustering_results, 'best_cluster', {})
                
                if best_cluster:
                    if isinstance(best_cluster, dict):
                        confidence_assessment = best_cluster.get('confidence_assessment', {})
                    else:
                        confidence_assessment = getattr(best_cluster, 'confidence_assessment', {})
                    
                    if confidence_assessment:
                        if not isinstance(confidence_assessment, dict):
                            cluster_confidence_level = getattr(confidence_assessment, 'confidence_level', None)
                        else:
                            cluster_confidence_level = confidence_assessment.get('confidence_level', None)
        
        analysis['template_analysis'] = {
            'best_match': _extract_template_info(templates[0]),
            'consistency_check': _calculate_match_statistics(templates),
            'classification_confidence': _assess_classification_confidence(templates, cluster_confidence_level)
        }

    # Flat spectrum analysis if available
    if flat_data is not None:
        # Convert to numpy array if needed
        if isinstance(flat_data, list):
            flat = np.array(flat_data)
        else:
            flat = flat_data
            
        # Ensure we have a valid 2D array
        if flat.ndim == 1:
            wavelengths = np.arange(len(flat))
            flat = np.column_stack([wavelengths, flat])
        elif flat.ndim == 2 and flat.shape[1] == 2 and flat.size > 0:
            analysis['flat_spectrum'] = {
                'statistics': {
                    'mean': float(flat[:, 1].mean()),
                    'std': float(flat[:, 1].std()),
                },
                'continuum_shape': _analyze_continuum_shape(flat)
        }

    return analysis 

def _assess_classification_confidence(templates: List[Dict], cluster_confidence_level: Optional[str] = None) -> str:
    """
    Assess overall classification confidence based on template matches.
    
    Prefers the pipeline-computed cluster confidence level if available.
    Falls back to heuristic assessment based on template metrics if no cluster data.
    """
    # Use pipeline-computed confidence if available
    if cluster_confidence_level:
        return cluster_confidence_level
    
    if not templates:
        return 'no_data'
    
    best_match = templates[0]
    
    # Handle best_match as either dict or object
    if isinstance(best_match, dict):
        metric = best_match.get('hsigma_lap_ccc', best_match.get('hlap', 0.0))
    else:
        metric = getattr(best_match, 'hsigma_lap_ccc', getattr(best_match, 'hlap', 0.0))
    
    # Check consistency among top matches
    type_consistency = _check_type_consistency(templates)
    redshift_consistency = _check_redshift_consistency(templates)
    
    # Fallback heuristic (not the official quality category - that comes from cluster)
    if float(metric) > 2.5 and type_consistency and redshift_consistency.get('consistent', False):
        return 'High'
    elif float(metric) >= 1.2 and type_consistency:
        return 'Moderate'
    elif float(metric) >= 0.7:
        return 'Low'
    else:
        return 'Very Low'

def _analyze_continuum_shape(flat_spectrum: np.ndarray) -> Dict[str, Any]:
    """Analyze the shape of the continuum from flattened spectrum."""
    wavelengths = flat_spectrum[:, 0]
    fluxes = flat_spectrum[:, 1]
    
    # Simple continuum shape analysis
    blue_region = fluxes[wavelengths < 5000] if np.any(wavelengths < 5000) else np.array([])
    red_region = fluxes[wavelengths > 6000] if np.any(wavelengths > 6000) else np.array([])
    
    shape_info = {
        'blue_red_ratio': float(blue_region.mean() / red_region.mean()) if len(blue_region) > 0 and len(red_region) > 0 and red_region.mean() != 0 else 1.0,
        'overall_slope': 'unknown'
    }
    
    # Determine overall color
    if shape_info['blue_red_ratio'] > 1.2:
        shape_info['overall_slope'] = 'blue'
    elif shape_info['blue_red_ratio'] < 0.8:
        shape_info['overall_slope'] = 'red'
    else:
        shape_info['overall_slope'] = 'neutral'
    
    return shape_info



def build_enhanced_context_with_metadata(snid_results: Union[Dict[str, Any], Any], 
                                        user_metadata: Dict = None,
                                        mask_regions: Optional[List[Tuple[float, float]]] = None,
                                        line_markers: Optional[List] = None,
                                        analysis_params: Optional[Dict] = None) -> Dict[str, Any]:
    """Build comprehensive context with user metadata support."""
    # Start with the existing enhanced context
    context = build_enhanced_context(snid_results, mask_regions, line_markers, analysis_params)
    
    # Add user metadata
    if user_metadata:
        context['user_metadata'] = user_metadata
    
    # Add tool description for better LLM understanding
    context['tool_description'] = {
        'name': 'Python SNID (SuperNova IDentification)',
        'purpose': 'Spectral template matching pipeline for supernova classification',
        'method': 'Cross-correlation analysis between observed spectra and template libraries',
        'outputs': [
            'Supernova type classification',
            'Redshift estimation',
            'Template match confidence scores',
            'Spectral line identification',
            'Quality assessment metrics'
        ],
        'template_library': 'Comprehensive library of supernova spectral templates across types and phases'
    }
    
    return context

 