# Evidence completion — blinded model review results

## Executed diagnostic result

The parent joined the frozen independent model review of 102 blinded pairs to the separately retained 208-row mapping, using Python after the review freeze. The reviewer did not see variant identities or prior verdicts. All 40 answerable questions remain in the accuracy denominator, including the rejected question.

| Completion | Explicit source constraint | Definite accepted-correct /40 | Answerable accepted /40 | No-answer false accepts /12 |
|---|---|---:|---:|---:|
| No | No | 35/40 (87.5%) | 39/40 | 0/12 |
| No | Yes | 36/40 (90%) | 39/40 | 0/12 |
| Yes | No | 38/40 (95%) | 39/40 | 0/12 |
| Yes | Yes | **39/40 (97.5%)** | 39/40 | 0/12 |

The combined intervention has no judged-wrong accepted answerable top1 on this diagnostic. One answerable question is still refused. These are model judgments, not human certification. The corpus was already exposed and interventions addressed observed failure categories; the result exceeds both stepping targets only as a **posthoc diagnostic point estimate**, not independent fresh acceptance or a population confidence bound. Bilingual fact-family dependence and small sample size remain.

## Evidence

- [Executed intervention, costs and limitations](EVIDENCE-COMPLETION.md).
- [Frozen blind reviewer verdicts](../../artifacts/completion-second-review/a7da391b539e459baf6ee65056e46d23/verdicts.json), SHA-256 `cc3cb8169827a0605531824579d3bae8b88fd1c684cfd0b9e923261741a36a98`.
- [Separate mapping](../../artifacts/evidence-completion/diagnostic-4d656d0e6d954964aadbf9deb9478a2b/mapping-DO-NOT-SEND.json).
- Reviewer packet SHA-256 `34f0ac2852336ce3a8972552d8269888e15e28deb8af145aadd3e2d0ee70d755`.

The original expected-ID metrics and historical evidence remain separate. The auxiliary audit-file integrity incident reported by the intervention is not repaired by this review and must remain disclosed.

## Next gate

Freeze the combined pipeline unchanged and evaluate new official-source topics, with semantic rubric and source-edition closure prepared before outputs. Judge shuffled actual evidence without pipeline labels. The fresh confirmation is running; no private ingestion, runtime promotion or global switch follows from this diagnostic.
