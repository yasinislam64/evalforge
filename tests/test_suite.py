import pytest

from evalforge.suite import SuiteError, load_suite, parse_suite


def test_parses_example_suite():
    suite = load_suite("examples/support_bot.yaml")
    assert suite.name == "support-bot"
    assert len(suite.cases) == 5
    assert suite.cases[0].checks[0].type == "contains"


@pytest.mark.parametrize(
    "data, message",
    [
        ({"cases": []}, "missing required key 'name'"),
        ({"name": "x", "cases": [{"id": "a", "checks": [{"exact": "y"}]}]}, "missing 'input'"),
        ({"name": "x", "cases": [{"id": "a", "input": "hi"}]}, "at least one check"),
        ({"name": "x", "cases": [{"id": "a", "input": "hi", "checks": [{"fuzzy": 1}]}]}, "unknown check type"),
        (
            {"name": "x", "cases": [{"id": "a", "input": "1", "checks": [{"exact": "1"}]},
                                    {"id": "a", "input": "2", "checks": [{"exact": "2"}]}]},
            "duplicate case id",
        ),
    ],
)
def test_rejects_bad_suites(data, message):
    with pytest.raises(SuiteError, match=message):
        parse_suite(data)
