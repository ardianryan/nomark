# Deployment

## Topology

The root development Compose file builds **two images and two containers**: the application and a private NMT service. The application image includes FastAPI/Uvicorn, static frontend assets, the Python cleaners, and the native PDF tools. Caddy runs on the VPS host and terminates HTTPS for `nomark.ardianryan.com`.

No Node.js runtime, database, Redis, external AI API, S3 bucket, or CDN service is needed. Server cleaning spawns bounded child processes inside the application container; these are not separate containers.

## Build and start

Initialize the pinned submodule before building; Docker does not fetch it automatically.

```sh
git submodule update --init --recursive
docker compose config
docker compose up --build -d
curl --fail http://127.0.0.1:8000/health
```

Confirm `ok` is true. The public health response intentionally omits internal tool details. Review container logs without enabling content or access logging. The supplied command disables Uvicorn access logs.

The service binds the host port to `127.0.0.1:8000`. It runs as UID 10001 with a read-only root filesystem, a 512 MiB temporary memory filesystem, two CPUs, a 2 GiB memory limit, and a 128-process limit. Shutdown allows 95 seconds for active work. Do not increase Uvicorn workers or add replicas without shared coordination.

## HTTPS and DNS

Point the production hostname at the VPS. Merge `deploy/Caddyfile` into the host's existing Caddy configuration, validate it, and reload Caddy using the host's service manager. Do not overwrite unrelated hosted sites.

The configuration enables HTTPS, a 21 MB request limit, compression, and a 100-second upstream response-header timeout. It does not include a Caddy rate-limit plugin: the application applies admission and rate limits. HTTP redirects and certificates are handled by the host's Caddy installation.

`NOMARK_TRUSTED_PROXIES` is a comma-separated list of proxy CIDRs permitted to supply client forwarding headers. Compose uses Docker's common private bridge range; narrow it to the actual bridge or proxy address on the VPS. If a CDN is later placed in front of Caddy, configure its trusted proxy ranges in Caddy as well. Do not trust arbitrary forwarded headers.

### Current Cloudflare and Nginx topology

On 2026-11-01, a connection from the Nginx proxy at `10.1.0.18` to `10.1.0.9:8120` was observed by the application container as `10.1.0.18`. The running stack trusted only `172.16.0.0/12`, so it ignored the forwarded address and shared a rate-limit bucket across clients arriving through that proxy. Nginx appended its peer to the forwarding chain and had no active Cloudflare real-IP directives. This diagnosis applies to that observed topology and should be rechecked if networking changes.

The Portainer example now trusts only `10.1.0.18/32`. Coordinate it with the Nginx configuration: install [the Cloudflare real-IP include](../deploy/nginx-cloudflare-realip.conf) inside the NoMark server block, then merge the header directives in [the NoMark proxy example](../deploy/nginx-nomark-proxy.conf) into its existing location. In particular, Nginx must replace `X-Forwarded-For` with the verified `$remote_addr`; appending the incoming chain makes the backend choose the wrong address. Only Cloudflare source ranges should be trusted for `CF-Connecting-IP`, and those ranges must be refreshed against [Cloudflare's published IP ranges](https://www.cloudflare.com/ips/) before use. Direct clients are identified by their socket address and cannot select their bucket by sending their own forwarded header.

Validate the complete live Nginx configuration with `nginx -t` before reloading; keep aaPanel's existing TLS, routes and unrelated sites. Update both Nginx and the Portainer stack as one deployment, verify separate real clients and a spoofed direct request, and retain the previous configuration for rollback. The repository examples do not alter production by themselves. Restrict direct origin access as appropriate for the host and verify the actual firewall and ingress configuration separately.

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

## Published images and Portainer (alpha.6)

Copy [the complete Portainer stack](../deploy/compose.portainer.yaml) into the stack editor. It uses both `latest` images, preserves the existing `nomark_temp` volume and `nomark_network`, and publishes the application on port 8120. Pull both images and redeploy to update; publishing a release does not redeploy production. Ensure port 8120 is available. Restrict ingress through the host firewall/reverse proxy as appropriate for the VPS.

The NMT service has no host port and only joins a dedicated internal network without outbound access. It has two CPUs, 2 GiB memory with no additional swap allowance, 64 processes/threads and 128 MiB temporary storage. Main readiness does not depend on NMT; local cleaning and PDF processing remain available if it is unavailable.

For an installation without NMT, use the versioned [release Compose](../deploy/compose.release.yaml). To add NMT to that installation, run from the repository root:

```sh
docker compose --project-directory . -f deploy/compose.release.yaml -f deploy/compose.paraphrase.yaml pull
docker compose --project-directory . -f deploy/compose.release.yaml -f deploy/compose.paraphrase.yaml up -d
```

The eighty reviewed model outputs pass the limited-edit quality gate; most inputs are retained unchanged. This does not establish general semantic accuracy or watermark removal. See [Paraphrasing](PARAPHRASE.md).
