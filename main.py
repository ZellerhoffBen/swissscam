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
BUILT_FRONTEND = ROOT / "web/dist"
if BUILT_FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=BUILT_FRONTEND / "assets"), name="frontend-assets")


@app.get("/")
def index():
    built_index = BUILT_FRONTEND / "index.html"
    return FileResponse(built_index if built_index.exists() else ROOT / "web/index.html")


@app.get("/swisscam-logo.png")
def logo():
    built_logo = BUILT_FRONTEND / "swissscam-logo.png"
    source_logo = ROOT / "web/public/swissscam-logo.png"
    if built_logo.exists():
        return FileResponse(built_logo, media_type="image/png")
    if source_logo.exists():
        return FileResponse(source_logo, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo asset not found")


@app.post("/api/transcribe")
def transcribe_audio(request: TranscribeRequest) -> Transcript:
    if request.audio_id != "demo":
        raise HTTPException(status_code=404, detail="Unknown demo audio")
    return Transcript(text=transcribe(ROOT / "data/audio/demo.wav"))


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> DetectionResult:
    return detect(request.transcript)
