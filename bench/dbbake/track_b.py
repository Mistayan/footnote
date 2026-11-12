"""Track B, vector index: exact versus approximate search over the same vectors.

    bench/.dbenv/Scripts/python.exe -I bench/dbbake/track_b.py --sizes 11462,100000,1000000

Vectors: the real bekko-a8m embeddings of the mix-fr-en corpus (384 dims, unit length) and 1000 real queries. Sizes above the real
corpus are SYNTHETIC: real vectors resampled with Gaussian noise (sigma 0.03 per dim, renormalized), so they keep a realistic local
structure but are not real documents. Recall is measured against exact search on the same vectors, so it says how much an index loses,
not how good the embedding is. Latency is one query at a time (the interactive path), after a warm-up. Disk is the index on disk.
Results are appended to bench/dbbake/results.jsonl.
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
VEC = HERE.parent / "work" / "vectors"
K = 10


def scaled(base: np.ndarray, n: int) -> np.ndarray:
    if n <= len(base):
        return base[:n]
    rng = np.random.default_rng(20261112)
    out = np.empty((n, base.shape[1]), dtype=np.float32)
    for s in range(0, n, 100_000):
        e = min(n, s + 100_000)
        v = base[rng.integers(0, len(base), e - s)] + rng.normal(0, 0.03, (e - s, base.shape[1])).astype(np.float32)
        out[s:e] = v / np.linalg.norm(v, axis=1, keepdims=True)
    return out


def exact_topk(docs: np.ndarray, qs: np.ndarray) -> np.ndarray:
    out = np.empty((len(qs), K), dtype=np.int64)
    for i, q in enumerate(qs):
        s = docs @ q
        top = np.argpartition(-s, K)[:K]
        out[i] = top[np.argsort(-s[top])]
    return out


def dirsize(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size


class Numpy:
    name = "numpy exact (brute force)"

    def build(self, docs, work):
        self.d = docs
        return 0

    def search(self, q):
        s = self.d @ q
        top = np.argpartition(-s, K)[:K]
        return top[np.argsort(-s[top])]


class SqliteVec:
    name = "sqlite-vec exact"

    def build(self, docs, work):
        import sqlite_vec
        import sqlite3
        self.db = sqlite3.connect(work / "v.db")
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.execute(f"CREATE VIRTUAL TABLE v USING vec0(embedding float[{docs.shape[1]}])")
        for s in range(0, len(docs), 20_000):
            self.db.executemany("INSERT INTO v(rowid, embedding) VALUES (?, ?)",
                                ((s + i + 1, docs[s + i].tobytes()) for i in range(min(20_000, len(docs) - s))))
            self.db.commit()
        self.path = work / "v.db"
        return self.path.stat().st_size

    def search(self, q):
        rows = self.db.execute("SELECT rowid FROM v WHERE embedding MATCH ? AND k = ? ORDER BY distance", (q.tobytes(), K)).fetchall()
        return np.array([r[0] - 1 for r in rows])


class Usearch:
    def __init__(self, dtype: str, connectivity=16, ef_add=128, ef_search=64):
        self.dtype, self.m, self.ea, self.es = dtype, connectivity, ef_add, ef_search
        self.name = f"usearch hnsw {dtype} M={connectivity} ef={ef_search}"

    def build(self, docs, work):
        from usearch.index import Index
        self.idx = Index(ndim=docs.shape[1], metric="ip", dtype=self.dtype, connectivity=self.m,
                         expansion_add=self.ea, expansion_search=self.es)
        self.idx.add(np.arange(len(docs)), docs)
        self.idx.save(str(work / "u.usearch"))
        return (work / "u.usearch").stat().st_size

    def search(self, q):
        return np.asarray(self.idx.search(q, K).keys)


class Lance:
    def __init__(self, kind: str):
        self.kind = kind
        self.name = f"lancedb {kind}"

    def build(self, docs, work):
        import lancedb
        import pyarrow as pa
        db = lancedb.connect(str(work))
        dim = docs.shape[1]
        arr = pa.FixedSizeListArray.from_arrays(pa.array(docs.reshape(-1), type=pa.float32()), dim)
        self.t = db.create_table("t", pa.table({"id": pa.array(np.arange(len(docs))), "vector": arr}))
        if self.kind != "flat":
            from lancedb.index import HnswSq, IvfPq
            cfg = IvfPq(distance_type="dot", num_sub_vectors=dim // 8) if self.kind == "ivf_pq" else HnswSq(distance_type="dot")
            self.t.create_index("vector", config=cfg)
        return dirsize(work)

    def search(self, q):
        r = self.t.search(q).metric("dot").limit(K)
        if self.kind == "ivf_pq":
            r = r.nprobes(20).refine_factor(5)
        return np.array([x["id"] for x in r.to_list()])


def engines():
    return [Numpy(), SqliteVec(), Usearch("f32"), Usearch("i8"), Usearch("f32", ef_search=128), Lance("flat"), Lance("ivf_pq"), Lance("hnsw_sq")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="11462")
    ap.add_argument("--only")
    ap.add_argument("--queries", type=int, default=300)
    args = ap.parse_args()
    base = np.load(VEC / "docs.npy")
    qs = np.load(VEC / "queries.npy")[: args.queries]
    for n in (int(x) for x in args.sizes.split(",")):
        docs = scaled(base, n)
        truth = exact_topk(docs, qs)
        for eng in engines():
            if args.only and args.only not in eng.name:
                continue
            work = Path(tempfile.mkdtemp(prefix="dbbake-"))
            row = {"track": "B", "engine": eng.name, "vectors": n, "dim": int(docs.shape[1]), "synthetic": n > len(base), "queries": len(qs)}
            try:
                t0 = time.perf_counter()
                row["disk_mb"] = round(eng.build(docs, work) / 1e6, 1)
                row["build_s"] = round(time.perf_counter() - t0, 1)
                for q in qs[:20]:
                    eng.search(q)
                times, hit = [], 0
                for i, q in enumerate(qs):
                    a = time.perf_counter()
                    got = eng.search(q)
                    times.append((time.perf_counter() - a) * 1000)
                    hit += len(set(got.tolist()) & set(truth[i].tolist()))
                row.update({"recall@10": round(hit / (K * len(qs)), 4), "p50_ms": round(statistics.median(times), 2),
                            "p95_ms": round(sorted(times)[int(.95 * (len(times) - 1))], 2)})
            except Exception as e:  # a failure is a result
                row["error"] = f"{type(e).__name__}: {e}"[:300]
            finally:
                shutil.rmtree(work, ignore_errors=True)
            print(json.dumps(row), flush=True)
            with (HERE / "results.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
