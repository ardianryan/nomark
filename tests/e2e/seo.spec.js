const { test, expect } = require('@playwright/test');

test('localized explanation and FAQ are readable without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:8000/en');
  await expect(page.getByRole('heading', { name: 'Tidy up hidden traces.' })).toBeVisible();
  await page.getByText('What does NoMark clean?', { exact: true }).click();
  await expect(page.locator('.faq-section')).toContainText('does not guarantee removal of statistical AI watermarks');
  await page.goto('http://127.0.0.1:8000/id');
  await expect(page.getByRole('heading', { name: 'Bereskan jejak tersembunyi.' })).toBeVisible();
  await expect(page.locator('#source-title')).toHaveText('Berbasis watermarks-remover');
  await context.close();
});

test('language switching preserves input and keeps metadata and schema consistent', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/en');
  await page.getByLabel('Original text').fill('Keep this draft');
  await page.getByRole('button', { name: 'ID', exact: true }).click();
  await expect(page).toHaveURL(/\/id$/);
  await expect(page.getByLabel('Teks asli')).toHaveValue('Keep this draft');
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute('content', 'https://nomark.ardianryan.com/id');
  const graph = await page.locator('script[type="application/ld+json"]').evaluate(el => JSON.parse(el.textContent)['@graph']);
  expect(graph.find(item => item['@type'] === 'FAQPage').inLanguage).toBe('id');
  expect(graph.find(item => item['@type'] === 'WebPage').url).toBe('https://nomark.ardianryan.com/id');
  await expect(page.locator('.brand-logo')).toBeVisible();
  await page.getByLabel('Tema', { exact: true }).selectOption('dark');
  await expect(page.locator('.brand-logo-dark')).toBeVisible();
  await expect(page.locator('.brand-logo')).toBeHidden();
  expect(await page.locator('.wordmark img').evaluateAll(images => images.every(img => img.complete && img.naturalWidth > 0))).toBe(true);
  expect(errors).toEqual([]);
});
