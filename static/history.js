(() => {
  const MAX_ITEMS = 20;
  const MAX_BYTES = 100 * 1024 * 1024;
  let connection;

  function open() {
    if (!connection) connection = new Promise((resolve, reject) => {
      const request = indexedDB.open('nomark-history', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('items', { keyPath: 'id' });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error('storage_blocked'));
    });
    return connection;
  }

  async function all() {
    const db = await open();
    return new Promise((resolve, reject) => {
      const request = db.transaction('items').objectStore('items').getAll();
      request.onsuccess = () => resolve(request.result.sort((a, b) => b.created - a.created));
      request.onerror = () => reject(request.error);
    });
  }

  async function write(operation) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction('items', 'readwrite');
      operation(transaction.objectStore('items'));
      transaction.oncomplete = () => resolve();
      transaction.onabort = () => reject(transaction.error || new Error('storage_failed'));
      transaction.onerror = () => reject(transaction.error);
    });
  }

  window.NoMarkHistory = {
    async list() {
      return (await all()).map(({ id, created, mode, title, sourceName, size }) => ({ id, created, mode, title, sourceName, size }));
    },
    async get(id) {
      const db = await open();
      return new Promise((resolve, reject) => {
        const request = db.transaction('items').objectStore('items').get(id);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
    },
    async save(record) {
      const clean = { ...record, result: JSON.parse(JSON.stringify(record.result)) };
      delete clean.result.cleaned_base64;
      delete clean.result.outputBlob;
      clean.size = (clean.sourceBlob?.size || new Blob([clean.inputText || '']).size) + (clean.outputBlob?.size || 0) + new Blob([JSON.stringify(clean.result)]).size;
      if (clean.size > MAX_BYTES) throw new Error('storage_limit');
      const previous = (await all()).filter(item => item.id !== clean.id);
      let total = previous.reduce((sum, item) => sum + item.size, 0) + clean.size;
      let count = previous.length + 1;
      const removed = [];
      for (const oldest of previous.toReversed()) {
        if (count <= MAX_ITEMS && total <= MAX_BYTES) break;
        removed.push(oldest.id);
        total -= oldest.size;
        count--;
      }
      await write(store => {
        removed.forEach(id => store.delete(id));
        store.put(clean);
      });
      return removed.length;
    },
    async remove(id) { await write(store => store.delete(id)); },
    async clear() { await write(store => store.clear()); },
  };
})();
