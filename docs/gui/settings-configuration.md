## Settings (GUI)

The main GUI `Settings` dialog currently covers GUI preferences only. It is not
a full configuration panel, and the main GUI does not expose a separate
`Settings -> Configuration` view.

### Display
- UI Scale (`ui_scale_percent`)
- Remember window position (present in the dialog; behavior may vary by build)

### Profile
- Active processing profile (`optical` or `onir`)

### Notes
- The User Templates Folder is managed in `snid-sage-templates` via `Change User Folder`
- Analysis parameters are configured from the analysis workflow/dialog, not from the main GUI `Settings` dialog
- `sage config` is inspection-only in this build; see the [Configuration Guide](../reference/configuration-guide.md) for the currently exposed CLI values

## See Also

- [Configuration Guide](../reference/configuration-guide.md) - Full settings reference
- [Parameters Reference](../reference/parameters.md) - Analysis parameter details
