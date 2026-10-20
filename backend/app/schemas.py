from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SpeakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sample_count: int
    consent_given_at: datetime
    created_at: datetime
    is_sample: bool = False
    expires_at: datetime | None = None


class CandidateOut(BaseModel):
    speaker_id: int
    name: str
    score: float


class IdentifyOut(BaseModel):
    label: str  # the speaker's name, or "unknown"
    is_match: bool
    speaker_id: int | None
    score: float  # cosine similarity of the best candidate (confidence)
    threshold: float
    reason: str
    speech_seconds: float
    candidates: list[CandidateOut]


class HealthOut(BaseModel):
    status: str
    model_loaded: bool
    threshold: float
    speakers: int
    demo_retention_hours: float  # visitor enrollments are deleted after this long (0 = never)
