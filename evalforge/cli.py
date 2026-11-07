"""Command line: `evalforge run` and `evalforge compare`."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .report import compare, summary, to_markdown
from .runner import RunResult, run_suite
from .suite import SuiteError, load_suite

DEFAULT_MODEL = "claude-haiku-5-5"


def cmd_run(args: argparse.Namespace) -> int:
    from .providers import AnthropicProvider

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run evals.", file=sys.stderr)
        return 2
    try:
        suite = load_suite(args.suite)
    except (SuiteError, OSError) as e:
        print(f"Invalid suite: {e}", file=sys.stderr)
        return 2

    model = args.model or suite.model or DEFAULT_MODEL
    judge = AnthropicProvider(args.judge_model) if args.judge_model else None
    tags = set(args.tag) if args.tag else None
    run = asyncio.run(
        run_suite(suite, AnthropicProvider(model), judge_provider=judge, concurrency=args.concurrency, tags=tags)
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{suite.name}-{model}".replace("/", "_")
    (out / f"{stem}.json").write_text(json.dumps(run.to_dict(), indent=2))
    (out / f"{stem}.md").write_text(to_markdown(run))

    s = summary(run)
    print(f"{s['suite']} on {s['model']}: {s['passed']}/{s['cases']} passed ({s['pass_rate']}%), "
          f"p95 {s['latency_p95_ms']} ms")
    print(f"Report: {out / (stem + '.md')}")
    if args.min_pass_rate is not None and s["pass_rate"] < args.min_pass_rate:
        print(f"FAIL: pass rate below {args.min_pass_rate}%", file=sys.stderr)
        return 1
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    base = RunResult.from_dict(json.loads(Path(args.baseline).read_text()))
    cand = RunResult.from_dict(json.loads(Path(args.candidate).read_text()))
    cmp = compare(base, cand)
    print(f"Pass rate: {cmp.baseline_rate}% -> {cmp.candidate_rate}%")
    if cmp.fixes:
        print(f"Fixed ({len(cmp.fixes)}): {', '.join(cmp.fixes)}")
    if cmp.regressions:
        print(f"Regressions ({len(cmp.regressions)}): {', '.join(cmp.regressions)}", file=sys.stderr)
        return 1
    print("No regressions.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evalforge", description="Regression testing for LLM prompts.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run an eval suite")
    run.add_argument("suite")
    run.add_argument("--model")
    run.add_argument("--judge-model", help="model used for llm_judge checks (defaults to --model)")
    run.add_argument("--concurrency", type=int, default=5)
    run.add_argument("--tag", action="append", help="only run cases with this tag (repeatable)")
    run.add_argument("--out", default="runs")
    run.add_argument("--min-pass-rate", type=float, help="exit 1 if pass rate is below this percent")
    run.set_defaults(func=cmd_run)

    cmp = sub.add_parser("compare", help="diff two runs; exit 1 on regressions")
    cmp.add_argument("baseline")
    cmp.add_argument("candidate")
    cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
