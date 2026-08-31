"""SQLAlchemy model for training_labels (Phase 10, docs/ARCHITECTURE.md §5).

`resume_id`/`job_id` are nullable and `external_resume_ref`/`external_job_ref`
exist specifically because most rows here come from an external dataset
(cnamuangtoun/resume-job-description-fit), never inserted into the
production `resumes`/`jobs` tables — those hold real user uploads, not
8,000 dataset rows. The external ref is a stable hash of the raw text
(app/services/dataset_sources/cnamuangtoun_loader.py), which is also how
the grouped train/val/test split is computed.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TrainingLabel(Base):
    __tablename__ = "training_labels"
    __table_args__ = (
        CheckConstraint("dataset_split IN ('train', 'val', 'test')", name="ck_training_labels_split"),
        # Scoped to external-ref rows (100% of what exists today) so
        # build_dataset.py's upsert can actually dedupe on re-run — see
        # alembic/versions/0008_training_labels_unique.py for the bug this
        # fixed (ON CONFLICT DO NOTHING had nothing to conflict on before).
        UniqueConstraint(
            "external_resume_ref", "external_job_ref", "label_source", name="uq_training_labels_external_pair_source"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    external_resume_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_job_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    label_source: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_split: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
