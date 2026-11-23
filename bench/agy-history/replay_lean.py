#!/usr/bin/env python3
"""Replay recorded Antigravity `run_command` calls through `footnote hook lean`.

Each call is sent as the PreToolUse event `agy` gives the hook. The hook's answer is a rewrite
(`{"decision": "allow", "overwrite": {...}}`), a pass (`{"decision": "allow"}`) or an error. The summary
holds aggregate counts only: rewrite and pass rates, pass reasons and rewritten programs from the hook's
own fixed vocabulary. `--fixtures` writes each command with its decision for #565; that file is private.

The hook runs with a temporary FOOTNOTE_STATE_DIR, so the real decision ledger is not touched.
Run with `python -I`: it reads the conversation stores.
"""

import argparse
import collections
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def load_extract():
    spec = importlib.util.spec_from_file_location("agy_extract", Path(__file__).with_name("extract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hook_event(row):
    return {
        "hookEventName": "PreToolUse",
        "conversationId": row["conversation"],
        "toolCall": {"name": row["tool"], "args": row["args"]},
    }


def classify(returncode, stdout):
    """Return (decision, rewritten command or None) for one hook answer."""
    if returncode:
        return "error", None
    text = stdout.strip()
    if not text:
        return "pass", None
    try:
        answer = json.loads(text)
    except ValueError:
        return "error", None
    if not isinstance(answer, dict) or answer.get("decision") != "allow":
        return "error", None
    overwrite = answer.get("overwrite")
    if overwrite:
        return "rewrite", overwrite.get("CommandLine") or overwrite.get("command")
    return "pass", None


def replayable(rows):
    return [r for r in rows if r["tool"] == "run_command" and r.get("json_args")
            and isinstance(r.get("args"), dict) and isinstance(r["args"].get("CommandLine"), str)]


def read_ledger(state):
    rows = []
    for name in ("lean-hooks.jsonl.old", "lean-hooks.jsonl"):
        path = state / "usage" / name
        if path.exists():
            rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def replay(rows, footnote, run=subprocess.run):
    """Feed each row to the hook; return (per-call results, aggregate summary)."""
    results = []
    with tempfile.TemporaryDirectory(prefix="footnote-agy-replay-") as tmp:
        state = Path(tmp)
        (state / "usage.json").write_text(json.dumps({"lean_log": True}), encoding="utf-8")
        env = dict(os.environ, FOOTNOTE_STATE_DIR=str(state))
        for row in rows:
            proc = run([str(footnote), "hook", "lean"], input=json.dumps(hook_event(row)).encode("utf-8"),
                       capture_output=True, env=env, timeout=60)
            decision, rewritten = classify(proc.returncode, proc.stdout.decode("utf-8", "replace"))
            results.append({"row": row, "decision": decision, "rewritten": rewritten})
        ledger = read_ledger(state)
    return results, summarize(results, ledger)


def rate(part, whole):
    return round(part / whole, 4) if whole else None


def summarize(results, ledger):
    decisions = collections.Counter(r["decision"] for r in results)
    done = [r for r in results if r["row"]["status"] == 3]
    done_decisions = collections.Counter(r["decision"] for r in done)
    reasons = collections.Counter(e.get("reason") or "none" for e in ledger if e.get("decision") != "rewrite")
    programs = collections.Counter(e.get("program") or "other" for e in ledger if e.get("decision") == "rewrite")
    total = len(results)
    return {
        "calls": total,
        "rewrite": decisions["rewrite"],
        "pass": decisions["pass"],
        "error": decisions["error"],
        "rewrite_rate": rate(decisions["rewrite"], total),
        "pass_rate": rate(decisions["pass"], total),
        "done_calls": len(done),
        "done_rewrite_rate": rate(done_decisions["rewrite"], len(done)),
        "ledger_rows": len(ledger),
        "pass_reasons": dict(reasons.most_common()),
        "rewrite_programs": dict(programs.most_common()),
    }


def footnote_version(footnote):
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        out = subprocess.run([str(footnote), "--version"], capture_output=True, timeout=30)
        return out.stdout.decode("utf-8", "replace").strip() or None
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--footnote", type=Path, help="footnote binary (default: the one on PATH).")
    parser.add_argument("--root", action="append", type=Path, help="Store root (repeatable); see extract.py.")
    parser.add_argument("--input", type=Path, help="Rows from `extract.py --with-args` instead of reading the stores.")
    parser.add_argument("--since", help="First UTC day to keep, YYYY-MM-DD.")
    parser.add_argument("--until", help="Last UTC day to keep, YYYY-MM-DD.")
    parser.add_argument("--summary", type=Path, help="Write the aggregate summary here (default: stdout).")
    parser.add_argument("--fixtures", type=Path,
                        help="Write each command, decision and rewrite as JSONL. Private: never commit.")
    args = parser.parse_args(argv)

    footnote = args.footnote or (Path(found) if (found := shutil.which("footnote")) else None)
    if not footnote or not footnote.exists():
        parser.error("footnote binary not found; pass --footnote")
    extract = load_extract()
    if args.input:
        rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = [r for r in rows if extract.in_window(r, args.since, args.until)]
    else:
        rows, _ = extract.extract(args.root or extract.default_roots(), True, args.since, args.until)
    calls = replayable(rows)
    if not calls:
        parser.error("no run_command calls with arguments (did --input come from extract.py --with-args?)")
    results, summary = replay(calls, footnote.resolve())
    summary = {"footnote": footnote_version(footnote), "window": {"since": args.since, "until": args.until}, **summary}
    text = json.dumps(summary, indent=2) + "\n"
    for path in (args.summary, args.fixtures):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
    if args.summary:
        args.summary.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.fixtures:
        with args.fixtures.open("w", encoding="utf-8", newline="\n") as sink:
            for r in results:
                row = r["row"]
                sink.write(json.dumps({
                    "conversation": row["conversation"], "step": row["step"], "status": row["status"],
                    "command": row["args"]["CommandLine"], "decision": r["decision"], "rewritten": r["rewritten"],
                }, ensure_ascii=False) + "\n")
    return 1 if summary["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
