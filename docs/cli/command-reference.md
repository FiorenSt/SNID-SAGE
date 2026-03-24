# CLI Command Reference

SNID SAGE provides a command-line interface for automated spectrum analysis, batch processing, and scripting workflows.

## Overview

The CLI offers:
- Single spectrum analysis with detailed outputs
- Batch processing of multiple spectra
- Configuration inspection
- Template and data management

### Supported input formats

SNID SAGE accepts common text and binary spectrum formats:
- .txt, .dat, .ascii, .asci
- .csv
- .flm
- .fits, .fit

Files can have header rows; CSVs with headers (e.g., wave,flux,flux_err) are supported.

## Installation

```powershell
pip install snid-sage
sage --version
```

## Core Commands

### `sage`

Analyze a single spectrum against the template library with cluster-aware analysis and detailed outputs.

#### Basic Usage
```powershell
sage <spectrum_file> [options]
```

#### Examples
```powershell
# Basic analysis
sage data\SN2018bif.csv

# With output directory
sage data\SN2018bif.csv --output-dir results\

# With specific redshift
sage data\SN2018bif.csv --forced-redshift 0.018

# Complete mode with all plots
sage data\SN2018bif.csv --complete
```

#### Modes

| Mode | Description |
|---|---|
| Default | Main outputs without detailed plots |
| `--complete` | All outputs including detailed GUI-style plots |

#### Standard Outputs
- Classification results (type, subtype, confidence)
- Redshift and age estimates
- Template matches and correlation scores
- Basic plots and data files

### `sage batch`

Process multiple spectra simultaneously with optimized workflows and detailed reporting.

#### Basic Usage
```powershell
sage batch <input_pattern> [templates_dir] [options]
sage batch --list-csv <file.csv> [templates_dir] [options]
```

#### Examples
```powershell
# Process all .dat files in a directory
sage batch "data/*.dat" --output-dir batch_results\

# Process specific files
sage batch "data/sn2024*.dat" --output-dir results\

# With explicit template directory (overrides auto-downloaded bank)
sage batch "data/*.dat" "D:\SNID_TEMPLATES" --output-dir results\

# List-based batch from CSV (per-row redshift when present)
sage batch --list-csv "data/spectra_list.csv" --output-dir results\

# Custom column names in CSV
sage batch --list-csv input.csv --path-column "Spectrum Path" --redshift-column "Host Redshift" --output-dir results\
```

#### Options

| Option | Description |
|---|---|
| `--output-dir DIR` | Output directory for results |
| `--zmin FLOAT` / `--zmax FLOAT` | Redshift range (default: -0.01 to 1.0) |
| `--age-min FLOAT` / `--age-max FLOAT` | Template age bounds (days) |
| `--forced-redshift FLOAT` | Force a fixed redshift for all spectra |
| `--profile {optical,onir}` | Analysis profile (default: optical) |
| `--lapmin FLOAT` | Minimum overlap fraction (default: 0.3) |
| `--hsigma-lap-ccc-threshold FLOAT` | HσLAP-CCC clustering threshold (default: 1.5) |
| `--type-filter TYPE...` | Restrict templates to these types |
| `--template-filter NAME...` | Only use specified template names |
| `--exclude-templates NAME...` | Exclude specified template names |
| `--list-csv FILE` | CSV list of spectra (columns: path[, redshift]) |
| `--path-column NAME` | Column for paths in `--list-csv` (default: path) |
| `--redshift-column NAME` | Column for redshift in `--list-csv` (default: redshift) |
| `--workers INT` | Parallel workers: 0=sequential, -1=all cores, N=fixed |
| `--savgol-window INT` / `--savgol-order INT` | Savitzky–Golay smoothing |
| `--aband-remove` | Remove telluric O2 A-band |
| `--skyclip` | Clip sky emission lines |
| `--emclip` | Auto host emission clipping using per-entry/forced z |
| `--emclip-z FLOAT` | Fixed redshift for emission clipping (-1 disables) |
| `--emwidth FLOAT` | Emission/sky clipping half-width in Å (default: 40) |
| `--wavelength-masks WMIN:WMAX ...` | Additional mask ranges |
| `--apodize-percent FLOAT` | Apodization percent (default: 10) |
| `--minimal` / `--complete` | Output modes |
| `--brief` / `--full` | Console verbosity modes |
| `--no-plots` / `--no-progress` | Disable plots/progress output |
| `--stop-on-error` / `--verbose` | Error handling and verbosity |

Outputs: per-spectrum result files; summary includes a `zFixed` column indicating whether a fixed redshift was used for that spectrum.

### `sage config`

Inspect SNID SAGE effective/default configuration values.

#### Basic Usage
```powershell
sage config <command> [options]
```

#### Commands

| Command | Description |
|---|---|
| `show` | Show current configuration/default values |
| `get <key>` | Get one configuration/default value |

#### Keys (selected)

| Key | Description |
|---|---|
| `paths.templates_dir` | Template directory |
| `paths.output_dir` | Default output directory |
| `paths.data_dir` | Data directory |
| `analysis.lapmin` | Minimum overlap fraction |
| `analysis.redshift_min`, `analysis.redshift_max` | Redshift bounds |
| `processing.apodize_percent` | Apodization percentage |

Notes:
- The User Templates Folder is managed from `snid-sage-templates` via `Change User Folder`
- The main GUI does not currently have a separate `Settings -> Configuration` panel
- To override the managed built-in templates location from the terminal, set `SNID_SAGE_TEMPLATE_DIR` before running SNID SAGE

### `sage templates`

Manage template library and template-related operations.

#### Basic Usage
```powershell
sage templates <command> [options]
```

#### Commands

| Command | Description |
|---|---|
| `list` | List available templates |
| `info <template>` | Show template information |
| `search <query>` | Search templates |
| `validate` | Validate template library |
| `update` | Update template library |
| `import-csv <file>` | Import templates from CSV/TSV (multi-epoch) |

#### Examples
```powershell
# List all templates
sage templates list

# Search for Type Ia templates
sage templates search "Ia"

# Show template information
sage templates info "SN1994D"

# Validate template library
sage templates validate

# Import templates from CSV/TSV
sage templates import-csv data\list.csv --dest C:\\User_templates --name-column object_name --path-column spectrum_file_path --age-column age --redshift-column redshift --type-column type --subtype-column subtype --sim-flag-column sim_flag
```

#### Environment Override

To override the managed built-in templates bank location from the terminal:

```bash
export SNID_SAGE_TEMPLATE_DIR=/path/to/templates_root
```

```powershell
$env:SNID_SAGE_TEMPLATE_DIR = "C:\path\to\templates_root"
```

The default User Templates folder then becomes the sibling `user_templates`
directory next to that location.

## Troubleshooting

### Common Issues

| Error | Cause | Solution |
|---|---|---|
| `Template library not found` | Missing template directory | Set `paths.templates_dir` in config |
| `Invalid spectrum format` | Unsupported file format | Convert to supported format |
| `No templates match criteria` | Template filters too restrictive | Adjust `--type-filter` or age range |
| `Analysis failed` | Input data quality issues | Check spectrum quality and preprocessing |

## Performance Tips

- Use `--type-filter` to limit template search
- Keep console noise low with `--brief` in large runs
- Save to SSD for faster I/O

## Related Documentation

- [Batch Processing Guide](batch-processing.md) - Advanced batch workflows
- [Configuration Guide](../reference/configuration-guide.md) - Detailed configuration options
- [Troubleshooting](../reference/troubleshooting.md) - Common issues and solutions 