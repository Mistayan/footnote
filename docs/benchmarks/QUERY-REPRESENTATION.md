# Query representation: executed negative control, not storage migration

**Outcome: reject technical-only lexical routing.** On 24 reused answerable diagnostics, selected top1 **13/24 (54.17%) → 11/24 (45.83%)**, with no top1 gains and two losses. French top1 **2/9 → 1/9**. A cheap, translation-free representation is not enough to repair multilingual constraints. Keep the incumbent; no default was changed.

**Status: OPEN, pending parent verification.** The user's first milestone is **80% top1**, then **90%**, for a personal agent knowledge store. Neither threshold is reached or certified here. These old incomplete labels are diagnostics, not independent acceptance judgments or exhaustive semantic precision. No enterprise qualification is being introduced.

## What actual existing errors imply

Read before implementation: [academic retrieval by theme](../research/ACADEMIC-RETRIEVAL-BY-THEME.md), [multilingual embeddings](MULTILINGUAL-EMBEDDINGS.md), [fusion experiments](FUSION-EXPERIMENTS.md), [fusion weights](FUSION-WEIGHTS.md), [candidate and abstention](CANDIDATE-AND-ABSTENTION.md), plus the actual helper implementations.

- Both existing bi-encoders are multilingual. E5 native context improved candidate recall but not final relevance; a new database does not correct its representations or ranker.
- Same-host WAL evidence was already dense rank1; lexical fusion suppressed it for E5. That is not missing storage or necessarily failed cross-lingual encoding.
- The implicit French exclusion question lacks the literal operator. Previous branch reservation acquired `qfilter-not`, but the existing mMARCO cross-encoder ranked it11 and presented incompatible `must` first. The problem is not merely replacing underscores, missing original text, or increasing a pool.
- Prior structure/heading trials and exact-index replacement already failed to dominate. This work therefore tests a different, narrow **query-side** lexical representation, not another segmentation or database sweep.

## Primary research, mechanisms and transfer limits

Fetched primary pages, literal supporting quotes, URLs, response hashes and task-local citation ledger are retained in [`workstream-d-research`](../../artifacts/query-representation/workstream-d-research/). Product docs describe capabilities, not independent performance. No community anecdotes were used as evidence.

### Multilingual mismatch and preserving technical tokens

**CLIRudit**, Francisco Valentini, Diego Kozlowski and Vincent Larivière, arXiv **2504.16264v1**, 22 April2025: full HTML retrieved, methods and results discussion read; treated here as a **preprint, venue not independently established**. It compares English queries against French scholarly metadata, including query/document translation and dense/sparse retrievers. Its discussion finds document translation generally stronger than query translation for sparse retrievers, and identifies mistranslated proper names and lexical overlap through acronyms/proper nouns. This is evidence for language alignment and technical-token preservation, not proof for our opposite FR→EN code-document task.[1]

Practical candidate: preserve original dense query and immutable technical spans, translate only natural-language spans locally, then search a bounded pivot-language lexical representation. Translation must retain negatives, versions and code exactly; replacing an implicit French exclusion phrase with a guessed operator would be answer injection, not translation. No verified local translation checkpoint was loaded here; no translation or LLM generation is claimed executed. Translation has online generation cost; document translation has larger offline/update/storage cost and must remain a derived routing view, never the citation authority. The paper's hosted translation setup is **not** an allowed execution recipe for personal data.[1]

The chosen cheaper test asks whether **shared technical atoms alone** can remove lexical cross-language noise while the original dense query preserves intent. This is our hypothesis inspired by the lexical-overlap observation, **not a CLIRudit algorithm reproduction**.[1]

Character n-grams are another cheap representation for spelling/morphology and code fragments, but do not translate an absent concept or preserve logical scope by themselves. Not executed; no hypothetical gain is assigned.

### Learned sparse expansion is not multilingual merely because it is sparse

**SPLADE**, Thibault Formal, Benjamin Piwowarski and Stéphane Clinchant, 2021: original arXiv abstract/metadata retrieved here, not the full paper newly reread. The existing academic report separately inspected the SIGIR author PDF. SPLADE learns sparse term weights/expansion with sparsity regularization and an inverted-index-compatible representation; changing the database without supplying learned representations does not implement it.[2]

CLIRudit distinguishes English SPLADE++ from multilingual mGTE/BGE sparse models; even multilingual vocabulary does not eliminate cross-language lexical mismatch in that evaluation. Do not assume an English sparse checkpoint translates French, or replace literal code matching with generated vocabulary. New sparse inference/checkpoint licensing and nonzero-vector costs must be qualified separately; no SPLADE checkpoint was installed or tested here.[1]

### Late interaction targets finer evidence discrimination

**ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction**, Keshav Santhanam, Omar Khattab, Jon Saad-Falcon, Christopher Potts and Matei Zaharia, **NAACL2022**, verified in ACL Anthology. The official abstract/metadata were fetched here; the local academic report previously read the PDF. It combines fine-grained multi-vector late interaction, residual compression and denoised supervision. No numerical paper result is reinterpreted as local top1 accuracy.[3]

A bounded future comparison should hold the admissible pool fixed and compare the current cross-encoder with a **qualified multilingual late-interaction checkpoint**, not reinterpret mean-pooled MiniLM token outputs as a validated ColBERT model. Per-token storage/scoring and checkpoint qualification are costs. MaxSim aligns terms but is not an automatic Boolean-negation or exact-identifier guarantee. Native compressed ColBERT indexes and generic multivector storage are not interchangeable implementations.[3]

## One frozen intervention and matched control

Implementation: `tools/query_representation_experiment.py`; tests: `tests/query_representation_experiment_test.py`. No existing helper/runtime files changed.

| Component | Both branches, frozen before replay/inference |
|---|---|
| Corpus/queries | Same136 original public parents,32 reused questions:24 selected-answerable,8 no-answer |
| Dense model | Existing pinned MiniLM parent128,384D; **original query unchanged** |
| Acquisition | Saved actual ANN dense60 ranks; FTS5 OR BM25 lexical20 |
| Fusion/pool | Equal RRF k60, deterministic ID ties, pool20; no refill |
| Gates | Existing original-query source-derived Python version gate after pool and independently at presentation |
| Reranker | **NONE in both branches**; paired first-pass intervention, not comparison against a production reranked pipeline |
| Presentation | First5 eligible original parents |
| Abstention | None in either branch; scores not confidence/probabilities |
| Repetitions | Two algorithm-replay blocks, reversing question/branch order; not extra relevance samples |

**Only changed input:** the intervention's lexical query keeps source-order deduplicated atoms containing underscores, a dot, a digit or uppercase characters after the first character; if none, retain the original query. It uses syntax, **no language/operator/domain dictionary, query IDs, answers, relevance categories or selected-proof text**. Examples: both French and English SQLite-WAL questions project to `SQLite WAL`; ``must_not sqlite3.connect 3.12`` survives byte-for-byte in the representation test. Title-case product names without those syntactic signals do not get special treatment. This is deliberately generic and imperfect, not a full language/code parser.

The projection preserves selected technical atoms but **drops all other lexical words**, including natural-language constraints/negation in that branch. The dense branch and gate always retain the complete original query. FTS5's existing tokenizer still processes the representation; the intervention does not claim exact symbolic matching or improved logical understanding. Source passages and citation offsets/hashes are never rewritten.

## Actually executed results

Primary evidence: [`paired-b5dc3ba5eb6c4cf795fd2a30b766f92d`](../../artifacts/query-representation/paired-b5dc3ba5eb6c4cf795fd2a30b766f92d/).

**128 algorithm-replay requests**, not128 new server requests:32 questions × two branches × two repetitions. Original raw dense ranks and HTTP responses are retained in `raw-dense-control.json`, historical manifest/input hashes are checked, lexical retrieval/fusion/gates/citations/JSON serialization are actually rerun. The baseline matches **32/32 historical top5s**. This establishes controlled replay parity, not a new full-server quality benchmark.

P@k counts selected-positive hits/k, absent slots zero. Recall5 and pool recall are macro selected-proof recall; MRR5 is truncated reciprocal rank, not accuracy. Quality table uses24 unique answerable questions, not timing repetitions.

| Branch | P1 | P3 | P5 | MRR5 | Recall5 | Pool20 recall |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | .5417 | .2500 | .1583 | .5986 | .7083 | .8750 |
| Technical projection | .4583 | .2222 | .1500 | .5396 | .6667 | .8333 |

| Subset | n | Baseline P1 / Recall5 | Intervention P1 / Recall5 |
|---|---:|---:|---:|
| French |9|.2222 / .3333|.1111 / .3333|
| English |15|.7333 / .9333|.6667 / .8667|
| Technical constraints, tiny reused diagnostic |3|.3333 / .3333|0 / .3333|

Computed paired effects, not a favorable-only sample:

- **Top1 gains0, losses2**: same-host `wal-network`1→2 and English `fts-prefix`1→2. WAL's original lexical constraints were not just removable noise.
- `holdout-05` loses the only presented selected backup proof `py311-backup` from top5; selected Recall5 falls overall.
- French coherent-backup `holdout-02` loses selected proofs from pool20: pool recall1→0.
- Implicit French exclusion `holdout-09` is unchanged: no technical syntax triggers projection, so the method cannot create the missing semantic alignment. Correct `qfilter-not` is still absent from top5; known incompatible evidence remains.
- Lexical representation changes23/32 queries; ordered top5 changes22/32. All32 paired changes are retained in `paired-changes.json`.
- No-answer retrieval false accepts **8/8 in both branches**. Incompatible top5 occurrences **2→2**; UNKNOWN occurrences **139→140** across32 unique queries. UNKNOWN is **not** proven irrelevant. No generated-answer accuracy or learned abstention was evaluated.

Every query, both ordered result sets, selected/incompatible/UNKNOWN status, original snippets/URLs/offsets/SHA256, P1/P3/P5, pool recall, RRF score and replay latency appear in [`PER-QUERY-REVIEW.md`](../../artifacts/query-representation/paired-b5dc3ba5eb6c4cf795fd2a30b766f92d/PER-QUERY-REVIEW.md). Full unchanged evidence bodies and scores are in `raw-results.json`.

### Latency and separately executed real-server smoke

Replay p50/p95: baseline **0.951/1.111ms**, intervention **0.915/1.100ms**,64 measured replay requests per branch. These intervals include live lexical query, gates, ranking, review/citation construction and JSON serialization; **exclude dense encoding and HTTP**. They are not E2E or a statistically established speed improvement.

Four **actual HTTP query requests** were separately executed on an owned isolated loopback **Qdrant1.19.2**, using the existing resident MiniLM model and all136 historical passage vectors uploaded into a fresh collection. All vectors/payload IDs were read back and checked. Same-host WAL and implicit French exclusion were each queried through both branches with fresh query encoding. Dense ranks and top5 matched the corresponding algorithm replay. Actual measured encode→HTTP→lexical→gates→citation-JSON smoke times were **6.904/4.978ms** for WAL baseline/intervention and **4.804/4.330ms** for exclusion. Four ordered requests, no warm-up/repetitions, are **only a functional smoke**, not a matched server-latency conclusion or full ANN acceptance.

Smoke's HNSW/query configuration is the same saved collection configuration, but tiny-corpus planner behavior/index maturity is not certified. `smoke-readback.json` retains server identity and point/vector readback; `smoke.json` retains raw responses. Owned PID23464/port55038 exited/closed. Returncode1 is Windows forced `terminate/wait`, **not graceful shutdown or durability acceptance**. No unrelated process was touched.

## Alternative engines: relevant capabilities, not measured superiority

| Engine | Actual fetched primary evidence | What it does not solve automatically |
|---|---|---|
| PostgreSQL + pgvector | Official pgvector README supports combining vectors with PostgreSQL full-text retrieval and explicitly suggests RRF or a cross-encoder.[4] | SQL joins/transactional metadata are useful operationally; vector storage does not supply translation, correct candidate labels or operator understanding. No PostgreSQL benchmark executed. |
| PostgreSQL + pg_search / ParadeDB | Current official RRF documentation combines BM25 text and vector branches with explicit weights/limits/SQL. Its page marks the illustrated native vector-search feature beta in0.25.0+; do not silently equate this newer recipe with pgvector deployment.[9] | It exposes essentially the same ranking choices that already lose WAL evidence here. Different lexical analyzers could matter but require a matched tokenizer/query test, not a migration claim. |
| Vespa | Official sample application uses dense retrieval plus ColBERT multivector reranking/MaxSim and RRF; includes model-export examples.[10] | Richer phased ranking could host a new representation, but the useful intervention is the checkpoint/ranker/representation. No Vespa deployment, license audit or local latency/accuracy measurement. |
| OpenSearch | Official hybrid-search documentation distinguishes score normalization/combination from rank-based RRF and recommends comparing on one's judgment lists.[7] | Normalization is a controllable method, not multilingual semantic repair. Reranking appears in linked navigation, but its detailed model-serving path was not fetched/tested here; no local cross-encoder integration claim. |
| Existing Qdrant | Official Query API supports prefetch and nested multi-stage queries.[8] | Present failures do not establish a missing storage capability. Keep the current backend while representations/ranking are tested separately. |

Initial extraction tool could not fetch with its configured search-only backend; direct public HTTPS capture succeeded. An old ParadeDB URL returned404 and the Vespa docs/blog host failed DNS. Recovery used the current official ParadeDB page and Vespa's official GitHub sample; all failures are retained in receipts, not represented as successful fetches. All product URLs are floating documentation snapshots bound to retained response hashes, not immutable version guarantees.

## Reproduce and acceptance boundary

From `D:/Projets/BorgKnowledge`, existing environment only:

```bash
env -u PYTHONPATH .venv/Scripts/python.exe -B tests/query_representation_experiment_test.py -v
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/query_representation_experiment.py \
  --verify artifacts/query-representation/paired-b5dc3ba5eb6c4cf795fd2a30b766f92d
# A separate fresh UUID artifact run, never overwrite a previous run:
env -u PYTHONPATH .venv/Scripts/python.exe -B tools/query_representation_experiment.py
```

**3/3 owned tests passed in4.062s**, including the complete replay and actual isolated smoke. RED failures were observed before each of three implementation slices. Tests cover bilingual projection with unchanged code/version spans, generic fallback, label-field poisoning invariance, unchanged original citation provenance, hash-mismatch rejection, version rejection, full paired replay parity and owned-server cleanup. `verify_run` checks retained file/input hashes, original source offsets/body hashes, live lexical rankings, fusion/gates/citation fields and per-query selected metrics. This verifier shares ranking helpers with the implementation; it is **not an independent audit**. No whole-repository suite was run.

First shell was `rtk --version`→0.48.0. No installs/downloaded checkpoints, LLM APIs, remote personal data, vault reads, runtime activation, shared-environment edits, staging, commits or other worker files changed. Only the two named new Python files, this document and unique `artifacts/query-representation/` outputs are owned by this workstream. `env -u PYTHONPATH` is command-local to avoid inherited Hermes Python3.14 packages shadowing the existing project Python3.11 environment.

## Recommendation and concrete next test

**Do not activate this projection or migrate storage to fix relevance.** The missing method is language/constraint-aware evidence discrimination, not the ability to persist another vector type. Technical atoms alone remove useful intent and fail the known negation case. Existing mMARCO's admitted-candidate negation failure also means “add any multilingual reranker” is not a sufficient next step.

Next bounded test: **original lexical representation versus original plus one locally produced pivot-language natural-text translation**, preserving code/version spans exactly and prohibiting operator inference; fix total dense/lexical acquisition, pool20, existing gate and reranker budget before judging. First qualify an actual permitted local translator; if none is available under download/compute authorization, leave this test blocked rather than call a hosted LLM. Include a same-pool ranking control so gains from better acquisition are not confused with reranker behavior. Translation is a hypothesis, not a promised gain. A qualified multilingual late-interaction same-pool challenger follows only if ranking remains the dominant loss.

Before claiming80% then90%: independently judge a fresh small bilingual/operator/no-answer set, pool judgments across systems, keep unjudged passages UNKNOWN, and report top1 correctness/applicability with answerable coverage and no-answer false acceptance. Reused-set gains—even if they had existed—would not certify either threshold. Parent task stays open.

## Sources

[1] https://arxiv.org/html/2504.16264v1
[2] https://arxiv.org/abs/2107.05720
[3] https://aclanthology.org/2022.naacl-main.272
[4] https://github.com/pgvector/pgvector
[7] https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index
[8] https://qdrant.tech/documentation/concepts/hybrid-queries
[9] https://paradedb.com/docs/documentation/hybrid/rrf
[10] https://raw.githubusercontent.com/vespa-engine/sample-apps/master/colbert/README.md
