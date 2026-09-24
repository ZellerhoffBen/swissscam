import pickle
from functools import lru_cache
from pathlib import Path

import sklearn

from schemas import DetectionResult

MODEL_PATH = Path(__file__).resolve().parent / "models" / "scam_classifier.pkl"


@lru_cache(maxsize=1)
def load_model() -> dict:
    if not MODEL_PATH.exists():
        raise RuntimeError("Classifier missing. Run: uv run python train.py")
    # Only load this project's trusted, locally trained artifact. Pickle files
    # can execute code; never load an uploaded or untrusted model here.
    artifact = pickle.loads(MODEL_PATH.read_bytes())
    if artifact["sklearn_version"] != sklearn.__version__:
        raise RuntimeError("Classifier version mismatch. Run uv sync, then retrain if needed.")
    return artifact


def detect(transcript: str) -> DetectionResult:
    """Classify the conversation heard so far; no speaker labels are required."""
    artifact = load_model()
    score = float(artifact["model"].predict_proba([transcript])[0, 1])
    warning = score >= artifact["threshold"]
    return DetectionResult(
        warning=warning,
        # This binary model does not predict individual scam signals.
        signals=[],
        reason=("Possible scam: this conversation resembles scam requests in the training examples. "
                "Pause and verify the caller independently.") if warning else "",
    )
