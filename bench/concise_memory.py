#!/usr/bin/env python3
"""Reproduce the synthetic #605 recall replay and opt-in live Codex pilot."""

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from uuid import uuid4

from codex_hook_activation import READY, REQUIRED, app_server, footnote_hooks, json_lines, mcp_delivery, normalized
from concise_memory_fixtures import CASES, DATE, NEAR_SCOPE

MODEL = "gpt-6.2-sol"
ARMS = ("current", "excerpt", "write_excerpt")
SERVER = "footnote-fixture"
WORD = "SYNTHETIC-LANTERN-95"
LINE = re.compile(r"^(- \[id (\d+) .*?\] )(.*)$")
COMPACT_HIT = re.compile(r"^\[(\d+) · [^\n]*?\] \S", re.M)
DECISION = re.compile(r"\b(must|may|never|only|unless|eligible|do not|required|prohibited)\b", re.I)
SAVE = (
    "Write one self-contained sentence per note that makes sense alone in a year, with absolute dates. "
    "Name the subject explicitly. Include the conditions or exceptions needed to interpret the fact. "
    "Keep exceptions explicit. Prefer a short self-contained fact over copied context or keyword lists. "
    "Keep the exact operational identifiers, archive references, deadlines, and dates stated in the notes."
)
GIT = "Run exactly one shell command, git log -3 --oneline. Set activation to the code in the hook memory."


def command(argv, env=None, cwd=None, payload=None):
    result = subprocess.run(argv, env=env, cwd=cwd, input=payload, capture_output=True,
                            encoding="utf-8", timeout=25)
    if result.returncode:
        raise ValueError(f"Fixture command failed (exit {result.returncode})")
    return result.stdout


def state_env(state, profile=None):
    env = dict(os.environ, FOOTNOTE_STATE_DIR=str(state), FOOTNOTE_POLICY_FILE=str(state / "policy.json"))
    for key in ("FOOTNOTE_CONTEXT_SESSION_FILE", "FOOTNOTE_HOOK_OFF", "FOOTNOTE_SUBAGENT"):
        env.pop(key, None)
    if profile:
        env["CODEX_HOME"] = str(profile)
    return env


@contextmanager
def fixture(root, scope, db=None, profile=None):
    with tempfile.TemporaryDirectory(dir=root) as directory:
        root = Path(directory)
        repo, state = root / scope, root / "state"
        repo.mkdir()
        state.mkdir()
        (state / "policy.json").write_text("{}", encoding="utf-8")
        (state / "memory.json").write_text(json.dumps({
            "db": str(db or state / "memory.db"), "resident": False, "follow_up_recall": False,
            "clean_days": 0, "handoff_tokens": 0, "idle_handoff_minutes": 0,
        }), encoding="utf-8")
        yield repo, state, state_env(state, profile)


def cli(footnote, state, db, *args, payload=None):
    return json.loads(command([footnote, "--db", db, *args], state_env(state), payload=payload))


def store(footnote, state, db, notes):
    batch = [{"kind": "fact", "scope": scope, "observed_at": DATE, "text": body} for scope, body in notes]
    ids = [row["id"] for row in cli(footnote, state, db, "remember", payload=json.dumps(batch))["stored"]]
    if len(ids) != len(notes) or len(set(ids)) != len(ids):
        raise ValueError("Fixture memories were not stored as distinct records")
    records = dict(zip(ids, (body for _, body in notes)))
    verify_originals(footnote, state, db, records)
    return records


def verify_originals(footnote, state, db, records):
    if any(cli(footnote, state, db, "get", str(id_))["text"] != body for id_, body in records.items()):
        raise ValueError("Full-text lookup differs from the stored fixture")


def recall(footnote, repo, state, env, query):
    # Replay a prompt event with a new delivery history, as in claude_follow_up_replay.py.
    event = {"session_id": uuid4().hex, "cwd": str(repo), "prompt": query, "hook_event_name": "UserPromptSubmit"}
    out = command([footnote, "hook"], env, repo, json.dumps(event))
    activity = json_lines(state / "memory-hook" / "activity.jsonl")
    if (state / "memory-hook" / "hook.log").exists() or not activity:
        raise ValueError("Prompt hook replay did not produce a clean trace")
    body = json.loads(out).get("hookSpecificOutput", {}).get("additionalContext", "") if out.strip() else ""
    traced = [id_ for row in activity if row["event"] == "recall" for id_ in row["ids"]]
    rendered = [int(m[2]) for line in body.splitlines() if (m := LINE.fullmatch(line))]
    if traced != rendered:
        raise ValueError("Rendered memories disagree with the hook's delivery trace")
    return body, rendered


def excerpt(body, records):
    if not body:
        return body
    header, *lines = body.splitlines()
    rendered, truncated = [], []
    for line in lines:
        match = LINE.fullmatch(line)
        if not match:
            continue
        prefix, id_, visible = match.groups()
        original = records[int(id_)]
        sentences = re.split(r"(?<=[.!?])\s+", original)
        choice = " ".join(s for s in sentences if DECISION.search(s))
        if choice and choice != original and len(choice) <= 200 and (visible.endswith("…") or len(choice) < len(visible)):
            visible = choice + "…"
        if visible.endswith("…"):
            truncated.append(id_)
        rendered.append(prefix + visible)
    if truncated:
        rendered.append(f"\n(… marks a cut text: footnote_get id=[{','.join(truncated)}] gives all of it)")
    return "\n".join([header, *rendered])


def measure_context(case, body, hits, other_hits, target, near):
    visible = next((m[3] for line in body.splitlines() if (m := LINE.fullmatch(line)) and int(m[2]) == target), "")
    return {
        "scope_verified": target in hits and near not in hits and near in other_hits and target not in other_hits,
        "hit_ids": hits, "other_project_hit_ids": other_hits, "source_id": target,
        "visible_exact_spans": {k: term.casefold() in visible.casefold() for k, term in case["evidence"].items()},
        "context_chars": len(body), "context_bytes": len(body.encode()),
    }


def options_for(state, env, footnote, db):
    options = ['model_reasoning_effort="medium"', 'web_search="disabled"', "project_doc_max_bytes=0"]
    options += [f"shell_environment_policy.set.{key}={json.dumps(env[key])}"
                for key in ("FOOTNOTE_STATE_DIR", "FOOTNOTE_POLICY_FILE")]
    if db:
        args = json.dumps(["--db", str(db), "serve", "--mcp"])
        options.append(f"mcp_servers.{SERVER}={{command={json.dumps(str(footnote))},args={args},"
                       f"enabled_tools=[\"footnote_get\"],env={{FOOTNOTE_STATE_DIR={json.dumps(str(state))},"
                       f"FOOTNOTE_POLICY_FILE={json.dumps(env['FOOTNOTE_POLICY_FILE'])}}}}}")
    return [arg for value in options for arg in ("-c", value)]


def parse_object(text):
    try:
        obj = json.loads(text or "")
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, RecursionError):
        return {}


def has_usage(turn):
    values = turn["usage"] or {}
    return all(type(values.get(key)) is int for key in ("inputTokens", "cachedInputTokens", "outputTokens"))


async def run_thread(args, root, prompts, db=None):
    trace = {"trust": {}, "turns": [], "memory_pack_verified": False, "lean_git_verified": False}
    answers = []
    with fixture(root, "pilot", profile=args.live_codex_home) as (repo, state, env):
        command(["git", "init", "-q"], cwd=repo, env=env)
        command(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c",
                 f"core.hooksPath={state / 'empty-hooks'}", "commit", "-qm", "Synthetic fixture", "--allow-empty",
                 "--no-gpg-sign"], cwd=repo, env=env)
        activation = next(iter(store(args.footnote, state, state / "memory.db", [("pilot", f"Activation is {WORD}.")])))
        options = options_for(state, env, args.footnote, db)
        thread = None
        try:
            async with asyncio.timeout(115 * len(prompts)):
                async with app_server(args.codex, repo, env, options, "footnote-concise-memory") as (send, receive):
                    listing = await send("hooks/list", {"cwds": [str(repo)]}, 2)
                    rows = listing["data"][0]["hooks"]
                    hooks = footnote_hooks(rows, args.footnote)
                    trace["trust"] = {event: hooks.get(event, {}).get("trustStatus", "missing") for event in sorted(REQUIRED)}
                    active = [row for row in rows if row.get("enabled") and row.get("trustStatus") in READY]
                    if len(active) != len(REQUIRED) or any(s not in READY for s in trace["trust"].values()):
                        raise ValueError("Hook trust did not match the fixture profile")
                    started = await send("thread/start", {"cwd": str(repo), "model": MODEL, "ephemeral": True,
                                         "sandbox": "danger-full-access", "approvalPolicy": "never"}, 3)
                    trace["model"] = started["model"]
                    if started["model"] != MODEL:
                        raise ValueError("Unexpected model")
                    thread = started["thread"]["id"]
                    for index, prompt in enumerate(prompts):
                        turn = {"hooks": [], "lookups": [], "shell_calls": 0, "other_tools": 0, "usage": None}
                        trace["turns"].append(turn)
                        answers.append({})
                        await send("turn/start", {"threadId": thread, "input": [
                            {"type": "text", "text": prompt, "text_elements": []}]}, index + 4)
                        await collect_turn(receive, thread, hooks, db, turn, answers)
                        if turn["completed"] is False:
                            break
        except (TimeoutError, OSError, ValueError, KeyError) as error:
            trace["error"] = type(error).__name__ if not isinstance(error, ValueError) else str(error)
        activity = json_lines(state / "memory-hook" / "activity.jsonl")
        trace["memory_pack_verified"] = any(
            row.get("session") == thread and row["event"] == "pack" and row["ids"] == [activation] for row in activity
        )
        lean = json_lines(state / "usage" / "lean.jsonl")
        trace["lean_git_verified"] = sum(
            row.get("tool") == "run" and row.get("family") == "git" and row.get("exit_code") == 0 for row in lean
        ) == 1
    trace["verified"] = (
        "error" not in trace and trace["memory_pack_verified"] and trace["lean_git_verified"]
        and len(trace["turns"]) == len(prompts) and set(trace["turns"][0]["hooks"]) == REQUIRED
        and trace["turns"][0]["shell_calls"] == 1 and answers[0].get("activation") == WORD
        and all(turn.get("completed") and has_usage(turn) and not turn["other_tools"]
                and not turn.get("rerouted") for turn in trace["turns"])
        and all({"userPromptSubmit", "stop"} <= set(turn["hooks"]) and turn["shell_calls"] == 0
                for turn in trace["turns"][1:])
    )
    return trace, answers


async def collect_turn(receive, thread, hooks, db, turn, answers):
    while True:
        row = await receive()
        method, params = row.get("method"), row.get("params", {})
        if not isinstance(params, dict) or params.get("threadId") != thread:
            continue
        if method == "hook/completed":
            run = params["run"]
            hook = hooks.get(run["eventName"])
            if (hook and run["status"] == "completed" and run["displayOrder"] == hook["displayOrder"]
                    and normalized(run["sourcePath"]) == normalized(hook["sourcePath"])):
                turn["hooks"].append(run["eventName"])
        elif method == "item/completed":
            item = params["item"]
            kind = item["type"]
            if kind == "agentMessage":
                answers[-1] = parse_object(item.get("text"))
            elif kind == "commandExecution":
                turn["shell_calls"] += 1
            elif db and kind == "mcpToolCall" and item.get("server") == SERVER and item.get("tool") == "footnote_get":
                turn["lookups"].append(lookup_result(item))
            elif kind in {"mcpToolCall", "dynamicToolCall", "fileChange", "webSearch"}:
                turn["other_tools"] += 1
        elif method == "thread/tokenUsage/updated":
            turn["usage"] = params["tokenUsage"]["total"]
        elif method == "model/rerouted":
            turn["rerouted"] = True
        elif method == "turn/completed":
            turn["completed"] = params["turn"]["status"] == "completed"
            return


def lookup_result(item):
    argument = item.get("arguments")
    ids = argument.get("id") if isinstance(argument, dict) else None
    ids = ids if isinstance(ids, list) else [ids]
    requested = [i for i in ids if type(i) is int]
    returned = []
    result = item.get("result") or {}
    if item.get("status") == "completed" and not result.get("isError"):
        try:
            returned = mcp_delivery(item)["ids"]
        except json.JSONDecodeError:
            returned = [int(id_) for part in result.get("content", []) if part.get("type") == "text"
                        for id_ in COMPACT_HIT.findall(part.get("text", ""))]
        except (ValueError, KeyError, TypeError):
            pass
    return {"ids": requested, "returned_ids": returned,
            "completed": bool(requested) and set(requested) == set(returned)}


def payload_notes():
    return [(case["scope"], case["note"]) for case in CASES] + [(NEAR_SCOPE, case["near"]) for case in CASES]


async def write_live(args, root, concise):
    instruction = SAVE + (" Aim for at most 34 words per sentence. Strip incidental context and rationale." if concise else "")
    notes = [f"{i}. {scope}: {text}" for i, (scope, text) in enumerate(payload_notes(), 1)]
    prompt = (f"{instruction}\n{GIT}\nUse no other tools. Reply with raw JSON whose keys are activation and memories. "
              "The memories value is an array of strings in note order, one per note.\n\n" + "\n".join(notes))
    trace, answers = await run_thread(args, root, [prompt])
    texts = answers[0].get("memories") if answers else None
    trace["valid_writes"] = (isinstance(texts, list) and len(texts) == len(notes)
                             and all(isinstance(s, str) and bool(s.strip()) and "\n" not in s for s in texts))
    if not trace["valid_writes"]:
        return trace, None
    trace["stored_chars"] = sum(map(len, texts))
    return trace, [(scope, body.strip()) for (scope, _), body in zip(payload_notes(), texts)]


async def task_live(args, root, case, context, body, db):
    schema = ", ".join([*case["initial"], "memory_id", "activation"])
    choices = "allow or hold" if case["scope"] in {"glasshouse", "greywater"} else "allow or deny"
    rule = (f"Use this project's decision. When asked for an action, use one of {choices}. "
            "A memory ID is the integer identifying the source. Return scope as a lowercase project slug. "
            f"If essential source text is missing, use only {SERVER}'s footnote_get with that ID. "
            "Reply with raw JSON and use null for unknowns.")
    prompt = f"{case['task']}\n{rule}\n{GIT}\nKeys: {schema}.\n\nRecall replay data:\n{body}"
    follow_up = f"{case['follow_up']}\n{rule}\nDo not run shell commands. Keys: {', '.join(case['later'])}."
    trace, answers = await run_thread(args, root, [prompt, follow_up], db)
    first, later = (answers + [{}, {}])[:2]
    grade = {"initial": {k: type(first.get(k)) is type(v) and first.get(k) == v
                         for k, v in {**case["initial"], "memory_id": context["source_id"]}.items()},
             "follow_up": {k: later.get(k) == v for k, v in case["later"].items()}}
    return {**context, "trace": trace, "grade": grade, "accepted": (
        trace["verified"] and context["scope_verified"] and all(value for step in grade.values() for value in step.values())
    )}


async def lookup_probe(args, root):
    case = CASES[0]
    with fixture(root, case["scope"]) as (repo, state, env):
        db = state / "memory.db"
        records = store(args.footnote, state, db, [(case["scope"], case["note"]), (NEAR_SCOPE, case["near"])])
        target, near = records
        body, hits = recall(args.footnote, repo, state, env, case["query"])
        with fixture(root, NEAR_SCOPE, db) as fixture_args:
            _, near_hits = recall(args.footnote, *fixture_args, case["query"])
        body = excerpt(body, records)
        context = measure_context(case, body, hits, near_hits, target, near)
        result = await task_live(args, root, case, context, body, db)
    result["full_text_lookup_verified"] = (
        not context["visible_exact_spans"]["archive_ref"] and result["accepted"] and any(
            call["completed"] and target in call["returned_ids"]
            for turn in result["trace"]["turns"] for call in turn["lookups"]
        )
    )
    return result


def usage(trace):
    reported = [turn["usage"] for turn in trace["turns"] if has_usage(turn)]
    if not reported:
        return None
    last = reported[-1]
    return {"cached_input_tokens": last["cachedInputTokens"],
            "uncached_input_tokens": last["inputTokens"] - last["cachedInputTokens"], "output_tokens": last["outputTokens"]}


def summarize(tasks, write):
    attempted = [row for row in tasks if "trace" in row]
    traces = [row["trace"] for row in attempted]
    complete = (len(tasks) == len(traces) == len(CASES) and usage(write) is not None
                and all(len(trace["turns"]) == 2 and all(t.get("completed") and has_usage(t) for t in trace["turns"])
                        for trace in traces))
    task_usage = [u for trace in traces if (u := usage(trace)) is not None]
    write_usage = usage(write)
    lookups = [call for trace in traces for turn in trace["turns"] for call in turn["lookups"]]
    repeated = 0
    for trace in traces:
        seen = set()
        for call in (call for turn in trace["turns"] for call in turn["lookups"]):
            ids = set(call["ids"])
            repeated += bool(ids & seen)
            seen.update(ids)
    counted = [*task_usage, *([write_usage] if write_usage else [])]
    totals = {k: sum(u[k] for u in counted) if counted else None for k in (
        "cached_input_tokens", "uncached_input_tokens", "output_tokens")}
    accepted = sum(row["accepted"] for row in attempted)
    return {"accepted_tasks": accepted, "scheduled_tasks": len(CASES), "complete_usage": complete,
            "comparison_valid": complete and write["verified"] and write["valid_writes"]
            and all(trace["verified"] for trace in traces),
            "critical_fields_correct": sum(v for row in attempted for step in row["grade"].values() for v in step.values()),
            "critical_fields_attempted": sum(len(step) for row in attempted for step in row["grade"].values()),
            "observed_cached_input_tokens": totals["cached_input_tokens"],
            "observed_uncached_input_tokens": totals["uncached_input_tokens"],
            "observed_write_output_tokens": write_usage["output_tokens"] if write_usage else None,
            "observed_task_output_tokens": sum(u["output_tokens"] for u in task_usage) if task_usage else None,
            "observed_full_text_calls": len(lookups), "observed_repeated_lookup_calls": repeated,
            "observed_failed_lookup_calls": sum(not call["completed"] for call in lookups),
            "scheduled_retries": 0, "provider_internal_retries": None,
            "tokens_per_accepted_task": sum(totals.values()) / accepted if complete and accepted else None}


async def run(args, root):
    live = args.live_codex_home is not None
    result = {"writers": {}, "tasks": {arm: [] for arm in ARMS}, "summary": {}, "eligible": []}
    write_runs = (await asyncio.gather(write_live(args, root, False), write_live(args, root, True))
                  if live else [(None, payload_notes()), (None, [(s, excerpt_note(n)) for s, n in payload_notes()])])
    stores = []
    for label, (trace, notes) in zip(("current", "concise"), write_runs):
        if live:
            result["writers"][label] = trace
        state = root / label
        state.mkdir()
        (state / "policy.json").write_text("{}", encoding="utf-8")
        db = state / "memory.db"
        stores.append((state, db, store(args.footnote, state, db, notes) if notes else {}))

    for index, case in enumerate(CASES):
        pending = {}
        for arm in ARMS[index % 3:] + ARMS[:index % 3]:
            _, db, records = stores[arm == "write_excerpt"]
            if not records:
                result["tasks"][arm].append({"case": case["scope"], "blocked": "writer output unavailable"})
                continue
            ids = list(records)
            with fixture(root, case["scope"], db) as fixture_args:
                body, hits = recall(args.footnote, *fixture_args, case["query"])
            with fixture(root, NEAR_SCOPE, db) as fixture_args:
                _, near_hits = recall(args.footnote, *fixture_args, case["query"])
            if arm != "current":
                body = excerpt(body, records)
            context = {"case": case["scope"], **measure_context(
                case, body, hits, near_hits, ids[index], ids[index + len(CASES)])}
            if live:
                pending[arm] = asyncio.create_task(task_live(args, root, case, context, body, db))
            else:
                result["tasks"][arm].append(context)
        for arm, task in pending.items():
            result["tasks"][arm].append(await task)
        print(f"Scored {case['scope']}", file=sys.stderr, flush=True)
    for state, db, records in stores:
        verify_originals(args.footnote, state, db, records)
    result["full_text_verified"] = {name: bool(records) for name, (_, _, records) in zip(("current", "concise"), stores)}
    if live:
        for arm, tasks in result["tasks"].items():
            result["summary"][arm] = summarize(tasks, result["writers"]["concise" if arm == "write_excerpt" else "current"])
        current = result["summary"]["current"]
        baseline = current["tokens_per_accepted_task"]
        for arm in ARMS[1:]:
            summary = result["summary"][arm]
            cost = summary["tokens_per_accepted_task"]
            if (current["comparison_valid"] and summary["comparison_valid"] and cost is not None and baseline is not None
                    and summary["accepted_tasks"] == len(CASES) and cost < baseline):
                result["eligible"].append(arm)
        result["lookup_probe"] = await lookup_probe(args, root)
    return result


def excerpt_note(note):
    # Shortcut: model-free write surrogate for local renderer checks. Live writes come from Codex.
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", note) if DECISION.search(s) or s.startswith("Archive reference"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--footnote", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--live-codex-home", type=Path, help="Dedicated fixture-only Codex profile with trusted hooks")
    parser.add_argument("--lookup-probe-only", action="store_true", help="Run the separate live fallback probe only")
    args = parser.parse_args()
    args.footnote = args.footnote.resolve(strict=True)
    if args.output.exists():
        parser.error("Use a new output path. Receipts are immutable.")
    if args.lookup_probe_only and not args.live_codex_home:
        parser.error("--lookup-probe-only requires --live-codex-home")
    if args.live_codex_home:
        args.live_codex_home = args.live_codex_home.resolve(strict=True)
        if args.live_codex_home == Path.home() / ".codex":
            parser.error("Use a fixture profile, separate from the normal Codex profile.")
    here = Path(__file__).resolve().parent
    receipt = {"protocol": 2, "lookup_trace_revision": 2, "utc": datetime.now(timezone.utc).isoformat(),
               "footnote": command([args.footnote, "--version"]).strip(), "footnote_sha256": digest(args.footnote),
               "source_sha256": {name: digest(here / name) for name in (
                   "CONCISE-MEMORY-PROTOCOL-2026-11-23.md", "concise_memory.py", "concise_memory_fixtures.py",
                   "codex_hook_activation.py")},
               "mode": "live" if args.live_codex_home else "local"}
    if args.live_codex_home:
        receipt.update(codex=command([args.codex, "--version"]).strip(), requested_model=MODEL)
    with tempfile.TemporaryDirectory(prefix="footnote-concise-") as directory:
        root = Path(directory)
        if args.lookup_probe_only:
            receipt.update(mode="live_lookup_probe", lookup_probe=asyncio.run(lookup_probe(args, root)))
        else:
            receipt.update(asyncio.run(run(args, root)))
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
