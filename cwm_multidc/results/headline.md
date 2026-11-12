# headline

> Carbon intensity: Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI) historical hourly data, window starting 2024-04-17 UTC.

## brown metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other (total gCO₂)

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              |  15 |        74.499 |          93.428 |       95.475 |            0.8   |              0 |
| B2: Greenest-DC + HEFT                     |  16 |        52.425 |          53.874 |      100     |            1     |              0 |
| B3: Greenest-DC + CWM                      |  16 |        19.082 |           0     |      100     |            0.25  |              0 |
| B4: Network-Optimized                      |  16 |        28.905 |           0     |      100     |            0.438 |              0 |
| B5: Compute-Optimized                      |  16 |        19.102 |           0     |      100     |            0.25  |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       |  15 |         0     |           0     |        0     |            0     |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) |  16 |        19.082 |           0     |      100     |            0.25  |              0 |
| C1: B3-bestN (equal solver budget)         |  16 |        18.593 |          -0.274 |      100     |            0.25  |              0 |

- Ours vs separable bound: median gap 0.0% (max 27.6%)
- CWM non-monotonicity (Prop. 1 violations): 12.0% of consecutive arrival steps

## location metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other (total gCO₂)

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              |  16 |        86.083 |          90.7   |       92.769 |            1     |              0 |
| B2: Greenest-DC + HEFT                     |  16 |        14.832 |          16.337 |       28.494 |            0.75  |              0 |
| B3: Greenest-DC + CWM                      |  16 |         0     |           0     |        0     |            0     |              0 |
| B4: Network-Optimized                      |  16 |         4.254 |           0     |       22.984 |            0.188 |              0 |
| B5: Compute-Optimized                      |  16 |         0     |           0     |        0     |            0     |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       |  16 |         0     |           0     |        0     |            0     |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) |  16 |         0     |           0     |        0     |            0     |              0 |
| C1: B3-bestN (equal solver budget)         |  16 |        -0.169 |          -0.052 |        0     |            0     |              0 |

- Ours vs separable bound: median gap 0.0% (max 12.0%)
- CWM non-monotonicity (Prop. 1 violations): 15.3% of consecutive arrival steps

## Per problem, brown metric (total kgCO₂)

|                                    |   Ours |     B1 |   B2 |   B3 |   B4 |   B5 |   A1 |   A2 |   C1 | Ours DC   |   Ours T_net (h) |
|:-----------------------------------|-------:|-------:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|:----------|-----------------:|
| ('atacseq200', 0, 1000.0, 1.5)     |   1.6  |   1.6  | 4.5  | 4.42 | 4.42 | 4.42 | 1.6  | 4.42 | 4.42 | FRA       |                0 |
| ('atacseq200', 0, 1000.0, 2.0)     |   0    |   0    | 4.5  | 4.42 | 4.42 | 4.42 | 0    | 4.42 | 4.42 | FRA       |                0 |
| ('atacseq200', 12, 1000.0, 1.5)    |   1.44 |   1.44 | 3.21 | 3.11 | 3.11 | 3.11 | 1.44 | 3.11 | 3.11 | FRA       |                0 |
| ('atacseq200', 12, 1000.0, 2.0)    |   0.37 |   0.37 | 3.21 | 3.11 | 3.11 | 3.11 | 0.37 | 3.11 | 3.11 | FRA       |                0 |
| ('chipseq1000', 0, 1000.0, 1.5)    |   7.17 |  70.89 | 9.7  | 7.17 | 7.17 | 7.17 | 7.17 | 7.17 | 7.1  | PAR       |                0 |
| ('chipseq1000', 0, 1000.0, 2.0)    |   4.46 |  92.23 | 9.7  | 4.46 | 9.44 | 4.46 | 4.46 | 4.46 | 4.45 | PAR       |                0 |
| ('chipseq1000', 12, 1000.0, 1.5)   |   5.84 | 111.27 | 9.16 | 5.84 | 5.84 | 5.84 | 5.84 | 5.84 | 5.8  | PAR       |                0 |
| ('chipseq1000', 12, 1000.0, 2.0)   |   3.23 |  71.48 | 9.16 | 3.23 | 3.23 | 3.23 | 3.23 | 3.23 | 3.2  | PAR       |                0 |
| ('eager1000', 0, 1000.0, 1.5)      |   7.34 |  61.18 | 9.42 | 7.34 | 7.34 | 7.34 | 7.34 | 7.34 | 7.25 | PAR       |                0 |
| ('eager1000', 0, 1000.0, 2.0)      |   4.43 |  79.77 | 9.42 | 4.43 | 9.25 | 4.43 | 4.43 | 4.43 | 4.42 | PAR       |                0 |
| ('eager1000', 12, 1000.0, 1.5)     |   5.97 |  94.72 | 8.91 | 5.97 | 5.97 | 5.97 | 5.97 | 5.97 | 5.93 | PAR       |                0 |
| ('eager1000', 12, 1000.0, 2.0)     |   3.15 |  64.75 | 8.91 | 3.15 | 3.15 | 3.15 | 3.15 | 3.15 | 3.15 | PAR       |                0 |
| ('methylseq1000', 0, 1000.0, 1.5)  |   7.1  |  78    | 9.87 | 7.1  | 7.1  | 7.1  | 7.1  | 7.1  | 7.04 | PAR       |                0 |
| ('methylseq1000', 0, 1000.0, 2.0)  |   4.57 |  69.54 | 9.87 | 4.57 | 9.57 | 4.57 | 4.57 | 4.57 | 4.56 | PAR       |                0 |
| ('methylseq1000', 12, 1000.0, 1.5) |   6.36 |  88.95 | 9.36 | 6.36 | 6.36 | 6.38 | 6.36 | 6.36 | 6.26 | PAR       |                0 |
| ('methylseq1000', 12, 1000.0, 2.0) |   3.45 |  55.07 | 9.36 | 3.45 | 3.45 | 3.45 | 3.45 | 3.45 | 3.44 | PAR       |                0 |

## ε_net sweep (brown metric, post hoc): gain of Ours over B3

|   eps_kwh_per_gb |   n |   mean_gain_% |   share_gain>=5% |
|-----------------:|----:|--------------:|-----------------:|
|            0.001 |  16 |         6.387 |            0.062 |
|            0.005 |  16 |         9.566 |            0.125 |
|            0.02  |  16 |        19.082 |            0.25  |
|            0.06  |  16 |        23.027 |            0.25  |
