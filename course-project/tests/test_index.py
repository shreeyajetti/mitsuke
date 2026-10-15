"""Unit tests on a tiny synthetic collection.  Run:  python -m unittest -v"""

import tempfile
import unittest

from src.indexer import Document, build_index
from src.normalizer import analyze
from src.query import Phrase, QueryError, parse_query
from src.search import search
from src.storage import load_index, save_index
from src.tokenizer import tokenize

DOCS = [
    Document(0, "A", "x", "a.txt", "猫が犬を見た。猫は眠った。"),
    Document(1, "B", "x", "b.txt", "犬が猫を見た。"),
    Document(2, "C", "x", "c.txt", "ＡＢＣの鳥が鳴いた。"),
]


def doc_ids(index, query):
    return sorted(r.doc_id for r in search(index, query))


class TestPipeline(unittest.TestCase):
    def test_tokenizer_segments_japanese(self):
        self.assertEqual([t.surface for t in tokenize("吾輩は猫である。")], ["吾輩", "は", "猫", "で", "ある", "。"])

    def test_normalizer_folds_width_and_drops_punctuation(self):
        self.assertEqual([t.term for t in analyze("ＡＢＣの鳥、「abc」。")], ["abc", "の", "鳥", "abc"])


class TestIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = build_index(DOCS)

    def test_all_positions_are_stored(self):
        # 猫(0) が(1) 犬(2) を(3) 見(4) た(5) 猫(6) は(7) 眠っ(8) た(9)
        self.assertEqual(self.index.get_postings("猫"), {0: [0, 6], 1: [2]})

    def test_boolean(self):
        self.assertEqual(doc_ids(self.index, "猫 AND 犬"), [0, 1])
        self.assertEqual(doc_ids(self.index, "猫 OR 鳥"), [0, 1, 2])
        self.assertEqual(doc_ids(self.index, "NOT 猫"), [2])
        self.assertEqual(doc_ids(self.index, "猫 AND NOT 眠っ"), [1])

    def test_phrase_requires_adjacency_and_order(self):
        self.assertEqual(doc_ids(self.index, '"猫が犬"'), [0])
        self.assertEqual(doc_ids(self.index, '"犬が猫"'), [1])
        self.assertEqual(doc_ids(self.index, '"猫犬"'), [])  # both present but not adjacent

    def test_unquoted_multi_token_word_is_a_phrase(self):
        self.assertEqual(parse_query("猫が犬"), Phrase(("猫", "が", "犬")))

    def test_query_goes_through_same_normalization(self):
        self.assertEqual(doc_ids(self.index, "abc"), [2])
        self.assertEqual(doc_ids(self.index, "ａｂｃ"), [2])

    def test_proximity_distance_and_order(self):
        # doc 0: 猫=0, 犬=2 (distance 2); doc 1: 犬=0, 猫=2 (distance 2, reversed order)
        self.assertEqual(doc_ids(self.index, "猫 /2 犬"), [0, 1])
        self.assertEqual(doc_ids(self.index, "犬 /2 猫"), [0, 1])
        self.assertEqual(doc_ids(self.index, "猫 /1 犬"), [])

    def test_proximity_term_with_itself(self):
        self.assertEqual(doc_ids(self.index, "猫 /6 猫"), [0])  # positions 0 and 6
        self.assertEqual(doc_ids(self.index, "猫 /5 猫"), [])  # a word is not near itself

    def test_match_positions(self):
        [result] = search(self.index, '"猫は眠っ"')
        self.assertEqual(result.matches, [(6, 8)])

    def test_query_errors(self):
        for bad in ["", "猫 AND", "(猫", "。", "猫 /2"]:
            with self.assertRaises(QueryError, msg=bad):
                parse_query(bad)


class TestStorage(unittest.TestCase):
    def test_round_trip(self):
        index = build_index(DOCS)
        with tempfile.TemporaryDirectory() as tmp:
            save_index(index, tmp)
            loaded = load_index(tmp)
        self.assertEqual(loaded.postings, index.postings)
        self.assertEqual(loaded.docs, index.docs)
        self.assertEqual(loaded.store, index.store)
        self.assertEqual(doc_ids(loaded, '"猫が犬"'), [0])


if __name__ == "__main__":
    unittest.main()
