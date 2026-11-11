# Bilingual evidence audit — separate posthoc semantic measurement

## Decision: diagnostic support, not a new acceptance certificate

**The frozen selected pipeline supports the ≥80% stepping goal as a posthoc semantic point estimate, but its ≥90% higher goal is unresolved.** Its accepted-correct lower bound is **35/40 = 87.5%**, upper bound **38/40 = 95%**, with three uncertain passages. Raw, before refusal, both pipelines have **36/40 definite passes (90%)**, at most **39/40 (97.5%)** if every uncertain passage passes. These are audit judgments by the **implementing agent, not an independent human or independent model reviewer**. They do not certify generalization, production activation, or a private vault.

Historical selected-quote **19/40 = 47.5%** and paired baseline **20/40 = 50%** remain unchanged. They measured membership of designated source-scoped IDs, not complete bilingual semantic correctness. No historical gold, output, report, frozen method, or threshold was repaired. This separate layer must not be reported as a newly successful v2 acceptance run.

## Frozen method and scope

- Review rubric: `tools/semantic_evidence_review/RUBRIC.json`, SHA256 `1a4459bb2b8d8918ca510e8748e8be880a1ebfd833124abd26cced16600d3b5d`, written before semantic verdicts.
- New unique evidence directory: `artifacts/semantic-evidence-review/audit-5af0ea33f6d14602817b2efa820a00c5/`.
- Input: actual saved v2 `run-9090a031e1014818b42a6df066b68eb1/results.json`; pinned corpus and originals: `validation-45b7cf7377844257ab27dc02c46662fb/` under `artifacts/accuracy-validation-v2/`.
- **All104 actual top1 rows** reviewed: both pipelines × (40 answerable +12 no-answer). Exact query+text deduplication gives **62 unique pairs**. There are no deduplicated-pair provenance conflicts. Every complete presented top1 was read, including rejected results. No similarity/translation scoring or automatic relevance classifier supplied semantic verdicts.
- The packet is shuffled with seed20261020. It retains exact query (including requested version), full original passage, URL, source edition, offsets, raw-source and excerpt hashes. It excludes pipeline, rank, score, acceptance, gold IDs, selected quotes, answerability and query IDs. The mapping is separate. Previously exposed implementing-agent context cannot be erased: this is **blinded presentation, not independent cognitive blinding**. No review subprocess or second model was used.
- Explicit evidence-language/source constraints remain binding. Merely asking in French does not require French evidence. However, `v2-011-en` explicitly says “According to the French contextlib documentation”; the English source is a real source-applicability failure despite correct underlying facts.
- A pass requires complete support from **the presented full passage only**, correct version and scope. Code counts only if it proves the requested claim; a why-question requires rationale. Partial or cut-off proof is uncertain, not an invented negative or an automatic positive. Extra source context may diagnose boundaries but earns no correctness credit.

## Exact-quote preflight, before semantic review

`quote-closure-preflight.json` exhaustively checks every original selected quote against all209 original windows of all six pinned originals, not only its designated source. It confirms omitted windows for exactly four query IDs:

| Questions | Additional exact-quote windows |
|---|---|
| `v2-004-en`, `v2-004-fr` | `contextlib-fr-0011`, `contextlib-fr-0012` |
| `v2-006-en`, `v2-006-fr` | `pathlib-fr-0015`, `pathlib-fr-0016` |

This is **four question records / two paired fact families**, not four independent facts. Source compatibility is recorded separately: these are official EN/FR editions of Python3.13, not an inference that equal text implies compatible editions. The French Python edition includes untranslated English text. Matching a quote elsewhere does not automatically mark a retrieved passage correct, and it does not make English provenance satisfy an explicitly French-source query.

## Exact scoring and abstention denominators

Semantic intervals below are **judgment uncertainty bounds**, not confidence intervals. Lower counts only `pass`; upper counts `pass + uncertain`. Every all-answerable denominator remains40, including abstentions.

| Pipeline / frozen rule | Raw top1 pass to possible / all40 | Accepted-correct / all40 | Answerable accepted | Conditional precision, all accepted | No-answer false acceptance |
|---|---:|---:|---:|---:|---:|
| Selected identity, original max-logit≥2.5 | 36–39/40 (90–97.5%) | **35–38/40 (87.5–95%)** | 39/40 (97.5%) | **35–38/39 (89.74–97.44%)** | 0/12 |
| Original-parent baseline, NONE | 36–39/40 (90–97.5%) | 36–39/40 (90–97.5%) | 40/40 (100%) | **36–39/52 (69.23–75%)** | 12/12 |

Baseline precision among accepted **answerable-only** requests is36–39/40; it must not be mislabeled precision among all accepted results because it excludes12 accepted negatives. Selected accepted-answerable and all-accepted denominators both happen to be39 because all12 negatives were rejected.

Refusal rejects one passage that this review finds a **definite pass**: `v2-016-fr` (B046), the English source explicitly states Python3.10 support for `parents` slices and negative indices. Thus the historical conclusion “refusal loses zero correct raw hits” applies only to selected-quote correctness; under this separate semantic audit it loses one correct answer. We did not change or refit the cutoff.

Descriptive Wilson95 intervals, ignoring fact-family correlation: raw36/40 gives76.95–96.04%; selected accepted-correct35/40 gives73.89–94.54%; zero false accepts out of12 still permits24.25% upper true-rate uncertainty. The40 queries are20 correlated bilingual families; neither these intervals nor a90% raw point estimate prove a population≥90% threshold. There is no user-approved no-answer/coverage acceptance contract beyond the standing80/90 P@1 goals.

## Why historical and semantic results differ

| Pipeline | Original ID hit, semantic pass | Original ID miss, semantic pass | Original ID miss, uncertain | Original ID miss, fail |
|---|---:|---:|---:|---:|
| Selected | 19 | **17** | 3 | 1 |
| Baseline | 20 | **16** | 3 | 1 |

All original ID hits remain semantic passes; the extra passes require reading actual translated/equivalent evidence, not treating nonmatching IDs as errors or globally equating editions. The selected accepted numerator gains16, rather than17, because one newly recognized pass was refused. The old47.5% is therefore not evidence of a52.5% semantic error rate. Conversely, replacing47.5% with97.5% by granting all unknowns or all cross-language outputs credit would also be unjustified.

## Remaining issues after reading actual passages

The same four answerable cases are non-pass in both pipelines:

| Query / blinded pair | Verdict | Actual deficiency and measured candidate availability |
|---|---|---|
| `v2-006-en` / B003 | **uncertain** | `pathlib-en[13500:15300]` starts after the exact `full_match('*.py')` False example. It presents other `full_match` cases and the different `match` method. Correct expected original windows exist in both pools, best rank4; this is a presentation/ranking boundary concern, not demonstrated candidate absence. |
| `v2-011-en` / B023 | **fail** | English URL violates explicit French-documentation constraint. Compatible French proof is already in selected pool at rank3 (baseline rank5). Confirmed applicability/presentation-selection failure, not a general inability to retrieve bilingual evidence. |
| `v2-013-en` / B006 | **uncertain** | `contextlib-en[9900:11700]` begins “brary code and most threaded applications”; the suitability predicate lies outside presentation. Subprocess clause alone does not complete the multipart question. Complete French proof already ranks3 in both pipelines. |
| `v2-020-en` / B012 | **uncertain** | `transactions-en[3600:5400]` ends “while the rolled-back actions never bec”. The never-visible claim is not complete in the passage. Complete French proof is already in both pools at rank3. Conservative uncertainty, not a claim that the underlying proposition is false. |

All12 no-answer top1s in each pipeline fail substantive support; public examples, footer dates and API descriptions do not answer private passwords, keys, real incidents, company latency/speedup or an absent release announcement. The selected abstention rule rejects them all, while the unrefused baseline accepts them all.

**Next generic mechanism, before model tuning:** test applicability-aware, sentence/code-block-complete evidence presentation. Preserve explicit source/edition constraints, then select/expand boundary-complete original proof units with exact offsets and no label-centered crops. Candidate pools already contain complete compatible proof for these cases. Isolate this mechanism from encoder/ranker replacement and compare under a new predeclared protocol. Separately investigate why the frozen refusal rejects the correctly supported French `parents` query, on development data only; do not adjust its threshold on this audit.

## Audit artifacts, verification and independent follow-up

- `blind-packet.json`: only this packet and frozen rubric should be sent to the parent's second reviewer. **Do not send mapping, verdicts, quote-closure preflight or this report before second-review verdict freeze.** The parent can independently adjudicate the three uncertain passages and the explicit source constraint after that freeze. Even a second review here remains posthoc audit, not fresh question acceptance.
- `mapping-DO-NOT-SEND-TO-REVIEWER.json`:104-row provenance/acceptance mapping for post-review scoring only.
- `per-query-ledger.json`: all104 rows, complete actual passage, query, source URL/hash, version/edition compatibility, manual verdict/rationale/criterion, verbatim evidence and exact Unicode passage/source offsets.
- `metrics.json`, `quote-closure-preflight.json`, `rubric-freeze.json`, `historical-before.json`, `historical-verification.json`, `diagnosis.json`, `execution-receipt.json`.
- Manual decisions are in `tools/semantic_evidence_review/verdicts-01.json` through `verdicts-04.json`; no source context or selected positive label is an automatic pass rule.

Observed RED→GREEN missing-feature runs covered corpus-wide quote closure without edition equality, exact substring rejection/offsets, blind pair deduplication/label removal, abstention denominators/uncertainty, and full104-row assembly. The missing features initially raised ImportError/AttributeError (not misleading semantic assertion failures). The final focused suite passes all5 tests and validates every evidence snippet against both actual passage and pinned normalized original.

```bash
python -m unittest discover -s tests -p 'test_semantic_evidence_review*.py' -v
python -c "from tools.semantic_evidence_review.audit import *; finish((ROOT/'tools/semantic_evidence_review/ACTIVE-RUN.txt').read_text())"
```

SHA256 before/after verifies **221 historical files unchanged**: all existing v2 artifact files (including pinned sources/results/freeze), v2 helpers, v2 tests and original report. No runtime/private vault/environment/staging/commits or model tuning were performed. The repository was already dirty; unrelated existing changes were not touched. Fresh independent acceptance still requires new questions/facts and corpus-wide bilingual/applicability judgments frozen before outputs.

## Pinned source URLs

These URLs identify the preserved source snapshots; no live mutable page was substituted for pinned text during review.

- https://docs.python.org/3.13/library/contextlib.html
- https://docs.python.org/fr/3.13/library/contextlib.html
- https://docs.python.org/3.13/library/pathlib.html
- https://docs.python.org/fr/3.13/library/pathlib.html
- https://www.postgresql.org/docs/17/tutorial-transactions.html
- https://docs.postgresql.fr/17/tutorial-transactions.html
