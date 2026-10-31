# Changelog

All application changes are recorded under a version before release. Versions follow SemVer; Python packaging uses the equivalent PEP 440 spelling.

## Unreleased

No changes yet.

## [0.1.0-alpha.6] - 2026-10-31

### Added

- Highlight paraphrase changes with accessible word-choice menus, original-text restoration, manual editing, and restoration of the initial model result.
- Compare text in a bounded browser worker using locally served JsDiff 9.0.0. Suggestions and manual edits never resend text or trigger additional inference.
- Return bounded, optional code-point edit metadata from existing reviewed equivalences; discard malformed metadata while retaining valid text results.
- Autosave the latest edited result in its existing browser-history item, with legacy-history support and the existing combined storage limits.

### Changed

- Simplify the workspace in Indonesian and English; move technical explanations and processing details into collapsed FAQ answers and the privacy policy.
- Preserve the original NMT models, edit vocabulary, admission limits and quality-release gate. Production deployment remains separate from publishing images.
- Verify 177 local Python tests (one Linux-only test deferred to GitLab), 29 browser tests and eight JavaScript tests. All eighty real-model outputs match reviewed alpha.5 results; metadata ranges and alternatives pass validation. Remove all alpha.6 test containers/images and temporary files while preserving production and `scc-*` images.

## [0.1.0-alpha.5] - 2026-10-30

### Added

- Optional isolated CPU NMT service for Indonesian/English back-translation, a dedicated paraphrase workspace, explicit server consent, and browser-local history.
- Independent bounded admission, per-client ticket ownership, hard inference cancellation with idle confirmation, offline pinned models and checksums, and two-image GitLab verification.
- Add a dedicated capability rate bucket, bilingual consent/privacy/terms/discovery updates, measured real-model probes, and a source-bound forty-sample quality gate before tagged image publication.
- Add abbreviation-aware segmentation, bounded alternative decoding and an ordered-token edit filter. Reject changes outside a narrow reviewed equivalence vocabulary, preserve original segments and avoid counting whitespace changes as paraphrases.
- Verify 168 Python and 22 browser tests in isolated staging. Review the original 40 samples plus 40 additional synthetic holdout samples: zero observed critical changes and 80/80 language-acceptable results, including 68 retained inputs and 12 actual limited rewrites. Keep the failed eleven-error baseline for comparison; unchanged inputs are not reported as successful rewrites.
- Require both evaluation reports and actual rewrites in both languages before the quality gate passes. Real 5,000-character repeated-sentence jobs complete in approximately 30–36 seconds on two CPUs; timeout and disconnect still terminate inference.
- Remove completed alpha.4/alpha.5 staging containers, images and build intermediates, socket volumes, the isolated network, expiry timers and temporary directories. Verify production NoMark keeps its original container/image, start time and zero restarts; no global Docker prune is used.
- Correct incomplete cleanup: identify three randomly named exited containers from failed dependency builds, remove eight additional unused NoMark image roots and their remaining untagged ancestors, and verify no exited containers or NoMark dangling images remain. Preserve unrelated application images, including a dangling image used by a running production container.
- Paraphrasing remains limited and requires review. It does not detect or guarantee removal of SynthID or other statistical watermarks. Passing the quality gate does not publish alpha.5, promote latest or change production. Existing security limitations remain open.

## [0.1.0-alpha.4] - 2026-10-30

### Security hardening

- Reject JSON nesting that exceeds the parser recursion limit with a controlled 400 response.
- Retain the socket address when a trusted proxy supplies an empty or invalid final X-Forwarded-For value.
- Anchor expired-job removal to a no-follow directory descriptor and Python's symlink-resistant rmtree implementation.
- Load the pinned upstream modules in a private namespace with scoped sibling imports instead of modifying global sys.path.
- Limit public health output to readiness and application version; remove tool inventory and capacity configuration.
- Use the upstream atomic, symlink-safe writer for cleaned image output.
- Verify Linux worker termination through procfs so regression tests also run in the minimal production runtime without installing procps.
- Add offline Pyodide smoke checks and document the dedicated, resource-limited staging environment; no production promotion is included.
- Place upstream and native PDF temporary storage inside the parent-owned job directory so forced termination also removes extracted attachments. Add real qpdf timeout/cancellation regressions and kernel memory/file-limit checks; the Linux Python suite now passes 110 tests.
- Make browser test Python/Chromium paths configurable for offline Linux staging, and document audit evidence, selected OWASP control mapping, Cloudflare deployment checks and unresolved work in SECURITY.md and the security verification record.
- Verify all 19 browser tests and run bounded observations for reservation fairness, attachment storage and HTML scanning; retain their unresolved security conclusions explicitly.

These changes harden the reviewed paths; they do not establish that every earlier audit hypothesis was exploitable or resolved. Existing alpha limitations remain applicable.


## [0.1.0-alpha.3] - 2026-10-30

### Added

- SVG metadata cleaning and LaTeX source cleaning in the browser, without rendering SVG or compiling LaTeX. HTML and SVG cleaning is not script sanitization.
- Browser-local metadata cleaning for PNG, JPEG, WebP, GIF, BMP, TIFF, AVIF, HEIC/HEIF, WAV, MP3, FLAC, M4A, MP4, MOV, and M4V using deterministic upstream functions.
- Document, image, audio, and video selectors above the upload area, with format-specific scope and processing-location guidance in Indonesian and English.
- Media signature and container-boundary validation; before/after reports, downloads, and history use the existing workflow.

### Changed

- Rename the Documents workspace to Files and update privacy, discovery documents, and format documentation.
- Report partial completion when native FLAC metadata or legacy MP3 ID3v1 tags remain outside upstream coverage.
- No model hooks, external scoring tools, re-encoding, destructive audio transformations, or pixel watermark removal are enabled. Alpha security limitations remain unchanged.


## [0.1.0-alpha.2] - 2026-10-30

### Changed

- Publish a rolling `latest` image alias after the release image passes tests and container readiness checks, including alpha releases.
- Promote the existing registry manifest and verify its digest against the build artifact; do not rebuild during promotion.
- Document Portainer updates with `latest`, rollback using version tags, and the continuing alpha limitations.

### Known limitations

- Security and infrastructure limitations recorded for 0.1.0-alpha.1 still apply. `latest` does not imply a stable release.
- Portainer must pull and redeploy the image to apply an update; active processing can be interrupted.


## [0.1.0-alpha.1] - 2026-10-30

### Added

- MIT license for the original NoMark application code.

- FastAPI application using the pinned watermarks-remover Python functions directly.
- Browser-local text and non-PDF document processing with Pyodide and a Web Worker.
- PDF metadata processing with explicit permission and a pre-upload admission queue.
- Local IndexedDB history, copy/download actions, sequential file processing, cancellation, and reports.
- Indonesian and English interfaces, privacy policies, and terms of service.
- System, light, and dark themes; responsive and accessible controls.
- LAN development launcher, Docker Compose, and host Caddy configuration.
- Outlined NoMark logos, favicons, device icons, and a social sharing image.
- Localized server-rendered pages, canonical/hreflang metadata, structured data, visible FAQs, robots.txt, sitemap.xml, llms.txt, and llms-full.txt.
- Contribution, conduct, security, architecture, deployment, licensing, and SEO documentation.

### Security and privacy

- Isolated, time-limited server workers; temporary-file cleanup; request size limits; bounded concurrency and rate limiting.
- No automatic server fallback for browser processing, no analytics, and no user-result caching.

### Release engineering

- Theme-aware README banners using the original outlined logo and Avenir Next lettering.
- Version consistency checks, GitLab CI tests, container image publishing, and tagged releases.
- CI uses Node.js 22 and Python 3.11 to match the locked browser tooling requirements.
- Single-container deployment manifest and OCI image version/revision labels.

### Known alpha limitations

- The source security review did not validate runtime exploitation or production infrastructure. This release is not a security certification.
- PDF admission fairness, parser staging cleanup, aggregate attachment budgets, and repeated metadata scans require further validation and hardening.
- Locked Pydantic 2.14.1 has published advisories; the affected model configuration was not identified in NoMark. Dependency remediation remains pending.
- Cloudflare, DNS, HTTPS, and VPS settings have not been deployed or verified.
