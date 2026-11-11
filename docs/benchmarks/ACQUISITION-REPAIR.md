# Acquisition repair — development improvement, not fresh acceptance

## Outcome

**The 80% first-result milestone and 90% stretch are NOT accepted.** The earlier final is now an exposed diagnostic set. This iteration changes candidate acquisition, not the incumbent runtime, source evidence, or judgments.

Actual resident CPU MiniLM + Qdrant + mMARCO execution improved development expected-proof P@1 from **12/16** to **14/16** with token-safe slices, and **15/16** with the separately controlled existing local French→English lexical pivot. This is development selection on a small, correlated, incomplete-positive benchmark, not semantic accuracy certification. Every development no-answer query is still accepted (**5/5 false accepts**). No fresh validation was run.

Canonical experiment: `artifacts/acquisition-repair/ar-40915afaca8b4fcdb699e70d7ad1b5bf/`.

Callable verification: `artifacts/acquisition-repair/callable-5c52d592f84748658b34d7257f1f7c23/`.

**Final handoff update:** the separately frozen identity-pivot slot control also reaches **15/16** with identical per-question P@1 outcomes and MRR. Translation has **zero demonstrated top1 gains** against that matched control. The final development choice is therefore the simpler **slice96 + original FTS top10 + pool20**, **no translation model loaded**. Its fully live callable was verified on21 requests: `artifacts/acquisition-repair/identity-callable-291d5b8e58d24f50b91a34b97a8a473c/selected-config.json`. The original pivot selection/report below is retained historically, not silently rewritten.

## Frozen protocol and inputs

`execution-freeze.json` was written before model inference. It binds the snapshot, source recipes, relevant code, tests, MiniLM manifest/artifacts, mMARCO receipt/artifacts, Qdrant executable and existing translation model/artifacts. `rerank-selection-freeze.json` records the predeclared development acquisition selection rule before new reranking. All bound inputs were rehashed after execution.

- Snapshot: `artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c`.
- Original corpus: **416** uniform source windows, 1800 Unicode characters, stride 900. All original parent records/text/IDs/offsets/hashes retained.
- Encoder: original `Xenova/paraphrase-multilingual-MiniLM-L12-v2`, revision `2c4055b12046f11709e9df2c122e59ffbdc2f900`, dynamic int8 ONNX, mean attention-mask pooling, L2 normalization, dimension 384, cap 128, no prefixes. **412/416** original parents reach or exceed the cap.
- Ranker: original `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision `1427fd652930e4ba29e8149678df786c240d8825`, pinned int8 artifact, longest-first pair cap 512, CPU intra/inter threads 2/1, batch 4. One resident session; each complete candidate request scored afresh. No Jina, downloads, model replacement, score cache, or new refusal threshold.
- Qdrant: actual owned isolated **1.19.2** loopback server, RAM cosine vectors, HNSW m16/ef_construct100, ef512 query. Every collection reached green and fully indexed counts. Exact point IDs/payloads/vectors were read back; maximum vector error below `1e-6`.
- Original-parent control and both source-wide slice collections use the same **400 point** search allowance, then at most **100 unique parents**, plus FTS5 full-parent original-text BM25 OR top20. RRF k60, one-based ranks, deterministic ID ties. Test distinct-parent candidate budgets **20/50/100**. Point budget is not distinct-parent budget.
- Legacy control uses the first 60 parent points and 60-parent RRF limit with pool20. All **21 development** baseline candidate pools, ordered ranks and raw logits exactly match the earlier bridge run. Its backend measurement reuses the 400-point response truncated to 60; it is NOT an independently timed historical top60 request.

## Source-wide slices and evidence semantics

Slice caps are **96** and **112 total tokenizer tokens**, with 24-token approximate overlap. Boundaries are chosen uniformly over each complete frozen source; no question, relevance label, quote anchor or output score determines a slice. Retokenization of exact source substrings verifies every cap. Source-wide slicing avoids repeatedly encoding the same original-parent overlap.

A slice maps to **all original parents fully containing its exact source interval**, sorted by original ID. If a source-wide boundary would not fit any parent, it is shortened at a source-derived parent boundary. Dense child points sort by descending score then point ID. A parent's first occurrence wins, so multiple children never accumulate extra RRF votes. Tied mapped parents sort by ID. The independent audit validates every mapping and substring hash against frozen corpus/source bytes.

Counts: **1494 slice96 children**, **1215 slice112 children**, plus 416 parents. `source-coverage.json` verifies continuous coverage of **every source character**, independently for all three representations; no gap is inferred away from document-length statistics. `proof-input-coverage.json` uses actual truncated tokenizer offsets, including query/document pair sequence IDs, to inspect proof visibility:

| Exact selected proof visible in at least one expected parent | Development | Exposed diagnostic |
|---|---:|---:|
| Original MiniLM128 visible prefix | 4/16 | 10/48 |
| Original mMARCO512 query/parent pair | 16/16 | 48/48 |

Thus dense truncation really removes many selected proofs, but ranker errors here cannot simply be blamed on its pair cap.

**Parent-label and wholequote-child semantics differ.** A parent is labeled positive only if it contains the entire originally selected quote. Acquiring one short child anywhere inside that parent does not prove that child contains that quote. We preserve these parent labels unchanged and separately measure whether any returned child that maps into the candidate pool contains the complete quote. Some selected quotes cannot fit a short child or straddle its uniform boundaries. No child is retroactively labeled relevant, and unknown parents remain UNKNOWN.

## Isolated acquisition ablations

Counts below mean questions with at least one frozen expected parent in the candidate pool, not correct ranked first results. All answerable questions remain in the denominator.

| Representation / dense parent limit | Candidate budget | Dev pool hits /16 | Diagnostic pool hits /48 |
|---|---:|---:|---:|
| Legacy original128 /60 | 20 | 14 | 38 |
| Original128 /100 | 20 | 14 | 39 |
| Original128 /100 | 50 | 15 | 44 |
| Original128 /100 | 100 | 16 | 45 |
| Slice96 /100 | 20 | 16 | 44 |
| Slice96 /100 | 50 | 16 | 47 |
| Slice96 /100 | 100 | 16 | 47 |
| Slice112 /100 | 20 | 15 | 44 |
| Slice112 /100 | 50 | 16 | 45 |
| Slice112 /100 | 100 | 16 | 47 |

This separates the benefit of a larger parent candidate allowance from token-safe acquisition. Do not attribute the legacy-to-100 change solely to pool size: the legacy dense limit is also different; the three `/100` rows are the matched candidate-size controls. Reranking 50/100 was not selected because slice96 already acquired all development selected proofs at pool20. Ranking gains at larger budgets are NOT claimed.

For slice96, complete selected quote child acquisition is only **7/16 development**, **14/48 diagnostic** at pool20; **16/48 diagnostic** at pools50/100. Parent pool hits are substantially higher, as expected from parent evidence semantics. Slice112 has 7/16 and 12/48 at20, 8/16 and13/48 at50, and8/16 and14/48 at100. These are returned-child visibility counts, not exhaustive semantic labels.

### All language directions — exposed diagnostic acquisition only

| Query → evidence | Original legacy20 | Slice96 pool20 | Slice96 pool50 | Slice96 pool100 | Supplied-proof mMARCO top1 |
|---|---:|---:|---:|---:|---:|
| EN → EN | 18/18 | 17/18 | 18/18 | 18/18 | 13/18 |
| FR → EN | 9/18 | 15/18 | 17/18 | 17/18 | 12/18 |
| EN → FR | 5/6 | 6/6 | 6/6 | 6/6 | 3/6 |
| FR → FR | 6/6 | 6/6 | 6/6 | 6/6 | 3/6 |

The development set has only EN→EN and FR→EN answerable strata. No development improvement claim is available for French-source evidence.

## Actual development reranking

The frozen rule selected slice96/pool20 by development candidate recall, smaller budget, then cap96 tie preference. Reranked matched parent20, slice96_20, legacy20 and a separate paired slice96_pivot20. No diagnostic outcome selected these configurations.

| Pipeline | Dev expected-proof top1 | EN→EN | FR→EN | No-answer false accepts |
|---|---:|---:|---:|---:|
| Legacy20 | 12/16 | 7/8 | 5/8 | 5/5 |
| Original128 dense100 / pool20 | 11/16 | 7/8 | 4/8 | 5/5 |
| Slice96 / pool20 | 14/16 | 7/8 | 7/8 | 5/5 |
| Slice96 / paired local pivot / pool20 | **15/16** | 7/8 | 8/8 | **5/5** |
| Followup identity10+identity10 slots / no translation / pool20 | **15/16** | 7/8 | 8/8 | **5/5** |
| NONDEPLOYABLE supplied-proof oracle | 15/16 | 7/8 | 8/8 | Not run on no-answer |

Slice96 improves three baseline misses (`development-010`, `012`, `016`) but regresses `development-014`; adding the controlled pivot repairs `014`. `development-011` remains an exact-label miss. No posthoc relevance changes were made. The observed 15/16 development point estimate has Wilson95 interval approximately **[0.717, 0.989]**, not a reliable ≥90% generalization claim.

The larger dense parent limit alone regresses French development ranking despite unchanged 14/16 pool recall: candidate membership and competing logits matter. It is retained as a negative result, not hidden by the selected winner.

### Pivot controls and limits

The existing pinned local OPUS French→English model and its existing isolated Python environment were feasible, so no dependency/model download occurred. Only development was translated: **10 actual French translation requests** including no-answer questions. Original English queries use identity. Original query remains the dense query and mMARCO query; only lexical acquisition changes to original10+pivot10, each half RRF mass, with duplicate slots consuming slots and no refill. Candidate budget remains20. This is NOT a translation-generated evidence index or an extra dense branch.

The original campaign froze span/version/operator roundtrip and French-negation checks with failclosed original-query fallback. The exported callable additionally tests exact CLI-flag and assignment preservation, such as `--decorate=full` and `strict=True`; changed versions, flags, assignments or lost explicit French negation are rejected. This strengthening was separately frozen before callable inference and reproduces the selected development pools, logits and rankings on all21 requests. Natural-span translation is not semantic certification: e.g. the unprotected bare option value `short` became `shorts` in one pivot. That known limitation is retained; no new labels or translation-quality acceptance claim follows from passing syntactic checks. Generated pivot text is never evidence.

### Identity-pivot followup: no demonstrated translation benefit

The original20-vs-original10+pivot10 comparison also changes lexical allocation. A new development-only freeze therefore tested **original10+original10**, each half mass, with duplicates consuming slots. This is mathematically original FTS top10 at weight1. It replays saved actual dense responses and performs21 **new actual full-candidate resident mMARCO requests**; it is not a new backend/E2E measurement. Results are in `pivot-identity-bff14d2bf3eb4b368b65e251750efce0/`.

It scores15/16, EN7/8, FR8/8, with **no paired top1 gains or losses from translation**, identical MRR5, and11/11 English pools/scores/ranks equal to the original pivot. The apparent extra pivot gain over original20 can thus be reproduced by smaller lexical depth, not translation. Both pivot and identity repair development014. Retain this negative translation result; do not claim bilingual query translation caused an accuracy gain.

A new frozen **IdentitySearchSession** was then exercised on21 full real requests, reproducing every identity-control pool, score and full ranking. No translation model is loaded and no translation RPC occurs. Cold startup2773.364ms; independently measured resident E2E p50 **1386.628ms**, p95 **1456.488ms**. Compared with the previous pivot callable these are separate sequential small workloads, not a controlled speedup estimate. Final selected declaration: `identity-callable-291d5b8e58d24f50b91a34b97a8a473c/selected-config.json`. The original selection artifact remains immutable.

## Acquisition vs ranking diagnosis

Actual baseline misses, classified without relabeling:

| Baseline outcome | Development /16 | Exposed diagnostic /48 |
|---|---:|---:|
| Correct exact expected first result | 12 | 24 |
| Expected parent missing from pool | 2 | 10 |
| Expected parent present but first result not selected-positive | 2 | 14 |

All answerable questions have at least one expected proof visible in the mMARCO pair; truncation is not the complete explanation for the remaining model/label ranking distinction.

For the nondeployable oracle, append **all supplied expected parents** deterministically to legacy20 and actually rerank the complete request with the same mMARCO. This guarantees an ideal label oracle could reach16/16 dev and48/48 diagnostic. Actual mMARCO reaches **15/16 dev and31/48 diagnostic**. All17 diagnostic oracle misses have a complete expected proof visible to the ranker. Candidate repair alone therefore does not demonstrate an ≥80% first-result system. **31/48 is an observed supplied-pool model diagnostic, not a universal model ceiling:** changing competitors/batching can change scores, and incomplete positives can undercount useful results.

### Per-query examples spanning every direction

Full original questions, expected IDs, every acquisition pool/branch contribution, ordered top-five original excerpts, citations, hashes, offsets, logits and timings are in `PER-QUERY-REVIEW.md`, `acquisition.json`, `rerank.json`, and `independent-audit.json`.

- **EN→EN `test-005`**: “Does the no-store request directive apply only to shared caches, or also to private caches?” Expected `http-cache-0058`; oracle ranks it3, choosing UNKNOWN `http-cache-0059`. The latter contains “applies to both private and shared caches” but begins mid-section and omits the full frozen selected quote. This is an incomplete-judgment/evidence-boundary warning, not grounds to mark it positive now.
- **FR→EN `test-004`**: “Quelle directive de requête HTTP exige une validation réussie avant de réutiliser une réponse stockée ?” Expected `http-cache-0057/0058` absent from legacy pool; even supplied, best expected rank8 behind UNKNOWN `http-cache-0023`. Both acquisition and ranking remain relevant.
- **EN→FR `test-036`**: “When resolving conflicting option strings, is a previous argparse action removed if only one of its aliases is overridden?” Expected `argparse-fr-0020/0021` present; oracle best expected rank2 behind UNKNOWN `argparse-fr-0052`.
- **FR→FR `test-031`**: “Comment argparse peut-il remplacer un argument de ligne de commande par les arguments contenus dans un fichier ?” Expected `argparse-fr-0016` present, oracle rank2 behind UNKNOWN `argparse-fr-0017`. The latter overlaps the behavior and example but drops the beginning of the quote; labels remain frozen.
- **Remaining development miss `development-011`**: “What happens in Python 3.13 batched when strict=True and the final batch is too short?” Expected `itertools-0010` visible and present, rank2; UNKNOWN `itertools-0011` ranks1. Direct source inspection confirms that the latter starts with the `ValueError` behavior and contains the strict implementation/version history. This demonstrates why exact selected-quote P@1 is not exhaustive semantic accuracy. No +1 was added.

## Resident request timing and resources

Main run: **966 acquisition variant rows**, backed by **252 actual Qdrant search requests** (84 questions × three representations), and **148 actual complete mMARCO requests**. Acquisition is shared across budget variants; do not present attributed stage sums as independently measured E2E requests. The main experiment finished in **245.516 seconds**, within its1050-second bound. This excludes later callable verification and unrelated regression tests.

Callable replay separately executes **21 full requests**, each actual translation if applicable → original query encoding → actual owned Qdrant HTTP search → lexical/fusion → original-parent mMARCO → original evidence serialization, without score reuse. It reproduces pools, full rankings and exact raw logits for all21 development requests. Cold startup/index restoration is **6663.3 ms**, not included in resident request latencies.

| Callable stage | p50 ms | p95 ms |
|---|---:|---:|
| Translation (English identity included) | 0.628 | 186.748 |
| Original query encoding | 3.875 | 4.663 |
| Backend | 2.198 | 23.400 |
| Lexical + fusion | 1.483 | 1.981 |
| mMARCO reranking | 1520.581 | 1579.603 |
| Evidence serialization | 0.075 | 0.098 |
| **Actually measured full resident E2E** | **1570.595** | **1716.200** |

Main-run sampled peak RSS: harness **2126987264 bytes**, Qdrant **90144768 bytes**; CPU time523.765625s and1.328125s respectively. ResourceSampler covers the harness/server, **not the separate translation worker**; do not claim whole-process-tree memory/CPU totals. Full timing/resource rows and cleanup receipts are retained.

All owned Qdrant processes were terminated/waited and ports verified closed. Translation workers exited normally. The first two short attempts failed before acquisition (ResourceSampler API mismatch, then stale HTTP connection after offline encoding); their unique directories and cleanup receipts are retained. New code now uses the existing sampler context API and refreshes owned HTTP connections after offline work. No runtime/incumbent helper was edited.

## Callable handoff

Use the verified selected seed configuration and new owned artifact directory:

```python
from pathlib import Path
from tools.acquisition_repair.identity_evaluator import IdentitySearchSession

seed = Path('D:/Projets/BorgKnowledge/artifacts/acquisition-repair/ar-40915afaca8b4fcdb699e70d7ad1b5bf')
new_run = Path('D:/Projets/BorgKnowledge/artifacts/acquisition-repair/NEW-UNIQUE-EVAL-RUN')
# The immutable seed declaration binds the input corpus/models. The final
# identity wrapper overrides query transformation/lexical allocation only.
with IdentitySearchSession(seed / 'selected-config.json', new_run) as session:
    result = session.search('Votre question originale', language='fr')
    # result: pool, ranked, scores, top5, original evidence, stage/E2E timings
```

Call `language='en'` or `'fr'` explicitly; no relevance labels, IDs or expected-answer routing enter the callable. Unsupported languages fail closed. `identity-callable-291d5b8e58d24f50b91a34b97a8a473c/selected-config.json` is the **final no-translation handoff**, binding the identity wrapper, inherited callable, input declaration, control report and21-request exact parity. `callable-5c52d592f84748658b34d7257f1f7c23/callable-config.json` remains the historical pivot-only wrapper declaration. This callable is an experimental Python harness, **not incumbent agent/runtime integration**. It restores pinned saved child vectors with verified hashes into a new isolated real Qdrant server; it does not claim fresh ingestion inference during startup.

## Verification and limitations

- TDD: observed missing-feature failures before implementation for slicing, dedup/fusion, real experiment, preservation/callable, audit, identity slot control and final identity callable. Three ordinary new unit tests plus independent saved-run audit pass; all four opt-in live tests were actually run and passed separately. Routine discovery reports8 tests with4 live skips, rather than falsely claiming skipped live work was rerun.
- Independent deterministic audit replays every acquisition pool, validates3125 source-derived records, checks all mappings/token caps, reads278 artifact hashes, checks exact saved Qdrant vectors, frozen labels, logits/order/evidence, summaries, and cleanup. It is independently implemented code, **not independent human adjudication**.
- Broader legacy `*_test.py` regression discovery ran98 tests with5 errors and13 skips. All5 errors are missing pre-existing optional extraction dependencies (`docling`, `pymupdf`, `bs4`) in the active interpreter; nothing was installed or globally changed. That suite also generated its normal unique fusion/embedding/query/server benchmark test artifacts outside this experiment's canonical directory; those are not used for selection.
- No private/vault corpus, global config, staging, commits, persistent environment changes, new dependency installation or downloads. Existing translator helper uses child-only offline environment settings; parent/global environment is untouched.
- Source hashes and incomplete selected labels remain unchanged. Unknown competitors can be useful; no posthoc positive expansion. No refusal calibration, no generated-answer accuracy, no production acceptance.

## Next bounded work / resource handoff

Development improves enough to justify a **new independently judged validation**, but none was acquired/run in this iteration. Freeze the verified callable and code/model hashes first; do not recycle this old final as acceptance. Include every language direction, version/applicability, operator/negation and genuine no-answer strata. A bare15/16 development result is insufficient, and5/5 no-answer accepts block safe activation.

Before scaling a ranker or candidate pool, independently review a new annotation version's answer-containing adjacent-window boundaries; preserve this exact-label campaign as-is. On development, separate ranking/model applicability failures from incomplete-positive evidence-boundary misses, and evaluate a calibrated no-answer rule with retained answerable coverage. The supplied-proof diagnostic shows that more acquisition alone is not a verified fix for the exposed final. No background task remains running.
