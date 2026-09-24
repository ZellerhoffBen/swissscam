"""Evaluate first warnings on held-out conversations, one turn at a time."""

import hashlib
import json
import statistics
from pathlib import Path

from sklearn.pipeline import Pipeline

from detector import MODEL_PATH, load_model
from prepare_data import EVALUATION, iter_prefixes, read_jsonl


def score_calls(model: Pipeline, calls: list[dict]) -> list[list[float]]:
    """The model sees only spoken text up to the current turn."""
    result = []
    for call in calls:
        texts = [prefix["text"] for prefix in iter_prefixes(call)]
        scores = model.predict_proba(texts)[:, 1]
        result.append([float(score) for score in scores])
    return result


def measure(calls: list[dict], scores: list[list[float]], threshold: float) -> dict:
    outcomes = []
    for call, values in zip(calls, scores, strict=True):
        if len(values) != len(call["turns"]):
            raise ValueError("Each call needs one score per turn.")
        first = next((i for i, score in enumerate(values, 1) if score >= threshold), None)
        onset = call["warning_turn"]
        if not call["label"]:
            outcome = "false_alarm" if first else "correctly_quiet"
        elif first is None:
            outcome = "missed"
        elif first < onset:
            outcome = "premature_warning"
        else:
            outcome = "detected"
        outcomes.append({
            "id": call["id"], "category": call["category"], "label": call["label"],
            "warning_turn": onset, "first_warning_turn": first, "outcome": outcome,
            "delay_turns": first - onset if outcome == "detected" else None,
            "scores": [round(value, 6) for value in values],
        })
    counts = {name: sum(r["outcome"] == name for r in outcomes) for name in
              ("detected", "missed", "premature_warning", "false_alarm", "correctly_quiet")}
    scams = sum(call["label"] for call in calls)
    legitimate = len(calls) - scams
    if not scams or not legitimate:
        raise ValueError("Evaluation needs both scam and legitimate calls.")
    delays = [r["delay_turns"] for r in outcomes if r["delay_turns"] is not None]
    return {
        "threshold": threshold, "scam_calls": scams, "legitimate_calls": legitimate,
        **counts,
        # Premature alerts count as failed scam detections, not successful warnings.
        "balanced_call_score": (counts["detected"] / scams + counts["correctly_quiet"] / legitimate) / 2,
        "mean_delay_turns": statistics.mean(delays) if delays else None,
        "calls": outcomes,
    }


def summary(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "calls"}


def write_report(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")


def main() -> None:
    # Run only after selecting and freezing the model using validation.
    artifact = load_model()
    calls = read_jsonl(EVALUATION / "test.jsonl")
    result = measure(calls, score_calls(artifact["model"], calls), artifact["threshold"])
    report = {
        "split": "test", "model_sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        "test_sha256": hashlib.sha256((EVALUATION / "test.jsonl").read_bytes()).hexdigest(),
        "classifier": result,
        "limitation": "Small synthetic text test; not evidence of real-call or speech-recognition performance.",
    }
    write_report(EVALUATION / "test_results.json", report)
    print(json.dumps(summary(result), indent=2))


if __name__ == "__main__":
    main()
