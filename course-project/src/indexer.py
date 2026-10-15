"""Stage 3 of the pipeline: build a positional inverted index.

Data model
----------
postings: term -> {doc_id -> sorted list of positions}

    "下人": {0: [3, 41, 120], 5: [77]}

A position is the 0-based index of the term in the document's normalized
term sequence (punctuation already removed). Storing *every* position, not
just the fact that a term occurs, is what makes phrase and proximity
queries possible: "A B" matches only where pos(B) == pos(A) + 1.

Alongside the postings, the index keeps per-document metadata (`docs`) and a
small document store (`store`: original text + character span of each
position) used only to print snippets around matches.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .normalizer import analyze


@dataclass
class Document:
    doc_id: int
    title: str
    author: str
    file: str
    text: str


@dataclass
class InvertedIndex:
    meta: dict = field(default_factory=dict)
    docs: dict[int, dict] = field(default_factory=dict)
    postings: dict[str, dict[int, list[int]]] = field(default_factory=dict)
    store: dict[int, dict] = field(default_factory=dict)

    def get_postings(self, term: str) -> dict[int, list[int]]:
        return self.postings.get(term, {})

    def all_doc_ids(self) -> set[int]:
        return set(self.docs)


def load_documents(data_dir: str | Path) -> list[Document]:
    """Read the documents listed in data/metadata.json (UTF-8 plain text)."""
    data_dir = Path(data_dir)
    with open(data_dir / "metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)
    documents = []
    for doc_id, entry in enumerate(metadata):
        path = data_dir / entry["file"]
        text = path.read_text(encoding="utf-8")
        documents.append(Document(doc_id, entry["title"], entry["author"], path.as_posix(), text))
    return documents


def build_index(documents: list[Document]) -> InvertedIndex:
    """Run every document through the pipeline and record term positions."""
    index = InvertedIndex()
    for doc in documents:
        terms = analyze(doc.text)
        for position, t in enumerate(terms):
            index.postings.setdefault(t.term, {}).setdefault(doc.doc_id, []).append(position)
        index.docs[doc.doc_id] = {
            "title": doc.title,
            "author": doc.author,
            "file": doc.file,
            "num_terms": len(terms),
        }
        index.store[doc.doc_id] = {
            "text": doc.text,
            "spans": [[t.token.start, t.token.end] for t in terms],
        }
    # Positions are appended in increasing order, so each list is already sorted.
    index.meta = {
        "tokenizer": "fugashi (MeCab) + unidic-lite",
        "term_form": "surface form",
        "normalization": "NFKC + lowercase, punctuation/symbol tokens removed",
        "num_docs": len(index.docs),
        "num_terms": len(index.postings),
        "num_postings": sum(len(p) for p in index.postings.values()),
        "num_positions": sum(d["num_terms"] for d in index.docs.values()),
    }
    return index
