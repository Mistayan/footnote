#!/usr/bin/env python3
"""Prove that a Codex benchmark arm receives Memory and uses Lean."""

import argparse
import asyncio
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


async def session(codex, footnote, model, sandbox, repo, env, word, memory_id):
    home = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
    config = home / "config.toml"
    user = tomllib.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
    options = ["-c", f"shell_environment_policy.set.FOOTNOTE_STATE_DIR={json.dumps(env['FOOTNOTE_STATE_DIR'])}"]
    for name in user.get("mcp_servers", {}):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Cannot isolate MCP servers with a nonstandard configuration key")
        options += ["-c", f"mcp_servers.{name}.enabled=false"]

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
        await send("turn/start", {
            "threadId": thread_id,
            "input": [{"type": "text", "text": PROMPT, "text_elements": []}],
        }, 4)
        matched = set()
        commands = []
        used = False
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
        shown = any(
            event.get("event") == "pack" and event.get("session") == thread_id
            and memory_id in event.get("ids", [])
            for event in activity
        )
        lean = json_lines(state / "usage" / "lean.jsonl")
        shell_runs = [row for row in lean if row.get("tool") == "run" and row.get("family") == "git"]
        used_lean = len(shell_runs) == 1 and shell_runs[0].get("exit_code") == 0
        expected_command = len(commands) == 1 and all(commands[0].values())
        return {
            "accepted": completed and not rerouted and matched == REQUIRED and shown and used
            and used_lean and expected_command,
            "model": started["model"], "trust": trust, "model_turn_started": True,
            "sandbox": started.get("sandbox", {}).get("type"),
            "turn_completed": completed, "model_rerouted": rerouted,
            "hooks_completed": sorted(matched), "fixture_memory_shown": shown,
            "fixture_memory_used": used, "successful_lean_git": used_lean,
            "commands": commands, "lean_git_runs": len(shell_runs), "tokens": usage,
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
        stored = subprocess.run([footnote, "--db", state / "memory.db", "remember"],
            env=env, input=json.dumps([{
                "kind": "fact", "scope": repo.name, "observed_at": date.today().isoformat(),
                "text": f"The Footnote activation word is {word}.",
            }]), text=True, capture_output=True, check=True,
        )
        memory_id = json.loads(stored.stdout)["stored"][0]["id"]
        try:
            result = asyncio.run(asyncio.wait_for(
                session(args.codex, footnote, args.model, args.sandbox, repo, env, word, memory_id), 120
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
