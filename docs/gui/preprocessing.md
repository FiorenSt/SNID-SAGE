## Preprocessing (GUI)

Note: This page is a work in progress.

How to prepare spectra before analysis.

### Step 0: Cosmic-ray cleanup (new in 0.7.0)
- Automatically detects and corrects obvious cosmic-ray hits prior to standard preprocessing.
- Enabled by default in quick preprocessing; can be toggled in the manual wizard.
- Keeps genuine narrow features by limiting width and amplitude thresholds.

### Quick SNID Preprocessing

| Purpose | Actions | When to use |
|---|---|---|
| Minimal steps to prepare a spectrum for SNID | Log rebinning, optional S-G smoothing, apodization, continuum handling | Most cases; fastest path to classification |

### Manual Preprocessing

Open via: Preprocessing → Manual wizard

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

### Best practices
- Inspect S/N before aggressive smoothing
- Prefer specific masks over broad ranges
- Keep `apodize_percent` modest to preserve edges

### CLI parity
GUI options map to `sage` flags:

```bash
sage spectrum.dat --output-dir results/ ; \
  sage spectrum.dat --savgol-window 11 --savgol-order 3 ; \
  sage spectrum.dat --aband-remove --skyclip ; \
  sage spectrum.dat --emclip-z 0.02 --emwidth 40 ; \
  # In batch, auto emission clipping uses per-row z when present
  sage batch --list-csv list.csv --emclip --output-dir results/ ; \
  sage spectrum.dat --wavelength-masks 6550:6600 7600:7700
```

