"""EmbeddingService — text -> dense vector, behind a swappable interface
(Phase 6, docs/ARCHITECTURE.md §4/§9). Everything downstream (Phase 7's
semantic-similarity features, Phase 5's stage-3 skill suggestions) depends
on this Protocol, never on `sentence_transformers` directly — exactly the
same shape as LLMService's provider-agnostic design.

Default model is `all-MiniLM-L6-v2` (384-dim, CPU-fast) per
docs/ARCHITECTURE.md §4; swappable via `EMBEDDING_MODEL_NAME`.
"""
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class EmbeddingService(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbeddingService:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None  # lazy-loaded: importing sentence_transformers/torch is expensive

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._get_model().get_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vectors.tolist()

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Settings-driven factory, mirroring LLM_PROVIDER's pattern
    (docs/ARCHITECTURE.md §9). Only `sentence_transformers` is implemented
    today; OpenAI/Voyage are documented as future alternates, not stubbed
    here — an unknown provider fails loudly rather than pretending to work.
    """
    settings = get_settings()
    if settings.embedding_model_provider == "sentence_transformers":
        return SentenceTransformerEmbeddingService(settings.embedding_model_name)
    raise ValueError(f"Unknown embedding_model_provider: {settings.embedding_model_provider!r}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
