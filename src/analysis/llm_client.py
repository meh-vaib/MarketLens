"""Provider-agnostic LLM client.

Supports Anthropic, OpenAI, and Ollama (local). The interface is intentionally
small: ``complete(system, user) -> str``.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

from config import get_settings
from src.utils import get_logger

log = get_logger("llm")


class LLMClient:
    """Single facade over multiple LLM providers."""

    def __init__(
        self,
        provider: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._init_provider()

    # ------------------------------------------------------------------ #
    def _init_provider(self) -> None:
        s = get_settings()
        if self.provider == "anthropic":
            try:
                from anthropic import Anthropic
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("anthropic package required") from e
            if not s.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = Anthropic(api_key=s.anthropic_api_key)
        elif self.provider == "openai":
            try:
                from openai import OpenAI
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("openai package required") from e
            if not s.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY not set")
            self._client = OpenAI(api_key=s.openai_api_key)
        elif self.provider == "ollama":
            self._ollama_base = s.ollama_base_url.rstrip("/")
            self._client = None
        elif self.provider == "groq":
            # Groq exposes an OpenAI-compatible HTTP API, so we reuse the
            # OpenAI SDK with a custom base_url.
            try:
                from openai import OpenAI
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("openai package required for groq provider") from e
            if not s.groq_api_key:
                raise RuntimeError("GROQ_API_KEY not set")
            self._client = OpenAI(
                api_key=s.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            raise ValueError(f"unsupported provider: {self.provider}")

    # ------------------------------------------------------------------ #
    def complete(self, system: str, user: str) -> str:
        """Synchronous text completion."""
        try:
            if self.provider == "anthropic":
                return self._complete_anthropic(system, user)
            if self.provider == "openai":
                return self._complete_openai(system, user)
            if self.provider == "ollama":
                return self._complete_ollama(system, user)
            if self.provider == "groq":
                # Same wire protocol as OpenAI, different host.
                return self._complete_openai(system, user)
        except Exception as e:  # noqa: BLE001
            log.error(f"LLM call failed ({self.provider}): {e}")
            return ""
        return ""

    # ------------------------------------------------------------------ #
    def complete_json(self, system: str, user: str) -> Optional[dict]:
        """Call the model and parse a JSON object out of the response.

        Robust to models that wrap JSON in markdown code fences.
        """
        raw = self.complete(system, user)
        if not raw:
            return None
        cleaned = raw.strip()
        # strip ```json ... ``` fences
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
            # remove trailing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        # find first { and last }
        try:
            start = cleaned.index("{")
            end = cleaned.rindex("}") + 1
            return json.loads(cleaned[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            log.warning(f"LLM JSON parse failed: {e}; raw={cleaned[:200]!r}")
            return None

    # ------------------------------------------------------------------ #
    # Provider implementations
    # ------------------------------------------------------------------ #
    def _complete_anthropic(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # ``content`` is a list of blocks; concatenate text blocks
        return "".join(getattr(b, "text", "") for b in resp.content)

    def _complete_openai(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def _complete_ollama(self, system: str, user: str) -> str:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                f"{self._ollama_base}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {"temperature": self.temperature},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")


_CLIENT: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Process-wide singleton."""
    global _CLIENT
    if _CLIENT is None:
        s = get_settings()
        _CLIENT = LLMClient(
            provider=s.llm_provider,
            model=s.llm_model,
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
        )
    return _CLIENT
