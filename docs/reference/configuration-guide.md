# Configuration Guide

This guide lists the effective/default configuration values exposed by the current
SNID SAGE build and points to the current GUI workflows.

## Access

- GUI: the main SNID SAGE window has a `Settings` dialog, but not a separate
  `Configuration` panel
- User Templates Folder: `snid-sage-templates` → `Change User Folder`
- CLI: `sage config show|get`

## Categories (implemented)

- Analysis: redshift/age bounds, lapmin, metric threshold, wavelength tolerance, output limits
- Processing: smoothing, flattening, masks (A-band, skylines), apodization
- Display: theme, plot style/DPI, grid/markers
- Templates: paths.templates_dir
- LLM: enable, provider, model_name, api_key, max_tokens, temperature

## Examples

```powershell
sage config show
sage config get paths.templates_dir
sage config get analysis.lapmin
```

## Template Location Override

If you want to override where the managed built-in templates bank lives, set
the `SNID_SAGE_TEMPLATE_DIR` environment variable before running SNID SAGE.

```bash
export SNID_SAGE_TEMPLATE_DIR=/path/to/templates_root
```

```powershell
$env:SNID_SAGE_TEMPLATE_DIR = "C:\path\to\templates_root"
```

With this override:
- built-in templates are stored/read from `SNID_SAGE_TEMPLATE_DIR`
- the default User Templates folder becomes the sibling `user_templates` directory next to it
- example: `/path/to/templates_root` -> `/path/to/user_templates`

## State Root Override

If you want to override the resolved SNID SAGE state/config root, set
`SNID_SAGE_STATE_DIR` before running SNID SAGE.

This affects the base location used for state-managed paths such as the
resolved config directory and the default managed template location unless a
more specific override such as `SNID_SAGE_TEMPLATE_DIR` is also set.

```bash
export SNID_SAGE_STATE_DIR=/path/to/snid_sage_state
```

```powershell
$env:SNID_SAGE_STATE_DIR = "C:\path\to\snid_sage_state"
```

With this override:
- the resolved state/config root moves to `SNID_SAGE_STATE_DIR`
- managed paths derived from that root follow the new location
- `SNID_SAGE_TEMPLATE_DIR` still takes precedence for the built-in template bank if both are set

## Notes

- The User Templates Folder is managed separately by the Template Manager GUI
- Unlisted categories are experimental or not available in this release

 