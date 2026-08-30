"""SQLAlchemy model for resumes (Phase 8, docs/ARCHITECTURE.md §5).

`owner_id` deliberately has no FK: Architecture's schema references
`users(id)`, but no `users` table is specified anywhere in the roadmap —
auth stays deferred throughout (docs/ARCHITECTURE.md §10). The column
exists now, nullable and unconstrained, exactly so adding real auth later
is a constraint addition, not a new column.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (CheckConstraint("file_type IN ('pdf', 'docx')", name="ck_resumes_file_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_profile: Mapped[dict] = mapped_column(JSONB, nullable=False)  # CandidateProfile
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
