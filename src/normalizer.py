"""Stage 2 of the pipeline: normalization of tokens into index terms.

- Unicode NFKC folds full-width/half-width variants into one form:
  ＡＢＣ -> ABC, １２３ -> 123, ｶﾀｶﾅ -> カタカナ
- Latin letters are lowercased.
- Tokens made only of punctuation, symbols or whitespace (。、「」！…) are
  dropped, so they do not occupy positions in the index.

Particles such as は/の/が are deliberately NOT removed as stop words:
phrase queries like 下人の行方 need them to stay in the position sequence.
"""

import unicodedata
from dataclasses import dataclass

from .tokenizer import Token, tokenize


@dataclass(frozen=True)
class Term:
    term: str  # normalized form stored in the index
    token: Token  # the original token it came from (surface + offsets)


def normalize_text(text: str) -> str:
    """Fold full-width/half-width variants and lowercase Latin letters."""
    return unicodedata.normalize("NFKC", text).lower().strip()


def is_punctuation(text: str) -> bool:
    """True if every character is punctuation (P*), a symbol (S*) or a separator/control (Z*, C*)."""
    return all(unicodedata.category(ch)[0] in "PSZC" for ch in text)


def normalize(tokens: list[Token]) -> list[Term]:
    """Turn tokens into index terms, dropping punctuation-only tokens."""
    terms = []
    for token in tokens:
        term = normalize_text(token.surface)
        if term and not is_punctuation(term):
            terms.append(Term(term, token))
    return terms


def analyze(text: str) -> list[Term]:
    """Full text-analysis chain shared by documents AND queries: tokenize -> normalize."""
    return normalize(tokenize(text))
