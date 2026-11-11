# Accuracy stepping stone — stronger multilingual reranking

**Status: OPEN; experiment only, not runtime activation or independent acceptance.**

The target is useful, applicable top-one evidence ≥80% as a stepping stone, ≥90% stretch, with an explicit answerable coverage floor of80%. This experiment never abstains, so it cannot reach a precision target by refusing everything. Public selected-positive labels remain incomplete; passing a small diagnostic point estimate does not certify exhaustive semantic accuracy or a personal vault.

## Measured failure motivating the intervention

The incumbent candidate study recovers Qdrant's `must_not` proof into pool20 but the mMARCO ranker still places it11th, behind the incompatible `must` operator. French→English evidence acquisition and reranking must be separated. MiniLM and the locally named `e5-small` are **both multilingual**. The existing E5 is multilingual E5-small, not monolingual E5. See [candidate/abstention](CANDIDATE-AND-ABSTENTION.md), [actual model recipes](MULTILINGUAL-EMBEDDINGS.md), and [fusion controls](FUSION-WEIGHTS.md).

## Research: mechanism and transfer limits

- **Cross-lingual reranking:** BAAI explicitly recommends `bge-reranker-v2-m3` for multilingual use and identifies bge-m3 as its base. Query/passage pairs produce scalar relevance scores; higher scores rank first.[1] This motivates testing a larger multilingual cross-encoder on the exact same admissible pool, **not a prediction of a local80% result**.
- **Research background, abstract only:** Jianlv Chen, Shitao Xiao, Peitian Zhang, Kun Luo, Defu Lian and Zheng Liu, *M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation*, arXiv2402.03216v5. The retrieved Atom abstract describes multilingual dense/multivector/sparse embedding training and self-knowledge distillation.[4] It is background on the base embedding model, **not direct evidence that this reranker solves negation**. No full-text/table/venue or peer-review claim is made; no published metric is converted into local precision.
- **Alternative considered:** Alibaba's GTE multilingual reranker card declares Apache-2.0 and includes French.[3] Its inspected official repository has no ONNX file; it was not selected or downloaded. Avoiding a new framework/export/dependency environment keeps this experiment attributable and bounded.
- **Deployability:** the pinned onnx-community card identifies an automatic ONNX conversion of BAAI's model.[2] The inspected repository supplies a standalone quantized model, avoiding the >2GB unquantized external-data checkpoint. This experiment uses that quantized artifact; it does not claim FP32-equivalent accuracy.
- **Confidence is not calibrated:** the public discussion index was used for discovery, not accuracy evidence.[5] A community user reports relevant-looking passages scoring below a0.5 sigmoid threshold and asks how to choose a threshold.[6] This is an anecdotal warning, not benchmark evidence. We retain raw logits for ranking and do **not** invent a universal confidence threshold.
- **Licensing boundary:** the exact pinned upstream card declares `apache-2.0`.[1] The conversion card declares its base model but no separate license field.[2] A community license-confirmation request contains no maintainer confirmation in the fetched thread.[7] This is verified upstream **license declaration**, not legal clearance or an invented independent conversion license. No redistribution or production activation is performed.

Research evidence, exact fetched bytes, citation ledger and failed fetch alternatives are under `artifacts/accuracy-stepping-stone/lrk-research/`. The web extractor backend was search-only and could not fetch bodies; public HTTPS GET with stdlib urllib was used instead. Guessed `Xenova/bge-reranker-v2-m3` returned401; the actual public onnx-community repository was discovered and pinned. The existing project environment lacks `requests`; urllib required no install.

## Frozen model recipe and cost boundary

| Item | Incumbent | Candidate |
|---|---|---|
| Model | Existing pinned multilingual mMARCO cross-encoder | BAAI bge-reranker-v2-m3, quantized ONNX |
| Conversion repository | Existing `reranker-model/receipt.json` | `onnx-community/bge-reranker-v2-m3-ONNX` |
| Candidate conversion revision | — | `6f5ff65298512715a1e669753bc754d2bc8f367b` |
| Candidate upstream card revision | — | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
| Input recipe | Original query+parent body, longest-first512 | Same query+parent body, longest-first512 |
| Output | Raw classification logit; no embedding pooling | Raw classification logit; no embedding pooling |
| Resident CPU | ONNX Runtime, intra/inter2/1, batch4 | Same |

BGE's upstream tokenizer declares8192 tokens.[8] The primary test intentionally caps it at512 to isolate the model at a matched context budget. This is **not its native maximum**. Quantization, tokenizer and parameters differ from the incumbent; not token-for-token numeric parity. Encoders retain their actual manifests: MiniLM128/empty prefixes, multilingual E5small512/`query: ` and `passage: `, attention-mask mean followed by L2 normalization, CPU2/1 batch8. Model bytes and tokenizer hashes are checked before session construction.

Downloaded checkpoint payload: **587812355 bytes** in the retained receipt, below the1.5GB total ceiling; no second model, package install, global/shared environment edit, remote inference or private upload. ONNX570727094 bytes, tokenizer17082900 bytes; remaining payload is config metadata. Model SHA256:`912fc1215c2dbff6499700534bd8d31253af01573861abbfc43afd1fab6cce5d`, matching the pinned LFS SHA. `bge-model/receipt.json` lists every URL, revision, byte size, hash and measured download duration. Small research/source/API GET response bytes are retained separately; total network overhead is not instrumented.

## Dataset preparation BEFORE new inference

Fresh bounded source-family-disjoint slice: **63 uniform original-source windows,16 questions** (six answerable and two no-answer per partition). Development uses Git/gitignore/reset/clean; holdout uses Rust Book borrowing/Rc/shared-state. Three French and three English answerable questions per partition. Git sources pin releasev2.47.0; the Rust branch was resolved to an immutable commit before downloading; exact URLs/raw bytes/normalized text hashes/offsets are retained.

`prepare.py` creates every source's1400-character windows at1100-character strides uniformly, with no question/label arguments. `annotate.py` then freezes selected evidence quotes and labels before any new model inference. All windows containing the complete selected quote receive positive labels. This does **not** exhaustively judge alternative phrasings/windows; UNKNOWN remains UNKNOWN. Overlapping positives can be near-duplicates, so P3/P5 are not independent information gain. Rust include directives remain visible original text, not expanded code; this is not a document-extraction benchmark. Development/holdout source families are disjoint, not every underlying programming concept.

Annotations are by the **implementing agent**, not independent human judgments. Private-password and private-deployment-latency questions deliberately have no answer in this bounded public corpus. The same two no-answer templates are reused across fresh partitions, so those four entries are **not four independent no-answer scenarios**; development-only model selection excludes all no-answer rows. Fresh questions are frozen prior to new inference but authored after reading the historical failure categories; they are not blind external evaluation. The old136-passage/32-question dataset is run separately as **reused diagnostic only** and cannot certify80%/90%.

## Prespecified paired experiment

1. Frozen union acquisition: MiniLM dense60 + E5 dense60 + incumbent OR lexical20 + exact technical-token20. Pool20 reserves exact2/MiniLM6/E5six/lexicalsix, deduplicates, then fills in MiniLM/E5/lexical/exact order. No labels or query-specific translation/expansion/operator patch enters retrieval. The union is an acquisition intervention versus history, so historical cross-run changes cannot be attributed to ranker alone.
2. On **identical** pools: existing source-derived Python family gate before reranking, each ranker scores at most20 admissible original parents; reapply the gate before top5; no refill. UNKNOWN metadata is rejected on explicit Python version requests, otherwise NOT_ASSESSED—not certified compatibility.
3. Both models independently execute the full request: own query encodings, actual isolated loopback Qdrant HTTP retrieval, lexical/exact search, pool/gates, resident rerank, source hydration and response JSON. E2E includes explicit per-request HTTP connection renewal. No reused-stage sums are advertised as E2E. One repetition; this is a bounded CPU diagnostic, no latency significance/SLA claim.
4. Development-only model choice: highest fresh-development answerable P1, then MRR; baseline wins exact ties. Save `selection-freeze.json` before any fresh holdout or old query inference. Both paired results remain reported regardless. No weight tuning or model selection on holdout.
5. Prespecified coverage floor80%; no abstention or threshold tuning. Report no-answer retrieval false accepts separately: nonempty retrieval is not a generated recommendation.
6.96 independently executed model/query requests,1200s measured-work cap. Four isolated Qdrant collections, green/indexed-count checks and full vector/payload readback. Only owned process/port/storage; no runtime endpoint/process/config is touched.

Metrics: P@k divides selected-positive hits by fixedk, missing slots zero. MRR is reciprocal first-positive rank at cutoff5, **not accuracy**. Recall5 and candidate recall use selected positives. A one-positive query's maximum selected-label P5 is0.2; P5 is **not** evidence that80% of all returned text is wrong. Incompatibility uses only explicitly labeled incompatible IDs; UNKNOWN is reported separately. Primary top1 denominator is answerable queries; all-question correct/attempted is additionally reported so no-answer failures cannot disappear. No80% generalization claim from a tiny point estimate.

## Execution and verification

- `tools/accuracy_stepping_stone.py`: new isolated executable harness and replay verifier.
- `tests/accuracy_stepping_stone_test.py`: fixed-cutoff/coverage metrics, deterministic bounded label-free union pool, development-only selection guard, opt-in real96-request integration plus retained-source/rank/readback replay.
- Vertical RED→GREEN observations: missing metrics module; missing pool/selection functions; missing real experiment. Real first run also caught a stale HTTP keep-alive connection after offline encoding (`WinError10053`). Failed `lrk-primary-v1` retains receipts and owned-server cleanup; connection renewal was fixed without changing variants/labels.

```bash
# Fast tests; integration explicitly skips without the environment variable:
.venv/Scripts/python.exe -B tests/accuracy_stepping_stone_test.py -v
# Real experiment: ALWAYS new directory, never overwrite historical evidence:
ACCURACY_STEPPING_RUN='D:/Projets/BorgKnowledge/artifacts/accuracy-stepping-stone/NEW-UNIQUE' \
  .venv/Scripts/python.exe -B -W error::ResourceWarning tests/accuracy_stepping_stone_test.py -v
# Replay retained primary run:
.venv/Scripts/python.exe -B tools/accuracy_stepping_stone.py --verify artifacts/accuracy-stepping-stone/lrk-primary-v2
.venv/Scripts/python.exe -B artifacts/accuracy-stepping-stone/lrk-research/audit.py artifacts/accuracy-stepping-stone/lrk-primary-v2
```

Task`bk-lrk` remains **in_progress/open for parent verification**. No staging/commits, source originals deleted, vault reads, global configuration or runtime changes. Broader repository tests are not claimed by these focused tests.

## Actual results

**Primary: neither80% stepping-stone nor90% stretch is established.** Fresh source-family holdout selected-label P1 is4/6=66.7% for both rankers; all-question selected-correct/attempted is4/8=50%. The fresh-development choice is the **incumbent** (6/6 versus BGE5/6) and was frozen before holdout. This is not a production selection, and selected-label misses are not all demonstrated semantic errors.

Primary run: [`lrk-primary-v2`](../../artifacts/accuracy-stepping-stone/lrk-primary-v2/). Failed transport run: [`lrk-primary-v1`](../../artifacts/accuracy-stepping-stone/lrk-primary-v1/). All96 full requests and480 returned original passages replay successfully. Real integration: **4/4 tests PASS in397.635s**; measured request workload379.140s. `report.json`, `raw-results.json[l]`, `PER-QUERY-REVIEW.md`, original source bytes/text, corpus/judgments, saved vectors, four collection readbacks, freeze/selection freeze, archived code and evidence hashes are retained. Every question has ordered top-five full evidence, URLs, offsets, hashes, labels, precision/recall/MRR, logits and independent E2E timing.

### Primary paired accuracy and cost

All relevance means below use answerable queries only (6 fresh/12 old per partition). P5 is selected-set precision with label-count ceiling, **not exhaustive semantic precision**. Candidate recall is after the fixed pool's admissibility gate; both models see identical candidates.

| Dataset / partition | Ranker | Top1 hits / answerable | P1 / P3 / P5 | MRR5 / R5 | Candidate recall | E2E p50/p95 ms |
|---|---|---:|---|---|---:|---|
| Fresh Git development | incumbent |6/6|1.0000 /0.3889 /0.2333|1.0000 /1.0000|1.0000|1119.3 /1179.0|
| Fresh Git development | BGE512 |5/6|0.8333 /0.3333 /0.2333|0.8750 /1.0000|1.0000|8197.4 /8669.0|
| Fresh Rust holdout | incumbent |4/6|0.6667 /0.2778 /0.2000|0.7917 /0.9167|1.0000|1163.2 /1290.0|
| Fresh Rust holdout | BGE512 |4/6|0.6667 /0.3889 /0.2333|0.8333 /1.0000|1.0000|8450.6 /8926.5|
| Old development, reused | incumbent |9/12|0.7500 /0.3056 /0.1833|0.7917 /0.8333|1.0000|881.0 /1000.8|
| Old development, reused | BGE512 |6/12|0.5000 /0.3333 /0.2000|0.6667 /0.9167|1.0000|6759.0 /7438.1|
| Old holdout, reused | incumbent |9/12|0.7500 /0.3056 /0.2000|0.8194 /0.8750|0.9583|764.8 /1140.5|
| Old holdout, reused | BGE512 |9/12|0.7500 /0.3333 /0.2000|0.8194 /0.8750|0.9583|6020.8 /8262.6|

**Effect counts:** BGE gains **zero** selected-top1 questions in every partition; regresses one fresh-development question (`fresh-development-04`) and three old-development questions (`development-00`, `development-09`, `development-11`). No fresh/reused-holdout top1 gains or regressions. BGE improves fresh-holdout selected recall5 and MRR without improving top1. This negative larger-model result is retained, not called a multilingual improvement.

### Language strata

| Partition | FR→EN selected P1 incumbent / BGE | EN or declared mixed selected P1 incumbent / BGE |
|---|---|---|
| Fresh development |3/3 /2/3|3/3 /3/3 (English)|
| Fresh holdout |2/3 /2/3|2/3 /2/3 (English)|
| Reused development |2/4 /2/4|7/8 /4/8 (English/mixed historical category)|
| Reused holdout |2/4 /2/4|7/8 /7/8 (English/mixed historical category)|

Complete per-language P3/P5/MRR/recall/cost strata are in each report's `summaries`; historical non-French categories are not retrospectively asserted to be exclusively English.

### Coverage, no-answer and compatibility

- Answerable attempted/presented coverage is **100% for both models**, above the prespecified80% floor. No abstention, thresholds or confidence calibration. This prevents refusal-only success but is not evidence of safe presentation.
- Every no-answer query returns passages: fresh2/2 per partition and old4/4 per partition, **12/12 per model overall retrieval false accepts**. No generated answer was evaluated. Neither model is acceptable as an unconditional answer provider.
- Explicit incompatible top1/top5 counts across old queries: incumbent1/2, BGE0/0. Fresh incompatible labels are empty, so zero fresh counts do **not** establish applicability. UNKNOWN top5 counts fresh development33/33, fresh holdout34/33, old development68/68, old holdout67/68 (incumbent/BGE). Unknown stays unjudged.
- Qdrant negation remains unresolved. Same admissible pool contains `qfilter-not`; incumbent ranks it12th, BGE10th. Incumbent presents explicit-incompatible `qfilter-must`; BGE instead presents unjudged `qfilter-context-04` about value-level `match except`/prefix matching, **not the requested Boolean `must_not` operator**. Removing an explicitly incompatible label from top1 is not evidence of a correct replacement.
- In fresh Rust `fresh-holdout-08`, both models' unjudged `rust-mutex-006` explicitly says Rc is unsafe across threads, so the selected-label miss is **not proven semantically wrong**. In `fresh-holdout-09`, ranking the same Rc-unsafe section does not directly identify the requested safe Arc pointer. Labels are not changed after seeing outputs; exhaustive fresh judgments remain a blocker.

For4/6, a descriptive Wilson95% interval is approximately[0.3000,0.9032], computed in retained diagnostics. These six implementing-agent, related-topic questions are not independent samples, so this interval is illustrative uncertainty, **not a generalization guarantee**. Old labels cannot certify80% and fresh selected-label counts cannot replace independent relevance judgment.

### Costs and verification receipts

Hardware: Intel Core Ultra7 270K Plus,24 physical/logical cores as reported by Windows/psutil,51132588032 RAM bytes. CPU inference only, two threads per ONNX session. Primary end-of-run harness RSS3472445440 bytes, Qdrant43786240 bytes; these are resident end measurements, **not peak/per-model standalone memory**. Model load/hash validation and offline passage encoding/indexing are separately recorded in `report.json`, outside request E2E.

Primary BGE scored924 query/passage pairs; independent full tokenization finds30 actually exceeding512 and one exactly512. The runtime's31 at-limit counter is not silently equated with31 truncations. The three fresh BGE top1 misses have selected proof lengths389/395/408 tokens, so their failure is **not512 truncation**. Larger context alone is not a justified fix for those errors.

The independent `lrk-research/audit.py` imports no benchmark implementation and replays96 requests,480 evidence records,199 source passages, raw-HTTP dense ordering, fixed pool membership, same-pool/model-vector parity, logit ranks, metrics, aggregate arithmetic, source offsets/hashes and selection-before-holdout. `lrk-primary-v2-independent-audit.json` records all checks passing. The harness verifier also checks frozen input/model hashes and complete server vector readback. Own historical harness/test hashes are verified against the archived code copies, so the separately declared follow-up can extend the current files without invalidating preserved primary evidence. Other frozen helpers/models/index remain unchanged.

Primary cleanup: owned PID5916/port closed, exit code1 from Windows forced terminate/wait; this is **not graceful shutdown/durability acceptance**. The failed first run also has process-exited/port-closed receipts. No unrelated PID or runtime was stopped. Focused incumbent regression checks:5 PASS,2 opt-in integration SKIP across candidate/budget test files; not a full application regression claim.

### One fixed diagnostic follow-up

Because the first candidate does not improve held-out top1, a **single** follow-up was declared anew in `lrk-research/followup-declaration.json`: uniformly append the first source title plus nearest preceding supported heading to BGE input only when the complete query/body/suffix fits512. Original body remains an unchanged prefix, no truncation displacement; original citations stay byte-identical. The motivation is the fresh-development confusion between Git clean OPTIONS/dry-run and Interactive-mode/quit—not a query-specific operator rewrite. No labels enter heading construction. Scope is only the16 fresh questions,32 new real resident requests; all fresh partitions are now reused diagnostics. The old32 primary requests per model remain reported and are **not** claimed retested by this follow-up. No additional checkpoint download, weight tuning or further experiment is allowed after this bounded follow-up.

**Executed follow-up: no top1 gain; stop here.** [`lrk-context-v1`](../../artifacts/accuracy-stepping-stone/lrk-context-v1/) contains32 actual requests/160 original-source evidence records. Its real integration run passed **5 tests with1 explicit primary-integration skip in198.383s**; measured request workload171.391s. Both baseline top5s and all candidate pools/query vectors match the primary exactly.306/320 BGE input pairs gain a fitting source-heading suffix; original citation bodies/hashes/offsets remain unchanged.

| Fresh partition, now reused diagnostic | Ranker | Top1 | P3 / P5 | MRR5 / R5 | E2E p50/p95 ms |
|---|---|---:|---|---|---|
| Development | incumbent control |6/6|0.3889 /0.2333|1.0000 /1.0000|1266.3 /1391.4|
| Development | BGE+source headings |5/6|0.3889 /0.2333|0.9167 /1.0000|9439.0 /10731.7|
| Reused holdout | incumbent control |4/6|0.2778 /0.2000|0.7917 /0.9167|1181.0 /1284.0|
| Reused holdout | BGE+source headings |4/6|0.3889 /0.2333|0.8056 /1.0000|9529.8 /10005.4|

Relative to plain BGE: **zero selected-top1 gains, zero regressions**, unchanged answerable top1 identities, unchanged100% answerable coverage, and unchanged4/4 fresh no-answer false accepts per model. Only the two duplicate French no-answer top1 passage identities change; neither becomes answerable. BGE's development MRR improves0.8750→0.9167, but reused-holdout MRR regresses0.8333→0.8056. Fresh French selected P1 remains2/3 per partition for BGE versus incumbent3/3 development and2/3 holdout. No production winner is selected from this diagnostic follow-up.

Follow-up costs: model load/hash validation3539.812ms, offline encoding/indexing4499.733ms; resident end harness RSS3483623424 bytes, Qdrant39231488 bytes. Primary equivalents: load3213.713ms, offline11662.479ms. Context construction/readback/review-verification costs are not hidden inside reused stage sums; follow-up E2E includes source-context construction. Independent follow-up audit passes32 requests/160 returned passages/63 source passages and all aggregate arithmetic. Full tokenization finds11/320 BGE pairs exceeding512; those original long bodies receive no suffix, so the suffix does not create truncation. Owned PID16492/port55752 exited/closed, forced terminate/wait return1. Follow-up comparison and diagnostics are separate immutable files next to the runs; neither historical run was overwritten.

### Final artifact map and decision

- [Primary per-query review](../../artifacts/accuracy-stepping-stone/lrk-primary-v2/PER-QUERY-REVIEW.md), [primary report](../../artifacts/accuracy-stepping-stone/lrk-primary-v2/report.json), [primary independent audit](../../artifacts/accuracy-stepping-stone/lrk-primary-v2-independent-audit.json), [primary error/visibility diagnostics](../../artifacts/accuracy-stepping-stone/lrk-primary-v2-diagnostics.json).
- [Follow-up per-query review](../../artifacts/accuracy-stepping-stone/lrk-context-v1/PER-QUERY-REVIEW.md), [follow-up report](../../artifacts/accuracy-stepping-stone/lrk-context-v1/report.json), [same-pool/follow-up comparison](../../artifacts/accuracy-stepping-stone/lrk-context-v1-comparison.json), [follow-up independent audit](../../artifacts/accuracy-stepping-stone/lrk-context-v1-independent-audit.json).
- Each run contains original sources, labels, freeze, model receipts/hashes, original vectors, verified Qdrant readbacks, raw scores and independent per-request timing, archived harness/tests and cleanup. Research/model files are under [`lrk-research`](../../artifacts/accuracy-stepping-stone/lrk-research/).
- `lrk-research/primary-v2-test.log` and `context-test.log` are actual test receipts. Replays use the commands above; follow-up CLI equivalent is `tools/accuracy_stepping_stone.py --diagnostic --context --fresh-only --run NEW-UNIQUE-PATH`. Follow-up replay uses `--verify artifacts/accuracy-stepping-stone/lrk-context-v1` and the same independent audit command with that path.

**Final decision:** retain the incumbent for further experiments; do not activate BGE or heading enrichment.≥80% useful/applicable top1 and90% stretch remain **unestablished**, not rescued by abstention or relabeling useful unjudged alternatives. The finite128-request primary/follow-up workload is complete and preserves the failed transport/model/context hypotheses. Remaining blockers are semantic operator/applicability ranking, no-answer safety at meaningful coverage, exhaustive independently reviewed fresh source-family-disjoint labels, and a larger multilingual holdout. Public experimental results do not certify a private vault or production runtime. Task`bk-lrk` stays open/in_progress for parent verification; no further model tuning in this task.

## Sources

[1] https://huggingface.co/BAAI/bge-reranker-v2-m3/raw/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e/README.md
[2] https://huggingface.co/onnx-community/bge-reranker-v2-m3-ONNX/raw/6f5ff65298512715a1e669753bc754d2bc8f367b/README.md
[3] https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base/raw/8215cf04918ba6f7b6a62bb44238ce2953d8831c/README.md
[4] https://export.arxiv.org/api/query?id_list=2402.03216
[5] https://huggingface.co/api/models/BAAI/bge-reranker-v2-m3/discussions?p=0
[6] https://huggingface.co/api/models/BAAI/bge-reranker-v2-m3/discussions/25
[7] https://huggingface.co/api/models/BAAI/bge-reranker-v2-m3/discussions/59
[8] https://huggingface.co/BAAI/bge-reranker-v2-m3/resolve/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e/tokenizer_config.json
