// Front matter and Chapters 1-3.
const L = require("./lib.js");
const { d, P, bullets, numbered, H1, H2, H3, EQ, STMT, FIG, TAB, FONT } = L;
const R = "../cwm_multidc/results";

const center = (text, size = 24, opts = {}) => new d.Paragraph({ alignment: d.AlignmentType.CENTER,
  spacing: { after: opts.after ?? 160, before: opts.before ?? 0 },
  children: [new d.TextRun({ text, font: FONT, size, bold: opts.bold, italics: opts.italics })] });

const TITLE = "Balancing Green Data Movement and Green Compute: Joint Spatiotemporal Scheduling of Deadline-Constrained Workflows Across Data Centres";

const REPO = "https://github.com/tuhina2005/carbon-aware-multidc-scheduling";

// Front-matter title that is not a heading (kept out of the Table of Contents).
const frontTitle = (text, pageBreak = true) => new d.Paragraph({ alignment: d.AlignmentType.CENTER, pageBreakBefore: pageBreak,
  spacing: { before: 240, after: 360 }, children: [new d.TextRun({ text, font: FONT, size: 32, bold: true })] });
// Front-matter title that is listed in the Table of Contents (List of Tables, List of Figures, ...).
const frontHeading = (text) => new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, pageBreakBefore: true,
  alignment: d.AlignmentType.CENTER, children: [new d.TextRun({ text, font: FONT })] });

function titlePage() {
  return [
    center(TITLE.toUpperCase(), 48, { bold: true, after: 480 }),
    center("Project Report Submitted in Partial Fulfilment of the Requirements for the Degree of", 24, { after: 360 }),
    center("Bachelor of Technology", 28, { bold: true }),
    center("in", 24, { italics: true }),
    center("Computer Science and Engineering", 28, { bold: true, after: 480 }),
    center("Submitted by", 24, { italics: true }),
    center("<Name of the Student 1>: (Roll No. <XXXXXXXXXX>)", 24, { after: 60 }),
    center("<Name of the Student 2>: (Roll No. <XXXXXXXXXX>)", 24, { after: 60 }),
    center("<Name of the Student 3>: (Roll No. <XXXXXXXXXX>)", 24, { after: 480 }),
    center("Under the Supervision of", 26, { bold: true, italics: true }),
    center("<Supervisor Name>", 24, { bold: true, after: 60 }),
    center("<Designation>, Department of Computer Science and Engineering", 24, { bold: true, after: 720 }),
    center("Shiv Nadar University, Delhi NCR", 24, { bold: true, after: 120 }),
    center("Department of Computer Science and Engineering", 24, { bold: true, after: 120 }),
    center("<Month, Year>", 24),
  ];
}

function declaration() {
  return [
    frontTitle("Declaration", false),
    P("I/We declare that this written submission represents my ideas in my own words and where others' ideas or words have been included, I have adequately cited and referenced the original sources. I also declare that I have adhered to all principles of academic honesty and integrity and have not misrepresented or fabricated or falsified any idea/data/fact/source in my submission. I understand that any violation of the above will be cause for disciplinary action by the University and can also evoke penal action from the sources which have thus not been properly cited or from whom proper permission has not been taken when needed."),
    P(""),
    ...[1, 2, 3].flatMap(() => [
      P("**Name of the Student:** ______________________________", { align: d.AlignmentType.LEFT, spacing: { before: 360, after: 0 } }),
      P("**Signature and Date:** ______________________________", { align: d.AlignmentType.LEFT }),
    ]),
  ];
}

function acknowledgements() {
  return [
    frontTitle("Acknowledgements"),
    P("I would like to express my sincere gratitude to my supervisor, **<Supervisor Name>**, for continuous guidance, critical feedback and encouragement throughout this project. Their suggestions shaped both the research questions and the way the results are tested and reported."),
    P("I am also thankful to the **Department of Computer Science and Engineering, Shiv Nadar University**, for the resources and the environment that made this work possible, and to the authors of CWM and CaWoSched for making their code and workflow instances openly available, and to Fraunhofer ISE (Energy-Charts) and CAISO for publishing the electricity data used in this report."),
    P("Finally, I thank my family and friends for their support and patience."),
    P(""),
    P("Regards,", { align: d.AlignmentType.LEFT, spacing: { after: 0 } }),
    P("**<Name of the Student>**", { align: d.AlignmentType.LEFT }),
  ];
}

function toc() {
  return [
    frontTitle("Contents"),
    new d.TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  ];
}

function listOfTables() {
  return [
    frontHeading("List of Tables"),
    new d.TableOfContents("List of Tables", { hyperlink: true, stylesWithLevels: [new d.StyleLevel("TabCaption", 1)] }),
  ];
}

function listOfFigures() {
  return [
    frontHeading("List of Figures"),
    new d.TableOfContents("List of Figures", { hyperlink: true, stylesWithLevels: [new d.StyleLevel("FigCaption", 1)] }),
  ];
}

function abbreviations() {
  const rows = (pairs) => pairs.map(([a, b]) => [a, b]);
  return [
    frontHeading("List of Symbols and Abbreviations"),
    P("**Abbreviations**", { align: d.AlignmentType.LEFT, keepNext: true }),
    ...TAB(null, "", ["Abbreviation", "Meaning"], rows([
      ["CI", "Carbon intensity of electricity (gCO₂/kWh)"],
      ["CWM", "Carbon-aware Workflow Mapping, the single-DC scheduler extended here"],
      ["CaWoSched", "Carbon-aware workflow scheduler (predecessor of CWM)"],
      ["DAG", "Directed acyclic graph (workflow of tasks and dependencies)"],
      ["DC", "Data centre"],
      ["HEFT", "Heterogeneous Earliest Finish Time list scheduler"],
      ["PUE", "Power usage effectiveness (facility energy / IT energy)"],
      ["WAN", "Wide-area network"],
      ["CAISO", "California Independent System Operator"],
      ["ENTSO-E", "European Network of Transmission System Operators for Electricity"],
      ["ASan", "AddressSanitizer (memory-error detector)"],
      ["B1–B7, A1, A2, C1, R1, R3", "Baselines, ablations, control and rules (Table 4.1)"],
    ]), [28, 72], { fontSize: 20 }),
    P("**Symbols**", { align: d.AlignmentType.LEFT, keepNext: true, spacing: { before: 240 } }),
    ...TAB(null, "", ["Symbol", "Meaning"], rows([
      ["Δ", "Input data volume (GB)"],
      ["d", "A candidate data centre (DC)"],
      ["κ", "Length of one CWM time unit (120 s; 30 units per hour)"],
      ["M", "HEFT makespan of the workflow: how long it takes at full speed"],
      ["α", "Deadline factor; the deadline is D = ⌈αM⌉"],
      ["D, D′", "Deadline; time left for computing after the data arrives"],
      ["B_{eff}, η", "Effective transfer rate; link efficiency (0.95)"],
      ["τ", "Transfer duration"],
      ["T_{net}, T_{arr}", "Transfer start time; arrival time"],
      ["ε", "Network energy per GB sent (kWh/GB; default 0.02)"],
      ["CI, CI^{net}", "Carbon intensity of a grid; of the network (average of both ends)"],
      ["𝒢", "Green-power budget of a DC in one interval"],
      ["P_{idle}, P_{dyn}, f", "Idle power, dynamic power, green fraction of the budget (0.2)"],
      ["ρ", "Busyness level of the DC queues (queue study)"],
      ["A", "Amplitude of a grid's daily carbon-intensity cycle"],
    ]), [28, 72], { fontSize: 20 }),
  ];
}

function abstract() {
  return [
    frontHeading("Abstract"),
    P("Large scientific workflows are increasingly run in whichever data centre (DC) has the cleanest electricity. When the input is terabytes, the data must first cross a wide-area network (WAN), and the transfer, any wait for a greener network, and the carbon-aware schedule of the workflow all share one deadline. CWM, a recent carbon-aware scheduler for deadline-constrained workflows (DAGs), handles only one DC. This project extends it to several: it chooses *where* to run, *when* to send the data and *how* to schedule the tasks, together."),
    P("We first prove three facts about this *deadline tension*. Data that arrives later can never make the computation cleaner (Prop. 1). Only a small, known set of transfer start times needs to be checked (Prop. 2). And the longer a transfer takes, the less there is to gain by waiting to start it (Prop. 3). We then build the joint search on top of the CWM C++ solver and test it on real 2024 hourly carbon-intensity data for five regions, with close to 1,000 problem instances, seven baselines, two ablations, an equal-solver-budget control and hypotheses written down before each run. Along the way we found and fixed a memory bug in the CWM solver that made its output nondeterministic."),
    P("The central finding is that **space and time are substitutes**. The cleanest grids (Norwegian hydro, French nuclear) are also the flattest: their carbon intensity varies by only 3–10 gCO₂/kWh within a day, against 158–232 gCO₂/kWh elsewhere. Once a job is moved there, there is almost nothing left to gain by waiting, so the joint optimiser beats “greenest DC, send now” by only 1.8 % on average. This result holds with different hardware, with data-centre queues and with almost free network energy. The same mechanism predicts when joint optimisation does pay: when no flat clean grid is available, the gain triples to 5.3 % (13× larger absolute saving, paired sign test p = 8·10⁻⁶). Finally, a cheap rule derived from the theory captures 76–85 % of the gain with at most four solver calls instead of about 64."),
    P("**Keywords:** carbon-aware computing, workflow scheduling, geo-distributed data centres, temporal shifting, data transfer, deadline constraints.", { align: d.AlignmentType.LEFT }),
    P(`**Source code:** ${REPO}`, { align: d.AlignmentType.LEFT }),
  ];
}

function ch1() {
  return [
    H1("Introduction"),
    H2("1.1", "Background"),
    P("Data centres use a growing share of the world's electricity, and how much carbon each kilowatt-hour emits depends on where and when it is drawn. In 2024 the Polish grid emitted almost twenty times more per kilowatt-hour than the Norwegian one ([tab:regions]), and a solar-heavy grid is cleaner at noon than at night. Carbon-aware computing uses this in two ways. *Temporal shifting* runs flexible work when the local grid is cleanest [cite:waitawhile,carbonscaler,cics]. *Spatial shifting* runs it where the grid is cleanest [cite:casper,k8s]."),
    P("CWM [cite:cwm] brings temporal shifting to scientific workflows. A workflow is a set of tasks with dependencies (a DAG) that must finish by a deadline. CWM decides which processor runs each task and when, so that as much work as possible happens in hours with plenty of green power."),
    H2("1.2", "Motivation: the deadline tension"),
    P("CWM assumes the workflow is already in the data centre (DC) that runs it. For large scientific workflows that is often not true. The input sits at one site, can be terabytes in size, and has to be moved before any task can start. Moving 1 TB over a 1 Gbit/s link takes about 2.3 hours, the network itself uses energy [cite:aslan], and the grids along the way get cleaner and dirtier through the day [cite:lints,e2e]."),
    P("Once the transfer and the computation share one deadline, the decisions pull against each other. Waiting for a cleaner network saves transfer carbon, but every minute of waiting is a minute less for CWM to fit the tasks into green hours. A distant, cleaner DC means a longer transfer and an even shorter compute window. We call this the *deadline tension*. No existing technique handles it: transfer schedulers ignore the computation that follows, workflow schedulers ignore where the data comes from, and placement systems ignore task dependencies and transfer timing."),
    H2("1.3", "A worked example"),
    P("Here is one real case from our experiments. The eager1000 workflow (1,000 tasks, about 11 hours of work) has 1 TB of input in Frankfurt. It is submitted at 06:00 UTC on 17 April 2024 and must finish within 28 hours. There are three sensible plans:"),
    ...bullets([
      "**Stay in Frankfurt.** No transfer, and CWM schedules the job on the German grid. Total: **98.4 kg CO₂**.",
      "**Send it to Paris now.** The French grid is far cleaner. The transfer takes 2.3 hours and costs 4.3 kg, and the computation costs 5.6 kg. Total: **9.9 kg**, ten times less.",
      "**Send it to Paris, but wait 4.7 hours first.** The transfer then runs over Germany's sunny midday, so it costs only 3.0 kg. The computation now has about 4.6 fewer hours to work with and costs a little more, 5.8 kg. Total: **8.8 kg**, another 11 % less.",
    ]),
    P("The example shows both sides of the project. Choosing *where* to run is the big win (98.4 → 9.9 kg). Choosing *when* to send the data adds a smaller but real saving (9.9 → 8.8 kg), and only because the shorter compute window costs less than the cleaner transfer saves. As we will see, this case is one of the better ones: over the whole year the extra saving from timing averages 1.8 %, and the main question of this report is why."),
    H2("1.4", "Objective"),
    P("The objective is to answer one question: *when data must move before the work can start, how much carbon does choosing the DC, the transfer time and the schedule together save, and why?* We break it into four research questions:"),
    ...numbered([
      "**RQ1.** How should the joint problem (where, when, how) be formulated, and what structure does it have that an algorithm can use?",
      "**RQ2.** On real grid data, how much carbon does joint optimisation save compared with simple strategies such as “send the data now to the greenest DC”?",
      "**RQ3.** *When* does joint optimisation matter, and why?",
      "**RQ4.** Can a cheap rule capture most of the benefit without searching every option?",
    ]),
    H2("1.5", "Contributions"),
    ...bullets([
      "**Model and theory.** We formulate the problem and prove three facts about it: data that arrives later can never make the computation cleaner; only a small, known set of transfer start times needs checking; and the longer a transfer takes, the less there is to gain by waiting (Chapter 3).",
      "**Implementation.** A Python system around the CWM C++ solver that evaluates every option exactly and compares against seven simpler strategies and three controls. It is resumable, cached and covered by 129 automated tests (Chapter 4).",
      "**A solver bug fix.** We found and fixed a memory bug in CWM that made its output random, and showed that no result changed (Section 4.5).",
      "**Findings.** The cleanest grids are also the flattest, so choosing the place and choosing the time substitute for each other. Joint optimisation adds little when a flat clean grid is reachable, and three times as much when none is (Chapter 6).",
      "**A cheap rule** that captures 76–85 % of the joint optimiser's gain with at most four solver calls instead of about 64 (Sections 4.4 and 6.5).",
    ]),
    H2("1.6", "Organisation"),
    P(`Chapter 2 reviews related work, explains how CWM works and states what is new here. Chapter 3 defines the problem and the theory behind it. Chapter 4 describes how we built and tested the system, and Chapter 5 the data and experiments. Chapter 6 presents the results as answers to four questions, then discusses them and compares them with earlier work. Chapter 7 covers implications and limitations, Chapter 8 the conclusions, and Chapter 9 future work. The source code, data and results are available at ${REPO} (Section 4.6).`),
  ];
}

function ch2() {
  return [
    H1("Related Work and Literature Survey"),
    H2("2.1", "Carbon-aware workflow scheduling"),
    P("HEFT [cite:heft] is the standard way to schedule a DAG on mixed processors. It ignores carbon, and its makespan is the yardstick used to set deadlines in this line of work. CaWoSched [cite:cawosched] keeps HEFT's choice of processors and only shifts tasks into greener hours. CWM [cite:cwm] goes further and chooses processors and timing together, with a HEFT-like construction, dynamic programming and local search; it proves the problem strongly NP-complete. Both work on a single cluster. Neither moves data or looks at more than one site. We use CWM, unchanged apart from a bug fix, as the scheduler inside each DC; the next section explains how it works."),
    H2("2.2", "Background: how CWM works"),
    P("Because this project builds directly on CWM [cite:cwm], it is worth describing in more detail. CWM takes four inputs: the workflow as a DAG (how much work each task needs and how much data it sends to the tasks after it); the deadline D; a cluster of processors that differ in speed, idle power and extra *working* power; and a *power profile*, which splits time into intervals, each with a green-power budget. Power used within the budget counts as carbon-free. CWM's cost is the energy used *above* the budget, the “brown” energy, added up until the deadline. Data sent between tasks on different processors is modelled as extra tasks on the links between them."),
    P("CWM builds a schedule in two phases, shown in [fig:cwm]:"),
    ...numbered([
      "**Pick processors for each interval.** There is usually not enough green power to run the whole cluster. For every interval CWM picks the fastest set of processors whose combined working power fits the green budget, a knapsack problem solved by dynamic programming. If the budget does not even cover idle power, it keeps the one processor with the lowest working power, so that work can still progress.",
      "**Place the tasks.** Tasks are ranked by their HEFT priority (roughly, the longest remaining path from the task to the end of the workflow). In that order, each task goes on whichever processor in its interval's set can finish it earliest, as in HEFT.",
      "**Local search.** CWM repeatedly finds the first interval that goes over its green budget and shifts one of its tasks, together with everything that depends on it, out of that interval, as long as the deadline still holds.",
      "**Deadline repair, only if needed.** Limiting processors to the green budget can make the schedule miss the deadline. If it does, CWM reschedules the tasks that finish too late, and everything after them, on all processors with plain HEFT (called HEFT-SL in the paper), changing as few tasks as possible. It then runs the local search again. In the worst case this falls back to the full HEFT-SL schedule, which is the tightest deadline CWM can meet.",
    ]),
    ...FIG("cwm", "figures/fig_cwm.png", "How CWM builds one schedule inside a single data centre (after [cite:cwm]). Phase 1 favours carbon by limiting the processors to what the green budget allows; Phase 2 runs only if the deadline is missed.", 6.2),
    P("In the authors' experiments, CWM cut carbon cost by 42–48 % compared with CaWoSched and by 69 % compared with carbon-agnostic HEFT-SL, at the most relaxed deadlines tested (D = 2M) [cite:cwm]."),
    P("**How this project uses CWM.** We use CWM unchanged, apart from the bug fix described in Section 4.5, as a black box inside each DC. For every candidate (DC, transfer start) we give it that DC's processors, a power profile built from that DC's hourly CI (Section 3.2) that starts when the data arrives, and the time left before the deadline, D′. CWM returns a schedule and its energy in each interval, from which we compute the carbon. Everything outside that box (choosing the DC, timing the transfer, the network model, the theory and the evaluation) is this project's extension."),
    H2("2.3", "Temporal shifting"),
    P("Wiesner *et al.* [cite:waitawhile] measured how much carbon delay-tolerant jobs save by waiting for cleaner hours in Germany, Great Britain, France and California. Their key observation is that the savings depend on how much each grid varies over the day. CarbonScaler [cite:carbonscaler] grows and shrinks elastic batch jobs with the carbon intensity instead of pausing them, and Google [cite:cics] delays flexible work using day-ahead forecasts. All three treat jobs as independent and none of them moves data."),
    H2("2.4", "Spatial and spatiotemporal shifting"),
    P("CASPER [cite:casper] spreads web traffic across regions to cut carbon while keeping latency low. A recent Kubernetes-based study [cite:k8s] combines spatial and temporal shifting for deadline-tolerant jobs and finds that the difference between regions dominates the savings. Our results explain why (Section 6.2)."),
    H2("2.5", "Carbon-aware data transfer"),
    P("LinTS [cite:lints] schedules transfers between cloud DCs over time with a linear program and saves substantial carbon while meeting every transfer deadline. Goldverg *et al.* [cite:e2e] measure the footprint of moving data end to end and propose shifting transfers in time, space and route. Sending a gigabyte was estimated to take 0.06 kWh in 2015, halving roughly every two years [cite:aslan]; we sweep this value rather than fix it (Section 5.3). All of these optimise the transfer alone. The computation that uses the data, and its deadline, are outside their model."),
    H2("2.6", "Novelty of this work"),
    P("[tab:related] shows which decisions each line of work makes. What is new here is twofold. **First, the coupling:** as far as we know, this is the first work to combine carbon-aware transfer timing with carbon-aware workflow scheduling under one shared deadline, so that waiting, transferring and computing all compete for the same hours. **Second, the explanation:** we do not just measure the gain, we explain *when* it appears. The dominance of location seen in [cite:k8s] turns out to follow from clean grids being flat, and joint scheduling becomes worthwhile exactly when no such grid is available. We do not propose a new scheduler for inside the DC."),
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
    P("This chapter states the problem precisely and gives the three properties the search relies on. We give each result with a short reason rather than a formal proof, and say what it means in practice."),
    H2("3.1", "System model"),
    P("A workflow with Δ GB of input starts at a source DC (Frankfurt in our experiments). Several candidate DCs, including the source, could run it. Each DC has its own processors and an hourly carbon-intensity (CI) series in gCO₂/kWh. Data moves to DC d at an effective rate B_{eff} (the link bandwidth times an efficiency η), so the transfer takes τ = Δ / B_{eff}. CWM measures time in whole units of κ = 120 s (30 units per hour). The deadline is D = ⌈αM⌉ units, where M is the workflow's HEFT makespan and α ≥ 1 says how much slack the job has, as in [cite:cwm]."),
    P("Three things are decided: the DC d, the time T_{net} at which the transfer starts, and the schedule inside d, which CWM chooses. Computation can start only when all the data has arrived, and CWM gets whatever is left of the deadline ([fig:timeline]):"),
    EQ("arrival", "T_{arr} = ⌈(T_{net} + Δ / B_{eff}) / κ⌉,      D′ = D − T_{arr}."),
    ...FIG("timeline", "figures/fig_timeline.png", "The deadline tension: waiting, transfer, queue (Section 3.5) and the CWM schedule all fit inside one global deadline D. Waiting longer or choosing a farther DC shrinks the window D′ left for carbon-aware scheduling.", 6.3),
    H2("3.2", "Objective and carbon"),
    P("We minimise the total carbon of moving and computing, over every DC and every allowed transfer start:"),
    EQ("objective", "min over (d, T_{net}) :   NetCarbon_{d}(T_{net}) + CompCarbon_{d}(T_{arr})."),
    P("The latest allowed start still leaves enough time to run the workflow at full speed. **Network carbon** charges ε kWh for every GB sent, at the CI of the network during the transfer. We take that CI to be the average of the source and destination grids, CI^{net}:"),
    EQ("net", "NetCarbon_{d}(T) = ε Δ · (average of CI^{net} over the transfer from T to T + τ)."),
    P("**Compute carbon** charges the energy the work adds on top of idle power, at the DC's grid CI in each interval j of the schedule:"),
    EQ("loc", "CompCarbon_{d} = Σ_{j} k( E^{tot}_{j} − P_{idle}|I_{j}| ) · CI_{d,j}."),
    P("Here E^{tot}_{j} is the energy CWM's schedule uses in interval j, and k(·) converts CWM's energy units to kWh. CWM itself also needs a *green-power budget* for each interval: how much power it may use while still counting as green. We derive it from the CI in the same way for every DC, so cleaner hours give a larger budget:"),
    EQ("budget", "𝒢_{d,j} = P_{idle} + max(0, 1 − CI_{d,j}/800) · f · P_{dyn},   with f = 0.2."),
    P("CWM optimises its own metric, the energy used *above* this budget. That metric has a blind spot, so we use it only as a secondary measure; Section 5.6 explains why."),
    H2("3.3", "Three properties of the problem"),
    STMT("Proposition 1 (waiting never makes computing cleaner).", "The best achievable compute carbon at a DC can only stay the same or rise as the data arrives later."),
    P("*Reason.* The deadline is fixed, so any schedule that fits after a later arrival also fits after an earlier one; arriving later only removes options. This is the deadline tension in one line: waiting can lower network carbon, but never compute carbon. CWM is a heuristic and does not follow this exactly (its compute carbon drops in 12–34 % of consecutive arrival steps on our data), which is why we add a control for solver luck (Section 4.3)."),
    STMT("Proposition 2 (only a few start times need checking).", "With hourly CI data, the best transfer start for network carbon is always either the earliest or latest allowed start, or a start where the transfer begins or ends exactly on an hour boundary. Together with the arrival-time steps, this finite set also contains the best start for the total."),
    P("*Reason.* Within an hour the CI is constant, so network carbon changes in straight lines as the start time moves, and bends only when the start or end of the transfer crosses an hour boundary. A function made of straight pieces is lowest at a bend or an end. Our search checks exactly these points, so it is exact for network carbon."),
    STMT("Proposition 3 (long transfers gain less from waiting).", "If the network CI follows a daily cycle of amplitude A, the most that waiting can save on network carbon is"),
    EQ("maxsave", "2 εΔ A |sinc(πτ / 24 h)|,   with sinc(x) = sin(x)/x."),
    P("*Reason.* A transfer averages the CI over its whole duration, and averaging a daily wave over τ hours shrinks it by exactly this sinc factor. In practice a long transfer covers both clean and dirty hours whenever it starts, so moving it helps less, and at τ = 24 h not at all. On real data the saving falls more slowly than this because weather is not perfectly daily ([fig:attenuation]). The key point is that the saving grows with the *amplitude* A of the grid's daily cycle. That single quantity turns out to decide most of the results in Chapter 6."),
    P("**Complexity.** CWM's own problem is the special case with no data to move, and it is strongly NP-complete [cite:cwm], so ours is strongly NP-hard. We therefore use CWM as a heuristic inside an exact search over DCs and transfer starts."),
    H2("3.4", "Different hardware"),
    P("In one study each DC has its own processor mix and its own power usage effectiveness (PUE: total facility energy divided by IT energy). The deadline is still set on the source DC's hardware, and a DC is usable only if its own HEFT makespan fits in the remaining window. A higher PUE scales both carbon measures by exactly that factor, so the scheduling problem inside the DC is unchanged and the three properties still hold."),
    H2("3.5", "Data-centre queues"),
    P("In another study a DC may have a queue: a job that arrives has to wait q hours before it can start. This adds one new effect. If a queue empties at an hour boundary, arriving just after it can start the computation *earlier* than arriving just before. So with queues, waiting can sometimes reduce compute carbon too. These boundaries are already among the start times checked by Proposition 2, so the search stays exact for queue lengths in whole time units."),
    H2("3.6", "Why place and time substitute"),
    P("Proposition 3 says the value of waiting at a DC is limited by how much its grid swings during the day. On real grids, the DC with the lowest average CI also swings very little: the cleanest grids run on hydro and nuclear power, which do not follow the sun. So once the cleanest DC is chosen, there is little left to gain from timing. The only remaining room is the network, whose CI keeps half of the *source* grid's swing, and near-ties between clean grids. This argument makes a prediction we can test: take away the flat clean grids, and joint scheduling should pay off much more. Section 6.3 tests it."),
    H2("3.7", "A cheap estimate for ranking"),
    P("For RQ4 we want to rank all candidates without running CWM on each. We estimate the total carbon of starting the transfer at time T at DC d as"),
    EQ("rule", "estimate = NetCarbon_{d}(T) + E · (PUE_{d}/PUE_{ref}) · (mean CI of the L cleanest hours left before the deadline),"),
    P("where E is the job's energy, taken from a single CWM run, and L = ⌈M⌉ hours is how long the job needs at minimum. The estimate is exact for the network and optimistic for the computation: it pretends the job could run in the cleanest hours that remain, ignoring task dependencies and the green budget. Like the real compute carbon, it never improves as the start moves later."),
  ];
}

module.exports = { titlePage, declaration, acknowledgements, toc, listOfTables, listOfFigures, abbreviations, abstract, ch1, ch2, ch3, TITLE, REPO };
