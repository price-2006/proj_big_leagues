"""Phase 6 test procedure per docs/ROADMAP.md: known-similar sentence
pairs score above a threshold, known-dissimilar pairs score below it;
swapping the configured model name changes the embedding
dimension/behavior without touching calling code.

Downloads real models on first run (all-MiniLM-L6-v2, and a second,
differently-sized model for the swap test) — no faked scores.
"""
from app.services.embedding_service import SentenceTransformerEmbeddingService, cosine_similarity

SIMILAR_PAIRS = [
    (
        "Built a resume parsing pipeline processing 10k documents per day",
        "Developed a document processing system that handles thousands of files daily",
    ),
    ("Experienced Python developer with FastAPI background", "Software engineer skilled in Python and FastAPI"),
]

DISSIMILAR_PAIRS = [
    (
        "Built a resume parsing pipeline processing 10k documents per day",
        "Managed a team of pastry chefs at a five-star restaurant",
    ),
    ("Experienced Python developer with FastAPI background", "Certified yoga instructor and nutrition coach"),
]


def _service() -> SentenceTransformerEmbeddingService:
    return SentenceTransformerEmbeddingService("all-MiniLM-L6-v2")


def test_known_similar_pairs_score_above_threshold():
    service = _service()
    for a, b in SIMILAR_PAIRS:
        [vec_a, vec_b] = service.embed([a, b])
        similarity = cosine_similarity(vec_a, vec_b)
        assert similarity > 0.5, f"{a!r} vs {b!r} scored {similarity:.3f}"


def test_known_dissimilar_pairs_score_below_threshold():
    service = _service()
    for a, b in DISSIMILAR_PAIRS:
        [vec_a, vec_b] = service.embed([a, b])
        similarity = cosine_similarity(vec_a, vec_b)
        assert similarity < 0.3, f"{a!r} vs {b!r} scored {similarity:.3f}"


def test_similar_pairs_score_higher_than_dissimilar_pairs():
    """The direct, threshold-independent version of the same check."""
    service = _service()
    similar_scores = [cosine_similarity(*service.embed([a, b])) for a, b in SIMILAR_PAIRS]
    dissimilar_scores = [cosine_similarity(*service.embed([a, b])) for a, b in DISSIMILAR_PAIRS]
    assert min(similar_scores) > max(dissimilar_scores)


def test_embed_returns_correct_shape_and_dimension():
    service = _service()
    vectors = service.embed(["one sentence", "another sentence"])
    assert len(vectors) == 2
    assert len(vectors[0]) == service.dimension
    assert service.dimension == 384


def test_embed_empty_list_returns_empty_list():
    assert _service().embed([]) == []


def test_swapping_model_name_changes_dimension_without_touching_calling_code():
    """Same EmbeddingService interface, same embed() call — only the
    configured model name differs, per docs/ROADMAP.md's exact Phase 6
    test procedure."""
    default_service = SentenceTransformerEmbeddingService("all-MiniLM-L6-v2")
    alt_service = SentenceTransformerEmbeddingService("average_word_embeddings_glove.6B.300d")

    default_vectors = default_service.embed(["a sentence to embed"])
    alt_vectors = alt_service.embed(["a sentence to embed"])

    assert default_service.dimension == 384
    assert alt_service.dimension == 300
    assert len(default_vectors[0]) == 384
    assert len(alt_vectors[0]) == 300
    assert default_service.model_name != alt_service.model_name
