"""
Centralized management of built-in SNID SAGE templates
======================================================

This module is responsible for:
- Deciding *where* the built-in template bank lives on disk.
- Lazily downloading the templates from GitHub on first use.
- Providing a single helper :func:`get_templates_dir` that the rest of the
  codebase can use instead of assuming ``snid_sage/templates`` exists.

Design notes
------------
- Download source is a single ZIP archive hosted as a GitHub Release asset.
- Storage location is resolved via :func:`get_templates_base_dir` and is designed
  to be stable across working directories after first use (via a small per-user
  pointer file), while still supporting explicit overrides.
- Advanced users can override the storage location by setting the
  ``SNID_SAGE_TEMPLATE_DIR`` environment variable. This may be an absolute or
  relative path; relative paths are resolved from the current working directory.
- Advanced users (or development installs) can override the archive URL by
  setting ``SNID_SAGE_TEMPLATES_ARCHIVE_URL``.
- A small JSON metadata file tracks the installed template *bank* version and
  the list of expected files so we can avoid re-downloading on every run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Callable
import json
import os
import sys
import zipfile
import time

import requests
from platformdirs import user_config_dir

from snid_sage.shared.utils.logging import get_logger
from snid_sage.shared.utils.paths.state_root import get_state_root_dir

_LOG = get_logger("snid_sage.shared.templates_manager")


# Bump this when you intentionally change the template bank contents on GitHub.
# This is *independent* from the JSON index's own "version" field.
TEMPLATE_BANK_VERSION: str = "2.2"

# Files that make up the built-in template bank. Update this list when
# templates are added/removed/renamed in the GitHub repo.
TEMPLATES_FILES: List[str] = [
    "template_index.json",
    "template_index_onir.json",
    "templates_AGN_onir.hdf5",
    "templates_AGN.hdf5",
    "templates_CV.hdf5",
    "templates_Galaxy_onir.hdf5",
    "templates_Galaxy.hdf5",
    "templates_GAP_onir.hdf5",
    "templates_GAP.hdf5",
    "templates_Ia_onir.hdf5",
    "templates_Ia.hdf5",
    "templates_Ib_onir.hdf5",
    "templates_Ib.hdf5",
    "templates_Ibn_onir.hdf5",
    "templates_Ibn.hdf5",
    "templates_Ic_onir.hdf5",
    "templates_Ic.hdf5",
    "templates_Icn_onir.hdf5",
    "templates_Icn.hdf5",
    "templates_II_onir.hdf5",
    "templates_II.hdf5",
    "templates_KN_onir.hdf5",
    "templates_KN.hdf5",
    "templates_LFBOT_onir.hdf5",
    "templates_LFBOT.hdf5",
    "templates_SLSN_onir.hdf5",
    "templates_SLSN.hdf5",
    "templates_Star_onir.hdf5",
    "templates_Star.hdf5",
    "templates_TDE_onir.hdf5",
    "templates_TDE.hdf5",
]

_ENV_DIR_OVERRIDE: str = "SNID_SAGE_TEMPLATE_DIR"
_ENV_ARCHIVE_URL_OVERRIDE: str = "SNID_SAGE_TEMPLATES_ARCHIVE_URL"
_META_FILENAME: str = "templates_meta.json"
_POINTER_FILENAME: str = "templates_pointer.json"
_PLATFORMDIRS_APPNAME: str = "SNID-SAGE"
_PLATFORMDIRS_APPAUTHOR_LEGACY: str = "SNID-SAGE"


def _pointer_file_path() -> Path:
    """
    Return the per-user pointer file path that remembers the managed templates dir.
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
    return base / _POINTER_FILENAME


def _legacy_pointer_file_path() -> Path:
    """Legacy pointer location (kept for migration/backwards compatibility)."""
    base = Path(
        user_config_dir(
            _PLATFORMDIRS_APPNAME,
            _PLATFORMDIRS_APPAUTHOR_LEGACY,
            roaming=False,
            ensure_exists=True,
        )
    )
    return base / _POINTER_FILENAME


def _load_templates_dir_pointer() -> Optional[Path]:
    """
    Load the templates base directory from the per-user pointer file, if valid.

    Valid means:
    - The pointer file can be parsed
    - The target exists and is a directory
    - The directory is writable (needed for first-time download / refresh)
    """
    p = _pointer_file_path()
    legacy_p = _legacy_pointer_file_path()
    try:
        if not p.exists() and legacy_p.exists():
            # Migrate legacy pointer forward to the new location (best-effort)
            try:
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
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        raw = (data.get("templates_base_dir") or data.get("path") or "").strip()
        if not raw:
            return None
        target = Path(raw).expanduser()
        if not target.exists() or not target.is_dir():
            return None
        if not os.access(str(target), os.W_OK):
            return None
        return target
    except Exception:
        return None


def _save_templates_dir_pointer(base_dir: Path) -> None:
    """
    Persist the templates base directory to the per-user pointer file.

    Uses an atomic write to avoid corrupting the pointer on interruption.
    """
    base_dir = base_dir.expanduser()
    pointer_path = _pointer_file_path()
    try:
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If we cannot create the pointer dir, we simply don't persist (non-fatal)
        return

    payload = {
        "templates_base_dir": str(base_dir),
        "bank_version": TEMPLATE_BANK_VERSION,
        "files": list(TEMPLATES_FILES),
    }

    tmp = pointer_path.with_suffix(pointer_path.suffix + ".part")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        tmp.replace(pointer_path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        # Pointer persistence is best-effort only; never fail template resolution because of it.
        return


def _ensure_writable_dir(path: Path) -> Path:
    """
    Ensure ``path`` exists as a directory and is writable.

    Raises a descriptive exception if the directory cannot be created or written.
    """
    try:
        path = path.expanduser()
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise OSError(f"Failed to create template directory '{path}': {exc}")

    if not path.is_dir():
        raise NotADirectoryError(f"Template path is not a directory: {path}")

    # Basic writability check
    if not os.access(str(path), os.W_OK):
        raise PermissionError(f"Template directory is not writable: {path}")

    return path


def _find_packaged_templates_dir() -> Optional[Path]:
    """
    Return a read-only templates directory bundled with the package, if any.

    This prefers templates shipped directly inside the ``snid_sage`` package
    (e.g. a Git clone with ``snid_sage/templates`` present) and avoids any
    download/state management when available.

    Returns ``None`` when no such directory exists (typical for wheel/pip
    installs where templates are no longer packaged).  For editable /
    development installs, we also look for a top-level ``templates`` directory
    in the project root (next to the ``snid_sage`` package), which is where
    the git repository ships the built-in bank.
    """
    try:
        import importlib.resources as pkg_resources
    except Exception:  # pragma: no cover - very old Python
        return None

    try:
        if hasattr(pkg_resources, "files"):
            try:
                pkg_root_obj = pkg_resources.files("snid_sage")  # type: ignore[attr-defined]
                pkg_root = Path(str(pkg_root_obj))

                # 1) Classic packaged location: snid_sage/templates
                tdir = pkg_root / "templates"
                if (tdir / "template_index.json").exists():
                    return tdir

                # 2) Editable/dev install: repository ships templates in a
                #    top-level ``templates`` directory next to ``snid_sage``.
                repo_templates = pkg_root.parent / "templates"
                if (repo_templates / "template_index.json").exists():
                    return repo_templates
            except Exception:
                pass
    except Exception:
        return None

    return None


def get_templates_base_dir() -> Path:
    """
    Return the base directory where built-in templates are stored.

    Resolution order:
    1. If ``SNID_SAGE_TEMPLATE_DIR`` is set, use that (absolute or relative).
    2. Otherwise, if a per-user pointer file exists and is valid, use that.
    3. Otherwise, place templates under ``<state_root>/templates`` where
       ``state_root`` is resolved via
       :func:`snid_sage.shared.utils.paths.state_root.get_state_root_dir`.
    """
    override = os.environ.get(_ENV_DIR_OVERRIDE, "").strip()
    if override:
        base = Path(override)
        _LOG.debug(f"Using override template directory from {_ENV_DIR_OVERRIDE}: {base}")
        return _ensure_writable_dir(base)

    # Prefer the per-user pointer file if present. This makes the templates bank
    # independent of the current working directory once it has been initialized.
    remembered = _load_templates_dir_pointer()
    if remembered is not None:
        _LOG.debug(f"Using remembered templates directory from pointer file: {remembered}")
        # We still validate writability/dir-ness here (and create if needed) to
        # keep behavior consistent with other paths.
        return _ensure_writable_dir(remembered)

    # Default: use the shared state root so that, on a fresh installation,
    # the first directory from which SNID SAGE is run becomes the anchor
    # for all state (config, templates, user templates, etc.). Existing
    # installations that already have ``~/.snid_sage`` continue to use it.
    root = get_state_root_dir()
    base = root / "templates"
    _LOG.debug(f"Using state-root template directory: {base}")
    base = _ensure_writable_dir(base)
    # Persist this resolved directory so future runs (from any cwd) reuse it.
    _save_templates_dir_pointer(base)
    return base


def _meta_path(base_dir: Path) -> Path:
    return base_dir / _META_FILENAME


def _load_meta(base_dir: Path) -> Optional[Dict[str, object]]:
    meta_path = _meta_path(base_dir)
    try:
        if not meta_path.exists():
            return None
        with meta_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        _LOG.warning(f"Failed to read templates metadata from {meta_path}: {exc}")
        return None


def _save_meta(base_dir: Path, meta: Dict[str, object]) -> None:
    meta_path = _meta_path(base_dir)
    try:
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
    except Exception as exc:  # pragma: no cover - defensive
        _LOG.warning(f"Failed to write templates metadata to {meta_path}: {exc}")


def _compute_archive_url() -> str:
    """
    Compute the expected URL of the templates ZIP archive for this version.

    By default this assumes a Git tag of the form ``v<version>`` and an
    attached release asset named ``templates-v<version>.zip``. For example,
    package version ``0.11.0`` expects:

        https://github.com/FiorenSt/SNID-SAGE/releases/download/v0.11.0/templates-v0.11.0.zip

    Advanced users and development installs can override this via the
    ``SNID_SAGE_TEMPLATES_ARCHIVE_URL`` environment variable.

    For *development* installs we deliberately avoid hitting GitHub at all
    (unless an explicit override URL is provided) and expect a local templates
    bank (for example the one living under ``SNID-SAGE/templates`` in a git
    checkout).
    """
    # Env override takes precedence (e.g. dev/testing mirrors)
    override = os.environ.get(_ENV_ARCHIVE_URL_OVERRIDE, "").strip()
    if override:
        return override

    # Try to derive from installed package version
    raw_version = TEMPLATE_BANK_VERSION
    try:
        from snid_sage import __version__ as pkg_version  # type: ignore

        raw_version = str(pkg_version)
    except Exception:
        # Fall back to TEMPLATE_BANK_VERSION when package version is unavailable
        pass

    # Detect common "development" style versions:
    lower = raw_version.lower()
    is_dev_build = (
        ".dev" in lower
        or "+g" in lower
        or "dirty" in lower
        or "local" in lower
        or "unknown" in lower
    )

    if is_dev_build:
        # For dev builds, never auto-hit GitHub. Callers should rely on a
        # pre-populated local templates bank instead (e.g. from a git clone).
        # We return a dummy URL that will fail fast if reached.
        return "file://dev-no-remote-templates"

    # Strip any local segments (e.g. 0.11.0+githash -> 0.11.0)
    version = raw_version.split("+", 1)[0]

    return (
        f"https://github.com/FiorenSt/SNID-SAGE/releases/download/"
        f"v{version}/templates-v{version}.zip"
    )


def _all_files_present(base_dir: Path) -> bool:
    for name in TEMPLATES_FILES:
        if not (base_dir / name).exists():
            return False
    return True


def is_templates_installed(base_dir: Optional[Path] = None) -> bool:
    """
    Return True if the current template bank is present and up-to-date.

    This checks:
    - The presence of the metadata file with matching ``TEMPLATE_BANK_VERSION``.
    - That all expected files in :data:`TEMPLATES_FILES` exist.

    For development installs (e.g. running directly from a git checkout),
    we are more permissive: if all expected files are present in the resolved
    templates base directory, we treat the bank as installed even when the
    metadata file is missing or has a mismatched version.  This avoids
    repeatedly attempting downloads when ``SNID-SAGE/templates`` from the
    repository already contains a complete bank.
    """
    if base_dir is None:
        base_dir = get_templates_base_dir()

    meta = _load_meta(base_dir)
    if meta and str(meta.get("version", "")) == TEMPLATE_BANK_VERSION:
        return _all_files_present(base_dir)

    # Development-friendly fallback: for dev builds, accept a bank as
    # "installed" when all expected files are present, even without a
    # matching metadata file.
    try:
        from snid_sage import __version__ as pkg_version  # type: ignore

        v = str(pkg_version).lower()
        is_dev = (
            ".dev" in v
            or "+g" in v
            or "dirty" in v
            or "local" in v
            or "unknown" in v
        )
    except Exception:
        is_dev = False

    if is_dev and _all_files_present(base_dir):
        _LOG.debug(
            "Treating templates as installed for development build: "
            f"{base_dir} (metadata missing or mismatched, but all files present)"
        )
        return True

    return False


def _download_file(
    url: str,
    dest: Path,
    timeout: float = 60.0,
    progress_cb: Optional[Callable[[int, Optional[int], float], None]] = None,
) -> None:
    """
    Download a single file from ``url`` to ``dest``.

    Uses a temporary ``.part`` file and renames it on success to avoid leaving
    corrupt files behind on interrupted downloads.
    """
    tmp_path = dest.with_suffix(dest.suffix + ".part")
    _LOG.info(f"Downloading {url} -> {dest}")

    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            total_size: Optional[int]
            try:
                total_size = int(resp.headers.get("Content-Length", "0")) or None
            except Exception:
                total_size = None

            downloaded = 0
            start_ts = time.monotonic()

            with tmp_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_cb is not None:
                        try:
                            elapsed = max(time.monotonic() - start_ts, 1e-6)
                            progress_cb(downloaded, total_size, elapsed)
                        except Exception:
                            # Never let a cosmetic progress callback break the download
                            progress_cb = None

        tmp_path.replace(dest)
    except Exception as exc:
        # Clean up partial file if present
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise RuntimeError(f"Failed to download template file from {url}: {exc}")


def _download_and_extract_archive(base_dir: Path) -> str:
    """
    Download the templates ZIP archive and extract it into ``base_dir``.

    This function is idempotent with respect to extraction: it will overwrite
    existing files with the contents of the archive but does not remove any
    unrelated files that may already reside in ``base_dir``.
    """
    archive_url = _compute_archive_url()
    archive_name = archive_url.rsplit("/", 1)[-1] or "templates.zip"
    archive_path = base_dir / archive_name

    _LOG.info(f"Downloading SNID SAGE template archive from {archive_url}")

    # Interactive progress bar for download (best-effort, cosmetic only)
    use_tty_progress = bool(sys.stdout and sys.stdout.isatty())

    def _print_download_progress(downloaded: int, total: Optional[int], elapsed: float) -> None:
        if not use_tty_progress:
            return

        # Basic throughput estimate (bytes per second)
        speed = downloaded / max(elapsed, 1e-6)

        # Human-friendly units
        def _fmt_size(num_bytes: int) -> str:
            mb = num_bytes / (1024 * 1024)
            if mb >= 1024:
                gb = mb / 1024
                return f"{gb:5.1f} GB"
            return f"{mb:5.1f} MB"

        if total is not None and total > 0:
            frac = min(max(downloaded / total, 0.0), 1.0)
            bar_width = 30
            filled = int(bar_width * frac)
            bar = "#" * filled + "-" * (bar_width - filled)
            percent = frac * 100.0
            msg = (
                f"\r[Downloading] [{bar}] {percent:5.1f}%  "
                f"{_fmt_size(downloaded)}/{_fmt_size(total)}  "
                f"{speed / (1024 * 1024):4.2f} MB/s"
            )
        else:
            bar_width = 30
            # When we don't know total size, just show a spinner-like bar by
            # mapping bytes to a moving position.
            idx = (downloaded // (1024 * 1024)) % bar_width  # 1 MB step
            bar = "".join("#" if i == idx else "-" for i in range(bar_width))
            msg = (
                f"\r[Downloading] [{bar}]  "
                f"{_fmt_size(downloaded)}  "
                f"{speed / (1024 * 1024):4.2f} MB/s"
            )

        try:
            print(msg, end="", flush=True)
        except Exception:
            # If stdout is misbehaving, quietly stop trying to update it.
            # We intentionally do *not* mutate outer-scope flags here to avoid
            # relying on ``nonlocal`` (which can be fragile across Python
            # versions); repeated failures are rare and purely cosmetic.
            return

    _download_file(archive_url, archive_path, progress_cb=_print_download_progress)

    # Ensure we end with a newline after the download progress line
    if use_tty_progress:
        try:
            print()
        except Exception:
            pass

    _LOG.info(f"Extracting template archive into {base_dir}")
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.infolist()
            total_members = len(members)

            use_tty_extract_progress = bool(sys.stdout and sys.stdout.isatty() and total_members > 0)

            def _print_extract_progress(current_index: int, total: int, name: str) -> None:
                if not use_tty_extract_progress:
                    return

                frac = min(max(current_index / total, 0.0), 1.0)
                bar_width = 30
                filled = int(bar_width * frac)
                bar = "#" * filled + "-" * (bar_width - filled)
                percent = frac * 100.0
                display_name = name[:30] + "..." if len(name) > 33 else name

                msg = (
                    f"\r[Extracting]  [{bar}] {percent:5.1f}%  "
                    f"{current_index:4d}/{total:4d}  {display_name:<33}"
                )
                try:
                    print(msg, end="", flush=True)
                except Exception:
                    # Same rationale as in the download progress: if stdout
                    # misbehaves, simply stop trying to update progress.
                    return

            for idx, member in enumerate(members, start=1):
                zf.extract(member, base_dir)
                _print_extract_progress(idx, total_members, member.filename)

            if use_tty_extract_progress:
                try:
                    print()
                except Exception:
                    pass
    except Exception as exc:
        raise RuntimeError(f"Failed to extract templates archive {archive_path}: {exc}")
    finally:
        # The archive itself is no longer needed after extraction; keep tree clean
        try:
            if archive_path.exists():
                archive_path.unlink()
        except Exception:
            # Non-fatal; leftover archive is merely wasted space
            pass

    return archive_url


def download_templates_if_needed(force: bool = False) -> Path:
    """
    Ensure the built-in template bank is available locally and return its path.

    - If ``force=True``, always re-download and overwrite the local copy.
    - Otherwise, do nothing when templates for the current bank version are
      already present.
    """
    base_dir = get_templates_base_dir()

    if not force and is_templates_installed(base_dir):
        _LOG.debug(
            f"Templates already installed in {base_dir} "
            f"(version={TEMPLATE_BANK_VERSION})"
        )
        return base_dir

    # Download (or re-download) all expected files (via a single ZIP archive)
    _LOG.info(f"Preparing to download SNID SAGE templates into {base_dir}")

    total = len(TEMPLATES_FILES)
    # Always give the user a clear, one-line heads-up even when logging is quiet
    try:
        print(
            f"Downloading SNID SAGE templates from GitHub "
            f"({total} files, first-time setup via archive)...",
            flush=True,
        )
    except Exception:
        # Printing is purely cosmetic; never fail download because of it
        pass

    archive_url_used = _download_and_extract_archive(base_dir)

    # Record metadata
    _save_meta(
        base_dir,
        {
            "version": TEMPLATE_BANK_VERSION,
            "files": list(TEMPLATES_FILES),
            "archive_url": archive_url_used,
        },
    )

    _LOG.info(f"Templates downloaded successfully into {base_dir}")
    return base_dir


def get_templates_dir(force_download: bool = False) -> Path:
    """
    Public helper used by the rest of the codebase.

    Returns a :class:`pathlib.Path` pointing to the directory containing
    ``template_index.json`` and the ``templates_*.hdf5`` files.

    Parameters
    ----------
    force_download:
        If True, always re-download the bank even when already present.
    """
    # 0) Prefer templates bundled directly with the package (e.g. Git clone)
    # when available, unless the caller explicitly forces a re-download.
    if not force_download:
        try:
            packaged = _find_packaged_templates_dir()
        except Exception:
            packaged = None
        if packaged is not None:
            _LOG.debug(f"Using packaged templates directory: {packaged}")
            return packaged

    # 1) Fallback to the managed, lazily-downloaded templates bank.
    return download_templates_if_needed(force=force_download)


def cli_download_templates_main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point to pre-download the managed template bank.

    Usage (PowerShell):
        snid-sage-download-templates
        snid-sage-download-templates --force

    Environment:
        - Respects SNID_SAGE_TEMPLATE_DIR if set.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="snid-sage-download-templates",
        description="Download or refresh the SNID SAGE built-in template library",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if templates are already present",
    )
    args = parser.parse_args(argv)

    try:
        target = download_templates_if_needed(force=args.force)
        print(f"Templates are available at: {target}")
        return 0
    except Exception as exc:  # pragma: no cover - CLI convenience
        print(f"Failed to download templates: {exc}", file=sys.stderr)
        return 1


__all__ = [
    "TEMPLATE_BANK_VERSION",
    "TEMPLATES_FILES",
    "get_templates_base_dir",
    "is_templates_installed",
    "download_templates_if_needed",
    "get_templates_dir",
    "cli_download_templates_main",
]



