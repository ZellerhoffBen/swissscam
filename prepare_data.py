"""Prepare scam-call data offline using only the Python standard library."""

import csv
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
SOURCE_SHA256 = "fe8a8fa0aa2b8afb0b0a672fb7f9739b323cb6dd12064f786a68c2a1f49a4e0b"
REVISION = "321b961b5ae353e19ed479b960658dcd223d5e06"
SPEAKER = re.compile(r"\b(caller|receiver):\s*", re.IGNORECASE)
SIGNALS = {
    "advance_fee", "banking_access", "cash_handover", "credential_request",
    "deceptive_authorisation", "gift_card_request", "isolation", "otp_request",
    "payment_pressure", "remote_access", "safe_account_transfer", "secrecy",
    "security_bypass", "threat", "unusual_payment", "urgency",
}
# One-based CSV data rows, excluding the header. These examples omit key dialogue.
REVIEW_EXCLUSIONS = {
    364: "Receiver comments on a callback number that the caller never supplies.",
    607: "Receiver refers to an SSN request absent from the preceding dialogue.",
    807: "Unrecognised order is treated as verified without resolving the mismatch.",
}
REVIEW_SAMPLE = [
    7, 29, 164, 190, 207, 229, 364, 390, 407, 429, 564, 590,
    607, 629, 764, 790, 807, 829, 964, 990, 1007, 1029, 1164, 1190,
    1207, 1229, 1364, 1390, 1407, 1429, 1564, 1590,
]


def normalize(text: str) -> str:
    """Ignore superficial formatting when checking duplicate text."""
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).lower()))


def transcript(turns: list[dict]) -> str:
    # The runtime transcriber does not promise speaker identification.
    return " ".join(turn["text"] for turn in turns)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def prepare_seed() -> tuple[list[dict], list[dict], int]:
    source = DATA / "source" / "scam-dialogue.csv"
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source CSV changed: review the new revision before preparing data.")
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    kept, excluded, seen = [], [], {}
    cleaned_count = 0
    for number, row in enumerate(rows, 1):
        original = row["dialogue"].strip()
        reason = REVIEW_EXCLUSIONS.get(number)
        if not reason and re.search(r"\*gives fake[^*]*\*", original):
            reason = "Non-spoken fake-number annotation; supplied dialogue is incomplete."
        if not reason and not re.search(r"[.!?][\"']?$", original):
            reason = "Possibly truncated ending; excluded rather than guessing missing speech."
        # Only observed non-spoken stage directions are removed, not arbitrary asterisks.
        text = re.sub(r"\*\s*(?:ahem|pauses?|rustling papers|writes down license number)\s*\*", "", original)
        text = " ".join(text.split())
        pieces = SPEAKER.split(text)
        turns = [{"speaker": pieces[i].lower(), "text": pieces[i + 1].strip()}
                 for i in range(1, len(pieces), 2)]
        if not reason and (pieces[0].strip() or len(turns) < 2 or any(not t["text"] for t in turns)):
            reason = "Unparseable dialogue or empty speaker turn."
        key = normalize(transcript(turns))
        label = int(row["label"])
        if key in seen and seen[key][1] != label:
            raise ValueError(f"Conflicting seed labels at data row {number}")
        if not reason and key in seen:
            reason = f"Duplicate after normalisation of data row {seen[key][0]}."
        if reason:
            excluded.append({"source_row": number, "category": row["type"], "label": label, "reason": reason})
            continue
        seen[key] = (number, label)
        cleaned_count += text != " ".join(original.split())
        kept.append({
            "id": f"seed-{number:04d}", "group_id": f"seed-{row['type']}",
            "split": "train", "category": row["type"], "label": label,
            "source": "BothBosu/scam-dialogue", "source_row": number,
            "synthetic": True, "annotation": "source_call_label_only",
            "turns": turns, "text": transcript(turns), "warning_turn": None,
            "evidence": [],
        })
    return kept, excluded, cleaned_count


def validate_authored(rows: list[dict]) -> None:
    expected = {"train": 240, "validation": 40, "test": 40}
    if dict(Counter(r["split"] for r in rows)) != expected:
        raise ValueError("Authored split sizes must be 240 / 40 / 40.")
    for split, count in expected.items():
        labels = Counter(r["label"] for r in rows if r["split"] == split)
        if labels != {0: count // 2, 1: count // 2}:
            raise ValueError(f"Unbalanced authored labels: {split}")
    categories = {"family": 20, "shock": 20, "police": 20, "bank": 20,
                  "support": 10, "refund": 10, "delivery": 10, "insurance": 10}
    expected_training = {(category, label): count for category, count in categories.items() for label in (0, 1)}
    if Counter((r["category"], r["label"]) for r in rows if r["split"] == "train") != expected_training:
        raise ValueError("Authored training categories do not match the agreed coverage.")
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


def main() -> None:
    seed, excluded, cleaned_count = prepare_seed()
    authored = read_jsonl(DATA / "authored.jsonl")
    validate_authored(authored)
    splits = {split: [r for r in authored if r["split"] == split]
              for split in ("train", "validation", "test")}
    splits["train"] = seed + splits["train"]
    overlap = audit_overlap(splits)
    prefixes = [p for call in splits["train"] for p in iter_prefixes(call)]
    # Matched pairs intentionally share harmless beginnings; their prefix labels must agree.
    prefix_labels = defaultdict(set)
    for prefix in prefixes:
        prefix_labels[normalize(prefix["text"])].add(prefix["warning"])
    if any(len(labels) != 1 for labels in prefix_labels.values()):
        raise ValueError("Identical authored prefixes have contradictory warning labels.")
    paths = {
        DATA / "train.jsonl": splits["train"],
        EVALUATION / "validation.jsonl": splits["validation"],
        EVALUATION / "test.jsonl": splits["test"],
    }
    for path, rows in paths.items():
        write_jsonl(path, rows)
    report = {
        "source_revision": REVISION, "source_sha256": SOURCE_SHA256,
        "source_rows": len(seed) + len(excluded), "seed_kept": len(seed),
        "seed_excluded": len(excluded), "stage_directions_removed_from_calls": cleaned_count,
        "excluded_rows": excluded,
        "seed_review": {"method": "Assistant qualitative sample review, not independent human annotation",
                        "sample_rows": REVIEW_SAMPLE, "sample_size": len(REVIEW_SAMPLE)},
        "splits": {split: summarize(rows) for split, rows in splits.items()},
        "authored_train": summarize([r for r in authored if r["split"] == "train"]),
        "train_prefixes": len(prefixes), "unique_train_prefix_texts": len(prefix_labels),
        "prefix_labels": dict(Counter(p["warning"] for p in prefixes)),
        "overlap": overlap,
        "files_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        "limitations": [
            "All data is synthetic; no measured model accuracy or real-world validation.",
            "Seed call labels are not turn labels and were only sample-reviewed.",
            "Authored pairs share scaffolding; held-out calls are only 20 scenario pairs per split.",
            "No audio timestamps, ASR errors, or harm-event annotations are supplied.",
            "The small enrichment set reduces but does not eliminate seed topic bias.",
        ],
    }
    (DATA / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Prepared {len(seed)} seed + 240 authored training calls, 40 validation, 40 test.")
    print(f"Excluded {len(excluded)} seed rows; checked {len(prefixes)} text-so-far examples.")
    print("No exact full-call or group overlap between splits; lexical overlap check passed.")


if __name__ == "__main__":
    main()
