# Visible image cleaning

NoMark alpha.8 adds an optional image service powered by the Apache-2.0 `remove-ai-watermarks` submodule at `b57ef6045cd7de525bc10546d4c1ce9f9fe151f7`. `nomark/image_client.py` and the media service are NoMark adapters. Upstream source is not patched.

## User flow

Images has its own tab and explicit server-upload permission. A single static PNG, JPEG or WebP is previewed locally. Reserving and polling a queue ticket sends no image. Only a ready ticket permits a multipart upload. Original and PNG result can be compared and downloaded. The Files tab keeps its existing browser-only image metadata cleaning, without automatic server fallback.

The output normalizes orientation and color to sRGB, preserves alpha, and strips user EXIF/text/location/provenance metadata. Color conversion and masked inpainting may alter details. PNG output avoids an additional lossy JPEG generation. `no_watermark` means no registered visible mark was recognized; it is not a watermark-free verdict. `partial` and `unvalidated` are retained rather than converted to success.

Limits: 20 MiB input, 8 megapixels, 8,192 pixels per side, 40 MiB output, 56 MiB JSON response. Reject animations, multipage images, 16-bit PNG, unsupported color modes/profiles, invalid files and format-extension mismatches. No silent resizing.

## Public contract

- `GET /api/media/capabilities`: availability, supported suffixes, byte/pixel/side limits.
- `POST /api/media/queue`: reserve a content-free, client-owned ticket.
- `GET /api/media/queue`: check state using `Authorization: Bearer <ticket>`.
- `DELETE /api/media/queue`: cancel the waiting or active job.
- `POST /api/image/process`: one `file` multipart part and `X-NoMark-Reservation` header.

The result follows the existing file-response pattern: `ok`, `kind: image`, `format: png`, `mime: image/png`, original and cleaned names, sizes, elapsed milliseconds, `processed_by: server`, `cleaned_base64`, normalized dimensions, generic status and a separate `visual_status`. Its report holds only allowlisted mark names/statuses, metadata disposition and review warning. Internal paths, raw metadata, confidence values and native diagnostics are discarded.

One active image job and two waiting tickets are independent of PDF and NMT capacity. Each temporary hashed client identity may hold one reservation; five reservations per minute, plus the existing general limit. Polling and cancellation are exempt. Ready tickets expire after 20 seconds, waiting tickets after 180 seconds. Each is single-use and scoped to media. A processing request cannot borrow a PDF/NMT ticket. Image capacity remains occupied through HTTP response delivery, with a 120-second request ceiling for stalled clients. `X-NoMark-Reservation-Consumed: 1` tells the browser that a parsed processing request has spent its ticket, including controlled errors, so it does not delete an already consumed ticket.

Upload timeout is 30 seconds; worker timeout 60 seconds; interservice HTTP timeout 75 seconds; browser processing timeout 90 seconds after the ticket becomes ready. Failed or cancelled inference triggers explicit internal job cancellation and idle confirmation before new admission. An uncertain stop blocks the queue until readiness/idle recovery. Completed tickets are not deleted again by the browser.

## Isolation and storage

The media container uses UID 10003, read-only root, no capabilities, no-new-privileges, two CPUs, 2 GiB RAM without extra swap, 128 processes/threads and 256 MiB tmpfs. Its only network is an internal bridge shared with NoMark. Image worker seccomp denies socket creation/connect/send syscalls, including native-library calls; the HTTP parent remains reachable internally. There are no model downloads, AI providers, GPUs or user-selected network addresses.

Working files are removed on success, parser/worker failure, timeout or cancellation. Idle cleanup safely removes abandoned job directories older than five minutes. A worker whose termination is uncertain keeps its directory and blocks admission. Container tmpfs is ephemeral. This is operational cleanup, not forensic RAM erasure.

Browser history stores `mode: image`, input/output blobs, report and time in the same existing IndexedDB store. Its shared limit remains 20 records/100 MiB, including both images and report. Existing file/text/paraphrase records remain compatible. Quota failure leaves the displayed result available.

## Deployment and releases

Use root Compose for development or the complete three-service Portainer stack. The optional media override supports an existing app installation. `NOMARK_MEDIA_URL` is operator configuration, not user input. Main-app startup and `/health` do not depend on media readiness. Capability checks expose only public limits.

GitLab prepares a sparse, pinned upstream source artifact, runs both-service unit/browser checks, builds the media image from repository root and runs an actual HTTP image-cleaning smoke. Branch builds use SHA tags. Alpha.8 remains a staging candidate; no media `latest` promotion is configured. The existing NMT release gate remains intact.
