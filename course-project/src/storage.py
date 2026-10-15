"""Storage and retrieval: persist the index to disk and load it back.

Format: JSON, chosen over pickle because
- it is human-readable and viewable on GitHub (the index is linked from the README),
- it is language-independent, and
- loading it cannot execute arbitrary code (unpickling untrusted files can).

Japanese text: files are always opened with encoding="utf-8" (the Windows
default would be cp1252/cp932) and written with ensure_ascii=False, so terms
appear as 下人 rather than "\\u4e0b\\u4eba" escape sequences.

Two files are written to the index directory:
- index.json      meta + document table + positional postings (the inverted index)
- doc_store.json  original text and per-position character spans, used only for snippets
"""

import json
from pathlib import Path

from .indexer import InvertedIndex

INDEX_FILE = "index.json"
STORE_FILE = "doc_store.json"


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def save_index(index: InvertedIndex, index_dir: str | Path) -> Path:
    """Write the index as JSON, one document / one term per line for readability."""
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    lines = ["{", f'"meta":{_dumps(index.meta)},', '"docs":{']
    doc_lines = [f'"{doc_id}":{_dumps(info)}' for doc_id, info in sorted(index.docs.items())]
    lines.append(",\n".join(doc_lines))
    lines += ["},", '"postings":{']
    term_lines = [
        f"{_dumps(term)}:{_dumps({str(d): p for d, p in sorted(docs.items())})}"
        for term, docs in sorted(index.postings.items())
    ]
    lines.append(",\n".join(term_lines))
    lines += ["}", "}"]
    index_path = index_dir / INDEX_FILE
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    store_lines = [f'"{doc_id}":{_dumps(entry)}' for doc_id, entry in sorted(index.store.items())]
    (index_dir / STORE_FILE).write_text("{\n" + ",\n".join(store_lines) + "\n}\n", encoding="utf-8")
    return index_path


def load_index(index_dir: str | Path) -> InvertedIndex:
    """Load a previously built index without re-tokenizing any documents."""
    index_dir = Path(index_dir)
    with open(index_dir / INDEX_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    index = InvertedIndex(
        meta=raw["meta"],
        docs={int(d): info for d, info in raw["docs"].items()},
        # JSON object keys are always strings; convert doc IDs back to int.
        postings={term: {int(d): p for d, p in docs.items()} for term, docs in raw["postings"].items()},
    )
    store_path = index_dir / STORE_FILE
    if store_path.exists():
        with open(store_path, encoding="utf-8") as f:
            index.store = {int(d): entry for d, entry in json.load(f).items()}
    return index
