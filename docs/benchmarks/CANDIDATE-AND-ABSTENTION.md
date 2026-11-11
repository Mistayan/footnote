# Candidate acquisition, structure and optional abstention

## Executed outcome — do not activate these variants

**640 real requests completed;4/4 new tests PASS in437.349s**, including the actual isolated Qdrant server and both resident pinned models. Measured request workload420.547s, below the predefined600s bound. Baseline pools reproduce32/32 historical questions, and baseline gated rerank5/rerank20 top5s each reproduce32/32. Zero source-version gate violations; all48 execution-input hashes stable.

- **Candidate correction, not operator correctness:** branch reservation recovers the missing `qfilter-not` (`must_not`) proof at pool rank10; the existing reranker still places it11th and presents incompatible `must` first. No query-specific fix, translation or hardcoded operator rule was introduced.
- At budget20, development selected-proof recall5 rises0.7500→0.8333, but reused holdout recall5 **regresses0.9167→0.8333**. P1 stays0.6667. Structural slicing/headings do not repair negation and reduce holdout candidate recall0.9167→0.8333. Exact syntax preservation is unit-tested; it brings no selected-label aggregate gain over quota-OR on these questions.
- The separately frozen development-only abstention rule rejects all4/4 reused-holdout no-answer requests, but also **rejects5/12 answerable questions**. It presents7/16 requests, selected-top1 precision6/7=0.8571, with27 UNKNOWN top5 passages remaining. Not a90% acceptance claim, not probability calibration, not independent validation.

Final measured evidence: [`artifacts/relevance-candidate/6ag-20261019-measured-v1/`](../../artifacts/relevance-candidate/6ag-20261019-measured-v1/). Independent replay and explanatory analysis: [`6ag-20261019-review/`](../../artifacts/relevance-candidate/6ag-20261019-review/). No winner was chosen or production default changed after observing holdout.

## Scope and frozen protocol

Personal knowledge storage and agent workflows, with the user's operational Qdrant goal in approximately 1–2 months. This is an **experimental diagnostic**, not runtime integration, private/vault migration, banking qualification or a ≥90% acceptance claim. No production/default/global configuration changes, installs, staging or commits.

Read before implementation: [retrieval budgets](RETRIEVAL-BUDGETS.md), [candidate recall](CANDIDATE-RECALL.md), existing helpers/reports and [academic retrieval by theme](../research/ACADEMIC-RETRIEVAL-BY-THEME.md), especially deterministic structure, lexical mismatch, mMARCO and selective QA (§1.2, §3.1–3.3, §4.3, §5). These motivate hypotheses, not a promise of local gains. No learned sparse model, late chunking, generated expansion or new checkpoint is claimed.

Five **predefined**, paired candidate families, each reranked at budgets **5 and 20**, two complete timed repetitions:

| Family | Change versus paired control |
|---|---|
| `or_rrf` | Historical MiniLM dense60 + technical-token OR BM25 top20, equal RRF60, pool20 |
| `quota_or` | Same branches; reserve first10 dense and first8 lexical; de-duplicate, fill dense-first to20 |
| `quota_exact` | Same quota, additionally reserve up to2 exact syntactically technical hits **first** |
| `split_quota_exact` | Same quota/lexical/exact; dense retrieval over token-safe body slices, resolve to original parents |
| `heading_quota_exact` | Same slices; append uniformly source-parsed headings only when the whole body plus suffix still fits |

Every family uses the existing explicit Python source-version gate **after its pool20, before budget/reranking and independently at presentation**. No refill from outside the pool. Explicit requested Python family rejects other known families and unknown metadata; other questions are NOT_ASSESSED, not certified compatible. This is a narrow gate, not a general applicability oracle. All citations/reranking use the original frozen parent text and original hashes/offsets; headings and children are routing representations, never synthetic evidence.

The exact branch hex-encodes whole casefolded identifiers (`must_not`, dotted names/versions) and longest-first symbolic operators, avoiding FTS5 underscore/operator conflation. It activates only for syntactically technical query atoms, not natural-language words. No French→English translation, operator dictionary, literal `must_not` condition or query-ID special case. `quota_or` isolates branch-reservation effects from exact matching. This deliberately differs from replacing all OR words with an exact index, a previously failed hypothesis.

Structure is applied to **all** frozen parents using only their source text and source offsets. Markdown ATX, RST/setext underlines and YAML titles are heuristic parsers; they are not full markup-language validators. Body slicing uses the same model tokenizer and remains below the128-token budget. A context suffix consumes only spare capacity; no prefix can displace the proof. The body-only split control separates segmentation from heading effects. No relevance/judgment fields are available to the builder; a poisoning test verifies output invariance. Max-child ranking, parent de-duplication and top60 **points**, not60 distinct parents, are explicit; this may reduce parent acquisition and is reported, not silently refilled.

Corpus:136 unchanged passages from ten pinned public sources;32 unchanged questions,12 selected-answerable and4 selected-no-answer in each historical partition. Both partitions are **REUSED DIAGNOSTIC**. Author-made selected labels are incomplete, not independent judgments. UNKNOWN stays UNKNOWN. No new unseen question or label was added after seeing results.

Same verified MiniLM384D ONNX max128 empty prefixes masked mean/L2 and same pinned mMARCO multilingual cross-encoder ONNX max512 longest-first batch4, CPU intra/inter2/1. Existing `.venv` used read/execute only with `-B`; no new dependency. Isolated actual Qdrant1.19.2 process, random loopback port, unique storage, three explicit cosine collections, HNSW M16/ef_construct100/ef128, collection green/indexed count and vector/payload readback. On this tiny corpus a planner scan is possible; no universal HNSW-path claim.

### Optional development-only abstention

Prespecified pipeline: **`quota_exact_20`**, regardless of which variant later scores best. Fit one maximum-reranker-logit threshold on block0 development answerability, maximizing balanced answerable-accept/no-answer-reject accuracy, higher threshold on ties. Freeze it **after the variant definition and before the first reused holdout request**. Do not fit other variants or choose by holdout. Apply as a separately named experimental output, never overwrite base ranks. This is an answerability decision rule, **not probability calibration**, exhaustive semantic precision or a production confidence score. UNKNOWN passages do not become negative training labels. Report selected-label top1 precision among accepted, coverage, answerable rejection, no-answer false acceptance and remaining incompatible/UNKNOWN evidence.

## Paired quality and costs actually measured

Pk = selected-positive hits in firstk / k, fixed denominator even if fewer results. Macro averages below use12 unique answerable questions per partition. MRR5 is reciprocal first-positive rank at cutoff5, **not truth percentage**. Pool recall counts selected proofs anywhere in pool20 **before the gate/budget**; rerank-candidate recall is separately saved after gate/budget. Incompatibility and UNKNOWN counts below include all16 unique questions × five slots. No-answer false acceptance is **4/4 for every uncalibrated variant in each partition**; nonempty retrieval is not a generated answer. Timing p50/p95 uses32 fully executed requests per variant/partition, not independent quality samples.

### Historical holdout, reused diagnostic

| Variant | P1 / P3 / P5 | MRR5 / R5 | Pool recall | Incompatible / UNKNOWN | E2E p50 / p95 ms |
|---|---|---|---:|---:|---:|
| or_rrf_5 | 0.6667 / 0.2500 / 0.1500 | 0.6667 / 0.6667 | 0.9167 | 1 / 70 | 258.3 / 436.6 |
| or_rrf_20 | 0.6667 / 0.3056 / 0.2167 | 0.7500 / 0.9167 | 0.9167 | 2 / 65 | 941.0 / 1470.9 |
| quota_or_5 | 0.6667 / 0.2778 / 0.1667 | 0.7083 / 0.7083 | 0.9167 | 0 / 70 | 249.9 / 452.3 |
| quota_or_20 | 0.6667 / 0.3056 / 0.2000 | 0.7361 / 0.8333 | 0.9167 | 1 / 67 | 950.1 / 1466.5 |
| quota_exact_5 | 0.6667 / 0.2778 / 0.1667 | 0.7083 / 0.7083 | 0.9167 | 0 / 70 | 261.6 / 407.5 |
| quota_exact_20 | 0.6667 / 0.3056 / 0.2000 | 0.7361 / 0.8333 | 0.9167 | 1 / 67 | 976.4 / 1447.3 |
| split_quota_exact_5 | 0.6667 / 0.2778 / 0.1667 | 0.7083 / 0.7083 | 0.8333 | 0 / 70 | 243.5 / 437.7 |
| split_quota_exact_20 | 0.6667 / 0.3056 / 0.2000 | 0.7361 / 0.8333 | 0.8333 | 1 / 67 | 932.6 / 1640.7 |
| heading_quota_exact_5 | 0.6667 / 0.2778 / 0.1667 | 0.7083 / 0.7083 | 0.8333 | 0 / 70 | 292.2 / 447.0 |
| heading_quota_exact_20 | 0.6667 / 0.3056 / 0.2000 | 0.7361 / 0.8333 | 0.8333 | 1 / 67 | 952.7 / 1420.9 |

### Historical development, reused diagnostic

| Variant | P1 / P3 / P5 | MRR5 / R5 | Pool recall | Incompatible / UNKNOWN | E2E p50 / p95 ms |
|---|---|---|---:|---:|---:|
| or_rrf_5 | 0.6667 / 0.2500 / 0.1667 | 0.6875 / 0.7500 | 0.8333 | 1 / 69 | 249.1 / 446.1 |
| or_rrf_20 | 0.6667 / 0.2778 / 0.1667 | 0.7083 / 0.7500 | 0.8333 | 1 / 69 | 1041.8 / 1471.9 |
| quota_or_5 | 0.5833 / 0.2222 / 0.1333 | 0.5833 / 0.5833 | 1.0000 | 0 / 72 | 295.9 / 485.1 |
| quota_or_20 | 0.6667 / 0.3056 / 0.1833 | 0.7500 / 0.8333 | 1.0000 | 1 / 68 | 1067.3 / 1539.1 |
| quota_exact_5 | 0.5833 / 0.2222 / 0.1333 | 0.5833 / 0.5833 | 1.0000 | 0 / 72 | 290.0 / 475.5 |
| quota_exact_20 | 0.6667 / 0.3056 / 0.1833 | 0.7500 / 0.8333 | 1.0000 | 1 / 68 | 1093.4 / 1509.8 |
| split_quota_exact_5 | 0.5833 / 0.2222 / 0.1333 | 0.5833 / 0.5833 | 0.9167 | 0 / 72 | 294.2 / 454.8 |
| split_quota_exact_20 | 0.6667 / 0.3056 / 0.1833 | 0.7500 / 0.8333 | 0.9167 | 0 / 69 | 1079.4 / 1631.1 |
| heading_quota_exact_5 | 0.5000 / 0.2222 / 0.1333 | 0.5417 / 0.5833 | 1.0000 | 0 / 72 | 296.4 / 485.5 |
| heading_quota_exact_20 | 0.6667 / 0.3056 / 0.1833 | 0.7500 / 0.8333 | 1.0000 | 1 / 68 | 1083.1 / 1419.3 |

Exact branch produced hits on9/32 queries and changed7/32 pools versus quota-OR, but no selected-label aggregate improvement. This is **not** proof that exact identifiers never help; the diagnostic lacks fresh operator-literal questions. No new questions were retroactively authored to create a success.

### Negation proof: evidence present, candidate loss corrected, ranking still wrong

Frozen question `holdout-09`: **« Quel opérateur Qdrant exclut tous les points satisfaisant une condition interdite ? »** Frozen relevant ID **`qfilter-not`**, not the mistaken historical prose ID `qfilter-must_not`.

Pinned original Qdrant filtering source, offsets[3063,3537), SHA256 `8c089272b4bd06cc552b021e79b1903129f4566a73ab19e1f6986d16701de377`:

> When using `must_not`, the clause becomes `true` if none of the conditions listed inside `must_not` is satisfied.
> In this sense, `must_not` is equivalent to the expression `(NOT A) AND (NOT B) AND (NOT C)`.

- Raw passage has181 model tokens. The max128 representation sees364 source-relative characters: **all three literal `must_not` spans and the complete Boolean equivalence survive**. Each operator decomposes into `mus`, `t`, `_`, `not`; literal equality is not a dense-vector operation. The110-character omitted tail contains chiefly JSON rows, not the negation sentence. Full subtoken/offset/raw-text diagnostics cover **every parent**, not just this positive.
- Historical dense rank10, OR20 omits the proof, and RRF pool20 omits it. Both quota controls acquire it at pool rank10 without a term-specific rule. Budget5 still excludes it; budget20 actually reranks it.
- With the exact same reranker checkpoint and original parent evidence, it finishes **rank11**, logit−3.74054. Incompatible `qfilter-must` finishes first, logit0.21167 in this quota batch. Literal-preserving lexical matching cannot bridge the absent operator in an implicit French query, and branch reservation alone cannot repair model ranking. Raw logits are neither probabilities nor comparable calibration guarantees across changed pools/batching.
- Body-split and heading variants lose the proof from pool20 again. Larger point counts and source headings are not sufficient evidence of better retrieval. No post-holdout variant was introduced to hide this failure.

### Concrete gains and losses, without changing labels

- `development-07`: quota20 newly presents selected `qsearch-threshold`; candidate pool had previously omitted it. This explains development R5 gain. Quota also recovers `qfilter-range` into the development-10 pool but does not present it at20.
- `holdout-00`: quotas lose selected `wal-writer` **from the candidate pool**, whereas OR20 presents it. Recovering negation in a different query therefore does not improve overall holdout candidate recall; final R5 regresses.
- `holdout-02`: quota5 retrieves selected `py311-backup` where OR5 had no selected positive; additional budget still matters for the other selected proof.
- `development-00` and `development-06`: quota5 loses selected `wal-checkpoint` and `qfilter-must` from presentation, respectively. Heading5 additionally loses `py312-thread` on development-09, while gaining `qfilter-range` on development-10. All such changes are retained, not summarized as a one-sided win.
- 391 lossless body children were created; only84 can append any heading without displacing body tokens. The heuristic parser finds no supported heading in the four SQLite HTML-derived sources. This is **not** complete HTML/layout extraction or lossless markup parsing. All391 encoded child texts independently fit below128 tokens; source-body reconstruction and heading offsets replay exactly. Parent citations remain unchanged.

### Optional abstention: explicit precision–coverage trade-off

Frozen threshold **2.3823580741882324**, chosen from16 development questions only for the prespecified quota_exact20 pipeline. This objective separates answerability labels, **not exhaustive evidence correctness**. Its observed development performance is training performance; reused holdout is diagnostic, not independent validation.

| Partition | Accepted / all | Coverage | Selected top1 hits / accepted | Answerable rejected /12 | No-answer false accepted /4 | Incompatible / UNKNOWN top5 |
|---|---:|---:|---:|---:|---:|---:|
| development |10/16|0.6250|8/10 =0.8000|2/12|0/4|1 /39|
| reused holdout |7/16|0.4375|6/7 =0.8571|5/12|0/4|0 /27|

Rejected answerable holdout IDs: `holdout-00`, `holdout-02`, `holdout-03`, `holdout-07`, `holdout-09`. Refusing the unresolved negation is preferable to presenting its known wrong operator but **does not correct it**, and losing shield/backup/writer questions is a substantial coverage cost. Accepted `holdout-08` still has UNKNOWN top1. The development rule also retains one explicitly incompatible top5 passage. Zero false accepts on only four no-answer examples does not establish reliable abstention or a precision threshold. No UNKNOWN was relabeled negative or made compatible to improve these counts.

### Measurement limitations

Offline structural encoding9,129.912ms; combined model hash validation/load1,428.457ms, outside E2E. The original passage vectors are reused byte-for-byte; query vectors equal historical vectors on every timed request. Encoder truncation counters are0 for newly encoded children/queries; this does **not** erase historical parent truncation. Reranker reaches512 tokens on290 pairs including warm-up; full original-parent reading is not guaranteed. Actual two-repeat block medians, stage medians and **paired** request-cost deltas are in `derived-diagnostics.json`; the sum of stage medians is not E2E. Small host/corpus/repeat count and possible worker contention preclude an SLA or statistical speed conclusion.

## Evidence and replay

Every run retains the protocol freeze and input hashes, code copies, model receipts/recipes, vectors, server readback, raw HTTP responses, all measured requests and source citations, candidate errors, full-parent embedding visibility and per-query review. All questions show P1/P3/P5, MRR5, selected-proof R5, candidate recall and loss stage. Timing repetitions are not extra relevance samples.

E2E is independently measured for every request from fresh query encoding through lexical, HTTP, gates, reranking, citation hydration and JSON serialization. Offline indexing/child encoding/model hash validation/load and evidence-file I/O are excluded and labeled separately. Two repeats reverse query/variant order in repeat1; development precedes holdout for the threshold freeze.600s measurement deadline, checked per request; no timing-significance or SLA claim, and unrelated runtime-worker contention remains possible.

From `D:/Projets/BorgKnowledge` in Git Bash:

```bash
# Fast tests (real integration skips unless explicitly enabled).
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B \
  -m unittest discover -s tests -p relevance_candidate_experiment_test.py -v

# Actual complete acceptance; ALWAYS choose a NEW unique run directory.
PYTHONDONTWRITEBYTECODE=1 \
RELEVANCE_CANDIDATE_RUN='D:/Projets/BorgKnowledge/artifacts/relevance-candidate/NEW-UNIQUE-RUN' \
.venv/Scripts/python.exe -B -W error::ResourceWarning \
  -m unittest discover -s tests -p relevance_candidate_experiment_test.py -v

# CLI equivalent, new UUID directory automatically; no downloads.
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B tools/relevance_candidate_experiment.py
```

Missing or mismatched pinned snapshots, checkpoints or binary fail rather than download or mutate the shared environment. The executable artifact is intentionally separate from production search/get and source lifecycle operations.

### Acceptance receipts

- First shell `rtk --version` returned0.48.0. Four vertical RED→GREEN slices were observed: missing exact branch; missing uniform source structure; missing development-only threshold; missing real experiment. An exact-operator test's equal-BM25 tie expectation was corrected to deterministic ID order before continuing. No claim that tests alone establish retrieval correctness.
- Actual integration **4/4 PASS,437.349s**, `ResourceWarning` errors enabled; all640 requests and3,200 citations checked, no integration skip in that run. Follow-up incumbent retrieval regression **14 tests:10 PASS,4 opt-in SKIP,0.143s**; skipped historical integrations are not claimed as rerun. Fast new tests also pass with the real integration explicitly skipped when its environment variable is absent. No whole-repository test-suite claim.
- Independent `verify.py` imports no benchmark implementation. It replays **150 retained file hashes,48 input hashes,640 raw HTTP/result rows,3,200 citations**, independent SQLite OR/exact queries, branch fusion/reservation, gate selection, logits→ranks, Pk/MRR/R5, aggregate/timing/abstention arithmetic, development-only threshold fitting, all child token budgets and source offsets. `verification.json` records the passing replay. It checks stable ranks across repeats and original vector/payload readback; no new inference or checkpoint download.
- Server PID18516, loopback51624: owned Popen terminate/wait only; PID absence and port closure rechecked. Return1 is Windows forced termination, **not graceful shutdown/durability acceptance**. No runtime-worker endpoint or process was stopped.
- Existing environment Python3.11.16, NumPy2.4.6, ONNX Runtime1.31.0, tokenizers0.22.2, psutil7.2.2. No install or dependency mutation; model recipes and checkpoint hashes are in the measured freeze/report. Git index and all48 frozen inputs are byte-stable. No helper/runtime file was edited, no staging/commit/push, no vault/private content read. Repository-authored deliverables are only the three named new paths and two unique artifact directories; own Beads task`bk-6ag` remains **in_progress** for parent verification/closure.

Primary evidence under `6ag-20261019-measured-v1/`:

| File | Purpose |
|---|---|
| [`PER-QUERY-REVIEW.md`](../../artifacts/relevance-candidate/6ag-20261019-measured-v1/PER-QUERY-REVIEW.md) | Every question, ten ordered top5s, source snippets, P1/P3/P5/MRR/R5, loss stages, timing repeats, optional abstention |
| `raw-results.json`, `raw-results.jsonl`, `raw-server.jsonl` | All640 real requests, raw candidates/logits, gates, HTTP rankings and full evidence |
| `candidate-errors-and-proofs.json` | All candidate non-selected statuses (UNKNOWN is not false), text/logits, expected proof ranks and raw/token visibility |
| `embedding-visibility.json`, `structural-children.json` | Every parent token omission and every source-derived child/body/context/offset |
| `freeze.json`, `calibration-freeze.json` | Pre-inference variant definition and later development-only threshold freeze |
| `experimental-abstention.json` | Separately labeled optional outputs; base measured ranks unchanged |
| `report.json`, `*-vectors.npy`, `*-readback.json`, `cleanup.json`, `evidence-sha256.json` | Actual metrics, recipes, verified vectors/collections, owned-server cleanup and retained-file manifest |

Post-run analysis under `6ag-20261019-review/`: `verify.py`, `verification.json`, `diagnose.py`, `derived-diagnostics.json`. These are explanatory/replay artifacts, not additional selected hypotheses. Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B \
  artifacts/relevance-candidate/6ag-20261019-review/verify.py
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -B \
  artifacts/relevance-candidate/6ag-20261019-review/diagnose.py
```

Final measured report SHA256: `0b8a263dedca342c6b481270535210a830f4480c4121cb3fde14c6a8200cf788`.
Variant freeze SHA256: `2355bfba7d68bcc8b3bfba663efb2b732588e54e3eff35d4fcbab12f8145d12c`.
Calibration freeze SHA256: `b90f841bc92ea686ea0aea5bf203770a6ed01e9aa1258526ebcc5ece562827b3`.

**Decision:** retain these as failed/partial hypotheses, not a backend change or activated replacement. Candidate acquisition can be corrected independently of operator ranking; the personal runtime still requires its own search/get/update/delete verification and fresh independently judged relevance/no-answer examples. The latter remain blockers to an acceptance claim, not reasons to turn the1–2-month personal project into enterprise qualification.
