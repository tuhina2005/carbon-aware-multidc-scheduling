# Final-submission plan (13 → 23 Nov 2026)

Deliverables: final report (CSD493 template), presentation / viva, code repository, paper-style
write-up. Compute: overnight runs on the Mac (≈ 8 h/night, lid open, plugged in).

## 1. Diagnosis

The current model is *uncontended* and *homogeneous*: every DC has the same hardware and is always
free. Then "send the data now to the DC with the cleanest grid" (B3) is near-optimal by
construction, and the joint optimiser adds ≈ 2 % (location metric, 12 dates). That result is
correct and stays in the report, but it is the **baseline regime**, not the whole story.

Real systems break both assumptions, and both are exactly where joint (where × when × how)
decisions should matter:

- **Heterogeneous hardware.** The CWM cluster file already has 6 processor types whose
  speed-per-watt differs ≈ 3.4× (PE1 vs PE5). A clean grid with old hardware can emit more than a
  dirtier grid with efficient hardware: *the greenest grid is not the greenest DC*.
- **Contention.** Clean regions attract load, so the greenest DC often has a queue. Waiting for a
  queue to drain costs deadline exactly like waiting for a green network, so the deadline tension
  becomes three-way (network timing × queue × compute schedule).

## 2. Thesis of the final work

> Under a shared deadline, *where* to run dominates *when* to transfer in uncontended,
> homogeneous settings (theory + 576-problem year-long study). Once DCs differ in hardware
> efficiency or face contention, CI-only placement fails and the joint spatiotemporal optimiser
> recovers the loss; a cheap theory-derived rule captures most of that benefit with a fraction
> of the solver calls.

Every claim is tested with the controls already in place (B1–B5, A1, A2, C1 equal-budget control,
multiple seeds, both metrics, ε sweep). **Hypotheses below are fixed before running; all outcomes
are reported, including null ones.**

## 3. Work items

| ID | Item | Hypothesis / purpose | Effort |
|---|---|---|---|
| W0 | Finish fixed-solver re-run of the current model (`run_chunks.sh` 1–5) | Baseline regime; pre- vs post-fix comparison | running |
| W1 | **Heterogeneous DCs**: per-DC cluster mixes (efficient / standard / legacy) from the 6 processor types; per-DC power model, budgets and HEFT reference | H1: B3 (CI-only) loses ≥ 10 % vs Ours in a substantial share of problems when efficiency and CI disagree; B5 (compute-aware) closes part of the gap | 1 day |
| W2 | **Contention**: per-DC, time-varying queue delay q_d(t) (diurnal, local business hours, scaled by a contention level ρ; the cleanest DCs most contended). Compute starts at arrival + q_d(arrival) | H2: as ρ grows, B3 degrades or becomes infeasible; Ours' gain over B3 grows with ρ and comes from both DC choice and transfer timing (A1 vs A2 split) | 1 day |
| W3 | **Source DC variation**: Frankfurt, Warsaw, California as data origins | H3: waiting pays more from sources with strong daily CI swings (California, Frankfurt) than flat ones (Warsaw), as Prop. 3 predicts | config only |
| W4 | **Theory-guided rule** ("Rule"): decide DC and wait from cheap features (Prop. 1/3: τ vs slack, forecast CI amplitude, queue) with ≤ 3 solver calls | H4: Rule reaches ≥ 80 % of Ours' gain over B3 at ≤ 10 % of its solver calls | 1 day |
| W5 | **Forecast-robust variant**: wait only when the forecast saving exceeds a margin scaled by forecast error | H5: removes the σ = 0.5 losses vs B3 while keeping most σ = 0 gains | ½ day |
| W6 | Theory: extend Prop. 1 / Cor. 2a to queue delays; derive the Rule's decision boundary | Rule is justified, not ad hoc | ½ day |
| W7 | Figures, tables, provenance; freeze results; commit | — | ½ day |
| W8 | Final report, paper-style write-up, slides, README | — | 3–4 days |

Model changes are **additive and off by default**, so every existing result and cached solver
call stays valid.

## 3a. Interim findings (updated as work lands)

- **W1, smoke test (13 Nov):** processor mixes alone barely change energy: both schedulers put the
  work on the efficient processor types, which a 200-task DAG fits on. A tier is therefore
  processor mix (sets speed, so deadline slack) **plus facility PUE**. With PUE, the decision still
  rarely flips: grid CI differs ≈ 5× between the clean and the other grids, realistic PUE at most
  2×, so only close calls between the two clean grids (Oslo vs Paris) can change. Expected outcome
  for H1: **mostly null**: "location dominance is robust to realistic facility efficiency", and
  where it is not, the efficiency-aware heuristic B6 suffices. W1 is cut to 2 seasons (Jan: Oslo
  greenest; Jul: Paris greenest) and effort moves to **W2 (contention)**, the lever that can
  genuinely make timing and placement interact.

- **Compute budget (13 Nov):** overnight runs are not possible every night, so the remaining
  compute is cut to fit short windows: final multi-date results use 4 seasonal dates (Jan, Apr,
  Jul, Oct; the pre-fix 12-date run showed every season behaves alike, and those 12-date results
  stay in the appendix), and W1 uses one start hour (06 UTC). All runs are resumable and pause
  safely when the lid closes. Remaining compute ≈ 6–7 h in total.

- **W1 result (13 Nov, 96 problems):** as predicted. Location metric, Ours vs B3: homogeneous
  2.0 %, aligned 2.8 %, opposed 1.9 %, **mixed 9.1 %** (a third of problems ≥ 5 %); vs B6 only
  1.4 % in "mixed". Hardware flips the decision only between the two clean grids, and the
  efficiency-aware heuristic recovers it. Paper claim: location dominance is robust to realistic
  hardware/PUE differences; where it is not, site efficiency is enough.
- **W2 built (13 Nov).** Diurnal queues, local business hours 09-18 (DST-aware), weights Oslo/Paris
  1.0, Frankfurt/California 0.5, Warsaw 0.25; wait = ρ·w·2 h (busy) or ρ·w·0.5 h (off);
  ρ ∈ {0, 1, 2}. New baseline B7 = send now to the greenest DC still feasible after its queue.
  Smoke (atacseq200, 1 TB, α = 2, Jul 06 UTC): ρ = 0: Ours 11.5 % over B3; ρ = 1: 6.2 % over B3
  and B7; ρ = 2: B3 misses the deadline, Ours = B7 (local). Full run: `./run_chunks.sh w2`.

- **W4 rule built and frozen (13 Nov).** R1/R3 rank every (DC, T_net) by a solver-free estimate
  (exact network carbon + E × PUE × mean CI of the L cleanest hours between compute start and D)
  and solve only the top 1 / top 3, plus one reference schedule for E. One revision, made after
  inspecting the 4-date multi-date results and justified by the theory: L = HEFT makespan M (the
  job's minimum duration) instead of the reference schedule's own length, which CWM stretches to
  fill its window. Multi-date (location metric): R3 captures **76 %** of Ours' gain over B3 with
  ≤ 4 solver calls vs 64 (pre-registered target 80 %: narrowly missed), equals Ours in 70 % of
  problems, worst case 5.5 % behind. Brown metric: 27 % (the estimate does not model green-budget
  coverage; documented limitation). The rule is now frozen; W1 and W2 are its held-out tests.
  After W2 finishes, re-run `hetero` and `contention` (cache hits, minutes) so their summaries
  include R1/R3, then session 5.

- **W2 result (13 Nov, 192 problems): H2 not supported.** Location metric, Ours vs B7 (queue-aware):
  1.7 % (ρ = 0), 1.2 % (ρ = 1), 2.1 % (ρ = 2); B3 misses the deadline in 6 % at ρ = 2. Reported as
  a null result; the scenario is not tuned further.
- **Mechanism found (13 Nov): space and time are substitutes.** Median daily CI swing (max − min)
  in 2024: Oslo 3 g, Paris 10 g, California 158 g, Frankfurt 191 g, Warsaw 232 g (gCO₂/kWh). Moving
  the job to a clean grid also moves it to a *flat* one, where timing (and queues) barely matter.
  This single fact explains the 2 % baseline gain, the W1 robustness and the W2 null.
- **H6 (fixed before running): supported.** Same 192 multi-date problems, candidate DCs restricted
  to Frankfurt/Warsaw/California (no flat clean grid). Location metric, ε = 0.02: Ours vs B3
  1.8 % → **5.3 %**, share ≥ 5 % 11 % → 24 %, value of waiting 1.6 % → 3.6 %, saving per job
  0.07 → 0.95 kg; paired sign test 96/139, p = 8·10⁻⁶. Holds at ε = 0.001 (1.1 % → 5.0 %,
  p = 1·10⁻⁸), so it does not rely on the network accounting. Rule R3 captures 85 % there.
  Report: `results/substitution/substitution.md`.
- **Rule on held-out studies:** R3 captures 55 % (W1, vs B6), 54–84 % (W2, vs B7), 85 % (H6).

- **Completion pass (13 Nov).** Decisions: W5 (forecast-robust waiting) **dropped**; the existing
  forecast-noise result (Ours falls below B3 at σ = 0.5) is reported with W5 as future work.
  W3 built small with predictions fixed before running, from measured 24 h amplitudes (PL 88,
  US-CAL 75, DE 72 g; 0.15 / 0.33 / 0.20 of mean path CI): H3a absolute waiting saving largest from
  Warsaw; H3b relative value of waiting California > Frankfurt > Warsaw. W6 theory written
  (`finalized_extension.md` §3.9). Mechanism figure `results/fig_ci_variability.png`. Reproduction
  and chunk scripts cover every study; README §6a documents studies, B6/B7 and R1/R3.

## 4. Schedule

| Day | Daytime (me) | Overnight run |
|---|---|---|
| Thu 13 | Plan; W1 implementation + tests | W0 sessions 3+4 (multi-date May–Dec) |
| Fri 14 | W0 session 5 (≈ 1.5 h); W2 implementation + tests; smoke runs | W1 + W3 experiments (4 seasonal dates × 4 hours) |
| Sat 15 | Analyse W1/W3; W4 + W5 implementation | W2 contention sweep (ρ ∈ {0, 0.25, 0.5, 1}) × sources |
| Sun 16 | Analyse W2; W6 theory; W4/W5 evaluation (mostly cache) | Buffer: extra seeds / C1 on winning cases |
| Mon 17 | W7: final figures, tables, freeze, commit | spare |
| Tue 18 – Thu 20 | W8: report draft (chapter structure from `writeup_notes.md`), paper-style draft | — |
| Fri 21 | Slides + speaker notes; repo README / reproduction check | — |
| Sat 22 – Sun 23 | Review, polish, buffer | — |

## 5. Decisions taken

- **Current computation: keep it running.** Sessions 1–2 compute the baseline regime with the
  fixed solver, which the final report needs in every plan. New features are additive, so nothing
  computed now is wasted.
- **Location metric primary**, brown secondary (unchanged).
- **ε default stays 0.02 kWh/GB in the tables for continuity, with the full sweep**; the report
  argues from the sweep and states the 2024 extrapolation (≈ 0.003).
- **Contention and hardware mixes are parametric scenarios**, stated as such (no fabricated traces);
  each sweep includes the zero / homogeneous setting, which reproduces the baseline results.
- **Not doing** (time): battery storage, DAG partitioning across DCs, a new CI-weighted CWM
  objective (documented as a limitation).
