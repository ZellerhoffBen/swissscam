"""Focused checks for warning timing, text boundaries and model integration."""

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from backend.detector import detect, load_model
from ml.evaluate import measure
from ml.prepare_data import behavior_rows, iter_prefixes, validate_behaviors
from ml.evaluate_external import source_metrics, verify_file
from ml.evaluate_validation import audio_outcome, audio_summary, compare_reports, load_suite, SUITE


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
    def test_validation_suite_is_frozen_balanced_and_separate(self) -> None:
        calls, manifest = load_suite()
        self.assertEqual(len(calls), 40)
        self.assertEqual(sum(c["label"] for c in calls), 20)
        self.assertEqual(len(manifest["audio"]), 14)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text((SUITE / "manifest.json").read_text())
            (path / "calls.jsonl").write_text((SUITE / "calls.jsonl").read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "Frozen validation cases changed"):
                load_suite(path)

    def test_unlabelled_audio_and_missing_onsets_are_not_passing_tests(self) -> None:
        self.assertEqual(audio_outcome(None, None, 5), "unlabelled")
        self.assertEqual(audio_outcome(1, None, 5), "onset_not_annotated")
        self.assertEqual(audio_outcome(1, 10, 5), "premature_warning")
        self.assertEqual(audio_outcome(1, 10, 10), "detected")
        self.assertEqual(audio_outcome(1, 10, None), "missed")
        self.assertEqual(audio_outcome(0, None, 0), "false_alarm")
        self.assertEqual(audio_outcome(0, None, None), "correctly_quiet")

    def test_audio_summary_separates_call_warnings_from_verified_onsets(self) -> None:
        report = audio_summary([
            {"status": "missing"},
            {"status": "tested", "label": None},
            {"status": "tested", "label": 1, "ever_warned": True, "warning_onset_seconds": None},
            {"status": "tested", "label": 0, "ever_warned": True, "warning_onset_seconds": None},
        ])
        self.assertEqual(report["labelled_recordings_tested"], 2)
        self.assertEqual(report["scam_calls_flagged"], 1)
        self.assertEqual(report["false_alarms"], 1)
        self.assertEqual(report["scam_calls_without_onset_annotation"], 1)

    def test_comparison_reports_lost_detections_even_if_false_alarms_improve(self) -> None:
        before = {"cases_sha256": "same", "model_files_sha256": {"model.safetensors": "old"},
                  "text": measure([call(1), call(0)], [[0, 0, 1, 1], [0, 0, 1, 1]], 0.5)}
        after = {**before, "text": measure([call(1), call(0)], [[0]*4, [0]*4], 0.5)}
        result = compare_reports(after, before)
        self.assertEqual(result["count_changes"]["false_alarm"], -1)
        self.assertEqual(result["lost_detections"], ["fixture-1"])
        with self.assertRaisesRegex(ValueError, "different test cases"):
            compare_reports({**after, "cases_sha256": "different"}, before)

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
            with patch("backend.detector.MODEL_PATH", Path(directory) / "model.safetensors"):
                with self.assertRaisesRegex(RuntimeError, "Classifier missing"):
                    detect("Hello")


if __name__ == "__main__":
    unittest.main()
