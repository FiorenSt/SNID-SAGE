## Lines GUI

Note: This page is a work in progress.

The standalone **SNID-SAGE Line Manager** is launched with `snid-sage-lines`.

This utility is separate from the main GUI's **Spectral Lines** button:

- **`Spectral Lines`** is the in-app, post-analysis line-identification and line-analysis workflow
- **`snid-sage-lines`** is a separate utility for managing line definitions, presets, and preview overlays

This standalone Line Manager is still evolving, so expect this page and the utility itself to change.

### Purpose

Use the Line Manager to maintain the line database and presets that can later appear in spectral-line overlays.

### Tabs

| Tab | Purpose |
|---|---|
| Lines | Searchable table of effective lines (built-in + user) |
| Presets | Define criteria sets (category, origin, SN types, strength, phase, name patterns) |

### Lines panel

| Action | Details |
|---|---|
| Manage lines | Add/Edit/Delete user lines |
| Columns | Name, Air/Vac wavelengths, Category, Origin, SN Types |
| Styling | Bold rows = user-defined entries |

### Test Spectrum
- Load a spectrum and preview with line overlays (pyqtgraph)
- Toggle “in-range only” to limit overlays to visible wavelength range
- Open **Advanced Preprocessing** for spectrum cleanup before checking overlays

### Presets panel
- Create and save named preset filters
- Useful to focus on e.g. He I for Type Ib or H-alpha for Type II

### Tips
- Keep names consistent; include notes when adding new lines
- Use presets to streamline repeated analysis tasks

## See Also

- [Preprocessing Guide](preprocessing.md) - Spectrum preparation
- [Interface Overview](interface-overview.md) - Main GUI features
