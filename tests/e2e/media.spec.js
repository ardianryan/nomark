const { test, expect } = require('@playwright/test');
const path = require('node:path');

test.beforeEach(async ({ page }) => { await page.goto('/en'); await page.getByRole('tab', { name: 'Files', exact: true }).click(); });

test('image categories clean locally, preserve pixels, download, and restore history', async ({ page }) => {
  const api = [];
  page.on('request', request => { if (/\/api\/(?:file|text|queue)/.test(request.url())) api.push(request.url()); });
  await page.getByRole('radio', { name: 'Images', exact: true }).check();
  await expect(page.locator('input[type=file]')).toHaveAttribute('accept', /\.png/);
  await expect(page.locator('.format-explanation')).toContainText('Clean image file metadata.');
  await page.locator('input[type=file]').setInputFiles(['png', 'jpg', 'webp', 'gif', 'bmp'].map(ext => path.resolve(`tests/fixtures/media/sample.${ext}`)));
  await page.getByRole('button', { name: 'Clean files', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download', exact: true })).toHaveCount(10, { timeout: 60000 });
  const compared = await page.evaluate(async () => {
    const records = await NoMarkHistory.list();
    const outcomes = [];
    for (const item of records) {
      const record = await NoMarkHistory.get(item.id);
      const pixels = async blob => {
        const bitmap = await createImageBitmap(blob);
        const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
        const context = canvas.getContext('2d'); context.drawImage(bitmap, 0, 0);
        return Array.from(context.getImageData(0, 0, canvas.width, canvas.height).data).join(',');
      };
      outcomes.push(await pixels(record.sourceBlob) === await pixels(record.outputBlob));
    }
    return outcomes;
  });
  expect(compared).toEqual([true, true, true, true, true]);
  const download = page.waitForEvent('download');
  await page.locator('.file-actions').first().getByRole('button', { name: 'Download', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('sample.cleaned.png');
  await page.reload();
  await page.locator('.history-item').first().click();
  await expect(page.getByRole('radio', { name: 'Images', exact: true })).toBeChecked();
  expect(api).toEqual([]);
});

test('audio metadata is cleaned locally and controls work in both languages and themes', async ({ page }) => {
  const uploads = [];
  page.on('request', request => { if (request.method() === 'POST') uploads.push(request.url()); });
  await page.getByRole('radio', { name: 'Audio', exact: true }).check();
  await expect(page.locator('input[type=file]')).toHaveAttribute('accept', /\.wav/);
  await page.locator('input[type=file]').setInputFiles(path.resolve('tests/fixtures/media/sample.wav'));
  await page.getByRole('button', { name: 'Clean files', exact: true }).click();
  await expect(page.locator('.file-actions').getByRole('button', { name: 'Download', exact: true })).toBeVisible({ timeout: 60000 });
  await page.getByRole('radio', { name: 'Video', exact: true }).check();
  await expect(page.locator('.format-explanation')).toContainText('Clean video file metadata.');
  await page.getByRole('button', { name: 'ID', exact: true }).click();
  await expect(page.getByRole('radio', { name: 'Gambar', exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: 'Tema', exact: true }).selectOption('dark');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'artifacts/media-dark-mobile.png', fullPage: false });
  await page.getByRole('combobox', { name: 'Tema', exact: true }).selectOption('light');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: 'artifacts/media-light-desktop.png', fullPage: false });
  expect(uploads).toEqual([]);
});
