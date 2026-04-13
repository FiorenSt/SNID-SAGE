# GUI Interface Overview (PySide6/Qt)

The SNID SAGE graphical interface is built with PySide6/Qt and `pyqtgraph`, providing an intuitive, high-performance environment for supernova spectrum analysis. This guide covers all interface components and workflows.

## Main Window Layout

The interface is organized into distinct regions for efficient workflow:

### Interface Regions
1. **Header Panel** - Logo, status indicators, and theme controls
2. **Control Panel** - Analysis parameters and workflow buttons
3. **Spectrum Display** - Interactive plotting area with modern styling
4. **Status Bar** - Progress indicators and system information

## Workflow Buttons

Order of operations:
1) Load Spectrum → 2) Preprocessing → 3) SNID Analysis → 4) Optional tools (redshift mode, overlays, summaries) → 5) AI Assistant (optional)

Always available:
- Load Spectrum, Reset, Settings

After loading: Preprocessing

After preprocessing: SNID Analysis and Redshift (manual or range search)

After analysis: Results dialogs, overlays, clustering, AI Assistant

## Control Panel (key items)

Most options are set here. For a compact list of parameters and defaults, see the [Parameters Reference](../reference/parameters.md).

| Group | Controls | Usage |
|---|---|---|
| Input | File path; Redshift (manual/auto); Wavelength range | Load spectrum and set optional fixed redshift and analysis window |
| Preprocessing | Smoothing (window/order); Telluric A-band; Skyline clipping; Custom masks | Clean spectrum before analysis; map to CLI flags like `--savgol-window`, `--aband-remove`, `--skyclip` |
| Templates | Type filters; Age range; Minimum correlation; Wavelength overlap | Restrict/guide matching for speed and precision |

## Spectrum Display

| Action | How | Notes |
|---|---|---|
| Pan | Drag | |
| Zoom | Wheel or box | |
| Reset | Double-click | Restores view |
| Toggle view | Flux vs flattened | Also show/hide grid and legend |
| Overlays | Template matches, masks, line IDs, optional errors | Configure in Controls/Dialogs |

## Results

| Area | Contents | Actions |
|---|---|---|
| Status | Type, best template, confidence, redshift, age | Quick overview |
| Dialogs | Cluster summary, subtype proportions, redshift–age | Open after analysis |
| Export | Save figures and data from dialogs | PNG/SVG/PDF supported |

## AI Assistant

| Feature | Description | Where |
|---|---|---|
| Quick Summary | Short explanation of classification | AI Assistant button |
| Detailed Analysis | Structured scientific interpretation | AI Assistant button |
| Scientific Context | Literature-style discussion | AI Assistant button |
| Publication Text | Methods/results blocks | AI Assistant button |
| Configuration | Provider, Model, API key | AI Assistant window → `Settings` tab |
 

## Notes

GUI: PySide6 (Qt). Plotting: pyqtgraph.

## Tips

- Follow the button order; check S/N and wavelength range first
- Use type filters for speed; close unused dialogs
- Review multiple top matches before finalizing

## Troubleshooting

- Buttons disabled: ensure prior step done (load → preprocess → analyze)
- Plot not updating: toggle view or refresh; check status messages
- Slow: reduce template set; close apps; check memory
- AI not working: set API key; ensure analysis completed

See [Troubleshooting](../reference/troubleshooting.md).

## See Also

- [First Analysis](../quickstart/first-analysis.md) - Step-by-step tutorial
- [Parameters Reference](../reference/parameters.md) - All settings and defaults
- [CLI Reference](../cli/command-reference.md) - Command-line alternative