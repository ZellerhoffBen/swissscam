"""Evaluate the active model on the pinned external research corpus, without training."""
import hashlib
import re
import zipfile
from pathlib import Path

from backend.detector import MODEL_PATH, load_model
from ml.evaluate import write_report
from ml.prepare_data import EVALUATION, normalize

# CC BY-NC-ND 4.0: local research evaluation only; do not redistribute source texts.
# https://www.kaggle.com/datasets/teeconnie/scam-and-non-scam-call-conversation-dataset/versions/1
ARCHIVE_SHA256 = "34746f3aeb21a70c03bf0af12ce30f365d9c6342c92e703650940f013f1c7fd5"


def verify_file(path: Path, expected: str) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Frozen evaluation input changed: {path}")


def external_calls(archive: Path) -> tuple[list[dict], list[str]]:
    rows, excluded, seen = [], [], {}
    with zipfile.ZipFile(archive) as source:
        for filename, label in (("English_NonScam.txt", 0), ("English_Scam.txt", 1)):
            texts = re.split(r"\n\s*\n", source.read(filename).decode("utf-8-sig").replace("\r\n", "\n"))
            texts = [text.strip() for text in texts if text.strip()]
            if len(texts) != 400:
                raise ValueError("Expected exactly 400 entries per source class.")
            for index, text in enumerate(texts, 1):
                text = " ".join(re.sub(r"^\d+\.\s*", "", text).split())
                key, identifier = normalize(text), f"external-{label}-{index:03}"
                if key in seen:
                    if seen[key] != label:
                        raise ValueError(f"Conflicting source labels: {identifier}")
                    excluded.append(identifier)
                    continue
                seen[key] = label
                rows.append({"id": identifier, "label": label, "text": text})
    return rows, excluded


def source_metrics(rows: list[dict], scores: list[float], threshold: float) -> dict:
    predictions = [bool(score >= threshold) for score in scores]
    positives = sum(r["label"] for r in rows)
    negatives = len(rows) - positives
    detected = sum(pred and row["label"] == 1 for pred, row in zip(predictions, rows))
    false = sum(pred and row["label"] == 0 for pred, row in zip(predictions, rows))
    return {"scams": positives, "legitimate": negatives, "detected": detected, "missed": positives - detected,
            "false_alarm": false, "recall": detected / positives, "false_positive_rate": false / negatives,
            "balanced_accuracy": (detected / positives + 1 - false / negatives) / 2,
            # Store row IDs/scores, not a redistributed copy of the restricted source.
            "cases": [{"id": row["id"], "label": row["label"], "score": float(score),
                       "correct": bool(pred == row["label"])}
                      for row, score, pred in zip(rows, scores, predictions, strict=True)]}


def main() -> None:
    archive = EVALUATION / "external/calls.zip"
    verify_file(archive, ARCHIVE_SHA256)
    rows, excluded = external_calls(archive)
    artifact = load_model()
    result = source_metrics(rows, artifact["model"].predict_proba([r["text"] for r in rows])[:, 1], artifact["threshold"])
    write_report(EVALUATION / "reports/external_results.json", {
        "model_sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        "archive_sha256": ARCHIVE_SHA256, "threshold": artifact["threshold"],
        "excluded_duplicates": excluded, "result": result,
        "limitation": "Inherited whole-text labels; some scam entries are ambiguous. No warning-onset labels or real-world accuracy guarantee.",
    })
    print({key: value for key, value in result.items() if key != "cases"})


if __name__ == "__main__":
    main()
