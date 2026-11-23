# GPT Sol memory deduplication on 23 November 2026

Repeats fell from three to two in one accepted pair. The two MCP responses together shrank by 377 bytes (12.6%). Both runs returned the two required facts, ran all four trusted Footnote hooks and used Lean for Git.

| Measure | Baseline | Bound session |
|---|---:|---:|
| Memory deliveries containing text | 6 | 5 |
| Repeat deliveries containing text | 3 | 2 |
| Distinct memories delivered | 3 | 3 |
| Required facts in the answer | 2 | 2 |
| Tool round trips | 3 | 3 |
| Total MCP response bytes | 2,981 | 2,604 |
| Total tokens | 67,537 | 90,979 |
| Cached input tokens | 57,984 | 80,896 |

The start hook supplied the short memory in full, so MCP get returned its ID with an already-shown marker. The prompt hook supplied an excerpt of the long memory. MCP get still returned its full text. The final answer contained both fixture values in each run.

Both arms used the same Footnote binary, Codex CLI 0.171.0, GPT-6.2 Sol, and a fresh synthetic repository and memory database. The host ran the bound arm first. The prompt fixes the tool sequence to exercise both retrieval paths, so this pair measures response size and fixture success. Observed tokens rose in the bound arm, with 22,912 more cached input tokens. Estimating end-to-end cost or the effect on model-selected tool use requires more pairs and a natural-session replay under #509.

### Binding contract

The experimental path uses a dedicated stdio MCP process for one host session. In the live probe, Codex did not supply the fresh thread ID to the stdio server. A launcher passes the absolute path of a private JSON file through `FOOTNOTE_CONTEXT_SESSION_FILE` to both the hooks and the MCP server. It writes `session` (the host's native UUID), `project` and the absolute `cwd` before the turn. The launcher controls the file and retires the binding when it ends or replaces the conversation. A missing or incompatible binding preserves regular MCP results.

Only complete project memories rendered by the hook qualify. The existing atomic hook session snapshot stores IDs and content digests, keyed to the bound session, workspace, project and database. A new SessionStart resets that snapshot. A pointer, changed text or a different session still gets a normal response. In a bound session, `footnote_get` with `full: true` explicitly requests text. The shared daemon continues serving its normal MCP results.

Automatic binding for installed clients, MCP-to-hook accounting, scope migration and a shared turn budget remain open under #510 and #513.

```powershell
python bench/codex_hook_activation.py --footnote $verifiedBinary --baseline --sandbox danger-full-access
python bench/codex_hook_activation.py --footnote $verifiedBinary --baseline --deduplicate --sandbox danger-full-access
```

[Sanitized paired receipt](../receipts/20261123T120003Z-context-codex-session-dedup.json)
