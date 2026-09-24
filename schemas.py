"""Shared request and response formats for the two processing steps."""

from typing import Literal

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
    type: Literal["segment", "done", "error"]
    text: str
    segment: TranscriptSegment | None = None
    error: str | None = None


class AnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=1)


class DetectionResult(BaseModel):
    warning: bool
    score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    signals: list[str]
    reason: str
