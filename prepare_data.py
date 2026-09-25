"""Load and validate the authored data used by MiniLM training and evaluation."""

import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "scam"
EVALUATION = ROOT / "evaluation"
SIGNALS = {
    "advance_fee", "banking_access", "cash_handover", "credential_request",
    "deceptive_authorisation", "gift_card_request", "isolation", "otp_request",
    "payment_pressure", "remote_access", "safe_account_transfer", "secrecy",
    "security_bypass", "threat", "unusual_payment", "urgency",
}
def normalize(text: str) -> str:
    """Ignore superficial formatting when checking duplicate text."""
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).lower()))


def transcript(turns: list[dict]) -> str:
    # The runtime transcriber does not promise speaker identification.
    return " ".join(turn["text"] for turn in turns)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_calls(split: str) -> list[dict]:
    return [row for row in read_jsonl(DATA / "authored.jsonl") if row["split"] == split]


def behavior_rows(split: str) -> list[dict]:
    return [{"id": pair["id"], "kind": pair["kind"], "text": pair[key], "label": label}
            for pair in read_jsonl(DATA / "behaviors.jsonl") if pair["split"] == split
            for key, label in (("legitimate", 0), ("scam", 1))]


def validate_behaviors() -> None:
    seen_ids, seen_texts = set(), set()
    for pair in read_jsonl(DATA / "behaviors.jsonl"):
        if pair["id"] in seen_ids or pair["split"] not in {"train", "validation", "test"}:
            raise ValueError("Duplicate behavior ID or invalid split.")
        seen_ids.add(pair["id"])
        for key in ("legitimate", "scam"):
            text = normalize(pair[key])
            if not text or text in seen_texts:
                raise ValueError("Empty or duplicate behavior text across examples/splits.")
            seen_texts.add(text)


def validate_authored(rows: list[dict]) -> None:
    if {r["split"] for r in rows} != {"train", "validation", "test"}:
        raise ValueError("Expected train, validation and test splits.")
    for split in ("train", "validation", "test"):
        labels = Counter(r["label"] for r in rows if r["split"] == split)
        if set(labels) != {0, 1} or labels[0] != labels[1]:
            raise ValueError(f"Unbalanced authored labels: {split}")
    pairs = defaultdict(list)
    for row in rows:
        pairs[row["group_id"]].append(row)
    for group, pair in pairs.items():
        if len(pair) != 2 or {r["label"] for r in pair} != {0, 1} or len({r["split"] for r in pair}) != 1:
            raise ValueError(f"Broken matched pair: {group}")
        receivers = [[t["text"] for t in r["turns"] if t["speaker"] == "receiver"] for r in pair]
        if receivers[0] != receivers[1]:
            raise ValueError(f"Receiver wording differs within a matched pair: {group}")
    for row in rows:
        turns, warning = row["turns"], row["warning_turn"]
        if row["annotation"] != "assistant_reviewed" or row["synthetic"] is not True:
            raise ValueError(f"Missing authorship disclosure: {row['id']}")
        if len(turns) < 4 or any(not t["text"].strip() or t["speaker"] not in {"caller", "receiver"} for t in turns):
            raise ValueError(f"Invalid turns: {row['id']}")
        if row["label"] == 0:
            if warning is not None or row["evidence"]:
                raise ValueError(f"Legitimate call has warning evidence: {row['id']}")
        else:
            if type(warning) is not int or not 1 <= warning <= len(turns):
                raise ValueError(f"Invalid warning turn: {row['id']}")
            if not row["evidence"] or min(e["turn"] for e in row["evidence"]) != warning:
                raise ValueError(f"Warning must match earliest evidence: {row['id']}")
            for evidence in row["evidence"]:
                turn = evidence["turn"]
                if not warning <= turn <= len(turns) or turns[turn - 1]["speaker"] != "caller":
                    raise ValueError(f"Invalid evidence turn: {row['id']}")
                if not evidence["text"] or evidence["text"] not in turns[turn - 1]["text"]:
                    raise ValueError(f"Evidence is not an exact substring: {row['id']}")
                if not evidence["signals"] or not set(evidence["signals"]) <= SIGNALS:
                    raise ValueError(f"Unknown signal: {row['id']}")
        row["text"] = transcript(turns)


def iter_prefixes(call: dict) -> Iterator[dict]:
    """Yield text-so-far labels only for calls with reviewed turn annotations."""
    if call["annotation"] != "assistant_reviewed":
        return
    for end in range(1, len(call["turns"]) + 1):
        warning = call["warning_turn"] is not None and end >= call["warning_turn"]
        yield {
            "text": transcript(call["turns"][:end]), "warning": warning,
        }


def audit_overlap(splits: dict[str, list[dict]]) -> dict:
    ids, groups, texts = {}, {}, {}
    for split, rows in splits.items():
        ids[split] = {r["id"] for r in rows}
        groups[split] = {r["group_id"] for r in rows}
        texts[split] = {normalize(r["text"]) for r in rows}
        if len(ids[split]) != len(rows) or len(texts[split]) != len(rows):
            raise ValueError(f"Duplicate call ID or full text within {split}.")
    for a, b in combinations(splits, 2):
        if ids[a] & ids[b] or groups[a] & groups[b] or texts[a] & texts[b]:
            raise ValueError(f"Call or group leaks between {a} and {b}.")
    # This lexical screen flags near copies, not all semantic paraphrases.
    shingle_sets, inverted = {}, defaultdict(set)
    for split, rows in splits.items():
        for row in rows:
            words = normalize(row["text"]).split()
            shingles = {tuple(words[i:i + 3]) for i in range(len(words) - 2)}
            shingle_sets[row["id"]] = (split, shingles)
            for shingle in shingles:
                inverted[shingle].add(row["id"])
    nearest = {}
    warnings = []
    for split in ("validation", "test"):
        maximum = (0.0, None, None)
        for row in splits[split]:
            shingles = shingle_sets[row["id"]][1]
            counts = Counter(other for sh in shingles for other in inverted[sh]
                             if shingle_sets[other][0] != split)
            for other, common in counts.items():
                score = common / len(shingles | shingle_sets[other][1])
                if score > maximum[0]:
                    maximum = (score, row["id"], other)
                if score >= 0.65:
                    warnings.append({"call": row["id"], "other": other, "jaccard": round(score, 4)})
        nearest[split] = {"jaccard": round(maximum[0], 4), "call": maximum[1], "other": maximum[2]}
    if warnings:
        raise ValueError(f"Review possible cross-split near copies: {warnings}")
    return {"exact_call_overlap": 0, "group_overlap": 0,
            "lexical_review_threshold": 0.65, "nearest_other_split": nearest}


def summarize(rows: list[dict]) -> dict:
    return {
        "calls": len(rows), "labels": dict(Counter(r["label"] for r in rows)),
        "sources": dict(Counter(r["source"] for r in rows)),
        "categories": dict(sorted(Counter(r["category"] for r in rows).items())),
        "median_words_by_label": {
            str(label): statistics.median(len(r["text"].split()) for r in rows if r["label"] == label)
            for label in (0, 1)
        },
    }


def training_rows() -> list[dict]:
    # Shared openings are counted once, with consistent labels.
    unique = {}
    for call in load_calls("train"):
        for prefix in iter_prefixes(call):
            key, label = normalize(prefix["text"]), int(prefix["warning"])
            if key in unique and unique[key]["label"] != label:
                raise ValueError("Conflicting training prefix labels.")
            unique[key] = {"text": prefix["text"], "label": label}
    return list(unique.values()) + behavior_rows("train")


def validate_data() -> dict:
    authored = read_jsonl(DATA / "authored.jsonl")
    validate_authored(authored)
    validate_behaviors()
    splits = {split: [r for r in authored if r["split"] == split]
              for split in ("train", "validation", "test")}
    return {
        "splits": {split: summarize(rows) for split, rows in splits.items()},
        "training_examples": len(training_rows()),
        "behavior_examples": {split: len(behavior_rows(split)) for split in splits},
        "overlap": audit_overlap(splits),
        "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (DATA / "authored.jsonl", DATA / "behaviors.jsonl")},
        "limitation": "Synthetic assistant-authored data; matching pairs share scaffolding. Lexical checks cannot prove semantic independence.",
    }


def main() -> None:
    report = validate_data()
    (DATA / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Validated {report['training_examples']} training examples; no split overlap.")


if __name__ == "__main__":
    main()
