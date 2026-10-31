const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Diff = require('diff');
const window = {};
vm.runInNewContext(fs.readFileSync('static/changes.js', 'utf8'), { window, setTimeout, clearTimeout });
const C = window.NoMarkChanges;
const plain = value => JSON.parse(JSON.stringify(value));

function compare(before, after, anchors = []) {
  let result;
  const self = { postMessage(value) { result = value; } };
  vm.runInNewContext(fs.readFileSync('static/changes-worker.js', 'utf8'), { self, Diff, importScripts() {} });
  self.onmessage({ data: { before, after, anchors } });
  return result;
}

const edit = { id: 'one', input_start: 2, input_end: 8, output_start: 2, output_end: 7,
  before: 'cannot', after: "can't", alternatives: ['can not'] };

test('word changes reconstruct exact source and result, including Unicode and CRLF', () => {
  for (const [before, after] of [
    ['🙂 cannot\r\n\r\nGo.', "🙂 can't\r\n\r\nGo."], ['same same same', 'same other same'],
    ['one two three', 'one three'], ['', 'new'], ['delete everything', ''],
    ['  - hello\n', '  - other\n'], ['漢字 é 👨‍👩‍👧', '漢字 é 👨‍👩‍👦'],
  ]) {
    const runs = compare(before, after);
    assert.equal(runs.map(item => item.before).join(''), before);
    assert.equal(runs.map(item => item.value).join(''), after);
  }
});

test('metadata positions are Unicode code points and reject malformed ranges', () => {
  const values = C.anchors([edit], '🙂 cannot', "🙂 can't");
  assert.equal(values[0].start, 2);
  assert.equal(C.slice("🙂 can't", values[0].start, values[0].end), "can't");
  assert.equal(C.anchors([{ ...edit, output_start: -1 }], '🙂 cannot', "🙂 can't").length, 0);
  assert.equal(C.anchors([edit, edit], '🙂 cannot', "🙂 can't").length, 0);
});

test('manual insertion shifts unaffected suggestions and touching an edit invalidates it', () => {
  const anchors = C.anchors([edit], '🙂 cannot', "🙂 can't");
  const shifted = C.rebase(anchors, compare("🙂 can't", "First 🙂 can't"));
  assert.equal(shifted[0].start, 8);
  assert.equal(C.slice("First 🙂 can't", shifted[0].start, shifted[0].end), "can't");
  assert.equal(C.rebase(anchors, compare("🙂 can't", '🙂 will')).length, 0);
});

test('adjacent changes preserve their own original phrases', () => {
  const source = 'Ia telah datang.', output = 'Dia sudah datang.';
  const values = C.anchors([
    { id: 'a', input_start: 0, input_end: 2, output_start: 0, output_end: 3, before: 'Ia', after: 'Dia', alternatives: [] },
    { id: 'b', input_start: 3, input_end: 8, output_start: 4, output_end: 9, before: 'telah', after: 'sudah', alternatives: [] },
  ], source, output);
  const chunks = C.decorate(compare(source, output), values, source, output);
  assert.deepEqual(plain(chunks.filter(item => item.anchorId).map(item => [item.before, item.value])), [['Ia', 'Dia'], ['telah', 'sudah']]);
  assert.equal(chunks.map(item => item.value).join(''), output);
});

test('verified phrase boundaries survive shared words and inserted whitespace', () => {
  const original = '🙂 cannot', output = '🙂 can not';
  const values = [{ ...edit, start: 2, end: 9 }];
  const chunks = C.decorate(compare(original, output, values), values, original, output);
  assert.equal(chunks.filter(item => item.changed).length, 1);
  assert.equal(chunks.find(item => item.changed).value, 'can not');
});

test('deletion markers and fallback never become result text', () => {
  const chunks = C.decorate(compare('Keep this text.', 'Keep text.'), [], 'Keep this text.', 'Keep text.');
  assert.ok(chunks.some(item => item.changed));
  assert.equal(chunks.map(item => item.value).join(''), 'Keep text.');
  assert.equal(C.decorate(null, [], 'old', 'new')[0].value, 'new');
});

test('pathological differences stop within the comparison budget', () => {
  assert.equal(compare('a '.repeat(2500), 'b '.repeat(25000)), null);
});

test('worker result wins and cancellation resolves an old request without stale output', async () => {
  class Worker {
    postMessage(value) { this.value = value; setTimeout(() => this.onmessage?.({ data: [value.after] }), 5); }
    terminate() { this.onmessage = null; }
  }
  const target = {};
  vm.runInNewContext(fs.readFileSync('static/changes.js', 'utf8'), { window: target, Worker, setTimeout, clearTimeout });
  const differ = target.NoMarkChanges.createDiffer();
  const first = differ.compare('a', 'b');
  const second = differ.compare('a', 'c');
  assert.equal(await first, null);
  assert.deepEqual(await second, ['c']);
});
