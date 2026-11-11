# Query-view calibration — paused; existing top-five evidence audit

## Current boundary

User steering paused fresh candidate data creation and new expensive inference while the parent clarifies the metric contract for realistic agent search success (top-five evidence and iterative retrieval versus first-try top-one). **No new development inference had started.** No calibration threshold was learned or frozen, no new source/question dataset was prepared, and no new model/Qdrant process was started. There is no new blind packet. The existing `2.5` cutoff remains historical and is **not** asserted calibrated for query2.

The proposed development-only helper is present under `tools/query_view_calibration/core.py`, but has only synthetic/unit-test execution. Its proposed family is max-top-parent logit `>= threshold`, answerable coverage at least 80%, no-answer false accepts at most 10% (five development negatives therefore allow zero), minimize accepted wrong selected-positive answerables, then maximize the mean of selected-correct acceptance/all answerables and no-answer rejection, then choose the highest threshold. It reports infeasibility instead of falling back to 2.5. **This is not a fitted rule, a selected system, or a newly agreed user acceptance contract.** Old40 diagnostic verdicts never enter calibration code.

## Existing evidence, depth-five audit

Executed artifact: [`paused-depth-audit-11f688a763c4474292bcd69f256ea089`](../../artifacts/query-view-calibration/paused-depth-audit-11f688a763c4474292bcd69f256ea089/).

All counts below reuse the exposed old52 diagnostic. Denominator: all40 answerable questions, including refusals. The12 no-answer questions are reported separately. No runtime activation or fresh acceptance claim.

| Metric | full2 | query2 | window256x2 |
|---|---:|---:|---:|
| Independently judged raw semantic top1 pass /40 |27|35|35|
| Accepted semantic top1 pass at historical2.5 /40 |26|31|29 (+1 uncertain)|
| Answerable accepted /40 |37|33|32|
| No-answer false accepts /12 |4|1|1|
| Complete frozen selected quote present in a top5 presentation /40 |35|39|37|
| Same top5 selected-quote hits **and** accepted /40 |33|32|32|
| First complete selected-quote MRR@5 |0.604167|0.754167|0.768333|
| Any selected expected-ID Hit@5 /40 |35|39|37|
| Mean per-question selected-ID Recall@5 |0.712500|0.900000|0.900000|
| First selected expected-ID MRR@5 |0.604167|0.735417|0.739167|

### What these measurements establish

- Query2's existing top-five presentations contain a complete exact frozen selected supporting quote for39/40 answerable questions. This measures source-anchored selected-proof availability, not independently judged semantic success across all five passages or final agent answers.
- Actual original-source **presentation text**, offsets and hashes were checked, not only model windows, parent IDs, token-limit statistics or candidate membership. A partial quote, wrong source or mismatching source substring does not count. Presentation completion can expose a quote not wholly inside the raw parent, so quote MRR and ID MRR can differ.
- Hit@5 is the fraction of answerable queries with at least one labeled hit among five. Recall@5 is the fraction of all labeled relevant IDs recovered for each query, averaged over queries. Multiple expected IDs make these values different; neither is exhaustive semantic recall because selected labels are incomplete.
- MRR@5 averages `1 / first relevant rank` (zero if none in five). It measures ranking position and **is not an answer-accuracy percentage**. The quote and expected-ID definitions are explicitly separate.
- The accepted top-five rows honor the existing top1-logit refusal rule; raw top-five availability cannot be silently substituted for usable accepted coverage.
- Only top1 received independent semantic review. Top2–5 can contain useful unlabelled alternatives or misleading evidence, and have no exhaustive semantic judgments. Therefore full semantic Hit@5/Recall@5 remain unknown.
- No generated final answer, citation correctness/completeness, iterative query reformulation, multi-search success or end-to-end agent task success has been tested here. Those are distinct evaluation layers, not retroactive interpretations of these retrieval scores. The original top1 results remain unchanged; a future metric contract must be prospective.

## Provenance and scope inspection

Read existing `rank_input_repair/core.py`, `runner.py`, request-scope compiler and acquisition implementation. Query2 retains the original request for dense/lexical acquisition and tool/evidence records, removes only a matching compiled anchored EN/FR Python provenance clause for the model view, and leaves unsupported syntax unchanged. Scope gates filter Qdrant IDs and SQL eligibility before limits and independently recheck get/presentation. Full2/query2 use two actual segment-slot rounds in original candidate order, maximum parent logit, unchanged passage texts and model tokenization. Re-interleaving duplicate pairs would change dynamic-quantization batch context and is forbidden.

The old16+5 development queries are generally unwrapped; the previous experiment described query2 as identity there. No new wrapped development was invented or counted. Actual new scoped development would still be needed before any calibration conclusion.

## Verification and files

- Four tests pass: threshold constraints/all-answerable denominator/highest tie; infeasibility/nonfinite/missing-strata rejection; original-order batch rounds including five candidates; complete exact-source quote depth rank.
- `audit.py` reads the existing ranked records, packet, mapping, semantic verdicts and source text; writes unique new artifacts only; no inference.
- Successful audit checked780 exact source presentations,156 exact archived top1 packet/verdict identities, and12 historical input files unchanged. Reviewer source identity includes URL, raw hash and normalized-text hash; full archived packet provenance is checked exactly. Reviewer omits nonidentity HTTP/license receipt extras, so its identity fields are compared exactly as a subset, not falsely treated as an identical full receipt.
- Rank order was checked against archived presentation IDs, not a newly rerun ranker. **No new-inference rank parity is claimed.**
- An initial failed audit directory is retained: it stopped on an overstrict full-receipt equality assertion because review records omit HTTP/license extras. Historical fixtures were not modified. Successful audit uses exact identity-field checks rather than weakening hashes/text equality.
- No downloads, installs, environment changes, private/vault access, global/runtime edits, staging or commits.

Run unit tests and read-only evidence audit:

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_query_view_calibration*.py' -v
.venv/Scripts/python.exe -m tools.query_view_calibration.audit
```

Each audit invocation creates a unique directory and retains per-query depth results, report, historical hashes, verification, archived code and an artifact manifest. `per-query-depth-DO-NOT-SEND.json` includes labels/variant mapping; it is **not a blind-review packet**.
