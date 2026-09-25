"""Fine-tune MiniLM and choose its checkpoint/threshold using validation only."""
import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path

import numpy as np

from ml.evaluate import measure, score_calls, summary, write_report
from ml.prepare_data import DATA, behavior_rows, load_calls, training_rows, validate_data


def choose_threshold(model: object, calls: list[dict], behaviors: list[dict]) -> dict:
    call_scores = score_calls(model, calls)
    behavior_scores = model.predict_proba([r["text"] for r in behaviors])[:, 1]
    trials = []
    for threshold in (i / 100 for i in range(5, 100, 5)):
        call_result = measure(calls, call_scores, float(threshold))
        correct = sum((score >= threshold) == r["label"] for r, score in zip(behaviors, behavior_scores))
        # Equal influence for call-level behavior and the explicit language checks.
        quality = (call_result["balanced_call_score"] + correct / len(behaviors)) / 2
        trials.append({"quality": float(quality), "behavior_correct": int(correct),
                       "behavior_total": len(behaviors), **summary(call_result)})
    return max(trials, key=lambda r: (r["quality"], -r["false_alarm"] - r["premature_warning"],
                                      -(r["mean_delay_turns"] or 0), -abs(r["threshold"] - 0.7)))


def train_context(rows: list[dict], validation: list[dict], behaviors: list[dict], output: Path) -> dict:
    import torch
    from backend.context_model import BASE_MODEL, BASE_REVISION, ContextClassifier

    torch.manual_seed(42)
    random.seed(42)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    classifier = ContextClassifier(BASE_MODEL, device, BASE_REVISION)
    optimizer = torch.optim.AdamW(classifier.model.parameters(), lr=2e-5, weight_decay=0.01)
    counts = np.bincount([r["label"] for r in rows])
    weights = torch.tensor(len(rows) / (2 * counts), dtype=torch.float32, device=device)
    best = None
    epochs = []
    # Fixed budget; checkpoint selection uses validation only.
    for epoch in range(1, 7):
        classifier.model.train()
        order = list(range(len(rows)))
        random.shuffle(order)
        loss_sum = 0.0
        for start in range(0, len(order), 16):
            batch_rows = [rows[i] for i in order[start:start + 16]]
            inputs = classifier.tokenizer([r["text"] for r in batch_rows], padding=True,
                                          truncation=True, max_length=512, return_tensors="pt").to(device)
            labels = torch.tensor([r["label"] for r in batch_rows], device=device)
            optimizer.zero_grad()
            logits = classifier.model(**inputs).logits
            loss = torch.nn.functional.cross_entropy(logits, labels, weight=weights)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(classifier.model.parameters(), 1.0)
            optimizer.step()
            loss_sum += float(loss.detach().cpu())
        selected = {"epoch": epoch, **choose_threshold(classifier, validation, behaviors)}
        epochs.append(selected)
        print(json.dumps({"loss_sum": loss_sum, **selected}), flush=True)
        if best is None or selected["quality"] > best["quality"]:
            best = selected
            classifier.save(output)
    return {"selected": best, "epochs": epochs,
            "base_model": BASE_MODEL, "base_revision": BASE_REVISION,
            "training": {"seed": 42, "epochs": 6, "batch_size": 16, "learning_rate": 2e-5,
                         "weight_decay": 0.01, "max_tokens": 512, "examples": len(rows)},
            "torch_version": torch.__version__}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("models/candidate"))
    output = parser.parse_args().output
    if output.resolve() == Path("models/context").resolve():
        parser.error("Use a separate candidate directory; keep active weights unchanged.")
    validate_data()
    report = train_context(training_rows(), load_calls("validation"), behavior_rows("validation"), output)
    metadata = {
        "model_type": "MiniLM sequence classifier", "threshold": report["selected"]["threshold"],
        "base_model": report["base_model"], "base_revision": report["base_revision"],
        "training": report["training"], "selected_epoch": report["selected"]["epoch"],
        "weights_sha256": hashlib.sha256((output / "model.safetensors").read_bytes()).hexdigest(),
        "input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (DATA / "authored.jsonl", DATA / "behaviors.jsonl")},
    }
    write_report(output / "metadata.json", metadata)
    write_report(output / "validation_results.json", report)
    shutil.copyfile("models/context/LICENSE", output / "LICENSE")
    print(f"Candidate saved to {output}. Active model unchanged.")


if __name__ == "__main__":
    main()
