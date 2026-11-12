# Electricity Maps hourly carbon intensity

`experiments.py --ci-dir cwm_multidc/data/electricitymaps` reads one file per topology region:

| File | Electricity Maps zone | Data centre |
|---|---|---|
| `DE.csv` | `DE` | Frankfurt (source) |
| `NO.csv` | `NO-NO1` | Oslo |
| `FR.csv` | `FR` | Paris |
| `PL.csv` | `PL` | Warsaw |
| `US-CAL.csv` | `US-CAL-CISO` | California |
| `IN.csv` | `IN-WE` | Mumbai |

Format (as exported by the Electricity Maps data portal): one row per UTC hour, a
`Datetime (UTC)` column and a carbon-intensity column. The loader prefers
`Carbon Intensity gCO₂eq/kWh (LCA)` / `Carbon intensity gCO₂eq/kWh (Life cycle)` and
falls back to `(direct)`. Gaps, blank values and non-hourly steps are errors; nothing is
interpolated.

## Getting the files

Electricity Maps has no anonymous download. Either:

1. Sign in (free account) at <https://app.electricitymaps.com/datasets>, download the
   **hourly 2024** CSV for each zone above, then
   `python -m cwm_multidc.scripts.fetch_ci_data import ~/Downloads`
2. Or, with an API token that has historical access:
   `ELECTRICITYMAPS_API_KEY=... python -m cwm_multidc.scripts.fetch_ci_data api --year 2024`

Both validate every file (full year, consecutive hours, no blanks), rename it to
`<REGION>.csv` and write `MANIFEST.json` (zone, row count, mean, sha256, retrieval time).

Check the Electricity Maps dataset licence before redistributing these files with the paper
artefact; cite Electricity Maps as the source in the paper.
