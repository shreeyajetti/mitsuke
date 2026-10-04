"""Command-line interface.

    python -m src.cli build    [--data data] [--index index]   # Storage
    python -m src.cli stats    [--index index]                 # Retrieval (load + inspect)
    python -m src.cli search   "QUERY" [--index index]         # Search
    python -m src.cli search                                   # interactive search prompt
    python -m src.cli tokenize "日本語の文"                      # show the analysis pipeline
"""

import argparse
import sys
import time
import unicodedata

from .indexer import build_index, load_documents
from .normalizer import normalize
from .query import QueryError
from .search import search, snippet
from .storage import load_index, save_index
from .tokenizer import tokenize


def cmd_build(args) -> None:
    started = time.perf_counter()
    documents = load_documents(args.data)
    print(f"Loaded {len(documents)} documents from {args.data}/")
    index = build_index(documents)
    for doc_id, info in index.docs.items():
        print(f"  [{doc_id:2}] {info['title']} / {info['author']}: {info['num_terms']:,} terms")
    path = save_index(index, args.index)
    m = index.meta
    print(
        f"Indexed {m['num_docs']} docs: {m['num_terms']:,} distinct terms, "
        f"{m['num_postings']:,} postings, {m['num_positions']:,} positions "
        f"in {time.perf_counter() - started:.2f}s"
    )
    print(f"Saved index to {path.as_posix()}")


def cmd_stats(args) -> None:
    started = time.perf_counter()
    index = load_index(args.index)
    print(f"Loaded index from {args.index}/ in {time.perf_counter() - started:.3f}s (no re-tokenization)")
    for key, value in index.meta.items():
        print(f"  {key}: {value}")
    if args.term:
        for term in args.term:
            postings = index.get_postings(term)
            print(f"\nPostings for {term!r} (document frequency {len(postings)}):")
            for doc_id, positions in sorted(postings.items()):
                print(f"  doc {doc_id} ({index.docs[doc_id]['title']}): tf={len(positions)} positions={positions}")


def print_results(index, query: str, max_snippets: int) -> None:
    try:
        results = search(index, query)
    except QueryError as e:
        print(f"Query error: {e}")
        return
    print(f"Query: {query}  ->  {len(results)} document(s)")
    for r in results:
        print(f"  doc {r.doc_id:2}  {r.title} / {r.author}  ({len(r.matches)} match(es))")
        for match in r.matches[:max_snippets]:
            print(f"      positions {match[0]}-{match[1]}: {snippet(index, r.doc_id, match)}")
        if len(r.matches) > max_snippets:
            print(f"      ... {len(r.matches) - max_snippets} more")


def cmd_search(args) -> None:
    index = load_index(args.index)
    if args.query:
        print_results(index, args.query, args.snippets)
        return
    print("Interactive search. Examples: 下人 AND 老婆 | \"下人の行方\" | メロス /3 王 | empty line to quit")
    while True:
        try:
            query = input("query> ").strip()
        except EOFError:
            break
        if not query:
            break
        print_results(index, query, args.snippets)


def pad(text: str, width: int) -> str:
    """Left-justify text, counting full-width (Japanese) characters as two columns."""
    display = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)
    return text + " " * max(1, width - display)


def cmd_tokenize(args) -> None:
    tokens = tokenize(args.text)
    print(f"Input: {args.text}")
    print("\n1. Tokenizer (fugashi):")
    print("   " + " | ".join(t.surface for t in tokens))
    print(f"   {pad('surface', 10)}{pad('lemma', 10)}{pad('POS', 10)}chars")
    for t in tokens:
        print(f"   {pad(t.surface, 10)}{pad(t.lemma, 10)}{pad(t.pos, 10)}{t.start}-{t.end}")
    terms = normalize(tokens)
    print("\n2. Normalizer (NFKC, lowercase, punctuation removed) -> index terms with positions:")
    print("   " + "  ".join(f"{i}:{t.term}" for i, t in enumerate(terms)))


def main(argv=None) -> None:
    # Windows consoles default to cp1252, which cannot print Japanese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Positional inverted index over Japanese texts (Aozora Bunko)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help="build the index from data/ and save it to index/")
    p.add_argument("--data", default="data")
    p.add_argument("--index", default="index")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("stats", help="load a saved index and print statistics / postings")
    p.add_argument("--index", default="index")
    p.add_argument("--term", nargs="*", help="show the positional postings list of these terms")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("search", help="run a query against a saved index")
    p.add_argument("query", nargs="?", help="omit for an interactive prompt")
    p.add_argument("--index", default="index")
    p.add_argument("--snippets", type=int, default=3, help="max snippets shown per document")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("tokenize", help="show tokenizer and normalizer output for a sentence")
    p.add_argument("text")
    p.set_defaults(func=cmd_tokenize)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
