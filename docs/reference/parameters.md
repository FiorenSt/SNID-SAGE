# Parameters Reference

Unified reference of configurable parameters across GUI and CLI.

Notes:
- Defaults below refer to the current public CLI unless a row is marked as a config key.
- `zmax` is profile-dependent: `1.0` for `optical`, `2.5` for `onir`.
- `sage config show` reflects dynamically resolved defaults from the current build; it is not currently a file-backed persisted user config.

## Analysis Parameters

| Name | Type | Effective default | CLI flag | Description |
|---|---|---:|---|---|
| `zmin` | float | `-0.01` | `--zmin` | Minimum redshift to search |
| `zmax` | float | `1.0` (`optical`), `2.5` (`onir`) | `--zmax` | Maximum redshift to search |
| `lapmin` | float | `0.3` | `--lapmin` | Minimum overlap fraction between spectrum and template |
| `hsigma_lap_ccc_threshold` | float | `1.5` | `--hsigma-lap-ccc-threshold` | Clustering threshold using Hsigma-LAP-CCC = `(height × lap × CCC) / sqrt(sigma_z)` |
| `peak_window_size` | int | `10` | `--peak-window-size` | Peak-refinement search radius |
| `phase1_peak_min_height` | float | `0.3` | `--phase1-peak-min-height` | Minimum normalized phase-1 correlation peak height |
| `phase1_peak_min_distance` | int | `3` | `--phase1-peak-min-distance` | Minimum distance between phase-1 peaks in bins |
| `max_output_templates` | int | `10` | `--max-output-templates` | Maximum templates included in CLI outputs and summaries |
| `forced_redshift` | float or null | `None` | `--forced-redshift` | Force analysis at a fixed redshift and skip the redshift search |
| `age_min` | float or null | `None` | `--age-min` | Minimum template age in days |
| `age_max` | float or null | `None` | `--age-max` | Maximum template age in days |
| `type_filter` | list[str] or null | `None` | `--type-filter` | Restrict templates to selected SN types |
| `template_filter` | list[str] or null | `None` | `--template-filter` | Only use specific template names |
| `exclude_templates` | list[str] or null | `None` | `--exclude-templates` | Exclude specific template names |
| `profile` | str | `optical` | `--profile` | Analysis profile: `optical` or `onir` |

## Preprocessing Parameters

| Name | Type | Effective default | CLI flag | Description |
|---|---|---:|---|---|
| `spike_masking` | bool | `True` | `--no-spike-masking` to disable | Early spike/outlier masking before smoothing |
| `spike_floor_z` | float | `50.0` | `--spike-floor-z` | Minimum floor-relative robust z used for spike detection |
| `spike_baseline_window` | int | `501` | `--spike-baseline-window` | Running median baseline window in pixels |
| `spike_baseline_width` | float or null | `None` | `--spike-baseline-width` | Baseline width in wavelength units; overrides pixel window |
| `spike_rel_edge_ratio` | float | `2.0` | `--spike-rel-edge-ratio` | Center residual must exceed neighboring residuals by this factor |
| `spike_min_separation` | int | `2` | `--spike-min-separation` | Minimum pixel separation between removed spikes |
| `spike_max_removals` | int or null | `None` | `--spike-max-removals` | Optional cap on spikes removed per spectrum |
| `spike_min_abs_resid` | float or null | `None` | `--spike-min-abs-resid` | Minimum absolute residual amplitude required to count as a spike |
| `savgol_window` | int | `0` | `--savgol-window` | Savitzky-Golay window in pixels; `0` disables smoothing |
| `savgol_order` | int | `3` | `--savgol-order` | Savitzky-Golay polynomial order |
| `aband_remove` | bool | `False` | `--aband-remove` | Remove telluric O2 A-band |
| `skyclip` | bool | `False` | `--skyclip` | Mask common sky emission lines |
| `emclip` | bool | `False` | `--emclip` | Mask host emission lines using a per-row or forced redshift when available |
| `emclip_z` | float | `-1.0` | `--emclip-z` | Redshift used for emission-line masking; `-1` disables masking |
| `emwidth` | float | `40.0` | `--emwidth` | Mask width in Angstroms for sky/emission-line clipping |
| `wavelength_masks` | list[range] or null | `None` | `--wavelength-masks WMIN:WMAX ...` | Additional wavelength ranges to mask |
| `apodize_percent` | float | `10.0` | `--apodize-percent` | Percentage of the spectrum ends to apodize |

## Batch-Only Parameters

| Name | Type | Effective default | CLI flag | Description |
|---|---|---:|---|---|
| `list_csv` | str or null | `None` | `--list-csv` | CSV file listing spectra to analyze |
| `path_column` | str | `path` | `--path-column` | Column in `--list-csv` containing spectrum paths |
| `redshift_column` | str | `redshift` | `--redshift-column` | Column in `--list-csv` containing per-row forced redshifts |
| `brief` | bool | `True` | `--brief` | Minimal console output for batch runs |
| `full` | bool | `False` | `--full` | Detailed console output |
| `workers` | int | `0` | `--workers` | Worker processes: `0` sequential, `-1` all cores, `N` fixed count |
| `stop_on_error` | bool | `False` | `--stop-on-error` | Stop processing after the first failing spectrum |
| `minimal` | bool | `False` | `--minimal` | Write per-spectrum `.output` files and batch reports only |
| `complete` | bool | `False` | `--complete` | Write full output files plus the extended plot/data artifact set |

## Config Keys Shown By `sage config`

These values come from the current `ConfigurationManager` defaults and dynamic path resolution.

### Paths

| Key | Type | Default | Notes |
|---|---|---|---|
| `paths.templates_dir` | str | auto-resolved managed template bank | Can be overridden with `SNID_SAGE_TEMPLATE_DIR` or by passing a templates directory argument to the CLI |
| `paths.output_dir` | str | `./results` | Default output directory used when `--output-dir` is omitted |
| `paths.data_dir` | str | `./data` | Default data directory key returned by `sage config show` |
| `paths.config_dir` | str | resolved state root | Uses `SNID_SAGE_STATE_DIR` when set; otherwise usually `<cwd>/SNID-SAGE`, or the repo root in editable/dev installs |

### Display

| Key | Type | Default | Notes |
|---|---|---|---|
| `display.theme` | str | `light` | GUI display setting |
| `display.plot_style` | str | `default` | Plot styling preset |
| `display.plot_dpi` | int | `100` | Saved figure DPI |
| `display.show_grid` | bool | `True` | Grid visibility preference |
| `display.show_markers` | bool | `True` | Marker/line visibility preference |

### LLM

| Key | Type | Default | Notes |
|---|---|---|---|
| `llm.enable_llm` | bool | `True` | Enables AI-assistant features in the GUI |
| `llm.llm_provider` | str | `openrouter` | Current default provider key |
| `llm.model_name` | str | `anthropic/claude-3-sonnet:beta` | Default model identifier returned by `sage config show` |
| `llm.api_key` | str | empty string | Sensitive value; normally set through the AI workflow |
| `llm.max_tokens` | int | `4000` | Token budget for AI responses |
| `llm.temperature` | float | `0.7` | Sampling temperature |

## CLI Examples

```powershell
sage spectrum.dat --output-dir results\
sage spectrum.dat --zmin 0.0 --zmax 0.1
sage spectrum.dat --lapmin 0.3
sage spectrum.dat --age-min -5 --age-max 30
sage spectrum.dat --savgol-window 11 --savgol-order 3
sage spectrum.dat --aband-remove --skyclip
sage spectrum.dat --wavelength-masks 6550:6600 7600:7700
sage spectrum.dat --type-filter Ia Ib Ic

sage batch "data/*.dat" --workers -1 --brief
sage batch --list-csv spectra.csv --path-column path --redshift-column redshift
```

## See Also

- [CLI Command Reference](../cli/command-reference.md) - Complete CLI documentation
- [Batch Processing](../cli/batch-processing.md) - Processing multiple spectra
- [GUI Settings](../gui/settings-configuration.md) - GUI parameter configuration

