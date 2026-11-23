"""Memory per encoder load step (#517), with a diagnostic build that pauses at each step. Windows only.

    git apply bench/experiments/daemon-ram/memtrace.patch   # then build: cargo build --release --features llama
    python -I bench/experiments/daemon_ram_components.py <footnote-diag.exe> <models dir> <out.json>

The patch makes the encoder print `MEMTRACE <step>` to stderr and sleep 1.5 s when FOOTNOTE_MEMTRACE is set, and stops
silencing llama.cpp's own log (its buffer sizes). For each model, one `footnote embed` process encodes 20 queries in one
call, then a second process 20 passages; the process's working set and private bytes are read at every step.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from daemon_ram import QUERIES, memory  # noqa: E402


def trace(exe: str, model: Path, kind: str) -> dict:
    env = {**os.environ, "FOOTNOTE_MEMTRACE": "1"}
    p = subprocess.Popen([exe, "embed", "--model", str(model), "--kind", kind], env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    steps, log = [], []
    sink = threading.Thread(target=lambda: p.stdout.read(), daemon=True)  # the vectors, not needed
    sink.start()
    p.stdin.write(json.dumps(QUERIES))
    p.stdin.close()
    for line in p.stderr:
        if line.startswith("MEMTRACE "):
            steps.append({"step": line.split()[1], **memory(p.pid)})
        elif any(k in line for k in ("buffer size", "compute buffer", "REPACK", "KV", "model size", "file size")):
            log.append(line.strip())
    p.wait(timeout=120)
    return {"steps": steps, "llama_log": log}


def main() -> None:
    exe, models_dir, out = sys.argv[1:4]
    result = {}
    for m in sorted(Path(models_dir).iterdir()):
        if (m / "manifest.json").is_file():
            result[m.name] = {kind: trace(exe, m, kind) for kind in ("query", "passage")}
            result[m.name]["files_mb"] = {f.name: round(f.stat().st_size / 2**20, 1) for f in m.iterdir() if f.is_file()}
    Path(out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
