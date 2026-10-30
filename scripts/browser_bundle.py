"""Package the same Python cleaners for the browser's virtual filesystem."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
files = [ROOT / "nomark/__init__.py", ROOT / "nomark/engine.py", ROOT / "nomark/media.py", ROOT / "nomark/upstream.py"]
files += [ROOT / "watermarks-remover/service/scripts" / name for name in (
    "common.py", "text_unicode.py", "container_meta.py", "image_meta.py", "av_meta.py",
)]
files.extend([ROOT / "LICENSE", ROOT / "watermarks-remover/LICENSE"])
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(files):
        info = zipfile.ZipInfo(str(file.relative_to(ROOT)), date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, file.read_bytes())
content = buffer.getvalue()
digest = hashlib.sha256(content).hexdigest()[:16]
directory = ROOT / "static/vendor/engines"
directory.mkdir(exist_ok=True, parents=True)
for old in directory.glob("*.zip"):
    old.unlink()
(directory / f"{digest}.zip").write_bytes(content)
(ROOT / "static/engine-manifest.json").write_text(json.dumps({
    "bundle": f"/static/vendor/engines/{digest}.zip",
    "pyodide": "/static/vendor/pyodide/314.0.7/",
    "version": digest,
}))
print(f"Browser cleaner: {len(content):,} bytes ({digest})")
