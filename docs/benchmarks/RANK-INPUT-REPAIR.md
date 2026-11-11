# Reranker input repair — development-first exposed diagnostic

## Contract

This standalone experiment changes only model input representations; it does not activate a runtime change or certify the multilingual 80%/90% milestone. Semantic relevance must be judged from the full presented evidence by a blinded independent parent reviewer. Expected-ID recovery is a diagnostic, never semantic correctness.

Original queries remain unchanged for dense acquisition, FTS5, request/tool protocol and evidence. A separate rank-query representation may remove an anchored EN/FR provenance clause only if the exact request was compiled with matching source-edition/version spans, the compiler did not fail closed, and hard scope constraints have already been enforced. The independent get gate rechecks constraints. Technical identifiers, flags, numbers, negation and every character after the provenance clause are retained byte-for-byte in Unicode text. Unsupported wording remains unchanged.

Passage inputs are greedy source sentence/paragraph windows capped at 256 or 384 model tokens, selected by lexical overlap with the **original** request. Oversized structural units fall back to token-boundary pieces. Selection never sees labels, proof anchors, query IDs or API-specific rules. No source-title enrichment is applied. Parent scores are maximum segment logits, not calibrated probabilities. Evidence always resolves to original parent/source text with its normal structural completion, not model-window text.

## Frozen protocol

- Original slice96/overlap24 dense representation, point400/dense-parent100, original FTS10, equal RRF60, top20 original candidate parents; pinned resident MiniLM and mMARCO512 longest-first CPU2/1 batch4.
- Development: all old16 answerable +5 no-answer questions, with no invented source-scope requirement. Two mechanically wrapped questions from the same development metadata are template checks only, not additional generalization evidence.
- Prespecified rank variants: original full2, query-only2, compact-query window256×2, original full3, compact-query window384×3. Each ×2 variant executes exactly two actual inference pairs per candidate, and each ×3 executes three. Short candidates/windows receive duplicate slots without adding candidates. Full-input controls execute the same duplicates, not cached fabricated logits.
- Select on old development selected-positive top1, then MRR; original controls win exact ties. Freeze before any old52 rerun. Author-selected labels are incomplete; unjudged alternatives remain unknown.
- Old52 is a reused exposed diagnostic. Rerun the corresponding full-input control, query-only2 where the selected segment budget is2, and development-selected window challenger; if development retains a full control, the prespecified 256×2 repair is still diagnosed but never renamed a selected winner.
- Report unthresholded top1 separately from the unchanged cutoff2.5. Calibration transfer is not assumed, and no threshold is fitted on diagnostics.

## Visibility and review boundaries

The earlier report counted 718/822 candidate pairs reaching512. That statistic alone establishes neither actual truncation nor invisible proof. The new tokenizer audit compares configured actual pair offsets to an untruncated clone, records query/passage token counts and exact source-relative offsets, and maps frozen proof anchors only **after** scoring. Source anchor labels never enter window selection. Proof absent from the candidate parent, excluded by window selection, partially visible and fully visible must be reported separately. Frozen anchors are incomplete, so visibility of one selected quote does not establish exhaustive semantic support.

Seven tracer-bullet edge cases were observed failing before their minimal implementation and then passing: no enforcement/no removal; exact compiled English clause; French negation/Unicode preservation; stale or spanless compilation refusal; exact source windows/token caps; reaching-limit versus real truncation and proof visibility; matched duplicate pair budgets/max parent aggregation. Only the newly owned test file is run; historical audit helpers that rewrite evidence are not invoked.

## Execution and artifacts

Run from `D:/Projets/BorgKnowledge`:

```bash
PYTHONPATH='D:/Projets/BorgKnowledge;D:/Projets/BorgKnowledge/tools' .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_rank_input_repair*.py' -v
.venv/Scripts/python.exe -m tools.rank_input_repair.runner
```

Each invocation creates a unique `artifacts/rank-input-repair/diagnostic-*` directory, archives exact owned code, hashes historical inputs before/after and closes only its owned resident Qdrant processes. Candidate maps, actual pair texts/scores, acquisition responses, top5 original evidence and timings are retained per query. Only `blind-packet.json` plus `RUBRIC.json` are suitable for independent review; mapping, labels and visibility diagnostics must remain separate until verdicts are frozen.

Live results are recorded below after real execution. No downloads, installs, environment/global configuration edits, private/vault access, staging or commits are authorized.

## Reproducibility failure retained and repaired

The initial unique run `diagnostic-3b7f3be280804fa6b6a82c81a4b21b09` completed development but stopped at the first diagnostic baseline-rank equality assertion. It is retained without rewriting its evidence. Both its resident server cleanup receipts show process exit and port closure.

A separate actual probe, `parity-probe-b2b0e90ae1804feb95b097b2a16e4b46`, demonstrated that original candidate-order full-input inference exactly matched historical logits and repeated identically, whereas **interleaving duplicate pairs changed the batch composition and produced up to 0.8042460083961487 absolute logit drift** with ranking changes. The pinned ONNX bytes contain98 `DynamicQuantizeLinear` and98 `MatMulInteger` string occurrences, consistent with batch-dependent dynamic quantization. This is measured batch-composition sensitivity, not evidence of random nondeterminism or new semantic gain.

An eighth RED→GREEN regression requires each segment slot to run in its own original-candidate-order round, including a five-candidate/non-multiple-of-four fixture. This preserves the original batch4 cohort and padding context for repeated full controls. Actual repaired probe `round-parity-3d995b13de86439ca2773b90295e4dc5` verified **exact** original scores/ranks at40 actual inference pairs. The final runner strengthens historical comparison to exact score equality; no epsilon/tie tolerance was introduced. All development selection was rerun from scratch under the corrected recipe in `diagnostic-5d7b8ad08d1d47fd887888632b029b3d`; the failed run's selection was not reused.

That corrected run exposed a separate audit-only bottleneck: cloning/deserializing the full tokenizer for every candidate pair. It was stopped deliberately by terminating only its positively identified owned Qdrant PID15152. The next request consequently raised `ConnectionRefusedError [WinError 10061]`; this was **not** an unexplained server crash or memory/resource failure. Its normal context manager wrote cleanup showing PID15152 exited, port59528 closed, returncode15. Independent socket/PID checks corroborated both.

A ninth RED→GREEN test proves that a session-scope untruncated tokenizer yields identical visibility output. Actual pinned-tokenizer measurement in the final run's `audit-equivalence.json` shows exact output equality, with one-pair audit time0.6192315000080271s for rebuilding the clone versus0.002449199993861839s when reused; these are single measurements, not a general performance benchmark. No rank/query/window/scoring function changed. The final unique run copies the completed corrected development receipts, verifies exact source identity for reranking, query views, window selection, pair construction/rounds and aggregation, preserves the selected winner, freezes again, and reruns **all52** actual diagnostic requests. It does not reuse any partial diagnostic score as a new inference result. `development-reuse-receipt.json` discloses the original development source and hashes.

## Actual outcome

Final complete run: [`diagnostic-75b0e124f04445c4a55c1e7cbe481c19`](../../artifacts/rank-input-repair/diagnostic-75b0e124f04445c4a55c1e7cbe481c19/). All52 original constrained candidate pools and all full-input baseline ranks/logits match the historical request-scope run **exactly**. Both inference and Qdrant are real, resident and isolated. No tolerance was substituted for reproducibility.

### Development selection — original control retained

| View | Selected-positive top1 /16 | MRR | Actual pairs on21 requests |
|---|---:|---:|---:|
| Original full2 |15|0.968750|840|
| Query-only2 (identity on unwrapped dev) |15|0.968750|840|
| Compact-query 256×2 |15|0.958333|840|
| Original full3 |15|0.968750|1260|
| Compact-query 384×3 |13|0.895833|1260|

These are incomplete selected-label diagnostics, not independently established semantic precision. The original full2 control won the frozen selection rule; the 256×2 challenger is therefore **not selected or accepted**, even though it was prespecified for diagnostic investigation. The two wrapped development questions supplied six additional mechanical rank requests; no new generalization denominator was invented.

### Old52 actual inference, unthresholded versus unchanged cutoff

| Measure | Original full2 | Query-only2 | Compact-query 256×2 |
|---|---:|---:|---:|
| Actual inference pairs |1644|1644|1644|
| Original candidate-parent opportunities |822|822|822|
| Unthresholded top1 available |52/52|52/52|52/52|
| Answerable accepted at frozen2.5 |37/40|33/40|32/40|
| No-answer accepted at frozen2.5 |4/12|1/12|1/12|
| Raw expected-ID top1, **not semantic correctness** |17/40|23/40|25/40|
| Measured reranker sum, seconds |112.087983|111.938404|44.001151|

The final diagnostic continuation took346.123882s wall time; it **excludes** reused completed development execution and earlier failed/stopped runs. Shared acquisition is executed once per request and its exact response/pool is used for each variant. The rerank sums are stage costs, not independently measured end-to-end pipeline latencies. The overall task exceeded the requested25-minute budget because of the reproducibility investigation and initially expensive audit; no claim of meeting that time limit is made.

### Visibility disproves the simple missing-input hypothesis

After collapsing duplicate full-input slots:

- **Original:**718/822 pairs reach512, but only716/822 are actually truncated. No query loses any token. All40 frozen answerable proof anchors are already fully visible in at least one original candidate pair.
- **Query-only:**691/822 pairs reach512;685 are actually truncated. Still no query-token loss, and the same40/40 proof anchors are fully visible somewhere in the pool. Removing the provenance clause changes25/52 top1 results, but does **not** recover a previously wholly invisible frozen proof.
- **256×2:** zero truncated pairs;35/40 anchors are fully visible in one selected segment, four are only partially/distributed-visible, and one is excluded. All40 anchors remain present in the original candidate pool. Generic lexical window selection therefore **loses full proof visibility for five questions** despite eliminating truncation. It changes38/52 top1 results.

These are source-anchored input facts, not semantic judgments. The result does not support “the asked behavior was cut out of the long query”; all query tokens survive. Provenance text can affect model scoring without token loss, but whether the changed top1 evidence fully answers each request remains for independent review. Windowing is not a blanket repair: baseline retains more fully visible proof and wins development selection. The unchanged cutoff also rejects more answerable requests after either transformation, so reduced no-answer acceptance cannot be presented as calibrated improvement.

### Exact evidence and cleanup

Only send these two files for blind review:

- [`blind-packet.json`](../../artifacts/rank-input-repair/diagnostic-75b0e124f04445c4a55c1e7cbe481c19/blind-packet.json):156 randomized actual top1 presentations, every52 requests ×3 variants, no IDs/gold/scores/acceptance/pipeline fields.
- [`RUBRIC.json`](../../artifacts/rank-input-repair/diagnostic-75b0e124f04445c4a55c1e7cbe481c19/RUBRIC.json): frozen full-support, applicability and source-edition rubric.

Keep `mapping-DO-NOT-SEND.json`, `diagnostic-results-DO-NOT-SEND.jsonl`, `token-visibility-DO-NOT-SEND.jsonl` and `per-query-proof-visibility-DO-NOT-SEND.json` separate until independent verdicts are frozen. The latter maps every frozen proof to exact source anchors, parent candidates, selected pair slots and visible source-token offsets. `visibility-summary.json` is the aggregate, and archived `code/visibility_audit.py` reproduces that report without model inference. `report.json` preserves pair budgets, scores, cutoff counts and measured times; `development-reuse-receipt.json` makes the continuation explicit.

Verification:142 historical files byte-identical; frozen owned code verified;780 presented top-five excerpts have exact source-offset/text/hash equality;29 artifact manifest entries verified after the separate visibility audit. Final owned Qdrant PID14876 exited and port54299 closed. Earlier failed/stopped/probe runs and their cleanup receipts are retained. No runtime activation, downloads, installs, private/vault access, global configuration edits, staging or commits. **Semantic accepted-correct and any80%/90% milestone remain unknown until blind review.**
