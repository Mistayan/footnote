# Opt-in personal knowledge runtime

## Delivered boundary

`python -m tools.knowledge_runtime` is a **working, resident JSONL agent adapter**, not MCP or an HTTP service. It packages the existing `tools/agent_knowledge_runtime.py` authority/encoder/Qdrant implementation without changing it. The new `KnowledgeRuntime` API adds a controlled-folder **sync = observe allowlisted files → commit immutable revisions and outbox → reconcile derived vectors** operation. Existing Rust commands, records/history and databases are untouched. This dedicated schema is additive, **not a migration or a replacement for the Rust structured-record API**.

Operational fixture acceptance is not retrieval relevance acceptance. Semantic search returns nearest candidates, including potentially irrelevant ones; `answerability` and applicability remain `not_estimated`. The default loads no reranker; explicit offline reranking is documented below. No answer generator, automatic action execution, watcher, vault ingestion or global agent activation is included. Do not switch normal knowledge access until the separate fresh judged ≥90% presented-evidence gate and authorized pilot pass.

## Explicit local setup

Run from `D:/Projets/BorgKnowledge` using the already provisioned Python environment with `numpy`, `onnxruntime`, `tokenizers`; no install or model download is performed. The exercised interpreter was `C:/Users/johan/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`. Existing pinned model: `artifacts/models/minilm`; existing Qdrant executable: `artifacts/server-provision/qdrant-1.19.2/qdrant.exe`. Both are read-only inputs.

There are **no default source/state/server paths**. Choose a new disposable or explicitly approved source folder, a dedicated nonexistent SQLite file and a new owned collection (`akr_` + 32 lowercase hexadecimal UUID characters). Do not point any argument at the vault or an incumbent database. Explicit source basenames are the allowlist, not a directory-wide wildcard. Files outside it are never read by sync. Initial limits: 1–32 `.md`/`.txt` basenames, no subdirectories, UTF-8 only, 65,536 bytes per source. Source symlinks and Windows reparse points are refused. Empty files are preserved as revisions with zero chunks.

Start your **separately terminal-owned Qdrant process** with an explicit config, for example a JSON file accepted as YAML (replace all example paths with your owned paths):

```json
{
  "storage": {
    "storage_path": "D:/OwnedKnowledgeDemo/qdrant/storage",
    "snapshots_path": "D:/OwnedKnowledgeDemo/qdrant/snapshots",
    "temp_path": "D:/OwnedKnowledgeDemo/qdrant/temp"
  },
  "service": {"host": "127.0.0.1", "http_port": 16339, "grpc_port": null, "max_workers": 4},
  "cluster": {"enabled": false},
  "telemetry_disabled": true,
  "log_level": "INFO"
}
```

```bash
artifacts/server-provision/qdrant-1.19.2/qdrant.exe --config-path D:/OwnedKnowledgeDemo/server.yaml --disable-telemetry
```

Do not override loopback binding through `QDRANT_*` environment variables. The runtime accepts only explicit loopback HTTP URLs with ports; it does not start, expose, reconfigure or terminate Qdrant. The acceptance harness removes inherited `QDRANT_*` variables and starts its own ephemeral loopback server/storage. Production operators own the separate server lifecycle and must verify its actual listener.

Create a resident worker (example collection must be newly generated for each new authority DB, not reused):

```bash
python -c "import uuid; print('akr_' + uuid.uuid4().hex)"
python -m tools.knowledge_runtime \
  --db D:/OwnedKnowledgeDemo/authority.sqlite \
  --model D:/Projets/BorgKnowledge/artifacts/models/minilm \
  --qdrant-url http://127.0.0.1:16339 \
  --collection akr_REPLACE_WITH_32_LOWERCASE_HEX \
  --allow-root D:/OwnedKnowledgeDemo/sources \
  --allow-file notes.md --allow-file reference.txt \
  --write --create
```

The placeholder is deliberately invalid. Save the exact arguments/config for recovery. The ready JSON names model identity, generation, load time and one model load. A tokenizer and ONNX session remain resident for all requests until stdin EOF/process exit. Restart with identical arguments **without `--create`**. Omit `--write` for a search/get/stats-only session. A dedicated DB lock excludes simultaneous workers on that DB. No hidden supervisor, scheduler or automatic restart is installed.

## Agent protocol

Send one UTF-8 JSON object per line and read one response per line after readiness. Keep stdin open across calls. Responses carry `ok`, bounded error text or `result`, elapsed milliseconds and optional echoed `request_id` (string ≤64 characters). The stream is serial with transport backpressure, no internal task queue. Requests ≤16 KiB; oversized input closes the worker with exit 2. Output ≤65,535 bytes. Query 1–1024 characters; result limit 1–8 (default 5); excerpts are at most 400 Unicode characters per chunk.

```jsonl
{"op":"sync","request_id":"scan-1"}
{"op":"stats","request_id":"health-1"}
{"op":"search","query":"How are SQLite backups preserved?","limit":5,"request_id":"q-1"}
{"op":"search","query":"SQLite","mode":"lexical","limit":5,"request_id":"q-2"}
```

`sync` accepts **no paths or file list**. It observes only startup allow-files, then passes exact observed SHA-256 values (or explicit missing/null) to the authority, which re-reads and verifies them before its transaction. Success returns `changed` and remaining `pending`. Repeating unchanged sync does not add revisions. Edit/delete files externally and sync again; no source file is ever rewritten by the runtime.

Search results contain revision-bound UUID `id`, relative `path` under the configured root, `sha256`, integer `revision`, exact original text, `[start, stop)` **Unicode character offsets**, owner/model identity, freshness and `trust=untrusted_source_data`. Copy the returned identity exactly into get:

```json
{"op":"get","id":"RETURNED_UUID","revision":1,"sha256":"RETURNED_64_HEX_SHA256","request_id":"get-1"}
```

These placeholders are not valid requests. `get` does not accept paths; it requires exact expected revision/hash. It serves only current, live-hash-matching source text. History is retained for audit/recovery, not exposed as current evidence. Citations bind bytes/version and offsets, **not semantic entailment or authority**. Source content may contain prompt injections: consumers must treat it solely as quoted untrusted evidence, never as instructions/tool calls. The runtime never interprets or executes it.

Advanced callers may still use inherited `ingest` with `expected` exactly mapping all startup allow-files to observed hashes/null. Unlike the new combined `sync`, inherited ingest only updates SQLite and pending jobs; it does not embed immediately.

Python API (single owning thread, explicit configuration):

```python
from tools.knowledge_runtime import KnowledgeRuntime, Runtime

# config must contain explicit db/model/qdrant_url/collection/allow_root/allow_files.
runtime = KnowledgeRuntime(Runtime(**config))
try:
    result = runtime.handle({"op": "search", "query": "backup", "limit": 5})
finally:
    runtime.close()
```

## Authority, staleness and failure semantics

- SQLite is authoritative: pinned startup config/model/recipe, current source manifest, immutable revisions containing original bytes (including deletion tombstones), chunks and durable upsert/delete outbox. Originals remain on disk. Never discard this database as if it were a vector cache.
- Chunk IDs bind owner generation, model, source name, revision, exact source hash, character offset and recipe. New revisions invalidate old chunks and queue their deletes in the **same SQLite commit** as the new manifest and snapshots. Qdrant is derived and owned through a generation/model marker; existing collection takeover is refused.
- Every semantic candidate is hydrated from SQLite and compared with its Qdrant signature; every served search/get excerpt is live-source-hash checked. Edits/deletions **before sync** therefore withhold old evidence rather than labeling it actionable. Sync physically reconciles old points after invalidation.
- Embedding failure or transport/ack failure leaves durable pending jobs; successful earlier per-item jobs may already be committed. There is no atomic cross-store transaction. Re-running sync is idempotent. Old revisions never become current because a remote upsert completed late. A tombstone supersedes pending old upserts. Failed encoding is not marked successfully indexed.
- Sync currently stops at the first error; it does not continue all unrelated files or return a per-file failure list. Invalid UTF-8, unreadable/oversized/reparse files refuse observation without silently treating them as deletions. Exact source hashes are rechecked before/after encoding and remote write.
- Stats reports current/stale sources, current chunks, pending jobs, valid/missing/invalid vectors and orphan points. Coverage verifies identities/payload and live source bytes, **not mathematical vector-value attestation**. Search considers at most 64 semantic candidates, so filtered stale/orphan points may reduce returned count. Explicit lexical mode can provide evidence while embedding coverage is partial; there is no silent fallback. Startup/stats still require Qdrant ownership verification, even for a planned lexical session.
- A single worker/SQLite lock serializes requests. No cross-process writer concurrency or multi-root snapshot is promised. External editors can change a file immediately after the final hash check; reads are best-effort observations, not a filesystem snapshot/lease. Keep controlled sources stable during sync and revalidate before important actions. Lock-file presence alone is not evidence of a live owner.
- HTTP calls have a five-second socket timeout. There is no hard inference deadline/cancellation or OS resource sandbox. A local agent must bound its wait and terminate only its own worker when needed. Pure Python callers must serialize calls; the API is not thread-safe.

## Stop, restart, backup and recovery

Close stdin and wait for the worker: SQLite and the process-owned exclusive lock close in `finally`. This does not stop the separately owned Qdrant process. Stop that process through its owning terminal/process handle, never by killing arbitrary port owners. The Windows test harness uses owned `Popen.terminate()/wait()`, then verifies port closure; that is forced Windows termination, not a graceful Qdrant shutdown attestation.

Back up authority with SQLite's backup API from its owning process, or stop the worker and copy the closed DB plus saved explicit configuration. Preserve source originals and revision snapshots. Do not live-copy SQLite while assuming journal-free consistency. If Qdrant's derived collection is missing/corrupt, keep the authoritative DB and source originals, restart with the same config plus `--write --recover-index` (no `--create`), then send `sync`. This recreates a missing collection/owner marker or requeues existing derived jobs after ownership verification. Wrong-owner existing collections are refused; never delete one to bypass the check. Model/schema/config changes require deliberate new DB/collection, not automatic in-place migration. Missing model/server yields a ready=false error; no installation or network fallback occurs.

The inherited backup/recovery path is also exercised by `tests/agent_knowledge_runtime_test.py`; this package's new replay test exercises failed inference, actual upsert followed by lost acknowledgment, reopen/replay and deletion superseding unacknowledged upserts. It is not sudden-power-loss/fsync durability qualification.

## Optional BM25 OR, hybrid RRF and compact evidence

The default remains **`semantic`**. Existing explicit **`lexical`** remains the incumbent distinct-word-overlap implementation, not BM25. No model, chunking, authority schema, Qdrant collection schema or incumbent runtime code changed. New modes require explicit selection:

```jsonl
{"op":"search","query":"task_group Python3.11 ->>","mode":"bm25_or","limit":5}
{"op":"search","query":"How are backups preserved?","mode":"hybrid_rrf","limit":5}
{"op":"search","query":"SQLite backup","mode":"hybrid_rrf","limit":5,"response_format":"compact_v2"}
```

### Ranking contract

- **`bm25_or`** executes real SQLite FTS5 `MATCH` with quoted OR terms, ordered by `bm25(lexical)` ascending, then chunk UUID ascending. Lower BM25 values rank first; the negative value is **not confidence**. It acquires at most64 candidates before freshness hydration, then returns at most the requested1–8.
- Technical-token recipe **`technical-hex-casefold-v1`** case-folds Unicode words while preserving internal dots, underscores, colons, slashes and hyphens; terminal `++`/`#` and operators `->>`, `->`, `#>>`, `#>`, `::` are recognized. Each whole token is UTF-8 hex encoded before FTS5 indexing/querying so `task_group`, `task group`, `Python3.11`, `Python3.12`, `C++`, `C`, `->>` and `->` do not silently collapse. Repeated body terms retain their frequencies; query terms are unique. No stemming, stopwords, translation, identifier decomposition, accent removal or general programming-language parser. Other punctuation is a separator; fixed400-character chunk boundaries can still split an identifier. New lexical modes permit at most128 unique query tokens within the existing1024-character bound.
- **`hybrid_rrf`** acquires dense60 from the same resident encoder/Qdrant and lexical20 from FTS5. Dense ties within the returned pool use UUID ascending; SQL ties do likewise. Authority hydration/freshness and dense payload signatures are checked **before branch ranks are assigned**. Unique branch ranks start at1. Equal fusion is exactly `sum(1 / (60 + rank))`, sorted descending, then UUID ascending, with a final hydration check at presentation. Units are current400-character chunks, not deduplicated source documents. Without `rerank_budget`, this ordering remains unchanged. There is no parent/metadata invention.
- Candidate budgets are hard bounds, not refill promises. Stale/orphan/owner points can consume remote slots, and equal dense scores at the remote60-candidate boundary can affect which points are acquired. Deterministic fusion does not certify ANN determinism outside that returned pool. Rejected candidates or a source edit during final hydration may reduce output count. Pending vectors can make dense coverage partial; lexical current revisions can be returned before their vector jobs succeed. `pending` is retained; use stats for vector coverage. **BM25, cosine and RRF scores are rankings, never evidence confidence.** Answerability/applicability remain `not_estimated`.

### Persistent derived lexical state

The first writer search selecting a new mode creates **`<explicit-authority-db>.lexical.sqlite`**, beside the dedicated authority file. No caller-supplied lexical path, source root or filename is accepted. It is disposable derived state, **not another authority**: only active `chunks` rows from the real authority schema are indexed. Owner generation, model identity, recipe and a SHA-256 snapshot of sorted chunk IDs/path/revision/source hash/offsets/text bind the index. Rebuilds replace FTS rows plus snapshot atomically. Original bytes, revision history, tombstones, jobs and citation hydration stay in the incumbent authority.

Once activated, combined sync reconciles lexical state after authoritative ingestion and before vector reconciliation, including after restart. Thus a failed encoder/remote operation retains durable vector jobs without making old lexical revisions current. Every new-mode search checks the authority snapshot and rebuilds it if this is a writer; inherited ingest is noticed on the next new-mode search. A read-only worker only reuses an existing matching snapshot; missing/stale state refuses the new mode and requires a writer. Wrong application ID, owner/model/recipe, links and reparse points are refused. Source live-hash checks still gate every search/get result, even before sync. No source bytes are read from this derived file, and no FTS text is presented as evidence.

Removing a **closed, explicitly owned** sidecar permits rebuilding via a writer new-mode search; never delete the authoritative DB or an unknown sidecar to bypass ownership checks. Include the authority/config/originals in backups; the sidecar is optional recovery acceleration. Lexical snapshot verification reads all bounded active chunks on each new-mode query, and a changed snapshot rebuilds all of them. This is deliberately bounded personal-store behavior, not a large-corpus throughput claim. An index corruption/I/O failure is explicit, not a silent fallback to overlap or semantic ranking. Startup still requires the resident model and Qdrant ownership checks.

### Response compatibility and lossless v2

No `response_format` means the existing **v1** result structure, unchanged and without an added version field. `response_format="compact_v2"` is accepted only for search/get and explicitly returns `contract_version=2`, `evidence_format="compact"`. Search factors metadata into `shared` **only when at least two hits repeat exactly the same value**. Eligible keys: owner, model, path, revision, sha256, freshness, usable, trust, applicability. IDs, scores, complete text and offsets remain per hit; distinct values are never removed. Recover every original hit with `{**result["shared"], **hit}` and remove the three v2 envelope fields to recover the original search result. Empty/single-hit searches retain all evidence fields with empty `shared`. A get wraps the unchanged full record in `evidence`; it has no duplicates to remove and may grow. Unknown formats/operations refuse before execution.

Compaction is not truncation, a preview, deferred get, fewer calls or a relevance policy. It uses the same transport bounds and can still exceed the64 KiB output ceiling. There is no claim that fewer bytes make inference or JSONL faster.

## Optional pinned resident reranker

Startup is **off by default**. Add this exact option to the explicit worker command above, using the already provisioned public model directory:

```bash
--reranker-model D:/Projets/BorgKnowledge/artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model
```

This is an argument to `python -m tools.knowledge_runtime`, not a standalone shell command. No automatic discovery, installation, model download, alternate checkpoint or network fallback exists. Missing/invalid artifacts produce bounded `ready=false` JSON and exit1 **before authority creation**. The adapter reuses `tools.retrieval_ablation.CrossEncoder` read-only; it does not modify the experimental harness. Python callers may pass the same explicit path as `KnowledgeRuntime(authority, reranker_model=path)`; they retain responsibility for closing an acquired authority if construction fails.

Pinned identity: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision `1427fd652930e4ba29e8149678df786c240d8825`, Apache-2.0, quantized AVX2 ONNX. The exact receipt SHA-256 is `4f18f4adefa4156052c8c32804b0e5b02b9c1c1d91bbd4587d7f6c11f49ebf6d`; its fixed README/config/tokenizer/model hashes are all checked, with link/reparse denial. The model ONNX SHA-256 is `6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b`. The recipe is unchanged from the prior budget experiment: original query/body pairs, longest-first512 tokens, pad ID1, batches4, CPU provider, intra/inter threads2/1, raw finite logits with UUID ascending ties. No sigmoid, automatic threshold, confidence, abstention or answerability policy is introduced. One tokenizer/session stays resident across requests; encoder and reranker remain separate sessions. Optional ranker selection does not migrate or alter the authority/model/index schemas and must be explicitly supplied again after restart.

Loading the model alone does **not** select reranking. Only explicit `hybrid_rrf` search supports these named budgets:

```jsonl
{"op":"search","mode":"hybrid_rrf","query":"SQLite backup database","limit":5,"rerank_budget":"budget5"}
{"op":"search","mode":"hybrid_rrf","query":"SQLite backup database","limit":5,"rerank_budget":"budget10"}
{"op":"search","mode":"hybrid_rrf","query":"SQLite backup database","limit":5,"rerank_budget":"budget20"}
```

Unknown budgets, numeric/null budgets, other modes/operations and requests without a loaded reranker fail explicitly before source reads; no silent fallback. Existing requests without this field retain the same v1 search/get result fields and ranking, even in a loaded worker. Readiness/stats add `reranker_loads` (0 or1), pinned receipt identity/recipe (null if unloaded), and the last successful `selected_search_mode`/`selected_rerank_budget` (initially null). These fields contain no source/model paths, URLs or credentials. Readiness separately measures `reranker_load_ms`; existing encoder counts/times remain intact.

Candidate contract:

1. Acquire the existing technical-token BM25 OR20 and dense60; retain existing authority revision/live-source hydration and dense payload checks before branch ranking and equal RRF60 fusion.
2. Freeze fused pool20. Independently rehydrate its members, then choose the first5/10/20 **eligible current chunks**, up to the named bound. Stale members cannot spend inference pairs. Do not refill outside frozen pool20 or append unscored tail candidates. Budgets are maxima, not minimum result counts.
3. Rerank only those exact IDs; reject nonfinite logits or a missing/duplicate/out-of-pool result permutation. Preserve original evidence and the RRF `score`; expose raw `rerank_logit` separately. Return at most requested limit after final hydration of each selected ID. An edit during inference can reduce the result count; it cannot promote stale text. `get` remains the incumbent exact revision/hash/live-source check and does not run a model.
4. Return opt-in `reranking` metadata: named budget, actual `candidate_count`, eligible frozen-pool count, pinned identity/recipe, `score_semantics=logits_not_confidence`, and real stage milliseconds. Stages separate lexical snapshot/acquisition/hydration, query encode, HTTP backend, dense validation/fusion, pool eligibility, rerank, and presentation. Cold validation/load is excluded. Outer JSONL elapsed time and retained transport wall time are independent measurements, not sums of reused stages.

**Without the optional explicit source manifest below, applicability remains unknown.** This controlled-folder authority has no inferred product/version applicability metadata. The runtime does not extract compatibility from filenames, prose, dates, queries or reranker logits, and does not transplant the public benchmark's pinned-CPython version gate. Version-specific queries without explicit constraints can still retrieve inapplicable evidence. `applicability` and `answerability` remain `not_estimated`; consumers must not treat this as version-qualified answers. The runtime's technical-hex lexical recipe and personal400-character chunks also differ from that benchmark's corpus preparation: no benchmark relevance gains transfer automatically.

SQLite/outbox authority, pending vector jobs and lexical reconciliation remain unchanged. A loaded-ranker regression verifies current lexical revision reranking while encoding is pending, a real remote upsert followed by lost acknowledgment, restart/replay, and deletion superseding a pending older upsert. No rerank score promotes a deleted/obsolete revision. External edit-after-final-check races, bounded acquisition, lack of inference deadlines/cancellation, serial ownership, no MCP/HTTP integration and no relevance qualification remain open limitations.

### Runnable isolated verification

From the repository, using the existing interpreter (no dependency changes):

```bash
"C:/Users/johan/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" -m tools.knowledge_runtime.verify_rerank
```

The runner allocates new UUID evidence under `artifacts/knowledge-rerank/executions/`, prints `verification_path`, freezes source/protected hashes, captures exact argv/stdout/stderr and reruns **13 runtime tests**, **10 incumbent authority tests**, and **2 budget contracts** (the historical large relevance experiment is explicitly skipped). It checks owned process exits, port closure, scratch removal, original encoder/reranker/server and staged-index hashes, and writes SHA-256 manifests. The incumbent suite's server/storage is redirected only in its child environment to owned scratch; logs/receipts are archived before removal. No global environment/configuration is changed.

TDD observed missing resident loader RED→real pinned recipe parity GREEN; unsupported-budget RED→eligible-pool/post-inference freshness GREEN; unknown CLI flag RED→actual JSONL lifecycle GREEN. Added tests retain hash-tamper rejection and foreign-ID rejection. The real transport journey covers ingest/sync, repeated budgeted search/get, edit-before-sync refusal, sync, loaded/unloaded restart equivalence, delete-before-sync refusal, tombstones and another loaded restart. Its worker exits are `[1,0,0,0,0,0]`: the first is deliberately invalid-model startup; the rest exit normally. UUID source/state/server storage is removed. Qdrant's Windows forced termination remains distinct from graceful durability qualification.

One [measured operational execution](../artifacts/knowledge-rerank/executions/cb74327044544b62baf00a528676152c/verification.json) scored exactly5/10/20 pairs at the three budgets; rerank-stage medians were15.22/27.72/55.00ms respectively, with2/1/2 initial alternating calls. These are tiny synthetic lifecycle observations, not a relevance benchmark, stable p95, model-wide performance claim or whole-pipeline speedup. Each rerun retains its own actual stage values/cold times and full JSONL transcript. Final-source receipts may postdate this measured execution's documentation hash; use the printed receipt from your rerun for exact final inputs.

Tracking: reranker bead **`bk-zxa` remains in progress for parent verification/closure**. Graph discovery/coverage confirms `tools/` and `docs/` are excluded from the current graph; direct source/caller inspection was used without reindexing. No current MCP hook implementation was edited. Incumbent authority and benchmark code remain unchanged; no private/vault corpus, global activation, staged changes, commit or push is part of this delivery.

## Optional explicit source metadata (operational slice; parent verification open)

Add `--source-manifest D:/OwnedKnowledgeDemo/source-metadata.json` to the existing explicit JSONL worker command, on creation **and every restart**. Python callers use `KnowledgeRuntime(authority, source_manifest=path)`. Keep the manifest **outside the source root**, separate from authority/derived state. This is operator-authored configuration, not extracted source contents:

```json
{"schema_version":1,"sources":{"notes.md":{"technology":"python","documented_version":"3.11","language":"en","status":"current"}}}
```

The exact root keys are `schema_version` (integer1) and `sources` (object). Source keys must belong to the startup filename allowlist. Sources and each of the four fields may be omitted; **omitted means unknown, never compatible by assumption**. Values are case-sensitive exact labels matching `[A-Za-z0-9][A-Za-z0-9_+.#-]{0,63}`. No arbitrary keys, paths/URLs, nulls, arrays, booleans, duplicate JSON fields, free-form notes, secrets or inferred fields are supported. The manifest is UTF-8 JSON at most16KiB; links/reparse points are refused. Choose non-sensitive labels. Version numbers are literal declarations, not semantic-version ranges: `3.11` does not imply `3.11.1`, and nothing is parsed from the query, filename or prose. Represent unknown version by **omitting** `documented_version`, not by inventing a compatible value.

```jsonl
{"op":"sync"}
{"op":"search","mode":"hybrid_rrf","query":"task_group","constraints":{"technology":"python","documented_version":"3.11"}}
{"op":"search","mode":"bm25_or","query":"task_group","constraints":{"language":"en","status":"current"}}
```

All constraints are ANDed exact equality. **A version-constrained query rejects every source missing that declared version**; there is no include-unknown switch. Constraints are explicit optional search/get fields and require the manifest option. Supported search modes in this opt-in runtime are semantic (including the unchanged default name), `bm25_or` and `hybrid_rrf`; legacy word-overlap `lexical` is refused rather than silently bypassing metadata. Calls without a manifest retain their existing defaults/contracts. With a manifest but no constraints, unknown sources are eligible: that is unconstrained access, not a compatibility assertion. `get` still requires the exact ID/revision/hash and can additionally carry `"constraints":{"documented_version":"3.11"}`. Old-version get requests fail even when source bytes/ID stayed unchanged after a metadata-only update. Compact responses retain the declared fields losslessly.

### Implemented filtering, not a Qdrant schema migration

The fallback slice is **source-admissibility filtering with eligible UUIDs**. The incumbent vector payload contains only owner/model/ID/revision/source hash. It is left byte-for-byte unchanged, as are `tools/agent_knowledge_runtime.py`, the authority schema/ownership signature and model recipe. **No payload metadata fields or Qdrant payload indexes are created, and no authority migration is implemented or claimed.** Any future payload-schema/index work needs separately coordinated authority ownership changes and recovery tests.

Before acquisition, the wrapper resolves admissible active authority chunk IDs from the synced manifest, revision and source hash, and applies existing live-source hydration. It sends an actual Qdrant `filter={"must":[{"has_id":[...]}]}` in dense requests **before** the remote60/64 limit. Empty eligibility skips the remote query. FTS5 uses `id IN (SELECT value FROM json_each(?))` in the MATCH query **before** ORDER/LIMIT20/64. Thus incompatible/unknown-version IDs cannot spend either branch budget or enter the fusion/rerank pool. Existing dense signature checks remain mandatory. Constraints/current metadata are independently rechecked during branch hydration, optional existing reranking eligibility and final evidence presentation/get. This adds no reranker/model or ranking weights. Returned `source_metadata` and `metadata_basis="explicit_source_manifest"` identify declarations only; `applicability`/`answerability` stay `not_estimated`. Declarations can be wrong and entailment/relevance remains unqualified.

### Persistence, drift and recovery

`<authority-db>.metadata.json` is an atomic-replaced, disposable derived snapshot, bound to schema1, authority owner generation, encoder identity, **exact manifest-byte SHA-256**, and sorted active IDs/path/revision/source hashes. It stores no source text and no manifest path. Combined writer sync validates the manifest before source observation, ingests authority revisions, publishes this snapshot, reconciles activated lexical state, then replays vector jobs. Metadata-only changes require sync even if original bytes are identical (`changed` remains the authority source-change count, so it is0). They do not fabricate a source revision or change immutable IDs. A remote failure leaves durable incumbent jobs pending while current declared metadata/current lexical evidence remain usable. Source edits/deletes still withhold stale evidence before sync and supersede pending old vectors through the incumbent outbox.

Search/get never silently reconcile stale metadata, including in a writer. Missing/mismatching manifest, sidecar or authority snapshot refuses until explicit writer sync; a change during acquisition can instead yield no hits after presentation rejection. Read-only restarts reuse only matching derived state and never write it. An existing metadata sidecar makes omission of the manifest option at wrapper restart an explicit error. Foreign-owner/model/schema sidecars refuse reconciliation. Back up originals/authority and the **operator manifest**; the metadata sidecar is rebuildable by writer sync if its closed owned file is missing. An abandoned owned `.metadata.json.tmp` refuses exclusive creation: inspect/remove only that closed, explicitly owned temporary file before retry. Do not delete foreign state to bypass checks. The sidecar is not immutable metadata history, cross-store atomic authority, authenticated configuration or power-loss durability qualification. Deliberately removing all derived state and calling the incumbent directly is not an access-control boundary.

This bounded implementation scans active authority rows and may re-read manifest/live files repeatedly. No large-corpus throughput, filesystem snapshot, concurrent editor lease, hard inference deadline, auto-watcher, MCP, private corpus migration or ≥90% relevance acceptance is claimed. A file/manifest can change after the final check; stabilize controlled inputs and revalidate before consequential use.

### Reproducible gate

```bash
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_knowledge_runtime*.py' -v
python artifacts/knowledge-metadata/6585767f0bf44614bc18f0d56d3e569e/verify.py
```

The unique execution receipt printed by the runner freezes source/protected hashes, exact argv/raw stdout/stderr, all existing runtime and incumbent tests, the non-experimental budget contracts, new JSONL transcripts, and owned process/port/scratch cleanup. New tests cover strict schema/ownership, explicit missing-version rejection,80 incompatible lexical competitors filtered before budget, actual dense filter payload, semantic read-only reuse without a lexical sidecar, metadata-only sync with unchanged bytes/ID, constrained get, restart, metadata drift during acquisition, source updates/deletion, failed encoding and actual remote-upsert lost acknowledgment/reopen/replay. Existing deletion-supersedes-pending tests are rerun as well. Metadata lifecycle fixtures use only newly owned scratch and local existing models/server. Initial RED logs are retained under the runner's parent evidence directory; the initial CLI RED's stderr records the unsupported flag (the test waited for absent readiness). Graph lookup/tracing was attempted before edits and returned no indexed runtime symbol/function-not-found; direct wrapper/entrypoint/tests and authority source inspection supplied impact discovery, not a claimed empty graph.

**Status remains OPEN_PENDING_PARENT_VERIFICATION.** This operational gate neither promotes a relevance experiment nor closes the parent task. No Git staging/commit, global install/configuration, source rewriting or incumbent authority edit is included.

## Finite acceptance and receipts

```bash
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_knowledge_runtime*.py' -v
```

The original two orchestration tests plus two real integration tests cover combined source observation, validation-before-read, three fresh resident process sessions, repeated search/get, original hash/revision/text agreement, edit-before-sync exclusion, edit sync, restart, delete-before-sync exclusion, delete sync, restart without resurrection, immutable history, unallowlisted sentinel preservation, path/query bounds, pending encoding failure, actual lost-upsert acknowledgment/replay and tombstone supersession. The failure/replay test now also exercises activated BM25/hybrid access to current lexical evidence while vector coverage is pending.

The additive hybrid contracts bring this command to **8 tests**: three mechanical unit contracts and another real three-session JSONL test. They verify exact technical-token matching, actual SQL BM25 scores/OR against a separate FTS5 index, four independently frozen rank-list fixtures, five frozen query/path expectations, independent dense/lexical fusion reconstruction for every query, compact search/get round-trip, writer-sync persistence, read-only reuse/stale refusal and wrong lexical-owner refusal. Real JSONL edit/delete/restart, invalid input bounds and sentinel exclusion are exercised with the new modes. These are mechanical acceptance fixtures, **not semantic judgments**.

Re-execute both runtime suites and the evidence/hash audit:

```bash
python artifacts/knowledge-hybrid/559aef7464214579a500ff38e6fe5be9/verify.py
```

The runner allocates a new UUID [execution receipt directory](../artifacts/knowledge-hybrid/559aef7464214579a500ff38e6fe5be9/executions/) on every invocation and prints its exact `verification_path`. Its receipt binds source/protected hashes, raw stdout/stderr, exact commands, the newly allocated raw hybrid run and cleanup. It runs these 8 tests and the incumbent 10 tests with ResourceWarnings treated as errors; no full unrelated-project test suite is claimed. RED/GREEN logs for each implemented slice are retained beside the runner. The original root-level verification predates the final documentation refinement and is historical; use the execution receipts for final-source hashes. [Measured hybrid run](../artifacts/knowledge-hybrid/3c57cc1c51cd40c498b371388a48dd45/measurements.json), `freeze.json`, `per-query-parity.json` and `transcript.json` preserve the following bounded result:

| Actual JSONL wall-clock boundary | Calls | Median ms |
|---|---:|---:|
| New BM25 OR, full evidence | 9 | 0.79 |
| New hybrid RRF, full evidence | 8 | 17.77 |
| Hybrid RRF, compact v2 | 5 | 7.82 |

These are serial successful request write/flush/read wall times across the small lifecycle, including empty/stale searches and first index creation where applicable, **not matched timing distributions, a compaction speedup or a production p95 benchmark**. Full/compact were requested sequentially, not randomized performance arms. Cold readiness was1165.64ms; restarts763.18ms and760.99ms. Five paired result envelopes contain8188 full versus6023 compact bytes (**26.44% fewer**), each mechanically expanded to exactly the original complete evidence. Byte totals exclude the outer JSONL timing/request envelope. Get has no duplicate fields and no byte reduction is asserted.

The measured run's three workers exited0; its owned Qdrant process exited and port closed, and the UUID scratch source/authority/sidecar/server storage was removed. Qdrant's Windows returncode1 reflects owned forced terminate/wait, not graceful-shutdown durability. Immutable input hashes (incumbent runtime, model manifest/ONNX/tokenizer, Qdrant executable) and the pre-existing staged Git index remain unchanged; each final rerun verifies them again. Evidence files have a separate SHA-256 manifest. Relevance acceptance, private-corpus pilot, automatic activation and Rust integration remain outside this delivery.

Each integration run writes a new UUID directory under `artifacts/knowledge-runtime/`: raw JSONL request/response transcript, exact subprocess argv, cold/warm timings, revision snapshots, model identity, Qdrant config/log and process/port/scratch cleanup receipts. Qdrant storage/source fixtures/SQLite are UUID-owned under Hermes scratch and removed after the test. No incumbent collection or private/vault fixture is used. Evidence hashes and exact final execution results are retained by the accompanying verification receipt. **No claim of ≥90% relevance, whole-vault readiness, MCP integration or automatic migration follows from these operational checks.**

Tracking: initial wrapper delivery `bk-06n` (parent-closed), incumbent authority `bk-dwx`; current optional hybrid delivery **`bk-90c` remains in progress for parent verification/closure**. GSD discovery is callable but still returns `phase_scope=unreadable`; no initialization/global changes were made. Graph hook tools are callable, but the index explicitly excludes `tools/`; `KnowledgeRuntime.handle` tracing returns function-not-found, not a verified empty impact graph. Direct caller/source inspection grounded the bounded wrapper edits (package entry point plus runtime tests). `tools/agent_knowledge_runtime.py` remains byte-identical.
