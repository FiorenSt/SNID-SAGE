## Results and Plots

### After analysis

| Area | Contents |
|---|---|
| Summary | Type, best template, confidence, redshift, age |
| Dialogs | Cluster summary, subtype proportions, redshift–age |

### Plots

| Plot | Description |
|---|---|
| Flux / Flattened comparison | Flux and flattened comparisons vs the best-match template |
| Redshift–Age | Scatter/summary of redshift vs age |
| 3D clustering | Type-aware GMM visualization (if available) |

### Export

| Method | Notes |
|---|---|
| Dialog Save/Export | Export from individual dialogs and plot windows |
| Formats | PNG for quick sharing; PDF/SVG for publications |

### CLI outputs

| Mode | Files |
|---|---|
| Standard | `{name}.output` |
| Complete | Adds `{name}.fluxed`, `{name}.flattened`, plus plots such as `{name}_flux_spectrum.png`, `{name}_flattened_spectrum.png`, `{name}_3d_gmm_clustering.png`, `{name}_redshift_age.png`, and `{name}_cluster_subtypes.png` |

```powershell
sage data\SN2018bif.csv --output-dir results\ --complete
```

## See Also

- [First Analysis](../quickstart/first-analysis.md) - Step-by-step workflow
- [CLI Command Reference](../cli/command-reference.md) - All output options
