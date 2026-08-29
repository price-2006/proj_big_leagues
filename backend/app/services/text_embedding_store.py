"""Writes chunk embeddings to text_embeddings (Phase 6). `entity_id` is
whatever the caller has — a real resume/job UUID once Phase 8 exists, or
any UUID in the interim; this table has no FK to enforce that (see
app/models/text_embedding.py).

replace_chunk_embeddings deletes-then-inserts rather than diffing,
because a re-parsed resume's bullets aren't stable by position or text
across a parser version bump — there's nothing meaningful to diff against.
"""
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.text_embedding import TextEmbedding
from app.services.embedding_service import EmbeddingService


async def replace_chunk_embeddings(
    session: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    chunks: list[str],
    embedding_service: EmbeddingService,
) -> int:
    await session.execute(
        delete(TextEmbedding).where(TextEmbedding.entity_type == entity_type, TextEmbedding.entity_id == entity_id)
    )

    if not chunks:
        return 0

    vectors = embedding_service.embed(chunks)
    session.add_all(
        [
            TextEmbedding(
                entity_type=entity_type,
                entity_id=entity_id,
                chunk_index=index,
                chunk_text=chunk_text,
                embedding_model=embedding_service.model_name,
                embedding=vector,
            )
            for index, (chunk_text, vector) in enumerate(zip(chunks, vectors))
        ]
    )
    return len(chunks)
