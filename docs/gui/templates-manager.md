## Templates Manager

Interactive manager for exploring, creating, and organizing templates.

For step-by-step workflows and expanded CLI usage, see the [CLI Reference](../cli/command-reference.md).

### Overview

| Area | Contents |
|---|---|
| Left | Template browser (search, type filter) |
| Right | Tabs for Viewer, Create, Manage, Compare, Statistics |
| Status bar | Template count |

### Data source and overrides
- The browser lists templates using a merged index:
  - Base index: the managed built-in bank (lazy-downloaded on first use)
  - User index: `<User Templates Folder>/template_index.user.json`
- The `"version"` field inside `template_index*.json` describes the **index format**, not the bank contents version.
- If a per-type user HDF5 exists (e.g., `<User Templates Folder>/templates_Ia.user.hdf5`), entries for that type come exclusively from the user file; base entries for the same type are hidden. This prevents duplicates in the UI and reflects user edits immediately.

### User Templates folder (prompt-once + remember)
- On first use, the Template Manager shows a small banner asking you to set the **User Templates Folder**.
- You can:
  - Choose any directory (recommended to keep it under your documents/workspace)
  - Adopt an existing folder discovered from previous versions
- By default, if you do not choose a custom folder, SNID SAGE uses the managed
  sibling `user_templates` directory next to the built-in templates bank.
- If you want to override the built-in templates bank location from the terminal,
  set `SNID_SAGE_TEMPLATE_DIR` before running SNID SAGE; the default User
  Templates folder will then follow that location as a sibling directory.
- The chosen folder is remembered by the Template Manager workflow.
- You can change it later via:
  - Left panel: "Change User Folder"
  - The banner (when visible)

### Tasks
- Browse and preview templates with metadata
- Create templates from spectra (wizard)
- Edit metadata and reorganize
- Compare templates and generate statistics

### Batch Import Templates

Use the Manage Templates tab and click "Batch Import…" to create many templates at once.

Input file: CSV/TSV with columns (case-insensitive):
- object_name, spectrum_file_path, age, redshift, type, subtype, sim_flag

Notes:
- Relative paths are resolved relative to the CSV file location.
- Multiple rows with the same object_name create a single multi-epoch template.
- Choose a destination templates folder or use your configured User Templates folder.
- An error report file is written next to the CSV if any rows fail.

### Tips
- Use type filters to speed navigation
- Keep metadata complete for research reuse

### Related CLI
See `sage templates` subcommands for scripting the same operations.

