# NoMark

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://gitlab.com/ardianryan/nomark/-/raw/main/docs/assets/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://gitlab.com/ardianryan/nomark/-/raw/main/docs/assets/banner-light.svg">
  <img src="docs/assets/banner.svg" alt="NoMark — Clean text. Clear traces. A browser workspace for hidden Unicode and document metadata." width="1200">
</picture>

[![Pipeline](https://gitlab.com/ardianryan/nomark/badges/main/pipeline.svg)](https://gitlab.com/ardianryan/nomark/-/pipelines) [![License: MIT](https://img.shields.io/badge/license-MIT-416e58)](LICENSE)

A public, account-free web tool for cleaning hidden Unicode characters and file metadata. NoMark makes [watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover) available through a browser without a complicated installation.

**Website:** https://nomark.ardianryan.com · **Contact:** me@ardianryan.com

The website address is the production target. Deployment and DNS setup are separate from this repository.

## Features

- Paste text or select supported documents; inspect changes, copy, and download results.
- Process text and non-PDF documents locally using the original Python cleaners in a Pyodide Web Worker.
- Clean PDF metadata on the server after explicit permission, with a bounded queue before upload.
- Keep history in the browser, with individual and bulk deletion.
- Switch between Indonesian and English, and system, light, or dark themes.
- Use keyboard-accessible controls, responsive layouts, and screen-reader status announcements.

No AI model, API key, MCP service, account, or server database is required. The cleaning tools do not rewrite text or perform PDF OCR, remove visual image/video watermarks, or guarantee removal of statistical AI watermarks. Image and audio/video cleaning removes supported metadata only: it does not alter pixel or waveform watermarks. Removing metadata may affect image orientation or color interpretation; review results. Findings do not establish who authored content.

## Where processing happens

| Input or feature | Location | Content uploaded? |
| --- | --- | --- |
| Pasted text | Browser worker | No |
| TXT, Markdown, HTML | Browser worker | No |
| DOCX, XLSX, PPTX, ODT, EPUB, TEX/LaTeX | Browser worker | No |
| PNG, JPEG, WebP, GIF, BMP, TIFF, AVIF, HEIC/HEIF, SVG metadata | Browser worker | No |
| WAV, MP3, FLAC, M4A, MP4, MOV, M4V metadata | Browser worker | No |
| PDF metadata | Server, after permission and admission | PDF and filename |
| History, preferences, downloads | Browser | No synchronization |

Local-engine failures never silently upload content. Direct compatibility API calls are server processing, including calls containing text or non-PDF documents.

## Quick start

Requirements: Python 3.11 and Git. Node.js is only needed for asset maintenance and browser tests.

```sh
git submodule update --init --recursive
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m nomark.dev
```

Open http://127.0.0.1:8000. The development server binds to `0.0.0.0:8000`, allowing access at `http://<computer-ip>:8000` from the same network. Use `--host 127.0.0.1` for local-only access. Local firewalls and Wi-Fi client isolation can affect access.

For native PDF processing on macOS:

```sh
brew install exiftool qpdf ghostscript
```

Restart the server and check `/health` for `pdf_ready: true`. Docker is not required to test PDFs locally.

## Deployment

For Portainer, use `registry.gitlab.com/ardianryan/nomark:latest` and pull/redeploy after each release. This rolling tag currently includes alpha releases; versioned tags remain available for rollback.

Published images and tagged releases are available from [GitLab](https://gitlab.com/ardianryan/nomark/-/releases). See [Releasing](docs/RELEASING.md) for version policy and image verification. Alpha limitations are recorded in [Changelog](CHANGELOG.md).

```sh
docker compose up --build -d
curl http://127.0.0.1:8000/health
```

**The default one-image, one-container deployment** includes FastAPI, frontend assets, the Python cleaners, ExifTool, qpdf, and Ghostscript. Caddy runs on the host for HTTPS. There is no separate frontend server, database or Redis. Optional paraphrasing adds a separate local NMT container. See [Deployment](docs/DEPLOYMENT.md) before configuring the VPS.

## Limits

- Text: 200,000 characters. Files: 20 MiB each; five sequential files per browser queue.
- PDF server: two simultaneous jobs and eight waiting tickets. Files stay on the device while waiting.
- Server upload timeout: 30 seconds. Processing timeout: 60 seconds. Browser processing timeout: 90 seconds.
- IndexedDB history: 20 entries or 100 MiB, including originals and results. Oldest entries are evicted.
- Working files are deleted after jobs; remnants older than five minutes are swept while running.

See [Architecture](docs/ARCHITECTURE.md) for admission, process isolation, rate limiting, and scaling details.

## Repository structure

```text
nomark/                  FastAPI app, Python integration, SEO, and public policies
static/                  Browser UI, translations, workers, and bundled runtime
  brand/                 Outlined logos, favicons, device icons, social preview
  vendor/                Versioned runtime assets and third-party licenses
watermarks-remover/      Pinned upstream Git submodule
scripts/                 Asset generation and maintenance
tests/                   Python and browser tests
deploy/                  Host Caddy configuration
docs/                    Architecture, deployment, design, SEO, verification
.github/                 Issue and pull request templates
```

`watermarks-remover` is a submodule pinned to `5c180932a00c793261177f79aee21db8929f3fe2`. Git records its URL and commit rather than importing its history. Clone this repository with `--recurse-submodules`, or initialize the submodule as shown above. The browser bundle includes the required upstream modules and their license.

## Development

```sh
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m pytest
npm ci
npm test
```

Browser tests use local Google Chrome or an installed Playwright Chromium. If needed, run `npx playwright install chromium`.

After changing Python cleaning code, run `.venv/bin/python scripts/browser_bundle.py`. After changing `static/translations.json`, run `.venv/bin/python scripts/translations.py`. `npm run vendor` regenerates the local engine, runtime, browser dictionary, and notices. `npm run brand` exports PNG and ICO assets from the committed SVG masters; it requires a browser, not a font download.

Read [Contributing](CONTRIBUTING.md), [Security](SECURITY.md), [Code of conduct](CODE_OF_CONDUCT.md), and [Changelog](CHANGELOG.md).

## Public documentation

- [Architecture and API](docs/ARCHITECTURE.md)
- [Deployment and scaling](docs/DEPLOYMENT.md)
- [SEO and discoverability](docs/SEO.md)
- [Design](docs/DESIGN.md) and [verification](docs/VERIFICATION.md)
- Privacy: `/id/privacy`, `/en/privacy`; terms: `/id/terms`, `/en/terms`

## Licensing and attribution

The upstream cleaner is MIT-licensed. Alpine.js, Vue, Pyodide, and CPython retain their own licenses; see [Third-party notices](THIRD_PARTY_NOTICES.md) and [browser notices](static/notices.txt).

NoMark's original application code is licensed under the [MIT License](LICENSE). Third-party components retain their own licenses and required notices.

## Optional paraphrasing

A separate, staging-first NMT service supports limited Indonesian and English back-translation with explicit server consent. Its conservative edit filter retains original segments when a candidate cannot be accepted; many texts remain unchanged. It is not a SynthID detector or a guaranteed watermark remover. The default single-container cleaner works without it. See [Paraphrasing](docs/PARAPHRASE.md) for data flow, two-container setup, limits and the model-quality release gate.

The result editor highlights changes, offers available word/phrase alternatives, and supports manual editing or restoration of the original text. Comparison, choices and editing run in the browser without another model request. Copy, download and local history follow the latest result. Technical details remain available in the FAQ and privacy policy.
