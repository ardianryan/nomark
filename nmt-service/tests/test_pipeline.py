import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nmt_service.pipeline import Pipeline, acceptable_edit, sentences, build_edits
from nmt_service.main import create_app


class Model:
    def __init__(self, path): pass
    def tokens(self, text): return text.split()
    def translate(self, text): return text
    def candidates(self, text): return [self.translate(text)]


def test_preserves_paragraphs_lists_and_protected_content():
    pipe = Pipeline('/unused', Model)
    source = '  - Hello 42 https://example.com\n\n1. Halo user@example.com\r\n'
    result = pipe.paraphrase(source, 'en')
    assert result['paraphrased_text'] == source
    assert result['warnings'] == ['review_required']


def test_failed_protection_preserves_original_and_reports_partial():
    class Broken(Model):
        def translate(self, text): return text.replace('42', '43')
    result = Pipeline('/unused', Broken).paraphrase('Hello 42.', 'id')
    assert result['paraphrased_text'] == 'Hello 42.'
    assert result['status'] == 'partial'
    assert 'segments_preserved' in result['warnings']


def test_unchanged_and_long_segment_splitting():
    class Same(Model):
        def translate(self, text):
            assert len(self.tokens(text)) <= 220
            return text
    pipe = Pipeline('/unused', Same)
    text = ' '.join(['word'] * 800)
    assert pipe.paraphrase(text, 'en')['paraphrased_text'] == text
    assert pipe.paraphrase('plain', 'id')['status'] == 'unchanged'


@pytest.mark.parametrize('language,original,candidate', [
    ('en', 'She signed the contract.', 'He signed the contract.'),
    ('en', 'They delivered a package.', 'They delivered packages.'),
    ('en', 'Nina paid Omar.', 'Omar paid Nina.'),
    ('en', 'They can leave.', 'They must leave.'),
    ('en', 'He did not agree.', 'He agreed.'),
    ('en', 'We bought five tickets.', 'We bought six tickets.'),
    ('en', 'The price decreased.', 'The price increased.'),
    ('en', 'Mira arrived yesterday.', 'Mira arrives today.'),
    ('en', 'The payment is optional.', 'The payment is mandatory.'),
    ('en', 'Ready?', 'Ready.'),
    ('id', 'Saya melarang pengiriman.', 'Saya mengizinkan pengiriman.'),
    ('id', 'Ia belum datang.', 'Ia sudah datang.'),
    ('id', 'Dana hanya untuk sekolah.', 'Dana untuk sekolah.'),
    ('id', 'Pembayaran paling lambat Jumat.', 'Pembayaran setelah Jumat.'),
    ('id', 'Rina menemui Dodi.', 'Dodi menemui Rina.'),
    ('id', 'Suhu turun dua derajat.', 'Suhu naik dua derajat.'),
    ('id', 'Layanan mungkin berhenti.', 'Layanan pasti berhenti.'),
    ('id', 'Simpan kedua salinan.', 'Simpan salinan.'),
])
def test_unverified_edits_are_rejected(language, original, candidate):
    assert not acceptable_edit(original, candidate, language)


@pytest.mark.parametrize('language,original,candidate', [
    ('en', 'We cannot proceed.', "We can't proceed."),
    ('en', 'They did not answer.', "They didn't answer."),
    ('en', 'Keep a copy of the receipt.', 'Save a copy of the receipt.'),
    ('id', 'Ia telah menyiapkan bahan.', 'Dia sudah mempersiapkan bahan.'),
    ('id', 'Usulan tersebut memerlukan evaluasi.', 'Usulan itu membutuhkan evaluasi.'),
])
def test_reviewed_surface_edits_are_accepted(language, original, candidate):
    assert acceptable_edit(original, candidate, language)


def test_selects_verified_candidate_instead_of_highest_scoring_error():
    class Alternatives(Model):
        def candidates(self, text):
            return ['They must proceed.', "They can't proceed.", text]
    result = Pipeline('/unused', Alternatives).paraphrase('They cannot proceed.', 'en')
    assert result['paraphrased_text'] == "They can't proceed."
    assert result['status'] == 'paraphrased'


def test_failed_edits_keep_spacing_and_abbreviations():
    class Broken(Model):
        def translate(self, text): return 'Wrong meaning.'
    text = 'Dr. Lestari  belum hadir.\t\tIa datang besok.  '
    result = Pipeline('/unused', Broken).paraphrase(text, 'id')
    assert result['paraphrased_text'] == text
    assert result['status'] == 'partial'
    assert list(sentences('Dr. Lestari datang. Ia pulang.')) == [
        ('Dr. Lestari datang.', ' '), ('Ia pulang.', '')]


def test_whitespace_alone_is_not_a_paraphrase():
    class Spacing(Model):
        def candidates(self, text): return [text.replace(' ', '  '), text]
    result = Pipeline('/unused', Spacing).paraphrase('Plain text.', 'en')
    assert result['paraphrased_text'] == 'Plain text.'
    assert result['status'] == 'unchanged'


def test_generated_space_before_punctuation_is_rejected():
    assert not acceptable_edit('Ia menunggu.', 'Ia menunggu .', 'id')


def test_edit_metadata_uses_codepoints_and_context_checked_alternatives():
    source, output = '🙂 We cannot proceed.', "🙂 We can't proceed."
    edits = build_edits(source, output, 'en')
    assert len(edits) == 1
    edit = edits[0]
    assert source[edit['input_start']:edit['input_end']] == 'cannot'
    assert output[edit['output_start']:edit['output_end']] == "can't"
    assert edit['output_start'] == 5
    assert edit['alternatives'] == ['can not']
    for choice in edit['alternatives']:
        assert acceptable_edit(source, output[:5] + choice + output[10:], 'en')


def test_metadata_limits_do_not_truncate_the_result():
    source, output = 'ia ' * 300, 'dia ' * 300
    edits = build_edits(source, output, 'id')
    assert len(edits) == 256
    assert edits[-1]['output_end'] < len(output)
    assert build_edits('She arrived.', 'He arrived.', 'en') == []


@pytest.mark.parametrize('payload,status', [({'text': 'hello', 'language': 'en'}, 200),
    ({'text': 'x' * 5001, 'language': 'id'}, 413), ({'text': 'hello', 'language': 'xx'}, 400),
    ({'text': '', 'language': 'en'}, 400), ({'text': '\ud800', 'language': 'en'}, 400)])
def test_internal_api(payload, status):
    class Runtime:
        def ready(self): return True
        async def process_text(self, text, language, disconnected): return {'ok': True}
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(Runtime())), base_url='http://test') as client:
            response = await client.post('/paraphrase', content=json.dumps(payload), headers={'Content-Type': 'application/json'})
            assert response.status_code == status
            assert response.headers['cache-control'] == 'no-store'
            assert (await client.post('/paraphrase', content=b'x' * 65537, headers={'Content-Type': 'application/json'})).status_code == 413
    asyncio.run(scenario())
