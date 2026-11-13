# CWM Multi-Data-Centre Extension

This package contains the core modules for extending Carbon-Aware Workflow Mapping (CWM, Euro-Par 2026) to geographically distributed multi-data-centre environments under the **Deadline Tension Model**.

| Module | Role |
| :--- | :--- |
| `profile_shifting.py` | shift a CWM profile to start at T_arrival; `truncate_profile` cuts it at D' |
| `wan_model.py` | WAN transfer time, network energy and (time-varying) network carbon |
| `cwm_runner.py` | subprocess wrapper for `solve_cwm` / `heft_mapping`, output parsing, result cache |
| `data_loader.py` | time scale, CI timeseries (Electricity Maps CSV or synthetic), CI→budget mapping, topology |
| `optimizer.py` | joint (DC, T_net) grid search + baselines B1–B5 |
| `experiments.py`, `plots.py` | experiment grid, headline comparison, figures and tables |

---

## 1. Background: The Deadline Tension Model

In single-cluster CWM, DAG workflows execute on a single platform starting at relative time $t = 0$.

In a multi-data-centre setting:
1. Massive workflow input datasets $\Delta$ (e.g. 1–10 TB) originate at a source data centre $d_s$.
2. The dataset can be transferred across wide-area networks (WAN) to any candidate execution data centre $d \in \mathcal{D}$.
3. Data transfer takes duration $\tau_{\text{net}} = \Delta / B_d$, arriving at absolute timestamp $T_{\text{arrival}} = T_{\text{net}} + \tau_{\text{net}}$.
4. Workflow compute at data centre $d$ cannot begin until $t = T_{\text{arrival}}$.
5. Compute and data transfer share a single global deadline $D$. Waiting for low-carbon hours to transfer data saves network emissions but compresses the remaining compute deadline:
   $$D'(d, T_{\text{net}}) = D - T_{\text{arrival}}$$
   which may force compute tasks into high-carbon hours.

---

## 2. Phase 2A — Profile-Shifting Module (`profile_shifting.py`)

### Schema & Semantics
CWM's C++ parser (`code_cwm/code/lib/config.cpp`) requires profile JSON files with:
- `"horizon"`: Total schedule time window (e.g. 50,000 time units).
- `"number_of_intervals"` ($N$): Total interval count.
- `"intervals"`: Array of $N+1$ non-negative strictly ascending integer boundaries $[0 = t_0, t_1, \dots, t_N = \text{horizon}]$.
- `"budgets"`: Array of $N$ green power budget values $[B_0, \dots, B_{N-1}]$.

### Shifting Operation
`shift_profile(profile, arrival_time, required_deadline=None, discretize="ceil")`
- Locates interval $j^*$ such that $t_{j^*} \le T_{\text{arrival}} < t_{j^*+1}$.
- Discards past intervals $0 \dots j^*-1$.
- Sets relative time $t'=0$ at $T_{\text{arrival}}$, retaining budget $B_{j^*}$ for the remainder of interval $j^*$.
- Shifts all subsequent interval boundaries leftward by $T_{\text{arrival}}$:
  $$\text{intervals}' = [0, t_{j^*+1} - T_{\text{arrival}}, t_{j^*+2} - T_{\text{arrival}}, \dots, \text{horizon} - T_{\text{arrival}}]$$
  $$\text{budgets}' = [B_{j^*}, B_{j^*+1}, \dots, B_{N-1}], \quad H' = \text{horizon} - T_{\text{arrival}}$$
- Validates that $H' \ge \text{required\_deadline}$ (if provided) and strictly rejects $T_{\text{arrival}} \ge \text{horizon}$.

---

## 3. Phase 2B — WAN Transfer & Emissions Model (`wan_model.py`)

### A. Mathematical Formulation & Units

| Quantity | Symbol | Standard Unit | Notes / Conventions |
| :--- | :--- | :--- | :--- |
| **Dataset Size** | $\Delta$ | Gigabytes (GB) | Default decimal convention: $1\text{ GB} = 10^9\text{ bytes} = 8\times 10^9\text{ bits}$. Binary GiB ($2^{30}\text{ bytes}$) supported via `unit_convention='binary'`. |
| **Nominal Bandwidth** | $B$ | Gbps | $1\text{ Gbps} = 10^9\text{ bits/second}$. |
| **Throughput Efficiency** | $\eta_{\text{eff}}$ | Dimensionless | In $(0.0, 1.0]$. Default $0.95$ (accounts for TCP framing, congestion, transport overhead). |
| **Effective Bandwidth** | $B_{\text{eff}}$ | Gbps | $B_{\text{eff}} = B \times \eta_{\text{eff}}$. |
| **Transfer Duration** | $\tau_{\text{net}}$ | Seconds (s) | Continuous: $\tau_{\text{net}} = \frac{\Delta_{\text{bits}}}{B_{\text{eff}}\times 10^9}$. For same-DC ($d_s == d$), $\tau_{\text{net}} = 0.0$. |
| **Arrival Timestamp** | $T_{\text{arrival}}$ | Seconds (s) | Continuous: $T_{\text{arr}}^{\text{cont}} = T_{\text{net}} + \tau_{\text{net}}$. Effective Integer: $T_{\text{arr}}^{\text{int}} = \lceil T_{\text{arr}}^{\text{cont}} \rceil$ (under `ceil` policy). |
| **Energy Intensity** | $\epsilon_{\text{net}}$ | kWh / GB | Configurable hypothesis (default $0.02\text{ kWh/GB} = 72\text{ kJ/GB}$). |
| **Network Energy** | $E_{\text{net}}$ | kWh (or Joules) | $E_{\text{net}} = \Delta_{\text{GB}} \times \epsilon_{\text{net}}$. For same-DC, $E_{\text{net}} = 0.0$. ($1\text{ kWh} = 3.6\times 10^6\text{ J}$). |
| **Carbon Intensity** | $\text{CI}^{\text{net}}(t)$ | gCO₂ / kWh | Endpoint-average: $(\text{CI}_{\text{src}} + \text{CI}_{\text{dst}})/2$, or integrated across piecewise-constant time profile. |
| **Network Emissions** | $\text{Emissions}_{\text{net}}$ | gCO₂ | $\text{Emissions}_{\text{net}} = E_{\text{net}} (\text{kWh}) \times \overline{\text{CI}}^{\text{net}} (\text{gCO}_2/\text{kWh})$. |

### B. Energy Intensity Parameter Provenance & Limitations
The parameter $\epsilon_{\text{net}} = 0.02\text{ kWh/GB}$ ($72\text{ kJ/GB}$) is frequently cited in earlier cloud sustainability literature (e.g. Aslan et al. 2018). However:
- Modern hyperscale optical backbones (e.g. Google B4, Azure WAN) report substantially lower values ($0.001 - 0.005\text{ kWh/GB}$).
- **Scientific constraint:** $\epsilon_{\text{net}}$ must be treated as a **configurable research hypothesis**, NOT established empirical truth. It is exposed in `WANConfig` to enable rigorous sensitivity analysis.

### C. Objective Compatibility: Separating Physical Dimensions
In CWM C++, the scheduler computes:
$$\text{CWM Cost} = \int \max(0, \mathcal{P}(t) - \mathcal{G}(t)) \, dt$$
where $\mathcal{P}(t)$ and $\mathcal{G}(t)$ are in Watts and time is in seconds. The returned integer is **excess brown energy in Watt × CWM time units** (Watt-seconds only if one unit = 1 s; in this project one unit = 120 s).
- **Critical rule:** The raw CWM integer is **NOT grams of CO₂**.
- Adding raw CWM output directly to network emissions in $\text{gCO}_2$ is dimensionally invalid.
- `combine_objectives()` maintains strict dimensional separation:
  - `network_energy_kwh`
  - `network_emissions_gco2`
  - `cwm_excess_brown_energy` (Watt-seconds)
  - `compute_emissions_gco2` (computed ONLY when physical calibration factors—kW/unit, hours/unit, and destination carbon intensity—are explicitly provided).

---

## 4. Usage Example

```python
import json
from cwm_multidc import (
    WANConfig,
    evaluate_wan_transfer,
    combine_objectives,
    shift_profile,
    validate_profile
)

from cwm_multidc.data_loader import TimeScale

ts = TimeScale(units_per_hour=30)  # 120 s per CWM time unit (Section 5)

# 1. Configure WAN parameters
cfg = WANConfig(
    bandwidth_gbps=1.0,
    energy_intensity_kwh_per_gb=0.02,
    throughput_efficiency=0.95,
    integer_arrival_policy="ceil"
)

# 2. Evaluate data transfer from Frankfurt to Oslo (1 TB)
wan_res = evaluate_wan_transfer(
    source_dc="DC_Frankfurt",
    dest_dc="DC_Oslo",
    data_size_gb=1000.0,
    transfer_start=0.0,
    config=cfg,
    source_ci_gco2_per_kwh=350.0,
    dest_ci_gco2_per_kwh=40.0
)

print(f"Transfer Duration: {wan_res.transfer_duration_seconds:.2f} s")
print(f"Effective Arrival: t={wan_res.effective_arrival_time_int} s")
print(f"Network Energy:    {wan_res.network_energy_kwh:.2f} kWh")
print(f"Network Emissions: {wan_res.network_emissions_gco2:.2f} gCO2")

# 3. Shift the destination power profile. shift_profile works in CWM time UNITS,
#    so convert the arrival time (seconds) first, rounding up.
#    (Use data_loader.build_topology(...).profiles(dc) for hourly-aligned profiles;
#    the original DE24s.json intervals are not real hours.)
arrival_units = ts.seconds_to_units_ceil(wan_res.arrival_time_seconds)  # 8421 s -> 71
with open("code_cwm/experiments/reproduce/instances/Profiles/small/DE24s.json") as f:
    orig_profile = json.load(f)

shifted = shift_profile(orig_profile, arrival_time=arrival_units, required_deadline=3000)

# 4. Combine objectives safely
#    (optimizer.evaluate does this per interval with hourly CI; this is the scalar form)
raw_cwm_excess_brown_energy = 355000  # Watt x CWM-units from solve_cwm
obj = combine_objectives(
    wan_result=wan_res,
    cwm_excess_brown_energy=raw_cwm_excess_brown_energy,
    dest_avg_ci_gco2_per_kwh=40.0,
    power_to_kw_factor=0.001,
    time_to_hours_factor=ts.seconds_per_unit / 3600.0,
)

print(f"Compute Emissions: {obj.compute_emissions_gco2:.2f} gCO2")
print(f"Total Emissions:   {obj.total_emissions_gco2:.2f} gCO2")
```

---

## 5. Multi-DC optimizer: model decisions

| Decision | Choice | Where |
| :--- | :--- | :--- |
| CWM time unit | 30 units = 1 h (120 s/unit); one interval per hourly CI sample | `TimeScale` |
| Clock | t = 0 at submission, aligned to a UTC hour, shared by all DCs | `Topology` |
| Budget | `G = P_idle + max(0, 1 − CI/800)·f·P_dyn`, f = 0.2 small / 0.4 large, same for every DC | `BudgetMapping` |
| Compute carbon (brown, primary) | Σ_j kWh(E_j^excess)·CI_{d,j}, per-interval excess from `solve_cwm --per-interval` | `optimizer.evaluate` |
| Compute carbon (location, secondary) | Σ_j kWh(E_j^total − P_idle·|I_j|)·CI_{d,j} (marginal, idle-free) | `optimizer.evaluate` |
| Network carbon | Δ·ε_net·mean over [T_net, T_net+τ) of (CI_src + CI_d)/2 | `wan_model` |
| Arrival | T_arr = ceil(units(T_net + τ)); D' = D − T_arr; profile shifted by T_arr and truncated to D' | `optimizer.evaluate` |
| Deadline | D = ceil(α·M), M = HEFT makespan (as in the CWM paper); candidates with D' < M skipped | `optimizer` |
| T_net grid | {0, T_max} ∪ {k·h} ∪ {k·h − τ}: contains the exact network-carbon optimum | `t_net_candidates` |
| Topology | source DC_Frankfurt (DE); NO, FR, PL, US-CAL, IN; same `small` cluster everywhere; 1 Gbps | `build_topology` |

Baselines (all but B2 are points of the joint search space, evaluated with the same solver calls):

- **B1 CWM-Local**: source DC, T_net = 0.
- **B2 Greenest-DC + HEFT**: lowest mean CI over [0, D] among DCs that can still meet the deadline, T_net = 0, plain HEFT schedule.
- **B3 Greenest-DC + CWM**: same DC, CWM.
- **B4 Network-Optimized**: greenest DC, T_net minimising network carbon (among slots CWM could schedule).
- **B5 Compute-Optimized**: T_net = 0 everywhere, the DC with least compute carbon (ties → greener DC).

Ablations and controls (2×2 factorial with B3/Ours, plus a noise control):

- **A1 Ours-NoWait**: T_net = 0, DC by total carbon (spatial choice only).
- **A2 Ours-FixedDC**: greenest DC, T_net by total carbon (temporal network shifting only).
- **C1 B3-bestN** (`Problem(equal_budget_control=True)`): B3's configuration with as many independent seed
  groups as Ours makes CWM calls. CWM is not monotone in the arrival time, so part of any gain could
  be best-of-N selection; C1 measures how much.
- **Separable bound** (`SearchResult.separable_bound`): min_d[min_T Net + min_T Comp], a lower bound on Ours.

`SearchResult.summary(metric, eps_scale)` re-derives every selection for either metric and any ε_net
without new solver calls (network carbon is linear in ε_net).

`solve_cwm` gained two opt-in flags (default output is byte-identical to the baseline):
`--per-interval` prints a second line with uint64 excess energy and a third with total energy per profile interval, and
`--heft` evaluates the HEFT schedule instead of CWM. Rebuild with `code_cwm/code/build.sh`.

**Carbon-intensity data.** Real data: `data/public_ci/` (free Energy-Charts/ENTSO-E + CAISO 2024, five regions, built by
`scripts/fetch_public_ci.py`; see its README) or `data/electricitymaps/<REGION>.csv` (one
Electricity Maps hourly export per region: DE, NO→NO-NO1, FR, PL, US-CAL→US-CAL-CISO,
IN→IN-WE; see `data/electricitymaps/README.md` and `scripts/fetch_ci_data.py`). Without
`--ci-dir`, `build_topology` uses `synthetic_ci` (diurnal solar dip + AR(1) noise, calibrated
to approximate 2024 annual means). Every result row records `synthetic_ci` and `ci_source`,
and every figure and table states the source in its footer.

## 6. Running experiments

**One command:** `./reproduce_multidc.sh` (build, tests, every experiment, plots; ~12–14 h) or
`./reproduce_multidc.sh quick` (~1.5 h, skips the multi-date study). To split the full run into
sessions of at most ~3 h that can be stopped and restarted safely, use `./run_chunks.sh 1` … `5`
(`./run_chunks.sh status` shows progress). Individual steps:

```bash
python -m cwm_multidc.experiments grid       # 2 DAGs x 5 data sizes x 7 deadlines (sweeps are slices)
python -m cwm_multidc.experiments headline   # 4 DAGs x 2 start hours x 2 deadlines, 3 seeds, + C1 control
python -m cwm_multidc.experiments sensitivity # kappa {60,120,240 s}, bandwidth {0.5..10 Gbps}, forecast error
python -m cwm_multidc.experiments multidate --ci-dir DIR  # 12 dates x 4 start hours (real CI only)
python -m cwm_multidc.experiments multidate-noise --ci-dir DIR  # 3 seeds + C1 where Ours beats B3 by >= 5 %
python -m cwm_multidc.experiments plot       # results/fig_*.png, results/*.md, results/multidate/
```

Figures use the **location** metric (primary); `fig_*_brown.png` are the brown-metric copies.
Multi-date outputs (third Wednesday of each month of 2024 × start hours 0/6/12/18 UTC) go to
`results/multidate/`.

Add `--ci-dir cwm_multidc/data/public_ci` (or an Electricity Maps directory) to `grid`/`headline`/
`sensitivity` for real CI.
Experiment start hours (UTC hour of day) are then placed on `--ci-start` (default 2024-04-17,
a mid-April Wednesday); a directory missing any region is an error, never a silent mix.

Solver results are cached in `results/cache.jsonl`, so the commands can be resumed and re-run cheaply.
The cache key includes the SHA-256 of `solve_cwm`, so results from another solver build are never
reused. Each results folder's `ci_source.json` records the CI source, the solver hash and the git
commit; the tables print a warning when the deployed solver differs from the one that produced them.
Every summary is also written for ε_net ∈ {0.001, 0.005, 0.02, 0.06} kWh/GB (column `eps_kwh_per_gb`).
Forecast experiments decide on CI × exp(AR(1) noise) and score the chosen points on the actual CI
(the CWM schedule itself is recomputed on the actual profile).

## 6a. Extension studies, baselines and the rule

Each study is a subcommand of `cwm_multidc.experiments` (add `--ci-dir cwm_multidc/data/public_ci`),
writes `<study>_summary.csv` / `<study>_evals.csv` and a Markdown report into its own folder under
`results/`, and was specified (hypothesis included) before it was run. Summary in
`finalized_extension.md` §14; decision log in `FINAL_PLAN.md`.

| Subcommand | Folder | Question | Key setting |
|---|---|---|---|
| `multidate` | `results/multidate/` | Does the picture hold across seasons and times of day? | Jan/Apr/Jul/Oct × 0/6/12/18 UTC (`--dates all`: 12 months) |
| `multidate-noise` | `results/multidate/` | Are the ≥ 5 % wins solver luck? | 3 seeds + equal-budget control C1 |
| `substitution` | `results/substitution/` | H6: is timing worth more without a flat clean grid? | candidate DCs DE/PL/US-CAL, paired with `multidate` |
| `hetero` | `results/hetero/` | W1: do hardware / PUE differences break CI-only placement? | tiers in `data/clusters/` (efficient / standard / legacy, PUE 1.10 / 1.55 / 2.00) |
| `contention` | `results/contention/` | W2: do DC queues make joint decisions matter? | diurnal queues, local business hours, ρ ∈ {0, 1, 2} |
| `sources` | `results/sources/` | W3: does the value of waiting follow the source grid's daily amplitude (Prop. 3)? | data originating in Frankfurt / Warsaw / California |

Baselines added for these studies (all are points of Ours' search space, so Ours ≤ them by
construction; `tests/test_result_invariants.py` checks this on every saved summary):

- **B6** efficiency-aware greenest DC: lowest PUE × mean CI, send now.
- **B7** queue-aware greenest DC: greenest DC that still meets the deadline after its queue, send now.
- **R1 / R3** theory-guided rule (`optimizer.rule_rank`): ranks every (DC, T_net) by exact network
  carbon + E × PUE × mean CI of the M cleanest hours after compute can start (one reference solver
  call for E), then solves only the best 1 / 3. ≤ 2 / ≤ 4 solver calls instead of ≈ 64.

`results/fig_ci_variability.png` shows the mechanism behind the results: the cleanest grids
(Oslo hydro, Paris nuclear) are also the flattest, so once the job moves there, timing barely matters.

**Solver output.** `solve_cwm` writes progress lines prefixed `[DEBUG]` to stderr; the runner
ignores them. They are left in on purpose: the solver cache and every results folder are keyed on
the exact binary (SHA-256 in `ci_source.json`), so changing the C++ code, even to remove log lines,
would invalidate all cached results and require a full re-run.

## 7. Automated Tests

```bash
python -m unittest discover -s cwm_multidc/tests -t .
```

The suite covers unit tests, a hand-computed check of the carbon arithmetic, a brute-force check of
the T_net grid, and end-to-end runs of the real `solve_cwm` binary on WfCommons DAGs.
