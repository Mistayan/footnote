"""Daemon resident memory by component, recall latency and ranking identity (#517). Windows only (process memory counters).

    python -I bench/experiments/daemon_ram.py <footnote.exe> <label> <source memory.db> <models dir> <out dir> [--configured jina-v5-nano]

Isolated state folder (never the user's): a copy of the memory database and of the model folders, memory.json naming the
configured model(s), metrics on. One daemon (`serve --mcp --daemon --idle-seconds 20`) and one agent session (`footnote mcp`)
held open all along, as an agent keeps it. Phases, the daemon's working set and private bytes read after each:

  started   daemon up, no request yet: process, runtime, nothing opened
  lexical   20 keyword recalls through the daemon: + SQLite connection caches and the Tantivy index readers
  hook      20 hook recalls (`memory-recall --resident --model <configured>`, what the prompt hook sends): + configured model
  agents    20 `footnote_recall` calls from the agent session (the agents' tool): + whatever models that tool loads
  idle      no request for idle_seconds: models unloaded
  reload    20 hook recalls again: the model loads again, rankings must equal the `hook` phase

Then latency, whole process per call as the hook pays it: 2 passes x 20 queries, hook recall through the warm daemon; and the
agent tool's in-daemon time per call. Rankings (memory ids only, never text) are written for the identity check.
Output: <out dir>/<label>.json. The queries are generic workload, not questions with answers: quality is checked as identity.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QUERIES = [
    "daemon resident memory", "benchmark table format", "commit message length", "one worktree per story",
    "release installer update", "recall in French prompts", "launcher design rules", "hook context budget",
    "embedding model choice", "keyword only recall", "subagent approval", "metrics spans",
    "mémoire du démon", "tableau de benchmark", "longueur des messages de commit", "rappel par le sens",
    "installer la version", "règles de conception", "modèle d'embedding", "budget de contexte",
]


class Counters(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


def memory(pid: int) -> dict:
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    h = k32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY_LIMITED_INFORMATION | VM_READ
    c = Counters()
    c.cb = ctypes.sizeof(c)
    ok = psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
    k32.CloseHandle(h)
    if not ok:
        raise SystemExit(f"cannot read memory of pid {pid}")
    mb = lambda b: round(b / 2**20, 1)  # noqa: E731
    return {"ws_mb": mb(c.WorkingSetSize), "private_mb": mb(c.PrivateUsage), "peak_ws_mb": mb(c.PeakWorkingSetSize)}


class Session:
    """An agent's MCP session through `footnote mcp` (relayed to the daemon)."""

    def __init__(self, cmd: list[str], env: dict):
        self.p = subprocess.Popen([*cmd, "mcp"], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self.n = 0
        self.call_raw("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "bench"}})

    def call_raw(self, method: str, params: dict) -> dict:
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def recall(self, query: str) -> tuple[list[int], float]:
        t = time.perf_counter()
        r = self.call_raw("tools/call", {"name": "footnote_recall", "arguments": {"query": query, "verbose": True}})
        ms = (time.perf_counter() - t) * 1000
        v = json.loads(r["result"]["content"][0]["text"])
        return [h["id"] for h in v.get("results", [])], ms

    def close(self) -> None:
        self.p.stdin.close()
        self.p.wait(timeout=10)


def main() -> None:
    exe, label, src_db, models_dir, out_dir = sys.argv[1:6]
    configured = sys.argv[sys.argv.index("--configured") + 1].split(",") if "--configured" in sys.argv else ["jina-v5-nano"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix="fn517-"))
    try:
        shutil.copy2(src_db, state / "memory.db")
        for m in Path(models_dir).iterdir():
            if (m / "manifest.json").is_file():
                shutil.copytree(m, state / "models" / m.name)
        model_paths = [str(state / "models" / m) for m in configured]
        db = str(state / "memory.db")
        (state / "memory.json").write_text(json.dumps({"db": db, "models": model_paths, "metrics": True}), encoding="utf-8")
        env = {**__import__("os").environ, "FOOTNOTE_STATE_DIR": str(state)}
        env.pop("CARGO_MANIFEST_DIR", None)
        base = [exe, "--db", db]
        hook_args = [a for m in model_paths for a in ("--model", m)]
        idle = 20
        daemon = subprocess.Popen([*base, "serve", "--mcp", "--daemon", "--no-audit", "--idle-seconds", str(idle)],
                                  env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result: dict = {"label": label, "exe": exe, "configured": configured, "queries": len(QUERIES), "phases": {}}
        try:
            def resident(q: str, extra: list[str]) -> subprocess.CompletedProcess:
                return subprocess.run([*base, "memory-recall", q, "--resident", "--project", "footnote", *extra],
                                      env=env, capture_output=True, text=True, encoding="utf-8")

            for _ in range(100):
                if resident("warm", []).returncode == 0 and '"error"' not in resident("warm", []).stdout:
                    break
                time.sleep(0.2)
            else:
                raise SystemExit("daemon never answered")
            # `started` is read after the one keyword probe above: the closest to "nothing loaded" a live daemon gets.
            time.sleep(1)
            result["phases"]["started"] = memory(daemon.pid)
            session = Session(base, env)  # held open: an agent's session keeps the daemon alive
            for q in QUERIES:
                resident(q, [])
            result["phases"]["lexical"] = memory(daemon.pid)
            hook_rank = {}
            for q in QUERIES:
                r = resident(q, hook_args)
                hook_rank[q] = [m["id"] for m in json.loads(r.stdout)["memories"]]
            result["phases"]["hook"] = memory(daemon.pid)
            agent_rank, agent_ms = {}, []
            for q in QUERIES:
                agent_rank[q], ms = session.recall(q)
            for _ in range(2):
                for q in QUERIES:
                    agent_ms.append(session.recall(q)[1])
            result["phases"]["agents"] = memory(daemon.pid)
            # latency: whole process per hook call, 2 passes
            hook_ms = []
            for _ in range(2):
                for q in QUERIES:
                    t = time.perf_counter()
                    resident(q, hook_args)
                    hook_ms.append((time.perf_counter() - t) * 1000)
            time.sleep(idle + 8)  # the idle check runs every 5 s
            result["phases"]["idle"] = memory(daemon.pid)
            # reload after the unload: the next hook recall loads the model again and ranks the same
            reload_rank = {q: [m["id"] for m in json.loads(resident(q, hook_args).stdout)["memories"]] for q in QUERIES}
            result["reload_same_rankings"] = reload_rank == hook_rank
            result["phases"]["reload"] = memory(daemon.pid)
            pct = lambda v, f: round(sorted(v)[max(0, int(f * len(v)) - 1)], 1)  # noqa: E731
            result["latency_ms"] = {
                "hook_recall_process": {"calls": len(hook_ms), "p50": round(statistics.median(hook_ms), 1),
                                        "p95": pct(hook_ms, 0.95)},
                "agent_recall_in_session": {"calls": len(agent_ms), "p50": round(statistics.median(agent_ms), 1),
                                            "p95": pct(agent_ms, 0.95)},
            }
            result["rankings"] = {"hook": hook_rank, "agents": agent_rank}
            session.close()
        finally:
            daemon.terminate()  # by its own handle (PID), never by name
            daemon.wait(timeout=10)
        spans = [json.loads(line) for line in (state / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
                 if '"span"' in line] if (state / "metrics.jsonl").exists() else []
        loads = [s for s in spans if s["span"] == "encoder.load"]
        result["encoder_loads"] = len(loads)
        result["span_names"] = sorted({s["span"] for s in spans})
        (out / f"{label}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "rankings"}, indent=1))
    finally:
        shutil.rmtree(state, ignore_errors=True)


if __name__ == "__main__":
    main()
