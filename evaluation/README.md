# Evaluation

The active MiniLM classifier is a hackathon prototype. It still produces false
alarms on security advice and reported scams. Scores are not calibrated probabilities.
All local text cases are synthetic and assistant-labelled; both supplied recordings
are synthetic voices. These are now known regression cases, not untouched tests.

## Run

```sh
uv run python evaluate.py                       # Call, behavior and wording checks
uv run python evaluate_audio.py                 # Real Whisper on both supplied MP3s
uv run python evaluate_external.py              # External corpus, downloaded below
uv run python evaluate.py --model models/candidate
```

The three scripts write `results.json`, `audio_results.json` and
`external_results.json`, including model/data hashes. Candidate evaluation writes
inside the candidate directory. No evaluation command changes model weights.

## Cases and measurements

- The `test` split in `data/scam/authored.jsonl` contains 48 calls.
- `fresh_calls.jsonl` contains 80 further calls in 40 paired scenarios.
- `regressions.jsonl` contains the two reported bank/SSA conversations.
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
uv run python evaluate_external.py
```

The script verifies the pinned archive hash before evaluating. Synthetic and
source-labelled test scores do not establish real-world accuracy.
