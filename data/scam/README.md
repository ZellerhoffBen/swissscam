# Training data

All examples are synthetic English text, authored and labelled by the assistant.
A negative label means no warning is justified by the text, not a verified caller.

| File | Contents |
| --- | --- |
| `authored.jsonl` | 272 training, 48 validation and 48 test calls |
| `behaviors.jsonl` | 28 training, eight validation and 12 test pairs |
| `audit.json` | Generated counts, overlap checks and source hashes |

Each JSONL line is one example. Calls contain spoken `turns`, a binary `label`,
and `warning_turn`: the first turn that warrants a warning, or null. `evidence`
quotes the harmful request. IDs, categories and evidence never enter the model.

Each scenario pairs a benign and a harmful continuation. Related variants stay
in the same split. Behavior pairs cover direct requests, negations, quoted scams,
mixed safety advice and routine verification.

`prepare_data.py` loads these files directly; there are no generated split copies.
It checks labels, matched pairs, duplicate texts and cross-split overlap. Training
uses 1,088 unique call prefixes plus 56 behavior texts: 1,144 examples in total.
Prefixes before the harmful request remain negative.

```sh
uv run python prepare_data.py
```

The old public corpus and TF-IDF training path are no longer used. MiniLM's training
examples are unchanged by that removal. Additional calls in `evaluation/` and the
supplied recordings are evaluation-only, never training inputs.

These checks catch exact copies and large lexical overlaps, not every semantic
paraphrase. The small synthetic dataset does not establish real-world accuracy.
