from __future__ import annotations

from typing import Optional, List
from pathlib import Path

from PySide6 import QtWidgets, QtCore

try:
    from snid_sage.shared.utils.paths.user_templates import (
        discover_legacy_user_templates,
        get_default_user_templates_dir,
        set_user_templates_dir,
    )
except Exception:
    discover_legacy_user_templates = None  # type: ignore
    get_default_user_templates_dir = None  # type: ignore
    set_user_templates_dir = None  # type: ignore


class UserTemplatesFolderDialog(QtWidgets.QDialog):
    """Dialog to select/adopt a User Templates folder."""

    folder_selected = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select User Templates Folder")
        self.setModal(True)
        self._setup_ui()
        self._load_candidates()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(
            "Choose where to store your User Templates.\n"
            "You can adopt an existing folder or choose a new one."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.candidates_list = QtWidgets.QListWidget()
        layout.addWidget(self.candidates_list)

        btn_row = QtWidgets.QHBoxLayout()
        self.choose_btn = QtWidgets.QPushButton("Choose Folder…")
        self.choose_btn.clicked.connect(self._choose_folder)
        btn_row.addWidget(self.choose_btn)

        self.adopt_btn = QtWidgets.QPushButton("Adopt Selected")
        self.adopt_btn.clicked.connect(self._adopt_selected)
        btn_row.addWidget(self.adopt_btn)

        btn_row.addStretch(1)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def _load_candidates(self) -> None:
        self.candidates_list.clear()
        paths: List[Path] = []

        # 1) Recommended sibling to managed built-ins: <managed>/User_templates
        try:
            if get_default_user_templates_dir is not None:
                default_dir = get_default_user_templates_dir()
                if isinstance(default_dir, Path):
                    paths.append(default_dir)
        except Exception:
            pass

        # 2) Discover existing user libraries
        try:
            if discover_legacy_user_templates is not None:
                legacy_paths = discover_legacy_user_templates()
                paths.extend(legacy_paths or [])
        except Exception:
            pass

        # De-duplicate while preserving order
        seen = set()
        unique_paths: List[Path] = []
        for p in paths:
            try:
                key = str(Path(p).resolve())
            except Exception:
                key = str(p)
            if key in seen:
                continue
            seen.add(key)
            unique_paths.append(Path(p))

        for p in unique_paths:
            self.candidates_list.addItem(str(p))

        # Select the first (typically the recommended) entry by default
        if self.candidates_list.count() > 0:
            self.candidates_list.setCurrentRow(0)

    def _choose_folder(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select User Templates Folder")
        if not path:
            return
        try:
            if set_user_templates_dir is not None:
                set_user_templates_dir(Path(path))
            self.folder_selected.emit(str(path))
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to set folder: {e}")

    def _adopt_selected(self) -> None:
        item = self.candidates_list.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "No Selection", "Select a folder to adopt or choose a new one.")
            return
        path = item.text().strip()
        if not path:
            return
        try:
            if set_user_templates_dir is not None:
                set_user_templates_dir(Path(path))
            self.folder_selected.emit(path)
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to adopt folder: {e}")


