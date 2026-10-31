const { test, expect } = require('@playwright/test');
const { readFile } = require('node:fs/promises');
const AxeBuilder = require('@axe-core/playwright').default;

const source = '🙂 We cannot proceed. We cannot stop.';
const model = "🙂 We can't proceed. We can't stop.";
const cp = text => Array.from(text).length;
function metadata() {
  let a = 0, b = 0;
  return [0, 1].map(index => {
    a = source.indexOf('cannot', a); b = model.indexOf("can't", b);
    const value = { id: `edit-${index}`, input_start: cp(source.slice(0, a)), input_end: cp(source.slice(0, a + 6)),
      output_start: cp(model.slice(0, b)), output_end: cp(model.slice(0, b + 5)), before: 'cannot', after: "can't", alternatives: ['can not'] };
    a += 6; b += 5;
    return value;
  });
}

async function openEditor(page, options = {}) {
  let posts = 0;
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { configurable: true,
    value: { writeText: async value => { window.testClipboard = value; } } }));
  if (options.workerFailure) await page.addInitScript(() => {
    const Original = window.Worker;
    window.Worker = class extends Original {
      constructor(url, settings) { if (String(url).includes('changes-worker')) throw new Error('synthetic worker failure'); super(url, settings); }
    };
  });
  await page.route('**/api/paraphrase/capabilities', route => route.fulfill({ json: { ok: true, available: true } }));
  await page.route('**/api/paraphrase/queue', route => {
    if (route.request().method() === 'POST') return route.fulfill({ json: { ok: true, token: 'synthetic', state: 'ready' } });
    return route.fulfill({ json: { ok: true } });
  });
  await page.route('**/api/text/paraphrase', route => {
    posts++;
    return route.fulfill({ json: { ok: true, paraphrased_text: model, language: 'en',
      status: 'paraphrased', warnings: ['review_required'], edits: metadata(), processed_by: 'server' } });
  });
  await page.goto('/en');
  await page.getByRole('tab', { name: 'Paraphrase', exact: true }).click();
  await page.getByLabel('Text to paraphrase', { exact: true }).fill(source);
  await page.getByRole('checkbox', { name: /I allow this text/ }).check();
  await page.getByRole('button', { name: 'Paraphrase text', exact: true }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText(model);
  return { posts: () => posts, errors, panel: page.locator('#paraphrase-panel') };
}

test('suggestions preserve Unicode positions after replacement, restore and reset', async ({ page }) => {
  // Measure dialog movement independently of the page's smooth focus scrolling.
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const session = await openEditor(page);
  const choices = page.getByRole('button', { name: "Word choices: can't", exact: true });
  await expect(choices).toHaveCount(2);
  await choices.first().focus();
  const scrollBefore = await page.evaluate(() => scrollY);
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Word choices', exact: true });
  await expect(dialog).toBeVisible();
  expect(await page.evaluate(() => scrollY)).toBe(scrollBefore);
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(axe.violations.map(item => item.id)).toEqual([]);
  await page.keyboard.press('Escape');
  await expect(choices.first()).toBeFocused();
  await choices.first().click();
  await dialog.getByRole('button', { name: 'can not', exact: true }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText("🙂 We can not proceed. We can't stop.");
  await choices.first().click();
  await dialog.getByRole('button', { name: 'can not', exact: true }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText('🙂 We can not proceed. We can not stop.');
  await page.getByRole('button', { name: 'Word choices: can not', exact: true }).first().click();
  await dialog.getByRole('button', { name: 'Restore original text' }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText('🙂 We cannot proceed. We can not stop.');
  await session.panel.getByRole('button', { name: 'Restore initial result' }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText(model);
  await expect(page.locator('.history-list li')).toHaveCount(1);
  expect(session.posts()).toBe(1);
  expect(session.errors).toEqual([]);
});

test('manual edits preserve untouched suggestions, export latest text and restore history', async ({ page }) => {
  const session = await openEditor(page);
  await session.panel.getByRole('button', { name: 'Edit text', exact: true }).click();
  const edited = "First 🙂 We will proceed. We can't stop.";
  await page.getByLabel('Edit text', { exact: true }).fill(edited);
  await session.panel.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText(edited);
  const untouched = page.getByRole('button', { name: "Word choices: can't", exact: true });
  await expect(untouched).toHaveCount(1);
  await untouched.click();
  await page.getByRole('dialog').getByRole('button', { name: 'can not', exact: true }).click();
  const final = 'First 🙂 We will proceed. We can not stop.';
  await expect(page.locator('#paraphrase-output')).toHaveText(final);
  await session.panel.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => window.testClipboard)).toBe(final);
  const download = page.waitForEvent('download');
  await session.panel.getByRole('button', { name: 'Download .txt', exact: true }).click();
  expect(await readFile(await (await download).path(), 'utf8')).toBe(final);
  await expect(page.locator('.history-list li')).toHaveCount(1);
  await page.reload();
  await page.locator('.history-item').click();
  await expect(page.locator('#paraphrase-output')).toHaveText(final);
  await session.panel.getByRole('button', { name: 'Edit text', exact: true }).click();
  await page.getByLabel('Edit text', { exact: true }).fill('Discard this draft.');
  await session.panel.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText(final);
  await session.panel.getByRole('button', { name: 'Restore initial result' }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText(model);
  expect(session.posts()).toBe(1);
  expect(session.errors).toEqual([]);
});

test('draft autosave survives reload and deleted text never enters export', async ({ page }) => {
  const session = await openEditor(page);
  await session.panel.getByRole('button', { name: 'Edit text', exact: true }).click();
  await page.getByLabel('Edit text', { exact: true }).fill('🙂 We proceed.');
  await expect.poll(() => page.evaluate(async () => (await NoMarkHistory.get((await NoMarkHistory.list())[0].id)).result.paraphrased_text)).toBe('🙂 We proceed.');
  await page.reload();
  await page.locator('.history-item').click();
  await expect(page.locator('#paraphrase-output')).toContainText('🙂 We proceed.');
  await session.panel.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => window.testClipboard)).toBe('🙂 We proceed.');
  await session.panel.getByRole('button', { name: 'Edit text', exact: true }).click();
  await page.getByLabel('Edit text', { exact: true }).fill('');
  await session.panel.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Word choices: Deleted text' })).toBeVisible();
  await session.panel.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => window.testClipboard)).toBe('');
  expect(session.posts()).toBe(1);
  expect(session.errors).toEqual([]);
});

test('legacy history highlights literal HTML as text without executing it', async ({ page }) => {
  const session = await openEditor(page);
  await page.evaluate(async () => {
    await NoMarkHistory.save({ id: 'legacy', created: Date.now() + 100, mode: 'paraphrase',
      title: 'Legacy record', language: 'en', inputText: 'Original text.',
      result: { paraphrased_text: '<img src=x onerror="window.injected=true">', status: 'paraphrased' } });
  });
  await page.reload();
  await page.locator('.history-item').filter({ hasText: 'Legacy record' }).click();
  await expect(page.locator('#paraphrase-output')).toContainText('<img src=x onerror="window.injected=true">');
  await expect(page.locator('#paraphrase-output img')).toHaveCount(0);
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  expect(session.posts()).toBe(1);
  expect(session.errors).toEqual([]);
});

test('worker failure and storage failure preserve an editable result and enforce the local limit', async ({ page }) => {
  const session = await openEditor(page, { workerFailure: true });
  await expect(page.locator('.changed-phrase')).toHaveCount(0);
  await page.evaluate(() => { NoMarkHistory.save = async () => { throw new Error('synthetic quota'); }; });
  await session.panel.getByRole('button', { name: 'Edit text', exact: true }).click();
  await page.getByLabel('Edit text', { exact: true }).fill('x'.repeat(50001));
  await expect(session.panel.getByRole('button', { name: 'Done', exact: true })).toBeDisabled();
  await expect(session.panel.getByRole('button', { name: 'Download .txt', exact: true })).toBeDisabled();
  await page.getByLabel('Edit text', { exact: true }).fill('A manually edited result.');
  await session.panel.getByRole('button', { name: 'Done', exact: true }).click();
  await expect(page.locator('#paraphrase-output')).toHaveText('A manually edited result.');
  await expect(page.locator('.notice')).toContainText('History could not be saved');
  await session.panel.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => window.testClipboard)).toBe('A manually edited result.');
  expect(session.posts()).toBe(1);
  expect(session.errors).toEqual([]);
});

test('workspace copy stays concise in both languages and suggestions fit mobile dark mode', async ({ page }) => {
  const session = await openEditor(page);
  await expect(session.panel).not.toContainText('local model');
  await expect(session.panel).not.toContainText('SynthID');
  await expect(session.panel).not.toContainText('API');
  await expect(page.locator('.mode-note')).toHaveCount(0);
  await page.getByRole('button', { name: 'ID', exact: true }).click();
  await expect(session.panel).toContainText('Ubah susunan teks, lalu sesuaikan hasilnya.');
  await expect(session.panel).toContainText('Tinjau kembali makna, fakta, nama, dan ejaan hasil sebelum digunakan.');
  await expect(session.panel).not.toContainText('EYD V');
  await page.getByLabel('Tema', { exact: true }).selectOption('dark');
  await page.setViewportSize({ width: 320, height: 800 });
  await page.getByRole('button', { name: "Pilihan kata: can't", exact: true }).first().click();
  const box = await page.getByRole('dialog', { name: 'Pilihan kata' }).boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(320);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(session.errors).toEqual([]);
});

test('new input preserves the old draft and deleting history does not resurrect it', async ({ page }) => {
  const session = await openEditor(page);
  await session.panel.getByRole('button', { name: 'Edit text', exact: true }).click();
  await page.getByLabel('Edit text', { exact: true }).fill('Keep this locally.');
  await page.getByLabel('Text to paraphrase', { exact: true }).fill('New input.');
  await expect.poll(() => page.evaluate(async () => {
    const list = await NoMarkHistory.list();
    const item = await NoMarkHistory.get(list[0].id);
    return [item.inputText, item.result.paraphrased_text, item.language];
  })).toEqual([source, 'Keep this locally.', 'en']);
  await page.locator('.history-item').click();
  await expect(page.locator('#paraphrase-output')).toContainText('Keep this locally.');
  await page.getByRole('button', { name: /^Delete:/ }).click();
  await expect(page.locator('.history-list li')).toHaveCount(0);
  await session.panel.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => NoMarkHistory.list())).toEqual([]);
  expect(session.posts()).toBe(1);
  expect(session.errors).toEqual([]);
});
