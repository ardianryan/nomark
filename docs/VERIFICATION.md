# Verification

## Current candidate: 0.1.0-alpha.4

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
