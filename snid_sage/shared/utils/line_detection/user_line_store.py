"""
User Line Store
===============

Load/save user-defined spectral lines and presets, and expose merged
line databases for the GUI so custom lines appear in the Spectral Lines
dialog alongside built-in ones.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Tuple
import json

try:
    from snid_sage.shared.utils.config.configuration_manager import config_manager
except Exception:
    config_manager = None  # Fallback handled below

# Built-in physical constants and helpers
from snid_sage.shared.constants import physical as _phys
from snid_sage.shared.utils.line_detection.line_db_loader import get_all_lines, reload_database


def _get_lines_dir() -> Path:
    """Return the directory where user lines/presets are stored."""
    if config_manager is not None:
        base = Path(config_manager.config_dir)
    else:
        # Fallback to current working directory if config manager missing
        base = Path.cwd() / "config"
    lines_dir = base / "lines"
    lines_dir.mkdir(parents=True, exist_ok=True)
    return lines_dir


def _get_store_paths() -> Tuple[Path, Path]:
    """Return (lines.json, presets.json) paths under the config lines dir."""
    lines_dir = _get_lines_dir()
    return lines_dir / "user_lines.json", lines_dir / "user_line_presets.json"


def _get_user_db_path() -> Path:
    """Return full path to the merged user database file used by the loader."""
    return _get_lines_dir() / "line_database_user.json"


def load_user_lines() -> List[Dict[str, Any]]:
    """Load user-defined lines as a list of LINE_DB-style dicts."""
    lines_path, _ = _get_store_paths()
    if not lines_path.exists():
        return []
    try:
        with open(lines_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data.get("lines", []))
    except Exception:
        return []


def save_user_lines(lines: List[Dict[str, Any]]) -> bool:
    """Persist user-defined LINE_DB entries."""
    lines_path, _ = _get_store_paths()
    try:
        payload = {"lines": lines}
        with open(lines_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        # Also write/refresh the merged _user database so the app auto-picks it up
        try:
            base_lines = list(get_all_lines())
        except Exception:
            base_lines = []
        # Merge base with user entries by key, with user entries overriding
        by_key: Dict[str, Dict[str, Any]] = {d.get("key"): dict(d) for d in base_lines if d.get("key")}
        for entry in lines:
            key = entry.get("key")
            if not key:
                continue
            by_key[key] = dict(entry)

        merged_payload: Dict[str, Any] = {
            "lines": list(by_key.values())
        }
        # If the base database contains additional top-level fields (e.g., phase_system), preserve them
        try:
            # Read packaged default DB to preserve top-level fields (e.g., phase_system)
            packaged_default = Path(__file__).resolve().parents[3] / "lines" / "line_database.json"
            if packaged_default.exists():
                with packaged_default.open("r", encoding="utf-8") as rf:
                    base_db = json.load(rf)
                for k, v in base_db.items():
                    if k != "lines" and k not in merged_payload:
                        merged_payload[k] = v
            else:
                # Fallback for editable installs
                repo_default = Path("config") / "lines" / "line_database.json"
                if repo_default.exists():
                    with repo_default.open("r", encoding="utf-8") as rf:
                        base_db = json.load(rf)
                    for k, v in base_db.items():
                        if k != "lines" and k not in merged_payload:
                            merged_payload[k] = v
        except Exception:
            pass

        user_db_path = _get_user_db_path()
        with user_db_path.open("w", encoding="utf-8") as uf:
            json.dump(merged_payload, uf, indent=2, ensure_ascii=False)

        # Invalidate and reload loader cache so new file is picked up
        reload_database()
        return True
    except Exception:
        return False


def load_user_presets() -> Dict[str, Any]:
    """Load user-defined preset sets. Schema:
    {
      "presets": {
        "My Preset": {
          "criteria": {"category": [..], "origin": [..], "sn_types": [..], "strength": [..], "phase": [..], "name_patterns": [..]},
          "lines": ["H-alpha", "[O III] 5007"]
        }
      }
    }
    """
    _, presets_path = _get_store_paths()
    if not presets_path.exists():
        return {"presets": {}}
    try:
        with open(presets_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"presets": {}}


def save_user_presets(presets: Dict[str, Any]) -> bool:
    """Persist user-defined presets."""
    _, presets_path = _get_store_paths()
    try:
        with open(presets_path, "w", encoding="utf-8") as f:
            json.dump({"presets": presets.get("presets", presets)}, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_effective_line_db() -> List[Dict[str, Any]]:
    """Return JSON DB merged with user-defined lines, keyed by 'key'.
    User entries override built-ins on key collisions.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    # Base from JSON database
    for d in get_all_lines():
        key = d.get("key")
        if not key:
            continue
        merged[key] = {
            "key": key,
            "wavelength_vacuum": float(d.get("wavelength_vacuum", 0.0) or 0.0),
            "wavelength_air": float(d.get("wavelength_air", 0.0) or 0.0),
            "sn_types": list(d.get("sn_types", []) or []),
            "category": d.get("category", ""),
            "origin": d.get("origin", "sn"),
            "note": d.get("note", ""),
        }
    # Overlay user entries
    for entry in load_user_lines():
        key = entry.get("key")
        if not key:
            continue
        merged[key] = {
            "key": key,
            "wavelength_vacuum": float(entry.get("wavelength_vacuum", 0.0) or 0.0),
            "wavelength_air": float(entry.get("wavelength_air", 0.0) or 0.0),
            "sn_types": list(entry.get("sn_types", []) or []),
            "category": entry.get("category", "galaxy"),
            "origin": entry.get("origin", "sn"),
            "note": entry.get("note", ""),
        }
    return list(merged.values())


def get_effective_supernova_emission_lines() -> Dict[str, Dict[str, Any]]:
    """Build SUPERNOVA_EMISSION_LINES-style dict from effective LINE_DB."""
    # Reuse helper functions and colors from physical
    try:
        _get_line_strength = _phys._get_line_strength  # type: ignore[attr-defined]
        _get_line_phase = _phys._get_line_phase  # type: ignore[attr-defined]
        _get_line_type = _phys._get_line_type  # type: ignore[attr-defined]
        CATEGORY_COLORS = _phys.CATEGORY_COLORS
    except Exception:
        # Fallbacks if internals change
        CATEGORY_COLORS = getattr(_phys, "CATEGORY_COLORS", {})

        def _get_line_strength(entry: Dict[str, Any]) -> str:  # type: ignore
            return entry.get("strength", "medium")

        def _get_line_phase(entry: Dict[str, Any]) -> str:  # type: ignore
            return entry.get("phase", "all")

        def _get_line_type(entry: Dict[str, Any]) -> str:  # type: ignore
            return "emission"

    result: Dict[str, Dict[str, Any]] = {}
    for line_entry in get_effective_line_db():
        if float(line_entry.get("wavelength_air", 0.0) or 0.0) <= 0:
            if line_entry.get("origin") != "alias":
                # skip entries without wavelengths unless alias
                continue
        line_name = line_entry["key"]
        category = line_entry.get("category", "")
        result[line_name] = {
            "wavelength": float(line_entry.get("wavelength_air", 0.0) or 0.0),
            "wavelength_vacuum": float(line_entry.get("wavelength_vacuum", 0.0) or 0.0),
            "wavelength_air": float(line_entry.get("wavelength_air", 0.0) or 0.0),
            "type": _get_line_type(line_entry),
            "sn_types": list(line_entry.get("sn_types", []) or []),
            "strength": _get_line_strength(line_entry),
            "color": CATEGORY_COLORS.get(category, "#888888"),
            "category": category,
            "phase": _get_line_phase(line_entry),
            "origin": line_entry.get("origin", "sn"),
            "description": f"{line_name} - { _phys.SN_LINE_CATEGORIES.get(category, 'Unknown category') }",
        }
    return result


def add_or_update_user_line(entry: Dict[str, Any]) -> bool:
    """Add or update a single user line by key."""
    if not entry.get("key"):
        return False
    lines = load_user_lines()
    by_key = {d.get("key"): d for d in lines}
    by_key[entry["key"]] = entry
    return save_user_lines(list(by_key.values()))


def delete_user_line(key: str) -> bool:
    """Delete a user line by key."""
    lines = [d for d in load_user_lines() if d.get("key") != key]
    return save_user_lines(lines)


