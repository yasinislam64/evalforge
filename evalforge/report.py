"""Summaries, markdown reports, and regression comparison between two runs."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import quantiles

from .runner import RunResult


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return round(quantiles(values, n=100, method="inclusive")[p - 1], 1)


def summary(run: RunResult) -> dict:
    lat = [c.latency_ms for c in run.cases if c.error is None]
    return {
        "suite": run.suite,
        "model": run.model,
        "cases": len(run.cases),
        "passed": sum(c.passed for c in run.cases),
        "pass_rate": round(run.pass_rate * 100, 1),
        "errors": sum(c.error is not None for c in run.cases),
        "latency_p50_ms": percentile(lat, 50),
        "latency_p95_ms": percentile(lat, 95),
        "input_tokens": sum(c.input_tokens for c in run.cases),
        "output_tokens": sum(c.output_tokens for c in run.cases),
    }


def to_markdown(run: RunResult) -> str:
    s = summary(run)
    lines = [
        f"# EvalForge report: {s['suite']}",
        "",
        f"**Model:** `{s['model']}`  ",
        f"**Pass rate:** {s['passed']}/{s['cases']} ({s['pass_rate']}%)  ",
        f"**Latency:** p50 {s['latency_p50_ms']} ms, p95 {s['latency_p95_ms']} ms  ",
        f"**Tokens:** {s['input_tokens']} in / {s['output_tokens']} out",
        "",
        "| Case | Result | Details |",
        "|---|---|---|",
    ]
    for c in run.cases:
        if c.error:
            detail = c.error
        else:
            detail = "; ".join(f"{k.type}: {k.reason}" for k in c.checks if not k.passed) or "all checks passed"
        lines.append(f"| {c.id} | {'✅ pass' if c.passed else '❌ fail'} | {detail.replace('|', '/')} |")
    return "\n".join(lines) + "\n"


@dataclass
class Comparison:
    regressions: list[str]
    fixes: list[str]
    baseline_rate: float
    candidate_rate: float

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)


def compare(baseline: RunResult, candidate: RunResult) -> Comparison:
    """Case-level diff: which cases newly fail (regressions) or newly pass (fixes)."""
    base = {c.id: c.passed for c in baseline.cases}
    cand = {c.id: c.passed for c in candidate.cases}
    shared = base.keys() & cand.keys()
    return Comparison(
        regressions=sorted(i for i in shared if base[i] and not cand[i]),
        fixes=sorted(i for i in shared if not base[i] and cand[i]),
        baseline_rate=round(baseline.pass_rate * 100, 1),
        candidate_rate=round(candidate.pass_rate * 100, 1),
    )
