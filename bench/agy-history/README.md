# Antigravity tool-call history

Tools that read the tool calls Antigravity (`agy`) keeps in its conversation stores, for measuring which tools it uses and
what Footnote's hooks would do with them (#571, #564).

| File | Role |
|---|---|
| `extract.py` | One JSONL row per tool call; `--summary` writes aggregate counts |
| `replay_lean.py` | Sends the recorded `run_command` calls to `footnote hook lean` and reports rewrite and pass rates |
| `test_extract.py` | Tests on a synthetic store built in the test |

```powershell
python -I bench/agy-history/extract.py --summary -                     # aggregate counts only
python -I bench/agy-history/extract.py --out bench/agy-history/out/calls.jsonl  # no argument values
python -I bench/agy-history/extract.py --with-args --out bench/agy-history/out/args.jsonl  # private
python -I bench/agy-history/replay_lean.py --footnote target/debug/footnote.exe --since 2026-11-20 --until 2026-11-22
python -m unittest discover -s bench/agy-history -p "test_*.py"
```

Run with `python -I` whenever the stores are read. `bench/agy-history/out/` is ignored by Git.

## Privacy

The stores hold whole conversations. A row has the conversation id, step number, time, status, tool name and the argument
**keys**. Argument values (commands, paths, edits) are only included with `--with-args`, and `replay_lean.py --fixtures` writes
commands. Keep those files local and never commit them. Committed results hold aggregate counts only.

## Where the stores are

| Root | Used by |
|---|---|
| `~/.gemini/antigravity-cli` | `agy` run from a terminal |
| `~/.t3/userdata/providers/antigravity/<hash>/antigravity-acp` | `agy` run by T3 Code (one root per installation hash) |

Each conversation is `<root>/conversations/<conversation id>.db`, a SQLite file. `extract.py` opens it with a
`file:…?mode=ro` URI, so it never writes, even while `agy` has the conversation open.

## Format notes (`agy` 1.5.14, stores from 20 to 22 Nov 2026)

Table `steps(idx, step_type, status, has_subtrajectory, metadata, error_details, permissions, task_details, render_info,
step_payload, step_format)`. `metadata` and `step_payload` are protobuf messages without a published schema. `extract.py`
reads them with a small varint and length-delimited reader. The field numbers below are the ones it relies on.

- **`step_type` 132 is a tool call.** Other types seen: 14, 15 (the most common, model turns), 17, 23, 101. None of them
  carry a tool call.
- **`metadata`**
  - Field 1 is the step's time: a Timestamp message with seconds at field 1 and nanoseconds at field 2.
  - Field 4 is the tool call: `call_<id>` at field 1, the tool name at field 2, the arguments as JSON text at field 3.
  - Field 8 is a later time, present on finished steps.
  - Field 26 is the list of status changes with their times.
- **`step_payload`**
  - Field 1 repeats `step_type`, field 4 repeats `status`, and field 5 is a copy of `metadata`.
  - Field 31 holds the error text on failed calls.
  - Field 140 is the arguments again as a map, repeated `{1: key, 2: value}`.
- **`status`.** 3 means done (3,646 of 4,101 calls). 7 is a failed call with an error at payload field 31 (47). Status 5
  (396) is a call whose tool call has **no JSON arguments**: the keys are only in the field 140 map. Statuses 6 (11) and 2 (1)
  carry arguments but no end time on some steps; their meaning is not confirmed.
- **Arguments are stored as the model wrote them**, not as a hook rewrote them, so a replay shows what a hook would answer.
  Rewrites that actually ran have to come from Footnote's own logs (#567).

Rows say where their argument keys came from: `json_args` is true when the tool call carries JSON, which is the definition
behind the per-tool counts in #564 (for example 1,247 `read_file`). Otherwise `arg_keys` falls back to the field 140 map.

## Spotting a new `agy` format

A new `agy` version can renumber fields or add step types. `extract.py` counts every mismatch under `problems` in the summary,
prints them on stderr and, with `--strict`, exits with code 2. Check after an `agy` update:

1. `python -I bench/agy-history/extract.py --summary - --strict` exits 0 and `problems` is empty. Each problem has a name:
   - `tool_call_missing`: a 132 step without metadata field 4.
   - `payload_step_type_mismatch`, `payload_status_mismatch`: the payload's copy disagrees with the columns.
   - `time_missing`, `args_not_json`, `bad_protobuf`.
   - `steps_columns_missing`: the table changed.
2. `step_types_seen` has no new type, and type 132 still appears in new conversations. If it vanishes while 15 and 101 keep
   growing, tool calls have moved to another type.
3. `by_tool` still names familiar tools. Garbled names mean field 4 no longer holds the tool call.
4. Compare `agy --version` with the version above, and update these notes and the tests when the format changes.

## Lean replay

`replay_lean.py` takes each `run_command` call with JSON arguments and sends it as the event `agy` gives a `PreToolUse` hook:
`{"hookEventName": "PreToolUse", "conversationId": …, "toolCall": {"name": "run_command", "args": {...}}}`.

The hook answers in one of three ways:
- a rewrite, `{"decision": "allow", "overwrite": {"CommandLine": …}}`;
- a pass, `{"decision": "allow"}`;
- an error.

The hook runs with a temporary `FOOTNOTE_STATE_DIR`, with the decision log turned on, so the summary can count the hook's pass
reasons and rewritten programs. Both come from the hook's fixed vocabulary, never from command text. The real ledger is not
touched. A binary older than #603 writes no decision log, so its summary has no reasons.
