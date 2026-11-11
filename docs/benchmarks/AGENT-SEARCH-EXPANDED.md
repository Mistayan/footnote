# Expanded end-to-end knowledge-agent diagnostic

## Verified outcome — independent review pending

**20 new task executions completed, 40 real model requests, 20 actual searches, zero gets.** All 20 outputs pass the frozen structured-output/citation-handle contract. Sixteen outputs declare sufficient evidence and four explicitly declare insufficient evidence with `abstain: true`. These are mechanical observations, **not independent semantic verdicts or an 80%/90% claim**. The objective is useful overall final-answer task success, not P@1.

Run: [`diagnostic-04c7e7cc3b7343a9a4582c1092bb14a0`](../../artifacts/agent-search-expanded/diagnostic-04c7e7cc3b7343a9a4582c1092bb14a0/).

The first pilot remains historically unchanged: 16 semantic passes but 12 strict passes because four premise-rejections supplied `abstain: false`, per frozen independent review `artifacts/agent-answer-review/ab84a86d-4e9f-4342-a9b1-a263b475a764`. No earlier answer was flipped or regraded as a prospective protocol pass.

## Frozen selection and prospective protocol

`FREEZE.json` predates first dispatch and binds the actual questions, code, source/model identities, instructions, strict response schema, rubric and limits. Selection uses seed 2026102082 and sorted design strata, not retrieval scores or easy-answer inspection. There are 16 answerable tasks (four per English/French question-to-source-language direction) and four public no-answer tasks (two per question language): ten English and ten French questions total. Every question pins a Python 3.13 documentation source edition. Negative behavior, absent APIs/guarantees, and multipart cases are included.

The original eight pilot questions and the eight completed questions from the earlier quota-blocked validation attempt are excluded. Q24 and Q20 are predeclared multipart coverage obligations; their original remaining-source questions were expanded before inference to ask explicitly for direct versus inherited field-order behavior and recursive container conversion versus copying other objects. No selected evidence IDs, answer keys, historical rankings or judge outputs enter worker requests. Design answerability/direction labels are used only by the controller to select the sample, never as a runtime answerability oracle. Private questions Q51/Q52 are excluded.

The public corpus is already exposed diagnostic material. These are new end-to-end executions, **not a fresh corpus, a human-adjudicated acceptance sample, or a private-vault evaluation**.

The versioned `agent-final/v1` schema requires exactly `schema_version`, `evidence_status`, `abstain`, `reason`, `answer` and `citations`; all are required on the actual strict JSON-schema wire request. Instructions explicitly require `abstain: true` for information unsupported by the sources, including absent requested options/guarantees, while preserving supported ordinary negative answers. The deterministic validator checks supplied `evidence_status`/`abstain` consistency, nonempty reason/answer, actual handles and exact inline/listed citation agreement. It does **not** infer answerability from answer prose or gold, flip any flag, or determine whether a cited passage semantically supports a claim.

A mechanically invalid final may receive at most one repair allowance within the four-turn task bound; invalid raw responses and rejections remain in traces. Repair is counted in model overhead, never hidden SDK retry. No repair occurred online. Search is optional (`tool_choice: auto`), not forced; the agent voluntarily chose one search for every task. Last permitted turns disable tools. Bounds are at most three searches, five gets, four model turns per task, 64 global model requests, 4096 output tokens per request, concurrency one, SDK retries zero and a 1500-second execution deadline with dispatch reserve. There was no provider/model fallback.

## Exercised system and evidence boundaries

This is custom bounded SDK orchestration, not native delegation or a full embedded AIAgent. It reuses the installed Hermes provider resolver and original authorized Codex route; requested and returned model identity is `gpt-6.1-sol` on all 40 requests. The empty worker cwd receives only current instructions/question and its own tool history, with only `search` and `get` exposed. No file, terminal, web, memory or gold tool is available.

Retrieval is the actual isolated scoped-query2 pipeline from the earlier pilot: resident encoder/reranker, a new owned Qdrant server/collection, pinned original-question constraints before acquisition and again at presentation/get, and original normalized passages with source metadata, Unicode offsets and SHA-256 hashes. Searches return raw untrusted top-five candidates, not a top-one refusal projection; ranks are not confidence. The run performed **584 real reranker pairs and 100 original-source presentations**. It is standalone experimental integration, not activation or acceptance of the shipped knowledge runtime. No live get/reformulation advantage was demonstrated; offline real-resident tests do exercise gets and source constraints.

## Actual accounting

| Measure | Actual |
|---|---:|
| Completed task executions / structural outputs | 20 / 20 |
| Model requests / terminal completions | 40 / 40 |
| Searches / gets | 20 / 0 |
| Validation repairs / refused tool calls | 0 / 0 |
| Input / output / total tokens | 139,775 / 3,468 / 143,243 |
| Missing usage requests | 0 |
| Provider billed USD | `null` (not supplied) |
| Full run wall time, including prerequisites/startup/cleanup | 200.506 s |
| Sum model-response intervals | 133.823 s |
| Sum retrieval intervals | 51.329 s |
| Median / maximum task wall time | 9.225 / 12.537 s |

Raw requests with UTC dispatch timestamps, effective wire bodies, streamed model events, terminal usage, tool returns, final answers and elapsed intervals are retained in `dispatches.jsonl`, `sdk-events.jsonl`, `traces.jsonl` and `answers.jsonl`. Missing provider cost is not fabricated as zero. All model calls in this continuation are included; the earlier quota-blocked run remains a separate historical ledger, not silently removed.

## Verification, issues and cleanup

- Sixteen scoped offline tests pass, including strict fields/disposition consistency, wrong/empty/duplicate citations, abstention without prose heuristics, one-repair allowance, optional search, source staleness, untrusted injection text, tool/turn/global limits, exact wire schema and no SDK retry. Injection controls test the interface, not live adversarial-model robustness.
- The read-only post-run verifier reconciles 40 dispatch/wire/model/terminal records, all final answers, 20 blind records, token sums, 100 source presentations, source applicability and 109 protected file/model hash entries. Historical first-pilot evidence and independent review are unchanged. The verifier was authored after inference and is not a semantic judge or part of the frozen online harness.
- Graph discovery was attempted explicitly. The index reports `tools/` as excluded and new tests as not tracked; no complete graph impact claim is made. Existing pilot core/transport/runner/retrieval were read directly. They were not modified: new expanded modules import their stable boundaries. Direct dependencies and frozen code copies provide the fallback audit.
- One pre-inference attempt (`diagnostic-e4798ead6bf843cbb1ebe0e1fc7cdd22`) stopped before any dispatch because a broad discovery pattern included an unrelated existing validation-verifier test that raises `KeyError` rather than its expected `AssertionError`. The owned runner prerequisite pattern was narrowed to its authorized `test_agent_search_pilot*.py` scope; no unrelated test/code was edited. The failed offline log is retained. This was not a provider retry or hidden model execution.
- Owned SDK exited normally. Qdrant PID25480 exited and port64162 is closed, independently rechecked. Windows termination returned code1: owned cleanup is verified, graceful durable shutdown is not claimed.
- No personal/vault ingestion, installs, downloads, new accounts, global/profile/runtime configuration changes, default activation, staging, commit or push. All authored changes are within the permitted pilot tools/tests/docs and unique diagnostic artifacts.

## Blind handoff — parent judge next

Send only these files for independent review:

1. [`blind-answer-packet.json`](../../artifacts/agent-search-expanded/diagnostic-04c7e7cc3b7343a9a4582c1092bb14a0/blind-answer-packet.json): shuffled final answers and actual original-source passages, no design labels, task IDs, ranks or expected IDs.
2. [`RUBRIC.json`](../../artifacts/agent-search-expanded/diagnostic-04c7e7cc3b7343a9a4582c1092bb14a0/RUBRIC.json).

Freeze strict and semantic verdicts before opening `mapping-DO-NOT-SEND.json`. Then report strict final success/20, answerable success and coverage/16, no-answer false-answer/4, abstention consistency, uncertainties and per-task failures. Do not infer those judgments from the mechanical count of four abstention flags. Task closure stays with the parent after verification/review.

```bash
# Scoped offline tests, including actual isolated public retrieval; no model inference
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_agent_search_pilot*.py' -v

# Read-only evidence reconciliation; writes a new verification receipt only
.venv/Scripts/python.exe -m tools.agent_search_pilot.expanded_verify artifacts/agent-search-expanded/diagnostic-04c7e7cc3b7343a9a4582c1092bb14a0
```

Documentation adversarial review checked metric substitution, historical regrading, selection leakage, fresh-sample overclaims, unsupported semantic acceptance, missing cost, optional-tool honesty, bounded repair overhead and cleanup scope. No 80%/90% milestone is asserted pending independent review.
