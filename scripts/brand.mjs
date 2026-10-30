import { chromium } from '@playwright/test';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';

const directory = 'static/brand';
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch(existsSync(chrome) ? { executablePath: chrome } : {});
const page = await browser.newPage({ deviceScaleFactor: 1 });
const icon = readFileSync(`${directory}/favicon.svg`, 'utf8');
const images = [];
for (const size of [16, 32, 48, 180, 192, 512]) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<style>body{margin:0}svg{display:block;width:100%;height:100%}</style>${icon}`);
  const png = await page.screenshot({ path: `${directory}/${size === 180 ? 'apple-touch-icon' : `icon-${size}`}.png`, omitBackground: true });
  if (size <= 48) images.push({ size, png });
}
const header = Buffer.alloc(6 + images.length * 16);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(images.length, 4);
let offset = header.length;
images.forEach(({ size, png }, index) => {
  const start = 6 + index * 16;
  header[start] = size; header[start + 1] = size;
  header.writeUInt16LE(1, start + 4); header.writeUInt16LE(32, start + 6);
  header.writeUInt32LE(png.length, start + 8); header.writeUInt32LE(offset, start + 12);
  offset += png.length;
});
writeFileSync(`${directory}/favicon.ico`, Buffer.concat([header, ...images.map(image => image.png)]));
await page.setViewportSize({ width: 1200, height: 630 });
const hasBrandFont = await page.evaluate(() => {
  const context = document.createElement('canvas').getContext('2d');
  context.font = '32px monospace';
  const baseline = context.measureText('NoMark hidden traces').width;
  context.font = '32px "Avenir Next", monospace';
  return context.measureText('NoMark hidden traces').width !== baseline;
});
if (!hasBrandFont) {
  await browser.close();
  throw new Error('Avenir Next is required to regenerate the approved social image. Use the committed PNG on other machines.');
}
const logo = readFileSync(`${directory}/logo.svg`, 'utf8');
await page.setContent(`<style>*{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#233b32;font-family:"Avenir Next","Segoe UI",sans-serif;padding:38px 48px}header{height:66px;display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #d9dfd6}svg{width:160px;height:auto;display:block}.domain{font-size:16px;color:#53645b;margin:8px 0 0}.layout{display:grid;grid-template-columns:1fr 250px;gap:20px;margin-top:28px}.main{background:#e1eee5;border:1px solid #d9dfd6;border-radius:24px;padding:36px 40px;height:396px}.eyebrow{font-size:16px;margin:0 0 23px;color:#53645b}h1{font-size:59px;line-height:1.12;letter-spacing:-2px;font-weight:600;margin:0 0 26px}p{font-size:20px;line-height:1.6;margin:0}.side{background:#f3e4d8;border-radius:24px;padding:30px 26px;display:flex;flex-direction:column;justify-content:space-between}.glyph{font-size:82px;line-height:1;letter-spacing:-7px;font-weight:500;color:#53645b}.side p{font-size:20px;font-weight:600;line-height:1.45}.side small{font-size:15px;line-height:1.6;color:#685b4e}.bottom{display:flex;justify-content:space-between;margin-top:24px;font-size:15px;color:#53645b}</style><header>${logo}<p class="domain">nomark.ardianryan.com</p></header><div class="layout"><div class="main"><p class="eyebrow">A little room for cleaner text</p><h1>Tidy up<br>hidden traces.</h1><p>Clean invisible characters<br>and document metadata.</p></div><aside class="side"><span class="glyph">Aa</span><p>Your words<br>stay your words.</p><small>No account.<br>No installation.</small></aside></div><div class="bottom"><span>Text and non-PDF documents stay in your browser.</span><span>Open to everyone</span></div>`);
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: `${directory}/social-card.png` });
await browser.close();
