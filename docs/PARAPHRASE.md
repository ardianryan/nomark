# Optional paraphrasing — 0.1.0-alpha.6

This feature back-translates Indonesian through English, or English through Indonesian, with locally operated OPUS-MT models. It does not detect SynthID, decrypt text, guarantee watermark removal, or provide a semantic-equivalence score. The browser cleaning engine remains deterministic and model-free.

## Enable the optional service

From the repository root, build and run with:

```sh
docker compose --project-directory . -f compose.yaml -f deploy/compose.paraphrase.yaml up -d --build
```

The same override can accompany `deploy/compose.release.yaml` after the corresponding images have actually been published. The base single-container configuration does not enable NMT. No hard readiness dependency is added to the main application.

The NMT service has no published port and joins only an internal network shared with the application. Runtime uses read-only model files; build-time downloads are pinned by model revision and SHA-256. The conversion build uses hash-locked CPU PyTorch and CTranslate2; runtime excludes PyTorch. Models are Apache-2.0, while original NoMark code remains MIT.

## Request lifecycle

The separate Paraphrase tab requires explicit consent. It reserves capacity before sending text: one active job, two waiting tickets, one outstanding ticket per temporary client identity. Five reservation/processing POST requests per minute share a dedicated rate bucket in addition to the general limit. Polling/cancellation are exempt. Shared/NAT connections share the identity limit.

Ready tickets expire after 20 seconds; waiting tickets after 180 seconds. Tickets are owner-bound and single-use. This coordination assumes one main application process/replica and one NMT service replica. It is separate from PDF admission.

Public endpoints are `/api/paraphrase/capabilities`, POST/GET/DELETE `/api/paraphrase/queue`, and POST `/api/text/paraphrase`. Processing accepts JSON `{ "text": "...", "language": "id" }` and an `X-NoMark-Reservation` header. Queue polling/cancellation use bearer tickets. Text is limited to 5,000 Unicode code points and bodies to 64 KiB. Responses identify server processing, language, elapsed time, warnings and `paraphrased`, `unchanged` or `partial` status. Response bodies are not cached.

An inference subprocess loads both int8 models lazily and reuses them serially. It is killed on timeout, cancellation or disconnect, and unloaded after five idle minutes. Inference includes cold loading in its 75-second budget; interservice/browser limits are 85/90 seconds, below Caddy's existing 100-second header timeout. Process lifetime management does not promise forensic memory erasure.

Paragraph/line boundaries and list prefixes are preserved. Abbreviations stay with their sentences. Protected tokens (URLs, email addresses and tokens containing digits) are compared before/after each segment. The decoder considers up to four forward candidates and four return candidates per forward candidate, stopping once it finds a permitted rewrite.

This candidate uses **constrained surface edits**, not unrestricted paraphrasing. The ordered token sequence, case and punctuation must match after normalizing a small, explicit vocabulary of reviewed equivalences, such as `memerlukan`/`membutuhkan` or `cannot`/`can't`. It does not discard unknown words, stem singular/plural nouns, ignore negation or accept a bag-of-words similarity score. Candidate changes outside those rules, empty or capped output, and overlong segments preserve the original segment and report partial completion. Whitespace-only differences do not count as rewrites. This substantially limits coverage: many requests return the original text. It is not a semantic proof, an EYD V guarantee or a way to force every text to change. Review results before use.

Inputs/outputs are not written as server history. IndexedDB retains them under the existing 20-item/100-MiB combined limit.

## Evaluation and release gate

`docs/nmt-evaluation.json` contains the original forty explicitly synthetic samples, twenty per language. A second forty-sample [holdout](nmt-holdout.json) was fixed before inspecting its outputs. The [failed baseline](evaluations/alpha5-baseline.json) remains available, including all eleven original critical errors. The reviewed alpha.5 reports are archived separately. `scripts/evaluate_nmt.py` collects real outputs without marking them reviewed. Review compares facts, negation, names, quantities, paragraphs and language quality. It does not measure SynthID removal.

`python scripts/nmt_quality_gate.py` applies the existing criteria to **both** forty-sample reports: all reviews completed, no critical factual errors, at least 32 acceptable language results, actual non-whitespace rewrites in both languages, and exact model/source fingerprints. Returning every input unchanged cannot pass. GitLab blocks tagged builds and latest promotion until that gate passes. A branch can build SHA images for isolated staging even if language evaluation fails. Review evidence must be refreshed after model/tokenizer changes.

GitLab builds separate main and `/nmt` images. Both smoke stages must finish before release promotion; the promotion script verifies each tested manifest digest. Registry updates are sequential, not an atomic two-image transaction: use matching explicit version tags for coordinated rollback if publication fails partway through. There is no SSH deployment or host-wide image pruning.

## Browser editing and suggestions

The result highlights changed words or phrases. Each highlight opens an accessible dialog with available replacements and an original-text restoration action. The service returns optional `edits` metadata containing an ID, input/output start and end offsets, before/after text and alternatives. Offsets count Unicode code points. Metadata is bounded to 256 changes and three alternatives per change, checked against the full segment, and generated without additional inference or a larger edit vocabulary. The main application discards invalid optional metadata while preserving a valid text result.

JsDiff 9.0.0 runs in a same-origin worker with a 150 ms comparison budget, a maximum edit distance of 2,000 tokens and a one-second worker deadline. Verified phrase boundaries anchor comparison so multiword suggestions stay together. A failed comparison falls back to plain, editable text. Rendering uses text nodes; uploaded or pasted markup is not executed. Suggestions and manual editing make no server requests.

Manual editing uses a plain textarea with a 50,000-code-point limit. Finishing an edit remaps untouched suggestions and invalidates suggestions overlapping the edited spans. Copy/download use the current text, excluding deletion markers. Reset restores the initial model output. Manual changes are not model-validated or evidence of watermark removal.

The initial model text, current output and editor state share one IndexedDB item. Drafts autosave after 500 ms; completion, export and history actions flush pending saves. Input/language snapshots remain attached to the original processing job. All editor metadata is included in the existing 20-item/100-MiB accounting. Legacy items gain local highlights and manual editing without a model request; server suggestions require their optional metadata.

Technical explanations now appear in closed FAQ answers and the privacy policy. The workspace retains concise consent and a short review reminder in both languages.

## Verification record

Runtime and browser results, model measurements, sample review outcome and staging access are recorded after testing. Existing security hypotheses and production TLS/Cloudflare/image-scan requirements remain open in SECURITY.md; adding NMT does not close them.

### Recorded staging outcome

- Real-model smoke: passed for both languages, with the runtime network internal-only.
- Baseline: eleven critical meaning/fact changes and 29/40 acceptable language outputs (72.5%). Examples included an instruction to keep the original schedule becoming a rescheduling instruction, and `She` becoming `He`.
- Revised pipeline: **quality gate passed**, with zero observed critical changes and 40/40 language-acceptable results in each report. Of 80 results, 12 contain actual limited rewrites and 68 equal the source. The 100% language acceptance includes preserved inputs; it is **not** a 100% paraphrasing success rate. All original eleven critical changes are rejected or avoided. The translation weights were not retrained; the improvement comes from candidate selection and original-segment fallback.
- Alpha.6 metadata regression: all eighty text outputs exactly match the reviewed alpha.5 outputs, and all returned edit ranges and alternatives passed validation. Manual user edits are excluded from model-quality claims.
- Runtime: alpha.6 5,000-character repeated-sentence requests took 29,339 ms (English) and 35,374 ms (Indonesian) on two CPUs. The real disconnect and shortened-deadline probes killed inference. See [measurements](nmt-measurements.json) for exact values and [Verification](VERIFICATION.md) for measurement scope. More candidates cost additional CPU time.
- Review was agent-assisted on synthetic examples, not an independent linguistic certification or a measurement of SynthID detectability.
- Alpha.6 model tests used a separate offline NMT container without a published host port; browser tests used a separate local development process. Temporary staging resources were removed after verification. Passing the local quality gate does not itself publish a release, promote `latest` or change production.
