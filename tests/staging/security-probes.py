"""Bounded observations for open audit hypotheses; run in offline staging only."""

import json
from pathlib import Path
import tempfile
import time

from pypdf import PdfWriter

from nomark.admission import Admission
from nomark.engine import process_file
from nomark.jobs import JobError
from nomark import upstream


def reservations():
    now = [0]
    queue = Admission(clock=lambda: now[0])
    allocations = 0
    samples = []
    for tick in range(0, 61, 5):
        now[0] = tick
        queue.sweep()
        while len(queue.tickets) < 10:
            queue.reserve()
            allocations += 1
        try:
            queue.reserve()
        except JobError as exc:
            samples.append(exc.code)
    active = queue.active
    for token in list(queue.tickets):
        queue.cancel(token)
    with queue.claim():
        recovered = queue.active == 1
    return {'allocations_including_t60': allocations, 'sampled_full_rejections': len(samples),
            'active_jobs': active, 'recovered_after_release': recovered,
            'limit': 'Direct fake-clock model; no HTTP rate or competing-arrival schedule tested.'}


def attachment_storage(root):
    pdf = PdfWriter()
    pdf.add_blank_page(width=72, height=72)
    for index in range(4):
        pdf.add_attachment(f'note-{index}.txt', b'a' * 32768)
    source = root / 'attachments.pdf'
    pdf.write(source)
    staging = root / 'extracted'
    staging.mkdir()
    module = upstream.container_meta
    original = module.MAX_ATTACHMENT_BYTES
    try:
        module.MAX_ATTACHMENT_BYTES = 65536
        accepted, skipped = module._pdf_extract_attachments(source, None, staging)
    finally:
        module.MAX_ATTACHMENT_BYTES = original
    sizes = [entry['in_path'].stat().st_size for entry in accepted]
    assert len(sizes) == 4 and not skipped and sizes == [32768] * 4
    return {'attachments': len(sizes), 'retained_bytes': sum(sizes),
            'scaled_per_attachment_cap': 65536,
            'limit': 'Reduced test cap; does not reproduce exhaustion at production limits.'}


def scanner_samples(root):
    samples = []
    for repetitions in (256, 512, 1024):
        source = root / f'scan-{repetitions}.html'
        source.write_text('<html><head>' + '<meta ' * repetitions + '</head></html>')
        started = time.perf_counter()
        result = process_file(source, source.name, root)
        samples.append({'bytes': source.stat().st_size,
                        'elapsed_ms': round((time.perf_counter() - started) * 1000, 3),
                        'status': result['status']})
    return {'samples': samples,
            'limit': 'Small accepted HTML fixtures only; no complexity bound or shared outage established.'}


with tempfile.TemporaryDirectory(prefix='nomark-audit-probes-') as directory:
    root = Path(directory)
    print(json.dumps({'version': '0.1.0-alpha.4', 'reservations': reservations(),
                      'attachments': attachment_storage(root), 'scanner': scanner_samples(root)}))
