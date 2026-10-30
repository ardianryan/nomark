# Security policy

## Supported code

The current development branch is the maintained version. There are no published stable releases or long-term support branches yet.

## Report a vulnerability

Email **me@ardianryan.com** with the subject `NoMark security report`. Do not disclose an unpatched vulnerability in a public issue.

Please include the affected commit or deployment, reproduction steps, expected and actual behavior, and the potential impact. Use synthetic input and redact credentials, reservation tokens, private documents, and personal data. An encrypted reporting channel is not currently published; ask before sending particularly sensitive details.

Reports will be reviewed as availability permits. There is no guaranteed response time, bug bounty, or permission to test infrastructure belonging to others. Coordinate any public disclosure after the report has been assessed.

## Data and deployment boundaries

- The website processes text and non-PDF documents locally. PDFs require explicit consent before server upload. Direct processing API requests send content to the server.
- Uploaded documents are untrusted input. Workers use temporary directories, process isolation, timeouts, and Linux resource limits.
- The supplied container runs without root, uses a read-only filesystem and temporary memory storage, and exposes its host port on loopback.
- Queue admission and request limiting are in memory. Run one Uvicorn worker and one application replica until shared coordination is implemented.
- Configure HTTPS, trusted proxies, and host updates before public deployment. Never log user content or cache processing responses.

Operational details are in [Deployment](docs/DEPLOYMENT.md). Verification limits are recorded in [Verification](docs/VERIFICATION.md). These controls do not constitute a security certification.

## Audit status — 0.1.0-alpha.4

A full source-review workflow was completed on 30 October 2026. Follow-up testing of the **unreleased 0.1.0-alpha.4 candidate** uses dedicated, offline Linux containers beside the owner's production workloads. Production has not been promoted by this verification work.

The [security verification record](docs/SECURITY-VERIFICATION.md) identifies the reviewed scope, implemented tests, OWASP topic mapping, Cloudflare deployment checks, and outstanding work. The [staging record](docs/STAGING.md) describes the execution boundaries. A checked item means the stated check passed in that environment; it does not establish that every requirement in an OWASP category is satisfied.

- [x] Full source-review workflow completed, with explicit unresolved runtime/deployment scope.
- [x] Follow-up Linux suite: **110 passed**; complete browser suite: **19 passed**.
- [x] PDF attachment staging containment/removal verified under timeout and cancellation; real worker kernel memory/file limits verified.
- [x] Selected OWASP control mapping and Cloudflare deployment checklist documented with test references.
- [ ] Close reservation fairness, aggregate attachment storage and scanner-work hypotheses; bounded observations alone do not close them.
- [ ] Resolve dependency advisory follow-up, scan the exact release image, and validate production TLS/proxy/Cloudflare controls.

**No OWASP ASVS level, Cloudflare certification, absence of CVEs, or complete production penetration test is claimed.** The original source review had no confirmed exploit and four hypotheses requiring validation. Follow-up checks and their disposition are recorded separately so that passing regression tests cannot silently close an untested hypothesis. Deployed Cloudflare account settings, public TLS, origin restrictions, and production image vulnerability status remain unverified.
