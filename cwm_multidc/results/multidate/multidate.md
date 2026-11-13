# multidate

> Carbon intensity: Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI) historical hourly data; 4 dates (2024-01, 2024-04, 2024-07, 2024-10; third Wednesdays), start hours 0/6/12/18 UTC. 192 problems, one CWM seed each (no C1 control).

## location metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              | 192 |        83.862 |          87.859 |       95.61  |            1     |              0 |
| B2: Greenest-DC + HEFT                     | 192 |        16.132 |          12.404 |       39.516 |            0.635 |              0 |
| B3: Greenest-DC + CWM                      | 192 |         1.758 |           0     |       22.668 |            0.109 |              0 |
| B4: Network-Optimized                      | 192 |         4.914 |           0.066 |       41.382 |            0.255 |              0 |
| B5: Compute-Optimized                      | 192 |         1.577 |           0     |       22.668 |            0.094 |              0 |
| B6: Efficiency-aware greenest DC + CWM     | 192 |         1.758 |           0     |       22.668 |            0.109 |              0 |
| B7: Queue-aware greenest DC + CWM          | 192 |         1.758 |           0     |       22.668 |            0.109 |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       | 192 |         1.572 |           0     |       22.668 |            0.094 |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) | 192 |         0.207 |           0     |       10.429 |            0.016 |              0 |
| R1: Rule, top-1 (≤ 2 solver calls)         | 192 |         0.52  |           0     |       10.223 |            0.016 |              0 |
| R3: Rule, top-3 (≤ 4 solver calls)         | 192 |         0.377 |           0     |        5.48  |            0.01  |              0 |

- Ours waits (T_net > 0) in 80 of 192 problems (42%); Ours picks the same DC as B3 in 93%.
- Value of waiting (gain vs A1, mean / median / max %): all 1.6 / 0.0 / 22.7; where Ours waits 3.8 / 1.9 / 22.7.
- Where Ours waits at B3's DC (73 problems): network saving vs B3 12.42 kg in total, compute change +0.60 kg (compute got worse in 33, better in 40).

### location: breakdown

| by               | value      |   n |   gain vs B3 mean % |   gain vs B3 max % |   gain vs A1 mean % |   share waiting |   mean T_net (h) when waiting | Ours DCs       |
|:-----------------|:-----------|----:|--------------------:|-------------------:|--------------------:|----------------:|------------------------------:|:---------------|
| month            | 2024-01    |  48 |                0.48 |               5.49 |                0.48 |            0.31 |                          3.52 | OSL 48         |
| month            | 2024-04    |  48 |                3.23 |              22.67 |                2.68 |            0.44 |                          3.57 | PAR 44, OSL 4  |
| month            | 2024-07    |  48 |                2.05 |              19.11 |                1.86 |            0.44 |                          2.88 | OSL 34, PAR 14 |
| month            | 2024-10    |  48 |                1.27 |              11.4  |                1.27 |            0.48 |                          2.61 | PAR 48         |
| start hour (UTC) | 0          |  48 |                1.16 |              19.11 |                1.16 |            0.52 |                          3.04 | PAR 32, OSL 16 |
| start hour (UTC) | 6          |  48 |                3.91 |              22.67 |                3.72 |            0.56 |                          3.13 | PAR 30, OSL 18 |
| start hour (UTC) | 12         |  48 |                0.58 |               6.79 |                0.23 |            0.19 |                          1.54 | OSL 27, PAR 21 |
| start hour (UTC) | 18         |  48 |                1.38 |              14.67 |                1.18 |            0.4  |                          3.9  | OSL 25, PAR 23 |
| DAG              | atacseq200 |  96 |                2.92 |              22.67 |                2.58 |            0.55 |                          3.05 | PAR 57, OSL 39 |
| DAG              | eager1000  |  96 |                0.6  |              10.88 |                0.56 |            0.28 |                          3.22 | PAR 49, OSL 47 |
| Δ (GB)           | 100.0      |  96 |                1.53 |              14.67 |                1.23 |            0.44 |                          3.3  | PAR 54, OSL 42 |
| Δ (GB)           | 1000.0     |  96 |                1.99 |              22.67 |                1.92 |            0.4  |                          2.89 | PAR 52, OSL 44 |
| α                | 1.5        |  64 |                0.67 |              10.22 |                0.48 |            0.23 |                          1.29 | PAR 37, OSL 27 |
| α                | 2.0        |  64 |                1.72 |              20.72 |                1.55 |            0.39 |                          2.51 | PAR 34, OSL 30 |
| α                | 2.5        |  64 |                2.89 |              22.67 |                2.68 |            0.62 |                          4.16 | PAR 35, OSL 29 |

## brown metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              | 136 |        75.026 |          92.303 |       99.565 |            0.86  |              0 |
| B2: Greenest-DC + HEFT                     | 192 |        71.638 |          80.679 |      100     |            0.979 |              0 |
| B3: Greenest-DC + CWM                      | 192 |        37.601 |           4.042 |      100     |            0.479 |              0 |
| B4: Network-Optimized                      | 192 |        50.34  |          52.508 |      100     |            0.651 |              0 |
| B5: Compute-Optimized                      | 192 |        37.441 |           3.873 |      100     |            0.458 |              0 |
| B6: Efficiency-aware greenest DC + CWM     | 192 |        37.601 |           4.042 |      100     |            0.479 |              0 |
| B7: Queue-aware greenest DC + CWM          | 192 |        37.601 |           4.042 |      100     |            0.479 |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       | 136 |         2.107 |           0     |       36.257 |            0.096 |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) | 192 |        36.272 |           0.616 |      100     |            0.427 |              0 |
| R1: Rule, top-1 (≤ 2 solver calls)         | 186 |        32.363 |           0     |      100     |            0.392 |              0 |
| R3: Rule, top-3 (≤ 4 solver calls)         | 186 |        32.184 |           0     |      100     |            0.371 |              0 |

- Ours waits (T_net > 0) in 31 of 192 problems (16%); Ours picks the same DC as B3 in 48%.
- Value of waiting (gain vs A1, mean / median / max %): all 2.1 / 0.0 / 36.3; where Ours waits 9.2 / 4.2 / 36.3.
- Where Ours waits at B3's DC (22 problems): network saving vs B3 3.14 kg in total, compute change +0.32 kg (compute got worse in 7, better in 0).

### brown: breakdown

| by               | value      |   n |   gain vs B3 mean % |   gain vs B3 max % |   gain vs A1 mean % |   share waiting |   mean T_net (h) when waiting | Ours DCs               |
|:-----------------|:-----------|----:|--------------------:|-------------------:|--------------------:|----------------:|------------------------------:|:-----------------------|
| month            | 2024-01    |  48 |               17.24 |             100    |                0.55 |            0.17 |                          3.71 | OSL 37, FRA 11         |
| month            | 2024-04    |  48 |               36.49 |             100    |                3.01 |            0.21 |                          3.93 | PAR 27, FRA 19, OSL 2  |
| month            | 2024-07    |  48 |               45.74 |             100    |                3.61 |            0.12 |                          3.61 | FRA 21, PAR 16, OSL 11 |
| month            | 2024-10    |  48 |               50.93 |             100    |                1.86 |            0.15 |                          3.4  | FRA 24, PAR 24         |
| start hour (UTC) | 0          |  48 |               46.44 |             100    |                2.15 |            0.21 |                          3.6  | FRA 22, PAR 19, OSL 7  |
| start hour (UTC) | 6          |  48 |               43.2  |             100    |                5.91 |            0.21 |                          3.21 | FRA 20, PAR 18, OSL 10 |
| start hour (UTC) | 12         |  48 |               33.1  |             100    |                0    |            0    |                        nan    | PAR 18, FRA 17, OSL 13 |
| start hour (UTC) | 18         |  48 |               27.65 |             100    |                0.86 |            0.23 |                          4.21 | OSL 20, FRA 16, PAR 12 |
| DAG              | atacseq200 |  96 |               72.03 |             100    |                0.82 |            0.05 |                          3.8  | FRA 75, OSL 17, PAR 4  |
| DAG              | eager1000  |  96 |                3.17 |              36.26 |                2.64 |            0.27 |                          3.67 | PAR 63, OSL 33         |
| Δ (GB)           | 100.0      |  96 |               33.6  |             100    |                2.74 |            0.2  |                          3.83 | PAR 35, FRA 31, OSL 30 |
| Δ (GB)           | 1000.0     |  96 |               41.6  |             100    |                1.47 |            0.12 |                          3.47 | FRA 44, PAR 32, OSL 20 |
| α                | 1.5        |  64 |               26.91 |             100    |                0.38 |            0.05 |                          2    | OSL 22, PAR 22, FRA 20 |
| α                | 2.0        |  64 |               38.08 |             100    |                0.8  |            0.11 |                          1.62 | FRA 26, PAR 23, OSL 15 |
| α                | 2.5        |  64 |               47.81 |             100    |                6.05 |            0.33 |                          4.62 | FRA 29, PAR 22, OSL 13 |

## ε_net sweep (post hoc)

| metric   |   eps_kwh_per_gb |   mean gain vs B3 % |   share gain>=5% |   share waiting |
|:---------|-----------------:|--------------------:|-----------------:|----------------:|
| location |            0.001 |               1.1   |            0.094 |           0.354 |
| location |            0.005 |               1.27  |            0.083 |           0.359 |
| location |            0.02  |               1.758 |            0.109 |           0.417 |
| location |            0.06  |               2.895 |            0.193 |           0.469 |
| brown    |            0.001 |              32.833 |            0.427 |           0.161 |
| brown    |            0.005 |              33.681 |            0.448 |           0.167 |
| brown    |            0.02  |              37.601 |            0.479 |           0.161 |
| brown    |            0.06  |              42.26  |            0.552 |           0.167 |

## Theory-guided rule vs full search (gain over B3)

Capture = Σ(base − rule) / Σ(base − Ours) over problems where Ours beats the base by > 0.1 %. Solver calls: rule ≤ 2 (R1) or ≤ 4 (R3), one of them the reference schedule; Ours = all grid points.

| metric   | rule   |   problems Ours beats base |   capture of Ours' gain |   rule vs B3 mean % |   Ours vs rule mean % |   Ours vs rule max % |   rule = Ours (share) |   Ours solver calls (mean) |
|:---------|:-------|---------------------------:|------------------------:|--------------------:|----------------------:|---------------------:|----------------------:|---------------------------:|
| location | R1     |                         82 |                   0.697 |               1.253 |                 0.52  |               10.223 |                 0.641 |                         64 |
| location | R3     |                         82 |                   0.761 |               1.396 |                 0.377 |                5.48  |                 0.703 |                         64 |
| brown    | R1     |                        121 |                   0.269 |               8.12  |                32.363 |              100     |                 0.526 |                         64 |
| brown    | R3     |                        121 |                   0.273 |               8.477 |                32.184 |              100     |                 0.557 |                         64 |

## Noise control: winning problems re-solved with 3 seeds + C1

Problems where Ours beat B3 by ≥ 5 % (location metric, ε = 0.02, one seed) re-solved with seeds 42/43/44 for every method and C1 = B3's configuration with Ours' number of CWM calls. A gain that survives against C1 is not best-of-N luck of the heuristic.

| metric   |   n |   gain vs B3, 1 seed (mean %) |   gain vs B3, 3 seeds (mean %) |   gain vs C1 (mean %) |   gain vs C1 (median %) |   share ≥ 5 % vs C1 |   share ≤ 0 vs C1 |   Ours waits (share) |
|:---------|----:|------------------------------:|-------------------------------:|----------------------:|------------------------:|--------------------:|------------------:|---------------------:|
| location |  21 |                        11.202 |                         11.212 |                11.18  |                  10.856 |                1    |                 0 |                0.905 |
| brown    |  21 |                        66.694 |                         64.448 |                64.448 |                 100     |                0.81 |                 0 |                0.238 |

- Location, same DC as B3 (16 problems): network saving 8.23 kg, compute change -0.08 kg (compute worse in 6, better in 10).
