# Verification

## 0.1.0-alpha.6 editor verification

Verified on 31 October 2026 before publication. The local Python suite passed **177 tests**, with one Linux-only resource-limit test deferred to GitLab; the existing framework TestClient deprecation warning remains. **29 browser tests** and **8 JavaScript unit tests** passed. A focused seven-test editor rerun additionally verified the final popup-position fix without a page-scroll jump. GitLab must pass the complete Linux suite, both image builds and runtime smoke checks before release promotion.

Coverage includes code-point metadata validation and malformed-metadata fallback; replacement/deletion and shared-word boundaries; Unicode, emoji and line endings; suggestion changes after length shifts; original/model restoration; manual editing with unaffected suggestions retained; draft autosave, reload and single-entry history; history deletion without resurrection; clipboard fallback/export; literal markup rendering; storage/worker failures; length limits; keyboard/dialog accessibility; language and dark/light/mobile behavior. Browser clipboard calls are captured in test doubles so testing does not overwrite the operator's clipboard. Comparison work is bounded and no local editing action sends text back to the model.

All eighty real-model outputs matched the reviewed alpha.5 outputs exactly. The previous agent-assisted language assessments are retained on that explicit basis: zero observed critical changes, twelve limited rewrites and sixty-eight preserved inputs. Every returned metadata range and alternative was checked. The current source-bound reports are [original samples](nmt-evaluation.json) and [holdout](nmt-holdout.json); the reviewed alpha.5 reports remain archived.

The isolated NMT source-overlay test used the published alpha.5 runtime with unchanged pinned models/dependencies, two CPUs, 2 GiB RAM and no network. Repeated-sentence 5,000-character requests took 29,339 ms (English) and 35,374 ms (Indonesian). A real disconnect and a shortened 50 ms warmed-inference deadline stopped model processes. The observed memory peak was 684,539,904 bytes including a second timeout-probe model process. These fixtures do not establish worst-case latency or steady-state memory. See [measurements](nmt-measurements.json).

Desktop light and mobile dark views were inspected in two bounded capture rounds. The existing typography, logo, mint/peach surfaces and system theme remain. The small dialog separates word choices without changing the editor layout; underlined phrase highlights do not rely on color alone. Keyboard, automated WCAG and mobile-overflow checks passed. Captures are development artifacts, not repository brand assets.

The [cleanup record](evaluations/alpha6-staging-cleanup.json) confirms removal of the staging container and both staging/build image records, the expiry timer and temporary directory. Existing production containers and all twelve preexisting `scc-*` images were preserved. No global prune or force deletion was used. Deployment remains a separate Portainer action.

## Historical verification: 0.1.0-alpha.5

The unreleased alpha.5 working tree is based on `3ed8d3916a9549ae00d5b5bd21414e542b9f0dba`. **168 Python tests passed** in offline Linux staging, including NMT queue/client/API/lifecycle tests, adversarial edit rejection and release-gate tests. **22 browser tests passed**, including consent, local waiting, copy/download/history, unavailability, cancellation and the existing cleaner regressions. One framework TestClient adapter deprecation warning remains. Both optional Compose combinations validate; GitLab YAML parses locally. The modified GitLab pipeline has not been executed remotely or published.

The NMT image built with checksum-pinned real models and dependencies, and both language smoke tests passed. The revised constrained pipeline **passes the local quality gate** on the original forty samples and an additional forty-sample holdout: zero observed critical changes, 80/80 language-acceptable results, **12 actual limited rewrites and 68 retained inputs**. The failed baseline is preserved. Retaining inputs contributes to language acceptance; it is not a successful paraphrase. This does not establish unrestricted rewriting quality or SynthID removal. See [Paraphrasing](PARAPHRASE.md), [sample review](nmt-evaluation.json), and the measurements below.

## Previously verified candidate: 0.1.0-alpha.4

Verified on 30 October 2026 in isolated Linux Docker containers on the owner-authorized staging host. This candidate is uncommitted and unreleased, based on root commit `82f876627e0ca33fc43d496445b08ace6f573de7`. See [Staging](STAGING.md) for containment and [Security verification](SECURITY-VERIFICATION.md) for OWASP/Cloudflare mapping and open work.

| Check | Result | Evidence |
| --- | --- | --- |
| Full Python suite | **110 passed**, no skips, one framework deprecation warning | `python -m pytest -o addopts= -q -p no:cacheprovider --basetemp=/tmp/pytest` |
| Full Playwright suite | **19 passed** in 1.1 minutes | `node node_modules/@playwright/test/cli.js test --reporter=dot --timeout=60000 --output=/tmp/test-results` |
| Offline browser engine | Passed | `tests/staging/wasm-check.mjs`: Pyodide private loader and text/PNG/Markdown cleaning |
| Staging HTTP processing | Passed | Minimal readiness, text, synthetic PDF; no job/helper staging remained after successful processing |
| Bounded audit observations | Completed, exit 0 | `tests/staging/security-probes.py`; observations do not certify controls |

### Security and functional coverage

- `tests/test_security_hardening.py`: nine regressions for recursive JSON, forwarded-address accounting, stale cleanup/symlink races, private upstream imports, atomic image output and minimal health.
- `tests/test_jobs.py`: successful/failed job cleanup; synthetic descendant termination; cancellation/capacity recovery; Linux kernel rejection of excess address-space allocation and file size. The real worker rejects an 800 MiB allocation under its 768 MiB address-space limit, and a 257 MiB truncate under its 256 MiB file limit.
- Two real-PDF attachment cases pause immediately after actual qpdf extraction, then trigger timeout or cancellation. They verify that extracted bytes are inside the parent-owned job directory and disappear after termination. This checks file lifetime under controlled timing; it is not an exploit demonstration.
- API/media tests cover supported formats, Unicode preservation, malformed/encrypted/mismatched input, paste/upload/streamed-body limits, one-file requests, origin checks, no-store responses and inactive HTML handling.
- Admission tests cover FIFO, two ready/eight waiting capacity, expiry, cancellation, single-use tickets and rejection before parsing file bodies. They do not establish per-requester fairness under replenishment.
- Browser suite covers copy/download, reload/history deletion, quota failure, twenty-item eviction, drag-and-drop, five-file limits, sequential processing, local processing without API uploads, explicit PDF consent, waiting without uploading, cancellation/retry and reservation release.
- Browser checks include 320–1440 px layouts, keyboard tabs, system/manual themes, stored language choice, Indonesian/English policies, localized SEO without JavaScript, metadata consistency and automated Axe WCAG A/AA checks. Automated accessibility checks do not replace a complete manual accessibility audit.
- Engine-bundle/source equivalence and mocked release-digest promotion protections are included. Registry publishing is not performed by tests.

### Warnings and failures resolved during verification

The first Linux browser attempt lacked a shared Chromium library. The next attempt passed 18 tests and exposed a remaining macOS-specific Python fixture path. The staging toolchain/library path and all three fixture invocations were corrected before the final rerun. Tests use existing cached runtimes; no dependency was downloaded. The Starlette test-client warning recommends migrating its deprecated httpx adapter; it does not fail the suite.

### Scope limits

These are candidate tests, not an ASVS certification, an exhaustive CVE scan, or proof of production safety. The browser toolchain is reused solely for testing and is not added to the application runtime image. The staging image overlays reviewed source on an already-cached application runtime; it does not reproduce a clean release Dockerfile/dependency build. The public HTTPS/CDN configuration, origin restrictions and Cloudflare account have not been validated.

The three remaining source hypotheses concern renewable reservation fairness, aggregate PDF attachment staging and repeated scanner work. Pydantic advisory remediation, an SBOM/current scan of the exact release image, and production proxy/TLS/edge verification remain open. Refer to the security verification checklist for specific closure evidence.

The fake-clock reservation probe allocated 16 tickets through second 60, saw 13 full-queue samples with zero active jobs, and recovered after release. It does not model an independent competing arrival schedule or prove a sustained HTTP denial of service. The real qpdf fixture retained four 32 KiB attachments, totaling 128 KiB under a **scaled 64 KiB per-attachment** limit; this demonstrates independent attachment accounting, not exhaustion at production limits. Three accepted HTML fixtures (1,562 / 3,098 / 6,170 bytes) completed in approximately 14 / 77 / 98 ms on the capped test container. These small, contention-sensitive measurements establish neither a complexity bound nor a shared outage. All scratch data disappeared when the containers stopped.

Production NoMark remains separate. No release tag, registry promotion, production restart, DNS change or Cloudflare rule change is part of this work.

## Earlier checks

Earlier alpha.3 verification reported 98 Python and 19 browser tests. Earlier milestones reported 67 Python and 17 browser tests. Those historical counts are superseded by the current candidate results above and must not be presented as current verification.

The original macOS host lacked Docker and could not enforce the memory sandbox required for this security follow-up. Those execution blockers were addressed by the dedicated offline Linux test containers. Physical-device LAN reachability, public social-preview fetchers and search-console registration remain separate deployment checks.

## 0.1.0-alpha.5 optional NMT follow-up

See [Paraphrasing](PARAPHRASE.md), the [original forty-sample evaluation](nmt-evaluation.json), [forty-sample holdout](evaluations/alpha5-holdout.json), [failed baseline](evaluations/alpha5-baseline.json) and [runtime measurements](nmt-measurements.json). This introduces a new boundary and is not covered by an implied ASVS certification from the alpha.4 source review. Both language smoke tests passed offline. The baseline had eleven critical errors and 29/40 language-acceptable outputs. Candidate selection now rejects edits outside an explicit ordered-token equivalence vocabulary and retains originals when necessary. All eighty final outputs were compared by the implementation agent: zero observed critical errors and 80/80 language-acceptable outputs, including twelve actual limited rewrites and sixty-eight exact retained inputs. The review is agent-assisted, synthetic and not independently certified. The gate additionally rejects reports containing no actual rewrites in either language; both source-bound reports must pass. No acceptance threshold was lowered and no failing original sample was removed.

At two CPUs, revised 5,000-character requests completed in 30,077 ms (English, unchanged) and 36,205 ms (Indonesian, partial with the source retained). These fixtures repeat sentences; they do not establish a worst-case processing time. Cold loading in a separate probe took 1,570 ms. Closing the real HTTP connection terminated the existing worker; an intentionally shortened 50 ms deadline terminated real warmed inference and recovered the runtime. The observed cgroup peak was 683,941,888 bytes, including simultaneous service and probe model processes; this is not an isolated steady-state request peak. Warm service memory was approximately 334 MiB; actual usage varies with input and tooling. The failed pipeline's earlier, faster measurements remain in [baseline measurements](evaluations/alpha5-baseline-measurements.json).

The staging service and test images ran separately from production, with no published NMT port. Public-application API checks confirmed both a rejected unsafe rewrite and an accepted limited rewrite through the real NMT service, with `Cache-Control: no-store`. Runtime dependencies/model downloads happened in the bounded build phase; application/model tests ran without outbound connectivity. Staging containers, images and temporary resources are removed after verification at the owner's request; the temporary localhost tunnel is not a permanent preview deployment. Production NoMark retained its original container/image IDs, start time and zero restarts throughout verification. No release, latest promotion or production deployment is included.
