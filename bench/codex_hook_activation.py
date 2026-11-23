#!/usr/bin/env python3
"""Prove that a Codex benchmark arm receives Memory and uses Lean."""

import argparse
import asyncio
from collections import Counter
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
from uuid import uuid4


REQUIRED = {"sessionStart", "userPromptSubmit", "preToolUse", "stop"}
READY = {"trusted", "managed"}
PROMPT = (
    "Run exactly one shell command: git log -3 --oneline. "
    "Then reply with the activation word from the supplied Footnote memory. "
    "If no activation word was supplied, reply MISSING. Do not read files or call MCP."
)
FIXTURE_SERVER = "footnote-fixture"
BASELINE_PROMPT = (
    "Run exactly one shell command: git log -3 --oneline. "
    "Call the footnote-fixture MCP server's footnote_recall with query 'wafer serial', "
    "project 'activation-fixture', mode 'lexical', limit 1, and verbose true. "
    "Then call footnote_get on that server with id [{hidden}, {visible}] and verbose true. "
    "Reply with only the activation word from the supplied Footnote memory and the wafer serial "
    "from the retrieval. Do not read files or call other tools."
)


def normalized(path):
    return os.path.normcase(os.path.normpath(path.replace("/", os.sep)))


def footnote_hooks(rows, footnote):
    selected = {}
    for row in rows:
        event = row.get("eventName")
        if event not in REQUIRED or not row.get("enabled"):
            continue
        suffix = " hook lean" if event == "preToolUse" else " hook"
        command = row.get("command", "").strip()
        if (
            command.endswith(suffix)
            and normalized(command[:-len(suffix)].strip("\"'")) == normalized(str(footnote))
        ):
            if event in selected:
                raise ValueError(f"Multiple Footnote hooks for {event}")
            selected[event] = row
    return selected


def json_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def mcp_ids(item):
    result = item.get("result")
    if item["status"] != "completed" or not result:
        return []
    for part in result["content"]:
        if part.get("type") == "text":
            payload = json.loads(part["text"])
            hits = payload if isinstance(payload, list) else payload.get("results", [payload])
            return [hit["id"] for hit in hits if "text" in hit and isinstance(hit.get("id"), int)]
    return []


def baseline_counts(hook_rows, mcp_calls, used_ids):
    by_source = {
        "hook_pack": Counter(id_ for row in hook_rows if row["event"] == "pack" for id_ in row["ids"]),
        "hook_recall": Counter(id_ for row in hook_rows if row["event"] == "recall" for id_ in row["ids"]),
        "mcp_recall": Counter(id_ for tool, ids in mcp_calls if tool == "footnote_recall" for id_ in ids),
        "mcp_get": Counter(id_ for tool, ids in mcp_calls if tool == "footnote_get" for id_ in ids),
    }
    shown = sum(by_source.values(), Counter())
    return {
        "sources": {
            name: {
                "items_shown": sum(ids.values()), "distinct_shown": len(ids),
                "distinct_used_in_answer": len(ids.keys() & used_ids),
            }
            for name, ids in by_source.items()
        },
        "repeated_items": sum(shown.values()) - len(shown),
        "memories": {id_: {"shown": n, "used_in_answer": id_ in used_ids} for id_, n in sorted(shown.items())},
    }


async def session(codex, footnote, model, sandbox, repo, env, word, memory_id, baseline=None):
    home = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
    config = home / "config.toml"
    user = tomllib.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
    options = ["-c", f"shell_environment_policy.set.FOOTNOTE_STATE_DIR={json.dumps(env['FOOTNOTE_STATE_DIR'])}"]
    for name in user.get("mcp_servers", {}):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Cannot isolate MCP servers with a nonstandard configuration key")
        options += ["-c", f"mcp_servers.{name}.enabled=false"]
    if baseline:
        state = Path(env["FOOTNOTE_STATE_DIR"])
        command = json.dumps(str(footnote))
        args = json.dumps(["--db", str(state / "memory.db"), "serve", "--mcp"])
        state_value = json.dumps(str(state))
        options += ["-c", (
            f"mcp_servers.{FIXTURE_SERVER}={{command={command},args={args},"
            f"env={{FOOTNOTE_STATE_DIR={state_value}}}}}"
        )]

    app = await asyncio.create_subprocess_exec(
        codex, "app-server", "--disable", "plugins", "--disable", "memories", *options,
        cwd=repo, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=2**20,
    )

    async def receive():
        line = await app.stdout.readline()
        if not line:
            raise ValueError("Codex app server exited")
        return json.loads(line)

    buffered = []

    async def send(method, params, request_id=None):
        row = {"method": method, "params": params}
        if request_id is not None:
            row["id"] = request_id
        app.stdin.write((json.dumps(row) + "\n").encode())
        await app.stdin.drain()
        if request_id is not None:
            while (reply := await receive()).get("id") != request_id:
                buffered.append(reply)
            if "error" in reply:
                raise ValueError(f"Codex rejected {method} ({reply['error']['code']})")
            return reply["result"]

    try:
        await send("initialize", {
            "clientInfo": {"name": "footnote-hook-activation", "version": "1"},
            "capabilities": {"experimentalApi": True},
        }, 1)
        await send("initialized", {})
        listed = await send("hooks/list", {"cwds": [str(repo)]}, 2)
        hooks = footnote_hooks(listed["data"][0]["hooks"], footnote)
        trust = {event: hooks.get(event, {}).get("trustStatus", "missing") for event in sorted(REQUIRED)}
        if any(status not in READY for status in trust.values()):
            return {"accepted": False, "reason": "hook trust", "trust": trust, "model_turn_started": False}

        started = await send("thread/start", {
            "cwd": str(repo), "model": model, "ephemeral": True,
            "sandbox": sandbox, "approvalPolicy": "never",
        }, 3)
        if started["model"] != model:
            return {"accepted": False, "reason": "unexpected model", "model": started["model"]}

        thread_id = started["thread"]["id"]
        prompt = BASELINE_PROMPT.format(hidden=baseline["id"], visible=memory_id) if baseline else PROMPT
        await send("turn/start", {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt, "text_elements": []}],
        }, 4)
        matched = set()
        commands = []
        used = False
        hidden_used = False
        mcp_calls = []
        usage = None
        rerouted = False
        while True:
            row = buffered.pop(0) if buffered else await receive()
            method = row.get("method")
            params = row.get("params", {})
            if not isinstance(params, dict) or params.get("threadId") != thread_id:
                continue
            if method == "hook/completed":
                run = params["run"]
                event = run["eventName"]
                hook = hooks.get(event, {})
                if (run["status"] == "completed" and run["displayOrder"] == hook.get("displayOrder")
                        and normalized(run["sourcePath"]) == normalized(hook["sourcePath"])):
                    matched.add(event)
            elif method == "item/completed":
                item = params["item"]
                if item["type"] == "agentMessage":
                    used |= word in item.get("text", "")
                    if baseline:
                        hidden_used |= baseline["word"] in item.get("text", "")
                elif item["type"] == "mcpToolCall":
                    if not baseline or item.get("server") != FIXTURE_SERVER:
                        raise ValueError("Unexpected MCP server in fixture")
                    mcp_calls.append((item["tool"], mcp_ids(item)))
                elif item["type"] == "commandExecution":
                    command = item.get("command", "").lower()
                    commands.append({
                        "success": item.get("exitCode") == 0,
                        "footnote_run": bool(re.search(r"footnote(?:\.exe)?[\"']?\s+run\b", command)),
                        "git_log": "git log -3 --oneline" in command,
                    })
            elif method == "thread/tokenUsage/updated":
                usage = params["tokenUsage"]["total"]
            elif method == "model/rerouted":
                rerouted = True
            elif method == "turn/completed":
                completed = params["turn"]["status"] == "completed"
                break

        state = Path(env["FOOTNOTE_STATE_DIR"])
        activity = json_lines(state / "memory-hook" / "activity.jsonl")
        hook_rows = [event for event in activity if event.get("session") == thread_id]
        shown = any(
            event.get("event") == "pack" and memory_id in event.get("ids", [])
            for event in hook_rows
        )
        lean = json_lines(state / "usage" / "lean.jsonl")
        shell_runs = [row for row in lean if row.get("tool") == "run" and row.get("family") == "git"]
        used_lean = len(shell_runs) == 1 and shell_runs[0].get("exit_code") == 0
        expected_command = len(commands) == 1 and all(commands[0].values())
        metrics = {}
        if baseline:
            hidden = baseline["id"]
            mcp_verified = mcp_calls == [
                ("footnote_recall", [hidden]), ("footnote_get", [hidden, memory_id])
            ]
            missed = all(hidden not in event.get("ids", []) for event in hook_rows)
            used_ids = {id_ for id_, ok in [(memory_id, used), (hidden, hidden_used)] if ok}
            metrics["baseline"] = {
                **baseline_counts(hook_rows, mcp_calls, used_ids),
                "required_items_missed_by_hooks": int(missed),
                "mcp_calls": [{"tool": tool, "ids": ids} for tool, ids in mcp_calls],
                "tool_round_trips": len(commands) + len(mcp_calls),
                "cached_input_tokens": usage["cachedInputTokens"] if usage else None,
            }
            expected_command = expected_command and mcp_verified and hidden_used and usage is not None
        return {
            "accepted": completed and not rerouted and matched == REQUIRED and shown and used
            and used_lean and expected_command,
            "model": started["model"], "trust": trust, "model_turn_started": True,
            "sandbox": started.get("sandbox", {}).get("type"),
            "turn_completed": completed, "model_rerouted": rerouted,
            "hooks_completed": sorted(matched), "fixture_memory_shown": shown,
            "fixture_memory_used": used, "successful_lean_git": used_lean,
            "commands": commands, "lean_git_runs": len(shell_runs), "tokens": usage, **metrics,
        }
    finally:
        if app.returncode is None:
            app.terminate()
            await app.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--footnote", required=True, type=Path)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--model", default="gpt-6.2-sol")
    parser.add_argument("--baseline", action="store_true", help="Measure hook and MCP results in one Codex turn.")
    parser.add_argument("--sandbox", choices=["read-only", "workspace-write", "danger-full-access"],
                        help="Codex sandbox for the probe. Defaults to the loaded Codex policy.")
    args = parser.parse_args()
    footnote = args.footnote.resolve(strict=True)
    codex_version = subprocess.check_output([args.codex, "--version"], text=True).strip()
    footnote_version = subprocess.check_output([footnote, "--version"], text=True).strip()
    with tempfile.TemporaryDirectory(prefix="footnote-hook-") as root:
        repo = Path(root) / "activation-fixture"
        repo.mkdir()
        state = repo / ".footnote-test-state"
        state.mkdir()
        env = dict(os.environ, FOOTNOTE_STATE_DIR=str(state))
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
        subprocess.run([
            "git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", f"core.hooksPath={Path(root) / 'empty-hooks'}",
            "commit", "-qm", "Footnote activation fixture", "--allow-empty", "--no-gpg-sign",
        ], cwd=repo, check=True, capture_output=True)
        word = f"FOOTNOTE-{uuid4().hex}"
        date_str = date.today().isoformat()
        memories = [{
            "kind": "fact", "scope": repo.name, "observed_at": date_str,
            "text": f"The Footnote activation word is {word}.",
        }]
        hidden_word = f"WAFER-{uuid4().hex}"
        if args.baseline:
            memories = [{
                "kind": "fact", "scope": repo.name, "observed_at": date_str,
                "text": f"Build wafer serial {hidden_word}. " + "Archive padding. " * 85,
            }, *memories, {
                "kind": "preference", "scope": "global", "observed_at": date_str,
                "text": "South wing inventory labels are purple. " + "Ledger padding. " * 100,
            }]
        stored = subprocess.run([footnote, "--db", state / "memory.db", "remember"],
            env=env, input=json.dumps(memories), text=True, capture_output=True, check=True,
        )
        ids = [row["id"] for row in json.loads(stored.stdout)["stored"]]
        memory_id = ids[int(args.baseline)]
        baseline = {"id": ids[0], "word": hidden_word} if args.baseline else None
        try:
            result = asyncio.run(asyncio.wait_for(
                session(args.codex, footnote, args.model, args.sandbox, repo, env, word, memory_id, baseline), 120
            ))
        except TimeoutError:
            result = {"accepted": False, "reason": "Codex probe timed out"}
        except ValueError as e:
            result = {"accepted": False, "reason": str(e)}
    print(json.dumps({
        "protocol": 1, "codex": codex_version, "footnote": footnote_version,
        "footnote_sha256": hashlib.sha256(footnote.read_bytes()).hexdigest(),
        "requested_model": args.model, **result,
    }, indent=2))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
