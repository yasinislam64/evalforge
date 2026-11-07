import pytest

from evalforge.scorers import parse_judge_verdict, score, score_deterministic
from evalforge.suite import Check


@pytest.mark.parametrize(
    "check, output, expected",
    [
        (Check("exact", "42"), " 42 \n", True),
        (Check("exact", "42"), "The answer is 42", False),
        (Check("contains", ["$8", "pro"]), "Pro costs $8/month", True),
        (Check("contains", "refund"), "Contact billing", False),
        (Check("not_contains", ["guarantee"]), "We guarantee it", False),
        (Check("regex", r"^\d{3}-\d{4}$"), "555-1234", True),
        (Check("json_keys", ["a", "b"]), '```json\n{"a": 1, "b": 2}\n```', True),
        (Check("json_keys", ["a", "b"]), '{"a": 1}', False),
        (Check("json_keys", ["a"]), "not json", False),
        (Check("max_words", 3), "one two three", True),
        (Check("max_words", 3), "one two three four", False),
    ],
)
def test_deterministic_scorers(check, output, expected):
    passed, reason = score_deterministic(check, output)
    assert passed is expected
    assert reason


def test_parse_judge_verdict():
    assert parse_judge_verdict("PASS: recommends Team") == (True, "recommends Team")
    assert parse_judge_verdict("fail: ignores rubric")[0] is False
    passed, reason = parse_judge_verdict("Sure! It looks good.")
    assert passed is False and "unparseable" in reason


async def test_llm_judge_without_judge_fails_cleanly():
    passed, reason = await score(Check("llm_judge", "be nice"), "hi", "hello", judge=None)
    assert not passed and "judge" in reason
