import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const root = process.cwd();
const directory = path.join(root, 'static/vendor/pyodide/314.0.7');
const { loadPyodide } = await import(pathToFileURL(path.join(directory, 'pyodide.mjs')).href);
const python = await loadPyodide({ indexURL: `${directory}/`, stdout: () => {}, stderr: () => {} });
const manifest = JSON.parse(await readFile(path.join(root, 'static/engine-manifest.json'), 'utf8'));
python.FS.mkdirTree('/app');
python.unpackArchive(new Uint8Array(await readFile(path.join(root, manifest.bundle))), 'zip', { extractDir: '/app' });
python.FS.writeFile('/tmp/sample.png', new Uint8Array(await readFile(path.join(root, 'tests/fixtures/media/sample.png'))));
const result = python.runPython(`
import sys, json, base64
from pathlib import Path
sys.path.insert(0, '/app')
original_path = list(sys.path)
from nomark import __version__
from nomark.engine import process_text, process_file
from nomark import upstream
assert sys.path == original_path
assert upstream.text_unicode.__name__ == '_nomark_upstream.text_unicode'
text = process_text('Halo\\u200bdunia. Spasi\\u00a0khusus.')
assert text['cleaned_text'] == 'Halodunia. Spasi khusus.'
root = Path('/tmp/job')
root.mkdir(exist_ok=True)
image = process_file(Path('/tmp/sample.png'), 'sample.png', root)
assert image['status'] == 'cleaned'
assert b'stable diffusion' not in base64.b64decode(image['cleaned_base64'])
source = root / 'draft.md'
source.write_text('Hello\\u200bworld')
markdown = process_file(source, 'draft.md', root)
assert base64.b64decode(markdown['cleaned_base64']) == b'Helloworld'
json.dumps({'version': __version__, 'private_upstream_loader': True, 'text': text['status'], 'png': image['status'], 'markdown': markdown['status']})
`);
console.log(result);
