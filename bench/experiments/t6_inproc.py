"""Test 6 (LLAMACPP-INPROCESS.md): Jina v5 nano query latency, HTTP per query (A), kept-alive HTTP (B), Rust in-process (C).

Run in bench/.labenv on a quiet machine, after `cargo build --release` in bench/llama_inproc:

    python -I experiments/t6_inproc.py

Rows append to sweeps/t6_inproc.jsonl.
"""
from __future__ import annotations

import datetime as dt
import http.client
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BENCH), str(BENCH / "lab")]
import fetch  # noqa: E402
from run import pct  # noqa: E402
import lab  # noqa: E402
import models  # noqa: E402

MODEL = "gguf-jina-v5-nano"
LIMITS = {"alloprof": 34.4, "mix-fr-en": 33.8}  # test 5 condition 3: twice the shipped pair's p95 of 13 November
EXE = BENCH / "llama_inproc/target/release/llama_inproc.exe"


def stats(times: list[float]) -> dict:
    return {"p50": round(statistics.median(times), 3), "p95": round(pct(times, 0.95), 3)}


def timed(fn, texts: list[str]) -> tuple[list[float], list]:
    for t in texts[:3]:
        fn(t)
    times, outs = [], []
    for t in texts:
        start = time.perf_counter()
        outs.append(fn(t))
        times.append((time.perf_counter() - start) * 1000)
    return times, outs


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def arm_c(texts: list[str]) -> tuple[list[float], np.ndarray]:
    with tempfile.TemporaryDirectory() as tmp:
        qfile, out = Path(tmp) / "q.bin", Path(tmp) / "out.jsonl"
        qfile.write_bytes(b"\0".join(t.encode("utf-8") for t in texts))
        subprocess.run([str(EXE), str(Path(lab.LLAMA_SERVER).parent), str(models.gguf_path(MODEL)), str(max(1, (os.cpu_count() or 4) // 2)),
                        str(qfile), str(out)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    return [r["ms"] for r in rows], unit(np.asarray([r["vec"] for r in rows], dtype=np.float32))


def main() -> None:
    assert EXE.exists(), "build bench/llama_inproc first"
    sets = {}
    for dataset in LIMITS:
        _, queries, _ = fetch.load(dataset, "dev")
        sets[dataset] = [t.encode("utf-8")[:500].decode("utf-8", errors="ignore") for _, t in sorted(queries.items())[:100]]
    pair = {}
    for name in ("bekko-a8m", "gte-small"):  # context only: the threshold stays the 13 November figure
        enc = lab.Encoder(name)
        pair[name] = {d: stats(timed(lambda t: enc.embed([t], "query"), texts)[0]) for d, texts in sets.items()}
    for dataset, texts in sets.items():
        c_times, c_vecs = arm_c(texts)  # first, while no server holds the cores
        enc = lab.LlamaEncoder(MODEL)
        try:
            a_times, a_vecs = timed(lambda t: enc.embed([t], "query")[0], texts)
            host, port = enc._url(0)[7:].split(":")
            conn = http.client.HTTPConnection(host, int(port))

            def keep_alive(text: str) -> None:
                conn.request("POST", "/v1/embeddings", json.dumps({"input": [enc.spec["q"] + text]}), {"Content-Type": "application/json"})
                json.loads(conn.getresponse().read())
            b_times, _ = timed(keep_alive, texts)
        finally:
            enc.close()
        cos = (np.asarray(a_vecs) * c_vecs).sum(axis=1)
        c = stats(c_times)
        row = {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "model": MODEL, "dataset": dataset, "queries": len(texts),
               "A_http_per_query": stats(a_times), "B_http_keep_alive": stats(b_times), "C_rust_in_process": c,
               "cos_min_C_vs_A": float(cos.min()), "valid": bool(cos.min() >= 0.9999), "limit_ms": LIMITS[dataset],
               "pass": bool(cos.min() >= 0.9999 and c["p95"] <= LIMITS[dataset]),
               "pair_today": {n: v[dataset] for n, v in pair.items()}}
        with (BENCH / "sweeps/t6_inproc.jsonl").open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(row) + "\n")
        print(json.dumps(row, indent=1), flush=True)


if __name__ == "__main__":
    main()
