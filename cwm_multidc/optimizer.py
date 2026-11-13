"""Joint spatiotemporal grid search over (execution DC d, transfer start T_net) + baselines.

Objective (gCO2), for a candidate (d, T_net):

    NetCarbon  = Delta_GB * eps_net * mean_{[T_net, T_net + tau)} (CI_src + CI_d)/2
    CompCarbon = sum_j  kWh(E_j^excess) * CI_{d, j}          (j over shifted+truncated intervals)
    Total      = NetCarbon + CompCarbon

with tau = Delta / B_eff (0 if d = d_s), T_arr = ceil_units(T_net + tau), D' = D - T_arr,
and CWM run on the destination profile shifted by T_arr and truncated to D'.

Time-grid for T_net (``grid="breakpoints"``, default).  NetCarbon(T_net) is piecewise
linear with kinks only where T_net or T_net + tau crosses an hour boundary (CI is
hourly), so its minimum over [0, T_max] lies in
    {0, T_max} U {k h} U {k h - tau}
which is exactly the candidate set used.  This also makes T_arr hit every hour
boundary, where the destination profile changes.  ``grid="uniform"`` gives the spec's
{0, dt, 2dt, ...} grid instead.

Reference makespan M is the HEFT makespan (as in the CWM paper: D = alpha * M).
Candidates with D' < M are not evaluated (CWM essentially never beats HEFT's makespan).

Two compute-carbon metrics are reported for every point:
    brown    (CWM's objective) sum_j kWh(E_j^excess) * CI_j
    location (marginal, location-based) sum_j kWh(E_j^total - P_idle |I_j|) * CI_j
Both exclude idle power, so neither depends on the window length D'.  Selections
(Ours, baselines, ablations) can be re-derived for either metric and any rescaled
eps_net without new solver calls, because network carbon is linear in eps_net.
"""

from __future__ import annotations

import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from .cwm_runner import STATUS_INFEASIBLE, STATUS_OK, CWMRunner
from .data_loader import SECONDS_PER_HOUR, Topology
from .profile_shifting import shift_profile, truncate_profile
from .wan_model import WANConfig, calculate_transfer_duration, evaluate_wan_transfer

BASELINES = ("B1", "B2", "B3", "B4", "B5", "B6", "B7")
BASELINE_NAMES = {
    "B1": "CWM-Local",
    "B2": "Greenest-DC + HEFT",
    "B3": "Greenest-DC + CWM",
    "B4": "Network-Optimized",
    "B5": "Compute-Optimized",
    "B6": "Efficiency-aware greenest DC + CWM",
    "B7": "Queue-aware greenest DC + CWM",
    "Ours": "Joint Spatiotemporal",
    "A1": "Ours-NoWait (best DC, T_net = 0)",
    "A2": "Ours-FixedDC (greenest DC, best T_net)",
    "C1": "B3-bestN (equal solver budget)",
    "R1": "Rule, top-1 (≤ 2 solver calls)",
    "R3": "Rule, top-3 (≤ 4 solver calls)",
}
ABLATIONS = ("A1", "A2", "C1")
RULES = ("R1", "R3")  # theory-guided rule, top-1 / top-3 candidates solved (see rule_rank)


@dataclass(frozen=True)
class Problem:
    """One multi-DC scheduling instance.

    Args:
        dag: DAG .dot file.
        topology: candidate DCs on a shared clock (must cover the deadline window).
        data_size_gb: input volume Delta at the source DC.
        alpha: deadline factor; D = ceil(alpha * M_HEFT) CWM units.  Ignored if
            ``deadline_units`` is given.
        wan: energy intensity / efficiency / unit convention (bandwidth is per DC).
        seeds: CWM seeds; compute carbon is averaged over them.
        grid: ``breakpoints`` (default) or ``uniform``.
        grid_step_s: step for the uniform grid (default 15 min).
        equal_budget_control: also run B3's configuration with as many independent seed
            groups as Ours has CWM candidates (same solver-call budget), to separate genuine
            joint-optimisation gains from best-of-N selection over a noisy heuristic.
    """

    dag: Path
    topology: Topology
    data_size_gb: float
    alpha: float = 1.5
    deadline_units: int | None = None
    wan: WANConfig = WANConfig()
    seeds: tuple[int, ...] = (42,)
    grid: str = "breakpoints"
    grid_step_s: float = 900.0
    equal_budget_control: bool = False

    def __post_init__(self) -> None:
        if self.data_size_gb < 0:
            raise ValueError("data_size_gb must be >= 0")
        if self.grid not in ("breakpoints", "uniform"):
            raise ValueError(f"grid must be 'breakpoints' or 'uniform', got {self.grid!r}")
        if not self.seeds:
            raise ValueError("at least one seed required")
        if self.alpha <= 0:
            raise ValueError("alpha must be positive")


@dataclass(frozen=True)
class Evaluation:
    """Outcome of one (d, T_net, scheduler) evaluation, all units explicit."""

    dc: str
    t_net_s: float
    scheduler: str
    status: str
    tau_s: float
    t_arrival_s: float
    t_arrival_units: int
    d_prime_units: int
    net_kwh: float
    net_gco2: float
    comp_brown_kwh: float | None = None
    comp_gco2: float | None = None
    total_gco2: float | None = None
    makespan_units: float | None = None
    cwm_raw_watt_units: float | None = None
    solver_ms: float | None = None
    message: str = ""
    comp_dyn_kwh: float | None = None  # dynamic (work) energy of the schedule
    comp_loc_gco2: float | None = None  # marginal location-based compute carbon
    role: str = "grid"  # "grid" (search space) or "control" (equal-budget B3 restarts)
    seeds: tuple[int, ...] = ()
    queue_wait_s: float = 0.0  # time waited in the DC's queue after the data arrived
    t_start_units: int | None = None  # compute start (arrival + queue), CWM units

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    @property
    def total_loc_gco2(self) -> float | None:
        return None if self.comp_loc_gco2 is None else self.net_gco2 + self.comp_loc_gco2

    def under(self, metric: str = "brown", eps_scale: float = 1.0) -> "Evaluation":
        """Copy whose net/comp/total fields hold the given metric with eps_net rescaled."""
        if metric not in ("brown", "location"):
            raise ValueError(f"metric must be 'brown' or 'location', got {metric!r}")
        net = self.net_gco2 * eps_scale
        comp = self.comp_gco2 if metric == "brown" else self.comp_loc_gco2
        return replace(self, net_gco2=net, net_kwh=self.net_kwh * eps_scale, comp_gco2=comp,
                       total_gco2=None if comp is None else net + comp)


@dataclass
class SearchResult:
    problem: Problem
    m_ref_units: int
    deadline_units: int
    evaluations: list[Evaluation]
    best: Evaluation | None
    baselines: dict[str, Evaluation | None] = field(default_factory=dict)
    greenest_dc: str | None = None

    def records(self) -> list[dict]:
        base = {
            "dag": Path(self.problem.dag).stem,
            "data_size_gb": self.problem.data_size_gb,
            "deadline_units": self.deadline_units,
            "m_ref_units": self.m_ref_units,
            "alpha": self.deadline_units / self.m_ref_units,
            "synthetic_ci": self.problem.topology.synthetic,
        }
        out = []
        for e in self.evaluations:
            r = dict(base, **asdict(e))
            r["seeds"] = " ".join(map(str, e.seeds))
            out.append(r)
        return out

    def summary(self, metric: str = "brown", eps_scale: float = 1.0) -> dict[str, Evaluation | None]:
        """Ours, B1-B5, ablations A1/A2 and control C1 under ``metric`` / rescaled eps."""
        if metric == "brown" and eps_scale == 1.0 and self.baselines:
            sel = {"Ours": self.best, **self.baselines}
        else:
            sel = select(self.problem, self.evaluations, self.deadline_units, self.greenest_dc, metric, eps_scale,
                         m_ref=self.m_ref_units)
        return sel

    def separable_bound(self, metric: str = "brown", eps_scale: float = 1.0) -> float | None:
        """min_d [ min_T NetC_d(T) + min_T CompC_d(T) ] over evaluated grid points.

        A lower bound on every evaluated total (hence on Ours).  If the inner solver were
        exact, CompC_d would be non-decreasing in T (Prop. 1), so the bound pairs the
        cheapest network slot with the compute carbon of the earliest arrival: the gap
        Ours - bound is the part of the network/compute trade-off that could not be
        realised simultaneously.
        """
        best = None
        for dc in {e.dc for e in self.evaluations}:
            g = [e.under(metric, eps_scale) for e in self.evaluations
                 if e.dc == dc and e.ok and e.role == "grid" and e.scheduler == "cwm"]
            if not g:
                continue
            v = min(e.net_gco2 for e in g) + min(e.comp_gco2 for e in g)
            best = v if best is None else min(best, v)
        return best

    def nonmonotone_fraction(self, metric: str = "brown") -> tuple[int, int]:
        """(#steps where compute carbon DROPS as arrival gets later, #steps) per DC.

        The exact inner problem is non-decreasing in T_arr (Prop. 1); drops are
        heuristic noise of CWM.
        """
        drops = steps = 0
        for dc in {e.dc for e in self.evaluations}:
            g = sorted((e for e in self.evaluations if e.dc == dc and e.ok and e.role == "grid"
                        and e.scheduler == "cwm"),
                       key=lambda e: e.t_arrival_units if e.t_start_units is None else e.t_start_units)
            c = [e.under(metric).comp_gco2 for e in g]
            for a, b in zip(c, c[1:]):
                steps += 1
                drops += b < a - 1e-9
        return drops, steps


# ------------------------------------------------------------------------ pieces
def transfer_duration_s(problem: Problem, dc: str) -> float:
    topo = problem.topology
    if dc == topo.source or problem.data_size_gb == 0:
        return 0.0
    return calculate_transfer_duration(problem.data_size_gb, topo.dc(dc).bandwidth_gbps,
                                       problem.wan.throughput_efficiency, problem.wan.unit_convention)


_RUNNERS: dict[tuple[int, str], CWMRunner] = {}
_RUNNERS_LOCK = threading.Lock()


def runner_for(problem: Problem, runner: CWMRunner, dc: str) -> CWMRunner:
    """The solver runner for DC ``dc``'s hardware: ``runner`` itself unless the DC has its own
    cluster file, in which case a copy bound to that file (same cache, same binaries)."""
    path = problem.topology.cluster_json_of(dc)
    if not path or Path(path).resolve() == Path(runner.cluster_json).resolve():
        return runner
    key = (id(runner), str(Path(path).resolve()))
    with _RUNNERS_LOCK:
        if key not in _RUNNERS:
            _RUNNERS[key] = replace(runner, cluster_json=Path(path), _heft_ms_cache={})
        return _RUNNERS[key]


def heft_reference(problem: Problem, runner: CWMRunner) -> tuple[int, dict[str, int]]:
    """(M_ref, {dc: M_dc}).  The deadline D = alpha * M_ref uses the *source* DC's hardware (the
    job's home); feasibility at DC d needs D' >= M_dc, the HEFT makespan on d's own hardware."""
    topo = problem.topology
    m = {d.name: runner_for(problem, runner, d.name).heft_makespan(problem.dag) for d in topo.dcs}
    return m[topo.source], m


def deadline_units(problem: Problem, m_ref: int) -> int:
    if problem.deadline_units is not None:
        return int(problem.deadline_units)
    return int(math.ceil(problem.alpha * m_ref - 1e-9))


def t_net_candidates(problem: Problem, dc: str, m_ref: int, d_units: int) -> list[float]:
    """Feasible transfer start times (seconds) for DC ``dc``."""
    ts = problem.topology.timescale
    if dc == problem.topology.source:
        return [0.0] if m_ref <= d_units else []
    tau = transfer_duration_s(problem, dc)
    # latest start such that ceil_units(T_net + tau) <= D - M
    slack_units = d_units - m_ref
    t_max = ts.units_to_seconds(slack_units) - tau
    if t_max < 0 or ts.seconds_to_units_ceil(tau) > slack_units:
        return []
    if problem.grid == "uniform":
        n = int(math.floor(t_max / problem.grid_step_s + 1e-9))
        cands = {k * problem.grid_step_s for k in range(n + 1)}
    else:
        h = SECONDS_PER_HOUR
        cands = {0.0, t_max}
        cands |= {k * h for k in range(int(t_max // h) + 1)}
        k0 = int(math.ceil(tau / h))
        cands |= {k * h - tau for k in range(k0, int((t_max + tau) // h) + 1)}
    out = sorted(c for c in cands if -1e-9 <= c <= t_max + 1e-9)
    # guarantee the ceil-units feasibility for every candidate
    return [max(0.0, c) for c in out if ts.seconds_to_units_ceil(max(0.0, c) + tau) <= slack_units]


def _network(problem: Problem, dc: str, t_net_s: float):
    topo = problem.topology
    cfg = replace(problem.wan, bandwidth_gbps=topo.dc(dc).bandwidth_gbps)
    return evaluate_wan_transfer(topo.source, dc, problem.data_size_gb, t_net_s, cfg,
                                 time_varying_ci_profile=topo.wan_ci(dc))


def evaluate(problem: Problem, runner: CWMRunner, dc: str, t_net_s: float, d_units: int,
             scheduler: str = "cwm", seeds: Sequence[int] | None = None, role: str = "grid") -> Evaluation:
    """Evaluate one candidate (runs CWM/HEFT once per seed; metrics averaged over seeds)."""
    seeds = tuple(problem.seeds if seeds is None else seeds)
    topo = problem.topology
    ts = topo.timescale
    if d_units > topo.hours * topo.timescale.units_per_hour:
        raise ValueError(f"deadline {d_units} units exceeds CI horizon of {topo.hours} h")
    wan = _network(problem, dc, t_net_s)
    tau = wan.transfer_duration_seconds
    arrival_s = 0.0 if dc == topo.source else wan.arrival_time_seconds
    t_arr_units = 0 if dc == topo.source else ts.seconds_to_units_ceil(arrival_s)
    # contention: compute starts after the DC's queue wait (0 in the baseline model, so the start
    # equals the arrival unit exactly as before)
    wait_s = topo.queue_wait_s(dc, arrival_s)
    t_start = t_arr_units if wait_s <= 0 else ts.seconds_to_units_ceil(arrival_s + wait_s)
    d_prime = d_units - t_start
    common = dict(dc=dc, t_net_s=t_net_s, scheduler=scheduler, tau_s=tau,
                  t_arrival_s=wan.arrival_time_seconds, t_arrival_units=t_arr_units,
                  d_prime_units=d_prime, net_kwh=wan.network_energy_kwh, net_gco2=wan.network_emissions_gco2,
                  role=role, seeds=seeds, queue_wait_s=wait_s, t_start_units=t_start)
    if d_prime <= 0:
        return Evaluation(status=STATUS_INFEASIBLE, message="no compute time left", **common)
    if wait_s > 0 and d_prime < runner_for(problem, runner, dc).heft_makespan(problem.dag):
        # the queue left less time than the DC's HEFT makespan: infeasible by the model's rule
        return Evaluation(status=STATUS_INFEASIBLE, message="queue leaves less than M_dc", **common)

    power, ci = topo.profiles(dc)
    p = truncate_profile(shift_profile(power, t_start, required_deadline=d_prime), d_prime)
    c = truncate_profile(shift_profile(ci, t_start, required_deadline=d_prime), d_prime)

    p_idle = topo.cluster_of(dc).p_idle
    runner = runner_for(problem, runner, dc)
    iv = p["intervals"]
    brown, gco2, dyn, loc, mk, raw, ms = [], [], [], [], [], [], []
    for seed in seeds:
        r = runner.solve(problem.dag, p, d_prime, seed=seed, scheduler=scheduler)
        if not r.ok:
            return Evaluation(status=r.status, message=r.message[-200:], **common)
        kwh = [ts.watt_units_to_kwh(e) for e in r.per_interval]
        brown.append(sum(kwh))
        gco2.append(sum(k * ci_j for k, ci_j in zip(kwh, c["budgets"])))
        # marginal location-based: dynamic energy (total minus idle) priced at grid CI
        dkwh = [ts.watt_units_to_kwh(max(0, en - p_idle * (b - a)))
                for en, a, b in zip(r.per_interval_energy, iv, iv[1:])]
        dyn.append(sum(dkwh))
        loc.append(sum(k * ci_j for k, ci_j in zip(dkwh, c["budgets"])))
        mk.append(r.makespan)
        raw.append(r.carbon_cost)
        ms.append(r.elapsed_ms)
    n = len(seeds)
    pue = topo.dc(dc).pue  # facility overhead: grid energy = PUE x IT energy (1.0 in the baseline model)
    comp = pue * sum(gco2) / n
    return Evaluation(status=STATUS_OK, comp_brown_kwh=pue * sum(brown) / n, comp_gco2=comp,
                      total_gco2=wan.network_emissions_gco2 + comp, makespan_units=sum(mk) / n,
                      cwm_raw_watt_units=sum(raw) / n, solver_ms=sum(ms) / n,
                      comp_dyn_kwh=pue * sum(dyn) / n, comp_loc_gco2=pue * sum(loc) / n, **common)


def greenest_feasible_dc(problem: Problem, d_units: int, feasible: Iterable[str]) -> str | None:
    """DC with the lowest mean CI over the deadline window [0, D] among feasible DCs."""
    topo = problem.topology
    hours = topo.timescale.units_to_hours(d_units)
    feas = list(feasible)
    if not feas:
        return None
    return min(feas, key=lambda n: (topo.dc(n).ci.mean(hours), n))


def _min(evals: Sequence[Evaluation], key) -> Evaluation | None:
    ok = [e for e in evals if e.ok]
    return min(ok, key=key) if ok else None


# ------------------------------------------------------------------------ driver
def solve(problem: Problem, runner: CWMRunner, workers: int | None = None) -> SearchResult:
    """Joint grid search + baselines B1-B5 for one problem.

    All baselines except B2 are points of the joint search space, so they are read off
    the same evaluations (identical seeds and solver calls) — guaranteeing a fair
    comparison and Ours <= B1, B3, B4, B5 by construction.
    """
    m_ref, m_dc = heft_reference(problem, runner)
    d_units = deadline_units(problem, m_ref)
    topo = problem.topology

    jobs: list[tuple[str, float, str]] = []
    feasible = []
    for d in topo.dcs:
        cands = t_net_candidates(problem, d.name, m_dc[d.name], d_units)
        if cands:
            feasible.append(d.name)
        jobs += [(d.name, t, "cwm") for t in cands]
    green = greenest_feasible_dc(problem, d_units, feasible)
    if green is not None:
        jobs.append((green, 0.0, "heft"))

    if problem.equal_budget_control and green is not None:
        k = sum(1 for j in jobs if j[2] == "cwm")
        n = len(problem.seeds)
        for g in range(1, k):  # group 0 is B3 itself (problem.seeds)
            jobs.append((green, 0.0, "control", tuple(10_000 + g * n + i for i in range(n))))

    workers = workers or os.cpu_count() or 1

    def run(j):
        if j[2] == "control":
            return evaluate(problem, runner, j[0], j[1], d_units, "cwm", seeds=j[3], role="control")
        return evaluate(problem, runner, j[0], j[1], d_units, j[2])

    with ThreadPoolExecutor(max_workers=workers) as ex:
        evals = list(ex.map(run, jobs))

    sel = select(problem, evals, d_units, green, "brown", 1.0, m_ref=m_ref)
    best = sel.pop("Ours")
    return SearchResult(problem, m_ref, d_units, evals, best, sel, green)


def select(problem: Problem, evals: Sequence[Evaluation], d_units: int, green: str | None,
           metric: str = "brown", eps_scale: float = 1.0, m_ref: int | None = None) -> dict[str, Evaluation | None]:
    """Derive Ours, B1-B5, A1, A2, C1 from evaluated points under a metric / eps scale."""
    topo = problem.topology
    ev = [e.under(metric, eps_scale) for e in evals]
    grid = [e for e in ev if e.scheduler == "cwm" and e.role == "grid"]
    hours = topo.timescale.units_to_hours(d_units)

    def at(dc, t, sched="cwm"):
        for e in ev:
            if e.dc == dc and e.t_net_s == t and e.scheduler == sched and e.role == "grid":
                return e if e.ok else None
        return None

    out: dict[str, Evaluation | None] = {m: None for m in ("Ours",) + BASELINES + ABLATIONS + RULES}
    out["Ours"] = _min(grid, key=lambda e: (e.total_gco2, e.t_net_s, e.dc))
    out["B1"] = at(topo.source, 0.0)
    if green is not None:
        out["B2"] = at(green, 0.0, "heft")
        out["B3"] = at(green, 0.0)
        # B4: network-optimal transfer time at the greenest DC, ignoring compute
        # (among T_net for which CWM found a schedule; network carbon is known a priori,
        #  so a network-optimizing operator would simply fall back to the next-best slot)
        out["B4"] = _min([e for e in grid if e.dc == green], key=lambda e: (e.net_gco2, e.t_net_s))
        # A2: greenest DC, transfer time chosen by TOTAL carbon (isolates temporal shifting)
        out["A2"] = _min([e for e in grid if e.dc == green], key=lambda e: (e.total_gco2, e.t_net_s))
        # C1: best of K independent seed groups at B3's configuration (equal solver budget)
        ctrl = [e for e in ev if e.role == "control" and e.ok]
        if ctrl:
            out["C1"] = _min(ctrl + ([out["B3"]] if out["B3"] else []), key=lambda e: e.total_gco2)
    # B5: transfer immediately everywhere, pick DC with least compute carbon
    # (ties in compute carbon, e.g. several DCs with zero brown energy, go to the
    #  greener DC, then by name, so the choice stays network-agnostic but deterministic)
    now = [e for e in grid if e.t_net_s == 0.0]
    out["B5"] = _min(now, key=lambda e: (e.comp_gco2, topo.dc(e.dc).ci.mean(hours), e.dc))
    # A1: transfer immediately, DC chosen by TOTAL carbon (isolates spatial choice)
    out["A1"] = _min(now, key=lambda e: (e.total_gco2, e.dc))
    # B6: like B3 but ranks DCs by PUE x mean CI (an operator who knows each site's facility
    # efficiency); identical to B3 when every PUE is equal
    cand = sorted({e.dc for e in now if e.ok})
    if cand:
        eff = min(cand, key=lambda n: (topo.dc(n).pue * topo.dc(n).ci.mean(hours), n))
        out["B6"] = at(eff, 0.0)
    # B7: send now to the greenest DC (mean CI) among those that can still meet the deadline
    # after their current queue: an operator who checks queues but does not time transfers.
    # Identical to B3 whenever B3 is feasible and there are no queues.
    if cand:
        q_ok = min(cand, key=lambda n: (topo.dc(n).ci.mean(hours), n))
        out["B7"] = at(q_ok, 0.0)
    # R1 / R3: theory-guided rule.  Rank every candidate by a solver-free estimate and keep the best
    # of the top k after solving them (their values are already among the evaluated grid points).
    ref = next((e for e in ([out["B7"], out["B3"], out["B1"]]) if e is not None and e.ok), None)
    if ref is not None:
        ranked = rule_rank(problem, [e for e in grid], d_units, ref, m_ref)
        for name, k in (("R1", 1), ("R3", 3)):
            top = [e for e in ranked[:k] if e.ok] + [ref]  # the reference was solved anyway
            out[name] = _min(top, key=lambda e: (e.total_gco2, e.t_net_s, e.dc))
    return out


def rule_rank(problem: Problem, cands: Sequence[Evaluation], d_units: int, ref: Evaluation,
              m_ref: int | None = None) -> list[Evaluation]:
    """Order candidates (DC, T_net) by a solver-free estimate of their total carbon.

    Uses only quantities known before scheduling, one reference schedule ``ref`` (the job's
    energy E, from one solver call) and its minimum duration L = the HEFT makespan M (known: it
    defines the deadline):
      - network carbon: exact, from the CI forecast (Prop. 2);
      - compute carbon: E / PUE_ref x PUE_d x the mean CI of the L cleanest whole hours of DC d
        in [compute start, D], where start = arrival + queue wait.  This mirrors CWM moving work
        into green hours, and it is non-decreasing in the start time, as Prop. 1 requires of the
        optimum.  Candidates whose window is shorter than L are dropped.
    """
    topo = problem.topology
    ts = topo.timescale
    pue_ref = topo.dc(ref.dc).pue or 1.0
    e_it = (ref.comp_dyn_kwh or 0.0) / pue_ref
    # L: the HEFT makespan, not the reference schedule's own length (CWM stretches a schedule to
    # fill its window, which would make every wait look costlier than it is)
    dur_units = m_ref if m_ref else (ref.makespan_units or 0.0)
    dur_h = max(1, math.ceil(ts.units_to_hours(dur_units)))
    d_h = ts.units_to_hours(d_units)
    scored = []
    for e in cands:
        start_units = e.t_start_units if e.t_start_units is not None else e.t_arrival_units
        h0 = math.ceil(ts.units_to_hours(start_units) - 1e-9)
        ci = topo.dc(e.dc).ci.values[h0:int(math.floor(d_h + 1e-9))]
        if len(ci) < dur_h:
            continue
        comp = e_it * topo.dc(e.dc).pue * float(np.mean(sorted(ci)[:dur_h]))
        scored.append((e.net_gco2 + comp, e.t_net_s, e.dc, e))
    return [s[-1] for s in sorted(scored, key=lambda s: s[:3])]
