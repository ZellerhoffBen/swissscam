import logging
import shutil
import tempfile
from pathlib import Path
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from detector import detect
from schemas import (
    AnalyzeRequest,
    DetectionResult,
    Transcript,
    TranscriptUpdate,
    TranscribeRequest,
)
from transcription import transcribe, transcribe_stream

ROOT = Path(__file__).parent
app = FastAPI(title="swissscam")
logger = logging.getLogger(__name__)
app.mount("/audio", StaticFiles(directory=ROOT / "data/audio"), name="audio")
BUILT_FRONTEND = ROOT / "web/dist"
if (BUILT_FRONTEND / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=BUILT_FRONTEND / "assets"), name="frontend-assets")


@app.get("/")
def index() -> FileResponse:
    built_index = BUILT_FRONTEND / "index.html"
    if not built_index.exists():
        raise HTTPException(status_code=503, detail="Build the frontend first: npm ci && npm run build")
    return FileResponse(built_index)


@app.get("/swissscam-logo.png")
def logo() -> FileResponse:
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
    try:
        return transcribe(ROOT / "data/audio/demo.wav", request.up_to_seconds)
    except Exception as error:
        logger.exception("Demo transcription failed")
        raise HTTPException(status_code=503, detail="Transcription failed. Check the server log and Whisper model download.") from error


@app.post("/api/transcribe/upload")
def transcribe_upload(audio: UploadFile = File(...)) -> StreamingResponse:
    """Stream completed Whisper segments for an uploaded audio file as SSE."""
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temporary_path = Path(temporary_file.name)

    try:
        shutil.copyfileobj(audio.file, temporary_file)
        temporary_file.close()
    except Exception:
        temporary_file.close()
        temporary_path.unlink(missing_ok=True)
        raise

    def events() -> Iterator[str]:
        transcript_parts: list[str] = []
        try:
            for segment in transcribe_stream(temporary_path):
                transcript_parts.append(segment.text)
                event = TranscriptUpdate(
                    type="segment",
                    text=" ".join(transcript_parts),
                    segment=segment,
                )
                yield f"data: {event.model_dump_json()}\n\n"

            finished = TranscriptUpdate(type="done", text=" ".join(transcript_parts))
            yield f"data: {finished.model_dump_json()}\n\n"
        except Exception:
            logger.exception("Uploaded audio transcription failed")
            failed = TranscriptUpdate(type="error", text=" ".join(transcript_parts),
                                      error="Transcription failed. Check the recording and server log.")
            yield f"data: {failed.model_dump_json()}\n\n"
        finally:
            temporary_path.unlink(missing_ok=True)

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
        background=BackgroundTask(temporary_path.unlink, missing_ok=True),
    )


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> DetectionResult:
    return detect(request.transcript)
