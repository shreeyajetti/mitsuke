"""Download the MIRACL Telugu collection and build the working subset in data/.

Usage:  python -m src.fetch_miracl

MIRACL (https://huggingface.co/datasets/miracl) is a multilingual retrieval
benchmark built from Wikipedia (Apache-2.0). Its Telugu part has 518,079
passages from 66,353 articles, plus test questions ("topics") with passages
judged relevant or not relevant by native speakers ("qrels").

The full collection is too large for the in-memory JSON index, so we index a
subset:
- every article containing a passage judged for a dev question, so that the
  questions still have their answers in the collection, plus
- the same number of randomly chosen other articles as distractors
  (fixed random seed, so the subset is reproducible).

Outputs (UTF-8):
- data/passages.jsonl  one passage per line: {"docid", "title", "text"}
- data/topics.dev.tsv  dev questions:  query_id <TAB> question
- data/qrels.dev.tsv   judgments:      query_id Q0 docid relevance
"""

import gzip
import json
import random
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/miracl"
CORPUS_FILES = ["docs-0.jsonl.gz", "docs-1.jsonl.gz"]
CORPUS_URL = BASE + "/miracl-corpus/resolve/main/miracl-corpus-v1.0-te/{}"
TOPICS_URL = BASE + "/miracl/resolve/main/miracl-v1.0-te/topics/topics.miracl-v1.0-te-dev.tsv"
QRELS_URL = BASE + "/miracl/resolve/main/miracl-v1.0-te/qrels/qrels.miracl-v1.0-te-dev.tsv"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache" / "miracl-te"
SEED = 42


def download(url: str, path: Path) -> Path:
    """Download once; later runs reuse the cached file."""
    if not path.exists():
        print(f"Downloading {url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, open(tmp, "wb") as f:
            while chunk := response.read(1 << 20):
                f.write(chunk)
        tmp.replace(path)
    return path


def article_id(docid: str) -> str:
    """Passage IDs look like '242633#8': article 242633, passage 8."""
    return docid.split("#")[0]


def main() -> None:
    corpus = [download(CORPUS_URL.format(name), CACHE_DIR / name) for name in CORPUS_FILES]
    topics = download(TOPICS_URL, CACHE_DIR / "topics.dev.tsv")
    qrels = download(QRELS_URL, CACHE_DIR / "qrels.dev.tsv")

    judged_articles = {article_id(line.split("\t")[2]) for line in qrels.read_text(encoding="utf-8").splitlines()}

    all_articles = set()
    for path in corpus:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                all_articles.add(article_id(json.loads(line)["docid"]))

    others = sorted(all_articles - judged_articles)
    distractors = set(random.Random(SEED).sample(others, len(judged_articles)))
    keep = judged_articles | distractors

    DATA_DIR.mkdir(exist_ok=True)
    kept = 0
    with open(DATA_DIR / "passages.jsonl", "w", encoding="utf-8", newline="\n") as out:
        for path in corpus:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    passage = json.loads(line)
                    if article_id(passage["docid"]) in keep:
                        out.write(json.dumps(passage, ensure_ascii=False) + "\n")
                        kept += 1

    for src, name in [(topics, "topics.dev.tsv"), (qrels, "qrels.dev.tsv")]:
        (DATA_DIR / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")

    print(
        f"Collection: {len(all_articles):,} articles. Kept {len(judged_articles):,} judged + "
        f"{len(distractors):,} random articles = {kept:,} passages -> {DATA_DIR / 'passages.jsonl'}"
    )


if __name__ == "__main__":
    main()
