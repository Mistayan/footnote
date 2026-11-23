"""Hook recall latency, builds alternated (#517): default model pair, 3 rounds x builds x metrics off/on, 40 calls each.

    python -I bench/experiments/daemon_ram_latency.py <source memory.db> <models dir> <footnote.exe> [<footnote.exe> ...]

Whole process per call, as the hook pays it (`memory-recall --resident` with bekko-a8m and gte-small), through a warm daemon
started for each build in an isolated state folder. Prints round, build, metrics, (p50 ms, p95 ms).
"""
import json, os, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from daemon_ram import QUERIES  # noqa: E402
SRC = sys.argv[1]; MODELS = sys.argv[2]; exes = sys.argv[3:]
state = tempfile.mkdtemp(prefix="fn517ab-")
shutil.copy2(SRC, os.path.join(state, "memory.db"))
for m in ("bekko-a8m", "gte-small"):
    shutil.copytree(os.path.join(MODELS, m), os.path.join(state, "models", m))
mp = [os.path.join(state, "models", m) for m in ("bekko-a8m", "gte-small")]
db = os.path.join(state, "memory.db")
hook = [a for m in mp for a in ("--model", m)]
def run(exe, metrics):
    json.dump({"db": db, "models": mp, "metrics": metrics}, open(os.path.join(state, "memory.json"), "w"))
    env = {**os.environ, "FOOTNOTE_STATE_DIR": state}
    d = subprocess.Popen([exe, "--db", db, "serve", "--mcp", "--daemon", "--no-audit", "--idle-seconds", "600"], env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        call = lambda q: subprocess.run([exe, "--db", db, "memory-recall", q, "--resident", "--project", "footnote", *hook], env=env, capture_output=True, text=True)
        for _ in range(100):
            r = call("warm")
            if r.returncode == 0 and '"error"' not in r.stdout: break
            time.sleep(0.2)
        for q in QUERIES[:5]: call(q)
        ts = []
        for q in QUERIES * 2:
            t = time.perf_counter(); call(q); ts.append((time.perf_counter() - t) * 1000)
        ts.sort()
        return round(statistics.median(ts), 1), round(ts[int(0.95 * len(ts)) - 1], 1)
    finally:
        d.terminate(); d.wait()
for rnd in range(3):
    for exe in exes:
        for metrics in (False, True):
            print(rnd, os.path.basename(exe), "metrics" if metrics else "nometrics", run(exe, metrics), flush=True)
shutil.rmtree(state, ignore_errors=True)
