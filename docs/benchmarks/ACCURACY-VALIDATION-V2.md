# Accuracy validation v2 — actual run, objective NOT met

## Decision

**Neither ≥80% P@1 nor the 90% stretch is verified.** The frozen identity method with its development-only max-logit refusal returned a frozen selected-quote first hit on **19/40 answerable questions (47.5%; Wilson95 32.94–62.50%)**. The paired original-parent baseline returned **20/40 (50%)**. Abstentions remain misses in these denominators.

**The new validation also has an annotation-design defect and must not be used for semantic acceptance.** Labels were authored before inference but scoped to one designated source. The independent audit subsequently found four questions with the *identical quote* also present in unlabeled windows of another source. This misses the requested corpus-wide “all windows containing quote” criterion. No frozen labels or results were repaired posthoc. Moreover, 20 of the 21 selected-quote misses returned a different source language; several clearly contain translated equivalent answers. UNKNOWN is not negative. These results do **not** establish a 52.5% semantic error rate, nor an alternate semantic ≥80% result.

The work went beyond the diagnostic: a new sealed 52-question corpus was actually encoded, indexed, queried and paired against the baseline. After it failed, a finite development-only ranking intervention was also actually executed. Nothing was activated in the incumbent runtime.

## Canonical evidence

Paths are relative to repository root `D:/Projets/BorgKnowledge`.

| Artifact | Location |
|---|---|
| Independent 21-request replay plus old diagnostic | `artifacts/accuracy-validation-v2/replay-9afbb1909b3d4677abe8899b859b8a6d/` |
| Original identity callable's live server for that diagnostic | `artifacts/acquisition-repair/v2-diagnostic-1789a549e8ff4978a49e23c0c5ea5489/` |
| New corpus, original bytes, questions, candidate and freeze | `artifacts/accuracy-validation-v2/validation-45b7cf7377844257ab27dc02c46662fb/` |
| Successful new actual paired run | `artifacts/accuracy-validation-v2/run-9090a031e1014818b42a6df066b68eb1/` |
| Constructor-binding parity on old development21 | `artifacts/accuracy-validation-v2/adapter-parity-1a15d66d497c468db50c1b67f8b40656/` |
| Subsequent finite development-only rank-view intervention | `artifacts/accuracy-validation-v2/dev-view-b8281cd4a4d94c36bf2d912bc4d23579/` |

The paired run contains `results.json`, append-flushed `results.jsonl`, `PER-QUERY-REVIEW.md`, `report.json`, `artifact-sha256.json`, `independent-audit.json`, source-coverage/mapping receipts, saved child/parent vectors, exact Qdrant point readbacks, configuration, logs and cleanup. The review contains each exact query, all frozen expected IDs and quotes, ordered top-five complete original-window excerpts, source URL/raw SHA256, Unicode offsets/excerpt SHA256, accepted/raw P1 status, P3/P5/recall5/RR. Full normalized originals and downloaded original bytes remain in the snapshot's `sources/` directory.

## First: independently replayed selected callable, then old diagnostic

Read the final identity declaration and acquisition-repair report, then independently replayed all21 original development requests. **Pools, all raw logits and complete ranks match exactly.** No translation model was loaded. A separate initial call to the original verifier also produced `artifacts/acquisition-repair/identity-callable-dc1af90947364030ab5c18b5438b062f/`.

The callable genuinely accepts the previously exposed diagnostic's original query and language: **48 answerable +15 no-answer**, all actually searched against the old pinned corpus with its owned resident Qdrant server. No diagnostic outcome was used to tune selection or refusal.

| Old set / rule | All-answerable P1 | Answerable accepted | No-answer false accepts |
|---|---:|---:|---:|
| Development, NONE | 15/16 | 16/16 | 5/5 |
| Development, selected max-logit ≥2.5 | 12/16 | 13/16 | 0/5 |
| Exposed diagnostic, NONE | 29/48 | 48/48 | 15/15 |
| Exposed diagnostic, frozen ≥2.5 | 24/48 | 37/48 | 1/15 |

Diagnostic raw direction counts: EN→EN13/18; FR→EN8/18; EN→FR4/6; FR→FR4/6. This is diagnostic, never new acceptance.

### Refusal selected only on development

Before replay inference, predeclared candidate cutoffs were `[-100,-10,-7.5,-5,-2.5,0,2.5,5,7.5,10,100]`. Accept iff a nonempty ranking has **max raw mMARCO logit ≥ cutoff**; RRF is not confidence. Select maximum `(accepted-correct / ALL development answerable + no-answer rejection rate)/2`, ties by higher answerable coverage then lower cutoff. Every candidate's precision, answerable coverage/rejection and no-answer false acceptance is saved in `refusal-frozen.json`. The selected cutoff is **2.5**. Development accepted precision is12/13, **not** milestone P1, which remains12/16. No test threshold fit occurred.

## New frozen corpus and judgments

Six actually downloaded official public snapshots, all topics different from the old Git log / itertools / HTTP cache / collections / argparse / Rust Result material:

| Snapshot | Official URL | Raw SHA256 |
|---|---|---|
| contextlib EN | https://docs.python.org/3.13/library/contextlib.html | `340f4da3e6c5f904f9f7b7e1efa48bdd4a4d1d8d5e1767f17473cb2720edc280` |
| contextlib FR | https://docs.python.org/fr/3.13/library/contextlib.html | `bde2649ea60bae68d0c8e8b0f72c21f163d407b2af0000cbf9eb2937096a60c8` |
| pathlib EN | https://docs.python.org/3.13/library/pathlib.html | `90048ef5d8c01a3519e4d3c0f0fcfce68de2740b8da2563f2a3212d042286f8f` |
| pathlib FR | https://docs.python.org/fr/3.13/library/pathlib.html | `ec5103409290f1e4dc10d99ab21fc35aa35ca72d5acdbe64e1978b58cf7edf60` |
| PostgreSQL transactions EN | https://www.postgresql.org/docs/17/tutorial-transactions.html | `a4cd14a60b682d3cdc3dcf3d29b3b4c6b30f13e72bc1686346fe3154e8171076` |
| PostgreSQL transactions FR | https://docs.postgresql.fr/17/tutorial-transactions.html | `14c65b255e8605f94c216c5995674f7bbdaf0ee7cbfa1c60aaccb2e0155591e3` |

Official version URLs are mutable; pinned bytes/hashes, **not an invented immutable upstream commit**, define these snapshots. The French Python pages are partially untranslated; language denotes the official source edition, not a claim every sentence is French. PostgreSQL French is the official community translation site. Original English/French text lengths and separate normalized hashes are in `source-receipts.json`.

The author-made gold was authored before ranked outputs in `tools/accuracy_validation_v2/gold-spec.json`, **not independently human judged**. There are40 answerable queries,10 in each query→target-evidence direction, plus12 no-answer queries (6 EN,6 FR). The40 questions comprise20 fact families queried in both languages: correlated, not40 independent semantic facts. Includes Python3.10/3.13 version changes, exact glob operators, one-value generator cardinality, rollback/savepoint and explicit negation. No-answer cases include absent private configurations/credentials, real incident tickets, company performance guarantees and a missing release date; they are largely easy out-of-corpus negatives, not industrial no-answer coverage.

Uniform original parents are1800 Unicode codepoints, stride900: **209 original windows**, not quote-centered crops. Source-wide tokenizer slices preserve the original selected96-token cap,24-token overlap and all-containing-original-parent mapping: **770 children**. Each child interval, original substring, hash, tokenizer count and complete source coverage was audited. Dense parents deduplicate on the first/highest-scoring child. Returned-child wholequote visibility is separately37/40; a parent candidate does not imply its selected proof was inside the acquired short child.

Before new-corpus inference, `freeze.json` was saved at `2026-10-20T06:22:43.242999+00:00`, SHA256 `a0b02875ae3001144dd6f22c8c163f40aaf35cf38c4d4a9185e928beb11ff9d5`. It binds source bytes/text, corpus, questions, complete candidate declaration, refusal artifact, model/tokenizer/ranker/Qdrant/lockfile/code hashes and copied code. Release follows the parent's conditional delegated authorization only after that complete freeze. Original freeze and release remain unchanged.

### Actual callable schema, not invented corpus support

`IdentitySearchSession(config,new_run)` hardcodes the old corpus and refuses v2-owned artifact paths; it does **not** accept a corpus argument. `CorpusIdentitySession` therefore changes initialization only, binding supplied label-free original parents/sources/child vectors. It inherits the **exact same `IdentitySearchSession.search` function**, including original-query dense/FTS/rerank, lexical10 identity mass, pool20 and evidence serialization. Its old-development21 constructor parity test exactly reproduced pools, logits and full ranks before new test inference. This is an explicitly declared corpus-binding adapter, not a claim the original constructor supported arbitrary new corpora.

MiniLM128 and mMARCO512 are the original pinned pretrained models and settings. No models or dependencies were downloaded. No query/source translation model or external inference service was used. The paired baseline independently executes original-parent MiniLM top60/ef128 + original FTS5 BM25 OR20 + RRF60 + full-parent mMARCO pool20, without refusal. It does not reuse selected-stage timings/scores.

## New actual results

| Method | Exact-quote P1 / all40 answerable | Answerable coverage | Precision among all accepted | No-answer false accepts |
|---|---:|---:|---:|---:|
| Selected identity, no refusal control | 19/40 (47.5%) | 40/40 | 19/52 | 12/12 |
| **Selected identity, frozen ≥2.5** | **19/40 (47.5%)** | **39/40 (97.5%)** | **19/39 (48.72%)** | **0/12** |
| Paired original-parent baseline, NONE | 20/40 (50%) | 40/40 | 20/52 | 12/12 |

Selected coverage Wilson95:87.12–99.56%. Accepted precision Wilson95:33.87–63.80%. Zero of12 false accepts still permits a Wilson95 upper bound24.25%; do not certify a≤10% true failure rate. These intervals ignore fact-family/source correlation and are descriptive, not IID generalization guarantees. Experimental assistant-proposed80% coverage/≤10% false-accept point gates pass, but accuracy fails, and annotation completeness additionally fails.

| Query→designated evidence | Selected raw and refusal P1 | Baseline P1 |
|---|---:|---:|
| EN→EN | 8/10 | 8/10 |
| FR→EN | 2/10 | 2/10 |
| EN→FR | 1/10 | 2/10 |
| FR→FR | 8/10 | 8/10 |

Selected acquisition misses the expected parent on1/40 (`v2-004-fr`);20 further misses have an expected parent in pool20. Refusal loses zero correct raw hits and rejects one UNKNOWN first result. There are no paired raw gains and one loss (`v2-018-en`). Merely increasing acquisition therefore is not justified by this batch.

### Annotation limitations discovered after exposure — no repair

The independent audit identifies exact identical-quote omissions for `v2-004-en`, `v2-004-fr`, `v2-006-en`, `v2-006-fr`: French-edition windows also contain the English selected quote. Frozen source-scoped labels were complete within their source, but **not corpus-wide**. The audited run is mechanically reproducible; its benchmark does not meet the full requested gold-completeness acceptance contract.

Examples remain UNKNOWN, not new positives:

- `v2-007-fr`: expected English PostgreSQL rollback proof, retrieves `transactions-fr-0004` containing “ROLLBACK ... Toutes les mises à jour ... annulées.”
- `v2-015-fr`: expected French UnsupportedOperation proof, retrieves `pathlib-en-0002` containing the class, inheritance and3.13 addition.
- `v2-006-en`: expected exact `full_match('*.py')` False example, retrieves adjacent `pathlib-en-0015` beginning with other glob examples. This same-language selected-proof miss deserves operator/scope review.

Do not silently turn source-edition preference into semantic correctness, or retrospectively add equivalent translation labels. Any future acceptance must have corpus-wide exact-quote completeness and independently authored bilingual equivalence/applicability judgments **before** outputs, ideally with different nonduplicated facts in source languages or an explicit requested-evidence-language contract.

## Real latency, backend and cleanup

Qdrant1.19.2 commit`016542aa5deb6c66380bb137badf73d54f742bde`, actual isolated owned loopback process. Both collections reached green and fully indexed209/770 counts. Every vector/payload was read back with maximum absolute vector error<1e-6.

The104 actual paired requests completed in172.613s including indexing/setup. Selected resident E2E p50/p951555.565/1617.087ms; baseline1554.401/1610.905ms. Selected cold source encode/index startup9952.780ms, separate from resident requests. These small sequential paired measurements are not a speedup claim.780 ranker pairs reached the512-token cap; no CPU/RSS whole-tree measurement was collected, so none is claimed.

Every owned Qdrant process was terminated/waited; recorded ports are closed. No incumbent service, private vault, global environment/config, staging or commits was touched.

### Infrastructure failures preserved, not hidden

1. French PostgreSQL extraction initially produced zero characters because its content marker differed; corrected against actual official raw HTML **before** freeze/inference, preserving raw bytes and recording normalization.
2. First fresh attempt failed before any ranked query: Qdrant's first collection PUT returned HTTP500 Gridstore IO error under a deeply nested Windows path. Its unique failed run and cleanup remain. `recover.py` froze an infrastructure-only amendment: shorter output directory and separate retry receipt filenames, no method/corpus/question/model/refusal changes. Exact executed source and edits are retained.
3. The recovery completed all104 requests and produced its verified report, but its live test then failed a final wrapper assertion comparing canonical LF source hash to Windows CRLF-persisted bytes. **That live wrapper test is not reported as passing.** The separate independent audit verifies the executable canonical source hash, exact persisted file hash, unmodified original method/corpus freeze, all104 scores/ranks/evidence and cleanup. Both original failures remain visible.
4. Replay protocol gained additive sealing helpers after the initial old diagnostic. The exact replay-time scoring source was reconstructed, hash-matched to its original frozen hash, and retained as `protocol-at-replay.py`; scoring/refusal logic did not change. Fresh freeze binds the later complete protocol.

## Continued: next finite intervention actually executed on development

After the new result, predeclared **one** dev-only variant: unchanged saved verified identity pool20; rank uniform600-character stride400 views of every original parent with the same resident mMARCO; aggregate parent score by max view logit; original full parent remains evidence. No quote/label-centered crop. This isolates ranking evidence granularity; it does not touch the newly exposed test.

Actual21 complete development requests ran in38.957s, within a240s cap, with zero ranker pairs at the token cap. Raw P1 remains15/16; frozen2.5 and the same finite dev-only cutoff refit both remain12/16 accepted-correct,13/16 coverage,0/5 no-answer accepts. **No gain; not selected.** This is real reranking with replayed candidate pools, **not** a new backend/E2E measurement.

Remaining bounded intervention: first author a fresh *development* bilingual-equivalence judgment protocol with corpus-wide exact duplicate-quote preflight and no result-based labels; resolve whether evidence language is an explicit user constraint. Then freeze a single ranker/input variant for a further fresh topic set. Suggested next resource cap is **15 minutes authoring/preflight +10 minutes inference/audit**, total25minutes, no installs/model changes. It is not started in this report and no further fresh claim is made. This iteration used a hard35-minute maximum and completed the requested diagnostic, actual new test, independent audit and one actual follow-up development intervention inside that budget.

## Verification commands and scope

TDD missing-feature failures were observed before implementing quote labels, denominator/refusal scoring, sealing, replay, corpus adapter, fresh runner, recovery, independent audit, global duplicate detection and development views.

```text
python -m unittest discover -s tests -p 'test_accuracy_validation_v2*.py' -v
python -m unittest tests.test_accuracy_validation_v2_audit -v
```

Final ordinary discovery: **12 tests,7 passed,5 opt-in live skips**. All five owned Qdrant ports were independently probed again and found closed. `closure.json` in the paired run explicitly separates mechanically verified execution from failed acceptance/design validity.

Opt-in live replay21+diagnostic and adapter21 tests actually passed in separate executions. The subsequent dev-only live test passed. Fresh live startup and the recovery wrapper's post-run hash assertion failures are disclosed above; the actual successful104-row run is validated by the independent saved-run audit. Ordinary discovery skips live work rather than pretending to rerun a sealed test. No broad legacy suite is claimed.

**Files created:** only `tools/accuracy_validation_v2/*`, `tests/test_accuracy_validation_v2*.py`, this report, unique v2 artifacts and the two explicitly required original-callable live artifact directories under acquisition-repair. Original report/helpers/config/source snapshots remain unchanged. No production integration or private-vault certification.
