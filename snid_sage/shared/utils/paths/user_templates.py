"""
User Templates Path Resolver
===========================

- Single source of truth for resolving and persisting the User Templates directory.
- GUI should call with strict=True to avoid silent fallbacks and instead prompt users.
- CLI can decide policy (e.g., require config or allow legacy discovery explicitly).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import os

from datetime import datetime

from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager
from snid_sage.shared.utils.paths.state_root import get_state_root_dir


def _is_writable_dir(path: Path) -> bool:
    try:
        # Do not create directories implicitly; only validate existing paths
        return path.exists() and os.access(path, os.W_OK)
    except Exception:
        return False


def get_user_templates_dir(strict: bool = False) -> Optional[Path]:
    """
    Return the configured user templates directory, or None if unset/invalid.

    Behaviour:
    - First, honor an explicitly configured directory stored in ``user_templates.json``.
      If that file exists and points to a writable directory, it is returned.
    - If no explicit directory is configured yet, fall back to a *known, managed*
      default next to the centralized templates bank, create it if needed, and
      persist it as the configured location. This makes the user templates folder
      predictable without requiring an explicit “Set folder” step in the GUI.

    The ``strict`` flag is preserved for backwards compatibility but no longer
    changes the resolution behaviour – callers that previously passed
    ``strict=True`` to avoid legacy fallbacks now simply get the managed default.
    """
    # 1) Minimal persistence independent of global config: a small JSON selector
    #    under the shared state root (typically <cwd>/SNID_SAGE).
    try:
        settings_path = get_state_root_dir() / 'user_templates.json'
        if settings_path.exists():
            import json
            with open(settings_path, 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
            raw = data.get('path') or data.get('user_templates_dir')
            if raw:
                p = Path(raw)
                if _is_writable_dir(p):
                    return p
    except Exception:
        # If reading/parsing fails, fall through to the managed default logic
        pass

    # 2) No explicit folder yet – adopt a stable, managed default next to the
    #    centralized templates bank and persist it so future calls are fast.
    try:
        default_dir = get_default_user_templates_dir()
        if default_dir is not None:
            # set_user_templates_dir will validate, create if needed, and persist
            set_user_templates_dir(default_dir)
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

        C:\\some\\proj\\SNID_SAGE\\templates
        C:\\some\\proj\\SNID_SAGE\\user_templates

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
    path = path.expanduser()
    if path.exists():
        if not _is_writable_dir(path):
            raise PermissionError(f"User templates directory is not writable: {path}")
    else:
        parent = path.parent
        if not parent.exists() or not os.access(parent, os.W_OK):
            raise PermissionError(
                f"Cannot create user templates directory; parent is not writable: {parent}"
            )
        parent.mkdir(parents=True, exist_ok=True)
        path.mkdir(parents=True, exist_ok=True)
    try:
        # Prefer the shared state root when configured; otherwise fall back
        # to the historic ~/.snid_sage location for backwards compatibility.
        settings_dir = get_state_root_dir()
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / 'user_templates.json'
        data = {'path': str(path), 'last_modified': datetime.now().isoformat()}
        import json
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise OSError(f"Failed to persist user templates directory: {e}")


def discover_legacy_user_templates() -> List[Path]:
    """
    Discover previous fallback locations that may contain an existing user library.

    This does NOT create directories; it only returns existing, writable candidates
    that contain hints of a user library (index or per-type user HDF5 files).
    """
    candidates: List[Path] = []

    # 0) If config already points to a dir that exists/writable, prefer it
    current = get_user_templates_dir(strict=False)
    if current and current.exists() and _is_writable_dir(current):
        candidates.append(current)

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

    # 3) App config dir templates/User_templates (legacy) and user_templates (new)
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

    # 4) (removed): legacy home fallback ~/.snid_sage/User_templates

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
]


