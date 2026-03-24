"""
User Templates Path Resolver
===========================

- Single source of truth for resolving and persisting the User Templates directory.
- The User Templates Folder is managed by the Template Manager workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import os

from datetime import datetime

from platformdirs import user_config_dir


def _is_writable_dir(path: Path) -> bool:
    try:
        # Do not create directories implicitly; only validate existing paths
        return path.exists() and os.access(path, os.W_OK)
    except Exception:
        return False


_PLATFORMDIRS_APPNAME: str = "SNID-SAGE"
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


def _load_user_templates_dir_pointer() -> Optional[Path]:
    """
    Load the User Templates directory from the per-user pointer file, if valid.
    """
    p = _pointer_file_path()
    try:
        if not p.exists():
            return None
        import json

        with p.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        mode = (data.get("mode") or "manual").strip().lower()
        if mode != "manual":
            return None

        raw = (data.get("path") or "").strip()
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
    try:
        if p.exists():
            p.unlink()
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


def get_user_templates_dir(strict: bool = False) -> Optional[Path]:
    """
    Return the active user templates directory.

    If the user has explicitly chosen a folder in the Template Manager, that
    manual override is used. Otherwise SNID SAGE uses the default managed
    sibling directory next to the built-in templates bank.
    """
    current = _load_user_templates_dir_pointer()
    if current is not None:
        return current

    try:
        default_dir = get_default_user_templates_dir()
        if default_dir is not None:
            _ensure_dir_exists(default_dir)
            return default_dir
    except Exception:
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
    Persist a manually chosen User Templates folder after validation.
    """
    _ensure_dir_exists(path)
    _save_user_templates_dir_pointer(path)


def discover_user_template_libraries() -> List[Path]:
    """
    Discover existing user template libraries worth offering for adoption.
    """
    candidates: List[Path] = []

    try:
        current = _load_user_templates_dir_pointer()
        if current and current.exists() and _is_writable_dir(current):
            candidates.append(current)
    except Exception:
        pass

    try:
        from snid_sage.shared.templates_manager import get_templates_base_dir

        tpl_base = Path(get_templates_base_dir())

        new_default = tpl_base.parent / 'user_templates'
        if new_default.exists() and _is_writable_dir(new_default):
            candidates.append(new_default)
    except Exception:
        pass

    try:
        docs = Path.home() / 'Documents' / 'SNID_SAGE' / 'User_templates'
        if docs.exists() and _is_writable_dir(docs):
            candidates.append(docs)
    except Exception:
        pass

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
    'discover_user_template_libraries',
    'clear_user_templates_dir_override',
]


