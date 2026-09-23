"""Shared request and response formats for the two processing steps."""

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    audio_id: str


class Transcript(BaseModel):
    text: str


class AnalyzeRequest(BaseModel):
    transcript: str = Field(min_length=1)


class DetectionResult(BaseModel):
    warning: bool
    signals: list[str]
    reason: str
