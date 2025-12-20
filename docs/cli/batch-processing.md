# Batch Processing

Efficiently process many spectra with the CLI `batch` command.

## Command

```powershell
# Process multiple spectra; write outputs under results/
sage batch "data/*.dat" --output-dir results/

# Parallel: use all CPU cores (Windows, macOS, Linux)
sage batch "data/*.dat" --output-dir results/ --workers -1

# Parallel: specify number of workers
sage batch "data/*.dat" --output-dir results/ --workers 4
```

### List-based input (CSV)

```powershell
# Use a CSV listing spectra with optional per-row redshift
sage batch --list-csv "data/spectra_list.csv" --output-dir results/

# If your CSV uses different column names
sage batch --list-csv input.csv --path-column "Spectrum Path" --redshift-column "Host Redshift" --output-dir results/
```

Notes:
- The CSV must include a path column; redshift is optional.
- Relative paths in the CSV are resolved relative to the CSV file's directory.
- When a row has a redshift value, analysis is performed at that fixed redshift for that spectrum; otherwise the global search range is used.
 - Emission clipping: `--emclip` uses the row's redshift when present (skips otherwise). Use `--emclip-z` to force a fixed clipping redshift for all rows.
- `--emclip`/`--emclip-z` only control masking; to fix the analysis redshift use `--forced-redshift`.

## Modes

| Mode | Description |
|---|---|
| Default | Main outputs per spectrum plus a summary |
| `--minimal` | Summary only (fastest, least disk) |
| `--complete` | Full outputs and plots (largest disk) |

## Common options

| Option | Description |
|---|---|
| `--zmin FLOAT` / `--zmax FLOAT` | Redshift search range (default: -0.01 to 1.0) |
| `--forced-redshift FLOAT` | Force a fixed redshift for all spectra |
| `--type-filter TYPE...` | Restrict templates by type (e.g., Ia Ib Ic) |
| `--template-filter NAME...` | Only use specific templates by name |
| `--hlapmin FLOAT` / `--lapmin FLOAT` | Quality/overlap thresholds (defaults: 0.1 / 0.3) |
| `--hlap-ccc-threshold FLOAT` | HLAP-CCC clustering threshold (default: 0.4) |
| `--output-dir DIR` | Output directory for results |
| `--stop-on-error` | Stop processing upon first error |
| `--verbose` | Verbose console output |
| `--brief` / `--full` | Toggle concise vs detailed console output |
| `--no-progress` | Disable progress output |
| `--workers INT` | Parallel workers: 0=sequential (default), -1=all cores, N=fixed |

### Preprocessing

| Option | Description |
|---|---|
| `--savgol-window INT` / `--savgol-order INT` | Savitzky–Golay smoothing (0 disables) |
| `--aband-remove` | Remove telluric O2 A-band (7550–7700 Å) |
| `--skyclip` | Clip sky emission lines (±emwidth Å) |
| `--emclip` | Auto host emission clipping using per-row/forced z (does not force analysis redshift) |
| `--emclip-z FLOAT` | Fixed redshift for emission clipping (-1 disables; masking only) |
| `--emwidth FLOAT` | Clipping half-width in Å (default: 40) |
| `--wavelength-masks WMIN:WMAX ...` | Additional mask ranges |
| `--apodize-percent FLOAT` | Apodization percent (default: 10) |

```powershell
# Redshift search range
sage batch "data/*.dat" --zmin 0.0 --zmax 0.5 --output-dir results/

# Force a fixed redshift for all spectra
sage batch "data/*.dat" --forced-redshift 0.023 --output-dir results/

# Force per-row redshift from a CSV list (only where present)
sage batch --list-csv "path/to/list.csv" --output-dir results/

# Restrict to specific types
sage batch "data/*.dat" --type-filter Ia Ib Ic --output-dir results/

# Stop on first error; increase verbosity
sage batch "data/*.dat" --stop-on-error --verbose --output-dir results/

# Parallel on all cores (cross-platform)
sage batch "data/*.dat" --output-dir results/ --workers -1
```

## Output structure (default)

| Per spectrum | Summary |
|---|---|
| `.output`, `.fluxed`, `.flattened` | `batch_summary.txt` (includes a `zFixed` column) |

With `--complete`, additional plots are generated (comparison, clustering, redshift–age, subtype proportions).

## Tips

- Start with a small subset to validate parameters
- Use `--type-filter` to reduce runtime on large template sets
- Prefer `--minimal` for quick surveys; rerun interesting cases with `--complete`
 - When using CSV lists, keep spectrum paths relative to the CSV folder for portability
 - Parallelism uses only Python standard library; no extra packages required
 - On multi-core systems, start with `--workers -1`; reduce if memory is limited

## Troubleshooting

- “Out of memory” on large batches: narrow the type range, reduce `--workers`, or run smaller batches
- Windows/macOS/Linux supported: ensure you run from a normal shell; the CLI handles process spawning safely

## See also

- [Command Reference](command-reference.md)
- [Template Management](../gui/templates-manager.md)

