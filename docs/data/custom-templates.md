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

1. Run `snid-sage-templates` to open the standalone Template Manager
2. Go to the **Create** tab
3. **Load spectrum** file (supports .dat, .txt, .csv, .fits)
4. **Fill metadata**:
   - Name, Type, Subtype
   - Age (days from max)
   - Redshift
5. **Preview** the processed template
6. **Save** to your User Templates folder

### Standalone launcher

```powershell
snid-sage-templates
```

Templates are currently created one spectrum or epoch at a time in `snid-sage-templates`.

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
