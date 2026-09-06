"""Phase 12: LLMService implementations. LocalLLMService (Ollama) is the
one provider this environment can actually call for real — no
LLM_API_KEY is configured for Anthropic/OpenAI here — so it gets one live
integration test proving the whole generate_structured -> JSON ->
Pydantic-validated round trip genuinely works against a real model, not
just a mocked HTTP layer. It's skipped, not failed, when Ollama isn't
reachable (an external, host-level dependency, unlike the
sentence-transformers model that ships baked into the backend image).

Run inside the backend container, Ollama reaches the Windows host at
host.docker.internal, not localhost — see LOCAL_OLLAMA_BASE_URL below.
"""
import httpx
import pytest
from pydantic import BaseModel

from app.services.llm_service import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_OLLAMA_MODEL,
    GROQ_BASE_URL,
    LLMGenerationError,
    LocalLLMService,
    OpenAILLMService,
    get_llm_service,
)

LOCAL_OLLAMA_BASE_URL = "http://host.docker.internal:11434"


def _ollama_reachable() -> bool:
    try:
        response = httpx.get(f"{LOCAL_OLLAMA_BASE_URL}/api/tags", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


class _Sentiment(BaseModel):
    sentiment: str
    confidence: float


@pytest.mark.asyncio
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable at host.docker.internal:11434")
async def test_local_llm_service_real_call_returns_schema_valid_output():
    service = LocalLLMService(base_url=LOCAL_OLLAMA_BASE_URL, model=DEFAULT_OLLAMA_MODEL)
    result = await service.generate_structured(
        "Classify the sentiment of this sentence as 'positive', 'negative', or 'neutral', "
        "with a confidence between 0 and 1: 'The candidate has strong Python experience.'",
        _Sentiment,
    )
    assert isinstance(result, _Sentiment)
    assert result.sentiment in ("positive", "negative", "neutral")
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_local_llm_service_wraps_unreachable_server_as_llm_generation_error():
    service = LocalLLMService(base_url="http://127.0.0.1:1", model=DEFAULT_OLLAMA_MODEL)  # nothing listens on port 1
    with pytest.raises(LLMGenerationError):
        await service.generate_structured("anything", _Sentiment)


def test_strict_json_schema_sets_additional_properties_false_on_every_nested_object():
    """Regression test for a real failure found by actually calling Groq:
    'additionalProperties:false must be set on every object' on a nested
    model (MatchExplanation's Recommendation, under $defs) — Pydantic's
    model_json_schema() doesn't set this itself. Using the real schema
    that failed, not a synthetic stand-in."""
    from app.schemas.match_explanation import MatchExplanation
    from app.services.llm_service import _strict_json_schema

    schema = _strict_json_schema(MatchExplanation)

    assert schema["additionalProperties"] is False
    defs = schema.get("$defs", {})
    assert defs, "expected MatchExplanation to have nested $defs (EvidencedClaim, Recommendation)"
    for name, definition in defs.items():
        assert definition.get("additionalProperties") is False, f"{name} is missing additionalProperties: false"


def test_strict_json_schema_requires_every_property_even_ones_with_a_python_default():
    """Regression test for a second real failure found the same way:
    Groq rejected EvidencedClaim's schema because `is_inference` (a bool
    field with a Python-side default of False) wasn't in `required` —
    Pydantic itself correctly excludes defaulted fields from `required`,
    but strict mode wants every property listed regardless."""
    from app.schemas.match_explanation import MatchExplanation
    from app.services.llm_service import _strict_json_schema

    schema = _strict_json_schema(MatchExplanation)

    evidenced_claim = schema["$defs"]["EvidencedClaim"]
    assert set(evidenced_claim["required"]) == set(evidenced_claim["properties"].keys())
    assert "is_inference" in evidenced_claim["required"]  # has a Python default; still must be required here

    recommendation = schema["$defs"]["Recommendation"]
    assert set(recommendation["required"]) == set(recommendation["properties"].keys())
    assert "fabricated_metric" in recommendation["required"]  # same situation


def test_openai_service_passes_a_custom_base_url_to_the_client():
    """Groq (and any other OpenAI-compatible host) reuses OpenAILLMService
    entirely via this one constructor arg — no separate class."""
    service = OpenAILLMService(api_key="fake-key", model="some-model", base_url="https://example.com/v1")
    client = service._get_client()
    assert str(client.base_url).rstrip("/") == "https://example.com/v1"


def test_openai_service_defaults_to_the_real_openai_base_url_when_unset():
    service = OpenAILLMService(api_key="fake-key", model="some-model")
    client = service._get_client()
    assert "api.openai.com" in str(client.base_url)


def test_get_llm_service_builds_a_groq_configured_openai_service(monkeypatch):
    from app import config
    from app.services import llm_service as llm_service_module

    # llm_model=None explicitly: this container's own ambient environment
    # has LLM_MODEL=qwen2.5 set (for local Ollama dev testing), and
    # Settings(_env_file=None) still reads real process env vars — found
    # by this exact test failing against that leaked value, same lesson
    # as tests/test_config.py's equivalent fix.
    fake_settings = config.Settings(_env_file=None, llm_provider="groq", llm_api_key="fake-groq-key", llm_model=None)
    monkeypatch.setattr(llm_service_module, "get_settings", lambda: fake_settings)
    llm_service_module.get_llm_service.cache_clear()
    try:
        service = get_llm_service()
        assert isinstance(service, OpenAILLMService)
        assert service.model_name == DEFAULT_GROQ_MODEL
        client = service._get_client()
        assert str(client.base_url).rstrip("/") == GROQ_BASE_URL
    finally:
        llm_service_module.get_llm_service.cache_clear()


def test_get_llm_service_raises_without_an_api_key_for_groq(monkeypatch):
    from app import config
    from app.services import llm_service as llm_service_module

    fake_settings = config.Settings(_env_file=None, llm_provider="groq", llm_api_key=None)
    monkeypatch.setattr(llm_service_module, "get_settings", lambda: fake_settings)
    llm_service_module.get_llm_service.cache_clear()
    try:
        with pytest.raises(ValueError, match="groq"):
            get_llm_service()
    finally:
        llm_service_module.get_llm_service.cache_clear()

