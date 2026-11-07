# EvalForge

Regression testing for LLM prompts. Write test cases in YAML, run them against a model, and get a pass rate, latency and token report. Then gate CI on it so a prompt or model change can't silently make your AI feature worse.

```bash
$ evalforge run examples/support_bot.yaml
support-bot on claude-haiku-5-5: 4/5 passed (80.0%), p95 1840.2 ms
Report: runs/support-bot-claude-haiku-5-5.md

$ evalforge compare runs/baseline.json runs/support-bot-claude-haiku-5-5.json
Pass rate: 100.0% -> 80.0%
Regressions (1): refund-policy
```

## Why

Changing a prompt or switching models is easy. Knowing whether you broke something is hard. EvalForge treats prompts like code: each behavior you care about becomes a test case, and every change gets checked against the last known-good run.

## Writing a suite

```yaml
name: support-bot
model: claude-haiku-5-5
system: |
  You are the support assistant for Acme Cloud Storage...
cases:
  - id: refund-policy
    input: I want my money back for last month.
    tags: [billing, safety]
    checks:
      - contains: billing@acme.example
      - not_contains: ["refund has been processed"]

  - id: storage-compare
    input: Which plan should a 10-person team needing 3 TB pick?
    checks:
      - llm_judge: Recommends the Team plan and explains it fits within 5 TB.
```

| Check | Passes when |
|---|---|
| `exact` | output equals the value (trimmed) |
| `contains` / `not_contains` | every / none of the strings appear (case-insensitive) |
| `regex` | the pattern matches |
| `json_keys` | output parses as a JSON object (code fences allowed) with these keys |
| `max_words` | output is at most N words |
| `llm_judge` | a grader model says the output meets the rubric |

## Commands

```bash
evalforge run SUITE [--model M] [--judge-model M] [--tag T] [--concurrency N] [--min-pass-rate 90]
evalforge compare BASELINE.json CANDIDATE.json   # exit 1 if any case regressed
```

Each run writes a JSON result and a Markdown report to `runs/`. `--min-pass-rate` and `compare` both exit non-zero on failure, so either can gate a CI job.

## Design

- **Async runner** with a concurrency limit, and retries with exponential backoff on rate limits and server errors. A failed case is recorded instead of crashing the run.
- **Pluggable providers.** Anything with an async `complete()` method works. `ScriptedProvider` makes the whole pipeline testable offline, including the LLM judge.
- **Strict suite validation** catches unknown check types, duplicate IDs and missing fields before any tokens are spent.
- **Case-level diffs.** `compare` reports exactly which cases regressed or got fixed, not just the aggregate score.

## Setup

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=...
pytest -q          # 22 tests, no API key needed
```

## Tech stack

Python 3.11+ · asyncio · Anthropic SDK · PyYAML · pytest · GitHub Actions
