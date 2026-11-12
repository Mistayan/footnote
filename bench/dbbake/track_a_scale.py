"""Track A at scale: lexical latency, build time and disk for SQLite FTS5 (porter) versus Tantivy (en_stem) over 100k..1M documents.

    bench/.dbenv/Scripts/python.exe -I bench/dbbake/track_a_scale.py --sizes 100000,1000000

Documents are SYNTHETIC: random 150-word spans cut from the real mix-fr-en documents, so word frequencies stay realistic. Queries are
300 real mix-fr-en queries. Quality is not scored (no judgments exist for synthetic documents); the check is that both engines
return overlapping top-10 lists. Results are appended to bench/dbbake/results.jsonl.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import track_a  # noqa: E402


class Lazy:
    def __init__(self, base_docs: list[list[str]], n: int):
        self.base, self.n = base_docs, n

    def __len__(self):
        return self.n

    def items(self):
        rng = random.Random(20261112)
        for i in range(self.n):
            w = rng.choice(self.base)
            s = rng.randrange(0, max(1, len(w) - 150))
            yield f"d{i}", ("", " ".join(w[s:s + 150]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="100000")
    args = ap.parse_args()
    corpus, queries, _ = fetch.load("mix-fr-en", "test")
    base = [(t + " " + x).split() for t, x in corpus.values()]
    qs = list(queries.values())[:300]
    for n in (int(x) for x in args.sizes.split(",")):
        top = {}
        for name in ("sqlite-fts5 porter", "tantivy en_stem"):
            eng = track_a.ENGINES[name]()
            row = {"track": "A-scale", "engine": name, "documents": n, "synthetic": True, "queries": len(qs)}
            try:
                t0 = time.perf_counter()
                eng.build(Lazy(base, n))
                row["build_s"] = round(time.perf_counter() - t0, 1)
                for q in qs[:20]:
                    eng.search(q, 10)
                times, got = [], []
                for q in qs:
                    a = time.perf_counter()
                    got.append(eng.search(q, 10))
                    times.append((time.perf_counter() - a) * 1000)
                top[name] = got
                row.update({"p50_ms": round(statistics.median(times), 2), "p95_ms": round(sorted(times)[int(.95 * (len(times) - 1))], 2),
                            "max_ms": round(max(times), 1), "disk_mb": round(eng.size() / 1e6, 1)})
            except Exception as e:
                row["error"] = f"{type(e).__name__}: {e}"[:300]
            finally:
                shutil.rmtree(eng.dir, ignore_errors=True)
            print(json.dumps(row), flush=True)
            with (HERE / "results.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        if len(top) == 2:
            a, b = top.values()
            ov = statistics.mean(len(set(x) & set(y)) / max(1, len(set(x) | set(y))) for x, y in zip(a, b))
            print(json.dumps({"track": "A-scale", "documents": n, "top10_jaccard_fts5_vs_tantivy": round(ov, 3)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
