# Architecture

## Runtime

FastAPI serves HTML, static assets, public policies, discovery documents, and server processing routes from one origin. Alpine.js CSP manages the interface. There is no upstream HTTP service or API bridge: NoMark imports the pinned upstream Python cleaners directly.

Pasted text and supported non-PDF files run the same Python core in a Pyodide Web Worker. The runtime and a fingerprinted archive of required Python modules are served locally. The worker starts on demand, times out after 90 seconds, and terminates after two minutes idle. A local failure does not trigger a server upload.

PDFs use native ExifTool, qpdf, and Ghostscript in an isolated Python process. The browser requests admission before uploading. The response includes the cleaned file as base64 and a report; the server exposes no persistent result URL.

## Data boundaries

Browser IndexedDB stores up to 20 history entries or 100 MiB, including originals, results, reports, and timing. Oldest entries are removed on overflow. Storage errors leave the current result available. Language and theme preferences use localStorage. No server history database, account, analytics, or cross-device synchronization is configured.

The website sends only PDFs for server cleaning, following explicit permission. Direct compatibility API calls can send other supported formats; those contents are processed on the server. Policies distinguish these paths.

## Server admission and workers

The admission controller has two processing slots and eight waiting tickets. It holds only random tokens and expiration times in process memory. Waiting files stay in the browser. Waiting tickets expire after 120 seconds; unclaimed ready slots after 20 seconds. Cancellation releases reservations. A slot is claimed before request-body parsing; a full server rejects direct processing requests before reading multipart contents.

Uploads have a 30-second timeout. Jobs have a 60-second timeout. Disconnects and cancellation stop the job, including its process group. Temporary directories are removed after success or failure. Stale job directories older than five minutes are swept at startup and every five seconds while running.

Linux workers limit address space to 768 MiB and individual output files to 256 MiB. The Compose service limits total memory to 2 GiB, CPU to two cores, and processes to 128. The container runs without root on a read-only filesystem with memory-backed `/tmp`.

The request limiter counts ticket creation and processing calls: 20 per IP per minute. Queue polling and cancellation are exempt. IP keys are temporary keyed hashes, periodically removed. Trusted forwarded headers are accepted only from configured proxy networks.

**One Uvicorn worker and one application replica are required by this in-memory coordination model.** Multiple replicas require shared admission and rate limiting before deployment.

## Processing API

| Endpoint | Input | Output |
| --- | --- | --- |
| `POST /api/queue` | No document content | Random ticket and queue status |
| `GET /api/queue` | `Authorization: Bearer <token>` | Ready/waiting status |
| `DELETE /api/queue` | Same authorization header | Cancellation |
| `POST /api/file/process` | Multipart `file`; optional `X-NoMark-Reservation` | Base64 file and report |
| `POST /api/text/process` | JSON `{"text":"..."}` | Server text result and report |
| `GET /health` | None | Minimal application/engine/PDF readiness and version |

Processing responses use `Cache-Control: no-store`. Results identify `processed_by: browser` or `server` and status `unchanged`, `cleaned`, or `partial`. Errors use `{"ok":false,"error":"code"}`. Server routes also validate format, size, encryption, unsafe names, and malformed input. Uploaded HTML is never rendered as active page content.

## Public content and assets

`static/translations.json` is the shared English/Indonesian dictionary. The server renders literal translations into `/en` and `/id`; the generated `static/copy.js` supports client interactions. The root page initially renders English and lets the browser select a saved or preferred language; explicit language URLs take precedence. Switching language preserves current input and changes the URL without submitting content.

`nomark/seo.py` supplies canonical/hreflang metadata, structured data, the sitemap, and public LLM context. `nomark/policies.py` supplies both policy translations. No user content is inserted into these discovery documents.

`static/brand/` contains committed SVG masters and generated raster exports. Versioned Pyodide and fingerprinted engine assets support immutable caching and precompressed gzip delivery. Main assets revalidate. See [SEO](SEO.md) and [Deployment](DEPLOYMENT.md).

## Media metadata (0.1.0-alpha.3)

The Files workspace adds image, audio, and video format selectors. All supported media run in the browser worker through deterministic `image_meta` strip functions and `av_meta.clean_av`. No optional scorer, model hook, external command, pixel processing, waveform transformation, or transcoding is called. Native-server compatibility endpoints retain their previous document allowlist; media are browser-only in the website and are not added to that API.

Validation checks filename/signature agreement, top-level boundaries, required media sections, and PNG checksums before cleaning. These are metadata/container checks, not full codec decoding or antivirus scanning. Original compressed image/audio/video payloads are retained; removing orientation or color metadata can still change image appearance. The UI explains these limits and the shared 20 MiB limit.

FLAC support follows upstream: leading ID3v2 tags only. Native FLAC application/comment/picture blocks and MP3 ID3v1 tags can remain; NoMark reports partial completion when these are present.

## Import and housekeeping boundaries (0.1.0-alpha.4)

`nomark.upstream` loads the five pinned upstream modules from explicit file paths under a private namespace. Its module-local import resolver binds upstream sibling imports to the same namespace; application-wide `sys.path` and unrelated modules named `common` or `image_meta` are left unchanged. Upstream source files and cleaning algorithms remain unchanged.

Expired-job housekeeping opens the work root with `O_NOFOLLOW` and uses descriptor-relative stat and symlink-resistant `shutil.rmtree`. It skips cleanup on platforms without that implementation. A path-resolution containment check alone would leave a check/use race. The old rmtree implementation already included symlink protections; these changes strengthen anchoring rather than establishing a previously demonstrated escape.

The public `/health` payload retains `ok`, `version`, `engine_available`, and `pdf_ready` so the browser and container health checks remain functional. Tool inventory and configured capacities are omitted. Socket-loopback checks are not an access-control mechanism behind a reverse proxy; external requests may arrive over the same loopback connection.

Each server worker sets Python's temporary-directory root and native tools' `TMPDIR` to its parent-owned job directory. Upstream attachment/Ghostscript staging therefore shares the job's lifetime: parent cleanup removes it after success, failure, timeout or cancellation. Real qpdf extraction regression tests cover timeout and cancellation at an instrumented extraction checkpoint. Files written by a native tool outside its configured temporary root and host crashes require separate assessment.
