const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const source = 'tests/fixtures/images/clean-01.png';
const bytes = fs.readFileSync(source);
const result = { ok: true, kind: 'image', format: 'png', mime: 'image/png', name: 'clean-01.png', cleaned_name: 'clean-01.cleaned.png',
  status: 'unchanged', visual_status: 'no_watermark', width: 640, height: 480, bytes_in: bytes.length, bytes_out: bytes.length,
  elapsed_ms: 120, processed_by: 'server', cleaned_base64: bytes.toString('base64'),
  report: { marks: [], metadata_removed: false, normalized: true, warnings: ['image_review'] } };

async function openImages(page) {
  await page.route('**/api/media/capabilities', route => route.fulfill({ json: { ok:true, available:true } }));
  await page.goto('/en');
  await page.getByRole('tab', {name:'Images',exact:true}).click();
  await page.locator('#image-picker').setInputFiles(source);
  await expect(page.locator('.image-selected')).toContainText('640 × 480');
}

test('image permission, waiting without upload, PNG download and restored history', async ({page}) => {
  let uploads = 0, polls = 0, deletes = 0;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/media/queue', async route => {
    const method=route.request().method();
    if(method==='POST') return route.fulfill({json:{ok:true,token:'image-test',state:'waiting',position:1}});
    if(method==='DELETE') {deletes++;return route.fulfill({json:{ok:true}});}
    polls++;expect(uploads).toBe(0);
    return route.fulfill({json:{ok:true,state:'ready',position:0}});
  });
  await page.route('**/api/image/process', route => {uploads++;return route.fulfill({json:result});});
  await openImages(page);
  const action=page.getByRole('button',{name:'Clean image',exact:true});
  await action.click();await expect(page.getByRole('alert')).toContainText('Allow this image');expect(uploads).toBe(0);
  await page.locator('#image-panel input[type=checkbox]').check();await action.click();
  await expect(page.locator('.image-report')).toContainText('No recognized visual mark');
  expect(uploads).toBe(1);expect(polls).toBe(1);expect(deletes).toBe(0);
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download PNG'}).click();
  expect((await download).suggestedFilename()).toBe('clean-01.cleaned.png');
  await page.reload();
  await page.locator('.history-item').first().click();
  await expect(page.getByRole('tab',{name:'Images',exact:true})).toHaveAttribute('aria-selected','true');
  await expect(page.locator('.image-report')).toContainText('No recognized visual mark');
  expect(uploads).toBe(1);expect(errors).toEqual([]);
});

test('cancel queued image without uploading',async({page})=>{
  let uploads=0,deleted=0;
  await page.route('**/api/media/queue',route=>{
    if(route.request().method()==='DELETE'){deleted++;return route.fulfill({json:{ok:true}});}
    return route.fulfill({json:{ok:true,token:'waiting',state:'waiting',position:1}});
  });
  await page.route('**/api/image/process',route=>{uploads++;return route.abort();});
  await openImages(page);await page.locator('#image-panel input[type=checkbox]').check();
  await page.getByRole('button',{name:'Clean image',exact:true}).click();
  await expect(page.locator('.process-status')).toContainText('Waiting for image processing');
  await page.locator('.process-status').getByRole('button',{name:'Cancel'}).click();
  await expect(page.locator('.process-status')).toBeHidden();expect(uploads).toBe(0);expect(deleted).toBe(1);
});

test('image result survives history quota failure; localized partial and unvalidated results',async({page})=>{
  await page.route('**/api/media/queue',route=>route.fulfill({json:{ok:true,token:'ready',state:'ready'}}));
  await page.route('**/api/image/process',route=>route.fulfill({json:{...result,status:'partial',visual_status:'unvalidated',report:{...result.report,marks:[{key:'gemini',label:'Gemini',status:'unvalidated'}]}}}));
  await openImages(page);
  await page.evaluate(()=>{window.NoMarkHistory.save=async()=>{throw new Error('quota');};});
  await page.locator('#image-panel input[type=checkbox]').check();await page.getByRole('button',{name:'Clean image',exact:true}).click();
  await expect(page.locator('.image-report')).toContainText('could not be verified');
  await expect(page.getByRole('button',{name:'Download PNG'})).toBeVisible();
  await expect(page.getByRole('status').filter({hasText:'History could not'})).toBeVisible();
  await page.getByRole('button',{name:'ID',exact:true}).click();
  await expect(page.locator('.image-report')).toContainText('belum dapat diverifikasi');
});

test('image rate limit shows wait and keeps the selected image',async({page})=>{
  await page.route('**/api/media/queue',route=>route.fulfill({status:429,headers:{'Retry-After':'24'},json:{ok:false,error:'rate_limited'}}));
  await openImages(page);await page.locator('#image-panel input[type=checkbox]').check();
  await page.getByRole('button',{name:'Clean image',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('24');
  await expect(page.locator('.image-selected')).toContainText('clean-01.png');
});

test('four tabs support keyboard and image layout fits mobile dark/light',async({page})=>{
  await openImages(page);
  await page.getByRole('tab',{name:'Images',exact:true}).focus();await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('tab',{name:'Files',exact:true})).toBeFocused();
  await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:'Images',exact:true})).toBeFocused();
  await page.setViewportSize({width:390,height:844});
  for(const mode of ['light','dark']){
    await page.getByRole('combobox',{name:'Theme',exact:true}).selectOption(mode);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:`artifacts/images-mobile-${mode}.png`,fullPage:true});
  }
});

test('rejects disguised active content before preview or image upload',async({page})=>{
  let uploads=0;
  await page.route('**/api/media/capabilities',route=>route.fulfill({json:{ok:true,available:true}}));
  await page.route('**/api/image/process',route=>{uploads++;return route.abort();});
  await page.goto('/en');await page.getByRole('tab',{name:'Images',exact:true}).click();
  await page.locator('#image-picker').setInputFiles({name:'fake.png',mimeType:'image/svg+xml',buffer:Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><script>alert(1)</script></svg>')});
  await expect(page.getByRole('alert')).toBeVisible();await expect(page.locator('.image-comparison')).toBeHidden();expect(uploads).toBe(0);
});
