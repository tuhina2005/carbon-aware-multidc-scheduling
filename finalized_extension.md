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
To our knowledge, no prior work couples carbon-aware data-transfer timing with carbon-aware DAG scheduling under one shared deadline (literature checked: report Chapter 2). CWM and CaWoSched do temporal compute only; LinTS and end-to-end data movement shift transfers but not the compute; CASPER and Google's CICS place or delay work without DAG precedence. The stronger contribution is explaining *when* the coupling matters (space and time substitute because clean grids are flat; §3.9, §14).

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
- *Marginal location-based* (**primary**): $\text{CompCarbon}^{\text{loc}} = \sum_j k(E_j^{\text{tot}} - P_{\text{idle}}|I_j|)\,\text{CI}_{d,j^*+j}$.
- *Brown* (CWM's native objective, secondary): $\text{CompCarbon}^{\text{brown}} = \sum_j k(E_j^{\text{exc}})\,\text{CI}_{d,j^*+j}$.

Why location is primary: the green budget is itself derived from CI, so the brown metric weights CI roughly quadratically, and it is **zero for any DC that stays under budget whatever its grid CI**. On the real data this makes the brown metric prefer Frankfurt (≈320 gCO₂/kWh) over Paris (≈36) for the small atacseq200 DAG, because Frankfurt's budget happens to cover it; every "100 %" brown-metric gain in the results is this effect. The brown metric measures "brown energy beyond a notional green allocation, priced at grid-average CI", not physical emissions.

**Objective mismatch (inner solver).** CWM minimises brown *energy* $\sum_j E_j^{\text{exc}}$, unweighted. Neither reported metric is CWM's objective: both weight energy by the hour's CI, and the location metric also counts energy under the budget. So the inner solver can return a schedule that is worse in carbon than plain HEFT. Observed on the real-data grid: at Frankfurt, eager1000 with α = 1.4–1.6, CWM's schedule has 24–26 % less brown energy than HEFT's (185–191 vs 250 kWh) but 3.5–4.6 % more brown carbon (89–90 vs 86 kg). B2 (HEFT) is outside Ours' search space and beats it in these rows. A CI-weighted inner objective is future work.

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

**Proposition 1 (monotone compute).** Under A, $C^*_d(a)$ is non-decreasing in $a$ for the brown metric. For the location metric it holds without A.
*Proof.* A schedule feasible for arrival $a_2$ (all tasks in $[a_2, D)$) is feasible for $a_1 \le a_2$, since the absolute end $D$ is the same. Under A, idle power never exceeds the budget, so a schedule's brown energy depends only on its busy periods, not on the window $[a, D)$. The location metric subtracts idle power by definition, so it depends only on busy periods with or without A. In both cases the feasible set only shrinks as $a$ grows and the cost of each schedule is unchanged. ∎
This is the formal content of the *deadline tension*: waiting can lower NetCarbon but can never lower $C^*$. **The CWM heuristic violates Prop. 1 empirically**: on the real-data runs, compute carbon drops in 12–18 % of consecutive arrival steps under the brown metric and 15–34 % under the location metric. Comparisons must therefore control for best-of-N selection over heuristic noise (baseline C1). On the real data every waiting gain of Ours over B3 is a *network* saving, with compute carbon flat or higher (consistent with Prop. 1), so it is not heuristic noise (single-date grid, brown metric).

**Proposition 2 (network breakpoints).** $\frac{d}{dT}\text{NetCarbon}_d(T) = \frac{\epsilon\Delta}{\tau_d}\big(\text{CI}^{\text{net}}(T+\tau_d) - \text{CI}^{\text{net}}(T)\big)$ is piecewise constant for piecewise-constant hourly CI. So NetCarbon is piecewise linear, and its minimum over $[0, T^{\max}]$ lies in $\mathcal{B} = \{0, T^{\max}\} \cup \{kh\} \cup \{kh - \tau_d\}$. Note that the start time need not lie on a CI boundary: either the start or the arrival does, or it is an endpoint.

**Corollary 2a (exact candidate set for the total).** Let $C$ be any non-decreasing function of the arrival unit (e.g. $C^*$, by Prop. 1). Then $f_d(T) = \text{NetCarbon}_d(T) + C(\lceil (T+\tau_d)/\kappa \rceil)$ attains its minimum on the finite set $\mathcal{B} \cup \{a\kappa - \tau_d : a \in \mathbb{Z}\} \cap [0, T^{\max}]$. Moreover, on any interval between consecutive points of $\mathcal{B}$ where NetCarbon is non-decreasing, only the left endpoint is needed; every arrival-unit boundary is needed only where NetCarbon is decreasing.
*Proof.* On each cell $((a-1)\kappa - \tau_d,\ a\kappa - \tau_d]$ the compute term is constant and NetCarbon is piecewise linear with kinks in $\mathcal{B}$, so the cell's minimum is at a kink or a cell endpoint; the open left end is dominated by the previous cell's right endpoint, whose compute term is no larger because $C$ is non-decreasing. Where NetCarbon is non-decreasing, moving later raises both terms. ∎
Our algorithm evaluates $\mathcal{B}$ only. It is therefore exact for NetCarbon, but for the total it can miss an optimum at an arrival-unit boundary inside a segment where NetCarbon decreases. Evaluating those boundaries as well would make the outer search exact given an exact monotone inner solver; with CWM (heuristic, non-monotone) no optimality guarantee holds either way.

**Proposition 3 (attenuation of temporal network shifting).** For $\text{CI}^{\text{net}}(t) = \bar c + A\cos(\omega t)$ with $\omega = 2\pi/P$, $P = 24$ h,
$$\text{NetCarbon}(T) = \epsilon\Delta\Big[\bar c + A\,\mathrm{sinc}\big(\tfrac{\omega\tau}{2}\big)\cos\big(\omega(T + \tfrac{\tau}{2})\big)\Big],\quad \mathrm{sinc}(x) = \tfrac{\sin x}{x}.$$
The most that waiting can save is $2\epsilon\Delta A|\mathrm{sinc}(\pi\tau/P)|$. This is zero at $\tau = P$, and waiting is feasible only if $\tau \le \kappa(D-M)$. Two readings: the *relative* saving ($2A|\mathrm{sinc}|/\bar c$) only falls as $\tau$ grows on $[0, P]$; the *absolute* saving $\propto \tau\,|\mathrm{sinc}(\pi\tau/P)| = (P/\pi)|\sin(\pi\tau/P)|$ peaks at $\tau = P/2$ (12 h, about 5 TB at 1 Gbps) and vanishes at $\tau = P$.

On the real 2024 data (window from 17 April, Frankfurt→Paris), the measured maximum relative saving falls from about 61 % (τ ≤ 1 h) to 46 % (10 h), 26 % (24 h) and 23 % (36 h), while the 24 h harmonic alone predicts 47 % → 0 at 24 h. Real CI has large non-periodic (weather) variability, so Prop. 3 is a stylised explanation of the attenuation, not a quantitative model.

**Remark (existence).** The feasible set $[0, T^{\max}]$ is non-empty iff $\tau_d \le \kappa(D - M)$, and $f_d$ attains its minimum there: the arrival unit takes finitely many values, and Corollary 2a gives a finite candidate set.

**Complexity.** The problem contains CWM's problem as the special case $d = d_s$, $\Delta = 0$, so it is at least as hard. The CWM paper proves its decision problem strongly NP-complete (already for a single processor with free ordering), so ours is **strongly NP-hard**.

### 3.9 Extensions: per-DC hardware, queues, and the theory-guided rule

**Per-DC hardware (W1).** DC $d$ has its own cluster (processor mix) with HEFT makespan $M_d$ and a facility power usage effectiveness $\mathrm{PUE}_d$. The deadline stays global, $D = \lceil \alpha M_{d_s} \rceil$ (the job's home hardware); feasibility at $d$ requires $D' \ge M_d$. Grid energy is $\mathrm{PUE}_d \times$ IT energy. If the green budget scales with facility power ($\mathcal{G}_{d,j}^{\text{fac}} = \mathrm{PUE}_d\,\mathcal{G}_{d,j}$), then facility excess $= \max(0, \mathrm{PUE}_d P - \mathrm{PUE}_d \mathcal{G}) = \mathrm{PUE}_d \max(0, P - \mathcal{G})$, so **both compute metrics scale exactly by $\mathrm{PUE}_d$** and the inner CWM problem is unchanged. Props. 1–3 hold per DC.

**Queues (W2).** DC $d$ has a queue $q_d(t) \ge 0$, piecewise constant on the hourly grid and left-closed ($q_d$ on $[h, h+1)$ is the value of hour $h$). Compute starts at $s_d(T) = \lceil (T_{\text{arr}} + q_d(T_{\text{arr}}))/\kappa \rceil$ and $D' = D - s_d(T)$.
- *Prop. 1 still holds in the start time:* $C^*_d(s)$ is non-decreasing in $s$ (same proof).
- *But the start is no longer monotone in $T$:* if the queue drops at an hour boundary, arriving just after it can start compute **earlier** than arriving just before. So waiting can now lower compute carbon too, which is the only new mechanism queues add.
- *Cor. 2a still gives an exact finite candidate set.* Hour boundaries are multiples of $30\kappa$, so every queue change coincides with an arrival-unit boundary $a\kappa - \tau_d$, already in the set. If every queue length is a multiple of $\kappa$, the start is constant within each arrival cell and the set is unchanged; otherwise each cell splits once more, at $a\kappa - \tau_d - q$, and those points must be added. (All W2 queues are multiples of $\kappa$ except the smallest Warsaw waits, 0.125 h; Warsaw is never chosen in W2.) Because $q_d$ is left-closed, a queue drop is attained at the boundary point, so the minimum exists (the lower-semicontinuity argument of the existence remark carries over).
- *Empirically* (§14) queues barely matter on the real data: the contended DCs are the clean, temporally flat grids, where a delayed start costs almost nothing.

**Why space and time substitute (the mechanism).** By Prop. 3 the value of temporal shifting at DC $d$ is bounded by its daily CI amplitude, $\approx 2 A_d$ per unit energy. Choosing $d$ by mean CI selects the lowest $\bar c_d$, and in 2024 the lowest-mean grids have the smallest amplitudes (median daily swing NO 3, FR 10 vs 158–232 gCO₂/kWh elsewhere; `results/fig_ci_variability.png`). Hence once the spatial choice is made, the temporal term is bounded by a small constant: the joint optimum differs from "greenest DC, send now" only through the network path (whose CI is the endpoint average and keeps half the *source* amplitude) and through near-ties between clean grids. Removing the flat clean grids removes that bound, which is the prediction tested by H6 (§14).

**Theory-guided rule (W4).** For candidate $(d, T)$ the rule computes
$$\hat f_d(T) = \text{NetCarbon}_d(T) + E\,\frac{\mathrm{PUE}_d}{\mathrm{PUE}_{\text{ref}}}\cdot \frac{1}{L}\sum_{\text{the } L \text{ cleanest whole hours } h \in [s_d(T), D)} \text{CI}_{d,h},$$
with $E$ the dynamic energy of one reference schedule (one solver call) and $L = \lceil M \rceil$ hours (HEFT makespan, known). It ranks all candidates by $\hat f$ and solves only the best 1 (R1) or 3 (R3).
- *Lemma (relaxation).* If the job's dynamic energy $E$ could be spread at constant power over any $L$ whole hours of the window, i.e. ignoring precedence and the budget, the minimum location-based compute carbon is exactly $E \cdot \mathrm{PUE}_d$ times the mean CI of the $L$ cleanest hours. *Proof:* minimise a sum of $L$ equal-energy slots over hours, which takes the $L$ smallest CI values. ∎ So $\hat f$ is NetCarbon (exact, Prop. 2) plus the optimum of a preemptive relaxation of the compute term.
- *Consistency with Prop. 1:* the relaxed term is non-decreasing in the start $s_d(T)$, because the window only shrinks.
- *Limits:* the relaxation ignores precedence, so it is optimistic about how much work fits into clean hours, and it models no green budget, so it is weak under the brown metric (captures 27 % there vs 76 % under the location metric).

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

## 5. BATTERY EXTENSION: NOT IMPLEMENTED (future work)

Battery storage (charge in green hours, discharge in brown hours, i.e. an augmented budget $\mathcal{G}'_{d,j}$ passed to CWM, following Yu et al. 2023) was considered but **not implemented or evaluated**. Mention it only as future work.

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
| **DAG workflows** | WfCommons instances shipped with CWM | atacseq200, eager1000 (grid, multi-date); chipseq1000, methylseq1000 (headline). |
| **Carbon intensity** | Energy-Charts (ENTSO-E) + CAISO, 2024 | Hourly production-based life-cycle CI for DE, NO, FR, PL (Energy-Charts) and US-CAL (CAISO), built by `scripts/fetch_public_ci.py` (IPCC AR5 median emission factors; storage and imports excluded; 16 CAISO hours interpolated, flagged in the CSV). India has no free hourly source, so **5 DCs** (Mumbai dropped). Electricity Maps exports can be used instead via `scripts/fetch_ci_data.py import`. |
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
8. *Data.* Final results use real 2024 hourly CI (Energy-Charts/ENTSO-E + CAISO, production-based, no imports): `experiments.py --ci-dir cwm_multidc/data/public_ci`. The earlier synthetic-CI results are kept in `results/synthetic/` for reference only.

## 12. IMPLEMENTATION STACK

- **Language:** Python (outer loop) + CWM C++ binary (inner solver).
- **Interface:** Python generates input files → calls CWM via `subprocess` → parses output.
- **Data processing:** Pandas for the hourly CI CSVs (Energy-Charts/ENTSO-E + CAISO, built by `scripts/fetch_public_ci.py`; Electricity Maps exports also supported).
- **DAG generation:** WfCommons Python library.
- **No MILP solver needed. No GPU needed.**

---

## 13. THREATS TO VALIDITY (to carry into the paper)

1. **Network accounting drives the result.** Compute is charged marginally and network attributionally (§11.1–2), so network carbon dominates totals: at 1 TB, B3's network carbon is ≈ 4.3 kg against ≈ 0.04 kg brown compute. The headline gain over B3 (brown) falls from 19 % at ε = 0.02 kWh/GB to 6 % at ε = 0.001. ε must be justified from current per-GB estimates and presented as a sweep.
2. **κ is a calibration, not a measurement.** eager1000, 1 TB, α = 2: gain over B3 (brown) is 23 % at κ = 240 s, 4 % at 120 s and 0 % at 60 s.
3. **Brown metric artefact** (§3.5): it can favour a dirtier grid. Location is the primary metric.
4. **Inner-solver objective mismatch** (§3.5): CWM minimises brown kWh, not CI-weighted carbon, so HEFT occasionally beats it on carbon.
5. **CI data.** Production-based (imports ignored, so PL and DE are likely underestimated relative to consumption-based CI); life-cycle factors are IPCC medians, not plant-specific; 16 CAISO hours interpolated; WAN CI is the endpoint average (§11.3).
6. **Temporal coverage.** The grid, headline and sensitivity runs use one date (17 April 2024). The multi-date study covers 4 seasonal dates (Jan/Apr/Jul/Oct third Wednesdays) × start hours 0/6/12/18 UTC with the fixed solver; an earlier 12-date run (pre-fix solver, identical behaviour per season) is kept for reference. W1 and W2 use Jan + Jul.
7. **Solver nondeterminism (found, fixed, results re-run).** `solve_cwm` returned different schedules for the same seed and input (e.g. 32 × 6222 and 8 × 5673 in 40 runs). Root cause, found with AddressSanitizer: a heap buffer over-read in `mapper.cpp` (6 copies of the same sweep-line loop, first hit in `CaWoMap::local_search`). When schedule events lie past the profile horizon, the loop reads `intervals[]` and `budgets[]` past their end, so the budget used beyond the horizon is whatever memory holds. The fix treats time past the horizon as having no green budget; with it, 40/40 runs agree and the sanitizers report no errors. It is inherited from the upstream CWM code. The fix is applied in `code_cwm/code/lib/algorithms/mapper.cpp` and covered by a regression test (`test_cwm_runner.TestDeterminism`); the solver cache key now includes the solver binary's SHA-256, so results from another build are never reused. All results were re-run with the fixed binary (`8a456bbb…`, recorded in each `ci_source.json`). **The fix changed none of the 294 problems of the grid, headline, sensitivity and multi-date studies**; a later audit also found that an interrupted run had cached 18 killed solver calls as failures (now never cached, regression-tested); re-running fixed one H6 problem; no value in the report's H6 table moved by more than 0.25 percentage points (same choice and total under both metrics; `results/pre_vs_post_fix.md`): the over-read only bites on rare inputs.
8. **Forecasts.** Decisions on noisy CI forecasts (σ = 0.5) can make Ours worse than B3; a forecast-robust rule (wait only when the forecast saving exceeds a margin scaled by forecast error) is future work.
8b. **Model simplifications** (§11.4–5): dedicated constant-bandwidth transfer, no output return, identical clusters, one workflow at a time, perfect CI foresight except in the forecast-noise study.
9. **Novelty claim** (§2) still needs a systematic literature search (spatio-temporal workload shifting, carbon-aware bulk data transfer, geo-distributed workflow scheduling) before it is stated as "first".
10. **Scenario parameters (W1, W2) are stylised.** Hardware tiers (processor mix + PUE 1.10/1.55/2.00) and queue models (local business hours, popularity weights, ρ ∈ {0, 1, 2}) are parametric scenarios fixed before running, not measured traces.
11. **Rule (W4).** One revision (L = HEFT makespan) was made after inspecting the multi-date results; W1, W2 and H6 are held-out tests. Its estimate is location-based, so it captures much less of the gain under the brown metric.

---

## 14. FINAL RESULTS (fixed solver; location metric, ε = 0.02 kWh/GB unless stated)

| Study | Problems | Finding |
|---|---|---|
| Multi-date baseline (4 seasons × 4 hours) | 192 | Ours vs B3 1.8 % mean (11 % of problems ≥ 5 %); vs B1 (local) 83.9 %; vs B2 (greenest + HEFT) 16.1 %; noise control: the 21 problems with ≥ 5 % keep 11.2 % over C1 (all ≥ 5 %, none ≤ 0) |
| W1 hardware (PUE + processor mix) | 96 | B3 loses 9.1 % only when the two clean grids differ in hardware ("mixed"); B6 (PUE-aware) recovers it (Ours vs B6 1.4 %). Location dominance is robust. |
| W2 contention (diurnal queues) | 192 | H2 not supported: Ours vs B7 1.2–2.1 %; B3 misses the deadline in 6 % at ρ = 2 |
| Mechanism | — | Median daily CI swing 2024: NO 3, FR 10, US-CAL 158, DE 191, PL 232 gCO₂/kWh: the cleanest grids are flat, so space and time are substitutes |
| H6: no flat clean grid (DE/PL/US-CAL) | 192 paired | Ours vs B3 1.8 % → 5.3 %, ≥ 5 % share 11 % → 24 %, saving 0.07 → 0.95 kg/job; sign test p = 8·10⁻⁶; at ε = 0.001: 1.1 % → 5.0 % (p = 1·10⁻⁸) |
| W3 data origin (all DCs as candidates) | 3 × 64 | Saved by waiting per job: Frankfurt 0.076, Warsaw 0.144, California 0.134 kg; value of waiting 1.6 / 2.1 / 2.9 %. H3a (largest absolute saving from Warsaw, the largest amplitude) supported, narrowly; H3b (relative order CA > DE > PL) partially: California highest as predicted, but Warsaw > Frankfurt |
| W4 rule R3 (≤ 4 solver calls vs ≈ 64) | — | captures 76 % (multi-date), 55 % (W1), 54–84 % (W2), 85 % (H6) of Ours' gain over the respective best heuristic |

