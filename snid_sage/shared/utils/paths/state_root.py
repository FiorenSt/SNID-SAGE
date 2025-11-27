"""
Centralised state root directory resolver
=========================================

This module defines a *single* overridable root directory for all
SNID SAGE per‑user/per‑project state, including:

- Configuration files
- Downloaded built‑in templates (when opting into local state)
- User templates metadata (small JSON selector)
- Optional LLM / OpenRouter config files

Design
------

- By default, the root is a ``SNID-SAGE`` subdirectory of the current
  working directory, e.g. if the user runs from ``C:\\work\\proj``:

      C:\\work\\proj\\SNID-SAGE

  This keeps all SNID SAGE state local to where the user is working,
  regardless of where ``pip`` installed the package.

- Advanced users can override the root via the ``SNID_SAGE_STATE_DIR``
  environment variable. This may be absolute or relative:

  - Absolute: use as‑is.
  - Relative: resolved from the current working directory.

Notes
-----

- ``SNID_SAGE_TEMPLATE_DIR`` still takes precedence for the templates
  bank and may point *outside* the state root when explicitly set.
- We intentionally *do not* create heavy subtrees here; the callers
  decide which subdirectories to create.
"""

from __future__ import annotations

from pathlib import Path
import os

_ENV_STATE_DIR = "SNID_SAGE_STATE_DIR"


def get_state_root_dir() -> Path:
    """
    Return the root directory for SNID SAGE state.

    Resolution order:

    1. If ``SNID_SAGE_STATE_DIR`` is set, use that (absolute or relative
       to the current working directory).
    2. Otherwise, use ``<cwd>/SNID-SAGE``.
    """
    override = os.environ.get(_ENV_STATE_DIR, "").strip()
    if override:
        base = Path(override).expanduser()
        if not base.is_absolute():
            base = (Path.cwd() / base).resolve()
        return base

    # Default: project-local SNID-SAGE directory under the current working dir.
    return (Path.cwd() / "SNID-SAGE").resolve()


__all__ = ["get_state_root_dir"]


