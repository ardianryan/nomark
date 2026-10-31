# Isolated staging tests

The 0.1.0-alpha.4 candidate was tested in a dedicated Docker environment on the owner-authorized SSH host `staginglocaldocker`. The host also runs production workloads; staging does not replace the production container, change its image tag, mount its data, or publish a host port.

## Isolation

- Separate staging image, containers, and a staging-only socket volume.
- Non-root UID/GID 10001; read-only root filesystem; all capabilities dropped; no-new-privileges; Docker's default seccomp and private process namespaces.
- Application and Python tests: one CPU, 1 GiB memory with no additional swap, and 64 process/thread slots. Browser tests: one CPU, 1.5 GiB memory, 192 process/thread slots and 128 MiB shared memory, to accommodate Chromium.
- A private `/tmp` tmpfs capped at 512 MiB (768 MiB for browser tests; 64 MiB for bounded probes). The application socket has its own 1 MiB tmpfs volume. No user results are retained on a host bind mount.
- Empty application/test environment populated from an explicit allowlist. No SSH keys, Docker socket, production environment files, or production volumes are available inside the containers.
- `network=none`: the test runtime has only its own loopback; the staging application listens on a Unix socket. SSH forwarding provides browser access without giving the container access to other services on the host.
- Test commands have CPU/file limits and external wall-clock deadlines. A dedicated transient host timer stops the manual staging application after six hours; it does not restart automatically.

## Validation performed

The complete Python suite passed: **110 tests**, including nine hardening regressions, worker kernel-limit enforcement and two real qpdf attachment interruption cases. No tests were skipped. The suite emits one framework adapter deprecation warning. A separate offline Node/Pyodide container loaded the exact browser bundle and verified the private upstream loader plus text, PNG, and Markdown cleaning.

HTTP checks through the SSH tunnel verified the minimal `/health` payload, text processing, and native PDF processing using synthetic input. After successful PDF processing, both the job directory and PDF helper staging-directory counts were zero. The production NoMark container retained its original container ID, image, start time, and zero restart count.

The complete Playwright suite passed: **19 tests**. Node, Chromium, their system libraries and fonts were reused from cached runtime images; only toolchain paths were copied, without those applications' code or configuration. No dependency was fetched. Browser/server traffic stayed on their container's private loopback. Authoritative source and toolchain remained read-only; a disposable source copy, browser state and screenshots lived only on the bounded `/tmp` filesystem. The outer Docker restrictions apply even though Playwright launches Chromium without its inner sandbox.

Bounded probes for the three remaining hypotheses also completed. Their inputs, observed results and limits are recorded in [Verification](VERIFICATION.md). They do not establish fairness, a production aggregate quota, bounded parser complexity or production safety.

### Reproduce with pre-provisioned tools

Run these commands only inside the isolated test container, using a disposable source copy for Playwright's artifacts. Do not install or download dependencies during the audit run.

```sh
python -m pytest -o addopts= -q -p no:cacheprovider --basetemp=/tmp/pytest
CI=1 NOMARK_TEST_PYTHON=python NOMARK_TEST_CHROMIUM=/path/to/chromium \
  node node_modules/@playwright/test/cli.js test --reporter=dot \
  --timeout=60000 --output=/tmp/test-results
python -m runpy tests/staging/security-probes.py
node tests/staging/wasm-check.mjs
```

The probe run is separately capped at half a CPU, 512 MiB memory, 64 processes, 16 MiB per file, 64 MiB scratch and 45 seconds. Python runs have a 180-second wall deadline; browser runs have a 360-second deadline. Empty environments allow only safe PATH, scratch HOME/TMPDIR/cache paths, Python bytecode/output settings, a single numerical-library thread, test runtime paths, CI mode and scratch application workdir. No inherited credentials are passed.

The long-running manual staging application may represent an earlier alpha.4 source snapshot. The final tests above use a fresh image overlay containing the final runtime/test changes. No release image or production promotion is implied by the shared candidate version.

## Browser access

The active session forwards local `127.0.0.1:8121` to the staging application's Unix socket over SSH. Open **http://127.0.0.1:8121** on the computer running that tunnel; this is not a newly opened LAN port on the Docker host.

For a later session, read the staging instance's `staging-state.json` on the SSH host for the socket path, then forward it:

```sh
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8121:/path/from/staging-state.json/app.sock \
  staginglocaldocker
```

Use only the `nomark-staging-*` resources when stopping or removing this environment. Do not run host-wide Docker cleanup commands. Starting or promoting production remains a separate operation requiring the owner's approval.

## Alpha.5 staging

The later optional NMT environment used a separate alpha.5 application/model pair on an internal-only network, with a distinct socket volume and six-hour expiry timer. The temporary local tunnel used `http://127.0.0.1:8122`; it is not a permanent deployment. At the owner's request, test containers, images, socket volumes, the staging network and temporary source/build directories are removed after verification. Production resources are excluded. Alpha.5 results and quality limitations are in [Verification](VERIFICATION.md) and [Paraphrasing](PARAPHRASE.md).

The [cleanup record](evaluations/alpha5-staging-cleanup.json) confirms removal of all three alpha.4/alpha.5 staging containers, no remaining staging image tags/volumes/networks, stopped expiry timers and removal of both temporary directories. Local SSH forwards on ports 8121 and 8122 were closed. Host free space increased by approximately 4.8 GiB during cleanup; this is an observed filesystem difference, not an exact accounting of Docker layer sizes. Production NoMark remained healthy with the same container/image, start time and zero restarts.

That first check missed randomly named containers left by failed legacy Docker builds and untagged test images. The [follow-up record](evaluations/alpha5-staging-cleanup-followup.json) documents removal of three failed-build containers, eight additional test image roots and sixteen remaining parent image records. Final inspection found zero exited containers and zero NoMark dangling images. Two unrelated application images remain untagged; one is used by a running production container. Running container IDs, images, start times and restart counts were unchanged during the final cleanup. No global prune or force removal was used.

## Alpha.6 editor follow-up

The real-model regression used one separately labelled, offline source-overlay container with two CPUs, 2 GiB RAM, read-only storage, 128 MiB tmpfs and 64 processes/threads. It used the existing published runtime and unchanged model/dependency pins. A three-hour timer bounded its lifetime. Local browser tests used synthetic responses and an isolated Chrome profile; no production service received test text. The [alpha.6 cleanup record](evaluations/alpha6-staging-cleanup.json) confirms that the container, both labelled build images, timer and temporary directory were removed while production containers and all preexisting `scc-*` images were preserved.
