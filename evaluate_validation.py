"""Run the fixed pitch-validation set without training or changing thresholds."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from detector import load_model
from evaluate import measure, score_calls, summary, write_report
from prepare_data import ROOT, normalize, read_jsonl, transcript

SUITE = ROOT / "evaluation" / "validation"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(directory: Path = SUITE) -> tuple[list[dict], dict]:
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "calls.jsonl") != manifest["calls_sha256"]:
        raise ValueError("Frozen validation cases changed. Create a new version, not a silent replacement.")
    calls = read_jsonl(directory / "calls.jsonl")
    if Counter(c["group"] for c in calls) != {"scam": 20, "normal": 10, "hard_legitimate": 10}:
        raise ValueError("Expected 20 scam, 10 normal and 10 hard legitimate cases.")
    ids, texts = set(), set()
    for call in calls:
        text = normalize(transcript(call["turns"]))
        if call["id"] in ids or not text or text in texts:
            raise ValueError("Duplicate ID, empty call or duplicate transcript.")
        ids.add(call["id"])
        texts.add(text)
        if call["annotation"] != "assistant_reviewed" or not call["synthetic"]:
            raise ValueError("The authored suite must disclose its origin and label review.")
        if call["label"] != int(call["group"] == "scam"):
            raise ValueError("Call label and group disagree.")
        onset = call["warning_turn"]
        if call["label"] and (type(onset) is not int or not 1 <= onset <= len(call["turns"])):
            raise ValueError("Scam call needs a valid warning turn.")
        if not call["label"] and onset is not None:
            raise ValueError("Legitimate call cannot have a warning turn.")
        if call["source"] and call["source"] not in manifest["sources"]:
            raise ValueError("Missing source attribution.")
    old_calls = []
    for path in (ROOT / "data/scam/authored.jsonl", ROOT / "evaluation/fresh_calls.jsonl",
                 ROOT / "evaluation/regressions.jsonl"):
        old_calls.extend(read_jsonl(path))
    if texts & {normalize(transcript(c["turns"])) for c in old_calls}:
        raise ValueError("Validation contains a full transcript already used in previous work.")
    planned = [item for item in manifest["audio"] if item["kind"] == "human"]
    by_id = {c["id"]: c for c in calls}
    if len(planned) != 12:
        raise ValueError("Expected twelve scripted recordings.")
    if len({item["id"] for item in manifest["audio"]}) != len(manifest["audio"]):
        raise ValueError("Duplicate audio ID.")
    # The case metadata records the original selection, not the recording method.
    if {item["id"] for item in planned} != {c["id"] for c in calls if c["audio"]}:
        raise ValueError("Audio plan does not match the frozen cases.")
    if sum(by_id[item["id"]]["label"] for item in planned) != 6:
        raise ValueError("Audio selection must contain six scam and six legitimate calls.")
    return calls, manifest


def audio_outcome(label: int | None, onset: float | None, first: float | None) -> str:
    """An unknown source label or missing onset must never become a passing test."""
    if label is None:
        return "unlabelled"
    if label == 0:
        return "false_alarm" if first is not None else "correctly_quiet"
    if onset is None:
        return "onset_not_annotated"
    if first is None:
        return "missed"
    return "premature_warning" if first < onset else "detected"


def audio_summary(recordings: list[dict]) -> dict:
    tested = [r for r in recordings if r["status"] == "tested" and r.get("label") in (0, 1)]
    scams = [r for r in tested if r["label"] == 1]
    legitimate = [r for r in tested if r["label"] == 0]
    return {
        "labelled_recordings_tested": len(tested),
        "scam_calls": len(scams), "scam_calls_flagged": sum(r["ever_warned"] for r in scams),
        "legitimate_calls": len(legitimate), "false_alarms": sum(r["ever_warned"] for r in legitimate),
        "scam_calls_without_onset_annotation": sum(r["warning_onset_seconds"] is None for r in scams),
        "note": "Flagged means a warning occurred somewhere in the call, not necessarily at the right point.",
    }


def evaluate_recording(item: dict, call: dict | None, artifact: dict) -> dict:
    from transcription import transcribe_stream

    path = ROOT / item["file"]
    result = {"id": item["id"], "kind": item["kind"], "file": item["file"]}
    if not path.exists():
        return {**result, "status": "missing", "outcome": "not_tested"}
    actual_hash = sha256(path)
    if item["sha256"] and actual_hash != item["sha256"]:
        raise ValueError(f"Frozen audio changed: {item['id']}")
    segments = list(transcribe_stream(path))
    if not segments:
        return {**result, "status": "empty_transcript", "outcome": "not_tested", "sha256": actual_hash}
    texts = [" ".join(s.text for s in segments[:end]) for end in range(1, len(segments) + 1)]
    scores = artifact["model"].predict_proba(texts)[:, 1]
    first = next((s.end_seconds for s, score in zip(segments, scores)
                  if score >= artifact["threshold"]), None)
    label = call["label"] if call else item["label"]
    onset = item["warning_onset_seconds"]
    if onset is not None and (not isinstance(onset, (int, float)) or onset < 0):
        raise ValueError(f"Invalid audio onset: {item['id']}")
    result.update(status="tested", sha256=actual_hash, frozen=bool(item["sha256"]),
                  label=label, warning_onset_seconds=onset, first_warning_audio_seconds=first,
                  outcome=audio_outcome(label, onset, first), scores=[float(s) for s in scores],
                  ever_warned=first is not None,
                  final_warning=bool(scores[-1] >= artifact["threshold"]))
    if call:
        reference_score = float(artifact["model"].predict_proba([transcript(call["turns"])])[0, 1])
        result.update(reference_final_score=reference_score,
                      reference_final_warning=reference_score >= artifact["threshold"],
                      final_decision_differs_from_script=(reference_score >= artifact["threshold"]) != result["final_warning"],
                      segments=[s.model_dump() for s in segments])
    # Keep third-party speech and identifiers out of committed result files.
    else:
        result["source"] = item["source"]
        result["transcript_sha256"] = hashlib.sha256(texts[-1].encode()).hexdigest()
    return result


def compare_reports(current: dict, previous: dict) -> dict:
    if current["cases_sha256"] != previous["cases_sha256"]:
        raise ValueError("Cannot compare different test cases.")
    before = {c["id"]: c["outcome"] for c in previous["text"]["calls"]}
    after = {c["id"]: c["outcome"] for c in current["text"]["calls"]}
    if before.keys() != after.keys():
        raise ValueError("Cannot compare incomplete call results.")
    counts = ("detected", "missed", "premature_warning", "false_alarm", "correctly_quiet")
    return {
        "baseline_model_sha256": previous["model_files_sha256"]["model.safetensors"],
        "count_changes": {key: current["text"][key] - previous["text"][key] for key in counts},
        "changed_calls": [{"id": id, "before": before[id], "after": after[id]}
                          for id in after if before[id] != after[id]],
        "lost_detections": [id for id in after if before[id] == "detected" and after[id] != "detected"],
        "note": "Text comparison only. Audio requires matching file hashes and onset annotations.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "models/context")
    parser.add_argument("--audio", action="store_true", help="Also run Whisper on available planned recordings.")
    parser.add_argument("--compare", type=Path, help="Previous report for a per-call text comparison.")
    parser.add_argument("--output", type=Path, help="New report path; existing reports are never overwritten.")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    output = args.output or SUITE / "runs" / f"{now:%Y%m%dT%H%M%S%fZ}.json"
    if output.exists():
        raise FileExistsError(f"Preserve the previous run; choose a new output path: {output}")
    calls, manifest = load_suite()
    artifact = load_model(args.model)
    result = measure(calls, score_calls(artifact["model"], calls), artifact["threshold"])
    groups = {}
    for group in ("scam", "normal", "hard_legitimate"):
        ids = {c["id"] for c in calls if c["group"] == group}
        groups[group] = {"total": len(ids), "outcomes": dict(Counter(c["outcome"] for c in result["calls"] if c["id"] in ids))}
    report = {
        "created_utc": now.isoformat(), "suite_version": manifest["version"],
        "cases_sha256": manifest["calls_sha256"], "manifest_sha256": sha256(SUITE / "manifest.json"),
        "model_files_sha256": {p.name: sha256(p) for p in sorted(args.model.iterdir())
                               if p.suffix in {".json", ".safetensors", ".txt"}},
        "evaluator_sha256": {name: sha256(ROOT / name) for name in
                             ("evaluate_validation.py", "evaluate.py", "context_model.py", "transcription.py")},
        "threshold": artifact["threshold"], "text": result, "groups": groups,
        "audio_requested": args.audio, "audio": [],
        "limitations": ["Authored, assistant-reviewed cases; not independent human validation or real-world accuracy.",
                        "Repeated runs are regression checks; do not train or tune on these cases.",
                        "Twelve audio cases are a subset, not twelve additional independent conversations.",
                        "Original robocalls are unlabelled exploratory checks, excluded from accuracy counts.",
                        "Audio times locate speech, not wall-clock latency or smartphone performance."],
    }
    by_id = {c["id"]: c for c in calls}
    for item in manifest["audio"]:
        if args.audio:
            print(f"Audio: {item['id']}", flush=True)
            report["audio"].append(evaluate_recording(item, by_id.get(item["id"]), artifact))
        else:
            report["audio"].append({"id": item["id"], "kind": item["kind"], "status": "not_run", "outcome": "not_tested"})
    report["audio_status"] = dict(Counter(item["status"] for item in report["audio"]))
    report["audio_summary"] = audio_summary(report["audio"])
    if args.compare:
        report["comparison"] = compare_reports(report, json.loads(args.compare.read_text()))
    write_report(output, report)
    print(json.dumps({"text": summary(result), "groups": groups, "audio_status": report["audio_status"],
                      "audio_summary": report["audio_summary"]}, indent=2))
    if args.compare:
        print(json.dumps(report["comparison"], indent=2))
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
