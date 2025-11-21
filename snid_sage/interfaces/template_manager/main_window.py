"""
SNID-SAGE Template Manager - Main Window
=======================================

Main window for the SNID-SAGE Template Manager GUI.
"""

import sys
import json
import logging
from typing import Dict, Any, Optional
from PySide6 import QtWidgets, QtCore, QtGui

# Import components
from .components.template_tree import TemplateTreeWidget
from .components.template_visualization import TemplateVisualizationWidget
from .widgets.template_creator import TemplateCreatorWidget
from .widgets.template_manager import TemplateManagerWidget

# Import utilities
from .utils.theme_manager import get_template_theme_manager
from .utils.layout_manager import get_template_layout_manager

# Import logging
try:
    from snid_sage.shared.utils.logging import get_logger
    _LOGGER = get_logger('template_manager.main')
except ImportError:
    import logging
    _LOGGER = logging.getLogger('template_manager.main')


class SNIDTemplateManagerGUI(QtWidgets.QMainWindow):
    """Main template manager GUI window"""
    
    def __init__(self):
        super().__init__()
        self.theme_manager = get_template_theme_manager()
        self.layout_manager = get_template_layout_manager()
        self.setup_window()
        self.setup_theme()
        self.create_interface()
        # Debounce rapid template selections to avoid heavy repeated loads
        try:
            self._selection_debounce_timer = QtCore.QTimer(self)
            self._selection_debounce_timer.setSingleShot(True)
            self._selection_debounce_timer.setInterval(150)
            self._selection_debounce_timer.timeout.connect(self._apply_pending_selection)
            self._pending_selection = None  # type: Optional[tuple]
            self._loading_template = False
        except Exception:
            self._selection_debounce_timer = None
            self._pending_selection = None
            self._loading_template = False
        
    def setup_window(self):
        """Setup main window properties"""
        self.setWindowTitle("SNID-SAGE Template Manager")
        
        # Try to use centralized logo manager icon if available
        try:
            from snid_sage.interfaces.ui_core.logo import get_logo_manager
            icon_path = get_logo_manager().get_icon_path()
            if icon_path:
                self.setWindowIcon(QtGui.QIcon(str(icon_path)))
            else:
                self.setWindowIcon(QtGui.QIcon())
        except Exception:
            self.setWindowIcon(QtGui.QIcon())
        
        # Setup window with layout manager
        self.layout_manager.setup_main_window(self)
        
    def setup_theme(self):
        """Setup theme matching main GUI"""
        try:
            stylesheet = self.theme_manager.generate_complete_stylesheet()
            self.setStyleSheet(stylesheet)
        except Exception as e:
            _LOGGER.warning(f"Could not apply theme: {e}")
            
    def create_interface(self):
        """Create the main interface"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        self.layout_manager.apply_panel_layout(central_widget, main_layout)
        
        # Create main splitter
        splitter = self.layout_manager.create_main_splitter()
        main_layout.addWidget(splitter)
        
        # Left panel - Template browser
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Tabbed interface
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        # Ensure right panel stretches and apply sizes after widgets are added
        try:
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            # Apply desired initial sizes now that children exist
            try:
                sizes = self.layout_manager.settings.main_splitter_sizes
            except Exception:
                sizes = [220, 680]
            splitter.setSizes(sizes)
            QtCore.QTimer.singleShot(0, lambda s=sizes: splitter.setSizes(s))
        except Exception:
            pass
        
        
    def create_left_panel(self) -> QtWidgets.QWidget:
        """Create the left panel with template browser"""
        panel = QtWidgets.QFrame()
        panel.setObjectName("template_left_panel")
        layout = QtWidgets.QVBoxLayout(panel)
        self.layout_manager.apply_panel_layout(panel, layout)
        try:
            # Add rounded light-grey contour consistent with main GUI
            panel.setStyleSheet(
                """
                QFrame#template_left_panel {
                    background-color: white;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    margin: 2px;
                }
                """
            )
            # Slightly reduce inner spacing to better fit within rounded frame
            layout.setContentsMargins(8, 8, 8, 8)
        except Exception:
            pass
        
        # Header
        header = QtWidgets.QLabel("Template Library")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # User folder banner (shown until user folder is configured)
        banner = QtWidgets.QFrame()
        banner.setObjectName("userFolderBanner")
        banner_layout = QtWidgets.QHBoxLayout(banner)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        banner_label = QtWidgets.QLabel("Set a User Templates folder to create and manage your own templates.")
        banner_label.setStyleSheet("color: #1f2937;")
        set_btn = QtWidgets.QPushButton("Set Folder…")
        set_btn.clicked.connect(self._prompt_set_user_folder)
        banner_layout.addWidget(banner_label)
        banner_layout.addStretch(1)
        banner_layout.addWidget(set_btn)
        banner.setStyleSheet("#userFolderBanner { background: #fef3c7; border: 1px solid #f59e0b; border-radius: 6px; }")
        self._user_folder_banner = banner
        layout.addWidget(banner)

        # Search and filters (rounded white subpanel with light grey contour)
        search_frame = QtWidgets.QFrame()
        search_frame.setObjectName("template_search_panel")
        search_layout = QtWidgets.QVBoxLayout(search_frame)
        try:
            search_frame.setStyleSheet(
                """
                QFrame#template_search_panel {
                    background-color: white;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    margin: 2px;
                }
                """
            )
            search_layout.setContentsMargins(8, 8, 8, 8)
            search_layout.setSpacing(6)
        except Exception:
            pass
        
        # Source selector: Default / User / Combined
        source_row = QtWidgets.QHBoxLayout()
        source_label = QtWidgets.QLabel("Source:")
        self.source_filter = QtWidgets.QComboBox()
        self.source_filter.addItems(["Combined", "Default", "User"])  # default Combined
        self.source_filter.currentTextChanged.connect(self._on_source_changed)
        source_row.addWidget(source_label)
        source_row.addWidget(self.source_filter)
        search_layout.addLayout(source_row)

        # Profile selector: Optical / ONIR (local toggle for Template Manager)
        profile_row = QtWidgets.QHBoxLayout()
        profile_label = QtWidgets.QLabel("Profile:")
        self.profile_optical = QtWidgets.QRadioButton("Optical")
        self.profile_onir = QtWidgets.QRadioButton("ONIR")
        self.profile_optical.setChecked(True)
        try:
            from .services.template_service import get_template_service
            svc = get_template_service()
            pid = (svc.get_active_profile() or 'optical').lower()
            if pid == 'onir':
                self.profile_onir.setChecked(True)
                self.profile_optical.setChecked(False)
        except Exception:
            pass
        self.profile_optical.toggled.connect(lambda checked: self._on_profile_changed('optical' if checked else None))
        self.profile_onir.toggled.connect(lambda checked: self._on_profile_changed('onir' if checked else None))
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.profile_optical)
        profile_row.addWidget(self.profile_onir)
        profile_row.addStretch()
        search_layout.addLayout(profile_row)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search templates...")
        self.search_edit.textChanged.connect(self._filter_templates)
        search_layout.addWidget(self.search_edit)
        
        self.type_filter = QtWidgets.QComboBox()
        # Populate dynamically from merged index for active profile
        try:
            from .services.template_service import get_template_service
            svc = get_template_service()
            pid = None
            try:
                pid = svc.get_active_profile()
            except Exception:
                pid = None
            by_type = svc.get_merged_index(profile_id=pid).get('by_type', {})
            dynamic_types = sorted(list(by_type.keys()))
            self.type_filter.addItem("All Types")
            self.type_filter.addItems(dynamic_types)
        except Exception:
            # Fallback to minimal defaults
            self.type_filter.addItems(["All Types", "Ia", "Ib", "Ic", "II", "AGN", "Galaxy", "Star"])
        self.type_filter.currentTextChanged.connect(self._on_type_changed)
        # Also react to re-selecting the same type (activated fires even if text didn't change)
        try:
            self.type_filter.activated.connect(lambda *_: self._on_type_changed(self.type_filter.currentText()))
        except Exception:
            pass
        search_layout.addWidget(self.type_filter)
        
        layout.addWidget(search_frame)
        
        # Template tree
        self.template_tree = TemplateTreeWidget()
        # Hide type count badges by default; they can be noisy and confusing
        try:
            self.template_tree.set_show_counts(False)
        except Exception:
            pass
        self.template_tree.template_selected.connect(self.on_template_selected)
        self.layout_manager.setup_template_browser(self.template_tree)
        layout.addWidget(self.template_tree)

        # Open User Folder button
        try:
            bottom_row = QtWidgets.QHBoxLayout()
            open_user_btn = self.layout_manager.create_action_button("Open User Folder", "📂")
            open_user_btn.clicked.connect(self._open_user_folder)
            change_user_btn = self.layout_manager.create_action_button("Change User Folder", "🛠")
            change_user_btn.clicked.connect(self._prompt_set_user_folder)
            bottom_row.addWidget(open_user_btn)
            bottom_row.addWidget(change_user_btn)
            bottom_row.addStretch()
            layout.addLayout(bottom_row)
        except Exception:
            pass
        
        # Removed explicit Refresh button; switching source auto-refreshes
        
        return panel
        
    def _filter_templates(self):
        """Filter templates based on search text and type"""
        # Ensure the tree source matches the current selector
        try:
            current_source = (self.source_filter.currentText() or "Combined").strip().title()
            if hasattr(self, 'template_tree') and self.template_tree.get_source_mode() != current_source:
                self.template_tree.set_source_mode(current_source)
        except Exception:
            pass
        search_text = self.search_edit.text()
        type_filter = self.type_filter.currentText()
        self.template_tree.filter_templates(search_text, type_filter)

    def _on_type_changed(self, type_text: str) -> None:
        """When type selection changes, filter and select first visible in that type."""
        try:
            self._filter_templates()
            t = (type_text or "").strip()
            # Avoid auto-select on 'All Types'
            if t and t != "All Types":
                # Defer selection until the view updates
                QtCore.QTimer.singleShot(0, lambda: self.template_tree.select_first_visible(t))
            else:
                QtCore.QTimer.singleShot(0, lambda: self.template_tree.select_first_visible(None))
        except Exception:
            pass

    def _on_source_changed(self, mode: str):
        """Handle source filter changes and reload tree"""
        try:
            self.template_tree.set_source_mode(mode)
            # After reload, re-apply current text/type filters
            # Repopulate type filter from the selected source
            try:
                from .services.template_service import get_template_service
                svc = get_template_service()
                if (mode or "").strip().title() == "Default":
                    idx = svc.get_builtin_index(profile_id=svc.get_active_profile())
                elif (mode or "").strip().title() == "User":
                    idx = svc.get_user_index(profile_id=svc.get_active_profile())
                else:
                    idx = svc.get_merged_index(profile_id=svc.get_active_profile())
                types = sorted(list((idx.get('by_type') or {}).keys())) if isinstance(idx, dict) else []
                # Preserve current selection if possible
                current = self.type_filter.currentText() if hasattr(self, 'type_filter') else None
                self.type_filter.blockSignals(True)
                self.type_filter.clear()
                self.type_filter.addItem("All Types")
                for t in types:
                    self.type_filter.addItem(t)
                # Restore selection if still valid
                if current and current in [self.type_filter.itemText(i) for i in range(self.type_filter.count())]:
                    self.type_filter.setCurrentText(current)
                else:
                    self.type_filter.setCurrentText("All Types")
            finally:
                try:
                    self.type_filter.blockSignals(False)
                except Exception:
                    pass
            self._filter_templates()
            # Refresh Manage tab empty-state
            if hasattr(self, 'manager_widget'):
                self.manager_widget.update_empty_state()
            # Update search placeholder to reflect active source
            try:
                self.search_edit.setPlaceholderText(f"Search templates ({(mode or 'Combined').title()})...")
            except Exception:
                pass
        except Exception as e:
            _LOGGER.warning(f"Source change failed: {e}")

    def _on_profile_changed(self, profile_id: Optional[str]) -> None:
        """Switch active profile in the service and reload lists/widgets."""
        try:
            if not profile_id:
                return
            from .services.template_service import get_template_service
            svc = get_template_service()
            svc.set_active_profile(profile_id)
            # Ensure advanced preprocessing dialog picks up the same profile
            try:
                import os
                os.environ['SNID_SAGE_ACTIVE_PROFILE'] = profile_id
            except Exception:
                pass
            # Reload indices and filters immediately
            self.template_tree.load_templates()
            # Repopulate type filter for the active profile and current source
            try:
                mode = (self.source_filter.currentText() or "Combined").strip().title()
                if mode == "Default":
                    idx = svc.get_builtin_index(profile_id=svc.get_active_profile())
                elif mode == "User":
                    idx = svc.get_user_index(profile_id=svc.get_active_profile())
                else:
                    idx = svc.get_merged_index(profile_id=svc.get_active_profile())
                types = sorted(list((idx.get('by_type') or {}).keys())) if isinstance(idx, dict) else []
                current = self.type_filter.currentText() if hasattr(self, 'type_filter') else None
                self.type_filter.blockSignals(True)
                self.type_filter.clear()
                self.type_filter.addItem("All Types")
                for t in types:
                    self.type_filter.addItem(t)
                if current and current in [self.type_filter.itemText(i) for i in range(self.type_filter.count())]:
                    self.type_filter.setCurrentText(current)
                else:
                    self.type_filter.setCurrentText("All Types")
            finally:
                try:
                    self.type_filter.blockSignals(False)
                except Exception:
                    pass
            # Re-apply current search filter
            self._filter_templates()
            # Refresh creator/manager widgets if they rely on service state
            try:
                # Refresh Manage tab empty-state
                if hasattr(self, 'manager_widget') and hasattr(self.manager_widget, 'update_empty_state'):
                    self.manager_widget.update_empty_state()
            except Exception:
                pass
            # Notify creator widget so it can refresh its type/subtype metadata
            try:
                if hasattr(self, 'creator_widget') and hasattr(self.creator_widget, 'refresh_profile_metadata'):
                    self.creator_widget.refresh_profile_metadata(profile_id)
            except Exception:
                pass
        except Exception as e:
            _LOGGER.warning(f"Profile change failed: {e}")
        
    def _on_tab_changed(self, index: int) -> None:
        """When switching tabs, force the library to 'User' for Create/Manage."""
        try:
            if not hasattr(self, 'tab_widget'):
                return
            tab_text = self.tab_widget.tabText(index) if index is not None else ""
            is_editing_tab = tab_text in {"Create Template", "Manage Templates"}
            if is_editing_tab:
                # Force source selector to 'User' and disable it
                try:
                    if hasattr(self, 'source_filter'):
                        if (self.source_filter.currentText() or "").strip().title() != 'User':
                            self.source_filter.setCurrentText('User')
                        self.source_filter.setEnabled(False)
                except Exception:
                    pass
                # Ensure the tree is in User mode
                try:
                    if hasattr(self, 'template_tree'):
                        self.template_tree.set_source_mode('User')
                        # Re-apply current filters
                        self._filter_templates()
                except Exception:
                    pass
            else:
                # Re-enable the source selector when leaving editing tabs
                try:
                    if hasattr(self, 'source_filter'):
                        self.source_filter.setEnabled(True)
                except Exception:
                    pass
        except Exception:
            pass
        
    def create_right_panel(self) -> QtWidgets.QWidget:
        """Create the right panel with tabbed interface"""
        self.tab_widget = QtWidgets.QTabWidget()
        self.layout_manager.setup_tab_widget(self.tab_widget)
        
        # Template Viewer tab
        self.viewer_widget = TemplateVisualizationWidget()
        self.tab_widget.addTab(self.viewer_widget, "Template Viewer")
        
        # Template Creator tab
        self.creator_widget = TemplateCreatorWidget()
        self.tab_widget.addTab(self.creator_widget, "Create Template")
        
        # Template Manager tab
        self.manager_widget = TemplateManagerWidget()
        self.tab_widget.addTab(self.manager_widget, "Manage Templates")

        # Initialize Manage tab empty-state
        try:
            self.manager_widget.update_empty_state()
        except Exception:
            pass

        # Apply Twemoji tab icons now that tabs are ready
        try:
            self.layout_manager.apply_tab_icons(self.tab_widget)
        except Exception:
            pass
        
        # Enforce 'User' source when switching to Create/Manage tabs
        try:
            self.tab_widget.currentChanged.connect(self._on_tab_changed)
            # Apply once for the initial tab
            try:
                self._on_tab_changed(self.tab_widget.currentIndex())
            except Exception:
                pass
        except Exception:
            pass
        
        # Update banner visibility once UI is built
        QtCore.QTimer.singleShot(0, self._update_user_folder_banner)
        return self.tab_widget
        
    def create_status_bar(self):
        """Create the status bar"""
        status_bar = self.statusBar()
        
        # Template count label
        self.template_count_label = QtWidgets.QLabel("Templates: Loading...")
        status_bar.addWidget(self.template_count_label)
        
        status_bar.addPermanentWidget(QtWidgets.QLabel("SNID-SAGE Template Manager v1.0"))
        
        # Update template count
        QtCore.QTimer.singleShot(1000, self.update_template_count)
        
    def update_template_count(self):
        """Update the template count in status bar"""
        try:
            count = self.template_tree.get_template_count()
            self.template_count_label.setText(f"Templates: {count}")
        except Exception as e:
            self.template_count_label.setText("Templates: Error")
            _LOGGER.error(f"Error updating template count: {e}")
            
    @QtCore.Slot(str, dict)
    def on_template_selected(self, template_name: str, template_info: Dict[str, Any]):
        """Handle template selection from tree with debouncing/throttling."""
        try:
            self._pending_selection = (template_name, template_info)
            if getattr(self, '_selection_debounce_timer', None) is not None:
                # Restart debounce window
                self._selection_debounce_timer.start(150)
            else:
                # Fallback: apply immediately
                self._apply_pending_selection()
        except Exception:
            # Fallback to immediate behavior in case of any issue
            try:
                self.viewer_widget.set_template(template_name, template_info)
            except Exception:
                pass
            try:
                self.manager_widget.set_template_for_editing(template_name, template_info)
            except Exception:
                pass
        
        
    
    def get_current_template(self) -> Optional[tuple]:
        """Get the currently selected template"""
        return self.template_tree.get_selected_template()
    
    def refresh_template_library(self):
        """Refresh the template library"""
        self.template_tree.load_templates()
        # Refresh Manage tab empty-state after refresh
        try:
            if hasattr(self, 'manager_widget'):
                self.manager_widget.update_empty_state()
        except Exception:
            pass

    @QtCore.Slot()
    def _apply_pending_selection(self) -> None:
        """Apply the latest pending selection, coalescing rapid changes."""
        try:
            if not getattr(self, '_pending_selection', None):
                return
            if getattr(self, '_loading_template', False):
                # Try again shortly after current load completes
                try:
                    self._selection_debounce_timer.start(100)
                except Exception:
                    pass
                return
            selection = self._pending_selection
            self._pending_selection = None
            self._loading_template = True
            name, info = selection
            # Do not force-switch tabs; just update widgets so they're ready if user navigates
            try:
                self.viewer_widget.set_template(name, info)
            except Exception:
                pass
            try:
                self.manager_widget.set_template_for_editing(name, info)
            except Exception:
                pass
        finally:
            self._loading_template = False
            # If new selection arrived meanwhile, apply it immediately
            try:
                if getattr(self, '_pending_selection', None) is not None:
                    QtCore.QTimer.singleShot(0, self._apply_pending_selection)
            except Exception:
                pass

    def _open_user_folder(self):
        """Open the user templates directory in the system file explorer."""
        try:
            from .services.template_service import get_template_service
            p = get_template_service().get_user_templates_dir()
            if p:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(p))
        except Exception:
            pass

    def _update_user_folder_banner(self) -> None:
        try:
            from snid_sage.shared.utils.paths.user_templates import get_user_templates_dir
            is_set = get_user_templates_dir(strict=True) is not None
            if hasattr(self, '_user_folder_banner'):
                self._user_folder_banner.setVisible(not is_set)
        except Exception:
            if hasattr(self, '_user_folder_banner'):
                self._user_folder_banner.setVisible(True)

    def _prompt_set_user_folder(self) -> None:
        try:
            from .dialogs.user_templates_folder_dialog import UserTemplatesFolderDialog
            dlg = UserTemplatesFolderDialog(self)
            dlg.folder_selected.connect(lambda _: self._after_user_folder_set())
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Unable to open folder selection dialog: {e}")

    def _after_user_folder_set(self) -> None:
        try:
            self._update_user_folder_banner()
            # Reload tree and manage tab empty-state
            self.template_tree.load_templates()
            if hasattr(self, 'manager_widget'):
                self.manager_widget.update_empty_state()
        except Exception:
            pass
    
    def show_about(self):
        """Show about dialog"""
        QtWidgets.QMessageBox.about(
            self,
            "About SNID-SAGE Template Manager",
            "SNID-SAGE Template Manager v1.0\n\n"
            "A comprehensive GUI for managing SNID-SAGE templates.\n\n"
            "Features:\n"
            "• Browse and visualize templates\n"
            "• Create new templates\n"
            "• Manage template metadata\n\n"
            "Developed by Fiorenzo Stoppa for SNID SAGE"
        )
    
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QtWidgets.QMessageBox.question(
            self, 
            'Exit Template Manager',
            'Are you sure you want to exit the Template Manager?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()