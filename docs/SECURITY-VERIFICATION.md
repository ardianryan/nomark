# Security verification — 0.1.0-alpha.4

Review date: 30 October 2026. Status: **unreleased candidate; source audit completed, runtime and deployment coverage qualified below**.

## Scope and provenance

The earlier standard full source audit covered FastAPI middleware/routes, admission, jobs, browser workers/history/DOM sinks, active upstream cleaners including PDF attachments, native command interfaces, dependencies, and deployment/build configuration. Its immutable source manifest contained 393 files; 23 delegated review/verification calls covered 20 recorded units: 11 source-covered, five candidate units, and four blocked runtime/deployment units. It reported **zero confirmed exploits and four hypotheses needing validation**. This describes the audit workflow, not a successful penetration test or a clean bill of health.

That audit predates the current root commit and later patches. Follow-up verification reviews the dirty alpha.4 candidate based on root commit `82f876627e0ca33fc43d496445b08ace6f573de7`; it is not a new full audit of an immutable released commit. The upstream submodule remains pinned to `5c180932a00c793261177f79aee21db8929f3fe2`. The browser engine archive is `d7f0eea17a106c1c.zip`; a test compares its contents with the selected Python sources.

The detailed original audit artifacts are retained outside the repository. This public record summarizes their scope and limitations without exposing host configuration or user data. No native C/C++/WASM implementation, host kernel, Cloudflare account, repository permission settings, or unrelated production application is covered by the source review.

## Verification checklist

Only completed checks are checked. See [Verification](VERIFICATION.md) for current suite results and [Staging](STAGING.md) for limits and commands.

- [x] Hidden Unicode cleaning, valid emoji/script preservation, and unchanged ordinary text.
- [x] All accepted document/media fixture groups; malformed, encrypted, truncated, mismatched and oversized input rejection.
- [x] Actual streamed-body limit independent of Content-Length; one file per request; admission before multipart parsing.
- [x] Origin rejection, request limiting, forwarded-address fallback/canonicalization, queue capacity, expiry, cancellation and single-use capability tickets.
- [x] Deeply nested JSON returns controlled 400 and releases capacity.
- [x] Symlink-resistant stale-job deletion, including a simulated swap during deletion and a symlinked work root.
- [x] Private upstream import namespace, sibling import resolution, no global sys.path mutation, and refusal of a symlink image destination.
- [x] Minimal readiness output and no-store response behavior.
- [x] Synthetic worker timeout/cancellation kills descendants and removes job directories.
- [x] Linux worker kernel limits reject an 800 MiB allocation and a 257 MiB file truncate; capacity and scratch recover afterward.
- [x] Actual qpdf extraction interrupted by timeout and cancellation leaves no extracted attachment in parent-owned job storage.
- [x] Offline Pyodide executes the selected cleaner bundle for text, PNG and Markdown without upstream services or AI credentials.
- [x] Synthetic native PDF request through the isolated staging application, with no remaining job/helper directories after success.
- [x] Full Playwright suite: 19 passing tests, including local processing, PDF consent, history, accessibility checks, languages and themes.
- [x] Bounded reservation, attachment-storage and HTML-scanner probes executed; limitations and observed results recorded in Verification.

## OWASP mapping

This is a **selected-control topic mapping**, using [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0) and the [Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/). It is not a requirement-by-requirement ASVS assessment. Requirement IDs and compliance levels are deliberately not asserted without a complete applicability matrix and evidence for each requirement.

| Security topic | Implemented controls and tests | Coverage and remaining limits |
| --- | --- | --- |
| Input validation and API parsing | `tests/test_api.py`: unsafe uploads, streamed body limits, multiple files, paste limits; `tests/test_security_hardening.py`: recursive JSON | Regression evidence for the listed fixtures. Arbitrary parser inputs are not exhaustively covered. |
| File handling and traversal | Fixed job filenames, bounded ZIP handling; media signature/boundary tests in `tests/test_media.py`; atomic writer and descriptor-relative deletion tests | No archive-member-selected extraction paths. Real native parser internals are outside source review. |
| Injection and unsafe content | HTML returned as data (`test_html_is_returned_as_data_and_cannot_execute`), SVG external-entity rejection, argv-based native command calls reviewed in source | Metadata cleaning is not HTML/SVG sanitization. Raw uploads are never rendered as active site markup. XML encoding edge cases and native parser safety need separate assessment. |
| Browser security and data protection | CSP, same-origin assets, framing prohibition, no-referrer, no-store processing responses; browser-local engine/history and explicit PDF consent | Browser tests check local processing, storage failure, history deletion and consent. A shared browser profile can read its own local history; no account isolation is promised. |
| Resource abuse and business logic | FIFO capacity, expiring tickets, pre-body admission, 60-second jobs, Linux limits; `tests/test_admission.py`, `tests/test_jobs.py` | Limits reduce individual job impact. Per-requester reservation fairness, aggregate attachment storage, and parser work amplification require the targeted checks below. |
| Access control | Opaque single-use queue capabilities, unrelated/waiting ticket rejection | Public processing is intentional. No account authentication, password recovery, sessions, tenant database or administrative API exists; those ASVS topics are not implemented. Bearer queue capabilities still require protection. |
| Error handling and configuration | Controlled API errors, minimal health response, no upload-content logging; non-root/read-only/capability/resource settings tested in isolated staging | Staging enforcement does not establish the effective production configuration or incident response coverage. |
| Dependency and build integrity | Pinned upstream, versioned Python lock, source/bundle equivalence test, digest checks in `tests/test_image_promotion.py` | Pydantic advisory follow-up and an updated scan/SBOM of the exact release image remain open. No blanket no-CVE claim. |

## Audit hypotheses and follow-up

These originated as source-grounded hypotheses, with no assigned severity. Tests that prove a local condition are not automatically evidence of a shared-service exploit.

| Item | Current disposition | Required evidence before closure |
| --- | --- | --- |
| Renewable reservations and fairness | Open. The bounded model reproduced idle occupied capacity and recovery. | Still needs an independent competing-client schedule, effective HTTP identity/rate controls and recovery under replenishment. Do not load-test shared production. |
| PDF helper staging after forced termination | Addressed for the tested qpdf extraction path: worker TMPDIR and Python tempfile root now belong to the parent-owned job directory. | Timeout and cancellation both verified containment/removal. Other native temporary-file conventions and host crashes are not exhaustively covered. |
| Aggregate PDF attachment staging | Open. A real four-attachment fixture demonstrated independent per-file accounting with a reduced test cap. | No production aggregate budget or storage-exhaustion effect established; still needs a bounded production-limit assessment and budget design. |
| Repeated scanner suffix work | Open. Three increasing accepted HTML fixtures completed in the bounded probe. | No complexity bound or shared-service availability effect established. Broader HTML/SVG/LaTeX cases and recovery remain unverified. |

Additional open work:

- [ ] Revalidate and remediate the Pydantic 2.14.1 advisory observation in the lock, including compatible core and regression tests. The prior review identified [GHSA-qpmf-fgh3-ff25](https://github.com/pydantic/pydantic/security/advisories/GHSA-qpmf-fgh3-ff25) and [GHSA-3r8g-cqwr-jr29](https://github.com/pydantic/pydantic/security/advisories/GHSA-3r8g-cqwr-jr29). Current raw-Request processing does not demonstrate exploitation of the affected model configurations.
- [ ] Obtain an SBOM and current vulnerability scan of the exact release image digest, including Debian security revisions of native tools. A tool version banner is insufficient.
- [ ] Verify production proxy hops, narrowly trusted peer CIDRs, public HTTPS and origin-bypass restrictions with owner-observed configuration.
- [ ] Complete a requirement-level ASVS applicability/evidence matrix before making any ASVS level claim.

## Cloudflare control mapping

Cloudflare documentation guides deployment controls; it is not an application certification. No Cloudflare account was inspected or changed. The following checks **remain unchecked** until owner-controlled deployment evidence exists.

| Deployment control | Application support / proposed check | Status |
| --- | --- | --- |
| [Full (strict) TLS](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/) | Validate the origin certificate and HTTPS chain, hostname and expiry | Not verified on production |
| [Origin authentication](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/) and bypass restriction | Inspect ingress/firewall or separately reviewed Tunnel configuration; preserve administration and certificate renewal | Not verified on production |
| [Managed WAF / OWASP ruleset](https://developers.cloudflare.com/waf/managed-rules/reference/owasp-core-ruleset/) | Check account entitlement, active rules, body-inspection limits and benign PDF false positives | Not configured or validated by this work |
| [Rate limiting](https://developers.cloudflare.com/waf/rate-limiting-rules/) | Scope to processing/reservation POST routes; preserve queue polling; verify real client identity and suitable API errors | Origin limits tested; edge settings unverified |
| [Cache rules](https://developers.cloudflare.com/cache/how-to/cache-rules/settings/) | Bypass `/api/*` and `/health`; cache only public versioned engine/runtime assets | Origin cache headers tested; edge rules unverified |

WAF filtering does not replace file validation, native parser updates, aggregate storage budgets or correct temporary-file ownership. Plan limits and rule behavior must be checked against the actual account before deployment changes.

## Reproduction and maintenance

Run only synthetic fixtures inside the isolated environment described in [Staging](STAGING.md). No production mounts, credentials, Docker socket or external network are exposed to target code. Browser test tooling accepts `NOMARK_TEST_PYTHON` and `NOMARK_TEST_CHROMIUM` to reuse locally available runtimes without fetching dependencies. Changes to runtime code require rerunning the affected tests; record results under the candidate version in [Changelog](../CHANGELOG.md). Do not replace an outstanding item with a checked box based solely on an unrelated green suite.
