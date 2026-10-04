# Sample output

All output below was produced by running the commands shown against the 14 documents in `data/` (see [README](README.md) for the query syntax).

## 1. Building the index (Storage)

```
$ python -m src.cli build
Loaded 14 documents from data/
  [ 0] 羅生門 / 芥川竜之介: 3,359 terms
  [ 1] 蜘蛛の糸 / 芥川竜之介: 1,621 terms
  [ 2] 鼻 / 芥川竜之介: 3,534 terms
  [ 3] 杜子春 / 芥川竜之介: 5,467 terms
  [ 4] 藪の中 / 芥川竜之介: 4,805 terms
  [ 5] 蜜柑 / 芥川竜之介: 1,892 terms
  [ 6] 走れメロス / 太宰治: 5,305 terms
  [ 7] 注文の多い料理店 / 宮沢賢治: 2,803 terms
  [ 8] よだかの星 / 宮沢賢治: 2,788 terms
  [ 9] ごん狐 / 新美南吉: 2,623 terms
  [10] 手袋を買いに / 新美南吉: 2,038 terms
  [11] 高瀬舟 / 森鴎外: 5,049 terms
  [12] 檸檬 / 梶井基次郎: 2,935 terms
  [13] 夢十夜 / 夏目漱石: 9,701 terms
Indexed 14 docs: 6,519 distinct terms, 12,296 postings, 53,920 positions in 0.74s
Saved index to index/index.json
```

## 2. Tokenization of one sample sentence

The first sentence of 羅生門, with a full-width ＡＢＣ added to show width normalization. fugashi segments the unspaced text into words, splits 羅生門 into 羅生 + 門, and reports the dictionary form (lemma) of the conjugated verb 待っ → 待つ. The normalizer then folds ＡＢＣ → abc and removes 、 and 。 before positions are assigned. Only the normalized surface forms in step 2 go into the index.

```
$ python -m src.cli tokenize "ＡＢＣ、一人の下人が、羅生門の下で雨やみを待っていた。"
Input: ＡＢＣ、一人の下人が、羅生門の下で雨やみを待っていた。

1. Tokenizer (fugashi):
   ＡＢＣ | 、 | 一人 | の | 下人 | が | 、 | 羅生 | 門 | の | 下 | で | 雨やみ | を | 待っ | て | い | た | 。
   surface   lemma     POS       chars
   ＡＢＣ    ＡＢＣ    名詞      0-3
   、        、        補助記号  3-4
   一人      一人      名詞      4-6
   の        の        助詞      6-7
   下人      下人      名詞      7-9
   が        が        助詞      9-10
   、        、        補助記号  10-11
   羅生      羅生      名詞      11-13
   門        門        名詞      13-14
   の        の        助詞      14-15
   下        下        名詞      15-16
   で        で        助詞      16-17
   雨やみ    雨止み    名詞      17-20
   を        を        助詞      20-21
   待っ      待つ      動詞      21-23
   て        て        助詞      23-24
   い        居る      動詞      24-25
   た        た        助動詞    25-26
   。        。        補助記号  26-27

2. Normalizer (NFKC, lowercase, punctuation removed) -> index terms with positions:
   0:abc  1:一人  2:の  3:下人  4:が  5:羅生  6:門  7:の  8:下  9:で  10:雨やみ  11:を  12:待っ  13:て  14:い  15:た
```

## 3. Loading the saved index (Retrieval) and inspecting positional postings

```
$ python -m src.cli stats --term 老婆 王
Loaded index from index/ in 0.066s (no re-tokenization)
  tokenizer: fugashi (MeCab) + unidic-lite
  term_form: surface form
  normalization: NFKC + lowercase, punctuation/symbol tokens removed
  num_docs: 14
  num_terms: 6519
  num_postings: 12296
  num_positions: 53920

Postings for '老婆' (document frequency 1):
  doc 0 (羅生門): tf=28 positions=[1649, 1653, 1747, 1839, 1853, 1950, 1977, 2100, 2106, 2116, 2141, 2159, 2205, 2249, 2274, 2325, 2408, 2490, 2610, 2662, 2922, 3039, 3114, 3151, 3191, 3204, 3261, 3285]

Postings for '王' (document frequency 2):
  doc 3 (杜子春): tf=1 positions=[3884]
  doc 6 (走れメロス): tf=23 positions=[10, 394, 437, 563, 626, 659, 696, 737, 845, 897, 1128, 1813, 2248, 2335, 2966, 2981, 3200, 3628, 3657, 3673, 3687, 4581, 5226]
```

## 4. Example queries (Search)

### Boolean: AND

```
$ python -m src.cli search "下人 AND 老婆"
Query: 下人 AND 老婆  ->  1 document(s)
  doc  0  羅生門 / 芥川竜之介  (72 match(es))
      positions 10-10: …ある日の暮方の事である。一人の【下人】が、羅生門の下で雨やみを待って…
      positions 413-413: …くこびりついているのが見える。【下人】は七段ある石段の一番上の段に、…
      positions 461-461: …めていた。 作者はさっき、「【下人】が雨やみを待っていた」と書いた…
      ... 69 more
```

### Boolean: OR / NOT with grouping

```
$ python -m src.cli search "(狐 OR 猫) AND NOT 手袋"
Query: (狐 OR 猫) AND NOT 手袋  ->  2 document(s)
  doc  9  ごん狐 / 新美南吉  (6 match(es))
      positions 66-66: …、少しはなれた山の中に、「ごん【狐】」という狐がいました。ごんは、…
      positions 69-69: …れた山の中に、「ごん狐」という【狐】がいました。ごんは、一人ぼっち…
      positions 79-79: …ました。ごんは、一人ぼっちの小【狐】で、しだの一ぱいしげった森の中…
      ... 3 more
  doc  0  羅生門 / 芥川竜之介  (1 match(es))
      positions 1158-1158: …広い梯子の中段に、一人の男が、【猫】のように身をちぢめて、息を殺し…
```

### Phrase

Matches only where 下人, の, 行方 occur at consecutive positions p, p+1, p+2.

```
$ python -m src.cli search '"下人の行方"'
Query: "下人の行方"  ->  1 document(s)
  doc  0  羅生門 / 芥川竜之介  (1 match(es))
      positions 3346-3348: …たる夜があるばかりである。 【下人の行方】は、誰も知らない。 （大正四年…
```

An unquoted word that fugashi splits into several tokens is automatically treated as a phrase (羅生門 → 羅生 門):

```
$ python -m src.cli search "羅生門"
Query: 羅生門  ->  1 document(s)
  doc  0  羅生門 / 芥川竜之介  (7 match(es))
      positions 12-13: …暮方の事である。一人の下人が、【羅生門】の下で雨やみを待っていた。 …
      positions 54-55: …柱に、蟋蟀が一匹とまっている。【羅生門】が、朱雀大路にある以上は、この…
      positions 191-192: …る。洛中がその始末であるから、【羅生門】の修理などは、元より誰も捨てて…
      ... 4 more
```

Phrases match on word boundaries, not substrings: 下人 is a single term, so 人 never occurs on its own here:

```
$ python -m src.cli search '"人の行方"'
Query: "人の行方"  ->  0 document(s)
```

### Proximity

`term1 /k term2` matches when both terms are within k positions of each other, in either order.

```
$ python -m src.cli search "メロス /2 王"
Query: メロス /2 王  ->  1 document(s)
  doc  6  走れメロス / 太宰治  (1 match(es))
      positions 624-626: …、騒ぎが大きくなってしまった。【メロスは、王】の前に引き出された。 「この短…
```

```
$ python -m src.cli search "メロス /5 王"
Query: メロス /5 王  ->  1 document(s)
  doc  6  走れメロス / 太宰治  (1 match(es))
      positions 624-626: …、騒ぎが大きくなってしまった。【メロスは、王】の前に引き出された。 「この短…
```

In メロスは激怒した the particle は sits between the two words, so they are 2 positions apart. /1 does not match, /2 does:

```
$ python -m src.cli search "メロス /1 激怒"
Query: メロス /1 激怒  ->  0 document(s)
```

```
$ python -m src.cli search "メロス /2 激怒"
Query: メロス /2 激怒  ->  1 document(s)
  doc  6  走れメロス / 太宰治  (2 match(es))
      positions 0-2: …【メロスは激怒】した。必ず、かの邪智暴虐の王を…
      positions 556-558: …人殺されました。」 聞いて、【メロスは激怒】した。「呆れた王だ。生かして置…
```

