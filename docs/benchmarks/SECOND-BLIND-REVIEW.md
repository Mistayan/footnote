# Second blinded model review — corroborated diagnostic milestone

The second reviewer saw only the 62-pair shuffled evidence packet and frozen rubric, not pipeline mappings or prior judgments. The parent joined its frozen verdicts to the 104-row mapping using Python after review completion.

| Pipeline | Definite accepted-correct / all 40 answerable | Uncertain accepted | Answerable accepted | No-answer false accepts / 12 |
|---|---:|---:|---:|---:|
| Selected, frozen logit cutoff 2.5 | 35/40 (87.5%) | 3 | 39/40 | 0/12 |
| Baseline, no refusal | 36/40 (90%) | 3 | 40/40 | 12/12 |

Both separately contextualized model reviewers agree on these aggregate counts. The selected pipeline exceeds the 80% stepping target as a corroborated **posthoc semantic diagnostic point estimate**. It does not establish fresh preregistered semantic acceptance, independent human validation, a population lower confidence bound of 80%, or 90% after refusal. The 40 questions include correlated bilingual fact families. Historical expected-ID results remain unchanged.

Sources: [first audit](BILINGUAL-EVIDENCE-AUDIT.md); [frozen second-review verdicts](../../artifacts/semantic-second-review/02540055-2ca3-4176-a4be-ad9b4cba3b39/verdicts.json); [mapping disclosed only after review](../../artifacts/semantic-evidence-review/audit-5af0ea33f6d14602817b2efa820a00c5/mapping-DO-NOT-SEND-TO-REVIEWER.json).

## Next experiment and integrity boundary

[Evidence completion](EVIDENCE-COMPLETION.md) executed sentence/code-block boundary completion and explicit source-language constraints on the exposed diagnostic set. It structurally restored three cut proof spans and selected the requested French source. A separate blinded review is running; no new semantic score is asserted here.

An existing regression audit rewrote an auxiliary historical `independent-audit.json`. Its original digest was `21908211fe907f885cbcac5c4ee1b1be657a931e65adb66a4bd4b6c710c18c3f`. Original result/gold/source/method hashes remain intact; 96/97 tracked historical files were unchanged according to the intervention receipt. The old auxiliary audit is not described as byte-preserved and no fabricated restoration was attempted. See the experiment's `final-integrity-incident.json`.
