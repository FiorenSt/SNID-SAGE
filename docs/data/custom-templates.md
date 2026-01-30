# Custom Templates

Add your own spectra to the template library for classification.

## Requirements

### Data Quality

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Signal-to-Noise | S/N ≥ 10 | S/N ≥ 20 |
| Wavelength Coverage | 70% of 3500–9000 Å | 90% |
| Spectral Resolution | R ≥ 500 | R ≥ 1000 |

### Metadata

Required fields:
- **Name**: Object designation (e.g., "SN2024abc")
- **Type**: Main classification (Ia, Ib, Ic, II, SLSN, etc.)
- **Subtype**: Detailed classification (norm, 91bg, IIP, etc.)
- **Age**: Days from maximum light
- **Redshift**: Host redshift

## Creating Templates

### GUI Method

1. **Open Template Manager** (Tools → Template Manager)
2. Go to the **Create** tab
3. **Load spectrum** file (supports .dat, .txt, .csv, .fits)
4. **Fill metadata**:
   - Name, Type, Subtype
   - Age (days from max)
   - Redshift
5. **Preview** the processed template
6. **Save** to your User Templates folder

### CLI Method

```powershell
# Single template
sage templates import-csv data\spectrum.csv --dest User_templates\ `
  --name-column object_name --path-column spectrum_file_path `
  --type-column type --subtype-column subtype `
  --age-column age --redshift-column redshift
```

## Batch Import

Import many templates at once from a CSV/TSV file.

### CSV Format

| object_name | spectrum_file_path | type | subtype | age | redshift |
|-------------|-------------------|------|---------|-----|----------|
| SN2024abc | spectra/sn2024abc_day5.dat | Ia | norm | 5.0 | 0.023 |
| SN2024abc | spectra/sn2024abc_day10.dat | Ia | norm | 10.0 | 0.023 |
| SN2024def | spectra/sn2024def.dat | II | IIP | 15.0 | 0.015 |

- Multiple rows with the same `object_name` create a **multi-epoch template**
- Paths can be relative to the CSV file location
- Column names are case-insensitive

### GUI Batch Import

1. Template Manager → **Manage** tab
2. Click **Batch Import**
3. Select your CSV file
4. Choose destination folder
5. Review and confirm

### CLI Batch Import

```powershell
sage templates import-csv data\my_templates.csv `
  --dest C:\User_templates `
  --name-column object_name `
  --path-column spectrum_file_path `
  --type-column type `
  --subtype-column subtype `
  --age-column age `
  --redshift-column redshift
```

## File Formats

Supported spectrum formats:
- `.dat`, `.txt`, `.ascii` - Whitespace-separated (wavelength, flux)
- `.csv` - Comma-separated with optional headers
- `.fits` - Standard FITS format

Wavelength must be in Angstroms. Flux units are normalized internally.

## User Templates Location

Templates you create are stored in your **User Templates folder**:

```
User_templates/
├── template_index.user.json    # Your template index
├── templates_Ia.user.hdf5      # Your Type Ia templates
├── templates_II.user.hdf5      # Your Type II templates
└── ...
```

Set or change this folder:
- Template Manager → left panel → **Change User Folder**
- Settings → Paths → User Templates Directory

## Override Behavior

When you have a user HDF5 for a type (e.g., `templates_Ia.user.hdf5`), it **replaces** the built-in templates for that type during analysis. This ensures your custom templates are used.

## Best Practices

- **Use high S/N spectra** - Better templates give better classifications
- **Accurate metadata** - Correct type, subtype, and age are essential
- **Complete wavelength coverage** - Gaps reduce correlation quality
- **Multiple epochs** - Time series improve age constraints
- **Version control** - Keep your User Templates folder backed up

## See Also

- [Template Library](template-library.md) - Built-in template bank
- [Templates Manager (GUI)](../gui/templates-manager.md) - GUI details
- [Supported Formats](../reference/supported-formats.md) - Input file formats
