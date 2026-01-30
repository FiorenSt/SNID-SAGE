# Installation Guide

This guide provides instructions for installing SNID SAGE on your system.

## Requirements

- **Python**: 3.8+ (3.10 recommended)
- **OS**: Windows, macOS, or Linux

## Quick Installation

```bash
pip install snid-sage
```

On first run, SNID SAGE downloads templates (~50 MB) into a `SNID-SAGE/templates` folder in your current directory. Once downloaded, templates are reused across runs.

### Virtual Environment Setup

#### Using venv (Recommended)

**Windows:**
```powershell
# Create virtual environment
python -m venv snid_env

# Activate environment
snid_env\Scripts\activate

# Install SNID SAGE
pip install snid-sage

# Verify installation
python -c "import snid_sage; print('SNID SAGE installed successfully!')"

# Deactivate when done
deactivate
```

**macOS/Linux:**
```bash
# Create virtual environment
python3 -m venv snid_env

# Activate environment
source snid_env/bin/activate

# Install SNID SAGE
pip install snid-sage

# Verify installation
python -c "import snid_sage; print('SNID SAGE installed successfully!')"

# Deactivate when done
deactivate
```

#### Using conda

```bash
# Create conda environment with Python 3.10
conda create -n snid_sage python=3.10

# Activate environment
conda activate snid_sage

# Install SNID SAGE
pip install snid-sage

# Verify installation
python -c "import snid_sage; print('SNID SAGE installed successfully!')"

# Deactivate when done
conda deactivate
```

### Alternative: Install from Source

If you need the latest development version or want to contribute:

```bash
# Clone repository
git clone https://github.com/FiorenSt/SNID-SAGE.git
cd SNID_SAGE

# Install in development mode (includes CLI and GUI)
pip install -e .
```

## Verification

### Test Installation
```bash
# Check version
sage --version

# Test CLI
sage --help

# Test GUI launch
snid-sage
```

### Check Dependencies
```bash
# Verify key dependencies
python -c "import numpy, matplotlib, scipy, astropy; print('Dependencies OK')"
```

## Platform-Specific Notes

### Windows
- **Python**: Use Python 3.9+ from python.org
- **Virtual Environment**: Recommended for dependency management
- **GUI**: PySide6-based interface with native Windows styling

### macOS
- **Python**: Use Python 3.9+ from python.org or Homebrew
- **Dependencies**: Some packages may require Xcode Command Line Tools
- **GUI**: Native macOS integration with PySide6

### Linux (Ubuntu/Debian)
```bash
# Install system dependencies
sudo apt update
sudo apt install python3-pip python3-venv

# Install SNID SAGE
pip3 install snid-sage
```

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Check Python version
python --version

# Reinstall with specific Python version
python3.9 -m pip install snid-sage
```

**GUI Not Launching**
```bash
# Check PySide6 installation
python -c "import PySide6; print('PySide6 OK')"

# Reinstall GUI dependencies
pip install --upgrade PySide6
```

**Template Library Issues**
```bash
# Check template installation
sage templates list

# Reinstall templates
pip install --upgrade snid-sage
```

**Windows: "Enterprise signing level requirements" / blocked snid-sage.exe**

If Windows Smart App Control (SAC) or WDAC blocks `snid-sage.exe`:
```powershell
# Option 1: Run the module directly (bypasses blocked exe)
python -m snid_sage.interfaces.gui.launcher

# Option 2: Reinstall the package
pip uninstall snid-sage
pip install snid-sage
```

To make `snid-sage` work permanently, add this to your PowerShell profile (`notepad $PROFILE`):
```powershell
function snid-sage { python -m snid_sage.interfaces.gui.launcher @args }
```

**Tip**: If using Microsoft Store Python, consider switching to [python.org](https://python.org) Python to avoid Store/policy issues.

### Error Messages

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError` | Install missing dependencies with `pip install package_name` |
| `ImportError: DLL load failed` | Update Visual C++ Redistributable (Windows) |
| `No module named 'PySide6'` | Install PySide6: `pip install PySide6` |
| `Permission denied` | Use virtual environment or `pip install --user` |
| `did not meet Enterprise signing level` | See "Windows: Enterprise signing" section above |

## Next Steps

1. **Test Installation**: Run `snid-sage` to launch the GUI
2. **Get Sample Data**: Download test spectra from TNS
3. **Read Documentation**: Start with the [First Analysis Guide](../quickstart/first-analysis.md)
4. **Configure AI**: Set up OpenRouter for AI features (optional)

## Support

- **Documentation**: [SNID SAGE Docs](https://fiorenst.github.io/SNID-SAGE/)
- **GitHub Issues**: Report bugs and request features
- **Community**: Join discussions on GitHub 