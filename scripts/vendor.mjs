import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { gzipSync } from 'node:zlib';

await mkdir('static/vendor', { recursive: true });
const source = 'node_modules/@alpinejs/csp/dist/cdn.min.js';
await copyFile(source, 'static/vendor/alpine-csp.min.js');
const { version } = JSON.parse(await readFile('node_modules/@alpinejs/csp/package.json', 'utf8'));
const license = await fetch(`https://raw.githubusercontent.com/alpinejs/alpine/v${version}/LICENSE.md`);
if (!license.ok) throw new Error('Could not retrieve the Alpine license');
await writeFile('static/vendor/ALPINE-LICENSE.txt', await license.text());
const hash = createHash('sha256').update(await readFile(source)).digest('hex');
await writeFile('static/vendor/VERSION.txt', `@alpinejs/csp ${version}\nSHA256 ${hash}\n`);
const upstreamLicense = await readFile('watermarks-remover/LICENSE', 'utf8');
const ownLicense = await readFile('LICENSE', 'utf8');
await writeFile('static/notices.txt', `NoMark — MIT License\n\n${ownLicense}\n\nNoMark — third-party notices\n\nwatermarks-remover\nhttps://github.com/guillaumemeyer/watermarks-remover\nCommit: 5c180932a00c793261177f79aee21db8929f3fe2\n\n${upstreamLicense}\n\nAlpine.js CSP ${version}\nhttps://github.com/alpinejs/alpine\n\n${await readFile('static/vendor/ALPINE-LICENSE.txt', 'utf8')}`);
for (const name of ['reactivity', 'shared']) {
  const license = await readFile(`node_modules/@vue/${name}/LICENSE`, 'utf8');
  await writeFile('static/notices.txt', `${await readFile('static/notices.txt', 'utf8')}\n\n@vue/${name}\n\n${license}`);
}

const pyodideDirectory = 'static/vendor/pyodide/314.0.7';
await mkdir(pyodideDirectory, { recursive: true });
for (const name of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  await copyFile(`node_modules/pyodide/${name}`, `${pyodideDirectory}/${name}`);
  const compressed = gzipSync(await readFile(`node_modules/pyodide/${name}`), { level: 9 });
  await writeFile(`${pyodideDirectory}/${name}.gz`, compressed);
}
const pyodideLicense = await fetch('https://raw.githubusercontent.com/pyodide/pyodide/314.0.7/LICENSE');
if (!pyodideLicense.ok) throw new Error('Could not retrieve the Pyodide license');
const licenseText = await pyodideLicense.text();
await writeFile(`${pyodideDirectory}/LICENSE.txt`, licenseText);
await writeFile('static/notices.txt', `${await readFile('static/notices.txt', 'utf8')}\n\nPyodide 314.0.7 (unmodified runtime)\nSource: https://github.com/pyodide/pyodide/tree/314.0.7\n\n${licenseText}`);
const pythonLicense = await fetch('https://raw.githubusercontent.com/python/cpython/v3.14.0/LICENSE');
if (!pythonLicense.ok) throw new Error('Could not retrieve the CPython license');
const pythonLicenseText = await pythonLicense.text();
await writeFile(`${pyodideDirectory}/PYTHON-LICENSE.txt`, pythonLicenseText);
await writeFile('static/notices.txt', `${await readFile('static/notices.txt', 'utf8')}\n\nCPython (included in Pyodide)\nSource: https://github.com/python/cpython/tree/3.14\n\n${pythonLicenseText}`);
execFileSync('.venv/bin/python', ['scripts/browser_bundle.py'], { stdio: 'inherit' });
execFileSync('.venv/bin/python', ['scripts/translations.py'], { stdio: 'inherit' });
