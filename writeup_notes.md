# Write-up notes: mid-term report (CSD493)

Working notes for turning the codebase into the report. Numbers marked *(pre-fix)* come from the
solver build with the `mapper.cpp` out-of-bounds read; replace them after the re-run.
References marked **[verify]** were found by a quick search: read each paper before citing it.

## 1. Chapter map (follows `Report Format_midterm.docx`)

Template rules: chapter-numbered equations "(2.1)"; figure captions **below** and table captions
**above**, both numbered by chapter and referred to in the text before they appear; IEEE references
in order of appearance; page numbers bottom centre; front page + declaration as in the template.

| Chapter | Content | Source in repo |
|---|---|---|
| Abstract | Problem, method, headline finding: space and time are substitutes: clean grids are flat, so where-to-run dominates (+1.8 % for joint search when a flat clean grid is reachable); without one, joint optimisation pays 3× more (5.3 %, p = 8·10⁻⁶) and a theory-derived rule gets 85 % of it with ≤ 4 solver calls | `finalized_extension.md` §14 |
| 1 Introduction | Bulk scientific workflows, geo-distributed DCs, the shared-deadline tension | `finalized_extension.md` §2 |
| 2 Related work | Temporal shifting, spatial shifting, carbon-aware data transfer, carbon-aware workflow scheduling (CWM) — see §3 below | below |
| 3 Model & theory | Formulation (§3.1–3.7), Props. 1–3, Corollary 2a, remark on existence, complexity | `finalized_extension.md` §3 |
| 4 Methodology | Algorithm (§4), baselines & ablations (§8), CI data pipeline, experiment design (grid, headline, sensitivity, multi-date) | `finalized_extension.md` §4, §7, §8; `data/public_ci/README.md` |
| 5 Initial results | Phase diagram, multi-date study, sensitivity, Prop. 3 check, Pareto | §4 below |
| 6 Timeline / plan after mid-term | §5 below | — |
| 7 Limitations | Threats to validity | `finalized_extension.md` §13 |
| References | IEEE | §3 below |
| Appendix | Reproduction (`reproduce_multidc.sh`), parameter table, solver bug write-up | README §6 |

## 2. Parameter justification

**ε_net (network energy intensity).** Aslan *et al.* estimate 0.06 kWh/GB for 2015 (core + fixed
access networks) and find the intensity halving roughly every 2 years since 2000 [1]. Extrapolating
that trend gives ≈ 0.06 / 2^(9/2) ≈ **0.003 kWh/GB for 2024**; the extrapolation is an assumption,
not a measurement. Our default 0.02 kWh/GB corresponds to about 2018. Recommendation:

- report **ε = 0.005 kWh/GB** as the default (between the extrapolated value and older estimates);
- keep the full sweep 0.001–0.06 and state that under marginal accounting network energy is
  nearly load-independent, so temporal network shifting would save little (our network gains are an
  upper bound, `finalized_extension.md` §11.1);
- effect on the result *(pre-fix, multi-date, location metric)*: mean gain over B3 is 1.0 % at
  ε = 0.001, 1.3 % at 0.005, 2.2 % at 0.02 and 3.9 % at 0.06.

**κ (seconds per CWM time unit) = 120 s.** CWM's instances have intervals of about 30 units; we map
one interval to one hour of CI. State this as a calibration and show the sweep (gain over B3,
brown metric, eager1000, 1 TB, α = 2: 23 % at 240 s, 4 % at 120 s, 0 % at 60 s *(pre-fix)*).

**Bandwidth 1 Gbps, η = 0.95; budget mapping f = 0.2 (small cluster).** Parameters, swept or fixed
as in `finalized_extension.md` §3.2 and §3.5.

## 3. Related work (draft; IEEE style)

Position: CaWoSched [3] and CWM [2] do temporal compute shifting for one DAG in one DC; LinTS [4]
and [5] shift data transfers in time (and space) under deadlines but do not schedule the compute;
CASPER [6] and Google's CICS [7] do spatial or spatio-temporal placement without DAG precedence;
Let's Wait Awhile [8] and CarbonScaler [9] shift or scale independent jobs in time. A 2025
Kubernetes study [10] also finds that regional CI differences dominate spatio-temporal savings,
which matches our finding and should be cited as agreement, not contradiction. Claim novelty for **the shared deadline between transfer timing and DAG scheduling,
with the theory (Props. 1–3) explaining when waiting pays**, not for "first to combine everything".

Status: authors, titles and venues below were checked against the arXiv / publisher listings
(13 Nov 2026). Still read each paper before citing a specific claim from it; items marked
**[check]** have a detail the listings did not settle.

1. J. Aslan, K. Mayers, J. G. Koomey, and C. France, "Electricity intensity of internet data
   transmission: Untangling the estimates," *J. Ind. Ecol.*, vol. 22, no. 4, pp. 785–798, 2018.
   (Online 2017; 0.06 kWh/GB for 2015, halving about every 2 years.)
2. D. Schweisgut, A. Benoit, Y. Robert, and H. Meyerhenke, "Carbon-aware mapping and scheduling for
   deadline-constrained workflows," arXiv:2605.27652, 2026 — the CWM base paper (`cwm.pdf`).
   **[check]** whether to cite the Euro-Par 2026 proceedings version instead. Its strong
   NP-completeness result supports our complexity statement (§3.8).
3. D. Schweisgut, A. Benoit, Y. Robert, and H. Meyerhenke, "Carbon-aware workflow scheduling with
   fixed mapping and deadline constraint," in *Proc. 54th Int. Conf. Parallel Processing (ICPP)*,
   2025 (arXiv:2507.08725) — CaWoSched, CWM's predecessor (code in `code_cawosched/`).
4. E. Rodrigues, J. Goldverg, and T. Kosar, "Carbon-aware temporal data transfer scheduling across
   cloud datacenters," arXiv:2506.04117, 2025 — LinTS: transfer timing as an LP under deadlines.
5. J. Goldverg, H. Jamil, E. Rodriguez, and T. Kosar, "Carbon-aware end-to-end data movement,"
   arXiv:2406.09650, 2024 — temporal, spatial and overlay shifting of transfers.
6. A. Souza, S. Jasoria, B. Chakrabarty, A. Bridgwater, A. Lundberg, F. Skogh, A. Ali-Eldin,
   D. Irwin, and P. Shenoy, "CASPER: Carbon-aware scheduling and provisioning for distributed web
   services," in *Proc. 14th Int. Green and Sustainable Computing Conf. (IGSC)*, 2023, pp. 67–73,
   doi: 10.1145/3634769.3634812.
7. A. Radovanović *et al.*, "Carbon-aware computing for datacenters," arXiv:2106.11750, 2021.
   **[check]** it was submitted to *IEEE Trans. Power Syst.*; take volume/pages from IEEE Xplore
   if it was published there, otherwise cite the arXiv version.
8. P. Wiesner, I. Behnke, D. Scheinert, K. Gontarska, and L. Thamsen, "Let's wait awhile: How
   temporal workload shifting can reduce carbon emissions in the cloud," in *Proc. 22nd Int.
   Middleware Conf.*, 2021, doi: 10.1145/3464298.3493399.
9. W. A. Hanafy, Q. Liang, N. Bashir, D. Irwin, and P. Shenoy, "CarbonScaler: Leveraging cloud
   workload elasticity for optimizing carbon-efficiency," *Proc. ACM Meas. Anal. Comput. Syst.
   (POMACS)*, vol. 7, no. 3, art. 57, Dec. 2023 (presented at SIGMETRICS 2024),
   doi: 10.1145/3626788.
10. M. Zanotto, L. Vicentini, R. Vreto, F. Lumpp, D. Braga, and S. Fiore, "A user-centric
    Kubernetes-based architecture for green cloud computing," arXiv:2509.13325, 2025 — finds that
    regional CI differences dominate spatio-temporal savings (agrees with our result).
11. Data and tools (IEEE web-link format, add access dates): WfCommons (DAG instances),
    Energy-Charts public power API (Fraunhofer ISE; ENTSO-E data), CAISO "Today's Outlook" fuel-source
    history, IPCC AR5 WG3 Annex III (life-cycle emission factors).

## 4. Figure and table set

| # | File | Message |
|---|---|---|
| Fig. 5.1 | `results/fig_heatmap.png` | Phase diagram: DC and wait chosen, gain vs B3 (location) |
| Fig. 5.2 | `results/multidate/fig_multidate.png` | Same picture across 12 months × 4 start hours |
| Fig. 5.3 | `results/fig_sensitivity.png` | κ, bandwidth, ε, forecast noise as gain over B3 |
| Fig. 5.4 | `results/fig_attenuation.png` | Prop. 3: measured vs harmonic attenuation |
| Fig. 5.5 | `results/fig_pareto.png` | Network vs compute trade-off at one problem |
| Fig. 5.6 | daily CI swing per region (to draw from `data/public_ci`) | The mechanism: clean grids are flat |
| Fig. 5.7 | `results/contention/fig_contention.png` | Queues: CI-only placement can miss deadlines; joint gain stays small |
| Table 5.3 | `results/substitution/substitution.md` | H6: no flat clean grid → 3× gain, paired test |
| Table 5.4 | `results/hetero/hetero.md` | Hardware/PUE robustness, B6 |
| Table 5.5 | `results/multidate/multidate.md` (rule + noise sections) | Rule capture; noise control vs C1 |
| Table 5.1 | `results/multidate/multidate.md` (location table) | Ours vs B1–B5, A1, A2 over the year |
| Table 5.2 | `results/headline.md` | Headline incl. C1 (equal solver budget) |
| Appendix | `fig_*_brown.png`, brown tables | Brown metric and why it is secondary |

## 5. Plan after mid-term (for the timeline chapter)

1. ~~Re-run every experiment with the fixed solver~~ done (13 Nov): no reported result changed.
2. ~~Noise control for the multi-date waiting gains~~ done: all 21 winners keep ≥ 5 % over C1.
3. Switch the default ε to the justified value; repeat sensitivity on several dates.
4. Optional: CI-weighted inner objective (CWM minimises brown kWh, not carbon), consumption-based CI
   (imports), an India region, battery storage.
5. Literature review completed and novelty statement finalised.
