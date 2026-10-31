document.addEventListener('alpine:init', () => {
  Alpine.data('paraphraseEditor', () => ({
    source: '', result: null, language: '', consent: false, available: false,
    controller: null, ticket: null, timedOut: false,
    editing: false, finishing: false, draft: '', modelText: '', inputSnapshot: '',
    chunks: [], anchors: [], selectedChange: null, suggestions: [],
    recordId: null, recordLanguage: '', created: 0, saveTimer: null, saveChain: Promise.resolve(),
    generation: 0, diffRevision: 0,
    async init() {
      this.language = this.locale;
      this.differ = NoMarkChanges.createDiffer();
      this.mapper = NoMarkChanges.createDiffer();
      window.NoMarkParaphraseFlush = () => this.flushSave();
      window.addEventListener('pagehide', () => this.flushSave());
      document.addEventListener('visibilitychange', () => { if (document.hidden) this.flushSave(); });
      window.addEventListener('nomark-history-removed', event => {
        if (!event.detail || event.detail === this.recordId) { clearTimeout(this.saveTimer); this.recordId = null; }
      });
      window.addEventListener('nomark-cancel-paraphrase', () => this.cancel());
      window.addEventListener('nomark-restore-paraphrase', event => {
        this.loadRecord(event.detail);
      });
      await this.refreshAvailability();
    },
    async refreshAvailability() {
      try { const response = await fetch('/api/paraphrase/capabilities'); this.available = response.ok && (await response.json()).available; }
      catch { this.available = false; }
    },
    get count() { return Array.from(this.source).length.toLocaleString(this.locale); },
    get limitLabel() { return (5000).toLocaleString(this.locale); },
    get output() { return this.editing ? this.draft : this.result?.paraphrased_text || ''; },
    get draftTooLong() { return this.editing && NoMarkChanges.length(this.draft) > 50000; },
    get cannotExport() { return this.noResult || this.finishing || this.draftTooLong; },
    get cannotEdit() { return this.noResult || this.busy || this.finishing; },
    get cannotReset() { return this.cannotEdit || this.output === this.modelText; },
    get showResult() { return !!this.result && !this.editing; },
    get selectedBefore() { return this.selectedChange?.before || ''; },
    get hasSuggestions() { return this.suggestions.length > 0; },
    get noResult() { return !this.result; },
    get cannotParaphrase() { return this.busy || this.finishing || !this.available || !this.source.trim(); },
    get resultSummary() { return !this.result ? '' : this.output === this.inputSnapshot ? this.t('noChanges') : this.output !== this.modelText ? this.t('resultEdited') : this.t('paraphraseChanged'); },
    get unavailable() { return !this.available; },
    invalidate() {
      this.flushSave(); this.closeSuggestions(); this.generation++; this.diffRevision++;
      this.differ.cancel(); this.mapper.cancel(); this.result = null; this.recordId = null;
      this.editing = false; this.chunks = []; this.anchors = [];
    },
    async loadRecord(record) {
      this.closeSuggestions();
      const generation = ++this.generation;
      this.diffRevision++; this.differ.cancel(); this.mapper.cancel(); this.editing = false;
      this.source = record.inputText; this.inputSnapshot = record.inputText;
      this.result = JSON.parse(JSON.stringify(record.result));
      this.language = record.language; this.consent = false;
      this.recordId = record.id; this.created = record.created;
      this.recordLanguage = record.language;
      const saved = this.result.editor;
      this.modelText = typeof saved?.model_text === 'string' ? saved.model_text : this.output;
      const base = NoMarkChanges.anchors(this.result.edits, this.inputSnapshot, this.modelText);
      this.anchors = base;
      if (saved) {
        const anchorText = typeof saved.anchor_text === 'string' ? saved.anchor_text : this.modelText;
        let end = 0;
        this.anchors = base.flatMap(anchor => {
          const value = Array.isArray(saved.anchors) && saved.anchors.find(item => item.id === anchor.id);
          if (!value || !Number.isInteger(value.start) || !Number.isInteger(value.end)
              || value.start < end || value.end <= value.start || value.end > NoMarkChanges.length(anchorText)
              || ![anchor.before, anchor.after, ...anchor.alternatives].includes(NoMarkChanges.slice(anchorText, value.start, value.end))) return [];
          end = value.end;
          return [{ ...anchor, start: value.start, end: value.end }];
        });
        if (anchorText !== this.output) {
          const runs = await this.mapper.compare(anchorText, this.output);
          if (generation !== this.generation) return;
          this.anchors = NoMarkChanges.rebase(this.anchors, runs);
        }
      }
      await this.refreshChanges();
    },
    async refreshChanges() {
      const revision = ++this.diffRevision, output = this.output;
      this.chunks = [{ id: 'plain', changed: false, value: output, display: output }];
      const runs = await this.differ.compare(this.inputSnapshot, output, this.anchors);
      if (revision !== this.diffRevision || output !== this.output) return;
      this.chunks = NoMarkChanges.decorate(runs, this.anchors, this.inputSnapshot, output);
    },
    changeLabel(chunk) { return `${this.t('changeOptions')}: ${chunk.value || this.t('deletedText')}`; },
    async openSuggestions(chunk, event) {
      if (this.finishing) return;
      this.selectedChange = chunk; this.suggestionTrigger = event.currentTarget;
      const anchor = this.anchors.find(item => item.id === chunk.anchorId);
      this.suggestions = [...new Set(anchor ? [anchor.after, ...anchor.alternatives] : [])]
        .filter(value => value !== chunk.value && value !== chunk.before);
      await this.$nextTick();
      const dialog = this.$refs.suggestions;
      const rect = this.suggestionTrigger.getBoundingClientRect();
      // Position in the viewport before native dialog focus can scroll the page.
      dialog.style.left = '12px'; dialog.style.top = '12px';
      dialog.showModal();
      dialog.style.left = `${Math.max(12, Math.min(rect.left, innerWidth - dialog.offsetWidth - 12))}px`;
      dialog.style.top = `${Math.max(12, Math.min(rect.bottom + 8, innerHeight - dialog.offsetHeight - 12))}px`;
    },
    closeSuggestions() {
      if (this.$refs.suggestions?.open) {
        this.$refs.suggestions.close();
        if (this.suggestionTrigger?.isConnected) this.suggestionTrigger.focus({ preventScroll: true });
        else this.$refs.outputView?.focus({ preventScroll: true });
      }
      this.selectedChange = null;
    },
    suggestionKey(event) {
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const buttons = [...this.$refs.suggestions.querySelectorAll('button')];
      const index = buttons.indexOf(document.activeElement);
      buttons[event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
        : (index + (event.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length]?.focus();
    },
    async chooseSuggestion(value) {
      const change = this.selectedChange;
      if (!change || (value !== change.before && !this.suggestions.includes(value))) return;
      const size = NoMarkChanges.length(value), delta = size - (change.end - change.start);
      const next = NoMarkChanges.slice(this.output, 0, change.start) + value + NoMarkChanges.slice(this.output, change.end);
      if (NoMarkChanges.length(next) > 50000) return;
      this.anchors = this.anchors.flatMap(anchor => {
        if (anchor.id === change.anchorId) return [{ ...anchor, end: anchor.start + size }];
        if (anchor.end <= change.start) return [anchor];
        if (anchor.start >= change.end) return [{ ...anchor, start: anchor.start + delta, end: anchor.end + delta }];
        return [];
      });
      this.closeSuggestions(); this.result.paraphrased_text = next;
      await this.refreshChanges(); await this.flushSave(); this.$refs.outputView.focus();
    },
    restoreChange() { return this.chooseSuggestion(this.selectedBefore); },
    startEditing() { this.closeSuggestions(); this.draft = this.output; this.editing = true; this.$nextTick(() => this.$refs.manual.focus()); },
    draftChanged() {
      clearTimeout(this.saveTimer);
      if (!this.draftTooLong) this.saveTimer = setTimeout(() => this.flushSave(), 500);
    },
    async finishEditing() {
      if (!this.editing) return true;
      if (this.draftTooLong || this.finishing) return false;
      this.finishing = true;
      const generation = this.generation, previous = this.result.paraphrased_text, next = this.draft;
      try {
        const runs = await this.mapper.compare(previous, next);
        if (generation !== this.generation) return false;
        this.anchors = NoMarkChanges.rebase(this.anchors, runs);
        this.result.paraphrased_text = next; this.editing = false;
        await this.refreshChanges(); await this.flushSave(); this.$refs.outputView.focus();
        return true;
      } finally { this.finishing = false; }
    },
    async cancelEditing() { this.editing = false; this.draft = ''; await this.flushSave(); this.$refs.outputView.focus(); },
    async resetResult() {
      this.editing = false; this.result.paraphrased_text = this.modelText;
      this.anchors = NoMarkChanges.anchors(this.result.edits, this.inputSnapshot, this.modelText);
      await this.refreshChanges(); await this.flushSave();
    },
    async flushSave() {
      clearTimeout(this.saveTimer);
      if (!this.result || !this.recordId || this.draftTooLong) return;
      const result = JSON.parse(JSON.stringify(this.result));
      result.paraphrased_text = this.output;
      result.editor = { model_text: this.modelText, anchor_text: this.result.paraphrased_text,
        anchors: this.anchors.map(({ id, start, end }) => ({ id, start, end })) };
      const record = { id: this.recordId, created: this.created, mode: 'paraphrase',
        title: this.inputSnapshot.slice(0, 100), inputText: this.inputSnapshot, language: this.recordLanguage, result };
      this.saveChain = this.saveChain.then(() => this.saveHistory(record));
      await this.saveChain;
    },
    async api(path, options = {}) {
      let response;
      try { response = await fetch(path, { ...options, signal: this.controller?.signal }); }
      catch (error) { if (error.name === 'AbortError') throw error; throw new Error('paraphrase_unavailable'); }
      let result;
      try { result = await response.json(); } catch { throw new Error('paraphrase_failed'); }
      if (!response.ok) throw new Error(result.error || 'paraphrase_failed');
      return result;
    },
    async release() {
      const ticket = this.ticket; this.ticket = null;
      if (ticket) { try { await fetch('/api/paraphrase/queue', { method: 'DELETE', headers: { Authorization: `Bearer ${ticket}` }, keepalive: true }); } catch {} }
    },
    cancel() { this.controller?.abort(); this.release(); },
    async paraphrase() {
      if (this.busy || this.finishing) return;
      if (!this.consent) { this.error = this.t('paraphraseConsentNeeded'); return; }
      if (Array.from(this.source).length > 5000) { this.error = this.t('paraphraseTooLong'); return; }
      if (!this.source.trim()) { this.error = this.t('empty_text'); return; }
      const source = this.source, language = this.language;
      this.busy = true; this.error = ''; this.notice = '';
      this.timedOut = false;
      this.controller = new AbortController();
      let timer;
      try {
        await this.flushSave();
        this.result = null; this.editing = false;
        this.stage = this.t('paraphraseWaiting');
        const ticket = await this.api('/api/paraphrase/queue', { method: 'POST' });
        this.ticket = ticket.token;
        let state = ticket;
        const waitingDeadline = Date.now() + 180000;
        while (state.state !== 'ready') {
          if (Date.now() > waitingDeadline) throw new Error('queue_expired');
          await new Promise(resolve => setTimeout(resolve, 1000));
          state = await this.api('/api/paraphrase/queue', { headers: { Authorization: `Bearer ${this.ticket}` } });
        }
        timer = setTimeout(() => { this.timedOut = true; this.cancel(); }, 90000);
        this.stage = this.t('paraphraseRunning');
        const result = await this.api('/api/text/paraphrase', { method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-NoMark-Reservation': this.ticket },
          body: JSON.stringify({ text: source, language }) });
        const consent = this.consent;
        await this.loadRecord({ id: newId(), created: Date.now(), inputText: source, language, result });
        this.consent = consent;
        await this.flushSave();
      } catch (error) {
        if (error.name === 'AbortError') { if (this.timedOut) this.error = this.t('paraphrase_timeout'); else this.notice = this.t('cancelled'); }
        else this.error = this.t(error.message);
      } finally {
        clearTimeout(timer); await this.release(); this.controller = null;
        this.busy = false; this.stage = '';
      }
    },
    async copy() {
      if (this.cannotExport) return;
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(this.output);
        else {
          const field = document.createElement('textarea'), focus = document.activeElement;
          field.value = this.output; field.setAttribute('readonly', ''); field.style.position = 'fixed';
          field.style.left = '-10000px'; document.body.append(field);
          try { field.select(); if (!document.execCommand('copy')) throw new Error(); }
          finally { field.remove(); focus?.focus(); }
        }
        await this.finishEditing(); await this.flushSave();
        this.notice = this.t('copied');
      } catch { this.notice = this.t('copyFailed'); }
    },
    async download() {
      if (this.cannotExport || !await this.finishEditing()) return;
      await this.flushSave(); download(new Blob([this.output], { type: 'text/plain;charset=utf-8' }), 'text.paraphrased.txt');
    },
  }));
});
