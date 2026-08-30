import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.candidate_profile import CandidateProfile


class ResumeResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    file_type: str
    parsed_profile: CandidateProfile
    created_at: datetime

    model_config = {"from_attributes": True}
