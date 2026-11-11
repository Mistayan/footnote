# Final Qdrant retrieval: repaired and exercised, not globally relevance-accepted

## Outcome

The task continued beyond migration: the **actual Qdrant-only search/get JSONL CLI** was baselined, repaired in two finite development iterations, replayed on all 14 retrospective questions, and compared with a competent adaptive direct-file search over the same 595 eligible files. Sixteen cited answers, including two newly identified real conversational subrequests, are delivered in the evidence directory. No cloud inference, downloads, activation, source edits, staging, commit or push occurred.

**Operational repair passes; broad useful-answer acceptance remains unverified.** The bounded observed synthesis supports 11 of the 14 retrospective cases, including three appropriately limited answers, with two historical-version partials and one presentation-evidence partial. The direct arm supports the same substantive outcomes. This is not an unbiased 11/14 model accuracy measurement: the same assistant had already seen the development gold and inspected both arms before writing their shared supported synthesis. No independent-model or fresh-holdout claim is made, and no engine superiority is established.

## Evidence

Run: `artifacts/qdrant-quality/00f85ca0-286e-4e1e-8021-84a5523d24c8/`.

| Artifact | What it contains |
|---|---|
| `answers.md` | Actual useful answers/caveats to all 14 questions plus the two real recent subrequests, with six cited sources |
| `citation-spans.json`, `citations.json` | 32 mechanically checked quote spans, original SHA/revision/source ID, exact decoded-character offsets and source URL ledger |
| `outcomes.json` | Counts recomputed from retained requests/reads, source/artifact checks and final state |
| `ordered-top5.md` | Exact questions and ordered baseline/final/adaptive top-five source excerpts, scores and offsets; unjudged passages remain unjudged |
| `baseline/transport.jsonl` | 42 pre-edit actual CLI searches: original full question under knowledge-hybrid, all-hybrid and all-dense controls |
| `auto2/`, `adaptive2/`, `gets2/` | Final code: full-question search, bounded reformulation and actual source reads, all through fresh SQLite-forbidden resident JSONL subprocesses |
| `final3/` | Repeat/restart control for all 14 questions, stats, chunk read and unsupported documented-version refusal |
| `direct-searches.json`, `direct-refinement.json`, `direct-gets.json` | Real literal/filename discovery, adaptive refinement and bounded direct reads; not the old weak fixed-regex baseline |
| `fresh-tasks.json`, `fresh-final/`, `fresh-direct-*.json` | Two actual quoted user subrequests found in history, frozen before acquisition, and their bounded queries/reads |
| `original-quote-audit.json`, `quote-coverage-summary.json` | Old selected quote visibility versus active snapshot, not semantic precision |
| `tests-final.log` | **21 passing tests in 85.641 s**, including the previous 17 and four new regression tests |
| Per-phase `code-before/after.json`, `argv.json`, `cleanup.json` | Frozen code per batch, guarded subprocess command and owned-process exit/closed-port receipts |
| `protected-before.json`, phase protection receipts | Original sealed evidence hashes; later fixture receipts enumerated separately |

The campaign/adaptation/acquisition/audit/finish helper scripts live under `artifacts/qdrant-quality/`. They are diagnostic tools, not an automatically activated agent integration.

## Repairs actually implemented

### 1. Instruction intent was being filtered out

The old default was `scope=knowledge`, which excludes requested UI/skill instructions before either retrieval branch runs. Simply changing every request to `all` adds skill noise and worsens some ordinary business questions.

`Store.search`, JSONL search and the search CLI now default to `scope=auto`: explicit UI/UX/skill intent routes to `instruction`, mixed process/UI questions keep `all`, ordinary knowledge questions keep `knowledge`, and ambiguous statistics/presentation requests retain both pools. The heuristic is explicit, bounded and overrideable with `knowledge`, `instruction` or `all`; it does not infer authority or execute returned instructions. The original full question is retained. Real-service tests inspect both native prefetch filters before branch caps. Existing filename-based source classification is unchanged, so no collection/payload migration was needed.

### 2. A source hit was not complete answer evidence

Ninety-six-token chunks can identify the correct source while omitting nearby qualifications, missing numbers or contradictions. The refresh source was already ranked first for R05, but its first presented chunk was frontmatter rather than the complete URL correction. Treating that as either a complete answer or an entirely missing source would be wrong.

`get` now supports `start` and `max_chars` (1–65,536) in Store, CLI and JSONL. Reads revalidate the **complete original payload/source identity before slicing**, preserve original hashes, and return a distinct `view` with slice offsets, slice hash, total length and truncation flag. The comparison used at most 14,000 characters per get. Search hits supply `source_id`; actual source gets recovered filters/asof/snapshot/page-1, no-latency proof, and both conflicting BP validation statements. Stale sources still fail closed. Full unbounded-compatible get remains available when no window is requested; bounded options bound the agent response, not Qdrant's internal full-payload read.

### 3. Native RRF ties were unstable across restarts

The first repeat control exposed equal native RRF scores swapping source order and even the selected chunk for a deduplicated source. A failing regression reproduced unstable tie/dedup order. Presentation now sorts **native score descending, then point ID**, before source dedup. Qdrant still performs dense scoring, native sparse BM25 and RRF; this is not Python fusion or a new relevance model. The repaired final 14-question rankings replayed exactly after service restart. This stabilizes the observed bounded returned pool, not an unlimited tie plateau at the native 60-point cutoff.

Graph coverage was checked before edits: `tools/` is explicitly excluded from the available graph. Direct source and usage inspection of Store, CLI, migration runner and tests was the stated fallback, not an invented complete graph analysis.

## Per-case actual answer assessment

Both arms had at most **3 searches × 20 results and 5 gets × 14,000 characters per task**. Final indexed acquisition used 28 searches / 17 gets across the 14 cases; direct acquisition used 17 searches / 15 gets. These are tool counts, not total CPU/I/O cost or efficiency claims. Direct searches scanned only the approved hash-verified file set, used conjunctive literal/filename discovery and refined an overly broad query rather than being forced to use a weak full-question regex. The current task set is small, exposed, and topic-concentrated.

| Cases | Assessment | Material result |
|---|---|---|
| H01 | Supported bounded answer | May 19 Qdrant storage activity is a clue, not proof of completed tests |
| R02 | Partial: historical revision unavailable in active view | Current three-reference/two-comparable-products rule recovered, not misattributed to October 17 |
| R03 | Partial: historical revision unavailable in active view | Current theme matrix differs from old rule; historical wording not silently replaced |
| R04 | Partial: presentation evidence | Measurement/unknown/subjective-score caveats recovered; full old UI presentation contract not established |
| R05–R06 | Supported | Filters retained; asof/snapshot removed; page 1; reported hypothesis, not universal validated optimization |
| R07 | Supported bounded numeric abstention | No user-latency or cost improvement measured in the entry |
| R08–R10 | Supported within note scope | Undecided project relations, maturity-dependent DEMPART circuit and no direct Jira→Conso IA flow |
| R11 | Supported with contradiction preserved | Dated V1 validation and residual V0-not-validated sentence both disclosed |
| R12 | Supported bounded mechanism abstention | Mapping input/mechanism unconfirmed; no deployment-status inference |
| R13 | Supported dated answer | Actual September 29 connected tools distinguished from global registry and parse_partial limitations |
| R14 | Supported current-version contrast | Current UI artifact-quality gates distinguished from individual BP current-process baseline validation |

The old gold is retained unchanged as **development evidence only**. Five selected old quotes are absent from the replacement active UI skill; those are applicability gaps, not five retrieval false negatives. Sixteen exact selected quotes remain in current sources: final indexed source gets expose all 16; direct gets expose 14. The two missing direct quotes are supplementary source citations, not two observed wrong answers. Exact long-quote visibility is a mechanical source-completeness check, **not** precision, exhaustive recall or final-answer success. Many old quotes are longer than a chunk: the initial top-five excerpts containing zero complete selected long quotes is not “0% answer quality.”

The two recent real subrequests came from session `20261021_180320_fafd55`, user message `87116`: IA4IT versus baseline BP, and RIA contributions/mandate/availability. Both arms found the general BP note but not the specific evidence needed for complete answers. Both receive **bounded insufficient-evidence answers**, not two forced successes. Related BP sources were already exposed and the wording was quoted inside a real user reply, so these are genuine conversational subrequests but not an independent holdout.

## Architecture and safety verified

- Final live stats: **595 sources / 16,734 chunks / 17,331 total points**.
- Actual read subprocesses patch `sqlite3.connect` to raise **before runtime imports**. Search, bounded source/chunk get and stats succeed with the final native Qdrant collection. Archive access remains offline-only in audit/import paths.
- A requested unsupported `documented_version=2026-10-17` yields zero results, not fallback to an unknown edition. The initial control used invalid key `version` and was correctly rejected; its failed receipt is retained, followed by a separately named corrected control.
- The initial protection comparator incorrectly treated added disposable test receipts as original mutations. It was repaired to compare **every original hash** and separately list additions; no original protected file changed. Tests produced new small fixture receipts only; no prior receipt was overwritten.
- All **595 live source hashes** stayed unchanged. All **174 historical migration files** also match the pre-existing historical hash manifest, including its saved storage; the 150 separately frozen protected receipt/input files also remain unchanged. The current owned service storage was necessarily reopened by finite read-service runs; it is not claimed byte-immutable while Qdrant runs.
- Current archive SHA: `9dce7cf83983b02a423b628010e70b5d180a134ff67e7eb039f702b2c10b0b6c`.
- Historical archive SHA: `179aa23c7a66e97c61288397cdf10c1f70372c8a3b9b2df87a9fd834f8d6ade3`.
- Final owned services exited and **port 53064 is closed**. No unrelated service was attached to or stopped. The JSON registry was copied byte-for-byte to the new evidence directory so read traces did not append to old logs.

## Disposition

The requested finite repair/comparison loop is delivered, with actual cited answers, real transport, two evidence-driven fixes plus bounded source presentation, full regression execution and explicit failed criteria. **It is not yet justified to replace normal direct Second Brain access globally or claim 80/90% useful-agent success.** The remaining concrete failures are historical-edition availability, incomplete R04 presentation evidence, missing IA4IT/RIA-specific source scope, and absence of an independent frozen final-answer evaluation. More ranking iterations over this exposed set cannot establish those missing proofs. Beads `bk-cw9` remains open for coordinator disposition; there is no “next step only” substitute for the work delivered here.
