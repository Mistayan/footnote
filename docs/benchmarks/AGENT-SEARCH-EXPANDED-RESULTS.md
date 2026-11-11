# Expanded agent-search pilot — verified outcome

## First bounded end-to-end milestone

All **20/20 task executions passed** the frozen strict final-task rubric in a separately contextualized blind model review: **16/16 answerable** correct, complete and citation-supported, and **4/4 no-answer** explicitly abstaining. Parent verified the verdict SHA-256 and mapping completeness after the verdict freeze. The 80% first and 90% higher targets are exceeded as **observed diagnostic pilot scores**, not as established general accuracy.

This is an exposed-corpus diagnostic, not a fresh held-out semantic acceptance test, human adjudication or private-vault certification. Authoring, answering and review use the same model family in separate contexts; correlated model errors remain possible. Twenty tasks cannot establish a true 90% population success rate: the descriptive Wilson 95% interval for 20/20 is approximately **83.89%–100%**, assuming independent representative tasks, which this diagnostic does not establish.

## What was exercised

- Actual current model and authorized provider, bounded search/get tools over an isolated real Qdrant backend and resident retrieval models.
- 20 new tasks excluded the first pilot's eight questions; 16 answerable and four no-answer.
- 40 actual model requests, 20 searches, zero gets, zero repair calls or inference errors.
- 143,243 recorded tokens; median task latency 9.225 seconds; wall 200.506 seconds. Dollar cost not supplied.
- The agent voluntarily used a single search per task. No incremental benefit from iterative searches or get is demonstrated.
- Standalone scoped-query2 adapter, not equivalent to deployment acceptance of every shipped runtime path.

## Review result

Correctness, completeness, support, citation entailment, citation completeness, valid handles, source/version compliance and abstention consistency each passed for all 20. These are model judgments of supplied answer/evidence packets. Source authenticity remains supported by the separate execution receipts rather than the restricted reviewer fetching originals.

## Evidence

- [Executed expanded pilot](AGENT-SEARCH-EXPANDED.md).
- [Frozen reviewer verdicts](../../artifacts/agent-expanded-review/d9d8c877-2a7a-40d1-b93e-91f22ab3375b/verdicts.json), SHA-256 `1cb3482b3c223a8f5ee2489d535040e8149d8f7d567c797faf75537a0650b2e8`.
- [Mapping disclosed after review](../../artifacts/agent-search-expanded/diagnostic-04c7e7cc3b7343a9a4582c1092bb14a0/mapping-DO-NOT-SEND.json).
- [First pilot](AGENT-SEARCH-PILOT.md), whose historical strict score remains 12/16; its inconsistent abstention flags were not silently repaired.

## Decision

The initial overall-success stepping stone is demonstrated on this bounded pilot. Do not describe it as universal 100% accuracy, engine-only performance or permission to switch normal knowledge access. Further work should prioritize reproducible integration and a representative authorized personal corpus pilot, rather than continued P@1-only tuning. Preserve originals, history, scoped ingestion and rollback. No private ingestion, global activation, staging or publication was performed.
