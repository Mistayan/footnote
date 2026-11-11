# Evidence views — development-only negative result

## Decision

**Reject all new ranking views; next export stays unchanged.** No view strictly improves expected-proof P@1 over the selected identity callable on development. Nothing was activated, committed, staged, or changed in the incumbent/runtime. NEW v2 judgments, review and failures were not opened. This is not an 80% acceptance claim on recycled development.

Canonical run: `artifacts/acquisition-repair/evidence-views-1ca950978161430894065d15e6bf3c12/`.

- `report.json` SHA256: `a05729dee50677ea0248944d0a9ff5c024088faa2a03b078586c945a8622e6d9`.
- Adjacent pre-inference `evidence-views-1ca950978161430894065d15e6bf3c12.freeze.json` SHA256: `80ba544ba5096256c818b78899554e085837d69185d0c6a1cafc7e45a84eb571`.
- `rows.jsonl`: all126 actual requests, original questions, identical candidate pools, full rankings/logits, original top-five evidence, URLs/hashes/offsets, exact source views, pair counts, actual query/document tokenizer visibility and post-score selected-proof diagnostics.
- `PER-QUERY-REVIEW.md`: every question/variant and ordered full top-five original parents with provenance and unchanged selected matches.
- `independent-audit.json` and `audit.py`: separately implemented deterministic audit, not independent human semantic adjudication.
- `artifact-sha256.json`: original execution file hashes; `delivery-sha256.json` adds final audit/review/document receipts without overwriting execution hashes.

## Frozen execution contract

Read acquisition identity-callable results (16 answerable +5 no-answer) and the old exposed17-miss evidence-boundary diagnosis first. No old exposed questions were reranked, and no NEW v2 label or failure was used for selection.

Before model inference, froze six variants, builder/test/code/input hashes, original source texts, selection rule and calibration objective. Preserved corpus, selected labels and original parent evidence. Builder receives only query, parent and full original source; poisoned IDs/relevance/expected/incompatible fields cannot alter its views. No API/operator/negation-specific rewriting, answer dictionaries, generated evidence, translation or new models.

Selected acquisition is unchanged: slice96 children, point400, dense parent100, original FTS top10, RRF k60, parent pool20. Each of126 requests independently performs actual original-query encoding, isolated resident Qdrant search, lexical/fusion, actual resident mMARCO reranking and original evidence serialization. All candidate pools equal the prior identity callable. Baseline ordered ranks and raw logits match that callable exactly on21/21 requests.

Models: existing original pinned MiniLM int8, cap128, and mMARCO int8, longest-first query/document cap512, threads2/1 and batch4. No downloads or installs. Actual owned Qdrant collection reached green,1494 points and1494 indexed vectors. The existing helper restores pinned saved child vectors; fresh source ingestion/embedding is not claimed. No shared service was used or stopped.

## Finite generic views

1. **raw:** unchanged full original parent.
2. **heading_spare:** source first-line title plus up to two nearest preceding generic headings, appended only when exact originally visible query/body token IDs and offsets survive. Never displaces visible body.420/420 pairs passed independent visibility comparison;171 pairs actually expose some added context. Remaining pairs need not gain visible context.
3. **crop320:** one source substring at sentence/paragraph/parent boundaries, at most320 Unicode characters, maximizing unique Unicode word-token overlap with query. Deterministic ties prefer longer crop, then earlier source offset.
4. **crop640:** same algorithm and20 pairs/request at640 characters.
5. **heading_crop:** source-title/heading context plus the640-character lexical crop; title/heading text is uniformly source-derived, not label-derived.
6. **paragraph_max:** score full parent AND every paragraph fragment within it against the original query with mMARCO; aggregate each parent's maximum raw logit. Paragraphs are not selected using expected quotes. This is variable extra inference, NOT an equal-compute improvement.

Candidate crop lengths are boundary constrained, not padded to exactly320/640. There were zero crop-size overflows in either actual arm. The builder falls back to the full parent for a hypothetical indivisible long sentence/paragraph; that untested-format fallback is not a universal hard crop-cap guarantee. Generic headings support Markdown, RST directives/underlined titles, AsciiDoc definitions and numbered section lines; unsupported structure remains absent. For example, the retained RFC text starts with a BOM-only line, so the first-line title extraction is uninformative there. No source-specific title repair was added.

## Actual results

P@1 here means frozen selected-proof ID top1 / **all16 answerable questions**. Unknown adjacent parents can contain useful information; no unknown was relabeled. All five no-answer questions remain false accepts without a threshold.

| View | Selected P@1 | Gains / losses vs raw | Scored pairs | Resident E2E p50 / p95 ms | Inference ms/pair |
|---|---:|---|---:|---:|---:|
| raw |15/16|none|420|1403.082 /1427.964|67.908|
| heading_spare |15/16|none|420|1432.651 /1477.924|67.988|
| crop320 |11/16|0 /4|420|216.300 /269.124|9.205|
| crop640 |15/16|1 /1|420|417.753 /543.139|19.336|
| heading_crop |11/16|0 /4|420|491.052 /617.153|23.587|
| paragraph_max |15/16|none|4422|5523.833 /6848.039|25.846|

**126 full requests,6522 actual scored pairs,203.005 seconds total**, including2707.420ms cold startup. All arms fit the frozen1100-second bound and the requested20-minute finite experiment. E2E is measured around each complete live request, not historical timing reuse or attributed stage addition; row-file I/O and report aggregation occur outside request E2E. Sequential tiny-workload timings are descriptive, not a controlled general speedup claim.

Paragraph aggregation costs **10.529×** the baseline pair count (109–295 pairs/request rather than20), while matching its15/16 selected P@1. The normalized inference cost and actual E2E are reported rather than crediting extra inference as a quality improvement. There is no gain even with that extra inference; an equal-pair paragraph challenger was not run.

Post-score whole selected quote visibility in at least one view/pool parent: raw16/16; heading_spare16/16; crop3205/16; crop64013/16; heading_crop13/16; paragraph_max16/16. Pair-at512 counts are237,307,0,0,0,253 respectively. These are diagnostic selected-quote visibility, not semantic accuracy.

## Paired failures and applicability

- Remaining raw miss `development-011`, Python3.13 `batched(strict=True)` short final batch: full selected proof is visible and present, but UNKNOWN `itertools-0011` outranks expected `itertools-0010`. Heading-spare and paragraph-max do not repair it. Crop640 promotes expected0010, but this is not a net improvement.
- Crop640 simultaneously regresses `development-015`, whether `combinations` distinguishes elements by position or value: it chooses `itertools-0014`, which contains the neighboring `combinations_with_replacement` section and its similar position/value language. Expected parent proof remains visible somewhere in that request. This is a concept-binding regression, not merely crop proof truncation. Do not silently credit the neighboring rule as the asked method's answer.
- Crop320 loses004,008,015,016; heading_crop loses002,014,015,016. Full raw and non-displacing context preserve these outcomes.
- Development's relevant false-choice/operator conditions include `--full-diff`005, merge/default `--patch`008 and strict=True011. All variants keep005 selected-correct; crop320 regresses008 while the other arms keep a selected positive. No API/negation-specific rescue was introduced.
- There is **no explicit “why” rationale question or Rust unwrap/Err false-premise question in this development set**. The old diagnosis motivates these views but supplies no new development evaluation stratum. No claim is made that these experiments repair the old why/false-premise failures; NEW v2 was reserved for the separate review worker.

## Development-only no-answer/logit calibration

Predeclared objective: enumerate unique observed top1 logits plus reject-all; among thresholds with zero development no-answer false accepts, maximize accepted-correct count, then answerable coverage, then higher threshold. Logits are not probabilities. The threshold fitting is an exploratory development diagnostic; **no new refusal rule is selected/exported**.

| View | Threshold (accept logit ≥) | Accepted correct / accepted answerable | Rejected answerable /16 | No-answer false accepts /5 |
|---|---:|---:|---:|---:|
| raw |1.2311344146728516|14/15|1/16|0/5|
| heading_spare |1.5506447553634644|14/15|1/16|0/5|
| crop320 |0.6828725337982178|9/14|2/16|0/5|
| crop640 |2.675171375274658|13/14|2/16|0/5|
| heading_crop |2.4486167430877686|9/13|3/16|0/5|
| paragraph_max |2.690626382827759|14/15|1/16|0/5|

Raw's fitted rule rejects answerable `development-010` alongside all five no-answer questions; it still accepts the011 selected-label miss. Thus accepted-result precision is14/15, not the all-answerable milestone score: accepted-correct/all-answerable is14/16. No general no-answer safety or accuracy follows from fitting5 no-answer samples from this small, correlated development collection.

## Verification, scope and cleanup

- Observed missing-feature RED failures before adding builder, formulas and live runner; subsequent live run passed all3 tests in203.400 seconds.
- Routine rerun:2 unit tests pass,1 opt-in live test skipped. The live test was actually executed separately, not counted from a skip.
- Independent saved-run audit verifies126 unique rows,6522 exact-source views,20 frozen input hashes, unchanged candidate pools, original text hashes, poisoned-label invariance, max aggregation/logit ordering, P@1/no-answer/threshold formulas, all420 non-displacement comparisons and cleanup.
- All original execution artifacts remain unchanged and hashed. New audit/report-review artifacts have their own delivery hash receipt.
- Owned Qdrant PID28348 was terminated/waited; port50476 verified closed. Windows terminate returned1, documented as forced owned shutdown, not graceful exit. No background inference/server remains owned by this experiment.
- Only new `tools/evidence_view_experiment.py`, `tests/evidence_view_experiment_test.py`, this document and the unique evidence-views artifacts were created. No v2 gold/review edits, incumbent edits, vault/private reads, global/shared environment changes, downloads, staging or commits.

**Export decision: retain the prior no-translation identity callable unchanged.** Further accuracy or refusal claims require a new frozen experiment and independent evaluation, not relabeling this development run.
