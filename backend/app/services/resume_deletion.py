"""Deletes a Resume and everything that references it (Phase 14,
docs/ARCHITECTURE.md §12: "a delete endpoint... purges the row and its
embeddings/matches"). Not just `session.delete(resume)`, because several
of the tables that point at a resume don't have DB-level cascade set up:

  - `matches.resume_id`/`job_id` have no `ondelete` — a plain FK-violation
    RESTRICT would reject deleting a resume that has any matches, so
    those rows are deleted explicitly here first (which in turn cascades
    to `match_explanations` via its own `ondelete="CASCADE"`, already in
    place since Phase 12).
  - `text_embeddings.entity_id` has no FK at all (it's polymorphic —
    app/models/text_embedding.py) — nothing in the schema can cascade it,
    so it's cleaned up explicitly, the same delete pattern already used
    by app/services/text_embedding_store.py for re-embedding.
  - `training_labels.resume_id` is nullable with no `ondelete`; real
    resume uploads have never populated it (Phase 10's training rows are
    all external-dataset references — see app/models/training_label.py),
    but it's nulled out defensively rather than left to a hypothetical
    future FK violation.
  - The uploaded file on disk (`resume.storage_path`) is real PII sitting
    outside the database entirely — nothing else removes it.
"""
from pathlib import Path

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.resume import Resume
from app.models.text_embedding import TextEmbedding
from app.models.training_label import TrainingLabel

_RESUME_ENTITY_TYPES = ("resume_experience", "resume_project")


async def delete_resume(session: AsyncSession, resume: Resume) -> None:
    await session.execute(
        delete(TextEmbedding).where(
            TextEmbedding.entity_type.in_(_RESUME_ENTITY_TYPES), TextEmbedding.entity_id == resume.id
        )
    )
    await session.execute(update(TrainingLabel).where(TrainingLabel.resume_id == resume.id).values(resume_id=None))
    await session.execute(delete(Match).where(Match.resume_id == resume.id))
    await session.delete(resume)
    await session.flush()

    _delete_file_if_exists(resume.storage_path)


def _delete_file_if_exists(storage_path: str) -> None:
    path = Path(storage_path)
    if path.exists():
        path.unlink()
