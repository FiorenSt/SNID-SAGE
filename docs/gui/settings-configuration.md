## Settings (GUI)

Centralized settings used by GUI and CLI. Saved in the user config. For the full list of keys and details, see the [Configuration Guide](../reference/configuration-guide.md).

### Paths
- Templates Directory (`paths.templates_dir`)
- Output Directory (`paths.output_dir`)
- Data Directory (`paths.data_dir`)
- User Templates Directory (`paths.user_templates_dir`)

Notes:
- The User Templates Directory is set the first time you create/manage user templates via a prompt in the Template Manager.
- You can change it here at any time; the Template Manager will use this location immediately.

### Analysis
- Redshift/age bounds; thresholds (rlapmin, lapmin, fraction_coverage)
- Output limits; emission clipping (emclip, emclip_z, emwidth)

### Processing
- Flattening/smoothing/median filters; A-band removal; skyline clipping; apodization

### Display
- Theme (light/dark), plot style, DPI, grid/markers

### LLM
- Enable, provider, model, API key, tokens, temperature

### Profiles
- Save, load, and delete named profiles

 

