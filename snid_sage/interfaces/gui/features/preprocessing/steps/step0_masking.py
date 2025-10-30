from PySide6 import QtWidgets

# Import flexible number input widget creators
from snid_sage.interfaces.gui.components.widgets.flexible_number_input import (
    create_flexible_double_input,
)


def create_options(dialog, layout: QtWidgets.QVBoxLayout) -> None:
    """Build UI for Step 0: Masking & Clipping."""
    desc = QtWidgets.QLabel("Mask wavelength regions and apply clipping operations to exclude unwanted features from analysis.")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #64748b; font-size: 11pt; margin-bottom: 10px;")
    layout.addWidget(desc)

    # Interactive masking section
    if dialog.masking_widget:
        masking_controls = dialog.masking_widget.create_masking_controls(dialog.options_frame)
        layout.addWidget(masking_controls)
        if hasattr(dialog, 'button_manager') and dialog.button_manager:
            dialog._setup_masking_toggle_button()
    else:
        unavailable_group = QtWidgets.QGroupBox("Interactive Masking (Unavailable)")
        unavailable_layout = QtWidgets.QVBoxLayout(unavailable_group)
        msg = QtWidgets.QLabel("Interactive masking requires PyQtGraph.\nInstall with: pip install pyqtgraph")
        msg.setStyleSheet("color: #f59e0b; font-style: italic;")
        msg.setWordWrap(True)
        unavailable_layout.addWidget(msg)
        layout.addWidget(unavailable_group)

    # Clipping operations
    clipping_group = QtWidgets.QGroupBox("Clipping Operations")
    clipping_layout = QtWidgets.QVBoxLayout(clipping_group)

    dialog.aband_cb = QtWidgets.QCheckBox("Remove telluric O₂ A-band")
    dialog.aband_cb.setChecked(dialog.processing_params['clip_aband'])
    dialog.aband_cb.toggled.connect(lambda *_: _on_clip_aband_toggled(dialog))
    clipping_layout.addWidget(dialog.aband_cb)

    sky_layout = QtWidgets.QHBoxLayout()
    dialog.sky_cb = QtWidgets.QCheckBox("Remove sky lines, width:")
    dialog.sky_cb.setChecked(dialog.processing_params['clip_sky_lines'])
    dialog.sky_cb.toggled.connect(lambda *_: _on_clip_sky_toggled(dialog))
    sky_layout.addWidget(dialog.sky_cb)

    dialog.sky_width_spin = create_flexible_double_input(min_val=1.0, max_val=200.0, suffix=" Å", default=30.0)
    dialog.sky_width_spin.setValue(dialog.processing_params['sky_width'])
    try:
        dialog.sky_width_spin.editingFinished.connect(lambda *_: _on_sky_width_changed(dialog))
    except Exception:
        dialog.sky_width_spin.valueChanged.connect(lambda *_: _on_sky_width_changed(dialog))
    sky_layout.addWidget(dialog.sky_width_spin)
    sky_layout.addStretch()
    clipping_layout.addLayout(sky_layout)
    layout.addWidget(clipping_group)


def apply_step(dialog) -> None:
    """Apply masking and clipping operations (Step 0)."""
    # Apply masking
    if dialog.masking_widget:
        mask_regions = dialog.masking_widget.get_mask_regions()
        if mask_regions:
            dialog.preview_calculator.apply_step("masking", mask_regions=mask_regions, step_index=0)

    # Cache widget values safely
    apply_aband = False
    apply_sky = False
    sky_width = 40.0
    try:
        if hasattr(dialog, 'aband_cb') and dialog.aband_cb is not None:
            apply_aband = bool(dialog.aband_cb.isChecked())
    except Exception:
        pass
    try:
        if hasattr(dialog, 'sky_cb') and dialog.sky_cb is not None:
            apply_sky = bool(dialog.sky_cb.isChecked())
    except Exception:
        pass
    try:
        if hasattr(dialog, 'sky_width_spin') and dialog.sky_width_spin is not None:
            sky_width = float(dialog.sky_width_spin.value())
    except Exception:
        pass

    if apply_aband:
        dialog.preview_calculator.apply_step("clipping", clip_type="aband", step_index=0)
    if apply_sky:
        dialog.preview_calculator.apply_step("clipping", clip_type="sky", width=sky_width, step_index=0)


def calculate_preview(dialog):
    """Preview Step 0 operations based on current UI state."""
    preview_wave, preview_flux = dialog.preview_calculator.get_current_state()

    # Masking preview
    if dialog.masking_widget:
        mask_regions = dialog.masking_widget.get_mask_regions()
        if mask_regions:
            preview_wave, preview_flux = dialog.preview_calculator.preview_step("masking", mask_regions=mask_regions)

    # A-band
    try:
        if hasattr(dialog, 'aband_cb') and dialog.aband_cb is not None and bool(dialog.aband_cb.isChecked()):
            temp_calc = type(dialog.preview_calculator)(preview_wave, preview_flux)
            preview_wave, preview_flux = temp_calc.preview_step("clipping", clip_type="aband")
    except Exception:
        pass

    # Sky lines
    try:
        if hasattr(dialog, 'sky_cb') and dialog.sky_cb is not None and bool(dialog.sky_cb.isChecked()):
            width = dialog.sky_width_spin.value() if hasattr(dialog, 'sky_width_spin') else 40.0
            temp_calc = type(dialog.preview_calculator)(preview_wave, preview_flux)
            preview_wave, preview_flux = temp_calc.preview_step("clipping", clip_type="sky", width=width)
    except Exception:
        pass

    return preview_wave, preview_flux


def _on_clip_aband_toggled(dialog):
    dialog.processing_params['clip_aband'] = bool(dialog.aband_cb.isChecked()) if hasattr(dialog, 'aband_cb') else False
    dialog._update_preview()


def _on_clip_sky_toggled(dialog):
    dialog.processing_params['clip_sky_lines'] = bool(dialog.sky_cb.isChecked()) if hasattr(dialog, 'sky_cb') else False
    dialog._update_preview()


def _on_sky_width_changed(dialog):
    try:
        if hasattr(dialog, 'sky_width_spin') and dialog.sky_width_spin is not None:
            dialog.processing_params['sky_width'] = float(dialog.sky_width_spin.value())
    except Exception:
        pass
    dialog._update_preview()


