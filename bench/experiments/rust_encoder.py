"""Rust encoder (`footnote embed`) against the Python helper (tools/embed.py): same texts, same models, vector agreement and speed.

    .venv/Scripts/python.exe -I bench/experiments/rust_encoder.py --bin target/release/footnote.exe --models C:/.../bekko-a8m C:/.../gte-small

BUILD-SPEED.md test 4, condition 1: every cosine at least 0.99999, for 2,000 SciFact documents and the SciFact test queries.
Both sides batch the same way (8 texts per inference, in the given order), so int8 per-batch quantization sees the same batches.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "bench")]
import embed  # noqa: E402
import fetch  # noqa: E402


def rust(bin_: str, model: str, kind: str, texts: list[str]) -> tuple[np.ndarray, float]:
    out = subprocess.run([str(Path(bin_).resolve()), "embed", "--model", model, "--kind", kind], input=json.dumps(texts), capture_output=True,
                         text=True, encoding="utf-8", check=True)
    v = json.loads(out.stdout)
    if "error" in v:
        raise RuntimeError(v["error"])
    return np.asarray(v["vectors"]), v["seconds"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--dataset", default="scifact")
    ap.add_argument("--docs", type=int, default=2000)
    args = ap.parse_args()
    corpus, queries, _ = fetch.load(args.dataset, "test")
    sets = {"passage": [f"{corpus[d][0]}\n{corpus[d][1]}".strip()[:2000] for d in sorted(corpus)[:args.docs]],
            "query": [queries[q] for q in sorted(queries)]}
    for m in args.models:
        e = embed.Embedder(m)
        for kind, texts in sets.items():
            e.encode({"texts": texts[:8], "kind": kind})  # warm-up
            t = time.perf_counter()
            py = np.asarray(e.encode({"texts": texts, "kind": kind})["vectors"])
            py_s = time.perf_counter() - t
            rs, rs_s = rust(args.bin, m, kind, texts)  # includes the first batch's warm-up, not the model load
            cos = (py * rs).sum(1)
            print(json.dumps({"model": Path(m).name, "kind": kind, "texts": len(texts), "cosine_min": round(float(cos.min()), 9),
                              "max_abs_diff": float(np.abs(py - rs).max()), "python_per_s": round(len(texts) / py_s, 1),
                              "rust_per_s": round(len(texts) / rs_s, 1)}), flush=True)


if __name__ == "__main__":
    main()
