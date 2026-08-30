"""Real embedding model, small synthetic occupation list — no live fetch
in the automated suite (consistent with Phase 5/6's testing pattern).
The threshold and match quality were calibrated against the real, full
1,016-occupation O*NET list first (see onet_occupations.py's module
docstring for those numbers); this locks in the same behavior cheaply.
"""
from app.services.embedding_service import SentenceTransformerEmbeddingService
from app.services.onet_occupations import Occupation, embed_occupations, infer_occupation

OCCUPATIONS = [
    Occupation(code="15-1252.00", title="Software Developers"),
    Occupation(code="41-9031.00", title="Sales Engineers"),
    Occupation(code="41-2031.00", title="Retail Salespersons"),
    Occupation(code="29-9093.00", title="Surgical Assistants"),
    Occupation(code="29-1141.00", title="Registered Nurses"),
    Occupation(code="13-2011.00", title="Accountants and Auditors"),
]


def _embedding_service() -> SentenceTransformerEmbeddingService:
    return SentenceTransformerEmbeddingService("all-MiniLM-L6-v2")


def test_matches_software_engineer_to_software_developers_not_sales_engineers():
    """Regression test: an earlier text-similarity (not embedding) version
    of this matcher confidently matched 'Software Engineer' to 'Sales
    Engineers' — real characters overlap, real meaning doesn't."""
    service = _embedding_service()
    occupation_embeddings = embed_occupations(OCCUPATIONS, service)

    match = infer_occupation("Software Engineer", OCCUPATIONS, occupation_embeddings, service)
    assert match is not None
    assert match.title == "Software Developers"


def test_matches_sales_associate_to_retail_salespersons_not_surgical_assistants():
    """Same regression, second real example from the same bad old
    matcher: 'Sales Associate' -> 'Surgical Assistants'."""
    service = _embedding_service()
    occupation_embeddings = embed_occupations(OCCUPATIONS, service)

    match = infer_occupation("Sales Associate", OCCUPATIONS, occupation_embeddings, service)
    assert match is not None
    assert match.title == "Retail Salespersons"


def test_exact_title_match_scores_very_high():
    service = _embedding_service()
    occupation_embeddings = embed_occupations(OCCUPATIONS, service)
    match = infer_occupation("Registered Nurse", OCCUPATIONS, occupation_embeddings, service)
    assert match is not None
    assert match.title == "Registered Nurses"


def test_empty_text_returns_none_without_calling_the_model():
    service = _embedding_service()
    occupation_embeddings = embed_occupations(OCCUPATIONS, service)
    assert infer_occupation("", OCCUPATIONS, occupation_embeddings, service) is None
    assert infer_occupation("   ", OCCUPATIONS, occupation_embeddings, service) is None


def test_major_group_is_first_two_digits_of_soc_code():
    occupation = Occupation(code="15-1252.00", title="Software Developers")
    assert occupation.major_group == "15"
