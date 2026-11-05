document.addEventListener('alpine:init', () => {
  Alpine.data('imageEditor', () => ({
    imageFile: null, imageResult: null, originalUrl: '', cleanedUrl: '', imageWidth: 0, imageHeight: 0,
    imageConsent: false, imageAvailable: false, imageSelecting: false, imageDragging: false,
    imageController: null, imageTicket: null, imageRevision: 0,
    init() {
      this.refreshImageAvailability();
      this.onImageCancel = () => this.cancelImage();
      this.onImageRestore = event => this.restoreImage(event.detail);
      window.addEventListener('nomark-cancel-image', this.onImageCancel);
      window.addEventListener('nomark-restore-image', this.onImageRestore);
    },
    destroy() {
      window.removeEventListener('nomark-cancel-image', this.onImageCancel);
      window.removeEventListener('nomark-restore-image', this.onImageRestore);
      this.cancelImage(); this.revokeImageUrls();
    },
    revokeImageUrls() {
      if (this.originalUrl) URL.revokeObjectURL(this.originalUrl);
      if (this.cleanedUrl) URL.revokeObjectURL(this.cleanedUrl);
      this.originalUrl = this.cleanedUrl = '';
    },
    async refreshImageAvailability() {
      try { const r = await fetch('/api/media/capabilities'); this.imageAvailable = r.ok && (await r.json()).available === true; }
      catch { this.imageAvailable = false; }
    },
    get imageMissing() { return !this.imageAvailable; },
    get cannotProcessImage() { return this.busy || this.imageSelecting || !this.imageFile || !this.imageAvailable; },
    get imageMeta() { return this.imageFile ? `${this.imageFile.name} · ${this.formatBytes(this.imageFile.size)} · ${this.imageWidth} × ${this.imageHeight}` : ''; },
    get imageDropClass() { return this.imageDragging ? 'dragging' : ''; },
    get imageSummary() { return this.imageResult ? this.t('image_' + this.imageResult.visual_status) : ''; },
    get imageMarks() { return this.imageResult?.report.marks || []; },
    imageMarkLabel(mark) { return `${mark.label} — ${this.t('imageMark_' + mark.status)}`; },
    pickImage(event) { const files = event.target.files; this.selectImage(files); event.target.value = ''; },
    dropImage(event) { this.imageDragging = false; if (!this.busy) this.selectImage(event.dataTransfer.files); },
    async selectImage(files) {
      if (this.busy || !files?.length) return;
      if (files.length !== 1) { this.error = this.t('imageOneFile'); return; }
      const file = files[0], revision = ++this.imageRevision;
      this.imageSelecting = false;
      if (!/\.(png|jpe?g|webp)$/i.test(file.name)) { this.error = this.t('unsupported_format'); return; }
      if (!file.size || file.size > 20 * 1024 * 1024) { this.error = this.t(file.size ? 'file_too_large' : 'empty_file'); return; }
      this.imageSelecting = true;
      const url = URL.createObjectURL(file);
      try {
        const header = new Uint8Array(await file.slice(0, 12).arrayBuffer());
        const format = [...header.slice(0, 8)].join(',') === '137,80,78,71,13,10,26,10' ? 'png'
          : header[0] === 255 && header[1] === 216 && header[2] === 255 ? 'jpeg'
          : String.fromCharCode(...header.slice(0,4)) === 'RIFF' && String.fromCharCode(...header.slice(8,12)) === 'WEBP' ? 'webp' : '';
        const extension = file.name.split('.').pop().toLowerCase().replace('jpg', 'jpeg');
        if (!format || format !== extension) throw new Error('invalid_document');
        if (revision !== this.imageRevision) return;
        const preview = new Image(); preview.src = url; await preview.decode();
        if (revision !== this.imageRevision) return;
        const w = preview.naturalWidth, h = preview.naturalHeight;
        if (!w || !h || w * h > 8000000 || Math.max(w, h) > 8192) throw new Error('image_dimensions');
        this.revokeImageUrls(); this.originalUrl = url; this.imageFile = file;
        this.imageWidth = w; this.imageHeight = h; this.imageResult = null;
        this.imageConsent = false; this.error = ''; this.notice = '';
      } catch (error) { if (revision === this.imageRevision) this.error = this.t(error.message === 'image_dimensions' ? error.message : 'invalid_document'); }
      finally { if (this.originalUrl !== url) URL.revokeObjectURL(url); if (revision === this.imageRevision) this.imageSelecting = false; }
    },
    clearImage() {
      if (this.busy) return;
      this.imageRevision++; this.imageSelecting = false; this.revokeImageUrls(); this.imageFile = this.imageResult = null; this.imageConsent = false;
    },
    async imageCall(url, options = {}) {
      const response = await fetch(url, { ...options, signal: this.imageController.signal });
      if (url === '/api/image/process' && response.headers.get('X-NoMark-Reservation-Consumed') === '1') this.imageTicket = null;
      let result;
      try { result = await response.json(); } catch { throw new Error('media_failed'); }
      if (!response.ok || result?.ok !== true) {
        const error = new Error(response.status === 429 ? 'rate_limited' : result?.error || 'media_failed');
        if (response.status === 429) error.retryAfter = Math.min(60, Math.max(1, Number(response.headers.get('Retry-After')) || 60));
        throw error;
      }
      return result;
    },
    async releaseImageTicket() {
      const ticket = this.imageTicket; this.imageTicket = null;
      if (ticket) try { await fetch('/api/media/queue', { method: 'DELETE', headers: { Authorization: `Bearer ${ticket}` }, keepalive: true }); } catch {}
    },
    cancelImage() { this.imageController?.abort(); this.releaseImageTicket(); },
    async processImage() {
      if (this.busy || !this.imageFile || this.imageSelecting) return;
      if (!this.imageConsent) { this.error = this.t('imageConsentNeeded'); return; }
      if (!this.imageAvailable) { this.error = this.t('media_unavailable'); return; }
      this.busy = true; this.error = ''; this.notice = '';
      this.imageController = new AbortController();
      let timedOut = false, timer;
      try {
        this.stage = this.t('imageReserving');
        timer = setTimeout(() => { timedOut = true; this.imageController.abort(); }, 185000);
        let ticket = await this.imageCall('/api/media/queue', { method: 'POST' });
        this.imageTicket = ticket.token;
        while (ticket.state !== 'ready') {
          this.stage = `${this.t('imageWaiting')} ${ticket.position}`;
          await new Promise((resolve, reject) => {
            const signal = this.imageController.signal;
            const done = () => { signal.removeEventListener('abort', abort); resolve(); };
            const id = setTimeout(done, 1000);
            function abort() { clearTimeout(id); reject(new DOMException('Cancelled', 'AbortError')); }
            signal.addEventListener('abort', abort, { once: true }); if (signal.aborted) abort();
          });
          ticket = await this.imageCall('/api/media/queue', { headers: { Authorization: `Bearer ${this.imageTicket}` } });
        }
        clearTimeout(timer); timer = setTimeout(() => { timedOut = true; this.imageController.abort(); }, 90000);
        this.stage = this.t('imageProcessing');
        const body = new FormData(); body.append('file', this.imageFile, this.imageFile.name);
        const result = await this.imageCall('/api/image/process', { method: 'POST', headers: { 'X-NoMark-Reservation': this.imageTicket }, body });
        this.imageTicket = null;
        if (result.kind !== 'image' || result.mime !== 'image/png' || typeof result.cleaned_base64 !== 'string') throw new Error('media_failed');
        const outputBlob = toBlob(result.cleaned_base64, 'image/png'); delete result.cleaned_base64;
        if (this.cleanedUrl) URL.revokeObjectURL(this.cleanedUrl);
        this.cleanedUrl = URL.createObjectURL(outputBlob); this.imageResult = { ...result, outputBlob };
        await this.saveHistory({ id: newId(), created: Date.now(), mode: 'image', title: this.imageFile.name,
          sourceName: this.imageFile.name, sourceBlob: this.imageFile, outputBlob, result });
      } catch (error) {
        if (error.name === 'AbortError') this.notice = this.t(timedOut ? 'media_timeout' : 'cancelled');
        else this.error = error.retryAfter ? this.t('paraphraseRetryAfter').replace('{seconds}', error.retryAfter) : this.t(error.message);
      } finally {
        clearTimeout(timer); await this.releaseImageTicket(); this.imageController = null; this.busy = false; this.stage = '';
      }
    },
    downloadImage() { if (this.imageResult) download(this.imageResult.outputBlob, this.imageResult.cleaned_name); },
    restoreImage(record) {
      if (this.busy) return;
      this.imageRevision++; this.revokeImageUrls(); this.imageSelecting = false;
      this.imageFile = new File([record.sourceBlob], record.sourceName);
      this.originalUrl = URL.createObjectURL(record.sourceBlob); this.cleanedUrl = URL.createObjectURL(record.outputBlob);
      this.imageResult = { ...record.result, outputBlob: record.outputBlob };
      this.imageWidth = record.result.width; this.imageHeight = record.result.height; this.imageConsent = false;
    },
  }));
});
