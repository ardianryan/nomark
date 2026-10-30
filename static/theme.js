(() => {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  let mode = 'system';
  try { mode = localStorage.getItem('nomark-theme') || 'system'; } catch {}
  function apply(value, persist = false) {
    mode = ['system', 'light', 'dark'].includes(value) ? value : 'system';
    document.documentElement.dataset.theme = mode === 'system' ? (media.matches ? 'dark' : 'light') : mode;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = document.documentElement.dataset.theme === 'dark' ? '#171d1a' : '#f7f5ef';
    if (persist) try { localStorage.setItem('nomark-theme', mode); } catch {}
    window.dispatchEvent(new CustomEvent('nomark-theme', { detail: mode }));
  }
  window.NoMarkAppearance = { get mode() { return mode; }, set(value) { apply(value, true); } };
  media.addEventListener('change', () => apply(mode));
  window.addEventListener('storage', event => { if (event.key === 'nomark-theme') apply(event.newValue); });
  apply(mode);
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-control]').forEach(select => {
      select.value = mode;
      select.addEventListener('change', event => apply(event.target.value, true));
      window.addEventListener('nomark-theme', event => { select.value = event.detail; });
    });
  });
})();
