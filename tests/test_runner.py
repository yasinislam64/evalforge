import json

from evalforge.cli import main
from evalforge.providers import Completion, ScriptedProvider
from evalforge.report import compare, summary, to_markdown
from evalforge.runner import RunResult, run_suite
from evalforge.suite import parse_suite

SUITE = parse_suite(
    {
        "name": "mini",
        "system": "Be brief.",
        "cases": [
            {"id": "capital", "input": "Capital of France?", "tags": ["geo"], "checks": [{"contains": "Paris"}]},
            {"id": "math", "input": "2+2?", "checks": [{"exact": "4"}]},
            {"id": "tone", "input": "Say hi", "checks": [{"llm_judge": "Is friendly"}]},
        ],
    }
)


async def test_run_suite_scores_each_case():
    model = ScriptedProvider({"Capital of France?": "Paris.", "2+2?": "5", "Say hi": "Hi there!"})
    judge = ScriptedProvider({}, default="PASS: friendly greeting", name="judge")
    run = await run_suite(SUITE, model, judge_provider=judge)

    results = {c.id: c for c in run.cases}
    assert results["capital"].passed
    assert not results["math"].passed
    assert results["tone"].passed
    assert round(run.pass_rate, 2) == 0.67
    assert len(judge.calls) == 1 and "Is friendly" in judge.calls[0]


async def test_tag_filter_and_error_handling():
    class Broken:
        name = "broken"

        async def complete(self, *a, **k) -> Completion:
            raise TimeoutError("model timed out")

    run = await run_suite(SUITE, Broken(), tags={"geo"})
    assert [c.id for c in run.cases] == ["capital"]
    assert run.cases[0].error == "TimeoutError: model timed out"
    assert summary(run)["errors"] == 1


async def test_report_and_regression_compare(tmp_path):
    good = ScriptedProvider({"Capital of France?": "Paris", "2+2?": "4", "Say hi": "Hi"}, name="v1")
    bad = ScriptedProvider({"Capital of France?": "Lyon", "2+2?": "4", "Say hi": "Hi"}, name="v2")
    judge = ScriptedProvider({}, default="PASS: ok")
    base = await run_suite(SUITE, good, judge_provider=judge)
    cand = await run_suite(SUITE, bad, judge_provider=judge)

    cmp = compare(base, cand)
    assert cmp.regressions == ["capital"] and cmp.has_regressions
    assert "❌ fail" in to_markdown(cand)

    # JSON round-trip + CLI exit codes
    base_path, cand_path = tmp_path / "base.json", tmp_path / "cand.json"
    base_path.write_text(json.dumps(base.to_dict()))
    cand_path.write_text(json.dumps(cand.to_dict()))
    assert RunResult.from_dict(json.loads(base_path.read_text())).pass_rate == 1.0
    assert main(["compare", str(base_path), str(cand_path)]) == 1
    assert main(["compare", str(base_path), str(base_path)]) == 0
