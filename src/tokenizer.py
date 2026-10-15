r"""Stage 1 of the pipeline: split Telugu text into word tokens.

Telugu separates words with spaces, but neither obvious approach works:

- str.split() leaves punctuation and invisible characters attached:
      "కి.మీ."  and  "విక్రమ్\u200c"  (with a zero-width non-joiner at the end)
- the regex \w+ treats Telugu vowel signs (combining marks) as non-word
  characters and shreds every word:
      విక్రమ్ -> వ / క / రమ

A Telugu syllable is a consonant plus vowel signs and the virama (్), which
Unicode classifies as *marks* (category M), not letters. So a token here is a
maximal run of letters (L), marks (M), numbers (N) and the zero-width
joiners U+200C/U+200D. Everything else (spaces, punctuation, symbols)
separates tokens.

Each token records its character offsets so search results can show a
snippet of the original text.
"""

import unicodedata
from dataclasses import dataclass

ZERO_WIDTH_JOINERS = {"\u200c", "\u200d"}  # ZWNJ, ZWJ


@dataclass(frozen=True)
class Token:
    surface: str  # the word exactly as written in the text
    start: int  # character offset in the original text (inclusive)
    end: int  # character offset in the original text (exclusive)


def is_word_char(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "LMN" or ch in ZERO_WIDTH_JOINERS


def tokenize(text: str) -> list[Token]:
    """Split text into word tokens with their character offsets."""
    tokens = []
    start = None
    for i, ch in enumerate(text):
        if is_word_char(ch):
            if start is None:
                start = i
        elif start is not None:
            tokens.append(Token(text[start:i], start, i))
            start = None
    if start is not None:
        tokens.append(Token(text[start:], start, len(text)))
    return tokens
