"""Evaluate the two supplied recordings with real Whisper and the active classifier."""
import hashlib
from pathlib import Path
from time import perf_counter

from backend.detector import MODEL_PATH, load_model
from ml.evaluate import write_report
from ml.prepare_data import EVALUATION, ROOT
from backend.transcription import transcribe_stream

# The scam's first explicit SSN request ends at 29.12 seconds.
RECORDINGS = [("ssa_scam.mp3", 1, 29.12), ("bank_legitimate.mp3", 0, None)]


def main() -> None:
    artifact = load_model()
    results = []
    for filename, label, onset in RECORDINGS:
        path = ROOT / "data/audio" / filename
        started = perf_counter()
        segments = list(transcribe_stream(path))
        transcription_seconds = perf_counter() - started
        parts, scores, latencies = [], [], []
        for segment in segments:
            parts.append(segment.text)
            started = perf_counter()
            scores.append(float(artifact["model"].predict_proba([" ".join(parts)])[0, 1]))
            latencies.append(perf_counter() - started)
        first = next((s.end_seconds for s, score in zip(segments, scores)
                      if score >= artifact["threshold"]), None)
        result = {"file": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "label": label, "warning_onset_seconds": onset, "transcription_seconds": transcription_seconds,
                  "segments": [s.model_dump() for s in segments], "scores": scores,
                  "first_warning_seconds": first, "max_score": max(scores),
                  "mean_analysis_ms": 1000 * sum(latencies) / len(latencies),
                  "correct": (first is not None and first >= onset) if label else first is None}
        results.append(result)
        print(filename, "first warning:", first, "correct:", result["correct"])
    write_report(EVALUATION / "reports/audio_results.json", {
        "model_sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(), "threshold": artifact["threshold"],
        "recordings": results,
        "limitation": "Two known synthetic-voice regressions. CPU timings exclude model load and depend on hardware/cache state.",
    })


if __name__ == "__main__":
    main()
