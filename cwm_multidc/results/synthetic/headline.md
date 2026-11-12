# headline

> **Synthetic carbon-intensity data**: development results, not empirical findings.

## brown metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other (total gCO₂)

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              |  14 |        77.633 |          90.538 |       92.511 |            0.857 |              0 |
| B2: Greenest-DC + HEFT                     |  16 |        55.755 |          56.667 |      100     |            1     |              0 |
| B3: Greenest-DC + CWM                      |  16 |        22.65  |           0     |      100     |            0.25  |              0 |
| B4: Network-Optimized                      |  16 |        31.597 |           0     |      100     |            0.438 |              0 |
| B5: Compute-Optimized                      |  16 |        22.65  |           0     |      100     |            0.25  |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       |  14 |         0     |           0     |        0     |            0     |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) |  16 |        22.65  |           0     |      100     |            0.25  |              0 |
| C1: B3-bestN (equal solver budget)         |  16 |        22.16  |          -0.466 |      100     |            0.25  |              0 |

- Ours vs separable bound: median gap 0.0% (max 34.1%)
- CWM non-monotonicity (Prop. 1 violations): 16.3% of consecutive arrival steps

## location metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other (total gCO₂)

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              |  16 |        83.245 |          88.704 |       90.198 |            1     |              0 |
| B2: Greenest-DC + HEFT                     |  16 |        15.743 |          15.32  |       27.783 |            0.75  |              0 |
| B3: Greenest-DC + CWM                      |  16 |         0     |           0     |        0     |            0     |              0 |
| B4: Network-Optimized                      |  16 |         2.843 |           0     |       15.897 |            0.188 |              0 |
| B5: Compute-Optimized                      |  16 |         0     |           0     |        0     |            0     |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       |  16 |         0     |           0     |        0     |            0     |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) |  16 |         0     |           0     |        0     |            0     |              0 |
| C1: B3-bestN (equal solver budget)         |  16 |        -0.179 |          -0.141 |        0     |            0     |              0 |

- Ours vs separable bound: median gap 0.0% (max 14.4%)
- CWM non-monotonicity (Prop. 1 violations): 25.8% of consecutive arrival steps

## Per problem, brown metric (total kgCO₂)

|                                    |   Ours |    B1 |    B2 |   B3 |   B4 |   B5 |   A1 |   A2 |   C1 | Ours DC   |   Ours T_net (h) |
|:-----------------------------------|-------:|------:|------:|-----:|-----:|-----:|-----:|-----:|-----:|:----------|-----------------:|
| ('atacseq200', 0, 1000.0, 1.5)     |   1.01 |  1.01 |  4.39 | 4.27 | 4.27 | 4.27 | 1.01 | 4.27 | 4.27 | FRA       |                0 |
| ('atacseq200', 0, 1000.0, 2.0)     |   0    |  0    |  4.39 | 4.27 | 4.27 | 4.27 | 0    | 4.27 | 4.27 | FRA       |                0 |
| ('atacseq200', 12, 1000.0, 1.5)    |   0.46 |  0.46 |  3.39 | 3.27 | 3.27 | 3.27 | 0.46 | 3.27 | 3.27 | FRA       |                0 |
| ('atacseq200', 12, 1000.0, 2.0)    |   0    |  0    |  3.39 | 3.27 | 3.27 | 3.27 | 0    | 3.27 | 3.27 | FRA       |                0 |
| ('chipseq1000', 0, 1000.0, 1.5)    |   7.17 | 65.36 | 10.25 | 7.17 | 7.17 | 7.17 | 7.17 | 7.17 | 7.14 | OSL       |                0 |
| ('chipseq1000', 0, 1000.0, 2.0)    |   4.39 | 46.94 | 10.25 | 4.39 | 8.66 | 4.39 | 4.39 | 4.39 | 4.39 | OSL       |                0 |
| ('chipseq1000', 12, 1000.0, 1.5)   |   6.48 | 78.76 |  9.59 | 6.48 | 6.48 | 6.48 | 6.48 | 6.48 | 6.44 | OSL       |                0 |
| ('chipseq1000', 12, 1000.0, 2.0)   |   3.67 | 49.03 |  9.59 | 3.67 | 3.67 | 3.67 | 3.67 | 3.67 | 3.64 | OSL       |                0 |
| ('eager1000', 0, 1000.0, 1.5)      |   7.21 | 60.02 | 10.05 | 7.21 | 7.21 | 7.21 | 7.21 | 7.21 | 7.16 | OSL       |                0 |
| ('eager1000', 0, 1000.0, 2.0)      |   4.41 | 50.08 | 10.05 | 4.41 | 8.44 | 4.41 | 4.41 | 4.41 | 4.38 | OSL       |                0 |
| ('eager1000', 12, 1000.0, 1.5)     |   6.56 | 70.78 |  9.38 | 6.56 | 6.56 | 6.56 | 6.56 | 6.56 | 6.47 | OSL       |                0 |
| ('eager1000', 12, 1000.0, 2.0)     |   3.66 | 44.51 |  9.38 | 3.66 | 3.66 | 3.66 | 3.66 | 3.66 | 3.64 | OSL       |                0 |
| ('methylseq1000', 0, 1000.0, 1.5)  |   7.6  | 72.37 | 10.45 | 7.6  | 7.6  | 7.6  | 7.6  | 7.6  | 7.48 | OSL       |                0 |
| ('methylseq1000', 0, 1000.0, 2.0)  |   4.78 | 52.62 | 10.45 | 4.78 | 8.86 | 4.78 | 4.78 | 4.78 | 4.75 | OSL       |                0 |
| ('methylseq1000', 12, 1000.0, 1.5) |   6.74 | 70.45 |  9.79 | 6.74 | 6.74 | 6.74 | 6.74 | 6.74 | 6.73 | OSL       |                0 |
| ('methylseq1000', 12, 1000.0, 2.0) |   4.01 | 41.63 |  9.79 | 4.01 | 4.01 | 4.01 | 4.01 | 4.01 | 4    | OSL       |                0 |

## ε_net sweep (brown metric, post hoc): gain of Ours over B3

|   eps_kwh_per_gb |   n |   mean_gain_% |   share_gain>=5% |
|-----------------:|----:|--------------:|-----------------:|
|            0.001 |  16 |        12.5   |            0.125 |
|            0.005 |  16 |        15.598 |            0.25  |
|            0.02  |  16 |        22.65  |            0.25  |
|            0.06  |  16 |        24.217 |            0.25  |
