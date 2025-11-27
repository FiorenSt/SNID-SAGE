# Changelog

All notable changes to SNID SAGE will be documented in this file.

## [0.11.2] - 2025-11-27

- Templates and state layout:
  - Templates, config, and user templates are now stored under a project-local `SNID-SAGE` folder rooted at the directory where SNID SAGE is first run (e.g. `C:\path\to\project\SNID_SAGE\templates`), unless overridden with `SNID_SAGE_TEMPLATE_DIR` or `SNID_SAGE_STATE_DIR`.

## [0.11.1] - 2025-11-26

- Template lazy-loader and Template Manager fixes:
  - `snid-sage-templates` now always reads built-in templates (optical + ONIR) from the lazily-downloaded GitHub Release bank via the centralized `templates_manager`, rather than assuming `snid_sage/templates` is packaged.
  - Fixed ONIR index resolution to prefer the managed templates directory, so ONIR templates reliably appear in the Template Manager.
  - Introduced a default User Templates folder as a `User_templates` subdirectory next to the managed templates bank, and wired the GUI folder picker to recommend/adopt it by default while still allowing custom locations.
  - Improved diagnostics and error messages around template discovery and download, including guidance to use `snid-sage-download-templates` when no templates are found.

## [0.11.0] - 2025-11-26

- Templates distribution refactor:
  - Removed large `.hdf5` template banks from the `snid-sage` wheel to keep installs small.
  - Templates are now downloaded once on first use from a versioned GitHub Release archive (`templates-v0.11.0.zip`).
  - Templates are stored in a managed, user-writable directory (default: platform-specific user data dir; override with `SNID_SAGE_TEMPLATE_DIR`).
  - Added `snid-sage-download-templates` CLI to pre-download or refresh the template bank explicitly.
  - All CLI, GUI, and template-manager components now resolve templates via the centralized `templates_manager` instead of assuming `snid_sage/templates` is packaged.

## [0.10.0] - 2025-11-01

- Added ONIR profile option with extended optical+near-IR coverage
  - Redshift reach: up to z = 2.5 (optical profile reaches z = 1.0)
  - Designed for higher-z analyses where near-IR features are informative
- Added Templates GUI (`snid-sage-templates`)
  - Create and manage user templates that complement the default library
  - Streamlined import, inspection, and metadata handling for custom templates
- Added profile onir/optical swap in GUI
- Replaced all “standard error (SE)” reporting with unbiased weighted standard deviation (error)

## [0.9.1] - 2025-10-08

- Uncertainty: Corrected cluster redshift SE to use σ = √(Σ w² σ²) / Σ w with w = exp(√RLAP-CCC)/σ². This replaces the previous RMS-style propagation.

## [0.9.0] - 2025-10-07

- Clustering: Adopted weighted 1-D GMM as default for cosmological clustering.
  - Per-sample weights: w_i = (RLAP-CCC_i)^2 / σ_{z,i}^2
  - Weighted BIC model selection with resampling fallback if `sample_weight` is unsupported
  - Enforced contiguity plus hard gap splitting at Δz > 0.025; clusters are annotated with `segment_id`, `gap_split`, and point `indices`
- Uncertainty: Cluster redshift uncertainty uses balanced inverse-variance × quality weighting with RMS propagation
  - w_i = (RLAP-CCC_i)^2 / σ_{z,i}^2;  z = Σ(w_i z_i)/Σ(w_i);  σ_final = √(Σ w_i σ_i^2 / Σ w_i)
- Template correction: `LSQ12fhs` subtype updated from `Ia-pec` to `Ia-02cx` in index and HDF5

## [0.8.1] - 2025-10-03

- Weighting: use sqrt(RLAP) instead of RLAP directly in weighting formula


## [0.8.0] - 2025-09-20

- Improved plot graphics
- New display settings
- Batch: optimal parallel execution

## [0.7.5] - 2025-09-14

- Template metadata corrections: updated `sn2016cvk` subtype from IIP to IIn and `sn1998S` subtype from IIn to II-flash in both JSON index and HDF5 storage files.

## [0.7.4] - 2025-09-04

- Enhanced wavelength range validation requiring minimum 2000 Å overlap with optical grid (2500-10000 Å), with automatic clipping and improved error handling across CLI, GUI, and core preprocessing.
- CLI: Added list-based batch mode `--list-csv` that accepts a CSV with a path column and optional per-row redshift column. Per-row redshift is applied as a fixed redshift for that spectrum; relative paths are resolved relative to the CSV file. Summary report now includes a `zFixed` column.

## [0.7.3] - 2025-09-02

- Template corrections:
  - Fixed incorrect subtype classifications for several Type Ia templates:
    - `sn2005hk`: corrected from `Ia-pec` to `Ia-02cx`
    - `sn2008A`: corrected from `Ia-pec` to `Ia-02cx`
    - `sn2013gr`: corrected from `Ia-pec` to `Ia-02cx`
    - `sn2016ado`: corrected from `Ia-pec` to `Ia-02cx`
    - `sn2008ae`: corrected from `Ia-pec` to `Ia-02cx`
    - `ASASSN-15ga`: corrected from `Ia-pec` to `Ia-91bg`
    - `ASASSN-15hy`: corrected from `Ia-pec` to `Ia-03fg`


## [0.7.2] - 2025-09-01

- Bug fixes:
  - Fixed subtype display in CLI summary output when clustering fails and only 1-2 matches survive (weak match cases)

## [0.7.1] - 2025-09-01

- Bug fixes:
  - Fixed autoscaling issue in plot display within the advanced preprocessing interface
  - Fixed subtype fetching in batch summary when only a single match survives

## [0.7.0] - 2025-08-30

- New preprocessing: added Step 0 to automatically detect and correct obvious cosmic-ray hits before standard preprocessing.
- Batch mode plotting: fixed inconsistencies when only weak matches are found; summary lines and generated plots now reflect weak-match status consistently.

## [0.6.1] - 2025-08-20

- Bug fixes and improvements:
  - Improved error handling for template loading failures in .csv
  - Fixed ejecta shifting

## [0.6.0] - 2025-08-19

- BREAKING: CLI renamed `snid` → `sage`; GUI utilities → `snid-sage-lines` / `snid-sage-templates`. Docs and entry points updated. Migration: replace `snid` with `sage`; main `snid-sage` unchanged.

- Analysis and messaging improvements:
  - Distinguish “weak match” vs “no matches” in GUI/CLI; cluster “no valid clusters” logs downgraded to INFO.
  - GUI: clearer status and dialogs for weak/no-match; added suggestion to reduce overlap threshold (`lapmin`).
  - CLI: “No good matches” suggestions now include lowering `lapmin`.
  - Batch CLI: adds “(weak)” marker in per-spectrum lines and suppresses cluster warnings.

- Clustering/logging:
  - More precise INFO messages for “no matches above RLAP-CCC” and “no types for clustering”.
