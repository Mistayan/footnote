"""Test 6 follow-up: Footnote's own llama.cpp encoder (`--features llama`) against the test 5 server, Jina v5 nano.

    python -I experiments/t6_product_check.py <footnote.exe built with --features llama>

Checks cosine >= 0.9999 per text (100 Alloprof dev queries, the 50 longest Alloprof documents, which exercise the 512-token cut)
and reports the mean time per query from two `footnote embed` calls (1 query, then 101: the difference removes model loading).
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BENCH), str(BENCH / "lab")]
import fetch  # noqa: E402
import lab  # noqa: E402

MODEL_DIR = BENCH.parent / "artifacts/models/jina-v5-nano"


def footnote(exe: str, texts: list[str], kind: str) -> tuple[np.ndarray, float]:
    out = subprocess.run([exe, "embed", "--model", str(MODEL_DIR), "--kind", kind], input=json.dumps(texts),
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    data = json.loads(out)
    return np.asarray(data["vectors"], dtype=np.float32), data["seconds"]


def main() -> None:
    exe = sys.argv[1]
    corpus, queries, _ = fetch.load("alloprof", "dev")
    qs = [t.encode("utf-8")[:500].decode("utf-8", errors="ignore") for _, t in sorted(queries.items())[:100]]
    docs = sorted((f"{a} {b}".strip() for a, b in corpus.values()), key=len, reverse=True)[:50]
    enc = lab.LlamaEncoder("gguf-jina-v5-nano")
    try:
        ref = {"query": enc.embed(qs, "query"), "passage": enc.embed(docs, "passage")}
    finally:
        enc.close()
    report = {}
    for kind, texts in (("query", qs), ("passage", docs)):
        mine, _ = footnote(exe, texts, kind)
        cos = (mine * ref[kind]).sum(axis=1)
        report[kind] = {"texts": len(texts), "cos_min": float(cos.min()), "below_0.9999": int((cos < 0.9999).sum())}
    _, one = footnote(exe, qs[:1], "query")
    _, many = footnote(exe, qs[:1] + qs, "query")
    report["mean_ms_per_query"] = round((many - one) / len(qs) * 1000, 2)
    report["valid"] = all(report[k]["below_0.9999"] == 0 for k in ("query", "passage"))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
