"""Shared request and response formats for the two processing steps."""

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    audio_id: str


class TranscriptSegment(BaseModel):
    text: str
    start_seconds: float
    end_seconds: float


class Transcript(BaseModel):
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=1)


class DetectionResult(BaseModel):
    warning: bool
    signals: list[str]
    reason: str
