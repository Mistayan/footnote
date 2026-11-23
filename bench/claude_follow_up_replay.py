#!/usr/bin/env python3
"""Replay one recorded Claude Code prompt against both hook settings locally."""

import argparse
from collections import deque
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

from claude_context_replay import instant, rows


def run(args):
    session = args.transcript.stem
    cutoff = int(args.start.timestamp() * 1000)
    history = deque(maxlen=128)
    for row in rows(args.transcript):
        if row.get("sessionId") != session or row.get("type") not in {"user", "assistant"}:
            continue
        if not row.get("timestamp") or instant(row["timestamp"]) > args.start:
            continue
        history.append(row)
    if not history or history[-1]["type"] != "user" or instant(history[-1]["timestamp"]) != args.start:
        raise ValueError("start must match the recorded user prompt")
    original = history[-1]
    prompt = original["message"]["content"]
    if not isinstance(prompt, str):
        raise ValueError("the replay expects a plain text prompt")
    cwd = args.cwd.resolve(strict=True)
    for row in history:
        if row.get("cwd") == original["cwd"]:
            row["cwd"] = str(cwd)

    shown = set()
    for row in rows(args.activity):
        if row.get("session") != session or row["t"] >= cutoff:
            continue
        if row["event"] == "pack":
            shown = set(row["ids"])
        elif row["event"] == "recall":
            shown.update(row["ids"])

    required = set(args.required)
    exe = args.footnote.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="footnote-follow-up-") as tmp:
        root = Path(tmp)
        transcript = root / f"{session}.jsonl"
        transcript.write_text("\n".join(json.dumps(row) for row in history) + "\n", encoding="utf-8")
        snapshot = root / "memory.db"
        with closing(sqlite3.connect(args.memory.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(snapshot)) as copy:
                source.backup(copy)

        results = {}
        for enabled in (False, True):
            state = root / ("on" if enabled else "off")
            activity = state / "memory-hook"
            activity.mkdir(parents=True)
            (activity / f"{session}.json").write_text(json.dumps({"shown": sorted(shown)}), encoding="utf-8")
            (state / "memory.json").write_text(json.dumps({
                "db": str(snapshot), "follow_up_recall": enabled, "resident": False,
                "idle_handoff_minutes": 0, "skills": False,
            }), encoding="utf-8")
            event = {
                "session_id": session, "cwd": str(cwd), "prompt": prompt,
                "hook_event_name": "UserPromptSubmit", "transcript_path": str(transcript),
            }
            reply = subprocess.run(
                [exe, "hook"], input=json.dumps(event), capture_output=True, encoding="utf-8",
                cwd=cwd, env=dict(os.environ, FOOTNOTE_STATE_DIR=str(state)), timeout=20,
            )
            if reply.returncode or (activity / "hook.log").exists():
                raise ValueError("the hook failed during the replay")
            output = json.loads(reply.stdout) if reply.stdout.strip() else {}
            rendered = output.get("hookSpecificOutput", {}).get("additionalContext", "")
            logged = list(rows(activity / "activity.jsonl"))
            recalls = [row for row in logged if row["event"] == "recall"]
            delivered = recalls[0]["ids"] if recalls else []
            visible = {
                id_: line for id_ in delivered if id_ in required
                for line in rendered.splitlines() if line.startswith(f"- [id {id_} ·")
            }
            results["follow_up" if enabled else "direct"] = {
                "memories_delivered": len(delivered),
                "required_ids_rendered": list(visible),
                "required_ids_rendered_as_excerpt": [id_ for id_, line in visible.items() if line.endswith("…")],
                "hook_context_bytes": len(rendered.encode()),
                "used_previous_reply": any(row.get("reason") == "previous_reply" for row in recalls),
            }
    return {
        "turn_start_utc": args.start.astimezone(timezone.utc).isoformat(),
        "footnote_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
        "settings": {"resident": False, "recall_limit": 4},
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("footnote", "transcript", "activity", "memory", "cwd"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--start", required=True, type=instant)
    parser.add_argument("--required", type=int, nargs="+", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), indent=2))
    except (ValueError, OSError, sqlite3.Error, subprocess.TimeoutExpired):
        parser.exit(1, "Could not replay the recorded hook input. Check the local paths and timestamp.\n")


if __name__ == "__main__":
    main()
