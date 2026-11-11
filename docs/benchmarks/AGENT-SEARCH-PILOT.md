# Agent search pilot — historical run, independent review completed

## Prospective continuation (historical outputs unchanged)

The frozen independent review at `artifacts/agent-answer-review/ab84a86d-4e9f-4342-a9b1-a263b475a764` found **16/16 semantic passes and 12/16 strict passes**: four correct premise rejections incorrectly supplied `abstain: false`. This is not a substantive invented-answer failure, but it fails the explicit-abstention protocol. No old response or score was changed to make the original run pass.

The prospective strict-schema protocol and **20 new task executions** are documented in [AGENT-SEARCH-EXPANDED.md](AGENT-SEARCH-EXPANDED.md). Its independent answer review remains pending. The original report below is retained as its historical pre-review description; references to pending review there describe that earlier reporting state.

## Outcome

The first bounded **actual model → search → source passages → cited final answer** pilot completed all **16 task executions** (the same eight questions in two arms). This is a reused-public-corpus diagnostic, **not fresh 80%/90% acceptance**, and not a private-vault evaluation. The target is **overall final task success**, not first-passage accuracy.

Run: [`diagnostic-de868c3bac8c4d47986bc8a861189699`](../../artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699/).

- **32 real model requests**, 32 terminal completions, 16 actual searches, zero online gets; no retries or provider/model fallback.
- All 16 final responses satisfy the structural JSON/citation-handle checks. Structural completion is **not semantic correctness**.
- The iterative-permitted model voluntarily stopped after one search on every task. **This run does not demonstrate online reformulation, get usage, or an advantage from iteration.** No extra inference, prompt tuning, or forced iteration was introduced after seeing that outcome.
- Independent final-answer/citation judgments are pending. No implementing-agent quality score or milestone claim is made.

## Frozen contract

[`FREEZE.json`](../../artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699/FREEZE.json) was saved before model dispatch. It binds exact questions, rubric, system prompt, schemas, model/server identities, code and inputs. Questions are unchanged selections from the existing exposed 52-question diagnostic: Q02, Q07, Q25, Q12, Q18, Q33, Q41, Q42. There are six author-design answerable and two no-answer cases, four English/four French questions, explicit English/French source-edition constraints, negation/false-valued flags, and multipart return-or-raise/ClassVar-or-InitVar cases. These are short technical questions, not a representative complex-task distribution.

| Arm | Search bound | Get bound | Model-turn bound | Actual executions / model requests / searches / gets |
|---|---:|---:|---:|---|
| Single search then answer | exactly 1 | 0 | 2 | 8 / 16 / 8 / 0 |
| Iterative permitted | 1–3 | 0–5 | 4 | 8 / 16 / 8 / 0 |

Both use top-five candidates, fresh histories and the same approved public corpus. Task order is frozen; which arm runs first alternates by task. Requests are sequential. Global dispatch ceiling is 64; each call sends `max_output_tokens=4096`, SDK `max_retries=0`, current model `gpt-6.1-sol`, reasoning effort `low`. Last permitted turn disables tools. No pilot prompt/schema/limit changed after inference.

The final output has exactly `answer`, `abstain`, and `citations`. Every non-abstaining answer requires returned handles. The independent rubric requires complete answers to every requested part, negation preservation, claim-level citation support, correct source edition/version/family, and explicit abstention rather than an invented absent API/guarantee for no-answer tasks. An answerable abstention is a miss. Author-selected IDs do not establish correctness; genuinely supporting unlabelled evidence is admissible.

## What actually ran

Provider resolution used the installed Hermes `resolve_runtime_provider`, authorized existing parent account and framework Codex identity-header helper. No credential file was directly opened or secret printed/copied into artifacts. Installed delegation construction and credential-resolution source were inspected first. Ordinary native delegation was not used because the experiment needs an exact two-tool surface, hard dispatch bounds and no inherited profile tools.

This is an explicitly labeled **custom bounded SDK orchestration loop**, not a claim that native `delegate_task` or an embedded full `AIAgent` was exercised. The project interpreter owns resident retrieval; a separate existing Hermes interpreter owns the SDK, avoiding incompatible package environments without installing anything. The SDK process has an empty owned worker cwd; inference sees only the frozen instructions, current question, its own tool exchanges and final-answer history. No model file, terminal, web, memory, vault, old-report or gold access is exposed. Source-author judgments were not loaded or copied; they remain outside that workspace.

The effective SDK request is checked **after** Hermes' `extra_body` transform bypass. Wire receipts record the full public request body, URL, tools and cap, never authentication headers. All 32 actual wire URLs are `https://chatgpt.com/backend-api/codex/responses`; all requested and returned model names are `gpt-6.1-sol`. SDK version was 2.24.0. SSE event payloads, exact model function names/argument strings, returned passages, response IDs and usage are retained. Consumption stops at a completed `response.completed`, without draining past terminal completion.

### Retrieval path is standalone, not shipped-runtime acceptance

The current `tools/knowledge_runtime` was inspected, not replaced. It exposes JSONL search/get and optional reranking, but its acquisition uses a direct point budget of 60/64, lexical acquisition 20/64, and budget5/budget10/budget20 reranking. That is **not** the scoped-query2 diagnostic recipe's source-sliced 400-point/100-parent acquisition, FTS10, equal RRF60 pool20 and two original-order mMARCO rounds. Substituting it would change the system being measured.

The pilot therefore uses a new standalone adapter over the actual existing frozen scoped-query2 functions, pinned public corpus/vectors, resident encoder/reranker and a new owned Qdrant server/collection. Server startup reported 500 points, green status. Original-question source constraints remain pinned across model reformulations, are enforced before dense/lexical limits and rechecked at source presentation/get. Evidence is original normalized source text with exact Unicode offsets and SHA-256 hashes, not ranker-window text. Source files are rehashed at presentation/get.

The historical top1-logit cutoff is **not** applied to hide the other candidates: raw top-five passages are explicitly `untrusted_source_data`, `answerability=not_estimated`. The final agent may abstain. All actual search traces retain acquisition, ranking, actual reranker pairs and full presented passages. There were **592 real reranker pairs**, not synthetic retrieval fixtures. Historical evidence/code/input hashes checked unchanged; this does not activate or certify the shipped runtime.

## Measured accounting

| Measure | Single | Iterative permitted | Combined |
|---|---:|---:|---:|
| Input tokens | 53,721 | 53,776 | 107,497 |
| Output tokens | 1,129 | 1,147 | 2,276 |
| Total tokens | 54,850 | 54,923 | 109,773 |
| Missing usage calls | 0 | 0 | 0 |
| Sum task wall time, seconds | 71.588 | 68.674 | — |
| Median task wall time, seconds | 8.536 | 8.585 | — |

Pilot wall time including startup/cleanup: **144.286 s**. Model-response intervals sum to 90.941 s; resident retrieval intervals sum to 49.293 s. These are attributed sequential stage intervals, not a new backend benchmark. Prompt calls: 32; retrieval-tool calls: 16. Provider-reported cached input tokens: 0; reasoning output tokens: 0. **Billed USD is unavailable (`null`), not zero.** Missing usage remains `null` in raw records, never a fabricated zero. This small sequential run does not establish a latency difference between arms.

No final response sets its `abstain` flag. That is an observed output property, not an assessment of no-answer success; the independent reviewer must apply the frozen rubric, including unsupported counterclaims and the explicit-abstention requirement.

## Evidence and independent handoff

Send the parent judge **only**:

1. [`blind-answer-packet.json`](../../artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699/blind-answer-packet.json): 16 shuffled final answers with the actual returned source passages and citation handles, no arm/rank/scores/expected IDs.
2. [`RUBRIC.json`](../../artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699/RUBRIC.json).

Freeze independent verdicts before opening `mapping-DO-NOT-SEND.json`, then join by `review_id`. Report final successes/8 per arm, answerable successes/6, coverage, abstentions, no-answer false answers/2 and paired outcomes; uncertain judgments remain explicit. No fresh generalization claim follows from this exposed small diagnostic.

Audit artifacts: `answers.jsonl`, `traces.jsonl`, `sdk-events.jsonl`, `dispatches.jsonl`, `route.json`, `resident-start.json`, `report.json`, `postrun-verification.json`, `postrun-verification-scope.json`, `offline-tests-final.log`, `cleanup.json`, archived frozen `code/`, original `artifact-sha256.json`, and `delivery-sha256.json`. Post-run mechanical verifier/test were authored after inference; they do not modify the frozen harness, prompts, outputs or rubric and do not score semantics.

## Verification, boundaries and cleanup

- TDD tracer bullets were observed failing before implementation for tool bounds/unknown-tool denial; untrusted context, source staleness/hash/offset checks and invalid citations; bounded model loop; real isolated resident search/get; SDK terminal-completion/retry/wire checks; freeze/accounting; post-run reconciliation. Offline model/SSE controls are explicitly synthetic **test fixtures only**, excluded from pilot counts and never substituted for inference.
- Seven focused tests pass. The real resident test exercises five gets offline; **online get usage remains zero**. Offline injection text is returned as data and does not execute an instruction; this is not a live adversarial-model prompt-injection certification.
- Read-only reconciliation checks 32 wire requests/completions against dispatches, model/tool traces and token totals; 80 exact source presentations; source constraints; 16 blind-packet mappings; original artifact manifest and 64 protected code/input/model entries.
- Owned SDK process exited normally. Owned Qdrant PID30200 exited and port55131 closed, corroborated by independent PID/socket checks. Windows termination returned code1; cleanup is owned termination, **not proof of graceful durability**. Retained server storage is unique public-fixture evidence, not an active service.
- No installs, downloads, new provider/subscription, model switch, personal/vault ingestion, global/profile/runtime/config edits, staging or commits. Only new `tools/agent_search_pilot/*`, `tests/test_agent_search_pilot*.py`, this document and unique pilot artifacts were authored. Process-local child environment flags do not activate a profile. Beads task closure is left to the parent.

Commands (from `D:/Projets/BorgKnowledge`):

```bash
# Offline tests plus actual isolated public-retrieval test; no model inference
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_agent_search_pilot*.py' -v

# Read-only reconciliation, writing only its new postrun receipt
.venv/Scripts/python.exe -m tools.agent_search_pilot.verify artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699

# Creates a NEW diagnostic and makes real billable/model-account requests;
# do not rerun merely to repair/review the completed pilot
.venv/Scripts/python.exe -m tools.agent_search_pilot.runner
```

Documentation adversarial review: checked metric confusion, fabricated execution, tool escalation, source-scope drift, hidden cutoff, iterative-arm overclaim, missing cost/usage, no-answer rubric, blind leakage and cleanup. These limitations are explicit. Semantic quality remains intentionally unscored by the implementing agent.
