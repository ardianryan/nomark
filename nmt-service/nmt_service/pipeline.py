"""Offline back-translation with conservative segment fallback."""
import re
from pathlib import Path

PROTECTED = re.compile(r'https?://[^\s<>]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\S*\d\S*')
LAYOUT = re.compile(r'(\r\n|\r|\n)')
PREFIX = re.compile(r'^(\s*(?:(?:[-*•]|\d+[.)])\s+)?)')
WORDS = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]", re.UNICODE)

# A deliberately narrow edit vocabulary: everything else, including token order,
# punctuation, tense, pronouns and grammatical number, must survive unchanged.
# These are surface equivalences, not a semantic similarity score.
EQUIVALENTS = {
    'id': (
        ('tersebut', 'itu'), ('ia', 'dia'),
        ('menyiapkan', 'mempersiapkan'), ('memerlukan', 'membutuhkan'),
        ('telah', 'sudah'), ('tambahan', 'lebih lanjut'),
        ('terlebih dahulu', 'lebih dahulu'),
    ),
    'en': (
        ('do not', "don't"), ('does not', "doesn't"),
        ('did not', "didn't"), ('is not', "isn't"),
        ('are not', "aren't"), ('will not', "won't"),
        ('cannot', 'can not', "can't"),
        ('additional', 'further'),
        ('keep a copy', 'save a copy'),
    ),
}


def signature(text, language):
    """Normalize only reviewed surface edits, retaining the ordered token stream."""
    tokens = WORDS.findall(text.replace('’', "'"))
    for index, group in enumerate(EQUIVALENTS[language]):
        for phrase in sorted(group, key=len, reverse=True):
            pattern = WORDS.findall(phrase)
            cursor = 0
            while cursor <= len(tokens) - len(pattern):
                # Only the first token may change case at the start of a sentence.
                window = tokens[cursor:cursor + len(pattern)]
                if [word.lower() for word in window] == pattern:
                    tokens[cursor:cursor + len(pattern)] = [f'@{index}']
                cursor += 1
    return tokens


def acceptable_edit(original, candidate, language):
    return (PROTECTED.findall(original) == PROTECTED.findall(candidate)
            and re.findall(r'\s+[.,;:!?]', original) == re.findall(r'\s+[.,;:!?]', candidate)
            and signature(original, language) == signature(candidate, language))


def sentences(text):
    """Keep abbreviations and numeric tokens together and retain separators."""
    start = 0
    for match in re.finditer(r'(?<=[.!?])\s+', text):
        previous = text[start:match.start()].split()[-1]
        if (re.fullmatch(r'(?:Dr|Mr|Mrs|Ms|Prof|Ir|No|Fig|vs|etc)\.', previous, re.I)
                or re.fullmatch(r'(?:[A-Za-z]\.)+', previous)
                or PROTECTED.fullmatch(previous)):
            continue
        yield text[start:match.start()], match.group()
        start = match.end()
    yield text[start:], ''


class Model:
    def __init__(self, path):
        import ctranslate2
        from transformers import MarianTokenizer
        self.tokenizer = MarianTokenizer.from_pretrained(str(path / 'tokenizer'), local_files_only=True)
        self.translator = ctranslate2.Translator(str(path), device='cpu', compute_type='int8',
                                                inter_threads=1, intra_threads=2, max_queued_batches=1)

    def tokens(self, text):
        return self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(text))

    def candidates(self, text):
        tokens = self.tokens(text)
        if len(tokens) > 256:
            raise ValueError('segment_too_long')
        result = self.translator.translate_batch([tokens], beam_size=6, num_hypotheses=4,
                                                max_decoding_length=512)[0]
        candidates = []
        for output in result.hypotheses:
            if not output or len(output) >= 512:
                continue
            ids = self.tokenizer.convert_tokens_to_ids(output)
            decoded = self.tokenizer.decode(ids, skip_special_tokens=True).strip()
            if decoded and decoded not in candidates:
                candidates.append(decoded)
        if not candidates:
            raise ValueError('segment_empty_or_truncated')
        return candidates

    def translate(self, text):
        return self.candidates(text)[0]


class Pipeline:
    def __init__(self, directory, model_factory=Model):
        self.models = {pair: model_factory(Path(directory) / pair) for pair in ('en-id', 'id-en')}

    def paraphrase(self, text, language):
        forward, backward = (self.models['id-en'], self.models['en-id']) if language == 'id' else (self.models['en-id'], self.models['id-en'])
        preserved = False
        pieces = []
        for line in LAYOUT.split(text):
            if not line.strip() or LAYOUT.fullmatch(line):
                pieces.append(line)
                continue
            prefix = PREFIX.match(line).group()
            body = line[len(prefix):]
            trailing = body[len(body.rstrip()):]
            body = body.rstrip()
            rewritten = []
            for sentence, separator in sentences(body):
                chunks = []
                start = 0
                for word in re.finditer(r'\S+', sentence):
                    if word.start() > start and len(forward.tokens(sentence[start:word.end()])) > 220:
                        chunks.append(sentence[start:word.start()])
                        start = word.start()
                chunks.append(sentence[start:])
                for chunk in chunks:
                    whitespace = chunk[len(chunk.rstrip()):]
                    original = chunk.rstrip()
                    try:
                        safe = []
                        for first in forward.candidates(original):
                            for candidate in backward.candidates(first):
                                if acceptable_edit(original, candidate, language):
                                    safe.append(candidate)
                            if any(WORDS.findall(candidate) != WORDS.findall(original) for candidate in safe):
                                break
                        if not safe:
                            raise ValueError('unverified_edit')
                        rewritten.append(next((candidate for candidate in safe
                                               if WORDS.findall(candidate) != WORDS.findall(original)), original) + whitespace)
                    except ValueError:
                        rewritten.append(chunk)
                        preserved = True
                rewritten.append(separator)
            pieces.append(prefix + ''.join(rewritten) + trailing)
        output = ''.join(pieces)
        return {'ok': True, 'paraphrased_text': output, 'language': language,
                'status': 'partial' if preserved else 'unchanged' if output == text else 'paraphrased',
                'warnings': ['review_required'] + (['segments_preserved'] if preserved else [])}
