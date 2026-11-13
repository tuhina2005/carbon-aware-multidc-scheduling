# hetero: heterogeneous DCs (processor mix + PUE)

> Carbon intensity: Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI) historical hourly data; dates 2024-01-17, 2024-07-17; start hours 6 UTC. Tiers: efficient (PE4–PE6, PUE 1.10), standard (all six types, PUE 1.55), legacy (PE1–PE3 + PE6, PUE 2.00). B6 = greenest DC by PUE × mean CI.

- **homogeneous**: all standard
- **aligned**: DC_Oslo=efficient, DC_Paris=efficient
- **opposed**: DC_Oslo=legacy, DC_Paris=legacy, DC_Warsaw=efficient, DC_California=efficient
- **mixed**: DC_Oslo=legacy, DC_California=efficient

## location metric, ε = 0.02 kWh/GB

| scenario    |   n |   vs B3 mean % |   vs B3 share ≥5 % |   vs B6 mean % |   vs B6 share ≥5 % |   vs B5 mean % |   vs A1 mean % |   vs A2 mean % |   Ours DC ≠ B3 DC |   Ours waits | Ours DCs                    |
|:------------|----:|---------------:|-------------------:|---------------:|-------------------:|---------------:|---------------:|---------------:|------------------:|-------------:|:----------------------------|
| homogeneous |  24 |          1.951 |              0.125 |          1.951 |              0.125 |          1.513 |          1.513 |          0.289 |             0.083 |        0.417 | OSL 18, PAR 6               |
| aligned     |  24 |          2.774 |              0.167 |          2.774 |              0.167 |          2.375 |          2.375 |          0.293 |             0.083 |        0.542 | OSL 18, PAR 6               |
| opposed     |  24 |          1.942 |              0.167 |          1.942 |              0.167 |          1.474 |          1.474 |          0.232 |             0.083 |        0.417 | OSL 15, PAR 5, CAL 3, FRA 1 |
| mixed       |  24 |          9.148 |              0.333 |          1.393 |              0.083 |          1.393 |          1.393 |          7.824 |             0.292 |        0.375 | PAR 14, OSL 10              |

## brown metric, ε = 0.02 kWh/GB

| scenario    |   n |   vs B3 mean % |   vs B3 share ≥5 % |   vs B6 mean % |   vs B6 share ≥5 % |   vs B5 mean % |   vs A1 mean % |   vs A2 mean % |   Ours DC ≠ B3 DC |   Ours waits | Ours DCs                    |
|:------------|----:|---------------:|-------------------:|---------------:|-------------------:|---------------:|---------------:|---------------:|------------------:|-------------:|:----------------------------|
| homogeneous |  24 |         34.159 |              0.542 |         34.159 |              0.542 |         33.215 |          3.333 |         32.231 |             0.542 |        0.125 | OSL 11, FRA 8, PAR 5        |
| aligned     |  24 |         35.995 |              0.542 |         35.995 |              0.542 |         34.847 |          5.105 |         32.862 |             0.542 |        0.167 | OSL 11, FRA 8, PAR 5        |
| opposed     |  24 |         32.165 |              0.522 |         32.165 |              0.522 |         31.724 |          2.984 |         30.015 |             0.458 |        0.167 | OSL 10, FRA 9, PAR 3, CAL 2 |
| mixed       |  24 |         44.836 |              0.625 |         35.53  |              0.542 |         33.419 |          3.418 |         43.055 |             0.667 |        0.167 | PAR 11, FRA 8, OSL 5        |

## Theory-guided rule vs full search (gain over B6)

Capture = Σ(base − rule) / Σ(base − Ours) over problems where Ours beats the base by > 0.1 %. Solver calls: rule ≤ 2 (R1) or ≤ 4 (R3), one of them the reference schedule; Ours = all grid points.

| metric   | rule   |   problems Ours beats base |   capture of Ours' gain |   rule vs B6 mean % |   Ours vs rule mean % |   Ours vs rule max % |   rule = Ours (share) |   Ours solver calls (mean) |
|:---------|:-------|---------------------------:|------------------------:|--------------------:|----------------------:|---------------------:|----------------------:|---------------------------:|
| location | R1     |                         39 |                   0.385 |               1.485 |                 0.538 |                9.271 |                 0.667 |                      65.25 |
| location | R3     |                         39 |                   0.551 |               1.579 |                 0.44  |                9.271 |                 0.76  |                      65.25 |
| brown    | R1     |                         53 |                   0.239 |               9.244 |                30.66  |              100     |                 0.49  |                      65.25 |
| brown    | R3     |                         53 |                   0.282 |              10.296 |                29.849 |              100     |                 0.552 |                      65.25 |
