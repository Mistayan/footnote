# Pivot-language lexical retrieval — executed bounded next attempt

**Status: OPEN for parent verification. No runtime activation.** The first milestone remains **≥80% applicable multilingual top1**, then **≥90%**; answerable coverage floor remains80%. Neither is established. Actual local translation and **180 real isolated Qdrant requests** completed. The new source-family holdout is **7/10 selected-positive top1 (70%) in every variant**, not a successful80% aggregate. French alone is4/5, but that small stratum is not the multilingual milestone.

## Outcome and concrete blockers

- A qualified local French→English translator **works within the download limit**. No external inference API, private documents, hardcoded translations or operator dictionary was used.
- Pivot lexical routing improves acquisition on reused diagnostics, but **does not improve fresh Go top1**. Every fresh selected proof is already in pool20 in all variants; the three selected-top1 misses are ranking/judgment issues, not absent candidates.
- Existing no-answer behavior is unsafe: **14/14 no-answer queries return evidence in each variant**, including both fresh no-answer questions. No abstention, reject-all trick, generated answers or calibrated answerability acceptance was evaluated. No operational no-answer false-acceptance limit was calibrated/frozen, so this is a relevance experiment, not an acceptance protocol for safe answer provision.
- Two fresh selected-label misses return potentially useful unjudged alternatives. Do **not** relabel those after seeing results to turn70% into90%. Exhaustive pooled judgments by independent reviewers remain a concrete acceptance blocker.
- The known implicit Qdrant exclusion query remains wrong: actual translation preserves the exclusion meaning without inventing `must_not`; fusion admits the selected proof, but the original-query incumbent ranker puts it**13th** and presents explicitly incompatible `must` first.

## Research and checkpoint qualification

The pinned **Helsinki-NLP/opus-mt-fr-en** card declares **Apache-2.0**, source French, target English, transformer-align and normalization/SentencePiece preprocessing. This is the exact checkpoint's upstream license declaration, not an invented conversion license or legal opinion. Original safetensors are used locally; no conversion/redistribution.[1]

| Item | Frozen value |
|---|---|
| Repository revision | `c4aed37b318c763fd177aa449b44e3b783cc6c02` |
| Checkpoint | `model.safetensors`,300803608 bytes |
| Checkpoint SHA256 | `6e3837f34b903802c3d0d670362b997cee6e87584a1108eb3fa89e4625e4424a` |
| Complete selected model payload | **303726567 bytes**, below800000000-byte bound |
| Dependencies | Separate project-local Python3.11 environment; torch2.6.0+cpu, transformers4.49.0, sentencepiece0.2.0, sacremoses0.1.1; full lock retained |
| Generation | CPU, intra/inter2/1 threads; greedy beam1, no sampling; natural-span input≤256 tokens without truncation; output≤96 new tokens; overflow fails closed |
| Network during inference | `local_files_only=True`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` in child only |

`model-receipt.json` retains all eight filenames, pinned URLs, bytes, SHA256 and download durations. The safetensors hash matches pinned HF LFS metadata; every model file is checked before initialization. Model bytes stay under the unique project artifact directory. Package installation targeted only the separate environment, not `.venv`, global Python or shared runtime packages; uv's normal package cache may be used by installation. Dependency-download bytes are not included in the checkpoint-payload total. No credential/gated model was required.

**Mechanism and transfer limits:** CLIRudit (Francisco Valentini, Diego Kozlowski, Vincent Larivière; arXiv2504.16264v1, preprint) reports mistranslated proper nouns losing recall and generally stronger document translation than query translation for sparse retrieval. Full HTML fetched; discussion inspected, not a paper reproduction or a claim that its numerical results transfer to code documentation.[2] MuSeCLIR (Wing Yan Li, Julie Weeds, David Weir; **COLING2022**, official abstract/metadata read, not full PDF newly read) emphasizes translation ambiguity and the weakness of benchmarks dominated by easy named-entity mentions.[4] Hence the new test includes implicit reader/writer blocking, panic/retry, all-versus-one wakeup, thread ownership and absent-version questions rather than only matching explicit method names. No paper metric is converted into local P1.

Fetch receipts preserve direct public HTTPS responses and failures. `web_extract` was unavailable with its search-only backend; urllib fetches succeeded for the model card, ACL metadata, arXiv HTML and Go sources/license. ACM returned403; its search snippet is not treated as a read paper. An additional discovered proper-name paper PDF is retained but not used for claims. A task-local citation ledger has literal supporting quotes.

## Immutable query transformation

`tools/pivot_language_experiment.py` protects generic **backtick code, dotted/underscored identifiers, numeric/version spans, uppercase abbreviations and symbolic comparison/Boolean operators** with ordered placeholders. This is an explicit syntax grammar, not a complete code-language parser; unquoted title/camel-case words without matching syntax are not universally protected.

Only natural-language fragments between placeholders enter the actual Marian checkpoint. Placeholder strings themselves never enter generation. Exact ordered roundtrip rejects missing, repeated, reordered or foreign placeholders and reserved-token intrusion; rejected translation falls back to the complete original query. Span boundaries preserve their original bytes. Fragmenting can lose cross-span grammatical context and cannot certify that natural-language negation/intent was translated correctly. There is no domain/operator dictionary, query-ID lookup, relevance-label input, manual translation substitution or automatic answer expansion.

The **original complete query** remains the dense input, reranker input and applicability-gate input in all variants. Translation affects only derived lexical routing. Original source bytes, normalized text, full parent bodies, hashes, offsets and citation URLs are never translated or rewritten. Explicit English/non-French language labels use the identity transform; this is not an automatic language-detector benchmark.

Actual example, not a fabricated translation:

> Quel opérateur Qdrant exclut tous les points satisfaisant une condition interdite ?
>
> Which Qdrant operator excludes all points satisfying a prohibited condition?

All**46 French query-translation requests succeeded**, without failclosed fallback. Actual natural fragments and outputs are retained for every translated request. This does not establish46 independent linguistic correctness judgments.

## Dataset freeze before inference

Three separate datasets are retained; they are never pooled into a favorable single acceptance number:

1. **Reused Git development / Rust diagnostic:**63 passages,16 questions. All previously observed; development selection uses only the six answerable Git questions. Rust is diagnostic, not a new holdout.
2. **Old public diagnostic:**136 passages,32 previously observed questions. No fresh/generalization claim.
3. **NEW Go source-family holdout:**35 uniformly generated1400-character windows at1100-character stride from six official `sync` source files (`mutex`, `rwmutex`, `once`, `waitgroup`, `pool`, `cond`). Tag `go1.23.2` resolves to immutable commit **`ed07b321aef7632f956ce991dd10fdd7e1abd827`**. Exact URLs/raw bytes/normalized text hashes/offsets retained. Source snapshot and uniform windows precede authored questions. Ten answerable questions, five French/five English, plus two no-answer questions; selected proof quotes/labels freeze before any translation or embedding inference. For example, the upstream Once source explicitly distinguishes a panic from a retryable initialization.[3]

Annotations are by the **implementing agent**, not independent humans. Go is source-family disjoint from Git development; underlying concurrency concepts are not guaranteed independent of prior Rust diagnostics. Selected labels cover all windows containing the selected literal quote, **not every semantically answering passage**. UNKNOWN remains UNKNOWN. No-answer cases are an absent private-production latency measurement (no actual private input) and unsupported Go9.99 `WaitGroup.Go` guarantees. English-version applicability does not become validated merely because a source was pinned.

Preparation scripts and the fresh-Go freeze live in [`pivot-20261019-a`](../../artifacts/pivot-language/pivot-20261019-a/). No holdout labels, anchors, segmentation, weights or model recipes were modified after inference.

## Frozen finite variants and timing contract

| Component | All variants |
|---|---|
| Dense | Existing verified MiniLM, manifest parent128, original query,384D; dense60 actual server results |
| Lexical | Existing FTS5 OR BM25; original and pivot raw lists retained |
| Baseline | Original lexical20, weight1 |
| Pivot | Pivot lexical20, weight1 |
| Fusion | Original lexical10 + pivot lexical10, weight0.5 each; duplicate slots consume their budget, no refill |
| Pool/ranker | Dense weight1; RRF60 deterministic ID ties; pool20; existing source-version gate; same incumbent mMARCO on at most20 original-query/original-parent pairs; longest-first512 CPU2/1, batch4 |
| Presentation | Existing gate independently reapplied; original top5 parents, no refill |
| Abstention | None; scores are ranking logits/RRF, not calibrated confidence |
| Choice | Highest reused-development P1, then MRR, exact ties baseline→pivot→fusion; freeze before fresh Go query inference |

The unchanged lexical helper **materializes up to20 results for each of two SQL calls per request**, even baseline where the queries are identical. Thus retained raw lexical lists can contain40 entries per request in every branch; **admitted lexical slots are capped20** as above. No additional lexical entries contribute to RRF/pool20. This is a constant admitted-candidate and reranker budget, not a claim that only20 raw SQL rows were fetched or every pool has20 unique relevant candidates.

Development selects **baseline**:6/6, pivot6/6 (MRR tie), fusion5/6. Choice is timestamped before fresh Go inference; all three results remain reported. This baseline is the matched **MiniLM+OR** control, not the earlier larger MiniLM/E5/exact-reservation union; differences versus earlier reports are not attributed to translation alone. No reranker or weight sweep, no tuning after holdout, exactly baseline plus two experimental variants.

Each of180 requests independently performs translation if applicable, original dense encoding, new loopback HTTP query, lexical acquisition, gates, resident rerank, original citation hydration and JSON serialization. Translation is not cached across pivot/fusion requests. E2E includes translation/RPC and explicit HTTP connection renewal; cold load and offline passage encoding/indexing are reported separately. No reused stage sums are called independently measured E2E. One sequential repetition: no latency significance/SLA claim.

## Actual paired scores

P@k=selected-positive hits divided by fixedk (missing slots zero); MRR5=reciprocal first selected-positive rank at cutoff5; recall5/candidate recall use selected positives. P5 is limited by the number of selected labels and is **not exhaustive semantic precision**. Answerable queries only for these relevance means; no-answer behavior is separately counted below.

| Dataset / partition | Variant | Correct top1 / answerable | P1 | P3 / P5 | MRR5 / Recall5 | Pool recall | E2E p50/p95 ms |
|---|---|---:|---:|---|---|---:|---|
| Reused Git development | baseline |6/6|1.0000|.3889 / .2333|1.0000 /1.0000|1.0000|1128.5 /1245.4|
| Reused Git development | pivot |6/6|1.0000|.3889 / .2333|1.0000 /1.0000|1.0000|1135.5 /1317.9|
| Reused Git development | fusion |5/6|.8333|.3889 / .2333|.9167 /1.0000|1.0000|1168.1 /1311.5|
| **NEW Go holdout** | **baseline** |**7/10**|**.7000**|.3000 / .2000|.7750 / .8500|1.0000|1299.3 /1358.7|
| NEW Go holdout | pivot |7/10|.7000|.3000 / .2200|.8000 / .9500|1.0000|1399.9 /1526.1|
| NEW Go holdout | fusion |7/10|.7000|.3000 / .2000|.7750 / .8500|1.0000|1382.2 /1526.1|
| Reused Rust diagnostic | baseline |3/6|.5000|.2778 / .1667|.6389 / .7500|.8333|1153.1 /1249.9|
| Reused Rust diagnostic | pivot |4/6|.6667|.2778 / .2000|.7917 / .9167|1.0000|1197.7 /1296.6|
| Reused Rust diagnostic | fusion |4/6|.6667|.2778 / .2000|.7917 / .9167|1.0000|1175.9 /1336.1|
| Old development diagnostic | baseline |8/12|.6667|.2778 / .1667|.7083 / .7500|.8333|862.0 /1059.5|
| Old development diagnostic | pivot |8/12|.6667|.3056 / .1833|.7500 / .8333|1.0000|870.1 /1166.1|
| Old development diagnostic | fusion |8/12|.6667|.3056 / .1833|.7500 / .8333|1.0000|892.1 /1082.0|
| Old holdout diagnostic | baseline |8/12|.6667|.3056 / .2167|.7500 / .9167|.9167|737.4 /1160.5|
| Old holdout diagnostic | pivot |8/12|.6667|.3333 / .2167|.7778 / .9167|.9167|794.2 /1184.0|
| Old holdout diagnostic | fusion |8/12|.6667|.2778 / .2000|.7361 / .8333|.9167|783.8 /1181.7|

### Fresh language strata (not independent certification)

| Language / variant | Selected top1 | MRR5 | Recall5 | Candidate recall | E2E p50/p95 ms |
|---|---:|---:|---:|---:|---|
| French / baseline |4/5|.8000|.8000|1.0000|1299.3 /1323.6|
| French / pivot |4/5|.8500|1.0000|1.0000|1468.9 /1526.1|
| French / fusion |4/5|.8000|.8000|1.0000|1483.7 /1526.1|
| English / baseline |3/5|.7500|.9000|1.0000|1303.4 /1358.7|
| English / pivot |3/5|.7500|.9000|1.0000|1313.4 /1365.7|
| English / fusion |3/5|.7500|.9000|1.0000|1307.6 /1340.7|

All language strata, including reused French and historical English-or-mixed categories, are in `report.json`; historical non-French queries are not silently certified exclusively English. For7/10, a descriptive Wilson95% interval is **[.3968,.8922]**. These authored related questions are not random independent samples; the interval is illustrative, not a generalization guarantee.

### Paired successes, failures and applicability

- **Fresh:**zero top1 gains, zero regressions for either translation variant. Pivot improves selected recall5 .85→.95 and MRR .775→.800 without top1 improvement.
- **Reused Rust:**one top1 gain (`fresh-holdout-06`, implicit mutable borrowing); no loss. Baseline misses its proof in pool20; translation variants acquire it. This is actual diagnostic acquisition success, not new-family generalization.
- **Reused Git:**fusion loses `fresh-development-04` (previewing clean without deletion); pivot does not. Splitting lexical budget/mass can regress even when original dense input is retained.
- **Old32:**zero top1 gains and zero losses in both variants. Acquisition improvements do not establish improved evidence presentation.
- **Implicit Qdrant exclusion:**pivot natural text is correct-looking, but its selected proof remains outside pool20; fusion acquires `qfilter-not`, incumbent rank13. All present incompatible `qfilter-must` first. A translation-only routing intervention does not solve operator semantics.
- **Go selected misses:**`go-holdout-01` selected writer-precedence proof rank4 with pivot (all proofs admitted); top1 includes “a blocked Lock call excludes new readers” and a pending-writer comment, so this is not proven a semantically wrong answer. `go-holdout-07` selected Mutex proof rank2 (and another rank8); top1 RWMutex passage explicitly says “As with Mutexes … not associated with a particular goroutine”, potentially useful. `go-holdout-08` requested all-waiter method has selected Broadcast proof rank4, while top1 only explicitly defines single-waiter Signal and mentions Broadcast in another context. Frozen selected labels stay unchanged; full excerpts permit independent adjudication.
- Full untruncated pair counts:3505 reranker pairs,144 exceed512 and3 equal512. The three fresh missed selected proofs have436/455/468/465 tokens, **below512**. Their failures are not explained by truncation of those proofs.
- Coverage**100%** in every dataset/variant; abstentions**0**. Fresh all-question selected-correct/attempted is**7/12**, distinct from answerable7/10. No-answer retrieval false accepts: Git2/2, Rust2/2, old development4/4, old holdout4/4, Go2/2, **14/14 per variant**. No generated-answer correctness was tested.
- Explicit incompatible top1/top5 counts: old holdout**1/2** and old development**0/1**, unchanged for all variants; fresh/reused explicit incompatible lists are empty, so zero does not demonstrate compatibility. Go version requests are **NOT_ASSESSED** by the existing Python-only version gate; the Go9.99 no-answer request still returns passages. Source snapshot version and runtime compatibility are not interchangeable.
- Fresh UNKNOWN top5 occurrences baseline/pivot/fusion**50/49/50** across12 queries. UNKNOWN is not irrelevant; the incomplete judgments block a trustworthy semantic80%/90% claim.

## Execution receipts and verification

Primary run: [`run-20261019-a1`](../../artifacts/pivot-language/run-20261019-a1/). Full original excerpts, questions, labels, ordered top5, candidate pools, fusion contributions, ranker logits, translations, source URLs/offsets/SHA256, latency and per-query CPU appear in [`PER-QUERY-REVIEW.md`](../../artifacts/pivot-language/run-20261019-a1/PER-QUERY-REVIEW.md) and `raw-results.json[l]`. No shortened-only excerpt substitute.

- **4/4 focused tests PASS in196.581s**, including the actual complete experiment/replay; test receipt `pivot-20261019-a/experiment-a1.log`. Vertical RED failures were observed for missing span functions/module, translation slice, bounded fusion and full experiment before implementation. Fast execution without opt-in explicitly skips real integration. No whole-repository suite is claimed.
- **Independent stdlib audit PASS:**180 requests,60 questions,900 full evidence records,234 source passages. It imports neither benchmark nor incumbent helpers; verifies manifests/source offsets/raw hashes, raw HTTP dense ordering, fixed admitted budgets/RRF/pool/logit ordering, per-query metrics, aggregate arithmetic/latencies, source readback identities, development choice before holdout and unchanged query vectors. Harness replay additionally verifies live lexical ranks, numeric vector readback and source gates. Independent audit reuses recorded gate states, so it is not an independent applicability implementation.
- Measured request workload**185.156s**; cold process/model load plus hash validation**4972.792ms**; offline passage encoding/indexing**2930.873ms**. Translator internal load724.641ms is part of cold load, not an additional request cost.
- French translation/RPC component p50/p95**122.412/170.346ms** over46 actual French requests; worker-internal process CPU totals**8.671875s**. No warm-cache translation substitution. Per-request CPU adds harness `process_time` and worker-reported inference-process CPU; Qdrant CPU is separately sampled.
- CPU-only Windows host reports24 logical/physical CPUs,51132588032 RAM bytes. Resource sampler: harness453.765625 CPU seconds and1235025920-byte sampled peak RSS; Qdrant .1875 CPU seconds and45199360-byte sampled peak RSS. Sampling interval10ms; not guaranteed true process peaks. **The retained `translator_end_rss_bytes=5152768` is the Windows virtualenv launcher's RSS, not torch model/child memory; no translator peak-memory claim is made.** Internal worker CPU is measured inside the actual inference process, so it is not launcher CPU.
- Owned Qdrant1.19.2 uses unique storage/snapshot/temp paths, ephemeral loopback port54525, gRPC/clustering/telemetry disabled, sanitized `QDRANT_*` environment, green/indexed-vector checks and full payload/vector readback. PID19856 exited, port closed; Windows terminate/wait return1 is forced termination, **not graceful-shutdown/durability acceptance**. Translator launcher PID15456 exits0. Independent post-run inspection finds both PIDs absent, owned port closed and no remaining `pivot_language_experiment.py --worker` processes.
- Frozen input hashes, existing helper/runtime/model bytes and `.git/index` remain unchanged. First shell `rtk --version` returned0.48.0. No vault ingress, global configuration/runtime changes, staging, commit or existing source/helper edits. New owned project files only: `tools/pivot_language_experiment.py`, `tests/pivot_language_experiment_test.py`, this document, unique `artifacts/pivot-language/` outputs. General procedural lessons were added to the default-profile query-representation skill, outside the project.

```bash
# Fast focused tests; real integration explicitly skipped unless opted in:
env -u PYTHONPATH .venv/Scripts/python.exe -B tests/pivot_language_experiment_test.py -v
# Full actual run; MUST a new unique project-local directory:
PIVOT_LANGUAGE_RUN='D:/Projets/BorgKnowledge/artifacts/pivot-language/NEW-UNIQUE' \
  env -u PYTHONPATH .venv/Scripts/python.exe -B -W error::ResourceWarning \
  tests/pivot_language_experiment_test.py -v
# Read-only retained harness verification:
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/pivot_language_experiment.py \
  --verify artifacts/pivot-language/run-20261019-a1
```

Artifact map: `pivot-20261019-a/model-receipt.json`, `translation-environment.lock`, `fresh-go/freeze.json`, research raw bytes/receipts and citation ledger; primary run freeze/selection freeze, archived code, original source snapshots, vectors, three readbacks, raw results/report/full review, server/translator logs, cleanup and evidence manifest; sibling `run-20261019-a1-independent-audit.json`; research `diagnostics-a1.json` and `token-diagnostics-a1.json`. Independent audit intentionally refuses to overwrite an existing receipt; an optional second positional argument selects a NEW receipt path, e.g. `.../audit.py artifacts/pivot-language/run-20261019-a1 artifacts/pivot-language/NEW-audit-receipt.json`. No artifacts from earlier experiments were overwritten.

## Next intervention, not another unbounded sweep

**Retain baseline; do not activate lexical translation or fusion.** Local translation is feasible and sometimes improves acquisition, but the fresh multilingual top1 remains70%, no-answer falseaccepts100%, and selected judgments are incomplete. The first80% milestone and90% target remain open, not lowered.

Before another acceptance claim, obtain independent pooled relevance/applicability judgments for the competing Go passages; keep these observed questions diagnostic thereafter. The narrow next ranking experiment should freeze a **same-pool original-query versus translated-query incumbent rerank20 control**, retaining original dense/gates/citations, with translation semantics and version rejection checked separately. That isolates the original French reranker-input bottleneck without another heavier-model download or database migration. If English all-versus-one and source-scope discrimination still fail, qualify a multilingual late-interaction same-pool challenger rather than expand lexical budgets or handcode operators. Separately develop no-answer/version rejection on development-only labels at meaningful coverage; no universal logit threshold is justified here.

This finite baseline+two-variant attempt is complete with concrete ranking, applicability, no-answer and judgment blockers. **Parent task stays OPEN/in_progress**; this is not permission to stop the broader user-directed improvement loop or activate a runtime.

## Sources

[1] https://huggingface.co/Helsinki-NLP/opus-mt-fr-en/raw/c4aed37b318c763fd177aa449b44e3b783cc6c02/README.md
[2] https://arxiv.org/html/2504.16264v1
[3] https://raw.githubusercontent.com/golang/go/ed07b321aef7632f956ce991dd10fdd7e1abd827/src/sync/once.go
[4] https://aclanthology.org/2022.coling-1.96
