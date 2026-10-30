# Verification

Verified locally on 30 October 2026,
using Python 3.11.16 and Google Chrome.

## Functional checks

- `python -m pytest`: **67 passed**. Covers every accepted extension, Unicode
  preservation, encrypted and malformed input, path names, upload and paste
  limits, streamed body limits, origin checks, rate limiting, and process cleanup.
- Browser suite: **17 passed** (15 workspace tests and two additional SEO tests).
  Real-browser tests cover copy/download, local history
  across reloads, individual and bulk deletion, dialog cancellation, quota failure,
  sequential uploads, drag-and-drop, queue limits, language selection, keyboard
  tabs, and layouts from 320px to 1440px. They also verify browser-only processing
  for every non-PDF format, explicit PDF consent, waiting without uploading,
  cancellation and retry, and release of cancelled queue reservations.
  The SEO tests verify readable localized HTML and native FAQ controls without
  JavaScript, and language switching that preserves input while updating metadata
  and structured data. The old no-JavaScript full-screen overlay was replaced
  with a non-blocking notice after this check exposed it.
- Axe WCAG 2/2.1 A/AA checks: **zero violations** on the empty text workspace,
  processed result, confirmation dialog, mobile document workspace, both themes,
  and bilingual policy pages. System theme changes and saved manual choices pass.
- `pip check`: **no broken requirements**.
- Compose YAML parses successfully; the host binding is `127.0.0.1:8000`.
- Source submodule is at `5c180932a00c793261177f79aee21db8929f3fe2`.
- Browser network inspection confirmed no geolocation or external asset requests.
- Text and all eight non-PDF format groups run the bundled Python core in a local
  Web Worker without requests to processing APIs. A source comparison test keeps
  the browser engine bundle synchronized with the server source.
- Admission tests verify FIFO ordering, the two active/eight waiting limits,
  reservation expiry, single-use tickets, and rejection before multipart parsing
  when capacity is unavailable. Waiting tickets contain no file data.
- Versioned assets return immutable cache headers; precompressed runtime assets
  preserve their MIME type and honor gzip negotiation. Processing responses are
  not cached. Stale temporary-directory cleanup is tested.
- Privacy and terms pages are available in Indonesian and English, with
  `me@ardianryan.com` as the contact address. They describe local storage,
  browser processing, PDF uploads, and direct compatibility API processing.
- Nine SEO/backend checks validate all six localized public pages, canonical and
  language alternates, parseable JSON-LD and XML sitemap, public discovery text,
  robots exclusions, generated dictionary consistency, and real image signatures.
  The English social PNG is 1200 × 630; ICO contains 16/32/48px frames and manifest
  icons resolve. The SVG logos, social preview, and mobile dark layout were viewed.
- English repository documentation now includes contribution, conduct, security,
  changelog, licensing status, architecture, deployment, and SEO details. The
  upstream submodule remains unchanged. No remote push or deployment was made.

## Design delivery gate

- **Hard gate PASS:** the browser tests cover actual controls, empty/loading/error
  states, focus and tabs, downloads and dialog actions; responsive tests find no
  horizontal overflow. There are no fabricated metrics, testimonials, or customer
  claims. The only example text is explicitly loaded with “Coba contoh”.
- **Purpose gate PASS:** `docs/DESIGN.md` records the roles of cream, mint, peach,
  system typography, editor comparison, local-history panel, and restrained motion.
  The user explicitly chose the pastel bento composition.
- **Liveliness PASS:** ENERGY 2 / RHYTHM 2 / MOTION 1. The input/result pair is the
  focal workspace; mint identifies output and peach identifies local history.
- **Craft and consistency PASS:** Indonesian and English use the same components;
  counts derive from actual input and stored records, and findings avoid claims
  about AI authorship. Axe checks and browser screenshots verify contrast and states.

The earlier design inspector reported **0 failures** at 1440, 768, and 390px after the
readability corrections. The approved warm palette and larger friendly heading
are intentional exceptions to its default app style. Its chart warning was a
false positive on a control SVG; the app has no charts. The remaining small-text
warning concerns secondary labels at 11–12px on phones; editable content remains
14px and contrast checks pass. Screenshots are generated under ignored
`artifacts/` during tests and inspection.

The public footer, policy links, processing-location descriptions, and updated
dark desktop/mobile screenshots were inspected after the theme changes. A fresh
1440px browser capture confirms a single header and no horizontal overflow.

## Verification limits

Docker is not installed on this development machine, so the image build has not
been executed here. ExifTool 13.55, qpdf 12.4.2, and Ghostscript 10.08.0 were
installed locally on 30 October. After restarting the dev server, `/health`
reports `pdf_ready: true`. A PDF submitted through the LAN HTTP endpoint had its
Author/Producer/Title metadata removed, retained the same extracted page text,
and passed `qpdf --check` with status `cleaned` and no warnings. The earlier
limited-tool PDF path was also tested before the tools were installed.

The dev launcher (`python -m nomark.dev` or `npm run dev`) now listens on
`0.0.0.0:8000`. Both local interface addresses answered health requests. A real
Chrome session using the LAN IP over HTTP successfully processed text and saved
history with `crypto.randomUUID` unavailable. A targeted Playwright regression
test also passed for the UUID fallback, clipboard fallback, and file selection.
Reachability from a separate physical device still depends on the local firewall
and Wi-Fi client isolation.

The Linux-only child memory/file limits are defined in the worker but were not
exercised on macOS. Timeout, descendant termination, cancellation, and temporary
directory cleanup were exercised locally. No deployment or DNS changes were made.
