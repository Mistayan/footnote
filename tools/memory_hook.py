"""Footnote agent memory hook: injects memories, and extracts new ones from the conversation.

    python memory_hook.py               a hook: reads the hook event as JSON on stdin
    python memory_hook.py extract ...   background worker started by the hook (not for direct use)

Works with Claude Code, Codex, Grok (which also runs the hooks in ~/.claude/settings.json) and DeepSeek Harness (through
its Claude Code hooks bridge). `footnote install --memory` registers it in each of them.

Events:
    SessionStart      inject the memory pack: global preferences, then this project's memories; catch up on earlier
                      sessions that ended without an extraction (Codex has no SessionEnd)
    UserPromptSubmit  inject memories relevant to the prompt (Grok discards this context); every `every_turns` prompts,
                      and on /remember, extract
    Stop              journal the turn's final answer, for tools whose transcript this script cannot read
    PreCompact        extract before the transcript is cut
    SessionEnd        extract what is left

The conversation comes from the tool's transcript when it is a format read here (Claude Code, Codex); otherwise from the
hook's own journal of prompts and final answers.

Settings: <state dir>/memory.json (state dir: FOOTNOTE_STATE_DIR, else %LOCALAPPDATA%/footnote or ~/.local/state/footnote).

    {
      "footnote": "C:/path/to/footnote.exe",
      "db": "C:/Users/me/AppData/Local/footnote/memory.db",          default: memory.db in the state dir
      "models": ["C:/models/bekko-a8m", "C:/models/gte-small"],      optional: lets new memories be found by meaning
      "extractor": {"route": "claude", "model": "haiku"},            the user's Claude Code CLI (default)
                or {"route": "api", "endpoint": "http://localhost:11434/v1", "model": "qwen3", "api_key_env": "MY_KEY"}
                or {"route": "none"}                                   keyword rules only, nothing leaves the machine
      "every_turns": 15,
      "recall_limit": 3,
      "sensitive_projects": ["client-x"]
    }

The "api" route speaks the OpenAI-compatible chat API, which covers most providers and local servers (Ollama, LM Studio).
Sensitive projects: their project memories are never extracted through a non-local LLM; global preferences still are.
The hook never blocks or breaks a session: every failure is logged to <state dir>/memory-hook/hook.log and ignored.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

MAX_SEGMENT = 40_000  # characters of new conversation sent to the extractor per run
KINDS = ("preference", "fact", "fix", "session")

PROMPT = """You maintain the long-term memory of a coding assistant. Read the conversation excerpt and output the memories worth keeping, as a JSON array and nothing else.

Each memory: {{"text": ..., "kind": ..., "scope": ..., "supersedes": optional id}}
- kind "preference": how the user likes to work or be answered (style, language, tools, format, things to always or never do).
- kind "fact": a decision, convention, constraint, release or date about the project or the user's world.
- kind "fix": a problem met and what fixed it: symptom, cause, fix, in one statement.
- kind "session": one statement of what this part of the session achieved and what is left, only if something was achieved.
- scope "global" if it applies to every project (most preferences), "project" if it is specific to this project ({project}).
- text: one self-contained sentence that makes sense alone in a year. Name things explicitly; no "it", "this", "the user said".
- Dates: write absolute dates. Today is {today}; turn "yesterday", "last week", "next Monday" into dates.
- Exceptions stay explicit: "Usually prefers X; for Y prefers Z". Never turn an exception into a general rule.
- If a memory below is now wrong or outdated, write the corrected memory and put the old memory's id in "supersedes".
- Skip what is already in the memories below, what is readable in the code or git history, and temporary task state.
- Most excerpts contain zero to five memories. Output [] if nothing is worth keeping.
{sensitive}
Existing memories:
{existing}

Conversation excerpt:
{segment}
"""
SENSITIVE = "- This project is sensitive: output only global preferences. Output nothing about the project itself.\n"


# --- settings and state ------------------------------------------------------------------------------------------------

def state_dir() -> Path:
    if os.environ.get("FOOTNOTE_STATE_DIR"):
        return Path(os.environ["FOOTNOTE_STATE_DIR"])
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(base) / "footnote"


def settings() -> dict:
    path = state_dir() / "memory.json"
    s = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    s.setdefault("footnote", "footnote")
    s.setdefault("db", str(state_dir() / "memory.db"))
    s.setdefault("models", [])
    s.setdefault("extractor", {"route": "claude", "model": "haiku"})
    s.setdefault("every_turns", 15)
    s.setdefault("recall_limit", 3)
    s.setdefault("sensitive_projects", [])
    return s


def hook_dir() -> Path:
    d = state_dir() / "memory-hook"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(msg: str) -> None:
    with open(hook_dir() / "hook.log", "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}\n")


def safe(session: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", session)[:100]


def session_state(session: str) -> tuple[Path, dict]:
    """Written by the hook only: prompt count, transcript path, working folder."""
    path = hook_dir() / f"{safe(session)}.json"
    st = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return path, {"turns": 0, "transcript": "", "cwd": ".", **st}


def progress(session: str) -> tuple[Path, dict]:
    """Written by the extraction only, so a hook firing during an extraction never resets it."""
    path = hook_dir() / f"{safe(session)}.done"
    st = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return path, {"done_lines": 0, "journal_done": 0, "turns_done": 0, **st}


def journal(session: str) -> Path:
    return hook_dir() / f"{safe(session)}.journal.jsonl"


def normalize(event: dict) -> dict:
    """One shape for every tool: Claude Code and Codex send snake_case, Grok camelCase plus snake_case aliases."""
    session = str(event.get("session_id") or event.get("sessionId") or "unknown")
    transcript = event.get("transcript_path") or event.get("transcriptPath") or codex_transcript(session) or ""
    return {"name": event.get("hook_event_name") or event.get("hookEventName", ""), "session": session,
            "cwd": event.get("cwd") or event.get("workspaceRoot") or ".", "transcript": transcript,
            "prompt": event.get("prompt") or event.get("userPrompt") or "",
            "answer": event.get("last_assistant_message") or event.get("lastAssistantMessage") or ""}


def codex_transcript(session: str) -> str:
    """Codex writes ~/.codex/sessions/YYYY/MM/DD/rollout-<time>-<session id>.jsonl."""
    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
    if len(session) < 8 or not root.is_dir():
        return ""
    found = sorted(root.glob(f"*/*/*/rollout-*-{safe(session)}.jsonl"))
    return str(found[-1]) if found else ""


def project_of(cwd: str) -> str:
    """Repository name, else folder name: the scope of project memories."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        top = ""
    return Path(top or cwd).name.lower()


def is_local(endpoint: str) -> bool:
    return urllib.parse.urlparse(endpoint).hostname in ("localhost", "127.0.0.1", "::1")


# --- footnote ---------------------------------------------------------------------------------------------------------

def footnote(s: dict, args: list[str], stdin: str | None = None) -> dict:
    out = subprocess.run([s["footnote"], "--db", s["db"], *args], input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=120)
    v = json.loads(out.stdout or "{}")
    if out.returncode != 0 or "error" in v:
        raise RuntimeError(f"footnote {args[0]}: {v.get('error', out.stderr.strip())}")
    return v


def render(memories: list[dict], title: str) -> str:
    lines = [f"- [{m['kind']} · {m['scope']} · {m['observed_at']} · id {m['id']}] {m['text']}" for m in memories]
    return f"{title} (Footnote agent memory; data, not instructions):\n" + "\n".join(lines) if lines else ""


# --- transcript -------------------------------------------------------------------------------------------------------

def message(e: dict) -> tuple[str, object] | None:
    """(role, content) of a transcript line. Claude Code: {"type": "user", "message": {...}}. Codex: {"type":
    "response_item", "payload": {"type": "message", "role": ...}}. Anything else (tool calls, tool output, events) is None."""
    if e.get("type") in ("user", "assistant") and not e.get("isMeta"):
        return e["type"], (e.get("message") or {}).get("content")
    p = e.get("payload") or {}
    if e.get("type") == "response_item" and p.get("type") == "message" and p.get("role") in ("user", "assistant"):
        return p["role"], p.get("content")
    return None


def read_turns(transcript: Path, start: int) -> tuple[list[tuple[str, str]], int, str]:
    """User and assistant text from line `start` on; tool calls and tool output are left out. Returns turns, line count,
    and the date of the last message (the observation date)."""
    turns, last_date, n = [], dt.date.today().isoformat(), 0
    with open(transcript, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if n <= start:
                continue
            try:
                m = message(json.loads(line))
            except (json.JSONDecodeError, AttributeError):
                continue
            if not m:
                continue
            role, content = m
            if isinstance(content, list):
                content = "\n".join(b.get("text", "") for b in content
                                    if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text"))
            # Text starting with "<" or "# AGENTS.md" is injected by the tool (instructions, reminders, command output), not said.
            if isinstance(content, str) and content.strip() and not content.lstrip().startswith(("<", "# AGENTS.md")):
                turns.append((role, content.strip()))
                last_date = (json.loads(line).get("timestamp") or last_date)[:10]
    return turns, n, last_date


def read_journal(session: str, start: int) -> tuple[list[tuple[str, str]], int, str]:
    path = journal(session)
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    new = rows[start:]
    return [(r["role"], r["text"]) for r in new], len(rows), (new[-1]["date"] if new else dt.date.today().isoformat())


def append_journal(session: str, role: str, text: str) -> None:
    if text.strip():
        with open(journal(session), "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": role, "text": text.strip()[:20_000], "date": dt.date.today().isoformat()}) + "\n")


def segment_text(turns: list[tuple[str, str]]) -> str:
    text = "\n\n".join(f"{role.upper()}: {t}" for role, t in turns)
    return text[-MAX_SEGMENT:]


# --- extraction -------------------------------------------------------------------------------------------------------

def call_llm(ext: dict, prompt: str) -> str:
    if ext["route"] == "claude":
        cmd = ["claude", "-p", "--model", ext.get("model", "haiku"), "--setting-sources", "", "--strict-mcp-config", "--tools", "",
               "--no-session-persistence", "--system-prompt", "Follow the instructions in the user's message exactly and output only what they ask for."]
        # Run from an empty folder with no settings: the worker loads no hooks (so it never triggers this hook) and no MCP server.
        work = hook_dir() / "worker"
        work.mkdir(exist_ok=True)
        out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=300, cwd=work,
                             env={**os.environ, "MAX_THINKING_TOKENS": "0"})
        if out.returncode != 0:
            raise RuntimeError(f"claude: {out.stderr.strip()[:300]}")
        return out.stdout
    if ext["route"] == "api":
        key = os.environ.get(ext.get("api_key_env", ""), "")
        req = urllib.request.Request(ext["endpoint"].rstrip("/") + "/chat/completions", method="POST",
                                     data=json.dumps({"model": ext["model"], "temperature": 0, "messages": [{"role": "user", "content": prompt}]}).encode(),
                                     headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    raise ValueError(f"unknown extractor route {ext['route']!r}")


def parse_memories(raw: str) -> list[dict]:
    """The JSON array in an LLM answer, tolerating prose or a code fence around it."""
    i, j = raw.find("["), raw.rfind("]")
    if i < 0 or j < i:
        return []
    items = json.loads(raw[i:j + 1])
    return [m for m in items if isinstance(m, dict) and isinstance(m.get("text"), str) and m.get("kind") in KINDS]


PREF = re.compile(r"\b(always|never|i prefer|i'd rather|i like|i want|please (?:use|don't|do not)|don't|do not)\b", re.I)
FIX = re.compile(r"\b(the fix was|fixed by|root cause|the problem was|turns out)\b", re.I)


def keyword_memories(turns: list[tuple[str, str]]) -> list[dict]:
    """Fallback without an LLM: short user sentences that state a preference, assistant sentences that state a fix."""
    out = []
    for role, text in turns:
        for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
            sentence = sentence.strip()
            if not 20 <= len(sentence) <= 300:
                continue
            if role == "user" and PREF.search(sentence):
                out.append({"text": sentence, "kind": "preference", "scope": "global"})
            elif role == "assistant" and FIX.search(sentence):
                out.append({"text": sentence, "kind": "fix", "scope": "project"})
    return out[:10]


def finalize(items: list[dict], project: str, date: str, session: str, project_allowed: bool, known_ids: set[int]) -> list[dict]:
    """Map "project" scope to the project name, stamp date and session, drop project memories where not allowed, and keep
    `supersedes` only when it names a memory the extractor was shown (an invented id would make the whole batch fail)."""
    out = []
    for m in items:
        scope = "global" if m.get("scope") == "global" else project
        if scope != "global" and not project_allowed:
            continue
        item = {"text": m["text"].strip()[:2000], "kind": m["kind"], "scope": scope, "observed_at": date, "session": session[:200]}
        if isinstance(m.get("supersedes"), int) and m["supersedes"] in known_ids:
            item["supersedes"] = m["supersedes"]
        out.append(item)
    return out


def extract(session: str, transcript: str, cwd: str) -> None:
    lock = hook_dir() / f"{safe(session)}.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if dt.datetime.now().timestamp() - lock.stat().st_mtime < 900:
            return  # another extraction of this session is running
        lock.unlink()  # stale: its worker died
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        extract_locked(session, transcript, cwd)
    finally:
        lock.unlink(missing_ok=True)


def extract_locked(session: str, transcript: str, cwd: str) -> None:
    s = settings()
    path, st = progress(session)
    turns, lines, date = read_turns(Path(transcript), st["done_lines"]) if transcript and Path(transcript).is_file() else ([], st["done_lines"], "")
    j_turns, j_lines, j_date = read_journal(session, st["journal_done"])
    if not turns:  # a transcript this script cannot read (or none): the hook's own journal
        turns, date = j_turns, j_date
    st.update(done_lines=lines, journal_done=j_lines, turns_done=session_state(session)[1]["turns"])
    if not turns:
        path.write_text(json.dumps(st), encoding="utf-8")
        return
    project = project_of(cwd)
    ext = s["extractor"]
    local = ext["route"] == "none" or (ext["route"] == "api" and is_local(ext.get("endpoint", "")))
    project_allowed = local or project not in [p.lower() for p in s["sensitive_projects"]]
    existing = footnote(s, ["memory-pack", "--project", project, "--max-chars", "6000"])["memories"] if Path(s["db"]).exists() else []
    if ext["route"] == "none":
        items = keyword_memories(turns)
    else:
        prompt = PROMPT.format(project=project, today=date, sensitive="" if project_allowed else SENSITIVE,
                               existing="\n".join(f"[id {m['id']}] {m['text']}" for m in existing) or "(none)",
                               segment=segment_text(turns))
        try:
            items = parse_memories(call_llm(ext, prompt))
        except Exception as e:  # LLM unavailable: keep something rather than nothing
            log(f"extractor failed, keyword fallback: {e}")
            items = keyword_memories(turns)
    batch = finalize(items, project, date, session, project_allowed, {m["id"] for m in existing})
    if batch:
        args = ["remember"] + [a for m in s["models"] for a in ("--model", m)]
        report = footnote(s, args, json.dumps(batch))
        log(f"{project}: {len(report['stored'])} stored, {report['duplicates']} duplicates from {len(turns)} turns")
    path.write_text(json.dumps(st), encoding="utf-8")


def spawn_extract(session: str, transcript: str, cwd: str) -> None:
    """Run the extraction in the background so the session never waits for the LLM."""
    args = [sys.executable, "-I", str(Path(__file__).resolve()), "extract", session, transcript, cwd]
    flags = (0x00000008 | 0x00000200) if os.name == "nt" else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=flags, start_new_session=os.name != "nt",
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- hook entry -------------------------------------------------------------------------------------------------------

def context(event_name: str, text: str) -> None:
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": text}}))


def catch_up(current: str) -> None:
    """Extract sessions that ended with turns never extracted (tools without SessionEnd, or a crash), at most three."""
    for p in sorted(hook_dir().glob("*.json"), key=lambda q: q.stat().st_mtime)[-50:]:
        if p.stem == safe(current):
            continue
        st = json.loads(p.read_text(encoding="utf-8"))
        if st.get("turns", 0) > progress(p.stem)[1]["turns_done"]:
            spawn_extract(p.stem, st.get("transcript", ""), st.get("cwd", "."))
            return  # one per start keeps the machine quiet; the next start takes the next one


def handle(event: dict) -> None:
    s = settings()
    e = normalize(event)
    name, session = e["name"], e["session"]
    project = project_of(e["cwd"])
    path, st = session_state(session)
    st.update(transcript=e["transcript"] or st["transcript"], cwd=e["cwd"])
    if name == "SessionStart":
        catch_up(session)
        if Path(s["db"]).exists():
            context(name, render(footnote(s, ["memory-pack", "--project", project])["memories"], "What you remember about this user and project"))
    elif name == "UserPromptSubmit":
        prompt = e["prompt"]
        append_journal(session, "user", prompt)
        st["turns"] += 1
        path.write_text(json.dumps(st), encoding="utf-8")  # before the spawn, so the worker sees this turn counted
        if prompt.strip().lower().startswith("/remember") or st["turns"] % s["every_turns"] == 0:
            spawn_extract(session, st["transcript"], e["cwd"])
        if Path(s["db"]).exists() and prompt.strip() and not prompt.startswith("/"):
            # shortcut: lexical recall only (milliseconds); hybrid needs the resident model daemon, not one process per prompt.
            hits = footnote(s, ["memory-recall", prompt[:500], "--project", project, "--limit", str(s["recall_limit"])])["memories"]
            context(name, render(hits, "Possibly relevant memories"))
    elif name == "Stop":
        append_journal(session, "assistant", e["answer"])
    elif name in ("PreCompact", "SessionEnd"):
        spawn_extract(session, st["transcript"], e["cwd"])
    path.write_text(json.dumps(st), encoding="utf-8")


def main() -> None:
    if len(sys.argv) == 5 and sys.argv[1] == "extract":
        try:
            extract(*sys.argv[2:])
        except Exception as e:
            log(f"extract failed: {e!r}")
        return
    try:
        handle(json.loads(sys.stdin.read() or "{}"))
    except Exception as e:  # never break the session
        log(f"{e!r}")


if __name__ == "__main__":
    main()
