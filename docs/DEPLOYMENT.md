# Deployment

## Topology

The supplied configuration uses **one Docker image and one application container**. It includes FastAPI/Uvicorn, static frontend assets, the Python cleaners, and the native PDF tools. Caddy runs on the VPS host and terminates HTTPS for `nomark.ardianryan.com`.

No Node.js runtime, database, Redis, external AI API, S3 bucket, or CDN service is needed. Server cleaning spawns bounded child processes inside the application container; these are not separate containers.

## Build and start

Initialize the pinned submodule before building; Docker does not fetch it automatically.

```sh
git submodule update --init --recursive
docker compose config
docker compose up --build -d
curl --fail http://127.0.0.1:8000/health
```

Confirm `ok`, `engine_available`, and `pdf_ready` are true. Review container logs without enabling content or access logging. The supplied command disables Uvicorn access logs.

The service binds the host port to `127.0.0.1:8000`. It runs as UID 10001 with a read-only root filesystem, a 512 MiB temporary memory filesystem, two CPUs, a 2 GiB memory limit, and a 128-process limit. Shutdown allows 95 seconds for active work. Do not increase Uvicorn workers or add replicas without shared coordination.

## HTTPS and DNS

Point the production hostname at the VPS. Merge `deploy/Caddyfile` into the host's existing Caddy configuration, validate it, and reload Caddy using the host's service manager. Do not overwrite unrelated hosted sites.

The configuration enables HTTPS, a 21 MB request limit, compression, and a 100-second upstream response-header timeout. It does not include a Caddy rate-limit plugin: the application applies admission and rate limits. HTTP redirects and certificates are handled by the host's Caddy installation.

`NOMARK_TRUSTED_PROXIES` is a comma-separated list of proxy CIDRs permitted to supply client forwarding headers. Compose uses Docker's common private bridge range; narrow it to the actual bridge or proxy address on the VPS. If a CDN is later placed in front of Caddy, configure its trusted proxy ranges in Caddy as well. Do not trust arbitrary forwarded headers.

Production canonical URLs are defined by `SITE` in `nomark/seo.py`. If the public domain changes, update this constant, the browser metadata URL in `static/app.js`, social artwork, README, and Caddy configuration together.

## Verification before public use

Check native PDF processing with a synthetic fixture, downloaded output readability, timeout/cancellation, queue admission, temporary cleanup, mobile UI, and policy links. Check `/robots.txt`, `/sitemap.xml`, `/llms.txt`, `/llms-full.txt`, `/favicon.ico`, and social image URLs over the public HTTPS origin after deployment.

The alpha.4 source overlay was built and tested in isolated Linux staging. Worker memory/file limits, termination and cleanup were exercised there; see [Verification](VERIFICATION.md). A fresh release Dockerfile/dependency build, the exact published image scan, and effective production ingress settings still require verification. Repository configuration alone does not publish the site or change DNS.

## Storage, CDN, and scaling

PDFs are transient and most content never leaves the browser. S3 is unnecessary for this request/response workflow. Adding a bucket would add copies, transfer, access control, and retention responsibilities without reducing PDF CPU consumption.

A CDN may cache **public versioned assets only**:

- `/static/vendor/pyodide/314.0.7/*` and `/static/vendor/engines/*`: public one-year immutable caching.
- Main JavaScript/CSS and the engine manifest: revalidate; do not force immutable caching.
- `/api/*` and `/health`: `no-store`; never cache user results or reservation responses.
- HTML pages: revalidate so changes to policies, translated content, and metadata reach users.

No external CDN or bucket has been provisioned. To scale beyond one process/VPS, introduce shared admission and rate limiting plus separate PDF workers. Private object storage with expiring signed URLs and automatic deletion is appropriate only if a future asynchronous workflow requires it. Update both privacy policies before changing storage or processing providers.

## Configuration

| Variable | Purpose |
| --- | --- |
| `NOMARK_TIMEOUT` | Server job timeout in seconds; default 60 |
| `NOMARK_WORKDIR` | Temporary work directory; Docker uses `/tmp/nomark-work` |
| `NOMARK_TRUSTED_PROXIES` | Comma-separated trusted proxy CIDRs |
| `WATERMARKS_MAX_INPUT_BYTES` | Upstream input limit; Docker sets 20 MiB |

Browser interface limits are intentionally fixed alongside server validation. Keep policy descriptions and tests synchronized if changing them.

## Optional NMT service (alpha.5)

The default deployment remains one container. The optional [paraphrase override](../deploy/compose.paraphrase.yaml) adds a private second container without making main readiness depend on it. Use `--project-directory .` from the repository root so build paths resolve correctly. Current model quality fails the release gate; keep it in isolated staging. See [Paraphrasing](PARAPHRASE.md).
