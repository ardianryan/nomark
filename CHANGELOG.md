# Changelog

All application changes are recorded under a version before release. Versions follow SemVer; Python packaging uses the equivalent PEP 440 spelling.

## Unreleased

No changes yet.

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
- Single-container deployment manifest and OCI image version/revision labels.

### Known alpha limitations

- The source security review did not validate runtime exploitation or production infrastructure. This release is not a security certification.
- PDF admission fairness, parser staging cleanup, aggregate attachment budgets, and repeated metadata scans require further validation and hardening.
- Locked Pydantic 2.14.1 has published advisories; the affected model configuration was not identified in NoMark. Dependency remediation remains pending.
- Cloudflare, DNS, HTTPS, and VPS settings have not been deployed or verified.
