"""Measure resident, single-query encoding after the queued quality runs finish.

    bench/.labenv/Scripts/python.exe -I bench/experiments/model_latency.py --after-log bench/work/models2.log

Uses the same fixed dev queries for every model. This measures encoding only,
not retrieval latency. Rows append to bench/sweeps/model_latency.jsonl.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
import fetch  # noqa: E402
from run import machine, pct  # noqa: E402

MODELS = ("bekko-a8m", "gte-small", "embeddinggemma-300m", "harrier-270m", "granite-small-en-r2", "arctic-m-v2")
DATASETS = ("scifact", "nfcorpus", "alloprof", "mix-fr-en")


def measure(encoder, queries: list[str]) -> dict:
    if not queries:
        raise ValueError("encoding latency requires queries")
    for _ in range(3):
        encoder.embed([queries[0]], "query")
    times = []
    for text in queries:
        start = time.perf_counter()
        vector = encoder.embed([text], "query")
        times.append((time.perf_counter() - start) * 1000)
    return {"queries": len(times), "dimensions": int(vector.shape[1]),
            "p50": round(statistics.median(times), 3), "p95": round(pct(times, 0.95), 3)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--after-log", type=Path, help="wait for a standalone DONE line before loading any model")
    args = ap.parse_args()
    if args.after_log:
        print(f"Waiting for {args.after_log}", flush=True)
        while not (args.after_log.exists() and "DONE" in args.after_log.read_text(encoding="utf-8").splitlines()):
            time.sleep(20)

    sys.path.insert(0, str(BENCH / "lab"))
    from lab import Encoder
    import models

    checks = [json.loads(line) for line in (BENCH / "lab/model_checks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for name in MODELS[2:]:
        matching = [row for row in checks if row["model"] == name]
        if not matching or not matching[-1]["pass"]:
            raise ValueError(f"model reproduction gate not passed: {name}")

    query_sets = {}
    for dataset in DATASETS:
        _, queries, _ = fetch.load(dataset, "dev")
        query_sets[dataset] = [(qid, text.encode("utf-8")[:500].decode("utf-8", errors="ignore"))
                               for qid, text in sorted(queries.items())[:100]]
    output = BENCH / "sweeps/model_latency.jsonl"
    output.parent.mkdir(exist_ok=True)
    host = machine()
    code = {"measurement_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "encoder_sha256": hashlib.sha256((BENCH / "lab/lab.py").read_bytes()).hexdigest()}
    for name in MODELS:
        encoder = Encoder(name)
        folder = models.model_dir(name)
        model_bytes = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
        for dataset, queries in query_sets.items():
            row = {"protocol": "model-encoding-v1", "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "model": name, "model_lock": models.lock_entry(name), "model_bytes": model_bytes,
                   "dataset": dataset, "split": "dev", "dataset_pin": fetch.dataset_pin(dataset),
                   "query_ids": [qid for qid, _ in queries], "query_clip_bytes": 500,
                   "machine": host, "code": code, "threads": max(1, (host["logical_cpus"] or 4) // 2),
                   "scope": "resident ONNX CPU, tokenizer + prefixes + batch-1 inference + pooling + normalization; no query cache; excludes retrieval",
                   "latency_ms": measure(encoder, [text for _, text in queries])}
            with output.open("a", encoding="utf-8") as sink:
                sink.write(json.dumps(row) + "\n")
            print(f"{dataset} {name}: {row['latency_ms']}", flush=True)
        del encoder
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
