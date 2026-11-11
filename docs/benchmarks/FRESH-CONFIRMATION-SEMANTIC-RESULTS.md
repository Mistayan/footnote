# Fresh confirmation — blinded semantic result: failed

The frozen pipeline did not confirm the earlier 97.5% exposed diagnostic result on new topics. Parent computed counts by joining the frozen independent-context model review with the previously separate acceptance/answerability mapping. Historical records and labels remain unchanged.

| Measure | Actual count |
|---|---:|
| Accepted and semantically correct top1 / all answerable | **21/40 (52.5%)** |
| Semantically correct raw top1, before refusal | 23/40 (57.5%) |
| Answerable accepted | 37/40 (92.5%) |
| No-answer false accepts | 4/12 (33.3%) |
| EN → EN accepted-correct | 5/10 |
| FR → EN accepted-correct | 5/10 |
| EN → FR accepted-correct | 4/10 |
| FR → FR accepted-correct | 7/10 |

This is independent-context model review, not human adjudication or population certification. The 80% first milestone and 90% higher target are not established by fresh evidence. The earlier posthoc diagnostic 97.5% remains a separate valid record, not a generalization claim.

## Provenance

- [Executed frozen campaign](FINAL-MULTILINGUAL-CONFIRMATION.md).
- [Frozen blind verdicts](../../artifacts/fresh-confirmation-review/c8d95379-7837-47cd-ab1a-93308bb084d1/verdicts.json).
- [Mapping disclosed after review freeze](../../artifacts/final-multilingual-confirmation/fresh-c6cfd7b5ae4149e7b9f76484e52bf863/mapping-DO-NOT-SEND.json).

The reviewer inspected all 52 full top1 passages without acceptance flags or gold. Parent kept rejected answerable questions in the denominator. Raw reviewer count was 23 pass, 29 fail; acceptance removes two correct answerable results.

## Failure mechanism and next experiment

Failures include explicit English/French source-edition constraints not consistently compiled into request filters, wrong-module evidence, and missing exact behavioral support despite topical similarity. Some semantically correct statements fail a legitimate requested-edition requirement; others genuinely do not answer the question.

A generic EN/FR request-scope compiler (source edition, documented version, explicit API/module scope) is being tested before both acquisition branches and at presentation. No per-query hardcoded correction, default switch or source-label rewrite is authorized by this report. New interventions on this exposed set will be diagnostic, not fresh validation.
