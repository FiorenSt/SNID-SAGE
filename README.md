# SNID SAGE - Advanced Supernova Spectral Analysis

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

<img src="docs/images/5.MatchTemplateFlux.png" alt="Match Template Flux" style="border: 2px solid #333; border-radius: 4px;">

**SNID SAGE** (SuperNova IDentification – Spectral Analysis and Guided Exploration) is your go-to tool for analyzing supernova spectra. It combines an intuitive PySide6/Qt graphical interface with the original SNID (Blondin & Tonry 2007) cross-correlation techniques, enhanced with modern clustering for classification choice, high-performance plotting via `pyqtgraph`, and LLM-powered analysis summaries and interactive chat assistance.



## Quick Installation

### Install from PyPI (Recommended)

```bash
pip install snid-sage
```

Python support: 3.10–3.13 (3.14 not yet supported due to dependency wheels).

This installs both the CLI and the full GUI stack by default, as defined in `pyproject.toml`.

### Using a virtual environment (recommended)

```bash
# Create virtual environment
python -m venv snid_env

# Activate environment
# Windows:
snid_env\Scripts\activate
# macOS/Linux:
source snid_env/bin/activate

# Install
pip install snid-sage
```

### Development installation

```bash
git clone https://github.com/FiorenSt/SNID-SAGE.git
cd SNID-SAGE
pip install -e .
```

Note: For user installs, you can use `pip install --user` to avoid system-wide changes.

## Getting Started

### Launch the GUI
```bash
snid-sage
```

### Use the CLI
```bash
# Single spectrum analysis (templates auto-discovered). Saves the summary (.output) by default
sage data/SN2018bif.csv -o results/

# Batch processing (default saves per-object summary plus standard batch outputs)
sage batch "data/*.dat" -o results/

# Batch from a CSV list with per-row redshift (if provided)
sage batch --list-csv "data/spectra_list.csv" -o results/
```

## Documentation & Support

- **[Complete Documentation](https://fiorenst.github.io/SNID-SAGE/)**
- **[First Analysis Guide](https://fiorenst.github.io/SNID-SAGE/quickstart/first-analysis/)**
- **[GUI Manual](https://fiorenst.github.io/SNID-SAGE/gui/interface-overview/)**
- **[CLI Reference](https://fiorenst.github.io/SNID-SAGE/cli/command-reference/)**
- **[AI Integration](https://fiorenst.github.io/SNID-SAGE/ai/overview/)**
- **[Troubleshooting](https://fiorenst.github.io/SNID-SAGE/reference/troubleshooting/)**

## Supported Data Formats

- FITS files (.fits, .fit)
- ASCII tables (.dat, .txt, .ascii, .asci, .csv, .flm)
- Space-separated values with flexible column detection
- Flexible text/FITS loading with automatic format detection

## Research & Citation

If you use SNID SAGE in your research, please cite the SNID-SAGE paper:

- Stoppa, F. and Smartt, S. J., *SNID-SAGE: A Modern Framework for Interactive Supernova Classification and Spectral Analysis* ([arXiv:2603.28741](https://arxiv.org/abs/2603.28741))

For the current arXiv version, the official BibTeX entry is:

```bibtex
@misc{stoppa2026,
  title={SNID-SAGE: A Modern Framework for Interactive Supernova Classification and Spectral Analysis},
  author={Fiorenzo Stoppa and Stephen J. Smartt},
  year={2026},
  eprint={2603.28741},
  archivePrefix={arXiv},
  primaryClass={astro-ph.IM},
  url={https://arxiv.org/abs/2603.28741}
}
```

## Community & Support

- **[Report Bug](https://github.com/FiorenSt/SNID-SAGE/issues)**
- **[Request Feature](https://github.com/FiorenSt/SNID-SAGE/issues)**
- **[Discussions](https://github.com/FiorenSt/SNID-SAGE/discussions)**
- **[Email Support](mailto:fiorenzo.stoppa@physics.ox.ac.uk)**

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Made with care for the astronomical community**

[Documentation](https://fiorenst.github.io/SNID-SAGE/) • [Report Bug](https://github.com/FiorenSt/SNID-SAGE/issues) • [Request Feature](https://github.com/FiorenSt/SNID-SAGE/issues) • [Discussions](https://github.com/FiorenSt/SNID-SAGE/discussions)

</div>
