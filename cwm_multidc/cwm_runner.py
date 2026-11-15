"""Subprocess wrapper around the CWM C++ solver (``solve_cwm``) and ``heft_mapping``.

All times passed to / returned from this module are in **CWM time units** (integers);
all energies are in **CWM power units x CWM time units** (Watt-units).  Conversion to
seconds / kWh / gCO2 is done by :mod:`cwm_multidc.data_loader` and
:mod:`cwm_multidc.optimizer` through an explicit :class:`~cwm_multidc.data_loader.TimeScale`.

``solve_cwm`` extensions used here (opt-in, baseline output unchanged without them):
    --per-interval   2nd stdout line: excess energy per profile interval (uint64);
                     3rd line: total energy (idle + work) per profile interval (uint64)
    --heft           evaluate the plain HEFT schedule instead of CWM (baseline B2)
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .profile_shifting import validate_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "code_cwm" / "code" / "deploy"
INSTANCES_DIR = REPO_ROOT / "code_cwm" / "experiments" / "reproduce" / "instances"
DEFAULT_CLUSTER = INSTANCES_DIR / "cluster_processors.json"
DAG_DIR = INSTANCES_DIR / "DAGs"

STATUS_OK = "ok"
STATUS_INFEASIBLE = "infeasible"  # solver ran but could not meet the deadline
STATUS_ERROR = "error"  # crash / bad input / unparsable output
STATUS_TIMEOUT = "timeout"


class CWMRunnerError(RuntimeError):
    """Raised for configuration errors (missing binaries, invalid inputs)."""


@dataclass(frozen=True)
class CWMResult:
    """Outcome of one solver invocation.

    Attributes:
        status: one of ``ok``, ``infeasible``, ``error``, ``timeout``.
        scheduler: ``cwm`` or ``heft``.
        deadline: deadline passed to the solver (CWM time units).
        elapsed_ms: solver-reported running time (ms), or None.
        makespan: schedule makespan (CWM time units), or None.
        carbon_cost: total excess (brown) energy in Watt-units (64-bit), or None.
        per_interval: excess energy per profile interval (len == number_of_intervals).
        per_interval_energy: total energy integral of P(t) per profile interval.
        message: stderr excerpt for non-ok results.
    """

    status: str
    scheduler: str
    deadline: int
    elapsed_ms: int | None = None
    makespan: int | None = None
    carbon_cost: int | None = None
    per_interval: tuple[int, ...] | None = None
    message: str = ""
    per_interval_energy: tuple[int, ...] | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["per_interval"] = list(self.per_interval) if self.per_interval is not None else None
        d["per_interval_energy"] = (list(self.per_interval_energy)
                                    if self.per_interval_energy is not None else None)
        return d

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "CWMResult":
        d = dict(d)
        for k in ("per_interval", "per_interval_energy"):
            if d.get(k) is not None:
                d[k] = tuple(int(x) for x in d[k])
        return cls(**d)


def parse_solver_output(stdout: str, expect_per_interval: bool, n_intervals: int | None = None):
    """Parse ``solve_cwm`` stdout.

    Returns (elapsed_ms, makespan, carbon_cost, per_interval, per_interval_energy); the
    last two are None without ``--per-interval``.

    Raises:
        ValueError: on any format violation (wrong field count, non-integers, per-interval
            vectors whose length or sum is inconsistent, energy below excess).
    """
    lines = [ln.strip() for ln in stdout.strip().splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty solver output")
    head = lines[0].split(",")
    if len(head) != 3:
        raise ValueError(f"expected 'elapsed_ms,makespan,carbon_cost', got {lines[0]!r}")
    elapsed_ms, makespan, carbon = (int(x) for x in head)
    if makespan <= 0 or carbon < 0 or elapsed_ms < 0:
        raise ValueError(f"implausible solver values: {lines[0]!r}")
    per = energy = None
    if expect_per_interval:
        if len(lines) != 3:
            raise ValueError(f"expected 3 lines with --per-interval, got {len(lines)}")
        per = tuple(int(x) for x in lines[1].split(","))
        energy = tuple(int(x) for x in lines[2].split(","))
        if any(x < 0 for x in per):
            raise ValueError("negative per-interval excess")
        if len(per) != len(energy):
            raise ValueError("excess and energy vectors differ in length")
        if n_intervals is not None and len(per) != n_intervals:
            raise ValueError(f"per-interval length {len(per)} != number_of_intervals {n_intervals}")
        if sum(per) != carbon:
            raise ValueError(f"per-interval sum {sum(per)} != total {carbon}")
        if any(e < x for e, x in zip(energy, per)):
            raise ValueError("total energy below excess energy in some interval")
    elif len(lines) != 1:
        raise ValueError(f"unexpected extra output lines: {lines[1:]!r}")
    return elapsed_ms, makespan, carbon, per, energy


def file_sha256(path: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ResultCache:
    """Thread-safe append-only JSONL cache of solver results keyed by input hash."""

    def __init__(self, path: str | os.PathLike[str] | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._mem: dict[str, CWMResult] = {}
        if self.path and self.path.exists():
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        res = CWMResult.from_json(rec["result"])
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue  # tolerate a torn last line
                    if res.status in (STATUS_ERROR, STATUS_TIMEOUT):
                        continue  # never reuse a failed run (older caches may hold some)
                    self._mem[rec["key"]] = res

    def get(self, key: str) -> CWMResult | None:
        with self._lock:
            return self._mem.get(key)

    def put(self, key: str, result: CWMResult) -> None:
        # Failures are not properties of the input: timeouts depend on machine load, and an "error" can
        # be a solver killed by a signal (e.g. Ctrl-C while a run was interrupted).  Never persist them,
        # otherwise an interrupted run leaves permanent false failures that later runs silently reuse.
        if result.status in (STATUS_TIMEOUT, STATUS_ERROR):
            return
        with self._lock:
            self._mem[key] = result
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a") as f:
                    f.write(json.dumps({"key": key, "result": result.to_json()}) + "\n")

    def __len__(self) -> int:
        return len(self._mem)


@dataclass
class CWMRunner:
    """Runs ``solve_cwm`` / ``heft_mapping`` on a given cluster.

    Args:
        cluster_json: CWM cluster configuration file.
        variant: ``small`` or ``large``.
        solve_bin / heft_bin: binary paths (default: ``code_cwm/code/deploy``).
        timeout_s: wall-clock limit per call.
        cache: optional :class:`ResultCache`.
    """

    cluster_json: Path = DEFAULT_CLUSTER
    variant: str = "small"
    solve_bin: Path = DEPLOY_DIR / "solve_cwm"
    heft_bin: Path = DEPLOY_DIR / "heft_mapping"
    timeout_s: float = 900.0
    cache: ResultCache | None = None
    _heft_ms_cache: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.cluster_json = Path(self.cluster_json)
        self.solve_bin = Path(self.solve_bin)
        self.heft_bin = Path(self.heft_bin)
        if self.variant not in ("small", "large"):
            raise CWMRunnerError(f"variant must be 'small' or 'large', got {self.variant!r}")
        for p in (self.cluster_json, self.solve_bin):
            if not p.exists():
                raise CWMRunnerError(f"required file not found: {p}")
        self.solver_sha256 = file_sha256(self.solve_bin)

    # ------------------------------------------------------------------ helpers
    def _key(self, dag: Path, profile: Mapping[str, Any], deadline: int, seed: int, scheduler: str) -> str:
        h = hashlib.sha256()
        h.update(json.dumps(
            {
                "dag": str(Path(dag).resolve()),
                "dag_mtime": os.path.getmtime(dag),
                "cluster": str(self.cluster_json.resolve()),
                "variant": self.variant,
                "profile": profile,
                "deadline": deadline,
                "seed": seed,
                "scheduler": scheduler,
                "output_format": 2,  # 2 = excess + total energy per interval
                # results from another solver build must never be reused (e.g. the pre-fix binary
                # with the out-of-bounds read in mapper.cpp)
                "solver_sha256": self.solver_sha256,
            },
            sort_keys=True,
        ).encode())
        return h.hexdigest()

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_s)

    # --------------------------------------------------------------------- API
    def solve(
        self,
        dag: str | os.PathLike[str],
        profile: Mapping[str, Any],
        deadline: int,
        seed: int = 42,
        scheduler: str = "cwm",
    ) -> CWMResult:
        """Schedule ``dag`` against ``profile`` with makespan <= ``deadline``.

        ``profile`` must be a valid CWM profile with ``horizon >= deadline``.  It is
        written to a private temp file for the duration of the call.
        """
        dag = Path(dag)
        if not dag.exists():
            raise CWMRunnerError(f"DAG not found: {dag}")
        if scheduler not in ("cwm", "heft"):
            raise CWMRunnerError(f"scheduler must be 'cwm' or 'heft', got {scheduler!r}")
        if not isinstance(deadline, int) or isinstance(deadline, bool) or deadline <= 0:
            raise CWMRunnerError(f"deadline must be a positive int (CWM units), got {deadline!r}")
        validate_profile(profile)
        if any(not float(b).is_integer() for b in profile["budgets"]):
            # C++ parses budgets as unsigned int; refuse silent truncation
            raise CWMRunnerError("profile budgets must be integers (C++ parses unsigned int)")
        if profile["horizon"] < deadline:
            raise CWMRunnerError(f"profile horizon {profile['horizon']} < deadline {deadline}")

        key = self._key(dag, profile, deadline, seed, scheduler)
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit

        fd, tmp = tempfile.mkstemp(prefix="cwm_profile_", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(profile, f)
            cmd = [str(self.solve_bin), str(dag), str(self.cluster_json), self.variant, tmp,
                   str(deadline), str(seed), "--per-interval"]
            if scheduler == "heft":
                cmd.append("--heft")
            try:
                proc = self._run(cmd)
            except subprocess.TimeoutExpired:
                res = CWMResult(STATUS_TIMEOUT, scheduler, deadline, message=f"timeout after {self.timeout_s}s")
                if self.cache is not None:
                    self.cache.put(key, res)
                return res
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass

        stderr_tail = "\n".join(ln for ln in proc.stderr.splitlines() if not ln.startswith("[DEBUG]"))[-500:]
        if proc.returncode != 0:
            status = STATUS_INFEASIBLE if "exceeds deadline" in proc.stderr else STATUS_ERROR
            res = CWMResult(status, scheduler, deadline, message=stderr_tail)
        else:
            try:
                el, mk, cc, per, en = parse_solver_output(proc.stdout, True, profile["number_of_intervals"])
            except ValueError as e:
                res = CWMResult(STATUS_ERROR, scheduler, deadline, message=f"parse error: {e}")
            else:
                if mk > deadline:  # defensive: binary already checks this
                    res = CWMResult(STATUS_INFEASIBLE, scheduler, deadline, el, mk, cc, per,
                                    "makespan > deadline", en)
                else:
                    res = CWMResult(STATUS_OK, scheduler, deadline, el, mk, cc, per, "", en)
        if self.cache is not None:
            self.cache.put(key, res)
        return res

    def heft_makespan(self, dag: str | os.PathLike[str]) -> int:
        """HEFT makespan of ``dag`` on this cluster (CWM time units).

        HEFT ignores the power profile, so a flat dummy profile is used.  This is the
        reference makespan M used to define deadlines D = alpha * M (as in the CWM paper).
        """
        dag = Path(dag)
        k = f"{dag.resolve()}|{self.cluster_json.resolve()}|{self.variant}"
        if k in self._heft_ms_cache:
            return self._heft_ms_cache[k]
        horizon = 10_000_000
        dummy = {"horizon": horizon, "number_of_intervals": 1, "intervals": [0, horizon], "budgets": [10**9]}
        fd, tmp = tempfile.mkstemp(prefix="cwm_flat_", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(dummy, f)
            if self.heft_bin.exists():
                proc = self._run([str(self.heft_bin), str(dag), str(self.cluster_json), self.variant, tmp])
                if proc.returncode != 0:
                    raise CWMRunnerError(f"heft_mapping failed: {proc.stdout[-300:]} {proc.stderr[-300:]}")
                last = proc.stdout.strip().splitlines()[-1]
                ms = int(last)
            else:  # fall back to solve_cwm --heft
                proc = self._run([str(self.solve_bin), str(dag), str(self.cluster_json), self.variant, tmp,
                                  str(horizon), "42", "--heft"])
                if proc.returncode != 0:
                    raise CWMRunnerError(f"solve_cwm --heft failed: {proc.stderr[-300:]}")
                ms = parse_solver_output(proc.stdout, False)[1]
        finally:
            os.remove(tmp)
        self._heft_ms_cache[k] = ms
        return ms
