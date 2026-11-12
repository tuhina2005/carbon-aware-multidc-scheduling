# Public hourly carbon intensity, 2024 (no account needed)

Built by `python -m cwm_multidc.scripts.fetch_public_ci --year 2024`; used with
`experiments.py --ci-dir cwm_multidc/data/public_ci`. `MANIFEST.json` records the method,
emission factors, sources, retrieval time, fuel shares, interpolated hours and file hashes.

| File | Source | Area | 2024 mean (gCO₂eq/kWh) |
|---|---|---|---|
| `DE.csv` | Energy-Charts (Fraunhofer ISE; ENTSO-E data, CC BY 4.0) | Germany | 320 |
| `NO.csv` | Energy-Charts | Norway (national; no NO1 series in the API) | 30 |
| `FR.csv` | Energy-Charts | France | 36 |
| `PL.csv` | Energy-Charts | Poland | 560 |
| `US-CAL.csv` | CAISO daily fuel-source files | CAISO balancing area | 196 |

India (DC_Mumbai) is not covered: no free hourly fuel-mix source was found for the Western
grid, so the experiments run with five DCs when this directory is used.

**Method.** Production-based life-cycle intensity: CI_h = Σ_f G_f,h · EF_f / Σ_f G_f,h, with G the
mean MW of each fuel over the UTC hour. Storage (pumped hydro, batteries), imports/exports and
load are excluded. EF = IPCC AR5 WG3 Annex III life-cycle medians (coal 820, gas 490, biomass 230,
solar 45, geothermal 38, hydro 24, nuclear 12, wind 11), oil 650 and other/waste 700 as in
Electricity Maps' defaults.

**Differences from Electricity Maps.** No cross-border flow tracing, so a region's figure is its
domestic generation mix; CAISO imports ~20–30 % of its energy, so its value is the in-state mix.

**Gaps.** Runs of up to 12 missing hours are linearly interpolated and flagged in the
`Interpolated` column; longer gaps abort the build. In 2024 only CAISO has gaps (16 hours: an
incomplete 11 Jan file, a few single hours, and the repeated hour of the November DST change).
