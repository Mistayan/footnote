# SecondBrain migration — relevance acceptance **NOT PASSED**

Evidence: `artifacts/migration-quality/ccd26034-a796-47a6-8274-1c3aa3e7f1a7/`. Read-only authority remains `artifacts/migration/full-20261021/authority.sqlite`, SHA-256 `179aa23c7a66e97c61288397cdf10c1f70372c8a3b9b2df87a9fd834f8d6ade3`.

## Decision

**Do not archive/delete originals or activate this as a replacement.** Preservation/ingestion verification passed previously; this quality assessment does not accept partial success. The real historical request remains unresolved, important existing facts are missed, and retrieved instruction/topic matches often lack answer evidence. No source code, model, index, migration run, agent config or vault file was modified. No server was started, model invoked/downloaded, cloud inference/API used, or staging/commit/push performed.

## What was actually judged

- **14 frozen questions: one genuine historical subrequest (H01), thirteen reconstructed documentary questions.** No claim that thirteen recent genuine tasks were validated. A session-history search was attempted before any request for more history; it recovered already-known deployment/prototype discussion, not an admissible original completed-test receipt. Session results were not used as factual gold.
- All **42 existing mode rows / 210 top-five passages** were manually read and labeled individually, with a question-specific reason. Another **70 direct-file-baseline top-five spans** were manually inspected: **280 judged presentations total**. Larger baseline get bodies remain unjudged, not zero-relevance.
- Independently searched original file bytes, not indexed summaries/chunks/FTS: retained source revisions under the exact final eligible manifest, then safe read-only live-file validation of all **595** approved MD/TXT paths, with identity/reparse/hardlink/size/secret checks and exact SHA agreement. No excluded directory was traversed or linked project dependency followed.
- `gold.json` contains manual documentary answers/refusals, exact original path/revision/SHA-256/decoded-character offsets/quotes and applicability limits for all fourteen. `independent-source-search.json` records search expressions, searched population, candidates and truncation-free selected original matching windows. That pool is selected, **not exhaustive semantic gold**.
- Historical pinned content for UI, refresh and BP matches original hashes exactly; MCP differs only CRLF versus LF, whose decoded-normalized SHA matches its frozen historical source receipt. No Git/vault history was read or changed.
- Labels were made **posthoc after retrieval exposure** by this assistant, not blind, held-out, independent-human or fresh acceptance. The seal is an auditability boundary, not certification of label correctness.

## Presented-passage relevance

Relevant means the span directly supports at least one material, applicable question-specific fact or justified refusal. Partial support counts as relevant, but not full answer success. Correct-note headers, links alone, generic policies substituted for historical/project facts, wrong versions/dates and topical overlap do not count. Unknown would remain null; all evaluated top-five spans here are judged.

P@5 = relevant presented passages / 5. MRR@5 is a rank statistic, not answer precision. Coverage = at least one material span, not task completion. FP = irrelevant retrieved passage, not false generated recommendation. **No generated answers were produced or scored.**

| Mode | Relevant / judged | P@5 | MRR@5 | Material-evidence queries /14 | Strict answerable coverage /11 | FP | Full documentary proof sets /14 | Median / max ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 13/70 | 18.57% | 0.4464 | 7 | 7 | 57 | 2 | 160.15 / 210.44 |
| dense | 12/70 | 17.14% | 0.4167 | 9 | 8 | 58 | 4 | 149.10 / 229.57 |
| hybrid | 17/70 | 24.29% | 0.4310 | 8 | 8 | 53 | 3 | 160.25 / 270.67 |
| direct-lexical-diagnostic | 0/70 | 0.00% | 0.0000 | 0 | 0 | 70 | 0 | 230.97 / 279.90 |

Strict positive-answer denominator excludes H01 (insufficient original test proof), R07 (no measured numerical gain documented) and R12 (mapping mechanism explicitly unconfirmed). Those last two still have valid documentary refusal evidence: dense retrieves R12, no mode retrieves R07. Full-proof labels concern the requested bounded documentary evidence, **not actual task completion or independently verified implementations**.

### Keep the historical and reconstructed outcomes separate

- **H01 alone:** BM25, dense and hybrid each have P@5=0, RR@5=0, coverage 0/1 and five false positives. No recent genuine task-success claim is supported.

| Thirteen reconstructed questions only | P@5 | MRR@5 | Evidence coverage | Relevant / judged | FP |
|---|---:|---:|---:|---:|---:|
| bm25 | 20.00% | 0.4808 | 7/13 | 13/65 | 52 |
| dense | 18.46% | 0.4487 | 9/13 | 12/65 | 53 |
| hybrid | 26.15% | 0.4641 | 8/13 | 17/65 | 48 |
| direct-lexical-diagnostic | 0.00% | 0.0000 | 0/13 | 0/65 | 65 |

### Same-note duplication

Collapse repeated paths only within the already-presented five passages; a source is useful if any of its presented passages contributes evidence. Precision denominator is the **actual unique-source count**, not five. This is not a fresh retrieval of five distinct notes, not complete-note relevance and not an excuse to label every chunk of a relevant note positive.

| Mode | Unique source occurrences | Useful source occurrences | Mean per-query unique-source precision | Unique-source MRR |
|---|---:|---:|---:|---:|
| bm25 | 51 | 8 | 22.26% | 0.4464 |
| dense | 50 | 11 | 26.31% | 0.4286 |
| hybrid | 47 | 13 | 36.55% | 0.5143 |
| direct-lexical-diagnostic | 38 | 0 | 0.00% | 0.0000 |

## Per-question result, not 42 nonempty-row smoke claims

Each cell is **relevant passages /5 · RR@5 · documentary sufficiency**. Full ordered excerpts, all negative reasons, SHA/offset citations and gold quotes are in `PER-QUERY-REVIEW.md`; machine-readable labels in `judged-replay.jsonl`.

| Question | Classification | BM25 | Dense | Hybrid |
|---|---|---|---|---|
| H01 | insufficient-evidence-in-reviewed-eligible-pool | 0/5 · 0.000 · none | 0/5 · 0.000 · none | 0/5 · 0.000 · none |
| R02 | answerable-documentary | 2/5 · 1.000 · partial | 1/5 · 0.333 · partial | 3/5 · 1.000 · partial |
| R03 | answerable-documentary | 0/5 · 0.000 · none | 0/5 · 0.000 · none | 0/5 · 0.000 · none |
| R04 | answerable-documentary | 1/5 · 1.000 · partial | 2/5 · 1.000 · full | 3/5 · 1.000 · full |
| R05 | answerable-reported-case | 0/5 · 0.000 · none | 1/5 · 0.500 · full | 0/5 · 0.000 · none |
| R06 | answerable-documentary | 1/5 · 1.000 · partial | 2/5 · 1.000 · full | 3/5 · 1.000 · full |
| R07 | unanswerable-numeric-explicit-documentary-absence | 0/5 · 0.000 · none | 0/5 · 0.000 · none | 0/5 · 0.000 · none |
| R08 | answerable-vault-note-only | 3/5 · 1.000 · partial | 0/5 · 0.000 · none | 2/5 · 0.500 · partial |
| R09 | answerable-vault-note-declaration | 2/5 · 1.000 · full | 2/5 · 1.000 · partial | 1/5 · 1.000 · partial |
| R10 | answerable-vault-note-declaration | 0/5 · 0.000 · none | 1/5 · 0.500 · partial | 1/5 · 0.200 · partial |
| R11 | answerable-documentary-conflict-unresolved-act | 3/5 · 1.000 · full | 1/5 · 0.250 · partial | 2/5 · 1.000 · full |
| R12 | unanswerable-mechanism-explicit-documentary-unknown | 0/5 · 0.000 · none | 1/5 · 0.250 · full | 0/5 · 0.000 · none |
| R13 | answerable-dated-documentary | 1/5 · 0.250 · partial | 0/5 · 0.000 · none | 0/5 · 0.000 · none |
| R14 | answerable-cross-domain-documentary | 0/5 · 0.000 · none | 1/5 · 1.000 · partial | 2/5 · 0.333 · partial |

## Concrete findings and source boundaries

1. **H01 is not merely a missing vector hit.** Independent literal `Qdrant` search over all 595 eligible originals finds 217 occurrences across four files. The original `200 Notes/AI Log/sync_log.txt` (SHA `de35731c7ca17a9e1eafbb701177179a3aaeea3fd914490f2334b20cea20bb73`) records May 19 storage creation/change. This is a pre-request **deployment-activity clue**, not a completed-test/performance receipt. The other matched documents are a current research summary, knowledge map and watchlist. The current summary postdates the historical request and is inadmissible as historical gold. This does not prove absence under every synonym or excluded descendant. Hidden `.qdrant_storage` itself and external project experiment receipts are **outside eligible scope**, not searched/followed/ingested.
2. **Existing answer evidence is missed:** R03 requires full dark journeys, targeted light checks and at least two QLoop passes; original UI skill contains all of this, yet all fifteen presented mode hits are irrelevant. R07 explicit “Ni latence utilisateur ni coût mesurés” is in the eligible refresh entry; all modes miss it. These are retrieval failures, not absent knowledge.
3. **Fusion can lose real proof:** R05 dense rank 2 presents filters retained, `asof`/`snapshot` removed and page 1, including the no-code-replay caveat. Hybrid instead presents that note’s header at rank 1 and generic URL/warehouse/brainstorming material. Correct source acquisition is not passage sufficiency. R12 dense rank 4 retrieves the explicit mapping unknown; hybrid does not.
4. **Useful originals:** R04 dense/hybrid retrieve the exact source/freshness/denominator/unknown/text-alternative rule; R06 dense/hybrid recover the announced-version/no-generalization and hypothesis limits. R11 BM25/hybrid expose both dated V1 validation and the residual V0-not-validated sentence rather than erasing the conflict. R09 BM25 alone presents the actual less-mature-entity DEMPART exception and ASI Go/No Go.
5. **Do not overclaim original authority:** BP source is the eligible project note, which explicitly says it references rather than copies canonical external process documents. Its interview facts are source-reported declarations, not audited business enforcement. Baseline V1 act, underlying interview/process artifacts and related-project canonical documents are outside the eligible manifest; they were not followed. The reported refresh’s source report/evidence JSON are likewise outside this MD/TXT evidence pool. Documentary unknowns are not universal absence.

## Direct file-search baseline — executed, but no fair agentic winner

`baseline-freeze.json` pins the deterministic adapter/policy before its run. It receives only the original question, never source hints, expected quotes or gold. Three searches per task, first 20 matching lines per search, preview ≤500 chars; five first-distinct-path gets per task, each ≤12,000 chars. Corpus is the same 595 safely read live originals matching frozen revisions. Actual total: 42 searches, 70 gets, 70 manually judged top-five presentations. Logs retain every expression, first-20 truncation, span, get and elapsed time.

Its observed top-five P@5/MRR/coverage are zero. This is a **weak fixed regex-OR + ordinal-path development diagnostic**, not a competent adaptive file-search agent. Short identifier substring matching (BP matching `subpath`/`SUBPROCESS`) and early skill-path saturation are concrete adapter failures. Do not tune this sealed baseline retrospectively or claim it demonstrates index superiority. The 70 larger get bodies are unjudged/unknown; no get evidence or final-answer accuracy is claimed.

**Matching limitation:** existing indexed replay performs one full-question search returning five small chunks and per-chunk get. The filesystem adapter uses three fixed derived expressions and whole-note gets under the same maximum ceiling. Neither is a matched iterative answering agent; presentation/acquisition differ, and manual source discovery had a separate adjudication budget. Fair automatic task-success comparison is **not established**. No model/provider was pinned or invoked; authorization for cloud inference was not assumed. The next paired trial needs frozen answering/iteration policies and independent new judgments.

Indexed latency is the existing small sequential resident replay, including freshness/citation checking. Filesystem diagnostic latency is three in-memory text scans plus get slicing after separately timed safe source loading/hash verification (`direct-files-read.json`). These are different workloads; no speedup or backend winner is claimed. Median means conventional middle-pair median, with upper-middle values separately retained in JSON.

## Next engineering blocker — scope and evidence granularity, not archive readiness

- Path-prefix diagnostic: **283 sources / 6618 chunks** are `.claude`, imported Claude skills or `999 Review/AbsolutelySkilled-staging`; another **35 sources /702 chunks** are canonical `AI-Agents` documents, often useful when the question actually requests skills. This is heuristic categorization, not semantic authority. All **595 source metadata records are empty `{}`**, and no query kind/scope is enforced in the replay.
- All fifteen R03 hits, and H01 hybrid’s generic evidence-workflow hits, show that merely seeing a relevant-looking word does not recover actual evidence. Noise also comes from unrelated ordinary notes: instruction pollution is an evidenced failure category, **not a proven sole cause**.
- Proposed generic development branch: explicit, reversible `kind`/`scope` metadata and user-visible knowledge-versus-instruction routing enforced before both lexical/dense candidate caps and at get. Keep skills available for requested skill questions; do not simply remove `AI-Agents`. Add distinct-source acquisition and nearby proof-window presentation as separate ablations, preserving original bytes and authority.
- **No source code/model/scope change or tuning trial was performed in this assessment.** The frozen baseline and exposed diagnostic labels must not become a claimed fresh holdout. A future variant must be selected on development and evaluated on new independently adjudicated tasks, including genuine history and explicit unknowns, under the bounded final-answer/citation rubric.
- Remaining acceptance blocker: reliable complete evidence and useful final answers/citations under matched budgets, including H01 original dated evidence or justified bounded abstention. Ingestion/preservation and nonempty retrieval do not meet the user goal.

## Artifacts and read-only verification

- `artifacts/migration-quality/ccd26034-a796-47a6-8274-1c3aa3e7f1a7/gold.json`, `manual_labels.json`, `judged-replay.jsonl`, `metrics.json`, `PER-QUERY-REVIEW.md`.
- `originals.json`, `supplemental-originals.json`, `independent-source-search.json`, `direct-files-read.json`: retained original source pool and direct-file receipts.
- `baseline.py`, `baseline-freeze.json`, `baseline.jsonl`, `baseline-review.txt`: automated baseline, freeze and actual results.
- `pollution.json`, `inputs.json`: heuristic corpus composition and historical-input identities.
- `seal.json` hashes task-local artifacts plus this report after direct-source adjudication. `verify.py` verifies hashes, exact source quotes/hit offsets, all counts and aggregate relevance metrics, authority integrity, and unchanged completed migration evidence **without writes or service startup**.

```bash
PYTHONDONTWRITEBYTECODE=1 python artifacts/migration-quality/ccd26034-a796-47a6-8274-1c3aa3e7f1a7/verify.py
```

Preservation remains a separate gate: all 595 originals are retained and live hashes matched; completed full-run files remained byte-identical. There is **no partial acceptance, archive permission, activation or universal ≥80%/≥90% success claim**.
