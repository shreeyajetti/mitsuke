"""Search: evaluate a parsed query against a loaded InvertedIndex.

Every sub-expression evaluates to  {doc_id -> list of matches}, where a match
is a (first_position, last_position) span of term positions. Boolean
operators combine these per document; phrase and proximity operators use the
positions stored in the postings.
"""

from dataclasses import dataclass

from .indexer import InvertedIndex
from .query import And, Not, Or, Phrase, Proximity, parse_query

Matches = dict[int, list[tuple[int, int]]]


@dataclass
class SearchResult:
    doc_id: int
    title: str
    author: str
    matches: list[tuple[int, int]]  # (first_position, last_position), inclusive


def phrase_starts(index: InvertedIndex, terms: tuple[str, ...]) -> dict[int, list[int]]:
    """Positions where the phrase begins: term i must be at start + i in the same document."""
    postings = [index.get_postings(t) for t in terms]
    if not all(postings):
        return {}
    # Only documents containing every term can contain the phrase (smallest list first).
    candidate_docs = set.intersection(*(set(p) for p in sorted(postings, key=len)))
    result = {}
    for doc_id in candidate_docs:
        later = [set(p[doc_id]) for p in postings[1:]]
        starts = [s for s in postings[0][doc_id] if all(s + i in later[i - 1] for i in range(1, len(terms)))]
        if starts:
            result[doc_id] = starts
    return result


def eval_phrase(index: InvertedIndex, node: Phrase) -> Matches:
    n = len(node.terms)
    return {d: [(s, s + n - 1) for s in starts] for d, starts in phrase_starts(index, node.terms).items()}


def eval_proximity(index: InvertedIndex, node: Proximity) -> Matches:
    """Both sides in the same document with start positions at most k apart (either order).

    Uses a two-pointer sliding window over the two sorted position lists.
    """
    left, right = phrase_starts(index, node.left.terms), phrase_starts(index, node.right.terms)
    len_l, len_r, k = len(node.left.terms), len(node.right.terms), node.k
    same_phrase = node.left == node.right
    result = {}
    for doc_id in left.keys() & right.keys():
        lpos, rpos = left[doc_id], right[doc_id]
        matches = []
        j = 0
        for p in lpos:
            while j < len(rpos) and rpos[j] < p - k:  # slide window start up to p - k
                j += 1
            m = j
            while m < len(rpos) and rpos[m] <= p + k:
                q = rpos[m]
                if not (same_phrase and q == p):  # a word is not "near" itself
                    matches.append((min(p, q), max(p + len_l - 1, q + len_r - 1)))
                m += 1
        if matches:
            result[doc_id] = sorted(set(matches))
    return result


def evaluate(index: InvertedIndex, node) -> Matches:
    if isinstance(node, Phrase):
        return eval_phrase(index, node)
    if isinstance(node, Proximity):
        return eval_proximity(index, node)
    if isinstance(node, And):
        left, right = evaluate(index, node.left), evaluate(index, node.right)
        return {d: sorted(set(left[d]) | set(right[d])) for d in left.keys() & right.keys()}
    if isinstance(node, Or):
        left, right = evaluate(index, node.left), evaluate(index, node.right)
        return {d: sorted(set(left.get(d, [])) | set(right.get(d, []))) for d in left.keys() | right.keys()}
    if isinstance(node, Not):
        # NOT matches documents, not positions, so there is nothing to highlight.
        excluded = evaluate(index, node.operand)
        return {d: [] for d in index.all_doc_ids() - excluded.keys()}
    raise TypeError(f"unknown query node {node!r}")


def search(index: InvertedIndex, query: str) -> list[SearchResult]:
    """Parse and run a query; results are ordered by number of matches, then doc ID."""
    matches = evaluate(index, parse_query(query))
    results = [
        SearchResult(d, index.docs[d]["title"], index.docs[d]["author"], spans) for d, spans in matches.items()
    ]
    results.sort(key=lambda r: (-len(r.matches), r.doc_id))
    return results


def snippet(index: InvertedIndex, doc_id: int, match: tuple[int, int], context: int = 15) -> str:
    """Original text around a match, with the matched span wrapped in 【】."""
    entry = index.store.get(doc_id)
    if entry is None:
        return ""
    text, spans = entry["text"], entry["spans"]
    start, end = spans[match[0]][0], spans[match[1]][1]
    before = text[max(0, start - context) : start]
    after = text[end : end + context]
    return " ".join(f"…{before}【{text[start:end]}】{after}…".split())
