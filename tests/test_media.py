import base64
import io
from pathlib import Path
import struct
import wave

import pytest

from nomark.engine import ProcessingError, process_file

FIXTURES = Path(__file__).parent / 'fixtures/media'


@pytest.mark.parametrize('extension', ['png', 'jpg', 'webp', 'gif', 'bmp', 'tiff', 'avif', 'wav'])
def test_real_media_samples_clean_and_validate(tmp_path, extension):
    source = FIXTURES / f'sample.{extension}'
    result = process_file(source, source.name, tmp_path)
    assert result['status'] in {'cleaned', 'unchanged', 'partial'}
    output = base64.b64decode(result['cleaned_base64'])
    assert output
    assert result['bytes_out'] == len(output)
    assert result['report']['after']['format']
    assert str(tmp_path) not in str(result)
    if extension in {'png', 'jpg', 'webp', 'gif', 'tiff', 'wav'}:
        assert result['status'] == 'cleaned'
        assert b'stable diffusion' not in output
    if extension == 'wav':
        with wave.open(io.BytesIO(source.read_bytes())) as before, wave.open(io.BytesIO(output)) as after:
            assert before.getparams() == after.getparams()
            assert before.readframes(before.getnframes()) == after.readframes(after.getnframes())


def box(kind, payload):
    return struct.pack('>I', len(payload) + 8) + kind + payload


@pytest.mark.parametrize('extension', ['mp4', 'mov', 'm4v', 'm4a'])
def test_av_metadata_removal_preserves_sample_offsets(tmp_path, extension):
    # A minimal container tests metadata boundaries; this is not a decodable clip.
    sample_data = b'media-payload-preserved'
    ftyp = box(b'ftyp', b'isom\0\0\0\0isom')
    moov = box(b'moov', box(b'udta', b'stable diffusion'))
    original = ftyp + moov + box(b'mdat', sample_data)
    source = tmp_path / f'input.{extension}'
    source.write_bytes(original)
    result = process_file(source, source.name, tmp_path)
    output = base64.b64decode(result['cleaned_base64'])
    assert output.index(b'mdat') == original.index(b'mdat')
    assert output.endswith(sample_data)
    assert b'stable diffusion' not in output
    assert result['status'] == 'cleaned'


@pytest.mark.parametrize('extension,data', [
    ('png', b'\x89PNG\r\n\x1a\n'), ('jpg', b'\xff\xd8broken'),
    ('webp', b'RIFF\xff\xff\xff\xffWEBP'), ('wav', b'RIFF\0\0\0\0WAVE'),
    ('mp4', box(b'ftyp', b'isom\0\0\0\0isom')),
    ('mp3', b'ID3\x04\0\0\0\0\0\0'), ('flac', b'fLaC'),
    ('gif', b'GIF89a'), ('tiff', b'II*\0'), ('heic', b'not an image'),
])
def test_rejects_truncated_or_mismatched_media(tmp_path, extension, data):
    source = tmp_path / f'broken.{extension}'
    source.write_bytes(data)
    with pytest.raises(ProcessingError, match='invalid_document'):
        process_file(source, source.name, tmp_path)


def test_mp3_strips_id3_without_changing_audio_frames(tmp_path):
    audio = b'\xff\xfb\x90\x64' + bytes(413)
    text = b'stable diffusion'
    frame = b'TENC' + struct.pack('>I', len(text) + 1) + b'\0\0\0' + text
    original = b'ID3\x03\0\0\0\0\0' + bytes([len(frame)]) + frame + audio
    source = tmp_path / 'sample.mp3'
    source.write_bytes(original)
    result = process_file(source, source.name, tmp_path)
    assert base64.b64decode(result['cleaned_base64']) == audio


def test_flac_keeps_streaminfo_and_audio_data(tmp_path):
    audio = b'\xff\xf8' + bytes(32)
    streaminfo = bytes(34)
    text = b'stable diffusion'
    original = b'fLaC' + b'\0\0\0\x22' + streaminfo + bytes([0x84]) + len(text).to_bytes(3, 'big') + text + audio
    source = tmp_path / 'sample.flac'
    source.write_bytes(original)
    result = process_file(source, source.name, tmp_path)
    output = base64.b64decode(result['cleaned_base64'])
    assert output.endswith(audio)
    assert streaminfo in output
    assert text in output
    assert result['status'] == 'partial'
    assert 'metadata is retained' in str(result['report'])


@pytest.mark.parametrize('extension,content', [
    ('tex', '\\documentclass{article}\n\\begin{document}Hello\u200bworld\\end{document}'),
    ('svg', '<svg xmlns="http://www.w3.org/2000/svg"><metadata>stable diffusion</metadata><rect width="8" height="8"/></svg>'),
])
def test_text_source_and_svg_clean_without_rendering_or_compiling(tmp_path, extension, content):
    source = tmp_path / f'sample.{extension}'
    source.write_text(content)
    result = process_file(source, source.name, tmp_path)
    output = base64.b64decode(result['cleaned_base64']).decode()
    assert result['status'] == 'cleaned'
    assert '\u200b' not in output
    assert 'stable diffusion' not in output


def test_svg_external_entities_are_rejected(tmp_path):
    source = tmp_path / 'sample.svg'
    source.write_text('<!DOCTYPE svg [<!ENTITY test SYSTEM "file:///etc/passwd">]><svg>&test;</svg>')
    with pytest.raises(ProcessingError, match='invalid_document'):
        process_file(source, source.name, tmp_path)
