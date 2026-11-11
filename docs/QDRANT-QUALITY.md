# Harmonized SQLite hybrid versus Qdrant retrieval benchmark

## Current paired result — both rejected against the 90% precision gate

**Primary comparison: CURRENT parent/truncated MiniLM SQLite exact hybrid versus Qdrant ANN ef128 hybrid.** The completed paired run is `artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/`. Child chunking and E5 are an exploratory appendix only, not replacements for the current baseline. No methods/publication research or new architecture was added.

**Ordered top5 matched on 32/32 queries. There is no observed relevance advantage for either backend under matched conditions. Neither clears 90% precision.** Both use the same 136 retained public parent excerpts, exact MiniLM passage/query vector inputs, queries and frozen labels, parent lexical candidates, parent resolution, RRF recipe and citation builder. Qdrant stores float32 cosine vectors; SQLite retains JSON float64 vectors and computes exact dot scores. Conversion and raw rankings are retained rather than assuming byte-identical scores.

### Per-query deliverables — start here

- [PRIMARY-PAIRED-REVIEW.md](../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/PRIMARY-PAIRED-REVIEW.md): **every primary query, both backends**, exact question text, selected relevant IDs, ordered returned top5, hits, P@1/P@3/P@5, ideal selected-label P@5, recall5, RR@5, incompatible/UNKNOWN IDs, actual returned snippets, official source URLs and original context offsets.
- [primary-pair-per-query.json](../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/primary-pair-per-query.json): 32 side-by-side pairs including metrics, precision, timings and full returned passage texts/source references for SQLite and Qdrant.
- [per-query.csv](../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/per-query.csv): **960 rows**, covering all three model/layout variants, both ranking recipes and five retrieval modes. Filter `variant=parent-minilm`, `ranking=hybrid`, `mode=sqlite_exact` or `ann128` for the current comparison.
- [PER-QUERY-REVIEW.md](../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/PER-QUERY-REVIEW.md): primary pair first, followed by exploratory exact SQLite/Qdrant configurations.
- [report.json](../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/report.json), `raw-results.json`, `raw-server-rankings.json`: 60 summaries and all **480 measured retrieval responses** (96 actual SQLite computations plus 384 actual Qdrant HTTP responses), score/rank evidence, common query-vector hashes and timing stages. SQLite computations are explicitly labeled as such, not presented as server responses.
- [Independent paired verification](../artifacts/qdrant-quality-review/613659fee2a84ff28f6d2bf5da91d00d/verification.json): all 243 manifest entries and 960 per-query precision rows checked, SQLite vector seed equality, common query-vector/lexical identity, source-snippet offsets, child reconstruction and primary ordered top5/full passage/metric equality on 32/32 queries.

### Primary quality results

Each split has 12 answerable questions and four no-answer questions. Precision below is **selected-label precision**, not exhaustive semantic relevance. Metrics for both backends are identical:

| Split | Top1 / P@1 | P@3 | P@5 | MRR@5 | Macro recall5 | Incompatible@1 / @5 | No-answer candidates |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 0.5833 | 0.2222 | 0.1333 | 0.5833 | 0.5833 | 0 / 1 | 4/4 |
| REUSED/observed holdout | 0.5000 | 0.2778 | 0.1667 | 0.6111 | 0.7083 | 0 / 1 | 4/4 |

Coverage is 32/32 candidate-bearing queries; abstention is 0/32. Candidate coverage is **not** useful answer coverage. No-answer review rows explicitly say this public corpus cannot answer the deployment/private/unsupported question; returned candidates and RRF are not confidence or generated answers. Most questions have one selected positive, hence ideal selected-label P@5=0.2. UNKNOWN/unjudged results are not proven wrong. Labels were not revised after seeing results.

The old holdout is **REUSED/observed, not independent validation**. No holdout-based backend/model winner selection. Neither incomplete agent labels nor ANN recall establish 90% semantic-precision certification. This is **not LAD/RAD certification**, OCR/table/extraction acceptance, or proof of heterogeneous information-loss-free document handling.

### Matched timing contract

Both engines reuse the identical measured resident-model query encode and parent FTS5 lexical work. Each backend interval starts immediately before its retrieval operation and ends after scored candidates return. SQLite includes disk table read, JSON decode, float64 matrix creation, exact dot product and sorting. Qdrant includes client JSON/HTTP roundtrip and server work. Both then execute the same timed deterministic parent resolution, fusion, citation/snippet construction and serialization. The reported combined stage sum is **attributed resident pipeline time**, not an independently rerun E2E latency. Query vector hashes match across all modes.

| Primary backend | Development backend p50 ms | Reused-holdout backend p50 ms | Development attributed pipeline p50 ms | Reused-holdout attributed pipeline p50 ms |
|---|---:|---:|---:|---:|
| SQLite JSON float64 exact | 8.423 | 8.420 | 11.630 | 11.385 |
| Qdrant ANN ef128 | 0.610 | 0.593 | 3.775 | 3.573 |

Common query encoding p50 is 2.986 ms development / 2.822 ms reused holdout. These are single sequential local measurements, fixed mode order, no randomized repeated blocks. **This is a Python resident harness, not execution/performance certification of the production Rust CLI, and not an engine-only speedup verdict:** JSON decode and HTTP are different representation/transport costs. Relevance is equal in this run; timing alone does not authorize a backend choice or relax the 90% requirement.

### Freeze, storage and exploratory appendix

The paired freeze precedes inference and binds all variants, model/source hashes, labels, retrieval and fusion recipes. Parent MiniLM has 135/136 passages at/over its 128-token input cap; shared lossless child slices produce 391 vectors with zero overflows for MiniLM and E5. Exploratory child/model quality remains descriptive; it does not replace the paired current baseline. Exact Qdrant and ef256/512 are controls/appendices. All requested ANN ef settings have strict point recall60=1.0 against Qdrant exact here; this small corpus cannot establish large-scale ANN quality.

Actual Qdrant **1.19.2**, owned PID **34440**, unused loopback port **54885**, storage/snapshots/temp all below the unique paired run. Every collection readback was green and fully indexed (136/136, 391/391, 391/391), HNSW M16 / construction100, scan threshold10 KB / indexing1 KB. Owned SQLite databases store the identical passage vectors/texts/parent IDs/source offsets and remain available for read-only checks. Existing services, borg_vault/vault storage and production ingestion/runtime were untouched.

After expensive embedding, this harness explicitly drops the stale readiness keepalive before collection setup and again before telemetry. This addresses the parent-observed WinError10053 / RemoteDisconnected baseline issue without changing the existing server helper or silently retrying measured calls. Owned terminate/wait cleanup readback confirms process exit and port closure; Windows forced termination is not durability acceptance.

### Reproduction and real verification

```bash
# From D:/Projets/BorgKnowledge; uses already provisioned dependencies/models/server.
QDRANT_QUALITY_INTEGRATION=1 rtk proxy .venv/Scripts/python.exe -B -m unittest discover -s tests -p qdrant_quality_test.py -v
# Alternative direct full paired run:
rtk proxy .venv/Scripts/python.exe -B tools/qdrant_quality.py
```

The harmonized requirement was first added to the integration test: RED completed an owned Qdrant-only run and failed with **missing harmonized SQLite/Qdrant experiment**. After adding the SQLite actual backend, GREEN ran the full paired experiment: **two tests passed in 22.333 s**, 60 summaries, 960 per-query rows, indexed readback, hash verification and cleanup assertions. Earlier RED/GREEN tracer bullets for ranking and the initial Qdrant experiment are retained in the historical appendix. No commits, staging, push, installation or global configuration changes.

Final regression command `rtk proxy .venv/Scripts/python.exe -B -W error::ResourceWarning -m unittest discover -s tests -p '*test.py' -v`: **17 tests run, 16 passed, one explicit opt-in integration skip, 14.521 s**. The paired integration had already run separately, not been substituted by this skip. Existing OCR regression coverage ran as part of the existing suite; no new OCR implementation or heterogeneous extraction acceptance was claimed. `git diff --check` passed with only the pre-existing `.gitignore` line-ending warning.

| Paired run file | SHA-256 |
|---|---|
| freeze.json | `53eae8659aafcbd462a0741c0234460e3264024f1f8124f89b431450ba0b0fda` |
| report.json | `b67288b4f8e832c5f1923beccc3974f6f114980ebc8a7344b2bb9ccfec906413` |
| evidence-sha256.json | `49f0a0a58b737bba48ee7641e4dbd406641a442b3d00685601e1412529d6bf5a` |
| per-query.csv | `1dc49d7c0c8a8ab656141ae658cd41e71ea573132c60e7338154984b46afb1ce` |
| PRIMARY-PAIRED-REVIEW.md | `94a23ad21b0acff5090f2fdb9e51695b6c8459536c24501a9e59f25571603cc2` |

The paired evidence manifest binds **243 files**, including all raw rankings, NPY vectors, SQLite databases, Qdrant vector readback/graph files, source receipts and cleanup. Original frozen source bytes/context remain intact. No new OCR/extraction build or future-method research was added; independently judged heterogeneous sources and extraction/table/OCR fidelity remain a separate future gate, after the current comparison and any explicit choice.

<details>
<summary>Historical Qdrant-only pilot — superseded by the paired run above; retained for audit, not the primary comparison</summary>

## Acceptance verdict: REJECTED — below the required 90% precision

The user requires at least **90% precision**, with relevance the first criterion. **None of these variants is accepted.** Observed exact-hybrid top1/P@1 ranges from 33.33% to 58.33%, and selected-label P@3/P@5 are also below 90%. Coverage is 100% (all questions receive candidates), abstention is 0%, and no-answer candidate false acceptance is 4/4 in each split. High coverage is not useful answer coverage.

The incomplete labels also make exhaustive 90% semantic-precision certification impossible: most queries have only one selected positive, so their selected-label ideal P@5 is 20%. This is a labeling ceiling, not evidence that the remaining 80% is irrelevant. Reported precision is against these frozen selected labels; unknown results require independent adjudication, not automatic rejection as wrong.

This is **not LAD/RAD certification**, not extraction/OCR/table-fidelity acceptance, and not proof of information-loss-free heterogeneous document handling. The retained original public source bytes and exact context offsets remain available; child slice reconstruction is checked separately. A future gate needs an independently judged heterogeneous corpus, preserving originals and provenance, with extraction/table/OCR fidelity measured separately from retrieval P@1/P@3/P@5, answerable coverage, abstention and no-answer behavior. No OCR/build scope was silently added.

## Read the per-query evidence first

Run: `artifacts/qdrant-quality/b88426eca60b4cc98660661efdda0278/`.

- [PER-QUERY-REVIEW.md](../artifacts/qdrant-quality/b88426eca60b4cc98660661efdda0278/PER-QUERY-REVIEW.md): every query for all six exact model/layout/ranking combinations, ordered results, selected-label precision, recall, reciprocal rank, incompatible IDs, UNKNOWN/unjudged IDs, actual passage snippets, source URLs and source character offsets.
- [per-query.csv](../artifacts/qdrant-quality/b88426eca60b4cc98660661efdda0278/per-query.csv): **768 query/configuration rows**, including every ANN setting. Exact query text, positive IDs, ordered top5, hits, P@1/P@3/P@5, ideal P@5, recall5, RR@5, answerability, incompatible IDs, unknown IDs, source references and full returned passage texts.
- [raw-results.json](../artifacts/qdrant-quality/b88426eca60b4cc98660661efdda0278/raw-results.json): equivalent structured review with per-query timing stages.
- [raw-server-rankings.json](../artifacts/qdrant-quality/b88426eca60b4cc98660661efdda0278/raw-server-rankings.json): **384 actual server query responses**, point IDs, raw scores, parent semantic and lexical rankings, RRF scores and query-vector hashes.
- [report.json](../artifacts/qdrant-quality/b88426eca60b4cc98660661efdda0278/report.json): 48 split/configuration summaries, index readback, timings, ANN comparisons and cleanup.
- [verification-and-90pct-gate.json](../artifacts/qdrant-quality-review/b88426eca60b4cc98660661efdda0278/verification-and-90pct-gate.json): independent readback of all 238 original manifest entries, all 768 per-query precision calculations, original-source snippet offsets, lossless child reconstruction and the later user-required 90% rejection gate. Kept outside the frozen run so the historical manifest remains unchanged.

These are **selected, incomplete agent-authored evidence labels**, not exhaustive relevance judgments. A result without a positive label is UNKNOWN/unjudged unless explicitly labeled incompatible. Low selected-label P@5 does **not** establish that other passages are wrong: most queries have one positive, giving ideal selected-label P@5 = 0.2. Labels were preserved byte-for-byte, not revised after reading results.

No-answer rows explicitly state that this public corpus cannot answer the deployment/private/unsupported question. Returning candidates is not an answer, and no similarity or RRF score is confidence. This harness has no abstention gate: all four no-answer queries in each split return candidates under every configuration.

## Frozen scope and recipe

Retained public snapshot: `artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92` — 136 parent excerpts, 10 official source pages, 32 queries: development and old holdout each contain 12 answerable and four no-answer queries. Python/SQLite/asyncio and Qdrant documentation are mixed in this corpus.

**The old holdout is REUSED/observed, not independent validation. No holdout-based winner selection.** All layouts, models, ANN settings, ranking recipes and unchanged labels were frozen before the first inference. No question-specific chunking or fine-tuning occurred. The retained source-freeze file hashes and exact excerpt offsets were checked before execution; explicit execution inputs were rehashed afterward and remained stable.

Three prespecified variants:

| Variant | Vectors | Text handling | Passages at/over token cap before encoding |
|---|---:|---|---:|
| parent-minilm | 136 | Old full parent input; inherited truncating 128-token MiniLM recipe | 135 |
| child-minilm | 391 | Existing `technical_quality.child_chunks`, lossless nonoverlapping source slices | 0 |
| child-e5-small | 391 | The identical shared child slices, fitting both tokenizers | 0 |

Chunking checks actual prefix-inclusive token counts and leaves one token below each cap. It has no access to questions or judgments. Child boundaries therefore follow the stricter MiniLM cap even for E5 (512-token cap); this is not an optimized E5-length comparison. Children are exact source slices, not generated text. Resident verified local ONNX dynamic-int8 models use attention-mask mean pooling and L2 normalization, dimension 384, CPUExecutionProvider, two intra-op threads and one inter-op thread. MiniLM has empty prefixes; E5 uses `query: ` and `passage: `. `freeze.json` retains complete model manifests, immutable repository revisions and file SHA-256 values.

Each collection is queried in exact mode and ANN-requested modes ef=128, 256 and 512. All four settings are fixed in advance. Model query vectors are encoded once and reused across modes/layouts. No silent request retries occur in the measured query region.

Ranking recipes, evaluated separately:

1. Retrieve cosine top60 point candidates from Qdrant. Sort by descending score, then lexical document ID. Map children to parents and retain the first occurrence per parent (max-child ranking). No parent gets duplicate credit. A child top60 can contain fewer than 60 distinct parents; there is no refill.
2. `semantic`: first five distinct parents.
3. `hybrid`: parent-corpus SQLite FTS5, literal whitespace terms joined with AND, BM25 ascending and ID ties, top20; equal semantic/lexical reciprocal-rank fusion, k=60 and one-based ranks; final ties by parent ID; top5. Deduplication occurs **before** fusion. This inherits the existing public-quality recipe, not `server_benchmark.Pipeline`'s different lexical OR recipe.

No relevance or answerability threshold is fitted. Queries and labels are not changed. The semantic-only branch makes the limited effect of inherited lexical matching visible.

## Actual results

Metrics below use **12 answerable queries per split**; MRR is RR truncated at rank5, and recall5 is macro over each query's selected relevant IDs. Incompatible columns count explicit-label hits, not generated recommendations. Precision denominators are k even if fewer than k results exist; ideal P@5 depends on the positive-label count. No-answer false-acceptance counts are reported separately over four no-answer questions.

### Exact hybrid parent-level retrieval

| Variant | Split | Top1/P@1 | MRR@5 | Recall5 | P@3 | P@5 | Incompatible@1 / @5 | No-answer candidates |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Parent MiniLM | Development | 0.5833 | 0.5833 | 0.5833 | 0.2222 | 0.1333 | 0 / 1 | 4/4 |
| Child MiniLM | Development | 0.4167 | 0.5000 | 0.5833 | 0.2222 | 0.1333 | 0 / 1 | 4/4 |
| Child E5-small | Development | 0.5000 | 0.5694 | 0.6667 | 0.2500 | 0.1500 | 0 / 1 | 4/4 |
| Parent MiniLM | REUSED holdout | 0.5000 | 0.6111 | 0.7083 | 0.2778 | 0.1667 | 0 / 1 | 4/4 |
| Child MiniLM | REUSED holdout | 0.3333 | 0.5069 | 0.7083 | 0.2500 | 0.1667 | 1 / 3 | 4/4 |
| Child E5-small | REUSED holdout | 0.5833 | 0.6875 | 0.8333 | 0.2778 | 0.2000 | 1 / 3 | 4/4 |

Removing truncation is not automatically a ranking improvement: child MiniLM loses top1 here without improving macro recall. E5's observed reused-holdout scores differ, but it is not selected as a winner; incompatibility counts remain material, and there is no independent validation.

### Exact semantic-only retrieval

| Variant | Development top1 / MRR@5 / recall5 | REUSED holdout top1 / MRR@5 / recall5 |
|---|---|---|
| Parent MiniLM | 0.5000 / 0.5278 / 0.5833 | 0.4167 / 0.5694 / 0.7083 |
| Child MiniLM | 0.4167 / 0.5000 / 0.5833 | 0.3333 / 0.5069 / 0.7083 |
| Child E5-small | 0.5000 / 0.5694 / 0.6667 | 0.5833 / 0.6875 / 0.8333 |

Semantic-only incompatible@1/@5: development 0/1 for all three; reused holdout parent 1/1, child MiniLM 1/3, child E5 1/3. All no-answer queries still return candidates.

### Qdrant-topic diagnostic

Among answerable questions containing the literal `Qdrant` (five development, three reused holdout), all three exact-hybrid variants have top1/MRR@5/recall5 = **0.2/0.2/0.2** on development and **0.3333/0.3333/0.3333** on reused holdout. This is a post-run descriptive subset, not an additional tuning/selection set.

For example, **“Qdrant should filter at least one condition”** has selected positive `qfilter-should`, ideal P@5=0.2. Every variant misses that selected ID in its top5. Parent MiniLM returns, in order, `qfilter-context-04`, `qfilter-context-08`, `qsearch-threshold`, `qfilter-context-00`, `qhybrid-context-01`. All five are UNKNOWN/unjudged for that query, not proven irrelevant. The linked per-query review exposes the actual retrieved source text so a reader can judge whether contextual passages also help.

### ANN and timings

Strict point-ID ANN recall60 against Qdrant exact was **1.0** for each ef setting across all 96 variant/query pairs. Ordered semantic parent top5 matched exact in **288/288 ANN requests**. All collection readbacks were green and fully indexed: 136/136, 391/391, 391/391. HNSW M=16, ef_construct=100, full_scan_threshold=10 KB, indexing_threshold=1 KB, one requested default segment, cosine float32 storage. Raw telemetry and on-disk graph files are retained. ANN-requested equivalence on this small corpus is not proof of large-scale ANN behavior or a useful ef tradeoff; Qdrant's planner can use scans for some work.

| Variant | Passage embedding ms | Seed + index ms | Exact server roundtrip p50, dev / reused holdout ms |
|---|---:|---:|---:|
| Parent MiniLM | 1372.88 | 252.35 | 0.575 / 0.553 |
| Child MiniLM | 4003.55 | 319.97 | 0.604 / 0.612 |
| Child E5-small | 4173.37 | 327.67 | 0.598 / 0.562 |

Model load/hash validation: 1523.61 ms. Query encoding p50 dev/reused holdout: MiniLM 3.331/3.083 ms, E5 3.637/3.496 ms. Timings are single local sequential measurements without repeated randomized blocks; query encoding is reused, not included in server roundtrip. They are not production E2E latency or an engine speed comparison. Raw per-query server-reported time and measured encode/lexical/fusion/HTTP stages remain available. Maximum vector readback absolute errors were 1.4092e-8, 1.4251e-8 and 1.3578e-8 respectively, consistent with server float32 conversion.

## Isolation and concrete lifecycle issue

Actual existing binary: `artifacts/server-provision/qdrant-1.19.2/qdrant.exe`; server identity reported **1.19.2**. Its existing provisioning receipt references the official Windows release archive. This run hashes the executable itself and does not redownload or modify it.

Owned process **PID 16096**, loopback HTTP port **65219** (ephemeral unused port reserved at setup); clustering, gRPC and telemetry disabled. All new storage/snapshot/temp paths live under the unique run directory. Only this owned Popen is terminated. No existing service, `borg_vault`, vault storage, ingestion pipeline or production runtime was accessed/changed.

The parent agent reported two baseline reruns failed at collection PUT after embedding with WinError10053 / RemoteDisconnected: the existing helper reused the readiness HTTP connection through expensive setup. This harness explicitly discards that idle connection **after passage embedding and before collection setup**, and opens a fresh connection before final telemetry. It does not modify `server_benchmark.py`, hide retries, or invalidate the retained earlier baseline.

Cleanup readback records `process_exited=true`, `port_closed=true`; an independent post-run PID lookup returned absent and a second socket probe confirmed closure. Windows terminate/wait is forced shutdown (recorded return code 1), **not** graceful durability/crash-recovery acceptance. Storage is retained as evidence. Server startup warnings concerned optional default config files, unsupported Windows filesystem-type checks and missing optional static Web UI. Telemetry includes optimizer fail_count values despite final optimizer status ok/green and full index coverage; this is retained, not silently described as warning-free server operation.

## Reproduce and verification

From `D:/Projets/BorgKnowledge`, with existing `.venv` dependencies/models/server already provisioned:

```bash
rtk --version
QDRANT_QUALITY_INTEGRATION=1 rtk proxy .venv/Scripts/python.exe -B -m unittest discover -s tests -p qdrant_quality_test.py -v
rtk proxy .venv/Scripts/python.exe -B tools/qdrant_quality.py
rtk proxy .venv/Scripts/python.exe -B -m unittest discover -s tests -p '*test.py' -v
rtk proxy git diff --check
```

The first integration command performs a full new run; direct CLI execution is an alternative, not required to replay the same evidence. Each creates a fresh UUID artifact directory and owned server. No global setup, downloads, staging or publication occurs.

Observed strict TDD sequence:

1. First ranking test RED: `AssertionError: ... missing isolated quality harness` (one failure).
2. Minimal ranking implementation GREEN: one passing test.
3. Real-server/per-query integration contract RED: `AssertionError: ... missing real experiment` (one failure; ranking test passed).
4. Complete prespecified experiment implemented; integration GREEN: **2 tests passed in 21.110 s**, running all three variants and all ANN settings, asserting 48 summaries, 768 CSV rows, zero child token overflows, exact source hashes, indexed counts and owned cleanup.
5. Broader Python suite: **17 tests run, 16 passed, one explicit integration opt-in skip, 13.444 s**. Existing server integration also ran successfully on its own fresh artifact path. `git diff --check` passed with the pre-existing `.gitignore` LF/CRLF warning.

Beads task: `bk-vp5`. GSD read-only checks found the full expected 35-agent set and 72 shared skills; `validate agents` reported no missing/incomplete agents but nine pre-existing sandbox posture violations (workspace-write where read-only expected). Project GSD state/config/roadmap are absent; no init/install/global repair was attempted. Beads supplies the finite acceptance ledger; only scoped new files were authored. Codebase-memory hook presence was verified in Codex hooks; no incumbent symbols were edited, so no existing-symbol graph mutation/impact operation was needed.

### Evidence hashes

| File in run directory | SHA-256 |
|---|---|
| freeze.json | `8d1d112498d8b20711a09feedb01f368354ccd1140f1abffc34be33e4d641a4b` |
| report.json | `9850a92bdbcac06b21b1d3bf237c616c7c10c53d62759e34c45205e58b98d95f` |
| evidence-sha256.json | `6585dff1b8375e00e9cf553bbb8e1cede4d22bf198ecaf95bc544a04765e7d5b` |
| per-query.csv | `9779eb76768547458023d050d93ac72d3f433e703ff63b3b8110d8953ac667e0` |
| PER-QUERY-REVIEW.md | `96b5bdab958bdf0711e3012f1ade139c44af51aa4eb12302605dc19576665d03` |

The evidence manifest binds 238 run files, including passage/query NPY vectors, server vector readback, source receipts, frozen inputs, raw rankings, graph/storage files, telemetry and cleanup. Every manifest entry was independently rehashed by the integration test. Original corpus SHA-256: `9f2cc5c17227fde3f273db47b29b0d6ee64e02460e94796cfe1f635b4e13f3f8`; unchanged judgments SHA-256: `b004b2716808e9211f643522318e5294254a197dc54029dc3c6c706f6f9d71c6`.

## Limits and next validation

Editorial review round 1 found that descriptive metrics alone did not state the user's 90% gate: corrected with the explicit REJECTED verdict above. Round 2 checked label ceilings, full per-query access, actual snippets, source offsets, no-answer coverage and lifecycle limitations: retained UNKNOWN rather than treating unjudged results as wrong, and separated future LAD/RAD/extraction acceptance from this retrieval run. These are document/content reviews, not rendered UI or independent relevance adjudication.

- No independent expert adjudication, exhaustive labels, generated-answer evaluation, confidence calibration, whole-document ingestion or user-vault certification.
- Related topics occur across development and reused holdout. Neither model differences nor the Qdrant-topic diagnostic support a deployment winner.
- Parent labels do not establish that every matching child itself contains complete answer evidence; inspect the actual child snippets/offsets in the review.
- Max-child retrieval creates multiple opportunities for longer parents; the experiment does not correct this bias. A raw 60-child budget is not a 60-parent budget.
- Source snapshots are time-bound; Python tags, Qdrant documentation commit, model revisions and raw bytes are pinned in retained receipts.
- Best next validation: independently adjudicate a fresh, question-disjoint Qdrant query set with deeper passage labels **before inference**. Do not tune these reused questions or silently relabel unknown results.

</details>
