## Lines GUI

Note: This page is a work in progress.

Spin-off GUI to manage spectral lines and user presets, with a light spectrum preview.

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
