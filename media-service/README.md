# NoMark Media

Optional CPU service for the Images tab, separate from the main application and NMT. It calls `remove_ai_watermarks.remove_visible_detailed` from the pinned submodule with `backend="cv2"` and `sensitivity="auto"`. NoMark does not modify upstream source.

Inputs: one static PNG, JPEG or WebP; 20 MiB, 8,000,000 pixels and 8,192 pixels per side. Only tested 8-bit RGB/RGBA/grayscale/palette modes are accepted. Outputs: upright sRGB RGBA PNG, private metadata removed, alpha preserved, at most 40 MiB. Unsupported or invalid profiles are rejected rather than guessed.

`requirements.lock` contains SHA-256 hashes for Python 3.11 Linux amd64 wheels. `build.lock` pins the pure-Python build toolchain. The upstream wheel is built from the checked-in submodule, without installing its optional AI/model extras. The upstream Apache-2.0 license ships in the image.

## Deployment

Build from the repository root:

```sh
docker build -f media-service/Dockerfile -t nomark-media:local .
```

The root Compose file includes media. For an existing single-service installation use the optional `deploy/compose.media.yaml` override. The complete Portainer example includes app, NMT and media. No host port is published for media; only the main app joins its private internal network.

Runtime requires Linux for worker seccomp enforcement. Every image gets a separate process and temporary directory. Network socket syscalls are denied in the image worker, including calls made by native libraries. The HTTP parent remains able to accept internal requests. Timeouts, disconnects and cancellations stop the process group; the service blocks admission if termination is not confirmed. Interrupted-job directories older than five minutes are swept while idle.

The public API is documented in `docs/IMAGE_PROCESSING.md`. Internal endpoints `/process`, `/idle`, `/health`, and `DELETE /jobs/{id}` are not public. Job identifiers are operator-internal random values; cancellation tombstones reject a delayed POST after cancellation.

## Tests

```sh
PYTHONPATH=media-service .venv/bin/python -m pytest media-service/tests tests/test_images.py tests/test_image_corpus.py
PYTHONPATH=media-service .venv/bin/python scripts/evaluate_media.py --output artifacts/media-alpha8
```

The synthetic corpus is a regression check, not evidence of general detection accuracy. See the alpha.8 verification record for the missed Jimeng pill example and visual fill artifacts.
