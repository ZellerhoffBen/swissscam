from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from detector import detect
from schemas import AnalyzeRequest, DetectionResult, TranscribeRequest, Transcript
from transcription import transcribe

ROOT = Path(__file__).parent
app = FastAPI(title="swissscam skeleton")
app.mount("/audio", StaticFiles(directory=ROOT / "data/audio"), name="audio")


@app.get("/")
def index():
    return FileResponse(ROOT / "web/index.html")


@app.post("/api/transcribe")
def transcribe_audio(request: TranscribeRequest) -> Transcript:
    if request.audio_id != "demo":
        raise HTTPException(status_code=404, detail="Unknown demo audio")
    return Transcript(text=transcribe(ROOT / "data/audio/demo.wav"))


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> DetectionResult:
    return detect(request.transcript)
