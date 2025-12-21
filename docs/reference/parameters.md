## Parameters Reference

Unified reference of configurable parameters across GUI and CLI.

### Analysis

| Name | Type | Default | CLI Flag | Description |
|---|---|---:|---|---|
| zmin | float | -0.01 | `--zmin` | Minimum redshift to search |
| zmax | float | 1.0 | `--zmax` | Maximum redshift to search |
| lapmin | float | 0.3 | `--lapmin` | Minimum overlap fraction between spectrum and template |
| age_min | float or null | None | `--age-min` | Minimum template age (days) |
| age_max | float or null | None | `--age-max` | Maximum template age (days) |
| max_output_templates | int | 10 | `--max-output-templates` | Maximum templates included in outputs (CLI/UI summaries) |
| hlap_ccc_threshold | float | 0.45 | `--hlap-ccc-threshold` (batch) | Threshold used when clustering by HLAP-CCC (HLAP/(1−CCC)) |
| forced_redshift | float or null | None | `--forced-redshift` | Force analysis at a fixed redshift; skips redshift search |
| type_filter | list[str] or null | None | `--type-filter` | Allowed supernova types (Ia, Ib, Ic, II, …) |
| template_filter | list[str] or null | None | `--template-filter` | Only use specified template names |
| exclude_templates | list[str] or null | None | `--exclude-templates` | Exclude specified template names |
| wavelength_tolerance | float | 10.0 | — | Matching tolerance in Å for config-based workflows |
| emclip | bool | False | `--emclip` (batch) | Auto host emission clipping using per-entry redshift (skips if none) |
| emclip_z | float | -1.0 | `--emclip-z` | Redshift for emission line clipping (-1 disables; masking only, does not force analysis redshift) |
| emwidth | float | 40.0 | `--emwidth` | Emission line clipping width (Å) |

### Processing

| Name | Type | Default | CLI Flag | Description |
|---|---|---:|---|---|
| spike_masking | bool | True | `--no-spike-masking` (to disable) | Early spike/outlier removal before smoothing |
| spike_floor_z | float | 50.0 | `--spike-floor-z` | Minimum robust z relative to floor for outlier detection |
| spike_baseline_window | int | 501 | `--spike-baseline-window` | Running median window (pixels; odd, large) |
| spike_baseline_width | float or null | None | `--spike-baseline-width` | Alternative baseline width in wavelength units |
| spike_rel_edge_ratio | float | 2.0 | `--spike-rel-edge-ratio` | Center residual must exceed neighbors by this factor |
| spike_min_separation | int | 2 | `--spike-min-separation` | Minimum pixel separation between removed spikes |
| spike_max_removals | int or null | None | `--spike-max-removals` | Optional cap on number of removed spikes |
| spike_min_abs_resid | float or null | None | `--spike-min-abs-resid` | Minimum absolute residual amplitude (flux units) |
| savgol_window | int | 0 | `--savgol-window` | Savitzky–Golay window (pixels; 0 disables) |
| savgol_fwhm | float | 0.0 | — | Savitzky–Golay FWHM in Å (alternative to window size) |
| savgol_order | int | 3 | `--savgol-order` | Savitzky–Golay polynomial order |
| aband_remove | bool | False | `--aband-remove` | Remove telluric A-band |
| skyclip | bool | False | `--skyclip` | Clip sky emission lines |
| emclip | bool | False | `--emclip` (batch) | Use per-entry/forced redshift for emission clipping (does not force analysis redshift) |
| wavelength_masks | list[range] or null | None | `--wavelength-masks WMIN:WMAX ...` | Wavelength ranges to mask (e.g., 6550:6600) |
| apodize_percent | float | 10.0 | `--apodize-percent` | Percentage of spectrum ends to apodize |

### Templates

| Name | Type | Default | CLI Flag | Description |
|---|---|---:|---|---|
| type_filter | list[str] or null | None | `--type-filter` | Allowed SN types (Ia, Ib, Ic, II, …) |
| template_filter | list[str] or null | None | `--template-filter` | Only use specified template names |
| exclude_templates | list[str] or null | None | `--exclude-templates` | Names to exclude from analysis |

### Display

| Name | Type | Default | CLI Flag | Description |
|---|---|---:|---|---|
| theme | str | light | — | UI theme (light/dark) |
| plot_style | str | default | — | Matplotlib style |
| plot_dpi | int | 100 | — | Saved figure DPI |
| show_grid | bool | True | — | Show grid in plots |
| show_markers | bool | True | — | Show markers/lines in plots |

### LLM

| Name | Type | Default | CLI Flag | Description |
|---|---|---:|---|---|
| enable_llm | bool | True | — | Enable AI assistant features |
| llm_provider | str | openrouter | — | LLM provider key |
| model_name | str | anthropic/claude-3-sonnet:beta | — | Model name identifier |
| api_key | str | '' | — | API key (stored securely) |
| max_tokens | int | 4000 | — | Max tokens per response |
| temperature | float | 0.7 | — | Sampling temperature |

### Paths

| Name | Type | Default | CLI Flag | Description |
|---|---|---:|---|---|
| templates_dir | str | auto/`templates/` | CLI arg | Path to templates directory |
| output_dir | str | `./results` | `--output-dir` | Directory for output files |
| data_dir | str | `./data` | — | Data directory |
| config_dir | str | platform config path | — | Configuration directory |

### CLI mappings (identify)
```bash
sage spectrum.dat --output-dir results/ ; \
  sage spectrum.dat --zmin 0.0 --zmax 0.1 ; \
  sage spectrum.dat --lapmin 0.3 ; \
  sage spectrum.dat --age-min -5 --age-max 30 ; \
  sage spectrum.dat --savgol-window 11 --savgol-order 3 ; \
  sage spectrum.dat --aband-remove --skyclip ; \
  sage spectrum.dat --wavelength-masks 6550:6600 7600:7700 ; \
  sage spectrum.dat --type-filter Ia Ib Ic
```

