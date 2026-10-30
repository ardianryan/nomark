# Contributing to NoMark

Small fixes, reproducible bug reports, and improvements to supported document handling are welcome. NoMark is licensed under the [MIT License](LICENSE). By contributing original work, you agree to provide it under the same license. Third-party contributions must retain their applicable licenses and notices.

## Before making changes

Check existing issues and describe substantial changes before implementing them. Never attach confidential documents, browser history, queue tokens, or personal metadata to public reports. Use minimal synthetic fixtures.

Initialize the upstream submodule, install Python 3.11 dependencies, and install development tools using the commands in [README.md](README.md). Node.js is not part of the production application.

## Development conventions

- Keep Python application code in `nomark/`, browser assets in `static/`, tests in `tests/`, and operational documentation in `docs/`.
- Keep upstream code in the submodule. Document and test intentional submodule updates; retain upstream attribution.
- Edit `static/translations.json` for both languages, then run `.venv/bin/python scripts/translations.py`. Do not edit generated `static/copy.js` directly.
- Rebuild the browser engine with `.venv/bin/python scripts/browser_bundle.py` after changing cleaner integration. Browser and server cleaning rules must agree.
- Preserve legitimate emoji, joiners, and writing systems. Do not equate detected characters or metadata with AI authorship.
- Make data flows visible to users. A change to uploads, storage, retention, providers, or tracking requires matching policy updates in both languages.
- Keep documentation and code comments in English. Indonesian interface text follows EYD V.

## Verify a change

Run `.venv/bin/python -m pytest` for Python behavior and `npm test` for affected browser flows. Use synthetic documents and review actual outputs. Include relevant test results, screenshots for UI changes, and any environment limits in the pull request. Do not claim a Docker build or a remote deployment was tested unless it was executed.

For UI changes, check keyboard use, small screens, both languages, and all theme choices. For cleaning changes, test unchanged input and preservation as well as removals. For server changes, review admission, timeout, cancellation, and cleanup behavior.

## Pull requests

Explain the problem, the change, and verification. Keep unrelated formatting and generated artifacts out of the patch. Include required generated assets when their source changes. Do not commit local virtual environments, test output, credentials, or uploaded files.

Report vulnerabilities privately using [SECURITY.md](SECURITY.md), and follow the [Code of conduct](CODE_OF_CONDUCT.md).

## Versioned changes

Record every change under its intended version in [CHANGELOG.md](CHANGELOG.md). Keep release metadata consistent using `python scripts/release.py check`; follow [Releasing](docs/RELEASING.md) before tagging. Published tags and versioned images must remain immutable.
