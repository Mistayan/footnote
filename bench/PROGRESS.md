# Bench progress (resume here)

Updated 2026-11-12. The protocol and rules are in `README.md`; this file is the working state.

## Done

- Harness validated (BM25 SciFact 0.663 vs published 0.665; lab encoders reproduce published MTEB scores for MiniLM, E5-small, Bekko).
- 10 product-engine receipts (lexical: `shipped-lexical`, `bm25-or-lexical` on syntec, scifact, nfcorpus, alloprof, longmemeval_s) and 2 hybrid receipts (syntec, `shipped-hybrid` 0.669 and `shipped-hybrid-e5` 0.780). They carry the old harness hash if `lab/` changed since: re-run `run_suite.py` before tagging `bench-v1`.
- Lab engine, sweeps `lexical` (done), `models` (running), splits (dev = official train/dev for SciFact/NFCorpus, hash 30 percent for the rest; report on `heldout`/`test`).

## Findings so far (evidence in `receipts/` and `sweeps/*.jsonl`)

1. The shipped lexical path ANDs every query word: SciFact nDCG@10 0.017 (295/300 queries empty) vs 0.663 with OR.
2. Hybrid in the product is therefore close to dense-only on natural-language questions.
3. Published dense scores (anchors.json): the shipped MiniLM-L12 is far below E5-small and Bekko on French (Alloprof 0.266 vs 0.274 vs 0.450) and below BM25 on SciFact (0.485 vs 0.665).
4. Stemming: +0.02..0.03 on English; on the mixed index one stemmer beats the union of both (0.469 vs 0.452).

## Running / next (in order)

```
# 1. dense model comparison on dev splits (background job; ~1 h)
bench/.labenv/Scripts/python.exe -I bench/sweep.py models --datasets scifact,nfcorpus,alloprof --split dev
# 2. pick the best EN and ML model, then fusion on top (pass the winner as --base-json)
bench/.labenv/Scripts/python.exe -I bench/sweep.py fusion --datasets scifact,nfcorpus --split dev --tag en --base-json '{"dense":{"model":"<en winner>"},"lexical":{"tokenizer":{"stem":"en"}},"chunker":{"kind":"whole"}}'
bench/.labenv/Scripts/python.exe -I bench/sweep.py fusion --datasets alloprof,mix-fr-en --split dev --tag ml --base-json '{"dense":{"model":"<ml winner>"},"lexical":{"tokenizer":{"stem":"fr"}}}'
# 3. chunking (alloprof, mix-fr-en, longmemeval via run_lme --split dev) then rerank (--max-queries 200)
# 4. freeze the two winning profiles, run them through run.py on heldout/test for receipts, write DECISION.md, run_suite.py, tag bench-v1
```

## Status 2026-11-12

Stages 1-6 done on dev, candidates validated on heldout with paired bootstrap (see `DECISION.md`). Provisional profiles: default `bekko-a8m` + BM25 (English stemmer, k1 1.5) + convex combination (z-score, alpha 0.55), whole documents; optional English variant `gte-small`; optional rerank mode `bge-reranker-v2-m3`.
Done since: test-split and LongMemEval heldout receipts, full `run_suite.py` (40 receipts), storage engine bake-off (`dbbake/`, see `DECISION.md`: Tantivy for lexical, exact in-memory vectors, SQLite stays the system of record).
Next: tag `bench-v1` (needs a commit, not authorized yet), copy tagged receipts to the vault, port the winners to the Rust core (Tantivy lexical layer, resident encoder, fusion), name and README.

## Open questions

- Dev results for chunking, rerank and language centering are in `DECISION.md` (stage 4-6). Remaining: confirm the winners on heldout, paired bootstrap, freeze two profiles (`en`, `mixed`).
- Cache-key bug fixed 2026-11-12 (chunked and whole texts shared an embedding cache key); `run_lme.py` no longer fails on lab engines.
- Port the winners into the Rust core: BM25 OR + stemming, resident encoder in the daemon, model choice, fusion weights.
- Database bake-off (sqlite-vec, Tantivy+USearch, LanceDB, Qdrant Edge) after the pipeline is fixed: the DB changes speed and operations, not exact-search precision.

## Rust port (started 2026-11-12)

1. DONE: lexical queries use OR (`app::match_expr`), tests updated (`tests/context.rs`). Product lexical: SciFact 0.017 -> 0.663, NFCorpus 0.189 -> 0.297, Syntec 0.000 -> 0.666, Alloprof -> 0.328, LongMemEval-S 0.015 -> 0.879. Receipts committed; Rust source is NOT committed (it shares files with the earlier hardening edits).
2. TODO: fusion = convex combination (z-score, alpha 0.55) instead of RRF, exact vectors in memory (`semantic.rs`).
3. TODO: Tantivy lexical layer (en_stem, derived index rebuilt from SQLite).
4. TODO: resident Rust encoder (`ort` + `tokenizers`, bekko-a8m, hash-locked) replacing `tools/embed.py` per-query helper (~1 s).
Gate for every step: product receipts through `bench/run.py` against the lab numbers in `DECISION.md`.
