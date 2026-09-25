# Evaluation

The active MiniLM classifier is a hackathon prototype. It still produces false
alarms on security advice and reported scams. Scores are not calibrated probabilities.
All local text cases are synthetic and assistant-labelled; both supplied recordings
are synthetic voices. These are now known regression cases, not untouched tests.

## Run

```sh
uv run python -m ml.evaluate                       # Call, behavior and wording checks
uv run python -m ml.evaluate_audio                 # Real Whisper on both supplied MP3s
uv run python -m ml.evaluate_external              # External corpus, downloaded below
uv run python -m ml.evaluate --model models/candidate
```

For the fixed **20 scam / 10 normal / 10 harder legitimate** pitch-validation set,
run `uv run python -m ml.evaluate_validation`. See [protocol, results and recording
scripts](validation/README.md). It supports candidate comparison and optional audio
checks; missing recordings are reported rather than counted as passing tests.

The three scripts write `reports/results.json`, `reports/audio_results.json` and
`reports/external_results.json`, including model/data hashes. Candidate evaluation writes
inside the candidate directory. No evaluation command changes model weights.

## Cases and measurements

- The `test` split in `data/scam/authored.jsonl` contains 48 calls.
- `cases/fresh_calls.jsonl` contains 80 further calls in 40 paired scenarios.
- `cases/regressions.jsonl` contains the two reported bank/SSA conversations.
- The `test` split in `data/scam/behaviors.jsonl` contains 24 short texts. Checks
  also remove punctuation or add an irrelevant introduction.
- `data/audio/bank_legitimate.mp3` and `ssa_scam.mp3` exercise actual Whisper
  segment boundaries. The first explicit SSN request ends at 29.12 seconds.

Call scoring uses accumulated text after each turn. The first warning counts even
if its score later drops. Warnings before annotated evidence are failures.
Paired variants and formatting variants are related cases, not independent samples.

## Recorded model comparison

Models and thresholds were frozen before the fresh evaluation: TF-IDF at 0.70 and
MiniLM at 0.95. Neither was retrained on the fresh cases or external corpus.

| Check | Previous TF-IDF | Active MiniLM |
| --- | ---: | ---: |
| 80 further calls: timely scam detection | 34/40 | 37/40 |
| 80 further calls: premature scam warnings | 2/40 | 2/40 |
| 80 further calls: false alarms | 15/40 | 14/40 |
| Original 48 calls: timely scam detection | 23/24 | 24/24 |
| Original 48 calls: false alarms | 3/24 | 4/24 |
| Behavior checks | 15/24 | 19/24 |
| External scam-labelled texts detected | 108/394 | 189/394 |
| External legitimate texts flagged | 1/400 | 1/400 |

MiniLM handles both supplied recordings correctly: no warning on the bank call,
and a warning at 29.12s on the scam. Warm CPU analysis averaged about 12ms per
update on the development machine, excluding model load.

The predeclared target of at most 2/40 false alarms on the further calls **failed**.
MiniLM was adopted as the relatively better prototype, not as production-ready.
It changes six of 24 behavior decisions after a neutral introduction and misses
205 external scam-labelled texts. Future accuracy claims need independent human
review and genuinely new calls.

The completed comparison scripts, old model and intermediate reports were removed
during cleanup. This table retains the historical result; the remaining scripts
reproduce the active model's results. The active weight hash is recorded in
`models/context/metadata.json`. Cleanup did not retrain or alter the model.

## Discarded Apertus experiment (2026-09-24)

We tested official Apertus Mini v1.1 Instruct 1.5B and 4B MLX INT4 models locally
as a second opinion on MiniLM. The final task was only a choice between scam
suspicion, no evidence yet, and uncertainty; no generated explanations or JSON.
Prompts and hybrid triggers were selected on 48 existing validation calls, then
frozen before evaluating 40 new synthetic calls (20 scam, 20 legitimate).
The hybrid consulted Apertus at MiniLM scores >=0.70; uncertainty fell back to
MiniLM's existing 0.95 threshold. We counted the first warning in each call.

| System | Timely scam warnings | Missed scams | Premature scam warnings | Legitimate calls flagged |
| --- | ---: | ---: | ---: | ---: |
| MiniLM | 20/20 | 0 | 0 | 5/20 |
| MiniLM + Apertus 1.5B | 19/20 | 0 | 1 | 6/20 |
| MiniLM + Apertus 4B | 18/20 | 1 | 1 | 4/20 |

**Decision: keep MiniLM.** With the selected prompt, 1.5B labelled every prefix
suspicious. The 4B hybrid removed one false alarm but suppressed a correct warning
on a request to approve a new bank device and share its activation code. Its
improvement on validation calls did not carry over to the new cases. Reported
scams and protective advice remained difficult. Simplifying the output removed
format failures, but did not solve the classification problem.

Speed was acceptable on an M1 Pro with 16GB RAM: 4B averaged 0.87s per check
(p95 2.18s), with 3.46GB peak MLX allocation, excluding other application memory.
This was not tested on a smartphone or alongside Whisper. The cases were
assistant-authored and labelled, with paired scenarios; they do not establish
real-world accuracy or rule out other local LLM configurations.

The experiment code, dependencies, weights, datasets and raw reports were removed.
This note retains the findings, not a reproducible benchmark. The active model
and application were unchanged. Future candidates need new, independently reviewed
calls and fewer false alarms without losing timely scam detections.

## External data

[Tee Connie et al., Scam and Non-Scam Call Conversation Dataset, version 1](https://www.kaggle.com/datasets/teeconnie/scam-and-non-scam-call-conversation-dataset/versions/1)
contains 400 scam and 400 non-scam texts, combining collected scenarios with
synthetic augmentation. Six exact duplicate scam texts are excluded before scoring.
Source labels apply to whole texts, with no warning onset; some entries are ambiguous
without more context. Report these scores separately from timed call detection.

License: **CC BY-NC-ND 4.0**. The archive is used locally for non-commercial research
evaluation, never for training or redistribution. It stays in the ignored
`evaluation/external/` directory; reports contain IDs/scores rather than source text.

```sh
mkdir -p evaluation/external
curl -L --fail 'https://www.kaggle.com/api/v1/datasets/download/teeconnie/scam-and-non-scam-call-conversation-dataset?datasetVersionNumber=1' -o evaluation/external/calls.zip
uv run python -m ml.evaluate_external
```

The script verifies the pinned archive hash before evaluating. Synthetic and
source-labelled test scores do not establish real-world accuracy.
