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

from app.services.llm_service import DEFAULT_OLLAMA_MODEL, LLMGenerationError, LocalLLMService

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
