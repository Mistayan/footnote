# Request scope repair — exposed-set diagnostic, not acceptance

## Outcome

Implemented a standalone label-free request-scope compiler and retrieval/get wrapper. **No production activation; no semantic accuracy or 80% claim.** Independent parent review of the newly blinded actual evidence is pending. The original fresh confirmation remains failed: 21/40 accepted-correct, 23/40 raw semantically correct, 37/40 accepted coverage, 4/12 no-answer false accepts, from independent review `c8d95379-7837-47cd-ab1a-93308bb084d1`.

Final diagnostic run: [`diagnostic-75f19087167340f3b8d23ed91a1d5947`](../../artifacts/request-scope-repair/diagnostic-75f19087167340f3b8d23ed91a1d5947/).

| Measure | Actual selected | Paired unconstrained baseline |
|---|---:|---:|
| Requests executed | 52 | 52 |
| Answerable accepted | 37/40 (92.5%) | 37/40 (92.5%) |
| Answerable abstentions | 3/40 | 3/40 |
| No-answer false accepts | 4/12 | 4/12 |
| Total accepted | 41/52 | 41/52 |
| Median request latency | 1.3721 s | 1.3757 s |

Selected maximum 1.4053 s; nearest-rank p95 1.3963 s. Selected latency includes query encoding, scoped retrieval, rerank and top5 source completion/get; excludes startup, baseline/control passes and diagnostic token inspection. Paired baseline timing includes its own query encoding and inherited search, not presentation/completion, so these are not an isolated speed comparison. Full run wall time: 203.246 s.

Raw expected-ID top1 hit diagnostic: **17/40**, not semantic correctness. Incomplete selected gold IDs cannot establish success or failure of an actual alternate passage. Raw semantic top1 and accepted-correct counts are **unknown until independent review**.

## Scope compiler contract

- Keep the request verbatim, with exact Unicode token spans, parsed values and reasons. Never rewrite the query used for dense embedding, BM25 or reranking.
- Parse explicit EN/FR documentation/source edition phrasing and documented `Python major.minor[.patch]` requests. Do not infer source language from query language, body language, or output preferences such as “answer in French,” including preferences followed nearby by documentation wording.
- Build a source catalog from immutable source receipts plus authoritative HTML `<title>` metadata and document URL namespaces. Edition language is receipt language, even for untranslated English paragraphs in a French edition. Record titles, title spans, raw SHA-256, original receipts and documented versions. All six catalog raw hashes match original raw-byte receipts.
- Family matching is lexical: case-fold exact catalog namespace/title tokens and URL slug tokens, with generic singular/plural morphology. Dotted APIs match their catalog module token. Multiple explicit families are a union, never the first family only. No question IDs, failure-specific lookup, gold, source-selected passages or answer labels enter compilation.
- Supplied formal constraints override parsed fields and are explicitly marked as structured **user input**, not automatic understanding. This live campaign supplied **no formal constraints**. Tests separately simulate them.
- Conflicting source languages, conflicting documented versions and ambiguous catalog aliases fail closed. Unknown/missing required candidate metadata and unmatched explicit version produce no eligible evidence. Invalid formal values fail closed. Comparison across multiple version/edition bindings needs relational scope and currently abstains rather than silently flattening it.

### Actual parsed requests — no implied success count

Every one of the 40 answerable requests parsed explicit source edition and documented version: 40/40 each. Source family parsed 37/40; Q13/Q14 use bare `JSONDecoder` without a catalog module token and Q37 uses unqualified `put_nowait()`. These keep only edition/version constraints; the compiler does not invent a module mapping. All 40 exact constraint objects are enumerated in `report.json` (`actual_parsed40`) and all 52 requests with exact spans/reasons are in `compiled-requests.json`.

Across all 52: language 50, version 50, family 47. The two private-unavailable requests have no inferred source constraints. Generic catalog aliases may be ambiguous in a larger catalog; ambiguity abstains, not a guarantee of complete natural-language understanding. The compiler is intentionally not a general semantic API resolver.

## Frozen retrieval and independent gates

Reuse the original frozen slice96/overlap24 records and passage vectors, resident MiniLM, resident pinned mMARCO512 CPU2/1 batch4 longest-first reranker, point400/dense-parent100/FTS10/RRF60/pool20, completion ceiling2500 and refusal cutoff2.5. Corpus, source bytes, source applicability, labels, model files and reranker parent input remain unchanged.

The new wrapper applies admissibility to Qdrant point IDs **before** point400 and dense-parent100, and verifies returned point IDs and dense parents against allowed sets. FTS5 BM25 SQL uses an admissible-ID subquery **before** `ORDER BY bm25 LIMIT 10`. This repairs the old wrapper's filter-after-original-LIMIT20 behavior. Completion/get independently rechecks the full scope before presenting exact source text.

All 52 requests have exact pool/ranking/score equality between inherited unconstrained `search` and the previous unconstrained `Session.constrained({})`. For the 27 original records whose previous request constraints were empty, the live baseline also exactly matches the historical pools/ranks/scores. Historical constrained records are not falsely advertised as unconstrained historical parity.

Eight previous top1 candidates are excluded by newly compiled scope. There are zero source-edition violations across all selected top5 presentations. These are mechanical scope results, **not eight newly correct answers**.

## TDD and evidence inspection

Seven unittest tracer bullets were added and observed RED before their implementation, then GREEN. Both adjacent existing regression suites also passed (five evidence-completion tests and three fresh-confirmation tests). Coverage includes EN/FR phrases, output preferences, verbatim spans, version mismatch/unknown metadata, empty acquisition, independent get refusal, SQL pre-limit filtering with 30 ineligible higher-ranked records, formal overrides/invalid forms, JSON/dataclasses comparison, title-token casefolding and ambiguity. The final live experiment exercises actual resident Qdrant and resident models, not synthesized API responses.

Per-query `failure-attribution-DO-NOT-SEND.json` preserves the previous independent verdict/rationale, newly eligible sources, previous top1 scope membership and new pool membership, full pool/ranking and reranker token spans. All new semantic judgments remain pending. Each pool candidate records exact source/parent span, visible passage-relative tokenizer span and whether its query/passage pair reaches512. Actual 718/822 reranked candidate pairs reach512; scope gating does not solve missing support or reranker truncation. Full actual requests, branches, scores, presented top5 evidence and paired baseline are in `actual-records-DO-NOT-SEND.jsonl`.

Two unique diagnostic runs were retained, not overwritten. The initial `diagnostic-4a0e805edf964aee92b5d55a023503f1` had 38/40 coverage and a narrower case-sensitive family lexer. Additional generic RED/GREEN tests exposed output-preference ambiguity and casefolded catalog-token behavior; the final corrected protocol was frozen before the second live run. This is disclosed iteration on an exposed diagnostic set, not fresh evaluation or cutoff tuning. Use only the final run's packet for review. The final run archives exact source code copies under `code/`.

## Independent review handoff

Send only these two files:

- [Actual blinded top1 packet](../../artifacts/request-scope-repair/diagnostic-75f19087167340f3b8d23ed91a1d5947/blind-packet.json)
- [Frozen semantic rubric](../../artifacts/request-scope-repair/diagnostic-75f19087167340f3b8d23ed91a1d5947/RUBRIC.json)

Packet contains all52 actual top1 presentations, including rejected and no-answer requests, with exact request/text/provenance/offset/hash. No query IDs, gold IDs, expected answers, scores or acceptance flags. Freeze independent verdicts before disclosing `mapping-DO-NOT-SEND.json`. Judge full support for requested behavior and edition, not topical overlap; keep all40 answerable requests in the accepted-correct denominator. Mapping and diagnostic files are not blind-review inputs.

SHA-256:

```text
blind-packet.json       48ecba4d2165c1ac8e33ca5de70fa4b69e568be3a6c7ffe31500ee1b6574da4b
RUBRIC.json             af353102e7448a3c55b3b5ef4bdc896b54d9ab39d6b710551ee149931d62aba2
protocol-freeze.json    bf3d4632c0e771f2c4b6722536d9bd0859a2b54397485f958d32228895c6d258
artifact-sha256.json    b9ad70bfe9d381f6b4760f69deca26bf9b21218ffabf297d886d69a9fd34b864
```

All21 final manifest entries verified. All66 historical snapshot/review files in the input receipt remained byte-identical, including original corpus, labels, raw/normalized sources, requests, old records, mapping and verdicts. Final frozen code hashes verified against current implementation and archived code. Owned Qdrant PID24592 exited and port58692 closed; only its owned Popen was terminated. No downloads, environment changes, private/vault access, global configuration changes, staging or commits.

## Run commands

From `D:/Projets/BorgKnowledge` in Git Bash using the existing project environment:

```bash
PYTHONPATH='D:/Projets/BorgKnowledge;D:/Projets/BorgKnowledge/tools' .venv/Scripts/python.exe -m unittest discover -s tests -p 'test_request_scope_repair*.py' -v
.venv/Scripts/python.exe -m tools.request_scope_repair.runner
```

Each invocation creates a new diagnostic directory and freezes its compiler/catalog/requests/rubric/code before resident inference. It never turns this exposed52 set into fresh acceptance. Next decision belongs to the parent's independent semantic review, not to expected-ID counts.
