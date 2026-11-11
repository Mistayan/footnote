# Rank-input repair — blinded diagnostic results

Parent joined frozen independent-context model verdicts to the 156-row mapping after verdict freeze. All answerable queries, including refusals, remain in the denominator. Old exposed diagnostic only; no fresh acceptance.

| Input | Accepted-correct /40 | Raw top1 correct /40 | Answerable accepted /40 | No-answer false accepts /12 |
|---|---:|---:|---:|---:|
| Original full input | 26/40 | 27/40 | 37/40 | 4/12 |
| Provenance-free model query, constraints enforced | **31/40** | **35/40** | 33/40 | **1/12** |
| 256-token segmented passage pairs | 29/40, plus 1 uncertain | 35/40 | 32/40 | 1/12 |

The query-view change is promising but remains below 80% accepted-correct accuracy. The existing cutoff 2.5 was calibrated for the previous view, not this changed score distribution. Recalibrate only on development; never select a cutoff from these diagnostic outcomes. Verify exact ranked-passage parity before reusing this blind evidence judgment for a different acceptance rule.

## Evidence

- [Executed experiment and token visibility](RANK-INPUT-REPAIR.md).
- [Frozen 156 blind verdicts](../../artifacts/rank-input-blind-review/bfe70d15-f920-49f0-992a-0db441281c7a/verdicts.json).
- [Mapping disclosed after freeze](../../artifacts/rank-input-repair/diagnostic-75b0e124f04445c4a55c1e7cbe481c19/mapping-DO-NOT-SEND.json).

## Rejected support-verification probe

[Multilingual extractive QA probe](../research/MULTILINGUAL-SUPPORT-VERIFICATION.md) executed on the older development corpus. It regressed selected-positive parent-ID recovery from 15/16 with mMARCO to 6/16 unthresholded; the development-calibrated QA rule accepted only one answerable request and no selected-correct top1. This is not a complete semantic accuracy comparison, but provides no justification for promoting the checkpoint. Extracted-span identity does not establish answer completeness; 409/420 QA pairs omitted overflow windows. Conversion license and weight parity also remain unqualified. No runtime promotion.

## Next step

A development-only query-view calibration experiment is running. If a rule is selected, freeze it before diagnostic replay and new semantic confirmation. Keep source/edition constraints as hard filters while retaining the original full request in tool and citation records.
