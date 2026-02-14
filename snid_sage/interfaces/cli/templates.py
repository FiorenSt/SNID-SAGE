"""
CLI: Templates Subcommands
==========================

Commands for managing SNID template libraries, including import from
legacy SNID .lnw format and CSV-based bulk import.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def add_arguments(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="templates_cmd")

    # import-lnw: convert a directory of .lnw files to HDF5 storage
    lnw = sub.add_parser(
        "import-lnw",
        help="Convert a directory of legacy SNID .lnw templates to HDF5 format",
    )
    lnw.add_argument("source_dir", help="Directory containing .lnw template files")
    lnw.add_argument(
        "-o", "--output",
        help="Output directory for HDF5 files (default: source_dir)",
    )

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


def _import_lnw(args: argparse.Namespace) -> int:
    """Convert a directory of .lnw templates to SNID-SAGE HDF5 format."""
    import h5py
    from snid_sage.snid.io import read_template
    from snid_sage.snid.preprocessing import log_rebin, init_wavelength_grid

    src = Path(args.source_dir)
    if not src.is_dir():
        print(f"[ERROR] Not a directory: {src}")
        return 1

    lnw_files = sorted(src.glob("*.lnw"))
    if not lnw_files:
        print(f"[ERROR] No .lnw files found in {src}")
        return 1

    out = Path(args.output) if args.output else src
    out.mkdir(parents=True, exist_ok=True)

    # Standard optical grid parameters
    NW = 1024
    W0 = 2500.0
    W1 = 10000.0
    init_wavelength_grid(num_points=NW, min_wave=W0, max_wave=W1)
    DWLOG = np.log(W1 / W0) / NW
    standard_log_wave = W0 * np.exp((np.arange(NW) + 0.5) * DWLOG)

    print(f"Reading {len(lnw_files)} .lnw files from {src} ...")

    templates_by_type: Dict[str, list] = defaultdict(list)
    seen_names: set = set()
    skipped = 0
    total_epochs = 0

    for lnw_file in lnw_files:
        try:
            tpl = read_template(str(lnw_file))
        except Exception as e:
            print(f"  [WARN] Skipping {lnw_file.name}: {e}")
            skipped += 1
            continue

        sn_type = tpl.get("type", "Unknown")
        subtype = tpl.get("subtype", "Unknown")
        name = tpl["name"]
        nepoch = tpl.get("nepoch", 1)
        ages = tpl.get("ages", [0.0])
        wave = tpl["wave"]  # already Angstroms
        flux_matrix = tpl.get("flux_matrix", tpl["flux"].reshape(1, -1))

        for epoch_idx in range(nepoch):
            epoch_age = ages[epoch_idx] if epoch_idx < len(ages) else 0.0
            if epoch_age == -999.0:
                continue

            epoch_flux = flux_matrix[epoch_idx]
            try:
                _, rebinned_flux = log_rebin(wave, epoch_flux)
            except Exception:
                continue
            if len(rebinned_flux) != NW:
                continue

            fft = np.fft.fft(rebinned_flux)

            # Build unique epoch name
            if nepoch > 1:
                epoch_name = f"{name}_ep{epoch_idx}_age{epoch_age:+.1f}"
            else:
                epoch_name = name
            base = epoch_name
            counter = 1
            while epoch_name in seen_names:
                epoch_name = f"{base}_{counter}"
                counter += 1
            seen_names.add(epoch_name)

            templates_by_type[sn_type].append({
                "name": epoch_name,
                "type": sn_type,
                "subtype": subtype,
                "age": epoch_age,
                "redshift": tpl.get("delta", 0.0),
                "flux": rebinned_flux,
                "fft": fft,
            })
            total_epochs += 1

    if total_epochs == 0:
        print("[ERROR] No valid template epochs extracted.")
        return 1

    print(f"Converted {total_epochs} template epochs across {len(templates_by_type)} types"
          + (f" (skipped {skipped} files)" if skipped else ""))
    for t, entries in sorted(templates_by_type.items()):
        print(f"  {t}: {len(entries)}")

    # Write HDF5 files per type
    for sn_type, entries in templates_by_type.items():
        safe_type = sn_type.replace("/", "_").replace("-", "_").replace(" ", "_")
        h5_path = out / f"templates_{safe_type}.hdf5"

        with h5py.File(h5_path, "w") as f:
            meta = f.create_group("metadata")
            meta.attrs["version"] = "2.0"
            meta.attrs["created_date"] = time.time()
            meta.attrs["template_count"] = len(entries)
            meta.attrs["supernova_type"] = sn_type
            meta.attrs["grid_rebinned"] = True
            meta.attrs["NW"] = NW
            meta.attrs["W0"] = W0
            meta.attrs["W1"] = W1
            meta.attrs["DWLOG"] = DWLOG
            meta.attrs["profile_id"] = "optical"
            meta.create_dataset("standard_wavelength", data=standard_log_wave)

            tpl_group = f.create_group("templates")
            for entry in entries:
                g = tpl_group.create_group(entry["name"])
                g.create_dataset("flux", data=entry["flux"])
                g.create_dataset("fft_real", data=entry["fft"].real)
                g.create_dataset("fft_imag", data=entry["fft"].imag)
                g.attrs["type"] = entry["type"]
                g.attrs["subtype"] = entry["subtype"]
                g.attrs["age"] = entry["age"]
                g.attrs["redshift"] = entry["redshift"]
                g.attrs["epochs"] = 1
                g.attrs["rebinned"] = True

        print(f"  Wrote {h5_path.name} ({len(entries)} templates)")

    # Write template_index.json
    index: Dict[str, Any] = {
        "version": "2.0",
        "created_date": time.time(),
        "template_count": total_epochs,
        "grid_rebinned": True,
        "grid_params": {"NW": NW, "W0": W0, "W1": W1, "DWLOG": DWLOG},
        "profile_id": "optical",
        "templates": {},
        "by_type": {},
    }
    for sn_type, entries in templates_by_type.items():
        safe_type = sn_type.replace("/", "_").replace("-", "_").replace(" ", "_")
        storage_file = f"templates_{safe_type}.hdf5"
        type_info: Dict[str, Any] = {
            "count": len(entries),
            "storage_file": storage_file,
            "template_names": [],
        }
        for entry in entries:
            index["templates"][entry["name"]] = {
                "type": entry["type"],
                "subtype": entry["subtype"],
                "redshift": entry["redshift"],
                "epochs": 1,
                "storage_file": storage_file,
            }
            type_info["template_names"].append(entry["name"])
        index["by_type"][sn_type] = type_info

    index_path = out / "template_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\nDone! {total_epochs} templates -> {out}")
    print(f"Use with:  sage identify <spectrum> {out}")
    return 0


def main(args: argparse.Namespace) -> int:
    cmd = getattr(args, "templates_cmd", None)

    if cmd == "import-lnw":
        return _import_lnw(args)

    if cmd != "import-csv":
        print("No templates subcommand selected. Use 'import-lnw' or 'import-csv'.")
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


