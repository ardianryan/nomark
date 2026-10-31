const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test('paraphrase consent, waiting without text upload, output and history', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { configurable: true,
    value: { writeText: async value => { window.testClipboard = value; }, readText: async () => window.testClipboard } }));
  let uploaded = 0, polls = 0, cancelled = 0;
  await page.route('**/api/paraphrase/capabilities', route => route.fulfill({ json: { ok: true, available: true } }));
  await page.route('**/api/paraphrase/queue', route => {
    const method = route.request().method();
    if (method === 'DELETE') { cancelled++; return route.fulfill({ json: { ok: true } }); }
    if (method === 'POST') return route.fulfill({ json: { ok: true, token: 'synthetic', state: 'waiting' } });
    polls++;
    expect(uploaded).toBe(0);
    return route.fulfill({ json: { ok: true, state: 'ready' } });
  });
  await page.route('**/api/text/paraphrase', route => {
    uploaded++;
    expect(route.request().postDataJSON()).toEqual({ text: 'An original sentence.', language: 'en' });
    return route.fulfill({ json: { ok: true, paraphrased_text: 'A rewritten sentence.', language: 'en', status: 'paraphrased', warnings: ['review_required'], elapsed_ms: 30, processed_by: 'server' } });
  });
  await page.goto('/en');
  await page.getByRole('tab', { name: 'Paraphrase', exact: true }).click();
  await page.getByLabel('Text to paraphrase', { exact: true }).fill('An original sentence.');
  await page.getByRole('button', { name: 'Paraphrase text', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Allow text');
  expect(uploaded).toBe(0);
  await page.getByRole('checkbox', { name: /I allow this text/ }).check();
  await page.getByRole('button', { name: 'Paraphrase text', exact: true }).click();
  await expect(page.locator('.process-status')).toContainText('stays on your device');
  expect(uploaded).toBe(0);
  await expect(page.getByLabel('Paraphrased text', { exact: true })).toHaveText('A rewritten sentence.');
  expect(polls).toBe(1);
  const section = page.locator('#paraphrase-panel');
  await section.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('A rewritten sentence.');
  const download = page.waitForEvent('download');
  await section.getByRole('button', { name: 'Download .txt' }).click();
  expect((await download).suggestedFilename()).toBe('text.paraphrased.txt');
  await page.reload();
  await page.locator('.history-item').click();
  await expect(page.getByLabel('Paraphrased text', { exact: true })).toHaveText('A rewritten sentence.');
  await expect(page.getByRole('checkbox', { name: /I allow this text/ })).not.toBeChecked();
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axe.violations.map(item => item.id)).toEqual([]);
  await page.setViewportSize({ width: 320, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(cancelled).toBeGreaterThan(0);
});

test('unavailable paraphrasing leaves local cleaning available', async ({ page }) => {
  await page.route('**/api/paraphrase/capabilities', route => route.fulfill({ json: { ok: true, available: false } }));
  await page.goto('/id');
  await page.getByRole('tab', { name: 'Parafrasa', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Parafrasakan teks' })).toBeDisabled();
  await page.getByRole('tab', { name: 'Teks', exact: true }).click();
  await page.getByLabel('Teks asli', { exact: true }).fill('Halo\u200bdunia');
  await page.getByRole('button', { name: 'Bersihkan teks', exact: true }).click();
  await expect(page.getByLabel('Hasil bersih', { exact: true })).toHaveValue('Halodunia');
});

test('cancelling a waiting paraphrase releases its ticket without sending text', async ({ page }) => {
  let uploads = 0, released = 0;
  await page.route('**/api/paraphrase/capabilities', route => route.fulfill({ json: { ok: true, available: true } }));
  await page.route('**/api/paraphrase/queue', route => {
    if (route.request().method() === 'DELETE') { released++; return route.fulfill({ json: { ok: true } }); }
    return route.fulfill({ json: { ok: true, token: 'waiting', state: 'waiting' } });
  });
  await page.route('**/api/text/paraphrase', route => { uploads++; return route.abort(); });
  await page.goto('/en');
  await page.getByRole('tab', { name: 'Paraphrase', exact: true }).click();
  await page.getByLabel('Text to paraphrase', { exact: true }).fill('Keep my original draft.');
  await page.getByRole('checkbox', { name: /I allow this text/ }).check();
  await page.getByRole('button', { name: 'Paraphrase text', exact: true }).click();
  await expect(page.locator('.process-status')).toContainText('stays on your device');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.notice')).toContainText('cancelled');
  await expect(page.getByLabel('Text to paraphrase', { exact: true })).toHaveValue('Keep my original draft.');
  expect(uploads).toBe(0);
  expect(released).toBeGreaterThan(0);
});
