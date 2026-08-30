"""O*NET occupation taxonomy (Phase 10) — the "occupation family" signal
for weak-supervision positive/negative pairing (docs/DATASET_STRATEGY.md
§3: "adjacent O*NET/ESCO occupation family... via its most frequent job
titles/skills"). Deliberately separate from app/services/onet_loader.py's
Hot-Technology skill subset (Phase 5) — that file's occupation coverage
is tech-skewed, too narrow for a dataset spanning sales, construction,
and engineering roles (verified against real cnamuangtoun sample rows).

Matching is embedding-based, not text-similarity: an earlier version used
difflib character/token overlap and produced confidently wrong matches on
real data ("Software Engineer" -> "Sales Engineers", "Sales Associate" ->
"Surgical Assistants") — short job titles carry meaning that surface text
overlap doesn't capture, which is exactly what an embedding model is for.
Real O*NET data (all ~1,000 SOC occupations, CC BY 4.0), but the matching
itself stays "distant supervision, not ground truth" (DATASET_STRATEGY.md
§3) — a best-effort title match, not a real classifier.
"""
import csv
import io
import urllib.request
from dataclasses import dataclass

from app.services.embedding_service import EmbeddingService, cosine_similarity

ONET_OCCUPATION_DATA_URL = "https://www.onetcenter.org/dl_files/database/db_31_0_csv/occupation_data.csv"

# Calibrated against real title pairs (see tests/services/test_onet_occupations.py):
# genuine matches ("Software Engineer" -> "Software Developers" 0.818,
# "Registered Nurse" -> "Registered Nurses" 0.957) scored 0.72-0.96; the
# lowest score for a real-but-generic input ("Contract Employee" ->
# "Labor Relations Specialists") was 0.561 — still above this threshold,
# so it's a deliberately permissive floor, not a tight one.
DEFAULT_MIN_SIMILARITY = 0.5


@dataclass(frozen=True)
class Occupation:
    code: str  # O*NET-SOC code, e.g. "15-1252.00"
    title: str

    @property
    def major_group(self) -> str:
        """First two digits of the SOC code — the coarse "occupation
        family" used for positive/negative pairing, e.g. "15" for
        Computer/Mathematical occupations."""
        return self.code.split("-")[0]


def fetch_onet_occupation_data_csv(url: str = ONET_OCCUPATION_DATA_URL, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — fixed, trusted onetcenter.org URL
        return response.read().decode("utf-8")


def parse_occupations(csv_text: str) -> list[Occupation]:
    reader = csv.DictReader(io.StringIO(csv_text))
    return [Occupation(code=row["O*NET-SOC Code"], title=row["Title"]) for row in reader]


def embed_occupations(occupations: list[Occupation], embedding_service: EmbeddingService) -> list[list[float]]:
    return embedding_service.embed([o.title for o in occupations])


def infer_occupation(
    text: str,
    occupations: list[Occupation],
    occupation_embeddings: list[list[float]],
    embedding_service: EmbeddingService,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> Occupation | None:
    """Best-matching occupation by title embedding similarity to `text`
    (typically a resume's most recent job title, or a JD's title) —
    None if nothing clears the threshold, rather than guessing."""
    if not text or not text.strip():
        return None

    [query_vector] = embedding_service.embed([text])
    best_occupation, best_score = None, 0.0
    for occupation, vector in zip(occupations, occupation_embeddings):
        score = cosine_similarity(query_vector, vector)
        if score > best_score:
            best_occupation, best_score = occupation, score

    return best_occupation if best_score >= min_similarity else None
