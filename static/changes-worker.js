importScripts('/static/vendor/diff.min.js');

self.onmessage = event => {
  const { before, after, anchors = [] } = event.data;
  const source = Array.from(before), output = Array.from(after), deadline = Date.now() + 150;
  const runs = [];
  let oldPosition = 0, position = 0, pending = null;
  const flush = () => {
    if (!pending) return;
    runs.push({ ...pending, end: position, oldEnd: oldPosition });
    pending = null;
  };
  const comparePart = (left, right) => {
    const remaining = deadline - Date.now();
    if (remaining <= 0) return false;
    const changes = Diff.diffWordsWithSpace(left, right, { timeout: remaining, maxEditLength: 2000 });
    if (!changes) return false;
    for (const change of changes) {
    const length = Array.from(change.value).length;
    if (!change.added && !change.removed) {
      flush();
      runs.push({ changed: false, value: change.value, before: change.value,
        start: position, end: position + length, oldStart: oldPosition, oldEnd: oldPosition + length });
      position += length; oldPosition += length;
    } else {
      pending ||= { changed: true, value: '', before: '', start: position, oldStart: oldPosition };
      if (change.added) { pending.value += change.value; position += length; }
      if (change.removed) { pending.before += change.value; oldPosition += length; }
    }
    }
    flush();
    return true;
  };
  for (const anchor of anchors) {
    if (anchor.input_start < oldPosition || anchor.start < position || anchor.input_end > source.length
        || anchor.end > output.length || source.slice(anchor.input_start, anchor.input_end).join('') !== anchor.before) continue;
    if (!comparePart(source.slice(oldPosition, anchor.input_start).join(''), output.slice(position, anchor.start).join(''))) {
      self.postMessage(null); return;
    }
    const value = output.slice(anchor.start, anchor.end).join('');
    runs.push({ changed: anchor.before !== value, value, before: anchor.before,
      start: position, end: anchor.end, oldStart: oldPosition, oldEnd: anchor.input_end });
    position = anchor.end; oldPosition = anchor.input_end;
  }
  if (!comparePart(source.slice(oldPosition).join(''), output.slice(position).join(''))) {
    self.postMessage(null); return;
  }
  self.postMessage(runs);
};
