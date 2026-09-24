# Data guide

All examples are **synthetic English conversations**, not real call recordings.
JSONL means one JSON record per line. Each call contains a list of spoken turns.

## Which files matter?

| File | Purpose |
| --- | --- |
| `source/scam-dialogue.csv` | Original public dataset: 1,600 calls. Do not edit. |
| `source/README.md`, `source/LICENSE` | Original dataset card and Apache 2.0 licence. |
| `authored.jsonl` | Our editable examples: 240 training, 40 validation and 40 test calls. |
| `train.jsonl` | Generated training data: 1,551 cleaned public calls + 240 additions. |
| `../../evaluation/validation.jsonl` | Generated calls used to choose the warning threshold. |
| `../../evaluation/test.jsonl` | Generated calls used to evaluate the finished model. |
| `audit.json` | Preparation checks, counts, excluded rows and file checksums. |

Edit `authored.jsonl`, then run `uv run python prepare_data.py` from the project
root. This rebuilds the generated files offline. The script checks the current
240/40/40 split sizes and topic balance; update those checks when expanding the set.
Training creates incomplete-conversation examples in memory, so there is no
separate prefix dataset to maintain.

## Where did the examples come from?

The public source is [BothBosu/scam-dialogue](https://huggingface.co/datasets/BothBosu/scam-dialogue),
generated with Llama 3 70B according to its dataset card, under Apache 2.0.
Keep the source card and licence when redistributing it or derived data.

Pinned revision: `321b961b5ae353e19ed479b960658dcd223d5e06`.
`prepare_data.py` checks the original CSV's SHA-256 before processing it.

Cleaning removes observed stage directions and extra whitespace. It excludes 49
rows: 41 possibly unfinished calls, three fake-number placeholders, three reviewed
dialogue inconsistencies and two duplicates. A 32-call sample was reviewed by the
assistant; the remaining public labels were not fully reviewed. All public calls
stay in training because their scripts are repetitive and their topics reveal labels.

Our additions cover family, emergency, police and bank impersonation (20 scam and
20 legitimate training calls each), plus support, refund, delivery and insurance
(10 scam and 10 legitimate training calls each).

Every authored scenario has a scam/legitimate pair with the same opening and
receiver reactions, but a different requested action. Each pair stays in one split.
Validation and test each contain 20 different pairs. The assistant wrote and
annotated these examples; they share a style and are not independent human labels.

Swiss scenario inspiration: [Swiss Crime Prevention](https://www.skppsc.ch/de/wp-content/uploads/sites/2/2019/12/telefonbetrug_dt.pdf),
[Solothurn police](https://so.ch/verwaltung/departement-des-innern/polizei/praevention/betrug/telefonbetrug/falsche-polizisten-schockanrufe-etc/)
and [BACS](https://www.bacs.admin.ch/en/call-fake-authorities).
These are original fictional dialogues, not recordings or endorsements from those organisations.

## How to read a call

- `turns`: the caller's and receiver's spoken text, in order.
- `text`: the combined spoken text, added during preparation. **Only this is model input.**
- `label`: `1` for a scam call, `0` when the example does not warrant a warning.
- `warning_turn`: the first suspicious turn, counted from 1. For authored legitimate
  calls it is null; for public calls it means **unknown**, including scams.
- `annotation`: `assistant_reviewed` for our additions or `source_call_label_only`
  for inherited public labels.
- `evidence`: exact suspicious wording and annotation tags. The binary model does
  not predict these tags or use them as input.
- `id`, `group_id`, `split`, `category`, `source`, `synthetic`: tracking information,
  never model input. `group_id` keeps related scenarios together.

A whole-call scam label does not make its greeting suspicious. `iter_prefixes()`
in `prepare_data.py` creates text-so-far examples only for annotated calls and labels
whether a warning is justified **at that turn**. The 240 authored training calls
produce 1,440 prefixes, or 960 distinct texts after duplicate removal.

Preparation checks annotation consistency, matching pairs, duplicate calls,
cross-split group overlap and large three-word-phrase overlap. These checks reduce
leakage but cannot prove semantic independence. See the
[evaluation guide](../../evaluation/README.md) for measured results and remaining gaps.
