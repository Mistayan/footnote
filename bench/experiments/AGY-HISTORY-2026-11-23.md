# Antigravity tool calls from the conversation stores, 23 November 2026

The extractor finds the same 4,101 tool calls and 1,247 `read_file` calls as #564; it finds 861 `run_command` calls with arguments where #564 reported 848.

## What was run

`bench/agy-history/extract.py` read every `agy` conversation store on this machine read-only (#571): 1 store from the CLI and
25 from T3 Code. `agy` 1.5.14 on Windows. Only aggregate counts are recorded here. The full summary is in the
[receipt](../receipts/20261123-agy-history.json).

```powershell
python -I bench/agy-history/extract.py --since 2026-11-20 --until 2026-11-22 --summary - --strict
python -I bench/agy-history/replay_lean.py --footnote target/debug/footnote.exe --since 2026-11-20 --until 2026-11-22
```

Every call falls between 20 and 22 Nov. The CLI store has no tool calls, so the counts are the same with or without the date
window. No format problem was counted (`--strict` exits 0).

## Counts against #564

A call is a step of type 132. #564 counted per-tool calls only when the tool call carries JSON arguments. The 396 calls with
status 5 have none.

| Figure | #564 | This run | |
|---|---:|---:|---|
| Tool calls (step type 132) | 4,101 | 4,101 | same |
| T3 conversation stores | 25 | 25, 23 with tool calls | same |
| `read_file` with arguments | 1,247 | 1,247 | same |
| of which ranged / whole / not done | 663 / 584 / 21 | 663 / 584 / 21 | same |
| `edit_file` with arguments | 873 | 873 | same |
| `write_file` with arguments | 163 | 163 | same |
| `pull_request_merge` done | 49 | 49 | same |
| `run_command` with arguments | 848 | 861 | +13 |

All 4,101 calls still have their original timestamps (1,151 on 20 Nov, 2,084 on 21 Nov, 866 on 22 Nov), so no calls were added
after #564. Of the 861 `run_command` calls, 853 are done, 4 have status 6, 3 failed (status 7) and 1 has status 2. Including
status 5, there are 923.

No single rule gives 848 together with the other five figures. These were each checked and ruled out:
- status;
- a time cutoff;
- strict UTF-8 or JSON decoding;
- empty commands;
- repeated commands.

#564 used an ad hoc script that was not kept, so its `run_command` filter cannot be recovered. The 861 comes from the same
rule that reproduces the other five figures.

## Lean replay

The 861 `run_command` calls were sent to `footnote hook lean` as `agy` `PreToolUse` events. The hook ran with a temporary state
folder and the decision log on, built from `main` at `e0a13be` (debug).

| Decision | Calls | Share |
|---|---:|---:|
| Rewrite to `footnote run` | 482 | 56.0% |
| Pass: compound command | 260 | 30.2% |
| Pass: not covered | 119 | 13.8% |
| Error | 0 | 0% |

Rewritten programs: `git` 296, `cargo` 72, `uv` 43, `rg` 34, `gh` 17, `npm` 7, other 13. The installed 0.6.1 binary gives the
same 482 rewrites and 379 passes. Among the 853 done calls, 55.9% are rewritten.

This measures what the current hook **would** answer for the recorded commands. `agy` stores the arguments as the model wrote
them, so the stores cannot show which rewrites actually ran (#567).
