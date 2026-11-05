# Alpha.8 image-processing verification

Date: 2026-11-05. Status: **staging candidate verified; not released or deployed to production**. The NMT alpha.7 quality gate still fails and has not been weakened. No release tag or `latest` promotion was made.

## Implementation provenance

The dedicated media container builds remove-ai-watermarks 0.54.0 directly from submodule commit `b57ef6045cd7de525bc10546d4c1ce9f9fe151f7`. The adapter calls `remove_visible_detailed` with `backend="cv2"`, `sensitivity="auto"` and no diffusion or learned fill backend. Apache-2.0 attribution appears on the site, in third-party notices, the Docker image and repository documentation. Source hashes for the adapter, isolation and transport are in the corpus report.

Inputs are one static PNG/JPEG/WebP, at most 20 MiB, 8 megapixels and 8,192 pixels per side. PNG output normalizes orientation/color, preserves alpha and excludes user metadata. Boundaries, consent, queue behavior and response fields are described in [image processing](IMAGE_PROCESSING.md).

## Results

- **225 Python tests passed on Linux**, in a disposable offline non-root test container with read-only source/root, a writable tmpfs, two CPUs, 2 GiB RAM and a process limit. This includes main app, NMT regression and media tests, including actual seccomp socket denial. No tests were skipped. One existing framework TestClient deprecation warning remains.
- All 36 browser tests passed, including six dedicated image checks. Eight JavaScript unit tests also passed. Image checks cover permission, no upload while waiting, PNG download, restored history, quota failure, cancellation, retry intervals, Indonesian/English copy, keyboard tabs, mobile layouts and disguised SVG rejection.
- Actual staging browser-to-app-to-media processing produced a downloadable Gemini-example PNG and restored it from IndexedDB. Automated accessibility checks of the image panel found no violations in light/dark themes. This is not a complete manual screen-reader certification.
- Real HTTP active cancellation and client disconnect each terminated an actual image worker. The media temporary job directory was empty after completed work. Unit checks cover timeout, crash paths, cancellation before POST, cancellation tombstone exhaustion, repeated cancellation during cleanup, response backpressure and stalled-send expiry.
- Stopping only the staging media container made its capability unavailable while main health/PDF readiness and text cleaning continued to work. Installed media dependencies passed `pip check`.
- GitLab CI lint with main-branch pipeline simulation passed. Candidate containers built and passed local staging smoke checks. A new GitLab pipeline has not been triggered by this unpushed working tree. Final shared queue/error wording was checked by repeating all 36 browser tests after the container smoke runs.

## Fixed corpus and visual limits

[Corpus report](evaluations/alpha8-media-corpus.json): 30 synthetic fixtures with fixed hashes, consisting of 15 supported-mark examples, ten clean controls and five unregistered-text-mark controls. Fourteen of the fifteen supported examples were recognized and processed; the top-left Jimeng pill was missed without provenance and remains an explicit allowed miss. No clean/unknown control triggered a removal. Every case had zero changed pixels outside the union of actual fill masks.

All 30 comparisons were inspected through six generated contact sheets on macOS. A Linux repeat matched statuses, detected marks and the unchanged-outside-mask check. Some filled regions show smoothing or diagonal artifacts. These are synthetic regression examples, not a photographic fidelity benchmark or a general detection-accuracy estimate. The same-detector after-check is not an independent removal oracle. No SynthID or hidden-watermark claim is made.

The active upstream registry contains 18 mark keys. Positive examples cover Gemini, Doubao, Jimeng, Qwen, Wan, Kling, Yuanbao, Dola, WorkBuddy, Samsung, RunningHub, Baidu, Liblib, Microsoft and Jimeng pill. The last is missed in this corpus. Liblib pill, generic AI label and OpenArt have no positive example in this NoMark corpus; their false-positive behavior is included in the clean-control scan, not a claim of positive validation. No detector was disabled because none altered the clean controls. A separate real-API test cleans Gemini and Microsoft together in one image.

## Measured CPU resources

[Resource record](evaluations/alpha8-media-resources.json) contains cold-process PNG/JPEG/WebP runs at 1, 4 and 8 megapixels under two CPUs and 2 GiB RAM. The more detailed series resizes a synthetic Gemini example; it is not a real photograph or worst-case adversarial input.

| Pixels | PNG time | JPEG time | WebP time | Largest child peak RSS |
| --- | --- | --- | --- | --- |
| 1 million | 1.206 s | 0.928 s | 0.928 s | 110.7 MiB |
| 4 million | 2.583 s | 2.056 s | 1.806 s | 192.2 MiB |
| 8 million | 5.467 s | 4.564 s | 3.786 s | 287.7 MiB |

RSS is measured by Linux `wait4` for the processing child. It is not total container memory and excludes parent/base64/HTTP/browser overhead. Flat-image baseline measurements are also retained separately. Cases passed the configured deadline and memory ceiling. These observations do not guarantee latency for every accepted image or establish a multi-service concurrency benchmark.

## Production observation and rollout gate

Production alpha.6 was read-only inspected. Its cached PDF readiness was false and Docker reported it unhealthy, while ExifTool, qpdf and Ghostscript each returned zero when checked directly. The candidate refreshes native readiness every 30 seconds, and its staging app was healthy with PDF ready. Production was not restarted or changed. Recheck and restore production readiness before a later rollout. Nginx's observed global upload limit is 50 MiB; the app still enforces its own 20 MiB image limit.

Deployment remains a separate decision. The three-service Portainer example's media rolling tag is not published; use matching tested SHA images for staging. The media service is optional and independent of NMT, and adding images does not bypass the existing NMT release-quality requirements.

## Cleanup

Testing uses only `nomark-alpha8-*` containers/images/networks and an isolated temporary source directory on the authorized shared host. Cleanup removes those resources, including their unused tagged/dangling image versions, without touching production, unrelated apps or `scc-*` images. No global Docker prune is used. Only explicitly identified private media-build cache records were pruned by exact ID; unrelated/shared BuildKit cache was retained. Free disk space returned to approximately 7.9 GiB. Local ignored logs and screenshots are retained for review; bounded reports above are included in the repository.
