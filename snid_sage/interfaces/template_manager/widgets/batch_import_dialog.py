"""
Batch Import Dialog
===================

GUI dialog to import templates in bulk from a CSV/TSV file.

Behavior:
- Lets the user pick a CSV/TSV file and map columns.
- Lets the user pick a destination templates directory (defaults to configured user folder).
- Processes rows grouped by object_name, appending epochs to the same template.
- Shows live progress and a compact error report.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from PySide6 import QtWidgets, QtCore

from ..utils.layout_manager import get_template_layout_manager


class BatchImportDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch Import Templates")
        self.layout_manager = get_template_layout_manager()
        self._headers: List[str] = []
        self._rows: List[Dict[str, Any]] = []
        self._csv_path: Optional[Path] = None
        self._dest_dir: Optional[Path] = None
        self._stop_requested = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self.layout_manager.apply_panel_layout(self, layout)

        # File picker
        file_row = QtWidgets.QHBoxLayout()
        self.csv_edit = QtWidgets.QLineEdit()
        self.csv_edit.setPlaceholderText("Select CSV/TSV file with spectra list…")
        browse_btn = self.layout_manager.create_action_button("Browse")
        browse_btn.clicked.connect(self._browse_csv)
        file_row.addWidget(self.csv_edit)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Destination directory picker
        dest_row = QtWidgets.QHBoxLayout()
        self.dest_edit = QtWidgets.QLineEdit()
        self.dest_edit.setPlaceholderText("Destination templates directory (optional: defaults to configured user folder)")
        dest_btn = self.layout_manager.create_action_button("Choose Folder")
        dest_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(self.dest_edit)
        dest_row.addWidget(dest_btn)
        layout.addLayout(dest_row)

        # Column mapping grid
        form = QtWidgets.QFormLayout()
        self.layout_manager.setup_form_layout(form)
        self.name_combo = QtWidgets.QComboBox()
        self.path_combo = QtWidgets.QComboBox()
        self.age_combo = QtWidgets.QComboBox()
        self.redshift_combo = QtWidgets.QComboBox()
        self.type_combo = QtWidgets.QComboBox()
        self.subtype_combo = QtWidgets.QComboBox()
        self.simflag_combo = QtWidgets.QComboBox()
        form.addRow("object_name", self.name_combo)
        form.addRow("spectrum_file_path", self.path_combo)
        form.addRow("age", self.age_combo)
        form.addRow("redshift", self.redshift_combo)
        form.addRow("type", self.type_combo)
        form.addRow("subtype", self.subtype_combo)
        form.addRow("sim_flag", self.simflag_combo)
        layout.addLayout(form)

        # Defaults when columns are missing
        defaults_row = QtWidgets.QHBoxLayout()
        self.default_age = QtWidgets.QDoubleSpinBox()
        self.default_age.setRange(-9999.9, 9999.9)
        self.default_age.setDecimals(3)
        self.default_age.setValue(0.0)
        self.default_redshift = QtWidgets.QDoubleSpinBox()
        self.default_redshift.setRange(0.0, 5.0)
        self.default_redshift.setDecimals(6)
        self.default_redshift.setValue(0.0)
        defaults_row.addWidget(QtWidgets.QLabel("Default age:"))
        defaults_row.addWidget(self.default_age)
        defaults_row.addSpacing(12)
        defaults_row.addWidget(QtWidgets.QLabel("Default redshift:"))
        defaults_row.addWidget(self.default_redshift)
        defaults_row.addStretch()
        layout.addLayout(defaults_row)

        # Progress
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.start_btn = self.layout_manager.create_action_button("Start Import")
        self.start_btn.clicked.connect(self._start_import)
        self.cancel_btn = self.layout_manager.create_action_button("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.start_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        # Try pre-fill destination from configured user folder
        try:
            from snid_sage.shared.utils.paths.user_templates import get_user_templates_dir
            p = get_user_templates_dir(strict=True)
            if p is not None:
                self.dest_edit.setText(str(p))
        except Exception:
            pass

    def _browse_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select CSV/TSV List",
            "",
            "CSV/TSV Files (*.csv *.tsv *.txt);;All Files (*.*)",
        )
        if not path:
            return
        self.csv_edit.setText(path)
        self._csv_path = Path(path)
        self._load_preview_and_headers()

    def _browse_dest(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Destination Templates Folder", "")
        if path:
            self.dest_edit.setText(path)

    def _set_combos(self, headers: List[str]) -> None:
        for combo in [
            self.name_combo,
            self.path_combo,
            self.age_combo,
            self.redshift_combo,
            self.type_combo,
            self.subtype_combo,
            self.simflag_combo,
        ]:
            combo.clear()
            combo.addItem("")
            combo.addItems(headers)
        # Best-effort auto-map
        lower = [h.lower() for h in headers]
        def try_set(combo: QtWidgets.QComboBox, candidates: List[str]) -> None:
            for c in candidates:
                if c in lower:
                    combo.setCurrentText(headers[lower.index(c)])
                    return
        try_set(self.name_combo, ["object_name", "name", "object"]) 
        try_set(self.path_combo, ["spectrum_file_path", "path", "file", "spectrum"]) 
        try_set(self.age_combo, ["age", "phase"]) 
        try_set(self.redshift_combo, ["redshift", "z"]) 
        try_set(self.type_combo, ["type"]) 
        try_set(self.subtype_combo, ["subtype", "sub_type"]) 
        try_set(self.simflag_combo, ["sim_flag", "sim", "is_sim"]) 

    def _load_preview_and_headers(self) -> None:
        if not self._csv_path or not self._csv_path.exists():
            return
        try:
            # Detect delimiter
            with open(self._csv_path, "r", encoding="utf-8", newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
                except Exception:
                    class _D: delimiter = ","
                    dialect = _D()  # type: ignore
                reader = csv.DictReader(f, dialect=dialect)
                self._headers = list(reader.fieldnames or [])
                self._rows = [row for row in reader]
            self._set_combos(self._headers)
            self.status_label.setText(f"Loaded {len(self._rows)} rows; delimiter '{getattr(dialect, 'delimiter', ',')}'")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to read CSV: {e}")
            self._headers = []
            self._rows = []

    def _start_import(self) -> None:
        if not self._rows:
            QtWidgets.QMessageBox.warning(self, "No Data", "Load a CSV/TSV file first.")
            return
        # Validate required mappings
        name_col = (self.name_combo.currentText() or "").strip()
        path_col = (self.path_combo.currentText() or "").strip()
        if not name_col or not path_col:
            QtWidgets.QMessageBox.warning(self, "Missing Mapping", "Map at least object_name and spectrum_file_path.")
            return
        # Resolve destination dir (optional)
        dest_text = (self.dest_edit.text() or "").strip()
        self._dest_dir = Path(dest_text) if dest_text else None
        if self._dest_dir is not None and (not self._dest_dir.exists() or not os.access(self._dest_dir, os.W_OK)):
            QtWidgets.QMessageBox.critical(self, "Invalid Destination", "Selected destination is not writable.")
            return
        # Disable controls while running
        for w in [self.csv_edit, self.dest_edit, self.start_btn]:
            w.setEnabled(False)
        self._run_import(name_col, path_col)

    def _run_import(self, name_col: str, path_col: str) -> None:
        # Column names
        age_col = (self.age_combo.currentText() or "").strip()
        z_col = (self.redshift_combo.currentText() or "").strip()
        type_col = (self.type_combo.currentText() or "").strip()
        subtype_col = (self.subtype_combo.currentText() or "").strip()
        sim_col = (self.simflag_combo.currentText() or "").strip()
        # Group rows by object_name
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for row in self._rows:
            key = (row.get(name_col) or "").strip()
            if not key:
                key = f"unnamed_{len(groups)+1}"
            groups.setdefault(key, []).append(row)

        # Import loop
        total = sum(len(v) for v in groups.values())
        processed = 0
        errors: List[str] = []
        self.progress.setValue(0)
        self.status_label.setText("Starting import…")

        # Resolve base for relative paths
        base_dir = self._csv_path.parent if self._csv_path else Path.cwd()

        try:
            from ..services.template_service import get_template_service
            svc = get_template_service()
            from snid_sage.snid.io import read_spectrum
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to initialize services: {e}")
            return

        for name, rows in groups.items():
            # First row creates (or combines), subsequent rows force combine-only
            for idx, row in enumerate(rows):
                try:
                    raw_path = (row.get(path_col) or "").strip()
                    in_path = Path(raw_path)
                    if not in_path.is_absolute():
                        in_path = (base_dir / in_path).resolve()
                    if not in_path.exists():
                        raise FileNotFoundError(f"Spectrum not found: {in_path}")
                    wave, flux = read_spectrum(str(in_path))
                    # Coerce metadata
                    def _f(v: Any, default: float) -> float:
                        try:
                            return float(v)
                        except Exception:
                            return float(default)
                    age = _f(row.get(age_col), self.default_age.value()) if age_col else float(self.default_age.value())
                    redshift = _f(row.get(z_col), self.default_redshift.value()) if z_col else float(self.default_redshift.value())
                    ttype = (row.get(type_col) or "Unknown").strip() if type_col else "Unknown"
                    subtype = (row.get(subtype_col) or "").strip() if subtype_col else ""
                    sim_flag = row.get(sim_col)
                    try:
                        sim_flag_val = int(sim_flag) if sim_flag is not None and str(sim_flag).strip() != "" else 0
                    except Exception:
                        sim_flag_val = 0

                    # If a destination folder is chosen, temporarily override user dir via service method variants
                    # For now, call the standard service and let it place into configured user folder if dest not given
                    ok = False
                    if self._dest_dir is None:
                        ok = svc.add_template_from_arrays(
                            name=name,
                            ttype=ttype,
                            subtype=subtype,
                            age=float(age),
                            redshift=float(redshift),
                            wave=np.asarray(wave, dtype=float),
                            flux=np.asarray(flux, dtype=float),
                            combine_only=(idx > 0),
                            sim_flag=sim_flag_val,
                            profile_id=getattr(svc, 'get_active_profile', lambda: None)(),
                        )
                    else:
                        ok = svc.add_template_from_arrays(
                            name=name,
                            ttype=ttype,
                            subtype=subtype,
                            age=float(age),
                            redshift=float(redshift),
                            wave=np.asarray(wave, dtype=float),
                            flux=np.asarray(flux, dtype=float),
                            combine_only=(idx > 0),
                            target_dir=self._dest_dir,
                            sim_flag=sim_flag_val,
                            profile_id=getattr(svc, 'get_active_profile', lambda: None)(),
                        )
                    if not ok:
                        raise RuntimeError("Service rejected template append/create")
                except Exception as e:
                    errors.append(f"{name}: {e}")
                finally:
                    processed += 1
                    pct = int(100.0 * processed / max(1, total))
                    self.progress.setValue(pct)
                    self.status_label.setText(f"Imported {processed}/{total} rows; errors: {len(errors)}")
                    QtWidgets.QApplication.processEvents()

        # Write error report next to CSV
        if errors and self._csv_path:
            try:
                err_path = self._csv_path.with_suffix(self._csv_path.suffix + ".errors.txt")
                with open(err_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(errors))
                self.status_label.setText(self.status_label.text() + f"  (Report: {err_path})")
            except Exception:
                pass

        if errors:
            QtWidgets.QMessageBox.warning(self, "Import Completed with Errors", f"Imported with {len(errors)} errors. See status for report path.")
        else:
            QtWidgets.QMessageBox.information(self, "Import Completed", "All templates imported successfully.")
        self.accept()


