const { test, expect } = require('@playwright/test');
const fs = require('node:fs/promises');
const AxeBuilder = require('@axe-core/playwright').default;
const { execFileSync } = require('node:child_process');
const python = process.env.NOMARK_TEST_PYTHON || '.venv/bin/python';

test.beforeEach(async ({ page }) => {
  page.errors = [];
  page.on('pageerror', error => page.errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Tidy up hidden traces.' })).toBeVisible();
});

test.afterEach(async ({ page }) => { expect(page.errors).toEqual([]); });

test('cleans text, copies, downloads, restores local history, and deletes it', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByLabel('Original text').fill('Hello\u200bworld 👩‍💻');
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await expect(page.getByLabel('Cleaned text')).toHaveValue('Helloworld 👩‍💻');
  await expect(page.locator('.report-summary')).toContainText('Removed: 1');
  await expect(page.locator('.history-list li')).toHaveCount(1);
  await page.getByRole('button', { name: 'Copy', exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('Helloworld 👩‍💻');
  const downloadEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download .txt', exact: true }).click();
  const download = await downloadEvent;
  expect(await fs.readFile(await download.path(), 'utf8')).toBe('Helloworld 👩‍💻');
  await page.reload();
  await page.locator('.history-item').click();
  await expect(page.getByLabel('Original text')).toHaveValue('Hello\u200bworld 👩‍💻');
  await expect(page.getByLabel('Cleaned text')).toHaveValue('Helloworld 👩‍💻');
  await page.getByRole('button', { name: 'Clear all history', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.history-list li')).toHaveCount(1);
  await page.getByRole('button', { name: 'Clear all history', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Clear all history', exact: true }).click();
  await page.getByRole('button', { name: 'Delete everything', exact: true }).click();
  await expect(page.locator('.history-list li')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.history-list li')).toHaveCount(0);
});

test('uploads a sequential document queue, downloads, and restores files', async ({ page }) => {
  await page.getByRole('tab', { name: 'Files' }).click();
  await page.locator('input[type=file]').setInputFiles([
    { name: 'first.txt', mimeType: 'text/plain', buffer: Buffer.from('Hello\u200bworld') },
    { name: 'second.md', mimeType: 'text/markdown', buffer: Buffer.from('# Halo\u200bdunia') },
  ]);
  await page.getByRole('button', { name: 'Clean files', exact: true }).click();
  await expect(page.locator('.file-row .copy-button').first()).toBeVisible();
  await expect(page.locator('.history-list li')).toHaveCount(2);
  const event = page.waitForEvent('download');
  await page.locator('.file-row .copy-button').first().click();
  const download = await event;
  expect(download.suggestedFilename()).toBe('first.cleaned.txt');
  expect(await fs.readFile(await download.path(), 'utf8')).toBe('Helloworld');
  await page.reload();
  await page.locator('.history-item').filter({ hasText: 'first.txt' }).click();
  await expect(page.locator('.file-row')).toContainText('first.txt');
  await expect(page.getByRole('tab', { name: 'Files' })).toHaveAttribute('aria-selected', 'true');
  await page.locator('.history-item-actions').last().getByRole('button', { name: 'Delete' }).click();
  await expect(page.locator('.history-list li')).toHaveCount(1);
});

test('validates uploads, retains input on network errors, and survives storage failure', async ({ page }) => {
  await page.getByRole('tab', { name: 'Files' }).click();
  await page.locator('input[type=file]').setInputFiles({ name: 'archive.7z', mimeType: 'application/x-7z-compressed', buffer: Buffer.from('unsupported') });
  await expect(page.getByRole('alert')).toContainText('not supported');
  await page.getByRole('tab', { name: 'Text', exact: true }).click();
  await page.getByRole('button', { name: 'Try a sample' }).click();
  const input = await page.getByLabel('Original text').inputValue();
  await page.route('**/static/engine-manifest.json', route => route.abort());
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('local engine could not load');
  await expect(page.getByLabel('Original text')).toHaveValue(input);
  await page.unroute('**/static/engine-manifest.json');
  await page.evaluate(() => { NoMarkHistory.save = async () => { throw new DOMException('Full', 'QuotaExceededError'); }; });
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await expect(page.getByLabel('Cleaned text')).toBeVisible();
  await expect(page.locator('.notice')).toContainText('History could not be saved');
  await expect(page.getByRole('button', { name: 'Download .txt', exact: true })).toBeEnabled();
});

test('language choice persists, keyboard tabs work, and responsive layouts do not overflow', async ({ page }) => {
  await page.getByRole('button', { name: 'ID', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'id');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Bereskan jejak tersembunyi.' })).toBeVisible();
  await page.getByRole('tab', { name: 'Teks' }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Berkas' })).toBeFocused();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('tab', { name: 'Teks' })).toBeFocused();
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 950 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.screenshot({ path: 'artifacts/mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: 'artifacts/desktop.png', fullPage: true });
});

test('history evicts oldest entries atomically at twenty records', async ({ page }) => {
  const result = await page.evaluate(async () => {
    for (let i = 0; i < 21; i++) {
      await NoMarkHistory.save({ id: String(i), created: i, mode: 'text', title: `Entry ${i}`, inputText: 'original', result: { cleaned_text: 'cleaned' } });
    }
    return (await NoMarkHistory.list()).map(entry => entry.id);
  });
  expect(result).toHaveLength(20);
  expect(result).not.toContain('0');
  expect(result[0]).toBe('20');
});

test('uses Indonesian browser language automatically without geolocation requests', async ({ browser }) => {
  const context = await browser.newContext({ locale: 'id-ID' });
  const page = await context.newPage();
  const external = [];
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:8000')) external.push(request.url()); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Bereskan jejak tersembunyi.' })).toBeVisible();
  expect(external).toEqual([]);
  await context.close();
});

test('supports dropping files and enforces the five-file queue limit', async ({ page }) => {
  await page.getByRole('tab', { name: 'Files' }).click();
  const transfer = await page.evaluateHandle(() => {
    const data = new DataTransfer();
    for (let i = 0; i < 6; i++) data.items.add(new File(['Hello'], `document-${i}.txt`, { type: 'text/plain' }));
    return data;
  });
  await page.locator('.dropzone').dispatchEvent('drop', { dataTransfer: transfer });
  await expect(page.locator('.file-row')).toHaveCount(5);
  await expect(page.getByRole('alert')).toContainText('up to 5 files');
  await page.locator('.remove-button').first().click();
  await expect(page.locator('.file-row')).toHaveCount(4);
});

test('supports the UUID and clipboard fallbacks needed for HTTP LAN access', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(crypto, 'randomUUID', { value: undefined, configurable: true });
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
  });
  await page.reload();
  await page.getByLabel('Original text').fill('Hello\u200bLAN');
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await expect(page.getByLabel('Cleaned text')).toHaveValue('HelloLAN');
  await expect(page.locator('.history-list li')).toHaveCount(1);
  await page.getByRole('button', { name: 'Copy', exact: true }).click();
  await expect(page.locator('.notice')).toContainText('Cleaned text copied');
  await page.getByRole('tab', { name: 'Files' }).click();
  await page.locator('input[type=file]').setInputFiles({ name: 'lan.txt', mimeType: 'text/plain', buffer: Buffer.from('Hello\u200bLAN') });
  await expect(page.locator('.file-row')).toHaveCount(1);
});

test('text, documents, and dialog satisfy automated WCAG checks', async ({ page }) => {
  const scan = async () => {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(result.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) }))).toEqual([]);
  };
  await scan();
  await page.getByRole('button', { name: 'Try a sample' }).click();
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await expect(page.getByLabel('Cleaned text')).toBeVisible();
  await scan();
  await page.getByRole('button', { name: 'Clear all history', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await scan();
  await page.keyboard.press('Escape');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('tab', { name: 'Files' }).click();
  await scan();
});

test('system theme follows the OS and manual preferences persist in both themes', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByLabel('Theme', { exact: true })).toHaveValue('system');
  await expect(page.locator('footer')).toContainText('Open to everyone');
  await expect(page.locator('footer')).not.toContainText('personal');
  for (const theme of ['light', 'dark']) {
    await page.getByLabel('Theme', { exact: true }).selectOption(theme);
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(result.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) }))).toEqual([]);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: `artifacts/${theme}-desktop.png`, fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `artifacts/${theme}-mobile.png`, fullPage: true });
  }
  await page.getByLabel('Theme', { exact: true }).selectOption('system');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('all non-PDF formats run locally without processing API requests', async ({ page }) => {
  const fixtures = JSON.parse(execFileSync(python, ['-c', `
import base64, json
from pathlib import Path
from tests.test_api import docx, odt, epub
files = [('sample.txt', 'Halo\\u200bdunia'.encode()), ('sample.md', '# Halo\\u200bdunia'.encode()), ('sample.html', '<p>Halo\\u200bdunia</p>'.encode()), ('sample.docx', docx()), ('sample.odt', odt()), ('sample.epub', epub())]
for ext in ('xlsx','pptx'):
    files.append(('sample.'+ext, Path('watermarks-remover/tests/fixtures/sample_ai.'+ext).read_bytes()))
print(json.dumps([{'name':name,'content':base64.b64encode(data).decode()} for name,data in files]))
`], { encoding: 'utf8' }));
  const processingRequests = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) processingRequests.push(request.url()); });
  const results = await page.evaluate(async files => {
    const results = [];
    for (const item of files) {
      const bytes = Uint8Array.from(atob(item.content), char => char.charCodeAt(0));
      const result = await NoMarkProcessor.run('file', new File([bytes], item.name), () => {});
      results.push({ name: item.name, ok: result.ok, processed_by: result.processed_by, bytes_out: result.bytes_out });
    }
    return results;
  }, fixtures);
  expect(results).toHaveLength(8);
  for (const result of results) {
    expect(result.ok, result.name).toBe(true);
    expect(result.processed_by).toBe('browser');
    expect(result.bytes_out).toBeGreaterThan(0);
  }
  expect(processingRequests).toEqual([]);
});

test('PDF waits before upload and requires explicit server permission', async ({ page, request }) => {
  const source = execFileSync(python, ['-c', 'from tests.test_api import pdf; import sys; sys.stdout.buffer.write(pdf())']);
  const tickets = [];
  let uploads = 0;
  page.on('request', request => { if (request.url().endsWith('/api/file/process')) uploads++; });
  try {
    for (let index = 0; index < 2; index++) tickets.push(await (await request.post('/api/queue')).json());
    await page.getByRole('tab', { name: 'Files' }).click();
    await page.locator('input[type=file]').setInputFiles({ name: 'sample.pdf', mimeType: 'application/pdf', buffer: source });
    await page.getByRole('button', { name: 'Clean files', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Allow PDF uploads');
    expect(uploads).toBe(0);
    await page.getByRole('checkbox', { name: /I allow queued PDFs/ }).check();
    await page.getByRole('button', { name: 'Clean files', exact: true }).click();
    await expect(page.locator('.process-status')).toContainText('Your file stays on your device');
    expect(uploads).toBe(0);
    await request.delete('/api/queue', { headers: { Authorization: `Bearer ${tickets[0].token}` } });
    await expect(page.locator('.file-row .copy-button')).toBeVisible();
    expect(uploads).toBe(1);
    await expect(page.locator('.result-location')).toContainText('Processed on the server');
    const event = page.waitForEvent('download');
    await page.locator('.file-row .copy-button').click();
    const downloaded = await event;
    expect(downloaded.suggestedFilename()).toBe('sample.cleaned.pdf');
  } finally {
    for (const ticket of tickets) await request.delete('/api/queue', { headers: { Authorization: `Bearer ${ticket.token}` } });
  }
});

test('privacy and terms are readable in Indonesian and English with dark mode', async ({ page }) => {
  await page.getByLabel('Theme', { exact: true }).selectOption('dark');
  await page.getByRole('link', { name: 'Privacy policy', exact: true }).click();
  await expect(page).toHaveURL(/\/en\/privacy$/);
  await expect(page.getByRole('heading', { name: 'Privacy policy', exact: true })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('main')).toContainText('me@ardianryan.com');
  await expect(page.locator('main')).toContainText('Web Worker');
  await page.getByRole('link', { name: 'Bahasa Indonesia' }).click();
  await expect(page.getByRole('heading', { name: 'Kebijakan privasi', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Ketentuan layanan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ketentuan layanan', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'English' }).click();
  await expect(page.getByRole('heading', { name: 'Terms of service', exact: true })).toBeVisible();
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(result.violations.map(item => item.id)).toEqual([]);
});

test('local processing can be cancelled and retried without uploading content', async ({ page }) => {
  await page.route('**/static/engine-manifest.json', () => {});
  await page.getByLabel('Original text').fill('Hello\u200bworld');
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.locator('.notice')).toContainText('Processing cancelled');
  await expect(page.getByLabel('Original text')).toHaveValue('Hello\u200bworld');
  await page.unroute('**/static/engine-manifest.json');
  await page.getByRole('button', { name: 'Clean text', exact: true }).click();
  await expect(page.getByLabel('Cleaned text')).toHaveValue('Helloworld');
});

test('cancelling a waiting PDF releases its ticket without uploading the file', async ({ page, request }) => {
  const held = [];
  const content = execFileSync(python, ['-c', 'from tests.test_api import pdf; import sys; sys.stdout.buffer.write(pdf())']);
  let uploads = 0;
  page.on('request', request => { if (request.url().endsWith('/api/file/process')) uploads++; });
  try {
    for (let i = 0; i < 2; i++) held.push(await (await request.post('/api/queue')).json());
    await page.getByRole('tab', { name: 'Files' }).click();
    await page.locator('input[type=file]').setInputFiles({ name: 'cancel.pdf', mimeType: 'application/pdf', buffer: content });
    await page.getByRole('checkbox', { name: /I allow queued PDFs/ }).check();
    const ticketResponse = page.waitForResponse(response => response.url().endsWith('/api/queue') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Clean files', exact: true }).click();
    const ticket = await (await ticketResponse).json();
    await expect(page.locator('.process-status')).toContainText('Your file stays on your device');
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(page.locator('.notice')).toContainText('Processing cancelled');
    expect(uploads).toBe(0);
    await expect.poll(async () => (await request.get('/api/queue', { headers: { Authorization: `Bearer ${ticket.token}` } })).status()).toBe(410);
  } finally {
    for (const ticket of held) await request.delete('/api/queue', { headers: { Authorization: `Bearer ${ticket.token}` } });
  }
});
