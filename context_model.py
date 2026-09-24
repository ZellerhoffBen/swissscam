"""MiniLM loading, prediction and checkpoint saving."""
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
BASE_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


class ContextClassifier:
    """Classify text with a local or pinned pretrained MiniLM checkpoint."""

    def __init__(self, path: str | Path, device: str = "cpu", revision: str | None = None) -> None:
        torch.set_num_threads(4)
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), revision=revision)
        # Preserve the recent request if a call exceeds the model's context window.
        self.tokenizer.truncation_side = "left"
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(path), revision=revision, num_labels=2,
            id2label={0: "NO_WARNING", 1: "WARNING"},
            label2id={"NO_WARNING": 0, "WARNING": 1},
        ).to(device)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        self.model.eval()
        scores = []
        with torch.inference_mode():
            for start in range(0, len(texts), 16):
                batch = self.tokenizer(texts[start:start + 16], padding=True,
                                       truncation=True, max_length=512, return_tensors="pt")
                logits = self.model(**batch.to(self.device)).logits
                scores.extend(logits.softmax(dim=-1).cpu().numpy())
        return np.asarray(scores)

    def save(self, path: Path) -> None:
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
