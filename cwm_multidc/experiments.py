"""Experiment runner for the Deadline Tension study.

Usage (from the repository root):

    python -m cwm_multidc.experiments grid         # heatmap grid (sweeps are slices of it)
    python -m cwm_multidc.experiments headline     # Ours vs baselines + ablations + equal-budget control
    python -m cwm_multidc.experiments sensitivity  # time scale kappa, bandwidth, CI forecast error
    python -m cwm_multidc.experiments multidate --ci-dir DIR   # same problems over 12 dates x 4 start hours
    python -m cwm_multidc.experiments multidate-noise --ci-dir DIR  # 3 seeds + C1 where Ours beats B3 by >= 5 %
    python -m cwm_multidc.experiments hetero --ci-dir DIR  # per-DC hardware scenarios (W1)
    python -m cwm_multidc.experiments contention --ci-dir DIR  # diurnal DC queues (W2)
    python -m cwm_multidc.experiments plot         # figures + tables from the CSVs

All solver calls go through a persistent cache (``results/cache.jsonl``), so every
subcommand is resumable and re-running it is cheap.  The eps_net sweep needs no solver
calls: network carbon is linear in eps_net, so every summary is re-derived for
EPS_SWEEP values from the same evaluations.

Outputs in ``cwm_multidc/results/``:
    <tag>_evals.csv     every evaluated (d, T_net) point (both compute metrics)
    <tag>_summary.csv   per problem x metric x eps: choice of every method + bound + noise stats
    fig_*.png, *.md
"""

from __future__ import annotations

import argparse
import calendar
import csv
import itertools
import json
import math
import threading
import time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from .cwm_runner import DAG_DIR, DEFAULT_CLUSTER, REPO_ROOT, CWMRunner, ResultCache
from .data_loader import DEFAULT_DCS, HardwareTier, QueueSpec, TimeScale, build_topology, hours_from_series_start, perturb_ci, scan_ci_dir, with_ci
from .optimizer import Problem, SearchResult, evaluate, solve

RESULTS = REPO_ROOT / "cwm_multidc" / "results"
CI_SOURCE_FILE = "ci_source.json"  # tells plots.py where the CI came from

# With real CI, experiment start hours (UTC hour of day) are placed on this date.  A mid-April
# Wednesday: no public holiday, strong solar in DE and California, normal weekday demand.
DEFAULT_CI_START = "2024-04-17"


def _manifest(ci_dir: Path) -> dict:
    f = ci_dir / "MANIFEST.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _source_text(man: dict, ci_dir: Path) -> str:
    if "label" in man:
        return man["label"]
    if man.get("source") == "Electricity Maps":
        return f"Electricity Maps {man.get('year', '')} (life-cycle gCO\u2082eq/kWh)".replace("  ", " ")
    return f"hourly CI CSVs from {ci_dir.name}/ (no MANIFEST.json)"


class CIConfig:
    """Carbon-intensity source.  ``ci_dir=None`` -> synthetic_ci() for all six DCs.  Otherwise
    real hourly CSVs ``<ci_dir>/<REGION>.csv``: the DCs are those whose region the directory's
    MANIFEST.json lists (all six if there is no manifest); a listed region without a file is an
    error, never a silent fallback to synthetic data."""

    def __init__(self, ci_dir: str | Path | None = None, start_utc: str = DEFAULT_CI_START):
        self.dcs = DEFAULT_DCS
        self.ci_csv = None
        self.start_utc = start_utc if ci_dir else None
        if ci_dir:
            ci_dir = Path(ci_dir)
            man = _manifest(ci_dir) if ci_dir.is_dir() else {}
            if man.get("regions"):
                self.dcs = tuple(d for d in DEFAULT_DCS if d[1] in man["regions"])
            if "DE" not in {r for _, r in self.dcs}:
                raise ValueError(f"{ci_dir}: the source DC (DE) has no CI data")
            self.ci_csv = scan_ci_dir(ci_dir, [r for _, r in self.dcs])
        offsets = {hours_from_series_start(p, start_utc) for p in self.ci_csv.values()} if self.ci_csv else {0}
        if len(offsets) != 1:
            raise ValueError(f"CI files in {ci_dir} do not share a first timestamp")
        self.offset = offsets.pop()
        self.label = f"{_source_text(man, ci_dir)}@{start_utc}" if ci_dir else "synthetic"

    def write(self, results: Path) -> None:
        results.mkdir(parents=True, exist_ok=True)
        info = {"label": self.label, "start_utc": self.start_utc, "offset_hours": self.offset,
                "dcs": [list(d) for d in self.dcs],
                "files": {r: str(p) for r, p in (self.ci_csv or {}).items()},
                **provenance()}
        (results / CI_SOURCE_FILE).write_text(json.dumps(info, indent=2) + "\n")

def provenance() -> dict:
    """Which code produced a results folder: solver build and git commit (dirty if uncommitted)."""
    import subprocess
    from .cwm_runner import DEPLOY_DIR, file_sha256

    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    solver = DEPLOY_DIR / "solve_cwm"
    return {"solver_sha256": file_sha256(solver) if solver.exists() else None,
            "git_commit": git("rev-parse", "HEAD") or None,
            "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


GRID_DAGS = ("atacseq200", "eager1000")
DATA_SIZES_GB = (100.0, 300.0, 1000.0, 3000.0, 10000.0)
ALPHAS = (1.2, 1.4, 1.6, 1.8, 2.0, 2.25, 2.5)
GRID_START_HOUR = 6  # submission at 06:00 UTC (before the German solar dip)

HEADLINE_DAGS = ("atacseq200", "eager1000", "chipseq1000", "methylseq1000")
HEADLINE_START_HOURS = (0, 12)
HEADLINE_ALPHAS = (1.5, 2.0)
HEADLINE_SEEDS = (42, 43, 44)

EPS_DEFAULT = 0.02
EPS_SWEEP = (0.001, 0.005, 0.02, 0.06)  # kWh/GB

SENS_DAG, SENS_SIZE, SENS_ALPHA, SENS_START = "eager1000", 1000.0, 2.0, 6
SENS_UNITS_PER_HOUR = (15, 30, 60)  # kappa = 240, 120, 60 s/unit
SENS_BANDWIDTH = (0.5, 1.0, 2.0, 5.0, 10.0)  # Gbps
SENS_FORECAST_SIGMA = (0.0, 0.1, 0.25, 0.5)
SENS_FORECAST_SEEDS = (0, 1, 2)

# Multi-date study (real CI only): does the single-date picture hold across seasons and times of day?
MD_DAGS = ("atacseq200", "eager1000")
MD_SIZES_GB = (100.0, 1000.0)
MD_ALPHAS = (1.5, 2.0, 2.5)
MD_START_HOURS = (0, 6, 12, 18)
MD_DIR = "multidate"
# Seasonal subset used for the final results (Jan, Apr, Jul, Oct third Wednesdays).  The pre-fix
# 12-date run showed every season behaves alike, so 4 dates keep the conclusions at a third of the
# compute; `--dates all` runs all 12.
MD_DATES_IDX = (0, 3, 6, 9)


def third_wednesdays(year: int = 2024) -> tuple[str, ...]:
    """One weekday per month, the same weekday as DEFAULT_CI_START (third Wednesday)."""
    out = []
    for m in range(1, 13):
        weds = [d for d in calendar.Calendar().itermonthdates(year, m) if d.month == m and d.weekday() == 2]
        out.append(weds[2].isoformat())
    return tuple(out)


# W1: heterogeneous DCs.  A tier = processor mix (CWM cluster file with 72 processors, so the 5112
# communication links stay valid) + facility PUE:
#   efficient  PE4-PE6 (faster: HEFT makespan 168/214 for atacseq200/eager1000), PUE 1.10 (hyperscale)
#   standard   the shared CWM "small" cluster (all six types, 168/335),         PUE 1.55 (industry average)
#   legacy     PE1-PE3 + PE6 (slower: 204/448),                                PUE 2.00 (older facility)
# Every DC not named in a scenario is "standard".  Scenarios are fixed before any run:
#   homogeneous  every DC standard (= the baseline model)
#   aligned      the cleanest grids (Oslo, Paris) have efficient hardware
#   opposed      the cleanest grids have legacy hardware, the dirtier remote ones efficient
#   mixed        one clean grid legacy (Oslo), one remote efficient (California)
HW_DIR = REPO_ROOT / "cwm_multidc" / "data" / "clusters"
HW_SCENARIOS = {
    "homogeneous": {},
    "aligned": {"DC_Oslo": "efficient", "DC_Paris": "efficient"},
    "opposed": {"DC_Oslo": "legacy", "DC_Paris": "legacy", "DC_Warsaw": "efficient", "DC_California": "efficient"},
    "mixed": {"DC_Oslo": "legacy", "DC_California": "efficient"},
}
# Jan (Oslo is the greenest grid) and Jul (Paris is): the two regimes in which a legacy Oslo
# can or cannot change the decision.  Chosen after the smoke test showed grid CI differences
# (about 5x) dwarf realistic PUE differences (at most 2x), so the cases that can flip are the
# close calls between the two clean grids.
HW_DATES_IDX = (0, 6)
HW_START_HOURS = (6,)  # the hour where waiting matters most; one hour keeps W1 to about 1 h
HW_DIRNAME = "hetero"


HW_TIERS = {
    "efficient": HardwareTier("efficient", HW_DIR / "efficient.json", 1.10),
    "standard": HardwareTier("standard", None, 1.55),
    "legacy": HardwareTier("legacy", HW_DIR / "legacy.json", 2.00),
}


def hw_tiers(scenario: str, dcs=DEFAULT_DCS) -> dict:
    named = HW_SCENARIOS[scenario]
    return {name: HW_TIERS[named.get(name, "standard")] for name, _ in dcs}


# W2: contention.  Each DC has a diurnal queue: a job that becomes ready there waits
# rho * weight * CT_PEAK_H hours if it arrives in local business hours (09-18, DST-aware) and
# rho * weight * CT_OFF_H hours otherwise.  Weights encode "clean regions attract load": the two
# cleanest grids are the most contended.  Fixed before any run; rho = 0 is the baseline model.
CT_WEIGHTS = {"DC_Oslo": 1.0, "DC_Paris": 1.0, "DC_Frankfurt": 0.5, "DC_California": 0.5,
              "DC_Warsaw": 0.25, "DC_Mumbai": 0.5}
CT_PEAK_H, CT_OFF_H = 2.0, 0.5
CT_RHOS = (0.0, 1.0, 2.0)
CT_DATES_IDX = (0, 6)  # Jan (Oslo greenest), Jul (Paris greenest)
CT_START_HOURS = (0, 6, 12, 18)
CT_ALPHAS = (2.0, 2.5)  # tighter deadlines leave no room for any queue
CT_DIRNAME = "contention"


def ct_queues(rho: float, dcs=DEFAULT_DCS) -> dict:
    return {name: QueueSpec(rho * CT_WEIGHTS.get(name, 0.5) * CT_PEAK_H, rho * CT_WEIGHTS.get(name, 0.5) * CT_OFF_H)
            for name, _ in dcs} if rho > 0 else {}


METRICS = ("brown", "location")

SUMMARY_FIELDS = ["experiment", "dag", "start_hour", "data_size_gb", "alpha", "deadline_units", "m_ref_units",
                  "units_per_hour", "bandwidth_gbps", "forecast_sigma", "forecast_seed", "metric", "eps_kwh_per_gb",
                  "synthetic_ci", "ci_source", "ci_date", "scenario", "hardware", "contention_rho", "greenest_dc", "method", "dc", "t_net_h", "scheduler", "net_gco2", "comp_gco2",
                  "total_gco2", "comp_brown_kwh", "comp_dyn_kwh", "d_prime_units", "n_evals", "n_cwm_calls",
                  "separable_bound_gco2", "nonmono_drops", "nonmono_steps"]


class _Writer:
    def __init__(self, path: Path, fields: list[str] | None):
        self.path, self.fields, self.lock = path, fields, threading.Lock()
        if path.exists():  # outputs are regenerated (cheaply) from the solver cache
            path.unlink()

    def write(self, rows: list[dict]) -> None:
        if not rows:
            return
        with self.lock:
            if self.fields is None:
                self.fields = list(rows[0].keys())
            new = not self.path.exists()
            with open(self.path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=self.fields, extrasaction="ignore")
                if new:
                    w.writeheader()
                w.writerows(rows)


def summary_rows(res: SearchResult, meta: dict, eps_values=EPS_SWEEP) -> list[dict]:
    p = res.problem
    n_calls = sum(len(e.seeds) for e in res.evaluations if e.role == "grid" and e.scheduler == "cwm")
    out = []
    for metric in METRICS:
        drops, steps = res.nonmonotone_fraction(metric)
        for eps in eps_values:
            scale = eps / p.wan.energy_intensity_kwh_per_gb
            bound = res.separable_bound(metric, scale)
            for method, e in res.summary(metric, scale).items():
                row = dict(meta, dag=Path(p.dag).stem, data_size_gb=p.data_size_gb, alpha=p.alpha,
                           deadline_units=res.deadline_units, m_ref_units=res.m_ref_units,
                           units_per_hour=p.topology.timescale.units_per_hour, metric=metric,
                           eps_kwh_per_gb=eps, synthetic_ci=p.topology.synthetic,
                           greenest_dc=res.greenest_dc, method=method, n_evals=len(res.evaluations),
                           n_cwm_calls=n_calls, separable_bound_gco2=bound, nonmono_drops=drops,
                           nonmono_steps=steps)
                if e is not None:
                    row.update(dc=e.dc, t_net_h=e.t_net_s / 3600, scheduler=e.scheduler, net_gco2=e.net_gco2,
                               comp_gco2=e.comp_gco2, total_gco2=e.total_gco2, comp_brown_kwh=e.comp_brown_kwh,
                               comp_dyn_kwh=e.comp_dyn_kwh, d_prime_units=e.d_prime_units)
                out.append(row)
    return out


class Runner:
    def __init__(self, tag: str, ci: CIConfig, out: Path = RESULTS, write_ci: bool = True):
        out.mkdir(parents=True, exist_ok=True)
        if write_ci:
            ci.write(out)
        self.tag, self.ci = tag, ci
        self.cwm = CWMRunner(cache=ResultCache(RESULTS / "cache.jsonl"))  # one cache for every study
        self.evals_w = _Writer(out / f"{tag}_evals.csv", None)
        self.summ_w = _Writer(out / f"{tag}_summary.csv", SUMMARY_FIELDS)
        self.t0 = time.time()
        self.done = 0
        self.lock = threading.Lock()

    def topology(self, dag_path: Path, start: int, ts: TimeScale, bandwidth: float = 1.0,
                 ci: CIConfig | None = None, hardware: dict | None = None, queues: dict | None = None):
        ci = ci or self.ci
        m = self.cwm.heft_makespan(dag_path)
        alpha_max = max(ALPHAS + HEADLINE_ALPHAS)
        hours = int(math.ceil(alpha_max * m / ts.units_per_hour)) + 2
        return build_topology(hours, DEFAULT_CLUSTER, dcs=ci.dcs, ci_csv=ci.ci_csv,
                              start_hour=ci.offset + start,
                              timescale=ts, bandwidth_gbps=bandwidth, hardware=hardware, queues=queues)

    def log(self, total: int, msg: str):
        with self.lock:
            self.done += 1
            print(f"[{self.tag} {self.done}/{total} {time.time() - self.t0:6.0f}s] {msg}", flush=True)

    def record(self, res: SearchResult, meta: dict):
        meta = {"ci_source": self.ci.label, "ci_date": self.ci.start_utc, **meta}
        self.evals_w.write([dict(r, **meta) for r in res.records()])
        self.summ_w.write(summary_rows(res, meta))


def _fmt(res: SearchResult) -> str:
    b = res.best
    if b is None:
        return "Ours=infeasible"
    return f"Ours={b.dc} T_net={b.t_net_s / 3600:.2f}h total={b.total_gco2 / 1000:.2f}kg ({len(res.evaluations)} evals)"


def run_problems(configs, tag: str, seeds, control: bool, ci: CIConfig, outer: int = 2,
                 out: Path = RESULTS) -> None:
    R = Runner(tag, ci, out)
    configs = list(configs)

    def one(cfg):
        dag, start, size, alpha = cfg
        dag_path = DAG_DIR / f"{dag}.dot"
        topo = R.topology(dag_path, start, TimeScale())
        res = solve(Problem(dag_path, topo, size, alpha=alpha, seeds=tuple(seeds),
                            equal_budget_control=control), R.cwm)
        R.record(res, {"experiment": tag, "start_hour": start, "bandwidth_gbps": 1.0})
        R.log(len(configs), f"{dag} start={start} D={size:g}GB a={alpha}: {_fmt(res)}")

    with ThreadPoolExecutor(max_workers=outer) as ex:
        list(ex.map(one, configs))


def cmd_grid(args) -> None:
    run_problems(itertools.product(GRID_DAGS, (GRID_START_HOUR,), DATA_SIZES_GB, ALPHAS),
                 "grid", seeds=(42,), control=False, ci=_ci(args), out=_out(args))


def cmd_headline(args) -> None:
    run_problems(itertools.product(HEADLINE_DAGS, HEADLINE_START_HOURS, (1000.0,), HEADLINE_ALPHAS),
                 "headline", seeds=HEADLINE_SEEDS, control=True, ci=_ci(args), out=_out(args))


def cmd_sensitivity(args) -> None:
    R = Runner("sensitivity", _ci(args), _out(args))
    dag_path = DAG_DIR / f"{SENS_DAG}.dot"
    jobs = ([("kappa", u, 1.0, 0.0, 0) for u in SENS_UNITS_PER_HOUR]
            + [("bandwidth", 30, b, 0.0, 0) for b in SENS_BANDWIDTH if b != 1.0]
            + [("forecast", 30, 1.0, s, fs) for s in SENS_FORECAST_SIGMA if s > 0 for fs in SENS_FORECAST_SEEDS])
    total = len(jobs)

    def one(job):
        kind, u, bw, sigma, fseed = job
        actual = R.topology(dag_path, SENS_START, TimeScale(u), bw)
        meta = {"experiment": kind, "start_hour": SENS_START, "bandwidth_gbps": bw,
                "forecast_sigma": sigma, "forecast_seed": fseed, "ci_source": R.ci.label}
        prob = Problem(dag_path, actual, SENS_SIZE, alpha=SENS_ALPHA, seeds=(42,), equal_budget_control=True)
        if kind != "forecast":
            res = solve(prob, R.cwm)
            R.record(res, meta)
            R.log(total, f"{kind} U={u} B={bw}: {_fmt(res)}")
            return
        # decide on a noisy forecast, then realise every method's choice on actual CI
        fc = with_ci(actual, lambda s: perturb_ci(s, sigma, fseed))
        dec = solve(replace(prob, topology=fc, equal_budget_control=False), R.cwm)
        # realise only the chosen points (each method, each metric) on actual CI
        chosen = {(e.dc, e.t_net_s, e.scheduler) for metric in METRICS
                  for m, e in dec.summary(metric).items() if e is not None and m != "C1"}
        lookup = {k: evaluate(prob, R.cwm, k[0], k[1], dec.deadline_units, k[2]) for k in sorted(chosen)}
        dec_sel = dec.summary("brown")
        rows = []
        for metric in METRICS:
            sel = {m: (None if e is None else lookup.get((e.dc, e.t_net_s, e.scheduler))) for m, e in
                   (dec.summary(metric).items())}
            for method, e in sel.items():
                row = dict(meta, dag=SENS_DAG, data_size_gb=SENS_SIZE, alpha=SENS_ALPHA,
                           deadline_units=dec.deadline_units, m_ref_units=dec.m_ref_units, units_per_hour=u,
                           metric=metric, eps_kwh_per_gb=EPS_DEFAULT, synthetic_ci=actual.synthetic,
                           greenest_dc=dec.greenest_dc, method=method, n_evals=len(dec.evaluations))
                if e is not None:
                    e = e.under(metric)
                    row.update(dc=e.dc, t_net_h=e.t_net_s / 3600, scheduler=e.scheduler, net_gco2=e.net_gco2,
                               comp_gco2=e.comp_gco2, total_gco2=e.total_gco2, comp_brown_kwh=e.comp_brown_kwh,
                               comp_dyn_kwh=e.comp_dyn_kwh, d_prime_units=e.d_prime_units)
                rows.append(row)
        R.summ_w.write(rows)
        R.log(total, f"forecast sigma={sigma} seed={fseed}: decided {dec_sel['Ours'].dc if dec_sel['Ours'] else None}")

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, jobs))


# H6 (substitution test, fixed before running): without a temporally flat clean grid (Oslo hydro,
# Paris nuclear), timing should matter more, so Ours' gain over B3 should be larger.  Same problems
# as `multidate`, candidate DCs restricted to the strongly varying grids.
SUB_REGIONS = ("DE", "PL", "US-CAL")
SUB_DIR = "substitution"


def cmd_multidate(args) -> None:
    if args.ci_dir is None:
        raise SystemExit("multidate needs real CI: pass --ci-dir")
    regions = getattr(args, "regions", None)
    tag, subdir = ("substitution", SUB_DIR) if regions else ("multidate", MD_DIR)
    if args.dates == "all":
        dates = third_wednesdays()
    elif args.dates:
        dates = tuple(args.dates.split(","))
    else:
        dates = tuple(third_wednesdays()[i] for i in MD_DATES_IDX)
    cis = {d: CIConfig(args.ci_dir, d) for d in dates}
    if regions:
        for c in cis.values():
            c.dcs = tuple(dc for dc in c.dcs if dc[1] in regions)
            if not any(n == "DC_Frankfurt" for n, _ in c.dcs):
                raise SystemExit("the source DC (DE) must stay in --regions")
    R = Runner(tag, cis[dates[0]], _out(args) / subdir)
    (_out(args) / subdir / "dates.json").write_text(json.dumps(
        {"dates": list(dates), "start_hours_utc": list(MD_START_HOURS), "dcs": [list(d) for d in cis[dates[0]].dcs],
         "label": cis[dates[0]].label.rsplit("@", 1)[0]}, indent=2) + "\n")
    # cheapest problems first, so a partial run already covers every date
    jobs = sorted(itertools.product(dates, MD_START_HOURS, MD_DAGS, MD_SIZES_GB, MD_ALPHAS),
                  key=lambda j: (MD_DAGS.index(j[2]), j[0], j[1], j[3], j[4]))

    def one(job):
        date, start, dag, size, alpha = job
        ci = cis[date]
        dag_path = DAG_DIR / f"{dag}.dot"
        topo = R.topology(dag_path, start, TimeScale(), ci=ci)
        res = solve(Problem(dag_path, topo, size, alpha=alpha, seeds=(42,), equal_budget_control=False), R.cwm)
        R.record(res, {"experiment": tag, "start_hour": start, "bandwidth_gbps": 1.0,
                       "ci_source": ci.label, "ci_date": date})
        R.log(len(jobs), f"{date} {dag} start={start} D={size:g}GB a={alpha}: {_fmt(res)}")

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, jobs))


NOISE_THRESHOLD = 0.05  # re-test multi-date problems where Ours beats B3 by at least this (location metric)


def noise_problems(summary_csv: Path, threshold: float = NOISE_THRESHOLD) -> list[tuple]:
    """(date, start, dag, size, alpha) of multi-date problems where Ours beats B3 by >= threshold,
    location metric, eps = EPS_DEFAULT, in the single-seed run."""
    import pandas as pd

    s = pd.read_csv(summary_csv)
    s = s[(s.metric == "location") & (abs(s.eps_kwh_per_gb - EPS_DEFAULT) < 1e-12)]
    keys = ["ci_date", "start_hour", "dag", "data_size_gb", "alpha"]
    piv = s.pivot_table(index=keys, columns="method", values="total_gco2", aggfunc="first")
    win = piv[(piv["B3"] > 0) & (1 - piv["Ours"] / piv["B3"] >= threshold)]
    return [(d, int(h), g, float(z), float(a)) for d, h, g, z, a in win.index]


def cmd_multidate_noise(args) -> None:
    """Noise control for the multi-date waiting gains: re-solve the winning problems with the headline
    seeds and the equal-solver-budget control C1.  A gain that survives 3 seeds and beats C1 is not
    best-of-N luck of the CWM heuristic."""
    if args.ci_dir is None:
        raise SystemExit("multidate-noise needs real CI: pass --ci-dir")
    src = _out(args) / MD_DIR / "multidate_summary.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found: run `multidate` first")
    jobs = noise_problems(src)
    cis = {d: CIConfig(args.ci_dir, d) for d in sorted({j[0] for j in jobs})}
    R = Runner("multidate_noise", next(iter(cis.values())), _out(args) / MD_DIR, write_ci=False)
    jobs.sort(key=lambda j: (MD_DAGS.index(j[2]), j))

    def one(job):
        date, start, dag, size, alpha = job
        ci = cis[date]
        dag_path = DAG_DIR / f"{dag}.dot"
        topo = R.topology(dag_path, start, TimeScale(), ci=ci)
        res = solve(Problem(dag_path, topo, size, alpha=alpha, seeds=HEADLINE_SEEDS, equal_budget_control=True),
                    R.cwm)
        R.record(res, {"experiment": "multidate_noise", "start_hour": start, "bandwidth_gbps": 1.0,
                       "ci_source": ci.label, "ci_date": date})
        R.log(len(jobs), f"{date} {dag} start={start} D={size:g}GB a={alpha}: {_fmt(res)}")

    print(f"{len(jobs)} problems with location gain >= {NOISE_THRESHOLD:.0%} over B3", flush=True)
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, jobs))


def cmd_hetero(args) -> None:
    if args.ci_dir is None:
        raise SystemExit("hetero needs real CI: pass --ci-dir")
    all_dates = third_wednesdays()
    dates = tuple(args.dates.split(",")) if args.dates else tuple(all_dates[i] for i in HW_DATES_IDX)
    scenarios = tuple(args.scenarios.split(",")) if args.scenarios else tuple(HW_SCENARIOS)
    cis = {d: CIConfig(args.ci_dir, d) for d in dates}
    out = _out(args) / HW_DIRNAME
    R = Runner("hetero", cis[dates[0]], out)
    (out / "scenarios.json").write_text(json.dumps(
        {"dates": list(dates), "start_hours_utc": list(HW_START_HOURS), "scenarios": {s: HW_SCENARIOS[s] for s in scenarios},
         "label": cis[dates[0]].label.rsplit("@", 1)[0]}, indent=2) + "\n")
    jobs = sorted(itertools.product(scenarios, dates, HW_START_HOURS, MD_DAGS, MD_SIZES_GB, MD_ALPHAS),
                  key=lambda j: (MD_DAGS.index(j[3]), scenarios.index(j[0]), j[1:]))

    def one(job):
        scen, date, start, dag, size, alpha = job
        ci = cis[date]
        dag_path = DAG_DIR / f"{dag}.dot"
        topo = R.topology(dag_path, start, TimeScale(), ci=ci, hardware=hw_tiers(scen, ci.dcs))
        res = solve(Problem(dag_path, topo, size, alpha=alpha, seeds=(42,), equal_budget_control=False), R.cwm)
        hw = ";".join(f"{d.name}={d.hardware}" for d in topo.dcs)
        R.record(res, {"experiment": "hetero", "scenario": scen, "hardware": hw, "start_hour": start,
                       "bandwidth_gbps": 1.0, "ci_source": ci.label, "ci_date": date})
        R.log(len(jobs), f"{scen} {date} {dag} start={start} D={size:g}GB a={alpha}: {_fmt(res)}")

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, jobs))


def cmd_contention(args) -> None:
    if args.ci_dir is None:
        raise SystemExit("contention needs real CI: pass --ci-dir")
    all_dates = third_wednesdays()
    dates = tuple(args.dates.split(",")) if args.dates else tuple(all_dates[i] for i in CT_DATES_IDX)
    rhos = tuple(float(r) for r in args.rhos.split(",")) if args.rhos else CT_RHOS
    cis = {d: CIConfig(args.ci_dir, d) for d in dates}
    out = _out(args) / CT_DIRNAME
    R = Runner("contention", cis[dates[0]], out)
    (out / "contention.json").write_text(json.dumps(
        {"dates": list(dates), "start_hours_utc": list(CT_START_HOURS), "rhos": list(rhos),
         "weights": CT_WEIGHTS, "peak_h": CT_PEAK_H, "off_h": CT_OFF_H, "business_hours_local": [9, 18],
         "label": cis[dates[0]].label.rsplit("@", 1)[0]}, indent=2) + "\n")
    jobs = sorted(itertools.product(rhos, dates, CT_START_HOURS, MD_DAGS, MD_SIZES_GB, CT_ALPHAS),
                  key=lambda j: (MD_DAGS.index(j[3]), j))

    def one(job):
        rho, date, start, dag, size, alpha = job
        ci = cis[date]
        dag_path = DAG_DIR / f"{dag}.dot"
        topo = R.topology(dag_path, start, TimeScale(), ci=ci, queues=ct_queues(rho, ci.dcs))
        res = solve(Problem(dag_path, topo, size, alpha=alpha, seeds=(42,), equal_budget_control=False), R.cwm)
        R.record(res, {"experiment": "contention", "contention_rho": rho, "start_hour": start,
                       "bandwidth_gbps": 1.0, "ci_source": ci.label, "ci_date": date})
        R.log(len(jobs), f"rho={rho:g} {date} {dag} start={start} D={size:g}GB a={alpha}: {_fmt(res)}")

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(one, jobs))


def cmd_plot(_args) -> None:
    from . import plots

    plots.make_all(RESULTS)


def _out(args) -> Path:
    """Where tables go.  The solver cache is always results/cache.jsonl, so a run with --out DIR
    only warms the cache (used by run_chunks.sh) and a later run without it rebuilds results/."""
    return Path(args.out).resolve() if getattr(args, "out", None) else RESULTS


def _ci(args) -> CIConfig:
    return CIConfig(args.ci_dir, args.ci_start)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ci_args = argparse.ArgumentParser(add_help=False)
    ci_args.add_argument("--ci-dir", type=Path, default=None,
                         help="directory of Electricity Maps hourly CSVs named <REGION>.csv "
                              "(DE, NO, FR, PL, US-CAL, IN); omit for synthetic CI")
    ci_args.add_argument("--out", type=Path, default=None,
                         help="write tables here instead of cwm_multidc/results (solver cache is shared)")
    ci_args.add_argument("--ci-start", default=DEFAULT_CI_START,
                         help=f"UTC date the experiment start hours fall on (real CI only; default {DEFAULT_CI_START})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("grid", cmd_grid), ("headline", cmd_headline), ("sensitivity", cmd_sensitivity)):
        sub.add_parser(name, parents=[ci_args]).set_defaults(fn=fn)
    md = sub.add_parser("multidate", parents=[ci_args])
    md.add_argument("--dates", default=None,
                    help="comma-separated UTC dates, or 'all' for the third Wednesday of every month "
                         "(default: Jan/Apr/Jul/Oct third Wednesdays)")
    md.set_defaults(fn=cmd_multidate)
    sb = sub.add_parser("substitution", parents=[ci_args],
                        help=f"multidate with candidate DCs restricted to {SUB_REGIONS} (H6)")
    sb.add_argument("--dates", default=None)
    sb.set_defaults(fn=cmd_multidate, regions=SUB_REGIONS)
    sub.add_parser("multidate-noise", parents=[ci_args]).set_defaults(fn=cmd_multidate_noise)
    hz = sub.add_parser("hetero", parents=[ci_args])
    hz.add_argument("--dates", default=None, help="comma-separated UTC dates (default: Jan and Jul third Wednesdays)")
    hz.add_argument("--scenarios", default=None, help=f"comma-separated subset of {list(HW_SCENARIOS)}")
    hz.set_defaults(fn=cmd_hetero)
    ct = sub.add_parser("contention", parents=[ci_args])
    ct.add_argument("--dates", default=None, help="comma-separated UTC dates (default: Jan and Jul third Wednesdays)")
    ct.add_argument("--rhos", default=None, help=f"comma-separated contention levels (default {CT_RHOS})")
    ct.set_defaults(fn=cmd_contention)
    sub.add_parser("plot").set_defaults(fn=cmd_plot)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
