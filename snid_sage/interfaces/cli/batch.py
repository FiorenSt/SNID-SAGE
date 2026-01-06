"""
SNID Batch Command
=================

Simplified command for batch processing multiple spectra with SNID.
Two modes: Complete analysis or Minimal summary.

OPTIMIZED VERSION: Templates are loaded once and reused for all spectra.
"""

import argparse
import sys
import os
import glob
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime
import json
import time
import numpy as np
import csv
import re
from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
import multiprocessing as mp

from snid_sage.snid.snid import preprocess_spectrum, run_snid_analysis, SNIDResult
from snid_sage.shared.exceptions.core_exceptions import SpectrumProcessingError
from snid_sage.shared.utils.math_utils import (
    estimate_weighted_redshift,
    estimate_weighted_epoch,
    weighted_redshift_error,
    weighted_epoch_error,
    get_best_metric_value
)
from snid_sage.shared.utils.results_formatter import clean_template_name
from snid_sage.shared.utils.logging import set_verbosity as set_global_verbosity
from snid_sage.shared.utils.logging import VerbosityLevel
from snid_sage.shared.utils.cli_parsing import parse_wavelength_mask_args

# ---------------------------------------------------------------------------
# CLI formatting helpers
# ---------------------------------------------------------------------------

def _is_finite_number(x: object) -> bool:
    try:
        return isinstance(x, (int, float)) and np.isfinite(float(x))
    except Exception:
        return False


def _fmt_val_pm(val: object, err: object, *, val_fmt: str, err_fmt: str) -> str:
    """Format value with optional ±error. If error is not finite/positive, omit it."""
    if not _is_finite_number(val):
        return "nan"
    v = float(val)
    s = val_fmt.format(v)
    if _is_finite_number(err) and float(err) > 0:
        s += f"±{err_fmt.format(float(err))}"
    return s


def _format_winning_cli_fields(summary: dict) -> dict:
    """
    Extract the 'winning-subtype in winning cluster' fields for CLI one-liners.

    Returns a dict with:
      - type_display
      - z_text, age_text (already including label prefixes)
      - q_cluster_text (e.g. "Q_cluster=5.5" or "Q_cluster=nan")
      - flags_str (MatchQual/TypeConf/SubtypeConf)
    """
    consensus_type = summary.get('consensus_type', 'Unknown')
    consensus_subtype = summary.get('consensus_subtype', '')
    type_display = f"{consensus_type} {consensus_subtype}".strip()

    # Winning-subtype z/age first; then cluster-weighted; then best-match fields.
    z_val = summary.get('winning_subtype_redshift', None)
    if not _is_finite_number(z_val):
        z_val = summary.get('cluster_redshift_weighted', summary.get('redshift', None))
    z_err = summary.get('winning_subtype_redshift_err', None)
    if not _is_finite_number(z_err):
        z_err = summary.get('cluster_redshift_err_weighted', summary.get('redshift_error', None))

    age_val = summary.get('winning_subtype_age', None)
    if not _is_finite_number(age_val):
        age_val = summary.get('cluster_age_weighted', summary.get('age', None))
    age_err = summary.get('winning_subtype_age_err', None)
    if not _is_finite_number(age_err):
        age_err = summary.get('cluster_age_err_weighted', summary.get('age_err', None))

    # Penalized cluster score for the winning subtype when available; fallback to cluster.
    q_cluster = summary.get('winning_subtype_penalized_score', None)
    if not _is_finite_number(q_cluster):
        q_cluster = summary.get('cluster_penalized_score', None)

    # Human-readable confidence/quality flags
    if summary.get('has_clustering'):
        match_quality = (summary.get('cluster_quality_category', '') or 'N/A')
        type_conf = summary.get('cluster_confidence_level', '') or 'N/A'
    else:
        match_quality = 'N/A'
        type_conf = 'N/A'
    type_conf = str(type_conf).title() if type_conf else 'N/A'

    subtype_conf = summary.get('subtype_confidence_level', None)
    subtype_conf = str(subtype_conf).title() if subtype_conf else 'N/A'
    flags_str = f" MatchQual={match_quality} TypeConf={type_conf} SubtypeConf={subtype_conf}"

    z_txt = _fmt_val_pm(z_val, z_err, val_fmt="{:.6f}", err_fmt="{:.6f}")
    # Make forced-redshift usage obvious in batch one-liners (common source of "wrong z" confusion).
    try:
        if bool(summary.get('redshift_fixed', False)):
            z_txt = f"{z_txt} (forced)"
    except Exception:
        pass
    age_txt = _fmt_val_pm(age_val, age_err, val_fmt="{:.1f}", err_fmt="{:.1f}") if _is_finite_number(age_val) else "nan"

    return {
        "type_display": type_display,
        "z_text": f"z={z_txt}",
        "age_text": (f" age={age_txt}" if _is_finite_number(age_val) else ""),
        "q_cluster_text": f"Q_cluster={float(q_cluster):.1f}" if _is_finite_number(q_cluster) else "Q_cluster=nan",
        "flags_str": flags_str,
    }

# Import and apply centralized font configuration for consistent plotting
try:
    from snid_sage.shared.utils.plotting.font_sizes import apply_font_config
    apply_font_config()
except ImportError:
    # Fallback if font configuration is not available
    pass


class BatchTemplateManager:
    """
    Optimized template manager for batch processing.
    
    Loads templates once and reuses them for all spectrum analyses,
    providing 10-50x speedup for batch processing by avoiding repeated
    template loading and FFT computation.
    """
    
    def __init__(self, templates_dir: Optional[str], verbose: bool = False, profile_id: Optional[str] = None):
        # Initialize logging early so helper methods can use it
        self._log = logging.getLogger('snid_sage.snid.batch.template_manager')

        # Validate and auto-correct templates directory
        self.templates_dir = self._validate_and_fix_templates_dir(templates_dir)
        self.verbose = verbose
        # Remember intended profile for unified storage consistency
        self._profile_id = (profile_id or 'optical')
        self._templates = None
        self._templates_metadata = None
        self._load_time = None
    
    def _validate_and_fix_templates_dir(self, templates_dir: Optional[str]) -> str:
        """
        Validate templates directory and auto-correct if needed.
        
        Args:
            templates_dir: Path to templates directory (None to auto-discover)
            
        Returns:
            Valid templates directory path
            
        Raises:
            FileNotFoundError: If no valid templates directory can be found
        """
        # If no templates directory provided, resolve via centralized manager
        if templates_dir is None:
            try:
                from snid_sage.shared.templates_manager import get_templates_dir

                auto_found_dir = get_templates_dir()
                self._log.info(f"[SUCCESS] Using built-in templates from: {auto_found_dir}")
                return str(auto_found_dir)
            except Exception as exc:
                raise FileNotFoundError(
                    "Could not resolve SNID templates directory automatically. "
                    "Ensure you have network access on first run or set SNID_SAGE_TEMPLATE_DIR."
                ) from exc

        # Check if provided directory exists and is valid
        if os.path.exists(templates_dir):
            return templates_dir
        
        # Provided directory not found – fall back to centralized manager if possible
        try:
            from snid_sage.shared.templates_manager import get_templates_dir

            auto_found_dir = get_templates_dir()
            self._log.warning(
                f"Templates directory '{templates_dir}' not found. "
                f"Falling back to built-in templates at: {auto_found_dir}"
            )
            return str(auto_found_dir)
        except Exception as exc:
            # Fallback failed
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}") from exc
        
    def load_templates_once(
        self,
        *,
        type_filter: Optional[List[str]] = None,
        template_filter: Optional[List[str]] = None,
        exclude_templates: Optional[List[str]] = None
    ) -> bool:
        """
        Load templates once for the entire batch processing session.
        
        Returns
        -------
        bool
            True if templates were loaded successfully, False otherwise
        """
        if self._templates is not None:
            return True  # Already loaded
            
        start_time = time.time()
        
        try:
            # Use unified storage system (for HDF5 templates) - this is already optimized
            try:
                from snid_sage.snid.core.integration import load_templates_unified
                self._templates = load_templates_unified(
                    self.templates_dir,
                    type_filter=type_filter,
                    template_names=template_filter,
                    exclude_templates=exclude_templates,
                    profile_id=self._profile_id
                )
                self._templates_metadata = {}
                self._log.info(f"✅ Loaded {len(self._templates)} templates using UNIFIED STORAGE")
            except ImportError:
                # Fallback to standard loading
                from snid_sage.snid.io import load_templates
                self._templates, self._templates_metadata = load_templates(
                    self.templates_dir,
                    flatten=True,
                    profile_id=self._profile_id,
                )
                self._log.info(f"✅ Loaded {len(self._templates)} templates using STANDARD method")
            
            self._load_time = time.time() - start_time
            
            if not self._templates:
                self._log.error("❌ No templates loaded")
                self._log.error("   Check that templates directory exists and contains HDF5 files and template_index.json")
                self._log.error(f"   Templates directory: {self.templates_dir}")
                return False
                
            self._log.info(f"🚀 Template loading complete in {self._load_time:.2f}s")
            self._log.info(f"📊 Ready for batch processing with {len(self._templates)} templates")
            
            return True
            
        except Exception as e:
            self._log.error(f"❌ Failed to load templates: {e}")
            self._log.error(f"   Templates directory: {self.templates_dir}")
            self._log.error("   Ensure the directory exists and contains valid template files")
            if self.verbose:
                import traceback
                self._log.error(f"   Full traceback: {traceback.format_exc()}")
            return False
    
    def get_filtered_templates(self, 
                             type_filter: Optional[List[str]] = None,
                             template_filter: Optional[List[str]] = None,
                             age_range: Optional[Tuple[float, float]] = None) -> List[Dict[str, Any]]:
        """
        Get filtered templates without reloading from disk.
        
        Parameters
        ----------
        type_filter : list of str, optional
            Only include templates of these types
        template_filter : list of str, optional
            Only include templates with these names
        age_range : tuple of (float, float), optional
            Only include templates within this age range
            
        Returns
        -------
        List[Dict[str, Any]]
            Filtered templates ready for analysis
        """
        if self._templates is None:
            raise RuntimeError("Templates not loaded. Call load_templates_once() first.")
        
        templates = self._templates[:]  # Start with copy of all templates
        original_count = len(templates)
        
        # Apply age filtering
        if age_range is not None:
            age_min, age_max = age_range
            def _age_in_range(tpl: Dict[str, Any]) -> bool:
                a = tpl.get('age', None)
                if a is None:
                    return True
                try:
                    av = float(a)
                except Exception:
                    return True
                return age_min <= av <= age_max
            templates = [t for t in templates if _age_in_range(t)]
            self._log.info(f"🔍 Age filtering: {original_count} -> {len(templates)} templates")
        
        # Apply type filtering
        if type_filter is not None and len(type_filter) > 0:
            templates = [t for t in templates if t.get('type', '') in type_filter]
            self._log.info(f"🔍 Type filtering: {original_count} -> {len(templates)} templates")
        
        # Apply template name filtering
        if template_filter is not None and len(template_filter) > 0:
            pre_filter_count = len(templates)
            templates = [t for t in templates if t.get('name', '') in template_filter]
            self._log.info(f"🔍 Template name filtering: {pre_filter_count} -> {len(templates)} templates")
            
            if len(templates) == 0 and pre_filter_count > 0:
                self._log.warning(f"⚠️ All templates filtered out by name filter: {template_filter}")
        
        return templates
    
    @property
    def is_loaded(self) -> bool:
        """Check if templates are loaded."""
        return self._templates is not None
    
    @property
    def template_count(self) -> int:
        """Get total number of loaded templates."""
        return len(self._templates) if self._templates else 0
    
    @property
    def load_time(self) -> float:
        """Get time taken to load templates."""
        return self._load_time or 0.0


_WORKER_TM: Optional[BatchTemplateManager] = None
_WORKER_ARGS_CACHE: Optional[Dict[str, Any]] = None


def _mp_worker_initializer(templates_dir: str,
                           type_filter: Optional[List[str]],
                           template_filter: Optional[List[str]],
                           exclude_templates: Optional[List[str]],
                           profile_id: Optional[str]) -> None:
    """Per-process initializer: load all templates once for this worker process."""
    global _WORKER_TM, _WORKER_ARGS_CACHE

    effective_profile_id = (profile_id or 'optical')
    try:
        # Avoid BLAS over-subscription inside processes
        os.environ.setdefault('OMP_NUM_THREADS', '1')
        os.environ.setdefault('MKL_NUM_THREADS', '1')
    except Exception:
        pass

    # Suppress verbose logging inside worker processes (keep console clean)
    try:
        logging.disable(logging.INFO)
        logging.getLogger().setLevel(logging.WARNING)
    except Exception:
        pass

    # Build a per-process template manager and pre-load templates (all relevant HDF5 files)
    _WORKER_TM = BatchTemplateManager(templates_dir, verbose=False, profile_id=effective_profile_id)
    _WORKER_TM.load_templates_once(
        type_filter=type_filter,
        template_filter=template_filter,
        exclude_templates=exclude_templates
    )

    _WORKER_ARGS_CACHE = {
        'type_filter': type_filter,
        'template_filter': template_filter,
        'exclude_templates': exclude_templates,
        'templates_dir': templates_dir,
        'profile_id': effective_profile_id,
    }


def _mp_process_one(index: int,
                    spectrum_path: str,
                    forced_redshift: Optional[float],
                    output_dir: str,
                    args_dict: Dict[str, Any]) -> Tuple[int, Tuple[str, bool, str, Dict[str, Any]]]:
    """Process exactly one spectrum in a worker process and return (index, result_tuple)."""
    # Rebuild a minimal argparse-like object for reuse of existing functions
    args = argparse.Namespace(**args_dict)

    # Use per-process template manager created in initializer
    global _WORKER_TM
    if _WORKER_TM is None:
        _WORKER_TM = BatchTemplateManager(args.templates_dir, verbose=False)
        _WORKER_TM.load_templates_once(
            type_filter=getattr(args, 'type_filter', None),
            template_filter=getattr(args, 'template_filter', None),
            exclude_templates=getattr(args, 'exclude_templates', None)
        )

    try:
        name, success, message, summary = process_single_spectrum_optimized(
            spectrum_path,
            _WORKER_TM,
            output_dir,
            args,
            forced_redshift_override=forced_redshift
        )
        return index, (name, success, message, summary)
    except Exception as e:
        name = Path(spectrum_path).stem
        return index, (name, False, str(e), {
            'spectrum': name,
            'file_path': spectrum_path,
            'success': False,
            'error': str(e)
        })


def process_single_spectrum_optimized(
    spectrum_path: str,
    template_manager: BatchTemplateManager,
    output_dir: str,
    args: argparse.Namespace,
    *,
    forced_redshift_override: Optional[float] = None
) -> Tuple[str, bool, str, Dict[str, Any]]:
    """
    Process a single spectrum using pre-loaded templates via first-class API.
    """
    spectrum_name = Path(spectrum_path).stem
    spectrum_output_dir = Path(output_dir) / spectrum_name
    
    # Determine output settings based on mode
    if args.minimal:
        # Minimal mode: basic output files only (no plots or extra data) - flat directory structure
        save_outputs = True
        create_dir = False  # Don't create individual spectrum directories
    elif args.complete:
        # Complete mode: all outputs including plots - organized in subdirectories
        save_outputs = True
        create_dir = True
        spectrum_output_dir.mkdir(parents=True, exist_ok=True)
    else:
        # Default mode: main outputs only - organized in subdirectories
        save_outputs = True
        create_dir = True
        spectrum_output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # STEP 1: Preprocess spectrum with grid validation/auto-clipping
        try:
            # Resolve active profile id: CLI only (ignore config/env)
            active_profile_id = getattr(args, 'profile_id', None) or 'optical'
            # Determine effective emission-clipping redshift for this item
            # Priority: explicit --emclip-z >= 0 → use fixed value for all
            # Else if --emclip flag → use per-entry forced redshift when available; otherwise skip
            # Else → disabled
            try:
                fixed_emclip_z = float(getattr(args, 'emclip_z', -1.0))
            except Exception:
                fixed_emclip_z = -1.0
            effective_emclip_z = fixed_emclip_z if fixed_emclip_z >= 0.0 else -1.0
            if effective_emclip_z < 0.0 and bool(getattr(args, 'emclip', False)):
                z_candidate = forced_redshift_override
                if z_candidate is None:
                    z_candidate = getattr(args, 'forced_redshift', None)
                if isinstance(z_candidate, (int, float)):
                    try:
                        zf = float(z_candidate)
                        if np.isfinite(zf):
                            effective_emclip_z = zf
                    except Exception:
                        effective_emclip_z = -1.0
            # Parse any CLI-provided wavelength masks into numeric ranges
            wavelength_masks = parse_wavelength_mask_args(getattr(args, 'wavelength_masks', None))

            processed_spectrum, _ = preprocess_spectrum(
                spectrum_path=spectrum_path,
                spike_masking=getattr(args, 'spike_masking', True),
                spike_floor_z=getattr(args, 'spike_floor_z', 50.0),
                spike_baseline_window=getattr(args, 'spike_baseline_window', 501),
                spike_baseline_width=getattr(args, 'spike_baseline_width', None),
                spike_rel_edge_ratio=getattr(args, 'spike_rel_edge_ratio', 2.0),
                spike_min_separation=getattr(args, 'spike_min_separation', 2),
                spike_max_removals=getattr(args, 'spike_max_removals', None),
                spike_min_abs_resid=getattr(args, 'spike_min_abs_resid', None),
                savgol_window=getattr(args, 'savgol_window', 0),
                savgol_order=getattr(args, 'savgol_order', 3),
                aband_remove=getattr(args, 'aband_remove', False),
                skyclip=getattr(args, 'skyclip', False),
                emclip_z=effective_emclip_z,
                emwidth=getattr(args, 'emwidth', 40.0),
                wavelength_masks=wavelength_masks,
                apodize_percent=getattr(args, 'apodize_percent', 10.0),
                verbose=False,  # Suppress preprocessing output in batch mode
                clip_to_grid=True,
                profile_id=active_profile_id
            )
        except SpectrumProcessingError as e:
            msg = str(e)
            # Classify error type for clearer reporting
            lower_msg = msg.lower()
            if 'completely outside' in lower_msg or 'outside the optical grid' in lower_msg:
                error_type = 'out_of_grid'
            elif 'insufficient overlap' in lower_msg:
                error_type = 'insufficient_overlap'
            else:
                error_type = 'spectrum_processing_error'
            return spectrum_name, False, msg, {
                'spectrum': spectrum_name,
                'file_path': spectrum_path,
                'success': False,
                'error': msg,
                'error_type': error_type,
                'error_class': 'SpectrumProcessingError'
            }
        
        # STEP 2: Get filtered templates (no reloading!)
        # Build optional age range from CLI (support open-ended by using wide bounds)
        age_min = getattr(args, 'age_min', None)
        age_max = getattr(args, 'age_max', None)
        age_range = None
        if (age_min is not None) or (age_max is not None):
            try:
                age_range = (
                    float(age_min) if age_min is not None else float('-inf'),
                    float(age_max) if age_max is not None else float('inf')
                )
            except Exception:
                age_range = None

        filtered_templates = template_manager.get_filtered_templates(
            type_filter=args.type_filter,
            template_filter=args.template_filter,
            age_range=age_range
        )
        # Apply exclude list defensively (BatchTemplateManager name filter supports includes; exclude is separate)
        exclude_templates = getattr(args, 'exclude_templates', None)
        if exclude_templates:
            try:
                exclude_set = set(exclude_templates)
                filtered_templates = [t for t in filtered_templates if t.get('name', '') not in exclude_set]
            except Exception:
                filtered_templates = [t for t in filtered_templates if t.get('name', '') not in list(exclude_templates)]
        
        if not filtered_templates:
            return spectrum_name, False, "No templates after filtering", {
                'spectrum': spectrum_name,
                'file_path': spectrum_path,
                'success': False,
                'error': 'No templates after filtering'
            }
        
        # STEP 3: Run SNID analysis using first-class API with preloaded templates
        # run_snid_analysis manages template loading internally
        # Determine if a forced redshift is being used for this spectrum
        used_forced_redshift = (
            forced_redshift_override
            if forced_redshift_override is not None
            else args.forced_redshift
        )

        result, _ = run_snid_analysis(
            processed_spectrum=processed_spectrum,
            templates_dir=template_manager.templates_dir,
            zmin=args.zmin,
            zmax=args.zmax,
            age_range=age_range,
            type_filter=getattr(args, 'type_filter', None),
            template_filter=getattr(args, 'template_filter', None),
            exclude_templates=getattr(args, 'exclude_templates', None),
            preloaded_templates=filtered_templates,
            peak_window_size=int(getattr(args, 'peak_window_size', 10)),
            lapmin=getattr(args, 'lapmin', 0.3),
            hsigma_lap_ccc_threshold=getattr(args, 'hsigma_lap_ccc_threshold', 1.5),
            phase1_peak_min_height=getattr(args, "phase1_peak_min_height", 0.3),
            phase1_peak_min_distance=getattr(args, "phase1_peak_min_distance", 3),
            forced_redshift=used_forced_redshift,
            max_output_templates=int(getattr(args, 'max_output_templates', 10)),
            verbose=False,
            show_plots=False,
            save_plots=False,
            use_weighted_gmm=getattr(args, 'weighted_gmm', False),
            profile_id=active_profile_id
        )
        
        # STEP 4: Generate outputs if requested
        if save_outputs and result.success:
            _save_spectrum_outputs(
                result=result,
                spectrum_path=spectrum_path,
                output_dir=spectrum_output_dir if create_dir else output_dir,
                args=args
            )

        # Default behavior: for default mode (not minimal/complete) also generate plots unless disabled
        if (not args.minimal) and (not args.complete) and result.success and (not getattr(args, 'no_plots', False)):
            try:
                from snid_sage.snid.plotting import (
                    plot_redshift_age, plot_flux_comparison, plot_flat_comparison
                )
                from snid_sage.shared.utils.math_utils import get_best_metric_value
                import matplotlib.pyplot as plt
                sdir = spectrum_output_dir if create_dir else Path(output_dir)
                spectrum_name = Path(spectrum_path).stem
                # Redshift vs Age (already cluster-aware inside the function)
                redshift_age_file = sdir / f"{spectrum_name}_redshift_age.png"
                try:
                    fig = plot_redshift_age(result)
                    # Only save if plot contains data (non-empty axes)
                    if fig and fig.axes and fig.axes[0].has_data():
                        fig.savefig(str(redshift_age_file), dpi=150, bbox_inches='tight')
                    plt.close(fig)
                except Exception as pe:
                    logging.getLogger('snid_sage.snid.batch').warning(f"Redshift-age plot failed: {pe}")

                # Choose the same match the GUI would show: winning cluster → filtered → best
                plot_matches = []
                winning_cluster = None
                if (hasattr(result, 'clustering_results') and result.clustering_results and
                    result.clustering_results.get('success')):
                    cr = result.clustering_results
                    if cr.get('user_selected_cluster'):
                        winning_cluster = cr['user_selected_cluster']
                    elif cr.get('best_cluster'):
                        winning_cluster = cr['best_cluster']
                if winning_cluster and winning_cluster.get('matches'):
                    plot_matches = winning_cluster['matches']
                elif hasattr(result, 'filtered_matches') and result.filtered_matches:
                    plot_matches = result.filtered_matches
                elif hasattr(result, 'best_matches') and result.best_matches:
                    plot_matches = result.best_matches

                if plot_matches:
                    plot_matches = sorted(plot_matches, key=get_best_metric_value, reverse=True)
                    top_match = plot_matches[0]
                    # Flux overlay
                    flux_file = sdir / f"{spectrum_name}_flux_spectrum.png"
                    try:
                        fig = plot_flux_comparison(top_match, result)
                        if fig and fig.axes and fig.axes[0].has_data():
                            fig.savefig(str(flux_file), dpi=150, bbox_inches='tight')
                        plt.close(fig)
                    except Exception as fe:
                        logging.getLogger('snid_sage.snid.batch').warning(f"Flux spectrum plot failed: {fe}")
                    # Flat overlay
                    flat_file = sdir / f"{spectrum_name}_flattened_spectrum.png"
                    try:
                        fig = plot_flat_comparison(top_match, result)
                        if fig and fig.axes and fig.axes[0].has_data():
                            fig.savefig(str(flat_file), dpi=150, bbox_inches='tight')
                        plt.close(fig)
                    except Exception as fe2:
                        logging.getLogger('snid_sage.snid.batch').warning(f"Flattened spectrum plot failed: {fe2}")
            except Exception as e:
                logging.getLogger('snid_sage.snid.batch').debug(f"Default plot generation failed: {e}")
        
        if result.success:
            # Create GUI-style summary with cluster-aware analysis
            summary = _create_cluster_aware_summary(result, spectrum_name, spectrum_path)
            # Record whether a fixed redshift was used and its value
            try:
                summary['redshift_fixed'] = used_forced_redshift is not None
                summary['redshift_fixed_value'] = (
                    float(used_forced_redshift) if used_forced_redshift is not None else None
                )
            except Exception:
                summary['redshift_fixed'] = False
                summary['redshift_fixed_value'] = None
            # Quality is evaluated uniformly

            return spectrum_name, True, "Success", summary
        else:
            return spectrum_name, False, "No good matches found", {
                'spectrum': spectrum_name,
                'file_path': spectrum_path,
                'success': False,
                # Even on failure, record whether a fixed redshift was attempted
                'redshift_fixed': used_forced_redshift is not None,
                'redshift_fixed_value': (
                    float(used_forced_redshift) if used_forced_redshift is not None else None
                )
            }
            
    except Exception as e:
        return spectrum_name, False, str(e), {
            'spectrum': spectrum_name,
            'file_path': spectrum_path,
            'success': False,
            'error': str(e),
            # Even on error, record whether a fixed redshift was attempted
            'redshift_fixed': used_forced_redshift is not None if 'used_forced_redshift' in locals() else False,
            'redshift_fixed_value': (
                float(used_forced_redshift) if ('used_forced_redshift' in locals() and used_forced_redshift is not None) else None
            )
        }
 


def _create_cluster_aware_summary(result: SNIDResult, spectrum_name: str, spectrum_path: str) -> Dict[str, Any]:
    """
    Create GUI-style cluster-aware summary with winning cluster analysis.
    
    This matches the GUI's approach of using the winning cluster for all analysis
    rather than mixing all matches above threshold.
    """
    # Get the winning cluster (user selected or automatic best)
    winning_cluster = None
    cluster_matches = []
    
    if (hasattr(result, 'clustering_results') and 
        result.clustering_results and 
        result.clustering_results.get('success')):
        
        clustering_results = result.clustering_results
        
        # Priority: user_selected_cluster > best_cluster  
        if 'user_selected_cluster' in clustering_results:
            winning_cluster = clustering_results['user_selected_cluster']
        elif 'best_cluster' in clustering_results:
            winning_cluster = clustering_results['best_cluster']
        
        if winning_cluster:
            cluster_matches = winning_cluster.get('matches', [])
            # Sort cluster matches by best available metric (HσLAP-CCC preferred) descending
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            cluster_matches = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
    
    # If no clustering or cluster, fall back to filtered_matches, then best_matches
    if not cluster_matches:
        if hasattr(result, 'filtered_matches') and result.filtered_matches:
            cluster_matches = result.filtered_matches
            # Sort by best available metric (HσLAP-CCC preferred) descending
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            cluster_matches = sorted(cluster_matches, key=get_best_metric_value, reverse=True)
        elif hasattr(result, 'best_matches') and result.best_matches:
            cluster_matches = result.best_matches
            # Sort by best available metric (HσLAP-CCC preferred) descending
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
        'hsigma_lap_ccc': getattr(result, 'hsigma_lap_ccc', 0.0),


        'runtime': result.runtime_sec,
        'has_clustering': winning_cluster is not None,
        'cluster_size': len(cluster_matches) if cluster_matches else 0,
    }
    
    # If we have any matches (from cluster or fallback), override the "best_*" fields
    # to reflect the true top match according to the best metric (HσLAP-CCC),
    # and also expose the best metric on the summary for downstream reporting.
    if cluster_matches:
        top_match = cluster_matches[0]
        top_tpl = top_match.get('template', {}) if isinstance(top_match.get('template'), dict) else {}
        summary['best_template'] = top_tpl.get('name', top_match.get('name', summary['best_template']))
        summary['best_template_type'] = top_tpl.get('type', summary['best_template_type'])
        summary['best_template_subtype'] = top_tpl.get('subtype', summary['best_template_subtype'])
        # Use the top match's redshift/error for "Best Match Redshift"
        summary['redshift'] = top_match.get('redshift', summary['redshift'])
        summary['redshift_error'] = top_match.get('sigma_z', summary['redshift_error'])
        # Expose HσLAP-CCC (may be NaN when sigma_z is unavailable)
        summary['hsigma_lap_ccc'] = top_match.get('hsigma_lap_ccc', float('nan'))
        # Propagate age for top match if available (used as fallback when no cluster age)
        if isinstance(top_tpl, dict):
            summary['age'] = top_tpl.get('age', summary.get('age', None))

        # If clustering failed and there are one or two surviving matches, use the top match
        # subtype for the consensus_subtype shown in batch one-line summaries
        try:
            if (not summary.get('has_clustering')) and (1 <= len(cluster_matches) <= 2):
                top_subtype = top_tpl.get('subtype', '') if isinstance(top_tpl, dict) else ''
                if top_subtype and top_subtype.strip() != '':
                    summary['consensus_subtype'] = top_subtype
        except Exception:
            pass

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
            summary['cluster_confidence_pct'] = ca.get('confidence_pct')
            summary['cluster_confidence_level'] = ca.get('confidence_level', 'N/A')
            summary['cluster_confidence_description'] = ca.get('confidence_description', '')
            summary['cluster_second_best_type'] = ca.get('second_best_type', 'N/A')
        
        # Expose subtype confidence and runner-up within the winning cluster
        try:
            subtype_info = winning_cluster.get('subtype_info', {}) if isinstance(winning_cluster, dict) else {}
            if subtype_info:
                summary['subtype_confidence'] = subtype_info.get('subtype_confidence', summary.get('subtype_confidence'))
                summary['subtype_margin_over_second'] = subtype_info.get('subtype_margin_over_second', summary.get('subtype_margin_over_second'))
                summary['winning_second_best_subtype'] = subtype_info.get('second_best_subtype')
        except Exception:
            # Fallback to result object attributes if available
            summary['subtype_confidence'] = getattr(result, 'subtype_confidence', summary.get('subtype_confidence', None))
            try:
                summary['subtype_margin_over_second'] = getattr(result, 'subtype_margin_over_second', summary.get('subtype_margin_over_second', None))
            except Exception:
                pass
        
        # Determine the second-best competitor TYPE (kept for reporting); do not override
        # the within-cluster runner-up subtype field
        try:
            if (hasattr(result, 'clustering_results') and result.clustering_results):
                clres = result.clustering_results
                all_candidates = clres.get('all_candidates', []) or []
                if isinstance(all_candidates, list) and len(all_candidates) > 1:
                    # Sort candidates by their own penalized score (annotated on each cluster)
                    def _pen_score(c):
                        try:
                            return float(c.get('penalized_score', c.get('composite_score', 0.0)))
                        except Exception:
                            return 0.0
                    sorted_candidates = sorted(all_candidates, key=_pen_score, reverse=True)
                    winning_type = winning_cluster.get('type', '')
                    competitor = None
                    for c in sorted_candidates:
                        if c.get('type', '') != winning_type:
                            competitor = c
                            break
                    # Expose competitor (second-best TYPE) subtype estimates for CSV export
                    if competitor:
                        try:
                            # Name of the competitor subtype
                            summary['second_best_type_subtype'] = (
                                competitor.get('subtype_info', {}).get('best_subtype')
                            )
                            # These keys are present on each cluster candidate
                            summary['second_best_type_subtype_z'] = competitor.get('subtype_redshift')
                            summary['second_best_type_subtype_z_err'] = competitor.get('subtype_redshift_err')
                            summary['second_best_type_subtype_age'] = competitor.get('subtype_age')
                            summary['second_best_type_subtype_age_err'] = competitor.get('subtype_age_err')
                        except Exception:
                            # Leave unset on failure; exporter will emit 'nan'
                            pass

        except Exception:
            pass
        
        # Calculate enhanced cluster statistics using hybrid methods
        if cluster_matches:
            # Collect redshift data with uncertainties for balanced estimation
            redshifts_with_errors = []
            redshift_errors = []
            metric_values = []
            
            # Collect age data for separate age estimation
            ages_for_estimation = []
            age_metric_values = []
            
            for m in cluster_matches:
                template = m.get('template', {})
                
                # Always collect redshift data (uncertainties are always available)
                z = m.get('redshift')
                z_err = m.get('sigma_z', float('nan'))
                metric_val = get_best_metric_value(m)
                
                if z is not None and np.isfinite(z) and z_err > 0:
                    redshifts_with_errors.append(z)
                    redshift_errors.append(z_err)
                    metric_values.append(metric_val)
                
                # Separately collect age data (no uncertainties available)
                age = template.get('age', 0.0) if template else 0.0
                if age is not None and np.isfinite(age):
                    ages_for_estimation.append(age)
                    age_metric_values.append(metric_val)
            
            # Weighted redshift mean and error using canonical weights (unbiased weighted SD)
            if redshifts_with_errors:
                z_final = estimate_weighted_redshift(redshifts_with_errors, redshift_errors, metric_values)
                z_err = weighted_redshift_error(redshifts_with_errors, redshift_errors, metric_values)
                summary['cluster_redshift_weighted'] = z_final
                summary['cluster_redshift_err_weighted'] = z_err
            else:
                summary['cluster_redshift_weighted'] = np.nan
                summary['cluster_redshift_err_weighted'] = np.nan

            # Weighted epoch mean and error using the same canonical weights
            if ages_for_estimation and redshift_errors:
                age_final = estimate_weighted_epoch(ages_for_estimation, redshift_errors, age_metric_values)
                age_err = weighted_epoch_error(ages_for_estimation, redshift_errors, age_metric_values)
                summary['cluster_age_weighted'] = age_final
                summary['cluster_age_err_weighted'] = age_err
            else:
                summary['cluster_age_weighted'] = np.nan
                summary['cluster_age_err_weighted'] = np.nan
            
            summary['cluster_mean_metric'] = float(np.mean(metric_values)) if metric_values is not None and len(metric_values) else 0.0

            # Compute winning subtype aggregates and penalized score within the winning type
            try:
                # Determine winning subtype (prefer consensus_subtype; fallback to top match subtype)
                winning_subtype = summary.get('consensus_subtype') or ''
                if (not winning_subtype) and cluster_matches:
                    top_tpl_local = cluster_matches[0].get('template', {}) if isinstance(cluster_matches[0].get('template'), dict) else {}
                    winning_subtype = top_tpl_local.get('subtype', '')

                # Filter matches to winning type and winning subtype
                winning_type = summary.get('consensus_type', '')
                subtype_matches = []
                # Also collect matches per subtype within the winning type to compute runner-up confidence
                by_subtype: Dict[str, Dict[str, List[float]]] = {}
                for m in cluster_matches:
                    tpl = m.get('template', {}) if isinstance(m.get('template'), dict) else {}
                    if tpl.get('type') == winning_type:
                        st = tpl.get('subtype', '') or ''
                        # Group for confidence computation
                        if st not in by_subtype:
                            by_subtype[st] = {'metrics': [], 'z_errs': []}
                        # Best available metric (HσLAP-CCC preferred)
                        try:
                            from snid_sage.shared.utils.math_utils import get_best_metric_value
                            metric_val_all = float(get_best_metric_value(m))
                        except Exception:
                            metric_val_all = float(m.get('hlap', 0.0) or 0.0)
                        zerr_all = m.get('sigma_z', None)
                        by_subtype[st]['metrics'].append(metric_val_all)
                        by_subtype[st]['z_errs'].append(float(zerr_all) if (zerr_all is not None) else float('nan'))
                        # Keep the list of matches only for the winning subtype aggregates
                        if st == winning_subtype:
                            subtype_matches.append(m)

                # Build arrays
                z_vals = []
                z_errs = []
                metrics = []
                age_vals = []
                for m in subtype_matches:
                    tpl = m.get('template', {}) if isinstance(m.get('template'), dict) else {}
                    z = m.get('redshift')
                    zerr = m.get('sigma_z', None)
                    # Best available metric (HσLAP-CCC preferred)
                    try:
                        from snid_sage.shared.utils.math_utils import get_best_metric_value
                        metric_val = float(get_best_metric_value(m))
                    except Exception:
                        metric_val = float(m.get('hlap', 0.0) or 0.0)
                    if z is not None and np.isfinite(z):
                        z_vals.append(float(z))
                        z_errs.append(float(zerr) if (zerr is not None) else float('nan'))
                        metrics.append(metric_val)
                    age = tpl.get('age', None)
                    if age is not None and np.isfinite(age):
                        age_vals.append(float(age))

                # Weighted redshift mean and error for winning subtype
                if z_vals:
                    z_mean = estimate_weighted_redshift(z_vals, z_errs, metrics)
                    z_err = weighted_redshift_error(z_vals, z_errs, metrics)
                    summary['winning_subtype_redshift'] = z_mean
                    summary['winning_subtype_redshift_err'] = z_err
                # Weighted age mean and error for winning subtype (use same weights scheme)
                if age_vals and z_vals:
                    age_mean = estimate_weighted_epoch(age_vals, z_errs, metrics)
                    age_err = weighted_epoch_error(age_vals, z_errs, metrics)
                    summary['winning_subtype_age'] = age_mean
                    summary['winning_subtype_age_err'] = age_err

                # Penalized score for winning subtype:
                # Q = mean(top-5 best metric values) × (N_top/5).
                if metrics:
                    import numpy as _np
                    mets_arr = _np.array(metrics, dtype=float)
                    sigmas_arr = _np.array([e if (e is not None and _np.isfinite(e) and e > 0) else _np.nan for e in z_errs], dtype=float)
                    if mets_arr.size:
                        top_idx = _np.argsort(-mets_arr)[:5]
                        top_metrics = mets_arr[top_idx]
                        top_sigmas = sigmas_arr[top_idx]
                        finite_top = _np.isfinite(top_metrics)
                        mean_top = float(_np.mean(top_metrics[finite_top])) if _np.any(finite_top) else 0.0
                        penalty_factor = min(top_metrics.size / 5.0, 1.0)
                        summary['winning_subtype_penalized_score'] = float(mean_top * penalty_factor)

                # Compute penalized scores for all subtypes within the winning type to derive qualitative confidence
                try:
                    import numpy as _np
                    subtype_scores: Dict[str, float] = {}
                    for st, agg in by_subtype.items():
                        mets = _np.asarray(agg['metrics'], dtype=float)
                        sigs = _np.asarray([e if (_np.isfinite(e) and e > 0) else _np.nan for e in agg['z_errs']], dtype=float)
                        if mets.size == 0:
                            subtype_scores[st] = 0.0
                            continue
                        top_idx = _np.argsort(-mets)[:5]
                        top_m = mets[top_idx]
                        top_s = sigs[top_idx]
                        finite_top = _np.isfinite(top_m)
                        mean_top = float(_np.mean(top_m[finite_top])) if _np.any(finite_top) else 0.0
                        penalty = min(top_m.size / 5.0, 1.0)
                        subtype_scores[st] = float(mean_top * penalty)
                    # Winner and runner-up within same type
                    winner_score = float(subtype_scores.get(winning_subtype, 0.0))
                    runner_st = None
                    runner_score = 0.0
                    for st, sc in sorted(subtype_scores.items(), key=lambda kv: kv[1], reverse=True):
                        if st != winning_subtype:
                            runner_st = st
                            runner_score = float(sc)
                            break
                    if runner_st is not None:
                        # Percent improvement relative to competitor score (runner as denominator)
                        denom = runner_score if runner_score > 0 else 1e-8
                        pct = 100.0 * (winner_score - runner_score) / denom
                        if pct >= 75.0:
                            level = 'High'
                        elif pct >= 25.0:
                            level = 'Medium'
                        elif pct >= 5.0:
                            level = 'Low'
                        else:
                            level = 'Very Low'
                        summary['subtype_confidence_level'] = level
                        if not summary.get('winning_second_best_subtype'):
                            summary['winning_second_best_subtype'] = runner_st
                    else:
                        summary['subtype_confidence_level'] = 'No Comp'
                except Exception:
                    # Leave unset on failure
                    pass
            except Exception:
                pass
            
            # If this is a forced-redshift run, clear reported redshift uncertainties to NaN
            try:
                if any(bool(m.get('forced_redshift', False)) for m in (cluster_matches or [])):
                    if 'cluster_redshift_err_weighted' in summary:
                        summary['cluster_redshift_err_weighted'] = np.nan
                    if 'winning_subtype_redshift_err' in summary:
                        summary['winning_subtype_redshift_err'] = np.nan
            except Exception:
                pass
            
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
    
    # Fallback approach only if no clustering available
    else:
        summary['cluster_method'] = 'No clustering'
        # Compute a type-level match quality from Q
        try:
            from snid_sage.shared.utils.math_utils import get_best_metric_value
            active = []
            # Use filtered_matches if available; else best_matches
            if hasattr(result, 'filtered_matches') and result.filtered_matches:
                active = result.filtered_matches
            elif hasattr(result, 'best_matches') and result.best_matches:
                active = result.best_matches
            if active:
                pairs = []
                for m in active:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    metric = float(get_best_metric_value(m))
                    sigma = m.get('sigma_z', m.get('z_err', None))
                    sigma = float(sigma) if sigma is not None else float('nan')
                    pairs.append((metric, sigma))
                pairs.sort(key=lambda x: x[0], reverse=True)
                top = pairs[:5]
                import numpy as _np
                mets = _np.asarray([p[0] for p in top], dtype=float)
                sigs = _np.asarray([p[1] for p in top], dtype=float)
                finite_mets = _np.isfinite(mets)
                mean_top = float(_np.mean(mets[finite_mets])) if _np.any(finite_mets) else 0.0
                penalty = min(mets.size / 5.0, 1.0) if mets.size else 0.0
                penalized = mean_top * penalty
                summary['cluster_penalized_score'] = penalized
                if penalized >= 8.0:
                    summary['cluster_quality_category'] = 'High'
                    summary['cluster_quality_description'] = f'Excellent match quality (HσLAP-CCC: {penalized:.2f})'
                elif penalized >= 5.0:
                    summary['cluster_quality_category'] = 'Medium'
                    summary['cluster_quality_description'] = f'Good match quality (HσLAP-CCC: {penalized:.2f})'
                elif penalized >= 2.5:
                    summary['cluster_quality_category'] = 'Low'
                    summary['cluster_quality_description'] = f'Poor match quality (HσLAP-CCC: {penalized:.2f})'
                else:
                    summary['cluster_quality_category'] = 'Very Low'
                    summary['cluster_quality_description'] = f'Very poor match quality (HσLAP-CCC: {penalized:.2f})'
        except Exception:
            pass
        
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


def _save_spectrum_outputs(
    result: SNIDResult,
    spectrum_path: str,
    output_dir: Path,
    args: argparse.Namespace
) -> None:
    """
    Save spectrum outputs based on the analysis mode using GUI-style cluster-aware approach.
    """
    # Ensure output_dir supports Path-style '/' operations even if a string was passed
    output_dir = Path(output_dir)
    try:
        # Extract spectrum name from path
        spectrum_name = Path(spectrum_path).stem
        
        if args.minimal:
            # Minimal mode: save main result file only
            from snid_sage.snid.io import write_result
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
                
                # CRITICAL: Sort all plot matches by best available metric (HσLAP-CCC preferred) descending
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
                        logging.getLogger('snid_sage.snid.batch').debug(f"3D GMM clustering plot failed: {e}")
                
                # 2. Redshift vs Age plot (cluster-aware)
                try:
                    import matplotlib.pyplot as plt
                    redshift_age_file = output_dir / f"{spectrum_name}_redshift_age.png"
                    fig = plot_redshift_age(result, save_path=str(redshift_age_file))
                    plt.close(fig)  # Prevent memory leak
                except Exception as e:
                    logging.getLogger('snid_sage.snid.batch').debug(f"Redshift-age plot failed: {e}")
                
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
                    logging.getLogger('snid_sage.snid.batch').debug(f"Cluster subtype plot failed: {e}")
                
                # 5. Flux spectrum plot (best match) - same as GUI
                if plot_matches:
                    try:
                        import matplotlib.pyplot as plt
                        flux_file = output_dir / f"{spectrum_name}_flux_spectrum.png"
                        fig = plot_flux_comparison(plot_matches[0], result, save_path=str(flux_file))
                        plt.close(fig)  # Prevent memory leak
                    except Exception as e:
                        logging.getLogger('snid_sage.snid.batch').debug(f"Flux spectrum plot failed: {e}")
                    
                    # 6. Flattened spectrum plot (best match) - same as GUI
                    try:
                        import matplotlib.pyplot as plt
                        flat_file = output_dir / f"{spectrum_name}_flattened_spectrum.png"
                        fig = plot_flat_comparison(plot_matches[0], result, save_path=str(flat_file))
                        plt.close(fig)  # Prevent memory leak
                    except Exception as e:
                        logging.getLogger('snid_sage.snid.batch').debug(f"Flattened spectrum plot failed: {e}")
                
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
                            logging.getLogger('snid_sage.snid.batch').warning(f"Failed to save template {i} data: {e}")
                
        elif not args.minimal:
            # Default mode: save main outputs only
            from snid_sage.snid.io import write_result
            output_file = output_dir / f"{spectrum_name}.output"
            write_result(result, str(output_file))
            
    except Exception as e:
        logging.getLogger('snid_sage.snid.batch').warning(f"Failed to save outputs: {e}")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the batch command."""
    # Set epilog with examples
    parser.epilog = """
Examples:
  # Auto-discover templates - minimal mode (only summary report)
  sage batch "spectra/*" --output-dir results/ --minimal
  
  # Auto-discover templates - complete mode (all outputs + 3D plots)
  sage batch "spectra/*" --output-dir results/ --complete
  
  # Auto-discover templates - default mode (main outputs + summary)
  sage batch "spectra/*" --output-dir results/
  
  # Explicit templates directory
  sage batch "spectra/*" templates/ --output-dir results/
  
  # Custom redshift range with auto-discovery
  sage batch "*.dat" --zmin 0.0 --zmax 0.5 --output-dir results/
  
  # With forced redshift and explicit templates
  sage batch "*.dat" templates/ --forced-redshift 0.1 --output-dir results/

  # NEW: List mode using CSV with per-row redshift (forced when provided)
  sage batch --list-csv "data/spectra_list.csv" --output-dir results/
  # If your CSV uses different column names
  sage batch --list-csv input.csv --path-column file --redshift-column z --output-dir results/
    """
    
    # Input source options
    parser.add_argument(
        "input_pattern",
        nargs="?",
        help="Glob pattern for input spectrum files (e.g., 'spectra/*'). Omit when using --list-csv."
    )
    parser.add_argument(
        "--list-csv",
        dest="list_csv",
        help="CSV file listing spectra to analyze. Must contain a path column; optional redshift column to force per-spectrum redshift."
    )
    parser.add_argument(
        "--path-column",
        dest="path_column",
        default="path",
        help="Column name in --list-csv containing spectrum paths (default: path)"
    )
    parser.add_argument(
        "--redshift-column",
        dest="redshift_column",
        default="redshift",
        help="Column name in --list-csv containing forced redshift values (default: redshift)"
    )
    parser.add_argument(
        "templates_dir", 
        nargs="?",  # Make optional
        help="Path to directory containing template spectra (optional - auto-discovers if not provided)"
    )
    parser.add_argument(
        "--output-dir", "-o", 
        help="Directory for output files (defaults to ./results or configured paths.output_dir)"
    )
    
    # Processing modes (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--minimal", 
        action="store_true",
        help="Minimal mode: Main result files + comprehensive summary report (no plots/extras)"
    )
    mode_group.add_argument(
        "--complete", 
        action="store_true",
        help="Complete mode: Save all outputs including 3D plots for each spectrum"
    )
    
    # Analysis parameters
    analysis_group = parser.add_argument_group("Analysis Parameters")
    analysis_group.add_argument(
        "--zmin",
        type=float,
        default=-0.01,
        help="Minimum redshift to consider"
    )
    # zmax default is resolved after parsing so it can depend on the selected profile.
    # When omitted, we use 2.5 for ONIR and 1.0 for optical (or other profiles).
    analysis_group.add_argument(
        "--zmax",
        type=float,
        default=None,
        help="Maximum redshift to consider (default: 1.0 for optical, 2.5 for ONIR)"
    )
    analysis_group.add_argument(
        "--lapmin",
        type=float,
        default=0.3,
        help="Minimum overlap fraction required"
    )
    analysis_group.add_argument(
        "--hsigma-lap-ccc-threshold",
        dest="hsigma_lap_ccc_threshold",
        type=float,
        default=1.5,
        help="Minimum HσLAP-CCC value required for clustering (HσLAP-CCC: (height × lap × CCC) / sqrt(sigma_z))"
    )
    analysis_group.add_argument(
        "--phase1-peak-min-height",
        dest="phase1_peak_min_height",
        type=float,
        default=0.3,
        help="Phase-1 peak finding: minimum normalized correlation peak height (default: 0.3)"
    )
    analysis_group.add_argument(
        "--phase1-peak-min-distance",
        dest="phase1_peak_min_distance",
        type=int,
        default=3,
        help="Phase-1 peak finding: minimum distance between peaks in bins (default: 3)"
    )
    analysis_group.add_argument(
        "--peak-window-size",
        dest="peak_window_size",
        type=int,
        default=10,
        help="Peak detection window size (phase-2 peak refinement search radius; default: 10)"
    )
    analysis_group.add_argument(
        "--max-output-templates",
        dest="max_output_templates",
        type=int,
        default=10,
        help="Maximum number of templates to expose in outputs (default: 10)"
    )
    analysis_group.add_argument(
        "--forced-redshift", 
        type=float, 
        help="Force analysis to this specific redshift for all spectra"
    )
    # Forced-redshift FWHM fallback handling:
    # Always reject fallback-width peaks (they are not reliable matches).
    analysis_group.add_argument(
        "--profile",
        dest="profile_id",
        choices=["optical", "onir"],
        default=None,
        help="Analysis profile to use (optical or onir). Defaults to config or optical."
    )
    analysis_group.add_argument(
        "--weighted-gmm",
        dest="weighted_gmm",
        action="store_true",
        help=argparse.SUPPRESS  # Internal toggle for using weighted GMM + weighted BIC
    )
    analysis_group.add_argument(
        "--type-filter", 
        nargs="+", 
        help="Only use templates of these types"
    )
    analysis_group.add_argument(
        "--template-filter", 
        nargs="+", 
        help="Only use specific templates (by name)"
    )
    analysis_group.add_argument(
        "--age-min",
        type=float,
        help="Minimum template age in days"
    )
    analysis_group.add_argument(
        "--age-max",
        type=float,
        help="Maximum template age in days"
    )
    analysis_group.add_argument(
        "--exclude-templates",
        nargs="+",
        help="Exclude specific templates from analysis (by name)"
    )

    # Display options
    # Preprocessing options
    preproc_group = parser.add_argument_group("Preprocessing Options")
    # Early spike masking (enabled by default; can be disabled)
    preproc_group.add_argument(
        "--no-spike-masking",
        dest="spike_masking",
        action="store_false",
        help="Disable early spike masking step (enabled by default)"
    )
    preproc_group.add_argument(
        "--spike-floor-z",
        type=float,
        default=50.0,
        help="Minimum floor-relative robust z for outlier detection (default: 50.0)"
    )
    preproc_group.add_argument(
        "--spike-baseline-window",
        type=int,
        default=501,
        help="Running median window size in pixels (odd, large; default: 501)"
    )
    preproc_group.add_argument(
        "--spike-baseline-width",
        type=float,
        default=None,
        help="Baseline width in wavelength units; overrides pixel window when set"
    )
    preproc_group.add_argument(
        "--spike-rel-edge-ratio",
        type=float,
        default=2.0,
        help="Require center residual to exceed neighbors by this factor (default: 2.0)"
    )
    preproc_group.add_argument(
        "--spike-min-separation",
        type=int,
        default=2,
        help="Minimum pixel separation between removed spikes (default: 2)"
    )
    preproc_group.add_argument(
        "--spike-max-removals",
        type=int,
        default=None,
        help="Optional cap on number of removed spikes per spectrum"
    )
    preproc_group.add_argument(
        "--spike-min-abs-resid",
        type=float,
        default=None,
        help="Minimum absolute residual amplitude (flux units) to consider a spike"
    )
    preproc_group.add_argument(
        "--savgol-window",
        type=int,
        default=0,
        help="Savitzky-Golay filter window size in pixels (0 = no filtering)"
    )
    preproc_group.add_argument(
        "--savgol-order",
        type=int,
        default=3,
        help="Savitzky-Golay filter polynomial order"
    )
    preproc_group.add_argument(
        "--aband-remove",
        action="store_true",
        help="Remove telluric O2 A-band (7550–7700 Å) via mask-aware interpolation"
    )
    preproc_group.add_argument(
        "--skyclip",
        action="store_true",
        help="Add masks around common sky emission lines (±emwidth Å)"
    )
    preproc_group.add_argument(
        "--emclip",
        action="store_true",
        help="Clip host emission lines using per-entry redshift when available; skipped if no redshift"
    )
    preproc_group.add_argument(
        "--emclip-z",
        type=float,
        default=-1.0,
        help="Redshift at which to clip host emission lines (-1 to disable)"
    )
    preproc_group.add_argument(
        "--emwidth",
        type=float,
        default=40.0,
        help="Width in Angstroms for emission/sky line masks"
    )
    preproc_group.add_argument(
        "--wavelength-masks",
        nargs="+",
        metavar="WMIN:WMAX",
        help="Additional wavelength ranges to mask (format: 6550:6600 7600:7700)"
    )
    preproc_group.add_argument(
        "--apodize-percent",
        type=float,
        default=10.0,
        help="Percentage of spectrum ends to apodize (default: 10)"
    )

    display_group = parser.add_argument_group("Display Options")
    display_group.add_argument(
        "--brief",
        action="store_true",
        help="Minimal console output: terse per-spectrum status and final summary"
    )
    display_group.add_argument(
        "--full",
        action="store_true",
        help="Detailed console output (disables brief mode)"
    )
    display_group.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress output (auto-disabled when stdout is not a TTY)"
    )

    # Default to brief output unless explicitly overridden
    parser.set_defaults(brief=True)
    
    # Processing options
    parallel_group = parser.add_argument_group("Parallel Processing")
    parallel_group.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Number of worker processes (0 = sequential, -1 = use all CPU cores)"
    )
    parser.add_argument(
        "--stop-on-error", 
        action="store_true",
        help="Stop processing if any spectrum fails"
    )
    # Rely on global --verbose/--debug from main parser
    # Default behavior: generate plots unless disabled
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Do not generate plots (by default plots are saved)"
    )



def generate_summary_report(results: List[Tuple], args: argparse.Namespace, wall_elapsed_seconds: Optional[float] = None) -> str:
    """Generate a clean, comprehensive summary report focused on batch processing success."""
    successful_results = [r for r in results if r[1] and r[3]]
    failed_results = [r for r in results if not r[1]]
    
    total_count = len(results)
    success_count = len(successful_results)
    failure_count = len(failed_results)
    
    # Generate report
    report = []
    report.append("="*80)
    report.append("SNID SAGE BATCH ANALYSIS REPORT")
    report.append("="*80)
    report.append("")
    
    # Summary
    report.append("BATCH PROCESSING SUMMARY")
    report.append("-"*50)
    if getattr(args, 'list_csv', None):
        report.append(f"Input List CSV: {args.list_csv}")
        report.append(f"Columns: path='{getattr(args, 'path_column', 'path')}', redshift='{getattr(args, 'redshift_column', 'redshift')}'")
        report.append("Per-spectrum forced redshift: applied where provided in CSV")
    else:
        report.append(f"Input Pattern: {args.input_pattern}")
    report.append(f"Templates Directory: {args.templates_dir}")
    report.append(f"Analysis Mode: {'Minimal (summary only)' if args.minimal else 'Complete (all outputs + plots)' if args.complete else 'Standard (main outputs)'}")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    report.append(f"PROCESSING RESULTS:")
    report.append(f"   Total Spectra Processed: {total_count}")
    report.append(f"   Successful Analyses: {success_count} ({success_count/total_count*100:.1f}%)")
    report.append(f"   Failed Analyses: {failure_count} ({failure_count/total_count*100:.1f}%)")
    report.append("")
    
    report.append(f"ANALYSIS PARAMETERS:")
    report.append(f"   Redshift Search Range: {args.zmin:.6f} ≤ z ≤ {args.zmax:.6f}")
    if args.forced_redshift is not None:
        report.append(f"   Forced Redshift: z = {args.forced_redshift:.6f}")
    if args.type_filter:
        report.append(f"   Type Filter: {', '.join(args.type_filter)}")
    if args.template_filter:
        report.append(f"   Template Filter: {', '.join(args.template_filter)}")
    
    report.append("")
    
    if successful_results:
        # Results table - focus on individual objects, not aggregated science
        report.append("INDIVIDUAL SPECTRUM RESULTS")
        report.append("-"*50)
        report.append("Each spectrum represents a different astronomical object.")
        report.append("Results are sorted by Q (analysis quality) - highest first.")
        report.append("")
        
        # Header (winning subtype focused)
        header = (
            f"{'Spectrum':<16} {'Type':<7} {'Subtype':<12} "
            f"{'z':<10} {'z_err':<10} {'Age':<8} {'Age_err':<8} "
            f"{'Q_cluster':<10} {'MatchQual':<10} {'TypeConf':<10} {'zFixed':<6} {'Status':<1}"
        )
        report.append(header)
        report.append("-" * len(header))
        
        # Sort results by penalized winning-subtype score when available, otherwise best metric
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        def _sort_key(item: Tuple):
            s = item[3]
            v = s.get('winning_subtype_penalized_score') if isinstance(s, dict) else None
            if isinstance(v, (int, float)) and np.isfinite(v):
                return float(v)
            return float(get_best_metric_value(s))
        successful_results_sorted = sorted(successful_results, key=_sort_key, reverse=True)
        
        # Results
        for _, _, _, summary in successful_results_sorted:
            spectrum = summary['spectrum'][:15]
            cons_type = summary.get('consensus_type', 'Unknown')[:6]
            cons_subtype = summary.get('consensus_subtype', 'Unknown')[:11]

            # Redshift/error from winning subtype or cluster-weighted; hide when not meaningful (<=0) or cluster size <= 1
            z_val = summary.get('winning_subtype_redshift', None)
            z_err_val = summary.get('winning_subtype_redshift_err', None)
            if not (isinstance(z_val, (int, float)) and np.isfinite(z_val)):
                z_val = summary.get('redshift', 0.0)
            cluster_size_disp = summary.get('cluster_size', 0)
            if not (isinstance(z_err_val, (int, float)) and np.isfinite(z_err_val)):
                # Only show error when clustering provided an aggregate; otherwise N/A
                z_err_val = None if not summary.get('has_clustering') else summary.get('redshift_error', None)
            # Hide only if non-positive or invalid; allow single-member σz to show
            try:
                if (not isinstance(z_err_val, (int, float))) or (not np.isfinite(z_err_val)) or (float(z_err_val) <= 0.0):
                    z_err_val = None
            except Exception:
                z_err_val = None

            z_str = f"{float(z_val):.6f}" if isinstance(z_val, (int, float)) else ""
            z_se_str = f"{float(z_err_val):.6f}" if isinstance(z_err_val, (int, float)) else "nan"

            # Age/error from winning subtype aggregates; fallback to best-match age; hide if not meaningful
            age_val = summary.get('winning_subtype_age', None)
            age_err_val = summary.get('winning_subtype_age_err', None)
            if not (isinstance(age_val, (int, float)) and np.isfinite(age_val)):
                age_val = summary.get('age', None)
            # Age error may be NaN for single-member; leave as-is (will render 'nan')
            age_str = f"{float(age_val):.1f}" if isinstance(age_val, (int, float)) else ""
            age_se_str = f"{float(age_err_val):.1f}" if isinstance(age_err_val, (int, float)) else "nan"

            # Display penalized top-5 best metric for winning subtype when available
            metric_val = summary.get('winning_subtype_penalized_score', None)
            if not isinstance(metric_val, (int, float)) or not np.isfinite(metric_val):
                from snid_sage.shared.utils.math_utils import get_best_metric_value
                metric_val = get_best_metric_value(summary)
            best_metric_str = f"{float(metric_val):.2f}"

            # Match Quality (cluster quality category) and Type Confidence (cluster confidence level)
            match_quality = (summary.get('cluster_quality_category', '') or '') if summary.get('has_clustering') else ''
            type_conf = summary.get('cluster_confidence_level', '') if summary.get('has_clustering') else ''
            type_conf = type_conf.title() if type_conf else ''

            status_marker = "✓"
            zfixed = "Y" if summary.get('redshift_fixed') else "N"

            row = (
                f"{spectrum:<16} {cons_type:<7} {cons_subtype:<12} "
                f"{z_str:<10} {z_se_str:<10} {age_str:<8} {age_se_str:<8} "
                f"{best_metric_str:<10} {match_quality:<10} {type_conf:<10} {zfixed:<6} {status_marker}"
            )
            report.append(row)

        # Append failed analyses to the same table with 'x' status
        if failed_results:
            for name, success, message, _ in failed_results:
                spectrum = name[:15]
                cons_type = 'nan'
                cons_subtype = 'nan'
                z_str = 'nan'
                z_se_str = 'nan'
                age_str = 'nan'
                age_se_str = 'nan'
                best_metric_str = 'nan'
                match_quality = 'nan'
                type_conf = 'nan'
                status_marker = 'x'
                row = (
                    f"{spectrum:<16} {cons_type:<7} {cons_subtype:<12} "
                    f"{z_str:<10} {z_se_str:<10} {age_str:<8} {age_se_str:<8} "
                    f"{best_metric_str:<10} {match_quality:<10} {type_conf:<10} {'N':<6} {status_marker}"
                )
                report.append(row)
        
        report.append("")
        report.append("")
        
        # Detailed analysis (sorted by Q - highest first)
        report.append("DETAILED INDIVIDUAL ANALYSIS")
        report.append("-"*50)
        report.append("Detailed results for each spectrum (sorted by analysis quality):")
        
        for _, _, _, summary in successful_results_sorted:
            report.append(f"\n{summary['spectrum']}")
            report.append(f"   Best Template: {clean_template_name(summary.get('best_template', 'Unknown'))}")
            report.append(f"   Classification: {summary.get('consensus_type', 'Unknown')} {summary.get('consensus_subtype', '')}")

            # Winning Subtype estimates (preferred)
            z_mean = summary.get('winning_subtype_redshift', None)
            z_se = summary.get('winning_subtype_redshift_err', None)
            age_mean = summary.get('winning_subtype_age', None)
            age_se = summary.get('winning_subtype_age_err', None)
            if isinstance(z_mean, (int, float)) and np.isfinite(z_mean):
                z_txt = f"{z_mean:.6f}"
            else:
                z_txt = f"{summary.get('redshift', 0):.6f}"
            zse_txt = f" (Err={z_se:.6f})" if isinstance(z_se, (int, float)) and np.isfinite(z_se) else ""
            if isinstance(age_mean, (int, float)) and np.isfinite(age_mean):
                age_txt = f"{age_mean:.1f}"
            else:
                age_txt = f"{summary.get('age', float('nan')):.1f}" if isinstance(summary.get('age', None), (int, float)) else "nan"
            agese_txt = f" (Err={age_se:.1f})" if isinstance(age_se, (int, float)) and np.isfinite(age_se) else ""
            report.append(f"   Winning Subtype Estimates: z={z_txt}{zse_txt}; age={age_txt}{agese_txt}")
            
            # Show cluster information if available
            if summary.get('has_clustering'):
                report.append(f"   CLUSTER ANALYSIS ({summary.get('cluster_method', 'Unknown')}):")
                report.append(f"      Cluster Type: {summary.get('cluster_type', 'Unknown')}")
                report.append(f"      Cluster Size: {summary.get('cluster_size', 0)} template matches")
                
                # Show new quality metrics (single structured line)
                if 'cluster_quality_category' in summary:
                    mq_cat = summary.get('cluster_quality_category', '')
                    mq_desc = summary.get('cluster_quality_description', '')
                    if mq_desc:
                        report.append(f"      Match Quality: {mq_cat} — {mq_desc}")
                    else:
                        report.append(f"      Match Quality: {mq_cat}")
                
                if 'cluster_confidence_level' in summary:
                    level = str(summary.get('cluster_confidence_level', '')).title()
                    pct = summary.get('cluster_confidence_pct', None)
                    sbt = summary.get('cluster_second_best_type', 'N/A')
                    try:
                        pct_val = float(pct) if pct is not None else float('nan')
                    except Exception:
                        pct_val = float('nan')
                    conf_parts = [level if level else 'N/A']
                    if isinstance(pct_val, float) and np.isfinite(pct_val):
                        conf_parts.append(f"(+{pct_val:.1f}%)")
                    if sbt and sbt != 'N/A':
                        conf_parts.append(f"vs {sbt}")
                    report.append(f"      Type Confidence: {' '.join(conf_parts)}")
                
                if 'cluster_redshift_weighted' in summary:
                    se_val = summary.get('cluster_redshift_err_weighted', float('nan'))
                    # Hide when not meaningful (<=0 or single-member cluster)
                    try:
                        cluster_size_disp = int(summary.get('cluster_size', 0))
                        show_se = (isinstance(se_val, (int, float)) and np.isfinite(se_val) and (float(se_val) > 0.0) and (cluster_size_disp > 1))
                    except Exception:
                        show_se = isinstance(se_val, (int, float)) and np.isfinite(se_val) and (float(se_val) > 0.0)
                    se_txt = f" (Err={se_val:.6f})" if show_se else ""
                    report.append(f"      Weighted Redshift: {summary['cluster_redshift_weighted']:.6f}{se_txt}")
                    report.append(f"      Cluster mean metric: {summary.get('cluster_mean_metric', 0):.2f}")
                
                report.append(f"   Best Match Redshift: {summary.get('redshift', 0):.6f} ± {summary.get('redshift_error', 0):.6f}")
            else:
                # No clustering: show only best-match redshift without error
                report.append(f"   Redshift: {summary.get('redshift', 0):.6f}")

            # Redshift mode
            if summary.get('redshift_fixed'):
                try:
                    report.append(f"   Redshift Mode: Fixed at z={summary.get('redshift_fixed_value', 0):.6f}")
                except Exception:
                    report.append("   Redshift Mode: Fixed")
            else:
                report.append("   Redshift Mode: Search within zmin/zmax")
            
            # Show Q (winning subtype) when available; fallback to best metric
            metric_value = summary.get('winning_subtype_penalized_score', None)
            if isinstance(metric_value, (int, float)) and np.isfinite(metric_value):
                report.append(f"   Q (analysis quality): {metric_value:.2f}")
            else:
                from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
                metric_value = get_best_metric_value(summary)
                metric_name = get_best_metric_name(summary)
                report.append(f"   {metric_name} (analysis quality): {metric_value:.2f}")
            report.append(f"   Runtime: {summary.get('runtime', 0):.1f} seconds")
            
            # Show subtype composition within this spectrum's analysis
            if summary.get('cluster_subtypes'):
                if summary.get('has_clustering'):
                    report.append(f"   Cluster Subtype Composition:")
                else:
                    report.append(f"   Template Subtype Distribution:")
                for i, (subtype_name, fraction) in enumerate(summary['cluster_subtypes'][:3], 1):  # Top 3
                    report.append(f"      {i}. {subtype_name}: {fraction*100:.1f}%")
        
        # Analysis quality statistics (these ARE meaningful to aggregate)  
        report.append(f"\n\nBATCH PROCESSING QUALITY STATISTICS")
        report.append("-"*50)
        report.append("These statistics describe the quality of the batch processing, not the science.")
        report.append("")
        
        # Best-metric distribution (analysis quality)
        from snid_sage.shared.utils.math_utils import get_best_metric_value
        all_metrics = [get_best_metric_value(summary) for _, _, _, summary in successful_results]
        avg_metric = sum(all_metrics) / len(all_metrics) if all_metrics else 0
        high_quality = sum(1 for metric in all_metrics if metric >= 10.0)
        medium_quality = sum(1 for metric in all_metrics if 5.0 <= metric < 10.0)
        low_quality = sum(1 for metric in all_metrics if metric < 5.0)
        
        # Determine metric name (HσLAP-CCC preferred)
        from snid_sage.shared.utils.math_utils import get_best_metric_name
        metric_name = get_best_metric_name(successful_results[0][3]) if successful_results else "HσLAP-CCC"
        
        report.append(f"ANALYSIS QUALITY ({metric_name} Distribution):")
        report.append(f"   Average {metric_name}: {avg_metric:.2f}")
        report.append(f"   High Quality ({metric_name} ≥ 10): {high_quality}/{success_count} ({high_quality/success_count*100:.1f}%)")
        report.append(f"   Medium Quality (5 ≤ {metric_name} < 10): {medium_quality}/{success_count} ({medium_quality/success_count*100:.1f}%)")
        report.append(f"   Low Quality ({metric_name} < 5): {low_quality}/{success_count} ({low_quality/success_count*100:.1f}%)")
        
        # Classification confidence (using cluster-based metrics)
        cluster_count = sum(1 for _, _, _, s in successful_results if s.get('has_clustering', False))
        high_confidence = sum(1 for _, _, _, s in successful_results 
                             if s.get('cluster_confidence_level') == 'High')
        medium_confidence = sum(1 for _, _, _, s in successful_results 
                               if s.get('cluster_confidence_level') == 'Medium')
        low_confidence = sum(1 for _, _, _, s in successful_results 
                            if s.get('cluster_confidence_level') == 'Low')
        very_low_confidence = sum(1 for _, _, _, s in successful_results 
                                 if s.get('cluster_confidence_level') == 'Very Low')
        
        report.append(f"\nCLASSIFICATION CONFIDENCE:")
        if cluster_count > 0:
            report.append(f"   High Confidence: {high_confidence}/{success_count} ({high_confidence/success_count*100:.1f}%)")
            report.append(f"   Medium Confidence: {medium_confidence}/{success_count} ({medium_confidence/success_count*100:.1f}%)")
            report.append(f"   Low Confidence: {low_confidence}/{success_count} ({low_confidence/success_count*100:.1f}%)")
            report.append(f"   Very Low Confidence: {very_low_confidence}/{success_count} ({very_low_confidence/success_count*100:.1f}%)")
        else:
            report.append("   Note: Cluster-based confidence not available in this run")
        
        # Clustering effectiveness
        cluster_count = sum(1 for _, _, _, s in successful_results if s.get('has_clustering', False))
        total_cluster_size = sum(s.get('cluster_size', 0) for _, _, _, s in successful_results if s.get('has_clustering', False))
        
        report.append(f"\nCLUSTERING EFFECTIVENESS:")
        report.append(f"   Spectra with GMM clustering: {cluster_count}/{success_count} ({cluster_count/success_count*100:.1f}%)")
        report.append(f"   Spectra with basic analysis: {success_count-cluster_count}/{success_count} ({(success_count-cluster_count)/success_count*100:.1f}%)")
        if cluster_count > 0:
            avg_cluster_size = total_cluster_size / cluster_count
            report.append(f"   Average cluster size: {avg_cluster_size:.1f} template matches")
        
    # Runtime statistics
    all_runtimes = [summary.get('runtime', 0) for _, _, _, summary in successful_results if summary.get('runtime', 0) > 0]
    if all_runtimes or wall_elapsed_seconds is not None:
        avg_cpu_runtime = (sum(all_runtimes) / len(all_runtimes)) if all_runtimes else 0.0
        total_wall_runtime = float(wall_elapsed_seconds) if wall_elapsed_seconds is not None else float(sum(all_runtimes))
        avg_effective_runtime = (total_wall_runtime / success_count) if (success_count > 0 and total_wall_runtime > 0) else 0.0
        is_parallel = bool(int(getattr(args, 'workers', 0) or 0) != 0)
        report.append(f"\nPERFORMANCE STATISTICS:")
        # Only show CPU average in sequential mode to avoid confusion in parallel runs
        if (not is_parallel) and avg_cpu_runtime > 0:
            report.append(f"   Average analysis time: {avg_cpu_runtime:.1f} seconds per spectrum")
        if avg_effective_runtime > 0:
            report.append(f"   Average effective time per spectrum (wall): {avg_effective_runtime:.1f} seconds")
        report.append(f"   Total analysis time: {total_wall_runtime:.1f} seconds")
        if total_wall_runtime > 0 and success_count > 0:
            report.append(f"   Throughput: {success_count/total_wall_runtime*60:.1f} spectra per minute")
        
        # Type distribution (for reference only - not scientifically aggregated)
        type_counts = {}
        for _, _, _, summary in successful_results:
            cons_type = summary.get('consensus_type', 'Unknown')
            type_counts[cons_type] = type_counts.get(cons_type, 0) + 1
        
        if len(type_counts) > 1:  # Only show if there's variety
            report.append(f"\nTYPE DISTRIBUTION (For Reference Only):")
            report.append("Note: Each spectrum is a different object - this is just a summary of what was found.")
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            for type_name, count in sorted_types:
                percentage = count / success_count * 100
                report.append(f"   {type_name}: {count} spectra ({percentage:.1f}%)")
    
    # Separate no-matches from actual failures
    no_match_results = []
    actual_failed_results = []
    
    for spectrum_name, _, error_message, _ in failed_results:
        if "No good matches" in error_message or "No templates after filtering" in error_message:
            no_match_results.append((spectrum_name, error_message))
        else:
            actual_failed_results.append((spectrum_name, error_message))
    
    # No matches section (normal outcome)
    if no_match_results:
        report.append(f"\n\nNO MATCHES FOUND ({len(no_match_results)} spectra)")
        report.append("-"*50)
        report.append("These spectra had no good template matches - this is a normal analysis outcome.")
        for spectrum_name, error_message in no_match_results:
            reason = "no templates available" if "No templates after filtering" in error_message else "no good matches"
            report.append(f"   {spectrum_name}: {reason}")
    
    # Actual failures section (real errors)
    if actual_failed_results:
        report.append(f"\n\nACTUAL FAILURES ({len(actual_failed_results)} spectra)")
        report.append("-"*50)
        report.append("These spectra failed due to processing errors:")
        for spectrum_name, error_message in actual_failed_results:
            report.append(f"   {spectrum_name}: {error_message}")
    
    report.append("\n" + "="*80)
    
    return "\n".join(report)


def _export_results_table(results: List[Tuple], output_dir: Path) -> Optional[Path]:
    """Export per-spectrum results to CSV with clear best-match column names."""
    # Build rows in a deterministic column order
    columns = [
        'file',
        'path',
        'type',
        'subtype',
        'z',
        'z_err',
        'age',
        'age_err',
        'Q_cluster',
        'match_quality',
        'type_confidence',
        'subtype_confidence',
        'second_best_subtype',  # Runner-up within winning cluster
        # Helpful extras
        'best_template',
        'zfixed',
        # Second-best competitor info near the end for readability
        'second_best_type',
        'second_best_type_subtype',
        'second_best_type_subtype_z',
        'second_best_type_subtype_z_err',
        'second_best_type_subtype_age',
        'second_best_type_subtype_age_err',
        'success',
        'error'
    ]

    rows: List[Dict[str, Any]] = []

    for name, success, message, summary in results:
        row: Dict[str, Any] = {c: None for c in columns}

        if success and isinstance(summary, dict) and summary.get('success', False):
            # Identification
            row['file'] = summary.get('spectrum', name)
            row['path'] = summary.get('file_path')
            # Classification
            row['type'] = summary.get('consensus_type', 'Unknown')
            row['subtype'] = summary.get('consensus_subtype', 'Unknown')
            # Second-best competitor TYPE retained for readability
            def _nan_if_missing(val):
                try:
                    txt = str(val).strip() if val is not None else ''
                except Exception:
                    txt = ''
                return 'nan' if (txt == '' or txt.upper() == 'N/A') else val
            row['second_best_type'] = _nan_if_missing(summary.get('cluster_second_best_type', None))
            row['second_best_type_subtype'] = _nan_if_missing(summary.get('second_best_type_subtype', None))
            # Runner-up subtype within the winning cluster
            row['second_best_subtype'] = _nan_if_missing(summary.get('winning_second_best_subtype', None))

            # Use estimated values: prefer winning subtype estimates; fallback to cluster-weighted; then best-match
            z_est = summary.get('winning_subtype_redshift')
            z_err_est = summary.get('winning_subtype_redshift_err')
            age_est = summary.get('winning_subtype_age')
            age_err_est = summary.get('winning_subtype_age_err')

            if not isinstance(z_est, (int, float)) or not np.isfinite(z_est):
                z_est = summary.get('cluster_redshift_weighted', summary.get('redshift'))
            if not isinstance(z_err_est, (int, float)) or not np.isfinite(z_err_est):
                z_err_est = summary.get('cluster_redshift_err_weighted', summary.get('redshift_error'))
            if not isinstance(age_est, (int, float)) or not np.isfinite(age_est):
                age_est = summary.get('cluster_age_weighted', summary.get('age'))
            if not isinstance(age_err_est, (int, float)) or not np.isfinite(age_err_est):
                age_err_est = summary.get('cluster_age_err_weighted', None)

            # Hide errors only when not meaningful (<=0); allow single-member σz
            try:
                cluster_size_csv = int(summary.get('cluster_size', 0))
            except Exception:
                cluster_size_csv = 0
            if not (isinstance(z_err_est, (int, float)) and np.isfinite(z_err_est) and (float(z_err_est) > 0.0)):
                z_err_est = 'nan'
            if not (isinstance(age_err_est, (int, float)) and np.isfinite(age_err_est) and (float(age_err_est) > 0.0)):
                age_err_est = 'nan'

            row['z'] = z_est
            row['z_err'] = z_err_est
            row['age'] = age_est
            row['age_err'] = age_err_est

            # Competitor (second-best TYPE) subtype estimates
            comp_z = summary.get('second_best_type_subtype_z')
            comp_z_err = summary.get('second_best_type_subtype_z_err')
            comp_age = summary.get('second_best_type_subtype_age')
            comp_age_err = summary.get('second_best_type_subtype_age_err')

            if not (isinstance(comp_z, (int, float)) and np.isfinite(comp_z)):
                comp_z = 'nan'
            if not (isinstance(comp_z_err, (int, float)) and np.isfinite(comp_z_err) and (float(comp_z_err) > 0.0)):
                comp_z_err = 'nan'
            if not (isinstance(comp_age, (int, float)) and np.isfinite(comp_age)):
                comp_age = 'nan'
            if not (isinstance(comp_age_err, (int, float)) and np.isfinite(comp_age_err) and (float(comp_age_err) > 0.0)):
                comp_age_err = 'nan'

            row['second_best_type_subtype_z'] = comp_z
            row['second_best_type_subtype_z_err'] = comp_z_err
            row['second_best_type_subtype_age'] = comp_age
            row['second_best_type_subtype_age_err'] = comp_age_err

            # Analysis quality metrics
            # Prefer cluster-level Q when available; fallback to subtype Q; then best metric
            q_cluster = summary.get('cluster_penalized_score', None)
            if not isinstance(q_cluster, (int, float)) or not np.isfinite(q_cluster):
                q_cluster = summary.get('winning_subtype_penalized_score', None)
            if not isinstance(q_cluster, (int, float)) or not np.isfinite(q_cluster):
                try:
                    from snid_sage.shared.utils.math_utils import get_best_metric_value
                    q_cluster = get_best_metric_value(summary)
                except Exception:
                    q_cluster = summary.get('hsigma_lap_ccc', None)
            row['Q_cluster'] = q_cluster

            row['match_quality'] = summary.get('cluster_quality_category', None)
            if not summary.get('has_clustering'):
                row['match_quality'] = None
            row['type_confidence'] = summary.get('cluster_confidence_level', None)
            # Subtype confidence: use qualitative level (High/Medium/Low/Very Low/No Comp)
            row['subtype_confidence'] = summary.get('subtype_confidence_level', None)

            # Extras
            try:
                row['best_template'] = clean_template_name(summary.get('best_template', 'Unknown'))
            except Exception:
                row['best_template'] = summary.get('best_template')
            row['zfixed'] = bool(summary.get('redshift_fixed', False))
            row['success'] = True
            row['error'] = ''
        else:
            # Failure row
            row['file'] = name
            row['path'] = summary.get('file_path') if isinstance(summary, dict) else None
            # Fill core analytic fields with literal 'nan' for no-match/error rows
            row['type'] = 'nan'
            row['subtype'] = 'nan'
            row['z'] = 'nan'
            row['z_err'] = 'nan'
            row['age'] = 'nan'
            row['age_err'] = 'nan'
            row['Q_cluster'] = 'nan'
            row['match_quality'] = 'nan'
            row['type_confidence'] = 'nan'
            row['subtype_confidence'] = 'nan'
            row['best_template'] = 'nan'
            # For failures, still report whether a fixed redshift was attempted
            row['zfixed'] = bool(summary.get('redshift_fixed', False)) if isinstance(summary, dict) else False
            # Fill competitor columns with nan on failures as requested
            row['second_best_type'] = 'nan'
            row['second_best_subtype'] = 'nan'
            row['second_best_type_subtype'] = 'nan'
            row['second_best_type_subtype_z'] = 'nan'
            row['second_best_type_subtype_z_err'] = 'nan'
            row['second_best_type_subtype_age'] = 'nan'
            row['second_best_type_subtype_age_err'] = 'nan'
            row['success'] = False
            row['error'] = message

        rows.append(row)

    # Always write CSV only
    csv_path = output_dir / 'batch_results.csv'
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    except Exception as e:
        logging.getLogger('snid_sage.snid.batch').warning(f"Failed to write CSV results: {e}")
        return None

    return csv_path


def main(args: argparse.Namespace) -> int:
    """Main function for the simplified batch command."""
    try:
        # Logging already configured at top-level; proceed
        is_quiet = bool(getattr(args, 'quiet', False) or getattr(args, 'silent', False))
        # Determine brief mode default: on by default, turned off by --full or verbosity flags
        brief_mode = bool(getattr(args, 'brief', True)) and not bool(getattr(args, 'full', False))
        if getattr(args, 'verbose', False) or getattr(args, 'debug', False):
            brief_mode = False

        # If brief mode, quiet down global logging to suppress INFO spam
        if brief_mode and not is_quiet:
            try:
                set_global_verbosity(VerbosityLevel.QUIET)
            except Exception:
                pass
            # Hard-disable INFO and DEBUG from all loggers to keep console minimal
            try:
                logging.disable(logging.INFO)
            except Exception:
                pass
        
        # Additional suppression for CLI mode - silence specific noisy loggers
        if not args.verbose:
            # Suppress the most verbose loggers that users don't need to see
            logging.getLogger('snid_sage.snid.pipeline').setLevel(logging.WARNING)
            logging.getLogger('snid_sage.snid.pipeline').setLevel(logging.WARNING)
        
        # Suppress matplotlib warnings (tight layout warnings)
        import warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
        
        # Suppress "No good matches found" as ERROR - it's a normal outcome
        pipeline_logger = logging.getLogger('snid_sage.snid.pipeline')
        pipeline_logger.setLevel(logging.CRITICAL)  # Only critical errors, not "no matches"
        
        # Determine input source (glob pattern or list CSV)
        items: List[Dict[str, Any]] = []
        using_list_csv = bool(getattr(args, 'list_csv', None))
        if (not using_list_csv) and (not getattr(args, 'input_pattern', None)):
            print("[ERROR] Provide an input pattern or use --list-csv to supply a file list.", file=sys.stderr)
            return 1
        if using_list_csv:
            # Read items from CSV
            try:
                with open(args.list_csv, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    # Normalize header names for robust matching
                    headers = reader.fieldnames or []
                    norm_map = {h: re.sub(r'[^a-z0-9]', '', h.lower()) for h in headers}

                    # Determine actual path and redshift keys
                    desired_path_key = getattr(args, 'path_column', 'path') or 'path'
                    desired_redshift_key = getattr(args, 'redshift_column', 'redshift') or 'redshift'

                    def resolve_column(desired: str, candidates: List[str]) -> Optional[str]:
                        # Exact match first
                        if desired in headers:
                            return desired
                        # Try case-insensitive exact
                        for h in headers:
                            if h.lower() == desired.lower():
                                return h
                        # Try normalized candidates
                        desired_norm = re.sub(r'[^a-z0-9]', '', desired.lower())
                        all_candidates = [desired_norm] + candidates
                        for h, n in norm_map.items():
                            if n in all_candidates:
                                return h
                        return None

                    path_candidates_norm = [
                        'path', 'file', 'spectrum', 'spectrumpath', 'pathname'
                    ]
                    redshift_candidates_norm = [
                        'redshift', 'hostz', 'sherlockhostz', 'z', 'hostredshift'
                    ]

                    actual_path_key = resolve_column(desired_path_key, path_candidates_norm)
                    actual_redshift_key = resolve_column(desired_redshift_key, redshift_candidates_norm)

                    base_dir = Path(args.list_csv).parent
                    for row in reader:
                        path_val = row.get(actual_path_key) if actual_path_key else None
                        if not path_val or str(path_val).strip() == "":
                            continue
                        path_str = str(path_val).strip()
                        # Resolve relative to CSV directory
                        try:
                            p = Path(path_str)
                            if not p.is_absolute():
                                p = (base_dir / p).resolve()
                            path_str = str(p)
                        except Exception:
                            pass
                        redshift_val: Optional[float] = None
                        raw_z = row.get(actual_redshift_key) if actual_redshift_key else None
                        if raw_z is not None and str(raw_z).strip() != "":
                            try:
                                zf = float(raw_z)
                                if np.isfinite(zf):
                                    redshift_val = float(zf)
                            except Exception:
                                redshift_val = None
                        items.append({"path": path_str, "redshift": redshift_val})
                # Helpful diagnostics: show which columns were actually resolved and how many rows will be forced.
                try:
                    n_forced = sum(1 for it in items if it.get("redshift") is not None)
                except Exception:
                    n_forced = 0
                if (not is_quiet) and (not brief_mode):
                    print(
                        f"[INFO] CSV columns resolved: path='{actual_path_key}', redshift='{actual_redshift_key}'. "
                        f"{n_forced}/{len(items)} rows have finite redshift and will run in forced-redshift mode."
                    )
            except FileNotFoundError:
                print(f"[ERROR] CSV file not found: {args.list_csv}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"[ERROR] Failed to read CSV '{args.list_csv}': {e}", file=sys.stderr)
                return 1
            input_files = [it["path"] for it in items]
            if not input_files:
                print(f"[ERROR] No valid rows found in CSV: {args.list_csv}", file=sys.stderr)
                return 1
        else:
            # Pattern-based discovery
            input_files = glob.glob(args.input_pattern)
            if not input_files:
                print(f"[ERROR] No files found matching pattern: {args.input_pattern}", file=sys.stderr)
                return 1
            items = [{"path": p, "redshift": None} for p in input_files]
        
        # Determine mode
        if args.minimal:
            mode = "Minimal (summary only)"
        elif args.complete:
            mode = "Complete (all outputs + plots)"
        else:
            mode = "Standard (main outputs)"
        
        # Resolve output directory from CLI or unified config
        if not args.output_dir:
            try:
                from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
                cfg = ConfigurationManager().load_config()
                args.output_dir = cfg.get('paths', {}).get('output_dir') or str(Path.cwd() / 'results')
            except Exception:
                args.output_dir = str(Path.cwd() / 'results')
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Always show a single concise startup line (respects quiet/silent)
        if not is_quiet:
            print(f"Starting batch analysis for {len(input_files)} spectra")
        
        # Simple startup message (after resolving output_dir)
        if not is_quiet and not brief_mode:
            print("SNID-SAGE Batch Analysis - Cluster-aware & optimized")
            print(f"   Files: {len(input_files)} spectra")
            print(f"   Mode: {mode}")
            print(f"   Analysis: GUI-style cluster-aware (winning cluster)")
            print(f"   Sorting: All results/plots sorted by Q_cluster (weighted top-5 metric, highest quality first)")
            print(f"   Output: {args.output_dir}")
            print(f"   Redshift Range: {args.zmin:.6f} to {args.zmax:.6f}")
            if args.forced_redshift is not None:
                print(f"   Forced Redshift: {args.forced_redshift:.6f}")
            if using_list_csv:
                print(f"   Input list CSV: {args.list_csv} (path='{getattr(args, 'path_column', 'path')}', redshift='{getattr(args, 'redshift_column', 'redshift')}')")
            print(f"   Error Handling: {'Stop on first failure' if args.stop_on_error else 'Continue on failures (default)'}")
            print("")
        
        # Decide parallelism BEFORE any template loading (avoid fork-after-init on POSIX)
        use_parallel = int(getattr(args, 'workers', 0) or 0) != 0
        max_workers = int(args.workers or 0)
        if max_workers < 0:
            try:
                max_workers = os.cpu_count() or 1
            except Exception:
                max_workers = 1
        # Avoid spawning a huge number of processes for tiny jobs; it slows startup,
        # increases filesystem pressure (HDF5/index reads), and can change behavior on
        # some HPC/NFS setups.
        if use_parallel:
            try:
                max_workers = max(1, min(int(max_workers), int(len(items))))
            except Exception:
                max_workers = max(1, int(max_workers) if max_workers else 1)
        
        # ============================================================================
        # OPTIMIZATION: Load templates ONCE for the entire batch
        # Also: adapt templates directory to profile when not explicitly provided
        # ============================================================================
        if (not use_parallel) and (not is_quiet) and (not brief_mode):
            print("Loading templates once for entire batch (sequential mode)...")
        # Start wall-clock timer before heavy work (template load + processing)
        start_time = time.time()
        # Resolve effective templates directory based on profile if none provided
        effective_templates_dir = getattr(args, 'templates_dir', None)
        active_profile_id = getattr(args, 'profile_id', None)

        # ----------------------------------------------------------------------
        # Profile-aware defaults for redshift range when user did not override
        # ----------------------------------------------------------------------
        if getattr(args, 'zmax', None) is None:
            try:
                pid = (active_profile_id or '').strip().lower()
            except Exception:
                pid = ''
            # Align CLI batch behavior with GUI: ONIR extends up to z≈2.5 by default
            args.zmax = 2.5 if pid == 'onir' else 1.0
        if not effective_templates_dir:
            try:
                from snid_sage.shared.templates_manager import get_templates_dir

                effective_templates_dir = str(get_templates_dir())
            except Exception:
                # Fallback to relative path for dev environments
                effective_templates_dir = 'templates'

        # Reflect resolved path back into args for downstream consumers and reporting
        args.templates_dir = effective_templates_dir

        template_manager = BatchTemplateManager(effective_templates_dir, verbose=args.verbose, profile_id=active_profile_id)
        
        # In sequential mode, preload templates in the parent process.
        # In parallel mode, defer loading to worker initializer to avoid fork-safety issues.
        if not use_parallel:
            if not template_manager.load_templates_once():
                print("[ERROR] Failed to load templates", file=sys.stderr)
                return 1
        
            if not is_quiet and not brief_mode:
                print(f"[SUCCESS] Templates loaded in {template_manager.load_time:.2f}s")
                print(f"Ready to process {len(input_files)} spectra with {template_manager.template_count} templates")
                print("")
        
        # Process spectra (parallel or sequential)
        results: List[Tuple[str, bool, str, Dict[str, Any]]] = []
        failed_count = 0

        if use_parallel:
            # In parallel mode, default to brief output even if user didn't pass --brief
            brief_mode = True if not getattr(args, 'full', False) else False
            if not is_quiet and not brief_mode:
                print(f"[INFO] Starting parallel processing with {max_workers} worker(s)...")

            # Build a lightweight dict of args to send to workers
            # Parse wavelength masks once here so workers receive numeric ranges
            parsed_wavelength_masks = parse_wavelength_mask_args(getattr(args, 'wavelength_masks', None))

            args_dict = {
                'minimal': bool(args.minimal),
                'complete': bool(args.complete),
                'zmin': float(args.zmin),
                'zmax': float(args.zmax),
                'age_min': getattr(args, 'age_min', None),
                'age_max': getattr(args, 'age_max', None),
                'lapmin': float(getattr(args, 'lapmin', 0.3)),
                'hsigma_lap_ccc_threshold': float(getattr(args, 'hsigma_lap_ccc_threshold', 1.5)),
                'forced_redshift': getattr(args, 'forced_redshift', None),
                'type_filter': getattr(args, 'type_filter', None),
                'template_filter': getattr(args, 'template_filter', None),
                'exclude_templates': getattr(args, 'exclude_templates', None),
                'no_plots': bool(getattr(args, 'no_plots', False)),
                'templates_dir': template_manager.templates_dir,
                'profile_id': getattr(args, 'profile_id', None),
                # --- Preprocessing flags needed inside worker processes ---
                'savgol_window': int(getattr(args, 'savgol_window', 0)),
                'savgol_order': int(getattr(args, 'savgol_order', 3)),
                'aband_remove': bool(getattr(args, 'aband_remove', False)),
                'skyclip': bool(getattr(args, 'skyclip', False)),
                'emclip': bool(getattr(args, 'emclip', False)),
                'emclip_z': float(getattr(args, 'emclip_z', -1.0)),
                'emwidth': float(getattr(args, 'emwidth', 40.0)),
                'wavelength_masks': parsed_wavelength_masks,
                'apodize_percent': float(getattr(args, 'apodize_percent', 10.0)),
                # --- Spike masking controls (parity with identify/GUI) ---
                'spike_masking': bool(getattr(args, 'spike_masking', True)),
                'spike_floor_z': float(getattr(args, 'spike_floor_z', 50.0)),
                'spike_baseline_window': int(getattr(args, 'spike_baseline_window', 501)),
                'spike_baseline_width': getattr(args, 'spike_baseline_width', None),
                'spike_rel_edge_ratio': float(getattr(args, 'spike_rel_edge_ratio', 2.0)),
                'spike_min_separation': int(getattr(args, 'spike_min_separation', 2)),
                'spike_max_removals': getattr(args, 'spike_max_removals', None),
                'spike_min_abs_resid': getattr(args, 'spike_min_abs_resid', None),
                # --- Analysis parameters needed inside worker processes ---
                'phase1_peak_min_height': float(getattr(args, 'phase1_peak_min_height', 0.3)),
                'phase1_peak_min_distance': int(getattr(args, 'phase1_peak_min_distance', 3)),
                'peak_window_size': int(getattr(args, 'peak_window_size', 10)),
                'max_output_templates': int(getattr(args, 'max_output_templates', 10)),
                'weighted_gmm': bool(getattr(args, 'weighted_gmm', False)),
            }

            # Submit all tasks at once; each task is ~30s so overhead is negligible
            submitted = 0
            processed = 0
            progress_every = max(10, len(items) // 10)  # ~10 updates
            try:
                # Ensure single-thread BLAS in parent before spawning workers
                try:
                    os.environ.setdefault('OMP_NUM_THREADS', '1')
                    os.environ.setdefault('MKL_NUM_THREADS', '1')
                except Exception:
                    pass
                # Use spawn context on POSIX to avoid fork-after-HDF5/MKL hangs
                ctx = mp.get_context('spawn') if os.name != 'nt' else None
                executor_kwargs = dict(
                    max_workers=max_workers,
                    initializer=_mp_worker_initializer,
                    initargs=(template_manager.templates_dir,
                              getattr(args, 'type_filter', None),
                              getattr(args, 'template_filter', None),
                              getattr(args, 'exclude_templates', None),
                              getattr(args, 'profile_id', None))
                )
                if ctx is not None:
                    executor_kwargs['mp_context'] = ctx
                with ProcessPoolExecutor(**executor_kwargs) as ex:
                    collected: List[Tuple[int, Tuple[str, bool, str, Dict[str, Any]]]] = []
                    # Submit work in a bounded window to reduce memory pressure:
                    # - Avoid holding thousands of Future objects/args at once in the parent.
                    # - Keeps steady-state memory ~O(workers) instead of O(n_items).
                    pending = set()
                    item_iter = enumerate(items)
                    window = max(1, int(max_workers) * 2)

                    def _submit_one(idx: int, item: Dict[str, Any]) -> None:
                        nonlocal submitted
                        fut = ex.submit(
                            _mp_process_one,
                            idx,
                            item['path'],
                            item.get('redshift', None),
                            args.output_dir,
                            args_dict
                        )
                        pending.add(fut)
                        submitted += 1

                    # Prime the pipeline
                    try:
                        for _ in range(min(window, len(items))):
                            idx, item = next(item_iter)
                            _submit_one(idx, item)
                    except StopIteration:
                        pass

                    # Drain with backpressure
                    while pending:
                        done, pending = wait(pending, return_when=FIRST_COMPLETED)
                        for fut in done:
                            idx, res = fut.result()
                            collected.append((idx, res))
                            processed += 1

                            # Refill one slot
                            try:
                                nidx, nitem = next(item_iter)
                                _submit_one(nidx, nitem)
                            except StopIteration:
                                pass

                        # Brief per-item one-liner (unordered, as futures complete)
                        if not is_quiet:
                            name, success, message, summary = res
                            if success and isinstance(summary, dict):
                                consensus_type = summary.get('consensus_type', 'Unknown')
                                consensus_subtype = summary.get('consensus_subtype', '')
                                # Preferred z/age from winning subtype; fallback to cluster-weighted; then best-match
                                fields = _format_winning_cli_fields(summary)
                                type_display = fields["type_display"]
                                try:
                                    # Match quality and type confidence flags
                                    if summary.get('has_clustering'):
                                        match_quality = (summary.get('cluster_quality_category', '') or 'N/A')
                                        type_conf = summary.get('cluster_confidence_level', '') or 'N/A'
                                    else:
                                        match_quality = 'N/A'
                                        type_conf = 'N/A'
                                    type_conf = str(type_conf).title() if type_conf else 'N/A'
                                    subtype_conf = summary.get('subtype_confidence_level', None)
                                    subtype_conf = str(subtype_conf).title() if subtype_conf else 'N/A'
                                    flags_str = f" MatchQual={match_quality} TypeConf={type_conf} SubtypeConf={subtype_conf}"
                                    print(
                                        f"[{processed}/{len(items)}] {name}: {type_display} "
                                        f"{fields['z_text']}{fields['age_text']} "
                                        f"{fields['q_cluster_text']}{flags_str}"
                                    )
                                except Exception:
                                    print(f"[{processed}/{len(items)}] {name}: {type_display}")
                            else:
                                # Failure: distinguish no-match vs error
                                if ("No good matches" in message) or ("No templates after filtering" in message):
                                    status = "no-match"
                                    print(f"[{processed}/{len(items)}] {name}: {status}")
                                else:
                                    status = "error"
                                    etype = summary.get('error_type') if isinstance(summary, dict) else None
                                    if etype:
                                        print(f"[{processed}/{len(items)}] {name}: {status} ({etype})")
                                    else:
                                        print(f"[{processed}/{len(items)}] {name}: {status}")

                        # Periodic overall progress (only in non-brief detailed mode)
                        if (not args.verbose) and (not is_quiet) and (not getattr(args, 'no_progress', False)) and (not brief_mode):
                            if (processed % progress_every == 0) or (processed == len(items)):
                                print(f"   Progress: {processed}/{len(items)} ({processed/len(items)*100:.0f}%)")

            except KeyboardInterrupt:
                print("[INFO] Cancellation requested. Shutting down workers...", file=sys.stderr)
                # Executor context manager will handle shutdown
                raise

            # Restore original order by index
            collected_sorted = [res for _, res in sorted(collected, key=lambda x: x[0])]
            results = collected_sorted

            # Count failures; suppress per-item logs in parallel unless explicitly verbose
            for i, (name, success, message, summary) in enumerate(results, 1):
                if not success:
                    failed_count += 1
                    if (not is_quiet) and (args.verbose or getattr(args, 'full', False)):
                        if ("No good matches" in message) or ("No templates after filtering" in message):
                            status = "no-match"
                            print(f"[{i}/{len(input_files)}] {name}: {status}")
                        else:
                            status = "error"
                            etype = summary.get('error_type') if isinstance(summary, dict) else None
                            if etype:
                                print(f"[{i}/{len(input_files)}] {name}: {status} ({etype})")
                            else:
                                print(f"[{i}/{len(input_files)}] {name}: {status}")
                else:
                    if summary and isinstance(summary, dict) and (not is_quiet) and (args.verbose or getattr(args, 'full', False)):
                        consensus_type = summary.get('consensus_type', 'Unknown')
                        consensus_subtype = summary.get('consensus_subtype', '')
                        if summary.get('has_clustering') and 'cluster_redshift_weighted' in summary:
                            redshift = summary['cluster_redshift_weighted']
                            z_marker = "*"
                        else:
                            redshift = summary.get('redshift', 0)
                            z_marker = ""
                        # Report BOTH best metric (HσLAP-CCC preferred) and Q_cluster (penalized top-5).
                        from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
                        best_metric_value = float(get_best_metric_value(summary))
                        best_metric_name = str(get_best_metric_name(summary))
                        q_cluster = summary.get('winning_subtype_penalized_score', None)
                        if not (isinstance(q_cluster, (int, float)) and np.isfinite(q_cluster)):
                            q_cluster = summary.get('cluster_penalized_score', None)
                        type_display = f"{consensus_type} {consensus_subtype}".strip()
                        best_template = str(summary.get('best_template', 'Unknown'))
                        best_template_short = best_template[:18]
                        if brief_mode:
                            # One-liner should reflect the winning-subtype summary, not best-match metric.
                            fields = _format_winning_cli_fields(summary)
                            metric_str = fields["q_cluster_text"]
                            # Preferred subtype z/age
                            z_value = summary.get('winning_subtype_redshift', redshift)
                            age_value = summary.get('winning_subtype_age', summary.get('age', None))
                            # Include z/age with errors (formatted in helper)
                            z_age_txt = f"{fields['z_text']}{fields['age_text']}"
                            # Match quality and type confidence flags
                            if summary.get('has_clustering'):
                                match_quality = (summary.get('cluster_quality_category', '') or 'N/A')
                                type_conf = summary.get('cluster_confidence_level', '') or 'N/A'
                            else:
                                match_quality = 'N/A'
                                type_conf = 'N/A'
                            type_conf = str(type_conf).title() if type_conf else 'N/A'
                            subtype_conf = summary.get('subtype_confidence_level', None)
                            subtype_conf = str(subtype_conf).title() if subtype_conf else 'N/A'
                            flags_str = f" MatchQual={match_quality} TypeConf={type_conf} SubtypeConf={subtype_conf}"
                            print(f"[{i}/{len(input_files)}] {name}: {type_display} {z_age_txt} {metric_str}{flags_str}")
                        else:
                            z_value = summary.get('winning_subtype_redshift', redshift)
                            age_value = summary.get('winning_subtype_age', summary.get('age', None))
                            age_str = f" age={float(age_value):.1f}" if isinstance(age_value, (int, float)) and np.isfinite(age_value) else ""
                            # Match quality and type confidence flags
                            if summary.get('has_clustering'):
                                match_quality = (summary.get('cluster_quality_category', '') or 'N/A')
                                type_conf = summary.get('cluster_confidence_level', '') or 'N/A'
                            else:
                                match_quality = 'N/A'
                                type_conf = 'N/A'
                            type_conf = str(type_conf).title() if type_conf else 'N/A'
                            subtype_conf = summary.get('subtype_confidence_level', None)
                            subtype_conf = str(subtype_conf).title() if subtype_conf else 'N/A'
                            flags_str = f" MatchQual={match_quality} TypeConf={type_conf} SubtypeConf={subtype_conf}"
                            fields = _format_winning_cli_fields(summary)
                            print(
                                f"      {name}: {type_display} "
                                f"{fields['z_text']}{fields['age_text']} {fields['q_cluster_text']}"
                                f"{flags_str} {z_marker}"
                            )
        else:
            # Sequential fallback (current behavior)
            if not is_quiet and not brief_mode:
                print("[INFO] Starting optimized sequential processing...")

            for i, item in enumerate(items, 1):
                spectrum_path = item["path"]
                per_row_forced_z = item.get("redshift", None)
                is_tty = sys.stdout.isatty()
                show_progress = (not args.verbose) and (not is_quiet) and (not getattr(args, 'no_progress', False)) and is_tty
                if args.verbose and not brief_mode:
                    print(f"[{i:3d}/{len(input_files):3d}] {Path(spectrum_path).name}")
                else:
                    if show_progress and (i % 10 == 0 or i == len(input_files)) and not brief_mode:
                        print(f"   Progress: {i}/{len(input_files)} ({i/len(input_files)*100:.0f}%)")

                name, success, message, summary = process_single_spectrum_optimized(
                    spectrum_path, template_manager, args.output_dir, args,
                    forced_redshift_override=per_row_forced_z
                )

                results.append((name, success, message, summary))

                if not success:
                    failed_count += 1
                    if brief_mode and not is_quiet:
                        if ("No good matches" in message) or ("No templates after filtering" in message):
                            status = "no-match"
                            print(f"[{i}/{len(input_files)}] {name}: {status}")
                        else:
                            status = "error"
                            etype = summary.get('error_type') if isinstance(summary, dict) else None
                            if etype:
                                print(f"[{i}/{len(input_files)}] {name}: {status} ({etype})")
                            else:
                                print(f"[{i}/{len(input_files)}] {name}: {status}")
                    else:
                        if "No good matches" in message or "No templates after filtering" in message:
                            if not is_quiet:
                                print(f"      {name}: No good matches found")
                        else:
                            if not is_quiet:
                                etype = summary.get('error_type') if isinstance(summary, dict) else None
                                if etype:
                                    print(f"      [ERROR] {name}: {message} [{etype}]")
                                else:
                                    print(f"      [ERROR] {name}: {message}")
                    if args.stop_on_error:
                        if not is_quiet and not brief_mode:
                            print("Stopping due to error.")
                        break
                else:
                    if summary and isinstance(summary, dict) and not is_quiet:
                        consensus_type = summary.get('consensus_type', 'Unknown')
                        consensus_subtype = summary.get('consensus_subtype', '')
                        if summary.get('has_clustering') and 'cluster_redshift_weighted' in summary:
                            redshift = summary['cluster_redshift_weighted']
                            z_marker = "*"
                        else:
                            redshift = summary.get('redshift', 0)
                            z_marker = ""
                        from snid_sage.shared.utils.math_utils import get_best_metric_value, get_best_metric_name
                        best_metric_value = get_best_metric_value(summary)
                        best_metric_name = get_best_metric_name(summary)
                        type_display = f"{consensus_type} {consensus_subtype}".strip()
                        if brief_mode:
                            # Align sequential one-liner with the parallel-mode one-liner:
                            # prefer winning-subtype redshift/age when available, then cluster-weighted, then best-match.
                            fields = _format_winning_cli_fields(summary)
                            metric_str = fields["q_cluster_text"]
                            weak_note = " (weak)" if summary.get('weak_match') else ""

                            # Match quality and confidence flags (same rules as parallel branch)
                            try:
                                if summary.get('has_clustering'):
                                    match_quality = (summary.get('cluster_quality_category', '') or 'N/A')
                                    type_conf = summary.get('cluster_confidence_level', '') or 'N/A'
                                else:
                                    match_quality = 'N/A'
                                    type_conf = 'N/A'
                                type_conf = str(type_conf).title() if type_conf else 'N/A'
                                subtype_conf = summary.get('subtype_confidence_level', None)
                                subtype_conf = str(subtype_conf).title() if subtype_conf else 'N/A'
                                flags_str = f" MatchQual={match_quality} TypeConf={type_conf} SubtypeConf={subtype_conf}"
                            except Exception:
                                flags_str = ""

                            print(
                                f"[{i}/{len(input_files)}] {name}: {type_display}{weak_note} "
                                f"{fields['z_text']}{fields['age_text']} {metric_str}{flags_str}"
                            )
                        else:
                            weak_note = " (weak)" if summary.get('weak_match') else ""
                            print(f"      {name}: {type_display}{weak_note} z={float(redshift):.6f} {best_metric_name}={best_metric_value:.2f} {z_marker}")
        
        # Results summary
        successful_count = len(results) - failed_count
        success_rate = successful_count / len(results) * 100 if results else 0
        
        if not is_quiet:
            if brief_mode:
                print(f"Done {successful_count}/{len(results)}; success rate {success_rate:.1f}%")
            else:
                print(f"\nCompleted: {success_rate:.1f}% success ({successful_count}/{len(results)})")

        # Generate summary report (use wall-clock time for correct parallel stats)
        summary_path = output_dir / "batch_analysis_report.txt"
        if not is_quiet and not brief_mode:
            print("Generating summary report...")

        # Compute wall-clock elapsed time from first template load to now
        try:
            wall_elapsed = time.time() - start_time
        except Exception:
            wall_elapsed = None

        summary_report = generate_summary_report(results, args, wall_elapsed_seconds=wall_elapsed)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_report)

        if not is_quiet and not brief_mode:
            print(f"[SUCCESS] Summary report: {summary_path}")

        # Export tabular results (CSV only)
        csv_file = _export_results_table(results, output_dir)
        if not is_quiet and csv_file:
            print(f"Results table (CSV): {csv_file}")

        # Show what was created
        if not is_quiet and not brief_mode and not args.minimal and successful_count > 0:
            print(f"Individual results in: {output_dir}/")
            if args.complete:
                print("   3D Plots: Static PNG files with optimized viewing angle")
                print("   Top 5 templates: Sorted by Q_cluster (weighted top-5 metric, highest quality first)")
            
        return 0 if failed_count == 0 else 1
        
    except Exception as e:
        print(f"[ERROR] Error: {e}", file=sys.stderr)
        return 1 