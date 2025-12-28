"""
SNID SAGE PySide6 Dialogs
=========================

Collection of PySide6 dialog windows for the SNID SAGE GUI interface.

Available dialogs:
- PreprocessingDialog: Spectrum preprocessing configuration (Qt native)
- ConfigurationDialog: SNID analysis parameters configuration (Qt native)
- SettingsDialog: GUI settings and preferences (Qt native)
- ShortcutsDialog: Keyboard shortcuts and hotkeys reference (Qt native)
- ResultsDialog: Analysis results viewing (Qt native)
- MaskManagerDialog: Spectrum masking management (Qt native)
- ManualRedshiftDialog: Galaxy redshift determination with drag-to-adjust (Qt native)
- RedshiftModeDialog: Redshift analysis mode selection (Qt native)
- PreprocessingSelectionDialog: Quick vs advanced preprocessing selection (Qt native)
- SNIDAnalysisDialog: Combined SNID analysis dialog (Qt native)
- EnhancedAIAssistantDialog: AI Assistant for analysis interpretation (Qt native)
"""

# Core dialogs without matplotlib dependencies (safe to import at module level)
from .preprocessing_dialog import PySide6PreprocessingDialog
from .configuration_dialog import PySide6ConfigurationDialog
from .settings_dialog import PySide6SettingsDialog
from .shortcuts_dialog import PySide6ShortcutsDialog
from .mask_manager_dialog import PySide6MaskManagerDialog
from .manual_redshift_dialog import PySide6ManualRedshiftDialog, show_manual_redshift_dialog
from .redshift_mode_dialog import PySide6RedshiftModeDialog, show_redshift_mode_dialog
from .preprocessing_selection_dialog import PySide6PreprocessingSelectionDialog, show_preprocessing_selection_dialog
from .enhanced_ai_assistant_dialog import PySide6EnhancedAIAssistantDialog

# Emission line dialog (matplotlib-free) - Refactored version
from .multi_step_emission_dialog import PySide6MultiStepEmissionAnalysisDialog, show_pyside6_multi_step_emission_dialog

# Dialog manager
from .dialog_manager import DialogManager

# The following dialogs use matplotlib and should be imported only when needed:
# - cluster_selection_dialog (uses matplotlib for 3D plots)
# - redshift_age_dialog (uses matplotlib for scatter plots)
# - subtype_proportions_dialog (uses matplotlib for pie charts)
# - gmm_clustering_dialog (commented out matplotlib imports)
# - results_dialog (may have matplotlib dependencies)

# Conditional imports for matplotlib-using dialogs
try:
    # Only import these when specifically requested
    pass
    # from .cluster_selection_dialog import PySide6ClusterSelectionDialog, show_cluster_selection_dialog
    # from .redshift_age_dialog import PySide6RedshiftAgeDialog, show_redshift_age_dialog
    # from .subtype_proportions_dialog import PySide6SubtypeProportionsDialog, show_subtype_proportions_dialog
except ImportError:
    # Fallback if matplotlib-using dialogs are not available
    pass

# Analysis results dialogs (may have matplotlib dependencies)
try:
    from .results_dialog import PySide6AnalysisResultsDialog, show_analysis_results_dialog
    # Export with the old name for compatibility
    PySide6ResultsDialog = PySide6AnalysisResultsDialog
except ImportError:
    # Fallback if analysis dialogs are not available
    PySide6AnalysisResultsDialog = None
    show_analysis_results_dialog = None
    PySide6ResultsDialog = None

# GMM clustering (matplotlib imports commented out)
try:
    from .gmm_clustering_dialog import PySide6GMMClusteringDialog, show_gmm_clustering_dialog
except ImportError:
    PySide6GMMClusteringDialog = None
    show_gmm_clustering_dialog = None

__all__ = [
    # Core dialogs
    'PySide6PreprocessingDialog',
    'PySide6ConfigurationDialog', 
    'PySide6SettingsDialog',
    'PySide6ShortcutsDialog',
    'PySide6MaskManagerDialog',
    'PySide6ManualRedshiftDialog', 'show_manual_redshift_dialog',
    'PySide6RedshiftModeDialog', 'show_redshift_mode_dialog',
    'PySide6PreprocessingSelectionDialog', 'show_preprocessing_selection_dialog',
    'PySide6EnhancedAIAssistantDialog',
    
    # Emission line dialog
    'PySide6MultiStepEmissionAnalysisDialog', 'show_pyside6_multi_step_emission_dialog',
    
    # Dialog manager
    'DialogManager',
    
    # Analysis dialogs (with fallbacks)
    'PySide6AnalysisResultsDialog', 'show_analysis_results_dialog', 'PySide6ResultsDialog',
    'PySide6GMMClusteringDialog', 'show_gmm_clustering_dialog',
] 