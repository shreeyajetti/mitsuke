"""Stage 3 of the pipeline: build a positional inverted index.

Data model
----------
postings: term -> {doc_id -> sorted list of positions}

    "గుంటూరు": {0: [0, 2, 36], 1: [0], ...}    # 458 passages in total

A position is the 0-based index of the term in the document's normalized
term sequence (punctuation already removed). Storing *every* position, not
just the fact that a term occurs, is what makes phrase and proximity
queries possible: "A B" matches only where pos(B) == pos(A) + 1.

A document is one MIRACL passage. Its indexed text is the article title
followed by the passage text, because passages often don't repeat the name of
what they describe.

Alongside the postings, the index keeps per-document metadata (`docs`) and a
document store (`store`: the indexed text) used only to print snippets. Term
character offsets are not stored; the snippet code re-tokenizes the one
passage it displays.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .normalizer import analyze


@dataclass
class Document:
    doc_id: int  # internal integer ID (0, 1, 2, ...)
    docid: str  # MIRACL passage ID, e.g. "786#0" = article 786, passage 0
    title: str
    text: str

    @property
    def indexed_text(self) -> str:
        return self.title + "\n" + self.text


@dataclass
class InvertedIndex:
    meta: dict = field(default_factory=dict)
    docs: dict[int, dict] = field(default_factory=dict)
    postings: dict[str, dict[int, list[int]]] = field(default_factory=dict)
    store: dict[int, str] = field(default_factory=dict)

    def get_postings(self, term: str) -> dict[int, list[int]]:
        return self.postings.get(term, {})

    def all_doc_ids(self) -> set[int]:
        return set(self.docs)


def load_documents(data_dir: str | Path) -> list[Document]:
    """Read data/passages.jsonl (one JSON passage per line, UTF-8)."""
    documents = []
    with open(Path(data_dir) / "passages.jsonl", encoding="utf-8") as f:
        for doc_id, line in enumerate(f):
            p = json.loads(line)
            documents.append(Document(doc_id, p["docid"], p["title"], p["text"]))
    return documents


def build_index(documents: list[Document]) -> InvertedIndex:
    """Run every document through the pipeline and record term positions."""
    index = InvertedIndex()
    for doc in documents:
        terms = analyze(doc.indexed_text)
        for position, t in enumerate(terms):
            index.postings.setdefault(t.term, {}).setdefault(doc.doc_id, []).append(position)
        index.docs[doc.doc_id] = {"docid": doc.docid, "title": doc.title, "num_terms": len(terms)}
        index.store[doc.doc_id] = doc.indexed_text
    # Positions are appended in increasing order, so each list is already sorted.
    index.meta = {
        "language": "Telugu",
        "collection": "MIRACL v1.0 Telugu (subset)",
        "tokenizer": "Unicode letter/mark/number runs",
        "normalization": "remove ZWNJ/ZWJ, NFKC, Telugu digits -> ASCII, lowercase",
        "num_docs": len(index.docs),
        "num_terms": len(index.postings),
        "num_postings": sum(len(p) for p in index.postings.values()),
        "num_positions": sum(d["num_terms"] for d in index.docs.values()),
    }
    return index
