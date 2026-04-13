# Supported File Formats

SNID SAGE supports a variety of spectrum file formats for analysis. This guide covers all supported formats and their requirements.

## Overview

SNID SAGE can load spectra from the following file types:

- **FITS files** (.fits, .fit)
- **ASCII/Text files** (.txt, .dat, .ascii, .asci, .csv, .flm)
- **Various delimited formats** (comma, tab, space-separated)

## FITS Files

### Supported Extensions
- `.fits` - Standard FITS format
- `.fit` - Alternative FITS extension

### Requirements
- FITS support is available in normal `snid-sage` installs because `astropy` is already included as a package dependency
- Automatically detected by file extension

### Format Details
- Supports both 1D and 2D data arrays
- Automatically extracts wavelength information from FITS headers when available
- Falls back to pixel-based wavelength axis if header information is insufficient
- Handles multiple extensions and bands

### Example Usage
```powershell
# Load FITS spectrum
sage spectrum.fits --output-dir results/
```

## ASCII/Text Files

### Supported Extensions
- `.dat` - Common data format
- `.txt` - Text files
- `.ascii` - ASCII format
- `.asci` - Alternative ASCII extension
- `.csv` - Comma-separated values
- `.flm` - FLM format (text-based)

### Format Details
- **Automatic header detection**: Recognizes common header keywords
- **Flexible delimiters**: Supports space, tab, comma, and semicolon separators
- **Column detection**: Automatically identifies wavelength and flux columns
- **Error handling**: Graceful fallback for various text formats

### Expected Data Structure
```
# Optional header line (auto-detected)
# Wavelength  Flux
4000.0       1.234
4001.0       1.245
...
```

### Header Keywords
The loader recognizes these header keywords:
- **Wavelength**: `WAVE`, `WAVELENGTH`, `LAMBDA`, `LAM`, `WL`, `ANGSTROM`, `ANG`
- **Flux**: `FLUX`, `FNU`, `FLAM`, `COUNTS`, `SPEC`, `SPECTRUM`, `INTENSITY`

### Example Usage
```powershell
# Load ASCII spectrum
sage spectrum.dat --output-dir results/

# Load CSV file
sage spectrum.csv --output-dir results/

# Load FLM file
sage spectrum.flm --output-dir results/
```

## Data Format Requirements

### Minimum Requirements
- **Two columns minimum**: Wavelength and flux
- **Numeric data**: All values must be numeric
- **Consistent format**: Same number of columns per row

### Optional Features
- **Header information**: Descriptive header lines
- **Comments**: Lines starting with `#` are ignored

### Supported Delimiters
- **Whitespace**: Space or tab separation (default)
- **Comma**: CSV format
- **Semicolon**: Alternative delimiter
- **Mixed**: Automatic detection

## File Format Detection

SNID SAGE automatically detects file formats based on:

1. **File extension**: Primary method for format identification
2. **File content**: Fallback analysis for unknown extensions
3. **Header analysis**: Intelligent header detection for text files

### Detection Process
```
1. Check file extension
2. For FITS: Use astropy for loading
3. For text: Analyze first few lines
4. Detect headers and delimiters
5. Validate data structure
6. Load with appropriate parser
```

## Troubleshooting

### Common Issues

**"Invalid spectrum format" error**
- Check file extension is supported
- Verify file contains numeric data
- Ensure consistent column structure

**"File not found" error**
- Verify file path is correct
- Check file permissions
- Ensure file exists

**"Failed to load spectrum" error**
- Check for corrupted files
- Verify data format consistency
- Try preprocessing the file

### Format Validation

Use these commands to check your file format:

```powershell
# View first few lines
Get-Content spectrum.dat -Head 10

# Count lines
(Get-Content spectrum.dat).Count

# Count comment lines
(Get-Content spectrum.dat | Where-Object { $_ -match "^#" }).Count
```

### Converting Unsupported Formats

If your file format isn't supported, convert it to a supported format:

```python
import numpy as np

# Load your data
data = np.loadtxt('your_file.txt', comments='#')

# Save in supported format
np.savetxt('spectrum.dat', data, fmt='%.6f %.6e')
```

## Best Practices

### Recommended Formats
- **For new data**: Use `.dat` or `.fits` formats
- **For sharing**: FITS format provides best metadata support
- **For simple data**: ASCII `.dat` format is most compatible

### Data Quality
- **Clean data**: Remove non-numeric lines
- **Consistent units**: Ensure wavelength in Angstroms
- **Metadata**: Add descriptive headers

### File Organization
- **Descriptive names**: Use meaningful filenames
- **Consistent structure**: Same format across related files
- **Backup copies**: Keep original files safe
- **Documentation**: Note any special formatting

## Advanced Features

### Custom Loading
For advanced users, SNID SAGE provides programmatic access to the spectrum loader:

```python
from snid_sage.shared.utils.data_io.spectrum_loader import load_spectrum

# Load with custom parameters
wavelength, flux = load_spectrum('spectrum.dat', skiprows=2)
```

### Format Extensions
The modular design allows for easy addition of new formats. See the development guide for extending format support.
