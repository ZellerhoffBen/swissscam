# Local scam classifier

Fine-tuned from [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache 2.0.
The original checkpoint comes from the Sentence Transformers project.
This repository changes its weights by supervised fine-tuning for binary call warnings.

`metadata.json` records the training recipe, checkpoint, threshold and weight hash.
Class 0 means no warning warranted by the observed text; class 1 means a warning.
Input is cumulative English text, limited to the most recent 512 tokens.

This is a hackathon prototype trained on synthetic examples. It still confuses
security advice and reported scams with harmful requests. See
[the evaluation](../../evaluation/README.md). Its scores are not
calibrated fraud probabilities, and lack of a warning does not establish safety.

No external evaluation text or user-supplied recording was used for fine-tuning.
