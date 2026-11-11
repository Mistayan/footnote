# Authorized SecondBrain MD/TXT hybrid migration — executed

## Outcome

The authorized local migration completed against `D:/Second Brain`, including the coordinator's final LikeC4 Markdown edits. This is a separate derived knowledge state, **not** activation or replacement of `borg_vault`, the Rust findings databases, or existing agent configurations.

- **595 eligible sources**: 588 Markdown + 7 TXT; **3,798,782 original bytes** retained unchanged in SQLite revisions.
- **16,639 active chunks**, 595 revisions, zero pending jobs, 595 fresh / zero stale sources.
- Qdrant exact count: **16,640 points** (16,639 chunks + one owner marker). Every chunk's returned identity/payload was checked against SQLite, not just sampled search results.
- Complete unchanged re-ingestion: zero ingested, **595 unchanged**, zero deletions; no extra revisions.
- SQLite `integrity_check`: `ok`. Every retained revision BLOB hashes to its recorded source SHA-256.
- Independent second service startup and fresh resident CLI performed stats/search/get, checked live hashes and character offsets, and left the authority database byte-identical.
- Both owned servers exited and their loopback port closed. No resident daemon/watcher/scheduler was installed. Windows termination returned 1; this is owned terminate/wait cleanup, not a graceful-shutdown claim.

## Evidence and exact identities

Canonical run: `artifacts/migration/full-20261021/`.

| Artifact | Purpose |
|---|---|
| `report.json` | Final corpus, index, freshness, replay and cleanup totals |
| `config.json` | Exact state/root/model/loopback URL/owned collection |
| `inventory-current.json` | Selected final inventory directory, manifest hash and summary |
| `inventory-*/` and `inventory-after-*/` | Pre/post inventory manifests, exclusions, link maps, heuristic metadata |
| `commands.jsonl` | Exact CLI argv, return codes, stdout and measured command times, including failed attempts |
| `ingest-stderr.log` | Append-only real per-file progress and failures |
| `input-hashes.json` | Implementation, model, server binary and task hashes used in the successful run |
| `replay.jsonl` | Actual 42 query/mode rows, result paths/revisions/hashes/offsets and timings |
| `transport.json` | Fresh JSONL CLI restart request/response receipt |
| `independent-verification/receipt.json` | Separate read-only DB/source/input verification plus restarted CLI stats/search/get |
| `cleanup.json`, `server.yaml`, `server.log` | Owned loopback service configuration and cleanup |
| `../tests-final.log` | Eleven passing targeted tests |

Authority: `D:/Projets/BorgKnowledge/artifacts/migration/full-20261021/authority.sqlite`.

SHA-256 (also independently rechecked unchanged):

```text
179aa23c7a66e97c61288397cdf10c1f70372c8a3b9b2df87a9fd834f8d6ade3
```

Collection: `akr_d710b328647b4ba5b4365ccfaee3aab0`; owner: `b0094196-0282-4938-aad6-d1942cf5fc8f`.

Final eligible manifest SHA-256: `00cabba1f9f0b8cb38f06f3869c32bef49926e1e573a227e864ed27c6dcd882f`.

The collection/storage remains on disk under this run. Its temporary loopback service at port 59482 is **stopped**, not left running for agents.

## Scope, exclusions and source safety

Final inventory: 1,165 manifest records, 836 observed regular file entries. It records:

- 595 eligible MD/TXT;
- 6 heuristic secret quarantines (60,400 bytes), not indexed;
- 231 unsupported non-MD/TXT files, not extracted/indexed;
- 4 archives, not opened;
- 81 reparse boundaries, not followed;
- 5 infrastructure/dependency boundaries, not traversed;
- 243 traversed directory records.

Boundary descendants are unenumerated/unknown, so **all eligible reachable MD/TXT** is the correct coverage claim, not all knowledge or all physical files. PDFs, Office, images, diagrams and other formats remain originals pending a separate extraction workflow. Zero duplicate eligible hash groups were observed.

Importer reads revalidate path containment, reparse points, hardlink count, regular-file identity/size, nested repository boundaries, sensitive names, heuristic secret content and exact manifest bytes/SHA-256. The explicitly authorized vault root may itself be Git-backed; nested repositories remain denied. No `.git` content is read. Source text is untrusted data, never commands. Secret detection is heuristic, not a DLP guarantee. Filesystem races cannot be absolutely prevented without a snapshot/lease; three scans and repeated eligible byte hashes detected the actual concurrent edits in this execution.

Initial inventory raced coordinator edits and was rejected. An ingest later stopped on an actual LikeC4 source hash mismatch after 575 committed sources. It did **not** silently consume changed bytes. After the coordinator confirmed edits finished, a new inventory/resume retained those 575 and ingested the remaining 20. Final pre/post inventory entries were identical. No source was edited by this task.

Inventory `role_hint=original_reference` is shallow explicit-type metadata only: **not original-author evidence, source authority, entailment or validation**. The importer preserves these hints in the bound inventory receipt, not as authoritative retrieval applicability metadata.

## Actual local hybrid implementation

`tools/vault_knowledge/core.py` is a recursive manifest-driven SQLite authority with immutable original BLOBs, source revisions, indexed durable outbox, FTS5 BM25, Qdrant dense retrieval and equal reciprocal-rank fusion. It is separate from the earlier 32-basename / 64 KiB adapter. The exercised real fixture ingests 40 recursive sources with a >64 KiB source and tests update/delete, stale refusal, inference failure, successful remote write followed by lost acknowledgment, restart/replay, backup/restore, derived-index rebuild, constrained search, CLI transport and the already available pinned reranker.

The embedding implementation actually used is the already provisioned **resident CPU ONNX encoder**, not a fake vector function and not the Python `SentenceTransformer` class. Its model is the quantized ONNX export of multilingual MiniLM:

- `Xenova/paraphrase-multilingual-MiniLM-L12-v2` revision `2c4055b12046f11709e9df2c122e59ffbdc2f900`;
- model manifest SHA-256: `b67fb9d833d17e0bbb8e4fbbf30796dfa57d7ff0f2c754b76a8f3c2f3b23fc64`;
- dimension 384; attention-mask mean pooling, L2 normalization; max 128 tokens; dynamic-int8; CPU ORT threads 2/1;
- one tokenizer/session per worker; outbox encoding batches at most 32 real passages;
- tokenizer and ONNX file hashes verified before inference;
- source-offset chunking: 96-token windows / 24 overlap, lexical recipe `technical-hex-casefold-v1`.

This is a reused pinned local model, not a claim it is the best model. No model downloads, private inference API, upload, or cloud generation occurred. Qdrant 1.19.2 is the already provisioned local executable; the harness removes inherited `QDRANT_*`, binds loopback, disables telemetry and owns only its subprocess.

## Retrieval smoke, not precision certification

The frozen retrospective contains **one genuine historical knowledge subrequest and thirteen reconstructed questions**. None is scoring-ready; gold/source adjudication remains pending. All fourteen were run against the current corpus in BM25, dense and hybrid modes: **42 real result rows**, all nonempty. Every presented hit was fetched and checked against current original bytes and character offsets.

| Mode | Rows | Resident p50 | Max |
|---|---:|---:|---:|
| BM25 | 14 | 160.15 ms | 210.44 ms |
| Dense | 14 | 149.10 ms | 229.57 ms |
| Hybrid RRF | 14 | 160.25 ms | 270.67 ms |

Timings include ownership/freshness/citation checking in this sequential small replay; they are not a comparative latency certification or end-to-end answer latency. The final resumed invocation took 74.04 seconds including verification/replay; this **excludes earlier partial work** (the interrupted ingest command itself took 169.89 seconds). Raw timings are retained rather than claiming a misleading full-import throughput.

**The genuine H01 historical Qdrant experiment question remains unresolved.** Its hybrid top five include workflow/UI/testing notes, not admissible original dated experiment receipts. A dense top-five hit includes the current BorgKnowledge status note, but a current summary is not proof of an experiment predating the historical request. Nonempty results and provenance checks are not relevance, precision, an answer, or historical entailment. No fabricated precision score, generated answer, or ≥90% certification is claimed. Global activation remains unapproved.

## Commands actually exercised

From `D:/Projets/BorgKnowledge` (Git Bash):

```bash
PY='C:/Users/johan/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe'

"$PY" -m unittest tests.test_vault_migration_inventory \
  tests.test_vault_knowledge tests.test_vault_knowledge_acceptance -v

"$PY" -m tools.vault_knowledge.migrate \
  --root 'D:/Second Brain' \
  --output 'D:/Projets/BorgKnowledge/artifacts/migration/full-20261021' \
  --tasks 'D:/Projets/BorgKnowledge/artifacts/migration-retrospective/666e06aa-37a5-4d08-8f52-d2f1cdadb1e9/tasks.json' \
  --resume

"$PY" artifacts/migration/verify_full.py
```

`--resume` was used only after failed attempts. **Do not rerun the completed evidence directory as an audit**: the resumable runner updates status/report/config/input receipt files and appends replay rows. Preserve this finished directory; use a new output for a fresh migration. The independent one-off verifier deliberately exclusively creates its verification directory and refuses to overwrite it. Both runner and verifier start and stop their owned local server in `finally`.

For explicit manual later search, preserve `config.json` and the retained storage. Start the saved isolated service configuration under a finite process owner, then invoke `python -m tools.vault_knowledge serve` with the exact five configuration arguments; omit writer flags. Finish by closing the worker and stopping/verifying only that owned service. Do not attach to or kill an incumbent service. If this port is occupied, fail rather than adopting it.

For lost derived-index recovery, the exercised Python API is `Vault(**saved_config, write=True, recover_index=True)` then `rebuild_index()`. It refuses takeover of an existing foreign owner. The CLI currently does **not** expose the constructor's recovery flag; the API/acceptance test is the verified recovery path. Keep authoritative SQLite/originals, not only Qdrant storage. This is not power-loss/fsync qualification.

No commits, pushes, staging, vault writes, incumbent-state mutations or global agent activation were performed. Existing dirty/staged repository files were left alone. The project `.venv` lacks pytest; the verified runner uses the already provisioned Hermes Python with unittest and existing local inference dependencies, without installing anything.
