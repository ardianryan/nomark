(() => {
  const slice = (text, start, end) => Array.from(text).slice(start, end).join('');
  const length = text => Array.from(text).length;

  function createDiffer() {
    let worker, timer, resolvePending;
    const cancel = (result = null) => {
      clearTimeout(timer); worker?.terminate(); worker = null;
      resolvePending?.(result); resolvePending = null;
    };
    return {
      cancel,
      compare(before, after, anchors = []) {
        cancel();
        return new Promise(resolve => {
          resolvePending = resolve;
          try {
            worker = new Worker('/static/changes-worker.js');
            worker.onmessage = event => cancel(event.data);
            worker.onerror = () => cancel();
            timer = setTimeout(cancel, 1000);
            worker.postMessage({ before, after, anchors: JSON.parse(JSON.stringify(anchors)) });
          } catch { cancel(); }
        });
      },
    };
  }

  function anchors(edits, source, output) {
    if (!Array.isArray(edits) || edits.length > 256) return [];
    let lastInput = 0, lastOutput = 0;
    const seen = new Set(), result = [];
    for (const edit of edits) {
      if (!edit || typeof edit !== 'object' || typeof edit.id !== 'string' || seen.has(edit.id)
          || !['input_start', 'input_end', 'output_start', 'output_end'].every(key => Number.isInteger(edit[key]))
          || edit.input_start < lastInput || edit.output_start < lastOutput
          || edit.input_end <= edit.input_start || edit.output_end <= edit.output_start
          || edit.input_end > length(source) || edit.output_end > length(output)
          || slice(source, edit.input_start, edit.input_end) !== edit.before
          || slice(output, edit.output_start, edit.output_end) !== edit.after
          || !Array.isArray(edit.alternatives) || edit.alternatives.length > 3
          || edit.alternatives.some(value => typeof value !== 'string' || !value.trim() || length(value) > 128)) return [];
      result.push({ ...edit, start: edit.output_start, end: edit.output_end });
      seen.add(edit.id); lastInput = edit.input_end; lastOutput = edit.output_end;
    }
    return result;
  }

  function rebase(values, runs) {
    if (!runs) return [];
    return values.flatMap(anchor => {
      const run = runs.find(item => !item.changed && item.oldStart <= anchor.start && item.oldEnd >= anchor.end);
      return run ? [{ ...anchor, start: anchor.start + run.start - run.oldStart,
        end: anchor.end + run.start - run.oldStart }] : [];
    });
  }

  function decorate(runs, values, source, output) {
    if (!runs) return [{ id: 'plain', changed: false, value: output }];
    const result = [];
    const append = value => {
      if (!value.value && !value.before) return;
      result.push({ ...value, id: `change-${result.length}` });
    };
    for (const run of runs) {
      if (!run.changed) { append(run); continue; }
      let position = run.start, oldPosition = run.oldStart;
      for (const anchor of values.filter(item => item.start >= run.start && item.end <= run.end
          && item.input_start >= run.oldStart && item.input_end <= run.oldEnd)) {
        if (anchor.start < position || anchor.input_start < oldPosition) continue;
        append({ changed: true, start: position, end: anchor.start,
          before: slice(source, oldPosition, anchor.input_start), value: slice(output, position, anchor.start) });
        append({ changed: true, start: anchor.start, end: anchor.end, before: anchor.before,
          value: slice(output, anchor.start, anchor.end), anchorId: anchor.id });
        position = anchor.end; oldPosition = anchor.input_end;
      }
      append({ changed: true, start: position, end: run.end,
        before: slice(source, oldPosition, run.oldEnd), value: slice(output, position, run.end) });
    }
    return result.map(item => ({ ...item, changed: !!item.changed && item.before !== item.value
      && !!(item.before?.trim() || item.value?.trim()), display: item.value }));
  }

  window.NoMarkChanges = { slice, length, createDiffer, anchors, rebase, decorate };
})();
