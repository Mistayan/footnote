# Matched LanceDB comparison

Pre-registered 2026-11-13, before running these configurations. This is a component experiment, not a production migration.

## Fixed inputs

- Export the current product's 2,000-character chunks and the stored bekko-a8m vectors from the completed public benchmark indexes, opened read-only.
- Decode the same int8 vectors to float32 for every backend. Preserve the small quantization norm error; use dot-product scores consistently.
- Use one model to isolate backend effects. The production pair is a later integration check, required before proposing a replacement.
- Encode the same official test queries once with the hash-matched lab encoder, clipped to 500 UTF-8 bytes. All configurations consume those identical query vectors.
- Same stored columns: chunk ID, document ID, text and float32 vector. Same candidate pool of 100, document deduplication and top-20 output.
- No approximate vector index, no model tuning, no test-set parameter selection. Tokenizers use English stemming, accent folding, no stopword removal and a 40-character token limit.

## Configurations

| Receipt engine | Store | Lexical | Dense retrieval | Fusion |
|---|---|---|---|---|
| `matched-sqlite-tantivy` | SQLite | separate Tantivy | resident exact NumPy scan | existing top-pool z-score rule, alpha 0.55 |
| `matched-lance-rrf` | LanceDB | native FTS | exact LanceDB scan | native hybrid RRF, K=60 |
| `matched-lance-cc` | LanceDB | native FTS | exact LanceDB scan | same z-score rule, alpha 0.55 |
| `matched-lance-tantivy` | LanceDB | separate Tantivy | resident exact NumPy scan loaded from LanceDB | same z-score rule, alpha 0.55 |

The last row tests LanceDB as the system of record underneath the existing derived-index pattern. It does not exercise LanceDB's vector engine.
All latency scopes exclude the common precomputed query encoding and include fetching candidate document IDs from the chosen store. Do not compare these timings directly with the end-to-end competitor receipts.
Both native candidate queries execute sequentially for the RRF and CC controls. RRF uses the SDK's `RRFReranker.rerank_hybrid`; the SDK hybrid builder's parallel query orchestration is not measured.

## Measurements and decision

Run the four configurations sequentially on Syntec, NFCorpus, SciFact, Alloprof and mix-fr-en, through `bench/run.py`. Keep its immutable receipts, rankings, quality metrics and determinism check. Record common input hashes, backend versions, source hashes, build time and total store/index sizes. Retain equal content when comparing bytes.

`run_matched.ps1` waits for the model-timing queue, freezes each input with `matched_inputs.py`, and then runs the four adapters through the pinned `bench/.dbenv` environment. It records failed commands in `bench/work/matched-failures.jsonl` and exits unsuccessfully if any run fails. Existing frozen inputs are verified again by every adapter; they are never silently overwritten.

Validate the native distance-to-score conversion, identical-vector nearest neighbors and SQLite/LanceDB round trips on a tiny fixture before running public corpora. A result requiring unknown IDs, changed query text or changed artifact hashes fails closed.

Use the thresholds in [PLAN.md](PLAN.md) for ranking changes; use paired comparisons and existing dev/heldout discipline before shipping anything. A backend change must also pass add/edit/delete freshness, optimization, crash-safety and transaction/provenance checks. Those operational tests and 100k/1M scale runs follow the judged-corpus comparison; a tiny fixture cannot establish production readiness.

The queue also extends the existing `dbbake/track_a_scale.py` run to LanceDB at 100k and 1M documents, alongside fresh SQLite FTS5 and Tantivy controls. All use the same seeded 150-word spans and 300 real queries. These are synthetic corpora: measure speed and returned-list overlap, not judged relevance. The lexical stores retain different content, as documented in the earlier bake-off; raw disk sizes here are not equivalent total-product footprints. Integrated vector scaling remains separate work.

## API evidence

- [LanceDB 0.41.0 vector search](https://github.com/lancedb/lancedb/blob/v0.41.0/docs/web/search/vector-search.mdx): dot distance is `1 - dot`, exact scans can bypass indexes.
- [LanceDB 0.41.0 hybrid search](https://github.com/lancedb/lancedb/blob/v0.41.0/docs/web/search/hybrid-search.mdx): vector plus FTS, native RRF reranker.
- Installed 0.41.0 `table.py` and `query.py` were checked directly. The adapter uses `create_index(..., config=FTS(...))`. The older `create_fts_index` is deprecated and `use_tantivy=True` now raises an error. The separate Tantivy variant therefore owns its own derived index.
