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
- $\Delta$: Input data volume (**must be massive, e.g., 1–10 TB**, otherwise network carbon is negligible).
- $D$: Global end-to-end deadline.
- $B_d$: WAN bandwidth from $d_s$ to DC $d$ (fixed parameter, default **1 Gbps**).
- $\mathcal{G}_{d,j}$: Green power budget at DC $d$ during interval $I_j$ (CWM's native format).
- $\text{CI}_{d,j}$: Carbon intensity at DC $d$ during interval $I_j$ (gCO₂/kWh). Used for unit conversion.
- $\epsilon_{\text{net}}$: Network energy intensity (kWh/GB, e.g., 0.02).
- $\text{CI}^{\text{net}}_{s,d}(t) = \frac{\text{CI}_{d_s}(t) + \text{CI}_d(t)}{2}$: WAN carbon intensity (endpoint average method).

### 3.3 Decision Variables
1. $d \in \mathcal{D}$: Execution DC (discrete, enumerated).
2. $T_{\text{net}} \in [0, T_{\text{net}}^{\max}(d)]$: Transfer start time (discretized, e.g., 15-min grid).
3. $\mu(v), \sigma(v)$: Task-to-processor mapping and start times (CWM's internal variables).

### 3.4 Derived Quantities
- $T_{\text{arrival}}(d, T_{\text{net}}) = T_{\text{net}} + \Delta / B_d$ (0 if $d = d_s$).
- $D'(d, T_{\text{net}}) = D - T_{\text{arrival}}$: Effective deadline for CWM.
- $T_{\text{net}}^{\max}(d) = D - \Delta/B_d - M_{\min}(d)$: Upper bound on transfer start time. $M_{\min}(d)$ = critical path length on DC $d$'s fastest processors.

### 3.5 Objective
$$\min_{d, T_{\text{net}}} \left[ \text{NetCarbon}(d, T_{\text{net}}) + \text{CompCarbon}(d, T_{\text{net}}) \right]$$

**Network Carbon:**
$$\text{NetCarbon} = \epsilon_{\text{net}} \cdot B_d \cdot \sum_{j \in \text{covered}} \text{CI}^{\text{net}}_{s,d,j} \cdot \text{overlap}(I_j, [T_{\text{net}}, T_{\text{net}} + \Delta/B_d])$$

**Compute Carbon:**
CWM returns excess energy per interval $\{E_j^{\text{excess}}\}$. Convert to gCO₂:
$$\text{CompCarbon} = \sum_{j} E_j^{\text{excess}} \cdot \text{CI}_{d, j+j^*}$$
where $j^*$ is the interval offset from the profile shift.

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
4. Truncate when cumulative duration reaches $D'$.

---

## 4. ALGORITHM

**Joint Spatiotemporal Grid Search + CWM Heuristic:**

```
best_carbon ← ∞

For each candidate DC d ∈ D:
  Precompute M_min(d)
  If d = d_s: evaluate only T_net = 0
  
  For each T_net in {0, Δt, 2Δt, ...} up to T_net_max(d):
    T_arrival = T_net + Δ/B_d  (or 0 if d = d_s)
    D' = D - T_arrival
    If D' < M_min(d): skip
    
    shifted_profile = shift_profile(G_d, T_arrival)
    
    NetC = compute_network_carbon(T_net, Δ, B_d, CI_net_sd)
    
    CWM_result = call_CWM_binary(DAG, processors(d), shifted_profile, D')
    CompC = convert_to_gCO2(CWM_result, CI_d, T_arrival)
    
    total = NetC + CompC
    If total < best_carbon:
      best_carbon = total
      best_solution = (d, T_net, CWM_result)

Return best_solution
```

**Properties:**
- Exact enumeration of outer variables $(d, T_{\text{net}})$. No solution quality lost from decomposition.
- Heuristic for inner variables $(\mu, \sigma)$ via CWM. Overall algorithm is a heuristic.
- Complexity: $O(|\mathcal{D}| \cdot N_T \cdot \text{CWM\_time})$. For 10 DCs × 96 time slots × 0.1s per CWM call ≈ **96 seconds total**.

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
| B5 | Compute-Optimized | Transfer immediately (maximize CWM deadline flexibility). |
| **Ours** | Joint Spatiotemporal | Full grid search over (DC, transfer time) with CWM. |

**Critical experiment:** Ours vs B3. If we don't beat "Greenest-DC + CWM" by ≥5-10%, the contribution is weak.

---

## 9. EXPECTED OUTPUTS

1. **Pareto Front:** Network Carbon (X) vs Compute Carbon (Y). Shows B4 minimizes X but explodes Y, B5 minimizes Y but explodes X, ours finds the optimal interior point.
2. **Deadline Sensitivity:** As $D$ tightens, the algorithm transitions from "wait for green network" to "transfer immediately."
3. **Data Size Sensitivity:** As $\Delta$ grows, network carbon becomes dominant and temporal network shifting becomes critical.
4. **DC Selection Heatmap:** Which DC is selected under different (deadline, data size) combinations.

---

## 10. KNOWN RISKS

1. **Network carbon may be too small.** If $\Delta < 100$ GB, network carbon is <1% of total. Must use TB-scale data.
2. **"Greenest-DC + CWM" might be near-optimal.** Bashir et al. (2024) showed simple policies often suffice. Must demonstrate ≥5-10% improvement.
3. **CWM C++ compilation.** Getting the original binary to compile and wrapping it via Python subprocess is the main engineering risk.
4. **Profile shift bugs.** The function that shifts CWM's green power profile by $T_{\text{arrival}}$ is the most critical piece of code. If wrong, all results are wrong.

---

## 11. IMPLEMENTATION STACK

- **Language:** Python (outer loop) + CWM C++ binary (inner solver).
- **Interface:** Python generates input files → calls CWM via `subprocess` → parses output.
- **Data processing:** Pandas for Electricity Maps CSV manipulation.
- **DAG generation:** WfCommons Python library.
- **No MILP solver needed. No GPU needed.**
