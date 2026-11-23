# Follow-up memory recall in the recorded code-map turn

The follow-up hook surfaced all three annotated decisions. Direct recall surfaced one on the same memory snapshot.

| Measure | Direct recall | Follow-up recall |
|---|---:|---:|
| Annotated decisions shown at prompt time | 1 of 3 | 3 of 3 |
| Memories shown by the prompt hook | 4 | 4 |
| Rendered hook context, UTF-8 bytes | 1,115 | 1,109 |

The prompt referred to the preceding work without naming the code-map topic. The previous completed reply named the project command. The hook used its two topic terms to find additional project memories, including a decision tagged `locked`. IDs 217, 228 and 268 appeared as excerpts. The agent can fetch the full text if it needs the rest.

Both arms used the same binary, recorded prompt, prior reply and already-shown list reconstructed from the activity log. They read a consistent snapshot of the current memory database with lexical ranking. The original recorded turn used its own database state and returned none of the three decisions at prompt time. The paired run exercised the real hook entry point locally without making a model request. It measures earlier delivery of the excerpts. Answer quality, tool calls and token use await a model replay. [Recorded turn](INFORMATION-LAYER-RECORDED-TURN-2026-11-22.md)

## Enable and reproduce

`memory.follow_up_recall` is off by default. When enabled for Claude Code, the hook looks at a bounded tail of the local transcript for the previous completed reply in the same session and workspace. The follow-up must contain a reference to earlier work and have no file or symbol anchors. The previous reply must point to one explicit project command with a hyphenated subcommand. Existing direct project hits keep their order. Matching project memories fill the remaining slots, with one matching locked decision preferred. The hook's usual recall limit and excerpt size apply. The transcript stays local and the activity log records only memory IDs and the recall reason.

```powershell
footnote config set memory.follow_up_recall true
python bench/claude_follow_up_replay.py --footnote $verifiedBinary --transcript $trace `
  --activity $activityLog --memory $memoryDb --cwd $footnoteCheckout `
  --start 2026-11-22T14:45:01.706Z --required 217 228 268
```

The replay command tests both settings in temporary state and leaves the installed configuration and memory store untouched.

[Sanitized receipt](../receipts/20261123-claude-follow-up-hook-replay.json)
