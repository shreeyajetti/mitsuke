# Mitsuke (見つけ)

*A multilingual full-text search engine with positional indexing, built for languages where "split on spaces" isn't enough.*

> **Status: in transition.** Mitsuke started as a university Information Retrieval project over Japanese literature. It is being rebuilt so that the index and search are language-independent, with each language plugged in as its own analyzer. The code in `src/` is still the original Japanese engine until that refactor lands.

## Course project (Japanese)

The graded version is preserved exactly as submitted:

- **Folder:** [`course-project/`](course-project/README.md), a frozen, runnable copy with full documentation
- **Git tag:** [`v1.0-course-project`](https://github.com/shreeyajetti/mitsuke/tree/v1.0-course-project)

That version covers a positional inverted index over 14 Aozora Bunko short stories, fugashi (MeCab) tokenization, AND/OR/NOT, phrase and proximity queries.

## Roadmap

1. **Shared core.** Separate the language-independent index/search code from the language-specific tokenizer and normalizer.
2. **Telugu first.** Telugu attaches suffixes to words: ఇల్లు (house) → ఇంటికి (to the house) → ఇంట్లో (in the house). Search has to match those forms to each other. Documents and judged test queries come from the [MIRACL](https://huggingface.co/datasets/miracl/miracl) Telugu retrieval benchmark, so retrieval quality can be measured from day one.
3. **Ranking and evaluation.** BM25 ranking, plus recall/precision on the benchmark queries.
4. **Japanese back in, with English glosses.** Tokens and snippets shown with English meanings, so non-Japanese readers can follow what is retrieved.
5. **Later: cross-lingual search.** Type a query in English and retrieve Japanese or Telugu documents.
