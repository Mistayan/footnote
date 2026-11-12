"""Real embeddings for the vector-index tracks: bekko-a8m over the mix-fr-en corpus (documents) and test queries.

    bench/.labenv/Scripts/python.exe -I bench/dbbake/make_vectors.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "lab"))
import fetch  # noqa: E402
import lab  # noqa: E402

OUT = HERE.parent / "work" / "vectors"


def main() -> None:
    corpus, queries, _ = fetch.load("mix-fr-en", "test")
    enc = lab.Encoder("bekko-a8m")
    docs = [f"{t}\n{x}" if t else x for t, x in corpus.values()]
    qs = list(queries.values())[:1000]
    d = lab.cached_embed(enc, docs, "passage").astype(np.float32)
    q = lab.cached_embed(enc, qs, "query").astype(np.float32)
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "docs.npy", d)
    np.save(OUT / "queries.npy", q)
    print(d.shape, q.shape, float(np.linalg.norm(d[0])))


if __name__ == "__main__":
    main()
