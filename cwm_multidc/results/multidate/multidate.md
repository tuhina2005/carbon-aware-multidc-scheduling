# multidate

> Carbon intensity: Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI) historical hourly data; 12 dates (2024-01-17 … 2024-12-18, third Wednesday of each month), start hours 0/6/12/18 UTC. 576 problems, one CWM seed each (no C1 control).

> ⚠ Produced with solver build `d849bc23fc71`, not the deployed `8a456bbb33a0`. pre-fix build: has the out-of-bounds read in mapper.cpp (results not bit-reproducible)

## location metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              | 576 |        82.262 |          86.843 |       95.61  |            1     |              0 |
| B2: Greenest-DC + HEFT                     | 576 |        16.661 |          13.036 |       47.633 |            0.651 |              0 |
| B3: Greenest-DC + CWM                      | 576 |         2.202 |           0     |       35.475 |            0.146 |              0 |
| B4: Network-Optimized                      | 576 |         5.927 |           0.176 |       41.382 |            0.297 |              0 |
| B5: Compute-Optimized                      | 576 |         2.12  |           0     |       35.475 |            0.141 |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       | 576 |         2.116 |           0     |       35.475 |            0.141 |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) | 576 |         0.093 |           0     |       10.429 |            0.005 |              0 |

- Ours waits (T_net > 0) in 270 of 576 problems (47%); Ours picks the same DC as B3 in 95%.
- Value of waiting (gain vs A1, mean / median / max %): all 2.1 / 0.0 / 35.5; where Ours waits 4.5 / 2.2 / 35.5.
- Where Ours waits at B3's DC (256 problems): network saving vs B3 63.25 kg in total, compute change +7.62 kg (compute got worse in 129, better in 127).

### location: breakdown

| by               | value      |   n |   gain vs B3 mean % |   gain vs B3 max % |   gain vs A1 mean % |   share waiting |   mean T_net (h) when waiting | Ours DCs         |
|:-----------------|:-----------|----:|--------------------:|-------------------:|--------------------:|----------------:|------------------------------:|:-----------------|
| month            | 2024-01    |  48 |                0.48 |               5.49 |                0.48 |            0.31 |                          3.52 | OSL 48           |
| month            | 2024-02    |  48 |                2.31 |              16.53 |                2.31 |            0.5  |                          3.12 | OSL 48           |
| month            | 2024-03    |  48 |                4.09 |              24.38 |                4.09 |            0.56 |                          4.05 | OSL 48           |
| month            | 2024-04    |  48 |                3.23 |              22.67 |                2.68 |            0.44 |                          3.57 | PAR 44, OSL 4    |
| month            | 2024-05    |  48 |                1.51 |              10.11 |                1.51 |            0.5  |                          3.68 | PAR 48           |
| month            | 2024-06    |  48 |                2.29 |              24.45 |                2.27 |            0.31 |                          3.78 | PAR 47, OSL 1    |
| month            | 2024-07    |  48 |                2.05 |              19.11 |                1.86 |            0.44 |                          2.88 | OSL 34, PAR 14   |
| month            | 2024-08    |  48 |                2.93 |              19.65 |                2.79 |            0.71 |                          3.24 | PAR 42, OSL 6    |
| month            | 2024-09    |  48 |                3.45 |              35.47 |                3.33 |            0.44 |                          3.03 | PAR 38, OSL 10   |
| month            | 2024-10    |  48 |                1.27 |              11.4  |                1.27 |            0.48 |                          2.61 | PAR 48           |
| month            | 2024-11    |  48 |                1.2  |              11.34 |                1.2  |            0.46 |                          3.03 | OSL 48           |
| month            | 2024-12    |  48 |                1.61 |               9.93 |                1.61 |            0.48 |                          3.7  | OSL 47, PAR 1    |
| start hour (UTC) | 0          | 144 |                1.54 |              19.11 |                1.54 |            0.49 |                          3.57 | PAR 79, OSL 65   |
| start hour (UTC) | 6          | 144 |                5.07 |              35.47 |                5.01 |            0.71 |                          3.51 | PAR 73, OSL 71   |
| start hour (UTC) | 12         | 144 |                0.49 |              12.63 |                0.31 |            0.21 |                          1.91 | OSL 81, PAR 63   |
| start hour (UTC) | 18         | 144 |                1.71 |              16.77 |                1.61 |            0.47 |                          3.49 | OSL 77, PAR 67   |
| DAG              | atacseq200 | 288 |                3.48 |              35.47 |                3.33 |            0.61 |                          3.22 | PAR 145, OSL 143 |
| DAG              | eager1000  | 288 |                0.92 |              16.8  |                0.9  |            0.33 |                          3.58 | OSL 151, PAR 137 |
| Δ (GB)           | 100.0      | 288 |                1.53 |              14.67 |                1.4  |            0.49 |                          3.53 | OSL 144, PAR 144 |
| Δ (GB)           | 1000.0     | 288 |                2.87 |              35.47 |                2.83 |            0.45 |                          3.14 | OSL 150, PAR 138 |
| α                | 1.5        | 192 |                0.59 |              10.22 |                0.52 |            0.28 |                          1.26 | PAR 98, OSL 94   |
| α                | 2.0        | 192 |                2.18 |              32.77 |                2.1  |            0.44 |                          2.7  | OSL 99, PAR 93   |
| α                | 2.5        | 192 |                3.83 |              35.47 |                3.73 |            0.68 |                          4.62 | OSL 101, PAR 91  |

## brown metric, ε = 0.02 kWh/GB: gain = 1 − Ours/other

| vs                                         |   n |   mean_gain_% |   median_gain_% |   max_gain_% |   share_gain>=5% |   n_infeasible |
|:-------------------------------------------|----:|--------------:|----------------:|-------------:|-----------------:|---------------:|
| B1: CWM-Local                              | 364 |        77.414 |          91.405 |       99.565 |            0.89  |              0 |
| B2: Greenest-DC + HEFT                     | 576 |        76.948 |          93.61  |      100     |            0.986 |              0 |
| B3: Greenest-DC + CWM                      | 576 |        43.457 |          12.341 |      100     |            0.545 |              0 |
| B4: Network-Optimized                      | 576 |        58.986 |          73.885 |      100     |            0.745 |              0 |
| B5: Compute-Optimized                      | 576 |        43.382 |          12.341 |      100     |            0.535 |              0 |
| A1: Ours-NoWait (best DC, T_net = 0)       | 364 |         3.033 |           0     |       50.454 |            0.151 |              0 |
| A2: Ours-FixedDC (greenest DC, best T_net) | 576 |        41.539 |           0.575 |      100     |            0.455 |              0 |

- Ours waits (T_net > 0) in 96 of 576 problems (17%); Ours picks the same DC as B3 in 49%.
- Value of waiting (gain vs A1, mean / median / max %): all 3.0 / 0.0 / 50.5; where Ours waits 11.5 / 7.7 / 50.5.
- Where Ours waits at B3's DC (79 problems): network saving vs B3 21.42 kg in total, compute change +5.59 kg (compute got worse in 30, better in 0).

### brown: breakdown

| by               | value      |   n |   gain vs B3 mean % |   gain vs B3 max % |   gain vs A1 mean % |   share waiting |   mean T_net (h) when waiting | Ours DCs                |
|:-----------------|:-----------|----:|--------------------:|-------------------:|--------------------:|----------------:|------------------------------:|:------------------------|
| month            | 2024-01    |  48 |               17.24 |             100    |                0.55 |            0.17 |                          3.71 | OSL 37, FRA 11          |
| month            | 2024-02    |  48 |               52.04 |             100    |                4.01 |            0.08 |                          4.08 | FRA 24, OSL 23, PAR 1   |
| month            | 2024-03    |  48 |               27.47 |             100    |                3.94 |            0.25 |                          4.18 | OSL 31, FRA 14, PAR 3   |
| month            | 2024-04    |  48 |               36.49 |             100    |                3.01 |            0.21 |                          3.93 | PAR 27, FRA 19, OSL 2   |
| month            | 2024-05    |  48 |               51.23 |             100    |                2.45 |            0.15 |                          3.62 | FRA 24, PAR 24          |
| month            | 2024-06    |  48 |               42.55 |             100    |                4.14 |            0.17 |                          3.58 | PAR 28, FRA 20          |
| month            | 2024-07    |  48 |               45.74 |             100    |                3.61 |            0.12 |                          3.61 | FRA 21, PAR 16, OSL 11  |
| month            | 2024-08    |  48 |               52.33 |             100    |                4.56 |            0.21 |                          2.83 | FRA 24, PAR 20, OSL 4   |
| month            | 2024-09    |  48 |               48.44 |             100    |                4.67 |            0.19 |                          3.37 | FRA 23, PAR 22, OSL 3   |
| month            | 2024-10    |  48 |               50.93 |             100    |                1.86 |            0.15 |                          3.4  | FRA 24, PAR 24          |
| month            | 2024-11    |  48 |               44.69 |             100    |                1.62 |            0.15 |                          2.79 | OSL 26, FRA 22          |
| month            | 2024-12    |  48 |               52.32 |             100    |                3.17 |            0.17 |                          3.12 | FRA 26, OSL 22          |
| start hour (UTC) | 0          | 144 |               44.7  |             100    |                2.69 |            0.19 |                          4.24 | FRA 64, PAR 46, OSL 34  |
| start hour (UTC) | 6          | 144 |               49.74 |             100    |                7.82 |            0.24 |                          3.35 | FRA 67, PAR 40, OSL 37  |
| start hour (UTC) | 12         | 144 |               41.78 |             100    |                0.05 |            0.02 |                          1    | FRA 63, OSL 41, PAR 40  |
| start hour (UTC) | 18         | 144 |               37.61 |             100    |                1.79 |            0.21 |                          3.3  | FRA 58, OSL 47, PAR 39  |
| DAG              | atacseq200 | 288 |               82.96 |             100    |                1.11 |            0.04 |                          2.69 | FRA 250, OSL 29, PAR 9  |
| DAG              | eager1000  | 288 |                3.96 |              50.45 |                3.54 |            0.29 |                          3.64 | PAR 156, OSL 130, FRA 2 |
| Δ (GB)           | 100.0      | 288 |               40.95 |             100    |                3.66 |            0.2  |                          3.45 | FRA 114, OSL 87, PAR 87 |
| Δ (GB)           | 1000.0     | 288 |               45.96 |             100    |                2.41 |            0.13 |                          3.64 | FRA 138, PAR 78, OSL 72 |
| α                | 1.5        | 192 |               34.13 |             100    |                0.42 |            0.05 |                          1.58 | FRA 71, OSL 63, PAR 58  |
| α                | 2.0        | 192 |               43.58 |             100    |                1.03 |            0.12 |                          1.48 | FRA 86, PAR 57, OSL 49  |
| α                | 2.5        | 192 |               52.66 |             100    |                8.7  |            0.33 |                          4.53 | FRA 95, PAR 50, OSL 47  |

## ε_net sweep (post hoc)

| metric   |   eps_kwh_per_gb |   mean gain vs B3 % |   share gain>=5% |   share waiting |
|:---------|-----------------:|--------------------:|-----------------:|----------------:|
| location |            0.001 |               0.977 |            0.071 |           0.349 |
| location |            0.005 |               1.309 |            0.083 |           0.373 |
| location |            0.02  |               2.202 |            0.146 |           0.469 |
| location |            0.06  |               3.889 |            0.257 |           0.521 |
| brown    |            0.001 |              40.021 |            0.502 |           0.158 |
| brown    |            0.005 |              40.615 |            0.505 |           0.165 |
| brown    |            0.02  |              43.457 |            0.545 |           0.167 |
| brown    |            0.06  |              47.185 |            0.606 |           0.181 |
