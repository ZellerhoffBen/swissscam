"""Evaluate first warnings on held-out conversations, one turn at a time."""

import argparse
import hashlib
import re
import json
import statistics
from pathlib import Path

from backend.context_model import ContextClassifier

from backend.detector import MODEL_PATH, load_model
from ml.prepare_data import DATA, EVALUATION, behavior_rows, iter_prefixes, load_calls, read_jsonl


def score_calls(model: ContextClassifier, calls: list[dict]) -> list[list[float]]:
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


def behavior_result(model: ContextClassifier, rows: list[dict], threshold: float) -> dict:
    values = model.predict_proba([r["text"] for r in rows])[:, 1]
    cases = [{"id": r["id"], "kind": r["kind"], "label": r["label"], "score": float(score),
              "correct": bool((score >= threshold) == r["label"])}
             for r, score in zip(rows, values, strict=True)]
    return {"correct": sum(r["correct"] for r in cases), "total": len(cases), "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, help="Candidate directory; defaults to the active model.")
    args = parser.parse_args()
    artifact = load_model(args.model)
    model, threshold = artifact["model"], artifact["threshold"]
    datasets = {"test": load_calls("test"),
                "fresh": read_jsonl(EVALUATION / "cases/fresh_calls.jsonl"),
                "reported": read_jsonl(EVALUATION / "cases/regressions.jsonl")}
    calls = {name: measure(rows, score_calls(model, rows), threshold) for name, rows in datasets.items()}
    behaviors = behavior_rows("test")
    language = {"original": behavior_result(model, behaviors, threshold)}
    for name, transform in {
        "no_punctuation": lambda text: re.sub(r"[^\w\s]", "", text.lower()),
        "neutral_context": lambda text: "Hello, my name is Alex. I called earlier about the 38 dollar purchase. " + text,
    }.items():
        language[name] = behavior_result(model, [{**r, "text": transform(r["text"])} for r in behaviors], threshold)
        language[name]["decision_changes"] = sum(
            (a["score"] >= threshold) != (b["score"] >= threshold)
            for a, b in zip(language["original"]["cases"], language[name]["cases"], strict=True))
    model_path = args.model / "model.safetensors" if args.model else MODEL_PATH
    report = {"model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(), "threshold": threshold,
              "calls": calls, "behaviors": language,
              "data_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                              (DATA / "authored.jsonl", DATA / "behaviors.jsonl",
                               EVALUATION / "cases/fresh_calls.jsonl", EVALUATION / "cases/regressions.jsonl")},
              "limitation": "Synthetic, now-known regression cases; not independent evidence of real-call accuracy."}
    output = args.model / "evaluation_results.json" if args.model else EVALUATION / "reports/results.json"
    write_report(output, report)
    for name, result in calls.items():
        print(name, json.dumps(summary(result)))
    print(f"Behavior checks: {language['original']['correct']}/{language['original']['total']}")


if __name__ == "__main__":
    main()
