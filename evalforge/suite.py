"""Load and validate eval suites from YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCORER_TYPES = {"exact", "contains", "not_contains", "regex", "json_keys", "max_words", "llm_judge"}


class SuiteError(ValueError):
    """Raised when a suite file is malformed."""


@dataclass
class Check:
    type: str
    value: Any = None


@dataclass
class Case:
    id: str
    input: str
    checks: list[Check]
    tags: list[str] = field(default_factory=list)


@dataclass
class Suite:
    name: str
    system: str
    cases: list[Case]
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int = 512


def _parse_check(raw: Any, case_id: str) -> Check:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise SuiteError(f"case {case_id}: each check must be a single-key mapping, got {raw!r}")
    (kind, value), = raw.items()
    if kind not in SCORER_TYPES:
        raise SuiteError(f"case {case_id}: unknown check type {kind!r} (expected one of {sorted(SCORER_TYPES)})")
    return Check(type=kind, value=value)


def parse_suite(data: dict[str, Any]) -> Suite:
    if not isinstance(data, dict):
        raise SuiteError("suite must be a mapping")
    for key in ("name", "cases"):
        if key not in data:
            raise SuiteError(f"suite is missing required key {key!r}")
    cases: list[Case] = []
    seen: set[str] = set()
    for i, raw in enumerate(data["cases"]):
        case_id = str(raw.get("id", f"case-{i + 1}"))
        if case_id in seen:
            raise SuiteError(f"duplicate case id {case_id!r}")
        seen.add(case_id)
        if "input" not in raw:
            raise SuiteError(f"case {case_id}: missing 'input'")
        checks = [_parse_check(c, case_id) for c in raw.get("checks", [])]
        if not checks:
            raise SuiteError(f"case {case_id}: needs at least one check")
        cases.append(Case(id=case_id, input=str(raw["input"]), checks=checks, tags=list(raw.get("tags", []))))
    return Suite(
        name=str(data["name"]),
        system=str(data.get("system", "")),
        cases=cases,
        model=data.get("model"),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(data.get("max_tokens", 512)),
    )


def load_suite(path: str | Path) -> Suite:
    with open(path, encoding="utf-8") as f:
        return parse_suite(yaml.safe_load(f))
