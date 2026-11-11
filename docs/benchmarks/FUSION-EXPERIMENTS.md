# Fixed fusion experiments — executed reused diagnostic

**Outcome: fusion explains the WAL rank loss, but no fixed branch dominates. No production change.** Dense weighting recovers specific French proofs, lexical weighting helps some English exact/operator questions and loses French evidence. Dense-only E5_128 increases selected P1 while losing English evidence and some overall recall. These results do not select a replacement encoder or ranking policy.

Status: **OPEN — `bk-d7i`, parent verification required.** Personal agent KB replacement in 1–2 months remains the goal; this is not enterprise qualification or a usable-store integration claim.

## Evidence / reproduction

Primary run: [`paired-4a8223f31da74bdcb0054f1d9228190a`](../../artifacts/fusion-experiments/paired-4a8223f31da74bdcb0054f1d9228190a/).

- [`PER-QUERY-REVIEW.md`](../../artifacts/fusion-experiments/paired-4a8223f31da74bdcb0054f1d9228190a/PER-QUERY-REVIEW.md): every question × model × branch, ordered five excerpts, URLs, original offsets/hashes, selected/incompatible/UNKNOWN status, P1/P3/P5, MRR5, R5, pool recall and no-answer status.
- `raw-results.json` and `.jsonl`: **768 actual HTTP retrieval requests**, each with its own resident query encoding, raw Qdrant scores/candidates, lexical ranks, every weighted RRF contribution, pool20, gates, full original returned texts and individual stage timings.
- `paired-changes.json`: all per-query changes relative to the same model's equal-RRF baseline; no favorable-only filter.
- `wal-network-causality.json`: exact competing candidate ranks and score contributions for all twelve cells.
- `freeze.json`, `model-recipes.json`, three passage/query vector pairs, visibility, server vector/payload readback, source texts, archived code, cleanup and evidence hashes.
- Freeze SHA256: `bd02d35f350ae978f2aeb5716bf2f362bf101d80c180c7b1975919ca4c074d8a`.
- Evidence manifest SHA256: `b51ba10a8890c5f4f5630936673df25fad6399ed6ff60fcf4525baa27f144696`.

```bash
rtk proxy env -u PYTHONPATH .venv/Scripts/python.exe tests/fusion_experiment_test.py -v
rtk proxy env -u PYTHONPATH .venv/Scripts/python.exe tools/fusion_experiment.py --verify artifacts/fusion-experiments/paired-4a8223f31da74bdcb0054f1d9228190a
# New unique directory, identical prespecified matrix:
rtk proxy env -u PYTHONPATH .venv/Scripts/python.exe tools/fusion_experiment.py
```

**Environment caveat:** a later standalone verification inherited Hermes's Python3.14 site-packages through `PYTHONPATH`, shadowing this project's Python3.11 NumPy and failing its C-extension import. `env -u PYTHONPATH` for that command alone restored the existing project packages and verification returned `True`; no environment/configuration or package installation was changed. The reproduction commands explicitly prevent that inherited-path collision.

**Two owned tests pass in 29.451s**, including a complete real server experiment, fixed-weight formula/absent-branch/tie contracts, byte corruption rejection and semantic UNKNOWN-status corruption rejection even after rehashing the modified raw JSON. RED failures were observed before each implementation slice. No application-wide regression suite was run.

Two previous executions are retained: `paired-b2042ba82126477a9a0ce3b39a78eeb9` (first green) and `paired-dd927943c9004a768459f923316012eb` (complete retrieval run followed by intentionally RED semantic-verifier test). The primary repeat adds semantic review validation; matrix, ranking, models and judgments never changed after observing results. Current-file verification intentionally rejects earlier code/test hashes; their archived input hashes and outputs remain intact.

## Prespecified protocol

All four branches and three encoders are frozen to disk **before session initialization/inference**:

| Branch | Dense weight | Lexical weight | Formula |
|---|---:|---:|---|
| `equal` | 1 | 1 | incumbent equal RRF, k60 |
| `dense2` | 2 | 1 | fixed dense-weighted RRF, k60 |
| `lexical2` | 1 | 2 | fixed lexical-weighted RRF, k60 |
| `dense_only` | 1 | 0 | dense rank only; lexical candidates do not enter ranking |

Score = sum of `weight / (60 + one-based branch rank)`; absent branch adds zero; deterministic document-ID tie break. **Scores are ranks, not confidence or probabilities.** No fitted thresholds, query/language-dependent selection, expansion, translation, reranker or optional lexical-coverage heuristic. Dense-only still executes/logs FTS for matched diagnostic work; its latency is not an optimized dense-only deployment estimate.

Reused unchanged **136 original parent passages, 32 questions (24 selected-answerable, eight no-answer)** from [the multilingual experiment](MULTILINGUAL-EMBEDDINGS.md), whose entire retained evidence manifest is hash-checked before running. Same original bodies, labels, source hashes/offsets and segmentation in every branch. No metadata enrichment or selected-anchor leakage. This is an already observed diagnostic set, **not new independent holdout evidence**.

Models: `minilm_parent128`, `e5_parent128`, `e5_parent512`. Both existing encoders are multilingual. MiniLM cap128 has empty prefixes; E5 caps128/512 use `query: ` and `passage: `, masked mean pooling and L2 normalization, dimension384. Existing pinned quantized ONNX/tokenizer bytes and exact model recipes are copied/hash-bound, not downloaded. E5_512 changes native visible context as well as model relative to MiniLM; cap128 is length-matched, not token-for-token visibility-matched. Passage and query vectors are **bit-identical to the corresponding historical arrays**.

FTS5 OR lexical20; dense60 ANN ef128; fixed fused pool20; existing raw-source Python-family/version gate after pool creation, then independently at presentation; no refill; top5. Unknown applicability is rejected for explicit requested Python versions, otherwise NOT_ASSESSED; this gate is not universal version understanding.

Actual isolated Qdrant **1.19.2**, commit `016542aa5deb6c66380bb137badf73d54f742bde`; loopback-only unique process/storage/port; cosine384, HNSW M16/ef_construct100/ef128. All three collections green, all136 vectors indexed and vectors/payloads read back before requests. Two blocks reverse question/model/branch order in block2. Every branch independently encodes and retrieves each request. The finite deadline is600s; actual measurement window4.047s. This run does not repeat exact-server control; previous exact/ANN evidence is not relabeled as new execution.

## Paired measured relevance

P@k = selected-positive hits/k, absent slots zero. MRR5 = reciprocal rank truncated at5, not percent accuracy. R5 = macro selected-label recall@5. Pool = macro selected-label recall in ungated pool20 (gated recall is also retained). Means below use24 selected-answerable questions, once each in block0; latency uses64 actual requests per cell, including no-answer queries, across both blocks.

| Model | Branch | P1 | P3 | P5 | MRR5 | R5 | Pool recall | E2E p50 / p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| minilm_parent128 | equal | 0.5417 | 0.2500 | 0.1583 | 0.5986 | 0.7083 | 0.8750 | 4.798 / 5.719 |
| minilm_parent128 | dense2 | 0.5000 | 0.2361 | 0.1583 | 0.5792 | 0.7083 | 0.8750 | 4.772 / 5.303 |
| minilm_parent128 | lexical2 | 0.5417 | 0.2361 | 0.1583 | 0.5951 | 0.7083 | 0.8542 | 4.841 / 5.335 |
| minilm_parent128 | dense_only | 0.5000 | 0.2500 | 0.1500 | 0.5694 | 0.6458 | 0.8958 | 4.743 / 5.419 |
| e5_parent128 | equal | 0.5417 | 0.2639 | 0.1667 | 0.6264 | 0.7500 | 0.8542 | 5.131 / 5.925 |
| e5_parent128 | dense2 | 0.5417 | 0.2639 | 0.1750 | 0.6368 | 0.7917 | 0.8542 | 5.090 / 5.701 |
| e5_parent128 | lexical2 | 0.5000 | 0.2500 | 0.1583 | 0.5938 | 0.7083 | 0.8542 | 5.000 / 5.701 |
| e5_parent128 | dense_only | 0.6250 | 0.2778 | 0.1667 | 0.6875 | 0.7292 | 0.9792 | 5.028 / 5.531 |
| e5_parent512 | equal | 0.4583 | 0.2222 | 0.1417 | 0.5292 | 0.6250 | 0.9375 | 5.131 / 5.825 |
| e5_parent512 | dense2 | 0.4583 | 0.2083 | 0.1500 | 0.5292 | 0.6667 | 0.9583 | 5.027 / 5.555 |
| e5_parent512 | lexical2 | 0.5417 | 0.2361 | 0.1417 | 0.5764 | 0.6250 | 0.8958 | 5.013 / 5.815 |
| e5_parent512 | dense_only | 0.4167 | 0.2500 | 0.1500 | 0.5278 | 0.6667 | 0.9583 | 5.004 / 5.792 |

### Language and technical constraints/negation

The frozen `fr` subset contains all nine French selected-answerable questions, including the Qdrant-version question; `en` contains15 English answerable questions. The old `fr_to_en` category contains eight and remains separately summarized in JSON. The three-question `technical_negation` subset is explicitly `development-01` (same-host WAL restriction), `holdout-00` (cannot write simultaneously) and `holdout-09` (excluded/forbidden filter condition). It is a tiny technical-constraint diagnostic, not a broad negation benchmark. No-answer queries are outside these language tables, but all eight are assessed separately.

| Model | Branch | French P1 / R5 (n9) | English P1 / R5 (n15) | Constraint/negation P1 / R5 (n3) |
|---|---|---:|---:|---:|
| minilm_parent128 | equal | 0.2222 / 0.3333 | 0.7333 / 0.9333 | 0.3333 / 0.3333 |
| minilm_parent128 | dense2 | 0.2222 / 0.3333 | 0.6667 / 0.9333 | 0.3333 / 0.3333 |
| minilm_parent128 | lexical2 | 0.1111 / 0.2222 | 0.8000 / 1.0000 | 0.0000 / 0.3333 |
| minilm_parent128 | dense_only | 0.2222 / 0.3889 | 0.6667 / 0.8000 | 0.3333 / 0.3333 |
| e5_parent128 | equal | 0.2222 / 0.3333 | 0.7333 / 1.0000 | 0.3333 / 0.6667 |
| e5_parent128 | dense2 | 0.2222 / 0.4444 | 0.7333 / 1.0000 | 0.3333 / 0.6667 |
| e5_parent128 | lexical2 | 0.1111 / 0.2222 | 0.7333 / 1.0000 | 0.0000 / 0.0000 |
| e5_parent128 | dense_only | 0.5556 / 0.5000 | 0.6667 / 0.8667 | 0.6667 / 0.6667 |
| e5_parent512 | equal | 0.1111 / 0.1111 | 0.6667 / 0.9333 | 0.0000 / 0.0000 |
| e5_parent512 | dense2 | 0.1111 / 0.3333 | 0.6667 / 0.8667 | 0.0000 / 0.6667 |
| e5_parent512 | lexical2 | 0.1111 / 0.1111 | 0.8000 / 0.9333 | 0.0000 / 0.0000 |
| e5_parent512 | dense_only | 0.2222 / 0.4444 | 0.5333 / 0.8000 | 0.3333 / 0.6667 |

Concrete gains/losses, relative to the same model's equal branch:

- MiniLM dense2 loses selected `fts-bm25` P1 (rank1→2); no French aggregate gain. Lexical2 promotes `qfilter-must` to1 and recovers `qfilter-should` into5, but moves same-host `wal-network`1→4 and drops `async-shield` outside5. English benefit masks French loss.
- E5_128 dense2 recovers French `async-shield` at5 and moves same-host WAL5→2; P1 unchanged, R5 .7500→.7917. It is not a universal fix.
- E5_128 dense-only promotes same-host WAL, French backup and shield to1 (French P1 .2222→.5556) but loses selected `qfilter-must` and `qfilter-should` from5 and moves English DBSF1→2. English R5 falls1.0000→.8667; overall R5 falls .7500→.7292 despite improved P1.
- E5_512 dense2 recovers `wal-network` at5 and `wal-writer` at4, but loses `qfilter-must` from5. Lexical2 promotes English dirty-read evidence and FTS prefix to1, but does not repair the French aggregate.
- E5_512 dense-only recovers the two WAL constraints and French shield, but loses must/should evidence and demotes Python3.11 transaction evidence1→2. No dominant branch emerges.
- **Strict filter negation remains unsolved:** all twelve cells miss selected `qfilter-not` in top5 for `holdout-09`. MiniLM equal/dense2/lexical2 still return explicitly incompatible `qfilter-must`; E5_128 lexical2 newly does so. Removing an incompatible result in dense-only does not establish retrieval of the correct proof.

Across all32 questions, incompatible top-five counts in branch order equal/dense2/lexical2/dense-only are MiniLM **2/2/1/0**, E5_128 **0/0/1/0**, E5_512 **0/0/0/0**; incompatible top-one counts are zero throughout. UNKNOWN top-five counts are **139/139/140/142**, **140/139/140/140**, **143/142/143/142**, respectively. UNKNOWN is not proven irrelevant; selected labels are incomplete and often permit only one or two positives in five slots.

**No-answer unresolved: 8/8 nonempty retrieval false accepts for every model/branch.** There is no abstention rule here and no generated-answer evaluation. No probability, 90% precision, independent-human validation or vault-generalization claim is justified.

## Exact WAL dense1 → fusion7 causality

Query `development-01`: “Pourquoi SQLite WAL exige-t-il que tous les processus soient sur le même ordinateur ?” Selected evidence is `wal-network`.

All three encoders rank it dense1; the shared lexical rank is16. Native E5 cosine is0.86939716. RRF discards that raw magnitude and uses only branch positions: equal score `1/61 + 1/76 = 0.029551337359792925` in **every model**. Its score does not get worse under E5; six competitors gain dense positions while keeping the same lexical support:

| Native E5 equal candidate | Dense rank | Lexical rank | RRF score |
|---|---:|---:|---:|
| wal-context-08 | 4 | 3 | 0.03149801587301587 |
| wal-context-10 | 7 | 1 | 0.03131881575727918 |
| wal-context-09 | 2 | 6 | 0.03128054740957967 |
| isolation-context-01 | 3 | 8 | 0.03057889822595705 |
| wal-checkpoint | 5 | 9 | 0.029877369007803793 |
| wal-context-11 | 9 | 5 | 0.029877369007803793 |
| **wal-network** | **1** | **16** | **0.029551337359792925** |

The tied fifth/sixth scores use ascending document ID. All seven are admitted as NOT_ASSESSED; neither version gating nor candidate omission explains this failure. `wal-network` is in pool20 at7, not lost to retrieval. The same target's equal fusion ranks are MiniLM1, E5_1285, E5_5127 because the **other candidates' dense ranks change**.

| Model | Equal | Dense2 | Lexical2 | Dense-only |
|---|---:|---:|---:|---:|
| MiniLM128 target rank | 1 | 1 | 4 | 1 |
| E5_128 target rank | 5 | 2 | 8 | 1 |
| E5_512 target rank | 7 | 5 | 10 | 1 |

Dense2 target score is0.045944779982743746, still behind four native-E5 competitors; lexical2 score is0.04270923209663503, behind nine. This is exact candidate/rank arithmetic, not a confidence calibration or a posthoc weight search.

## Timing, integrity and cleanup

All timings are actual per-request intervals, not reused stage sums. Encode, HTTP JSON/transport/server, lexical-plus-parent-resolution, weighted fusion/both gates and evidence/citation JSON are retained individually. Evidence-file logging/export/hash auditing is outside E2E. Dense-only retains unused lexical work intentionally. Stage medians need not sum to E2E median.

| Equal-RRF model | Encode p50 ms | HTTP p50 ms | Lexical/resolution p50 ms | Fusion/gates p50 ms | Citation/evidence JSON p50 ms |
|---|---:|---:|---:|---:|---:|
| MiniLM128 | 3.001 | 0.737 | 0.138 | 0.669 | 0.187 |
| E5_128 | 3.327 | 0.779 | 0.139 | 0.673 | 0.187 |
| E5_512 | 3.321 | 0.754 | 0.142 | 0.670 | 0.183 |

- Resident session load/hash validation1785.215ms; offline passage encoding1304.290 /1291.988 /5359.106ms, excluded from E2E. Runtime Python3.11.16, NumPy2.4.6, ONNX Runtime1.31.0, CPU provider, batch8, intra/inter threads2/1.
- Truncated passage counts135/136,136/136,3/136 for MiniLM128/E5_128/E5_512; no query exceeds its cap. Prefix-aware token counts and visible offsets/omitted suffixes are retained. No change in truncation across ranking branches.
- Every equal baseline matches the historical multilingual run's top5 on32/32 questions; repeated block top5 and all dense/lexical candidate lists match across branches. This is reproducibility, not relevance acceptance.
- Readback maximum absolute vector error1.4091273120575565e-08; every point/payload checked. Every emitted evidence body matches original source offsets and SHA256. Both gates replay with zero violations.
- Harness RSS after measurement2692632576 bytes; Qdrant40652800 bytes. Harness includes three active encoder sessions and allocator effects, not standalone model memory. No claim of tiny production footprint.
- Owned PID14412, port60976 exited/closed; terminate/wait returncode1 is forced owned-process termination, **not graceful shutdown**. No other PID was touched; isolated storage retained for audit.
- Zero model downloads, installs, shared-environment, global configuration, vault, runtime or existing-symbol edits. No staging/commit/push. Graph status was ready but explicitly excludes tools/docs/artifacts; helpers were read directly, not assumed graph-covered. GSD CLI is available; repo progress reported unreadable/no phases, so the durable work item is Beads, not an invented GSD phase.

## Bounded follow-up, not retrospective selection

1. **Validation:** independently judge a fresh small bilingual/operator/negation set before choosing weights. Potential gain: distinguish reproducible diagnostics from observed-set overfit. Do not promote dense-only merely because its P1 is highest here.
2. **Ranking:** if another experiment is authorized, freeze one existing pool20 reranker comparison separately and retain same-pool controls. High candidate recall makes ranking worth investigating, but this report deliberately stops at the clean first-pass attribution; no reranker is claimed executed.
3. **Personal-product delivery:** prioritize an authorized source-sync/search/get/update/delete/restart pilot in parallel with evaluation, retaining originals. More benchmark variants alone do not deliver the desired agent KB replacement.
