"""Train the chosen model recipe; choose its warning threshold on validation."""

import hashlib
import json
import pickle
from collections import Counter

import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from detector import MODEL_PATH
from evaluate import measure, score_calls, summary, write_report
from prepare_data import DATA, EVALUATION, iter_prefixes, normalize, read_jsonl


def training_rows() -> tuple[list[dict], list[dict]]:
    calls = read_jsonl(DATA / "train.jsonl")
    unique = {}
    # Build text-so-far examples in memory instead of storing a duplicate dataset.
    for call in calls:
        for prefix in iter_prefixes(call):
            key = normalize(prefix["text"])
            label = int(prefix["warning"])
            if key in unique and unique[key]["label"] != label:
                raise ValueError("Conflicting training prefix labels.")
            unique[key] = {"text": prefix["text"], "label": label}
    seed = [call for call in calls if call["annotation"] == "source_call_label_only"]
    return list(unique.values()), seed


def fit_model(local: list[dict], seed: list[dict]) -> Pipeline:
    rows, weights = [], []
    # Equal total weight for each label. Public whole-call labels get only 25%
    # of the weight because they lack warning-onset labels.
    for pool, share in ((local, 0.75), (seed, 0.25)):
        counts = Counter(row["label"] for row in pool)
        rows.extend(pool)
        weights.extend(len(local) * share / (2 * counts[row["label"]]) for row in pool)
    model = Pipeline([
        ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2, max_features=20000)),
        ("classifier", LogisticRegression(C=4.0, max_iter=1000, random_state=42)),
    ])
    model.fit([r["text"] for r in rows], [r["label"] for r in rows], classifier__sample_weight=weights)
    return model


def selection_key(result: dict) -> tuple:
    # Balance correct scam warnings and quiet legitimate calls. Break ties with
    # fewer false/premature alerts, faster warnings, then a threshold near 0.5.
    delay = result["mean_delay_turns"]
    return (result["balanced_call_score"],
            -result["false_alarm"] - result["premature_warning"],
            -delay if delay is not None else -float("inf"),
            -abs(result["threshold"] - 0.5))


def main() -> None:
    local, seed = training_rows()
    model = fit_model(local, seed)
    validation = read_jsonl(EVALUATION / "validation.jsonl")
    scores = score_calls(model, validation)
    trials = [measure(validation, scores, i / 100) for i in range(5, 100, 5)]
    selected = max(trials, key=selection_key)
    input_paths = [DATA / "train.jsonl", EVALUATION / "validation.jsonl"]
    input_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    artifact = {"model": model, "threshold": selected["threshold"],
                "sklearn_version": sklearn.__version__, "input_sha256": input_hashes}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_bytes(pickle.dumps(artifact, protocol=pickle.HIGHEST_PROTOCOL))
    write_report(EVALUATION / "validation_results.json", {
        "unique_training_prefixes": len(local), "public_training_calls": len(seed),
        "input_sha256": input_hashes, "selected": summary(selected),
        "threshold_trials": [summary(result) for result in trials],
    })
    print(json.dumps(summary(selected), indent=2))
    print("Model frozen. Run: uv run python evaluate.py")


if __name__ == "__main__":
    main()
