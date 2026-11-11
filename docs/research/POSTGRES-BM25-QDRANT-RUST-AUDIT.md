# PostgreSQL, BM25, Qdrant and Rust: initial audit

**Scope:** source inspection and current primary-source research, 2026-10-19 UTC. No installation, build, corpus ingestion, private/vault access, service startup, configuration change or Git write. Only this new report and its task-local evidence directory are repository deliverables. Source conclusions refer to the hashes in [source-receipts.json](postgres-bm25-qdrant-rust-audit-evidence/source-receipts.json), not to an unavailable commit.

## Decision in brief

1. **Do not migrate to PostgreSQL on the strength of “thematic ranking.”** The colleagues' actual extensions, schema, query, model and evaluation are unknown. Native PostgreSQL full-text ranking, extension BM25, topic tags and embedding similarity are different mechanisms.
2. **BM25 is already present** in the Rust CLI and Python experimental lexical branches. The important untested product change is not “add BM25,” but change restrictive candidate matching, evaluate lexical-only fairly, and preserve exact applicability. The resident Qdrant adapter's explicit lexical mode is an exception: it uses distinct word overlap, **not BM25**.
3. **There is no implemented Rust → Qdrant path in the inspected crate.** Rust reads SQLite and optionally spawns a short-lived Python encoder; a separate resident Python JSONL runtime calls Qdrant over HTTP. Improving “Rust Qdrant tool calls” therefore requires an explicit integration design, not optimization of a nonexistent Rust Qdrant caller.
4. Preserve the SQLite revision/outbox/hydration safety boundary. First compare lexical BM25 alone, dense alone, fusion and matched-pool reranking. Then isolate metadata, token-safe chunking and transport improvements. PostgreSQL and native Qdrant sparse BM25 are optional benchmark arms, not prerequisites or selected replacements.

## 1. What was actually inspected and exercised

- First shell command: `rtk --version` → `rtk 0.48.0`.
- Repository: `D:/Projets/BorgKnowledge`; branch `feat/local-knowledge` is **unborn**. `git log -1` returned exit 128, no commits. The worktree already contains staged Beads files and broadly untracked project files. No commit identifier can honestly pin this audit; source SHA-256 receipts do.
- Read `Cargo.toml`, all `src/*.rs` via the relevant callers and entry points, `tools/knowledge_runtime/{__init__,__main__}.py`, `tools/agent_knowledge_runtime.py`, embedding and retrieval harness code, README and runtime documentation. Direct source is the authority; no code-graph coverage claim is made.
- Existing release executable `--help` and `python -B -m tools.knowledge_runtime --help` succeeded without starting a runtime or opening a corpus DB. This verifies entry-point availability, **not** binary/source parity, production integration or retrieval quality.
- An in-memory, synthetic three-document FTS5 sanity check returned one candidate for `"sqlite" AND "backup"` and two for `"sqlite" OR "backup"`. It verifies match semantics only; it is not a relevance benchmark. Commands, exits and actual rows are retained in [inspection-receipts.json](postgres-bm25-qdrant-rust-audit-evidence/inspection-receipts.json).
- No incumbent database, Qdrant collection, running endpoint or colleagues' system was queried. No timing/relevance campaign was rerun. Historical documentation claims are not newly verified measurements here.

## 2. Actual call paths: Rust and Qdrant are separate

| Path | Exact inspected locations | Actual behavior |
|---|---|---|
| Rust entry/dispatch | `src/main.rs:1–7`; `src/app.rs:15–81,456–516` | Clap CLI with explicit `--db`; lexical/hybrid search, get, structured records, indexing and backup. No resident JSONL or MCP command. |
| Rust lexical | `src/app.rs:423–454`; `src/records.rs:248–275` | SQLite FTS5 MATCH, literal whitespace terms joined by AND, ordered by `bm25(...)` ascending with ID ties. |
| Rust hybrid | `src/semantic.rs:211–295` | Reads derived JSON vectors from SQLite, dot product against normalized query vector, cosine top60 plus lexical top20, RRF. No Qdrant client/server involved. |
| Rust encoding boundary | `src/semantic.rs:48–110`, especially `62–80`; `tools/embed.py:12–47,50–58` | `Command::new(python).arg("-I").arg(tools/embed.py)` with local input/output JSON scratch files, 600-second subprocess timeout. Helper hashes model artifacts and creates tokenizer/ONNX session per process. Not HTTP and not JSONL. |
| Resident Python entry | `tools/knowledge_runtime/__main__.py:11–28,29–52` | Constructs Python `Runtime` once, emits readiness, serial bounded stdin/stdout JSONL. No HTTP listener and no MCP server. |
| Controlled-folder sync | `tools/knowledge_runtime/__init__.py:19–34` | Observe explicit basenames, compute expected hashes, ingest SQLite revisions/outbox, then reconcile Qdrant. Delegates other operations unchanged. |
| Python → Qdrant | `tools/agent_knowledge_runtime.py:82–107,296–327,339–374` | Loopback HTTP REST with `http.client.HTTPConnection`; point upsert/delete/readback and `/points/query`. This is the actual Qdrant integration. |

`Cargo.toml:7–18` contains `rusqlite`, CLI/serialization/hash/filesystem/tempfile/timeout dependencies, **no `qdrant-client`, `reqwest`, `tokio`, or PostgreSQL driver**. Searching every `src/*.rs` for `qdrant|http|reqwest|TcpStream|agent_knowledge|knowledge_runtime` returned no matches. This negative evidence is scoped to this crate; it does not prove no other project uses Rust/Qdrant.

### Cold startup and transport implications

- Rust `search --mode hybrid` calls `encode()` for each invocation (`src/semantic.rs:249`), which launches a helper; `tools/embed.py:25–31` creates a new tokenizer/session. Replacing vector storage alone cannot remove that model startup.
- Python runtime loads one encoder/session per resident worker (`agent_knowledge_runtime.py:154–156`, `Encoder:40–79`) and preserves it across JSONL requests. Keep stdin open; launching this worker once per tool call discards its principal lifecycle advantage.
- REST currently opens and closes a new connection **for every** remote operation (`94–107`), with a five-second socket timeout; sync encodes and upserts one point at a time and performs readback (`303–322`). Warm connection reuse, bounded batching and deduplicated per-request source hashing are plausible optimizations, not measured speedups.
- JSONL is the agent-to-worker framing; REST/JSON is worker-to-Qdrant framing. Neither should be confused with Rust's scratch JSON or with MCP. The official Rust Qdrant client uses gRPC/Tonic and requires an enabled gRPC endpoint; it cannot be dropped onto the current HTTP-only runtime contract without deployment work.[9]
- `docs/KNOWLEDGE-RUNTIME.md:24,35,98` illustrates `grpc_port: null`, separately owned Qdrant lifecycle and no hard inference deadline. This is documented configuration, not a live listener observation.

## 3. Existing lexical ranking is not one uniform system

| Surface | Candidate matching | Ranking/fusion | Important limit |
|---|---|---|---|
| Rust default lexical | Quoted whitespace terms AND; FTS5 `unicode61 remove_diacritics 2` (`app.rs:105,432–450`) | Real FTS5 BM25 for records and chunks | Structured records reserve slots before chunks (`436–444`); not a globally calibrated cross-type ranking. Structured filters select records only. |
| Rust hybrid | Same lexical AND path | Cosine top60 + lexical top20, equal RRF `1/(60+rank)` (`semantic.rs:281–295`) | Record/chunk lexical ranks are enumerated separately, then fused; not the same unit as a single global lexical list. No reranker or calibrated abstention. |
| Original quality harness | `tools/technical_quality.py:129–141`: text-only FTS5; whitespace AND | `fuse:144–149`: dense60 + lexical20, RRF k60 | No Rust title/record index. Harness is not the Rust product. |
| Later experimental lexical OR | `tools/retrieval_ablation.py:48–61` | Real FTS5 BM25, OR over extracted technical tokens, top20 | Changes both query splitting and Boolean semantics relative to whitespace AND. Not wired into Rust or resident runtime. |
| Later experimental fusion/rerank | `tools/retrieval_refinement.py:6–27,185–211` | Source gate → RRF → pool5/10/20; optional cross-encoder on same pool; final gate | Explicitly “no runtime wiring”; gate covers a narrow source/version policy, not universal applicability. |
| Resident Python lexical | `agent_knowledge_runtime.py:344–359` | Count intersection of distinct `\w+` query/body terms; UUID ties | No TF saturation, IDF, length normalization, FTS table or hybrid option; scans all active chunks. |
| Resident Python semantic | `agent_knowledge_runtime.py:360–374` | One dense Qdrant query top64, then authoritative hydration/signature check | No lexical fusion, reranker, topic/version filter or abstention. |

FTS5's `bm25()` is genuine BM25: it uses corpus statistics and length normalization, with hard-coded `k1=1.2`, `b=0.75`; it negates the score so lower values are better, and supports per-column weights.[2] The inspected Rust query uses no explicit weights; text and combined title/heading are distinct FTS columns (`app.rs:397–400,446`).[2]

**BM25 scoring and AND/OR selection are orthogonal.** A passage rejected by MATCH cannot be rescued by a better ranker. Restrictive AND over a natural-language question can remove useful evidence before scoring; OR admits more candidates but can elevate common-word distractors. These are hypotheses to test per query, not proof OR always wins. Technical punctuation matters too: the experimental regex preserves dotted/underscored query strings, but FTS5's tokenizer still determines indexed token boundaries. Literal quotes do not guarantee byte-exact matching of `->>`, `C++`, or an identifier.

A real lexical baseline should therefore include unchanged AND, same-token-list OR (isolating Boolean semantics), and the existing technical-token OR as separately named variants. Stopwords, stemming, field weights, exact identifier channels and language handling belong in later controlled ablations, not an unannounced “BM25 upgrade.”

## 4. Qdrant storage/content audit

### Verified current schema and invariants

- New collections have one unnamed 384-dimensional Cosine vector (`agent_knowledge_runtime.py:169,204`), plus a sentinel owner/model point (`170–172,205–207`). No sparse vector is configured.
- Content point payload is exactly `owner`, `model`, `id`, `revision`, `sha256` (`325–327`). Original bytes, relative path, text and `[start,stop)` character offsets remain in SQLite revisions/chunks (`175–181,279–290,329–337`). This is intentional authoritative hydration, not “missing text in Qdrant” by itself.
- UUIDv5 chunk identity binds generation, model, source basename, revision, source hash, start offset and recipe (`284–289`). New immutable revisions, invalidation and pending deletes/upserts commit together (`264–290`). Updates/deletions cannot simply reuse an old identity as current.
- Sync verifies source freshness and owner; upserts/deletes use `wait=true`, then point readback before clearing pending (`296–322`). Failed operations retain replayable jobs. Recovery requeues jobs against the same authority (`196–212`). There is no cross-store atomic transaction, but there is a durable outbox.
- `hydrate()` rejects inactive or live-hash-stale evidence (`329–337`); semantic results must match their SQLite signature (`364–371`). Stats checks current-source hash plus identity/payload coverage, explicitly **not vector-value attestation** (`376–398`). These are useful safety properties to preserve.

### Gaps and smallest safe interventions (proposals, not edits)

| Priority | Observation / evidence | Consequence and proposed change |
|---|---|---|
| P1 | No payload-index creation and no Qdrant query `filter` anywhere in this runtime; semantic top64 is unfiltered (`169,204,361–362`) | Owner sentinel, obsolete/orphan points and eventually inapplicable points can consume candidate budget before local rejection. Add explicit `role=chunk`, owner/model and active-source revision eligibility policy; apply supported filters before candidate selection and revalidate at hydration. Continue outbox reconciliation: filters must not replace deletion. |
| P1 | Payload has no product, version, language, source/parent ID, title, heading, topic or authority fields (`325–327`) | No server-side applicability/topic constraint or parent diversity grouping is possible from these fields today. Define metadata from original sources with provenance and UNKNOWN handling, not from relevance labels. Keep authoritative copy in SQLite and project only needed fields into derived payload. |
| P1 | Fixed non-overlapping 400-character slices (`284–289`); no title/heading context in the embedding call (`311`) | Can split sentences, APIs and proof context. Compare token-safe, structure-aware slices with exact parent offsets and stable citations; keep unchanged segmentation as the first baseline. |
| P1 | Tokenizer truncates (`58`), counter increments at `>=max_length` (`72`) | “At token limit” is not a count of definitely truncated inputs. Character bounds do not guarantee token fit. Retained MiniLM manifest specifies 128 tokens, 384 dimensions, empty prefixes. Measure untruncated tokens, actual discarded tokens and body proof loss separately. |
| P1 | Pending state is reported but not a semantic coverage gate (`359,374,397`) | New current chunks may lack vectors after failed sync; old vectors remain until deletes replay. Search is freshness-safe but may be incomplete. Return explicit partial coverage/degraded status, reconcile pending jobs and consider bounded refill after rejecting candidates. Never silently claim full coverage. |
| P2 | No stored document title/heading in this adapter; Rust has title/heading FTS context (`app.rs:348–400`) but Rust embedding uses heading+body (`semantic.rs:124–130`) | Avoid treating all surfaces as equally context-enriched. Test compact deterministic source context only within measured spare token capacity; maintain unmodified authoritative body and citations. Do not prepend long URLs/titles that displace proof. |
| P2 | Per-point encoding, HTTP connection and readback; repeated file hashes during hydration | Measure batching, connection reuse and per-request hash cache under source-stability guards. Retain acknowledgement/readback and pending replay semantics, and test partial-batch failure. |
| P2 | Single serial worker and exclusive SQLite lock; even lexical startup constructs encoder and verifies Qdrant (`141–156,212`) | Not a Qdrant-independent lexical fallback. A future explicit offline lexical mode needs separate startup/dependency behavior, not just the existing mode switch. Add bounded deadlines and response correlation at the consumer. |

Qdrant payload indexes accelerate filtering and help cardinality planning; vector indexes alone do not provide that. Official guidance says to index fields used in filters and create payload indexes **before** ingesting data so filter-aware HNSW can benefit; payload indexes cost memory/disk.[7] Proposed initial indexed fields are keyword/UUID-compatible owner/model, role, source/parent ID, product/version and language **only where real query filters use them**; topic IDs can be keyword arrays. Do not index every diagnostic/hash field by default.[7]

A `text` payload index for matching is not itself BM25 ranking. Current Qdrant documentation distinguishes full-text filtering from ranked full-text search using sparse vectors, including native `qdrant/bm25` inference or client-generated vectors.[11][12]

Native BM25 needs an explicitly configured sparse vector and IDF modifier; the inspected dense-only runtime does not use it.[11]

The docs expose `k`, `b`, and `avg_len` (default 256), default English processing and consistent ingest/query options; French/English technical text therefore requires an explicit language/token policy and a corpus-appropriate average length, not a promise of FTS5 rank parity.[11] Native BM25F is not currently supported according to this guide; separate sparse field vectors plus fusion are a workaround, not equivalent BM25F.[11]

## 5. What “PostgreSQL ranking / thematic” could mean

| Mechanism | What it actually supplies | What it does not establish |
|---|---|---|
| Native PostgreSQL `tsvector` + `tsquery`, `ts_rank` | Lexeme-frequency ranking, weighted fields and configurable normalization | **Not default BM25**. Official docs say its ranking functions do not use global information; they do not supply BM25 corpus-IDF semantics.[1] |
| Native `ts_rank_cd` | Cover-density ranking adds proximity and requires positional lexemes | Not semantic embeddings, BM25, or a calibrated probability. Stripped positional data can make it zero; rank/(rank+1) is cosmetic normalization.[1] |
| ParadeDB `pg_search` | Optional PostgreSQL extension delivering BM25 search/scoring and an index inside Postgres; current docs also describe vector/hybrid features | Not built-in PostgreSQL, and not proof the colleagues use it. Current score docs use `pdb.score(...)`; pin the installed extension before reusing older examples.[3][13][15] |
| `pgvector` + lexical search | Optional extension providing exact vector search and HNSW/IVFFlat; official guidance combines it with native FTS, RRF or cross-encoder for hybrid search | Does not make native FTS BM25. ANN recall, relevance, filtering and fusion must be evaluated separately.[5] |
| Explicit topic taxonomy | SQL tables/joins or JSON metadata grouping documents by known topics; can drive filters/facets | No evidence that a topic label entails an answer, authority or version compatibility. |
| Topic inference / clustering / dense embeddings | Potential semantic similarity across paraphrases/languages or learned topic assignments | Unknown here: model, training, prompts, taxonomy and human validation are absent. Embedding proximity is not a deterministic topic membership or evidence-confidence score. |

**Minimum questions for the colleagues:** PostgreSQL major version; `SELECT extname, extversion FROM pg_extension` output; exact DDL/index definitions and search SQL; whether “thématique” means curated tags, a topic classifier, clustering or embeddings; embedding/reranking models and their residency; language/tokenizer/stopword settings; AND/OR behavior; source/version/access filters; corpus/chunking; judged per-query examples; lexical-only/dense-only comparison; cold vs warm end-to-end timings. Request sanitized examples, not credentials or private documents. No installation or migration decision depends on receiving private material.

### Version, deployment and license constraints

- The fetched PostgreSQL `/docs/current/` page identifies **PostgreSQL 18**. This is what was actually read, not a claim that every deployment or prerelease is version 18.[1] PostgreSQL has its permissive PostgreSQL License.[16]
- Current `pg_search` source manifest exposes `pg15`, `pg16`, `pg17`, `pg18`, with `pg18` default. This is source-build capability evidence, **not** confirmation of a compatible packaged extension on this Windows host or a specific managed provider.[14] Current installation docs describe Docker and Postgres.app/macOS; the latter requires preload configuration, server restart and `CREATE EXTENSION pg_search CASCADE`.[17] No native Windows pg_search installation was verified. Pin an exact released tag, PostgreSQL major, operating system/architecture, provider extension availability and upgrade/backup protocol before a pilot.
- ParadeDB Community is **AGPLv3**, with commercial Enterprise licensing described separately; these are not the same license/deployment product.[3][4] This is an engineering constraint, not a legal opinion; review intended distribution/network-service obligations rather than assuming pg_search has PostgreSQL's license.
- The retrieved pgvector README installs **v0.8.7**, supports PostgreSQL **13+**, and documents a native Windows MSVC/nmake path as well as other packages.[5] Its LICENSE grants use/copy/modify/distribute rights subject to notices.[6] This is current README evidence, not a verified installed or latest-release inventory. ANN post-filtering can return too few results; iterative scans are documented from **0.8.0**, with scan-budget/order tradeoffs.[5]
- Qdrant's source license is Apache 2.0.[10] Repository runtime documentation references an existing **1.19.2** executable, but this audit did not run it or attest a live server version. Current docs describe Query API hybrid support from **1.10**, DBSF from **1.11**, parameterized RRF `k` from **1.16**, and some language-neutral BM25 processing from **1.19**.[7][8][11] Validate the exact chosen binary/client API rather than projecting all moving-current documentation onto old deployments.
- Qdrant's default RRF examples use `k=2` and a zero-based rank convention; this repository uses rank starting at one with `1/(60+rank)`. Specifying a parameter named 60 alone is not sufficient proof of parity: verify formula, index origin, weighting, candidate limits, ties and parent deduplication on frozen rank fixtures.[8]

## 6. Proposed fair benchmark (not executed in this audit)

### Freeze before selecting a backend or improvement

Use a public technical corpus first, with immutable original bytes/hashes, source versions/authority, normalized extraction plus offsets, one common chunk inventory, parent mapping, and a uniformly derived metadata schema. Keep extraction defects separate from ranking errors. Reuse the historical corpus only as a **reused diagnostic set**; obtain a fresh independently judged holdout before any generalization/activation claim. Never use query labels or chosen proof anchors to create titles/tags.

Predeclare at least these query strata: exact APIs/errors/operators and versions; natural-language questions; French/English paraphrases; broad topical discovery; near-topic distractors; wrong-version and unknown-version evidence; missing-answer and adversarial unsupported requests. Fix development/holdout split, presentation unit (parent evidence vs child point), top5, tie rules, filter semantics and UNKNOWN policy. Pool outputs for blinded relevance/applicability judgments; leave genuinely unjudged documents UNKNOWN.

### Primary ranking arms on the same evidence units

| Arm | Prespecified purpose |
|---|---|
| L-AND | Existing FTS5 BM25 whitespace-AND lexical-only top5; no embedding cost. |
| L-OR-controlled | Same query token list, OR instead of AND: isolates candidate matching. |
| L-OR-existing | Existing technical-token OR FTS5 BM25 lexical-only top5: separates the already implemented experimental variant. |
| D-exact | Same pinned resident dense encoder, exact similarity, top5: establishes dense relevance independently of ANN. |
| D-ANN | Same vectors/query vectors, Qdrant ANN with frozen params, top5; report ANN recall against D-exact separately. |
| H | Frozen lexical20 + dense60, unique-parent resolution before equal RRF k60, top5; exact formula and deterministic ties. |
| H+R | **Identical H candidate pool** bounded to a frozen budget (initially20), resident pinned cross-encoder, top5; unchanged filters and evidence text. |

First report the existing baseline path beside these common-unit arms; do not conceal differences between Rust record-priority ranking, text-only harness and resident 400-character runtime. For reranking, store the exact pool and all logits and assert pool equality. Separately vary budgets 5/10/20 with matched reranked/unreranked controls; do not let a reranker win by accessing more candidates. Add independently judged pure lexical reranking only as another explicitly budgeted arm.

Optional **storage/engine arms after primary baselines**: native PostgreSQL `ts_rank` and `ts_rank_cd`; pg_search BM25 lexical-only; pgvector exact/ANN plus the same lexical fusion; Qdrant sparse BM25 lexical-only and sparse+dense fusion. Freeze PostgreSQL/extension/server versions, lexeme/tokenizer configuration, field weights, IDF scope, length averages and precision. BM25 implementations may differ in scoring details; call these matched-input engine comparisons, not mathematically identical scores. Do not simultaneously change chunking, model and database and attribute the gain to PostgreSQL or BM25.

### Required outputs and acceptance

- **Every query:** exact question; ordered top5 full proof excerpts with URL/path, source revision/hash and offsets; relevant/incompatible/UNKNOWN labels; missing slots; P@1/P@3/P@5, recall@5, reciprocal rank, candidate recall and incompatible/unknown-version counts. Define denominator k; do not equate MRR or ANN recall with answer precision.
- **Decision quality:** correct accepted / all accepted evidence, answerable accepted / answerable queries, abstention, answerable rejection and no-answer false acceptance. Calibrate any acceptance rule on development only, freeze before holdout; RRF/cosine/logits are not confidence. Require the user's **≥90% presented-evidence precision** plus useful coverage and controlled no-answer behavior, with sample sizes/uncertainty; incomplete selected labels cannot certify that threshold. Do not pass by answering almost nothing.
- **Performance:** independently measured wall-clock end-to-end search+hydration+serialization p50/p95, not just sums of shared stages. Also report query encoding, lexical stage, transport/backend, fusion, reranking and source-hash work. Separate cold CLI/helper startup, worker readiness/model hashing/load, warm resident calls, Qdrant indexing readiness and offline ingestion. Pin hardware/thread counts, warmup, schedule seed/repeats, actual server/client versions, payload bytes, memory/storage and indexed-vector coverage.
- **Lifecycle:** later, on newly authorized disposable fixtures, exercise insert/update/delete, pending replay, acknowledgement loss, restart, no resurrection, vector/payload corruption and strict applicability. Backend selection, operational acceptance and relevance acceptance are three separate verdicts.

### Recommended implementation order after approval

1. Obtain a sanitized description/query from colleagues; keep their stack unknown until then. Complete fresh fair lexical-only/dense/fusion comparisons before revisiting the selected development storage backend.
2. Add a real BM25 lexical branch to the resident runtime by reusing the inspected FTS5 approach, with explicit mode and failure/coverage semantics; test OR separately, not as a hidden replacement.
3. Project source-derived applicability/parent metadata into payload, create only useful indexes, filter before selecting candidates, retain final hydration checks, reconcile pending data and expose partial coverage.
4. Isolate token-safe body slicing, then non-displacing deterministic context enrichment. Confirm parent evidence/citation fidelity before any relevance claim.
5. Add bounded resident reranking only if matched-pool evidence supports its CPU/quality tradeoff. Keep abstention calibration separate.
6. Only then choose Rust integration: a narrow typed serial JSONL consumer retaining one Python worker is the smallest reuse path; direct Rust REST/gRPC and resident inference is a larger alternative. Preserve explicit allowlists, request IDs, bounded output/deadlines, outbox ownership, source revisions and untrusted-evidence treatment. Benchmark complete paths before claiming a language/transport speedup.

## 7. Evidence, limitations and verification

Task-local ledger: [citation-ledger.json](postgres-bm25-qdrant-rust-audit-evidence/citation-ledger.json). Web receipts preserve requested/final URLs, UTC retrieval time, HTTP result, raw SHA-256 and saved raw/text filenames. Official sources are live retrieval snapshots; GitHub default-branch docs are **not release pins**. Raw bodies and extracted text are retained for quote checks; public HTTP session cookie metadata was not retained in receipts.

`web_extract` could not extract with the configured search-only backend. Direct public HTTPS retrieval succeeded instead. A legacy Qdrant FastEmbed BM25 URL and an attempted ParadeDB extension-install URL returned 404; corrected official documentation paths were retrieved, and failures remain in web receipts. Search fallback produced no result for one narrow ParadeDB query; manifest and linked official install docs supplied stronger evidence. No missing prerequisite was concealed by an installation or fabricated benchmark output.

The report does **not** establish: colleagues' implementation; live Qdrant configuration/index state; source/binary identity; actual token-loss count; modern pg_search package compatibility on Windows; a speedup, ≥90% relevance or a PostgreSQL migration benefit. Static gaps are recommendations until exercised in an authorized isolated pilot.

Verification receipts include source-hash stability, fetched-byte hashes, CLI/help outcomes, the synthetic in-memory MATCH check and citation-ledger verification. No source/config files were edited, no Git-mutating command (add/commit/reset/ref update) was run, and no private/vault/source corpus was opened. Git status/log were used for inspection; byte-for-byte Git index preservation was not instrumented.

## Sources

[1] https://www.postgresql.org/docs/current/textsearch-controls.html — postgres-ranking
[2] https://www.sqlite.org/fts5.html — sqlite-fts5
[3] https://raw.githubusercontent.com/paradedb/paradedb/main/README.md — pg-search-readme
[4] https://raw.githubusercontent.com/paradedb/paradedb/main/LICENSE — pg-search-license
[5] https://raw.githubusercontent.com/pgvector/pgvector/master/README.md — pgvector
[6] https://raw.githubusercontent.com/pgvector/pgvector/master/LICENSE — pgvector-license
[7] https://qdrant.tech/documentation/concepts/indexing — qdrant-indexing
[8] https://qdrant.tech/documentation/concepts/hybrid-queries — qdrant-hybrid
[9] https://github.com/qdrant/rust-client — qdrant-rust
[10] https://raw.githubusercontent.com/qdrant/qdrant/master/LICENSE — qdrant-license
[11] https://qdrant.tech/documentation/search/text-search/full-text-search/index.md — qdrant-fulltext
[12] https://qdrant.tech/documentation/inference/inference-bm25/index.md — qdrant-inference-bm25
[13] https://www.paradedb.com/docs/start/introduction — pg-search-overview
[14] https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/Cargo.toml — pg-search-cargo
[15] https://www.paradedb.com/docs/reference/full-text/score — pg-search-score
[16] https://www.postgresql.org/about/licence — postgres-license
[17] https://www.paradedb.com/docs/start/install — pg-search-install-current
