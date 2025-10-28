"""
Template Service (HDF5-only)
============================

Centralized service for HDF5-only template storage and index management.

Responsibilities:
- Manage a user-writable template library in the user's config directory
  (e.g., `<config_dir>/templates/User_templates/`)
- Append templates to per-type HDF5 files (rebinned to the standard grid)
- Maintain a user index (`template_index.user.json`) and merge with built-in index
- Provide a small API for the GUI (creator, browser, manager)

Notes:
- Legacy .lnw support is intentionally removed. All new templates are written
  directly to HDF5 and indexed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json
import threading
from importlib import resources
import os

import numpy as np
import h5py

try:
    # Profile registry is available in core
    from snid_sage.shared.profiles.registry import get_profile
except Exception:  # pragma: no cover - defensive import
    get_profile = None  # type: ignore

def _compute_builtin_dir() -> Path:
    """Resolve the packaged templates directory robustly (installed or dev)."""
    # Prefer importlib.resources traversal of the installed package
    try:
        with resources.as_file(resources.files('snid_sage') / 'templates') as tpl_dir:
            if tpl_dir.exists():
                return tpl_dir
    except Exception:
        pass
    # Fallback: use the repo-relative path for editable installs
    try:
        return Path(__file__).resolve().parents[3] / "templates"
    except Exception:
        return Path("snid_sage/templates").resolve()


_BUILTIN_DIR = _compute_builtin_dir()
from snid_sage.shared.utils.paths.user_templates import get_user_templates_dir

def _user_index_path() -> Optional[Path]:
    p = get_user_templates_dir(strict=True)
    return (p / "template_index.user.json") if p else None

_USER_INDEX = _user_index_path()
_BUILTIN_INDEX = _BUILTIN_DIR / "template_index.json"


@dataclass
class StandardGrid:
    num_points: int = 1024
    min_wave: float = 2500.0
    max_wave: float = 10000.0

    @property
    def dlog(self) -> float:
        return float(np.log(self.max_wave / self.min_wave) / self.num_points)

    def wavelength(self) -> np.ndarray:
        # Same construction used by TemplateFFTStorage
        idx = np.arange(self.num_points) + 0.5
        return self.min_wave * np.exp(idx * self.dlog)


class TemplateService:
    """
    HDF5-only template service.

    Thread-safe for write operations via an internal lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Do not auto-create user template directories; user must select a valid folder
        # Active profile and derived standard grid
        self._active_profile_id: str = 'optical'
        self._standard_grid = StandardGrid()
        self._standard_wave = self._standard_grid.wavelength()
        try:
            self._apply_profile(self._active_profile_id)
        except Exception:
            # Fall back to default optical-like grid if registry not available
            self._standard_grid = StandardGrid()
            self._standard_wave = self._standard_grid.wavelength()

    # ---- Profile selection ----
    def set_active_profile(self, profile_id: str) -> None:
        pid = (profile_id or 'optical').strip().lower()
        if pid == self._active_profile_id:
            return
        self._apply_profile(pid)

    def get_active_profile(self) -> str:
        return self._active_profile_id

    def _apply_profile(self, profile_id: str) -> None:
        """Apply profile by updating the standard grid and wavelength vector."""
        if get_profile is None:
            # Registry unavailable; keep defaults
            self._active_profile_id = (profile_id or 'optical')
            return
        prof = get_profile(profile_id)
        # Derive grid from profile
        self._standard_grid = StandardGrid(
            num_points=int(getattr(prof.grid, 'nw', 1024)),
            min_wave=float(getattr(prof.grid, 'min_wave_A', 2500.0)),
            max_wave=float(getattr(prof.grid, 'max_wave_A', 10000.0)),
        )
        self._standard_wave = self._standard_grid.wavelength()
        self._active_profile_id = prof.id

    # ---- Public API ----
    def get_merged_index(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """Return the merged built-in + user index for the GUI browser.

        If profile_id is provided, filter entries to that profile.
        """
        builtin = self.get_builtin_index(profile_id=profile_id)
        user = self.get_user_index(profile_id=profile_id)

        merged_templates: Dict[str, Any] = {}
        merged_templates.update((builtin.get("templates") or {}))
        merged_templates.update((user.get("templates") or {}))

        # Recompute by_type from merged templates
        by_type: Dict[str, Any] = {}
        for name, meta in merged_templates.items():
            ttype = meta.get("type", "Unknown")
            bucket = by_type.setdefault(ttype, {"count": 0, "storage_file": meta.get("storage_file", ""), "template_names": []})
            bucket["count"] += 1
            bucket["template_names"].append(name)
            if not bucket.get("storage_file") and meta.get("storage_file"):
                bucket["storage_file"] = meta["storage_file"]

        return {
            "version": user.get("version") or builtin.get("version") or "2.0",
            "template_count": len(merged_templates),
            "templates": merged_templates,
            "by_type": by_type,
        }

    def get_user_templates_dir(self) -> Optional[str]:
        """Return absolute path to the active user templates directory or None if unset."""
        p = get_user_templates_dir(strict=True)
        return str(p) if p else None

    def get_builtin_index(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """Return built-in index from packaged optical and ONIR banks, merged.

        When profile_id is provided, filter entries to that profile.
        """
        # Load optical index
        optical = self._read_json(_BUILTIN_INDEX) or {
            "version": "2.0",
            "template_count": 0,
            "templates": {},
            "by_type": {},
        }
        # Load ONIR index if present
        onir_idx_path = self._compute_onir_index_path()
        onir = self._read_json(onir_idx_path) if onir_idx_path is not None else None
        if not isinstance(onir, dict):
            onir = {"templates": {}, "by_type": {}, "template_count": 0}

        # Tag entries with profile_id if missing
        def _tag(templates: Dict[str, Any], pid: str) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for k, v in (templates or {}).items():
                meta = dict(v or {})
                if not meta.get('profile_id'):
                    meta['profile_id'] = pid
                out[k] = meta
            return out

        optical_templates = _tag(optical.get('templates', {}), 'optical')
        onir_templates = _tag(onir.get('templates', {}), 'onir')

        merged_templates: Dict[str, Any] = {}
        merged_templates.update(optical_templates)
        merged_templates.update(onir_templates)

        # Optional filtering by profile
        if profile_id is not None:
            req = (profile_id or '').strip().lower()
            merged_templates = {k: v for k, v in merged_templates.items() if (v or {}).get('profile_id', '').lower() == req}

        # Recompute by_type summary
        by_type = self._compute_by_type(merged_templates)

        return {
            "version": optical.get("version") or onir.get("version") or "2.0",
            "template_count": len(merged_templates),
            "templates": merged_templates,
            "by_type": by_type,
        }

    def get_user_index(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """Return only the user index; optionally filtered by profile.

        For legacy entries missing profile_id, infer by HDF5 grid metadata.
        """
        idx_path = _user_index_path()
        data = self._read_json(idx_path) or {
            "version": "2.0",
            "template_count": 0,
            "templates": {},
            "by_type": {},
        }
        templates: Dict[str, Any] = dict((data.get('templates') or {}))

        # If filtering by profile, include only matching entries (using inference when missing)
        if profile_id is not None:
            req = (profile_id or '').strip().lower()
            # Cache storage_file -> inferred_profile
            storage_to_profile: Dict[str, Optional[str]] = {}
            def infer(nm: str, meta: Dict[str, Any]) -> Optional[str]:
                if not isinstance(meta, dict):
                    return None
                pid = (meta.get('profile_id') or '').strip().lower()
                if pid:
                    return pid
                sf = str(meta.get('storage_file', '')).strip()
                if not sf:
                    return None
                if sf in storage_to_profile:
                    return storage_to_profile[sf]
                storage_to_profile[sf] = self._infer_profile_from_h5(Path(sf))
                return storage_to_profile[sf]

            filtered: Dict[str, Any] = {}
            for name, meta in templates.items():
                ipid = infer(name, meta)
                if (ipid or '') == req:
                    # ensure the returned meta includes profile_id
                    mm = dict(meta or {})
                    mm['profile_id'] = ipid
                    filtered[name] = mm
            templates = filtered

        by_type = self._compute_by_type(templates)
        return {
            "version": data.get("version") or "2.0",
            "template_count": len(templates),
            "templates": templates,
            "by_type": by_type,
        }

    def has_user_templates(self) -> bool:
        """Return True if any user templates exist."""
        idx_path = _user_index_path()
        data = self._read_json(idx_path) or {}
        templates = (data.get("templates") or {})
        return bool(templates)

    def add_template_from_arrays(
        self,
        *,
        name: str,
        ttype: str,
        subtype: str,
        age: float,
        redshift: float,
        wave: np.ndarray,
        flux: np.ndarray,
        combine_only: bool = False,
        target_dir: Optional[Path] = None,
        sim_flag: Optional[int] = None,
        profile_id: Optional[str] = None,
    ) -> bool:
        """
        Append a template to the per-type user HDF5 and update the user index.
        Data are rebinned to the standard grid and FFT is precomputed.
        """
        if not isinstance(wave, np.ndarray) or not isinstance(flux, np.ndarray):
            return False
        if wave.size == 0 or flux.size == 0:
            return False
        try:
            # Resolve target profile/grid without mutating global state
            target_profile_id = (profile_id or self._active_profile_id or 'optical')
            target_grid = self._grid_for_profile(target_profile_id)

            with self._lock:
                h5_abs_path = self._ensure_user_h5_for_type(ttype, target_dir=target_dir, profile_id=target_profile_id, grid=target_grid)

                # Rebin to the target grid
                rebinned_flux = self._rebin_to_standard_grid(wave, flux, grid=target_grid)
                fft = np.fft.fft(rebinned_flux)

                # Write (append/combine or create) to HDF5
                final_name, combined, epochs_count, status = self._append_to_h5(
                    h5_abs_path,
                    name,
                    ttype,
                    subtype,
                    age,
                    redshift,
                    rebinned_flux,
                    fft,
                    allow_suffix=(not combine_only),
                    sim_flag=(int(sim_flag) if sim_flag is not None else None),
                )
                if combine_only and not combined:
                    # Do not create a suffixed template when explicitly adding to existing
                    return False

                # Update user index (omit non-essential fields like phase/age/rebinned)
                # Determine index path (override when target_dir provided)
                idx_path = self._index_path_for_target(target_dir)
                index = self._read_json(idx_path) or {
                    "version": "2.0",
                    "templates": {},
                    "by_type": {},
                    "template_count": 0,
                }
                index_templates = index.setdefault("templates", {})
                if combined and final_name in index_templates:
                    # Update epochs count; preserve existing metadata, enforce storage_file
                    entry = index_templates[final_name]
                    entry["epochs"] = int(epochs_count)
                    entry["storage_file"] = str(h5_abs_path).replace("\\", "/")
                    if sim_flag is not None:
                        entry["sim_flag"] = int(sim_flag)
                else:
                    index_templates[final_name] = {
                        "type": ttype,
                        "subtype": subtype,
                        "redshift": float(redshift),
                        "epochs": 1 if not combined else int(epochs_count),
                        "storage_file": str(h5_abs_path).replace("\\", "/"),
                        "profile_id": target_profile_id,
                    }
                    if sim_flag is not None:
                        index_templates[final_name]["sim_flag"] = int(sim_flag)

                # Recompute by_type summary
                index["by_type"] = self._compute_by_type(index_templates)
                index["template_count"] = len(index_templates)

                if idx_path is not None:
                    self._write_json_atomic(idx_path, index)
            return True
        except Exception:
            return False

    def update_metadata(self, name: str, changes: Dict[str, Any]) -> bool:
        """Update metadata attributes for a user template and its index entry."""
        try:
            with self._lock:
                idx_path = _user_index_path()
                index = self._read_json(idx_path) or {}
                tmpl = (index.get("templates") or {}).get(name)
                if not tmpl:
                    return False  # only user templates can be edited
                storage_abs = Path(tmpl.get("storage_file", ""))
                if not storage_abs:
                    return False
                if not storage_abs.exists():
                    return False
                # Update HDF5 attrs
                with h5py.File(storage_abs, "a") as f:
                    g = f["templates"].get(name)
                    if g is None:
                        return False
                    for k, v in changes.items():
                        if k in {"type", "subtype"} and isinstance(v, str):
                            g.attrs[k] = v
                        elif k in {"age", "redshift"}:
                            try:
                                g.attrs[k] = float(v)
                            except Exception:
                                pass
                # Update index entry (omit phase/age which are HDF5-only)
                for k in ["type", "subtype", "redshift"]:
                    if k in changes:
                        tmpl[k] = changes[k]
                # Write back
                index["by_type"] = self._compute_by_type(index.get("templates", {}))
                if idx_path is not None:
                    self._write_json_atomic(idx_path, index)
            return True
        except Exception:
            return False

    def delete(self, name: str) -> bool:
        """Delete a user template group and its index entry."""
        try:
            with self._lock:
                idx_path = _user_index_path()
                index = self._read_json(idx_path) or {}
                templates = index.get("templates") or {}
                meta = templates.get(name)
                # If missing in index, try to find and delete from any user H5
                storage_abs = None
                if meta:
                    storage_abs = Path(meta.get("storage_file", "")).resolve()
                else:
                    user_dir = get_user_templates_dir(strict=True)
                    if not user_dir:
                        return False
                    for h5_path in (user_dir.glob("templates_*.user.hdf5")):
                        try:
                            with h5py.File(h5_path, "r") as f:
                                if "templates" in f and name in f["templates"]:
                                    storage_abs = h5_path.resolve()
                                    break
                        except Exception:
                            continue
                    if storage_abs is None:
                        return False
                if not storage_abs.exists():
                    return False
                with h5py.File(storage_abs, "a") as f:
                    tgroup = f["templates"]
                    if name in tgroup:
                        del tgroup[name]
                        try:
                            m = f["metadata"]
                            m.attrs["template_count"] = max(0, int(m.attrs.get("template_count", 1)) - 1)
                        except Exception:
                            pass
                    # After deletion, if no templates remain, close file and delete it
                    try:
                        remaining = len(f["templates"].keys())
                    except Exception:
                        remaining = 0
                # Remove from index
                if meta:
                    templates.pop(name, None)
                    index["by_type"] = self._compute_by_type(templates)
                    index["template_count"] = len(templates)
                    if idx_path is not None:
                        self._write_json_atomic(idx_path, index)
                # Delete empty H5 file and rebuild index if needed
                if storage_abs.exists():
                    try:
                        with h5py.File(storage_abs, "r") as fchk:
                            empty_now = ("templates" in fchk and len(fchk["templates"].keys()) == 0)
                    except Exception:
                        empty_now = False
                    if empty_now:
                        try:
                            storage_abs.unlink()
                        except Exception:
                            pass
                        # Rebuild user index to drop references to deleted file
                        try:
                            self.rebuild_user_index()
                        except Exception:
                            pass
            return True
        except Exception:
            return False

    def cleanup_unused(self, delete_empty_files: bool = True) -> Dict[str, int]:
        """Remove H5 template groups not referenced in the user index.

        Returns a summary: {"removed_groups": int, "deleted_files": int}
        """
        summary = {"removed_groups": 0, "deleted_files": 0}
        try:
            with self._lock:
                idx_path = _user_index_path()
                index = self._read_json(idx_path) or {"templates": {}}
                referenced = set((index.get("templates") or {}).keys())
                user_dir = get_user_templates_dir(strict=True)
                if not user_dir:
                    return summary
                for h5_path in (user_dir.glob("templates_*.user.hdf5")):
                    removed_here = 0
                    try:
                        with h5py.File(h5_path, "a") as f:
                            if "templates" not in f:
                                continue
                            tgroup = f["templates"]
                            # Collect unreferenced groups
                            names = list(tgroup.keys())
                            for nm in names:
                                if nm not in referenced:
                                    del tgroup[nm]
                                    removed_here += 1
                            if removed_here:
                                try:
                                    m = f["metadata"]
                                    m.attrs["template_count"] = max(0, int(m.attrs.get("template_count", 0)) - removed_here)
                                except Exception:
                                    pass
                    except Exception:
                        continue
                    summary["removed_groups"] += removed_here
                    # Optionally delete file if empty
                    if delete_empty_files and h5_path.exists():
                        try:
                            with h5py.File(h5_path, "r") as fchk:
                                is_empty = ("templates" in fchk and len(fchk["templates"].keys()) == 0)
                        except Exception:
                            is_empty = False
                        if is_empty:
                            try:
                                h5_path.unlink()
                                summary["deleted_files"] += 1
                            except Exception:
                                pass
                # Rebuild index to reflect cleanup
                self.rebuild_user_index()
        except Exception:
            return summary
        return summary

    # Cleanup helpers were removed after one-time migration

    def rename(self, old_name: str, new_name: str) -> bool:
        """Renaming/duplication is disabled for built-in or user templates by policy."""
        return False

    def duplicate(self, name: str, new_name: str) -> bool:
        """Duplication is disabled by policy."""
        return False

    def rebuild_user_index(self) -> bool:
        """Re-scan user HDF5 files and rebuild the user index from scratch."""
        try:
            templates: Dict[str, Any] = {}
            user_dir = get_user_templates_dir(strict=True)
            if not user_dir:
                return False
            for h5_path in (user_dir.glob("templates_*.user.hdf5")):
                with h5py.File(h5_path, "r") as f:
                    if "templates" not in f:
                        continue
                    tg = f["templates"]
                    for name in tg.keys():
                        g = tg[name]
                        attrs = dict(g.attrs)
                        templates[name] = {
                            "type": attrs.get("type", "Unknown"),
                            "subtype": attrs.get("subtype", "Unknown"),
                            "redshift": float(attrs.get("redshift", 0.0)),
                            "epochs": int(attrs.get("epochs", 1)),
                            "storage_file": str(h5_path).replace("\\", "/"),
                        }
            index = {
                "version": "2.0",
                "templates": templates,
                "by_type": self._compute_by_type(templates),
                "template_count": len(templates),
            }
            with self._lock:
                idx_path = _user_index_path()
                if idx_path is None:
                    return False
                self._write_json_atomic(idx_path, index)
            return True
        except Exception:
            return False

    # ---- Internals ----
    def _rebin_to_standard_grid(self, wave: np.ndarray, flux: np.ndarray, *, grid: Optional[StandardGrid] = None) -> np.ndarray:
        """Rebin flux onto the (optionally provided) standard logarithmic grid by interpolation in log space."""
        # Guard inputs
        wave = np.asarray(wave, dtype=float)
        flux = np.asarray(flux, dtype=float)
        # Enforce strictly positive wavelengths
        mask = np.isfinite(wave) & np.isfinite(flux) & (wave > 0)
        wave, flux = wave[mask], flux[mask]
        if wave.size < 2:
            # Not enough data to interpolate; pad with median
            out = np.full(self._standard_wave.shape, np.median(flux) if flux.size else 0.0, dtype=float)
            return out
        # Interpolate flux in log-lambda domain
        logw = np.log(wave)
        g = grid or self._standard_grid
        target_wave = StandardGrid(g.num_points, g.min_wave, g.max_wave).wavelength()
        target_logw = np.log(target_wave)
        # Use linear interpolation in log space; out-of-bounds filled with nearest value
        rebinned = np.interp(target_logw, logw, flux, left=float(flux[0]), right=float(flux[-1]))
        # Normalize by median to emulate flattened spectra expectation
        med = float(np.median(rebinned)) if rebinned.size else 1.0
        if med != 0.0 and np.isfinite(med):
            rebinned = rebinned / med
        return rebinned.astype(float, copy=False)

    def _ensure_user_h5_for_type(self, ttype: str, *, target_dir: Optional[Path] = None, profile_id: Optional[str] = None, grid: Optional[StandardGrid] = None) -> Path:
        """Ensure the per-type HDF5 exists in the selected target or user config dir; return absolute path.

        Writes profile/grid metadata when creating a new file.
        """
        safe_type = ttype.replace("/", "_").replace("-", "_").replace(" ", "_")
        base_dir: Optional[Path] = None
        if target_dir is not None:
            base_dir = Path(target_dir)
        else:
            base_dir = get_user_templates_dir(strict=True)
        if base_dir is None:
            raise RuntimeError("Templates destination is not set. Configure a User Templates folder or select a destination.")
        abs_path = Path(base_dir) / f"templates_{safe_type}.user.hdf5"
        if not abs_path.exists():
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            with h5py.File(abs_path, "w") as f:
                meta = f.create_group("metadata")
                # Use provided grid if any, otherwise current standard grid
                g = grid or self._standard_grid
                meta.attrs["version"] = "2.0"
                meta.attrs["created_date"] = float(np.floor(np.datetime64("now").astype("datetime64[s]").astype(int)))
                meta.attrs["template_count"] = 0
                meta.attrs["supernova_type"] = ttype
                meta.attrs["grid_rebinned"] = True
                meta.attrs["NW"] = g.num_points
                meta.attrs["W0"] = g.min_wave
                meta.attrs["W1"] = g.max_wave
                meta.attrs["DWLOG"] = g.dlog
                # Persist profile id for the storage file
                meta.attrs["profile_id"] = (profile_id or self._active_profile_id or 'optical')
                # Create standard wavelength array for this grid
                wave = StandardGrid(g.num_points, g.min_wave, g.max_wave).wavelength()
                meta.create_dataset("standard_wavelength", data=wave)
                f.create_group("templates")
        return abs_path

    def _append_to_h5(
        self,
        h5_path: Path,
        name: str,
        ttype: str,
        subtype: str,
        age: float,
        redshift: float,
        flux: np.ndarray,
        fft: np.ndarray,
        allow_suffix: bool = True,
        sim_flag: Optional[int] = None,
    ) -> tuple[str, bool, int, str]:
        """Append or combine into an existing template group if same name and redshift.

        Returns (final_name, combined, epochs_count)
        """
        with h5py.File(h5_path, "a") as f:
            templates_group = f["templates"]
            # Combine if same name exists and redshift matches
            if name in templates_group:
                g = templates_group[name]
                try:
                    existing_z = float(g.attrs.get("redshift", float("nan")))
                except Exception:
                    existing_z = float("nan")
                if np.isfinite(existing_z) and abs(existing_z - float(redshift)) < 1e-6:
                    # Multi-epoch combine (only if no duplicate epoch age)
                    # Check duplicate ages (tolerance)
                    age_tol = 1e-3
                    duplicate_age = False
                    existing_ages: list[float] = []
                    try:
                        if "epochs" in g:
                            for ek in g["epochs"].keys():
                                try:
                                    existing_ages.append(float(g["epochs"][ek].attrs.get("age", float("nan"))))
                                except Exception:
                                    continue
                        else:
                            existing_ages.append(float(g.attrs.get("age", float("nan"))))
                    except Exception:
                        existing_ages = []
                    try:
                        for ea in existing_ages:
                            if np.isfinite(ea) and abs(ea - float(age)) < age_tol:
                                duplicate_age = True
                                break
                    except Exception:
                        duplicate_age = False
                    if not duplicate_age:
                        # Ensure epochs group exists, move current data if needed
                        if "epochs" not in g:
                            eg = g.create_group("epochs")
                            eg0 = eg.create_group("epoch_0")
                            eg0.create_dataset("flux", data=g["flux"][:])
                            eg0.create_dataset("fft_real", data=g["fft_real"][:])
                            eg0.create_dataset("fft_imag", data=g["fft_imag"][:])
                            eg0.attrs["age"] = float(g.attrs.get("age", 0.0))
                            eg0.attrs["rebinned"] = True
                        # Append new epoch
                        eg = g["epochs"]
                        new_epoch_idx = len(list(eg.keys()))
                        egn = eg.create_group(f"epoch_{new_epoch_idx}")
                        egn.create_dataset("flux", data=flux)
                        egn.create_dataset("fft_real", data=np.asarray(fft.real))
                        egn.create_dataset("fft_imag", data=np.asarray(fft.imag))
                        egn.attrs["age"] = float(age)
                        egn.attrs["rebinned"] = True
                        if sim_flag is not None:
                            try:
                                egn.attrs["sim_flag"] = int(sim_flag)
                            except Exception:
                                pass
                        # Update epochs count and latest age
                        g.attrs["epochs"] = new_epoch_idx + 1
                        g.attrs["age"] = float(age)
                        if sim_flag is not None:
                            try:
                                g.attrs["sim_flag"] = int(sim_flag)
                            except Exception:
                                pass
                        # Keep top-level flux/fft as last epoch for compatibility
                        try:
                            del g["flux"]
                            del g["fft_real"]
                            del g["fft_imag"]
                        except Exception:
                            pass
                        g.create_dataset("flux", data=flux)
                        g.create_dataset("fft_real", data=np.asarray(fft.real))
                        g.create_dataset("fft_imag", data=np.asarray(fft.imag))
                    return name, True, int(g.attrs.get("epochs", 1)), "combined"
                    # else: fall through to create a suffixed new template name
                else:
                    # z mismatch
                    if not allow_suffix:
                        return name, False, 0, "z_mismatch"
            # Otherwise, create new (handle name collision by suffixing)
            final_name = name
            suffix = 1
            while final_name in templates_group:
                if not allow_suffix:
                    return name, False, 0, "name_taken"
                final_name = f"{name}_{suffix}"
                suffix += 1
            g = templates_group.create_group(final_name)
            g.create_dataset("flux", data=flux)
            g.create_dataset("fft_real", data=np.asarray(fft.real))
            g.create_dataset("fft_imag", data=np.asarray(fft.imag))
            g.attrs["type"] = ttype
            g.attrs["subtype"] = subtype
            g.attrs["age"] = float(age)
            g.attrs["redshift"] = float(redshift)
            g.attrs["epochs"] = 1
            g.attrs["rebinned"] = True
            try:
                g.attrs["profile_id"] = self._active_profile_id
            except Exception:
                pass
            if sim_flag is not None:
                try:
                    g.attrs["sim_flag"] = int(sim_flag)
                except Exception:
                    pass
            # bump count
            meta = f["metadata"]
            try:
                meta.attrs["template_count"] = int(meta.attrs.get("template_count", 0)) + 1
            except Exception:
                meta.attrs["template_count"] = 1
            return final_name, False, 1, "created"

    def _index_path_for_target(self, target_dir: Optional[Path]) -> Optional[Path]:
        """Return the index path for the selected destination or the configured user folder."""
        if target_dir is not None:
            try:
                base = Path(target_dir)
                return base / "template_index.user.json"
            except Exception:
                return _user_index_path()
        return _user_index_path()

    def _compute_by_type(self, templates: Dict[str, Any]) -> Dict[str, Any]:
        by_type: Dict[str, Any] = {}
        for name, meta in templates.items():
            ttype = meta.get("type", "Unknown")
            bucket = by_type.setdefault(ttype, {"count": 0, "storage_file": meta.get("storage_file", ""), "template_names": []})
            bucket["count"] += 1
            bucket["template_names"].append(name)
            if not bucket.get("storage_file") and meta.get("storage_file"):
                bucket["storage_file"] = meta["storage_file"]
        return by_type

    # ---- Helpers for profile-aware operations ----
    def _grid_for_profile(self, profile_id: str) -> StandardGrid:
        if get_profile is None:
            return self._standard_grid
        prof = get_profile(profile_id)
        return StandardGrid(
            num_points=int(getattr(prof.grid, 'nw', self._standard_grid.num_points)),
            min_wave=float(getattr(prof.grid, 'min_wave_A', self._standard_grid.min_wave)),
            max_wave=float(getattr(prof.grid, 'max_wave_A', self._standard_grid.max_wave)),
        )

    def _compute_onir_index_path(self) -> Optional[Path]:
        """Return path to packaged ONIR index if available."""
        try:
            with resources.as_file(resources.files('snid_sage') / 'templates_onir') as tpl_dir:
                idx = tpl_dir / 'template_index.json'
                if idx.exists():
                    return idx
        except Exception:
            pass
        # Fallback to repo-relative path
        try:
            p = Path(__file__).resolve().parents[3] / 'templates_onir' / 'template_index.json'
            return p if p.exists() else None
        except Exception:
            return None

    def _infer_profile_from_h5(self, h5_path: Path) -> Optional[str]:
        """Infer profile id by comparing grid metadata to known profiles."""
        try:
            if not h5_path.exists():
                return None
            with h5py.File(h5_path, 'r') as f:
                meta = f.get('metadata')
                if meta is None:
                    return None
                # Prefer explicit attribute
                try:
                    pid = meta.attrs.get('profile_id')
                    if isinstance(pid, (str, bytes)):
                        return (pid.decode() if isinstance(pid, bytes) else pid)
                except Exception:
                    pass
                nw = int(meta.attrs.get('NW', self._standard_grid.num_points))
                w0 = float(meta.attrs.get('W0', self._standard_grid.min_wave))
                w1 = float(meta.attrs.get('W1', self._standard_grid.max_wave))
            # Compare against optical and onir grids
            def eq(a: float, b: float) -> bool:
                return abs(a - b) <= max(1e-6, 1e-6 * max(abs(a), abs(b)))
            candidates = ['optical', 'onir']
            for pid in candidates:
                try:
                    g = self._grid_for_profile(pid)
                except Exception:
                    continue
                if nw == g.num_points and eq(w0, g.min_wave) and eq(w1, g.max_wave):
                    return pid
            return None
        except Exception:
            return None

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return None
        return None

    @staticmethod
    def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)


# Global singleton
_template_service: Optional[TemplateService] = None


def get_template_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service


