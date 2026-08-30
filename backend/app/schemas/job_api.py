import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.job_profile import JobProfile


class JobResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    source: str
    parsed_profile: JobProfile
    created_at: datetime

    model_config = {"from_attributes": True}
