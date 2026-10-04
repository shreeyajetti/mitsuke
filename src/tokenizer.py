"""Stage 1 of the pipeline: Japanese morphological tokenization with fugashi.

Japanese is written without spaces between words, so `str.split()` would
return whole sentences. fugashi wraps the MeCab morphological analyser and,
with the unidic-lite dictionary, segments text into words (morphemes):

    吾輩は猫である。 -> 吾輩 / は / 猫 / で / ある / 。

Each token also records its character offsets in the original text so that
search results can later show a snippet of the original document.
"""

from dataclasses import dataclass

import fugashi

_tagger = None


@dataclass(frozen=True)
class Token:
    surface: str  # the word exactly as written in the text
    lemma: str  # dictionary form (kept for display/debugging; not indexed)
    pos: str  # coarse part of speech, e.g. 名詞 (noun), 助詞 (particle)
    start: int  # character offset in the original text (inclusive)
    end: int  # character offset in the original text (exclusive)


def get_tagger() -> fugashi.Tagger:
    """Create the MeCab tagger once; loading the dictionary is slow."""
    global _tagger
    if _tagger is None:
        _tagger = fugashi.Tagger()
    return _tagger


def tokenize(text: str) -> list[Token]:
    """Segment Japanese text into a list of Tokens (punctuation included)."""
    tokens = []
    offset = 0
    for word in get_tagger()(text):
        # MeCab skips whitespace before a word and reports it separately.
        offset += len(word.white_space)
        start, end = offset, offset + len(word.surface)
        offset = end
        lemma = word.feature.lemma or word.surface  # unknown words have no lemma
        tokens.append(Token(word.surface, lemma, word.feature.pos1, start, end))
    return tokens
