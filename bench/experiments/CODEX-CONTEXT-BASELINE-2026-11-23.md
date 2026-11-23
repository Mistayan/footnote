# GPT Sol context baseline on 23 November 2026

GPT Sol accepted both fixture runs. Footnote delivered six memory items per run, including three repeats.

## Protocol

Run the Codex hook gate with `--baseline`. It creates one short project memory, one longer project fact retrieved by MCP, and one unrelated global preference. Two random words never appear in the prompt. Acceptance requires both in the final answer, all four trusted hooks, one successful Lean Git rewrite, and the expected MCP recall and get calls. Each result is attributed to the same Codex thread using app-server notifications and the hook activity log. Raw prompts, responses and fixture words stay out of the receipt.

## Result

| Source | Items delivered | Distinct items used in the final answer |
|---|---:|---:|
| Hook session pack | 2 | 1 |
| Hook prompt recall | 1 | 1 |
| MCP recall | 1 | 1 |
| MCP get | 2 | 2 |

The pack included the unrelated preference. Prompt recall supplied the longer fact before either MCP request, so there were zero required facts missed by the hooks in this fixture. The model completed three tool round trips. Each accepted run recorded 51,072 cached input tokens. The provider's cache counter measures observed cache reads. The test does not identify other portions of context the model reread.

Use counts reflect words in the final answer. They can mark the same memory as useful in multiple channels because this fixture measures delivery and repetition, not which copy caused the answer. The prompt specifies the tool route so the test can exercise all four channels. Standalone Codex, Footnote 0.6.1, and GPT-6.2 Sol ran with Codex memories, plugins and other configured MCP servers disabled. Measuring overhead from additional injectors, production MCP-to-hook correlation, and replaying a natural session remain open under #509.

```powershell
python bench/codex_hook_activation.py --footnote (Join-Path $env:LOCALAPPDATA 'Programs/footnote/footnote.exe') --baseline
```

[Sanitized receipt](../receipts/20261123T112440Z-context-codex-footnote061.json)
