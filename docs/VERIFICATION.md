# Verified pilot delivery

## Current hybrid acceptance

[Hybrid implementation, source-bound receipt, raw evidence and limitations](HYBRID.md) is the current acceptance: 14 Rust tests, real OCR test, 2 metric tests, strict Clippy/format/build and dependency checks passed. The opt-in hybrid release CLI was evaluated against FTS5 and isolated Qdrant-client local exact stores on the same 1,000 synthetic documents and two pinned multilingual models. Holdout macro R@5 was 0.286 lexical vs 0.929 hybrid; P@5 was 0.057 vs 0.200. Every hybrid no-answer case still returns candidates. No global activation, real-vault quality, server benchmark or storage-engine verdict is claimed.

The original schema-3 pilot is retained unchanged; use the schema-4 copy linked from [README](../README.md). Migration/rebuild preserved authoritative rows and backup/restore was exercised. New receipt: [803ba94aa98b4f628abb4feb4557a323](../artifacts/hybrid-acceptance/803ba94aa98b4f628abb4feb4557a323/receipt.json). Historical numbers below refer only to their earlier source/binary hashes and must not be presented as current schema/build behavior.

## Historical lexical/OCR acceptance (before hybrid)

Source-bound receipt: [`artifacts/verification/384fbf64722c40c3a36e32ad9ac3b910/receipt.json`](../artifacts/verification/384fbf64722c40c3a36e32ad9ac3b910/receipt.json). Each future `tools/verify.py` run gets a unique directory; [`latest.json`](../artifacts/verification/latest.json) is navigation only. The receipt binds hashes for every Rust/Python/test/build input before and after execution; sources stayed identical during this run.

`tools/verify.py` completed all four steps with exit code zero: full quality gate, real scoped evidence import, persistent PDF/image/text demo, and synthetic lexical benchmark.

| Gate | Observed result |
|---|---|
| `cargo fmt --check` | Passed |
| `cargo clippy --locked --all-targets -- -D warnings` | No issues |
| `cargo test --locked --all-targets` | **9 passed, 0 failed, 7 suites** |
| `cargo build --locked --release` | Passed, optimized Windows executable |
| Real PNG/scanned-PDF OCR release test | **1 passed**; actual packaged RapidOCR/ONNX inference, original hashes unchanged |
| Python AST parse | 6 source/test modules passed |
| `git diff --check` | Passed |
| SQLite runtime | **3.51.1**, FTS5 compile option true; schema 3 |
| Real imported findings | 2 proposals, exact pinned evidence current; duplicate import returned the same IDs |
| Persistent demo | 3 source files, 5 chunks, no extraction failures; PDF page 1 and real OCR page 2 returned |

The retrieval engine's bundled SQLite **3.51.1** is not the imported finding's tested SQLite **3.53.1**. The latter is applicability metadata, not the engine runtime. Rust was `1.99.0`, Cargo `1.99.0`, RTK `0.48.0`; project extraction dependencies are locked, including pypdfium2 `5.15.2` (PDFium), RapidOCR ONNX `1.4.4`, ONNX Runtime `1.31.0`. PyMuPDF `1.28.2` was replaced by pypdfium2 on 2026-11-11 to remove an AGPL-3.0 dependency from the runtime; measurements in this document that predate that change were taken with the PyMuPDF extractor.

Release executable: `target/release/borg-knowledge.exe` (2,889,216 bytes). SHA-256: `2861da7d04d9c38299a971a6f3dd05d729875fe2851b0c7cd6d8d70e5bb65594`.

## Covered behaviors

Black-box Rust tests exercise exact hash/heading/line citations, stored prompt-injection text remaining data, real PDF text page provenance, invalid-image failure rather than empty success, title-context retrieval within child sections, unchanged incremental reuse, content deduplication, stale hashes, rename/delete tombstones, read-only search/stat database-byte preservation, Unicode long-line tails, scope rejection, private/credential exclusions, literal FTS operator input, query limit rejection, future-schema refusal, proposal deduplication, revision-bound validation with hashed evidence, exact incompatible-version exclusion, stale proof detection, live FTS5/status stats, and coherent backup/restore opening of a database larger than 16 MiB with overwrite refusal.

The separate release OCR test generates its own PNG and scanned PDF and verifies transcribed terms, file types, 1-based page references, unchanged originals and incremental reuse. Persistent demo sources include a real PDF text layer, an OCR-only image page, a PNG, and a Markdown prompt-injection sentence explicitly labeled synthetic untrusted fixture text. No performance data is invented in those fixture documents.

Initial RED failures were observed for the missing text index, missing binary ingestion, missing proposal API, content deduplication/long-line-tail defects, missing backup API, title-context omission, missing status/FTS reporting and oversized-backup verification. Those failures were repaired before the aggregate green run.

## Actual CLI readback

Pilot DB: `D:/Projets/BorgKnowledge/artifacts/demo/knowledge.db`.

```text
search substr --technology 'Python/SQLite' --tested-version sqlite=3.53.1 --status proposal --limit 1
→ record id 2, revision 1, status proposal, evidence_freshness current
  root_cause: SQL materialized substr(body,1,4097) for heartbeat/lifecycle receipts ...
  exclusions: Not production health or global performance. Campaign preservation NOT_CERTIFIED; writer UNKNOWN.

search rustcheckpoint
→ chunk id 4, sample.pdf, page 1, line 1, freshness current
  Rustcheckpoint source citation: owned synthetic PDF fixture.

search 'local ocr'
→ ocr.png page 1 AND sample.pdf page 2, freshness current
  LOCAL OCR CHECKPOINT SAMPLE
```

`get-record 1` and `get-record 2` were independently read back after import; their outputs are in `artifacts/record-1-readback.json` and `artifacts/record-2-readback.json`. Demo/import receipts preserve full returned citations and source/evidence hashes. The four authorized BorgInvestor evidence originals were rehashed unchanged after copying; the raw archive passed ZIP CRC verification. No live trading registry was opened.

## Measured lexical baseline — not a production speedup

1,000 owned synthetic Markdown files; eight fixed labeled queries, 15 executable invocations each (**120 measured calls**, process startup included). The benchmark initializes a fresh isolated database each run; it does not delete an authoritative findings database.

| Metric | This run |
|---|---:|
| Full index, 1,000 accepted sources | 173.9493 ms |
| Unchanged rescan, all 1,000 unchanged | 103.3822 ms |
| Search process p50 | 5.5878 ms |
| Search process p95 | 7.2865 ms |
| Answerable recall@5 | 5 of 7 |
| Unanswerable query | Correctly empty |

Exact identifier/function/version and technical-word queries matched. The held-out English paraphrase and French-to-English question **both failed**. No semantic model was installed or evaluated; hybrid/RRF/reranking are unimplemented. The small synthetic query set is not a reliable estimate of personal-vault recall, OCR accuracy, production concurrency or global latency. Earlier exploratory timings varied with the active host; no causal speedup claim is made. Use the source-bound receipt, not an old chat number, for this run.

## Boundaries and remaining work

- Repository is separate from BorgInvestor. No BorgInvestor, existing Qdrant collection, vault original, paused Markdown prototype, Hermes profile or MCP runtime configuration was edited. The vault retains its pre-existing dirty backup archive and untracked prototype; no preservation certification is inferred for concurrent external writers.
- The imported SQL and SSE findings remain scoped **proposals**. Campaign preservation is `NOT_CERTIFIED`; production health is `UNKNOWN`. Original synthetic-only performance and adverse small-workload/cancellation results remain in payload details.
- Beads tracker `bk-d19` records implementation. There is no remote. The sole auto-created tracker-bootstrap branch reference was removed using its expected commit ID; no working files were deleted, no product commit or push occurred, and the feature branch has no reachable commits.
- Protected `AGENTS.md` creation was denied by an approval timeout and was not bypassed. Project documentation/canonical symlinks are present, but that instruction file is absent.
- No independent external-AI review, full vulnerability audit, chart/table understanding, multilingual semantic retrieval, MCP server, automatic watcher, supersession/edit API, real-vault relevance acceptance or global activation is claimed.

## Historical prioritized upgrades (superseded by current hybrid report)

Current follow-up is approved real-corpus evaluation, answerability, authority/version risk handling and inference-cost profiling; the items below preserve the earlier handoff rather than denying the shipped experimental hybrid.

1. **Retrieval quality:** benchmark a pinned local multilingual embedding model against the observed paraphrase failures, then consider rank fusion. Gain: recall without sending private documents out; reject added complexity if held-out gains do not justify cold-start/index costs.
2. **Lifecycle:** add revision-checked edit/supersede/withdrawal operations and explicit concurrent-writer/migration acceptance cases. Gain: maintainable long-lived advice without direct SQL edits.
3. **Integration:** after approving a bounded technical corpus and provenance/quality gates, publish one canonical global-stack navigation link and evaluate an SDK-backed MCP adapter. Gain: agent discoverability without silently altering existing runtimes or replacing the incumbent Qdrant index.
