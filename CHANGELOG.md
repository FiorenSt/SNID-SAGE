# Changelog

All notable changes to SNID SAGE will be documented in this file.

## [1.1.1] - 2026-01-16

### Analysis Improvements

- Cosmological clustering: tightened the 1-D GMM post-processing hard gap split threshold from Δz > 0.025 to Δz > 0.01 (still scaled by (1+z))

### GUI

- Space Debris mini-game: `pygame` dependency removed; game is now implemented in Qt/PySide6

### Templates

- Removed the built-in template `sn2017ben` ("2017ben") from the official optical and ONIR template banks (wrong redshift)
- Template metadata correction: reclassified `LSQ15adm` from **Ia/Ia-pec** to **Ia/Ia-csm** in optical and ONIR template banks
- Added 13 templates to the official default optical template banks:
  - Ia: `PTF11kx`, `2020qxz`, `2010ae`, `2012Z`, `PTF09dav`, `1999aa`
  - SLSN: `2017egm`, `2016eay`, `2018jkq`, `2023gpw`
  - Ibn: `2010al`, `2011hw`
  - GAP (LRN): `AT2015dl`
- Added 4 new Type Ib **Ib-Ca-rich** templates to the optical template banks: `PTF11kmb`, `PTF12bho`, `2016hgs`, `2005E`

## [1.1.0] - 2026-01-09

### Analysis Improvements

- Changed CCC (concordance correlation coefficient) trim percentile from 99.5% to 99.0% for improved match quality discrimination

### Templates

- Templates download location now persists across working directories via per-user pointer file; templates are reused when `snid-sage` is launched from different folders (override with `SNID_SAGE_TEMPLATE_DIR`)
- User Templates selection persisted in per-user config location (no longer depends on working directory); defaults to sibling of templates bank (`.../templates` → `.../user_templates`)
- Template metadata correction: reclassified `sn2016drl` from **II/IIn** to **II/IIP** in optical and ONIR template banks


## [1.0.0] - 2026-01-06

### 🎉 First Stable Release

This release marks the first stable production version of SNID SAGE, representing a mature, feature-complete tool for supernova spectral analysis.

### Major Features

- **New composite metric: HσLAP-CCC (BREAKING CHANGE)**
  - Introduced HσLAP-CCC = (height × lap × CCC) / sqrt(sigma_z) as the primary match quality metric
  - Replaces the previous RLAP-CCC metric with improved statistical rigor
  - Includes trimmed concordance correlation coefficient (CCC) with 99.5% trimming to reduce domination by extreme peaks
  - Provides better discrimination of match quality through sigma_z normalization
  - Weighting policy updated: w_i = (HσLAP-CCC_i)^2 for clustering and aggregation
  - Automatic fallback to HLAP when sigma_z is unavailable
  - All analysis outputs, clustering, and quality assessments now use HσLAP-CCC as the primary metric

- **Enhanced uncertainty estimation**
  - Replaced all "standard error (SE)" reporting with unbiased weighted standard deviation
  - Improved cluster redshift uncertainty calculations using balanced inverse-variance weighting
  - More statistically rigorous error propagation throughout the analysis pipeline

- **Template library version 2.0**
  - 603 optical templates covering all major supernova types and subtypes
  - 467 ONIR (optical+near-IR) templates for extended redshift reach (up to z = 2.5)
  - Comprehensive coverage including Ia, Ib, Ic, Ibn, Icn, II, SLSN, LFBOT, TDE, KN, GAP, AGN, Galaxy, Star, and CV types
  - All templates rebinned to standardized logarithmic wavelength grids

### Templates

- Added three new GAP optical templates:
  - `2008S` and `2008jd` as **GAP ILRT**
  - `2021biy` as **GAP LRN**
- Added three new Type II flash optical templates:
  - `sn2023ixfEarly`, `sn2020pniEarly`, and `sn2024ggiEarly` as **II-flash**
- Template metadata corrections applied across multiple subtypes

### Infrastructure

- **Template distribution system**
  - Templates distributed via versioned GitHub Release archives for efficient installation
  - Lazy download on first use with `snid-sage-download-templates` CLI for pre-download
  - Centralized template management via `templates_manager` module
  - Platform-appropriate storage locations with environment variable overrides

- **Template Manager GUI**
  - Full-featured GUI (`snid-sage-templates`) for creating and managing user templates
  - Streamlined import, inspection, and metadata handling
  - Support for both optical and ONIR profiles

- **ONIR profile support**
  - Extended optical+near-IR coverage for higher redshift analyses
  - Redshift reach: up to z = 2.5 (vs. z = 1.0 for optical profile)
  - Profile switching available in GUI

### Analysis Improvements

- **Clustering enhancements**
  - Unweighted 1-D GMM as default for cosmological clustering (weighted GMM available via `--weighted-gmm` flag or `SNID_SAGE_WEIGHTED_GMM` environment variable)
  - Elbow method for GMM model selection as default (BIC available via `SNID_SAGE_GMM_MODEL_SELECTION` environment variable)
  - Enforced contiguity plus hard gap splitting at Δz > 0.025
  - Comprehensive cluster quality assessment and categorization

- **Preprocessing**
  - Automatic cosmic-ray detection and correction (Step 0)
  - Enhanced wavelength range validation (minimum 2000 Å overlap)
  - Improved error handling across CLI, GUI, and core preprocessing

- **Batch processing**
  - Optimal parallel execution with configurable worker count
  - CSV-based batch mode with per-row redshift support
  - Comprehensive summary reports with quality metrics

### Bug Fixes & Improvements

- Fixed template metadata corrections across multiple subtypes
- Improved handling of weak matches and edge cases
- Enhanced error messages and diagnostics
- Better distinction between "weak match" vs "no matches" scenarios
- Improved plot graphics and display settings
- Fixed various subtype display issues in CLI and GUI

### Documentation

- Complete documentation available at https://fiorenst.github.io/SNID-SAGE/
- Comprehensive guides for first analysis, GUI usage, CLI reference, and AI integration
- Troubleshooting guides and API documentation

## [0.11.4] - 2025-11-28

- **Templates**
  - Added three new GAP optical templates to the default library:
    - `2008S` and `2008jd` as **GAP ILRT**.
    - `2021biy` as **GAP LRN**.
  - Added three new Type II flash optical templates to the default library:
    - `sn2023ixfEarly`, `sn2020pniEarly`, and `sn2024ggiEarly` as **II-flash**.
- **Template folders**
  - Simplified and unified how the default `user_templates` folder is created for both `.dev` checkouts and `pip install` installs, using a managed `user_templates` sibling next to the active templates bank.

## [0.11.3] - 2025-11-27

- Template Manager (`snid-sage-templates`):
  - Fixed default templates resolution after fresh `pip install` so that storage files are loaded from the centralized, lazily-downloaded templates bank (via `templates_manager`) instead of relying on legacy packaged paths.

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
