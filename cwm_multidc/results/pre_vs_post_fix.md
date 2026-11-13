# Results comparison

- old: `cwm_multidc/results/pre_fix_solver`
- new: `cwm_multidc/results`

| study       | metric   |   problems |   only old |   only new |   choice changed |   Ours total changed (>0.1 %) |   median |Δ total| % |   max |Δ total| % |   gain vs B3 old (mean %) |   gain vs B3 new (mean %) |   share ≥ 5 % old |   share ≥ 5 % new |
|:------------|:---------|-----------:|-----------:|-----------:|-----------------:|------------------------------:|---------------------:|------------------:|--------------------------:|--------------------------:|------------------:|------------------:|
| grid        | location |         70 |          0 |          0 |                0 |                             0 |                    0 |                 0 |                     4.179 |                     4.179 |             0.271 |             0.271 |
| grid        | brown    |         70 |          0 |          0 |                0 |                             0 |                    0 |                 0 |                    29.392 |                    29.392 |             0.386 |             0.386 |
| headline    | location |         16 |          0 |          0 |                0 |                             0 |                    0 |                 0 |                     0     |                     0     |             0     |             0     |
| headline    | brown    |         16 |          0 |          0 |                0 |                             0 |                    0 |                 0 |                    19.082 |                    19.082 |             0.25  |             0.25  |
| sensitivity | location |         16 |          0 |          0 |                0 |                             0 |                    0 |                 0 |                     0.994 |                     0.994 |             0.25  |             0.25  |
| sensitivity | brown    |         16 |          0 |          0 |                0 |                             0 |                    0 |                 0 |                     1.896 |                     1.896 |             0.25  |             0.25  |
| multidate   | location |        192 |        384 |          0 |                0 |                             0 |                    0 |                 0 |                     1.758 |                     1.758 |             0.109 |             0.109 |
| multidate   | brown    |        192 |        384 |          0 |                0 |                             0 |                    0 |                 0 |                    37.601 |                    37.601 |             0.479 |             0.479 |

