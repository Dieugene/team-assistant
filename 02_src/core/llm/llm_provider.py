"""LLM Provider implementation using Anthropic Claude API."""

import os
from typing import Protocol

import anthropic


class ILLMProvider(Protocol):
    """Abstraction for LLM access."""

    async def complete(
        self,
        messages: list[dict],  # [{"role": "user", "content": "..."}]
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate completion."""
        ...


class LLMProvider:
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20241022"):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def complete(
        self,
        messages: list[dict],  # [{"role": "user", "content": "..."}]
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Generate completion using Claude API."""
        try:
            # Convert messages format if needed
            # Our format: {"role": "user", "content": "..."}
            # Anthropic format: same

            response = await self._client.messages.create(
                model=self._model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
            )

            return response.content[0].text

        except Exception as e:
            # Re-raise for handling by caller
            raise RuntimeError(f"LLM API error: {e}") from e
