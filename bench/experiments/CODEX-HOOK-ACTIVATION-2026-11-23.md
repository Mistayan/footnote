# Codex hook activation on 23 November 2026

GPT-6.2 Sol used the fixture memory and ran the requested Git command through Footnote Lean.

## Decision rule

Count a Codex run only if Codex trusts the installed Footnote definitions, all four hooks complete in the same session, and the requested model actually uses them. The fixture seeds a random word in its private scratch memory database and never puts that word in the prompt. The model must return the word after one Git command. A same-session pack entry proves the memory was shown. The completed command and the successful Lean ledger row prove the rewrite ran.

## First accepted run

- Windows, Codex CLI 0.171.0, GPT-6.2 Sol, and Footnote 0.6.1 from the published Windows engine archive. Engine SHA-256 `d6517d41062451eeb42dccfd276a3b6ef1198febd533106da320b98ebbdcd532`.
- Codex reported all four hooks as modified before approval. After review through Codex's own hook menu, a fresh app-server process reported all four as trusted.
- The live turn completed SessionStart, UserPromptSubmit, PreToolUse and Stop. One fixture memory was shown and used. The only shell command was rewritten to `footnote run -- git log -3 --oneline`, and the scratch Lean log recorded one successful Git run.
- The user's configured `dangerFullAccess` profile was used for the accepted result. With an explicitly forced Windows workspace-write profile, the shell could not launch the executable from its per-user installation path. That profile failed the gate.
- Fresh Codex profiles with missing or untrusted Footnote hooks were rejected before a model call.

The rerun passed all checks again. [Sanitized run receipt](../receipts/20261123T111035Z-activation-codex-footnote061.json)

## Replay

```powershell
python bench/codex_hook_activation.py --footnote (Join-Path $env:LOCALAPPDATA 'Programs/footnote/footnote.exe')
```

Use the same Codex profile and sandbox policy as the benchmark under test. The probe disables plugins, Codex memories and configured MCP servers for its synthetic turn. Its receipt contains counts and check outcomes. The scratch database and raw responses stay out of Git.

This is one activation fixture for #509. Measuring precision across sources, joining MCP tool results to hook sessions, and measuring cost per accepted project task still require the baseline replay.
