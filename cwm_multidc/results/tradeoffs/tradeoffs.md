# Carbon vs deadline, and results by workflow type

Location metric, ε = 0.02 kWh/GB, from the saved summaries (no solver calls). CWM fills its window (median makespan = 99.8 % of D′), so a job finishes at its deadline D: the carbon/latency trade-off is carbon against D.

## Mean carbon per job against the deadline (seasonal study, 4 dates × 4 start hours)

| dag        |   data_size_gb |   alpha |    D_h |     B1 |     B3 |   Ours |
|:-----------|---------------:|--------:|-------:|-------:|-------:|-------:|
| atacseq200 |            100 |     1.5 |  8.4   | 14.521 |  1.503 |  1.471 |
| atacseq200 |            100 |     2   | 11.2   | 14.444 |  1.503 |  1.455 |
| atacseq200 |            100 |     2.5 | 14     | 14.404 |  1.498 |  1.449 |
| atacseq200 |           1000 |     1.5 |  8.4   | 14.521 |  4.764 |  4.74  |
| atacseq200 |           1000 |     2   | 11.2   | 14.444 |  4.764 |  4.609 |
| atacseq200 |           1000 |     2.5 | 14     | 14.404 |  4.779 |  4.538 |
| eager1000  |            100 |     1.5 | 16.767 | 99.53  |  6.746 |  6.746 |
| eager1000  |            100 |     2   | 22.333 | 89.931 |  6.025 |  6.018 |
| eager1000  |            100 |     2.5 | 27.933 | 82.282 |  6.032 |  5.984 |
| eager1000  |           1000 |     1.5 | 16.767 | 99.53  | 11.039 | 11.029 |
| eager1000  |           1000 |     2   | 22.333 | 89.931 |  9.425 |  9.397 |
| eager1000  |           1000 |     2.5 | 27.933 | 82.282 |  9.311 |  9.094 |

## Carbon saved per extra hour of deadline (α 1.5 → 2.5), g CO₂ per hour

| dag        |   data_size_gb |   extra_hours |   B1_g_per_h |   B3_g_per_h |   Ours_g_per_h |
|:-----------|---------------:|--------------:|-------------:|-------------:|---------------:|
| atacseq200 |            100 |           5.6 |         21   |          0.9 |            4   |
| atacseq200 |           1000 |           5.6 |         21   |         -2.7 |           35.9 |
| eager1000  |            100 |          11.2 |       1544.6 |         64   |           68.2 |
| eager1000  |           1000 |          11.2 |       1544.6 |        154.8 |          173.3 |

## By workflow: headline study (17 Apr 2024, 1 TB, start 00/12 UTC, α 1.5/2.0, 3 seeds)

| dag           |   tasks |   dependencies |   M_h |   ours_kg |   gain_vs_B2_pct |   gain_vs_B3_pct |
|:--------------|--------:|---------------:|------:|----------:|-----------------:|-----------------:|
| atacseq200    |     195 |            350 |  5.6  |      4.87 |             0.68 |                0 |
| chipseq1000   |     975 |           1755 | 11.7  |     10.38 |            20.01 |                0 |
| eager1000     |     944 |           3328 | 11.17 |     10.14 |            19.24 |                0 |
| methylseq1000 |     996 |           1743 | 11.83 |     10.63 |            19.4  |                0 |

## By workflow: seasonal study (gain and where the saving comes from)

`saved_net_g` / `saved_comp_g`: mean grams Ours saves over B3 in network / compute carbon (negative = Ours spends more).

| dag        |   data_size_gb |   M_h |   B3_kg |   net_share_B3_pct |   gain_vs_B3_pct |   value_of_waiting_pct |   saved_net_g |   saved_comp_g |   waits_pct |
|:-----------|---------------:|------:|--------:|-------------------:|-----------------:|-----------------------:|--------------:|---------------:|------------:|
| atacseq200 |            100 |  5.6  |    1.5  |              23.65 |             2.76 |                   2.19 |         17.91 |          25.49 |       56.25 |
| atacseq200 |           1000 |  5.6  |    4.77 |              74.35 |             3.08 |                   2.97 |        135.41 |           4.55 |       54.17 |
| eager1000  |            100 | 11.17 |    6.27 |               5.75 |             0.29 |                   0.26 |          9.59 |           8.43 |       31.25 |
| eager1000  |           1000 | 11.17 |    9.93 |              35.77 |             0.9  |                   0.87 |        104.84 |         -19.42 |       25    |
