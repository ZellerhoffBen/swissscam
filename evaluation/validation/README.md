# Repeatable validation

Run the same 40 conversations after a model change. This is a small scenario test,
not an estimate of performance on all real phone calls. The app and model were not
changed for this evaluation.

## Run

```sh
uv run python -m ml.evaluate_validation
uv run python -m ml.evaluate_validation --compare evaluation/validation/baseline.json
uv run python -m ml.evaluate_validation --model models/candidate --compare evaluation/validation/baseline.json
uv run python -m ml.evaluate_validation --audio
```

Each run creates a new JSON report in ignored `runs/`. Use `--output path.json` to
save a report elsewhere; existing reports cannot be overwritten. Reports record
model, data and code hashes, thresholds, individual outcomes and missing audio.
Comparison lists changed text outcomes and lost scam detections, not just a total
score. Audio reports separately list call-level warnings and transcript differences.

## Fixed test set

`calls.jsonl` contains 20 scams, 10 ordinary legitimate calls and 10 plausible
legitimate calls involving security, payments or support. Each has six spoken
turns and 80–103 words, roughly 30–60 seconds at conversational speed.
Scams cover family impersonation, shock calls, fake police, banking and support.

The assistant wrote and reviewed the scenarios before running the classifier.
All 20 scam scenarios use mechanisms documented by the NCSC, FTC, CFPB or US
Office for Victims of Crime. Source links and the distinction between invented
dialogue and original audio are in `manifest.json`. These are **reenactments, not
transcripts of 20 actual victims' calls**, and have no independent human review.

Cases, labels, first harmful turns and the audio selection were fixed before the
first model run. The manifest pins the cases' hash. Exact full-call duplicates
against existing training and evaluation conversations are rejected; thematic
similarity remains. Only spoken text enters the model, cumulatively, one turn at
a time. IDs, roles, labels and source descriptions never enter the classifier.

For scam calls, the first warning must occur at or after the annotated harmful
turn. An earlier warning is a failure. Any warning on a legitimate call is a
false alarm, even if the score later falls. No warning means insufficient evidence,
not proof that the caller is genuine. The active threshold remains 0.95.

Keep these cases out of training and threshold selection. After results have been
inspected they are regression cases, not an untouched test. Before claiming further
improvement, add a small new batch written and reviewed independently of model
results. Never remove a failed case to make the score better.

## First result — 24 September 2026

| Group | Result |
| --- | --- |
| 20 scam calls | 20 detected at the first annotated harmful turn; none missed or premature |
| 10 ordinary legitimate calls | 0 false alarms |
| 10 harder legitimate calls | 4 false alarms |

The false alarms are `h04` (reporting a scam), `h07` (requested router support),
`h08` (shop refund) and `h10` (work-account recovery). The 36/40 correct outcomes
apply only to this fixed set. The earlier, harder 80-call test still had 14/40
false alarms; the new result does not supersede it or show a model improvement.

`baseline.json` contains the complete text and audio run. Cleanup consolidated
the earlier reports; all text outcomes and audio decisions were checked against
the previous runs. No test cases, model weights or thresholds changed.

## Audio checks

Twelve of the 40 cases are selected in advance: six scam and six legitimate.
These recordings are another input format for the same cases, not 12 independent
additional conversations.

All twelve were recorded by two team members. No TTS was used. Whisper reads
the unchanged M4A files in `audio/` directly. Files are named by case ID;
`manifest.json` preserves their original filenames and SHA-256 hashes.

The [recording scripts](SCRIPTS.md) are retained as references. The frozen cases'
`audio` field describes the original production plan; the manifest's `kind`
records the actual human-spoken origin.
IDs were assigned by reviewing recognised dialogue against the scripts before
running audio classification. Small wording/recognition differences remain; the
scripts are not independently checked verbatim transcripts of the recordings.

`--audio` runs real Whisper followed by MiniLM on accumulated transcript segments.
For each scripted recording it also compares the model's final decision on the
written script with its final decision on Whisper's text. A change can reflect
spoken wording or recognition errors; matching decisions do not prove a perfect transcript.
The first-warning outcome is reported separately. Missing files, empty transcripts,
missing onset annotations and files without frozen hashes stay visible.

Recorded audio results:

| Human-spoken recordings | Call-level result |
| --- | --- |
| 6 scam calls | All 6 triggered a warning |
| 3 ordinary legitimate calls | No false alarms |
| 3 harder legitimate calls | 1 false alarm: `h07`, requested router support |

All twelve final decisions match the corresponding complete-script decisions.
The router-support false alarm already occurred in the text baseline. This does
not establish robustness across other speakers, noise levels or real telephone calls.

**Warning timing remains unverified:** no independently checked harmful-request
timestamps were supplied. Scam outcomes therefore remain `onset_not_annotated`,
while `audio_summary` counts whether a warning occurred anywhere in the call.
It does not claim six correctly timed warnings. To complete that check, annotate
`warning_onset_seconds` by listening to the original audio, independently of
Whisper's timestamps and classifier scores, then save a new run. There is no
wall-clock latency benchmark or smartphone performance claim.

Two additional files are unchanged real telephone recordings from the
[International Robocalls Dataset](https://zenodo.org/records/21066049), by
Kemal Altwlkany, Andro Merćep, Tomislav Đuričić, Ante Kapetanović and Emanuel Lacic
(2026), under **CC BY-NC 4.0**. They are for non-commercial research evaluation;
commercial reuse needs separate permission. Original files remain locally in
ignored `evaluation/external/robocalls/`; reports do not redistribute their speech.

We selected the first two US-English filenames in sorted order lasting 10–60
seconds, before classifier inference: `english_us_0004.wav` (33.36s) and
`english_us_0006.wav` (24.48s). They contain a debt-collection message and an account
login alert. The source confirms robocalls, not individual fraud labels; these
are exploratory audio-pipeline checks, excluded from accuracy counts.

To restore these optional original recordings on another machine:

```sh
mkdir -p evaluation/external/robocalls
curl -L --fail https://zenodo.org/api/records/21066049/files/audio.zip/content -o evaluation/external/robocalls/audio.zip
uv run python - <<'PY'
import hashlib, zipfile
from pathlib import Path
folder = Path('evaluation/external/robocalls')
archive = folder / 'audio.zip'
assert hashlib.md5(archive.read_bytes()).hexdigest() == 'c0e832c51613a8015ab586031b273876'
with zipfile.ZipFile(archive) as source:
    for name in ('english_us_0004.wav', 'english_us_0006.wav'):
        (folder / name).write_bytes(source.read('audio/english_us/' + name))
PY
```

## Submission wording

> We evaluated the local classifier on 40 fixed English conversations: 20 scam,
> 10 ordinary legitimate and 10 more challenging legitimate scenarios. Scam
> scenarios were informed by official fraud reports and guidance, with newly
> authored dialogue. The model detected all 20 scams at the first annotated
> harmful turn, with no premature alerts. It produced four false alarms among
> 20 legitimate calls. We separately exercised the transcription and detection
> pipeline on two original robocall recordings, without claiming fraud accuracy
> for those unlabelled examples. Two team members also recorded twelve of the
> fixed scenarios. In the audio pipeline, all six scam calls triggered a warning
> and one of six legitimate calls triggered a false alarm. Warning timing in
> those recordings has not been independently verified. Every model version can
> run the same checks with saved model/data hashes. This is prototype validation,
> not real-world accuracy.
