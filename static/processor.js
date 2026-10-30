(() => {
  let worker;
  let rejectJob;
  let idleTimer;
  let serverController;
  let generation = 0;

  function reset() {
    worker?.terminate(); worker = null;
    clearTimeout(idleTimer);
  }

  window.NoMarkProcessor = {
    async run(mode, input, progress) {
      const startedGeneration = generation;
      clearTimeout(idleTimer);
      if (!window.Worker || !window.WebAssembly) throw new Error('browser_engine_unavailable');
      if (!worker) worker = new Worker('/static/processor-worker.js', { type: 'module' });
      const bytes = mode === 'file' ? await input.arrayBuffer() : null;
      if (startedGeneration !== generation) throw new Error('cancelled');
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { reset(); reject(new Error('browser_timeout')); }, 90000);
        const finish = () => { clearTimeout(timer); rejectJob = null; idleTimer = setTimeout(reset, 120000); };
        rejectJob = () => { finish(); reset(); reject(new Error('cancelled')); };
        worker.onmessage = ({ data }) => {
          if (data.type === 'stage') { progress(data.stage); return; }
          finish();
          if (data.result.ok) resolve(data.result);
          else { if (data.result.error === 'browser_engine_unavailable') reset(); reject(new Error(data.result.error)); }
        };
        worker.onerror = () => { finish(); reset(); reject(new Error('browser_engine_unavailable')); };
        worker.postMessage({ mode, text: mode === 'text' ? input : '', name: input.name || '', bytes }, bytes ? [bytes] : []);
      });
    },
    cancel() { generation++; rejectJob?.(); serverController?.abort(); },
    async serverFile(file, progress) {
      const controller = new AbortController();
      serverController = controller;
      let token;
      const timer = setTimeout(() => controller.abort(), 220000);
      async function call(url, options = {}) {
        const response = await fetch(url, { ...options, signal: controller.signal });
        let result;
        try { result = await response.json(); } catch { throw new Error('network'); }
        if (!response.ok || !result.ok) throw new Error(result.error || 'processing_failed');
        return result;
      }
      try {
        progress('serverReserving');
        let ticket = await call('/api/queue', { method: 'POST' });
        token = ticket.token;
        const deadline = performance.now() + 120000;
        while (ticket.state !== 'ready') {
          progress('serverWaiting', ticket.position);
          if (performance.now() > deadline) throw new Error('queue_expired');
          await new Promise((resolve, reject) => {
            const id = setTimeout(() => { controller.signal.removeEventListener('abort', abort); resolve(); }, 1000);
            function abort() { clearTimeout(id); reject(new DOMException('Cancelled', 'AbortError')); }
            controller.signal.addEventListener('abort', abort, { once: true });
            if (controller.signal.aborted) abort();
          });
          ticket = await call('/api/queue', { headers: { Authorization: `Bearer ${token}` } });
        }
        progress('serverProcessing');
        const body = new FormData(); body.append('file', file, file.name);
        return await call('/api/file/process', { method: 'POST', headers: { 'X-NoMark-Reservation': token }, body });
      } catch (error) {
        if (error.name === 'AbortError') throw new Error('cancelled');
        if (error instanceof TypeError) throw new Error('network');
        throw error;
      } finally {
        clearTimeout(timer); serverController = null;
        if (token) fetch('/api/queue', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` }, keepalive: true }).catch(() => {});
      }
    },
  };
})();
