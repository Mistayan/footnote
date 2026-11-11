# Qdrant full-text migration — completed, local and opt-in

## Executed outcome

The interrupted `tools/qdrant_knowledge/` implementation was resumed, not replaced. The completed historical migration was **not rerun**. This follow-up implements **Qdrant-only retrieval**: complete source text and chunk text live in Qdrant payloads; named native dense and sparse vectors provide semantic/BM25 retrieval, with fusion executed by Qdrant. SQLite is an original-byte/revision archive and import/rebuild input, never a search/get/stats backend.

Current verified corpus: **595 sources, 16,734 chunks, 17,331 Qdrant points** (595 source points + 16,734 chunk points + two control points), **3,820,653 original active-source bytes**. All 595 approved live sources were revalidated safely before snapshot creation, during import/verification, and again in a separate post-completion audit. No current source was edited by this task.

### Why this is not the historical 16,639-chunk snapshot

The historical archive contains 595 sources / 16,639 chunks / 3,798,782 bytes, but four live sources have changed since it completed:

- `AI-Agents/_shared/AI Coding Rules.md`
- `AI-Agents/_shared/stack-contract.md`
- `AI-Agents/skills/premium-editable-presentations/SKILL.md`
- `AI-Agents/skills/ui-ux-qloop/SKILL.md`

A **separate archive-only snapshot** preserves all historical original revisions, reuses unchanged chunk records, and versions/rechunks only these four changed files with the existing pinned 96-token / 24-overlap tokenizer recipe. It contains **599 original revision BLOBs**, all checked for byte length and SHA-256, with SQLite `integrity_check=ok` and no lexical/FTS table. The changed source text was not silently attributed to the older archive.

## Exact evidence and identities

Paths below are relative to `D:/Projets/BorgKnowledge`.

| Receipt | Purpose |
|---|---|
| `artifacts/qdrant-text/9ce1f3c6be37/report.json` | Completed real import, unchanged replay, full payload verification, retrieval replay, transport, restart and cleanup |
| `artifacts/qdrant-text/9ce1f3c6be37/registry.json` | Qdrant owner/config, collision-free BM25 vocabulary/DF, source identity registry and durable import checkpoints; contains no source/chunk text |
| `artifacts/qdrant-text/9ce1f3c6be37/commands.jsonl` | Exact fresh CLI argv, stdout/stderr, exit codes and command timings |
| `artifacts/qdrant-text/9ce1f3c6be37/network.jsonl` | Actual native Qdrant query requests and responses, including sparse/dense prefetch and native `rrf` requests |
| `artifacts/qdrant-text/9ce1f3c6be37/replay.jsonl` | 42 actual query/mode result rows; no fabricated relevance judgments |
| `artifacts/qdrant-text/9ce1f3c6be37/transport.json` | Fresh guarded resident CLI stats/search/source-get/chunk-get requests and responses |
| `artifacts/qdrant-text/9ce1f3c6be37/final-handles.json` | Saved collection, model, archive, registry and ownership identities |
| `artifacts/qdrant-text/9ce1f3c6be37/server.yaml`, `server-initial.log`, `server.log`, `cleanup.json` | Owned loopback process configuration, both service-start logs and final cleanup |
| `artifacts/qdrant-text/receipts-20261023/snapshot/archive.sqlite` | Separately created original-byte archive; not a retrieval dependency |
| `artifacts/qdrant-text/receipts-20261023/snapshot/snapshot.json` | Four changed paths and all 595 safely read live-file hashes |
| `artifacts/qdrant-text/receipts-20261023/archive-audit.json` | All 599 retained original revision BLOBs checked; integrity/absence of lexical tables |
| `artifacts/qdrant-text/receipts-20261023/tests.log`, `tests.json`, `compile.json` | 17 passing targeted tests and successful compilation |
| `artifacts/qdrant-text/receipts-20261023/historical-before.json`, `historical-after.json`, `completion.json` | All 174 historical migration files byte-identical; Git index unchanged |
| `artifacts/qdrant-text/receipts-20261023/post-completion/receipt.json` | Separate read-only final audit: all sources fresh, chunk offsets, raw query payloads, guarded subprocess receipts, historical hashes, closed port |

Collection: `akr_22dd615b7f384c6b9de559a983d6a9d7`.

Owner: `27e76c64-fe70-4512-b383-73e006fcc3e3`.

Snapshot: `140eb85fb6a0b0d57b9c4cbdbd6b4145a83bb1f25124419d0f8a644a98cd0196`.

New archive SHA-256:

```text
9dce7cf83983b02a423b628010e70b5d180a134ff67e7eb039f702b2c10b0b6c
```

Historical `artifacts/migration/full-20261021/authority.sqlite` SHA-256, unchanged:

```text
179aa23c7a66e97c61288397cdf10c1f70372c8a3b9b2df87a9fd834f8d6ade3
```

The old collection/storage, historical reports/logs, and existing `borg_vault` were not activated or mutated. The older `SECOND-BRAIN-HYBRID.md` describes its historical SQLite/FTS5 architecture; this document describes the new separate Qdrant-text state, not a retroactive reinterpretation of that evidence.

## Actual storage and ranking contract

- Each active source has its own versioned UUID point carrying **all UTF-8-SIG-decoded source text**, path/revision, original byte count/SHA, encoding, BOM flag, decoded-text SHA, source metadata, archive reference and source ID. Sources have no fabricated dense vectors.
- Each chunk point carries complete chunk text, heading, decoded Unicode character offsets, text SHA, source revision/hash/metadata/reference, plus named `dense` and `sparse` vectors. Original byte fidelity, including BOM, remains available from archived original BLOBs; decoded text is not falsely described as identical original bytes.
- All **595 source payloads and 16,734 chunk payloads** were retrieved from Qdrant and compared in full with the new archive and live bytes. Chunk offsets/text/SHA/heading/metadata were checked, not just counts or excerpts. Dense vectors were checked for dimension, finiteness and unit norm; every sparse vector was compared with the pinned exact recipe. This does not claim independent re-encoding of every dense vector.
- Full source payloads preserve **3,793,330 decoded characters**. The active chunk span unions cover the same count; zero uncovered characters in this snapshot.
- BM25 uses deterministic technical-casefold tokens, a sorted **41,323-term collision-free vocabulary**, document frequencies over 16,734 chunks, `k1=1.2`, `b=0.75`, unique query terms, and `IDF=log1p((N-df+0.5)/(df+0.5))`. Stored document weights are `tf*2.2/(tf+1.2*(0.25+0.75*dl/avgdl))`; query weights supply the exact pinned IDF. **Qdrant native sparse dot-product scoring** executes this BM25 recipe, with no extra native-IDF modifier or Python ranker.
- Hybrid requests use native Qdrant `prefetch` branches (`using=dense` / `using=sparse`) and `query={"rrf":{"k":60}}`. Qdrant 1.19.2 uses **zero-based rank** in `1/(60+rank)`; independent live tests compare sparse and fused scores with arithmetic. This is not represented as identical to the old Python one-based fusion implementation.
- Ownership, source/instruction scope and supported exact metadata constraints are filtered before branch limits. Presentation validates live hashes/offsets again and optionally deduplicates by source path. Scope is a mechanical filename/directory policy, not author authority or instruction execution.
- Search overfetches at most 60 branch/fused candidates before freshness filtering. If many candidates become stale, a shorter result list is possible; no unbounded recall guarantee is implied.

The real encoder is the already provisioned resident CPU ONNX multilingual MiniLM, reused from the existing runtime: `Xenova/paraphrase-multilingual-MiniLM-L12-v2`, revision `2c4055b12046f11709e9df2c122e59ffbdc2f900`, 384 dimensions, mean pooling/L2 normalization, max 128 tokens, existing dynamic-int8 model/tokenizer hashes validated before inference. Qdrant is the existing local **1.19.2** executable. No model downloads, installations, cloud inference, uploads or global configuration changes occurred.

## Acceptance, lifecycle and limits

**17 targeted tests passed**: the previous 11 inventory/vault acceptance tests, three existing Qdrant Store tests, two repaired native BM25/RRF tests and one new separate-snapshot/full-runner test. The interrupted `TextVault` test referred to a nonexistent alternate implementation; it is now grounded in the existing `Store`, with lifecycle coverage retained in the live Store test rather than adding a duplicate runtime.

Real-service fixtures exercise stale source refusal before sync, changed-snapshot replacement, deletion of obsolete source/chunk points, a successful remote write followed by lost acknowledgment, reopen/replay, payload/vector verification, collection takeover refusal and owner isolation. Pending import status withholds reads; deterministic IDs and readback allow idempotent replay. The full corpus was imported once and replayed unchanged with identical counts.

A fresh CLI interpreter patched `sqlite3.connect` to raise **before runtime imports** and successfully performed resident stats/search/source-get/chunk-get. After a real Qdrant process restart against the same new storage, fresh guarded subprocesses again performed stats/search/get. The original and new archives were never renamed or deleted to obtain this proof. The post-completion audit rechecked 2,820 raw returned chunk payloads across 47 native query responses, including 19 fused responses.

This is a **finite snapshot migration**, not a globally installed watcher or automatic filesystem synchronization service. `refresh_archive` conservatively revalidates the historical approved allowlist and refuses missing/unreadable/stale-boundary sources; it does not infer filesystem deletions or expand scope. The importer reconciles explicit replacement archives, including deletions, as exercised in fixtures. Import checkpoints are JSON state, not a cross-system atomic transaction or power-loss/fsync certification. Reads require the registry, pinned model and approved live source root for freshness checks, but not SQLite/archive file access. Archive BLOB hashes prove original-byte restorability; no originals were overwritten as a restoration demonstration.

Scope stays the approved 595 MD/TXT sources. Historical exclusion records remain unchanged: **231 unsupported files, six secret quarantines, 81 reparse boundaries, five infrastructure boundaries and four archives**. Boundary descendants remain unknown, not silently included. Every selected source is rechecked for containment, symlink/reparse/hardlink hazards, nested repositories, credential/sensitive names, regular-file identity/size, UTF-8 decoding and heuristic secret content. Secret detection remains heuristic, not certified DLP.

A real Windows acceptance failure exposed Qdrant gridstore path-length limits under deeply nested UUID directories. The runner now exclusively allocates a short UUID-prefix directory while retaining its full run UUID and full collection/owner identities. No global Windows configuration was changed. Graph coverage was checked: the current code graph excludes `tools/`; direct source inspection and live tests were used, not a claim of complete graph impact coverage. No incumbent core module was modified.

## Retrieval replay — smoke only

All 14 frozen retrospective questions ran in BM25, dense and hybrid modes: **42 nonempty rows**. These comprise one actual historical subrequest and thirteen reconstructions; relevance adjudication is not supplied here. Precision/quality scores remain `null`; nonempty results do not establish the historical question's answer or relevance qualification.

| Mode | Rows | Resident p50 | Max |
|---|---:|---:|---:|
| Native BM25 | 14 | 102.05 ms | 159.07 ms |
| Dense | 14 | 119.39 ms | 147.95 ms |
| Native RRF hybrid | 14 | 111.27 ms | 149.61 ms |

These are small sequential safety-checked samples, not a speedup or precision benchmark. Actual full import command: 199.99 s; unchanged replay: 28.58 s; full archive/payload verification: 23.41 s. Finite migration/verification/replay/restart runner: 292.88 s, excluding preceding tests and archive snapshot creation.

## Exercised commands and later use

```bash
# Existing Hermes Python; no installation required.
PY='C:/Users/johan/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe'
"$PY" -m unittest tests.test_vault_migration_inventory \
  tests.test_vault_knowledge tests.test_vault_knowledge_acceptance \
  tests.test_qdrant_knowledge tests.test_qdrant_text tests.test_qdrant_snapshot -v

# Executed finite continuation and separate final audit; both exclusively
# create their receipt directories. Do not rerun these sealed paths.
"$PY" artifacts/qdrant-text/resume_full_20261023.py
"$PY" artifacts/qdrant-text/verify_completion_20261023.py

# Read CLI, only while a separately owned finite service is running with
# the exact saved storage/port configuration:
"$PY" -m tools.qdrant_knowledge stats --state \
  'D:/Projets/BorgKnowledge/artifacts/qdrant-text/9ce1f3c6be37/registry.json'
"$PY" -m tools.qdrant_knowledge search --state \
  'D:/Projets/BorgKnowledge/artifacts/qdrant-text/9ce1f3c6be37/registry.json' \
  --query 'archival checkpoint' --mode hybrid
```

General `import`, `verify`, `get` and resident JSONL `serve` commands are available through `python -m tools.qdrant_knowledge --help`. Resume an **incomplete** Store via `import --state <its registry> --archive <its exact snapshot>` under an exclusively owned service; do not point the runner at sealed historical evidence. New migrations require new output directories and collection identities. For later finite reads, keep report/config logs immutable, capture any new service logs in a separate verification directory, use only the saved owned storage and verify the port is free before starting. Never attach to or stop an unrelated incumbent process.

**Final state:** both owned full-run service processes exited; port **53064** was independently rechecked closed. Windows terminate/wait returned 1; this is not a graceful-shutdown claim. Storage is retained, services are off, and nothing is globally activated. No Git staging, commit or push occurred; the pre-existing dirty/staged repository was preserved. Beads parent `bk-cw9` remains open for the coordinator's disposition.
