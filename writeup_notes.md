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
| Abstract | Problem, method, headline finding: *where* you run dominates; *when* you transfer is second-order (≈2 % mean, up to 35 % in a predictable regime) | `results/multidate/multidate.md` |
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

Position: CWM [2] does temporal compute shifting for one DAG in one DC; LinTS [3] does temporal
data-transfer shifting with deadlines but no compute; CASPER [4] and Google's CICS [5] do spatial or
spatio-temporal placement without DAG precedence; Let's Wait Awhile [6] and CarbonScaler [7] do
temporal shifting of jobs. A 2025 Kubernetes study [8] also finds that regional CI differences
dominate spatio-temporal savings, which matches our finding and should be cited as agreement, not
contradiction. Claim novelty for **the shared deadline between transfer timing and DAG scheduling,
with the theory (Props. 1–3) explaining when waiting pays**, not for "first to combine everything".

1. J. Aslan, K. Mayers, J. G. Koomey, and C. France, "Electricity intensity of internet data
   transmission: Untangling the estimates," *J. Ind. Ecol.*, vol. 22, no. 4, pp. 785–798, 2018.
2. *CWM: Carbon-aware workflow mapping*, Euro-Par 2026 (base paper, `cwm.pdf`) — fill in authors
   from the PDF. Its strong NP-completeness result supports our complexity statement.
3. E. Rodrigues, J. Goldverg, and T. Kosar, "Carbon-aware temporal data transfer scheduling across
   cloud datacenters," arXiv:2506.04117, 2025. **[verify]**
4. A. Souza *et al.*, "CASPER: Carbon-aware scheduling and provisioning for distributed web
   services," *Proc. IGSC*, 2023. **[verify]**
5. A. Radovanović *et al.*, "Carbon-aware computing for datacenters," *IEEE Trans. Power Syst.*,
   vol. 38, no. 2, 2023. **[verify]**
6. P. Wiesner *et al.*, "Let's wait awhile: How temporal workload shifting can reduce carbon
   emissions in the cloud," *Proc. ACM/IFIP Middleware*, 2021. **[verify]**
7. W. A. Hanafy *et al.*, "CarbonScaler: Leveraging cloud workload elasticity for optimizing carbon
   efficiency," *Proc. ACM SIGMETRICS*, 2024. **[verify]**
8. "A user-centric Kubernetes-based architecture for green cloud computing," arXiv:2509.13325,
   2025. **[verify]** authors
9. Also check: "Carbon-aware end-to-end data movement" (Kosar group, 2024, arXiv:2406.09650)
   **[verify]**; Schweisgut, Benoit, Robert, Meyerhenke, "Carbon-aware workflow scheduling with
   fixed mapping and deadline constraint," 2025 **[verify]**; WfCommons for the DAG instances;
   Energy-Charts / ENTSO-E and CAISO for the CI data (web-link format).

## 4. Figure and table set

| # | File | Message |
|---|---|---|
| Fig. 5.1 | `results/fig_heatmap.png` | Phase diagram: DC and wait chosen, gain vs B3 (location) |
| Fig. 5.2 | `results/multidate/fig_multidate.png` | Same picture across 12 months × 4 start hours |
| Fig. 5.3 | `results/fig_sensitivity.png` | κ, bandwidth, ε, forecast noise as gain over B3 |
| Fig. 5.4 | `results/fig_attenuation.png` | Prop. 3: measured vs harmonic attenuation |
| Fig. 5.5 | `results/fig_pareto.png` | Network vs compute trade-off at one problem |
| Table 5.1 | `results/multidate/multidate.md` (location table) | Ours vs B1–B5, A1, A2 over the year |
| Table 5.2 | `results/headline.md` | Headline incl. C1 (equal solver budget) |
| Appendix | `fig_*_brown.png`, brown tables | Brown metric and why it is secondary |

## 5. Plan after mid-term (for the timeline chapter)

1. Re-run every experiment with the fixed solver (`./reproduce_multidc.sh`, ≈ 13 h) and compare with the
   pre-fix results (`results/pre_fix_solver/`).
2. Noise control for the multi-date waiting gains: 3 seeds + C1 on the problems where Ours beats
   B3 by ≥ 5 %.
3. Switch the default ε to the justified value; repeat sensitivity on several dates.
4. Optional: CI-weighted inner objective (CWM minimises brown kWh, not carbon), consumption-based CI
   (imports), an India region, battery storage.
5. Literature review completed and novelty statement finalised.
