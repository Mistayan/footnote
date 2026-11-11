# Resident-inference SQLite vs Qdrant server benchmark

## Outcome and evidence

**A real isolated Qdrant 1.19.2 Windows server and HNSW index ran successfully.** This is a **Python harness**, not a measurement of the Rust CLI or an integrated product server. Inference, lexical search, citation hydration, source hashing and JSON response serialization are common to both paths. Qdrant was faster than the Python SQLite JSON-vector scan in this workload, but its ANN search lost candidates: do not treat the timing difference as a Rust engine speedup or a quality-neutral migration recommendation.

Primary run: [`5234a80c81cf4d1bb2475a9a88d8a2dd`](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/).

- [Report](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/report.json): SHA-256 `dd8140d11e39123923224a171495351561a86c2bf838857835d2536a64ebdae2`.
- [Raw requests, rankings, stages and serialized citation responses](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/raw-results.json): **384 measured requests**, 96 per engine/workload cell.
- [ANN vs exact rankings](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/recall.json), [collection/index readback](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/collection-ready.json), [server identity](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/server-identity.json), [server log](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/server.log).
- [Evidence hash manifest](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/evidence-sha256.json): **1,074 files verified**, manifest SHA-256 `561e0cd1392e3f32e25d68b35f2e6741c0d3d843910e2dc6d0e2a8506e464a4c`. Includes model input/output vectors, all server vector readback, corpus and judgments, raw responses, resource samples, storage, configuration and cleanup. The manifest excludes itself.
- [Source-before](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/source-before.json) and source-after bind **10 execution inputs**, including harness, its tests, existing helper/dataset, dependency lock, model artifacts, server executable and pre-existing Git index. They matched. Unrelated parallel-worker scripts are deliberately outside this execution-input stability claim.

Artifacts are local and Git-ignored; preserve them separately when sharing this uncommitted tree.

## Method

The corpus and judgments reuse [the previous synthetic protocol](HYBRID.md): 20 technical documents, 980 gardening distractors, 32 fixed bilingual/adversarial/no-answer queries. This is not a real technical corpus or independently judged quality benchmark. MiniLM only, 384 dimensions, dynamic-int8 CPU ONNX; **one resident tokenizer/session shared by both engine paths**, ORT intra-op=2/inter-op=1. Tokenization/inference is serialized with one common lock; concurrent timings include its wait. A separate call to the existing `embed.encode` verified the resident query recipe at absolute tolerance `1e-12` before measurement.

Document vectors are computed once and inserted identically into a new SQLite database and Qdrant. All 1,000 Qdrant vectors were read back; maximum absolute difference was `1.4231140654796803e-08` after server float32 conversion/normalization. Every measured query's vector hash matches the saved reference, including across engines and workloads.

Both paths execute the same FTS5 lexical top20 query on the same SQLite database; candidate identity was asserted across all requests. Semantic top60 + lexical top20 use RRF `1/(60+rank)`, rank starting at one, ID tie-break, limit5. Both hydrate selected IDs from the **same SQLite documents table**, SHA-256 the original isolated Markdown files and use the **same response serializer**. All **1,920 selected citation freshness checks** passed. This certifies fixture provenance, not evidence entailment or recommendation truth.

SQLite is a Python/stdlib SQLite read + per-request JSON-vector decode, NumPy float64 exact cosine scan and sort. It intentionally does **not** pre-load a vector matrix instead of reading SQLite. It is not sqlite-vec, not ANN, and not a Rust implementation. Qdrant uses REST/JSON over loopback with per-worker persistent HTTP connections, `exact=false`, `hnsw_ef=128`, M=16, ef_construct=100, one shard. Collection full-scan threshold=10 KB (the server's accepted minimum), indexing threshold=1 KB, all **1,000 vectors indexed**, green status before warm-up. Persisted `vector_index/graph.bin` and `hnsw_config.json` corroborate HNSW construction; the latter expresses the threshold as six vectors, not 10 KB. Qdrant exact REST queries separately establish the float32 brute-force reference.

Warm-up runs every query through both pipelines. Then three fixed-query repetitions per workload, alternating engine block order on odd repetitions. Sequential uses one worker; concurrent uses bounded batches of four, waiting for a batch before submitting the next. There is no unbounded executor backlog or open-loop load generator. End-to-end runs from worker entry through serialized response creation; submission-to-completion is also retained. Block throughput includes executor startup, scheduling and sampler overhead; it is **not** the reciprocal of median latency. Raw JSON/evidence-file writes occur after measured request/block completion. Query timing excludes model validation/load, document embedding, index construction and recall evaluation. OS caches and model are warm, but workers/connections are newly allocated per block.

## Actual warm latency

Nearest-rank p95; p50 is the median. Each row has 96 samples. All times in milliseconds.

| Workload | Backend | E2E p50 | E2E p95 | Submit→done p95 | Block throughput req/s |
|---|---|---:|---:|---:|---:|
| Sequential | SQLite JSON exact / Python | 78.80 | 86.74 | 86.77 | 12.42 |
| Sequential | Qdrant server HNSW | 3.73 | 10.17 | 10.30 | 172.48 |
| Concurrent, four workers | SQLite JSON exact / Python | 237.38 | 352.98 | 353.03 | 11.74 |
| Concurrent, four workers | Qdrant server HNSW | 9.32 | 31.97 | 32.11 | 193.62 |

### Stages, p50 / p95 milliseconds

| Stage | SQLite sequential | Qdrant sequential | SQLite concurrent | Qdrant concurrent |
|---|---:|---:|---:|---:|
| Inference-lock wait | 0.00 / 0.00 | 0.00 / 0.00 | 4.45 / 16.92 | 4.28 / 14.30 |
| Tokenize + inference + pooling | 2.65 / 3.18 | 2.50 / 7.89 | 3.01 / 55.72 | 2.69 / 8.30 |
| Common lexical | 0.13 / 0.20 | 0.12 / 0.18 | 0.23 / 47.34 | 0.16 / 0.39 |
| Vector backend, caller-observed | 75.34 / 83.19 | 0.72 / 1.05 | 184.91 / 318.25 | 0.86 / 22.40 |
| Common RRF | 0.02 / 0.02 | 0.02 / 0.02 | 0.02 / 0.04 | 0.02 / 0.02 |
| Common hydrate + hash + serialize | 0.48 / 0.76 | 0.35 / 0.48 | 1.01 / 76.12 | 0.38 / 0.74 |

SQLite read/JSON decode alone: sequential **73.61 / 78.45 ms**, concurrent **179.59 / 312.55 ms**. Qdrant's server-reported processing time: sequential **0.20 / 0.27 ms**, concurrent **0.23 / 0.35 ms**; caller-observed vector time also includes request encoding, HTTP round-trip, response decoding and ranking canonicalization. Stage percentiles are marginal distributions and do not add to E2E percentiles. Concurrent wall stages include scheduler/GIL contention, not just CPU work.

## Recall and retrieval risk

- Mean strict ANN recall@60 vs SQLite exact: **0.9421875**.
- Mean strict ANN recall@60 vs Qdrant exact: **0.9421875**.
- Minimum per-query strict recall@60: **0.65**.
- Mean score-boundary-tolerant recall@60 vs SQLite exact: **0.9427083333**, tolerance `1e-6`. Strict results remain primary; near ties do not explain the loss.
- Ordered hybrid top5 matched for **31/32** queries. The mismatch was `development-06`, `réduire le coût des reçus inutilisés`: SQLite IDs `[16,15,14,3,19]`, Qdrant `[14,270,16,516,15]`. Neither is an assertion that the intended receipt-cost source was retrieved.
- All **four** no-answer queries still return five candidates under **both** engines. `answerability: not_estimated`; no abstention or answer generator is evaluated.

There was no ef/model/ranking tuning after observing these results. HNSW graph construction is not seeded/reproducible byte-for-byte; an earlier completed request set before an unrelated final-telemetry failure had recall 0.946875. That failed run is not the primary result. Repeat the full benchmark, not just the fastest stage, before any engine decision.

## Resources and one-time work

Process CPU is user+system accumulated across the three measured blocks per cell. RSS is sampled every 10 ms; samples can miss peaks and include shared pages. The shared Python process retains model, corpus, vector snapshots and setup allocations in **both** paths; Qdrant remains running during SQLite measurements. These are not two independently deployed minimal services.

| Workload/backend | Harness CPU s | Server CPU s | Harness peak RSS bytes | Server peak RSS bytes |
|---|---:|---:|---:|---:|
| Sequential SQLite | 15.203125 | 0 | 560,017,408 | 40,751,104 |
| Sequential Qdrant | 1.000000 | 0.015625 | 556,941,312 | 40,751,104 |
| Concurrent SQLite | 16.406250 | 0 | 587,800,576 | 40,968,192 |
| Concurrent Qdrant | 1.000000 | 0.093750 | 585,601,024 | 41,132,032 |

CPU accounting is coarse for sub-second server work. Host: Python 3.11.16, SQLite 3.53.1, NumPy 2.4.6, ONNX Runtime 1.31.0, Windows build 28000, 24 reported logical/physical CPUs, 51,132,588,032 bytes physical RAM. The host was not reserved/exclusively idle; no tail-latency confidence interval is claimed.

One-time model validation/load: **627.40 ms**; 1,000 document embeddings: **2,394.73 ms**; Qdrant seed + HNSW wait, excluding embeddings: **384.46 ms**. SQLite file: **9,236,480 bytes**; Qdrant storage after forced shutdown: **139,022,555 bytes**. Qdrant's WAL/segment allocation and SQLite's authoritative text/FTS/JSON have different coverage and allocation policies: not a storage-efficiency verdict, and not crash-recovery verification.

## Isolation, provisioning and cleanup

Docker was absent and WSL reported uninstalled. The official public Windows release worked without either. [Provision receipt](../artifacts/server-provision/qdrant-1.19.2/receipt.json) records the URL and GitHub-published archive digest:

- URL: `https://github.com/qdrant/qdrant/releases/download/v1.19.2/qdrant-x86_64-pc-windows-msvc.zip`
- Verified ZIP SHA-256: `7d86596f16c6e85d45a50312f5e16ccb51e059b62e3d7308110cb65b4c799a4d`.
- Executable SHA-256: `b25bcc612583333289b00754907639ee97cd28b8741d50f1b4ce0e2bd1ad12eb`.

The harness creates a UUID child of `artifacts/server-benchmark`, a new SQLite database and new server storage/snapshot/temp paths. It binds an ephemeral unused loopback port before launch, disables gRPC, clustering and telemetry, removes inherited `QDRANT_*` overrides, and uses its new run directory as the server cwd. It does not open `D:/Second Brain/.qdrant_storage`, `borg_vault`, any existing collection or a shared server. No global installation/configuration, staging, commit or push.

Primary run: spawned PID **7100**, loopback port **49524**. [Cleanup readback](../artifacts/server-benchmark/5234a80c81cf4d1bb2475a9a88d8a2dd/cleanup.json) confirms process exit and closed port. Only the owned `Popen` is terminated/waited. Windows `terminate()` is forced shutdown (returncode 1), **not graceful durability/recovery acceptance**. A separate process lookup confirmed PID 7100 no longer existed. Earlier failure/test runs also executed the same finally cleanup; evidence remains in their unique directories.

## Reproduce and tests

Prerequisites: repository `.venv` with `requirements-hybrid.lock`, verified MiniLM artifacts under `artifacts/models/minilm`, and the extracted official executable at `artifacts/server-provision/qdrant-1.19.2/qdrant.exe`. Provisioning is deliberately explicit rather than a hidden network operation in a benchmark. To provision on another host, download the ZIP from the URL above, verify the **exact** digest before extracting, retain a local receipt, and use a new destination. The harness fails rather than falling back to Qdrant-client local mode.

```bash
rtk proxy .venv/Scripts/python.exe -m unittest discover -s tests -p server_benchmark_test.py -v
rtk proxy .venv/Scripts/python.exe tools/server_benchmark.py --documents 1000 --repeats 3 --concurrency 4
rtk proxy .venv/Scripts/python.exe -m unittest discover -s tests -p '*_test.py' -v
rtk git diff --check
```

**Three harness tests passed**, including a real 64-document server/HNSW run and cleanup. The full Python discovery passed **14 tests**, including the concurrently developed technical-quality tests and existing OCR/metrics tests. New tests were observed failing before implementation. Rust was unchanged and its suite was not rerun by this workstream. GSD CLI was available but local `STATE.md` absent; no global install or planning-file overwrite was attempted. Beads task: `bk-npj`, isolated benchmark acceptance only.

Two implementation defects were observed and corrected before the primary run: Qdrant 1.19.2 rejects `full_scan_threshold=0` (minimum 10 KB), and a main-thread HTTP connection can expire while worker blocks run; final telemetry now opens a fresh connection. A third guard initially hashed unrelated concurrent-worker source additions; it now binds the explicit execution inputs rather than claiming the whole repository was frozen.

### Review and remaining boundaries

Editorial review, not visual/UI certification: round 1 rejected a speedup/engine-verdict framing because Python JSON decoding and ANN recall loss confound it; corrected the title, backend labels, recall and GIL warnings. Round 2 checked denominators, raw-evidence links, resource ownership, differing disk coverage and Windows forced shutdown; corrected throughput and cleanup wording and distinguished input stability from whole-repository immutability.

Next useful validation: a larger heterogeneous approved technical corpus with independent relevance judgments; then compare a Rust resident-inference/compact-vector path against the same server and citation boundary. Neither production migration, model selection nor global activation follows from this synthetic Python result.
