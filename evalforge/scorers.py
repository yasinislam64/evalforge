"""Scorers: each returns (passed, reason) for one check against one model output."""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from .suite import Check

JudgeFn = Callable[[str, str, str], Awaitable[tuple[bool, str]]]

JUDGE_PROMPT = """You are grading an AI assistant's answer against a rubric.

User input:
{input}

Assistant answer:
{output}

Rubric:
{rubric}

Reply with exactly one line: PASS or FAIL, then a colon and a short reason."""


def _strip_code_fence(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def score_deterministic(check: Check, output: str) -> tuple[bool, str]:
    out = output.strip()
    v = check.value
    if check.type == "exact":
        ok = out == str(v).strip()
        return ok, "matches exactly" if ok else f"expected exactly {v!r}"
    if check.type == "contains":
        needles = v if isinstance(v, list) else [v]
        missing = [n for n in needles if str(n).lower() not in out.lower()]
        return not missing, "contains all" if not missing else f"missing {missing}"
    if check.type == "not_contains":
        needles = v if isinstance(v, list) else [v]
        found = [n for n in needles if str(n).lower() in out.lower()]
        return not found, "none present" if not found else f"should not contain {found}"
    if check.type == "regex":
        ok = re.search(str(v), out, re.MULTILINE) is not None
        return ok, "regex matched" if ok else f"no match for /{v}/"
    if check.type == "json_keys":
        try:
            parsed = json.loads(_strip_code_fence(out))
        except json.JSONDecodeError as e:
            return False, f"invalid JSON: {e.msg}"
        if not isinstance(parsed, dict):
            return False, "JSON is not an object"
        missing = [k for k in v if k not in parsed]
        return not missing, "has all keys" if not missing else f"missing keys {missing}"
    if check.type == "max_words":
        n = len(out.split())
        return n <= int(v), f"{n} words (limit {v})"
    raise ValueError(f"not a deterministic check: {check.type}")


def parse_judge_verdict(text: str) -> tuple[bool, str]:
    line = text.strip().splitlines()[0] if text.strip() else ""
    verdict, _, reason = line.partition(":")
    verdict = verdict.strip().upper()
    if verdict not in {"PASS", "FAIL"}:
        return False, f"unparseable judge reply: {line[:80]!r}"
    return verdict == "PASS", reason.strip() or verdict.lower()


async def score(check: Check, case_input: str, output: str, judge: JudgeFn | None) -> tuple[bool, str]:
    if check.type == "llm_judge":
        if judge is None:
            return False, "llm_judge check needs a judge model"
        return await judge(case_input, output, str(check.value))
    return score_deterministic(check, output)
