#!/usr/bin/env python3
"""Measure a Lean hook invocation with the decision log enabled and disabled."""

import argparse
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import tempfile
import time


REWRITE = {
    "hook_event_name": "PreToolUse",
    "turn_id": "fixture",
    "tool_name": "Bash",
    "tool_input": {"command": "git status --short"},
}
CLAUDE_PASS = {
    "hook_event_name": "PreToolUse", "tool_name": "Bash",
    "tool_input": {"command": "git diff | sort"},
}
AGY_PASS = {
    "hookEventName": "PreToolUse", "conversationId": "fixture",
    "toolCall": {"name": "run_command", "args": {"CommandLine": "Write-Host hello"}},
}


def summary_ms(samples):
    p95 = sorted(samples)[math.ceil(len(samples) * 0.95) - 1]
    return {"p50_ms": round(statistics.median(samples) / 1e6, 3), "p95_ms": round(p95 / 1e6, 3)}


def measure(exe, before, trials):
    rng = random.Random(567)
    timings = {False: [], True: []}
    with tempfile.TemporaryDirectory(prefix="footnote-lean-hook-") as tmp:
        state = {flag: Path(tmp) / str(flag) for flag in timings}
        for flag, path in state.items():
            path.mkdir()
            (path / "usage.json").write_text(json.dumps({"lean_log": flag}), encoding="utf-8")
        def invoke(flag, case):
            env = dict(os.environ, FOOTNOTE_STATE_DIR=str(state[flag]))
            binary = exe if flag or before is None else before
            payload = json.dumps(case).encode()
            start = time.perf_counter_ns()
            result = subprocess.run([binary, "hook", "lean"], input=payload, capture_output=True, env=env)
            elapsed = time.perf_counter_ns() - start
            if result.returncode:
                raise RuntimeError("hook invocation failed")
            out = json.loads(result.stdout) if result.stdout.strip() else {}
            if case is REWRITE and " run -- git status --short" not in out["hookSpecificOutput"]["updatedInput"]["command"]:
                raise RuntimeError("expected a Codex rewrite")
            if case is CLAUDE_PASS and out or case is AGY_PASS and out != {"decision": "allow"}:
                raise RuntimeError("expected the agent's pass-through response")
            return elapsed

        for _ in range(5):
            invoke(False, REWRITE)
            invoke(True, REWRITE)
        cases = (REWRITE,) if before is None else (REWRITE, CLAUDE_PASS, AGY_PASS)
        for i in range(trials):
            for flag in rng.sample([False, True], 2):
                timings[flag].append(invoke(flag, cases[i % len(cases)]))
        ledger = state[True] / "usage" / "lean-hooks.jsonl"
        count = sum(1 for line in ledger.read_bytes().splitlines() if json.loads(line)["decision"] in {"rewrite", "pass"})
        if count != trials + 5 or (state[False] / "usage" / "lean-hooks.jsonl").exists():
            raise RuntimeError("decision logging did not match the two settings")

    differences = [on - off for off, on in zip(timings[False], timings[True])]
    medians = sorted(statistics.median(rng.choices(differences, k=trials)) / 1e6 for _ in range(4000))
    return {
        "pairs": trials, "logged_decisions_including_warmup": count,
        "before" if before else "log_disabled": summary_ms(timings[False]),
        "after" if before else "log_enabled": summary_ms(timings[True]),
        "paired_median_delta_ms": round(statistics.median(differences) / 1e6, 3),
        "bootstrap_95_percent_interval_ms": [round(medians[i], 3) for i in (100, 3899)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--footnote", type=Path, required=True)
    parser.add_argument("--before", type=Path, help="Compare the full hook with this pre-change binary on a mix of calls.")
    parser.add_argument("--pairs", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.pairs <= 1000:
        parser.error("--pairs must be between 1 and 1000")
    before = args.before.resolve(strict=True) if args.before else None
    print(json.dumps(measure(args.footnote.resolve(strict=True), before, args.pairs), indent=2))


if __name__ == "__main__":
    main()
