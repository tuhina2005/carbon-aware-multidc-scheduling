# sources: where the data originates (W3)

> Carbon intensity: Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI) historical hourly data; dates 2024-01-17, 2024-07-17; start hours 0/6/12/18 UTC; all DCs are candidates. Predictions fixed before running (Prop. 3; median 24 h CI amplitude 2024: PL 88, US-CAL 75, DE 72 g, i.e. 0.15 / 0.33 / 0.20 of the mean WAN-path CI): **H3a** absolute carbon saved by waiting (A1 − Ours) is largest from Warsaw; **H3b** the relative value of waiting (gain vs A1) ranks California > Frankfurt > Warsaw.

## location metric, ε = 0.02 kWh/GB

| source     |   n |   value of waiting vs A1 mean % |   saved by waiting (A1 − Ours) kg mean |   Ours vs B3 mean % |   Ours vs B1 (local) mean % |   Ours waits |   R3 vs B3 mean % | Ours DCs       |
|:-----------|----:|--------------------------------:|---------------------------------------:|--------------------:|----------------------------:|-------------:|------------------:|:---------------|
| Frankfurt  |  64 |                           1.573 |                                  0.076 |               1.719 |                      84.318 |        0.453 |             1.335 | OSL 56, PAR 8  |
| Warsaw     |  64 |                           2.125 |                                  0.144 |               2.231 |                      87.583 |        0.578 |             1.838 | OSL 54, PAR 10 |
| California |  64 |                           2.907 |                                  0.134 |               3.049 |                      79.578 |        0.625 |             2.615 | OSL 57, PAR 7  |

## brown metric, ε = 0.02 kWh/GB

| source     |   n |   value of waiting vs A1 mean % |   saved by waiting (A1 − Ours) kg mean |   Ours vs B3 mean % |   Ours vs B1 (local) mean % |   Ours waits |   R3 vs B3 mean % | Ours DCs               |
|:-----------|----:|--------------------------------:|---------------------------------------:|--------------------:|----------------------------:|-------------:|------------------:|:-----------------------|
| Frankfurt  |  64 |                           2.737 |                                  0.024 |              36.583 |                      73.486 |        0.188 |             4.321 | OSL 27, FRA 24, PAR 13 |
| Warsaw     |  64 |                           3.361 |                                  0.07  |              11.999 |                      79.644 |        0.391 |             4.138 | OSL 34, PAR 23, WAW 7  |
| California |  64 |                           5.128 |                                  0.039 |              53.183 |                      83.759 |        0.234 |             6.844 | CAL 32, OSL 22, PAR 10 |
