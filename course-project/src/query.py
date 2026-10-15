"""Query parsing: turn a query string into an expression tree.

Syntax (operators are upper-case ASCII and must be separated by spaces):

    下人 AND 老婆          both terms in the document
    メロス OR セリヌンティウス  either term
    下人 AND NOT 老婆      first but not second
    "下人の行方"            phrase: terms adjacent and in this order
    下人 /5 太刀           proximity: within 5 positions, either order
    (猫 OR 狐) AND 森       parentheses for grouping
    猫 森                  implicit AND

Every word or quoted phrase is run through the SAME analyze() pipeline as
the documents (fugashi tokenization + normalization). Japanese has no spaces,
so an unquoted word like 走れメロス may produce several tokens; it is then
treated as a phrase, which is what the user meant.

Grammar:
    expr    := and_expr ("OR" and_expr)*
    and_expr:= not_expr (["AND"] not_expr)*
    not_expr:= "NOT" not_expr | prox
    prox    := primary ("/k" primary)?
    primary := "(" expr ")" | PHRASE | WORD
"""

import re
from dataclasses import dataclass

from .normalizer import analyze


@dataclass(frozen=True)
class Phrase:
    """A sequence of one or more terms that must appear adjacently (a single term is a 1-term phrase)."""

    terms: tuple[str, ...]


@dataclass(frozen=True)
class Proximity:
    left: Phrase
    right: Phrase
    k: int


@dataclass(frozen=True)
class And:
    left: object
    right: object


@dataclass(frozen=True)
class Or:
    left: object
    right: object


@dataclass(frozen=True)
class Not:
    operand: object


class QueryError(ValueError):
    pass


# Quoted phrase | parenthesis | /k | any run of non-space, non-paren, non-quote chars.
_TOKEN_RE = re.compile(r'"([^"]*)"|“([^”]*)”|「([^」]*)」|([()（）])|/(\d+)|([^\s()（）"“”「」]+)')
_OPERATORS = {"AND", "OR", "NOT"}


def lex(query: str) -> list[tuple[str, str]]:
    """Split a query into (kind, value) tokens: PHRASE, LPAREN, RPAREN, PROX, OP, WORD."""
    tokens = []
    for m in _TOKEN_RE.finditer(query):
        phrase = next((g for g in m.group(1, 2, 3) if g is not None), None)
        if phrase is not None:
            tokens.append(("PHRASE", phrase))
        elif m.group(4):
            tokens.append(("LPAREN" if m.group(4) in "(（" else "RPAREN", m.group(4)))
        elif m.group(5):
            tokens.append(("PROX", m.group(5)))
        elif m.group(6) in _OPERATORS:
            tokens.append(("OP", m.group(6)))
        else:
            tokens.append(("WORD", m.group(6)))
    return tokens


def to_phrase(text: str) -> Phrase:
    """Analyze query text with the document pipeline (tokenize -> normalize)."""
    terms = tuple(t.term for t in analyze(text))
    if not terms:
        raise QueryError(f"'{text}' contains no searchable words (only punctuation?)")
    return Phrase(terms)


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        if not self.tokens:
            raise QueryError("empty query")
        node = self.expr()
        if self.peek()[0] is not None:
            raise QueryError(f"unexpected '{self.peek()[1]}'")
        return node

    def expr(self):
        node = self.and_expr()
        while self.peek() == ("OP", "OR"):
            self.take()
            node = Or(node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while True:
            kind, value = self.peek()
            if (kind, value) == ("OP", "AND"):
                self.take()
            elif kind in ("WORD", "PHRASE", "LPAREN") or (kind, value) == ("OP", "NOT"):
                pass  # implicit AND
            else:
                return node
            node = And(node, self.not_expr())

    def not_expr(self):
        if self.peek() == ("OP", "NOT"):
            self.take()
            return Not(self.not_expr())
        return self.prox()

    def prox(self):
        node = self.primary()
        if self.peek()[0] == "PROX":
            k = int(self.take()[1])
            right = self.primary()
            if not isinstance(node, Phrase) or not isinstance(right, Phrase):
                raise QueryError("both sides of /k must be words or phrases")
            node = Proximity(node, right, k)
        return node

    def primary(self):
        kind, value = self.take()
        if kind == "LPAREN":
            node = self.expr()
            if self.take()[0] != "RPAREN":
                raise QueryError("missing ')'")
            return node
        if kind in ("WORD", "PHRASE"):
            return to_phrase(value)
        if kind is None:
            raise QueryError("query ended unexpectedly")
        raise QueryError(f"unexpected '{value}'")


def parse_query(query: str):
    """Parse a query string into an expression tree of Phrase/Proximity/And/Or/Not."""
    return _Parser(lex(query)).parse()
