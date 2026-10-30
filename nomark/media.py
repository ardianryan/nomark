"""Deterministic upstream metadata cleaners; no external tools or model hooks."""
import zlib
from pathlib import Path

from nomark.upstream import av_meta, common, image_meta

clean_av = av_meta.clean_av
detect_av_format = av_meta.detect_av_format
inspect_av = av_meta.inspect_av

IMAGE_EXTENSIONS = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.webp': 'webp', '.gif': 'gif', '.bmp': 'bmp', '.tif': 'tiff', '.tiff': 'tiff', '.avif': 'avif', '.heic': 'heic', '.heif': 'heic'}
AV_EXTENSIONS = {'.mp4': 'mp4', '.mov': 'mp4', '.m4v': 'mp4', '.m4a': 'mp4', '.wav': 'wav', '.mp3': 'mp3', '.flac': 'flac'}


def validate_media(data: bytes, suffix: str):
    expected = (IMAGE_EXTENSIONS | AV_EXTENSIONS)[suffix]
    actual = image_meta.detect_format(data) if suffix in IMAGE_EXTENSIONS else detect_av_format(data)
    if actual != expected:
        raise ValueError('File content does not match extension')
    if actual == 'png':
        offset, chunks = 8, []
        while offset + 12 <= len(data):
            size = int.from_bytes(data[offset:offset + 4], 'big')
            end = offset + 12 + size
            if end > len(data):
                raise ValueError('Truncated PNG')
            kind = data[offset + 4:offset + 8]
            if zlib.crc32(data[offset + 4:end - 4]) & 0xffffffff != int.from_bytes(data[end - 4:end], 'big'):
                raise ValueError('Invalid PNG checksum')
            chunks.append(kind)
            offset = end
            if kind == b'IEND':
                break
        if not chunks or chunks[0] != b'IHDR' or b'IDAT' not in chunks or chunks[-1] != b'IEND' or offset != len(data):
            raise ValueError('Incomplete PNG')
    elif actual in {'webp', 'wav'}:
        if len(data) < 20 or int.from_bytes(data[4:8], 'little') + 8 != len(data):
            raise ValueError('Invalid RIFF size')
        offset, chunks = 12, []
        while offset + 8 <= len(data):
            size = int.from_bytes(data[offset + 4:offset + 8], 'little')
            chunks.append(data[offset:offset + 4])
            offset += 8 + size + (size & 1)
        if offset != len(data) or (actual == 'wav' and not {b'fmt ', b'data'}.issubset(chunks)) or (actual == 'webp' and not any(c in chunks for c in (b'VP8 ', b'VP8L', b'ANMF'))):
            raise ValueError('Incomplete RIFF content')
    elif actual == 'jpeg':
        if len(data) < 20 or not data.endswith(b'\xff\xd9') or b'\xff\xda' not in data:
            raise ValueError('Incomplete JPEG')
    elif actual == 'gif':
        if len(data) < 14 or not data.endswith(b';') or b',' not in data[13:]:
            raise ValueError('Incomplete GIF')
    elif actual == 'bmp':
        if len(data) < 54 or int.from_bytes(data[2:6], 'little') != len(data) or not 26 <= int.from_bytes(data[10:14], 'little') < len(data):
            raise ValueError('Incomplete BMP')
    elif actual == 'tiff':
        if len(data) < 16:
            raise ValueError('Incomplete TIFF')
        endian = 'little' if data[:2] == b'II' else 'big'
        big = int.from_bytes(data[2:4], endian) == 43
        position = int.from_bytes(data[8:16] if big else data[4:8], endian)
        if position < (16 if big else 8) or position + (8 if big else 2) > len(data):
            raise ValueError('Invalid TIFF directory')
    elif actual in {'mp4', 'avif', 'heic'}:
        offset, kinds = 0, []
        while offset + 8 <= len(data):
            size = int.from_bytes(data[offset:offset + 4], 'big')
            kind = data[offset + 4:offset + 8]
            header = 8
            if size == 1:
                if offset + 16 > len(data):
                    raise ValueError('Truncated extended box')
                size = int.from_bytes(data[offset + 8:offset + 16], 'big')
                header = 16
            elif size == 0:
                size = len(data) - offset
            if size < header or offset + size > len(data):
                raise ValueError('Truncated media box')
            kinds.append(kind)
            offset += size
        if offset != len(data) or (actual == 'mp4' and not {b'moov', b'mdat'}.issubset(kinds)) or (actual != 'mp4' and b'meta' not in kinds):
            raise ValueError('Incomplete media container')
    elif actual == 'flac':
        start = data.find(b'fLaC')
        if start < 0 or len(data) < start + 42 or data[start + 4] & 127 != 0 or data[start + 5:start + 8] != b'\x00\x00\x22':
            raise ValueError('Missing FLAC stream information')
        offset = start + 4
        while True:
            if offset + 4 > len(data):
                raise ValueError('Truncated FLAC metadata')
            last = data[offset] & 128
            size = int.from_bytes(data[offset + 1:offset + 4], 'big')
            offset += size + 4
            if offset > len(data):
                raise ValueError('Truncated FLAC block')
            if last:
                break
        if offset == len(data):
            raise ValueError('Missing FLAC audio')
    elif actual == 'mp3':
        offset = 0
        if data.startswith(b'ID3'):
            if any(byte > 127 for byte in data[6:10]):
                raise ValueError('Invalid ID3 length')
            offset = 10 + sum(byte << shift for byte, shift in zip(data[6:10], (21, 14, 7, 0)))
            if data[5] & 16:
                offset += 10
        if offset + 4 >= len(data) or not data[offset] == 255 or data[offset + 1] & 224 != 224:
            raise ValueError('Missing MPEG audio frame')


def clean_media(source: Path, destination: Path, data: bytes, suffix: str):
    if suffix in AV_EXTENSIONS:
        before = inspect_av(source, data=data).to_dict()
        report = clean_av(source, destination)
        after = inspect_av(destination).to_dict()
        limited = False
        if AV_EXTENSIONS[suffix] == 'flac':
            offset = data.find(b'fLaC') + 4
            while offset + 4 <= len(data):
                kind = data[offset] & 127
                last = data[offset] & 128
                size = int.from_bytes(data[offset + 1:offset + 4], 'big')
                limited = limited or kind in {2, 4, 6}
                offset += 4 + size
                if last:
                    break
        elif suffix == '.mp3' and len(data) >= 128 and data[-128:-125] == b'TAG':
            limited = True
        if limited:
            after['notes'].append('Native FLAC tags or legacy MP3 ID3v1 tags are outside this upstream cleaner; some metadata is retained.')
            report['actions'].append(after['notes'][-1])
        return before, after, report['actions'], bool(limited or report['still_has_c2pa'] or report['still_has_ai_metadata'])
    fmt = IMAGE_EXTENSIONS[suffix]
    inspector = getattr(image_meta, f'inspect_{fmt}') if fmt not in {'avif', 'heic'} else lambda raw: image_meta.inspect_isobmff(raw, fmt)
    if fmt == 'png':
        cleaned, actions = image_meta.strip_png(data, strip_all_text=True)
    elif fmt == 'jpeg':
        cleaned, actions = image_meta.strip_jpeg(data, strip_all_app=True)
    elif fmt in {'avif', 'heic'}:
        cleaned, actions = image_meta.strip_isobmff(data, fmt, strip_all_metadata=True)
    else:
        cleaned, actions = getattr(image_meta, f'strip_{fmt}')(data, strip_all_metadata=True)
    common.safe_write_bytes(destination, cleaned)
    def inspect(raw):
        c2pa, ai, findings = inspector(raw)
        return {'format': fmt, 'has_c2pa': c2pa, 'has_ai_metadata': ai, 'findings': findings, 'notes': []}
    before, after = inspect(data), inspect(cleaned)
    partial = after['has_c2pa'] or after['has_ai_metadata'] or any('truncat' in action.lower() for action in actions)
    return before, after, actions, bool(partial)
