#!/usr/bin/env python3
"""
Export WISEREP / SNID-SAGE batch results into a browser-friendly dataset for
`docs/table/` local viewing.

This intentionally avoids importing the PySide6 GUI module so it can run in
headless environments.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd


# --- Flag ranking (match GUI behaviour) ---------------------------------------

FLAG_SORT_ORDER = ["no comp", "very low", "low", "medium", "high"]
FLAG_SORT_RANK = {name: rank for rank, name in enumerate(FLAG_SORT_ORDER)}


# --- String normalization + ID heuristics (copied from GUI logic) -------------

def _normalize_string(value: object) -> str:
    """Normalize string-like values from CSV (treat NaN/None/blank as empty)."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    return s


_EVENT_ID_RE = re.compile(r"(?:19|20)\d{2}[a-z]{1,3}", re.IGNORECASE)
_EVENT_ID_WITH_SUFFIX_RE = re.compile(
    r"(?:19|20)\d{2}[a-z]{1,3}(?=(?:early|late|max|peak))", re.IGNORECASE
)


def _extract_event_id(text: str) -> str:
    """
    Extract a compact event ID (e.g. 1999bw, 2014ej, 2008jd, 2019udc) from a
    name or template string.
    """
    raw = _normalize_string(text).lower()
    if not raw or raw in {"n/a", "na"}:
        return ""

    s = raw.replace(" ", "").replace("_", "")

    m = _EVENT_ID_WITH_SUFFIX_RE.search(s)
    if m:
        return m.group(0)

    m = _EVENT_ID_RE.search(s)
    if m:
        return m.group(0)

    # Survey-style internal names with coordinates
    if "-" in s:
        core = s.split("-", 1)[0]
        if len(core) >= 8 and any(ch.isdigit() for ch in core):
            return core

    # Fallback: moderately long alphanumeric token containing digits
    if len(s) >= 6 and any(ch.isdigit() for ch in s) and not s.isdigit():
        return s

    return ""


def _filter_success_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows where Success is not false, if such a column exists."""
    success_col = None
    for name in ("Success", "success"):
        if name in df.columns:
            success_col = name
            break
    if success_col is None:
        return df

    col = df[success_col]
    if col.dtype == bool or col.dtype == "bool":
        return df[col]

    false_like = {"false", "0", "no", "nan", "none", ""}
    as_str = col.astype(str).str.strip().str.lower()
    mask = ~as_str.isin(false_like)
    return df[mask]


def _choose_spectra_columns(columns: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Heuristically pick (ascii_file_column, official_name_column) from spectra CSV."""
    ascii_col = None
    name_col = None
    best_ascii_score = -1
    best_name_score = -1

    for col in columns:
        low = col.lower().strip()

        ascii_score = 0
        if "ascii" in low:
            ascii_score += 3
        if "file" in low or "filename" in low or low == "file":
            ascii_score += 2
        if "spec" in low or "spectrum" in low:
            ascii_score += 1
        if ascii_score > best_ascii_score:
            best_ascii_score = ascii_score
            ascii_col = col

        name_score = 0
        if "iau" in low:
            name_score += 3
        if "tns" in low:
            name_score += 2
        if "object" in low:
            name_score += 1
        if "name" in low:
            name_score += 1
        if name_score > best_name_score:
            best_name_score = name_score
            name_col = col

    if best_ascii_score <= 0 or best_name_score <= 0:
        return None, None
    return ascii_col, name_col


def _choose_spectra_type_column(columns: List[str]) -> Optional[str]:
    """Heuristically select a TNS type column from the spectra CSV."""
    type_col = None
    best_score = -1
    for col in columns:
        low = col.lower().strip()
        score = 0
        if "obj" in low or "object" in low:
            score += 2
        if "type" in low:
            score += 2
        if "tns" in low:
            score += 1
        if score > best_score:
            best_score = score
            type_col = col
    return type_col if best_score > 0 else None


def _choose_internal_name_column(columns: List[str]) -> Optional[str]:
    """Heuristically select an internal-name column from the spectra CSV."""
    internal_col = None
    best_score = -1
    for col in columns:
        low = col.lower().strip()
        score = 0
        if "internal" in low:
            score += 3
        if "alt" in low:
            score += 2
        if "name" in low or "names" in low:
            score += 1
        if score > best_score:
            best_score = score
            internal_col = col
    return internal_col if best_score > 0 else None


def _choose_ra_dec_columns(columns: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Heuristically select (ra_col, dec_col) from spectra CSV.

    Intended to match columns like "Obj. RA" / "Obj. DEC" or "RA" / "DEC".
    """
    ra_col = None
    dec_col = None
    best_ra = -1
    best_dec = -1

    for col in columns:
        low = col.lower().strip()

        ra_score = 0
        if "ra" in low:
            ra_score += 3
        if "obj" in low or "object" in low:
            ra_score += 1
        if ra_score > best_ra:
            best_ra = ra_score
            ra_col = col

        dec_score = 0
        if "dec" in low:
            dec_score += 3
        if "obj" in low or "object" in low:
            dec_score += 1
        if dec_score > best_dec:
            best_dec = dec_score
            dec_col = col

    if best_ra <= 0 or best_dec <= 0:
        return None, None
    return ra_col, dec_col


def _stem_key_from_pathlike(raw_file: str) -> str:
    norm = raw_file.replace("\\", "/")
    base = norm.split("/")[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    return stem.strip().lower()


def build_official_name_mapping(spectra_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not spectra_path.exists():
        return mapping
    spectra_df = pd.read_csv(spectra_path, dtype=str, low_memory=False)
    if spectra_df.empty:
        return mapping

    ascii_col, name_col = _choose_spectra_columns(list(spectra_df.columns))
    if not ascii_col or not name_col:
        return mapping

    for _, row in spectra_df.iterrows():
        raw_file = _normalize_string(row.get(ascii_col, ""))
        official_name = _normalize_string(row.get(name_col, ""))
        if not raw_file or not official_name:
            continue
        key = _stem_key_from_pathlike(raw_file)
        if key and key not in mapping:
            mapping[key] = official_name
    return mapping


def build_tns_type_mapping(spectra_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not spectra_path.exists():
        return mapping
    spectra_df = pd.read_csv(spectra_path, dtype=str, low_memory=False)
    if spectra_df.empty:
        return mapping

    ascii_col, _ = _choose_spectra_columns(list(spectra_df.columns))
    type_col = _choose_spectra_type_column(list(spectra_df.columns))
    if not ascii_col or not type_col:
        return mapping

    for _, row in spectra_df.iterrows():
        raw_file = _normalize_string(row.get(ascii_col, ""))
        tns_type = _normalize_string(row.get(type_col, ""))
        if not raw_file or not tns_type:
            continue
        key = _stem_key_from_pathlike(raw_file)
        if key and key not in mapping:
            mapping[key] = tns_type
    return mapping


def build_internal_name_mapping(spectra_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not spectra_path.exists():
        return mapping
    spectra_df = pd.read_csv(spectra_path, dtype=str, low_memory=False)
    if spectra_df.empty:
        return mapping

    ascii_col, _ = _choose_spectra_columns(list(spectra_df.columns))
    internal_col = _choose_internal_name_column(list(spectra_df.columns))
    if not ascii_col or not internal_col:
        return mapping

    for _, row in spectra_df.iterrows():
        raw_file = _normalize_string(row.get(ascii_col, ""))
        internal_name = _normalize_string(row.get(internal_col, ""))
        if not raw_file or not internal_name:
            continue
        key = _stem_key_from_pathlike(raw_file)
        if key and key not in mapping:
            mapping[key] = internal_name
    return mapping


def build_ra_dec_mapping(spectra_path: Path) -> Tuple[Dict[str, object], Dict[str, object]]:
    """
    Build mappings from spectrum filename stem -> RA/DEC values from spectra CSV.

    Returned values are either float (when parseable) or the original string.
    """
    ra_map: Dict[str, object] = {}
    dec_map: Dict[str, object] = {}
    if not spectra_path.exists():
        return ra_map, dec_map

    spectra_df = pd.read_csv(spectra_path, dtype=str, low_memory=False)
    if spectra_df.empty:
        return ra_map, dec_map

    ascii_col, _ = _choose_spectra_columns(list(spectra_df.columns))
    ra_col, dec_col = _choose_ra_dec_columns(list(spectra_df.columns))
    if not ascii_col or not ra_col or not dec_col:
        return ra_map, dec_map

    def _maybe_float(v: str) -> object:
        s = _normalize_string(v)
        if not s:
            return ""
        try:
            return float(s)
        except Exception:
            return s

    for _, row in spectra_df.iterrows():
        raw_file = _normalize_string(row.get(ascii_col, ""))
        if not raw_file:
            continue
        key = _stem_key_from_pathlike(raw_file)
        if not key:
            continue

        if key not in ra_map:
            ra_map[key] = _maybe_float(str(row.get(ra_col, "")))
        if key not in dec_map:
            dec_map[key] = _maybe_float(str(row.get(dec_col, "")))

    return ra_map, dec_map


def _lookup_by_file_key(filename: object, mapping: Dict[str, str]) -> str:
    if not mapping:
        return ""
    key = _stem_key_from_pathlike(_normalize_string(filename))
    return mapping.get(key, "")


def _pick_best_template_field(df: pd.DataFrame) -> Optional[str]:
    for name in ("best_template", "best_template_method1", "best_template_method2"):
        if name in df.columns:
            return name
    return None


def _label_for_column(col: str) -> str:
    if col == "official_name":
        return "IAU name"
    if col == "internal_name":
        return "Internal name/s"
    if col == "tns_type":
        return "WISEREP type"
    if col == "type":
        return "SAGE type"
    if col == "subtype":
        return "SAGE subtype"
    if col == "z":
        return "z"
    if col == "z_err":
        return "z error"
    if col == "match_kind":
        return "Match kind"
    if col == "spectra_file_name":
        return "Spectra file name"
    if col == "ra":
        return "RA"
    if col == "dec":
        return "DEC"
    label = (
        col.replace("_method1", " (M1)")
        .replace("_method2", " (M2)")
        .replace("_", " ")
        .title()
    )
    return label


@dataclass(frozen=True)
class ExportPaths:
    out_dir: Path
    data_json: Path
    meta_json: Path


def _resolve_output_paths(out_dir: Path) -> ExportPaths:
    out_dir.mkdir(parents=True, exist_ok=True)
    return ExportPaths(
        out_dir=out_dir,
        data_json=out_dir / "wiserep_results.json",
        meta_json=out_dir / "meta.json",
    )


def _latest_spectra_csv(wiserep_dir: Path) -> Optional[Path]:
    candidates = sorted(wiserep_dir.glob("spectra_*.csv"))
    return candidates[-1] if candidates else None


def _choose_display_columns(df: pd.DataFrame, max_columns: int = 16) -> List[str]:
    """Mimic the GUI column selection behaviour (cap at ~16 payload columns)."""
    key_cols = [
        "type",
        "subtype",
        "z",
        "z_err",
        "Q_cluster",
        "match_quality",
        "type_confidence",
        "subtype_confidence",
        "age",
        "age_err",
    ]

    display_cols: List[str] = []
    for col in key_cols:
        if col in df.columns:
            display_cols.append(col)
        elif f"{col}_method1" in df.columns:
            display_cols.append(f"{col}_method1")
        elif f"{col}_method2" in df.columns:
            display_cols.append(f"{col}_method2")

    for col in df.columns:
        if col in display_cols:
            continue
        if col in {"_merge"}:
            continue
        if col in {"file", "path"}:
            continue
        # Hide internal/auxiliary columns that we don't want in the web table.
        # (Still available in the raw CSV if needed.)
        if col.lower() in {"zfixed"}:
            continue
        display_cols.append(col)

    return display_cols[:max_columns]


def export_wiserep_web_table(
    *,
    results_csv: Path,
    spectra_csv: Optional[Path],
    out_dir: Path,
    max_payload_columns: int = 16,
    limit_rows: Optional[int] = None,
) -> ExportPaths:
    paths = _resolve_output_paths(out_dir)

    df = pd.read_csv(results_csv, low_memory=False)
    df = _filter_success_rows(df)
    if limit_rows is not None and limit_rows > 0:
        df = df.head(limit_rows)

    # Add stable index for deterministic sorts in the browser
    df = df.copy()
    df["__index"] = list(range(len(df)))

    # Build mappings from spectra catalog (if available)
    official_map: Dict[str, str] = {}
    internal_map: Dict[str, str] = {}
    tns_type_map: Dict[str, str] = {}
    ra_map: Dict[str, object] = {}
    dec_map: Dict[str, object] = {}
    if spectra_csv is not None and spectra_csv.exists():
        official_map = build_official_name_mapping(spectra_csv)
        internal_map = build_internal_name_mapping(spectra_csv)
        tns_type_map = build_tns_type_mapping(spectra_csv)
        ra_map, dec_map = build_ra_dec_mapping(spectra_csv)

    if "file" in df.columns:
        df["official_name"] = df["file"].map(lambda x: _lookup_by_file_key(x, official_map))
        df["internal_name"] = df["file"].map(lambda x: _lookup_by_file_key(x, internal_map))
        df["tns_type"] = df["file"].map(lambda x: _lookup_by_file_key(x, tns_type_map))
        df["ra"] = df["file"].map(lambda x: ra_map.get(_stem_key_from_pathlike(_normalize_string(x)), ""))
        df["dec"] = df["file"].map(lambda x: dec_map.get(_stem_key_from_pathlike(_normalize_string(x)), ""))
    else:
        df["official_name"] = ""
        df["internal_name"] = ""
        df["tns_type"] = ""
        df["ra"] = ""
        df["dec"] = ""

    # Derive a short "Spectra file name" field from `path` (basename only).
    if "path" in df.columns:
        df["spectra_file_name"] = df["path"].map(
            lambda p: Path(_normalize_string(p).replace("\\", "/")).name
        )
    else:
        df["spectra_file_name"] = ""

    best_template_field = _pick_best_template_field(df)

    def _classify_match_kind(row: pd.Series) -> str:
        best_template = _normalize_string(row.get(best_template_field, "")) if best_template_field else ""
        template_id = _extract_event_id(best_template)

        official_name = _normalize_string(row.get("official_name", ""))
        internal_name = _normalize_string(row.get("internal_name", ""))
        file_name = _normalize_string(row.get("file", ""))
        obj_id = _extract_event_id(official_name) or _extract_event_id(internal_name) or _extract_event_id(file_name)

        if template_id and obj_id:
            return "self_template" if template_id == obj_id else "new_object"
        return "unknown"

    df["match_kind"] = df.apply(_classify_match_kind, axis=1)

    payload_cols = _choose_display_columns(df, max_columns=max_payload_columns)
    # Always try to keep best_template visible if present
    if best_template_field and best_template_field not in payload_cols:
        payload_cols = (payload_cols[:-1] + [best_template_field]) if payload_cols else [best_template_field]

    # Final columns: identity fields first, then payload, then match_kind
    final_cols: List[str] = [
        "official_name",
        "internal_name",
        "ra",
        "dec",
        "tns_type",
        "type",
        "subtype",
    ]
    for col in payload_cols:
        if col not in final_cols and col != "file":
            final_cols.append(col)

    # Put the spectra filename at the very end of the visible table.
    if "spectra_file_name" not in final_cols:
        final_cols.append("spectra_file_name")
    if "match_kind" not in final_cols:
        final_cols.append("match_kind")
    # Keep internal stable index (not displayed by default but useful)
    if "__index" not in final_cols:
        final_cols.append("__index")

    df_out = df[final_cols].copy()
    # IMPORTANT: ensure strict JSON for browser consumption.
    # Python's json module can emit NaN/Infinity tokens by default, which are NOT
    # valid JSON in browsers. Pandas will serialize NaN as `null` in to_json().
    data_json_text = df_out.to_json(orient="records", force_ascii=False)
    paths.data_json.write_text(data_json_text, encoding="utf-8")

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_results_csv": str(results_csv),
        "source_spectra_csv": str(spectra_csv) if spectra_csv else None,
        "rows": int(len(df_out)),
        # Columns shown in the table UI. Some fields (e.g. match_kind) are kept
        # in the data JSON for functionality but intentionally hidden from view.
        "columns": [
            {
                "key": c,
                "label": _label_for_column(c),
                "is_flag": c
                in {
                    "match_quality",
                    "type_confidence",
                    "subtype_confidence",
                },
            }
            for c in final_cols
            if c not in {"__index", "match_kind"} and c.lower() not in {"zfixed"}
        ],
        "flag_sort_rank": FLAG_SORT_RANK,
    }
    with paths.meta_json.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, allow_nan=False)

    return paths


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Export WISEREP/SNID-SAGE results into docs/table/data/ JSON."
    )
    p.add_argument(
        "--results",
        type=Path,
        default=Path("WISEREP_RESULTS") / "batch_results_WISEREP.csv",
        help="Path to the WISEREP batch results CSV.",
    )
    p.add_argument(
        "--spectra",
        type=Path,
        default=None,
        help="Path to the spectra_*.csv catalog (optional; auto-picks latest if omitted).",
    )
    p.add_argument(
        "--wiserep-dir",
        type=Path,
        default=Path("WISEREP_RESULTS"),
        help="Directory to search for spectra_*.csv when --spectra is not provided.",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs") / "table" / "data",
        help="Output directory for wiserep_results.json and meta.json.",
    )
    p.add_argument(
        "--max-cols",
        type=int,
        default=16,
        help="Max number of payload columns (excluding identity columns).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit for quick testing.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    spectra = args.spectra
    if spectra is None:
        spectra = _latest_spectra_csv(args.wiserep_dir)

    export_wiserep_web_table(
        results_csv=args.results,
        spectra_csv=spectra,
        out_dir=args.out_dir,
        max_payload_columns=args.max_cols,
        limit_rows=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

