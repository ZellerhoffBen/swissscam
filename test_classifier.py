"""Focused checks for warning timing, text boundaries and model integration."""

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from detector import detect, load_model
from evaluate import measure
from prepare_data import behavior_rows, iter_prefixes, validate_behaviors
from evaluate_external import source_metrics, verify_file


def call(label: int) -> dict:
    return {
        "id": f"fixture-{label}", "group_id": "fixture", "category": "bank",
        "label": label, "warning_turn": 3 if label else None,
        "annotation": "assistant_reviewed", "evidence": [],
        "turns": [{"speaker": "caller", "text": "Hello from the bank."},
                  {"speaker": "receiver", "text": "What is this about?"},
                  {"speaker": "caller", "text": "Read me your password." if label else "Visit your branch."},
                  {"speaker": "receiver", "text": "I understand."}],
    }


class EvaluationTests(unittest.TestCase):
    def test_external_metrics_keep_both_classes_and_serialize_numpy_scores(self) -> None:
        import numpy as np
        rows = [{"id": "scam", "label": 1}, {"id": "legitimate", "label": 0}]
        result = source_metrics(rows, np.array([0.9, 0.8]), 0.7)
        self.assertEqual(result["detected"], 1)
        self.assertEqual(result["false_alarm"], 1)
        self.assertEqual(result["balanced_accuracy"], 0.5)
        json.dumps(result)

    def test_frozen_evaluation_rejects_changed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            path.write_text("changed")
            with self.assertRaisesRegex(ValueError, "Frozen evaluation input changed"):
                verify_file(path, "0" * 64)

    def test_behavior_data_has_separate_balanced_splits(self) -> None:
        validate_behaviors()
        for split in ("train", "validation", "test"):
            rows = behavior_rows(split)
            self.assertTrue(rows)
            self.assertEqual(sum(r["label"] for r in rows), len(rows) // 2)

    def test_later_scam_does_not_make_early_warning_correct(self) -> None:
        result = measure([call(1), call(0)], [[0.9] * 4, [0.1] * 4], 0.5)
        self.assertEqual(result["premature_warning"], 1)
        self.assertEqual(result["detected"], 0)
        self.assertEqual(result["balanced_call_score"], 0.5)

    def test_first_warning_counts_even_if_score_later_drops(self) -> None:
        result = measure([call(1), call(0)], [[0.1, 0.1, 0.2, 0.8], [0.1, 0.8, 0.1, 0.1]], 0.5)
        self.assertEqual(result["detected"], 1)
        self.assertEqual(result["mean_delay_turns"], 1)
        self.assertEqual(result["false_alarm"], 1)

    def test_missing_warning_is_missed_and_threshold_is_inclusive(self) -> None:
        result = measure([call(1), call(0)], [[0.1] * 4, [0.1] * 4], 0.5)
        self.assertEqual(result["missed"], 1)
        result = measure([call(1), call(0)], [[0.1, 0.1, 0.5, 0.5], [0.1] * 4], 0.5)
        self.assertEqual(result["balanced_call_score"], 1)

    def test_future_request_is_hidden_and_seed_has_no_prefix_labels(self) -> None:
        fixture = call(1)
        prefixes = list(iter_prefixes(fixture))
        self.assertNotIn("password", prefixes[1]["text"])
        self.assertFalse(prefixes[1]["warning"])
        self.assertTrue(prefixes[2]["warning"])
        fixture["annotation"] = "source_call_label_only"
        self.assertEqual(list(iter_prefixes(fixture)), [])

    def test_incomplete_scores_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            measure([call(1), call(0)], [[0.1], [0.1]], 0.5)

class DetectorTests(unittest.TestCase):
    def tearDown(self) -> None:
        load_model.cache_clear()

    def test_runtime_uses_saved_threshold_and_keeps_response_contract(self) -> None:
        artifact = load_model()
        for text in ("Hello, this is your bank.",
                     "Hello, this is your bank. Please share your verification code."):
            expected = bool(artifact["model"].predict_proba([text])[0, 1] >= artifact["threshold"])
            result = detect(text)
            self.assertEqual(result.score, float(artifact["model"].predict_proba([text])[0, 1]))
            self.assertEqual(result.threshold, artifact["threshold"])
            self.assertEqual(result.warning, expected)
            self.assertEqual(result.signals, [])
            self.assertEqual(bool(result.reason), expected)

    def test_missing_model_never_silently_returns_no_warning(self) -> None:
        load_model.cache_clear()
        with tempfile.TemporaryDirectory() as directory:
            with patch("detector.MODEL_PATH", Path(directory) / "missing.pkl"):
                with self.assertRaisesRegex(RuntimeError, "train.py"):
                    detect("Hello")


if __name__ == "__main__":
    unittest.main()
