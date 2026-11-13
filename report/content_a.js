// Front matter and Chapters 1-3.
const L = require("./lib.js");
const { d, P, bullets, numbered, H1, H2, H3, EQ, STMT, FIG, TAB, FONT } = L;
const R = "../cwm_multidc/results";

const center = (text, size = 24, opts = {}) => new d.Paragraph({ alignment: d.AlignmentType.CENTER,
  spacing: { after: opts.after ?? 160, before: opts.before ?? 0 },
  children: [new d.TextRun({ text, font: FONT, size, bold: opts.bold, italics: opts.italics })] });

const TITLE = "Balancing Green Data Movement and Green Compute: Joint Spatiotemporal Scheduling of Deadline-Constrained Workflows Across Data Centres";

function titlePage() {
  return [
    center(TITLE, 36, { bold: true, before: 1200, after: 600 }),
    center("Project Report Submitted in Partial Fulfilment of the Requirements for the Degree of", 24),
    center("Bachelor of Technology", 28, { bold: true }),
    center("in", 24),
    center("Computer Science and Engineering", 28, { bold: true, after: 600 }),
    center("Submitted by", 24, { italics: true }),
    center("<Name of the Student 1>: (Roll No. <XXXXXXXX>)", 24),
    center("<Name of the Student 2>: (Roll No. <XXXXXXXX>)", 24),
    center("<Name of the Student 3>: (Roll No. <XXXXXXXX>)", 24, { after: 600 }),
    center("Under the Supervision of", 24, { italics: true }),
    center("<Supervisor Name>", 24, { bold: true }),
    center("<Designation>, Department of Computer Science and Engineering", 24, { after: 900 }),
    center("Department of Computer Science and Engineering", 26, { bold: true }),
    center("<Month, Year>", 24),
  ];
}

function declaration() {
  return [
    new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, children: [new d.TextRun({ text: "Declaration", font: FONT })] }),
    P("I/We declare that this written submission represents my ideas in my own words and where others' ideas or words have been included, I have adequately cited and referenced the original sources. I also declare that I have adhered to all principles of academic honesty and integrity and have not misrepresented or fabricated or falsified any idea/data/fact/source in my submission. I understand that any violation of the above will be cause for disciplinary action by the University and can also evoke penal action from the sources which have thus not been properly cited or from whom proper permission has not been taken when needed."),
    P(""),
    ...[1, 2, 3].map(() => P("Name of the Student: ________________    Signature and Date: ________________",
      { align: d.AlignmentType.LEFT, spacing: { before: 240 } })),
  ];
}

function abstract() {
  return [
    new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new d.TextRun({ text: "Abstract", font: FONT })] }),
    P("Large scientific workflows are increasingly run in whichever data centre (DC) has the cleanest electricity. When their input is terabytes, the data must first cross a wide-area network (WAN), and the transfer, the wait for a greener network, and the carbon-aware schedule of the workflow itself all share one deadline. This project extends CWM, a recent carbon-aware mapper for deadline-constrained DAG workflows in a single DC, to multiple DCs: it jointly chooses *where* to run, *when* to start the transfer, and *how* to schedule the tasks."),
    P("We formalise this *deadline tension* and prove its structure: optimal compute carbon can only grow when the data arrives later (Prop. 1), network carbon is piecewise linear with an exact finite set of candidate start times (Prop. 2, Cor. 2a), and the benefit of delaying a transfer decays as a sinc function of its duration (Prop. 3). We implement the joint search on top of the CWM C++ solver, evaluate it on real 2024 hourly carbon-intensity data for five regions with close to 1,000 problem instances, and test every claim against fixed-in-advance hypotheses, seven baselines, ablations, and an equal-solver-budget control. While doing so we found and fixed a memory bug in the CWM solver that made its output nondeterministic."),
    P("The central finding is that **space and time are substitutes**. The cleanest grids (Norwegian hydro, French nuclear) are also the flattest: their carbon intensity varies by only 3–10 gCO₂/kWh within a day, against 158–232 gCO₂/kWh elsewhere. Moving a job there removes almost all value of waiting, so the joint optimiser improves on \"greenest DC, transfer now\" by only 1.8 % on average, and this result is robust to hardware differences, data-centre queues and the network-energy assumption. The same mechanism predicts when joint optimisation does pay: when no flat clean grid is available, its gain triples to 5.3 % (13× larger absolute saving, paired sign test p = 8·10⁻⁶). Finally, a rule derived from the theory captures 76–85 % of the joint optimiser's gain with at most four solver calls instead of about 64."),
    P("**Keywords:** carbon-aware computing, workflow scheduling, geo-distributed data centres, temporal shifting, data transfer, deadline constraints.", { align: d.AlignmentType.LEFT }),
  ];
}

function toc() {
  return [
    new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new d.TextRun({ text: "Contents", font: FONT })] }),
    new d.TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  ];
}

function ch1() {
  return [
    H1("Introduction"),
    P("Data centres consume a growing share of the world's electricity, and the carbon emitted per kilowatt-hour depends strongly on where and when that electricity is drawn. Carbon-aware computing exploits this variation in two ways: *temporal shifting* runs flexible work when the local grid is cleanest [cite:waitawhile,carbonscaler,cics], and *spatial shifting* runs it where the grid is cleanest [cite:casper,k8s]. CWM [cite:cwm] brings temporal shifting to scientific workflows: it maps and schedules a deadline-constrained DAG onto a heterogeneous cluster so that as much work as possible falls into periods of high green-power availability."),
    P("CWM, like its predecessor CaWoSched [cite:cawosched], assumes the workflow already sits in the DC that runs it. For the large scientific workflows targeted here this is often false: the input is generated or stored at one site, may be terabytes in size, and must be moved before computation can start. Moving 1 TB over a 1 Gbit/s link takes about 2.3 hours, the network itself consumes energy [cite:aslan], and the grid along the path also varies in time [cite:lints,e2e]."),
    H2("1.1", "The deadline tension"),
    P("When the transfer and the computation share one end-to-end deadline, the decisions interact. Waiting for a cleaner network can save transfer carbon, but every minute spent waiting is a minute less for CWM to place the workflow's tasks into green hours. Choosing a distant, cleaner DC lengthens the transfer and shortens the compute window further. We call this the *deadline tension*. No single-dimension technique resolves it: transfer schedulers ignore the compute that follows, workflow schedulers ignore where the data comes from, and placement systems ignore DAG precedence and the timing of the transfer."),
    H2("1.2", "Research questions"),
    ...numbered([
      "**RQ1.** How should the joint problem (where, when, how) be formulated, and what structure does it have that an algorithm can exploit?",
      "**RQ2.** On real grid data, how much carbon does joint optimisation save compared with simple strategies such as \"send the data now to the greenest DC\"?",
      "**RQ3.** *When* does joint optimisation matter, and why? Which properties of grids, hardware, contention or data origin decide it?",
      "**RQ4.** Can the theory be turned into a cheap rule that captures most of the benefit without an exhaustive search?",
    ]),
    H2("1.3", "Contributions"),
    ...bullets([
      "**Model and theory.** A formulation of joint DC selection, transfer timing and DAG scheduling under a shared deadline, with proofs that compute carbon is monotone in the arrival time (Prop. 1), that network carbon has an exact finite candidate set (Prop. 2, Cor. 2a), and that the value of waiting decays with transfer duration (Prop. 3); extensions to heterogeneous hardware and DC queues (Chapter 3).",
      "**Implementation.** A Python system around the CWM C++ solver that shifts and truncates power profiles, evaluates every candidate exactly, and reports two carbon metrics, seven baselines, two ablations and an equal-solver-budget control; resumable, cached and covered by 114 automated tests (Chapter 4).",
      "**A solver bug fix.** AddressSanitizer [cite:asan] located a heap buffer over-read in the CWM mapper that made its output depend on uninitialised memory; we fixed it and showed that no reported result changed (Section 4.5).",
      "**Findings.** On real 2024 data the cleanest grids are also the flattest, so location and timing are substitutes: joint optimisation adds little when a flat clean grid is reachable, robustly so, and triples its gain when none is (Chapter 6).",
      "**A theory-guided rule** that ranks candidates without the solver and captures 76–85 % of the joint optimiser's gain with at most four solver calls (Sections 4.4 and 6.9).",
    ]),
    H2("1.4", "Organisation"),
    P("Chapter 2 reviews related work. Chapter 3 formulates the problem and develops the theory. Chapter 4 describes the system and algorithms, Chapter 5 the data and experiments, and Chapter 6 the results. Chapter 7 discusses implications and threats to validity, and Chapter 8 concludes."),
  ];
}

function ch2() {
  return [
    H1("Related Work"),
    H2("2.1", "Carbon-aware workflow scheduling"),
    P("HEFT [cite:heft] is the standard list scheduler for DAGs on heterogeneous processors and is the reference makespan used to define deadlines in this line of work. CaWoSched [cite:cawosched] shifts the tasks of a workflow with a fixed HEFT mapping into greener intervals under a deadline, and shows the problem is polynomial on one processor and NP-hard from two. CWM [cite:cwm] removes the fixed-mapping assumption and jointly maps and schedules the tasks, with a HEFT-based construction, dynamic-programming processor selection and local search; it proves the decision problem strongly NP-complete. Both operate on a single cluster whose green-power budget varies over time; neither models data movement or multiple sites. Our work uses CWM as its inner solver."),
    H2("2.2", "Temporal shifting"),
    P("Wiesner *et al.* [cite:waitawhile] quantified how much carbon delay-tolerant jobs save by waiting for cleaner hours in Germany, Great Britain, France and California, and showed that the potential depends on how strongly each grid varies over time. CarbonScaler [cite:carbonscaler] scales the resources of elastic batch jobs with the carbon intensity instead of suspending them. Google's carbon-intelligent compute management [cite:cics] delays temporally flexible workloads using day-ahead forecasts. These systems treat jobs as independent and do not move data."),
    H2("2.3", "Spatial and spatiotemporal shifting"),
    P("CASPER [cite:casper] places distributed web-service load across regions to minimise carbon under latency objectives. A recent Kubernetes-based study [cite:k8s] combines spatial and temporal shifting for deadline-tolerant jobs and reports that the difference in carbon intensity between regions dominates the savings, an observation our results explain mechanistically (Section 6.4)."),
    H2("2.4", "Carbon-aware data transfer"),
    P("LinTS [cite:lints] formulates the temporal scheduling of transfers between cloud DCs as a linear program and reports large savings while meeting all transfer deadlines. Goldverg *et al.* [cite:e2e] measure the footprint of end-to-end data movement and propose shifting transfers in time, space and overlay routes. The energy intensity of data transmission has been estimated at 0.06 kWh/GB for 2015, halving roughly every two years [cite:aslan]; we sweep this parameter rather than fix it (Section 5.3). These works optimise the transfer alone; the compute that consumes the data, and its deadline, are outside their model."),
    H2("2.5", "Positioning"),
    P("[tab:related] summarises which decisions each line of work makes, as described by the cited papers. This project is, to our knowledge, the first to couple carbon-aware transfer timing with carbon-aware DAG scheduling under a single shared deadline. More importantly than coverage, it explains *when* the coupling matters: the dominance of location reported in [cite:k8s] is a consequence of clean grids being flat, and the coupling becomes valuable exactly when that is not available."),
    ...TAB("related", "Decisions made by related approaches (✓ = modelled, – = not modelled).",
      ["Approach", "Spatial (where)", "Temporal compute", "Transfer timing", "DAG precedence", "Shared deadline"],
      [["HEFT [cite:heft]", "–", "–", "–", "✓", "–"],
       ["CaWoSched [cite:cawosched], CWM [cite:cwm]", "–", "✓", "–", "✓", "✓ (compute)"],
       ["Let's Wait Awhile [cite:waitawhile], CarbonScaler [cite:carbonscaler]", "–", "✓", "–", "–", "per job"],
       ["CASPER [cite:casper]", "✓", "–", "–", "–", "latency SLO"],
       ["Kubernetes spatiotemporal [cite:k8s]", "✓", "✓", "–", "–", "per job"],
       ["LinTS [cite:lints], end-to-end data movement [cite:e2e]", "partly", "–", "✓", "–", "✓ (transfer)"],
       ["**This work**", "✓", "✓ (CWM)", "✓", "✓", "✓ (end to end)"]],
      [3.2, 1.2, 1.3, 1.2, 1.2, 1.4]),
  ];
}

function ch3() {
  return [
    H1("Problem Formulation and Theory"),
    H2("3.1", "System model"),
    P("A workflow G = (V, E) with input volume Δ (GB) is generated at a source DC d_{s}. A set 𝒟 of candidate DCs, which always contains d_{s}, can run it; each DC d has a cluster of heterogeneous processors and an hourly carbon-intensity (CI) series CI_{d}(t) in gCO₂/kWh. The WAN from d_{s} to d offers nominal bandwidth B_{d} with efficiency η, so the effective rate is B_{eff} = ηB_{d}. CWM works in integer time units of κ seconds (κ = 120 s, so one hour is 30 units). The job has a global deadline D = ⌈αM⌉ units, where M is the HEFT makespan of G and α ≥ 1 the deadline factor, as in [cite:cwm]."),
    P("The decisions are the execution DC d, the transfer start T_{net}, and the task mapping and start times inside d, which CWM chooses. [fig:timeline] shows how the four phases share the deadline. The transfer lasts"),
    EQ("tau", "τ_{d} = Δ / B_{eff}   (τ_{d} = 0 if d = d_{s}),"),
    P("and compute may start only when all data has arrived, rounded up to whole units, which leaves CWM the effective deadline D′:"),
    EQ("arrival", "T_{arr}(d, T_{net}) = ⌈(T_{net} + τ_{d}) / κ⌉,      D′ = D − T_{arr}."),
    ...FIG("timeline", "figures/fig_timeline.png", "The deadline tension: waiting, transfer, queue (Section 3.5) and the CWM schedule all fit inside one global deadline D. Waiting longer or choosing a farther DC shrinks the window D′ left for carbon-aware scheduling.", 6.3),
    H2("3.2", "Objective and carbon metrics"),
    P("The objective is the total carbon of moving and computing,"),
    EQ("objective", "min over (d, T_{net}) :   NetCarbon_{d}(T_{net}) + CompCarbon_{d}(T_{arr}),"),
    P("where d ranges over 𝒟 and T_{net} over [0, T^{max}_{d}], with T^{max}_{d} = κ(D − M_{d}) − τ_{d} the latest start that still leaves at least the HEFT makespan M_{d}. Network carbon charges ε kWh per GB, attributionally, at the endpoint-average WAN carbon intensity:"),
    EQ("net", "NetCarbon_{d}(T) = ε Δ · (1/τ_{d}) · ∫ CI^{net}_{s,d}(t) dt  over [T, T + τ_{d}],"),
    EQ("wanci", "CI^{net}_{s,d}(t) = ( CI_{s}(t) + CI_{d}(t) ) / 2,   CI_{s} = CI of the source DC."),
    P("For compute we report two metrics. The solver returns, per interval j of the shifted and truncated profile, the total energy E^{tot}_{j} and the energy above the green budget E^{exc}_{j}; k(·) converts CWM energy units to kWh. The **location-based** metric, our primary one, prices the dynamic energy (total minus idle) at the grid CI:"),
    EQ("loc", "CompCarbon^{loc}_{d} = Σ_{j} k( E^{tot}_{j} − P_{idle}|I_{j}| ) · CI_{d,j}."),
    P("The **brown** metric is CWM's native objective priced at the grid CI:"),
    EQ("brown", "CompCarbon^{brown}_{d} = Σ_{j} k( E^{exc}_{j} ) · CI_{d,j}."),
    P("CWM needs a green-power budget per interval. We derive it identically for every DC from the CI,"),
    EQ("budget", "𝒢_{d,j} = P_{idle} + max(0, 1 − CI_{d,j}/800) · f · P_{dyn},"),
    P("with f = 0.2 for the cluster size used, following the CWM instances. The floor 𝒢 ≥ P_{idle} matters for Prop. 1. Because the budget itself depends on CI, the brown metric is zero for any DC whose budget covers the job, however dirty its grid: on real data it prefers Frankfurt (≈ 320 gCO₂/kWh) to Paris (≈ 36) for small jobs. We therefore report the location metric as primary and the brown metric as secondary throughout."),
    H2("3.3", "Structural properties"),
    P("Let C^{*}_{d}(a) be the optimal compute carbon at DC d when the data arrives at unit a, and f_{d}(T) = NetCarbon_{d}(T) + C^{*}_{d}(T_{arr}(T))."),
    STMT("Proposition 1 (monotone compute).", "If 𝒢_{d,j} ≥ P_{idle} for all intervals, C^{*}_{d}(a) is non-decreasing in a under the brown metric. Under the location metric it is non-decreasing without this condition."),
    P("*Proof.* A schedule that is feasible for arrival a_{2} (all tasks in [a_{2}, D)) is feasible for any a_{1} ≤ a_{2}, because the absolute end D is unchanged. When idle power never exceeds the budget, a schedule's brown energy depends only on its busy periods, not on the window; the location metric subtracts idle power by definition. So the feasible set only shrinks as a grows while the cost of each schedule stays the same. ∎"),
    P("Prop. 1 is the formal content of the tension: waiting can lower network carbon but can never lower optimal compute carbon. The CWM heuristic does not satisfy it exactly; on our data its compute carbon drops in 12–34 % of consecutive arrival steps, which is why we control for best-of-N effects (Section 4.3)."),
    STMT("Proposition 2 (network breakpoints).", "For hourly piecewise-constant CI, NetCarbon_{d}(T) is piecewise linear in T, and its minimum over [0, T^{max}_{d}] lies in ℬ = {0, T^{max}_{d}} ∪ {kh} ∪ {kh − τ_{d}}, where h is one hour."),
    P("*Proof.* Differentiating [eq:net],"),
    EQ("deriv", "dNetCarbon_{d}/dT = (εΔ/τ_{d}) · ( CI^{net}(T + τ_{d}) − CI^{net}(T) ),"),
    P("which is piecewise constant, with changes only where the start or the end of the transfer crosses an hour boundary. A piecewise-linear function attains its minimum at a kink or an endpoint. ∎"),
    STMT("Corollary 2a (exact candidates for the total).", "If the compute term is any non-decreasing function of the arrival unit, f_{d} attains its minimum on the finite set ℬ ∪ {aκ − τ_{d} : a ∈ ℤ} ∩ [0, T^{max}_{d}]. On segments of ℬ where NetCarbon is non-decreasing only the left endpoint is needed."),
    P("*Proof.* On each arrival cell ((a−1)κ − τ_{d}, aκ − τ_{d}] the compute term is constant and NetCarbon is piecewise linear with kinks in ℬ, so the minimum over the cell is at a kink or a cell endpoint; the open left end is dominated by the previous cell's right endpoint, whose compute term is no larger. Where NetCarbon is non-decreasing, moving later raises both terms. ∎ Our search evaluates ℬ; it is exact for network carbon and can miss an optimum only inside a segment where network carbon decreases."),
    STMT("Proposition 3 (attenuation of waiting).", "For a daily-periodic WAN intensity CI^{net}(t) = c̄ + A cos(ωt), ω = 2π/P, P = 24 h,"),
    EQ("sinc", "NetCarbon(T) = εΔ [ c̄ + A · sinc(ωτ/2) · cos(ω(T + τ/2)) ],"),
    P("with sinc(x) = sin(x)/x, so the most that waiting can save is"),
    EQ("maxsave", "max_{T} NetCarbon − min_{T} NetCarbon = 2 εΔ A |sinc(πτ/P)|."),
    P("*Proof.* Integrate the cosine over [T, T+τ] and apply the sum-to-product identity. ∎ The relative saving falls as the transfer lengthens and vanishes at τ = P; the absolute saving ∝ τ|sinc(πτ/P)| peaks at τ = 12 h. On real data the measured saving decays more slowly than the harmonic predicts because weather adds non-periodic variability ([fig:attenuation]), so Prop. 3 is an explanation of the trend rather than a quantitative model. Crucially, the saving scales with the *amplitude* A of the grid's daily cycle, which is the quantity that turns out to decide everything in Chapter 6."),
    P("**Existence and complexity.** The feasible set is non-empty iff τ_{d} ≤ κ(D − M_{d}); since the arrival unit takes finitely many values and Cor. 2a gives a finite candidate set, f_{d} attains its minimum. The problem contains CWM's problem as the special case d = d_{s}, Δ = 0, which is strongly NP-complete [cite:cwm], so ours is strongly NP-hard and we use CWM as a heuristic inner solver."),
    H2("3.4", "Heterogeneous hardware"),
    P("In the extension studies DC d may have its own processor mix, with HEFT makespan M_{d}, and a facility power usage effectiveness PUE_{d}. The deadline stays global, D = ⌈αM_{s}⌉ (M_{s} on the source DC's hardware), and feasibility at d requires D′ ≥ M_{d}. If the green budget scales with facility power, facility excess energy is PUE_{d} · max(0, P − 𝒢), so both compute metrics scale exactly by PUE_{d} and the inner scheduling problem is unchanged; Props. 1–3 hold per DC."),
    H2("3.5", "Data-centre queues"),
    P("A DC may have a queue q_{d}(t) ≥ 0, piecewise constant on the hourly grid. Compute then starts at"),
    EQ("start", "s_{d}(T) = ⌈( T_{arr} + q_{d}(T_{arr}) ) / κ⌉,      D′ = D − s_{d}(T)."),
    P("Prop. 1 still holds in the start time s. However s_{d}(T) need no longer be monotone in T: if a queue drains at an hour boundary, arriving just after it starts compute *earlier* than arriving just before. This is the only new mechanism queues add, since waiting can now also reduce compute carbon. Hour boundaries are multiples of 30κ, so queue changes coincide with arrival-cell boundaries already in Cor. 2a's set; when queue lengths are multiples of κ the candidate set is unchanged, and otherwise one extra point per cell, aκ − τ_{d} − q, must be added."),
    H2("3.6", "Why space and time substitute"),
    P("By Prop. 3, the value of temporal shifting at a DC is bounded by roughly twice its daily CI amplitude per unit of energy. Choosing the DC with the lowest mean CI is, on real grids, also choosing one with a small amplitude: the lowest-carbon grids are hydro and nuclear, which do not follow the solar cycle. Once the spatial choice is made, the temporal term is therefore bounded by a small constant, and the joint optimum differs from \"greenest DC, send now\" only through the network path (whose CI keeps half of the *source* amplitude, [eq:wanci]) and through near-ties between clean grids. This argument makes a testable prediction: removing the flat clean grids removes the bound, so joint optimisation should pay more. Section 6.5 tests it."),
    H2("3.7", "A relaxation for cheap ranking"),
    P("For RQ4 we need to rank candidates without running the solver. For candidate (d, T) define"),
    EQ("rule", "f̂_{d}(T) = NetCarbon_{d}(T) + E · (PUE_{d}/PUE_{ref}) · CI^{(L)}_{d}(s_{d}(T), D),"),
    P("where CI^{(L)}_{d}(s, D) is the mean of the L cleanest whole hours of CI_{d} in [s, D), E is the dynamic energy of one reference schedule (one solver call), and L = ⌈M⌉ hours is the job's minimum duration."),
    STMT("Lemma (relaxation).", "If the job's dynamic energy E could be spread at constant power over any L whole hours of the window, ignoring precedence and the green budget, the minimum location-based compute carbon is exactly E · PUE_{d} times the mean CI of the L cleanest hours."),
    P("*Proof.* Minimising a sum of L equal-energy slots over the available hours selects the L smallest CI values. ∎ So [eq:rule] is network carbon, which is exact, plus the optimum of a preemptive relaxation of the compute term, and it is non-decreasing in the start time, consistent with Prop. 1. It is optimistic about how much work fits into clean hours, and it models no budget, so it is weaker under the brown metric."),
  ];
}

module.exports = { titlePage, declaration, abstract, toc, ch1, ch2, ch3, TITLE };
