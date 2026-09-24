"""Shared request and response formats for the two processing steps."""

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    audio_id: str
    up_to_seconds: float | None = Field(default=None, ge=0)


class TranscriptSegment(BaseModel):
    text: str
    start_seconds: float
    end_seconds: float


class Transcript(BaseModel):
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


class TranscriptUpdate(BaseModel):
    type: str
    text: str
    segment: TranscriptSegment | None = None


class AnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=1)


class DetectionResult(BaseModel):
    warning: bool
    signals: list[str]
    reason: str
