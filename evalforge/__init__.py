"""EvalForge: regression testing for LLM prompts."""
from .providers import AnthropicProvider, Completion, ScriptedProvider
from .report import compare, summary, to_markdown
from .runner import RunResult, run_suite
from .suite import Suite, SuiteError, load_suite, parse_suite

__all__ = [
    "AnthropicProvider", "Completion", "ScriptedProvider", "RunResult", "Suite", "SuiteError",
    "compare", "load_suite", "parse_suite", "run_suite", "summary", "to_markdown",
]
__version__ = "0.1.0"
