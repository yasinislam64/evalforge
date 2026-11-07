"""Model providers. Anything with an async `complete` method works."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    name: str

    async def complete(self, system: str, prompt: str, *, temperature: float, max_tokens: int) -> Completion: ...


class AnthropicProvider:
    """Claude via the Anthropic SDK, with retries on transient errors."""

    def __init__(self, model: str, max_retries: int = 3):
        import anthropic

        self.name = model
        self._client = anthropic.AsyncAnthropic()
        self._errors = (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError)
        self._max_retries = max_retries

    async def complete(self, system: str, prompt: str, *, temperature: float, max_tokens: int) -> Completion:
        for attempt in range(self._max_retries + 1):
            try:
                msg = await self._client.messages.create(
                    model=self.name,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = "".join(b.text for b in msg.content if b.type == "text")
                return Completion(text, msg.usage.input_tokens, msg.usage.output_tokens)
            except self._errors:
                if attempt == self._max_retries:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("unreachable")


class ScriptedProvider:
    """Deterministic provider for tests and offline demos: maps prompt -> reply."""

    def __init__(self, replies: dict[str, str], default: str = "", name: str = "scripted"):
        self.name = name
        self.replies = replies
        self.default = default
        self.calls: list[str] = []

    async def complete(self, system: str, prompt: str, *, temperature: float, max_tokens: int) -> Completion:
        self.calls.append(prompt)
        text = self.replies.get(prompt, self.default)
        return Completion(text, input_tokens=len(prompt.split()), output_tokens=len(text.split()))
