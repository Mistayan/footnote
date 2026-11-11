# Frozen fusion-weight experiment

**Outcome: fusion explains a real native-E5 regression, but no new default is selected.** Increasing dense weight recovers the French WAL proof into top5 while losing another selected proof. Negation remains unresolved in every matrix cell. These are reused diagnostics, not acceptance or independent validation; no 90% claim.

Status: **OPEN — parent verification required.** No Beads closure, incumbent/runtime changes, private ingestion, model downloads, installs, shared-environment mutation, staging, commits or pushes.

## Evidence and reproduction

Primary verified run: [`paired-2ae1521cc129454a82660954b2f4c517`](../../artifacts/fusion-weights/paired-2ae1521cc129454a82660954b2f4c517/).

- `freeze.json`: finite protocol saved before model initialization/inference. SHA256 `2dbdbaeca951bc8687ba2682191eb055b390b86145b6b7000f8e5dfc04d10e2a`.
- `report.json`: all18 cells, all/FR→EN/negation/no-answer summaries, measured costs and cleanup.
- `PER-QUERY-REVIEW.md`: all576 unique question/model/weight combinations, ordered five source excerpts, URLs, offsets, passage/raw-source hashes, selected labels, incompatible/UNKNOWN IDs and metrics.
- `raw-results.json` / `.jsonl`: **1152 independently executed resident requests** (32 questions × three encoders × six ranking settings × two counterordered blocks), actual HTTP responses, dense60/lexical20 ranks, complete fused ordering, per-candidate weighted contributions, pool20, gates, top5, timings, full citation evidence and query-vector identity.
- `target-attribution.json`: every selected target's branch/fused rank, contribution, and **every competitor above it**, including targets absent from active branches. Reporting uses labels after ranking, not in the indexed text or payload.
- `paired-changes.json`: every cell versus equal fusion for that same encoder, preserving regressions as well as gains.
- All three passage/query `.npy` matrices, model manifests/recipes, collection vector/payload readbacks, archived code, original public `.raw` and `.txt` sources, receipts, and `evidence-sha256.json` (170 retained files; manifest SHA256 `999fd56f103dd54c79b2a2320c794c1f83f290be6178c9a21d7833123321357e`).
- Final independent replay verified the actual HTTP response→dense rank mapping and independently reconstructed the weighted reciprocal-rank formula for all1152 rows, plus all18 aggregate metric cells; standalone `--verify` returned `True`.

```bash
.venv/Scripts/python.exe tests/fusion_weight_experiment_test.py -v
.venv/Scripts/python.exe tools/fusion_weight_experiment.py --verify artifacts/fusion-weights/paired-2ae1521cc129454a82660954b2f4c517
# New unique run only; never overwrite evidence:
.venv/Scripts/python.exe tools/fusion_weight_experiment.py
```

Three tests passed in **31.863s**: independent RRF formula and incumbent equal-RRF parity; direct real ONNX masked-mean/L2/prefix/truncation parity for all three model recipes; complete actual server matrix, evidence verification and deliberate evidence-byte corruption rejection/restoration. RED was observed first for the missing formula module, then missing resident factory/runner. This is the owned experiment suite, not a full application regression claim.

An initial run `paired-4c9fb135b6d343e696be3524b1b511c9` completed1152 calls but its final audit failed: old `text_sha256` receipts hash normalized LF Unicode, while some Windows `.txt` bytes contain CRLF. The verifier was corrected to distinguish normalized-text hashes from byte hashes; unchanged original `.raw` bytes and every retained file's byte hash are still checked. The first run is retained, not overwritten. Its original code and freeze remain available; current-input verification deliberately rejects it after the verifier change. No model, weights, query, labels or ranking changed in response to that run.

## Frozen protocol

136 unchanged original parent passages;32 old questions,24 selected-answerable and eight no-answer; eight selected-answerable French questions against English evidence. Same snapshot as the multilingual experiment. Text/source versions, offsets, passage identity, segmentation, lexical tokenizer/OR query, dense/lexical budgets, source-version gates and cutoff remain unchanged. No headings, label-derived metadata, query-specific rules, expansion, translation, reranking or abstention.

Encoders reuse the existing hash-verified CPU ONNX artifacts:

| Variant | Model | Cap | Prefixes query / passage |
|---|---|---:|---|
| minilm_parent128 | Xenova/paraphrase-multilingual-MiniLM-L12-v2 |128| empty / empty |
| e5_parent512 | Xenova/multilingual-e5-small |512| `query: ` / `passage: ` |
| e5_parent128 | same E5, separate short-context control |128| `query: ` / `passage: ` |

Both checkpoints are multilingual,384-dimensional, attention-mask mean pooled and L2-normalized. Native E5 changes model **and** context capacity;128 is an independently declared length control, not identical token visibility. Pinned identities, upstream license declarations and the conversion-card license caveat are inherited from [the audited multilingual experiment](MULTILINGUAL-EMBEDDINGS.md) and retained in `model-recipes.json`. All actual passage and query vectors are bit-identical to that experiment for the corresponding recipe, including every independently repeated query encoding. No downloads were performed.

The finite settings, frozen before inference, are **dense-only, lexical-only, dense:lexical RRF1:1,2:1,4:1,1:2**. One-based rank formula:

`score(d) = wd/(60 + dense_rank(d)) + wl/(60 + lexical_rank(d))`

An absent or inactive branch contributes zero; union only includes positive-contribution IDs. Sorting is descending score then ID, as in the existing equal-RRF helper. Dense top60, lexical top20, fused pool20, no refill, existing source-derived gate before selection and independently at presentation, final top5. Unknown source metadata is rejected on explicit requested Python versions, otherwise `NOT_ASSESSED`; this gate is not universal applicability reasoning. Query vectors and dense/lexical branch ranks exactly match the historical experiment for each model, and every equal-fusion top5 exactly reproduces it.

A new owned loopback Qdrant1.19.2 process, commit `016542aa5deb6c66380bb137badf73d54f742bde`, uses isolated storage and three collections. Cosine384, HNSW M16/ef_construct100/ef128, all vectors indexed and read back. ANN128 is held fixed here; there is no new exact-search arm. The previous paired experiment independently demonstrated ANN/exact top5 parity for these vectors. No incumbent service/PID was touched.

**Single-branch controls disable the other branch's ranking contribution, not acquisition work.** Every timed cell independently runs encoding, actual dense HTTP and lexical acquisition to keep branches and common budgets fixed. Therefore these are matched-acquisition pipeline timings, not optimized dense-only/lexical-only serving costs.

## Measured selected-label relevance

P@k = selected-positive hits/k, including missing slots as zero. Means below use the24 selected-answerable questions; MRR is reciprocal rank truncated at5, not percent correctness. R5 and pool recall are macro selected-label recall. Incompatible/UNKNOWN counts use all32 questions, once per cell, not both repeats. Labels are incomplete author-selected evidence locations; UNKNOWN passages may answer a question. These are **judged-set diagnostics, not exhaustive semantic precision**.

| Model | Ranking | P1 | P3 | P5 | MRR5 | R5 | Pool20 recall | Incompatible@5 | UNKNOWN@5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MiniLM128 | dense |.5000|.2500|.1500|.5694|.6458|.8958|0|142|
| MiniLM128 | lexical |.4167|.2361|.1500|.5292|.6667|.8542|1|141|
| MiniLM128 |1:1|.5417|.2500|.1583|.5986|.7083|.8750|2|139|
| MiniLM128 |2:1|.5000|.2361|.1583|.5792|.7083|.8750|2|139|
| MiniLM128 |4:1|.5000|.2361|.1500|.5660|.6667|1.0000|2|140|
| MiniLM128 |1:2|.5417|.2361|.1583|.5951|.7083|.8542|1|140|
| E5 native512 | dense |.4167|.2500|.1500|.5278|.6667|.9583|0|142|
| E5 native512 | lexical |.4167|.2361|.1500|.5292|.6667|.8542|1|141|
| E5 native512 |1:1|.4583|.2222|.1417|.5292|.6250|.9375|0|143|
| E5 native512 |2:1|.4583|.2083|.1500|.5292|.6667|.9583|0|142|
| E5 native512 |4:1|.4583|.2361|.1500|.5431|.6667|.9583|0|142|
| E5 native512 |1:2|.5417|.2361|.1417|.5764|.6250|.8958|0|143|
| E5 control128 | dense |.6250|.2778|.1667|.6875|.7292|.9792|0|140|
| E5 control128 | lexical |.4167|.2361|.1500|.5292|.6667|.8542|1|141|
| E5 control128 |1:1|.5417|.2639|.1667|.6264|.7500|.8542|0|140|
| E5 control128 |2:1|.5417|.2639|.1750|.6368|.7917|.8542|0|139|
| E5 control128 |4:1|.5000|.2639|.1667|.6056|.7500|.8542|0|140|
| E5 control128 |1:2|.5000|.2500|.1583|.5938|.7083|.8542|1|140|

All18 cells have zero incompatible top1. **All18 cells return results on all eight no-answer questions:8/8 retrieval false accepts.** This is nonempty retrieval, not a measured generated-answer error. RRF scores are rankings, never confidence. Zero source-version gate violations; those gates do not remove all semantic incompatibilities.

### French → English (eight selected-answerable)

Cells show **P1 / R5 / pool20 recall**.

| Model | dense | lexical |1:1|2:1|4:1|1:2|
|---|---|---|---|---|---|---|
| MiniLM128 |.2500/.4375/.8125|.0000/.1250/.5625|.2500/.3750/.6250|.2500/.3750/.6250|.2500/.3750/1.0000|.1250/.2500/.5625|
| E5 native512 |.2500/.5000/.8750|.0000/.1250/.5625|.1250/.1250/.8125|.1250/.3750/.8750|.1250/.3750/.8750|.1250/.1250/.6875|
| E5 control128 |.6250/.5625/.9375|.0000/.1250/.5625|.2500/.3750/.5625|.2500/.5000/.5625|.2500/.5000/.5625|.1250/.1250/.5625|

Removing lexical influence helps some French rankings but does not establish a general winner: control128 dense has higher P1 yet lower overall R5 than its1:1 fusion. Native512 lexical-heavy improves aggregate P1 but leaves French recall low. Candidate acquisition and presentation are distinct problems.

## WAL failure: unchanged target score, better competing dense ranks

Question `development-01`: **Pourquoi SQLite WAL exige-t-il que tous les processus soient sur le même ordinateur ?** Selected target `wal-network` is dense rank1 and lexical rank16 in all three models.

| Model | dense-only rank | lexical-only rank |1:1 rank|2:1 rank|4:1 rank|1:2 rank|
|---|---:|---:|---:|---:|---:|---:|
| MiniLM128 |1|16|1|1|1|4|
| E5 native512 |1|16|7|5|2|10|
| E5 control128 |1|16|5|2|2|8|

For1:1 the target score is exactly the same in all three models: `1/61 + 1/76 = 0.029551337359792925`. Native E5 did **not** lose the proof in dense search, nor reduce its fused score. Six competitors now outrank it because they obtain better dense positions while keeping their lexical contributions:

| Native E5 competitor above wal-network | Dense rank | Lexical rank | Dense contribution | Lexical contribution | Total1:1 |
|---|---:|---:|---:|---:|---:|
| wal-context-08 |4|3|.0156250000|.0158730159|.0314980159|
| wal-context-10 |7|1|.0149253731|.0163934426|.0313188158|
| wal-context-09 |2|6|.0161290323|.0151515152|.0312805474|
| isolation-context-01 |3|8|.0158730159|.0147058824|.0305788982|
| wal-checkpoint |5|9|.0153846154|.0144927536|.0298773690|
| wal-context-11 |9|5|.0144927536|.0153846154|.0298773690|

The target gets `0.045944779982743746` at2:1 and `0.07873166522864539` at4:1, restoring top5, but this is diagnostic recovery, not calibrated correctness. All competing candidates/contributions for every weight and query are retained, not just these six.

### Gains AND regressions versus each model's equal fusion

Count questions with positive/negative selected R5 delta (24 answerable; ties excluded):

| Model | dense gains/losses |2:1 gains/losses|4:1 gains/losses|1:2 gains/losses|
|---|---:|---:|---:|---:|
| MiniLM128 |1/2|0/0|0/1|1/1|
| E5 native512 |3/2|2/1|2/1|0/0|
| E5 control128 |2/2|1/0|1/1|1/2|

For native E5,2:1 recovers `wal-network` (`development-01`) and `wal-writer` (`holdout-00`), but loses `qfilter-must` from top5 on `development-06`. Its unchanged aggregate MRR5 conceals those changes. Control1282:1 improves selected recall here without a recall loss on this reused set; that does **not** authorize a posthoc default or prove generalization.

## Negation failure class remains open

The frozen diagnostic contains **one selected negation question**, `holdout-09`: **Quel opérateur Qdrant exclut tous les points satisfaisant une condition interdite ?** Relevant `qfilter-not`; incompatible `qfilter-must` and `qfilter-should`. This tiny class is not a broad operator benchmark.

`qfilter-not` is absent from lexical20 for all models. Its full branch/fused ranks:

| Model | dense rank | lexical rank |1:1 rank|2:1 rank|4:1 rank|1:2 rank|
|---|---:|---|---:|---:|---:|---:|
| MiniLM128 |10|absent|24|22|17|27|
| E5 native512 |10|absent|20|20|19|21|
| E5 control128 |14|absent|24|23|22|25|

Every setting has selected P1/P3/P5, MRR5 and R5 equal to zero for this question, including dense-only. MiniLM4:1 acquires the proof into pool20 without presenting it; native512 already has it in pool20 at1:1,2:1,4:1, but never top5. Control128 weighted fusion still excludes it from pool20. Merely weakening lexical influence cannot solve the dense-rank10/14 evidence discrimination failure. No hardcoded negation fix or new query expansion was introduced.

## Real latency versus attribution

Each cell's64 timings are independent actual resident requests (32 questions × two blocks). E2E is directly measured from request start through that request's encoding, actual HTTP, lexical search, fusion, two gates, citation assembly and outgoing JSON serialization. No shared stage time is relabeled E2E. Saved branch-contribution evidence, raw-response logging, hashes and report exports are outside the request boundary.

`timing_ms` also retains measured encode/http/lexical-parent/fusion-gates/citations-JSON intervals and their **attributed sum**, separately from directly measured `e2e`. These contiguous stage intervals currently telescope to E2E; equality is not a second independent timing experiment. The wall measurement window includes logging overhead and is not the sum of request latencies alone. Citation/JSON timing includes selected-label evaluation bookkeeping in this diagnostic harness; it is not a production service latency claim.

| Model | Ranking | E2E p50 ms | E2E p95 ms |
|---|---|---:|---:|
| MiniLM128 |dense|4.540|5.159|
| MiniLM128 |lexical|4.414|4.977|
| MiniLM128 |1:1|4.391|5.102|
| MiniLM128 |2:1|4.379|4.980|
| MiniLM128 |4:1|4.497|4.903|
| MiniLM128 |1:2|4.448|5.153|
| E5 native512 |dense|4.709|5.446|
| E5 native512 |lexical|4.677|5.266|
| E5 native512 |1:1|4.635|5.174|
| E5 native512 |2:1|4.569|5.184|
| E5 native512 |4:1|4.683|5.297|
| E5 native512 |1:2|4.743|5.351|
| E5 control128 |dense|4.760|5.436|
| E5 control128 |lexical|4.758|5.222|
| E5 control128 |1:1|4.643|5.242|
| E5 control128 |2:1|4.581|5.203|
| E5 control128 |4:1|4.658|5.301|
| E5 control128 |1:2|4.703|5.316|

- Resident model load/hash validation: **1781.250ms**, excluded from resident requests.
- Offline passage encoding: MiniLM128 **1289.973ms**; E5 native512 **5437.995ms**; E5 control128 **1266.525ms**, excluded from requests.
- Actual1152-request measurement/logging window: **5.688s**. Small CPU diagnostic; two blocks do not establish production p99 or statistically reliable speed differences among weights.
- Owned PID22764/port50707 exited/closed, returncode1 from Windows owned-process terminate/wait, not a claimed graceful shutdown. All frozen inputs unchanged. Every vector/payload read back, source offsets/raw/normalized hashes verified, repeated ranks stable.

## Decision boundary

This experiment establishes a concrete fusion failure and bounded recovery, **not** a replacement encoder or weight policy. Selected labels are incomplete and reused, related-topic holdout is not independent human validation, all no-answer cases remain accepted by retrieval, and the negation proof is still never presented. No claim about a private user vault or90% industrial precision follows. Fresh independent judgments and a separately frozen applicability/abstention acceptance protocol are still required. Leave the parent FUSION task open.
