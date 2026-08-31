"""LLMService — prompt + a Pydantic schema -> a validated instance of that
schema, behind a swappable provider (Phase 12, docs/ARCHITECTURE.md §9).
Nothing outside this module imports an LLM provider SDK directly — same
shape as EmbeddingService (Phase 6). `generate_structured` is async, like
every other service function in this codebase (AsyncSession throughout)
— a sync HTTP call here would block the event loop inside a FastAPI
request handler.

Three implementations, not one, because ARCHITECTURE.md §9 names all
three explicitly (`AnthropicLLMService`, `OpenAILLMService`,
`LocalLLMService`) and each earns its place differently here:
  - Anthropic and OpenAI are the two real hosted providers a production
    deployment would use.
  - Local (Ollama) is what this session could actually exercise live —
    no LLM_API_KEY is configured in this environment, but Ollama is
    already installed with local models, so it's the one provider this
    phase's tests genuinely call end-to-end rather than only mocking.

Each provider gets the structured output from the model differently
(Anthropic: forced tool-use; OpenAI: native structured-output JSON
schema; Ollama: its own `format` JSON-schema constraint), but all three
converge on the same contract: parse to a dict, then
`response_schema.model_validate(...)` — the Pydantic model is what's
trusted, never "the SDK says this matches."
"""
import json
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_OLLAMA_MODEL = "qwen2.5"


class LLMGenerationError(Exception):
    """Raised when a provider can't produce a schema-valid response —
    a network/API failure, or a response that fails Pydantic validation
    even after the provider's own structured-output constraint. Callers
    (explanation_service.py) treat this as "explanation unavailable",
    never as a reason to fall back to unvalidated output."""


class LLMService(Protocol):
    @property
    def model_name(self) -> str: ...

    async def generate_structured(self, prompt: str, response_schema: type[T]) -> T: ...


class AnthropicLLMService:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(self, prompt: str, response_schema: type[T]) -> T:
        client = self._get_client()
        # Forced tool-use is the standard way to get schema-constrained
        # JSON out of a Claude model: define one tool whose input_schema
        # *is* the response schema, then force that exact tool call.
        tool_name = "emit_result"
        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                tools=[
                    {
                        "name": tool_name,
                        "description": "Emit the structured result.",
                        "input_schema": response_schema.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )
            tool_use_block = next(b for b in response.content if b.type == "tool_use")
            return response_schema.model_validate(tool_use_block.input)
        except Exception as exc:
            raise LLMGenerationError(f"Anthropic generation failed: {exc}") from exc

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client


class OpenAILLMService:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(self, prompt: str, response_schema: type[T]) -> T:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "schema": response_schema.model_json_schema(),
                        "strict": True,
                    },
                },
            )
            content = response.choices[0].message.content
            return response_schema.model_validate(json.loads(content))
        except Exception as exc:
            raise LLMGenerationError(f"OpenAI generation failed: {exc}") from exc

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client


class LocalLLMService:
    """Ollama, for offline/dev use (ARCHITECTURE.md §9's own comment on
    the Protocol stub) — no API key needed, just a running local server."""

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(self, prompt: str, response_schema: type[T]) -> T:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "format": response_schema.model_json_schema(),
                        "stream": False,
                    },
                )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            return response_schema.model_validate(json.loads(content))
        except Exception as exc:
            raise LLMGenerationError(f"Local (Ollama) generation failed: {exc}") from exc


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for llm_provider=anthropic")
        return AnthropicLLMService(settings.llm_api_key, settings.llm_model or DEFAULT_ANTHROPIC_MODEL)
    if settings.llm_provider == "openai":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for llm_provider=openai")
        return OpenAILLMService(settings.llm_api_key, settings.llm_model or DEFAULT_OPENAI_MODEL)
    if settings.llm_provider == "local":
        return LocalLLMService(settings.ollama_base_url, settings.llm_model or DEFAULT_OLLAMA_MODEL)
    raise ValueError(f"Unknown llm_provider: {settings.llm_provider!r}")
