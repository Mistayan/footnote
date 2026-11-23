# Concise memory writes and recall excerpts

In the second synthetic pilot, concise writes with excerpts qualified for a larger opt-in trial. The excerpt-only arm missed the quality gate.

This benchmark tests whether shorter memory text preserves enough information for an agent to act. The [protocol](CONCISE-MEMORY-PROTOCOL-2026-11-23.md), fixture notes, answer key and scorer were frozen in `0e952caac1b51d88d2403e98261605aabb38559b` before scoring.

## Local replay

| Arm | Scoped task hits | Exact spans in the first excerpt | Recall context characters |
|---|---:|---:|---:|
| Current | 4/4 | 16/28 | 1,480 |
| Excerpt | 4/4 | 25/28 | 1,189 |
| Write and excerpt (fixed write surrogate) | 4/4 | 25/28 | 1,189 |

The replay reproduced all case rows on a second run with Footnote 0.6.1. Current recall clipped the action and identifiers for Glasshouse and Redwood. Selecting whole decision sentences recovered those fields and used 19.7% fewer characters. The selection left out archive references for Glasshouse, Windward and Greywater. Current recall showed the Greywater reference. Every stored record returned its full original fixture text by ID before and after replay. The [local receipt](receipts/20261123-concise-memory-local.json) records the spans and hit IDs per case.

## Live pilot

The pilot uses Codex 0.171.0 and GPT-6.2 Sol with medium reasoning effort in fresh ephemeral threads. The standard and concise writers receive the same eight synthetic source notes. The runner stores their JSON replies through `footnote remember` in two temporary databases. Current and Excerpt share the standard writer's records and usage. The live hooks run on all three arms with a separate activation record. The replay payload enters the initial task prompt, and a fixture MCP server serves full texts by ID. Each follow-up stays in the same thread and receives no new replay payload.

The first pilot accepted 0/4 tasks in each arm even though every case retrieved the scoped record and passed the hook trace. All arms missed the scope field as scored, and all used a different action label than expected for the same two initial requests. Each arm scored 23/29 fields. The prompts left scope formatting and the distinction between `hold` and `deny` underspecified. The [first live receipt](receipts/20261123-concise-memory-codex.json) preserves the complete usage and failure grades. Commit `75f3b67a8a00f3471854fba298f50f6df7db4c69` froze the clarified response format and a separate fallback probe before the second live run.

| Arm | Correct fields | Accepted | Cached input | Uncached input | Write output | Task output | Total tokens per accepted task |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current | 28/29 | 3/4 | 211,328 | 51,838 | 445 | 1,066 | 88,226 |
| Excerpt | 27/29 | 2/4 | 202,368 | 60,698 | 445 | 927 | 132,219 |
| Write and excerpt | 29/29 | 4/4 | 272,896 | 47,780 | 364 | 1,041 | 80,520 |

Both writers and all 12 measured task threads passed hook, model and usage checks. All cases excluded the other-project near-match. The standard writer produced 951 stored characters and the concise writer produced 888. The recall formatter made no change to the standard writer's excerpts in this run. The only failed task fields were the exact `scope` strings in Redwood for Current and in Windward and Redwood for Excerpt. The action, identifiers and follow-up fields all matched across the three arms. Write and Excerpt spent 322,081 total tokens, 21.7% more than Current's 264,677. Its fourth acceptance brought the observed tokens per accepted task 8.7% below Current. With four cases and scope-field failures driving that denominator, the result supports another trial. The [second live receipt](receipts/20261123-concise-memory-codex-v2.json) has the case grades and usage.

Current and Excerpt made zero full-text calls. Write and Excerpt made two attempts, including one repeated ID lookup. The second pilot's parser expected verbose JSON and could not verify the compact responses. The `observed_failed_lookup_calls` field in that receipt therefore counts unverified deliveries. Both pilot invocations scheduled zero retries. The raw Codex telemetry and observed tool events leave provider-internal retries unknown.

Commit `854ed3217baaeb619da7fe79244e3c774ca34dd5` added compact response decoding. The [separate live lookup probe](receipts/20261123-concise-memory-codex-lookup.json) verified one successful full-text lookup on the follow-up and the exact archive reference that the excerpt omitted. Its usage has its own receipt and stays outside the paired totals.

## Reproduce

Run from the repository root with Python 3.12 and Footnote 0.6.1. For the live pilot, point `--live-codex-home` at a dedicated authenticated test profile that already trusts the four installed Footnote hooks. Use a new output path for each run.

```powershell
$benchFootnote = (Get-Command footnote).Source
python bench/concise_memory.py --footnote $benchFootnote --output bench/receipts/concise-local-rerun.json
python bench/concise_memory.py --footnote $benchFootnote --live-codex-home <fixture-profile> --output bench/receipts/concise-live-rerun.json
python bench/concise_memory.py --footnote $benchFootnote --live-codex-home <fixture-profile> --lookup-probe-only --output bench/receipts/concise-lookup-rerun.json
python -m unittest discover -s bench -p test_concise_memory.py
```

## Limits

The four tasks use author-written English fixtures, lexical recall, and structured dry-run decisions. Exact-span checks describe the shown text and can miss paraphrases. The task score checks the returned action, relevant fields and memory ID. The benchmark's write prompts approximate the product save guidance and count model output through the writer reply. Live recall placement and the writer's reply format are controlled benchmark inputs. Billing costs are unknown. A larger opt-in trial needs representative held-out tasks, verified lookup outcomes across both arms, and native hook and write-path measurements.
