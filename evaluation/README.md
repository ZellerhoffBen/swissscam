# Evaluation guide

## The training recipe

`train.py` uses the recipe that won our initial validation comparison:
**75% training weight for authored text-so-far examples, 25% for public full calls**.
Within each group, warning and no-warning examples get equal total weight.
Identical prefixes are removed before training.

The initial comparison detected 19/20 validation scams with prefixes alone
(one premature warning and one legitimate call flagged), versus 20/20 with public
data included (no premature warnings or false alarms). That experiment is finished;
the code now trains only the winning recipe.

The model uses word/two-word TF-IDF features and logistic regression. Settings stay
fixed: sublinear term frequency, minimum document frequency 2, maximum 20,000
features, `C=4`, maximum 1,000 iterations. Only training text fits these components.

Validation chooses a threshold from 0.05 to 0.95, in steps of 0.05. It balances
correct scam warnings against quiet legitimate calls. Early warnings count against
the model; ties prefer fewer false/early alerts, shorter delays, then thresholds
closer to 0.5. The selected threshold is **0.70**, not a calibrated fraud probability.

## Results on the 40 test calls

| Measurement | Result |
| --- | ---: |
| Scam calls detected at/after the suspicious request | 19/20 |
| Scam calls missed | 1/20 |
| Scam calls warned before suspicious evidence | 0/20 |
| Legitimate calls with any warning | 0/20 |

Fourteen scams triggered at the evidence turn; five triggered one turn later.
A turn is an utterance, not seconds. The average delay among detected scams was
0.26 turns. An alert still counts even if a later score falls below the threshold.

The missed call is `local-test-test-police-coincollection-scam`: a fake official
requests a coin collection for safekeeping and asks the recipient to hide the visit.
Its final score is about 0.59. We did not lower the threshold after seeing this miss.

Separately, the fixed demo transcript also gets no warning despite asking for a
verification code. This known short-text miss is outside the test counts.

## What to trust, and what to improve

These are small synthetic samples: 20 related scenario pairs per evaluation split,
with shared author/style. Zero observed false alarms does not mean zero real-world
false alarms. There are no real recordings, transcription errors, accents or
word-level streaming tests. An unflagged call is not guaranteed safe.

The next useful work is independent human-written short scam/legitimate examples
and separate recordings. Reserve fresh test calls before further tuning; the
current test results are now known. The cleanup kept the training recipe and
predictions unchanged, rather than tuning against these results.

## Generated reports

- `validation_results.json`: threshold comparison and selected validation result.
- `test_results.json`: per-call outcomes and scores for the saved model.

Run `uv run python evaluate.py` to reproduce the test report. Model/data hashes
identify what was evaluated; an old report does not validate a newly trained model.
The root README has the complete prepare/train/check/evaluate commands.

References: scikit-learn's [TF-IDF](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html),
[logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
and [threshold selection](https://scikit-learn.org/stable/modules/classification_threshold.html).
