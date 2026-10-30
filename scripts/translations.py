"""Generate the browser dictionary from the server-rendered content source."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
content = json.loads((root / "static/translations.json").read_text())
(root / "static/copy.js").write_text("window.NoMarkCopy = " + json.dumps(content, ensure_ascii=False) + ";\n")
