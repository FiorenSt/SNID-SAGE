# CLI Command Reference

SNID SAGE provides a command-line interface for automated spectrum analysis, batch processing, and scripting workflows.

## Overview

The CLI offers:
- Single spectrum analysis with detailed outputs
- Batch processing of multiple spectra
- Configuration management
- Template and data management

### Supported input formats

SNID SAGE accepts common text and binary spectrum formats:
- .txt, .dat, .ascii, .asci
- .csv
- .flm
- .fits, .fit

Files can have header rows; CSVs with headers (e.g., wave,flux,flux_err) are supported.

## Installation

### Install SNID SAGE CLI
```bash
pip install snid-sage
```

### Verify Installation
```bash
sage --version
sage --help
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
| `--type-filter TYPE...` | Filter templates by type |
| `--template-filter NAME...` | Restrict to specific templates |
| `--zmin FLOAT` | Min redshift (default: -0.01) |
| `--zmax FLOAT` | Max redshift (default: 1.0) |
| `--age-min FLOAT` / `--age-max FLOAT` | Template age bounds (days) |
| `--forced-redshift FLOAT` | Force a fixed redshift for all spectra |
| `--profile {optical,onir}` | Analysis profile (default: config/optical) |
| `--list-csv FILE` | CSV list of spectra (columns: path[, redshift]) |
| `--path-column NAME` | Column for paths in `--list-csv` (default: path) |
| `--redshift-column NAME` | Column for redshift in `--list-csv` (default: redshift) |
| `--hlapmin FLOAT` | Minimum HLAP (default: 0.1) |
| `--lapmin FLOAT` | Minimum overlap fraction (default: 0.3) |
| `--hlap-ccc-threshold FLOAT` | HLAP-CCC clustering threshold (HLAP/(1−CCC), default: 0.4) |
| `--type-filter TYPE...` | Restrict templates to these types |
| `--template-filter NAME...` | Only use specified template names |
| `--exclude-templates NAME...` | Exclude specified template names |
| `--workers INT` | Parallel workers: 0=sequential, -1=all cores, N=fixed |
| `--no-plots` | Do not generate plots |
| `--savgol-window INT` | Savitzky–Golay window (0 disables) |
| `--savgol-order INT` | Savitzky–Golay polynomial order |
| `--aband-remove` | Remove telluric O2 A-band (7550–7700 Å) |
| `--skyclip` | Clip sky emission lines (±emwidth Å) |
| `--emclip` | Auto host emission clipping using per-entry/forced z when provided (does not force analysis redshift) |
| `--emclip-z FLOAT` | Fixed redshift for emission clipping (-1 disables; masking only, does not force analysis redshift) |
| `--emwidth FLOAT` | Emission/sky clipping half-width in Å (default: 40) |
| `--wavelength-masks WMIN:WMAX ...` | Additional mask ranges (e.g., 6550:6600) |
| `--apodize-percent FLOAT` | Apodization percent (default: 10) |
| `--minimal` / `--complete` | Output modes |
| `--brief` / `--full` | Console verbosity modes |
| `--no-progress` | Disable progress output |
| `--stop-on-error` | Stop processing on first error |
| `--verbose` | Verbose output |

Outputs: per-spectrum result files; summary includes a `zFixed` column indicating whether a fixed redshift was used for that spectrum.

### `sage config`

Manage SNID SAGE configuration settings.

#### Basic Usage
```powershell
sage config <command> [options]
```

#### Commands

| Command | Description |
|---|---|
| `show` | Show current configuration |
| `set <key> <value>` | Set configuration value |
| `get <key>` | Get configuration value |
| `reset` | Reset to defaults |
| `export` | Export configuration |
| `import <file>` | Import configuration |

#### Keys (selected)

| Key | Description |
|---|---|
| `paths.templates_dir` | Template directory |
| `paths.output_dir` | Default output directory |
| `paths.data_dir` | Data directory |
| `analysis.hlapmin` | Minimum HLAP |
| `analysis.lapmin` | Minimum overlap fraction |
| `analysis.redshift_min`, `analysis.redshift_max` | Redshift bounds |
| `processing.apodize_percent` | Apodization percentage |

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