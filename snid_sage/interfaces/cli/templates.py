"""
CLI: Templates Subcommands
==========================

Add CSV-based bulk import for templates with multi-epoch support.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def add_arguments(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="templates_cmd")

    imp = sub.add_parser("import-csv", help="Import templates in bulk from a CSV/TSV file")
    imp.add_argument("file", help="Path to CSV/TSV file with spectra list")
    imp.add_argument("--dest", help="Destination templates directory (defaults to configured user folder)")
    imp.add_argument("--delimiter", choices=[",", "\t", ";"], help="Explicit delimiter (auto-detect if omitted)")
    imp.add_argument("--profile", choices=["optical", "onir"], help="Profile for rebinned storage (optical|onir)")
    imp.add_argument("--name-column", default="object_name")
    imp.add_argument("--path-column", default="spectrum_file_path")
    imp.add_argument("--age-column", default="age")
    imp.add_argument("--redshift-column", default="redshift")
    imp.add_argument("--type-column", default="type")
    imp.add_argument("--subtype-column", default="subtype")
    imp.add_argument("--sim-flag-column", default="sim_flag")
    imp.add_argument("--default-age", type=float, default=0.0)
    imp.add_argument("--default-redshift", type=float, default=0.0)


def main(args: argparse.Namespace) -> int:
    if getattr(args, "templates_cmd", None) != "import-csv":
        print("No templates subcommand selected.")
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return 1

    dest_dir: Optional[Path] = Path(args.dest) if getattr(args, "dest", None) else None
    if dest_dir is not None and (not dest_dir.exists() or not os.access(dest_dir, os.W_OK)):
        print(f"[ERROR] Destination not writable: {dest_dir}")
        return 1

    # Load CSV
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            if getattr(args, "delimiter", None):
                class _D: pass
                dialect = _D()  # type: ignore
                setattr(dialect, "delimiter", args.delimiter)
            else:
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
                except Exception:
                    class _D: pass
                    dialect = _D()  # type: ignore
                    setattr(dialect, "delimiter", ",")
            reader = csv.DictReader(f, dialect=dialect)
            headers = [h for h in (reader.fieldnames or [])]
            rows: List[Dict[str, Any]] = [r for r in reader]
    except Exception as e:
        print(f"[ERROR] Failed to read CSV: {e}")
        return 1

    base_dir = file_path.parent
    name_col = args.name_column
    path_col = args.path_column
    age_col = args.age_column
    z_col = args.redshift_column
    type_col = args.type_column
    subtype_col = args.subtype_column
    sim_col = args.sim_flag_column

    # Group rows
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        nm = (row.get(name_col) or "").strip()
        if not nm:
            nm = f"unnamed_{len(groups)+1}"
        groups.setdefault(nm, []).append(row)

    try:
        from snid_sage.interfaces.template_manager.services.template_service import get_template_service
        svc = get_template_service()
        from snid_sage.snid.io import read_spectrum
    except Exception as e:
        print(f"[ERROR] Failed to initialize services: {e}")
        return 1

    # Apply CLI-selected profile if provided
    cli_profile = getattr(args, 'profile', None)
    if cli_profile:
        try:
            svc.set_active_profile(cli_profile)
        except Exception as e:
            print(f"[WARN] Failed to set profile '{cli_profile}': {e}")

    total = sum(len(v) for v in groups.values())
    processed = 0
    errors: List[str] = []

    for name, rs in groups.items():
        for idx, row in enumerate(rs):
            try:
                raw_path = (row.get(path_col) or "").strip()
                p = Path(raw_path)
                if not p.is_absolute():
                    p = (base_dir / p).resolve()
                if not p.exists():
                    raise FileNotFoundError(f"Spectrum not found: {p}")
                wave, flux = read_spectrum(str(p))
                # Coerce fields
                def _f(v: Any, default: float) -> float:
                    try:
                        return float(v)
                    except Exception:
                        return float(default)
                age = _f(row.get(age_col), args.default_age)
                z = _f(row.get(z_col), args.default_redshift)
                ttype = (row.get(type_col) or "Unknown").strip()
                subtype = (row.get(subtype_col) or "").strip()
                try:
                    sim_flag = int(row.get(sim_col)) if row.get(sim_col) not in (None, "") else 0
                except Exception:
                    sim_flag = 0

                ok = svc.add_template_from_arrays(
                    name=name,
                    ttype=ttype,
                    subtype=subtype,
                    age=age,
                    redshift=z,
                    wave=np.asarray(wave, dtype=float),
                    flux=np.asarray(flux, dtype=float),
                    combine_only=(idx > 0),
                    target_dir=dest_dir,
                    sim_flag=sim_flag,
                    profile_id=getattr(svc, 'get_active_profile', lambda: None)(),
                )
                if not ok:
                    raise RuntimeError("Service rejected template append/create")
            except Exception as e:
                errors.append(f"{name}: {e}")
            finally:
                processed += 1
                if processed % 50 == 0 or processed == total:
                    print(f"Progress: {processed}/{total}")

    if errors:
        err_path = file_path.with_suffix(file_path.suffix + ".errors.txt")
        try:
            with open(err_path, "w", encoding="utf-8") as f:
                f.write("\n".join(errors))
            print(f"Completed with {len(errors)} errors. Report: {err_path}")
        except Exception:
            print(f"Completed with {len(errors)} errors. Failed to write error report.")
        return 2

    print("Import completed successfully.")
    return 0


