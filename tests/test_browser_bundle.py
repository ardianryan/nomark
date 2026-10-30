import json
from pathlib import Path
import zipfile


def test_browser_bundle_matches_python_sources():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "static/engine-manifest.json").read_text())
    bundle = root / manifest["bundle"].lstrip("/")
    with zipfile.ZipFile(bundle) as archive:
        for name in archive.namelist():
            assert archive.read(name) == (root / name).read_bytes(), f"Regenerate the browser bundle: {name} differs"
