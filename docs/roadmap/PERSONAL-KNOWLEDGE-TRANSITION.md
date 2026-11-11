# Personal knowledge transition: durable program kickoff

**Decision: start a staged personal-knowledge program, not a migration or activation.** The destination is useful knowledge storage and agent workflows beyond Markdown-only access. The user's **one-to-two-month target is an aspiration, not a delivery promise**: available capacity, corpus size, format mix and judgment effort are unknown. No personal source is authorized by this document.

At kickoff, the bounded SQLite CLI has executed fixture acceptance; resident Qdrant integration and candidate-recall work are **in progress and not delivered until the parent verifies them**. The ≥90% presented-evidence relevance gate has not passed. A roadmap, passing benchmark or closed research task does not establish a working replacement.

## Theme

**Beads `bk-y05` — personal knowledge storage and agent access beyond Markdown-only.** The existing tracker represents Theme as an `epic` with a `theme` label; no custom tracker type/configuration was installed. Beads is the task/status authority; this document is its program contract, not a separate task queue.

### Destination and non-goals

- Replace the need for agents to rely exclusively on direct Markdown file traversal with bounded search, revision-bound retrieval, citations, applicable evidence and explicit abstention. Preserve direct Markdown access as the fallback during rollout.
- Store and recover original sources, canonical revisions and structured knowledge independently of the vector index. Add heterogeneous formats deliberately, not via an unbounded whole-vault import.
- **Replacing Markdown access does not mean deleting Markdown. Original Markdown files and binaries must not be deleted by this program.** Tombstoning an index entry when an externally removed fixture disappears is not permission to remove originals. No automatic canonical pruning or destructive source conversion.
- Personal use only: no banking/GED qualification, enterprise tenancy or certification is a milestone prerequisite. No SLA, deadline, unattended activation, global profile/MCP change, cloud upload or whole-vault acceptance is implied.

## Epic

**Beads `bk-y05.1` — staged reversible personal knowledge access transition.** It stays open until M0–M7 receipts and explicit decisions are verified. Stages are capability gates, not promised calendar weeks. Runtime work can proceed beside relevance diagnostics; neither bypasses the fresh quality gate or personal-data authorization.

### Authority contract: originals → canonical history → derived retrieval

1. **Existing foundations stay authoritative.** Human-edited files own original content. Existing SQLite structured records and `record_history` own findings and transitions; never discard them as an index refresh. Current source/chunk/FTS/vector tables are derived, and the current CLI revision counter is not a retrievable archive of old source bytes.
2. **Required target, not claimed current:** retain immutable original-byte objects and canonical revision manifests under a declared owner independent of Qdrant. Bind stable source identity, revision, original SHA-256, original locator, extractor/chunker/model recipe and normalization/anchor metadata. SQLite may catalog these objects and revisions; do not silently replace existing findings/history or imply that a new fixture database includes them. Define rename and supersession semantics before migration.
3. Qdrant is selected as the **derived search index**, not the source of truth. An index point/payload/score alone cannot establish original bytes, revision, validation state or applicability. Rebuild Qdrant from canonical content without losing records/history. No interoperability assumption about an existing `borg_vault` collection; new owned collections only.
4. Durable SQLite change intent and revision/model/signature-bound upserts/tombstones must converge under idempotent replay. Hydrate candidates from authority, recheck identity/freshness at presentation/get, and withhold stale, deleted or incompatible evidence from actionable use. Unknown applicability is not compatibility; old historical content must be labeled historical, not current.
5. Backups include the coherent authoritative database **and** original/revision objects and manifests. A Qdrant snapshot alone is not a knowledge backup. Retention and eventual physical erasure would require a separate instruction; this program authorizes neither.

## Evidence baseline: what is known versus missing

Historical measurements below were read from retained reports/JSON, **not rerun by this kickoff**. They apply to their own fixtures/corpora, not a personal vault or today's concurrent worker output.

| Evidence | Established result and boundary | Still missing from product acceptance |
|---|---|---|
| [Executed personal-agent readiness](../benchmarks/PERSONAL-AGENT-READINESS.md#executed-personal-use-acceptance--18-october-2026), [raw report](../../artifacts/personal-agent-audit/b925ead048704cbbb58dce5a1e790cb0/report.json) | Existing CLI fixture journey: 21/21 named assertions; explicit ingest, search/get, stale edit, rescan, vector rebuild, deletion status, proposal/validation and backup/reopen. No Qdrant product path in that audited baseline. | Resident operational path, reconciliation/recovery, comprehensive coverage stats, canonical original revision archive, generic record lifecycle and independent relevance acceptance. Concurrent additive runtime may change this boundary only after parent verification. |
| [Paired Qdrant quality](../QDRANT-QUALITY.md), [per-query primary review](../../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/PRIMARY-PAIRED-REVIEW.md) | Identical ordered top5 on 32/32 paired queries. Reused-holdout selected-label P@1 0.5000, MRR@5 0.6111, recall@5 0.7083; 4/4 no-answer questions still receive candidates. Both fail the requested quality gate. | Fresh independent deep judgments, presentation-level precision, useful coverage and abstention. ANN parity/recall and MRR are not answer correctness. |
| [Rerank budgets](../benchmarks/RETRIEVAL-BUDGETS.md), [measured report](../../artifacts/retrieval-budgets/90afd10bbff64c1dae95729d5a745133/measured-v2/report.json) | 1,024 historical requests. Gated budget20 reused-holdout selected P@1 0.6667 and recall@5 0.9167; two explicit incompatible top5 hits, 4/4 no-answer candidate returns. Actual resident harness E2E median 817.282 ms at20 versus 4.884 ms gated without reranking. | No ≥90% acceptance or operational reranker deployment. Timing repeats are not additional independently judged questions. Candidate-pool misses cannot be fixed merely by reranking the same pool. |
| [Document-intelligence pilot](../benchmarks/DOCUMENT-INTELLIGENCE-PILOT.md) | Two public originals/three dependent variants; populated output in 7/9 adapter pairs. PDF header relations fail even when selected numbers survive. | Representative Office, multilingual, table/reading-order fidelity and end-to-end ingestion acceptance; unsupported/degraded formats must be explicit. Number presence is not losslessness. |
| [Architecture](../ARCHITECTURE.md), [operations](../OPERATIONS.md), [hybrid mode](../HYBRID.md), [server benchmark](../SERVER-BENCHMARK.md) | SQLite records/history, explicit allowlists, bounded JSON, point-in-time citation freshness and online backup are existing foundations; resident server timings are experimental harness results. | Product startup/readiness/restart, real agent-call latency, complete semantic coverage, portable canonical exports and Qdrant-loss recovery. Forced Windows process termination does not establish graceful shutdown or durability. |

### Concurrent and existing ownership

| Work | Exact existing task | Coordination boundary |
|---|---|---|
| Resident runtime | `bk-dwx` — in_progress at kickoff | Owner's additive `tools/agent_knowledge_runtime.py` and associated tests/evidence are not edited here. `bk-y05.1.2` depends on it and owns **parent acceptance**, not duplicate implementation. Require actual command transcripts, authority model, lifecycle and cleanup readbacks before counting M1. |
| Candidate recall/depth and exact lexical ablation | `bk-iv7` — in_progress at kickoff | New candidate-recall harness/test/report remain with that owner. Treat all results as pending parent verification and reused diagnostic evidence; feed failure categories into `bk-y05.1.3`, never mark fresh relevance acceptance from this benchmark. |
| Broader relevance/lifecycle backlog | `bk-e6z`, `bk-bkr` — in_progress; `bk-doj` — open at kickoff | Keep existing scopes and ownership. `bk-doj` is the existing revision-safe edit/supersede/withdrawal feature; do not invent these APIs or close it from a reader integration. |
| Completed research fixtures | `bk-d19`, `bk-vp5`, `bk-npj`, `bk-ao9`, `bk-hah` — historically closed | Their scoped evidence is reusable. Closed benchmark work is not program delivery. No existing issue is closed, reopened or reassigned by this kickoff. |

The parent coordinates workers and resolves conflicts. Worker completion claims require exact receipt/code identity, reproducible commands, raw results, failure cases and cleanup readback. Changing a shared model, chunker, corpus or judging recipe requires a separate frozen variant. This document does not certify files merely because they appeared during concurrent work.

## Milestone contract

**Status at kickoff: M0 authored/locally checked, awaiting parent acceptance; M1–M7 not accepted.** Work may happen in parallel only where its dependencies allow. No personal source reads before M5 authorization. M2 may use public/synthetic material before a pilot; personal-scope judgments are separately required after authorized ingestion.

### Kickoff

**M0 · `bk-y05.1.1` · parent accepts the durable kickoff.**

Finite exit: this new contract, exact Theme/Epic/story mapping, current evidence boundaries, explicit authorization steps and read-back-verified tracker records; two editorial passes and machine link/anchor/hash checks retained in the unique evidence directory. Parent checks the handoff before closing even this documentation story. No runtime or relevance completion is inferred.

### Runtime

**M1 · `bk-y05.1.2`, implementation `bk-dwx` · opt-in resident lifecycle on owned fixtures.**

Finite journey: explicit allowlisted index → sync → repeated **actual adapter** search/get/stats → edit before rescan → scan/reconcile → delete/scan/sync → interrupted replay → restart. Pin source/revision/signature/model identities. Observe exactly one encoder load per worker lifetime; separate cold readiness/model-load from warm E2E, query-stage and index-sync costs. Bound queue, message size, requests and timeouts; malformed requests and dependency failure must have defined errors.

Exit evidence: no old revision accepted as current; expected-revision/hash get either matches or refuses; tombstones never resurrect; replay converges; new edits have explicit pending coverage; owned process/port cleanup is read back. Lexical fallback must identify degraded mode, not silently claim Qdrant availability. New canonical snapshot/history claims require reopen checks; retain existing SQLite findings/history. If the additive runtime uses a different schema/database, verify a copy-based compatibility path and compare all incumbent record/history identities before any pilot; an isolated fixture authority is not proof of incumbent-data interoperability. Parent executes the journey, not just unit tests.

### Relevance

**M2 · `bk-y05.1.3` · fresh independently judged presented evidence, not a ranking-score proxy.**

- Freeze source bytes/rights, task/query split, exact presentation unit, cutoff, candidate recipe, model/segmentation, applicability policy and abstention rule before held-out inference. Use fresh question-disjoint questions; the observed 32-question corpus remains diagnostic only. Keep development/calibration separate; inspecting a holdout makes it reused for future tuning.
- Relevance means the excerpt actually answers the question with the correct revision, scope and applicability. Independently judge deeper pools and every presented excerpt; retain UNKNOWN/unjudged rather than declaring it wrong. Unjudged evidence cannot count as verified relevant. Publish original question, ordered top-five candidates, full cited evidence/anchors, judgments, presentation/abstention decision and failure category per query.
- **Required user gate: precision of presented evidence ≥0.90.** Proposed reporting unit: each evidence item actually admitted to agent context, not all raw candidates. Report micro/macro precision, per-query P@1/P@3/P@5 (candidate diagnostics), recall, uncertainty and exact numerators/denominators. Any generated-answer claim requires separate claim-to-evidence judgments; retrieval precision alone does not certify answers or actions.
- **Additional proposed rollout thresholds, not yet user-approved:** answerable-query useful coverage ≥0.80; no-answer false acceptance ≤0.05; zero accepted stale/wrong-version evidence in the evaluated sample. Precision with almost no useful answers fails. Parent/user must approve these thresholds, finite sample size, stratification and uncertainty decision rule **before freeze**; absent that decision, M2 is blocked, not passed by a small point estimate. Report abstention overall and by answerable/no-answer stratum, false rejection and unknown-applicability handling.
- Freeze an adequate finite sample plan with independent reviewer availability and confidence intervals; no promise that a tiny sample certifies a population threshold. No automatic promotion because recall improves or a backend is fast. If a variant fails, diagnose missing extraction/candidate, wrong version, negation, ranking or absent proof, then start a new variant and fresh acceptance set.

Exit: independently inspectable judgments and held-out per-query receipts pass the agreed gate, with coverage/abstention and uncertainty explicitly accepted. A candidate-recall improvement from `bk-iv7` is useful input, not an M2 receipt.

### Ingestion

**M3 · `bk-y05.1.4` · bounded heterogeneous ingestion and source fidelity.**

Freeze a rights-reviewed public fixture matrix covering Markdown/TXT, native PDF, scanned PDF, HTML, DOCX, PPTX and XLSX. For each format declare maximum files/bytes/pages/cells, supported content, exact anchor mapping and success/degraded/unsupported states. Test numbers/units/signs, table/header relations, text/reading order, notes and relevant non-text content independently; do not silently drop unsupported macros/formulas/charts and claim full fidelity. Keep original bytes, normalized blocks, extraction diagnostics and hashes separately.

Exit: per-format inspectable original→block→citation receipts, edit/delete/retry tests, reproducible extraction identity and canonical revision retention. Agree finite fidelity criteria from the fixture gold before execution. Only passing declared formats can enter a pilot; failures either block that requested format or require an explicit user-approved scope reduction. More extraction engines are not a substitute for this contract.

### Agent

**M4a · `bk-y05.1.5` · bounded project-local agent workflow.**

After M1, execute search → revision/hash-bound get → cited evidence → applicability/freshness decision → answer or abstain through a real project-local caller. Record protocol schema/version, retry/reconnect/timeouts, maximum context/results, stable errors and fallback mode. Treat retrieved instructions as untrusted data; they cannot authorize new actions or alter scope. Reads never imply validation or a record write. Reuse explicit proposal/validation contracts; generic edit/supersede/withdrawal remains `bk-doj` until separately accepted.

Exit: repeated real agent-call transcripts and adverse stale/unknown/no-answer/injection-text cases; citations resolve to matching authority; no hidden global registration or provider fallback. This is agent access integration, not permission to replace an entire agent memory stack.

### Recovery

**M4b · `bk-y05.1.6` · backup, restore, portable export and observability.**

- Take a coherent SQLite online backup, immutable original/revision-object copies and a versioned manifest covering schema, extractor/chunker/model identity, object hashes and expected record/history identities. Preserve current database and journals for diagnosis; restore to a **new path**, never overwrite originals or copy a live database file alone.
- Reopen independently; check SQLite integrity/foreign keys, record/history identity, original object hashes, citation mapping and sample get/search. Simulate losing the entire owned Qdrant index and rebuild it from canonical authority, including pending writes and tombstones. Qdrant snapshots may accelerate recovery but must not be required to recover knowledge.
- Export documented portable text/JSON, metadata, revisions, tombstones, source anchors and original bytes; independently reopen and verify a finite representative sample and complete manifest. An export of current snippets alone is not a knowledge/history export. Rehearse replay and rollback after interruption.
- Expose request/error/timeout totals, readiness/restarts/model load count, warm/cold latency distributions, extraction failures, live canonical items, valid/pending/failed/stale/orphan vectors, last successful sync, tombstones, queue age/retries, backup age and last restore outcome. Distinguish global coverage from top-k result counts. Logs should use bounded IDs/status, not unrequested personal content.

Exit: new-path restore/export receipts, Qdrant-loss recovery and history-preservation assertions; parent confirms thresholds for alerting and resource/latency budgets before pilot. These are **required product receipts**, not claimed implemented metrics.

### Pilot

**M5 · `bk-y05.1.7` · explicitly authorized bounded personal pilot.**

Prerequisites: accepted M1–M4 receipts and a user decision naming exact roots/files, exclusions, read/import/write operations, file/byte bounds, permitted formats, storage destination, retention, reviewer access, finite evaluation tasks and stop/rollback conditions. No private/vault read, inventory, hydration or ingestion happens merely to discover this scope. After authorization, show a bounded inventory and obtain the specified import approval; never expand to siblings or the whole vault implicitly.

Exit: authorized bounded import, original-byte and SQLite records/history preservation checks, personal task relevance/coverage/abstention re-evaluation, recoverable backup, explicit limitations and user acceptance. Public evaluation cannot certify this corpus. Stop on authorization mismatch, bad/stale citations, authority loss, recovery failure or an agreed quality regression. No unapproved external egress.

### Comparison

**M6 · `bk-y05.1.8` · parallel read comparison, Markdown still available.**

User/parent freeze a finite representative task sample, source revisions, task success rubric and latency/context budgets. Run current Markdown access and new knowledge access read-only side by side on the same scope. Record paired evidence correctness, omitted context, citations, useful coverage, abstention, task success, elapsed time and failures; capture disagreements rather than average them away. Resolve every critical discrepancy or explicitly exclude the affected scope. Do not introduce destructive dual writing.

Exit: per-task paired report, accepted discrepancy decisions and a copy-based rollback rehearsal. The finite task count, task-success/non-regression criteria and latency/context budgets must be approved and frozen before comparison; unspecified criteria cannot be reported as passed. Failure retains Markdown as default; no authority swap is hidden inside a comparison benchmark.

### Migration

**M7 · `bk-y05.1.9` · separately authorized reversible access switch.**

Only after M6 passes may the user approve changing the **default access route for the bounded accepted scope**. Pin accepted receipts, source/revision manifest, backup/export hashes, compatibility mapping, exact local routing change and previous route. Test switch and rollback on a copy first. Preserve direct file access and canonical revisions; if new writes are later enabled, authorize their owner and conflict policy separately.

Exit: parent verifies actual switched agent calls, matching citations, unchanged authoritative findings/history and original bytes, restore/export availability and successful rollback. User accepts the scoped default; no irreversible migration or original deletion. Roll back for bad/stale evidence, missing accepted source coverage, failed sync/recovery or changed scope; retain discrepancy evidence. Broader rollout requires another explicit scope decision.

## Execution ledger and decisions

Beads keeps the live cursor. Current ledger: **personal transition → kickoff contract → linked historical reports plus unique tracker/readback checks → parent reviews kickoff and concurrent M1/diagnostic receipts → stop this delegation at verified documentation handoff, not program delivery**. Implementation proceeds in the owning issues; do not close someone else's work.

| Contract | Exact created task | Initial status |
|---|---|---|
| Theme | `bk-y05` | in_progress |
| Epic | `bk-y05.1` | in_progress |
| M0 kickoff | `bk-y05.1.1` | in_progress, parent review pending |
| M1 runtime acceptance | `bk-y05.1.2` | open, depends on `bk-dwx` |
| M2 fresh relevance | `bk-y05.1.3` | open; related diagnostic `bk-iv7` |
| M3 heterogeneous ingestion | `bk-y05.1.4` | open |
| M4a agent workflow | `bk-y05.1.5` | open, depends on M1 |
| M4b recovery/export | `bk-y05.1.6` | open, depends on M1 |
| M5 personal pilot | `bk-y05.1.7` | open, depends on M2/M3/M4a/M4b |
| M6 paired reads | `bk-y05.1.8` | open, depends on M5 |
| M7 access switch | `bk-y05.1.9` | open, depends on M6 |

Capacity planning begins with parent estimates of runtime integration, independent judgment effort, format coverage and desired pilot size. Reforecast against the user's one-to-two-month target after these are known; reduce scope rather than skip evidence gates. Immediate decisions: approve the quality/coverage/abstention protocol and reviewer, choose minimum supported formats, and later authorize an exact pilot. No dates or effort estimates are invented here.

## Kickoff evidence and limitations

Unique local evidence: [artifacts/personal-transition/01fcb8ad5fc64899a87301f93cba4d4b/](../../artifacts/personal-transition/01fcb8ad5fc64899a87301f93cba4d4b/). It contains the one-shot tracker creation runner, exact command/response journal, before/after tracker snapshots, returned task map, individual readbacks, editorial review and verification receipt. Re-running the one-shot creator refuses duplicate writes.

First shell `rtk --version` returned `0.48.0`. Existing Beads `1.3.1` was used with `--sandbox`; no initialization, migration, remote sync, global changes or issue closure. The installed GSD CLI is present; `gsd-tools progress json` returned empty phases and `phase_scope=unreadable`. No `.planning` initialization, installation or global repair was attempted. This document is the requested roadmap contract, not a substitute tracker.

This worker owns **only this new roadmap and its unique artifact directory**. No runtime/candidate implementation edits, personal/vault reads, ingestion, service startup, global configuration, installation, staging, Git commit or push. Historical performance/product assertions are cited, not re-executed here. Machine checks validate links, anchors, task hierarchy/status and evidence integrity; two editorial reviews assess scope and gate clarity, not independent relevance, rendered UI or product acceptance. Parent verification remains required.
