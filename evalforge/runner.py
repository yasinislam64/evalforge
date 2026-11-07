"""Run a suite against a provider concurrently and collect results."""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .providers import Provider
from .scorers import JUDGE_PROMPT, JudgeFn, parse_judge_verdict, score
from .suite import Suite


@dataclass
class CheckResult:
    type: str
    passed: bool
    reason: str


@dataclass
class CaseResult:
    id: str
    passed: bool
    output: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    checks: list[CheckResult]
    tags: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class RunResult:
    suite: str
    model: str
    started_at: str
    cases: list[CaseResult]

    @property
    def pass_rate(self) -> float:
        return sum(c.passed for c in self.cases) / len(self.cases) if self.cases else 0.0

    def to_dict(self) -> dict:
        return {**asdict(self), "pass_rate": self.pass_rate}

    @classmethod
    def from_dict(cls, d: dict) -> "RunResult":
        cases = [CaseResult(**{**c, "checks": [CheckResult(**k) for k in c["checks"]]}) for c in d["cases"]]
        return cls(suite=d["suite"], model=d["model"], started_at=d["started_at"], cases=cases)


def make_judge(provider: Provider) -> JudgeFn:
    async def judge(case_input: str, output: str, rubric: str) -> tuple[bool, str]:
        prompt = JUDGE_PROMPT.format(input=case_input, output=output, rubric=rubric)
        reply = await provider.complete("You are a strict, fair grader.", prompt, temperature=0.0, max_tokens=4000)  # room for adaptive thinking before the verdict
        return parse_judge_verdict(reply.text)

    return judge


async def run_suite(
    suite: Suite,
    provider: Provider,
    *,
    judge_provider: Provider | None = None,
    concurrency: int = 5,
    tags: set[str] | None = None,
) -> RunResult:
    judge = make_judge(judge_provider or provider)
    sem = asyncio.Semaphore(concurrency)
    cases = [c for c in suite.cases if not tags or tags & set(c.tags)]

    async def run_case(case) -> CaseResult:
        async with sem:
            start = time.perf_counter()
            try:
                comp = await provider.complete(
                    suite.system, case.input, temperature=suite.temperature, max_tokens=suite.max_tokens
                )
            except Exception as e:  # keep going; record the failure
                return CaseResult(case.id, False, "", 0.0, 0, 0, [], case.tags, error=f"{type(e).__name__}: {e}")
            latency = (time.perf_counter() - start) * 1000
            checks = []
            for check in case.checks:
                ok, reason = await score(check, case.input, comp.text, judge)
                checks.append(CheckResult(check.type, ok, reason))
            return CaseResult(
                case.id,
                all(c.passed for c in checks),
                comp.text,
                round(latency, 1),
                comp.input_tokens,
                comp.output_tokens,
                checks,
                case.tags,
            )

    results = await asyncio.gather(*(run_case(c) for c in cases))
    return RunResult(
        suite=suite.name,
        model=provider.name,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        cases=list(results),
    )
