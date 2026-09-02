"""Package discovery that works on Windows and Unix.

Git tracks ``snid_sage/``, but a case-insensitive checkout can leave the
folder as ``SNID_SAGE/``. Setuptools' ``snid_sage*`` glob then finds nothing
and ``import snid_sage`` fails. Map whichever on-disk name exists to the
public import name so editable installs, wheels, and PyPI all expose
``snid_sage``.
"""

from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup

_ROOT = Path(__file__).resolve().parent
_IMPORT_NAME = "snid_sage"


def _source_dir_name() -> str:
    for child in _ROOT.iterdir():
        if not child.is_dir():
            continue
        if child.name.lower() != _IMPORT_NAME:
            continue
        if (child / "__init__.py").is_file():
            return child.name
    return _IMPORT_NAME


_SRC = _source_dir_name()
_PACKAGES = [_IMPORT_NAME] + [f"{_IMPORT_NAME}.{p}" for p in find_packages(_SRC)]

setup(
    package_dir={_IMPORT_NAME: _SRC},
    packages=_PACKAGES,
)
