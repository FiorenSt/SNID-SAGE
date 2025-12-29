```
SNID_SAGE/                                    # project root
├── pyproject.toml                            # Project configuration
├── README.md                                 # Project documentation
├── CHANGELOG.md                              # Changelog
├── LICENSE                                   # License file
├── MANIFEST.in                               # Package manifest
├── mkdocs.yml                                # Documentation configuration
 
├── docs/                                     # Documentation
│   ├── ai/
│   │   ├── openrouter-setup.md
│   │   └── overview.md
│   ├── assets/
│   │   └── overrides.css
│   ├── cli/
│   │   ├── batch-processing.md
│   │   └── command-reference.md
│   ├── data/
│   │   ├── custom-templates.md
│   │   ├── data-preparation.md
│   │   ├── supported-formats.md
│   │   └── template-library.md
│   ├── dev/
│   │   └── contributing.md
│   ├── gui/
│   │   ├── ai-assistant.md
│   │   ├── interface-overview.md
│   │   ├── lines-manager.md
│   │   ├── preprocessing.md
│   │   ├── results-and-plots.md
│   │   ├── settings-configuration.md
│   │   ├── template-manager.md
│   │   └── templates-manager.md
│   ├── images/                               # Documentation screenshots (PNG)
│   ├── installation/
│   │   └── installation.md
│   ├── quickstart/
│   │   └── first-analysis.md
│   └── reference/
│       ├── api-reference.md
│       ├── changelog.md
│       ├── configuration-guide.md
│       ├── parameters.md
│       ├── supported-formats.md
│       └── troubleshooting.md
├── images/                                   # Branding assets and icons
│   ├── icon.ico
│   ├── icon.png
│   ├── icon_dark.png
│   ├── light.png
│   ├── Screenshot.png
│   ├── icon.iconset/                         # macOS iconset
│   ├── icon_dark.iconset/                    # Dark theme iconset
│   └── (icons only; legacy OLD_ICONS is ignored)
 
 
 
 
├── snid_sage/                                # Main package
│   ├── __init__.py
 
│   ├── images/
│   │   ├── icon.png
 
│   │   ├── tick_white.svg
│   │   └── twemoji/                          # Twemoji SVG set
│   ├── interfaces/                           # User interfaces
│   │   ├── __init__.py
│   │   ├── cli/                              # Command line interface
│   │   │   ├── __init__.py
│   │   │   ├── batch.py
│   │   │   ├── config.py
│   │   │   ├── identify.py
│   │   │   ├── main.py
│   │   │   └── templates.py
│   │   ├── gui/                              # PySide6 GUI
│   │   │   ├── __init__.py
│   │   │   ├── components/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analysis/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── analysis_menu_manager.py
│   │   │   │   ├── dialogs/__init__.py
│   │   │   │   ├── events/pyside6_event_handlers.py
│   │   │   │   ├── forms/
│   │   │   │   ├── plots/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── enhanced_plot_widget.py
│   │   │   │   │   ├── pyside6_analysis_plotter.py
│   │   │   │   │   └── pyside6_plot_manager.py
│   │   │   │   ├── pyside6_dialogs/          # PySide6 dialogs
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── analysis_progress_dialog.py
│   │   │   │   │   ├── button_palette_demo_dialog.py
│   │   │   │   │   ├── cluster_selection_dialog.py
│   │   │   │   │   ├── configuration_dialog.py
│   │   │   │   │   ├── dialog_manager.py
│   │   │   │   │   ├── emission_dialog_events.py
│   │   │   │   │   ├── emission_dialog_ui.py
│   │   │   │   │   ├── enhanced_ai_assistant_dialog.py
│   │   │   │   │   ├── games_dialog.py
│   │   │   │   │   ├── gmm_clustering_dialog.py
│   │   │   │   │   ├── manual_redshift_dialog.py
│   │   │   │   │   ├── mask_manager_dialog.py
│   │   │   │   │   ├── multi_step_emission_dialog.py
│   │   │   │   │   ├── multi_step_emission_dialog_step2.py
│   │   │   │   │   ├── preprocessing_dialog.py
│   │   │   │   │   ├── preprocessing_selection_dialog.py
│   │   │   │   │   ├── progress_dialog.py
│   │   │   │   │   ├── redshift_age_dialog.py
│   │   │   │   │   ├── redshift_mode_dialog.py
│   │   │   │   │   ├── results_dialog.py
│   │   │   │   │   ├── settings_dialog.py
│   │   │   │   │   ├── shortcuts_dialog.py
│   │   │   │   │   └── subtype_proportions_dialog.py
│   │   │   ├── controllers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pyside6_app_controller.py
│   │   │   │   └── pyside6_preprocessing_controller.py
│   │   │   ├── demos/
│   │   │   │   ├── interactive_indicators_demo.py
│   │   │   │   ├── tick_effects_emission_style.py
│   │   │   │   └── ticks_demo.py
│   │   │   ├── features/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analysis/                 # Analysis-related features
│   │   │   │   ├── configuration/
│   │   │   │   │   └── config_controller.py
│   │   │   │   ├── preprocessing/            # Preprocessing features
│   │   │   │   └── results/
│   │   │   │       └── __init__.py
│   │   │   ├── launcher.py
│   │   │   ├── pyside6_gui.py
│   │   │   ├── utils/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── cross_platform_window.py
│   │   │   │   ├── dialog_button_enhancer.py
│   │   │   │   ├── enhanced_button_manager.py
│   │   │   │   ├── enhanced_dialog_button_manager.py
│   │   │   │   ├── import_manager.py
│   │   │   │   ├── layout_config.py
│   │   │   │   ├── layout_conflict_detector.py
│   │   │   │   ├── logo_manager.py
│   │   │   │   ├── matplotlib_qt.py
│   │   │   │   ├── no_title_plot_manager.py
│   │   │   │   ├── plot_legend_utils.py
│   │   │   │   ├── pyqtgraph_rest_axis.py
│   │   │   │   ├── pyside6_helpers.py
│   │   │   │   ├── pyside6_message_utils.py
│   │   │   │   ├── pyside6_theme_manager.py
│   │   │   │   ├── pyside6_workflow_manager.py
│   │   │   │   ├── twemoji_manager.py
│   │   │   │   └── unified_pyside6_layout_manager.py
│   │   │   └── widgets/
│   │   │       └── __init__.py
│   │   ├── line_manager/
│   │   │   ├── __init__.py
│   │   │   ├── launcher.py
│   │   │   └── main_window.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── analysis/
│   │   │   │   └── llm_utils.py
│   │   │   ├── llm_integration.py
│   │   │   └── openrouter/
│   │   │       ├── __init__.py
│   │   │       ├── openrouter_llm.py
│   │   │       └── openrouter_summary.py
│   │   ├── template_manager/
│   │   │   ├── __init__.py
│   │   │   ├── components/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── template_data.py
│   │   │   │   ├── template_tree.py
│   │   │   │   └── template_visualization.py
│   │   │   ├── dialogs/
│   │   │   │   └── user_templates_folder_dialog.py
│   │   │   ├── launcher.py
│   │   │   ├── main_window.py
│   │   │   ├── services/
│   │   │   │   └── template_service.py
│   │   │   ├── utils/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── layout_manager.py
│   │   │   │   └── theme_manager.py
│   │   │   └── widgets/
│   │   │       ├── __init__.py
│   │   │       ├── batch_import_dialog.py
│   │   │       ├── template_creator.py
│   │   │       └── template_manager.py
│   │   └── ui_core/
│   │       ├── __init__.py
│   │       ├── layout.py
│   │       ├── logo.py
│   │       ├── theme.py
│   │       └── twemoji.py
│   ├── lines/
│   │   └── line_database.json
│   ├── shared/                               # Shared utilities
│   │   ├── __init__.py
│   │   ├── constants/
│   │   │   ├── __init__.py
│   │   │   └── physical.py
│   │   ├── exceptions/
│   │   │   ├── __init__.py
│   │   │   └── core_exceptions.py
│   │   ├── profiles/
│   │   │   ├── bandpass.py
│   │   │   ├── builtins.py
│   │   │   ├── registry.py
│   │   │   └── types.py
│   │   ├── types/
│   │   │   ├── __init__.py
│   │   │   ├── result_types.py
│   │   │   └── spectrum_types.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── config/
│   │       │   ├── __init__.py
│   │       │   ├── configuration_manager.py
│   │       │   └── platform_config.py
│   │       ├── data_io/
│   │       │   ├── __init__.py
│   │       │   └── spectrum_loader.py
│   │       ├── line_detection/
│   │       │   ├── __init__.py
│   │       │   ├── detection.py
│   │       │   ├── fwhm_analysis.py
│   │       │   ├── interactive_fwhm_analyzer.py
│   │       │   ├── line_db_loader.py
│   │       │   ├── line_presets.py
│   │       │   ├── line_selection_utils.py
│   │       │   ├── spectrum_utils.py
│   │       │   └── user_line_store.py
│   │       ├── logging/
│   │       │   ├── __init__.py
│   │       │   ├── config.py
│   │       │   └── snid_logger.py
│   │       ├── mask_utils/
│   │       │   └── __init__.py
│   │       ├── match_utils.py
│   │       ├── math_utils/
│   │       │   ├── __init__.py
│   │       │   ├── similarity_metrics.py
│   │       │   └── weighted_statistics.py
│   │       ├── paths/
│   │       │   └── user_templates.py
│   │       ├── plotting/
│   │       │   ├── __init__.py
│   │       │   ├── font_sizes.py
│   │       │   ├── plot_theming.py
│   │       │   └── spectrum_utils.py
│   │       ├── results_formatter.py
│   │       ├── secure_storage.py
│   │       ├── simple_template_finder.py
│   │       ├── version_checker.py
│   │       └── wind_analysis/
│   │           ├── __init__.py
│   │           ├── pcygni_fitting.py
│   │           └── wind_calculations.py
│   ├── snid/                                 # Core engine
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── integration.py
│   │   ├── cosmological_clustering.py
│   │   ├── fft_tools.py
│   │   ├── games.py
│   │   ├── io.py
│   │   ├── optimization_integration.py
│   │   ├── plotting_3d.py
│   │   ├── plotting.py
│   │   ├── preprocessing.py
│   │   ├── snid.py
│   │   ├── snidtype.py
│   │   ├── template_fft_storage.py
│   │   ├── template_manager.py
│   │   └── vectorized_peak_finder.py
│   ├── templates/                            # Optical templates
│   │   ├── template_index.json
│   │   └── templates_*.hdf5
│   └── templates/                            # Unified templates (optical + *_onir files)
│       ├── template_index.json
│       └── templates_*.hdf5
 
└── plots/                                    # Output plots
```
