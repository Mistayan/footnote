# Information delivery in the recorded 22 November code-map turn

All three design decisions cited in the answer arrived through MCP recall. The hooks supplied 14 items without surfacing any of the three decisions.

| Source | Deliveries | Annotated decisions cited in the answer |
|---|---:|---:|
| Session-start pack | 10 | 0 |
| Prompt recall | 4 | 0 |
| MCP recall | 5 | 3 |
| MCP get | 2 | 0 |

The turn made 11 tool calls in nine round trips. Four were Footnote reads. One recall failed, then the successful recall returned decision IDs 217, 228 and 268. Two of the 21 memory deliveries repeated an ID. The ten recorded model requests processed 1,501,804 input tokens, of which 1,481,862 were cache reads. Peak input was 157,935 tokens.

The initial skill listing in the same trace contained 94 skills and 29,774 UTF-8 bytes. It overlaps Footnote's task-specific skill suggestions. The originating issue also identifies a terse-reply rule, a shell-output compressor and a codebase-map hook. Those overlap Footnote's Lean rules, Lean output trimming and Code map respectively. The replay provides no isolated token measurement for those injectors or the skill listing's cost on every request. [Measurement issue](https://github.com/bobcat88/footnote/issues/509)

## Reproduce locally

Run `bench/claude_context_replay.py` on the original Claude Code JSONL and the Footnote activity JSONL. The receipt fixes the task window from the user's code-map prompt to the next user message. The script includes the last recorded pack before the task, joins MCP results to their tool call IDs, and groups parallel calls into one round trip. It measures explicit references to the three annotated decisions in the final answer. That measure cannot establish whether other memories influenced the answer.

```powershell
python bench/claude_context_replay.py --transcript $trace --activity $activityLog `
  --start 2026-11-22T14:45:01.706Z --end 2026-11-22T14:47:06.301Z --required 217 228 268
```

The receipt contains counts and the three IDs already documented in the issue. Prompts, answers, payloads, file paths and native session IDs stay local.

## Next replay

Judge the context changes on whether all three decisions reach the agent before its first explicit recall, how many unrelated startup preferences it sees, and whether the answer still covers the three decisions. Use tool round trips and cached and uncached input to measure cost. This receipt records the original behavior and holds the baseline steady for that test.

Use the host's own session event to correlate each MCP result. Claude Code supports replacing an MCP result from `PostToolUse`, which offers a route for session-bound delivery and logging. Codex's published hook parser rejects that output override. Verify Codex telemetry independently and keep result replacement behind a verified host binding. [Claude Code hook reference](https://code.claude.com/docs/en/hooks#posttooluse-decision-control) · [Codex hook parser](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/engine/output_parser.rs)

[Sanitized receipt](../receipts/20261123-context-claude-recorded-turn.json)
