# Candidate recall: depth controls and exact lexical index

## Outcome

**Personal knowledge/agent base, approximately 1–2 months; not a banking qualification.** No runtime configuration or production retrieval was changed.

The frozen Qdrant negation proof is **already dense rank 10**, also rank 10 under independently recomputed exact cosine. Historical OR-RRF demotes it to **full fusion rank 24**, outside pool20. Deeper acquisition/pool50 recovers it at rank11, but **does not put it in the presented top5**. Increasing to100 finds no additional frozen positive beyond50. A separate exact-identifier lexical sidecar preserves literal tokens but does **not** fix this French negation query and loses an asyncio proof from final top5.

Final run: [`artifacts/candidate-recall/9eeb92ce715d47d790c3d2873ccdc317/measured-v2/`](../../artifacts/candidate-recall/9eeb92ce715d47d790c3d2873ccdc317/measured-v2/).

- **576 actual requests**: 32 unchanged questions × six variants × three sequential blocks. Baseline pools/top5 reproduced on32/32 questions; all query vectors equal the historical MiniLM vectors.
- Actual owned Qdrant1.19.2 server, existing resident MiniLM ONNX;136 unchanged passages, ten pinned public sources. No downloads/installations/private ingestion.
- **No ≥90% acceptance claim.** Selected old positives and incompatibilities remain frozen and incomplete; all other results remain UNKNOWN. Previously seen development/holdout are both **REUSED DIAGNOSTIC**, not independent validation.

## Frozen experiment

Read before implementation: [retrieval budgets](RETRIEVAL-BUDGETS.md), [ablations](RETRIEVAL-ABLATIONS.md), and [academic research by theme](../research/ACADEMIC-RETRIEVAL-BY-THEME.md), especially sections1.2,3.1–3.3,5. The research motivates separating literal identifiers, candidate generation, ranking and truncation; it does not establish a local improvement. This experiment tests the inexpensive literal-index alternative, **not** late chunking or structure-aware segmentation.

| Variant family | Dense point budget | Lexical budget | Fused parent pool |
|---|---:|---:|---:|
| original_20 / exact_20 |60|20|20|
| original_50 / exact_50 |60|50|50|
| original_100 / exact_100 |100|100|100|

Depth controls deliberately increase acquisition budgets as well as the fused cutoff; do not attribute all changes to cutoff alone. The independent full historical fusion calculation isolates the baseline cutoff loss for the negation proof. At each fixed depth, original versus exact changes **only** the lexical representation/tokenization. Every observed pool has the declared number of distinct parents.

Constants:

- Original MiniLM384D, max128, unchanged empty prefixes, masked mean/L2, CPU intra/inter2/1. One resident session; document vectors reused byte-for-byte, fresh query inference for every request.
- Original lexical: FTS5 unicode61, technical words/underscores/dotted identifiers expressed as literal OR phrases, BM25 ascending then ID.
- Exact lexical: a uniformly applied sidecar uses casefolded whole words with underscores/dots and longest-first operators (`!=`, `==`, `<=`, `>=`, `&&`, `||`, `->`, `=>`, single-character operators). UTF8 hex-encoded ASCII tokens prevent FTS5 splitting an identifier/operator. HTML tags are delimiters; backticks/other unrecognized punctuation delimit. No stemming, stopword tuning, generated terms, translation, query-specific rule or judgment-derived field.
- Full original text, code, negation, source offsets and hashes remain the citation authority; the sidecar never rewrites evidence. It is a narrow tokenizer, **not** a lossless markup parser or complete programming-language lexer. Casefolding deliberately does not enforce case-sensitive API identity. HTML-looking code/comparisons can be ambiguous under its tag heuristic; broader code fidelity is unproven.
- Dense sorting and original first-occurrence parent resolution precede equal-weight, rank1 RRF60 with ID tie-break. Explicit new fusion honors the caller's full acquired lists, rather than inheriting incumbent hidden60/20 caps.
- Qdrant cosine384, shard1, HNSW M16/ef_construct100, full_scan_threshold10KB, indexing_threshold1KB, ANN ef128. Collection green with136 indexed vectors; vectors/payloads read back. Small-corpus planner may scan; no universal HNSW-path or large-scale ANN claim.
- **No filter**, no refill, no abstention, no reranking. Incompatible/UNKNOWN candidates are retained and reported. Python source-version status is diagnostic only, never used to hide a failure. Optional fixed reranker usefulness test was not run.
- Freeze saved before inference. Blocks0/2 run forward, block1 reverses questions/variants. Three requests each are timing repeats, not extra quality examples.

## Candidate recall before ranking versus final quality

Candidate recall = macro fraction of frozen selected proofs present anywhere in that query's pool. Final R5 = macro selected-proof recall in top5. Top1 = selected-positive top1 rate. MRR5 = mean reciprocal first-positive rank at cutoff5, **not a truth percentage**. Twelve answerable unique questions per split; no-answer metrics are separate/null where inapplicable. There are27 selected query–proof assignments in total, not exhaustive judgments of all136 passages.

| Variant | Dev candidate recall | Dev top1 / R5 / MRR5 | Reused holdout candidate recall | Holdout top1 / R5 / MRR5 |
|---|---:|---|---:|---|
| original_20 |.8333|.5833 / .7500 / .6528|.9167|.5000 / .6667 / .5444|
| original_50 |1.0000|.5833 / .7500 / .6528|1.0000|.5000 / .6667 / .5444|
| original_100 |1.0000|.5833 / .7500 / .6528|1.0000|.5000 / .6667 / .5444|
| exact_20 |.9167|.4167 / .7500 / .5694|.9167|.5000 / .5833 / .5417|
| exact_50 |1.0000|.4167 / .7500 / .5694|1.0000|.5000 / .5833 / .5417|
| exact_100 |1.0000|.4167 / .7500 / .5694|1.0000|.5000 / .5833 / .5417|

In every variant, all four no-answer questions **per split** receive five candidates:4/4 candidate false acceptance, not generated-answer accuracy. Answerable requests are also nonempty12/12. There is no abstention success.

| Family, all three depths | Explicit incompatible top5 dev / holdout | UNKNOWN top5 dev / holdout | Known wrong Python version top5 dev / holdout |
|---|---:|---:|---:|
| original |2 / 2|68 / 69|1 / 3|
| exact |1 / 3|69 / 69|1 / 4|

Counts use16 unique questions × five displayed slots per split. A source-version mismatch and an explicit incompatible judgment are different dimensions. UNKNOWN is not treated as irrelevant or compatible. No confidence probabilities are inferred from cosine, BM25 or RRF.

## Diagnosis: why `must_not` disappears

Question `holdout-09`: **« Quel opérateur Qdrant exclut tous les points satisfaisant une condition interdite ? »**

The frozen label is **`qfilter-not`**; `must_not` is its actual operator. Earlier prose called it `qfilter-must_not`, which is not the snapshot ID. No label has been renamed.

Pinned [Qdrant source](https://raw.githubusercontent.com/qdrant/landing_page/3d4e1897a2ca017999ad3d77b1ade6f7530ca1ed/qdrant-landing/content/documentation/search/filtering.md), normalized source offsets[3063,3537), passage SHA256 `8c089272b4bd06cc552b021e79b1903129f4566a73ab19e1f6986d16701de377`:

> When using `must_not`, the clause becomes `true` if none of the conditions listed inside `must_not` is satisfied.
> In this sense, `must_not` is equivalent to the expression `(NOT A) AND (NOT B) AND (NOT C)`.

1. **Evidence exists; not an ANN miss.** Exact dense rank10 equals server dense rank10. Original lexical20 does not contain the proof; historical fusion ranks it24. Other passages receive both dense and lexical contributions while this proof receives only dense support.
2. **Deeper candidates recover it.** Original50/100: lexical rank28, fused rank11. Exact50/100: lexical rank26, fused rank9. Neither family presents it top5. Pool recall1.0 is therefore not final answer precision.
3. **Negation proof itself survives truncation.** This passage has181 tokens before truncation. The max128 prefix reaches source offset3427;110 trailing characters, chiefly JSON example rows, are omitted. All three `must_not` occurrences and the complete Boolean equivalence above are visible. Each `must_not` becomes four model sub-tokens: a dense vector is not literal operator equality.
4. **Markup is a measured budget consumer, not an established causal remedy.** The Hugo code-snippet directive at[3295,3391) consumes39 overlapping tokenizer tokens and remains visible. Its removal was **not** tested. Missing example rows are real, but cannot explain absence of the already-visible negation sentence on their own.
5. **Exact lexical identity cannot translate an implicit French request.** This query contains no literal `must_not`. Preventing identifier conflation does not add the absent French→English operator bridge. Unit tests prove literal preservation, not semantic disambiguation.

Across the corpus, **135/136 passages exceed128 tokens** and omit non-whitespace. All136 have some character tail outside tokenizer offsets; the remaining case is trailing whitespace, not token truncation. The report separates these counts explicitly.

## Per-query gains and losses

The full [PER-QUERY-REVIEW.md](../../artifacts/candidate-recall/9eeb92ce715d47d790c3d2873ccdc317/measured-v2/PER-QUERY-REVIEW.md) contains every exact question, all six ordered top5s, snippets, pinned sources, offsets, hashes, incomplete labels and candidate/final metrics. Full source passages and HTTP rankings are retained in `raw-results.json`; `derived-diagnostics.json` additionally compares every variant to the original **at the same budget**, as well as baseline20.

- `development-07`: deeper original50/100 recovers `qsearch-threshold` into candidates; exact20 already recovers it. No final positive gained.
- `development-10`: deeper50/100 recovers `qfilter-range` in both families. No final positive gained.
- `holdout-09`: deeper50/100 recovers `qfilter-not` in both families. No final positive gained. Original top5 still contains incompatible `qfilter-must`; exact places that wrong operator one position higher, from4 to3.
- `holdout-07`: exact lexical loses `async-shield` from final top5 at every depth, while retaining it in the pool. Recall5 falls1→0 for this question; the replacement remains UNKNOWN, not relabeled false.
- `development-01` and `development-08`: exact lexical demotes selected `wal-network` and `qhybrid-rrf` from rank1 to2, causing the two top1 losses. No opposite top1 gain.
- Deeper original controls gain no selected final-top5 member and lose none. Exact candidate gain on one development query does not offset these final-order regressions. No selected positive is lost from a candidate pool by the exact ablation in this finite run.

## Costs actually measured

Every request independently executes query encoding, HTTP retrieval, lexical retrieval, parent fusion, diagnostics/citations and JSON serialization. Disk exports/hash verification are outside E2E. No shared-stage sums are called E2E. Quality counts use unique questions; stage medians below use48 actual requests per variant/split (16 questions × three blocks).

| Reused holdout | Encode p50 ms | Qdrant HTTP p50 ms | Lexical p50 ms | E2E p50 ms |
|---|---:|---:|---:|---:|
| original_20 |3.129|.721|.152|4.265|
| original_50 |3.091|.752|.162|4.315|
| original_100 |2.996|.809|.162|4.367|
| exact_20 |3.045|.758|.178|4.292|
| exact_50 |3.016|.765|.183|4.250|
| exact_100 |3.197|.826|.187|4.444|

The sum of stage medians is not the E2E median. Single host, tiny index, sequential requests, concurrent runtime-worker contention possible; no SLA, significance or storage-speed verdict. Larger pools would add reranker pair cost, **not measured here**. Document vectors were reused: no new document-encoding latency claimed. Model load/hash validation788.123ms; original+exact lexical build cost is separately retained in `report.json`. Python3.11.16, NumPy2.4.6, ONNX Runtime1.31.0 from the existing immutable-use `.venv`.

## Verification, isolation and reproducibility

Five vertical RED→GREEN slices: exact literal index; candidate-versus-final diagnostics; real experiment; explicit fusion depth; whitespace-versus-token truncation. Missing feature failures and green logs are retained.

- **Final5/5 tests PASS,9.851s**, including the576-request actual server run, ResourceWarning treated as error.
- Targeted retrieval/extraction regression: **30 tests,25 PASS,5 SKIP,12.325s**. Its skipped real candidate test does not replace the integration just executed. No claim of global/doc-intelligence suite acceptance. Existing server test also produced its own unique `artifacts/server-benchmark/8e5247540e864b9abdb0d233e1cc6386/`, cleanup verified.
- Independent `verify.py` imports **no benchmark implementation**. It verifies71 retained file hashes,41 frozen inputs,576 rows,2,880 citations, independent SQLite lexical retrieval/RRF/metrics, all source offsets and literal spans, vector readback, historical query-vector hashes, per-query gains/losses, stable ranks across blocks and exact cosine proof rank.
- **The independent verifier caught a real defect in the first run:** incumbent `tq.fuse` silently capped acquired lists at60/20. That run's declared deeper acquisition was not faithfully fused. It is preserved under `measured/` but **excluded**. New depth regression observed RED, new uncapped standalone fusion implemented, and an entirely fresh `measured-v2/` passed independent reconstruction. No incumbent helper was edited; no mixed results or retroactive freeze repair.
- Final owned server PID4056, loopback49823: only its Popen was terminated/waited; PID absence and port closure independently rechecked. Windows return1 is forced termination, **not graceful shutdown or durability acceptance**. Retained server files are frozen after cleanup.
- First shell `rtk --version`→0.48.0. Existing Beads searched, own task`bk-iv7` tracked; existing GSD CLI returned unreadable/no phases. No initialization/global install. No runtime-worker files touched.
- Only new `tools/candidate_recall_benchmark.py`, `tests/candidate_recall_benchmark_test.py`, this document and unique evidence were authored, plus own Beads task. No incumbent/runtime edits, staging, commit, push, downloads, dependency updates or private/vault ingestion. `.git/index` is a frozen input and remains byte-identical.

Final report SHA256: `990cad2be90b853aaf4aab84006dc83ca91dfe8609bf8ff8e4587e57680e26c0`.

From **`D:/Projets/BorgKnowledge`**, Git Bash:

```bash
# Light tests; the actual integration is opt-in, no downloads.
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B \
  -m unittest discover -s tests -p candidate_recall_benchmark_test.py -v

# Actual integration: MUST use a NEW path, not the retained measured-v2 path.
PYTHONDONTWRITEBYTECODE=1 \
CANDIDATE_REAL_RUN='D:/Projets/BorgKnowledge/artifacts/candidate-recall/NEW-UNIQUE-RUN' \
.venv/Scripts/python.exe -B -W error::ResourceWarning \
  -m unittest discover -s tests -p candidate_recall_benchmark_test.py -v

# CLI equivalent: new UUID directory automatically.
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B tools/candidate_recall_benchmark.py

# Replay final independent verification and explanatory diagnostics, no inference.
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B \
  artifacts/candidate-recall/9eeb92ce715d47d790c3d2873ccdc317/verify.py
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B \
  artifacts/candidate-recall/9eeb92ce715d47d790c3d2873ccdc317/diagnose.py
```

Models, binary and snapshots must already exist at the paths in `freeze.json`; missing/mismatched inputs fail rather than trigger downloads. Retained inputs include the previous ablation snapshots/model receipts and original helper code.

## Next hypothesis, not implemented

**Keep the original lexical representation; test the same pinned reranker on frozen pool20 versus pool50 with paired ungated/source-version-gated controls.** Pool50 now contains the negation proof; the remaining question is whether that existing ranker promotes it instead of `must`/`should`, and at what pair cost. A uniform branch-quota candidate-union control could distinguish RRF suppression from sheer depth. Neither is proof of operator understanding or abstention.

Do not activate the exact lexical replacement on these results. Before concluding about the user's personal agent base, obtain fresh judgments (including implicit negation, exact identifiers, wrong versions and no-answer) and test the actual agent search/get/update/delete path separately. This benchmark supplies candidate diagnosis, not an operational runtime or exhaustive precision estimate.

Editorial review: two substantive rounds—(1) independent reconstruction exposed hidden fusion caps and triggered a fresh run; (2) interpretation review separated cutoff from acquisition, implicit French wording from exact identifiers, trailing whitespace from truncation, and candidate recall from final quality. Remaining lexer/markup, incomplete-judgment and no-abstention limitations are explicit; no visual/UI acceptance claimed.
