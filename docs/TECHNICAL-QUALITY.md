# Public technical retrieval quality — measured harness, not product acceptance

## Outcome

The standalone [harness](../tools/technical_quality.py) was executed twice against a frozen, bounded **real public technical corpus**. Both executions produced identical ranked query/engine rows, scores, metrics and abstention threshold. No vault, production database, existing Qdrant collection or production CLI was used or modified.

**Holdout:** FTS5 top1 **0.0833**, MRR@5 **0.0833**, macro recall@5 **0.0417**; MiniLM hybrid top1 **0.5000**, MRR@5 **0.6111**, recall@5 **0.7083**. Ungated hybrid returned candidates for **4/4 no-answer questions** and retrieved **one explicitly version-incompatible passage**. This does not establish safe answer generation or justify activation.

A development-fit experimental cosine gate reduced holdout no-answer false acceptance to **1/4**, but rejected **4/12 answerable questions**. It is not a calibrated answerability classifier, and is not part of the product.

## Exact retained evidence

All paths below are under `D:/Projets/BorgKnowledge/`:

- Snapshot: [`artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/`](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/).
- [Pre-inference freeze](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/freeze.json), SHA-256 `61b86569d4c7991ec52fb59be745358940d2b93d1b97d2fddc49403f42e7f8a6`; frozen at `2026-10-17T08:54:04.793149+00:00`.
- [Public source receipts](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/source-receipts.json): original/final URL, HTTP status, retrieval UTC, byte count, SHA-256, ETag/Last-Modified where supplied. Full fetched bytes and normalized text are retained in `sources/`.
- [Corpus](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/corpus.json): exact passage text, normalized-source character offsets, source ID and passage hash.
- [Frozen judgments](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/judgments.json): query, split, category, relevant IDs and explicitly incompatible IDs.
- First evaluation: [`evaluations/50a110e4a3404dd2a60883566d38e7b0/report.json`](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/evaluations/50a110e4a3404dd2a60883566d38e7b0/report.json), [raw query/engine rows](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/evaluations/50a110e4a3404dd2a60883566d38e7b0/raw-results.json), [receipt](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/evaluations/50a110e4a3404dd2a60883566d38e7b0/receipt.json).
- Each evaluation also retains `passage-vectors.npy`, one JSON per query with query vector, lexical top20, cosine top60, RRF top5 scores, labels and query-inference UTC, plus `development-results.json` and `frozen-threshold.json`.
- Replay: `evaluations/21d0c12148754a6d94c298ce6dc67417/` in the same snapshot. [Verification receipt](../artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/verification.json) confirms **136 exact source excerpts**, **37 first-run evidence-file hashes**, **96 query/engine rows**, and identical replay rows/metrics.

These artifact directories are ignored by Git: retain them separately when sharing the source tree. No `latest` pointer or historical evidence was overwritten.

## Corpus and judgment protocol

**10 official public source pages, 585,440 fetched bytes; 136 indexed excerpts:** 24 selected evidence passages and 112 additional same-domain passages from those pages. There are no invented technical documents or gardening distractors. Passage text is copied, not generated. SQLite HTML is parsed without scripts/styles and whitespace-normalized; Python reStructuredText and Qdrant Markdown are retained as source text. Stored offsets refer to normalized text, not raw HTML bytes. Markup and Qdrant documentation shortcodes are not rendered or recursively fetched.

Sources:

| Source | Pinned scope |
|---|---|
| Python `sqlite3` | Official `python/cpython`, tags **v3.11.9** and **v3.12.3**, `Doc/library/sqlite3.rst` |
| Python asyncio tasks | Same official repository, **v3.12.3**, `Doc/library/asyncio-task.rst` |
| SQLite | `sqlite.org/wal.html`, `isolation.html`, `fts5.html`, `backup.html`; time-bound bytes pinned by receipt hashes, not an immutable documentation revision |
| Qdrant | Official `qdrant/landing_page`, commit **3d4e1897a2ca017999ad3d77b1ade6f7530ca1ed**, `documentation/search/{filtering,hybrid-queries,search}.md` |

The full URLs are in the receipts and `SOURCES` constant. A guessed old Qdrant `concepts/filtering.md` URL initially returned a real 404; the official public GitHub tree supplied the current `search/` path. An initial preparation failed on a nonexistent BM25 anchor; the anchor was corrected against actual official text **before corpus/query inference**. The incomplete fetch-only directory `cc7e1e6cf118452590e25e7740fd158a/` has no freeze or evaluation and is not accepted evidence.

**32 author-made questions:** 16 development and 16 holdout; each has 12 answerable and 4 no-answer questions. Both splits include English exact/API queries, English paraphrases, French-to-English questions, confusable concepts and version-specific questions. No-answer examples concern absent deployment facts or unsupported API/features; absence is relative to this bounded corpus.

Real confusables include Qdrant `must` / `should` / `must_not`, cancellation versus shielding, backup versus checkpoint, and Python 3.11 `isolation_level` versus Python 3.12 `autocommit`. Version-incompatible labels mean the passage comes from the explicitly wrong version for that query; confusable-operator labels mean a different filter semantics, not proof that the source itself is false. The Python 3.11 source is genuinely older documentation, not an authored fake obsolete recommendation. No automatic source-version filtering is applied.

Source hashes, passage selection, both query splits and judgments are persisted in `freeze.json` before evaluation starts. `run` checks every frozen input and the harness hash before/after evaluation, and checks model identity. No ranking/model/label changes were made after observing either split. The replay uses the same frozen inputs, not newly fetched pages.

**The implementing agent authored the judgments. There was no independent human/expert validation.** Questions differ across splits, but related topics and some evidence passages overlap; this is not topic-disjoint holdout. Relevant sets are selected evidence locations, not exhaustive annotations of every answer-bearing passage. Unjudged context is treated as nonrelevant in these metrics, even if a human might find it useful. For example, other isolation/backup passages can discuss the same topic. Scores therefore measure recovery of the frozen labeled evidence set, not authoritative answer correctness.

## Ranking and resident inference

- Independent Python SQLite FTS5 baseline, literal whitespace-token `AND`, safely quoted terms, `bm25` ascending, deterministic ID tie-breaks, top20 candidates. This follows the existing text-query construction, not a tuned OR/token-drop baseline. Long natural-language and French queries often have no lexical match. The harness indexes excerpt text only, without the production CLI's title/heading context, record priority, chunking, freshness or citation-output machinery.
- Exact cosine over the same public excerpt vectors; semantic top60 plus lexical top20; equal reciprocal rank fusion `1/(60 + rank)`, rank starting at one; ID tie-breaks; evaluate top5. This is the existing ranking recipe, not Qdrant's own server default fusion configuration.
- Local `artifacts/models/minilm`, **384 dimensions**, CPU ONNX dynamic-int8, attention-mask mean pooling, L2 normalization, 128-token maximum, empty query/passage prefixes. Official model revision **2c4055b12046f11709e9df2c122e59ffbdc2f900** and file hashes are retained in the model manifest.
- One resident tokenizer and ONNX session for the evaluation, two intra-op threads and one inter-op thread; no model/session reload per query. The unit test compares actual query vectors against unchanged `tools/embed.py::encode` with `atol=rtol=1e-6` and verifies session reuse. This harness does **not** change the production helper lifecycle.
- Observed runtime: Python **3.11.16**, SQLite **3.53.1**, NumPy **2.4.6**, ONNX Runtime **1.31.0**. First-run passage encoding was about **1.30 seconds**, excluding model/session construction. This is not an end-to-end latency benchmark or SQLite/Qdrant storage comparison.
- **135/136 passages reached the 128-token limit**, and 0/32 queries did. This is substantial evidence truncation; longer excerpts are fully available to FTS5 but only their leading tokens reach the model. No post-holdout chunk-size adjustment was made.

## Metrics and actual results

Top1, MRR@5 and recall@5 are macro-averaged over the **12 answerable questions per split**. Empty results score zero. MRR@5 uses the reciprocal rank of the first labeled relevant result within five; recall@5 divides unique relevant hits by the frozen relevant-set size. No-answer false acceptance is the fraction of **four no-answer questions** for which at least one candidate survives, not a generated-answer error rate. Incompatibilities are counted result occurrences against each query's explicit incompatible list. Missing labels are not inferred from model scores or prose.

| Mode | Split | Top1 | MRR@5 | Recall@5 | No-answer false acceptance | Incompatible @1 / @5 |
|---|---|---:|---:|---:|---:|---:|
| FTS5 | development | 0.1667 | 0.1667 | 0.1250 | 0/4 | 0 / 0 |
| FTS5 | holdout | 0.0833 | 0.0833 | 0.0417 | 0/4 | 0 / 0 |
| MiniLM hybrid | development | 0.5833 | 0.5833 | 0.5833 | 4/4 | 0 / 1 |
| MiniLM hybrid | holdout | 0.5000 | 0.6111 | 0.7083 | 4/4 | 0 / 1 |
| Experimental gated hybrid | development | 0.5000 | 0.5000 | 0.5000 | 0/4 | 0 / 1 |
| Experimental gated hybrid | holdout | 0.4167 | 0.5278 | 0.6250 | 1/4 | 0 / 0 |

Read per-query results rather than the averages alone:

- `holdout-11` retrieves the relevant Python 3.12 autocommit passage first, **but Python 3.11 transaction documentation second**. Correct top1 does not make the full candidate list version-safe.
- `holdout-07` returns cancellation cleanup before the labeled shielding passage, which is second.
- `holdout-08` and `holdout-09` miss the labeled `should` and `must_not` passages in the top five despite retrieving other Qdrant filtering context.
- The gated false acceptance is **“Quel utilisateur possède notre fichier de base SQLite en production ?”**, max cosine **0.6520066526534731**. Public docs cannot establish that deployment fact.

### Experimental abstention, not confidence

With `--experimental-abstention`, fit one threshold on **development only** using maximum query-to-corpus cosine. Candidate thresholds are development scores plus fixed endpoints; maximize balanced answerable/no-answer classification accuracy, with a higher threshold winning ties. This target is corpus answerability, **not whether the retrieved top1 is correct**. The helper rejects any holdout row passed into threshold fitting.

Frozen threshold: **0.5839476571324791**. Retain the full hybrid top5 only if maximum cosine meets the threshold; otherwise return no candidates. RRF scores are never interpreted as confidence. The threshold artifact is written before encoding any holdout query and binds the development result hash. The first holdout timestamp equals the threshold timestamp at host clock resolution; sequential code order writes the freeze first. Later holdout timestamps are after it.

Development accepts 8/12 answerable and 0/4 no-answer questions. Holdout accepts 8/12 answerable and **1/4 no-answer**; the four answerable rejections count as misses in the gated metrics. Zero incompatible holdout results after gating is not a compatibility guarantee: the gate discarded entire candidate lists and also lost valid evidence.

## Reproduce without refetching

From the repository root in Git Bash/native Windows, with the existing local `.venv` and model:

```bash
.venv/Scripts/python.exe tests/technical_quality_test.py

# A new evaluation subdirectory is created every time; no latest pointer.
.venv/Scripts/python.exe tools/technical_quality.py run \
  --snapshot artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92 \
  --model artifacts/models/minilm --experimental-abstention

# A genuinely new public snapshot, new hashes/judgments freeze, NO inference:
.venv/Scripts/python.exe tools/technical_quality.py prepare \
  --model artifacts/models/minilm
# Then pass the printed snapshot path to run.
```

`run` requires a frozen snapshot. It does not fetch sources, install dependencies, read a vault, call a remote model, or modify the production CLI. Changing the harness requires a fresh snapshot; do not silently alter frozen inputs or judgments to improve holdout scores. `prepare` does public downloads only, with an 8 MB bound per source. Exact replays use retained bytes because SQLite's live documentation may change.

Verification: **8 focused tests passed**, covering metric semantics, FTS5 AND/RRF behavior, threshold split isolation, exact extraction/missing anchors, actual resident-helper vector parity/session reuse, HTML normalization, hash-tamper rejection and judgment definitions. The broader `unittest discover -s tests -p '*_test.py'` run passed **14 tests**, including the other workstream's isolated server integration test; that separate test created its own new server-benchmark artifact and shut down its owned process. No server-benchmark source/doc file was edited here. Replaying this quality run produced identical **96** query/engine rows and summary metrics; all first-run receipt hashes and corpus offsets were checked against retained bytes.

## Boundaries

This is an evaluation harness, not a product feature or an acceptance certificate. It makes no generated-answer, citation-entailment, deployment-safety, general multilingual, real-vault, independent-human-validation, Qdrant-engine-superiority or globally accepted-model claim. The corpus is small, selected, all in English, partly markup-heavy and substantially truncated by the model. No confidence intervals or statistical generalization are claimed. A better development score cannot establish production safety.

No existing source/document file was edited for this work; only the three new scoped harness/test/doc files and unique evidence artifacts were created. No commit, staging, push, global activation/configuration or vault ingestion was performed. README/navigation ownership remains with the coordinating agent.
