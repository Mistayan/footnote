"""Warm per-query cost of a lab pipeline: query encode, BM25, dense scoring and fusion, in milliseconds, plus model and index size.

    bench/.labenv/Scripts/python.exe -I bench/lab/latency.py bekko-a8m scifact

Measured in one process after a warm-up, single-threaded caller, 200 queries from the dev split. Numbers are for this machine only.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import lab  # noqa: E402
import models  # noqa: E402


def main() -> int:
    model, dataset = sys.argv[1], sys.argv[2]
    corpus, queries, _ = fetch.load(dataset, "dev")
    texts = list(queries.values())[:200]
    eng = lab.LabEngine("latency", {"dense": {"model": model}, "lexical": {"k1": 1.5, "tokenizer": {"stem": "en"}},
                                    "chunker": {"kind": "whole"}, "fusion": {"kind": "cc", "norm": "zscore", "alpha": 0.55}})
    info = eng.prepare(dataset, corpus)
    enc = eng._enc
    for t in texts[:10]:  # warm-up: thread pools, allocators
        enc.embed([t], "query")
    encode, total = [], []
    for t in texts:
        a = time.perf_counter()
        eng._qcache.pop(t, None)
        eng.search("q", t, 10)
        total.append((time.perf_counter() - a) * 1000)
    for t in texts:
        a = time.perf_counter()
        enc.embed([t], "query")
        encode.append((time.perf_counter() - a) * 1000)
    p = lambda v, q: sorted(v)[int(q * (len(v) - 1))]
    folder = models.model_dir(model)
    row = {"model": model, "dataset": dataset, "queries": len(texts),
           "encode_ms_p50": round(statistics.median(encode), 2), "encode_ms_p95": round(p(encode, .95), 2),
           "search_total_ms_p50": round(statistics.median(total), 2), "search_total_ms_p95": round(p(total, .95), 2),
           "model_mb": round((folder / "model.onnx").stat().st_size / 1e6, 1),
           "index_mb_per_1000_chunks": round(info["index_bytes_in_memory"] / info["chunks"] * 1000 / 1e6, 2)}
    print(json.dumps(row))
    with (HERE / "latency.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
