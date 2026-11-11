# Alternative retrieval architectures for a personal multilingual agent

**Research snapshot: 20 October 2026. Decision: keep the current Qdrant development direction; no alternative has demonstrated a local relevance or speed advantage.** This is sourced architecture research, not an executed alternative-engine benchmark, migration, or acceptance result. Only this new report and its [unique public evidence directory](alternative-retrieval-evidence-20261020/) were authored. No installs, services, private ingestion, runtime edits, or global configuration changes.

## 1. Start from the failures, not the engine catalogue

The current [harmonized primary comparison](../QDRANT-QUALITY.md#primary-quality-results) returns identical ordered top5 on **32/32** questions for SQLite exact and Qdrant ANN ef128, with the same parent passages, query vectors, lexical branch, parent resolution, fusion and citations. Reused-holdout selected-label P@1 is **0.5000**, MRR@5 **0.6111**, recall@5 **0.7083**; both return candidates on **4/4** no-answer questions per split. These are repository-reported measurements reviewed here, not rerun in this task. Most questions have one selected positive and unjudged results remain UNKNOWN: selected-label P@5 is not exhaustive semantic precision. The [paired raw per-query artifact](../../artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/primary-pair-per-query.json) remains the inspectable source of the equality claim.

The more recent [candidate-depth diagnosis](../benchmarks/CANDIDATE-RECALL.md#diagnosis-why-must_not-disappears) locates the French negation proof `qfilter-not` at **dense rank10 under both exact cosine and Qdrant**; original fusion puts it rank24 outside pool20. Pool50 recovers it but does not present it top5. The [candidate/abstention experiment](../benchmarks/CANDIDATE-AND-ABSTENTION.md#negation-proof-evidence-present-candidate-loss-corrected-ranking-still-wrong) recovers it at quota pool rank10, yet the existing reranker puts it rank11 and promotes incompatible `must`. The actual negation sentence survives the 128-token representation. This failure is neither an absent source nor a demonstrated ANN approximation error.

The [reranker budget experiment](../benchmarks/RETRIEVAL-BUDGETS.md#résultat-exécuté) reports historical holdout resident E2E medians **4.884 ms without reranking versus 817.282 ms at budget20**; its gated top1 is still **0.6667**, and all four no-answer questions still receive candidates. Those costs are pipeline observations on a tiny public corpus, not transferable engine speed rankings. The newer optional abstention rule rejects all four reused-holdout no-answer queries but also **5/12 answerable questions**, with selected top1 **6/7** among accepted requests, not a 90% acceptance result.

**Interpretation:** a different nearest-neighbor database cannot by itself repair implicit French operator disambiguation, fusion suppression, a bad cross-encoder decision, missing version metadata, or absent proof. The current first milestone is ≥80% P@1 on all answerable questions, with ≥90% as the higher target; neither is achieved by this research. Presented-evidence precision, correct top1, answer correctness and useful coverage are different. No published score below is converted into local “accuracy80/90.” Coverage and no-answer false acceptance must be reported separately; proposed coverage floors are experimental criteria, not already approved or achieved results.

## 2. Separate what can actually improve

| Failure layer | Matched diagnostic | What a new engine could change | What it cannot establish |
|---|---|---|---|
| Extraction / representation | Is the exact proof visible in authoritative and model input text? | Storage of richer fields or token vectors | Faithful OCR/table extraction, missing proof recovery |
| Embedding/model | Exact similarity with identical vectors; French↔English and negation strata | Support a different representation | Better meaning from identical vectors merely by moving storage |
| ANN approximation | Recall against exact search on the same eligible vectors | Index type, filtering strategy, recall/latency trade-off | Semantic correctness of nearest vectors |
| Candidate acquisition | Selected-proof presence before fusion/budget | Lexical analyzers, union/query operators, refill | Ranker recovery of an excluded proof |
| Ranking | Identical candidate IDs/text, checkpoint, budget, ties | Native model execution, feature composition, co-location | Understanding negation or probability calibration |
| Applicability | Source-derived owner/revision/version eligibility before top-k, then recheck | Payload filtering or transactional relational joins | Compatibility inferred from an unknown version |
| Presentation / no-answer | Fresh blinded evidence judgments plus separately frozen refusal policy | Execution of a decision rule | Calibrated confidence from BM25/RRF/cosine/logits alone |

The table is an experimental decomposition proposed here, not a vendor finding. Preserve SQLite authority/hydration and current citation checks in ordinary Qdrant improvement experiments. A true single-database alternative is a different architectural trial and must say that authority moved.

## 3. Primary academic evidence: late interaction, not a database endorsement

**ColBERT**, Omar Khattab and Matei Zaharia, arXiv **2004.12832v2**, lists acceptance at **SIGIR 2020**. Only its abstract and metadata were read here: it separates query/document encoding and allows precomputed document representations rather than jointly encoding every query-document pair.[8] **ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction**, Keshav Santhanam, Omar Khattab, Jon Saad-Falcon, Christopher Potts and Matei Zaharia, arXiv **2112.01488v3**, has an independently checked **NAACL 2022** proceedings record.[7][24]

For ColBERTv2, retrieved full-text sections **§3.1–3.3, §3.4 and Limitations** were read; the whole paper and every result table were not exhaustively reviewed. The mechanism combines independently encoded token vectors with query-token MaxSim aggregation, residual compression and denoised supervision; candidate generation still precedes full scoring.[27] This can change representation/ranking cost, but a new trained checkpoint, document re-encoding, more token-vector storage and approximation controls are part of the intervention—not a free engine upgrade.[27]

The paper explicitly states that **all its evaluation benchmarks are in English**, and leaves other-language transfer for future work.[27] Therefore it does not demonstrate French negation resolution on this corpus. No cross-dataset numerical gain, storage ratio, nDCG or recall score is treated as a personal precision target. Model/checkpoint licenses, French capability, CPU ONNX export/parity and truncation must be checked for the exact candidate checkpoint before any future trial; the paper's publication or an engine's Apache license does not license an arbitrary model.

## 4. Capability comparison against the same Qdrant pipeline

### 4.1 PostgreSQL + pgvector + ParadeDB `pg_search`

pgvector provides exact search and optional HNSW/IVFFlat approximate indexes, and documents combining vector search with Postgres full-text retrieval.[1] ParadeDB documents BM25, tokenizers, filters and joins inside Postgres with SQL/ACID transactions; this is a primary vendor capability statement, not an accepted comparative quality result.[2] Its current tokenizer page distinguishes default Unicode word segmentation/lowercasing from configurable ngrams: these choices affect matching and are not multilingual semantic understanding.[3]

**Potentially distinct capability:** keeping source revisions, eligibility relations, evidence rows and derived searchable data inside one relational transactional authority. Native JOIN/EXISTS eligibility can express relationships without continually projecting every relation into a separate vector payload. ParadeDB documents join pushdown only under explicit requirements (indexes on participating tables; indexed keys/filter/order fields; a search predicate; LIMIT), with ordinary Postgres execution as fallback.[23] This is not proof that arbitrary joins, especially pgvector ANN plus those joins, share one accelerated path. The future trial must inspect actual query plans.

**What is not distinctive:** BM25, changed AND/OR acquisition, RRF, better embeddings and external reranking can be paired with Qdrant without migrating authority. pgvector says approximate-index filtering occurs **after** the index scan and documents iterative scans to acquire more eligible results.[1] SQL WHERE syntax alone is therefore not proof of prefiltered ANN recall or freedom from candidate starvation.

**Windows/CPU and license:** pgvector documents native Windows compilation with Visual Studio C++ and `nmake`; that does not prove `pg_search` native Windows readiness.[1] ParadeDB's install guide offers Docker and Postgres.app rather than a verified native Windows extension package in the material read.[16]
ParadeDB Community is **AGPL-3.0**, Enterprise commercially licensed; pgvector's separate permissive license must not be conflated with the extension or PostgreSQL distribution.[2][17] Planning assessment: additional PostgreSQL service, extension/version compatibility, backups and upgrades; Docker/WSL adds a Linux/container dependency on this Windows host. Nothing was installed or compiled; CPU cost and actual local compatibility remain unmeasured.

### 4.2 Vespa: native hybrid retrieval and phased ranking

Vespa documents combining retrieval operators and evaluating ranking on content nodes, followed by optional container/global ranking; it exposes bounded second-phase reranking and ONNX-oriented global inference.[19] Its official sample combines single-vector retrieval, ColBERT token-vector reranking and RRF.[22] The embedding documentation explicitly treats the ColBERT tensor as a **ranking** representation rather than input to `nearestNeighbor`, and suggests paged attributes to reduce memory footprint.[20]

**Relevant hypothesis:** co-located lexical/vector matching and bounded feature/tensor/model ranking may reduce application orchestration or tensor movement. It is not evidence of faster CPU inference, a superior checkpoint, operator understanding or no-answer detection. ColBERT itself is **not** a reason to migrate: Qdrant documents dense prefetch followed by multivector MaxSim reranking in one API call and disabling HNSW on reranking token vectors with `m=0`.[29]

**Windows/CPU and license:** reviewed operational docs describe Docker containers and host/Linux tuning, not a verified native Windows server route.[21] Core Vespa is Apache-2.0.[9] Planning assessment: application schemas, rank profiles, deployment and Linux/container resource tuning are a larger operational surface than the already demonstrated local Qdrant fixture. CPU ONNX model/operator compatibility and memory/latency for the exact multilingual model are unknown here. **Do not schedule a separate engine trial merely to obtain ColBERT**; first isolate the same late-interaction pipeline in Qdrant.

### 4.3 OpenSearch and Elasticsearch: mature lexical analysis plus semantic hybrid

OpenSearch documents hybrid pipelines with **score normalization/combination** or a **rank-based RRF processor**; those are different fusion recipes, not interchangeable defaults.[4] Elasticsearch documents full-text and vector search in one request and recommends an RRF combination.[5]
Both document language-specific analyzers, including French and English; OpenSearch additionally documents stem exclusions and plugin requirements for some languages.[14][25] Proposed multilingual design: separate language-analyzed fields or explicit language routing, plus a literal API/operator field, with a pinned multilingual semantic branch. This is a proposed design, not an already tested engine configuration.

**Against Qdrant:** the stronger reason is a substantial need for integrated lexical field analysis/query DSL and search operations, not “hybrid” as a unique feature. The same analyzers could be a lexical sidecar while Qdrant remains vector storage; existing Qdrant candidate/reranking experiments must receive the same model, text, metadata and budget. Stemming must not merge technical identifiers or remove meaningful negation; inspect analyzer output on the actual tokens before measuring retrieval. Neither language analysis nor RRF establishes cross-language entailment or refusal reliability.

**Windows/CPU and license:** OpenSearch's download page lists a Windows x64 ZIP and Apache-2.0 licensing; Elasticsearch documents Windows ZIP and service installation, bundled service management and JVM heap configuration.[11][15] This is published distribution availability, **not** verification that all chosen neural-search/native inference plugins work on this machine. Elastic distinguishes its default **ELv2 distribution** from source portions with **AGPLv3/SSPL/ELv2** options; do not describe it simply as Apache-2.0 or assume a desired reranking feature is included in a free tier.[12] Planning assessment: JVM service/heap, index mappings, analysis and plugin/model management create appreciable operational burden for a personal Windows deployment. Exact model hosting, local/offline execution and feature entitlements remain to verify; no hosted inference is assumed or authorized.

### 4.4 LanceDB multivector: useful embedded alternative, not a unique accuracy method

LanceDB documents per-row multivector columns, query matrices and MaxSim, currently **cosine-only** for multivector search; its example builds an IVF_PQ index.[6] Its documentation warns that unindexed multivector scans grow with both rows and vectors per row, and distinguishes OSS/Cloud/Enterprise safety behavior.[6]
Local storage and Python/Node/Rust integration are documented, and the core license is Apache-2.0.[26][10]

**Against Qdrant:** embedded/columnar ownership can be operationally attractive, but MaxSim is already available in Qdrant.[29] Testing LanceDB with a new token-vector model against old single-vector Qdrant would confound architecture, representation and model. Planning assessment: potentially fewer server lifecycle components, but wheel/platform support for the exact Windows Python/architecture, multivector ANN recall, concurrent read/write/delete behavior and end-to-end citation freshness are **not verified** here. No priority engine trial on current failure evidence.

## 5. Community evidence — separately labeled, not benchmark truth

1. **pgvector GitHub #721:** a user reports HNSW planner selection changing with LIMIT/filter selectivity, then inferior quality after forcing the index, and a move to a more tightly scoped index. A maintainer discusses scan cost and suggests planner-cost/hint investigation.[13] This is a workload-specific report with user-supplied plans, not a controlled comparison or proof pgvector is worse. It motivates exact-search controls and actual EXPLAIN/eligible-result measurements.
2. **ParadeDB GitHub #2686**, opened 11 June 2025 and displayed **Open** in the fetched page: the maintainer calls native Windows support low priority; the author reports a patched Windows11 install and locale/pgrx changes; a later maintainer reply still invites a contribution.[30] This is stronger evidence of friction than generic “Rust supports Windows,” but not a current reproduction or proof all native builds fail. Treat native `pg_search` readiness as unverified, not universally impossible.

Coverage: two inspected public GitHub discussions; no independent community Vespa/OpenSearch/LanceDB performance result was validated. Search snippets and vendor/community popularity were not substituted for read content. Vendor benchmark tables and speed slogans are deliberately excluded as evidence of causal engine superiority.

## 6. One conditional alternative worth a future matched trial

**Only nominate PostgreSQL + pgvector + `pg_search`, and only for relational transactional eligibility—not to chase a precision number.** The relevant architectural difference is a single authoritative transaction domain for source/evidence state and relational eligibility before bounded ranking. This cannot be obtained by simply attaching a new embedding, reranker or lexical branch to Qdrant; retaining a separate authority and Qdrant projection still requires synchronization. Qdrant payload denormalization and hydration rechecks may already be sufficient, so first establish that relational eligibility or reconciliation is a material limitation. This is a conditional feasibility nomination, not an instruction to migrate.

If that prerequisite is absent, **no alternative engine trial is justified yet**. Vespa native ranking co-location is interesting, but its core model/ranking methods are testable with Qdrant; OpenSearch/Elastic analyzers can be lexical sidecars; LanceDB MaxSim is not exclusive. The local evidence currently supports fixing candidate/ranking/no-answer behavior before changing storage.

### Evidence-backed experiment order (future work, none executed here)

| Order | Paired experiment | Freeze / control | Observable decision, not promised gain |
|---|---|---|---|
| 0 | Fresh multilingual evidence/answerability evaluation | Public/explicitly authorized corpus; independent deep judgments; dev/calibration and unseen question-disjoint test; literal identifiers, implicit negation, wrong/unknown version and no-answer strata | Presented-evidence precision, useful answerable coverage, false accepts, uncertainty and failures; no more tuning on the 32 observed questions |
| 1 | Improve ranking within Qdrant first | Identical eligible parent pool20/50, proof text, version policy and checkpoint; separately test a licensed multilingual late-interaction model against the existing cross-encoder | Candidate recall vs final rank; `must_not` proof vs incompatible `must`; E2E p50/p95, model encode, rerank CPU/RAM and index size. Qdrant MaxSim is documented, so engine migration is not necessary.[29] |
| 2 | Conditional Postgres feasibility / exact parity | Pin PostgreSQL/pgvector/pg_search versions and license; approved isolated container route if native support remains unresolved; same source revisions, exact vectors, lexical tokenization, eligibility, RRF rank origin/k/ties, pool and hydration | Reproduce exact eligible IDs first; inspect JOIN/vector plans and transactional visibility. Failure to match candidates must be explained before quality/speed claims.[1][23] |
| 3 | Distinct architecture capability test | Compare Postgres single-authority transactions with current SQLite authority + Qdrant reconciliation. Identical update/delete/revision schedule, crash boundaries, final presentation checks and query workload | Stale/deleted/unknown-version admission, useful eligible coverage, convergence, operational recovery and cost; do not pretend this is a storage-only relevance comparison |
| 4 | Approximate and timed matched replay, only after parity | Same vectors and allowed rows; exact oracle for each engine; controlled memory/threads, randomized paired blocks, warm/cold reported separately, network/inference/hydration all included in E2E | ANN recall distinct from judged relevance; common precision/coverage envelope then p50/p95, build/update time, resident memory/disk and startup/shutdown burden |

Use the actual current Qdrant pipeline—not a deliberately weak dense-only competitor—as the baseline. Separate an engine-only arm (common externally supplied embeddings/lexical candidates/reranker) from an architecture arm (native analyzers/joins/model execution). If native lexical analysis changes candidates, that is a lexical intervention. If model/checkpoint changes, that is a model intervention. Any accepted result must publish per-query proof, eligibility state, raw component ranks/scores, failures and exact denominators. Predeclare the precision/coverage/no-answer decision rule and CPU latency budget before the fresh test; no backend is accepted solely for fast ANN or recall.

## 7. Evidence integrity and blockers

The task-local [ledger](alternative-retrieval-evidence-20261020/ledger.json) maps citation IDs to fetched URLs and **literal quotes checked against saved text**. [citation-map.json](alternative-retrieval-evidence-20261020/citation-map.json) maps report citations to raw/text source files. Fetch manifests retain original/final URLs, UTC and HTTP failures. Exact content snapshots—not mutable live pages alone—are the evidence for this report; source branches and unversioned docs can change later. Academic versions read are identified above.

Actual retrieval issues: the configured `web_extract` backend was search-only and refused URL extraction; no global setting was changed. Standard-library HTTPS fetched primary pages instead. Direct `docs.vespa.ai` DNS failed, so the official documentation GitHub source was read. The first Qdrant URL returned a short redirect-target body; it was not accepted as substantive evidence, and the target tutorial was fetched. One guessed raw Qdrant path returned404 and was not cited. A quote-validation attempt rejected a long markup/truncated quote; shorter exact text and then explicit retained line ranges passed. These failures are preserved or described, not treated as source claims.

The retained OpenSearch and Qdrant core license texts both specify Apache License 2.0; model licenses remain separate.[18][28]

No alternative runtime, installation, model export, license entitlement, CPU inference plugin or fresh judged quality result was executed. Windows Docker/WSL availability and resource headroom were not inspected. Current engine/version capability documentation is not proof of compatibility with the already provisioned Qdrant1.19.2 binary or any future pinned version; test the exact APIs before a trial. No “80/90 accuracy” or alternative speed claim is made.

## Sources

[1] https://raw.githubusercontent.com/pgvector/pgvector/master/README.md — Source 1: # pgvector
[2] https://raw.githubusercontent.com/paradedb/paradedb/main/README.md — Source 2: <h1 align="center">
[3] https://docs.paradedb.com/documentation/tokenizers/overview — Source 3: Tokenizers - ParadeDB
[4] https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index — Source 7: Hybrid search | OpenSearch Documentation                      Link      Search      Menu      Expand      Document
[5] https://www.elastic.co/docs/solutions/search/hybrid-search — Source 8: Hybrid search | Elastic Docs
[6] https://docs.lancedb.com/search/multivector-search — Source 9: Multivector Search - LanceDB
[7] https://arxiv.org/abs/2112.01488 — Source 11: [2112.01488] ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction
[8] https://arxiv.org/abs/2004.12832 — Source 12: [2004.12832] ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT
[9] https://raw.githubusercontent.com/vespa-engine/vespa/master/LICENSE — Source 13:                               Apache License
[10] https://raw.githubusercontent.com/lancedb/lancedb/main/LICENSE — Source 14:
[11] https://opensearch.org/downloads.html — Source 15: Download & Get Started - OpenSearch
[12] https://www.elastic.co/pricing/faq/licensing — Source 16: FAQ on Software Licensing | Elastic
[13] https://github.com/pgvector/pgvector/issues/721 — Source 17: HNSW index bypassed when LIMIT or filter selectivity exceeds threshold · Issue #721 · pgvector/pgvector · GitHub
[14] https://docs.opensearch.org/latest/analyzers/language-analyzers/index — Source 19: Language analyzers | OpenSearch Documentation                      Link      Search      Menu      Expand      Document
[15] https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-with-zip-on-windows — Source 20: Install Elasticsearch with .zip on Windows | Elastic Docs
[16] https://docs.paradedb.com/documentation/getting-started/install — Source 21: Install ParadeDB - ParadeDB
[17] https://raw.githubusercontent.com/pgvector/pgvector/master/LICENSE — Source 22: Portions Copyright (c) 1996-2026, PostgreSQL Global Development Group
[18] https://raw.githubusercontent.com/opensearch-project/OpenSearch/main/LICENSE.txt — Source 23:                                  Apache License
[19] https://raw.githubusercontent.com/vespa-engine/documentation/master/en/ranking/phased-ranking.html — Source 24: ---
[20] https://raw.githubusercontent.com/vespa-engine/documentation/master/en/rag/embedding.html — Source 25: ---
[21] https://raw.githubusercontent.com/vespa-engine/documentation/master/en/operations/self-managed/docker-containers.html — Source 26: ---
[22] https://raw.githubusercontent.com/vespa-engine/sample-apps/master/colbert/README.md — Source 28:
[23] https://www.paradedb.com/docs/reference/joins/overview — Source 29: Supported Join Types - ParadeDB
[24] https://aclanthology.org/2022.naacl-main.272 — Source 30: ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction - ACL Anthology
[25] https://www.elastic.co/docs/reference/text-analysis/analysis-lang-analyzer — Source 31: Language analyzers | Elasticsearch Reference
[26] https://raw.githubusercontent.com/lancedb/lancedb/main/README.md — Source 32: <div align="center">
[27] https://arxiv.org/html/2112.01488v3 — Source 33: ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction
[28] https://raw.githubusercontent.com/qdrant/qdrant/master/LICENSE — Source 35:                                  Apache License
[29] https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations — Source 36: Multivectors and Late Interaction - Qdrant
[30] https://github.com/paradedb/paradedb/issues/2686 — Source 37: Add support for compiling `pg_search` on Windows · Issue #2686 · paradedb/paradedb · GitHub
