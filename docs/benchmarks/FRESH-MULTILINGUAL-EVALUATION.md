# Fresh multilingual evaluation — frozen public evidence

**Status: OPEN for parent verification. Final test SEALED and not ranked. Neither the ≥80% milestone nor ≥90% stretch is established.**

## Frozen contract and scope

Primary reporting unit: **exact expected-evidence top-one hit rate across ALL answerable questions**, including rejected queries in the denominator. These are implementing-agent selected quotes, not independent human judgments or exhaustive semantic relevance labels. Other windows remain **UNKNOWN**, not proven irrelevant. No ranked-output pooling, posthoc relabeling, or claim that selected-label P@1 equals true answer accuracy.

Proposed strict experimental criteria, **not user-approved industrial certification**: P1 ≥80%, answerable accepted-evidence coverage ≥80%, and no-answer false acceptance ≤10%; ≥90% P1 is the stretch. No abstention threshold is fitted on final test. A nonempty evidence list counts as acceptance, not a generated recommendation. The baselines have no abstention gate. High P1 alone would not pass safe-evidence acceptance.

Snapshot: `artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c/`.
Freeze SHA256: `9d5432c634680f3921b40e9c60876b13871d17cacbb1e1730f2b89c0e436aea1`.

- **416 uniform original-source windows**; width1800 Unicode characters, stride900. The initial1400-character width failed quote-containment preflight; all sources were uniformly rebuilt at1800 **before freeze or inference**. No question/label-derived title prefixes or per-query windows.
- **84 questions:64 answerable plus20 no-answer.** Development:16 answerable/5 no-answer. Final test:48 answerable/15 no-answer. The ≥60 answerable requirement is met across the complete suite, **not by final test alone**.
- French/English questions, EN→EN, FR→EN, FR→FR and EN→FR expected-evidence strata; explicit negation and Python-version cases. Development is8 English/8 French answerable questions. All four language directions occur in the frozen suite, but only EN→EN and FR→EN have been executed so far.
- Development topics: Git log and Python itertools. Final topics: HTTP caching, collections, French argparse and Rust Result error handling. No source topic crosses the development/test boundary. Git and Rust source families occurred in older work; these specific topics and the HTTP source family are fresh. This is topic separation, not a claim that every publisher is novel.
- Python generic collections proofs are labeled in both retained releases if the quote exists in both; explicit3.13 questions require the3.13 source. No generic result is called wrong solely because it comes from3.12.
- Repeated questions within sources, overlapping windows, and one bilingual version-case paraphrase create dependence. Wilson95% intervals are descriptive, **not population certification**. Public documentation does not certify a private vault.

## Official provenance and source preservation

The fresh development sources cover Git2.49 log options and Python3.13 itertools.[1][2]

Held-out sources include RFC9111 HTTP caching and Python collections at3.13 and3.12.[3][4][5]

Additional sources are the French3.13 argparse page and the Rust Book Result chapter.[6][7]

`source-receipts.json` retains exact requested/final URLs, HTTP200 status, response headers, retrieval timestamps, sizes, SHA256 hashes, source language, split and version. `sources/*.raw` are the genuine originals; `sources/*.txt` are normalized public source text. Each corpus window carries character offsets and its own hash. Expected spans retain exact quotes plus source offsets, and **all windows containing the whole quote** receive expected-evidence labels. No incumbent corpus bytes or labels were reused.

Git/Python use release URLs, Rust an immutable commit, and HTTP the fixed RFC number. **The French documentation URL is mutable:** this evaluation pins the exact retrieved bytes/hash, not an upstream immutable French translation revision. HTML normalization strips markup and script/style text but retains navigation, examples and untranslated English portions. French evidence strata use selected French prose, not a claim that the entire page is translated. Rust include directives are preserved, not expanded; this is not a lossless document-extraction certification. These limitations are frozen in `protocol.json`.

No-answer cases cover absent private configuration, runtime telemetry, inputs, contracts, unsupported future releases and unavailable market measurements. They are bounded-corpus no-answer assertions, not claims that those questions cannot be answered elsewhere. Many are intentionally obvious; they do not certify hard near-miss abstention generalization.

## Actual execution — development ONLY

Real isolated Qdrant1.19.2 server, CPU-resident hash-verified MiniLM and existing mMARCO cross-encoder. One encoder session and one ranker session; no model or package installation. All416 vectors were indexed green and read back with matching IDs and <1e-6 vector conversion error.

Each of the21 development questions independently executes each of five baseline requests: **105 real resident end-to-end requests**, not reused component sums. Query encoding, real loopback HTTP search, lexical retrieval, ranking, evidence hydration and evidence serialization are measured. Original MiniLM manifest128 and original mMARCO longest-first512 recipes are unchanged. Dense top60 ef128, lexical top20, equal RRF k60/rank1, document-ID ties. The mMARCO control uses the existing OR-RRF pool20, with identical original passage bodies and no newly added applicability gate.

Run: `artifacts/fresh-multilingual-evaluation/runs/eae052500e3f4ee6ba4bfabba50b3a9f/`.

| Development baseline | Exact top1 hits /16 answerable | P1 | Descriptive Wilson95% | Answerable coverage | No-answer false accepts /5 | Proposed gate |
|---|---:|---:|---|---:|---:|---|
| MiniLM dense |3/16|18.75%|6.59–43.01%|100%|5/5 (100%)|FAIL|
| Current MiniLM + FTS5 literal AND equal RRF |3/16|18.75%|6.59–43.01%|100%|5/5 (100%)|FAIL|
| Equal OR-RRF pool control |5/16|31.25%|14.16–55.60%|100%|5/5 (100%)|FAIL|
| FTS5 literal AND alone |0/16|0%|0–19.36%|0%|0/5 (0%)|FAIL: rejects every answerable|
| Existing mMARCO on OR-RRF pool20 |12/16|75%|50.50–89.82%|100%|5/5 (100%)|FAIL|

mMARCO development EN→EN:7/8=87.5%; FR→EN:5/8=62.5%. Its selected-evidence P3/P5 are0.375/0.2625, MRR5 is0.79375 and selected recall5 is0.78125. MRR is a rank statistic, **not answer accuracy**. Selected-positive label ceilings and overlapping windows limit P3/P5 interpretation. The no-answer false-accept interval for5/5 is56.55–100%; for FTS's0/5 it is0–43.45%. None establishes ≤10% population risk.

Measured query workload38.484s; model validation/load1574.214ms and offline encoding/indexing6048.976ms are separate. **412/416 passages reach or exceed MiniLM's128-token cap**, an important disclosed truncation confound. No model/segmentation change is made in response on this frozen test.

`PER-QUERY-REVIEW.md` provides every exact development question, ordered top-five original passages, URLs, original/excerpt hashes, character spans, expected hits and UNKNOWN status. `raw-results.json[l]` preserves full candidates, branch ranks, logits, query vectors, server responses and independent timings. All420 returned evidence records are retained; FTS5 AND returns none. No final-test failure or per-query output exists.

Owned Qdrant PID18944/port61871 exited/closed; independently rechecked after completion. Windows terminate/wait return1 is forced shutdown, **not graceful shutdown or durability acceptance**. No unrelated process or runtime endpoint was touched.

## Verification

- Focused real integration: **4 tests PASS in47.896s**, including105-row replay, no-answer/coverage arithmetic, exact quote labeling and sealed-test guard.
- `audit_development.py` independently verifies all frozen hashes,105 rows,420 original-source evidence records,416 indexed vectors/readback, raw HTTP dense ordering, RRF contributions, query-vector parity, logit ordering, unchanged expected labels, aggregates and owned PID/port closure. `independent-development-audit.json`: **PASS**.
- Final-test CLI attempt was deliberately rejected with `SEALED: parent must release test with frozen challenger config first`, before query loading, model construction or run creation. No `release-test.json` or `test-exposure.json` exists.
- External reusable scorer was exercised on the **actual21 retained mMARCO development predictions**, reproducing75% P1. Replay receipt: `external-score-replay-receipt.json`; scored evidence: `artifacts/fresh-multilingual-evaluation/scores/b165d82f3240483b94d6878fc31b9efd/`. This is scoring replay, not a fabricated new candidate run.
- Report citation enrichment initially touched the frozen citation ledger; the original ledger was restored **byte-identically to its pre-inference SHA256**, with final snapshot/run verification passing. Report-only quotes are now in separate `report-citations.json`; corpus, judgments, protocol and ranked outputs never changed.
- Incumbent files/models/helpers were checked unchanged against the execution freeze. Only the new owned evaluator/test/report and unique artifact paths were written. No vault/private reads, environment changes, activation, staging or commits. Broader application regression is not claimed.

## Reusable commands and sealed-test handoff

Run from repository root with the existing environment; do not activate/install anything globally:

```bash
S=artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c
.venv/Scripts/python.exe -B tests/fresh_retrieval_evaluation_test.py -v
.venv/Scripts/python.exe -B tools/fresh_retrieval_evaluation.py verify --snapshot "$S"
.venv/Scripts/python.exe -B tools/fresh_retrieval_evaluation.py verify-run \
  --run artifacts/fresh-multilingual-evaluation/runs/eae052500e3f4ee6ba4bfabba50b3a9f
# Optional new UUID development baseline run; never overwrites the retained run:
.venv/Scripts/python.exe -B tools/fresh_retrieval_evaluation.py run --snapshot "$S" --split development
```

The stronger-ranker worker may use `corpus.json`, `source-receipts.json`, `sources/`, `development-judgments.json`, and development outputs. **Do not send it `test-judgments.json`, `annotate.py` or test outcomes while it is selecting.** The seal is a procedural/hash-and-CLI barrier, not encrypted access control. The author necessarily saw final questions during annotation; no test ranked outputs have been produced.

After the parent fixes the challenger, prepare a declaration JSON with:

```json
{
  "name": "selected-challenger",
  "selection_used_development_only": true,
  "config": {"complete": "all retrieval/model/prefix/chunking/rerank/abstention settings, no defaults omitted"},
  "files": {"tools/actual_candidate.py": "ACTUAL_SHA256", "artifacts/actual_model/receipt.json": "ACTUAL_SHA256"}
}
```

Include **all** actual code/model/tokenizer/config input hashes, not just the illustrative two entries. Fit any proposed evidence gate on development only; freeze the exact threshold, scoring pipeline, minimum coverage and no-answer criteria in this declaration. This attestation is the parent's responsibility, not automatic proof of independent selection.

```bash
# Parent only, once the selected challenger is fully frozen:
.venv/Scripts/python.exe -B tools/fresh_retrieval_evaluation.py release-test \
  --snapshot "$S" --candidate PATH-TO-REAL-DECLARATION.json
# Now run baseline and the already-frozen challenger in the same release campaign:
.venv/Scripts/python.exe -B tools/fresh_retrieval_evaluation.py run --snapshot "$S" --split test
# Candidate emits a JSON array covering EVERY test query exactly once:
# [{"id":"actual-query-id", "top5":["actual-corpus-document-id"], ...raw scores/config receipts...}, ...]
# Rejected queries MUST have top5: []; do not omit them.
.venv/Scripts/python.exe -B tools/fresh_retrieval_evaluation.py score --snapshot "$S" \
  --split test --predictions PATH-TO-ACTUAL-CANDIDATE-PREDICTIONS.json
```

Programmatic interfaces: `queries_for(snapshot, split)` enforces release and records first test exposure; `score_predictions(snapshot, path, split)` checks complete unique query coverage, at mostfive distinct valid corpus IDs, retains raw prediction records, hydrates original evidence and computes the same metrics/intervals. `[]` is rejection; denominator stays all answerable. If a challenger changes chunking, export/resolve its returned evidence to the frozen corpus IDs with a **predeclared** mapping, or extend the evaluator under a separately frozen protocol; do not invent IDs or map observed failures posthoc. The external scorer proves arithmetic and source identity, **not live challenger execution**; preserve actual execution receipts separately.

**After the first final query read/inference, the final set is diagnostic for every subsequent selection.** Keep this first paired comparison unchanged. Publish both baseline and preselected challenger regardless of outcome; never retune on final results or relabel failures to cross80%. Even observed ≥80% is only a point estimate, not population/industrial certification.

Parent owns acceptance and task closure. The delegated task remains open; this work does not wait for or poll the separate stronger-ranker worker.

## Sources

[1] https://raw.githubusercontent.com/git/git/v2.49.0/Documentation/git-log.adoc — git-log
[2] https://raw.githubusercontent.com/python/cpython/v3.13.0/Doc/library/itertools.rst — itertools
[3] https://www.rfc-editor.org/rfc/rfc9111.txt — http-cache
[4] https://raw.githubusercontent.com/python/cpython/v3.13.0/Doc/library/collections.rst — collections313
[5] https://raw.githubusercontent.com/python/cpython/v3.12.0/Doc/library/collections.rst — collections312
[6] https://docs.python.org/fr/3.13/library/argparse.html — argparse-fr
[7] https://raw.githubusercontent.com/rust-lang/book/1500248d8f230566e4ec9f27fcbb8fe9e2898ab1/src/ch09-02-recoverable-errors-with-result.md — rust-result
