# Fresh selected-challenger acceptance bridge — measured results

**Outcome: neither the ≥80% all-answerable point-estimate milestone nor the ≥90% target was reached. No activation. Parent verification/task closure remains outstanding.**

The first frozen paired final run gives the selected Jina challenger **26/48 =54.17%** exact expected-evidence P1, versus incumbent mMARCO **24/48 =50.00%**. Jina accepts42/48 answerable questions and falsely accepts3/15 no-answer questions. It fails the experimental accuracy and ≤10% no-answer criteria. This is personal evaluation under Jina's CC-BY-NC-4.0 terms, not commercial authorization.

This report supersedes the earlier reports' *execution-status* statement that final remained sealed; those read-only reports, evaluator helpers, source bytes, labels and their historical artifacts were not edited.

## Frozen scope and bridge

- Snapshot: `artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c`;416 original-source windows, width1800/stride900, unchanged corpus and judgments.
- Development21 queries (16 answerable/5 no-answer); final63 (48 answerable/15 no-answer). Final topics remain HTTP caching, collections, French argparse and Rust Result.
- The **already development-selected** `selected-config.json` is passed unchanged to the original `create_evaluator`. Jina int8, pair cap512, uniform complete opening YAML-frontmatter removal for scoring only, batch4, longest-first truncation, CPUExecutionProvider2/1 threads, raw-logit cutoff **≥0**, top5, descending-score/ID tie order. Scores are **not probabilities**. Original evidence is never transformed.
- Acquisition is precisely the **fresh incumbent OR-RRF20**, not the older selection experiment's two-encoder reserved union: existing MiniLM manifest128, dense60 ANN ef128, existing FTS5 `lexical_or`20, equal one-based RRF k60, ID ties, first20. Both rankers receive the identical actual ordered original candidate20. **No applicability/version gate is added**, matching this fresh baseline before and after ranking. Explicit-version failures count unchanged.
- The old selected JSON's `candidate_contract` describes its original acquisition environment. Inspection and live calls established that the exported callable uses only question and caller candidates and does not enforce that metadata. **No path adaptation, config mutation, candidate-ID mapping, new gate, ranking rewrite, threshold fit or challenger reselection was needed.** The declaration explicitly records the fresh acquisition override authorized by the parent.
- Proposed experimental criteria remain P1≥80% over **ALL answerable**, accepted-answerable coverage≥80%, and no-answer false acceptance≤10%;90% is stretch. Empty top5 is rejection, not an omitted query. These are not industrial certification requirements or generated-answer accuracy.

## Declaration before one final release

Development ran first, solely to validate transport and contract. All21 development queries had **bit-exact direct callable versus bridge scores, complete ranks, token counts and thresholded presentation**. The reexecuted incumbent additionally reproduced the earlier development's candidate pools, query vectors, complete ranks and logits exactly. Configuration was not changed in response to development metrics.

The complete declaration binds **31 custom code/model/tokenizer/config/server files**, plus **846 hashed interpreter/runtime-package code/native artifacts**. It includes original encoder manifest, prefixes/normalization, both ranker receipts and all receipt-listed artifacts, actual evaluator/preparation/ranker and imported helper code, new bridge/tests, runtime settings, acquisition, absence of applicability gates, presentation/cutoff, metrics and license limitations. All were checked before execution and independently again afterward.

- Declaration: `artifacts/fresh-challenger-bridge/fcb-20261020-acceptance-01-declaration.json`.
- Declaration SHA256: `f0f67633d49782ece192efbb6b686cc9e0891d1a066a90c8c1cf4585b0140cfa`.
- Snapshot freeze SHA256: `9d5432c634680f3921b40e9c60876b13871d17cacbb1e1730f2b89c0e436aea1`.
- Selected config SHA256, unchanged: `33e5a3974892c743f8ed44c4790955f13f17cb3f829cc9794b57edbc81f4df78`.
- Release readback: **2026-10-20T05:38:46.259452+00:00**; final was independently checked still unexposed immediately afterward.
- First final exposure: **2026-10-20T05:38:57.067267+00:00**. Final was released once, with one actual inference campaign, after the declaration and successful development audit. All future selection must treat it as diagnostic.

| Actual model input | SHA256 |
|---|---|
| MiniLM model ONNX | `66fc00f5f29afcaff34092e1bdd20008ca3918265a82fb9695a551e510cc4ebc` |
| MiniLM tokenizer | `b60b6b43406a48bf3638526314f3d232d97058bc93472ff2de930d43686fa441` |
| mMARCO model ONNX | `6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b` |
| mMARCO tokenizer | `62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626` |
| Jina model ONNX | `c5220cf8fe023f8aa0ed2a3eb787d4451a7f17cf53f6b787e35718dd4b8815c3` |
| Jina tokenizer | `3a56def25aa40facc030ea8b0b87f3688e4b3c39eb8b45d5702b3a1300fe2a20` |
| New bridge | `98128d7662e237133e97e0f3c0fdd788ce093b627697c20339bf51262a4e239f` |
| New bridge tests | `4be183b80e456f08561b4510ef5f47c7b3ca8c1a218f935866f5da60d5c36a16` |

All remaining bound paths/hashes are in the declaration. Model and package downloads: **none**. Existing `.venv/Scripts/python.exe` was used without installation or environment changes.

## Primary measured results

P1 is exact selected-quote hit@1 across all answerable questions, with abstentions counted as misses. UNKNOWN passages are not declared semantically wrong. Bracketed intervals are descriptive Wilson95% intervals.

| Split / pipeline | Correct / all answerable | P1 [95%] | Answerable accepted / all | No-answer false accepts / all | Gate |
|---|---:|---:|---:|---:|---|
| Development / mMARCO |12/16|75.00% [50.50–89.82]|16/16 (100%)|5/5 (100%)|FAIL|
| Development / frozen Jina |11/16|68.75% [44.40–85.84]|14/16 (87.5%)|1/5 (20%)|FAIL|
| **Final / mMARCO** |**24/48**|**50.00% [36.39–63.61]**|48/48 (100%)|15/15 (100%)|FAIL|
| **Final / frozen Jina** |**26/48**|**54.17% [40.29–67.42]**|42/48 (87.5%)|3/15 (20%)|FAIL|

Final Jina accepted precision is26/42=61.90%, **not** the all-answerable milestone. Its6 answerable rejections remain in the48 denominator. Coverage Wilson95% is75.30–94.14%; no-answer false-accept Wilson95% is7.05–45.19%. Final baseline coverage interval92.59–100%; no-answer interval79.61–100%.

Final paired outcomes:21 both correct,5 challenger-only,3 baseline-only,19 neither. Net gain is2 correct questions /4.17 percentage points, not evidence of ≥80% accuracy or a population-level superiority claim. Exact question IDs for gains/regressions are in the independent audit.

Candidate selected-evidence presence is **38/48=79.17%** for BOTH final rankers. Ten final questions have no complete selected-proof window in candidate20. Therefore a ranking-only change on this frozen acquisition cannot attain80% under these frozen selected labels, even with perfect subsequent ordering. This is a diagnostic observation, **not permission to change acquisition or labels on this final**. Development candidate presence is14/16.

| Final pipeline | Selected P3 | Selected P5 | MRR5 | Selected recall5 |
|---|---:|---:|---:|---:|
| mMARCO |0.375000|0.237500|0.618056|0.657986|
| Frozen Jina |0.381944|0.241667|0.618056|0.671875|

MRR is a rank statistic, not answer accuracy. Incomplete selected labels impose P3/P5 ceilings. As a secondary descriptive total only, development+final gives Jina37/64=57.8125% and mMARCO36/64=56.25%; this does not replace the first final-test result or create independent observations.

## Every answerable language direction

Direction is question→expected-evidence language from frozen metadata. No inferred question-language classifier or test-derived mapping was introduced.

| Split | Direction | mMARCO hits / n; P1 [95%] | Frozen Jina hits / n; P1 [95%] | Jina accepted / n | Shared pool proof presence |
|---|---|---|---|---:|---:|
| Development |EN→EN|7/8;87.50% [52.91–97.76]|6/8;75.00% [40.93–92.85]|7/8|8/8|
| Development |FR→EN|5/8;62.50% [30.57–86.32]|5/8;62.50% [30.57–86.32]|7/8|6/8|
| Development |EN→FR|not present|not present|—|—|
| Development |FR→FR|not present|not present|—|—|
| Final |EN→EN|12/18;66.67% [43.75–83.72]|14/18;77.78% [54.79–91.00]|18/18|18/18|
| Final |FR→EN|7/18;38.89% [20.31–61.38]|4/18;22.22% [9.00–45.21]|12/18|9/18|
| Final |EN→FR|2/6;33.33% [9.68–70.00]|4/6;66.67% [30.00–90.32]|6/6|5/6|
| Final |FR→FR|3/6;50.00% [18.76–81.24]|4/6;66.67% [30.00–90.32]|6/6|6/6|

Baseline accepts every answerable question in every stratum. All6 final Jina answerable rejections occur in FR→EN:12/18 coverage, versus18/18 baseline. Gains elsewhere must not hide that regression. Full per-stratum coverage intervals and selected recall are in `fcb-20261020-acceptance-01-independent-audit.json`.

No-answer question-language counts (no evidence language is asserted):

| Split / language | mMARCO false accepts | Frozen Jina false accepts |
|---|---:|---:|
| Development / EN |3/3|1/3|
| Development / FR |2/2|0/2|
| Final / EN |8/8|1/8|
| Final / FR |7/7|2/7|

The3 final Jina false accepts are retained, not repaired:

- `test-no-006`: « Quelle clé secrète signe les réponses de notre cache ? » → `http-cache-0012`, raw top logit0.020127221941947937.
- `test-no-007`: “What exception will namedtuple._replace raise in Python 3.99 final?” → `collections313-0042`, raw top logit0.1333664059638977.
- `test-no-008`: « Quel sera le comportement de Counter.elements dans Python 4.2 ? » → `collections312-0014`, raw top logit0.23012599349021912.

The fresh baseline has no applicability gate. Unsupported-version false acceptance is disclosed without adding one posthoc.

## Actual execution, latency and cleanup

Each split used a new **real isolated Qdrant1.19.2 server**, fresh vectors encoded from the416 original corpus passages, green HNSW indexing of416 vectors, full ID/vector/payload readback and <1e-6 conversion error. One resident encoder, one original mMARCO ranker and one frozen Jina ranker per run. No local-client substitute, saved-score replay, external API or generated predictions were used for the live comparison.

- Development:21 actual acquisitions,42 primary full-candidate ranker requests plus21 extra full Jina direct-call parity requests;176.421s measured loop,2470.163ms model validation/load,5307.651ms offline encoding/indexing.
- Final:63 actual acquisitions,126 primary full-candidate ranker requests;300.234s measured loop,2398.754ms model validation/load,5314.590ms offline encoding/indexing.
- Total primary168 result rows;189 actual full-candidate rerank calls including development parity. Original returned evidence:180 development/540 final records. Full original candidate evidence:840 development/2520 final records.

**Acquisition is shared once per question for a strictly paired pool.** Rerank latency is measured for each actual full request. “Attributed pipeline” is the per-question shared acquisition + that ranker's measured rerank + evidence JSON serialization, **not an independently measured end-to-end request or production transport latency**. Development parity calls are excluded from the primary latency distributions, but included in loop wall time. Ordering is baseline then challenger, not randomized.

| Split / stage | mMARCO p50 / p95 ms | Frozen Jina p50 / p95 ms |
|---|---:|---:|
| Development / shared acquisition |18.462 /29.141|same acquisition|
| Development / rerank |1352.275 /1369.815|3527.311 /3557.029|
| Development / attributed pipeline |1367.668 /1392.108|3547.611 /3578.106|
| Final / shared acquisition |20.054 /29.527|same acquisition|
| Final / rerank |1333.422 /1387.857|3520.965 /3559.770|
| Final / attributed pipeline |1353.295 /1400.347|3537.914 /3575.930|

Owned development Qdrant PID18180/port51969 and final PID12124/port52040 were terminated/waited and independently checked absent/closed. Return1 is Windows forced termination, **not graceful shutdown or crash-durability acceptance**. No unrelated process was stopped and no background campaign remains.

## Evidence and verification

Artifact prefix: `artifacts/fresh-challenger-bridge/fcb-20261020-acceptance-01`.

- `-development/` and `-final/`: execution freezes, candidate declarations, actual query vectors, raw HTTP responses, complete dense/lexical/pool/reranker ranks and raw scores, question constraints, original-source candidate text and IDs, original returned evidence with URLs/raw+excerpt hashes/offsets, per-stage timings, original passage vectors, server readbacks/config/log/cleanup, aggregate intervals, full `PER-QUERY-REVIEW.md`, and evidence SHA256 manifests. Rejections have empty presented evidence while their20 scored original candidates remain available.
- `-development/development-callable-parity.json`: all21 exact direct-call parity checks and incumbent prior-run parity.
- `-final-audit.json`:126 rows/63 queries,540 presented evidence and2520 candidate records;31 bound code/model/config files plus846 runtime artifacts unchanged; owned PID/port independently closed.
- `-audit-report.py` and `-independent-audit.json`: separate stdlib recomputation of denominators, cutoff, source spans/hashes, labels, language directions, paired wins/losses, Wilson intervals and summaries. **PASS**. This is independent arithmetic/provenance auditing, not independent human semantic annotation.
- `-scorer-receipt.json`: actual retained predictions also passed through the unchanged external scorer. Incumbent score run `artifacts/fresh-multilingual-evaluation/scores/79d285fcdee74fbc816b8f78dd9639c4`; challenger `.../scores/3eca589c1660419ea56d595ba13c3c20`. They reproduce24/48 and26/48 respectively. This extra step is explicitly **scoring replay**, not another inference campaign.
- New bridge TDD: first test failed with missing bridge import; candidate validation/declaration tests then failed for the absent behavior; runner/auditor availability failed before implementation. GREEN unit tests followed, then the actual development and final receipt integrations. Retained `-development-tests.log` and `-final-tests.log`:5/5 PASS with the requested live receipt, no skips.
- Existing fresh evaluator focused suite:3 PASS,1 opt-in integration SKIP. Existing accuracy iteration suite:7 PASS,7 opt-in integration SKIP. Separate logs retained; skips are not claimed as new integrations. No whole-application regression claim.
- Frozen source, model, tokenizer, config, helper and judgment hashes verified unchanged after execution. No post-observation label changes. No private/vault ingestion, global config, staging, commit or push.

### Commands (repository root; no install)

```bash
P=artifacts/fresh-challenger-bridge/fcb-20261020-acceptance-01
# Executed ONCE, in this order; do NOT rerun release or infer again as a fresh test:
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/fresh_challenger_bridge.py run \
  --split development --run "$P-development"
env -u PYTHONPATH BK_BRIDGE_RUN="D:/Projets/BorgKnowledge/$P-development" \
  .venv/Scripts/python.exe -B tests/fresh_challenger_bridge_test.py -v
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/fresh_challenger_bridge.py release \
  --development "$P-development" --candidate "$P-declaration.json"
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/fresh_challenger_bridge.py run \
  --split test --candidate "$P-declaration.json" --run "$P-final"
# Repeatable read-only verification:
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/fresh_challenger_bridge.py audit --run "$P-final"
env -u PYTHONPATH BK_BRIDGE_RUN="D:/Projets/BorgKnowledge/$P-final" \
  .venv/Scripts/python.exe -B tests/fresh_challenger_bridge_test.py -v
# Reporting audit only; overwrites its own derived audit JSON, never ranking/labels:
.venv/Scripts/python.exe -B "$P-audit-report.py"
```

## Acceptance boundary and next owner

**Point-estimate objective: NOT REACHED. Population certificate: NOT ESTABLISHED. Activation: NOT PERFORMED.** Even a measured80% would only have been a small-sample selected-evidence milestone. Here neither80% nor90% is observed. The48 final answerable questions are below60 by themselves;64 exists only across development+final. Repeated questions within sources, bilingual paraphrases, overlapping windows, author-selected incomplete quotes, UNKNOWN alternatives and mutable French source URL pinned by bytes limit generalization. Wilson intervals are descriptive, not IID guarantees or private-vault certification.

The decisive measured failure mechanisms are frozen-pool proof absence (especially FR→EN), further ranking misses, answerable rejection, and remaining unsupported/private no-answer acceptance. No new variant was selected from these observations. Final is now diagnostic for future selection. Parent owns verification and task closure; any next experiment needs a separately authorized resource bound and new independent final judgments, not relabeling or tuning to this result.
