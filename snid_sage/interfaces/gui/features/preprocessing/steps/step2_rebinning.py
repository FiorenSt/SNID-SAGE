from PySide6 import QtWidgets


def create_options(dialog, layout: QtWidgets.QVBoxLayout) -> None:
    desc = QtWidgets.QLabel("Apply log-wavelength rebinning on the SNID grid.")
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #64748b; font-size: 11pt; margin-bottom: 10px;")
    layout.addWidget(desc)

    rebin_group = QtWidgets.QGroupBox("Rebinning Configuration")
    rebin_layout = QtWidgets.QVBoxLayout(rebin_group)
    # Add more vertical spacing to increase the area
    rebin_layout.setSpacing(15)
    rebin_layout.setContentsMargins(15, 20, 15, 20)

    dialog.log_rebin_cb = QtWidgets.QCheckBox("Apply log-wavelength rebinning")
    dialog.log_rebin_cb.setChecked(True)
    dialog.log_rebin_cb.setEnabled(False)
    rebin_layout.addWidget(dialog.log_rebin_cb)

    # Add some extra vertical space at the bottom
    rebin_layout.addStretch(1)
    layout.addWidget(rebin_group)

    info_group = QtWidgets.QGroupBox("Grid Information")
    info_layout = QtWidgets.QVBoxLayout(info_group)
    # Add more vertical spacing to increase the area
    info_layout.setSpacing(15)
    info_layout.setContentsMargins(15, 20, 15, 20)
    
    try:
        from snid_sage.snid.snid import NW, MINW, MAXW
        info_text = QtWidgets.QLabel(
            f"Target grid: {NW} points\n"
            f"Wavelength range: {MINW} - {MAXW} Å\n"
            "Log spacing: uniform in log wavelength"
        )
    except Exception:
        info_text = QtWidgets.QLabel(
            "Target grid: 1024 points\nWavelength range: 2500 - 10000 Å\nLog spacing: uniform in log wavelength"
        )
    info_text.setStyleSheet("color: #64748b; font-size: 10pt;")
    info_layout.addWidget(info_text)
    
    # Add some extra vertical space at the bottom
    info_layout.addStretch(1)
    layout.addWidget(info_group)


def apply_step(dialog) -> None:
    # Collect mask regions to force interpolation-based rebin (no steps)
    mask_regions = []
    try:
        if hasattr(dialog, 'masking_widget') and dialog.masking_widget is not None:
            mask_regions = dialog.masking_widget.get_mask_regions() or []
    except Exception:
        mask_regions = []
    # Include A-band/skylines using stable processing_params (widgets may be deleted)
    try:
        apply_aband = bool(dialog.processing_params.get('clip_aband', False))
    except Exception:
        apply_aband = False
    try:
        apply_sky = bool(dialog.processing_params.get('clip_sky_lines', False))
    except Exception:
        apply_sky = False
    try:
        sky_width = float(dialog.processing_params.get('sky_width', 40.0))
    except Exception:
        sky_width = 40.0
    if apply_aband:
        mask_regions = list(mask_regions) + [(7550.0, 7700.0)]
    if apply_sky:
        for l in (5577.0, 6300.2, 6364.0):
            mask_regions.append((l - sky_width, l + sky_width))
    dialog.preview_calculator.apply_step("log_rebin", mask_regions=mask_regions, step_index=2)


def calculate_preview(dialog):
    # Pass mask regions forward so rebin preview can use interpolation-based method
    mask_regions = []
    try:
        if hasattr(dialog, 'masking_widget') and dialog.masking_widget is not None:
            mask_regions = dialog.masking_widget.get_mask_regions() or []
    except Exception:
        mask_regions = []
    # Include A-band/skylines using stable processing_params
    try:
        apply_aband = bool(dialog.processing_params.get('clip_aband', False))
    except Exception:
        apply_aband = False
    try:
        apply_sky = bool(dialog.processing_params.get('clip_sky_lines', False))
    except Exception:
        apply_sky = False
    try:
        sky_width = float(dialog.processing_params.get('sky_width', 40.0))
    except Exception:
        sky_width = 40.0
    if apply_aband:
        mask_regions = list(mask_regions) + [(7550.0, 7700.0)]
    if apply_sky:
        for l in (5577.0, 6300.2, 6364.0):
            mask_regions.append((l - sky_width, l + sky_width))
    return dialog.preview_calculator.preview_step("log_rebin", mask_regions=mask_regions)


