# Project Guide: Carbon-Aware Workflow Scheduling Across Multiple Data Centres

This guide explains, in plain language, what this project does, what we added on top of the
original work, what we found, and where everything lives in the repository. For the formal
version (equations, proofs, full tables) see the final report in `report/CSD493_Final_Report.pdf`
and the technical design document `finalized_extension.md`.

---

## 1. The starting point: what CWM does

Scientific workflows (for example a genome-analysis pipeline) are made of many small tasks with
dependencies between them, a structure called a **DAG** (directed acyclic graph). Running them
uses electricity, and how "dirty" that electricity is changes hour by hour as the grid's mix of
coal, gas, wind and solar changes. This is measured as **carbon intensity (CI)**, in grams of CO₂
per kWh.

**CWM** (Schweisgut et al., "Carbon-Aware Workflow Mapping") is the scheduler we start from. Given
**one** data centre, one workflow and a deadline, it decides *which processor runs each task and
when*, so that as much of the work as possible happens during the hours when green power is
available. It lives in `code_cwm/` and is written in C++.

CWM's limitation: it assumes the job is already in one place and starts right away. It never
asks *"would this job be cleaner somewhere else?"* or *"should I wait a bit before sending it?"*

## 2. Our extension, in plain words

We let the scheduler choose between **five real data centres** in different countries:

| Data centre | Grid | 2024 average CI (gCO₂/kWh) | Character |
|---|---|---|---|
| DC_Frankfurt (where the data starts) | Germany | 320 | medium, swings a lot during the day |
| DC_Oslo | Norway | 30 | very clean, almost flat |
| DC_Paris | France | 36 | very clean (nuclear), almost flat |
| DC_Warsaw | Poland | 560 | dirty (coal), swings a lot |
| DC_California | CAISO | 196 | medium, big solar swing at midday |

The workflow's input data begins in Frankfurt. For every job the extended scheduler makes three
decisions **together**:

1. **Where** to run it: which of the five data centres.
2. **When** to send the input data over the internet (the wide-area network, WAN): now, or
   later when the network's electricity is cleaner.
3. **How** to schedule the tasks once the data arrives: this part is CWM itself, run on the
   chosen data centre.

**The catch: "deadline tension."** All three decisions share *one* deadline. Every hour spent
waiting to send the data, or transferring it, is an hour the workflow no longer has to run.
Waiting for a cleaner network can therefore force the computation into dirtier hours. Our
optimiser searches over all (data centre, send time) pairs, runs CWM on each, adds the network
carbon and the compute carbon, and keeps the cheapest that still meets the deadline.

**An analogy.** You need to bake a cake for a party at 8 pm. You can bake at home or drive to a
friend's house with a better oven. You can leave now or after rush hour. But every minute you
spend waiting or driving is a minute less for baking. Picking the friend's house, the departure
time and the baking plan *together* beats picking them one at a time.

### What else we added

| Addition | What it means |
|---|---|
| Real 2024 carbon data | Hourly CI for all five grids for the whole of 2024, built from public sources (Energy-Charts/ENTSO-E and CAISO). No paid account needed. |
| Network carbon model | Sending data costs energy (ε kWh per GB, default 0.02) at the CI along the path. Transfer time comes from the bandwidth (default 1 Gbps). |
| Fair comparisons | Seven baseline strategies (B1–B7), two ablations (A1, A2) and an equal-effort control (C1), listed in Section 3. |
| Theory | Proofs explaining *when* waiting can help and when it cannot. For example: the benefit of waiting shrinks as the transfer gets longer, following a "sinc" curve. |
| Mixed hardware (W1) | Data centres with different machines and different cooling overhead (PUE). |
| Queues (W2) | Data centres that are busy at certain hours, so jobs wait in a queue before starting. |
| Data origin (W3) | What changes when the data starts in Warsaw or California instead of Frankfurt. |
| Cheap rule (W4) | A shortcut that ranks the options using a fast estimate and runs the expensive CWM solver on only the top 1 or 3. |
| Grid-mix study (H6) | Rerunning with only the three "swinging" grids (Germany, Poland, California) to test *why* gains were small. |

## 3. The strategies we compare

"Ours" is the full joint optimiser. Every other row is a simpler strategy it is measured against.

| Name | Strategy | Why it is here |
|---|---|---|
| **Ours** | Joint search over data centre × send time, with CWM inside | the method |
| B1 | Stay in Frankfurt, run CWM | "do nothing new" |
| B2 | Greenest data centre + a standard non-carbon-aware scheduler (HEFT) | shows CWM's value |
| **B3** | Greenest data centre + CWM, send immediately | **the strongest simple rival** |
| B4 | Cheapest network option at the greenest data centre | network-only thinking |
| B5 | Lowest compute carbon, send now | compute-only thinking |
| B6 | Greenest *after* accounting for hardware efficiency | fair rival in the hardware study |
| B7 | Greenest among data centres whose queue still allows the deadline | fair rival in the queue study |
| A1 | Ours, but never wait | measures the value of *waiting* |
| A2 | Ours, but fixed to the greenest data centre | measures the value of *choosing a location* |
| C1 | B3 given the same number of solver runs as Ours | checks gains are not just luck from more tries |
| R1 / R3 | The cheap rule: solve only the top 1 or 3 ranked options | the practical shortcut |

Gains are reported as **1 − Ours/other**. A 5 % gain means Ours emits 5 % less CO₂ than that
strategy. The main metric is **location-based carbon** (energy × the grid's CI). CWM's own
"brown energy" metric is reported too, as secondary: it can rate a dirty grid as zero carbon
whenever that grid's green budget happens to cover the job.

## 4. The results, honestly

### 4.1 Headline (192 problems: 4 seasons × 4 start hours × 2 workflows × 2 data sizes × 3 deadlines)

| Ours compared with | Average CO₂ saved |
|---|---|
| B1: stay in Frankfurt | **83.9 %** |
| B2: greenest DC, ordinary scheduler | **16.1 %** |
| B3: greenest DC + CWM | **1.8 %** (at least 5 % in 11 % of problems) |

**What this means.** Moving the job to a clean data centre is the big win. Doing it with CWM
rather than an ordinary scheduler adds another 16 %. Jointly choosing the send time and location
on top of "greenest + CWM" adds a small amount on average, and a meaningful amount in about one
problem in nine. The equal-effort control C1 confirms those winners are real: the 21 problems
with at least 5 % gain still keep 11.2 % over C1.

### 4.2 Why the extra gain is small: the substitution mechanism

The cleanest grids, Norway and France, are also **flat**. Their CI barely changes during the day
(median daily swing 3 and 10 gCO₂/kWh, against 158–232 for California, Germany and Poland).
With a flat clean grid available there is nothing to gain by waiting: you just go there.
*Choosing the place and choosing the time substitute for each other.*

**We tested this directly (H6).** With only the swinging grids (Germany, Poland, California)
available, the gain over B3 rises from **1.8 % to 5.3 %**. The share of problems with at least
5 % gain rises from 11 % to 24 %, and the saving per job from 0.07 to 0.95 kg CO₂. This is
statistically significant (sign test p = 8 × 10⁻⁶) and also holds when network energy is set
almost to zero.

**Takeaway:** joint scheduling matters most in regions *without* a flat, clean grid nearby,
which describes most of the world.

### 4.3 The other studies

| Study | Result in plain words |
|---|---|
| W1 hardware | Picking "the greenest grid" fails, by 9.1 %, only when the two clean data centres have different hardware. A hardware-aware greenest choice (B6) fixes most of it; Ours is still 1.4 % better than B6. |
| W2 queues | No clear benefit beyond a queue-aware greedy choice (1.2–2.1 % vs B7). But the naïve B3 *misses the deadline* in 6 % of the busiest cases, while Ours never does. |
| W3 data origin | Waiting saves more per job when the data starts on a swinging grid (Warsaw 0.144 kg, California 0.134 kg, Frankfurt 0.076 kg). |
| W4 cheap rule | Solving only 3–4 options instead of about 64 recovers 54–85 % of the full method's gain. |
| Upper bound | We proved that *no* strategy of this kind can beat B3 by more than about 3 % year-round on these grids. Ours reaches 58–99 % of that ceiling. |
| Pre-emptive transfer | Pausing and resuming transfers adds only about +0.1 %. Not worth the complexity. |

### 4.4 One-paragraph summary

Moving workflows to the cleanest data centre removes most of their carbon, and CWM makes that
much better than an ordinary scheduler. Jointly choosing location, send time and schedule adds a
modest 1.8 % on average in Europe, because the cleanest grids there are flat. Where clean grids
fluctuate, the gain triples to 5.3 %. We explain this with theory, confirm it with a controlled
experiment, show that a cheap rule recovers most of the benefit, and bound how much any such
method could ever gain.

## 5. The data

| Data | Location | What it is |
|---|---|---|
| Hourly carbon intensity, 2024 | `cwm_multidc/data/public_ci/{DE,NO,FR,PL,US-CAL}.csv` | One row per hour, 8,784 hours (2024 is a leap year). Built from each grid's generation mix × life-cycle emission factors per fuel. |
| CI provenance | `cwm_multidc/data/public_ci/MANIFEST.json` and `README.md` | Sources, emission factors, retrieval time, file hashes and which hours were interpolated. |
| Electricity Maps (optional) | `cwm_multidc/data/electricitymaps/README.md` | How to use the paid Electricity Maps data instead. Not needed. |
| Hardware tiers | `cwm_multidc/data/clusters/efficient.json`, `legacy.json` | Processor types (speed, idle power, working power) used in the W1 hardware study. |
| Workflows (DAGs) | `code_cwm/experiments/reproduce/instances/DAGs/*.dot` | Real bioinformatics pipelines (atacseq, chipseq, eager, methylseq, bacass) at sizes from 200 to 30,000 tasks. We mainly use `atacseq200`, `eager1000`, `chipseq1000` and `methylseq1000`. |
| Green power profiles | `code_cwm/experiments/reproduce/instances/Profiles/` | The original CWM paper's profiles (used by the original reproduction only). |
| WAN example config | `cwm_multidc/example_wan_config.json` | Example bandwidth and energy settings for the network model. |

**How CI becomes a green power budget.** For each hour, the data centre's green budget is
idle power + max(0, 1 − CI/800) × 0.2 × dynamic power. Cleaner hours give CWM more "green" power
to work with. One CWM time unit is 2 minutes (30 units per hour).

## 6. Repository structure

```
submission/
├── PROJECT_GUIDE.md          ← this file
├── README.md                 short entry point and licences (run instructions: cwm_multidc/README.md §6, §6a)
├── finalized_extension.md    full technical design, theory, threats to validity, final results (§14)
├── FINAL_PLAN.md             decision log: what we planned, decided and why
├── writeup_notes.md          notes for the paper-style write-up
│
├── code_cwm/                 ORIGINAL CWM (C++) — the single-data-centre solver
│   ├── code/
│   │   ├── app/solve_cwm.cpp       command-line solver our Python code calls
│   │   ├── app/heft_mapping.cpp    HEFT baseline scheduler
│   │   ├── lib/algorithms/mapper.cpp  core CWM algorithm (we fixed a memory over-read here)
│   │   ├── lib/data_structure/dag.*   DAG data structure
│   │   └── build.sh                builds the binaries into code_cwm/code/deploy/
│   └── experiments/          the original paper's reproduction (DAGs, profiles, notebook)
│
├── code_cawosched/           CaWoSched, a competitor from the original paper (lightly patched, see its README)
│
├── cwm_multidc/              OUR EXTENSION (Python)
│   ├── data_loader.py        loads CI data, builds the data-centre topology, hardware tiers, queues
│   ├── wan_model.py          network transfer time, energy and carbon
│   ├── profile_shifting.py   shifts a DC's power budget so CWM starts when the data arrives
│   ├── cwm_runner.py         runs the C++ solver, caches results (keyed on inputs + solver hash)
│   ├── optimizer.py          the joint search ("Ours"), baselines B1–B7, A1/A2/C1, rule R1/R3
│   ├── experiments.py        every study as a subcommand (grid, headline, multidate, hetero, ...)
│   ├── plots.py              turns result CSVs into the markdown tables and figures
│   ├── scripts/
│   │   ├── fetch_public_ci.py      downloads and builds the 2024 CI data
│   │   ├── fetch_ci_data.py        optional Electricity Maps fetcher
│   │   ├── compare_results.py      compares results before and after the solver fix
│   │   └── preemptive_transfer.py  the pause-and-resume transfer analysis
│   ├── tests/                118 automated tests (models, optimiser, cache, invariants on results)
│   ├── data/                 see Section 5
│   └── results/              see Section 7
│
├── report/                   final report (CSD493 format)
│   ├── CSD493_Final_Report.docx / .pdf
│   ├── build_report.js, content_a.js, content_b.js, lib.js, refs.js, labels.js  — report source
│   ├── make_schematics.py    draws the architecture and timeline figures
│   └── figures/
│
├── setup.sh                  builds CWM + CaWoSched and creates the Python venv
├── check.sh                  checks the setup without running anything
├── reproduce.sh              reproduces the ORIGINAL CWM paper's experiments
├── reproduce_multidc.sh      reproduces ALL of our extension's results (~8–10 h; "quick" ≈ 1.5 h)
├── run_chunks.sh             the same, split into ~1-hour sessions that can be resumed
├── quick_run.sh              setup + original reproduction in one go
├── requirements.txt / requirements.lock.txt   Python dependencies (exact versions in .lock)
└── LICENSES/                 licences for the code and the workflow data
```

### How the pieces fit together

```
2024 CI data ──► data_loader ──► topology (5 DCs, budgets, hardware, queues)
                                          │
                        optimizer: for each (DC, send time T_net)
                                          │
              wan_model: arrival time + network CO₂
                                          │
     profile_shifting: cut the DC's budget to start at arrival, deadline shrinks to D′
                                          │
         cwm_runner ──► solve_cwm (C++) ──► schedule + compute CO₂   (cached)
                                          │
                 pick the cheapest feasible option = "Ours"; also compute B1–B7, A1, A2, C1, R1, R3
                                          │
                experiments.py writes *_evals.csv ──► plots.py writes *.md tables + figures
```

## 7. Where each result lives

All under `cwm_multidc/results/`. Each study folder has `*_evals.csv` (every evaluation, one row
per method per problem), `*_summary.csv` (gains), `*.md` (readable tables) and `ci_source.json`
(exact data dates, solver hash and git commit used).

| Folder / file | Study |
|---|---|
| `headline.md`, `grid_gains.md`, `sensitivity_summary.csv`, `fig_*.png` (top level) | single-date (17 Apr 2024) studies: headline, data-size × deadline grid, sensitivity to bandwidth, time step and forecast error |
| `multidate/` | **main result**: 4 seasons, 192 problems, plus the noise control (C1) |
| `substitution/` | H6: only the swinging grids (DE/PL/US-CAL) |
| `hetero/` | W1: mixed hardware and PUE |
| `contention/` | W2: queues at busy data centres |
| `sources/` | W3: data starting in Frankfurt, Warsaw or California |
| `synthetic/` | early development runs on made-up CI data; **not** used for conclusions |
| `fig_ci_variability.png` | the daily CI swing of each grid (the mechanism figure) |
| `pre_vs_post_fix.md` | proof that fixing the solver bug did not change the conclusions |
| `ci_source.json` | provenance of the top-level results |

## 8. How to reproduce

```bash
./setup.sh
```

```bash
./check.sh
```

```bash
./reproduce_multidc.sh quick
```

```bash
.venv/bin/python -m unittest discover -s cwm_multidc/tests -t .
```

`quick` builds the solver, runs the tests and the single-date studies, then makes the plots
(about 1.5 h). Use `./reproduce_multidc.sh` with no argument for everything, or
`./run_chunks.sh 1 | 2 | 3 | w1 | w2 | w3 | 5` to run it in short resumable sessions
(`./run_chunks.sh status` shows progress). Results are cached, so an interrupted run resumes
where it stopped.

## 9. Things worth knowing (threats and fixes)

- **Two bugs were found and fixed during the project.** (1) A memory over-read in CWM's
  `mapper.cpp` made results occasionally non-deterministic. (2) The result cache was saving
  failed solver runs. Both are fixed, both have regression tests, and everything was rerun.
  `pre_vs_post_fix.md` and report Section 4.5 document the effect: no conclusion changed.
- **India (Mumbai) is left out of the real-data runs**: no free hourly data source was found.
- **Carbon intensity is "life-cycle, production-based"**: it counts the emissions of what a grid
  generates, not imports. This is standard, but other datasets may differ slightly. The method
  does not depend on the data source.
- **We kept the strongest baseline (B3)** even though it makes our average gain look small.
  Removing it would overstate the method; the honest framing is *when and why* joint scheduling
  helps.
