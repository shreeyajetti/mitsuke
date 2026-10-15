# Kanipettu (కనిపెట్టు)

*A Telugu full-text search engine with positional indexing.*

> **Status: early development.** The code in `src/` is the positional-index engine from my Information Retrieval course project (originally built for Japanese). It is being adapted to Telugu. The graded course version is preserved at the git tag [`v1.0-course-project`](https://github.com/shreeyajetti/kanipettu/tree/v1.0-course-project).

## Why Telugu is interesting for search

Telugu attaches suffixes directly to words, and the stem itself can change:

| Telugu | Meaning |
|---|---|
| ఇల్లు | house |
| ఇంటికి | to the house |
| ఇంట్లో | in the house |

A search for ఇల్లు should find all three. Exact word matching finds only the first, and simply stripping suffixes doesn't connect ఇల్లు with ఇంటి-. Handling this well, and measuring how well, is the core of the project.

## Roadmap

1. **Telugu analyzer.** Word splitting plus Telugu-specific Unicode normalization (vowel signs, zero-width joiners).
2. **Data.** Documents and judged test queries from the [MIRACL](https://huggingface.co/datasets/miracl/miracl) Telugu retrieval benchmark (Telugu Wikipedia, Apache-2.0).
3. **Evaluation.** Measure recall on the benchmark queries before changing anything.
4. **Suffix handling.** Stemming and/or character n-grams, measured against the baseline.
5. **Ranking.** BM25.
