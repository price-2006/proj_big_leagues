"""SQLAlchemy models for the skill taxonomy (Phase 5, docs/ARCHITECTURE.md §5, §7).

`Skill.embedding` is nullable and unpopulated until the embedding service
(Phase 6) exists — stage 3 of the normalization pipeline degrades to "no
suggestions" until then (app/services/skill_normalization_service.py).
"""
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="internal")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    aliases: Mapped[list["SkillAlias"]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class SkillAlias(Base):
    __tablename__ = "skill_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    skill: Mapped["Skill"] = relationship(back_populates="aliases")


class SkillDisambiguationRule(Base):
    __tablename__ = "skill_disambiguation_rules"
    __table_args__ = (UniqueConstraint("skill_a_id", "skill_b_id", name="uq_disambiguation_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    skill_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
