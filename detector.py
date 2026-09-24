import json
from functools import lru_cache
from pathlib import Path

from schemas import DetectionResult

MODELS = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODELS / "context" / "model.safetensors"


@lru_cache(maxsize=1)
def load_model(directory: Path | None = None) -> dict:
    path = MODEL_PATH if directory is None else directory / "model.safetensors"
    if not path.exists():
        raise RuntimeError("Classifier missing. Restore models/context; train.py creates candidates separately.")
    from context_model import ContextClassifier

    metadata = json.loads((path.parent / "metadata.json").read_text())
    return {**metadata, "model": ContextClassifier(path.parent)}


def detect(transcript: str) -> DetectionResult:
    """Classify the conversation heard so far; no speaker labels are required."""
    artifact = load_model()
    score = float(artifact["model"].predict_proba([transcript])[0, 1])
    warning = score >= artifact["threshold"]
    return DetectionResult(
        warning=warning,
        score=score,
        threshold=artifact["threshold"],
        # This binary model does not predict individual scam signals.
        signals=[],
        reason=("Possible scam: this conversation resembles scam requests in the training examples. "
                "Pause and verify the caller independently.") if warning else "",
    )
