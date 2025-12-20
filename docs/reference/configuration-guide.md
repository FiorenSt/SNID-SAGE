# Configuration Guide

This guide lists implemented configuration options and how to access them via GUI and CLI.

## Access

- GUI: Settings → Configuration
- CLI: `sage config show|get|set|reset`

## Categories (implemented)

- Analysis: redshift/age bounds, hlapmin, lapmin, wavelength tolerance, output limits
- Processing: smoothing, flattening, masks (A-band, skylines), apodization
- Display: theme, plot style/DPI, grid/markers
- Templates: paths.templates_dir
- User Templates: paths.user_templates_dir
- LLM: enable, provider, model_name, api_key, max_tokens, temperature

## Examples

```powershell
sage config show
sage config set paths.user_templates_dir C:\\Users\\<you>\\Documents\\SNID_SAGE\\User_Templates
sage config set paths.templates_dir C:\\data\\snid_templates
sage config get analysis.hlapmin; sage config set analysis.hlapmin 0.2
```

## Notes

- Settings are stored in a user config file; manual edits are rarely needed
- Unlisted categories are experimental or not available in this release

 