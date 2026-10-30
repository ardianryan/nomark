document.addEventListener('alpine:init', () => {
  Alpine.data('paraphraseEditor', () => ({
    source: '', result: null, language: '', consent: false, available: false,
    controller: null, ticket: null, timedOut: false,
    async init() {
      this.language = this.locale;
      window.addEventListener('nomark-cancel-paraphrase', () => this.cancel());
      window.addEventListener('nomark-restore-paraphrase', event => {
        this.source = event.detail.inputText; this.result = event.detail.result;
        this.language = event.detail.language; this.consent = false;
      });
      await this.refreshAvailability();
    },
    async refreshAvailability() {
      try { const response = await fetch('/api/paraphrase/capabilities'); this.available = response.ok && (await response.json()).available; }
      catch { this.available = false; }
    },
    get count() { return Array.from(this.source).length.toLocaleString(this.locale); },
    get limitLabel() { return (5000).toLocaleString(this.locale); },
    get output() { return this.result?.paraphrased_text || ''; },
    get noResult() { return !this.result; },
    get cannotParaphrase() { return this.busy || !this.available || !this.source.trim(); },
    get resultSummary() { return this.result ? this.t(this.result.status === 'partial' ? 'paraphrasePartial' : this.result.status === 'unchanged' ? 'noChanges' : 'paraphraseChanged') : ''; },
    get unavailable() { return !this.available; },
    invalidate() { this.result = null; },
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
      if (this.busy) return;
      if (!this.consent) { this.error = this.t('paraphraseConsentNeeded'); return; }
      if (Array.from(this.source).length > 5000) { this.error = this.t('paraphraseTooLong'); return; }
      if (!this.source.trim()) { this.error = this.t('empty_text'); return; }
      const source = this.source, language = this.language;
      this.busy = true; this.error = ''; this.notice = ''; this.result = null;
      this.timedOut = false;
      this.controller = new AbortController();
      let timer;
      try {
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
        this.result = await this.api('/api/text/paraphrase', { method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-NoMark-Reservation': this.ticket },
          body: JSON.stringify({ text: source, language }) });
        await this.saveHistory({ id: newId(), created: Date.now(), mode: 'paraphrase',
          title: source.slice(0, 100), inputText: source, language, result: this.result });
      } catch (error) {
        if (error.name === 'AbortError') { if (this.timedOut) this.error = this.t('paraphrase_timeout'); else this.notice = this.t('cancelled'); }
        else this.error = this.t(error.message);
      } finally {
        clearTimeout(timer); await this.release(); this.controller = null;
        this.busy = false; this.stage = '';
      }
    },
    async copy() {
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(this.output);
        else { this.$refs.output.focus(); this.$refs.output.select(); if (!document.execCommand('copy')) throw new Error(); }
        this.notice = this.t('copied');
      } catch { this.notice = this.t('copyFailed'); }
    },
    download() { if (this.result) download(new Blob([this.output], { type: 'text/plain;charset=utf-8' }), 'text.paraphrased.txt'); },
  }));
});
