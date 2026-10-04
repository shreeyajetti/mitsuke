# Mitsuke (見つけ)

*Japanese full-text search with positional indexing: phrase and proximity queries over Aozora Bunko literature.*

**Mitsuke** (見つけ, from 見つける, "to find") is an information-retrieval system in Python that builds a **positional inverted index** over 14 Japanese short stories from [Aozora Bunko (青空文庫)](https://www.aozora.gr.jp/). It supports **AND / OR / NOT**, **phrase**, and **proximity** (`term1 /k term2`) queries. Japanese text is segmented into words with the morphological analyser **fugashi** (MeCab + `unidic-lite`).

**Built index:** [`index/index.json`](index/index.json) (postings) · [`index/doc_store.json`](index/doc_store.json) (snippet store)
**Sample run:** [`sample_output.md`](sample_output.md)

---

## Repository structure

```
├── src/
│   ├── fetch_aozora.py  # download + clean Aozora texts into data/
│   ├── tokenizer.py     # pipeline stage 1: fugashi morphological tokenization
│   ├── normalizer.py    # pipeline stage 2: NFKC width folding, lowercase, punctuation removal
│   ├── indexer.py       # pipeline stage 3: builds the positional inverted index
│   ├── storage.py       # save / load the index as UTF-8 JSON
│   ├── query.py         # query parser (boolean, phrase, proximity)
│   ├── search.py        # query evaluation over positional postings + snippets
│   └── cli.py           # command-line interface: build / stats / search / tokenize
├── data/                # 14 cleaned UTF-8 texts + metadata.json (title, author, source URL)
├── index/               # the built index (committed so it can be viewed on GitHub)
├── tests/test_index.py  # unit tests on a tiny synthetic collection
├── sample_output.md     # index build, tokenization example, example queries
└── requirements.txt
```

## The collection

| ID | File | Title | Author |
|---:|---|---|---|
| 0 | `01_rashomon.txt` | 羅生門 | 芥川竜之介 |
| 1 | `02_kumo_no_ito.txt` | 蜘蛛の糸 | 芥川竜之介 |
| 2 | `03_hana.txt` | 鼻 | 芥川竜之介 |
| 3 | `04_toshishun.txt` | 杜子春 | 芥川竜之介 |
| 4 | `05_yabu_no_naka.txt` | 藪の中 | 芥川竜之介 |
| 5 | `06_mikan.txt` | 蜜柑 | 芥川竜之介 |
| 6 | `07_hashire_merosu.txt` | 走れメロス | 太宰治 |
| 7 | `08_chumon_no_ooi_ryoriten.txt` | 注文の多い料理店 | 宮沢賢治 |
| 8 | `09_yodaka_no_hoshi.txt` | よだかの星 | 宮沢賢治 |
| 9 | `10_gongitsune.txt` | ごん狐 | 新美南吉 |
| 10 | `11_tebukuro_wo_kaini.txt` | 手袋を買いに | 新美南吉 |
| 11 | `12_takasebune.txt` | 高瀬舟 | 森鴎外 |
| 12 | `13_remon.txt` | 檸檬 | 梶井基次郎 |
| 13 | `14_yume_juya.txt` | 夢十夜 | 夏目漱石 |

All works are in the public domain. `src/fetch_aozora.py` looks each title up in Aozora Bunko's official catalog CSV and prefers the modern-orthography edition (新字新仮名). It then downloads the zip, decodes it from **Shift_JIS** to Unicode and removes Aozora markup before saving the text as UTF-8. The markup removed is ruby readings `羅生門《らしょうもん》`, editorial notes `［＃…］`, the header and the `底本：` bibliography footer. Source URLs are recorded in `data/metadata.json`.

---

## The indexing pipeline

```
 raw text ──► Tokenizer ──► Normalization ──► Indexer ──► Inverted Index ──► Storage (JSON)
             (fugashi)    (NFKC, lowercase,  (assign      term → {doc →
                           drop punctuation)  positions)   [positions]}
```

Each stage is its own module. Documents and queries go through **the same** `analyze()` function (`tokenize` → `normalize`), so a query term always has the same form as the indexed term.

### 1. Tokenizer: `src/tokenizer.py`

**Why a whitespace split doesn't work for Japanese:** Japanese is written without spaces between words. `"吾輩は猫である。".split()` returns the whole sentence as a single "word". Splitting on punctuation only gives clauses, and splitting on every character destroys words like 下人 (servant) or 老婆 (old woman). Kanji, hiragana and katakana also follow each other with no marker at word boundaries.

The solution is a **morphological analyser**. MeCab (through the `fugashi` wrapper) uses a dictionary (`unidic-lite`) and a statistical cost model to find the most likely segmentation:

```
吾輩は猫である。  ──►  吾輩 | は | 猫 | で | ある | 。
一人の下人が、羅生門の下で雨やみを待っていた。
                ──►  一人 | の | 下人 | が | 、 | 羅生 | 門 | の | 下 | で | 雨やみ | を | 待っ | て | い | た | 。
```

For each token we keep the **surface form** (the text exactly as written), the lemma and part of speech for display, and the **character offsets** in the original text, which are used to print snippets.

**Design decision: index surface forms, not lemmas.** fugashi can also return the dictionary form (`待っ` → `待つ`). We index the surface form so that a phrase query matches the literal text of the document. The trade-off: searching `待つ` will not find the conjugated `待っ`.

### 2. Normalization: `src/normalizer.py`

- **Unicode NFKC** folds full-width and half-width variants into one form: `ＡＢＣ` → `ABC`, `１２３` → `123`, half-width `ｶﾀｶﾅ` → `カタカナ`. Without this, `ＡＢＣ` and `abc` would be different terms.
- **Lowercasing** for Latin letters.
- **Punctuation and symbol tokens are dropped** (。、「」！？…), detected by Unicode category, so they don't take up positions.
- **No stop-word removal.** Particles like は, の and が are very frequent, but phrase queries like `下人の行方` need them in the position sequence.

### 3. Indexer: `src/indexer.py`

The indexer numbers the normalized terms of each document 0, 1, 2, … and appends each position to that term's postings.

### 4. Inverted index: the positional data model

```python
postings: dict[str, dict[int, list[int]]]   # term -> {doc_id -> sorted positions}

"下人": {0: [10, 413, 461, 473, ...]}         # 72 occurrences in 羅生門
"行方": {0: [3348], 4: [1105]}
```

Alongside the postings, the index keeps:

- `docs`: per-document metadata (title, author, file, number of terms).
- `store`: the original text plus the character span of every position. It is used only to print snippets, so search results show the original text with its punctuation.

---

## Why positional indexing?

A basic inverted index only records **which** documents contain a term. That's enough for boolean queries but not for phrases. `下人 AND 行方` matches any document that has both words anywhere. The phrase `"下人の行方"` should only match where the three terms appear **next to each other, in that order**.

With every position stored, both kinds of query can be checked exactly:

- **Phrase** `t1 t2 … tn`: for each document containing all terms, keep the start positions *p* where *t1* is at *p*, *t2* at *p+1*, …, *tn* at *p+n−1*. In 羅生門, `下人`, `の` and `行方` are at positions 3346, 3347 and 3348, so the phrase matches. Every other occurrence of `下人` is followed by something other than `の行方`.
- **Proximity** `t1 /k t2`: for each document containing both terms, find pairs of positions with |pos(t1) − pos(t2)| ≤ k, in either order. Because both position lists are sorted, this is a **two-pointer sliding window** in O(|P1| + |P2| + matches) time.

The index stores **all** positions of a term in a document, not only the first one. Otherwise a phrase starting at the term's second occurrence would be missed.

Positions count normalized terms, so **particles count as positions and punctuation does not**. In `メロスは激怒した`, メロス (0) and 激怒 (2) are 2 positions apart. `メロス /1 激怒` therefore doesn't match, but `メロス /2 激怒` does.

---

## How to use this code

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt   # fugashi + unidic-lite (dictionary included, no MeCab install needed)
python -m unittest -v             # 12 tests
```

Tested with Python 3.13 on Windows. The CLI switches stdout to UTF-8 itself, because the default Windows console encoding (cp1252) can't print Japanese.

Optional: `python -m src.fetch_aozora` downloads the collection again into `data/`. The texts are already committed, so this step isn't needed.

### 1. Storage: build the index and save it to disk

```bash
python -m src.cli build                  # defaults: --data data --index index
```

```
Loaded 14 documents from data/
  [ 0] 羅生門 / 芥川竜之介: 3,359 terms
  ...
  [13] 夢十夜 / 夏目漱石: 9,701 terms
Indexed 14 docs: 6,519 distinct terms, 12,296 postings, 53,920 positions in 0.61s
Saved index to index/index.json
```

**Format: JSON instead of pickle.**

- JSON is human-readable and renders on GitHub, so the full index can be [browsed directly](index/index.json).
- It's portable across languages and Python versions.
- Loading it can't execute code. Unpickling a file can, so pickle is unsafe for files you didn't write yourself.

Pickle would be smaller and faster to load, but at about 0.1 s for this collection that doesn't matter.

**Japanese text encoding:**

- Every file is read and written with an explicit `encoding="utf-8"`. Python on Windows otherwise defaults to cp1252/cp932.
- JSON is written with `ensure_ascii=False`, so terms are stored as readable `"下人"` rather than `"下人"`.
- The source texts are Shift_JIS and are converted to UTF-8 once, at fetch time.
- The JSON has one term per line, so the file can be read in a browser and diffs cleanly. JSON object keys must be strings, so doc IDs are written as `"0"` and converted back to `int` when loading.

Two files are written:
- [`index/index.json`](index/index.json): metadata, document table and positional postings, about 420 KB.
- [`index/doc_store.json`](index/doc_store.json): original text plus per-position character spans, used for snippets only, about 900 KB.

### 2. Retrieval: load a previously built index

`storage.load_index()` reads the JSON back into an `InvertedIndex`. Nothing is re-tokenized. `stats` loads the index and can print a term's positional postings:

```bash
python -m src.cli stats --term 老婆 王
```

```
Loaded index from index/ in 0.101s (no re-tokenization)
  num_docs: 14
  num_terms: 6519
  ...
Postings for '老婆' (document frequency 1):
  doc 0 (羅生門): tf=28 positions=[1649, 1653, 1747, 1839, ...]

Postings for '王' (document frequency 2):
  doc 3 (杜子春): tf=1 positions=[3884]
  doc 6 (走れメロス): tf=23 positions=[10, 394, 437, 563, 626, ...]
```

From Python:

```python
from src.storage import load_index
from src.search import search, snippet

index = load_index("index")
for r in search(index, '"下人の行方"'):
    print(r.doc_id, r.title, r.matches, snippet(index, r.doc_id, r.matches[0]))
# 0 羅生門 [(3346, 3348)] …たる夜があるばかりである。 【下人の行方】は、誰も知らない。 （大正四年…
```

### 3. Searching: run queries against the loaded index

```bash
python -m src.cli search "QUERY"        # one query (add --snippets N to show more matches)
python -m src.cli search                # interactive prompt; empty line quits
python -m src.cli tokenize "日本語の文"  # show how text is segmented and normalized
```

**Query syntax.** Operators are upper-case and separated by spaces:

| Query | Meaning |
|---|---|
| `下人 AND 老婆` | both terms in the document |
| `下人 老婆` | implicit AND |
| `メロス OR セリヌンティウス` | either term |
| `狐 AND NOT 手袋` | first term, but not the second |
| `(狐 OR 猫) AND NOT 手袋` | parentheses for grouping |
| `"下人の行方"` (or `「下人の行方」`) | **phrase**: terms adjacent, in this order |
| `メロス /2 王` | **proximity**: within 2 positions, either order |
| `"下人の行方" /10 誰` | proximity also works between phrases (distance between start positions) |

Precedence: `NOT` > `AND` > `OR`. Every word in a query goes through the same tokenizer and normalizer as the documents. So `ＭＥＲＯＳ` and `meros` are the same term, and an **unquoted** word that fugashi splits into several tokens is searched as a phrase. For example, `羅生門` is tokenized as `羅生 門`.

Each result shows the document, the number of matches, and for each match its term positions and a snippet of the original text with the match in 【】. Results are ordered by number of matches. `NOT` excludes documents but has no positions to highlight.

**Boolean:**
```
$ python -m src.cli search "(狐 OR 猫) AND NOT 手袋"
Query: (狐 OR 猫) AND NOT 手袋  ->  2 document(s)
  doc  9  ごん狐 / 新美南吉  (6 match(es))
      positions 66-66: …、少しはなれた山の中に、「ごん【狐】」という狐がいました。ごんは、…
      ...
  doc  0  羅生門 / 芥川竜之介  (1 match(es))
      positions 1158-1158: …広い梯子の中段に、一人の男が、【猫】のように身をちぢめて、息を殺し…
```
手袋を買いに has 35 matches for 狐 but is excluded by `NOT 手袋`.

**Phrase:**
```
$ python -m src.cli search '"下人の行方"'
Query: "下人の行方"  ->  1 document(s)
  doc  0  羅生門 / 芥川竜之介  (1 match(es))
      positions 3346-3348: …たる夜があるばかりである。 【下人の行方】は、誰も知らない。 （大正四年…
```

**Proximity:**
```
$ python -m src.cli search "メロス /2 激怒"
Query: メロス /2 激怒  ->  1 document(s)
  doc  6  走れメロス / 太宰治  (2 match(es))
      positions 0-2: …【メロスは激怒】した。必ず、かの邪智暴虐の王を…
      positions 556-558: …人殺されました。」 聞いて、【メロスは激怒】した。「呆れた王だ。生かして置…
```

See [`sample_output.md`](sample_output.md) for the full output of these and other queries.

---

## Limitations

- **Surface forms only.** Inflected forms don't match their dictionary form: `走る` won't find `走っ`. Indexing `lemma` instead of `surface` in `normalizer.py` would change this.
- **Segmentation errors propagate.** If fugashi segments a word differently in two contexts, a phrase query won't match across the difference. Running queries through the same analyser keeps this consistent in most cases.
- **Positions cross sentence boundaries.** Punctuation is removed before positions are assigned, so a phrase or proximity match can span the end of one sentence and the start of the next.
- **No ranking.** This is boolean retrieval: results are ordered by match count, not by TF-IDF or BM25.
