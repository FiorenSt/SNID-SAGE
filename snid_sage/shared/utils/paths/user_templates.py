"""
User Templates Path Resolver
===========================

- Single source of truth for resolving and persisting the User Templates directory.
- GUI should call with strict=True to avoid silent fallbacks and instead prompt users.
- CLI can decide policy (e.g., require config or allow discovery explicitly).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import os

from datetime import datetime

from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
from snid_sage.shared.utils.paths.state_root import get_state_root_dir
from platformdirs import user_config_dir


def _is_writable_dir(path: Path) -> bool:
    try:
        # Do not create directories implicitly; only validate existing paths
        return path.exists() and os.access(path, os.W_OK)
    except Exception:
        return False


_PLATFORMDIRS_APPNAME: str = "SNID-SAGE"
_PLATFORMDIRS_APPAUTHOR_LEGACY: str = "SNID-SAGE"
_USER_TEMPLATES_POINTER_FILENAME: str = "user_templates_pointer.json"


def _ensure_dir_exists(path: Path) -> None:
    """
    Ensure a directory exists (create it if needed) without persisting any pointer.
    """
    path = path.expanduser()
    if path.exists():
        if not path.is_dir():
            raise NotADirectoryError(f"User templates path exists but is not a directory: {path}")
        if not os.access(path, os.W_OK):
            raise PermissionError(f"User templates directory is not writable: {path}")
        return

    parent = path.parent
    if not parent.exists() or not os.access(parent, os.W_OK):
        raise PermissionError(
            f"Cannot create user templates directory; parent is not writable: {parent}"
        )
    parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(parents=True, exist_ok=True)


def _pointer_file_path() -> Path:
    """
    Return the per-user pointer file path used for a manual User Templates override.
    """
    # appauthor=False avoids Windows paths like "...\\SNID-SAGE\\SNID-SAGE\\...".
    base = Path(
        user_config_dir(
            _PLATFORMDIRS_APPNAME,
            appauthor=False,
            roaming=False,
            ensure_exists=True,
        )
    )
    return base / _USER_TEMPLATES_POINTER_FILENAME


def _legacy_pointer_file_path() -> Path:
    base = Path(
        user_config_dir(
            _PLATFORMDIRS_APPNAME,
            _PLATFORMDIRS_APPAUTHOR_LEGACY,
            roaming=False,
            ensure_exists=True,
        )
    )
    return base / _USER_TEMPLATES_POINTER_FILENAME


def _load_user_templates_dir_pointer() -> Optional[Path]:
    """
    Load the User Templates directory from the per-user pointer file, if valid.
    """
    p = _pointer_file_path()
    legacy_p = _legacy_pointer_file_path()
    try:
        if not p.exists() and legacy_p.exists():
            # Migrate legacy pointer forward to the new location (best-effort)
            try:
                import json
                with legacy_p.open("r", encoding="utf-8") as f:
                    legacy_data = json.load(f) or {}
                tmp = p.with_suffix(p.suffix + ".part")
                with tmp.open("w", encoding="utf-8") as f:
                    json.dump(legacy_data, f, indent=2, sort_keys=True)
                tmp.replace(p)
            except Exception:
                pass

        if not p.exists():
            return None
        import json

        with p.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        mode = (data.get("mode") or "manual").strip().lower()
        if mode != "manual":
            # Auto mode means "follow the managed templates location"; no fixed path to load.
            return None

        raw = (data.get("path") or data.get("user_templates_dir") or "").strip()
        if not raw:
            return None
        target = Path(raw).expanduser()
        if _is_writable_dir(target):
            return target
    except Exception:
        return None
    return None


def _save_user_templates_dir_pointer(path: Path) -> None:
    """
    Persist the User Templates directory to the per-user pointer file.

    Uses an atomic write to avoid corrupting the pointer on interruption.
    """
    path = path.expanduser()
    pointer_path = _pointer_file_path()
    try:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort only; do not fail if pointer storage is unavailable.
        return

    payload = {
        "mode": "manual",
        "path": str(path),
        "last_modified": datetime.now().isoformat(),
    }
    tmp = pointer_path.with_suffix(pointer_path.suffix + ".part")
    try:
        import json

        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        tmp.replace(pointer_path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return


def clear_user_templates_dir_override() -> None:
    """
    Clear any manual override so user templates "follow templates" again.

    Best-effort; never raises.
    """
    p = _pointer_file_path()
    legacy_p = _legacy_pointer_file_path()
    try:
        if p.exists():
            p.unlink()
        # Also clear any legacy pointer so behavior is consistent after migration
        try:
            if legacy_p.exists():
                legacy_p.unlink()
        except Exception:
            pass
    except Exception:
        # As a fallback, try to write an explicit 'auto' mode marker
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {"mode": "auto", "last_modified": datetime.now().isoformat()}
            tmp = p.with_suffix(p.suffix + ".part")
            import json

            with tmp.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            tmp.replace(p)
        except Exception:
            return


def _load_legacy_state_root_pointer() -> Optional[Path]:
    """
    Backwards-compatibility: prior versions stored the pointer under state root.
    """
    try:
        settings_path = get_state_root_dir() / "user_templates.json"
        if not settings_path.exists():
            return None
        import json

        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        raw = data.get("path") or data.get("user_templates_dir")
        if raw:
            p = Path(raw)
            if _is_writable_dir(p):
                return p
    except Exception:
        return None
    return None


def get_user_templates_dir(strict: bool = False) -> Optional[Path]:
    """
    Return the configured user templates directory, or None if unset/invalid.

    Behaviour:
    - First, honor an explicitly configured directory stored in a per-user pointer
      file (via ``platformdirs``). If that file exists and points to a writable
      directory, it is returned.
    - If no explicit directory is configured yet, fall back to a *known, managed*
      default next to the centralized templates bank, create it if needed, and
      persist it as the configured location. This makes the user templates folder
      predictable without requiring an explicit “Set folder” step in the GUI.

    The ``strict`` flag is preserved for backwards compatibility but no longer
    changes the resolution behaviour – callers that previously passed
    ``strict=True`` to avoid fallbacks now simply get the managed default.
    """
    # 1) Preferred: per-user pointer file (stable across working directories)
    current = _load_user_templates_dir_pointer()
    if current is not None:
        return current

    # 1b) Backwards-compatibility: migrate legacy pointer from state root if present
    legacy = _load_legacy_state_root_pointer()
    if legacy is not None:
        _save_user_templates_dir_pointer(legacy)
        return legacy

    # 2) No explicit folder yet – adopt a stable, managed default next to the
    #    centralized templates bank and persist it so future calls are fast.
    try:
        default_dir = get_default_user_templates_dir()
        if default_dir is not None:
            # Ensure directory exists but DO NOT persist a pointer:
            # default behavior should "follow templates" unless user explicitly chose a custom folder.
            _ensure_dir_exists(default_dir)
            return default_dir
    except Exception:
        # If anything goes wrong, report “unset” and let callers decide how to react.
        return None

    return None


def get_default_user_templates_dir() -> Optional[Path]:
    """
    Return the recommended default User Templates directory.

    By default this is a ``user_templates`` sibling directory next to the
    managed built-in templates directory resolved by the centralized templates
    manager, e.g. on Windows for a fresh install run from ``C:\\some\\proj``::

        C:\\some\\proj\\SNID-SAGE\\templates
        C:\\some\\proj\\SNID-SAGE\\user_templates

    The directory is not created here; callers may choose to create it.
    """
    try:
        from snid_sage.shared.templates_manager import get_templates_base_dir

        base = Path(get_templates_base_dir())
        # ``base`` is typically ".../snid-sage/templates"; we want a stable,
        # cross-platform sibling directory ".../snid-sage/user_templates".
        return base.parent / "user_templates"
    except Exception:
        return None


def set_user_templates_dir(path: Path) -> None:
    """
    Persist the user templates directory into configuration after validation.

    Behaviour:
    - If ``path`` exists, it must be a writable directory.
    - If it does not exist, its parent must be writable; the directory is then
      created (along with any missing parents).
    """
    _ensure_dir_exists(path)
    # Persist pointer in per-user config (stable across working directories)
    _save_user_templates_dir_pointer(path)


def discover_legacy_user_templates() -> List[Path]:
    """
    Discover previous fallback locations that may contain an existing user library.

    This does NOT create directories; it only returns existing, writable candidates
    that contain hints of a user library (index or per-type user HDF5 files).
    """
    candidates: List[Path] = []

    # 0) Manual pointer targets only (avoid get_user_templates_dir() side effects).
    try:
        current = _load_user_templates_dir_pointer()
        if current and current.exists() and _is_writable_dir(current):
            candidates.append(current)
    except Exception:
        pass

    try:
        legacy_ptr = _load_legacy_state_root_pointer()
        if legacy_ptr and legacy_ptr.exists() and _is_writable_dir(legacy_ptr):
            candidates.append(legacy_ptr)
    except Exception:
        pass

    # 1) Siblings to built-ins:
    #    - New default:   .../snid-sage/user_templates
    #    - Old default:   .../snid-sage/templates/User_templates
    try:
        from snid_sage.shared.templates_manager import get_templates_base_dir

        tpl_base = Path(get_templates_base_dir())

        # New default (preferred)
        new_default = tpl_base.parent / 'user_templates'
        if new_default.exists() and _is_writable_dir(new_default):
            candidates.append(new_default)

        # Legacy location under the templates directory
        legacy_sibling = tpl_base / 'User_templates'
        if legacy_sibling.exists() and _is_writable_dir(legacy_sibling):
            candidates.append(legacy_sibling)
    except Exception:
        pass

    # 2) Documents/SNID_SAGE/User_templates
    try:
        docs = Path.home() / 'Documents' / 'SNID_SAGE' / 'User_templates'
        if docs.exists() and _is_writable_dir(docs):
            candidates.append(docs)
    except Exception:
        pass

    # 3) App config dir templates/User_templates and user_templates
    try:
        cm = ConfigurationManager()
        cfg_root = Path(cm.config_dir)

        legacy_appdata = cfg_root / 'templates' / 'User_templates'
        if legacy_appdata.exists() and _is_writable_dir(legacy_appdata):
            candidates.append(legacy_appdata)

        new_appdata = cfg_root / 'user_templates'
        if new_appdata.exists() and _is_writable_dir(new_appdata):
            candidates.append(new_appdata)
    except Exception:
        pass

    # 4) (removed): home fallback ~/.snid_sage/User_templates

    # Filter for libraries that look populated
    filtered: List[Path] = []
    seen = set()
    for p in candidates:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        try:
            has_index = (p / 'template_index.user.json').exists()
            has_h5 = any(p.glob('templates_*.user.hdf5'))
            if has_index or has_h5:
                filtered.append(p)
        except Exception:
            continue

    return filtered


__all__ = [
    'get_user_templates_dir',
    'get_default_user_templates_dir',
    'set_user_templates_dir',
    'discover_legacy_user_templates',
    'clear_user_templates_dir_override',
]


