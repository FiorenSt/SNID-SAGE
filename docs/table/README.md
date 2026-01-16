## SNID-SAGE WISEREP Results Viewer (local-only)

This is a **static** browser viewer under `docs/table/` intended for **local testing**.
It is **not deployed** (GitHub Pages should remain disabled while results are private).

### 1) Generate the dataset

From the repo root:

```bash
python -m snid_sage.tools.wiserep_web_table_export --results WISEREP_RESULTS/batch_results_WISEREP.csv --wiserep-dir WISEREP_RESULTS --out-dir docs/table/data
```

Notes:
- If you don’t pass `--spectra`, the exporter auto-picks the latest `WISEREP_RESULTS/spectra_*.csv`.
- Use `--limit 2000` for faster iteration if the full dataset is large.

### 2) Run locally

```bash
cd docs/table
python -m http.server 8000
```

Open `http://localhost:8000`.

### 3) Privacy

Do **not** enable GitHub Pages while the generated `docs/table/data/*.json` contains private results.
