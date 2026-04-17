## Preprocessing (GUI)

How to prepare spectra before analysis.

### Step 0: Early spike masking (automatic)
- SNID SAGE applies an automatic early spike/outlier masking step before the standard preprocessing pipeline.
- This is enabled by default in both the GUI and the CLI.
- In the CLI, you can disable it with `--no-spike-masking`.
- The current GUI workflow uses the default automatic behavior rather than exposing a separate user-facing "cosmic-ray cleanup" wizard step.

### Quick SNID Preprocessing

| Purpose | Actions | When to use |
|---|---|---|
| Minimal steps to prepare a spectrum for SNID | Log rebinning, optional S-G smoothing, apodization, continuum handling | Most cases; fastest path to classification |

### Advanced Preprocessing

Open via: **Preprocessing** → **Advanced Preprocessing**

| Step | Control | Parameter | Default | CLI Flag | Notes |
|---|---|---|---:|---|---|
| 1. Input and range | Wavelength range | `wmin`, `wmax` | None | — | Leave blank for auto |
| 2. Smoothing | Savitzky–Golay window | `savgol_window` | 0 | `--savgol-window` | 0 disables; typical 11–21 |
|  | Savitzky–Golay order | `savgol_order` | 3 | `--savgol-order` | |
| 3. Telluric and sky | Remove A-band | `aband_remove` | False | `--aband-remove` | Masks ~7550–7700 Å |
|  | Sky line clipping | `skyclip` | False | `--skyclip` | |
|  | Emission clipping (auto) | — | — | `--emclip` | Uses per-entry/forced z; does not force analysis redshift |
|  | Emission clipping z | `emclip_z` | -1.0 | `--emclip-z` | -1 disables; masking only (does not force z) |
|  | Emission width (Å) | `emwidth` | 40.0 | `--emwidth` | |
| 4. Apodization | Apodize percent (%) | `apodize_percent` | 10.0 | `--apodize-percent` | Typical 5–15% |
| 5. Masks | Custom wavelength masks | `wavelength_masks` | None | `--wavelength-masks` | e.g. 6550:6600 7600:7700 |

### Automatic spike-masking controls (CLI)

The automatic step above corresponds to the CLI spike-masking options:

| Parameter | Default | CLI Flag | Notes |
|---|---:|---|---|
| `spike_masking` | `True` | `--no-spike-masking` to disable | Early spike/outlier masking before smoothing |
| `spike_floor_z` | `50.0` | `--spike-floor-z` | Minimum floor-relative robust z for spike detection |
| `spike_baseline_window` | `501` | `--spike-baseline-window` | Running median baseline window in pixels |
| `spike_baseline_width` | `None` | `--spike-baseline-width` | Baseline width in wavelength units; overrides pixel window |
| `spike_rel_edge_ratio` | `2.0` | `--spike-rel-edge-ratio` | Center residual must exceed neighboring residuals by this factor |
| `spike_min_separation` | `2` | `--spike-min-separation` | Minimum pixel separation between removed spikes |
| `spike_max_removals` | `None` | `--spike-max-removals` | Optional cap on spikes removed per spectrum |
| `spike_min_abs_resid` | `None` | `--spike-min-abs-resid` | Minimum absolute residual required to count as a spike |

### Best practices
- Inspect S/N before aggressive smoothing
- Prefer specific masks over broad ranges
- Keep `apodize_percent` modest to preserve edges

### CLI parity
GUI options map to `sage` flags:

```powershell
sage spectrum.dat --output-dir results\
sage spectrum.dat --savgol-window 11 --savgol-order 3
sage spectrum.dat --aband-remove --skyclip
sage spectrum.dat --emclip-z 0.02 --emwidth 40
# In batch, auto emission clipping uses per-row z when present
sage batch --list-csv list.csv --emclip --output-dir results\
sage spectrum.dat --wavelength-masks 6550:6600 7600:7700
```

## See Also

- [CLI Command Reference](../cli/command-reference.md) - All preprocessing CLI flags
- [Parameters Reference](../reference/parameters.md) - Complete parameter documentation
- [First Analysis Guide](../quickstart/first-analysis.md) - Step-by-step workflow

