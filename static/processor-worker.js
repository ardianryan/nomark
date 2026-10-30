import { loadPyodide } from '/static/vendor/pyodide/314.0.7/pyodide.mjs';

let runtime;
async function initialize() {
  const manifest = await (await fetch('/static/engine-manifest.json', { cache: 'no-cache' })).json();
  const engine = await loadPyodide({ indexURL: manifest.pyodide, stdout: () => {}, stderr: () => {} });
  const archive = new Uint8Array(await (await fetch(manifest.bundle)).arrayBuffer());
  engine.FS.mkdirTree('/app');
  engine.unpackArchive(archive, 'zip', { extractDir: '/app' });
  engine.runPython("import sys; sys.path.insert(0, '/app')\nfrom nomark.engine import process_text, process_file, ProcessingError\nimport json, tempfile\nfrom pathlib import Path");
  return engine;
}

self.onmessage = async ({ data }) => {
  try {
    if (!runtime) { self.postMessage({ type: 'stage', stage: 'localLoading' }); runtime = initialize(); }
    const engine = await runtime;
    self.postMessage({ type: 'stage', stage: 'localProcessing' });
    const started = performance.now();
    engine.globals.set('nm_mode', data.mode);
    engine.globals.set('nm_text', data.text || '');
    engine.globals.set('nm_name', data.name || '');
    const bytes = data.bytes ? new Uint8Array(data.bytes) : new Uint8Array();
    engine.globals.set('nm_bytes', bytes);
    const raw = engine.runPython(`
try:
    if nm_mode == 'text':
        result = process_text(nm_text)
    else:
        if Path(nm_name).suffix.lower() == '.pdf':
            raise ProcessingError('pdf_server_required')
        with tempfile.TemporaryDirectory(prefix='nomark-') as temporary:
            root = Path(temporary)
            source = root / 'input'
            source.write_bytes(bytes(nm_bytes.to_py()))
            result = process_file(source, nm_name, root)
    result = {'ok': True, **result, 'processed_by': 'browser'}
except ProcessingError as error:
    result = {'ok': False, 'error': error.code}
except Exception:
    result = {'ok': False, 'error': 'processing_failed'}
json.dumps(result, ensure_ascii=True)
`);
    engine.globals.delete('nm_text');
    engine.globals.delete('nm_bytes');
    engine.runPython("result = None; nm_text = None; nm_bytes = None; nm_name = None; import gc; gc.collect()");
    const result = JSON.parse(raw);
    result.elapsed_ms = Math.round(performance.now() - started);
    self.postMessage({ type: 'result', result });
  } catch {
    runtime = null;
    self.postMessage({ type: 'result', result: { ok: false, error: 'browser_engine_unavailable' } });
  }
};
