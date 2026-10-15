"""Download the sample collection from Aozora Bunko (青空文庫) into data/.

Usage:  python -m src.fetch_aozora

Each work is looked up by title + author in Aozora Bunko's official catalog
CSV, preferring the modern-orthography edition (新字新仮名). The text zip is
downloaded, decoded from Shift_JIS to Unicode, cleaned of Aozora markup and
saved as UTF-8 plain text, together with data/metadata.json.

Aozora markup removed:
- header (title/author) and the 【テキスト中に現れる記号について】 legend block
- footer starting at 底本： (bibliographic information)
- ruby readings  羅生門《らしょうもん》 -> 羅生門, and the ruby start marker ｜
- editorial notes ［＃...］ and the ※ that marks a non-JIS character
"""

import csv
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

CATALOG_URL = "https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"

# (file slug, title, author family name, author given name)
WORKS = [
    ("rashomon", "羅生門", "芥川", "竜之介"),
    ("kumo_no_ito", "蜘蛛の糸", "芥川", "竜之介"),
    ("hana", "鼻", "芥川", "竜之介"),
    ("toshishun", "杜子春", "芥川", "竜之介"),
    ("yabu_no_naka", "藪の中", "芥川", "竜之介"),
    ("mikan", "蜜柑", "芥川", "竜之介"),
    ("hashire_merosu", "走れメロス", "太宰", "治"),
    ("chumon_no_ooi_ryoriten", "注文の多い料理店", "宮沢", "賢治"),
    ("yodaka_no_hoshi", "よだかの星", "宮沢", "賢治"),
    ("gongitsune", "ごん狐", "新美", "南吉"),
    ("tebukuro_wo_kaini", "手袋を買いに", "新美", "南吉"),
    ("takasebune", "高瀬舟", "森", "鴎外"),
    ("remon", "檸檬", "梶井", "基次郎"),
    ("yume_juya", "夢十夜", "夏目", "漱石"),
]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ir-project-fetcher"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def load_catalog() -> list[dict]:
    CACHE_DIR.mkdir(exist_ok=True)
    cached = CACHE_DIR / "aozora_catalog.zip"
    if not cached.exists():
        cached.write_bytes(fetch(CATALOG_URL))
    with zipfile.ZipFile(cached) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        text = z.read(name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def find_work(catalog: list[dict], title: str, family: str, given: str) -> dict:
    rows = [
        r
        for r in catalog
        if r["作品名"] == title
        and r["姓"] == family
        and r["名"] == given
        and r["役割フラグ"] == "著者"
        and r["テキストファイルURL"].endswith(".zip")
    ]
    if not rows:
        raise LookupError(f"{title} by {family}{given} not found in the Aozora catalog")
    # Prefer modern kanji + modern kana editions.
    rows.sort(key=lambda r: r["文字遣い種別"] != "新字新仮名")
    return rows[0]


def decode(raw: bytes) -> str:
    # Aozora texts are Shift_JIS; cp932 is Microsoft's superset that covers most files.
    for encoding in ("cp932", "shift_jis_2004"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("cp932", errors="replace")


def clean_aozora_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    # Header: title/author lines, optionally followed by a legend block between dashed lines.
    dash_lines = [i for i, line in enumerate(lines[:60]) if re.fullmatch(r"-{20,}", line.strip())]
    if len(dash_lines) >= 2:
        lines = lines[dash_lines[1] + 1 :]
    else:
        # No legend: skip title/author lines up to the first blank line.
        lines = lines[lines.index("") + 1 :] if "" in lines else lines
    # Footer: bibliographic information starts at 底本：
    for i, line in enumerate(lines):
        if line.startswith("底本："):
            lines = lines[:i]
            break
    body = "\n".join(lines)
    body = re.sub(r"※?［＃[^］]*］", "", body)  # editorial notes / gaiji descriptions
    body = re.sub(r"《[^》]*》", "", body)  # ruby readings
    body = body.replace("｜", "")  # ruby start marker
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    catalog = load_catalog()
    metadata = []
    for number, (slug, title, family, given) in enumerate(WORKS, start=1):
        row = find_work(catalog, title, family, given)
        with zipfile.ZipFile(io.BytesIO(fetch(row["テキストファイルURL"]))) as z:
            txt_name = next(n for n in z.namelist() if n.lower().endswith(".txt"))
            text = clean_aozora_text(decode(z.read(txt_name)))
        file_name = f"{number:02d}_{slug}.txt"
        (DATA_DIR / file_name).write_text(text, encoding="utf-8")
        metadata.append(
            {
                "file": file_name,
                "title": title,
                "author": f"{family}{given}",
                "orthography": row["文字遣い種別"],
                "source_card": row["図書カードURL"],
                "source_text": row["テキストファイルURL"],
            }
        )
        print(f"{file_name:32} {title} / {family}{given}  ({len(text):,} chars)")
    (DATA_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nSaved {len(metadata)} documents to {DATA_DIR}")


if __name__ == "__main__":
    main()
