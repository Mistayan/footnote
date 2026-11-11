# Multilingual accuracy iterations — GTE, Jina, preparation and final-rank controls

**Status: NOT ACCEPTED; `bk-2jv` remains in progress for parent verification.** Personal knowledge/agent workflows only. No runtime activation, commercial deployment, private/vault ingestion, global configuration, staging, commit or push.

## Outcome and gate

The selected development ranking is **Jina v2 multilingual, int8 ONNX, pair cap512, uniformly remove only complete opening YAML frontmatter**. Selection uses old DEVELOPMENT answerable P1, then MRR, with incumbent preference on exact metric ties. All sets here are **reused diagnostics with incomplete selected-positive labels**, not fresh independent judgments. The sealed final evaluation owned by the other worker was not read, modified or used for selection.

The experimental contract is P1 **correct / ALL answerable >=80%**, accepted-answer coverage >=80%, no-answer false acceptance <=10%; 90% is stretch, not a claim. Selected ranking development is9/12 before rejection. The development-only raw-logit cutoff0 gives8/12 correct,10/12 accepted and0/4 no-answer accepts. **8/10 accepted precision is not an80%-all-answerable success.** These small development counts do not establish generalization. No uncalibrated score is called a probability.

A single unselected diagnostic cell (incumbent+FP32-GTE equal RRF on the old holdout) reaches10/12, but its DEVELOPMENT is7/12 and it returns4/4 no-answer queries. It is explicitly **not** selected retrospectively or presented as the requested milestone.

## Measured failure mechanisms and research

Previous BGE512 and source-heading experiments did not improve top1; fusion could demote dense-rank-one evidence; the required `must_not` proof was already in pool20. The current study therefore changes rankers, not the vector engine. Actual isolated Qdrant acquisition confirms development candidate recall1.0 and old diagnostic holdout.9583 for every ranker on the matched pools. Changing engines has no evidenced remedy for these ranking errors.

The mGTE paper is *mGTE: Generalized Long-Context Text Representation and Reranking Models for Multilingual Text Retrieval*, Xin Zhang and twelve coauthors, EMNLP2024 Industry Track, pages1393–1412. Only its official abstract/metadata was read here. It describes a native8192-context encoder and contrastively trained cross-encoder; no paper metric is converted to local P1.[4] The exact upstream GTE card declares Apache-2.0, French among supported languages, and scalar pair logits. Its ONNX conversion card identifies the upstream base but has **no independent license field**: upstream declaration is verified, conversion-specific legal clearance is not invented.[1][2]

The public TEI issue498 reports a model-loading failure in a particular Candle backend, not proof that GTE cannot run on CPU or ONNX. It was used as a deployment-risk hypothesis; our real ONNX Runtime execution succeeded without installing anything.[3]

Jina's exact upstream card supplies its own ONNX weights, supports multilingual cross-encoding and1024-token context, and explicitly licenses research/evaluation under **CC-BY-NC-4.0**. This is not commercial-use authorization. Its card's benchmark table motivated a second genuinely multilingual checkpoint after GTE failed; no external benchmark gain is claimed to transfer locally.[5]

### Qualified artifacts and runtime

| Checkpoint | Pinned repository revision | Payload bytes | ONNX SHA256 |
|---|---|---:|---|
| GTE int8 | `onnx-community/gte-multilingual-reranker-base@ee64367e35a2db0da46bb6497e13a18f8bd585cb` |357945658|`ccf51dba7f8aa9205753761cfaa68c55f741792501463a3bf25d7e5bcdac7c35`|
| GTE FP32 |same|1274902308|`4712afa6eed2ba8c3f00bf5b90f37fa2c58e60f4f22cf37763d4a48f523ffcc9`|
| Jina int8 |`jinaai/jina-reranker-v2-base-multilingual@9cfeff2df7d40d1b78e75e5e9cebec92a99813c9`|296678844|`c5220cf8fe023f8aa0ed2a3eb787d4451a7f17cf53f6b787e35718dd4b8815c3`|

Total new checkpoint/tokenizer/config payload **1929526810 bytes**, below the2000000000-byte ceiling. Research/API responses are retained separately; package/network overhead is not claimed instrumented. Every selected file matches pinned API size and LFS SHA where provided. Cards, exact API metadata, URLs, download durations and per-file hashes are retained. No package installation or shared-environment mutation was needed; the existing isolated translator environment was reused offline without modification.

First shell command: `rtk --version` ->0.48.0. Live discovery found24 logical CPUs and AMD Radeon RX6800; `nvidia-smi` was absent. Inference explicitly uses ONNX Runtime CPUExecutionProvider, intra/inter threads2/1, batch4, longest-first truncation, pad1, raw scalar logits. Hardware was inspected before choosing CPU; CUDA was not assumed. GTE's native8192 and Jina's native1024 are not confused with matched512 controls.

## Frozen iterative ledger

Each finite stage writes its declaration before new model inference or algorithm replay. Later stages are justified by measured development failures. Old holdout is already observed diagnostic; no new variants are tuned from the sealed final test.

1. **`int8-live-v1`:** actual isolated Qdrant1.19.2, two resident encoders, baseline mMARCO/GTE512/GTE1024 on identical admissible union20.136 original parents/32 questions. Dense60 each, OR lexical20, exact20; reserve exact2+MiniLM6+E5six+lexical6, dedupe/fill uniformly; source-version gates before ranking/presentation, no refill.96 ranker requests. Acquisition is shared once per question, so component timings are **not independently measured pipeline E2E**. Green/indexed136 checks plus full vector/payload readbacks are retained.
2. **`float-control-v1`:** GTE FP32 numerical control on the same frozen actual-Qdrant pools;32 actual resident requests. Separately replay fixed equal-RRF incumbent+GTE-int8/FP32 final ranks. Numerical conversion effects are isolated, not attributed to an engine or new language model.
3. **`jina-control-v1`:**64 actual resident requests on those same pools;512 matched and1024 native controls. Original Jina ONNX artifact, no remote model code execution.
4. **`pivot-control-v1`:** existing pinned local OPUS French→English worker with NEW GTE/Jina rankers; fixed pivot-only and.5 original+.5 pivot-logit controls. English scores are exact original reuse, not duplicate inference. A uniform French question-word rule includes `Depuis quelle`; original-query gates and original evidence remain unchanged. Translation preserves protected code/version spans using the existing worker, but syntax roundtrip is not semantic proof. Example actual error: *intervalle numérique* becomes *digital range*; no manual repair or operator dictionary.
5. **`preparation-v1`:** complete opening YAML frontmatter only is removed uniformly from ranker input, never from evidence. Generic filtering metadata was repeatedly ranked over actual operator/range/threshold passages. The incremental ablation reuses unchanged-pair logits and rescored changed pairs; **it is not full-request latency or guaranteed dynamic-quantization batch parity**.
6. **`fusion-control-v1`:** eight finite weak lexical final-rank variants: incumbent/GTE/Jina/Jina-clean × lexical RRF weight.125/.25, reranker weight1, k60, unchanged pool.256 saved-rank replay rows, **zero new model/server inference**. Negative results retained, not called live E2E.
7. **`export-replay-v1`:** actual complete candidate20 calls through the exported callable, with both unthresholded ranking and frozen-threshold presentations reported. This guards batching-dependent quantization differences from the incremental preparation control. Frozen configuration is not tuned from this diagnostic replay.

Full original top-five passages, question text, frozen selected/incompatible labels, UNKNOWN status, P1/P3/P5, MRR5, recall5, candidate recall, full rankings, raw scores, original offsets/hashes/URLs, truncation counts and latency components are retained per query. P@k divides selected hits by fixedk; absent slots are zero. A one-positive query has maximum selected P5.2; UNKNOWN is not retrospectively made irrelevant or positive. MRR is a rank statistic, not answer accuracy.

## Verified measured results

All rows below are **reused diagnostics**, not the sealed final evaluation. Candidate pools are matched. Full precision/recall/MRR, coverage, incompatibility and latency table: [RESULTS-TABLE.md](../../artifacts/accuracy-iteration/ai-20261020-gte/RESULTS-TABLE.md). Every stage has full original per-query review, not just aggregates.

| Variant | Development correct / ALL answerable | Old diagnostic holdout correct / ALL answerable | Development MRR5 | Resident p50 ms development / holdout |
|---|---:|---:|---:|---:|
| incumbent mMARCO |9/12|9/12|.7917|856.8 /735.3|
| GTE int8 cap512 |7/12|9/12|.7500|2854.7 /2515.8|
| GTE int8 cap1024 |7/12|8/12|.7500|2971.4 /2525.3|
| GTE FP32 cap512 |6/12|9/12|.6944|7220.3 /6354.5|
| Jina int8 cap512 |9/12|6/12|.8194|2602.6 /2223.9|
| Jina int8 cap1024 |9/12|6/12|.8194|2849.9 /2220.2|
| Selected Jina, full-call no-frontmatter |9/12|6/12|.8333|2399.7 /2130.4|
| Same frozen cutoff0 |8/12|6/12|.7500|2399.7 /2130.4|

Unthresholded variants accept12/12 answerable and4/4 no-answer questions per split. Frozen cutoff0 accepts10/12 answerable and0/4 no-answer per split; it rejects two answerable queries per split. This still fails the80%-all-answerable gate. These four no-answer examples per split are not a general safety certificate.

The full exported callable ran **32 actual requests /604 pairs**, preserving all top1 identities versus the incremental ablation, but changing full rank order on10/32 questions with maximum raw-logit delta.298046350479126. Development MRR remains.8333; diagnostic holdout MRR is.6458, not the incremental.6528. Consequently only full-call latency and metrics are used for the exported configuration; the incremental median near0ms is explicitly not deployment performance.

Corrected language strata are in `language-strata-final.json`, using the same uniform question-word rule across every variant, including the French version question previously grouped as English-or-mixed by historical categories. For the selected cutoff0: French→English development2/5 correct with3/5 accepted, diagnostic holdout1/4 correct with2/4 accepted; English development6/7 correct with7/7 accepted, diagnostic holdout5/8 correct with8/8 accepted. Aggregate coverage hides a French coverage regression; it is disclosed, not tuned away.

Operator visibility: for `holdout-09`, original `qfilter-not` pair length is203 tokens, below512 and still containing its complete `none` / `(NOT A) AND (NOT B) AND (NOT C)` semantics. Incumbent ranks it12, GTE-int8 seven, GTE-FP32 eight, Jina six. Jina still ranks incompatible `qfilter-must` first before the cutoff; the cutoff rejects that query but does not repair operator ranking. No label-specific rewrite or manual translation was added.

## Verification and cleanup

Seven finite stage commands passed their real opt-in tests; all768 result rows across24 distinct variants are retained. Independent stdlib audits verify every stage's hashes, original evidence offsets/hashes, labels, raw-server dense order, fixed pool construction, logit/rank order and metric arithmetic. The auditor does not implement independent semantic applicability judgment; UNKNOWN labels remain a limitation. The full exported replay additionally checks cutoff acceptance and coverage arithmetic. Per-stage audit receipts, test logs and the final artifact manifest are retained.

Owned Qdrant PID25096/port61641 exited and closed; Windows terminate/wait returned1, which is forced owned-process termination, **not graceful durability acceptance**. Offline translator launcher PID12756 exited0; child/process/port readback is retained. No unrelated process was stopped. Existing incumbent/runtime helpers were only read; historical live input code and original test bytes are archived with exact frozen hash matches. Current tests evolved only in owned files. The fast suite explicitly skips costly integrations unless the relevant run environment variable is set; historical integration success is backed by each separate real log, not inferred from skips. No whole-application regression claim is made.

```bash
# Fast owned tests (integration skip is explicit):
env -u PYTHONPATH .venv/Scripts/python.exe -B tests/test_accuracy_iteration.py -v
# Read-only independent audit example:
env -u PYTHONPATH .venv/Scripts/python.exe -c \
  "from tools.accuracy_iteration.audit import audit; print(audit('artifacts/accuracy-iteration/ai-20261020-gte/export-replay-v1'))"
```

## Evaluator handoff

Artifacts: [`artifacts/accuracy-iteration/ai-20261020-gte`](../../artifacts/accuracy-iteration/ai-20261020-gte/).

- `selected-config.json`: frozen ranking/input recipe plus raw cutoff0 and model receipt hash; evaluation-only, **not accepted**.
- `selected-ranking-control-config.json`: same ranking, no cutoff, diagnostic control only.
- `final-selection-freeze.json`: development-only summaries, selected threshold counts and input/config hashes.
- `tools/accuracy_iteration/evaluator.py`: callable accepts only query and caller-supplied original admissible candidate20. It does not load labels, perform query-ID routing or silently change acquisition.

```python
from tools.accuracy_iteration.evaluator import create_evaluator
search = create_evaluator('artifacts/accuracy-iteration/ai-20261020-gte/selected-config.json')
result = search(question, [documents[name] for name in gated_pool20])
# result: ranked, scores, top5, accepted, score_kind, pair_tokens, wall_ms
```

The fresh evaluator must use the frozen union acquisition above, apply unchanged eligibility before/after, hydrate **original** evidence, preserve all-answerable denominators, and independently judge presented evidence. This callable is the resident **ranking/presentation stage**, not a hidden replacement for retrieval or an integrated agent runtime. Full source text stays local; no vault source is ingested.

## Bound and concrete next handoff

The selected configuration has not reached the all-answerable80% gate; no90% claim is made. Inspected additional comparable multilingual model payloads do not fit the remaining download allowance. Same-pool proof visibility shows operator failures are not proof truncation: `must`/`must_not` passages are short and retain their actual Boolean clauses. A larger context, another database, metadata agreement or raw-score threshold cannot be asserted to solve semantic applicability.

The next owner should run the sealed independently judged final evaluation with the exported configuration **without tuning from it**. If it fails, retain it as diagnostic and authorize a new resource-bounded mechanism (for example independently qualified entailment/late-interaction or a better independently reviewed training/evaluation set), rather than relabeling observed UNKNOWN alternatives or adding a label-specific operator patch. No continuing background experiment or automatic production promotion is authorized by this report.

### Proposed skill additions for parent review only

Do not patch the shared retrieval skill concurrently. Verified class-level learning: **dynamic-int8 quantization may make changed-pair-only rescoring differ from full-candidate request scoring; compare the complete exported callable before promoting an incremental preprocessing ablation.** Preserve original evidence even when stripping uniform source boilerplate from scoring input. Record inference versus rank replay and incremental latency separately. Exact task results belong in this report, not the skill.

## Sources

[1] https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base/raw/8215cf04918ba6f7b6a62bb44238ce2953d8831c/README.md
[2] https://huggingface.co/onnx-community/gte-multilingual-reranker-base/raw/ee64367e35a2db0da46bb6497e13a18f8bd585cb/README.md
[3] https://github.com/huggingface/text-embeddings-inference/issues/498
[4] https://aclanthology.org/2024.emnlp-industry.103
[5] https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual/raw/9cfeff2df7d40d1b78e75e5e9cebec92a99813c9/README.md
