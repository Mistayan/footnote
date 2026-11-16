"""Sequential, resumable Vulkan speed grid; run only after other benchmarks stop."""
import hashlib
import json
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import platform

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import llamacpp_runtimes as original

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "bench/work/speed-grid-20261116-v2"
RUNTIMES = {k: original.RUNTIMES[k] for k in ("b11901-vulkan", "b12421-vulkan")}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def post(url, inputs):
    req = urllib.request.Request(url + "/v1/embeddings", json.dumps({"input": inputs}).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        data = json.load(response)["data"]
    return [x["embedding"] for x in sorted(data, key=lambda x: x["index"])]


def run_cell(name, exe, flash, ub, repeat, passages, queries):
    label = f"{name}-fa-{flash}-ub-{ub}-r{repeat}"
    result = OUT / (label + ".json")
    if result.exists():
        return json.loads(result.read_text(encoding="utf-8"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    cmd = [str(exe), "-m", str(original.GGUF), "--embedding", "--pooling", "last", "-ngl", "99", "-np", "8",
           "-c", "8192", "-b", "8192", "-ub", str(ub), "-fa", flash, "--host", "127.0.0.1",
           "--port", str(port), "--no-webui"]
    with (OUT / (label + ".log")).open("a", encoding="utf-8") as log:
        log.write(f"\n--- attempt {time.time()} ---\n")
        log.flush()
        proc = subprocess.Popen(cmd, cwd=exe.parent, stdout=log, stderr=log)
        try:
            for _ in range(180):
                try:
                    with urllib.request.urlopen(url + "/health", timeout=2):
                        break
                except OSError:
                    if proc.poll() is not None:
                        raise RuntimeError(f"server exited {proc.returncode}")
                    time.sleep(1)
            else:
                raise RuntimeError("server startup timeout")
            post(url, ["Query: warm up"])
            latencies = []
            for q in queries:
                start = time.perf_counter()
                post(url, ["Query: " + q])
                latencies.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            vectors = []
            for i in range(0, len(passages), 16):
                vectors.extend(post(url, ["Document: " + p for p in passages[i:i + 16]]))
            duration = time.perf_counter() - start
            reference_path = OUT / "reference-vectors.npy"
            arr = np.asarray(vectors[:100], dtype=np.float32)
            if not np.isfinite(arr).all() or np.any(np.linalg.norm(arr, axis=1) == 0):
                raise RuntimeError("non-finite or zero vectors")
            if not reference_path.exists():
                np.save(reference_path, arr)
            reference = np.load(reference_path)
            cosine = np.sum(arr * reference, axis=1) / (np.linalg.norm(arr, axis=1) * np.linalg.norm(reference, axis=1))
            ordered = sorted(latencies)
            row = {"label": label, "command": cmd, "queries": len(queries), "passages": len(passages),
                   "query_p50_ms": statistics.median(ordered), "query_p95_ms": ordered[int(0.95 * len(ordered)) - 1],
                   "passages_per_s": len(passages) / duration, "min_cosine": float(cosine.min())}
            result.write_text(json.dumps(row, indent=2), encoding="utf-8")
            return row
        finally:
            proc.terminate()
            proc.wait(timeout=30)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    passages, queries = original.texts()
    clipped = [p.encode("utf-8")[:400].decode("utf-8", errors="ignore") for p in passages[:256]]
    snapshot = {"passages": clipped, "queries": queries[:100], "model_sha256": digest(original.GGUF),
                "runtime_sha256": {k: digest(v) for k, v in RUNTIMES.items()}, "runner_sha256": digest(Path(__file__)),
                "platform": platform.platform(), "processor": platform.processor()}
    path = OUT / "inputs.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != snapshot:
            raise RuntimeError("Inputs changed; refusing to resume")
    else:
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(snapshot["queries"]) != 100 or len(snapshot["passages"]) != 256:
        raise RuntimeError("Fixture does not meet frozen sample sizes")
    for name, exe in RUNTIMES.items():
        for flash in ("off", "on"):
            for ub in (512, 2048, 8192):
                for repeat in (1, 2):
                    try:
                        row = run_cell(name, exe, flash, ub, repeat, snapshot["passages"], snapshot["queries"])
                    except Exception as exc:
                        label = f"{name}-fa-{flash}-ub-{ub}-r{repeat}"
                        row = {"label": label, "error": f"{type(exc).__name__}: {exc}"}
                        error_path = OUT / (label + ".error.json")
                        if not error_path.exists():
                            error_path.write_text(json.dumps(row, indent=2), encoding="utf-8")
                    print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
