# NoMark NMT

Optional CPU-only Indonesian/English back-translation service for NoMark 0.1.0-alpha.5. It is a paraphraser, not a SynthID detector or a guaranteed watermark remover. Model output requires review.

The current pipeline permits only constrained surface edits. Multiple translation candidates are checked against an ordered-token signature with a small reviewed equivalence vocabulary; candidates changing other tokens or their order are rejected. Original segments are retained when no permitted candidate exists. Most evaluation inputs therefore remain unchanged. The original failed model outputs and the revised eighty-sample results are preserved in the main documentation; no model retraining or universal semantic guarantee is claimed.

The parent application owns one-active/two-waiting admission and one outstanding reservation per temporary client identity. This service independently serializes inference in a warm subprocess. Timeout, cancellation and client disconnect terminate that process; idle models are unloaded after five minutes. Run one instance of each service.

Models are converted to CTranslate2 int8 at build time from revisions and source checksums in `models.lock.json`. Runtime tokenizer/model files are hashed in `/models/checksums.json`. Runtime is offline; there is no provider API, training, input logging or server history. Native models can retain memory until their process exits; no forensic zeroization is promised.

Build with `docker build -t nomark-nmt:local nmt-service`. Use the optional Compose override described in the root deployment documentation. Do not publish the internal NMT port. It is intended exclusively for the isolated application network and has no public authentication layer.

The application code is MIT licensed. Both Helsinki-NLP OPUS-MT model cards declare Apache-2.0; `LICENSE.models` includes its terms. Model repositories: https://huggingface.co/Helsinki-NLP/opus-mt-en-id and https://huggingface.co/Helsinki-NLP/opus-mt-id-en.
