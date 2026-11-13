# contention: diurnal DC queues

> Carbon intensity: Energy-Charts/ENTSO-E + CAISO 2024 (production-based life-cycle CI) historical hourly data; dates 2024-01-17, 2024-07-17; start hours 0/6/12/18 UTC. Queue wait = ρ × weight × 2 h for arrivals in local business hours (09–18), × 0.5 h otherwise. Weights: OSL 1, PAR 1, FRA 0.5, CAL 0.5, WAW 0.25. B7 = send now to the greenest DC that can still meet the deadline after its queue.

## location metric, ε = 0.02 kWh/GB

|   ρ |   n |   Ours feasible |   B3 misses deadline |   vs B3 mean % |   vs B3 share ≥5 % |   vs B7 mean % |   vs B7 share ≥5 % |   vs A1 mean % |   vs A2 mean % |   Ours DC ≠ B7 DC |   Ours waits | Ours DCs                    |
|----:|----:|----------------:|---------------------:|---------------:|-------------------:|---------------:|-------------------:|---------------:|---------------:|------------------:|-------------:|:----------------------------|
|   0 |  64 |               1 |                0     |          1.719 |              0.109 |          1.719 |              0.109 |          1.573 |          0.102 |             0.031 |        0.453 | OSL 56, PAR 8               |
|   1 |  64 |               1 |                0     |          1.203 |              0.078 |          1.203 |              0.078 |          1.065 |          0.043 |             0.016 |        0.406 | OSL 57, PAR 7               |
|   2 |  64 |               1 |                0.062 |          1.005 |              0.05  |          2.061 |              0.062 |          1.954 |          0     |             0.016 |        0.422 | OSL 56, PAR 5, CAL 2, FRA 1 |

## brown metric, ε = 0.02 kWh/GB

|   ρ |   n |   Ours feasible |   B3 misses deadline |   vs B3 mean % |   vs B3 share ≥5 % |   vs B7 mean % |   vs B7 share ≥5 % |   vs A1 mean % |   vs A2 mean % |   Ours DC ≠ B7 DC |   Ours waits | Ours DCs                      |
|----:|----:|----------------:|---------------------:|---------------:|-------------------:|---------------:|-------------------:|---------------:|---------------:|------------------:|-------------:|:------------------------------|
|   0 |  64 |               1 |                0     |         36.583 |              0.531 |         36.583 |              0.531 |          2.737 |         35.024 |             0.578 |        0.188 | OSL 27, FRA 24, PAR 13        |
|   1 |  64 |               1 |                0     |         35.029 |              0.5   |         35.029 |              0.5   |          2.096 |         33.584 |             0.547 |        0.188 | OSL 29, FRA 23, PAR 12        |
|   2 |  64 |               1 |                0.062 |         28.575 |              0.5   |         29.759 |              0.508 |          1.866 |         28.313 |             0.5   |        0.188 | OSL 30, FRA 23, PAR 10, CAL 1 |

## Theory-guided rule vs full search (gain over B7), ρ = 0

Capture = Σ(base − rule) / Σ(base − Ours) over problems where Ours beats the base by > 0.1 %. Solver calls: rule ≤ 2 (R1) or ≤ 4 (R3), one of them the reference schedule; Ours = all grid points.

| metric   | rule   |   problems Ours beats base |   capture of Ours' gain |   rule vs B7 mean % |   Ours vs rule mean % |   Ours vs rule max % |   rule = Ours (share) |   Ours solver calls (mean) |
|:---------|:-------|---------------------------:|------------------------:|--------------------:|----------------------:|---------------------:|----------------------:|---------------------------:|
| location | R1     |                         28 |                   0.642 |               1.268 |                 0.468 |                 5.48 |                 0.625 |                         81 |
| location | R3     |                         28 |                   0.684 |               1.335 |                 0.399 |                 5.48 |                 0.641 |                         81 |
| brown    | R1     |                         43 |                   0.063 |               3.757 |                35.386 |               100    |                 0.422 |                         81 |
| brown    | R3     |                         43 |                   0.07  |               4.321 |                35     |               100    |                 0.484 |                         81 |

## Theory-guided rule vs full search (gain over B7), ρ = 1

Capture = Σ(base − rule) / Σ(base − Ours) over problems where Ours beats the base by > 0.1 %. Solver calls: rule ≤ 2 (R1) or ≤ 4 (R3), one of them the reference schedule; Ours = all grid points.

| metric   | rule   |   problems Ours beats base |   capture of Ours' gain |   rule vs B7 mean % |   Ours vs rule mean % |   Ours vs rule max % |   rule = Ours (share) |   Ours solver calls (mean) |
|:---------|:-------|---------------------------:|------------------------:|--------------------:|----------------------:|---------------------:|----------------------:|---------------------------:|
| location | R1     |                         25 |                   0.536 |               0.836 |                 0.371 |                5.176 |                 0.703 |                         81 |
| location | R3     |                         25 |                   0.544 |               0.861 |                 0.346 |                5.176 |                 0.781 |                         81 |
| brown    | R1     |                         43 |                   0.046 |               2.269 |                34.087 |              100     |                 0.453 |                         81 |
| brown    | R3     |                         43 |                   0.054 |               3.389 |                33.547 |              100     |                 0.484 |                         81 |

## Theory-guided rule vs full search (gain over B7), ρ = 2

Capture = Σ(base − rule) / Σ(base − Ours) over problems where Ours beats the base by > 0.1 %. Solver calls: rule ≤ 2 (R1) or ≤ 4 (R3), one of them the reference schedule; Ours = all grid points.

| metric   | rule   |   problems Ours beats base |   capture of Ours' gain |   rule vs B7 mean % |   Ours vs rule mean % |   Ours vs rule max % |   rule = Ours (share) |   Ours solver calls (mean) |
|:---------|:-------|---------------------------:|------------------------:|--------------------:|----------------------:|---------------------:|----------------------:|---------------------------:|
| location | R1     |                         25 |                   0.803 |               1.698 |                 0.367 |                3.555 |                 0.672 |                         81 |
| location | R3     |                         25 |                   0.838 |               1.758 |                 0.307 |                3.438 |                 0.703 |                         81 |
| brown    | R1     |                         40 |                   0.181 |               3.877 |                27.646 |              100     |                 0.469 |                         81 |
| brown    | R3     |                         40 |                   0.19  |               4.724 |                27.232 |              100     |                 0.5   |                         81 |
