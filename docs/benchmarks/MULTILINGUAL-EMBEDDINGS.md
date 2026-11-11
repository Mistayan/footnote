# Multilingual embeddings: frozen paired diagnostic

**Outcome: do not replace the current encoder on this evidence.** The existing `e5-small` is already **multilingual E5-small**, not English-only E5. Both incumbent MiniLM and tested E5 are multilingual. Native E5 improves selected candidate recall but regresses selected top-five relevance, including French-to-English questions. This is an executed model experiment, not another lexical substitution.

Status: **OPEN — parent verification required.** No runtime activation, private ingestion, shared-environment modification, staging or commits.

## Evidence and reproduction

Primary run: [`paired-fc703e012031447fb5066b8224f540b4`](../../artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4/).

- [`report.json`](../../artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4/report.json): measured summaries, costs, truncation and cleanup.
- [`PER-QUERY-REVIEW.md`](../../artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4/PER-QUERY-REVIEW.md): every question/variant/search mode, ordered five snippets, source URLs, offsets, passage hashes, labels and repeated latency.
- `raw-results.json` / `.jsonl`: 512 actual requests, raw Qdrant responses, dense/lexical ranks, pool20, gates, candidates, full evidence and query-vector hashes.
- `paired-changes.json`: every per-query delta against the exact incumbent, without selecting only improvements.
- `model-recipes.json`, `freeze.json`, vector `.npy` files, four `*-readback.json`, `*-visibility.json`, original public sources and archived code.
- `evidence-sha256.json` SHA256: `e23438aa1d8b6ff79413b19a84444a88c65bd6f6efab0a9442aa7f828ead80c4`.
- Freeze SHA256: `12b58526ce5e6ea2d2f38cc8c3521f1744a515560e4ab0f826fa1b165cca308d`.

```bash
.venv/Scripts/python.exe tests/multilingual_embedding_experiment_test.py -v
.venv/Scripts/python.exe tools/multilingual_embedding_experiment.py --verify artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4
# New unique run, same frozen recipe:
.venv/Scripts/python.exe tools/multilingual_embedding_experiment.py
```

Four tests passed in 32.979 seconds, including a complete isolated server experiment, direct ONNX attention-mask pooling/prefix/tokenizer parity for both models, historical baseline helper parity, deliberate evidence-byte corruption rejection, and saved-query-vector semantic hash mismatch rejection. Each new feature was first observed failing before implementation. Only this owned test file was run; this is not a full application regression claim.

A first successful run `paired-676f3306d50d451cb03a52d6d834423d` is retained, not overwritten. The primary repeat adds historical-input hash coverage and semantic query-vector verification; variants, ranking, labels and model recipe were not tuned after observing that first run. Current-input verification intentionally rejects old runs after harness changes; archived code and original hashes remain available.

## Exact model identity and recipe

The local model manifests were read and every model/tokenizer SHA checked before execution.

The conversion cards identify their upstream models.[1][3]

The E5 upstream card specifies `query: ` / `passage: ` even for non-English inputs, attention-mask mean pooling, 512-token truncation and L2 normalization.[2]

MiniLM upstream specifies 384 dimensions, 128 tokens and attention-mask mean pooling; cosine search retains the incumbent L2 normalization.[4]

| Artifact | Incumbent | Actual multilingual E5-small |
|---|---|---|
| Conversion repository | `Xenova/paraphrase-multilingual-MiniLM-L12-v2` | `Xenova/multilingual-e5-small` |
| Pinned conversion revision | `2c4055b12046f11709e9df2c122e59ffbdc2f900` | `761b726dd34fb83930e26aab4e9ac3899aa1fa78` |
| Native token cap | 128 | 512 |
| Query / passage prefixes | empty / empty | `query: ` / `passage: ` |
| Dimension / pooling | 384 / masked mean + L2 | 384 / masked mean + L2 |
| ONNX artifact bytes | 118308126 | 118308185 |
| Tokenizer bytes | 17082913 | 17082730 |
| Upstream declared license | Apache-2.0 | MIT |

Upstream license declarations were retrieved at revisions `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` (MiniLM) and `614241f622f53c4eeff9890bdc4f31cfecc418b3` (E5).[2][4]

The pinned conversion cards do **not** declare a license field; the manifest records `NOT_DECLARED_IN_CONVERSION_CARD` rather than claiming an independently verified conversion license.[1][3]

This is a licensing caveat for redistribution, not an invented model license.

SHA256 of the exact downloaded-existing ONNX bytes:

- MiniLM: `66fc00f5f29afcaff34092e1bdd20008ca3918265a82fb9695a551e510cc4ebc`.
- E5-small: `f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193`.

Tokenizer hashes, URLs and exact byte sizes are in `model-recipes.json`. These are the existing public quantized ONNX checkpoints, not locally generated quantization or an undocumented conversion recipe. Runtime: Python 3.11.16, NumPy 2.4.6, ONNX Runtime 1.31.0, CPU provider, intra/inter-op 2/1, batch8, padding ID1, mask-aware pooling. Tests independently reconstruct vectors directly from each real ONNX output and compare against the incumbent resident helper.

**Provisioning cost:** zero new model bytes, zero installs, zero shared-venv changes. Both existing model directories together occupy 270783744 bytes. Retained fetched public cards/configs/citation metadata occupy 508796 bytes; total wire traffic including API responses was not instrumented. Initial conversion-repository pooling/sequence-config URLs returned 404; actual pinned upstream configurations were then retrieved. No unavailable artifact was replaced with fabricated data.

## Frozen protocol and attribution

136 unchanged parent passages from the existing public technical snapshot, 32 reused questions: 24 selected-answerable and eight no-answer. Source bytes, offsets and text hashes are verified. No private/vault corpus is touched. Queries and incomplete author-made selected labels are old diagnostics, **not an independent holdout**.

Four prespecified variants were frozen before encoder initialization/inference:

1. `minilm_parent128`: exact incumbent parent-text control.
2. `e5_parent512`: actual multilingual E5 with its native 512-token recipe, same parent text/segmentation. This changes **model plus native context length**, not weights alone.
3. `e5_parent128`: separately labeled E5 length-matched diagnostic. Same cap, different model/tokenizer/prefix recipe; not a claim of token-for-token visibility equivalence.
4. `minilm_child127`: separate segmentation-only control, 391 lossless original-text children strictly below128 tokens, no headings or enrichment; max-child parent collapse, top60 point budget without refill. It must not be conflated with the model effect.

Every variant uses the same FTS5 OR query, dense60/lexical20, RRF constant60, pool20, existing source-derived version gate before selection and independently at presentation, then top5. No reranker, translation, query expansion, thresholds or abstention training. Unknown metadata is rejected for explicit requested Python versions, otherwise `NOT_ASSESSED`; the existing family gate is not universal version understanding.

An owned loopback Qdrant 1.19.2 server (`016542aa5deb6c66380bb137badf73d54f742bde`) uses separate collections/storage, cosine384, HNSW M16/ef_construct100/ef128. Both actual ANN requests and exact-search control requests are executed twice, reversing query/variant/mode order in block2. Every collection was green and all its vectors indexed/read back before measurement. No other server or PID is stopped.

### Truncation, measured rather than inferred

| Variant | Truncated passage inputs | At-limit inputs | Truncated queries |
|---|---:|---:|---:|
| MiniLM parent128 | 135/136 | 135/136 | 0/32 |
| E5 parent512 | 3/136 | 3/136 | 0/32 |
| E5 parent128 | 136/136 | 136/136 | 0/32 |
| MiniLM child127 | 0/391 | 0/391 | 0/32 |

Counts use full tokenization **after the appropriate prefix**; actual truncation is `tokens > cap`, not merely reaching the cap. Per-input visible offsets and omitted suffixes are saved. Removing truncation did not itself establish better ranking.

## Paired measured results

P@k = selected-positive hits divided by k, missing slots zero. MRR is reciprocal rank truncated at5, not percent correctness. R5 is macro selected-label recall@5. Candidate recall is macro selected-label recall in pool20. Primary relevance means below use the **24 selected-answerable questions**; latency uses 64 independently encoded ANN requests per variant (32 questions × two blocks).

| Variant | P1 | P3 | P5 | MRR5 | R5 | Pool20 recall | E2E p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| minilm_parent128 | 0.5417 | 0.2500 | 0.1583 | 0.5986 | 0.7083 | 0.8750 | 4.735 / 5.465 |
| e5_parent512 | 0.4583 | 0.2222 | 0.1417 | 0.5292 | 0.6250 | 0.9375 | 5.121 / 5.893 |
| e5_parent128 | 0.5417 | 0.2639 | 0.1667 | 0.6264 | 0.7500 | 0.8542 | 5.058 / 5.724 |
| minilm_child127 | 0.5000 | 0.2361 | 0.1417 | 0.5486 | 0.6250 | 0.8750 | 4.734 / 5.528 |

### French questions → English source passages (eight selected-answerable)

| Variant | P1 | P3 | P5 | MRR5 | R5 | Pool20 recall |
|---|---:|---:|---:|---:|---:|---:|
| minilm_parent128 | 0.2500 | 0.0833 | 0.0750 | 0.2750 | 0.3750 | 0.6250 |
| e5_parent512 | 0.1250 | 0.0417 | 0.0250 | 0.1250 | 0.1250 | 0.8125 |
| e5_parent128 | 0.2500 | 0.0833 | 0.0750 | 0.2750 | 0.3750 | 0.5625 |
| minilm_child127 | 0.1250 | 0.0833 | 0.0500 | 0.1875 | 0.2500 | 0.6250 |

For the six **exact-term category** questions, P1 is 0.8333 / 0.8333 / 1.0000 / 0.8333 in the same variant order; R5 is 1.0000 / 1.0000 / 1.0000 / 0.8333. This category is distinct from the backend's exact-search control mode.

Across all32 questions, explicit incompatible top-five counts are **2 / 0 / 0 / 0**; incompatible top-one counts are zero throughout. UNKNOWN top-five counts are **139 / 143 / 140 / 143**. Unjudged context passages may contain useful answers; no result is relabeled after observation. Selected labels are incomplete and often contain only one or two positives, constraining possible selected-set P5. These are not exhaustive semantic-precision estimates.

**No-answer safety remains unresolved:** all four variants return nonempty results on all eight no-answer questions, i.e. **8/8 retrieval false accepts** for each. No-answer precision/confidence is not inferred from RRF, and no generated-answer accuracy was measured.

### Concrete gains, losses and failure attribution

- `development-00`, WAL checkpoint: E5 native moves selected `wal-checkpoint` from baseline rank3 to rank1. E5_128 also ranks it first.
- `development-01`, French same-host WAL: selected `wal-network` is **dense rank1 in both models**, but incumbent fusion presents it first while native E5 fusion drops it to **pool rank7**, outside top5. This is a ranking/fusion failure, not evidence that the multilingual encoder cannot find it.
- `holdout-00`, French concurrent WAL writers: native E5 improves selected `wal-writer` dense rank29→2, yet fused rank12→6 still misses top5. E5_128 presents it first. This supports a bounded pool/ranking follow-up, not a retrospective winner claim.
- `holdout-03`, FTS prefix index: native E5 moves selected `fts-prefix` from rank1 to rank2, promoting UNKNOWN `fts-context-00`; UNKNOWN is not automatically wrong.
- `holdout-05`, backup: native E5 loses selected `py311-backup` from top5 while retaining `backup-snapshot`.
- `holdout-07`, French asyncio shield: native E5 and the separate child control lose selected `async-shield` from top5.
- `holdout-08`, Qdrant should: both E5 lengths recover selected `qfilter-should` into top5; neither reaches selected P1.
- E5_128 is mixed, not a safe replacement: exact-term improvement and modest aggregate MRR/R5 gains, unchanged French aggregate P1/R5, lower pool recall, and `holdout-11` selected Python autocommit rank1→3 behind UNKNOWN context.

All other paired changes and full evidence remain in the linked artifacts. No reranker was added post hoc to conceal this first-pass regression. A next separately frozen experiment could compare the same pool20 reranker on both model recipes, and independently test fusion; neither is claimed executed here.

## Timing, resource and cleanup receipts

- Loading/hash validation of three resident sessions: **1910.805ms**. This is excluded from resident-request latency.
- Offline passage encoding: MiniLM parents **1319.123ms**, native E5 parents **5577.407ms**, E5_128 parents **1336.470ms**, separate MiniLM children **3836.132ms**.
- All512 requests completed in a **2.625s** measurement window. Each E2E includes its own query encoding, actual HTTP, lexical search, fusion, both gates, citation assembly and outgoing JSON serialization; not an attributed sum of reused stages. Evidence logging/export/hash auditing is outside E2E. This is a small CPU microbenchmark, not a production p99 claim.
- Exact-server control E2E p50/p95 ms: MiniLM **4.665/5.541**, E5_512 **5.013/5.646**, E5_128 **5.022/5.525**, MiniLM children **4.780/5.295**.
- ANN and exact top5 match on **32/32 questions for each variant**; repeated top5 ranks are stable. This is backend/rank parity, not relevance acceptance.
- Historical incumbent query and passage vectors are **bit-identical** to the existing matched baseline arrays.
- Readback maximum absolute vector difference: **1.4250265606419177e-08**, with every point/payload checked. Zero version-gate violations. All frozen inputs unchanged.
- Whole test harness RSS after measurement: **2680659968 bytes**; owned Qdrant RSS **50278400 bytes**. Harness memory includes three active encoder sessions and preceding parity-test allocator effects; it is **not** per-model standalone memory.
- Owned PID16996/port59017 exited/closed. Windows terminate/wait returns code1 here; this is forced owned-process termination, not a claimed graceful shutdown. No unrelated PID was touched.

**Acceptance:** no 90% claim, no generalization claim, no vault validation, no model activation. This negative native-E5 result narrows the next intervention toward paired candidate ranking/fusion, while preserving independent fresh judgments as a prerequisite for acceptance.

## Sources

[1] https://huggingface.co/Xenova/multilingual-e5-small/blob/761b726dd34fb83930e26aab4e9ac3899aa1fa78/README.md
[2] https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md
[3] https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/blob/2c4055b12046f11709e9df2c122e59ffbdc2f900/README.md
[4] https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/blob/e8f8c211226b894fcb81acc59f3b34ba3efd5f42/README.md
