# substitution: is timing worth more without a flat clean grid? (H6)

> Same problems as `multidate` (2024-01-17, 2024-04-17, 2024-07-17, 2024-10-16; start hours 0/6/12/18 UTC), candidate DCs restricted to Frankfurt, Warsaw, California. Hypothesis fixed before running: Ours' gain over B3 is larger without Oslo (hydro) and Paris (nuclear), whose CI barely changes within a day.

## location metric

|     ε | DCs                                |   n |   gain vs B3 mean % |   share ≥5 % |   value of waiting vs A1 mean % |   saving vs B3 kg (mean) |   R3 capture | paired: larger without flat grid   |   sign-test p |
|------:|:-----------------------------------|----:|--------------------:|-------------:|--------------------------------:|-------------------------:|-------------:|:-----------------------------------|--------------:|
| 0.001 | all DCs                            | 192 |              1.0997 |       0.0938 |                          0.7956 |                   0.019  |       0.7066 |                                    |           nan |
| 0.001 | only Frankfurt, Warsaw, California | 191 |              5.0076 |       0.2135 |                          4.6156 |                   0.7746 |       0.7751 | 96/128                             |             0 |
| 0.005 | all DCs                            | 192 |              1.27   |       0.0833 |                          1.0147 |                   0.0272 |       0.7241 |                                    |           nan |
| 0.005 | only Frankfurt, Warsaw, California | 191 |              4.9019 |       0.2031 |                          4.3734 |                   0.7842 |       0.7931 | 96/131                             |             0 |
| 0.02  | all DCs                            | 192 |              1.7584 |       0.1094 |                          1.5724 |                   0.0717 |       0.761  |                                    |           nan |
| 0.02  | only Frankfurt, Warsaw, California | 191 |              5.3382 |       0.2396 |                          3.7692 |                   0.9598 |       0.8497 | 96/139                             |             0 |
| 0.06  | all DCs                            | 192 |              2.8947 |       0.1927 |                          2.441  |                   0.2848 |       0.8627 |                                    |           nan |
| 0.06  | only Frankfurt, Warsaw, California | 191 |             11.1252 |       0.349  |                          2.7994 |                   2.8715 |       0.9414 | 109/153                            |             0 |

## brown metric

|     ε | DCs                                |   n |   gain vs B3 mean % |   share ≥5 % |   value of waiting vs A1 mean % |   saving vs B3 kg (mean) |   R3 capture | paired: larger without flat grid   |   sign-test p |
|------:|:-----------------------------------|----:|--------------------:|-------------:|--------------------------------:|-------------------------:|-------------:|:-----------------------------------|--------------:|
| 0.001 | all DCs                            | 192 |             32.833  |       0.4271 |                          2.0136 |                   0.0321 |       0.3168 |                                    |      nan      |
| 0.001 | only Frankfurt, Warsaw, California | 173 |             28.076  |       0.4167 |                          4.5706 |                   0.5016 |       0.715  | 47/87                              |        0.5203 |
| 0.005 | all DCs                            | 192 |             33.6806 |       0.4479 |                          1.9963 |                   0.1493 |       0.2622 |                                    |      nan      |
| 0.005 | only Frankfurt, Warsaw, California | 173 |             30.4686 |       0.4531 |                          4.2696 |                   0.6782 |       0.6167 | 55/90                              |        0.0446 |
| 0.02  | all DCs                            | 192 |             37.6008 |       0.4792 |                          2.1065 |                   0.7367 |       0.273  |                                    |      nan      |
| 0.02  | only Frankfurt, Warsaw, California | 173 |             34.5368 |       0.4792 |                          3.6052 |                   1.5408 |       0.6137 | 64/95                              |        0.0009 |
| 0.06  | all DCs                            | 192 |             42.2603 |       0.5521 |                          2.3845 |                   2.698  |       0.4061 |                                    |      nan      |
| 0.06  | only Frankfurt, Warsaw, California | 173 |             41.78   |       0.5729 |                          2.8254 |                   4.6716 |       0.875  | 81/106                             |        0      |
