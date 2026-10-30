const COPY = window.NoMarkCopy;

function toBlob(encoded, type) {
  const raw = atob(encoded);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return new Blob([bytes], { type });
}

function newId() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener('alpine:init', () => {
  Alpine.data('workspace', () => ({
    locale: 'id', tab: 'text', formatCategory: 'documents', input: '', textResult: null, selectedFileResult: null,
    files: [], history: [], busy: false, dragging: false, stage: '', error: '', notice: '', pdfReady: false, theme: 'system', allowServer: false, cancelled: false,
    async init() {
      let saved;
      try { saved = localStorage.getItem('nomark-language'); } catch {}
      const pathLocale = location.pathname.match(/^\/(id|en)$/)?.[1];
      this.locale = pathLocale || (['id', 'en'].includes(saved) ? saved : navigator.languages.some(language => /^id(?:-|$)/i.test(language)) ? 'id' : 'en');
      this.updateLanguage();
      this.theme = NoMarkAppearance.mode;
      window.addEventListener('nomark-theme', event => { this.theme = event.detail; });
      await this.refreshHistory();
      try { const response = await fetch('/health'); this.pdfReady = (await response.json()).pdf_ready; } catch {}
    },
    t(key) { return COPY[this.locale][key] || COPY.en[key] || key; },
    updateLanguage() {
      document.documentElement.lang = this.locale;
      document.title = this.t('seoTitle');
      const url = `https://nomark.ardianryan.com/${this.locale}`;
      document.querySelector('meta[name="description"]').content = this.t('seoDescription');
      document.querySelector('link[rel="canonical"]').href = url;
      for (const [key, value] of Object.entries({title: this.t('seoTitle'), description: this.t('seoDescription'), url, locale: this.locale === 'id' ? 'id_ID' : 'en_US'})) document.querySelector(`meta[property="og:${key}"]`).content = value;
      document.querySelector('meta[property="og:locale:alternate"]').content = this.locale === 'id' ? 'en_US' : 'id_ID';
      for (const key of ['title', 'description']) document.querySelector(`meta[name="twitter:${key}"]`).content = this.t(key === 'title' ? 'seoTitle' : 'seoDescription');
      const schema = document.querySelector('script[type="application/ld+json"]');
      const data = JSON.parse(schema.textContent);
      for (const item of data['@graph']) {
        if (item['@type'] === 'WebPage') Object.assign(item, { '@id': `${url}#page`, url, name: this.t('seoTitle'), description: this.t('seoDescription'), inLanguage: this.locale });
        if (item['@type'] === 'WebApplication') Object.assign(item, { url, description: this.t('seoDescription') });
        if (item['@type'] === 'FAQPage') Object.assign(item, { '@id': `${url}#faq`, inLanguage: this.locale, mainEntity: [1, 2, 3, 4].map(i => ({ '@type': 'Question', name: this.t(`faq${i}Q`), acceptedAnswer: { '@type': 'Answer', text: this.t(`faq${i}A`) } })) });
      }
      schema.textContent = JSON.stringify(data);
    },
    setLanguage(locale) { this.locale = locale; history.replaceState(null, '', `/${locale}${location.hash}`); this.updateLanguage(); try { localStorage.setItem('nomark-language', locale); } catch {} this.error = ''; this.notice = ''; },
    useIndonesian() { this.setLanguage('id'); }, useEnglish() { this.setLanguage('en'); },
    changeTheme(event) { NoMarkAppearance.set(event.target.value); },
    get privacyHref() { return `/${this.locale}/privacy`; }, get termsHref() { return `/${this.locale}/terms`; },
    get isIndonesian() { return this.locale === 'id'; }, get isEnglish() { return this.locale === 'en'; },
    get isTextTab() { return this.tab === 'text'; }, get isFileTab() { return this.tab === 'file'; },
    get textTabClass() { return this.isTextTab ? 'selected' : ''; }, get fileTabClass() { return this.isFileTab ? 'selected' : ''; },
    get textTabIndex() { return this.isTextTab ? 0 : -1; }, get fileTabIndex() { return this.isFileTab ? 0 : -1; },
    setTextTab() { if (!this.busy) { this.tab = 'text'; this.error = ''; } }, setFileTab() { if (!this.busy) { this.tab = 'file'; this.error = ''; } },
    tabKey(event) { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); if (this.busy) return; this.tab = event.key === 'Home' ? 'text' : event.key === 'End' ? 'file' : this.isTextTab ? 'file' : 'text'; document.getElementById(`${this.tab}-tab`).focus(); } },
    get notBusy() { return !this.busy; }, get characterCount() { return Array.from(this.input).length.toLocaleString(this.locale); },
    get characterLimit() { return (200000).toLocaleString(this.locale); },
    get cannotCleanText() { return this.busy || !this.input.trim(); }, get cannotClear() { return this.busy || !this.input; },
    get hasNoTextResult() { return !this.textResult; }, get cleanedText() { return this.textResult?.cleaned_text || ''; },
    get cleanedCount() { return Array.from(this.cleanedText).length.toLocaleString(this.locale); }, get textStatus() { return this.textResult ? this.statusLabel(this.textResult.status) : ''; },
    get cleanButtonLabel() { return this.t(this.busy ? 'processing' : 'cleanText'); }, get fileButtonLabel() { return this.t(this.busy ? 'processing' : 'cleanFiles'); },
    get hasFiles() { return this.files.length > 0; }, get cannotCleanFiles() { return this.busy || !this.files.some(entry => !entry.result); },
    get hasPdfFiles() { return this.files.some(entry => /\.pdf$/i.test(entry.name) && !entry.result); },
    processingRoute(entry) { return this.t(/\.pdf$/i.test(entry.name) ? 'serverRoute' : 'localRoute'); },
    get resultLocation() { return this.activeResult ? this.t(this.activeResult.processed_by === 'browser' ? 'localRoute' : 'serverLocation') : ''; },
    get fileFormats() { return {
      documents: 'txt,md,markdown,html,htm,pdf,docx,xlsx,pptx,odt,epub,tex,latex',
      images: 'png,jpg,jpeg,webp,gif,bmp,tif,tiff,avif,heic,heif,svg',
      audio: 'wav,mp3,flac,m4a', video: 'mp4,mov,m4v',
    }; },
    get acceptedFormats() { return this.fileFormats[this.formatCategory].split(',').map(extension => `.${extension}`).join(','); },
    get supportedFormats() { return this.fileFormats[this.formatCategory].split(',').join(' · ').toUpperCase(); },
    get fileMethod() { return this.t(`${this.formatCategory}Method`); },
    categoryFor(name) { const suffix = name.split('.').pop().toLowerCase(); return Object.keys(this.fileFormats).find(category => this.fileFormats[category].split(',').includes(suffix)) || 'documents'; },
    get dropClass() { return this.dragging ? 'dragging' : ''; },
    get activeResult() { return this.isTextTab ? this.textResult : this.selectedFileResult; },
    get reportTiming() { return this.activeResult ? `${(this.activeResult.elapsed_ms / 1000).toLocaleString(this.locale, { maximumFractionDigits: 2 })} s` : ''; },
    get reportSummary() {
      if (!this.activeResult) return '';
      if (this.activeResult.status === 'partial') return this.t('documentPartial');
      if (this.activeResult.status === 'unchanged') return this.t('noChanges');
      const stats = this.activeResult.report.stats;
      return stats ? `${this.t('removed')}: ${stats.removed_count}. ${this.t('replaced')}: ${stats.replaced_count}.` : this.t('documentChanged');
    },
    get reportWarnings() { return (this.activeResult?.report.warnings || []).map(key => this.t(key)); },
    get characterChanges() {
      const stats = this.activeResult?.report.stats;
      if (!stats) return [];
      return [...Object.entries(stats.removed).map(([label, count]) => ({ label, count, action: this.t('removed') })), ...Object.entries(stats.replaced).map(([label, count]) => ({ label, count, action: this.t('replaced') }))];
    },
    get hasCharacterChanges() { return this.characterChanges.length > 0; },
    get reportDetails() { const report = this.activeResult?.report; return report ? [...new Set([...(report.actions || []), ...(report.before.findings || []), ...(report.after.notes || [])])] : []; },
    get hasReportDetails() { return this.reportDetails.length > 0; },
    get historyIsEmpty() { return this.history.length === 0; }, get cannotClearHistory() { return this.busy || this.historyIsEmpty; },
    get historyCountLabel() { return `${this.history.length} / 20`; }, get historyStorageLabel() { const size = this.history.reduce((sum, item) => sum + item.size, 0); return `${this.t('historyLimit')} (${this.formatBytes(size)})`; },
    statusLabel(status) { return this.t({ cleaned: 'cleanedStatus', unchanged: 'unchangedStatus', partial: 'partialStatus', ready: 'readyStatus', processing: 'processingStatus', failed: 'failedStatus' }[status] || 'readyStatus'); },
    dismissNotice() { this.notice = ''; }, dismissError() { this.error = ''; },
    invalidateResult() { this.textResult = null; this.error = ''; },
    loadSample() { this.input = this.locale === 'id' ? 'Halo\u200bdunia!\n\nIni\u00a0contoh teks dengan karakter\u200b tersembunyi dan spasi\u2003khusus.\nEmoji tetap utuh: 👩‍💻 🌿\n\nKata-katamu tetap milikmu.' : 'Hello\u200bworld!\n\nThis\u00a0sample has hidden\u200b characters and unusual\u2003spaces.\nEmoji stay intact: 👩‍💻 🌿\n\nYour words stay your words.'; this.invalidateResult(); },
    clearText() { this.input = ''; this.invalidateResult(); document.getElementById('source-text').focus(); },
    async cleanText() {
      if (this.busy) return;
      if (!this.input.trim()) { this.error = this.t('empty_text'); return; }
      if (Array.from(this.input).length > 200000) { this.error = this.t('text_too_large'); return; }
      const source = this.input;
      this.busy = true; this.cancelled = false; this.error = ''; this.notice = ''; this.stage = this.t('localLoading');
      try {
        this.textResult = await NoMarkProcessor.run('text', source, stage => { this.stage = this.t(stage); });
        await this.saveHistory({ id: newId(), created: Date.now(), mode: 'text', title: source.slice(0, 100), inputText: source, result: this.textResult });
      } catch (error) { if (error.message === 'cancelled') this.notice = this.t('cancelled'); else this.error = this.t(error.message); }
      finally { this.busy = false; this.stage = ''; }
    },
    async copyText() {
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(this.cleanedText);
        else {
          const field = document.getElementById('cleaned-text');
          const previous = document.activeElement;
          field.focus(); field.select();
          const copied = document.execCommand('copy');
          previous?.focus();
          if (!copied) throw new Error('copy_failed');
        }
        this.notice = this.t('copied');
      } catch { this.notice = this.t('copyFailed'); }
    },
    downloadText() { if (this.textResult) download(new Blob([this.cleanedText], { type: 'text/plain;charset=utf-8' }), 'text.cleaned.txt'); },
    dragEnter() { if (!this.busy) this.dragging = true; }, dragLeave() { this.dragging = false; },
    dropFiles(event) { this.dragging = false; if (!this.busy) this.addFiles(event.dataTransfer.files); },
    pickFiles(event) { if (!this.busy) this.addFiles(event.target.files); event.target.value = ''; },
    addFiles(list) {
      this.error = '';
      for (const file of list) {
        if (this.files.length >= 5) { this.error = this.t('tooManyFiles'); break; }
        const suffix = file.name.split('.').pop().toLowerCase();
        if (!Object.values(this.fileFormats).some(formats => formats.split(',').includes(suffix))) { this.error = this.t('unsupported_format'); continue; }
        if (file.size > 20 * 1024 * 1024) { this.error = this.t('file_too_large'); continue; }
        if (!file.size) { this.error = this.t('empty_file'); continue; }
        this.files.push({ id: newId(), file, name: file.name, size: file.size, result: null, status: 'ready', error: '' });
      }
    },
    removeFile(id) { if (!this.busy) { const selected = this.files.find(entry => entry.id === id); if (selected?.result === this.selectedFileResult) this.selectedFileResult = null; this.files = this.files.filter(entry => entry.id !== id); } },
    removeLabel(entry) { return `${this.t('delete')}: ${entry.name}`; },
    viewFile(id) { this.selectedFileResult = this.files.find(entry => entry.id === id)?.result || null; },
    fileMeta(entry) { return `${this.formatBytes(entry.size)} · ${this.statusLabel(entry.status)}`; },
    async cleanFiles() {
      if (this.busy) return;
      if (this.hasPdfFiles && !this.allowServer) { this.error = this.t('pdfConsentNeeded'); return; }
      this.busy = true; this.cancelled = false; this.error = ''; this.notice = '';
      const pending = this.files.filter(entry => !entry.result);
      for (let index = 0; index < pending.length; index++) {
        const entry = pending[index];
        if (this.cancelled) break;
        entry.status = 'processing'; entry.error = '';
        try {
          const progress = (stage, position) => { this.stage = `${this.t(stage)}${position ? ` ${position}` : ''} · ${entry.name}`; };
          const result = /\.pdf$/i.test(entry.name) ? await NoMarkProcessor.serverFile(entry.file, progress) : await NoMarkProcessor.run('file', entry.file, progress);
          const outputBlob = toBlob(result.cleaned_base64, result.mime);
          delete result.cleaned_base64;
          entry.result = { ...result, outputBlob }; entry.status = result.status;
          this.selectedFileResult = entry.result;
          await this.saveHistory({ id: newId(), created: Date.now(), mode: 'file', title: entry.name, sourceName: entry.name, sourceBlob: entry.file, outputBlob, result });
        } catch (error) { if (error.message === 'cancelled') { entry.status = 'ready'; this.notice = this.t('cancelled'); break; } entry.status = 'failed'; entry.error = this.t(error.message); }
      }
      this.busy = false; this.stage = '';
    },
    cancelProcessing() { this.cancelled = true; NoMarkProcessor.cancel(); },
    downloadFile(id) { const result = this.files.find(entry => entry.id === id)?.result; if (result) download(result.outputBlob, result.cleaned_name); },
    formatBytes(value) { return value >= 1024 * 1024 ? `${(value / (1024 * 1024)).toLocaleString(this.locale, { maximumFractionDigits: 1 })} MiB` : value >= 1024 ? `${(value / 1024).toLocaleString(this.locale, { maximumFractionDigits: 1 })} KiB` : `${value} B`; },
    async refreshHistory() { try { this.history = await NoMarkHistory.list(); } catch { this.notice = this.t('storageFailed'); } },
    async saveHistory(record) { try { const evicted = await NoMarkHistory.save(record); await this.refreshHistory(); if (evicted) this.notice = this.t('storageEvicted'); } catch { this.notice = this.t('storageFailed'); } },
    itemType(item) { return this.t(item.mode === 'text' ? 'textTab' : 'fileTab'); },
    itemTitle(item) { return item.title; },
    itemDate(item) { return new Intl.DateTimeFormat(this.locale, { dateStyle: 'medium', timeStyle: 'short' }).format(item.created); },
    deleteLabel(item) { return `${this.t('delete')}: ${item.title}`; },
    async restore(id) {
      if (this.busy) return;
      try {
        const record = await NoMarkHistory.get(id);
        if (!record) { this.notice = this.t('historyMissing'); await this.refreshHistory(); return; }
        this.tab = record.mode;
        if (record.mode === 'text') { this.input = record.inputText; this.textResult = record.result; }
        else { this.formatCategory = this.categoryFor(record.sourceName); const result = { ...record.result, outputBlob: record.outputBlob }; this.files = [{ id: record.id, name: record.sourceName, size: record.sourceBlob.size, file: new File([record.sourceBlob], record.sourceName), status: result.status, result, error: '' }]; this.selectedFileResult = result; }
        this.error = ''; this.notice = this.t('pendingResult');
      } catch { this.notice = this.t('storageFailed'); }
    },
    async downloadHistory(id) { try { const record = await NoMarkHistory.get(id); if (!record) { this.notice = this.t('historyMissing'); return; } if (record.mode === 'text') download(new Blob([record.result.cleaned_text], { type: 'text/plain;charset=utf-8' }), 'text.cleaned.txt'); else download(record.outputBlob, record.result.cleaned_name); } catch { this.notice = this.t('storageFailed'); } },
    async deleteHistory(id) { try { await NoMarkHistory.remove(id); await this.refreshHistory(); } catch { this.notice = this.t('storageFailed'); } },
    requestClearHistory() { this.$refs.confirmDialog.showModal(); }, cancelClearHistory() { this.$refs.confirmDialog.close(); },
    async clearHistory() { try { await NoMarkHistory.clear(); await this.refreshHistory(); this.notice = this.t('historyCleared'); } catch { this.notice = this.t('storageFailed'); } this.$refs.confirmDialog.close(); },
  }));
});
