# Finalized Research Extension: Complete Reference Document

## 1. BASE PAPER

**Title:** "CWM: Carbon-Aware Workflow Mapping" (Euro-Par, 2026)

**What CWM does:**
- Schedules a DAG workflow on heterogeneous processors within a **single** data center.
- Exploits **temporal** variation in green power (e.g., solar peaks at noon) to shift tasks to low-carbon time intervals.
- Uses a green-power-budget model: each time interval $I_j$ has a budget $\mathcal{G}_j$. Power consumption exceeding $\mathcal{G}_j$ is "brown" carbon cost.
- Objective: minimize total brown energy = $\int_0^D \max(0, \mathcal{P}_t - \mathcal{G}_j) \, dt$.
- Constraint: makespan $\leq D$ (deadline).
- Algorithm: HEFT-based mapping + DP-based processor selection + local search. Heuristic (NP-hard problem).
- Implementation: C++ with open-source code.

**What CWM does NOT model:**
- No multiple data centers (single cluster only).
- No geographic/spatial carbon variation.
- No WAN or data transfer.
- No network carbon.
- No battery/energy storage.
- Data is assumed to already exist on the platform.

---

## 2. OUR EXTENSION: "The Deadline Tension Model"

**Title:** "Balancing Green Data Movement and Green Compute: Joint Spatiotemporal Scheduling for Deadline-Constrained DAG Workflows"

**Core Idea:**
A massive (Terabyte-scale) DAG workflow is generated at a Source DC. It can be transferred to and executed at any of several geographically distributed Execution DCs with different time-varying carbon profiles. The scheduler jointly decides:
1. **WHERE** to execute (which DC — spatial optimization)
2. **WHEN** to transfer the data (temporal network optimization)
3. **HOW** to schedule the tasks (temporal compute optimization, handled by CWM)

**The Novel "Tension":**
These decisions share a single global deadline $D$. Waiting for the WAN to become "green" before transferring data saves network carbon but steals deadline from CWM, potentially forcing compute into brown hours. The optimizer must find the globally optimal balance.

**Novelty Claim:**
No existing paper models the shared-deadline tension between carbon-aware data movement timing and carbon-aware DAG scheduling. CWM does temporal compute only; LinTS does temporal data transfer only; CASPER/Google CIC do spatial placement without DAGs. Our work is the first to combine all four dimensions (spatial DC selection + temporal network shifting + temporal compute shifting + DAG precedence constraints) under a shared deadline.

---

## 3. MATHEMATICAL FORMULATION (All fixes applied)

### 3.1 Sets
- $\mathcal{D}$: Candidate execution DCs. **$d_s \in \mathcal{D}$ always** (source DC is a candidate).
- $\mathcal{P}_d$: Heterogeneous processors at DC $d$.
- $\mathcal{J}_d$: Time intervals at DC $d$ (typically hourly).

### 3.2 Parameters
- $G = (V, E, \omega, c)$: DAG workflow. $\omega(v)$ = computational work, $c(v_i, v_j)$ = inter-task data.
- $\Delta$: Input data volume. Moving data is only possible if $\Delta \le B_{\text{eff}}\,(D - M)$, and the benefit of *delaying* the transfer shrinks as $\tau = \Delta/B_{\text{eff}}$ approaches the 24 h period of the CI signal (Prop. 3). At 1 Gbps the interesting range is about 0.1–3 TB; 10 TB (23.4 h) is generally infeasible to move within the deadline.
- $D$: Global end-to-end deadline.
- $B_d$: nominal WAN bandwidth from $d_s$ to DC $d$ (fixed parameter, default **1 Gbps**); effective rate $B_{\text{eff}} = \eta B_d$ with $\eta = 0.95$.
- $\kappa$: seconds per CWM time unit (default 120 s, i.e. 30 units = 1 h = one CI interval). Compute energy scales linearly with $\kappa$ while network energy does not, so $\kappa$ is a sensitivity parameter, not a constant of nature.
- $\mathcal{G}_{d,j}$: Green power budget at DC $d$ during interval $I_j$ (CWM's native format).
- $\text{CI}_{d,j}$: Carbon intensity at DC $d$ during interval $I_j$ (gCO₂/kWh). Used for unit conversion.
- $\epsilon_{\text{net}}$: Network energy intensity (kWh/GB, e.g., 0.02).
- $\text{CI}^{\text{net}}_{s,d}(t) = \frac{\text{CI}_{d_s}(t) + \text{CI}_d(t)}{2}$: WAN carbon intensity (endpoint average method).

### 3.3 Decision Variables
1. $d \in \mathcal{D}$: Execution DC (discrete, enumerated).
2. $T_{\text{net}} \in [0, T_{\text{net}}^{\max}(d)]$: Transfer start time (continuous; searched on the breakpoint set of Prop. 2).
3. $\mu(v), \sigma(v)$: Task-to-processor mapping and start times (CWM's internal variables).

### 3.4 Derived Quantities
- $\tau_d = \Delta / B_{\text{eff}}$ (0 if $d = d_s$).
- $T_{\text{arrival}}(d, T_{\text{net}}) = \lceil (T_{\text{net}} + \tau_d)/\kappa \rceil$ CWM units (rounded up: compute never starts before the data has arrived).
- $D'(d, T_{\text{net}}) = D - T_{\text{arrival}}$: Effective deadline for CWM.
- $M$ = HEFT makespan of the DAG on DC $d$'s cluster (the CWM paper's reference makespan; deadlines are $D = \lceil\alpha M\rceil$). The critical path is *not* used: CWM essentially never schedules below HEFT's makespan.
- $T_{\text{net}}^{\max}(d) = \kappa (D - M) - \tau_d$: latest start that leaves $D' \ge M$.

### 3.5 Objective
$$\min_{d, T_{\text{net}}} \left[ \text{NetCarbon}(d, T_{\text{net}}) + \text{CompCarbon}(d, T_{\text{net}}) \right]$$

**Network Carbon** (gCO₂):
$$\text{NetCarbon} = \epsilon_{\text{net}}\,\Delta \cdot \frac{1}{\tau_d}\int_{T_{\text{net}}}^{T_{\text{net}}+\tau_d} \text{CI}^{\text{net}}_{s,d}(t)\,dt
= \epsilon_{\text{net}} \cdot \hat B \cdot \sum_{j} \text{CI}^{\text{net}}_{s,d,j} \cdot \text{overlap}(I_j, [T_{\text{net}}, T_{\text{net}} + \tau_d))$$
with $\hat B = B_{\text{eff}}/8$ in **GB/s** (the earlier version multiplied by $B_d$ in Gbit/s, which is off by a factor of 8). Units: kWh/GB · GB/s · gCO₂/kWh · s = gCO₂.

**Compute Carbon.** `solve_cwm --per-interval` returns, per interval of the shifted and truncated profile, the excess energy $E_j^{\text{exc}}$ and the total energy $E_j^{\text{tot}}$ (W × units). With $k(\cdot) = \kappa/3.6\times10^{6}$ converting W·unit to kWh:
- *Brown* (CWM's own objective, primary): $\text{CompCarbon}^{\text{brown}} = \sum_j k(E_j^{\text{exc}})\,\text{CI}_{d,j^*+j}$.
- *Marginal location-based* (secondary): $\text{CompCarbon}^{\text{loc}} = \sum_j k(E_j^{\text{tot}} - P_{\text{idle}}|I_j|)\,\text{CI}_{d,j^*+j}$.

Caveat: the green budget is itself derived from CI, so the brown metric weights CI roughly quadratically, and it is zero for any DC that stays under budget whatever its grid CI. It measures "brown energy beyond a notional green allocation, priced at grid-average CI", not physical emissions. The location-based metric is reported alongside it for that reason.

**Budget mapping** (identical for all DCs): $\mathcal{G}_{d,j} = P_{\text{idle}} + \max(0, 1 - \text{CI}_{d,j}/800)\cdot f\cdot P_{\text{dyn}}$, with $f = 0.2$ (small) / $0.4$ (large). The floor $\mathcal{G} \ge P_{\text{idle}}$ is what makes Prop. 1 hold.

### 3.6 Constraints
1. $T_{\text{arrival}} \leq D - M_{\min}(d)$ (feasibility check).
2. $\sigma(v) \geq T_{\text{arrival}}$ for all source tasks (no compute before data arrives).
3. Standard CWM precedence and processor non-overlap constraints.
4. $\max_v(\sigma(v) + \text{exec\_time}(v)) \leq D$ (global deadline).

### 3.7 Critical Implementation Detail: Profile Shifting
CWM assumes time starts at $t=0$. When the DAG starts at $T_{\text{arrival}}$, the green power profile must be shifted:
1. Find interval $j^*$ containing $T_{\text{arrival}}$.
2. First CWM interval = remainder of $j^*$ with duration $e_{j^*} - T_{\text{arrival}}$ and budget $\mathcal{G}_{d,j^*}$.
3. Subsequent CWM intervals = $j^*+1, j^*+2, \ldots$
4. Truncate when cumulative duration reaches $D'$ (`truncate_profile`). CWM integrates cost over the *whole* profile, idle power included, so without truncation the cost would depend on the leftover horizon.
5. The CI profile is shifted and truncated with the same operations, so the per-interval CI stays aligned with CWM's per-interval energy by construction.

### 3.8 Formal Properties

Let $C^*_d(a)$ be the *optimal* compute carbon for arrival unit $a$, and $f_d(T) = \text{NetCarbon}_d(T) + C^*_d(T_{\text{arrival}}(T))$.

**Assumption A (idle covered).** $\mathcal{G}_{d,j} \ge P_{\text{idle}}$ for all $d, j$ (guaranteed by the budget mapping).

**Proposition 1 (monotone compute).** Under A, $C^*_d(a)$ is non-decreasing in $a$.
*Proof.* A schedule feasible for arrival $a_2$ (all tasks in $[a_2, D)$) is feasible for $a_1 \le a_2$, since the absolute end $D$ is the same. Under A, idle power never exceeds the budget, so a schedule's brown energy depends only on its busy periods, not on the window $[a, D)$. Hence the feasible set only shrinks and the cost of each schedule is unchanged. ∎
This is the formal content of the *deadline tension*: waiting can lower NetCarbon but can never lower $C^*$. **The CWM heuristic violates Prop. 1 empirically** (compute carbon drops in about 19% of consecutive arrival steps on our grid). Comparisons must therefore control for best-of-N selection over heuristic noise (baseline C1).

**Proposition 2 (network breakpoints).** $\frac{d}{dT}\text{NetCarbon}_d(T) = \frac{\epsilon\Delta}{\tau_d}\big(\text{CI}^{\text{net}}(T+\tau_d) - \text{CI}^{\text{net}}(T)\big)$ is piecewise constant for piecewise-constant hourly CI. So NetCarbon is piecewise linear, and its minimum over $[0, T^{\max}]$ lies in $\{0, T^{\max}\} \cup \{kh\} \cup \{kh - \tau_d\}$. Note that the start time need not lie on a CI boundary: either the start or the arrival does, or it is an endpoint. This holds for NetCarbon only; the total has no such guarantee.

**Proposition 3 (attenuation of temporal network shifting).** For $\text{CI}^{\text{net}}(t) = \bar c + A\cos(\omega t)$ with $\omega = 2\pi/P$, $P = 24$ h,
$$\text{NetCarbon}(T) = \epsilon\Delta\Big[\bar c + A\,\mathrm{sinc}\big(\tfrac{\omega\tau}{2}\big)\cos\big(\omega(T + \tfrac{\tau}{2})\big)\Big],\quad \mathrm{sinc}(x) = \tfrac{\sin x}{x}.$$
The most that waiting can save is $2\epsilon\Delta A|\mathrm{sinc}(\pi\tau/P)|$. This is zero at $\tau = P$, and waiting is feasible only if $\tau \le \kappa(D-M)$. The gain therefore peaks at intermediate data volumes and vanishes for very large ones. Synthetic DE↔NO data: the maximum saving from waiting falls from 32% (τ = 0.25 h) to 29% (2.3 h), 9.5% (8 h) and 3.4% (23.4 h).

**Proposition 4 (existence).** The feasible set $[0, T^{\max}]$ is compact and non-empty iff $\tau_d \le \kappa(D - M)$. NetCarbon is continuous. $T_{\text{arrival}}(T)$ uses a ceiling, which is left-continuous and lower semicontinuous, and $C^*$ is non-decreasing, so $f_d$ is lower semicontinuous and attains its minimum.

**Complexity.** The problem contains CWM ($d = d_s$, $\Delta = 0$) and is therefore strongly NP-hard.

---

## 4. ALGORITHM

**Joint Spatiotemporal Grid Search + CWM Heuristic:**

```
best_carbon ← ∞

For each candidate DC d ∈ D:
  Precompute M_HEFT(d)   (HEFT makespan; deadline D = ceil(α·M_HEFT))
  If d = d_s: evaluate only T_net = 0
  
  For each T_net in {0, T_max} ∪ {k·h} ∪ {k·h − τ_d} within [0, T_net_max(d)]   (Prop. 2):
    T_arrival = ceil((T_net + τ_d)/κ)  (or 0 if d = d_s)
    D' = D - T_arrival
    If D' < M_HEFT: skip
    
    shifted_profile = truncate(shift_profile(G_d, T_arrival), D')
    
    NetC = compute_network_carbon(T_net, Δ, B_d, CI_net_sd)
    
    CWM_result = call_CWM_binary(DAG, processors(d), shifted_profile, D')
    CompC = Σ_j kWh(E_j) · CI_{d, j*+j}       (per-interval, both metrics)
    
    total = NetC + CompC
    If total < best_carbon:
      best_carbon = total
      best_solution = (d, T_net, CWM_result)

Return best_solution
```

**Properties (corrected):**
- The outer enumeration is exact **only for NetCarbon** (Prop. 2): the breakpoint set contains its minimiser. It is *not* exact for the total. $T_{\text{net}}$ is continuous and $C_d(\cdot)$ is a heuristic, non-monotone black box, so no optimality guarantee holds.
- The inner variables $(\mu, \sigma)$ are solved heuristically by CWM; the overall algorithm is a heuristic.
- Complexity: $O(|\mathcal{D}| \cdot N_T \cdot |\text{seeds}| \cdot t_{\text{CWM}})$. **Measured** $t_{\text{CWM}}$ is 1.1 s (atacseq200), 8 s (eager1000) and 33 s (methylseq4000), not 0.1 s. Evaluations are cached and run in parallel (8 workers). In practice $N_T$ is 2–35 per DC.

---

## 5. OPTIONAL EXTENSION: BATTERY (from Yu et al. 2023)

**Concept:** DCs may have battery storage that charges during green hours and discharges during brown hours, effectively augmenting the green power budget.

**Simplified Model (pre-committed discharge):**
1. Charge battery from excess green power: $c_j = \min(c_{\max}, \max(0, \mathcal{G}_{d,j} - P_{\text{base}}))$.
2. Discharge into brownest intervals: augment $\mathcal{G}'_{d,j} = \mathcal{G}_{d,j} + d_j^{\text{battery}}$.
3. Pass augmented profile $\mathcal{G}'_d$ to CWM.

**Status:** Optional experimental parameter. Does NOT require modifying CWM. Sub-optimal but bounded. Include as an experiment, not a core contribution.

---

## 6. EXPLICIT EXCLUSIONS

| Feature | Why excluded |
|---------|-------------|
| **Multi-path WAN routing** | Optimizing which fiber path saves ~0.3% of total carbon. Not worth the implementation cost. |
| **DAG partitioning across DCs** | Creates a massive MILP. Too complex for an undergraduate project. |
| **Batch scheduling / congestion** | Requires traffic engineering and capacity modeling. Destroys the clean grid search. |
| **Variable bandwidth** | Introduces MINLP nonlinearity ($\Delta/b$). |
| **Re-implementing CWM in Python** | CWM is complex C++ (DP + HEFT + local search). Would take 3 months and run 100x slower. |

---

## 7. DATASETS

| Data | Source | Details |
|------|--------|---------|
| **DAG workflows** | WfCommons (WFGen) | atacseq, bacass, chipseq, eager. 50–5000 tasks. |
| **Carbon intensity** | Electricity Maps | Hourly CI for Norway, France, Germany, California, Poland, India. |
| **Network CI** | Derived | Endpoint average: $\text{CI}^{\text{net}}(t) = (\text{CI}_{\text{source}}(t) + \text{CI}_{\text{dest}}(t))/2$. |
| **WAN bandwidth** | Fixed parameter | Default: 1 Gbps. Sensitivity: 0.1–10 Gbps. |
| **Input data size $\Delta$** | Fixed parameter | Default: 1 TB. Sensitivity: 100 GB – 10 TB. |

---

## 8. BASELINES

| ID | Name | Description |
|----|------|-------------|
| B1 | CWM-Local | Run CWM at source DC. No spatial optimization. |
| B2 | Greenest-DC + HEFT | Pick DC with lowest avg CI, transfer immediately, run HEFT (no temporal optimization). |
| B3 | Greenest-DC + CWM | Pick DC with lowest avg CI, transfer immediately, run CWM. |
| B4 | Network-Optimized | Pick transfer time that minimizes network carbon, ignoring compute impact. |
| B5 | Compute-Optimized | Transfer immediately to every DC; pick the DC with least compute carbon (ignores network). |
| **Ours** | Joint Spatiotemporal | Full grid search over (DC, transfer time) with CWM. |
| A1 | Ours-NoWait | $T_{\text{net}} = 0$, DC chosen by total carbon: isolates *spatial* choice. |
| A2 | Ours-FixedDC | Greenest DC, $T_{\text{net}}$ chosen by total carbon: isolates *temporal network shifting*. |
| C1 | B3-bestN | B3's configuration with as many independent seed groups as Ours makes CWM calls (equal solver budget). Separates real joint gains from best-of-N selection over heuristic noise. |
| LB | Separable bound | $\min_d[\min_T \text{Net}_d + \min_T \text{Comp}_d]$ over evaluated points: a lower bound on Ours. The gap Ours − LB measures the trade-off that cannot be realised simultaneously. |

A1/A2 against B3/Ours form the 2×2 factorial over {DC by mean CI, DC by total} × {transfer now, transfer at the best time}. B2 isolates CWM's own contribution (the base paper's, not ours).

**Critical experiment:** Ours vs B3 **and** vs C1. Ties with B1/B3 are *predicted* in identifiable regimes (§10) and are reported as a phase diagram, not hidden.

---

## 9. EXPECTED OUTPUTS

1. **Pareto Front:** Network Carbon (X) vs Compute Carbon (Y). Shows B4 minimizes X but explodes Y, B5 minimizes Y but explodes X, ours finds the optimal interior point.
2. **Deadline Sensitivity:** As $D$ tightens, the algorithm transitions from "wait for green network" to "transfer immediately."
3. **Data Size Sensitivity:** As $\Delta$ grows, network carbon becomes dominant and temporal network shifting becomes critical.
4. **DC Selection Heatmap:** Which DC is selected under different (deadline, data size) combinations.

---

## 10. KNOWN RISKS

1. **The ratio of network to compute carbon is set by parameters** ($\kappa$, $\epsilon_{\text{net}}$, $B$), not measured: report sensitivity sweeps over all three. Large $\Delta$ is *not* automatically better (Prop. 3).
2. **"Greenest-DC + CWM" is near-optimal by construction when the greenest DC is also the greenest network path.** This is almost automatic under endpoint-averaged WAN CI. Expected ties:
   - Ours = B1 when compute at the source stays under budget, when $\tau > \kappa(D-M)$, or when moving the data costs more than it saves.
   - Ours = B3 when the greenest DC is also the greenest network path and the compute penalty of waiting (Prop. 1) exceeds the sinc-limited network saving (Prop. 3).
3. **CWM C++ compilation.** Getting the original binary to compile and wrapping it via Python subprocess is the main engineering risk.
4. **Profile shift bugs.** The function that shifts CWM's green power profile by $T_{\text{arrival}}$ is the most critical piece of code. If wrong, all results are wrong.

---

## 11. MODELLING ASSUMPTIONS (phrasing for the paper)

1. *Attributional network energy.* "We attribute WAN energy per transferred GB (ε_net), consistent with attributional carbon accounting. Most network energy is load-independent, so under marginal accounting temporal network shifting yields little benefit; our network-side gains are an upper bound." ε_net is swept over 0.001–0.06 kWh/GB.
2. *Asymmetric accounting.* Compute is charged marginally (idle power is covered by the budget floor) and network attributionally. We state this explicitly and report the location-based compute metric alongside.
3. *Endpoint-average WAN CI.* A modelling proxy that ignores routing and the CI of transit countries.
4. *Bulk, dedicated transfer.* Constant bandwidth, no contention, no TCP dynamics, input transferred entirely before compute starts (no per-task streaming, which would weaken the tension), and no return of output data.
5. *Identical clusters and a single workflow per DC.* This isolates the carbon signal; heterogeneity and background load are future work.
6. *CI foresight.* Decisions use CI forecasts; we evaluate decisions taken on noisy forecasts (multiplicative AR(1), σ ∈ {0.1, 0.25, 0.5}) against realised CI.
7. *Time scale κ.* Calibrated so one CWM interval (mean length 30 units in the CWM instances) equals one hour; swept over κ ∈ {60, 120, 240} s.
8. *Data.* Results with synthetic CI are for development only; final results require Electricity Maps hourly data (supported via `build_topology(ci_csv=...)`).

## 12. IMPLEMENTATION STACK

- **Language:** Python (outer loop) + CWM C++ binary (inner solver).
- **Interface:** Python generates input files → calls CWM via `subprocess` → parses output.
- **Data processing:** Pandas for Electricity Maps CSV manipulation.
- **DAG generation:** WfCommons Python library.
- **No MILP solver needed. No GPU needed.**
