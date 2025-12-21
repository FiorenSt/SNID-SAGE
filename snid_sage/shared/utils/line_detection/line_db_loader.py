"""
JSON Line Database Loader and Query Helpers
=========================================

Loads the packaged database at `snid_sage/lines/line_database.json` and
exposes helpers to filter lines by SN type, phase label, category, and
origin. Results are designed to be drop-in for plotting overlays: each
line dict contains `key`, `wavelength_air`, `wavelength_vacuum`,
`category`, `origin`, `sn_types`, and `phase_profiles`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable, Set
import json
import threading


_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Any] | None = None
_SOURCE_PATH: Path | None = None

# Optional config manager to locate user-config directory
try:
    from snid_sage.shared.utils.config.configuration_manager import config_manager  # type: ignore
except Exception:
    config_manager = None  # type: ignore


def _default_db_path() -> Path:
    """Return the default DB path, preferring a user override if present.

    Order of preference:
    1) <config_dir>/lines/line_database_user.json (if exists)
    2) <cwd>/config/lines/line_database_user.json (if exists)
    3) packaged default at snid_sage/lines/line_database.json
    """
    # 1) User override under the configured app config directory
    try:
        if config_manager is not None and getattr(config_manager, "config_dir", None):
            user_dir = Path(config_manager.config_dir) / "lines"
            user_path = user_dir / "line_database_user.json"
            if user_path.exists():
                return user_path
    except Exception:
        # Fall through to repo default if anything goes wrong
        pass

    # 2) CWD-level user override (fallback if config manager is not available)
    try:
        cwd_user_path = Path.cwd() / "config" / "lines" / "line_database_user.json"
        if cwd_user_path.exists():
            return cwd_user_path
    except Exception:
        pass

    # 3) Packaged default within the installed package
    try:
        # snid_sage/lines/line_database.json relative to this file
        return Path(__file__).resolve().parents[3] / "lines" / "line_database.json"
    except Exception:
        # Final fallback to repo path (for editable installs during transition)
        return Path("config") / "lines" / "line_database.json"


def load_database(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the JSON database once and cache it."""
    global _CACHE, _SOURCE_PATH
    with _CACHE_LOCK:
        if _CACHE is None:
            src = path or _default_db_path()
            _SOURCE_PATH = src
            with src.open("r", encoding="utf-8") as f:
                _CACHE = json.load(f)
        return _CACHE  # type: ignore[return-value]


def reload_database() -> Dict[str, Any]:
    """Force reload from the last source path or default."""
    global _CACHE, _SOURCE_PATH
    with _CACHE_LOCK:
        _CACHE = None
        # Reset source to allow reevaluating default path (may switch to user override)
        _SOURCE_PATH = None
        return load_database()


def get_all_lines() -> List[Dict[str, Any]]:
    db = load_database()
    return list(db.get("lines", []))


def get_anchors() -> Dict[str, str]:
    db = load_database()
    phase_system = db.get("phase_system", {})
    return dict(phase_system.get("anchors", {}))


def get_categories() -> Dict[str, Dict[str, str]]:
    """Return category metadata mapping: {name: {description, color}}."""
    db = load_database()
    return dict(db.get("categories", {}))


def get_phase_labels_for_type(sn_type: str) -> List[str]:
    """Return unique phase_label values present for this SN type across all lines."""
    labels: Set[str] = set()
    for line in get_all_lines():
        profiles = (line.get("phase_profiles") or {}).get(sn_type)
        if not profiles:
            continue
        for prof in profiles:
            label = prof.get("phase_label")
            if isinstance(label, str) and label:
                labels.add(label)
    return sorted(labels)


def filter_lines(
    sn_types: Optional[Iterable[str]] = None,
    phase_labels: Optional[Iterable[str]] = None,
    category: Optional[str] = None,
    origin: Optional[str] = None,
    name_patterns: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Filter lines by multiple criteria from the JSON database.

    - sn_types: at least one must match the keys in `phase_profiles` or be
      present in `sn_types` field
    - phase_labels: at least one phase_label in the matched type's profiles
    - category/origin exact match if provided
    - name_patterns: any substring match against `key`
    """
    stypes = set(x for x in (sn_types or []) if x)
    phases = set(x for x in (phase_labels or []) if x)
    patterns = [p for p in (name_patterns or []) if p]

    results: List[Dict[str, Any]] = []
    for line in get_all_lines():
        # category filter
        if category and line.get("category") != category:
            continue
        # origin filter
        if origin and line.get("origin") != origin:
            continue
        # name pattern filter
        if patterns and not any(p in line.get("key", "") for p in patterns):
            continue

        # SN type/phase filtering
        if stypes:
            profiles = line.get("phase_profiles") or {}
            # type is considered a match if a key exists in profiles or sn_types contains it
            type_matches: List[str] = [t for t in stypes if t in profiles or t in (line.get("sn_types") or [])]
            if not type_matches:
                continue
            if phases:
                # require at least one matched type to have any of the requested phase_labels
                ok = False
                for t in type_matches:
                    for prof in (profiles.get(t) or []):
                        label = prof.get("phase_label")
                        if label in phases:
                            ok = True
                            break
                    if ok:
                        break
                if not ok:
                    continue
        elif phases:
            # If no SN types specified but phases are, include lines with any matching phase labels across any type
            profiles = line.get("phase_profiles") or {}
            any_phase = False
            for t, arr in profiles.items():
                for prof in arr or []:
                    if prof.get("phase_label") in phases:
                        any_phase = True
                        break
                if any_phase:
                    break
            if not any_phase:
                continue

        results.append(line)

    return results


