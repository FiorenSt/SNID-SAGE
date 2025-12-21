"""
Template Tree Widget
===================

Tree widget for displaying and selecting templates organized by type/subtype.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from PySide6 import QtWidgets, QtCore

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('template_manager.tree')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('template_manager.tree')


class TemplateTreeWidget(QtWidgets.QTreeWidget):
    """Custom tree widget for displaying templates by type/subtype"""
    
    template_selected = QtCore.Signal(str, dict)  # template_name, template_info
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Template", "Type"])
        self.setSelectionMode(QtWidgets.QTreeWidget.SingleSelection)
        self.itemClicked.connect(self._on_item_clicked)
        # Ensure keyboard navigation updates selection preview
        try:
            self.currentItemChanged.connect(self._on_current_item_changed)
        except Exception:
            pass
        # Ensure the widget can accept focus for arrow key navigation
        try:
            self.setFocusPolicy(QtCore.Qt.StrongFocus)
        except Exception:
            pass
        self._source_mode = 'Combined'  # 'Default' | 'User' | 'Combined'
        # Whether to show (visible/total) counts in the type headers
        self._show_counts = False
        
        # Load templates on initialization
        self.load_templates()

    def set_show_counts(self, show: bool) -> None:
        """Enable/disable showing (visible/total) counts next to type names."""
        try:
            self._show_counts = bool(show)
            # Re-apply current filter to refresh labels
            # Infer current filters by reading visible state (best-effort)
            # Default to no search and all types
            self.filter_templates("", "All Types")
        except Exception:
            pass
        
    def set_source_mode(self, mode: str) -> None:
        """Set source mode: 'Default', 'User', or 'Combined' and reload."""
        normalized = (mode or 'Combined').strip().title()
        if normalized not in {'Default', 'User', 'Combined'}:
            normalized = 'Combined'
        if self._source_mode != normalized:
            self._source_mode = normalized
            self.load_templates()

    def get_source_mode(self) -> str:
        return self._source_mode

    def load_templates(self):
        """Load templates from the selected source index"""
        try:
            try:
                from snid_sage.interfaces.template_manager.services.template_service import get_template_service
                svc = get_template_service()
                active_pid = None
                try:
                    active_pid = svc.get_active_profile()
                except Exception:
                    active_pid = None
                if self._source_mode == 'Default':
                    index_data = svc.get_builtin_index(profile_id=active_pid)
                elif self._source_mode == 'User':
                    index_data = svc.get_user_index(profile_id=active_pid)
                else:
                    index_data = svc.get_merged_index(profile_id=active_pid)
            except Exception as e:
                _LOGGER.warning(f"Falling back to alternate index loading: {e}")
                template_index_path = self._find_template_index()
                if not template_index_path:
                    _LOGGER.warning("Template index not found")
                    self._create_sample_templates()
                    return
                with open(template_index_path, 'r') as f:
                    index_data = json.load(f)
                
            self.clear()

            # Group templates by type (defensive against malformed entries)
            by_type = index_data.get('by_type', {}) if isinstance(index_data, dict) else {}
            templates_map = index_data.get('templates', {}) if isinstance(index_data, dict) else {}

            # If Combined yields nothing (e.g., empty user index), log and fall back to Default
            if self._source_mode == 'Combined' and (not by_type or len(by_type) == 0):
                try:
                    from pathlib import Path as _Path
                    from snid_sage.shared.templates_manager import get_templates_dir as _get_tpl_dir

                    managed_dir = _Path(_get_tpl_dir())
                    idx_path = managed_dir / "template_index.json"
                    _LOGGER.debug(
                        "Combined templates index is empty; "
                        f"managed_dir={managed_dir}, index_exists={idx_path.exists()}"
                    )
                except Exception:
                    # Logging is best-effort only
                    pass
                try:
                    from snid_sage.interfaces.template_manager.services.template_service import get_template_service
                    fallback_idx = get_template_service().get_builtin_index()
                    if isinstance(fallback_idx, dict):
                        by_type = fallback_idx.get('by_type', {}) or {}
                        templates_map = fallback_idx.get('templates', {}) or {}
                except Exception:
                    pass

            for template_type, type_info in by_type.items():
                if not isinstance(type_info, dict):
                    continue
                count_display = type_info.get('count', 0)
                type_item = QtWidgets.QTreeWidgetItem(self, [template_type, f"{count_display} templates"])
                type_item.setExpanded(True)
                
                # Add individual templates
                for template_name in type_info.get('template_names', []):
                    template_info = templates_map.get(template_name)
                    if not isinstance(template_info, dict):
                        # Skip malformed entries
                        continue
                    
                    subtype = template_info.get('subtype', 'Unknown')
                    
                    template_item = QtWidgets.QTreeWidgetItem(type_item, [
                        template_name, 
                        f"{template_type}/{subtype}"
                    ])
                    template_item.setData(0, QtCore.Qt.UserRole, template_info)
                    
        except Exception as e:
            _LOGGER.error(f"Error loading templates: {e}")
            self._create_sample_templates()
    
    def _create_sample_templates(self):
        """Create sample templates for testing when index is not available"""
        _LOGGER.info("Creating sample templates for testing")
        
        sample_data = {
            'Ia': [
                {'name': 'sn1991T', 'subtype': 'Ia-91T', 'age': 0.0, 'epochs': 5},
                {'name': 'sn1994D', 'subtype': 'Ia-norm', 'age': 5.0, 'epochs': 3},
                {'name': 'sn2011fe', 'subtype': 'Ia-norm', 'age': -3.0, 'epochs': 7},
            ],
            'II': [
                {'name': 'sn1993J', 'subtype': 'IIb', 'age': 10.0, 'epochs': 4},
                {'name': 'sn1999em', 'subtype': 'IIP', 'age': 0.0, 'epochs': 6},
            ],
            'Ib': [
                {'name': 'sn2008D', 'subtype': 'Ib', 'age': 15.0, 'epochs': 3},
                {'name': 'sn1999ex', 'subtype': 'Ib', 'age': 8.0, 'epochs': 4},
            ],
            'Ic': [
                {'name': 'sn1998bw', 'subtype': 'Ic-BL', 'age': 12.0, 'epochs': 5},
                {'name': 'sn2002ap', 'subtype': 'Ic', 'age': 7.0, 'epochs': 3},
            ]
        }
        
        self.clear()
        
        for template_type, templates in sample_data.items():
            type_item = QtWidgets.QTreeWidgetItem(self, [template_type, f"{len(templates)} templates"])
            type_item.setExpanded(True)
            
            for template_data in templates:
                template_info = {
                    'type': template_type,
                    'subtype': template_data['subtype'],
                    'age': template_data['age'],
                    'epochs': template_data['epochs'],
                    'redshift': 0.01,
                    'storage_file': f'templates_{template_type}.hdf5'
                }
                
                template_item = QtWidgets.QTreeWidgetItem(type_item, [
                    template_data['name'],
                    f"{template_type}/{template_data['subtype']}"
                ])
                template_item.setData(0, QtCore.Qt.UserRole, template_info)
            
    def _find_template_index(self) -> Optional[str]:
        """Find the template index file"""
        # 1) Prefer the centralized templates manager (managed SNID-SAGE/templates bank)
        try:
            from pathlib import Path as _Path
            from snid_sage.shared.templates_manager import get_templates_dir as _get_tpl_dir

            managed_dir = _Path(_get_tpl_dir())
            idx_path = managed_dir / "template_index.json"
            if idx_path.exists():
                _LOGGER.info(f"Found managed template index at: {idx_path}")
                return str(idx_path)
        except Exception:
            # Best-effort only; fall through to local discovery.
            pass

        # 2) Legacy/local fallbacks relative to the current working directory
        possible_paths = [
            "templates/template_index.json",
            "template_index.json",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                _LOGGER.info(f"Found template index at: {path}")
                return path

        _LOGGER.warning("Template index not found in any of the expected locations")
        return None
        
    def _on_item_clicked(self, item, column):
        """Handle template selection"""
        template_info = item.data(0, QtCore.Qt.UserRole)
        if template_info:
            template_name = item.text(0)
            self.template_selected.emit(template_name, template_info)

    def _on_current_item_changed(self, current, previous):
        """Emit selection when current item changes (e.g., via keyboard)."""
        try:
            if current is None:
                return
            template_info = current.data(0, QtCore.Qt.UserRole)
            if not template_info:
                return
            template_name = current.text(0)
            self.template_selected.emit(template_name, template_info)
        except Exception:
            pass
    
    def filter_templates(self, search_text: str = "", type_filter: str = "All Types"):
        """Filter templates based on search text and selected type.
        Types are dynamic; no special 'Other' bucket.
        """
        search_text = search_text.lower()

        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            type_item = root.child(i)
            # Strip any appended counts from the displayed type text
            base_type_name = type_item.text(0).split(' (')[0]

            type_visible = (type_filter == "All Types" or type_filter == base_type_name)

            template_count = 0
            visible_templates = 0

            for j in range(type_item.childCount()):
                template_item = type_item.child(j)
                template_name = template_item.text(0).lower()
                template_type = template_item.text(1).lower()

                search_visible = (not search_text or search_text in template_name or search_text in template_type)

                template_visible = type_visible and search_visible
                template_item.setHidden(not template_visible)

                template_count += 1
                if template_visible:
                    visible_templates += 1

            if self._show_counts:
                if visible_templates > 0:
                    type_item.setText(0, f"{base_type_name} ({visible_templates}/{template_count})")
                    type_item.setHidden(False)
                else:
                    type_item.setHidden(not type_visible or bool(search_text))
                    if not type_item.isHidden():
                        type_item.setText(0, f"{base_type_name} (0/{template_count})")
            else:
                # Only show the base type name; control visibility as usual
                type_item.setText(0, base_type_name)
                if visible_templates > 0:
                    type_item.setHidden(False)
                else:
                    type_item.setHidden(not type_visible or bool(search_text))
    
    def get_selected_template(self) -> Optional[tuple]:
        """Get the currently selected template"""
        current_item = self.currentItem()
        if current_item:
            template_info = current_item.data(0, QtCore.Qt.UserRole)
            if template_info:
                template_name = current_item.text(0)
                return (template_name, template_info)
        return None
    
    def select_template_by_name(self, template_name: str) -> bool:
        """Select a template by name"""
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            type_item = root.child(i)
            for j in range(type_item.childCount()):
                template_item = type_item.child(j)
                if template_item.text(0) == template_name:
                    self.setCurrentItem(template_item)
                    template_info = template_item.data(0, QtCore.Qt.UserRole)
                    if template_info:
                        self.template_selected.emit(template_name, template_info)
                    return True
        return False
    
    def get_all_templates(self) -> List[tuple]:
        """Get all templates as a list of (name, info) tuples"""
        templates = []
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            type_item = root.child(i)
            for j in range(type_item.childCount()):
                template_item = type_item.child(j)
                template_info = template_item.data(0, QtCore.Qt.UserRole)
                if template_info:
                    template_name = template_item.text(0)
                    templates.append((template_name, template_info))
        return templates
    
    def get_template_count(self) -> int:
        """Get the total number of templates"""
        count = 0
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            type_item = root.child(i)
            count += type_item.childCount()
        return count
    
    def get_type_counts(self) -> Dict[str, int]:
        """Get template counts by type"""
        counts = {}
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            type_item = root.child(i)
            type_name = type_item.text(0).split(' (')[0]  # Remove count from display
            counts[type_name] = type_item.childCount()
        return counts

    def select_first_visible(self, type_name: Optional[str] = None) -> bool:
        """Select the first visible template item (optionally within a given type).

        Returns True if a selection was made.
        """
        try:
            root = self.invisibleRootItem()
            # Helper to emit selection
            def _select_item(it) -> bool:
                if it is None or it.isHidden():
                    return False
                self.setCurrentItem(it)
                info = it.data(0, QtCore.Qt.UserRole)
                if info:
                    self.template_selected.emit(it.text(0), info)
                return True

            if type_name:
                for i in range(root.childCount()):
                    type_item = root.child(i)
                    base_name = type_item.text(0).split(' (')[0]
                    if base_name != type_name:
                        continue
                    if type_item.isHidden():
                        return False
                    for j in range(type_item.childCount()):
                        tpl_item = type_item.child(j)
                        if not tpl_item.isHidden():
                            return _select_item(tpl_item)
                    return False
            # No specific type: find first visible across tree
            for i in range(root.childCount()):
                type_item = root.child(i)
                if type_item.isHidden():
                    continue
                for j in range(type_item.childCount()):
                    tpl_item = type_item.child(j)
                    if not tpl_item.isHidden():
                        return _select_item(tpl_item)
            return False
        except Exception:
            return False