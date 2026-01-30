## Results and Plots

Note: This page is a work in progress.

### After analysis

| Area | Contents |
|---|---|
| Summary | Type, best template, confidence, redshift, age |
| Dialogs | Cluster summary, subtype proportions, redshift–age |

### Plots

| Plot | Description |
|---|---|
| Comparison | Flux and flattened comparisons vs best match |
| Redshift–Age | Scatter/summary of redshift vs age |
| 3D clustering | Type-aware GMM visualization (if available) |

### Export

| Method | Notes |
|---|---|
| File → Export | Export from main window |
| Dialog Save/Export | Export from individual dialogs |
| Formats | PNG for quick sharing; PDF/SVG for publications |

### CLI outputs

| Mode | Files |
|---|---|
| Standard | `{name}.output`, `{name}.fluxed`, `{name}.flattened` |
| Complete | Adds plot files (`comparison`, `3d_gmm_clustering`, `redshift_age`, `cluster_subtypes`) |

```powershell
sage data\sn2003jo.dat --output-dir results\ --complete
```

## See Also

- [First Analysis](../quickstart/first-analysis.md) - Step-by-step workflow
- [CLI Command Reference](../cli/command-reference.md) - All output options
