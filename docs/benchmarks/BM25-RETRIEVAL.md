# Standalone BM25 versus current Qdrant: bounded diagnostic

## Outcome

**No demonstrated retrieval improvement from replacing incumbent FTS5 OR with standalone Okapi BM25 on this reused diagnostic set.** Okapi and FTS5 have identical selected-label P@1 and recall@5; Okapi has lower RR@5 and P@3. Dense+Okapi acquires one more selected positive into pool20 than dense+FTS5, but does not improve recall@5 and lowers P@1. Adding uniform source headings does not improve P@1. These observations do not establish an inherent engine advantage: tokenization, IDF and scoring semantics differ, and query language matters.

A separate lossless delivery-schema ablation reduces serialized evidence bytes **25.11%**, retaining all full passage text, source URLs, offsets, status, version metadata and both hashes. This is a measured serialization improvement, **not measured agent/MCP call latency or production integration**.

**PostgreSQL remains a separate, unprovisioned candidate. No PostgreSQL measurements exist here.** No production activation, dependency installation, downloads, vault access, shared-environment changes, staging or Git commits were performed.

## Inputs, pre-inference freeze and scope

Final run: [`artifacts/bm25-retrieval/618eea74b7e04e9e80b75bf3aa175320`](../../artifacts/bm25-retrieval/618eea74b7e04e9e80b75bf3aa175320).

- Same frozen **136 parent passages, 32 reused questions** from `artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92`; all source bytes/offsets and snapshot hashes checked.
- Original MiniLM document/query vectors from `artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3`. Every dense request freshly encodes its query and asserts **byte-identical historical query vectors**. Model and server hashes checked against the earlier freeze. No model changes.
- Seven variants, budgets, gates, metrics and serializer ablation saved in `freeze.json` **before inference**. No relevance labels enter index builders or representation builders. Labels are read only for scoring/review after ranking.
- **24 answerable questions, 27 selected positive labels; eight no-answer questions.** English public sources; mixed English/French questions, including eight `fr_to_en` questions. No translation or language-specific tuning. French-to-English P@1 is 0 for all lexical variants, 0.25 for dense and dense+FTS5, and 0 for dense+Okapi. This mismatch prohibits an engine-only conclusion.
- Both historical development and holdout sets are already observed: **reused diagnostics, not independent validation**. Author-made selected labels are incomplete. UNKNOWN/unjudged does not mean wrong. No winner selection, score confidence, calibrated abstention or **90% certification**.

## Fixed ranking contract

All branches use identical output/pool budgets and applicability policy:

1. Dense: existing real Qdrant ANN, ef128, 60 point candidates. Lexical: top20 candidates. Dense branches use identical query vectors; lexical branches do not require query embeddings.
2. Fusion: existing equal-weight RRF, constant60, rank starting1, document-ID tie break. Standalone branches preserve their own rank. Take **pool20**, then apply gate; no refill from the unacquired tail. Dense60 versus lexical20 is the incumbent acquisition contract, unchanged across comparable branches; it is not an assertion of equal retrieval work.
3. **Every branch**, including lexical-only and dense-only, rejects wrong CPython versions and UNKNOWN provenance on explicit `Python X.Y[.Z]` questions. Family request accepts matching patch releases; an exact patch request must match. Re-derive metadata and independently gate again at presentation. This is a narrow pinned-source provenance gate, not a full API-compatibility oracle. Non-version questions remain NOT_ASSESSED.
4. Present up to five original parent passages, with original source citations, hashes and character offsets. No reranker: deliberately omitted to bound runtime.

### Independent Okapi implementation

Pure Python standard library; independent of SQLite FTS5 and without new dependencies. Defaults **k1=1.2, b=0.75**. For each unique query term:

`IDF(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))`

`score(d,q) = Σ IDF(t) × tf(t,d) × (k1+1) / (tf(t,d) + k1 × (1-b+b×|d|/avgdl))`

Query term frequency is binary. Zero-match documents are not returned. Ties use document ID. Unicode lower-case tokenizer: `\w+(?:\.\w+)*`; underscores and internal dots stay intact, trailing punctuation dots do not. Thus `TaskGroup` → `taskgroup`, `task_group` stays `task_group`, and `Python3.11` stays `python3.11`. There is **no stemming, stopword removal, accent stripping, identifier decomposition or expansion**. Exact identifier tokens are not silently conflated, although case is intentionally folded. Incumbent FTS5 uses its default unicode61/BM25 with the existing technical-token OR phrase expression, so underscores/dots may split and accents fold. This is a controlled pipeline comparison, not a tokenizer-isolated engine microbenchmark.

### Separate source-title representation

`okapi_title` prepends one uniformly extracted heading from the full original normalized source, identically for positive and unjudged passages. UNKNOWN headings add nothing. It does not index curated passage names, label lists, source keys or query terms. Original excerpts/citations are unchanged. Dense vectors remain original body-only vectors. `title-provenance.json` records source-text hash and heading offset; `lexical-title-representation.json` retains actual indexed text. Total characters increase from **143,024 to 146,566**; this is representation size, not a database disk-space comparison.

## Actual results

Answerable-only macro means below; P@k denominator is k, with absent slots counting zero. MRR is RR truncated at5, a rank statistic, not answer confidence. Pool R is selected-label recall in pre-gate pool20. Pool hits count selected positive query/document pairs across all32 questions (27 available). Incompatibility/UNKNOWN counts concern all32 top-five lists in the first block. Timings are medians across both blocks/all32 questions.

| Variant (all gated) | P@1 | P@3 | P@5 | RR@5 | R@5 | Pool R | Pool hits | Incompatible | UNKNOWN | Ranking ms | E2E ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 0.5000 | 0.2500 | 0.1500 | 0.5694 | 0.6458 | 0.8958 | 24 | 0 | 142 | 1.368 | 4.352 |
| fts5_or | 0.4167 | 0.2361 | 0.1500 | 0.5292 | 0.6667 | 0.8542 | 23 | 1 | 141 | 0.747 | 0.844 |
| okapi | 0.4167 | 0.1944 | 0.1500 | 0.4979 | 0.6667 | 0.8542 | 23 | 1 | 141 | 0.763 | 0.856 |
| okapi_title | 0.4167 | 0.2083 | 0.1500 | 0.5014 | 0.6667 | 0.8542 | 23 | 1 | 141 | 0.771 | 0.878 |
| dense_fts5_rrf | 0.5417 | 0.2500 | 0.1583 | 0.5986 | 0.7083 | 0.8750 | 24 | 2 | 139 | 1.535 | 4.417 |
| dense_okapi_rrf | 0.4583 | 0.2361 | 0.1583 | 0.5465 | 0.7083 | 0.9167 | 25 | 1 | 140 | 1.523 | 4.459 |
| dense_okapi_title_rrf | 0.4167 | 0.2500 | 0.1583 | 0.5361 | 0.7083 | 0.9167 | 25 | 1 | 140 | 1.525 | 4.426 |

All branches return something on all **eight no-answer questions: 8/8 candidate false acceptances**, and return something on24/24 answerable questions. This is not generated-answer accuracy. No abstention threshold was tested. The gate eliminates known wrong Python-family presentation, not all explicit topic incompatibilities. Gate violations: **zero**. Eligible selected-pool hits equal pre-gate hits in this run.

Primary evidence: [per-query review](../../artifacts/bm25-retrieval/618eea74b7e04e9e80b75bf3aa175320/PER-QUERY-REVIEW.md), `raw-results.json`, and `per-query.csv` under the run directory. Every question/branch contains ordered top-five snippets and full original evidence, relevance labels/hits, P1/P3/P5, RR@5, recall@5, pool hits, incompatibilities, UNKNOWN, no-answer status, original references, branch-specific timings and raw dense responses/Okapi scores. Incumbent FTS5 exports its ordered IDs via its unchanged helper, not calibrated score probabilities. `report.json` includes development/holdout breakdowns, category P@1, p50/p95 timings, warm-up and index/model load separately. CSV repeats both blocks; review uses block0.

## Timings, delivery/tool-call ablation and limits

- **448 independently executed requests**: 32 questions × seven branches × two blocks; query and branch order reversed in block1. Every dense request does fresh resident encoding + actual HTTP retrieval. Lexical branches correctly avoid embedding work.
- Ranking timing includes backend retrieval, lexical work if needed, fusion and both gates. E2E is an actual elapsed boundary including encoding if needed and evaluation/citation serialization. It includes benchmark scoring metadata, not a production HTTP endpoint or model-generated answer; logging/hashing are excluded. No reused stage sums are called E2E. Cold model validation/load was606.686ms; combined lexical index build10.181ms.
- Resident CPython3.11.16, unchanged existing `.venv`, ONNX CPU. Real owned **Qdrant1.19.2** server, 136 HNSW-indexed vectors, M16/ef_construct100/ef128. No SQLite simulation of Qdrant. On this tiny corpus, transport/interpreter overhead matters; two blocks are bounded diagnostics, not throughput or production p95 qualification.
- `delivery-ablation.json` compares **224 unique full-evidence envelopes** with identical JSON separators. Baseline contains `query` plus actual full citation records; compact removes only duplicate preview text and `passage_id` when equal to `parent_id`. All full evidence, original citation identity/hash/offsets, version metadata and judgment status are retained; genuinely distinct passage IDs remain.
- Baseline **2,473,580 bytes**, compact **1,852,524 bytes**, **25.1076% less**. Baseline serialization median0.03405ms; compact packing+serialization median0.02710ms. This is microtiming outside ranking/E2E; it must not be added to/subtracted from request timings as a production latency claim. No truncation, deferral, extra get requests, retrieval changes or relevance claims.
- `internal_calls` records encode/query/lexical/envelope operations for every branch. Public search/get or MCP transport was **not** modified or benchmarked; no measured agent-call reduction is claimed. The compact full-evidence envelope is a tested representation available for later integration, not an operational rollout.

## Verification and reproducibility

First shell command: `rtk --version` → `rtk 0.48.0`.

From `D:/Projets/BorgKnowledge`:

```bash
# Unit contracts; no server unless opt-in explicitly set
.venv/Scripts/python.exe -m unittest discover -s tests -p bm25_retrieval_benchmark_test.py -v

# Actual complete paired diagnostic, through the integration test
RUN_BM25_INTEGRATION=1 .venv/Scripts/python.exe -m unittest discover -s tests -p bm25_retrieval_benchmark_test.py -v

# Equivalent standalone entry point (creates a fresh UUID run)
.venv/Scripts/python.exe tools/bm25_retrieval_benchmark.py

# Existing adjacent regression contracts; their separate expensive integrations stay opt-in
.venv/Scripts/python.exe -m unittest discover -s tests -p retrieval_ablation_test.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -p retrieval_budget_benchmark_test.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -p qdrant_quality_test.py -v
```

Strict vertical RED→GREEN execution observed for four slices: missing standalone module; missing source representation/gate; missing actual paired runner; missing compact-delivery representation. Each RED failed on the expected explicit missing-feature assertion before its implementation. Final new suite **4/4 passes**, including full real integration, in6.918s. Adjacent suites: ablation7 tests with2 deliberate opt-in skips, budget3 with1 skip, Qdrant2 with1 skip; all non-skipped tests pass. No full-project suite or unrelated runtime integrations were run.

Readback verification recomputed every saved row's metrics, pool selection, gate, rankings, lexical candidates and original citations; dense query vectors match historical bytes. Returned Qdrant payload identities and all136 stored vectors verified: maximum absolute float32 difference **1.4091273120575565e-08**. All ranks stable across two blocks. Every one of the **74 evidence-manifest entries** was rehashed from disk, and frozen execution-input hashes still match. Freeze precedes first inference with non-strict timestamp ordering checked.

Final owned server PID17668, loopback port51650: terminate/wait, independently verified PID absent and port closed; cleanup receipt read back. Windows termination reports returncode1 and is forced cleanup, **not graceful-shutdown/durability acceptance**. No other server or storage touched. Retained storage is uniquely owned diagnostic evidence.

Earlier successful first-slice run `artifacts/bm25-retrieval/1f6d60d6a0d0485e9e7d086079ef33ca` (448 rows,73 manifest entries) is retained unchanged, but superseded by the final run including delivery ablation. Its executable-input hashes describe the earlier source version, not the current script.

New source files only: `tools/bm25_retrieval_benchmark.py`, `tests/bm25_retrieval_benchmark_test.py`, this document; plus the two unique artifact directories. Existing code was not edited. Beads **bk-l8t** remains in progress pending parent verification; do not close it automatically.
