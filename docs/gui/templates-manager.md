## Templates GUI

Note: This page is a work in progress.

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
- If a per-type user HDF5 exists (e.g., `<User Templates Folder>/templates_Ia.user.hdf5`), entries for that type come exclusively from the user file; base entries for the same type are hidden. This prevents duplicates in the UI and reflects user edits immediately.

### User Templates folder (prompt-once + remember)
- On first use, the Template Manager shows a small banner asking you to set the **User Templates Folder**.
- You can:
  - Choose any directory (recommended to keep it under your documents/workspace)
  - Adopt an existing folder discovered from previous versions
- The chosen folder is remembered in configuration (`paths.user_templates_dir`).
- You can change it later via:
  - Left panel: "Change User Folder"
  - The banner (when visible)
  - Settings → Configuration → Paths → User Templates Directory

### Tasks
- Browse and preview templates with metadata
- Create templates from spectra (wizard)
- Edit metadata and reorganize
- Compare templates and generate statistics

### Tips
- Use type filters to speed navigation
- Keep metadata complete for research reuse

### Related CLI
See `sage templates` subcommands for scripting the same operations.

